"""Insights-Extractor — Backstage-LLM-Call beim Session-Close.

Konzept (siehe SHIKSHA_RESPONSE_ENGINE.md + TAGESAUSKLANG_KONTEXTUELLE_REAKTION.md):

Beim Session-Close läuft ein zweiter Anthropic-Call mit dem kompletten
Transkript + Sonder-Prompt. Anthropic gibt **strukturiertes JSON** zurück:

    {
      "summary": "<ein Satz, was die Person heute beschäftigt hat>",
      "observations": ["<konkrete Beobachtung 1>", ...],
      "frictions":    ["<offene Stelle / Unsicherheit 1>", ...],
      "memory_candidates": ["<Erinnerung, die für späteren Wiederbeginn wichtig ist>", ...]
    }

Der Server parst das, persistiert:
  - summary           → sessions.summary
  - observations[]    → observations-Tabelle
  - frictions[]       → friction_points-Tabelle
  - memory_candidates → memory_entries (sind verfügbar für nächsten Session-Prompt)

Die Trägerin sieht von all dem nichts — das ist Backstage. Was sie sieht
ist die nächste Session, in der SHIKSHA "weiß, wie es ihr gestern ging".
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from anthropic import Anthropic
from sqlalchemy.orm import Session as DBSession

from ..models import FrictionPoint, MemoryEntry, Message, Observation, Session
from ..settings import get_settings

logger = logging.getLogger("shiksha.insights")


EXTRACTION_SYSTEM_PROMPT = """Du bist eine ruhige Beobachterin, die für SHIKSHA aus einem Gespräch
das Wesentliche herauszieht. Verwende keine technische Sprache.
Schreibe wie eine kluge Notiz, die später jemand anders lesen wird.

Du analysierst ein Tagesausklang- oder Kennenlern-Gespräch und gibst
GENAU dieses JSON-Format zurück (keine Erklärung davor oder danach):

{
  "summary": "<EIN Satz, was die Person heute beschäftigt hat. Ihre Stimme nicht imitieren, aber ihre Worte aufnehmen wenn sie eindrücklich sind.>",
  "observations": [
    "<konkrete Beobachtung 1, max 1 Satz>",
    "<konkrete Beobachtung 2, max 1 Satz>"
  ],
  "frictions": [
    "<offene Stelle / Unsicherheit / wo es geklemmt hat, max 1 Satz>"
  ],
  "memory_candidates": [
    "<Erinnerung, die für späteren Wiederbeginn wichtig ist — was SHIKSHA sich merken sollte. Max 1 Satz, in dritter Person formuliert.>"
  ]
}

REGELN:
- Maximal 3 Einträge pro Liste. Lieber 1 gut als 3 mittelmäßig.
- Wenn keine Observation/Friction/Memory passt: leere Liste [].
- summary IMMER ein Satz (kein Bullet, kein Absatz).
- Niemals technische Sprache: nicht Analyse, Audit, Workflow, Daten, KI, Backend, API.
- Niemals "Ich habe analysiert / erkannt / erfasst".

Antworte AUSSCHLIESSLICH mit dem JSON-Objekt — keine Markdown-Codeblöcke, kein Vor-/Nachtext.
"""


@dataclass
class ExtractedInsights:
    summary:           str            = ""
    observations:      list[str]      = field(default_factory=list)
    frictions:         list[str]      = field(default_factory=list)
    memory_candidates: list[str]      = field(default_factory=list)
    raw_response:      str            = ""
    error:             str | None     = None


# ===================================================================
# Anthropic-Aufruf
# ===================================================================

def _call_anthropic(transcript: str) -> str:
    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=600,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Hier das Transkript:\n\n{transcript}\n\n"
                       f"Gib das JSON-Objekt zurück, sonst nichts."
        }],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def _build_transcript(messages: list[Message]) -> str:
    """Format: 'User: ...' / 'SHIKSHA: ...' alternierend, chronologisch."""
    parts = []
    for m in messages:
        role = "User" if m.role == "user" else "SHIKSHA"
        parts.append(f"{role}: {m.content}")
    return "\n".join(parts)


def _parse_json(raw: str) -> dict | None:
    """Robust gegen Markdown-Codeblöcke, führende/trailing Texte."""
    # Direkt versuchen
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Codeblock entfernen
    stripped = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    # Erstes {...}-Block extrahieren
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ===================================================================
# Hauptfunktion
# ===================================================================

def extract_and_persist(
    db: DBSession,
    session: Session,
    messages: list[Message],
) -> ExtractedInsights:
    """Ruft Anthropic auf, parst JSON, persistiert in DB.

    Idempotent für `summary` — bei Wiederholung wird summary überschrieben.
    `observations`, `frictions`, `memory_candidates` werden APPENDED — bei
    wiederholtem Aufruf entstehen Duplikate, der Aufrufer (Endpoint) sollte
    deshalb idempotent-Logic vorhalten falls nötig.
    """
    if not messages:
        return ExtractedInsights(error="empty transcript")

    transcript = _build_transcript(messages)

    try:
        raw = _call_anthropic(transcript)
    except Exception as e:
        logger.exception("Anthropic insights call failed")
        return ExtractedInsights(error=f"anthropic_call_failed: {e}", raw_response="")

    parsed = _parse_json(raw)
    if parsed is None:
        return ExtractedInsights(
            error="json_parse_failed",
            raw_response=raw[:500],
        )

    result = ExtractedInsights(
        summary=str(parsed.get("summary", "")).strip(),
        observations=[
            str(x).strip() for x in (parsed.get("observations") or []) if str(x).strip()
        ][:3],
        frictions=[
            str(x).strip() for x in (parsed.get("frictions") or []) if str(x).strip()
        ][:3],
        memory_candidates=[
            str(x).strip() for x in (parsed.get("memory_candidates") or []) if str(x).strip()
        ][:3],
        raw_response=raw[:500],
    )

    # Persistieren
    if result.summary:
        session.summary = result.summary
        # insights-Spalte: Snapshot des kompletten Extraction-Outputs
        session.insights = {
            "summary": result.summary,
            "observations": result.observations,
            "frictions": result.frictions,
            "memory_candidates": result.memory_candidates,
        }
        db.add(session)

    for obs_text in result.observations:
        db.add(Observation(
            session_id=session.id,
            edition=session.edition,
            kind="insight_extraction",
            text=obs_text,
            metadata_={"source": "session_close_extractor"},
        ))

    for fric_text in result.frictions:
        db.add(FrictionPoint(
            session_id=session.id,
            edition=session.edition,
            where_label="extracted",
            text=fric_text,
        ))

    for mem_text in result.memory_candidates:
        db.add(MemoryEntry(
            operator_id=session.operator_id,
            edition=session.edition,
            text=mem_text,
            source_session_id=session.id,
        ))

    db.flush()
    return result
