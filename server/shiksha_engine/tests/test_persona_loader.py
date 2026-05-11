"""Persona-Loader Tests — Edition-Fallback + Vokabular-Interpolation + Memory."""

from shiksha_engine.models import MemoryEntry, PersonaPrompt
from shiksha_engine.services.persona_loader import load_system_prompt


def test_edition_specific_takes_precedence(db, mira):
    # Generic
    db.add(PersonaPrompt(
        name="tagesausklang", edition="*", version=1,
        system_prompt="GENERIC PROMPT",
    ))
    # KITA-specific (sollte gewinnen)
    db.add(PersonaPrompt(
        name="tagesausklang", edition="kita", version=1,
        system_prompt="KITA PROMPT",
    ))
    db.commit()

    result = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert result is not None
    assert "KITA PROMPT" in result
    assert "GENERIC" not in result


def test_fallback_to_star(db, mira):
    db.add(PersonaPrompt(
        name="kennenlernen", edition="*", version=1,
        system_prompt="GENERIC KENNENLERNEN",
    ))
    db.commit()

    result = load_system_prompt(db, operator=mira, persona="kennenlernen")
    assert result is not None
    assert "GENERIC KENNENLERNEN" in result


def test_returns_none_when_missing(db, mira):
    result = load_system_prompt(db, operator=mira, persona="does-not-exist")
    assert result is None


def test_memory_block_appended(db, mira):
    db.add(PersonaPrompt(
        name="tagesausklang", edition="*", version=1,
        system_prompt="BASE",
    ))
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Mira mag keine Wochenend-Anrufe.",
    ))
    db.commit()

    result = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "BASE" in result
    assert "Mira mag keine Wochenend-Anrufe" in result
    assert "AUS FRÜHEREN GESPRÄCHEN" in result


def test_higher_version_wins(db, mira):
    db.add(PersonaPrompt(
        name="tagesausklang", edition="*", version=1,
        system_prompt="V1",
    ))
    db.add(PersonaPrompt(
        name="tagesausklang", edition="*", version=2,
        system_prompt="V2",
    ))
    db.commit()

    result = load_system_prompt(db, operator=mira, persona="tagesausklang", include_memory=False)
    assert "V2" in result
    assert "V1" not in result
