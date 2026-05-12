"""Tool-Runtime Tests — Dispatcher, Handler, Audit, Permissions.

Diese Tests laufen ohne Anthropic-Mock — sie rufen execute_tool direkt
und prüfen DB-Schreibvorgänge und tool_result-Blöcke.

Multi-Turn-Loop-Tests siehe test_multi_turn_loop.py.
"""

from __future__ import annotations

import json

import pytest

from shiksha_engine.models import (
    AuditLog,
    FrictionPoint,
    MemoryEntry,
    Observation,
    Session,
)
from shiksha_engine.services.tools_runtime import (
    TOOL_REGISTRY,
    execute_tool,
    list_tools_for_anthropic,
    registry_snapshot,
)


@pytest.fixture
def ses(db, mira) -> Session:
    s = Session(
        id="ses_tools_test",
        operator_id=mira.id,
        org_id=mira.org_id,
        edition=mira.edition,
        persona="tagesausklang",
    )
    db.add(s)
    db.commit()
    return s


# ===================================================================
# Registry & Tool-Liste
# ===================================================================

def test_registry_has_four_core_tools():
    names = set(TOOL_REGISTRY.keys())
    assert {"log_observation", "log_friction", "add_memory", "save_day_summary"} <= names


def test_list_tools_for_anthropic_returns_schema(mira):
    tools = list_tools_for_anthropic(mira)
    assert len(tools) >= 4
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


def test_registry_snapshot_serializable():
    snap = registry_snapshot()
    # Muss durch json.dumps gehen
    json.dumps(snap)


# ===================================================================
# log_observation
# ===================================================================

def test_log_observation_creates_row(db, mira, ses):
    result = execute_tool(
        name="log_observation",
        args={"text": "Lukas ist seit Montag wieder da.", "category": "kind"},
        tool_use_id="toolu_abc",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()

    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_abc"
    assert "is_error" not in result

    content = json.loads(result["content"])
    assert content["logged"] is True

    rows = db.query(Observation).filter_by(session_id=ses.id).all()
    assert len(rows) == 1
    assert rows[0].text == "Lukas ist seit Montag wieder da."
    assert rows[0].kind == "observation"
    assert rows[0].metadata_["category"] == "kind"


def test_log_observation_too_long_returns_error(db, mira, ses):
    long_text = "x" * 501
    result = execute_tool(
        name="log_observation",
        args={"text": long_text},
        tool_use_id="toolu_long",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()

    assert result.get("is_error") is True
    assert "Invalid arguments" in result["content"]
    # Nichts geschrieben
    assert db.query(Observation).count() == 0


def test_log_observation_empty_text_returns_error(db, mira, ses):
    result = execute_tool(
        name="log_observation",
        args={"text": ""},
        tool_use_id="toolu_empty",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    assert result.get("is_error") is True


# ===================================================================
# log_friction
# ===================================================================

def test_log_friction_with_severity(db, mira, ses):
    result = execute_tool(
        name="log_friction",
        args={
            "text": "Mittwochs ist Personal-Knappheit zum dritten Mal in Folge.",
            "severity": "mittel",
        },
        tool_use_id="toolu_fric_1",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()

    assert "is_error" not in result
    rows = db.query(FrictionPoint).filter_by(session_id=ses.id).all()
    assert len(rows) == 1
    assert rows[0].severity == "mittel"
    assert rows[0].resolved is False


def test_log_friction_invalid_severity_fails(db, mira, ses):
    """Pydantic akzeptiert beliebige Strings für severity, aber der
    Handler prüft gegen FRICTION_SEVERITIES und wirft ValueError."""
    result = execute_tool(
        name="log_friction",
        args={"text": "Reibung", "severity": "extrem"},
        tool_use_id="toolu_fric_bad",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    assert result.get("is_error") is True
    assert db.query(FrictionPoint).count() == 0


def test_log_friction_with_first_observed_date(db, mira, ses):
    result = execute_tool(
        name="log_friction",
        args={"text": "Test", "first_observed_at": "2026-04-15"},
        tool_use_id="toolu_fric_date",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()
    assert "is_error" not in result
    rows = db.query(FrictionPoint).all()
    assert rows[0].first_observed_at.isoformat() == "2026-04-15"


# ===================================================================
# add_memory
# ===================================================================

def test_add_memory_creates_proposed(db, mira, ses):
    result = execute_tool(
        name="add_memory",
        args={"text": "Mira plant Erweiterung in den oberen Stock im Herbst."},
        tool_use_id="toolu_mem",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()

    assert "is_error" not in result
    mems = db.query(MemoryEntry).filter_by(operator_id=mira.id).all()
    assert len(mems) == 1
    assert mems[0].status == "proposed"
    assert mems[0].source_session_id == ses.id


# ===================================================================
# save_day_summary
# ===================================================================

def test_save_day_summary_creates_observation_with_kind_summary(db, mira, ses):
    result = execute_tool(
        name="save_day_summary",
        args={
            "summary": "Heute war zwischen Lukas-Rückkehr und Kerstin-Ausfall — anstrengend, aber gut.",
            "mood": "belastet",
        },
        tool_use_id="toolu_sum",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()

    assert "is_error" not in result
    rows = db.query(Observation).filter_by(session_id=ses.id).all()
    assert len(rows) == 1
    assert rows[0].kind == "summary"
    assert rows[0].metadata_["mood"] == "belastet"


# ===================================================================
# Unbekannte Tools
# ===================================================================

def test_unknown_tool_returns_error(db, mira, ses):
    result = execute_tool(
        name="zerstoere_alles",
        args={},
        tool_use_id="toolu_evil",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    assert result.get("is_error") is True
    assert "Unknown tool" in result["content"]


# ===================================================================
# Audit-Logging
# ===================================================================

def test_audit_log_written_per_tool_call(db, mira, ses):
    """Audit landet in eigener SessionLocal — physikalisch in DB.
    Test-Session muss expire_all rufen, sonst Cache."""
    execute_tool(
        name="log_observation",
        args={"text": "audit-test"},
        tool_use_id="toolu_audit",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.flush()
    db.expire_all()  # erzwingt Re-Query gegen DB

    logs = db.query(AuditLog).filter(
        AuditLog.action.like("tool.log_observation.%")
    ).all()
    assert len(logs) >= 1
    log = logs[-1]
    assert log.actor_id == mira.id
    assert log.action == "tool.log_observation.ok"
    assert log.target_type == "observation"


def test_audit_log_records_failure(db, mira, ses):
    execute_tool(
        name="log_observation",
        args={"text": ""},  # invalid
        tool_use_id="toolu_failaudit",
        operator=mira,
        shiksha_session=ses,
        db=db,
    )
    db.expire_all()
    logs = db.query(AuditLog).filter(
        AuditLog.action == "tool.log_observation.fail"
    ).all()
    assert len(logs) >= 1
