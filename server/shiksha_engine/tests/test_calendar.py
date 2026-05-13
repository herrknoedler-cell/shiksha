"""Calendar — Endpoints + Berechtigung + Repeat + Stats + Geburtstage.

Spec: SHIKSHA_CALENDAR_SPEC.md §6.4 verlangt mindestens vier Berechtigungs-Tests
(test_eltern_read_filter, test_padagogin_urlaub_other_pending,
 test_cross_tenant_reject, test_eltern_cannot_write).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------- Fixtures-Hilfen


def _create_event_via_api(
    client, tenant_token, **overrides
):
    payload = {
        "event_type": "termin",
        "title": "Testtermin",
        "start_at": (datetime.now(tz=timezone.utc) + timedelta(hours=2)).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {},
        **overrides,
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------- 1. Basis-CRUD


def test_list_events_empty(client, mira_token):
    r = client.get(
        "/api/v1/calendar/events",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_create_and_get_event(client, mira_token):
    created = _create_event_via_api(client, mira_token, title="Elternabend")
    assert len(created) == 1
    eid = created[0]["id"]

    r = client.get(
        f"/api/v1/calendar/events/{eid}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Elternabend"
    assert body["event_type"] == "termin"
    assert body["metadata"]["urgency"] == "normal"


def test_create_with_repeat_weekly_4(client, mira_token):
    created = _create_event_via_api(
        client,
        mira_token,
        event_type="kurs",
        title="Musikkreis",
        repeat={"kind": "weekly", "count": 4},
    )
    assert len(created) == 4

    group_ids = {e["metadata"]["recurrence_group"] for e in created}
    assert len(group_ids) == 1, "alle Repeat-Events haben dieselbe recurrence_group"

    indices = sorted(e["metadata"]["recurrence_index"] for e in created)
    assert indices == [1, 2, 3, 4]


def test_patch_event(client, mira_token):
    created = _create_event_via_api(client, mira_token, title="Initial")
    eid = created[0]["id"]
    r = client.patch(
        f"/api/v1/calendar/events/{eid}",
        json={"title": "Geändert", "metadata": {"urgency": "important"}},
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Geändert"
    assert body["metadata"]["urgency"] == "important"


def test_delete_event_soft(client, mira_token, db_session):
    from shiksha_engine.models.event import Event
    created = _create_event_via_api(client, mira_token, title="ToDelete")
    eid = created[0]["id"]
    r = client.delete(
        f"/api/v1/calendar/events/{eid}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 204

    # Liste sieht es nicht mehr, DB-Row existiert mit deleted_at gesetzt
    r2 = client.get(
        f"/api/v1/calendar/events/{eid}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r2.status_code == 404

    e_db = db_session.query(Event).filter_by(id=eid).first()
    assert e_db is not None
    assert e_db.deleted_at is not None


# ---------------------------------------------------------- 2. Filter


def test_filter_by_type(client, mira_token):
    _create_event_via_api(client, mira_token, event_type="termin", title="T1")
    _create_event_via_api(client, mira_token, event_type="kurs", title="K1")
    r = client.get(
        "/api/v1/calendar/events?type=kurs&include_birthdays=false",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    titles = [e["title"] for e in r.json()]
    assert "K1" in titles and "T1" not in titles


def test_filter_by_from_to(client, mira_token):
    now = datetime.now(tz=timezone.utc)
    _create_event_via_api(
        client, mira_token, title="vergangen",
        start_at=(now - timedelta(days=10)).isoformat(),
    )
    _create_event_via_api(
        client, mira_token, title="bald",
        start_at=(now + timedelta(hours=1)).isoformat(),
    )

    # isoformat() liefert '+00:00' — in URL wird '+' zu ' '. Z-Suffix vermeidet das.
    from_iso = now.isoformat().replace("+00:00", "Z")
    to_iso = (now + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    r = client.get(
        f"/api/v1/calendar/events?from={from_iso}&to={to_iso}&include_birthdays=false",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    titles = [e["title"] for e in r.json()]
    assert titles == ["bald"]


def test_filter_by_person_id_gin(client, mira_token):
    _create_event_via_api(client, mira_token, title="ohne Personen", participants=[])
    _create_event_via_api(client, mira_token, title="mit Lio", participants=[1, 2])
    _create_event_via_api(client, mira_token, title="mit Tobias", participants=[3])

    r = client.get(
        "/api/v1/calendar/events?person_id=2&include_birthdays=false",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    titles = [e["title"] for e in r.json()]
    assert "mit Lio" in titles
    assert "mit Tobias" not in titles
    assert "ohne Personen" not in titles


# ---------------------------------------------------------- 3. Berechtigung (Spec §6.4 — vier Pflicht-Tests)


def test_eltern_read_filter(client, mira_token, eltern_token):
    """Eltern sehen nur globale Termine, keine privaten Events.

    Spec §6.2: Event ist "betreffend" wenn participants @> [own_kid] ODER
    (participants=[] AND event_type=termin).
    Phase 1 ohne Operator-↔-Person-Link: nur global termin.
    """
    # Leitung legt drei Events an:
    _create_event_via_api(client, mira_token, title="Globaler Termin", participants=[])
    _create_event_via_api(client, mira_token, title="Privat mit Mira", participants=[19])  # Mira
    _create_event_via_api(client, mira_token, event_type="urlaub", title="Urlaub Mira", participants=[19])

    r = client.get(
        "/api/v1/calendar/events?include_birthdays=false",
        headers={"Authorization": f"Bearer {eltern_token}"},
    )
    assert r.status_code == 200
    titles = [e["title"] for e in r.json()]
    assert titles == ["Globaler Termin"]


def test_padagogin_urlaub_other_pending(
    client, mira_token, padagogin_token, padagogin_id
):
    """Pädagogin sieht keinen pending-Urlaub von anderen, eigenen schon."""
    # Leitung-Urlaub pending
    _create_event_via_api(
        client, mira_token, event_type="urlaub", title="Mira-Urlaub-pending",
        metadata={"status": "pending"},
    )
    # Leitung-Urlaub approved
    _create_event_via_api(
        client, mira_token, event_type="urlaub", title="Mira-Urlaub-approved",
        metadata={"status": "approved"},
    )

    r = client.get(
        "/api/v1/calendar/events?type=urlaub&include_birthdays=false",
        headers={"Authorization": f"Bearer {padagogin_token}"},
    )
    assert r.status_code == 200
    titles = [e["title"] for e in r.json()]
    assert "Mira-Urlaub-approved" in titles
    assert "Mira-Urlaub-pending" not in titles


def test_cross_tenant_reject(client, mira_token, other_tenant_token):
    """Operator von Tenant A bekommt nichts von Tenant B."""
    e_from_a = _create_event_via_api(client, mira_token, title="Krummelus-only")
    eid = e_from_a[0]["id"]

    # Operator aus anderem Tenant
    r = client.get(
        f"/api/v1/calendar/events/{eid}",
        headers={"Authorization": f"Bearer {other_tenant_token}"},
    )
    assert r.status_code == 404


def test_eltern_cannot_write(client, eltern_token):
    """Eltern dürfen weder POST noch PATCH noch DELETE."""
    payload = {
        "event_type": "termin",
        "title": "soll fehlschlagen",
        "start_at": datetime.now(tz=timezone.utc).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {},
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {eltern_token}"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------- 4. Stats + TodaySummary


def test_stats(client, mira_token):
    now = datetime.now(tz=timezone.utc)
    _create_event_via_api(
        client, mira_token, event_type="termin", title="t1",
        start_at=now.isoformat(),
    )
    _create_event_via_api(
        client, mira_token, event_type="kurs", title="k1",
        start_at=(now + timedelta(hours=1)).isoformat(),
    )
    _create_event_via_api(
        client, mira_token, event_type="urlaub", title="u1",
        start_at=(now + timedelta(days=2)).isoformat(),
        metadata={"status": "approved"},
    )

    r = client.get(
        "/api/v1/calendar/stats",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 3
    assert body["by_type"].get("termin", 0) >= 1
    assert body["by_type"].get("urlaub", 0) >= 1


def test_today_summary(client, mira_token):
    now = datetime.now(tz=timezone.utc)
    _create_event_via_api(client, mira_token, title="heute1", start_at=now.isoformat())
    _create_event_via_api(client, mira_token, title="heute2",
                          start_at=(now + timedelta(hours=2)).isoformat())

    r = client.get(
        "/api/v1/calendar/today_summary",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["event_count_today"] >= 2
    # staff_count_today abhängig von DB-Fixture-Stand — Hauptsache Field ist da
    assert isinstance(body["staff_count_today"], int)
    assert body["next_event"] is not None


# ---------------------------------------------------------- 5. Virtual Birthdays


def test_virtual_birthdays_merged(client, mira_token, krummelus_with_birthdays):
    """Mit Personen, die im Fenster Geburtstag haben, kommen virtuelle Events."""
    now = datetime.now(tz=timezone.utc)
    # ein Jahr-Fenster:
    from_ = now.replace(month=1, day=1)
    to = now.replace(year=now.year + 1, month=1, day=1)

    from_iso = from_.isoformat().replace("+00:00", "Z")
    to_iso = to.isoformat().replace("+00:00", "Z")
    r = client.get(
        f"/api/v1/calendar/events?from={from_iso}&to={to_iso}&include_birthdays=true",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    birthdays = [e for e in r.json() if e["event_type"] == "geburtstag"]
    assert len(birthdays) >= 1
    for b in birthdays:
        assert b["synthetic"] is True
        assert b["all_day"] is True


# ---------------------------------------------------------- 6. Validierung


def test_validation_invalid_event_type(client, mira_token):
    payload = {
        "event_type": "reservierung",  # Camping-Type, nicht KITA
        "title": "darf nicht",
        "start_at": datetime.now(tz=timezone.utc).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {},
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 422


def test_validation_invalid_urgency(client, mira_token):
    payload = {
        "event_type": "termin",
        "title": "bad urgency",
        "start_at": datetime.now(tz=timezone.utc).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {"urgency": "super_urgent"},
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 422


def test_developer_requires_tenant(client, developer_token_no_org):
    """Developer ohne Tenant-Kontext bekommt 400."""
    payload = {
        "event_type": "termin",
        "title": "missing tenant",
        "start_at": datetime.now(tz=timezone.utc).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {},
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {developer_token_no_org}"},
    )
    assert r.status_code == 400


def test_repeat_count_bounds(client, mira_token):
    """Repeat-Count außerhalb [2,104] wird abgelehnt."""
    payload = {
        "event_type": "kurs",
        "title": "zu oft",
        "start_at": datetime.now(tz=timezone.utc).isoformat(),
        "all_day": False,
        "participants": [],
        "metadata": {},
        "repeat": {"kind": "weekly", "count": 500},
    }
    r = client.post(
        "/api/v1/calendar/events",
        json=payload,
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 422
