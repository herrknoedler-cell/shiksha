"""Sessions-Filter Tests."""

from datetime import datetime, timedelta

import pytest

from shiksha_engine.models import Session
from shiksha_engine.services.jwt_service import issue_token


def _auth_header(operator):
    return {"Authorization": f"Bearer {issue_token(operator_id=operator.id, role=operator.role, edition=operator.edition, org_id=operator.org_id)}"}


@pytest.fixture
def sessions_in_db(db, mira):
    """Drei Sessions: zwei kita-tagesausklang mit Summaries, eine ohne."""
    now = datetime.utcnow()
    s1 = Session(
        id="ses_1", operator_id=mira.id, org_id=mira.org_id, edition="kita",
        persona="tagesausklang", started_at=now - timedelta(days=2),
        summary="Gestern war chaotisch wegen Personalausfall.",
    )
    s2 = Session(
        id="ses_2", operator_id=mira.id, org_id=mira.org_id, edition="kita",
        persona="tagesausklang", started_at=now - timedelta(days=1),
        summary="Wochenend-Anrufe haben Mira beschäftigt.",
    )
    s3 = Session(
        id="ses_3", operator_id=mira.id, org_id=mira.org_id, edition="kita",
        persona="kennenlernen", started_at=now,
        summary=None,
    )
    db.add_all([s1, s2, s3])
    db.commit()
    return [s1, s2, s3]


def test_list_all(client, mira, sessions_in_db):
    r = client.get("/api/v1/sessions", headers=_auth_header(mira))
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_filter_by_persona(client, mira, sessions_in_db):
    r = client.get("/api/v1/sessions?persona=tagesausklang", headers=_auth_header(mira))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_filter_has_summary(client, mira, sessions_in_db):
    r = client.get("/api/v1/sessions?has_summary=true", headers=_auth_header(mira))
    assert len(r.json()) == 2

    r = client.get("/api/v1/sessions?has_summary=false", headers=_auth_header(mira))
    assert len(r.json()) == 1


def test_search_q(client, mira, sessions_in_db):
    r = client.get("/api/v1/sessions?q=Wochenend", headers=_auth_header(mira))
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 1
    assert "Wochenend" in entries[0]["summary"]


def test_filter_since(client, mira, sessions_in_db):
    yesterday = (datetime.utcnow() - timedelta(hours=20)).isoformat()
    r = client.get(f"/api/v1/sessions?since={yesterday}", headers=_auth_header(mira))
    # Nur die letzten ~20h: s2 (-1 Tag) + s3 (now) — also 2, s2 grenzwertig
    entries = r.json()
    assert all("ses_1" != e["id"] for e in entries)
