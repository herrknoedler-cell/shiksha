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
) -> str | None:
    """Lädt den system_prompt für einen Operator und eine Persona.

    Returns None wenn kein Prompt gefunden.
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


def _build_memory_block(db: DBSession, operator: Operator, limit: int = 15) -> str:
    """Baut den Erinnerungs-Block für die letzten N Memory-Einträge."""
    entries = (
        db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.operator_id == operator.id)
            .where(MemoryEntry.edition == operator.edition)
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
