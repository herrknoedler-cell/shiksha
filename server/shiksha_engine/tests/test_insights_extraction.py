"""Insights-Extraction Tests — mit Anthropic-Mock."""

from unittest.mock import patch

import pytest

from shiksha_engine.models import FrictionPoint, MemoryEntry, Message, Observation, Session
from shiksha_engine.services import insights_extractor


@pytest.fixture
def session_with_messages(db, mira):
    s = Session(
        id="ses_extract_1",
        operator_id=mira.id,
        org_id=mira.org_id,
        edition="kita",
        persona="tagesausklang",
    )
    db.add(s)
    db.flush()

    msgs = [
        Message(session_id=s.id, role="user",      content="Heute war Lukas zurück nach drei Tagen Fieber."),
        Message(session_id=s.id, role="assistant", content="Schön, dass er wieder da ist."),
        Message(session_id=s.id, role="user",      content="Aber Kerstin war krank und ich wusste nicht ob der Eltern-Push raus ging."),
        Message(session_id=s.id, role="assistant", content="Das halten wir als offene Stelle fest.", mode="VERDICHTEN"),
    ]
    for m in msgs:
        db.add(m)
    db.commit()
    return s, msgs


def test_parse_clean_json():
    raw = '{"summary": "Mira war heute belastet.", "observations": ["Lukas zurück."], "frictions": [], "memory_candidates": []}'
    result = insights_extractor._parse_json(raw)
    assert result is not None
    assert result["summary"] == "Mira war heute belastet."


def test_parse_with_codeblock():
    raw = '```json\n{"summary": "ok", "observations": [], "frictions": [], "memory_candidates": []}\n```'
    result = insights_extractor._parse_json(raw)
    assert result["summary"] == "ok"


def test_parse_with_extra_text():
    raw = 'Hier ist das JSON:\n\n{"summary": "passt"}\n\nDas war\'s.'
    result = insights_extractor._parse_json(raw)
    assert result is not None
    assert result["summary"] == "passt"


def test_extract_and_persist_happy_path(db, mira, session_with_messages):
    session, messages = session_with_messages

    mock_response = (
        '{'
        '"summary": "Mira war heute zwischen Lukas-Rückkehr und Kerstin-Ausfall.",'
        '"observations": ["Lukas wieder da nach 3 Tagen Fieber."],'
        '"frictions": ["Unsicher ob Eltern-Push raus ging."],'
        '"memory_candidates": ["Mira merkt sich Eltern-Push als Reibungspunkt."]'
        '}'
    )

    with patch.object(insights_extractor, "_call_anthropic", return_value=mock_response):
        result = insights_extractor.extract_and_persist(db, session, messages)

    assert result.error is None
    assert "Lukas-Rückkehr" in result.summary
    assert len(result.observations) == 1
    assert len(result.frictions) == 1
    assert len(result.memory_candidates) == 1

    # Persistiert?
    db.refresh(session)
    assert session.summary.startswith("Mira war heute")

    obs = db.query(Observation).filter_by(session_id=session.id).all()
    assert len(obs) == 1

    fric = db.query(FrictionPoint).filter_by(session_id=session.id).all()
    assert len(fric) == 1

    mem = db.query(MemoryEntry).filter_by(operator_id=mira.id, source_session_id=session.id).all()
    assert len(mem) == 1


def test_extract_handles_parse_failure(db, mira, session_with_messages):
    session, messages = session_with_messages

    with patch.object(insights_extractor, "_call_anthropic", return_value="not json at all"):
        result = insights_extractor.extract_and_persist(db, session, messages)

    assert result.error == "json_parse_failed"
    # Session bleibt ohne Summary
    db.refresh(session)
    assert session.summary is None


def test_extract_caps_at_3_per_list(db, mira, session_with_messages):
    session, messages = session_with_messages

    mock_response = (
        '{'
        '"summary": "test",'
        '"observations": ["a","b","c","d","e"],'
        '"frictions": ["x","y","z","w"],'
        '"memory_candidates": ["m1","m2","m3","m4"]'
        '}'
    )

    with patch.object(insights_extractor, "_call_anthropic", return_value=mock_response):
        result = insights_extractor.extract_and_persist(db, session, messages)

    assert len(result.observations) == 3
    assert len(result.frictions) == 3
    assert len(result.memory_candidates) == 3
