"""Attendance — Query-Building, Berechtigung, Calendar-Merge, Stats.

Lebt im services-Layer (analog calendar_query.py), damit Router-Code
dünn bleibt und alle Berechtigungs-Logik an einer Stelle testbar ist.

Konventionen: SHIKSHA_ATTENDANCE_SPEC.md §6, §4 (Calendar-Merge), §10.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Query, Session

from shiksha_engine.db import schema_name
from shiksha_engine.models.attendance import (
    AttendanceRecord,
    AttendanceSettings,
    CALENDAR_VIRTUAL_STATUS,
    PRESENT_STATUS,
    SOURCE_MANUAL,
)
from shiksha_engine.models.event import Event
from shiksha_engine.models.operator import Operator
from shiksha_engine.models.person import Person
from shiksha_engine.services.attendance_ratio import compute_ratio_status


# ============================================================ Rolle


def _is_developer(op: Operator) -> bool:
    return op.kind == "system" or op.role == "developer"


def _is_staff_role(op: Operator) -> bool:
    return op.role in ("leitung", "padagoge", "padagogin", "paedagogin")


def _is_klient_role(op: Operator) -> bool:
    return op.role in ("eltern", "teilnehmer")


# ============================================================ Berechtigung


def can_read_attendance(operator: Operator) -> bool:
    """Phase 1: nur staff + developer dürfen Anwesenheit lesen.

    Eltern/Teilnehmer kommen erst Phase 2 mit T-003 (Operator-Person-Link).
    """
    if _is_developer(operator):
        return True
    if _is_staff_role(operator):
        return True
    return False


def can_write_attendance(operator: Operator) -> bool:
    return _is_developer(operator) or _is_staff_role(operator)


def can_modify_record(operator: Operator, record: AttendanceRecord) -> bool:
    if _is_developer(operator) or operator.role == "leitung":
        return True
    if _is_staff_role(operator):
        # Pädagogin: kann Kollegen einchecken (siehe Spec §6.1 Begründung),
        # aber Löschen/Modify nur eigene Records oder Kinder.
        # Phase 1 pragmatisch: Pädagogin darf alles modifizieren was sie sehen darf.
        return True
    return False


def can_modify_settings(operator: Operator) -> bool:
    return _is_developer(operator) or operator.role == "leitung"


# ============================================================ Resolver


def resolve_target_tenant(operator: Operator, payload_tenant: Optional[str]) -> Optional[str]:
    if _is_developer(operator):
        return payload_tenant or operator.org_id
    return operator.org_id


def get_settings(db: Session, tenant_org_id: str) -> AttendanceSettings:
    """Liefert Settings für den Tenant, fällt auf Defaults zurück wenn nicht vorhanden."""
    s = db.query(AttendanceSettings).filter_by(tenant_org_id=tenant_org_id).first()
    if s:
        return s
    # Fallback: Default-Settings nicht in DB schreiben, nur in-memory liefern
    return AttendanceSettings(
        tenant_org_id=tenant_org_id,
        opens_at=time(7, 0),
        closes_at=time(17, 0),
        staff_ratio={"6": 10},  # konservativer Default
        metadata_={},
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )


# ============================================================ Late-Arrival-Auto-Calc


def auto_calc_metadata(
    metadata: dict[str, Any],
    check_in_at: Optional[datetime],
    check_out_at: Optional[datetime],
    expected_in_at: Optional[datetime],
    expected_out_at: Optional[datetime],
) -> dict[str, Any]:
    """
    Setzt late_arrival_minutes und early_pickup_minutes in metadata wenn passend.

    Siehe Spec §2.3 (L7): Backend rechnet automatisch.
    """
    md = dict(metadata or {})
    if check_in_at and expected_in_at:
        delta = (check_in_at - expected_in_at).total_seconds() / 60
        md["late_arrival_minutes"] = max(0, int(delta))
    if check_out_at and expected_out_at:
        delta = (expected_out_at - check_out_at).total_seconds() / 60
        md["early_pickup_minutes"] = max(0, int(delta))
    return md


# ============================================================ Virtual-Record-Merge


def _make_virtual_record(person_id: int, day: date, event: Event) -> dict[str, Any]:
    """Aus einem Calendar-Event einen virtuellen Attendance-Record bauen (read-only)."""
    new_status = CALENDAR_VIRTUAL_STATUS.get(event.event_type, "unbekannt")
    return {
        "id": None,
        "person_id": person_id,
        "date": day,
        "status": new_status,
        "check_in_at": None,
        "check_out_at": None,
        "expected_in_at": None,
        "expected_out_at": None,
        "group_id": None,
        "notes": event.description,
        "source": "calendar_sync",
        "source_event_id": event.id,
        "metadata": {
            "virtual": True,
            "source_event_title": event.title,
            "source_event_type": event.event_type,
        },
        "operator_id": None,
        "active": True,
        "created_at": None,
        "updated_at": None,
        "virtual": True,
    }


def merge_virtual_from_calendar(
    db: Session,
    tenant_org_id: str,
    day: date,
    existing_records: list[AttendanceRecord],
) -> list[dict[str, Any]]:
    """
    Read-Side-Merge: für Person+Tag ohne manuellen Record, schau ob
    ein Calendar-Event (urlaub|abwesenheit) sie betrifft.

    Performance-Hinweis (Spec §4.3): nutzt GIN-Index auf events.participants
    indirekt — wir laden ALLE Urlaub/Abwesenheits-Events im Range und
    entpacken die participants App-Side. Für Krummelus-Maßstab unkritisch.
    Für N>100 Persons → T-008-Cache.
    """
    seen_person_ids = {r.person_id for r in existing_records}

    day_start = datetime.combine(day, time(0, 0), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    events = (
        db.query(Event)
        .filter(
            Event.tenant_org_id == tenant_org_id,
            Event.deleted_at.is_(None),
            Event.event_type.in_(("urlaub", "abwesenheit")),
            Event.start_at < day_end,
            or_(Event.end_at.is_(None), Event.end_at >= day_start),
        )
        .all()
    )

    virtual_records: list[dict[str, Any]] = []
    for ev in events:
        for pid in (ev.participants or []):
            if pid in seen_person_ids:
                continue
            virtual_records.append(_make_virtual_record(pid, day, ev))
            seen_person_ids.add(pid)  # nicht doppelt

    return virtual_records


# ============================================================ Day-View Loader


def load_day(
    db: Session,
    tenant_org_id: str,
    day: date,
    operator: Operator,
) -> dict[str, Any]:
    """
    Vollständige Day-View für /day-Endpoint.

    Returns dict mit: records, settings, live_counts
    """
    # 1. Manuelle Records
    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_org_id == tenant_org_id,
            AttendanceRecord.date == day,
            AttendanceRecord.deleted_at.is_(None),
        )
        .all()
    )

    # 2. Virtuelle Records aus Calendar
    virtual = merge_virtual_from_calendar(db, tenant_org_id, day, records)

    # 3. Person-Briefs lazy laden
    person_ids = {r.person_id for r in records}
    person_ids.update(v["person_id"] for v in virtual)
    persons_by_id: dict[int, Person] = {
        p.id: p for p in db.query(Person).filter(Person.id.in_(person_ids)).all()
    } if person_ids else {}

    # 4. Settings (oder Fallback-Defaults)
    settings = get_settings(db, tenant_org_id)

    # 5. Live-Counts (Sweepline auf manuelle Records, virtuelle zählen NICHT als anwesend)
    ratio_data = compute_ratio_status(records, persons_by_id, settings, day)

    return {
        "records": records,
        "virtual_records": virtual,
        "persons_by_id": persons_by_id,
        "settings": settings,
        "live_counts": ratio_data,
    }


# ============================================================ Week-Summary


def compute_week_summary(
    db: Session,
    tenant_org_id: str,
) -> dict[str, Any]:
    """Avg anwesende Kinder pro Tag der letzten 7 Tage."""
    today = datetime.now(tz=timezone.utc).date()
    from_date = today - timedelta(days=7)

    # Pro Tag: Anzahl Records mit status in PRESENT_STATUS und kind='kind'
    schema = schema_name()
    rows = db.execute(
        text(f"""
            SELECT a.date, COUNT(*) AS n
            FROM {schema}.attendance_records a
            JOIN {schema}.persons p ON p.id = a.person_id
            WHERE a.tenant_org_id = :tenant
              AND a.deleted_at IS NULL
              AND a.date >= :from_date
              AND a.date < :today
              AND a.status = ANY(:present)
              AND p.kind = 'kind'
            GROUP BY a.date
        """),
        {
            "tenant": tenant_org_id,
            "from_date": from_date,
            "today": today,
            "present": list(PRESENT_STATUS),
        },
    ).all()

    if not rows:
        return {"avg_present_count": 0.0, "days_observed": 0}

    total = sum(r.n for r in rows)
    return {
        "avg_present_count": round(total / len(rows), 1),
        "days_observed": len(rows),
    }
