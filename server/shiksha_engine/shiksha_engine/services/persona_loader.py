"""Persona-Loader — lädt system_prompts aus DB mit Edition-Fallback.

Auflösungs-Regel:
  1. Suche persona_prompts mit (name=<persona>, edition=<edition>) → höchste version
  2. Fallback: (name=<persona>, edition="*") → höchste version
  3. Falls nichts: None → Aufrufer entscheidet (HTTPException)

Plus: hängt einen Memory-Block aus memory_entries an, gefiltert nach
operator_id und edition. Plus: hängt edition-spezifisches Vokabular aus
EditionConfig an (Operator-Rolle, Org-Wort, …).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..models import MemoryEntry, Operator, PersonaPrompt
from .edition_config import get_edition_config


def load_system_prompt(
    db: DBSession,
    *,
    operator: Operator,
    persona: str,
    include_memory: bool = True,
    include_tools_hint: bool = True,
) -> str | None:
    """Lädt den system_prompt für einen Operator und eine Persona.

    Returns None wenn kein Prompt gefunden.

    Parameter:
      include_memory     — hängt aktive Memory-Einträge an (Default ja).
      include_tools_hint — hängt den Zahnarzt-Regel-Block für Tool-Use an
                           (Default ja). Auf False setzen z.B. bei der
                           Insights-Extraktion in /chat/close, wo kein Tool-Use
                           stattfindet.
    """
    # 1. Versuche edition-spezifisch
    edition_specific = (
        db.execute(
            select(PersonaPrompt)
            .where(PersonaPrompt.name == persona)
            .where(PersonaPrompt.edition == operator.edition)
            .order_by(PersonaPrompt.version.desc())
            .limit(1)
        )
        .scalar_one_or_none()
    )
    if edition_specific:
        base = edition_specific.system_prompt
    else:
        # 2. Fallback zu cross-edition (edition="*")
        cross = (
            db.execute(
                select(PersonaPrompt)
                .where(PersonaPrompt.name == persona)
                .where(PersonaPrompt.edition == "*")
                .order_by(PersonaPrompt.version.desc())
                .limit(1)
            )
            .scalar_one_or_none()
        )
        if cross is None:
            return None
        base = cross.system_prompt

    # Vokabular-Token aus EditionConfig ersetzen ({{operator_role}}, {{org_word}}, ...)
    cfg = get_edition_config(operator.edition)
    if cfg:
        base = _interpolate_vocab(base, cfg)

    # Tool-Hinweis (Zahnarzt-Regel) anhängen
    if include_tools_hint:
        tools_block = _build_tools_hint(operator)
        if tools_block:
            base = f"{base}\n\n{tools_block}"

    # Memory-Block anhängen
    if include_memory:
        memory_block = _build_memory_block(db, operator)
        if memory_block:
            base = f"{base}\n\n{memory_block}"

    return base


def _interpolate_vocab(prompt: str, cfg: dict) -> str:
    """Ersetzt Edition-Vokabular-Platzhalter im System-Prompt.

    Erlaubte Platzhalter: {{operator_role}}, {{org_word}}, {{member_word}}, ...
    """
    vocab = cfg.get("vocabulary", {})
    result = prompt
    for key, value in vocab.items():
        if isinstance(value, str):
            result = result.replace(f"{{{{{key}}}}}", value)
    return result


def _build_tools_hint(operator: Operator) -> str:
    """Hängt den Zahnarzt-Regel-Block plus eine knappe Tool-Liste an.

    Erfüllt SHIKSHA_TOOL_USE_SPEC.md Abschnitte 1, 4, 5, 6.

    WICHTIG: Dies ist die TEXTUELLE Anweisung an das Modell, wie es Tools
    gebrauchen soll. Die Tool-DEFINITIONEN (JSON-Schemas) kommen separat
    über den Anthropic-Parameter `tools=[...]` aus list_tools_for_anthropic.
    Beide Wege ergänzen sich: tools= gibt das Was, dieser Block das Wann.
    """
    # Lokaler Import — vermeidet Zyklus mit tools_runtime, das im Hot-Path
    # vielleicht nicht immer verfügbar ist (z.B. in isolierten Tests).
    try:
        from .tools_runtime import TOOL_REGISTRY
    except ImportError:
        return ""

    # Edition-Filter — nur Tools die für diesen Operator gelten.
    available = [
        t for t in TOOL_REGISTRY.values()
        if "*" in t.edition_scope or operator.edition in t.edition_scope
    ]
    if not available:
        return ""

    tool_names = ", ".join(t.name for t in available)

    return f"""WERKZEUGE ZU DEINER VERFÜGUNG: {tool_names}.

