"""Memory-Lifecycle Tests — proposed → active/dismissed, Soft-Delete,
Prompt-Filter (kritisch: proposed leakt NIEMALS in den System-Prompt).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from shiksha_engine.models import MemoryEntry, PersonaPrompt
from shiksha_engine.services.persona_loader import load_system_prompt


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture
def persona_for_mira(db):
    p = PersonaPrompt(
        name="tagesausklang", edition="*", version=1,
        system_prompt="BASE-PROMPT",
    )
    db.add(p)
    db.commit()
    return p


# ===================================================================
# Prompt-Filter — die zentrale Sicherheits-Eigenschaft
# ===================================================================

def test_active_memory_appears_in_prompt(db, mira, persona_for_mira):
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Mira hat fünf Mitarbeiterinnen.",
        status="active",
    ))
    db.commit()

    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "Mira hat fünf Mitarbeiterinnen" in prompt


def test_proposed_memory_does_NOT_appear_in_prompt(db, mira, persona_for_mira):
    """Kritisch: proposed sind nur Vorschläge — sie dürfen nicht ungeprüft
    in den Prompt fließen."""
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="SOLLTE NICHT IM PROMPT AUFTAUCHEN.",
        status="proposed",
    ))
    db.commit()

    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "SOLLTE NICHT IM PROMPT AUFTAUCHEN" not in prompt


def test_dismissed_memory_does_NOT_appear_in_prompt(db, mira, persona_for_mira):
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Verworfener Eintrag.",
        status="dismissed",
    ))
    db.commit()

    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "Verworfener Eintrag" not in prompt


def test_soft_deleted_memory_does_NOT_appear_in_prompt(db, mira, persona_for_mira):
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Gelöschter Eintrag.",
        status="active",
        deleted_at=datetime.now(timezone.utc),
    ))
    db.commit()

    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "Gelöschter Eintrag" not in prompt


def test_mixed_status_only_active_in_prompt(db, mira, persona_for_mira):
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="ACTIVE-1", status="active",
    ))
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="PROPOSED-1", status="proposed",
    ))
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="DISMISSED-1", status="dismissed",
    ))
    db.add(MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="ACTIVE-2", status="active",
    ))
    db.commit()

    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "ACTIVE-1" in prompt
    assert "ACTIVE-2" in prompt
    assert "PROPOSED-1" not in prompt
    assert "DISMISSED-1" not in prompt


# ===================================================================
# Tools-Hinweis im Prompt
# ===================================================================

def test_tools_hint_included_by_default(db, mira, persona_for_mira):
    prompt = load_system_prompt(db, operator=mira, persona="tagesausklang")
    assert "WERKZEUGE" in prompt
    assert "log_observation" in prompt
    assert "Zahnarzt" in prompt or "Unsichtbarkeit" in prompt


def test_tools_hint_excluded_when_disabled(db, mira, persona_for_mira):
    prompt = load_system_prompt(
        db, operator=mira, persona="tagesausklang",
        include_tools_hint=False,
    )
    assert "WERKZEUGE" not in prompt
    assert "log_observation" not in prompt


# ===================================================================
# Confirm / Dismiss Endpoints — via TestClient + JWT
# ===================================================================

@pytest.fixture
def auth_headers(mira):
    """Bearer-Token für Mira."""
    from shiksha_engine.services import jwt_service
    token = jwt_service.issue_token(
        operator_id=mira.id,
        role=mira.role,
        edition=mira.edition,
        org_id=mira.org_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_confirm_promotes_proposed_to_active(db, mira, client, auth_headers):
    entry = MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Vorschlag.", status="proposed",
    )
    db.add(entry)
    db.commit()
    eid = entry.id

    res = client.post(f"/api/v1/memory/{eid}/confirm", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    db.expire_all()
    refreshed = db.get(MemoryEntry, eid)
    assert refreshed.status == "active"


def test_confirm_active_returns_409(db, mira, client, auth_headers):
    entry = MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Schon aktiv.", status="active",
    )
    db.add(entry)
    db.commit()

    res = client.post(f"/api/v1/memory/{entry.id}/confirm", headers=auth_headers)
    assert res.status_code == 409


def test_dismiss_marks_dismissed(db, mira, client, auth_headers):
    entry = MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Abzulehnen.", status="proposed",
    )
    db.add(entry)
    db.commit()
    eid = entry.id

    res = client.post(f"/api/v1/memory/{eid}/dismiss", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "dismissed"


def test_delete_is_soft_delete(db, mira, client, auth_headers):
    entry = MemoryEntry(
        operator_id=mira.id, edition=mira.edition,
        text="Soft-Delete-Test.", status="active",
    )
    db.add(entry)
    db.commit()
    eid = entry.id

    res = client.delete(f"/api/v1/memory/{eid}", headers=auth_headers)
    assert res.status_code == 204

    db.expire_all()
    refreshed = db.get(MemoryEntry, eid)
    # Eintrag existiert noch, hat aber deleted_at
    assert refreshed is not None
    assert refreshed.deleted_at is not None


def test_list_default_filters_active(db, mira, client, auth_headers):
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="A1", status="active"))
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="P1", status="proposed"))
    db.commit()

    res = client.get("/api/v1/memory", headers=auth_headers)
    assert res.status_code == 200
    texts = [m["text"] for m in res.json()]
    assert "A1" in texts
    assert "P1" not in texts


def test_list_status_proposed_shows_only_proposed(db, mira, client, auth_headers):
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="A1", status="active"))
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="P1", status="proposed"))
    db.commit()

    res = client.get("/api/v1/memory?status=proposed", headers=auth_headers)
    assert res.status_code == 200
    texts = [m["text"] for m in res.json()]
    assert "P1" in texts
    assert "A1" not in texts


def test_list_status_all_shows_everything(db, mira, client, auth_headers):
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="A1", status="active"))
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="P1", status="proposed"))
    db.add(MemoryEntry(operator_id=mira.id, edition=mira.edition, text="D1", status="dismissed"))
    db.commit()

    res = client.get("/api/v1/memory?status=all", headers=auth_headers)
    assert res.status_code == 200
    texts = [m["text"] for m in res.json()]
    assert {"A1", "P1", "D1"} <= set(texts)
