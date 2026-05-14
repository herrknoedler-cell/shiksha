"""Attendance — REST-Endpoints für /api/v1/attendance.

Spec: SHIKSHA_ATTENDANCE_SPEC.md §10.
Router OHNE Prefix — wird in main.py registriert (siehe Repo-Map §6).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from shiksha_engine.db import get_db, schema_name
from shiksha_engine.deps import require_authenticated, require_operator_or_developer
from shiksha_engine.models.attendance import (
    AttendanceRecord,
    AttendanceSettings,
    STATUS_BY_EDITION,
    SOURCE_MANUAL,
)
from shiksha_engine.models.operator import Operator
from shiksha_engine.models.organization import Organization
from shiksha_engine.models.person import Person
from shiksha_engine.schemas.attendance import (
    AttendanceCreate,
    AttendanceOut,
    AttendancePatch,
    AttendanceSettingsOut,
    AttendanceSettingsPatch,
    DayView,
    LiveCounts,
    Overview,
    OverviewDay,
    PersonBrief,
    WeekSummary,
)
from shiksha_engine.services import attendance_query as aq


router = APIRouter(tags=["attendance"])


# ============================================================ Helpers


def _resolve_target_or_400(operator: Operator, payload_tenant: Optional[str]) -> str:
    target = aq.resolve_target_tenant(operator, payload_tenant)
    if not target:
        raise HTTPException(
            status_code=400,
            detail="Developer must call from a tenant context (org_id required)",
        )
    return target


def _to_out(r: AttendanceRecord, person: Optional[Person] = None) -> AttendanceOut:
    person_brief = None
    if person:
        person_brief = PersonBrief(
            id=person.id,
            given_name=person.given_name,
            family_name=person.family_name,
            kind=person.kind,
            group_id=person.group_id,
        )
    return AttendanceOut(
        id=r.id,
        person_id=r.person_id,
        person_brief=person_brief,
        date=r.date,
        status=r.status,
        check_in_at=r.check_in_at,
        check_out_at=r.check_out_at,
        expected_in_at=r.expected_in_at,
        expected_out_at=r.expected_out_at,
        group_id=r.group_id,
        notes=r.notes,
        source=r.source or SOURCE_MANUAL,
        source_event_id=r.source_event_id,
        metadata=dict(r.metadata_ or {}),
        operator_id=r.operator_id,
        active=r.active,
        created_at=r.created_at,
        updated_at=r.updated_at,
        virtual=False,
    )


def _virtual_to_out(virtual: dict) -> AttendanceOut:
    return AttendanceOut(
        id=None,
        person_id=virtual["person_id"],
        date=virtual["date"],
        status=virtual["status"],
        notes=virtual["notes"],
        source=virtual["source"],
        source_event_id=virtual["source_event_id"],
        metadata=virtual.get("metadata", {}),
        virtual=True,
        active=True,
    )


def _validate_status_for_tenant(db: Session, tenant_org_id: str, status_val: str) -> None:
    org = db.query(Organization).filter_by(id=tenant_org_id).first()
    edition = org.edition if org else "kita"
    allowed = STATUS_BY_EDITION.get(edition, STATUS_BY_EDITION["kita"])
    if status_val not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"status '{status_val}' nicht zulässig für edition '{edition}'",
        )


# ============================================================ DAY-VIEW


@router.get("/day", response_model=DayView)
def get_day(
    date: date = Query(...),
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, tenant_org_id)
    data = aq.load_day(db, target, date, operator)

    # Records + virtuelle Records zusammen
    records_out = [
        _to_out(r, data["persons_by_id"].get(r.person_id))
        for r in data["records"]
    ]
    records_out.extend(_virtual_to_out(v) for v in data["virtual_records"])

    return DayView(
        date=date,
        records=records_out,
        settings=AttendanceSettingsOut.model_validate(data["settings"]),
        live_counts=LiveCounts(**data["live_counts"]),
    )


# ============================================================ OVERVIEW


@router.get("/overview", response_model=Overview)
def get_overview(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, tenant_org_id)

    # Anzahl Records mit status=present pro Tag im Range
    from sqlalchemy import func, text
    schema = schema_name()
    rows = db.execute(
        text(f"""
            SELECT a.date, COUNT(*) FILTER (WHERE a.status = ANY(:present)) AS present_count,
                   COUNT(*) AS expected_count
            FROM {schema}.attendance_records a
            WHERE a.tenant_org_id = :tenant
              AND a.deleted_at IS NULL
              AND a.date >= :from_date
              AND a.date < :to_date
            GROUP BY a.date
            ORDER BY a.date
        """),
        {
            "tenant": target,
            "from_date": from_,
            "to_date": to,
            "present": ["anwesend", "eingecheckt", "verlängert"],
        },
    ).all()

    by_date = {r.date: (r.present_count, r.expected_count) for r in rows}

    days_out = []
    cur = from_
    while cur < to:
        pres, exp = by_date.get(cur, (0, 0))
        days_out.append(OverviewDay(
            date=cur,
            is_open_day=True,  # TODO 5.5.5.5: aus Calendar Schließtage einbeziehen
            is_holiday=False,
            present_count=pres,
            expected_count=exp,
        ))
        cur = cur + timedelta(days=1)

    return Overview(days=days_out)


# ============================================================ PERSON-HISTORY


@router.get("/person/{person_id}", response_model=list[AttendanceOut])
def get_person_history(
    person_id: int,
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, tenant_org_id)

    records = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.tenant_org_id == target,
            AttendanceRecord.person_id == person_id,
            AttendanceRecord.date >= from_,
            AttendanceRecord.date < to,
            AttendanceRecord.deleted_at.is_(None),
        )
        .order_by(AttendanceRecord.date.desc())
        .all()
    )

    person = db.query(Person).filter_by(id=person_id).first()
    return [_to_out(r, person) for r in records]


# ============================================================ CREATE


@router.post("/records", response_model=AttendanceOut, status_code=201)
def create_record(
    payload: AttendanceCreate,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    if not aq.can_write_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, payload.tenant_org_id)

    _validate_status_for_tenant(db, target, payload.status)

    # late_arrival_minutes / early_pickup_minutes auto-calc (Spec §2.3 / L7)
    md = aq.auto_calc_metadata(
        payload.metadata,
        payload.check_in_at,
        payload.check_out_at,
        payload.expected_in_at,
        payload.expected_out_at,
    )

    now = datetime.now(tz=timezone.utc)
    r = AttendanceRecord(
        tenant_org_id=target,
        person_id=payload.person_id,
        date=payload.date,
        status=payload.status,
        check_in_at=payload.check_in_at,
        check_out_at=payload.check_out_at,
        expected_in_at=payload.expected_in_at,
        expected_out_at=payload.expected_out_at,
        group_id=payload.group_id,
        notes=payload.notes,
        source=payload.source or SOURCE_MANUAL,
        source_event_id=payload.source_event_id,
        metadata_=md,
        operator_id=operator.id,
        active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(r)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Partial-Unique-Verletzung
        if "uq_attendance_person_date_active" in str(e):
            raise HTTPException(
                status_code=409,
                detail="Bereits ein Anwesenheits-Eintrag für diese Person an diesem Tag — modifizieren statt neu anlegen.",
            )
        raise

    db.refresh(r)
    person = db.query(Person).filter_by(id=r.person_id).first()
    return _to_out(r, person)


# ============================================================ PATCH


@router.patch("/records/{record_id}", response_model=AttendanceOut)
def patch_record(
    record_id: int,
    payload: AttendancePatch,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    if not aq.can_write_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, tenant_org_id)

    r = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.id == record_id,
            AttendanceRecord.tenant_org_id == target,
            AttendanceRecord.deleted_at.is_(None),
        )
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Record nicht gefunden")

    if not aq.can_modify_record(operator, r):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Ändern")

    data = payload.model_dump(exclude_unset=True)
    if "status" in data:
        _validate_status_for_tenant(db, target, data["status"])
    if "metadata" in data:
        # User-bereitgestelltes metadata MIT auto-calc-überlagern
        merged = {**(r.metadata_ or {}), **(data.pop("metadata") or {})}
        r.metadata_ = merged

    for k, v in data.items():
        if hasattr(r, k):
            setattr(r, k, v)

    # Re-Calc late_arrival nach Patch
    r.metadata_ = aq.auto_calc_metadata(
        r.metadata_,
        r.check_in_at,
        r.check_out_at,
        r.expected_in_at,
        r.expected_out_at,
    )

    r.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(r)
    person = db.query(Person).filter_by(id=r.person_id).first()
    return _to_out(r, person)


# ============================================================ DELETE


@router.delete("/records/{record_id}", status_code=204)
def delete_record(
    record_id: int,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    if not aq.can_write_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")

    target = _resolve_target_or_400(operator, tenant_org_id)
    r = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.id == record_id,
            AttendanceRecord.tenant_org_id == target,
            AttendanceRecord.deleted_at.is_(None),
        )
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="Record nicht gefunden")

    if not aq.can_modify_record(operator, r):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Löschen")

    r.deleted_at = datetime.now(tz=timezone.utc)
    r.active = False
    db.commit()


# ============================================================ SETTINGS


@router.get("/settings", response_model=AttendanceSettingsOut)
def get_settings(
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    target = _resolve_target_or_400(operator, tenant_org_id)
    return AttendanceSettingsOut.model_validate(aq.get_settings(db, target))


@router.patch("/settings", response_model=AttendanceSettingsOut)
def patch_settings(
    payload: AttendanceSettingsPatch,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    if not aq.can_modify_settings(operator):
        raise HTTPException(status_code=403, detail="Nur leitung/developer darf Settings ändern")

    target = _resolve_target_or_400(operator, tenant_org_id)

    s = db.query(AttendanceSettings).filter_by(tenant_org_id=target).first()
    now = datetime.now(tz=timezone.utc)
    if not s:
        s = AttendanceSettings(
            tenant_org_id=target,
            opens_at=payload.opens_at or time(7, 0),
            closes_at=payload.closes_at or time(17, 0),
            staff_ratio=payload.staff_ratio or {},
            metadata_=payload.metadata or {},
            created_at=now,
            updated_at=now,
        )
        db.add(s)
    else:
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            s.metadata_ = {**(s.metadata_ or {}), **data.pop("metadata")}
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, v)
        s.updated_at = now

    db.commit()
    db.refresh(s)
    return AttendanceSettingsOut.model_validate(s)


# ============================================================ HEIM-PROVIDER


@router.get("/live_counts", response_model=LiveCounts)
def get_live_counts(
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    target = _resolve_target_or_400(operator, tenant_org_id)
    today = datetime.now(tz=timezone.utc).date()
    data = aq.load_day(db, target, today, operator)
    return LiveCounts(**data["live_counts"])


@router.get("/week_summary", response_model=WeekSummary)
def get_week_summary(
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    if not aq.can_read_attendance(operator):
        raise HTTPException(status_code=403, detail="Keine Berechtigung")
    target = _resolve_target_or_400(operator, tenant_org_id)
    return WeekSummary(**aq.compute_week_summary(db, target))
