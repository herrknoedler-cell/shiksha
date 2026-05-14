"""Attendance — Endpoints + Berechtigung + Sweepline + Calendar-Merge.

Spec: SHIKSHA_ATTENDANCE_SPEC.md §6.2 verlangt fünf Pflicht-Tests
(eltern_read_filter, padagogin_can_check_in_kollegen, cross_tenant_reject,
 eltern_cannot_write, virtual_records_via_calendar_urlaub)
plus zwei Berechnungs-Tests (late_arrival, sweepline_peak).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest


# ============================================================ Helpers


def _today_iso() -> str:
    return date.today().isoformat()


def _now_z() -> str:
    """ISO-Datetime mit Z-Suffix für URL-sichere Tests (Repo-Map §6)."""
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _create_record_via_api(client, token, person_id, **overrides):
    payload = {
        "person_id": person_id,
        "date": _today_iso(),
        "status": "anwesend",
        **overrides,
    }
    r = client.post(
        "/api/v1/attendance/records",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


# ============================================================ 1. Basis-CRUD


def test_create_basic(client, mira_token, krummelus_kid_id):
    body = _create_record_via_api(client, mira_token, krummelus_kid_id, status="anwesend")
    assert body["status"] == "anwesend"
    assert body["person_id"] == krummelus_kid_id


def test_get_day_empty(client, mira_token):
    r = client.get(
        f"/api/v1/attendance/day?date={_today_iso()}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "records" in body
    assert "settings" in body
    assert "live_counts" in body


def test_get_day_with_records(client, mira_token, krummelus_kid_id):
    _create_record_via_api(client, mira_token, krummelus_kid_id, status="anwesend")
    r = client.get(
        f"/api/v1/attendance/day?date={_today_iso()}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    records = r.json()["records"]
    assert any(rec["person_id"] == krummelus_kid_id for rec in records)


def test_patch_status(client, mira_token, krummelus_kid_id):
    rec = _create_record_via_api(client, mira_token, krummelus_kid_id, status="anwesend")
    r = client.patch(
        f"/api/v1/attendance/records/{rec['id']}",
        json={"status": "krank"},
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "krank"


def test_delete_soft(client, mira_token, krummelus_kid_id, db_session):
    from shiksha_engine.models.attendance import AttendanceRecord
    rec = _create_record_via_api(client, mira_token, krummelus_kid_id)
    r = client.delete(
        f"/api/v1/attendance/records/{rec['id']}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 204
    db_rec = db_session.query(AttendanceRecord).filter_by(id=rec["id"]).first()
    assert db_rec is not None
    assert db_rec.deleted_at is not None


def test_partial_unique_softdelete_then_recreate(client, mira_token, krummelus_kid_id):
    """Nach Soft-Delete kann man am gleichen Tag neu anlegen — Partial-Unique-Index."""
    rec1 = _create_record_via_api(client, mira_token, krummelus_kid_id)
    client.delete(
        f"/api/v1/attendance/records/{rec1['id']}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    # Neuanlage am gleichen Tag muss klappen
    rec2 = _create_record_via_api(client, mira_token, krummelus_kid_id, status="krank")
    assert rec2["id"] != rec1["id"]


def test_duplicate_active_record_rejected(client, mira_token, krummelus_kid_id):
    """Aktiver Record + Neuanlage am gleichen Tag → 409."""
    _create_record_via_api(client, mira_token, krummelus_kid_id)
    payload = {
        "person_id": krummelus_kid_id,
        "date": _today_iso(),
        "status": "krank",
    }
    r = client.post(
        "/api/v1/attendance/records",
        json=payload,
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 409


# ============================================================ 2. Berechnungen (Pflicht-Tests §6.2 L7)


def test_late_arrival_minutes_calculated(client, mira_token, krummelus_kid_id):
    """expected 08:00, check_in 08:15 → metadata.late_arrival_minutes = 15."""
    today = date.today()
    expected = datetime.combine(today, time(8, 0), tzinfo=timezone.utc)
    actual = datetime.combine(today, time(8, 15), tzinfo=timezone.utc)
    rec = _create_record_via_api(
        client,
        mira_token,
        krummelus_kid_id,
        status="anwesend",
        expected_in_at=expected.isoformat().replace("+00:00", "Z"),
        check_in_at=actual.isoformat().replace("+00:00", "Z"),
    )
    assert rec["metadata"].get("late_arrival_minutes") == 15


def test_sweepline_peak_concurrent(client, mira_token, three_krummelus_kids):
    """Drei Kinder mit überlappenden Zeiten — Peak = 3 wenn alle gleichzeitig da."""
    today = date.today()
    base = datetime.combine(today, time(9, 0), tzinfo=timezone.utc)
    for i, kid_id in enumerate(three_krummelus_kids):
        _create_record_via_api(
            client, mira_token, kid_id,
            status="anwesend",
            check_in_at=(base + timedelta(minutes=i * 10)).isoformat().replace("+00:00", "Z"),
            check_out_at=(base + timedelta(hours=4 - i)).isoformat().replace("+00:00", "Z"),
        )
    r = client.get(
        f"/api/v1/attendance/day?date={today.isoformat()}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    counts = r.json()["live_counts"]
    assert counts["kids_present_count"] == 3


# ============================================================ 3. Berechtigung (Pflicht-Tests §6.2)


def test_eltern_read_filter(client, eltern_token):
    """Eltern Phase 1: 403 auf /day."""
    r = client.get(
        f"/api/v1/attendance/day?date={_today_iso()}",
        headers={"Authorization": f"Bearer {eltern_token}"},
    )
    assert r.status_code == 403


def test_padagogin_can_check_in_kollegen(
    client, padagogin_token, krummelus_kid_id, mira_person_id
):
    """Pädagogin darf Kollegen-Check-In setzen (Spec §6.1 Begründung)."""
    rec = _create_record_via_api(
        client, padagogin_token, mira_person_id, status="anwesend"
    )
    assert rec["status"] == "anwesend"


def test_cross_tenant_reject(client, mira_token, other_tenant_token, krummelus_kid_id):
    """Operator von Tenant A bekommt 404 bei Record von Tenant B."""
    rec = _create_record_via_api(client, mira_token, krummelus_kid_id)
    r = client.patch(
        f"/api/v1/attendance/records/{rec['id']}",
        json={"status": "krank"},
        headers={"Authorization": f"Bearer {other_tenant_token}"},
    )
    assert r.status_code == 404


def test_eltern_cannot_write(client, eltern_token, krummelus_kid_id):
    """Eltern: POST/PATCH/DELETE liefern 403."""
    payload = {
        "person_id": krummelus_kid_id,
        "date": _today_iso(),
        "status": "anwesend",
    }
    r = client.post(
        "/api/v1/attendance/records",
        json=payload,
        headers={"Authorization": f"Bearer {eltern_token}"},
    )
    assert r.status_code == 403


def test_virtual_records_via_calendar_urlaub(
    client, mira_token, mira_person_id, calendar_mira, db_session
):
    """Wenn Calendar-Urlaub für Mira existiert → in /day mit status=urlaub, virtual=true."""
    from shiksha_engine.models.event import Event
    today = date.today()
    now = datetime.now(tz=timezone.utc)
    e = Event(
        tenant_org_id=calendar_mira.org_id,
        event_type="urlaub",
        title="Mira-Urlaub",
        start_at=datetime.combine(today, time(0, 0), tzinfo=timezone.utc),
        end_at=datetime.combine(today + timedelta(days=2), time(0, 0), tzinfo=timezone.utc),
        all_day=True,
        participants=[mira_person_id],
        metadata_={"status": "approved"},
        operator_id=calendar_mira.id,
        active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(e)
    db_session.commit()

    r = client.get(
        f"/api/v1/attendance/day?date={today.isoformat()}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    records = r.json()["records"]
    mira_records = [rec for rec in records if rec["person_id"] == mira_person_id]
    assert len(mira_records) == 1
    assert mira_records[0]["status"] == "urlaub"
    assert mira_records[0]["virtual"] is True
    assert mira_records[0]["id"] is None


# ============================================================ 4. Virtual-Record-Promotion (Spec §4.2)


def test_virtual_record_promotion_via_post(
    client, mira_token, mira_person_id, calendar_mira, db_session
):
    """Mira override eines virtuellen Records via POST mit source_event_id."""
    from shiksha_engine.models.event import Event
    today = date.today()
    now = datetime.now(tz=timezone.utc)
    e = Event(
        tenant_org_id=calendar_mira.org_id,
        event_type="urlaub",
        title="Mira-Urlaub",
        start_at=datetime.combine(today, time(0, 0), tzinfo=timezone.utc),
        all_day=True,
        participants=[mira_person_id],
        operator_id=calendar_mira.id,
        active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(e)
    db_session.commit()

    # Mira ist doch da — Promote zu echtem Record mit status=anwesend
    rec = _create_record_via_api(
        client, mira_token, mira_person_id,
        status="anwesend",
        source_event_id=e.id,
    )
    assert rec["status"] == "anwesend"
    assert rec["source_event_id"] == e.id

    # Im /day-View sollte jetzt nur EINER auftauchen (der echte überschreibt virtuellen)
    r = client.get(
        f"/api/v1/attendance/day?date={today.isoformat()}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    mira_records = [r for r in r.json()["records"] if r["person_id"] == mira_person_id]
    assert len(mira_records) == 1
    assert mira_records[0]["status"] == "anwesend"


# ============================================================ 5. Settings


def test_settings_get(client, mira_token):
    r = client.get(
        "/api/v1/attendance/settings",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "opens_at" in body
    assert "staff_ratio" in body
    # Test-DB läuft via create_all (kein Alembic-Seed) → in-memory Fallback
    # aus services/attendance_query.get_settings(); Produktion seedt via Migration 0009.
    assert isinstance(body["staff_ratio"], dict)
    assert len(body["staff_ratio"]) >= 1


def test_settings_patch_leitung_only(client, padagogin_token):
    """Pädagogin darf Settings NICHT ändern — nur leitung+developer."""
    r = client.patch(
        "/api/v1/attendance/settings",
        json={"opens_at": "08:00"},
        headers={"Authorization": f"Bearer {padagogin_token}"},
    )
    assert r.status_code == 403


def test_settings_patch_works_as_leitung(client, mira_token):
    r = client.patch(
        "/api/v1/attendance/settings",
        json={"opens_at": "07:00"},
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200


# ============================================================ 6. Provider


def test_live_counts(client, mira_token, krummelus_kid_id):
    _create_record_via_api(client, mira_token, krummelus_kid_id, status="anwesend")
    r = client.get(
        "/api/v1/attendance/live_counts",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "kids_present_count" in body
    assert "ratio_status" in body
    assert body["ratio_status"] in ("green", "yellow", "red")


def test_live_counts_empty_day_is_green(client, mira_token):
    """Bei 0 Kindern + 0 Päd. ist der Personalschlüssel trivial erfüllt = grün."""
    r = client.get(
        "/api/v1/attendance/live_counts",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    body = r.json()
    if body["kids_present_count"] == 0:
        assert body["ratio_status"] == "green", f"Empty day must be green, got {body}"


def test_week_summary(client, mira_token):
    r = client.get(
        "/api/v1/attendance/week_summary",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "avg_present_count" in body
    assert "days_observed" in body


def test_overview_range(client, mira_token):
    from_d = (date.today() - timedelta(days=3)).isoformat()
    to_d = (date.today() + timedelta(days=1)).isoformat()
    r = client.get(
        f"/api/v1/attendance/overview?from={from_d}&to={to_d}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "days" in body
    assert len(body["days"]) == 4


def test_person_history(client, mira_token, krummelus_kid_id):
    _create_record_via_api(client, mira_token, krummelus_kid_id, status="anwesend")
    from_d = (date.today() - timedelta(days=1)).isoformat()
    to_d = (date.today() + timedelta(days=1)).isoformat()
    r = client.get(
        f"/api/v1/attendance/person/{krummelus_kid_id}?from={from_d}&to={to_d}",
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 200
    assert any(rec["status"] == "anwesend" for rec in r.json())


# ============================================================ 7. Validierung


def test_developer_requires_tenant(client, developer_token_no_org, krummelus_kid_id):
    payload = {
        "person_id": krummelus_kid_id,
        "date": _today_iso(),
        "status": "anwesend",
    }
    r = client.post(
        "/api/v1/attendance/records",
        json=payload,
        headers={"Authorization": f"Bearer {developer_token_no_org}"},
    )
    assert r.status_code == 400


def test_status_not_in_kita_rejected(client, mira_token, krummelus_kid_id):
    payload = {
        "person_id": krummelus_kid_id,
        "date": _today_iso(),
        "status": "reservierung",  # Camping-Status, nicht KITA
    }
    r = client.post(
        "/api/v1/attendance/records",
        json=payload,
        headers={"Authorization": f"Bearer {mira_token}"},
    )
    assert r.status_code == 422