Sie sind keine Pflicht. Nutze sie sparsam, wenn ein Werkzeug das Gespräch
oder zukünftige Gespräche substanziell besser macht. Eine Session ohne
einen einzigen Werkzeug-Einsatz ist eine gute Session, wenn der Inhalt es
nicht verlangt.

Heuristik nach Modus:
- PRÄSENZ: fast nie. Wenn die Person ausatmet, schweigst Du.
- FOKUS: log_observation, wenn ein konkretes, NEUES Faktum auftaucht, das
  später wieder relevant sein könnte.
- VERDICHTEN: hier liegt der Schwerpunkt — log_friction und add_memory.
  log_friction NUR wenn ein Muster sichtbar ist (Frequenz benannt oder
  schon im Memory bestätigt), nicht beim ersten Auftauchen.
- AUSKLANG: sparsam. save_day_summary nur, wenn die Person selbst
  zusammenfasst.

WICHTIG — Wiederholungen vermeiden:
- Wenn Du in dieser Session schon eine Reibung zum selben Thema geloggt
  hast, logge sie nicht noch einmal. Das gleiche Thema durch das Gespräch
  hindurch ist dieselbe Reibung — nicht eine neue pro Mira-Nachricht.
  Der Server wird Duplikate erkennen und Dir das mitteilen; richte Dich
  schon vorher danach.
- log_observation ist nur für neue, konkrete Fakten — nicht für Paraphrasen
  dessen, was die Person gerade gesagt hat. „Die Person arbeitet in der
  Gruppe Sommer" ist keine Beobachtung, das ist Wiedergabe.

WICHTIG — Friction vs. Memory:
add_memory ist Dein Werkzeug für bleibende Tatsachen über die Person und
ihre Welt. Wenn ein Friction-Punkt strukturell wirkt — nicht „heute war
Mittwoch schwer", sondern „Mittwoche sind strukturell schwer hier", oder
„diese KITA hat keine externe Vertretungsregelung" — dann gehört das
zusätzlich als Memory festgehalten, damit Du es in zukünftigen Sessions
weißt. Friction ist die akute Reibung, Memory die bleibende Tatsache.
Beide ergänzen sich.

UNSICHTBARKEIT — Zahnarzt-Regel:
Wenn Du ein Werkzeug einsetzt, sprich nicht darüber. Niemals Werkzeug-Namen
nennen. Niemals "Ich speichere das jetzt", "Ich logge das" oder ähnliche
technische Formulierungen. Niemals Quittungen.

In seltenen Fällen — etwa wenn Du eine wichtige Erinnerung angelegt hast —
darfst Du ein sehr kurzes "Notiert.", "Das nehme ich mit." oder "Behalte
ich." in Deine Antwort einbetten, als natürlichen Bestandteil. Nicht als
UI-Quittung. Nicht jedes Mal."""


def _build_memory_block(db: DBSession, operator: Operator, limit: int = 15) -> str:
    """Baut den Erinnerungs-Block für die letzten N Memory-Einträge.

    WICHTIG: Nur status='active' und non-deleted Einträge gehen in den Prompt.
    Proposed-Einträge (von Inline-Tool-Calls) sind unsichtbar, bis die
    Operator-Person sie via /memory/{id}/confirm bestätigt.
    """
    entries = (
        db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.operator_id == operator.id)
            .where(MemoryEntry.edition == operator.edition)
            .where(MemoryEntry.status == "active")
            .where(MemoryEntry.deleted_at.is_(None))
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    if not entries:
        return ""

    lines = [f"- {e.text}" for e in reversed(entries)]  # älteste zuerst
    return "AUS FRÜHEREN GESPRÄCHEN HAST DU DIR FOLGENDES GEMERKT:\n" + "\n".join(lines)
