"""Tool-Runtime — Dispatcher für Tool-Use mitten in der Conversation.

Spec: SHIKSHA_TOOL_USE_SPEC.md (Abschnitte 3, 5, 7, 8, 11).

Das Modell ruft Tools auf, diese Runtime führt sie aus, schreibt Audit-
Einträge und liefert das tool_result-Block zurück, das die nächste Anthropic-
Iteration als user-content sieht.

Aufrufpfad:
    chat-router → respond_with_tools() in anthropic_client →
    execute_tool() hier → DB-Write + Audit → tool_result → loop weiter.

Tools schreiben in die übergebene DB-Session (kein eigener Commit).
Der Chat-Router committet am Ende des Multi-Turn-Loops einmal.
Audit-Einträge committen separat (eigene SessionLocal) — bleiben auch
dann erhalten, wenn der Chat-Loop später abbricht.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..db import SessionLocal
from ..models import (
    AuditLog,
    FrictionPoint,
    MemoryEntry,
    Observation,
    Operator,
    Session as ShikshaSession,
)
from ..models.friction import FRICTION_SEVERITIES
from ..models.observation import OBSERVATION_KIND_SUMMARY

log = logging.getLogger("shiksha.tools")


# ===================================================================
# Dedup-Helpers (Spec 7.3 — verhindert Re-Logging desselben Themas)
# ===================================================================

# Deutsche Stopwörter — dünn gehalten, nur die häufigsten Funktionswörter.
# Ziel: dass "Mittwochs Personal knapp" und "Personal Mittwoch knappheit"
# als gleiches Thema erkannt werden, aber "Lukas krank" davon abgegrenzt.
_STOPWORDS = frozenset({
    "der", "die", "das", "den", "dem", "des",
    "ein", "eine", "einer", "eines", "einem", "einen",
    "und", "oder", "aber", "doch", "auch",
    "ist", "war", "sind", "waren", "wird", "werden", "wurde", "wurden",
    "hat", "haben", "hatte", "hatten",
    "kann", "können", "soll", "sollen", "muss", "müssen",
    "in", "im", "an", "am", "auf", "aus", "bei", "mit", "nach", "von", "vom",
    "zu", "zum", "zur", "über", "unter", "vor", "während", "durch", "für",
    "sich", "es", "er", "sie", "wir", "ich", "du", "ihr", "ihn", "ihm",
    "sein", "seine", "seinen", "seiner", "ihre", "ihren", "ihrer",
    "mehr", "als", "noch", "nur", "schon", "wieder", "jetzt", "heute",
    "dass", "wenn", "wie", "weil", "obwohl", "damit",
    "nicht", "kein", "keine", "keinen", "keiner",
    "etwa", "ungefähr", "viel", "viele", "alle", "jeder",
})

# Zwei-Linien-Dedup:
#   1. Bigram-Match: ≥2 geteilte 2-Wort-Phrasen → starkes Themen-Signal,
#      auch wenn Texte ansonsten anders formuliert sind.
#   2. Jaccard auf Unigrammen: erfasst überlappende Wort-Mengen, wenn
#      Bigram-Match nicht greift (z.B. bei sehr kurzen Texten).
#
# Schwellenwerte sind absichtlich tief — Re-Logging in derselben Session
# ist fast immer das selbe Thema, auch wenn paraphrasiert.
_JACCARD_THRESHOLD_FRICTION = 0.20
_JACCARD_THRESHOLD_OBSERVATION = 0.25
_MIN_SHARED_BIGRAMS = 2


def _tokenize(text: str) -> list[str]:
    """Worte extrahieren, lowercase, Stopwords raus, kurze Worte raus.
    Liste statt Set — wir brauchen Reihenfolge für Bigramme."""
    words = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _texts_similar(
    new_text: str, existing_text: str,
    jaccard_threshold: float,
) -> bool:
    """True wenn die zwei Texte dasselbe Thema behandeln."""
    new_tokens = _tokenize(new_text)
    if len(new_tokens) < 2:
        return False
    existing_tokens = _tokenize(existing_text)
    if len(existing_tokens) < 2:
        return False

    # Linie 1: Bigram-Match
    shared = _bigrams(new_tokens) & _bigrams(existing_tokens)
    if len(shared) >= _MIN_SHARED_BIGRAMS:
        return True

    # Linie 2: Jaccard-Schwellenwert auf Unigrammen
    if _jaccard(set(new_tokens), set(existing_tokens)) >= jaccard_threshold:
        return True

    return False


def _find_similar_friction(
    db: DBSession, session_id: str, new_text: str,
) -> FrictionPoint | None:
    existing = db.execute(
        select(FrictionPoint)
        .where(FrictionPoint.session_id == session_id)
        .where(FrictionPoint.deleted_at.is_(None))
    ).scalars().all()
    for fp in existing:
        if _texts_similar(new_text, fp.text, _JACCARD_THRESHOLD_FRICTION):
            return fp
    return None


def _find_similar_observation(
    db: DBSession, session_id: str, new_text: str,
) -> Observation | None:
    existing = db.execute(
        select(Observation)
        .where(Observation.session_id == session_id)
        .where(Observation.kind == "observation")
        .where(Observation.deleted_at.is_(None))
    ).scalars().all()
    for obs in existing:
        if _texts_similar(new_text, obs.text, _JACCARD_THRESHOLD_OBSERVATION):
            return obs
    return None


# ===================================================================
# Session-State-Spiegel (gibt dem Modell direktes Feedback)
# ===================================================================

def _session_state_summary(db: DBSession, session_id: str) -> dict:
    """Kurze Übersicht: was hat das Modell in dieser Session schon geloggt?

    Wird jedem tool_result beigegeben. Das Modell sieht damit explizit, was
    es schon kennt — und wiederholt nicht. Stärker als jede Persona-Anweisung
    oder Ähnlichkeits-Heuristik, weil das Modell die Information direkt im
    Kontext hat.

    Texte werden auf 80 Zeichen gekürzt — reicht zum Wiedererkennen, hält
    den Token-Verbrauch im Loop niedrig.
    """
    fricts = db.execute(
        select(FrictionPoint.text)
        .where(FrictionPoint.session_id == session_id)
        .where(FrictionPoint.deleted_at.is_(None))
    ).scalars().all()
    obs = db.execute(
        select(Observation.text)
        .where(Observation.session_id == session_id)
        .where(Observation.kind == "observation")
        .where(Observation.deleted_at.is_(None))
    ).scalars().all()
    summaries = db.execute(
        select(Observation.text)
        .where(Observation.session_id == session_id)
        .where(Observation.kind == OBSERVATION_KIND_SUMMARY)
        .where(Observation.deleted_at.is_(None))
    ).scalars().all()
    mems = db.execute(
        select(MemoryEntry.text)
        .where(MemoryEntry.source_session_id == session_id)
        .where(MemoryEntry.deleted_at.is_(None))
    ).scalars().all()

    def _trim(items):
        return [t[:80] + ("…" if len(t) > 80 else "") for t in items]

    return {
        "frictions_in_session":   _trim(fricts),
        "observations_in_session": _trim(obs),
        "memories_proposed_in_session": _trim(mems),
        "session_summarized":     bool(summaries),
    }


# ===================================================================
# Tool-Definition
# ===================================================================

ToolHandler = Callable[
    [BaseModel, Operator, ShikshaSession, DBSession],
    dict,
]


@dataclass
class ToolDefinition:
    """Was eine Tool-Registrierung braucht."""

    name: str
    description: str                # geht an Anthropic
    input_model: type[BaseModel]    # Pydantic-Schema für Argumente
    handler: ToolHandler
    visibility_hint: str            # für Persona-Prompt-Doku
    target_type: str                # für AuditLog.target_type
    edition_scope: list[str] = field(default_factory=lambda: ["*"])
    # ["*"] = alle Editions, sonst Liste konkreter Edition-Slugs


TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(tool: ToolDefinition) -> None:
    if tool.name in TOOL_REGISTRY:
        raise RuntimeError(f"Tool already registered: {tool.name}")
    TOOL_REGISTRY[tool.name] = tool


def list_tools_for_anthropic(operator: Operator) -> list[dict[str, Any]]:
    """Liefert die Tool-Liste im Anthropic-API-Format für einen Operator.

    Edition-aware: nur Tools mit `*` oder mit der Edition des Operators.
    """
    result = []
    for tool in TOOL_REGISTRY.values():
        if "*" not in tool.edition_scope and operator.edition not in tool.edition_scope:
            continue
        result.append({
            "name":         tool.name,
            "description":  tool.description,
            "input_schema": tool.input_model.model_json_schema(),
        })
    return result


# ===================================================================
# Dispatcher
# ===================================================================

class ToolPermissionError(Exception):
    """Operator darf dieses Tool nicht ausführen, oder nicht in diesem Skopus."""


def execute_tool(
    name: str,
    args: dict[str, Any],
    tool_use_id: str,
    operator: Operator,
    shiksha_session: ShikshaSession,
    db: DBSession,
) -> dict[str, Any]:
    """Führt ein Tool aus, gibt das tool_result-Block zurück.

    Das Block-Format folgt der Anthropic-Spec:
        {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": bool?}

    Bei Fehlern wird IMMER ein Block zurückgegeben — der Loop läuft weiter,
    das Modell sieht den Fehler und entscheidet selbst.
    """
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return _error_result(tool_use_id, f"Unknown tool: {name}")

    # Edition-Skopus prüfen
    if "*" not in tool.edition_scope and operator.edition not in tool.edition_scope:
        _audit_tool_call(
            operator=operator,
            tool_name=name,
            args=args,
            success=False,
            target_type=tool.target_type,
            target_id=None,
            error=f"Edition '{operator.edition}' not allowed for tool '{name}'",
        )
        return _error_result(
            tool_use_id,
            f"Tool '{name}' not available for this edition",
        )

    # Argument-Validierung via Pydantic
    try:
        validated = tool.input_model(**args)
    except ValidationError as e:
        _audit_tool_call(
            operator=operator,
            tool_name=name,
            args=args,
            success=False,
            target_type=tool.target_type,
            target_id=None,
            error=f"Invalid arguments: {e.errors()}",
        )
        return _error_result(tool_use_id, _human_validation_error(e))

    # Tool ausführen
    try:
        result = tool.handler(validated, operator, shiksha_session, db)
        # Handler darf 'target_id' im Ergebnis setzen
        target_id = str(result.get("id") or result.get("memory_id") or result.get("friction_id") or result.get("observation_id") or result.get("summary_id") or "")
        _audit_tool_call(
            operator=operator,
            tool_name=name,
            args=validated.model_dump(),
            success=True,
            target_type=tool.target_type,
            target_id=target_id or None,
            error=None,
        )
        return _success_result(tool_use_id, result)
    except ToolPermissionError as e:
        _audit_tool_call(
            operator=operator,
            tool_name=name,
            args=args,
            success=False,
            target_type=tool.target_type,
            target_id=None,
            error=f"Permission denied: {e}",
        )
        return _error_result(tool_use_id, f"Permission denied: {e}")
    except Exception as e:
        log.exception("Tool '%s' raised", name)
        _audit_tool_call(
            operator=operator,
            tool_name=name,
            args=args,
            success=False,
            target_type=tool.target_type,
            target_id=None,
            error=str(e),
        )
        return _error_result(tool_use_id, "Tool execution failed")


# ===================================================================
# Result-Helpers
# ===================================================================

def _success_result(tool_use_id: str, payload: dict) -> dict:
    return {
        "type":        "tool_result",
        "tool_use_id": tool_use_id,
        "content":     json.dumps(payload, ensure_ascii=False, default=_json_default),
    }


def _error_result(tool_use_id: str, message: str) -> dict:
    return {
        "type":        "tool_result",
        "tool_use_id": tool_use_id,
        "content":     message,
        "is_error":    True,
    }


def _human_validation_error(e: ValidationError) -> str:
    """Pydantic-Fehler in eine kurze, modell-verständliche Form bringen."""
    parts = []
    for err in e.errors()[:3]:
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "invalid")
        parts.append(f"{loc}: {msg}")
    return "Invalid arguments — " + "; ".join(parts)


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Type {type(value)} not JSON serializable")


# ===================================================================
# Audit-Logging
# ===================================================================

def _audit_tool_call(
    *,
    operator: Operator,
    tool_name: str,
    args: dict,
    success: bool,
    target_type: str,
    target_id: str | None,
    error: str | None,
) -> None:
    """Eigene DB-Session — Audit überlebt Rollback des Chat-Loops."""
    try:
        with SessionLocal() as db:
            db.add(AuditLog(
                actor_id=operator.id,
                actor_role=operator.role,
                action=f"tool.{tool_name}.{'ok' if success else 'fail'}",
                target_type=target_type,
                target_id=target_id,
                diff={"args": args, "error": error} if not success else {"args": args},
                request_path=None,
                request_method=None,
                ip_address=None,
            ))
            db.commit()
    except Exception:
        log.exception("Audit-Log für Tool-Call '%s' fehlgeschlagen", tool_name)


# ===================================================================
# Pydantic-Schemas für die vier Core-Tools
# ===================================================================

class LogObservationArgs(BaseModel):
    """Spec 3.1 — neutrale Beobachtung über Mira's Welt."""

    text: str = Field(
        min_length=1, max_length=500,
        description="Die Beobachtung als kompletter Satz im Indikativ. Max 500 Zeichen.",
    )
    category: str | None = Field(
        default=None,
        description="personal | familie | kind | finanzen | raum | rhythmus | sonst",
    )


class LogFrictionArgs(BaseModel):
    """Spec 3.2 — wiederkehrende Reibung markieren."""

    text: str = Field(
        min_length=1, max_length=500,
        description="Die Reibung als Aussage. Idealerweise mit Frequenz-Marker.",
    )
    severity: str | None = Field(
        default=None,
        description="leicht | mittel | belastend",
    )
    first_observed_at: date | None = Field(
        default=None,
        description="Datum (ISO YYYY-MM-DD), wenn rückwirkend datierbar.",
    )


class AddMemoryArgs(BaseModel):
    """Spec 3.3 — Memory-Kandidat anlegen (Status: proposed)."""

    text: str = Field(
        min_length=1, max_length=500,
        description="Erinnerung als faktischer Satz in dritter Person.",
    )


class SaveDaySummaryArgs(BaseModel):
    """Spec 3.4 — Tageszusammenfassung als Observation mit kind='summary'."""

    summary: str = Field(
        min_length=1, max_length=1000,
        description="Zwei bis drei Sätze in Mira-Stimme, nicht in technischer Sprache.",
    )
    mood: str | None = Field(
        default=None,
        description="klar | belastet | aufgekratzt | leer | dankbar | sonst",
    )


# ===================================================================
# Handler-Implementierungen
# ===================================================================

def _handle_log_observation(
    args: LogObservationArgs,
    operator: Operator,
    shiksha_session: ShikshaSession,
    db: DBSession,
) -> dict:
    duplicate = _find_similar_observation(db, shiksha_session.id, args.text)
    if duplicate is not None:
        return {
            "observation_id":  duplicate.id,
            "logged":          False,
            "reason":          "duplicate_in_session",
            "existing_text":   duplicate.text,
            "session_state":   _session_state_summary(db, shiksha_session.id),
        }

    metadata: dict = {}
    if args.category:
        metadata["category"] = args.category

    obs = Observation(
        session_id=shiksha_session.id,
        edition=operator.edition,
        kind="observation",
        text=args.text,
        metadata_=metadata,
    )
    db.add(obs)
    db.flush()
    return {
        "observation_id": obs.id,
        "logged":         True,
        "session_state":  _session_state_summary(db, shiksha_session.id),
    }


def _handle_log_friction(
    args: LogFrictionArgs,
    operator: Operator,
    shiksha_session: ShikshaSession,
    db: DBSession,
) -> dict:
    if args.severity and args.severity not in FRICTION_SEVERITIES:
        raise ValueError(
            f"severity must be one of {FRICTION_SEVERITIES}, got '{args.severity}'"
        )

    duplicate = _find_similar_friction(db, shiksha_session.id, args.text)
    if duplicate is not None:
        return {
            "friction_id":    duplicate.id,
            "logged":         False,
            "reason":         "duplicate_in_session",
            "existing_text":  duplicate.text,
            "session_state":  _session_state_summary(db, shiksha_session.id),
        }

    fp = FrictionPoint(
        session_id=shiksha_session.id,
        edition=operator.edition,
        text=args.text,
        severity=args.severity,
        first_observed_at=args.first_observed_at,
        resolved=False,
    )
    db.add(fp)
    db.flush()
    return {
        "friction_id":   fp.id,
        "logged":        True,
        "session_state": _session_state_summary(db, shiksha_session.id),
    }


def _handle_add_memory(
    args: AddMemoryArgs,
    operator: Operator,
    shiksha_session: ShikshaSession,
    db: DBSession,
) -> dict:
    mem = MemoryEntry(
        operator_id=operator.id,
        edition=operator.edition,
        text=args.text,
        source_session_id=shiksha_session.id,
        status="proposed",  # Mira muss bestätigen, bevor 'active'
    )
    db.add(mem)
    db.flush()
    return {
        "memory_id":     mem.id,
        "status":        "proposed",
        "session_state": _session_state_summary(db, shiksha_session.id),
    }


def _handle_save_day_summary(
    args: SaveDaySummaryArgs,
    operator: Operator,
    shiksha_session: ShikshaSession,
    db: DBSession,
) -> dict:
    # Hard-Limit: maximal eine Summary pro Session. Wenn schon eine da
    # ist, sagen wir das dem Modell — es soll nicht nochmal versuchen.
    existing = db.execute(
        select(Observation)
        .where(Observation.session_id == shiksha_session.id)
        .where(Observation.kind == OBSERVATION_KIND_SUMMARY)
        .where(Observation.deleted_at.is_(None))
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "summary_id":    existing.id,
            "saved":         False,
            "reason":        "already_summarized_in_session",
            "existing_text": existing.text,
            "session_state": _session_state_summary(db, shiksha_session.id),
        }

    metadata: dict = {}
    if args.mood:
        metadata["mood"] = args.mood

    obs = Observation(
        session_id=shiksha_session.id,
        edition=operator.edition,
        kind=OBSERVATION_KIND_SUMMARY,
        text=args.summary,
        metadata_=metadata,
    )
    db.add(obs)
    db.flush()
    return {
        "summary_id":    obs.id,
        "saved":         True,
        "session_state": _session_state_summary(db, shiksha_session.id),
    }


# ===================================================================
# Tool-Registrierung
# ===================================================================

register_tool(ToolDefinition(
    name="log_observation",
    description=(
        "Halte eine konkrete, neutrale Beobachtung über die Welt der "
        "Operator-Person fest. Nur für Faktisches, das später relevant sein "
        "könnte. Nicht für Gefühle oder Vermutungen. Sparsam nutzen — eine "
        "Session ohne log_observation ist eine gute Session, wenn der Inhalt "
        "es nicht verlangt."
    ),
    input_model=LogObservationArgs,
    handler=_handle_log_observation,
    visibility_hint="invisible",
    target_type="observation",
))

register_tool(ToolDefinition(
    name="log_friction",
    description=(
        "Markiere eine wiederkehrende Reibung. Nur einsetzen, wenn ein Muster "
        "sichtbar ist (Frequenz benannt oder im Memory bestätigt) — nicht beim "
        "ersten Auftauchen. Eine einzelne schlechte Mittwoch ist noch kein "
        "Friction Point.\n\n"
        "WICHTIG: PRO SESSION GENAU EINMAL PRO THEMA. Wenn das gleiche Thema "
        "im Gespräch weiter ausgebreitet wird (mehr Details, neue Aspekte), "
        "ist das immer noch DIESELBE Reibung — kein neuer log_friction-Call. "
        "Der Server lehnt Wiederholungen ab; richte Dich schon vorher danach. "
        "Wenn eine Reibung strukturell wirkt (\"diese KITA hat keine "
        "Vertretungsregelung\", nicht nur \"heute war's knapp\"), erwäge "
        "zusätzlich add_memory, damit Du es nächstes Mal weißt."
    ),
    input_model=LogFrictionArgs,
    handler=_handle_log_friction,
    visibility_hint="microsignal_50pct",
    target_type="friction_point",
))

register_tool(ToolDefinition(
    name="add_memory",
    description=(
        "Lege eine bleibende Erinnerung über die Person oder ihre Welt an, "
        "die zukünftige Sessions als Kontext laden. Status ist 'proposed' — "
        "die Person bestätigt manuell, bevor sie aktiv wird.\n\n"
        "TYPISCHE AUSLÖSER:\n"
        "- Eine wiederkehrende Reibung hat strukturelle Ursachen, die Du in "
        "  zukünftigen Sessions kennen solltest (\"diese KITA hat keine "
        "  externe Vertretungsregelung\", \"die Trägerin trägt allein "
        "  Personalverantwortung für fünf Mitarbeiterinnen\").\n"
        "- Eine bleibende Tatsache über die Person, ihr Team, ihre Familie "
        "  oder Organisation wird beiläufig erwähnt.\n"
        "- Wenn Du schon einen log_friction zu einem strukturellen Thema "
        "  abgesetzt hast, ist ein paralleles add_memory mit der strukturellen "
        "  Form fast immer richtig (Friction = akute Reibung, Memory = "
        "  bleibende Tatsache).\n\n"
        "Sparsam, aber nicht zaghaft — drei pro Session ist viel, NULL ist "
        "verdächtig, wenn substanzielle Themen besprochen wurden."
    ),
    input_model=AddMemoryArgs,
    handler=_handle_add_memory,
    visibility_hint="microsignal_30pct",
    target_type="memory_entry",
))

register_tool(ToolDefinition(
    name="save_day_summary",
    description=(
        "Halte eine Tageszusammenfassung mitten in der Session fest, wenn "
        "die Operator-Person selbst zusammenfasst oder eine starke Verdichtung "
        "gehört wird. Nicht reflexartig am Ende — die Session-Close-Routine "
        "macht das zuverlässiger."
    ),
    input_model=SaveDaySummaryArgs,
    handler=_handle_save_day_summary,
    visibility_hint="invisible_until_recap",
    target_type="observation",
))


# ===================================================================
# Diagnostik (für Tests + /dev/tools-Endpoint später)
# ===================================================================

def registry_snapshot() -> list[dict]:
    """Lesbare Übersicht aller registrierten Tools."""
    return [
        {
            "name":          t.name,
            "description":   t.description,
            "visibility":    t.visibility_hint,
            "target_type":   t.target_type,
            "edition_scope": t.edition_scope,
            "input_schema":  t.input_model.model_json_schema(),
        }
        for t in TOOL_REGISTRY.values()
    ]
