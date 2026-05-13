"""Calendar — REST-Endpoints für /api/v1/calendar.

Spec: SHIKSHA_CALENDAR_SPEC.md §10.
Berechtigung + Query-Building leben in services/calendar_query.py.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from shiksha_engine.db import get_db
from shiksha_engine.deps import require_authenticated, require_operator_or_developer
from shiksha_engine.models.event import Event
from shiksha_engine.models.operator import Operator
from shiksha_engine.schemas.event import (
    EventCreate,
    EventListItem,
    EventOut,
    EventPatch,
    EventStats,
    TodaySummary,
)
from shiksha_engine.services import calendar_query as cq
from shiksha_engine.services.event_types import (
    is_valid_type,
    is_valid_urgency,
    is_valid_urlaub_status,
    normalize_metadata,
)

router = APIRouter()


# ---------------------------------------------------------- Helpers


def _to_list_item(e: Event) -> EventListItem:
    return EventListItem(
        id=e.id,
        event_type=e.event_type,
        title=e.title,
        start_at=e.start_at,
        end_at=e.end_at,
        all_day=e.all_day,
        location=e.location,
        participants=list(e.participants or []),
        subtype=(e.metadata_ or {}).get("subtype"),
        urgency=(e.metadata_ or {}).get("urgency", "normal"),
        status=(e.metadata_ or {}).get("status", "approved"),
        synthetic=False,
    )


def _to_out(db: Session, e: Event) -> EventOut:
    return EventOut(
        id=e.id,
        tenant_org_id=e.tenant_org_id,
        event_type=e.event_type,
        title=e.title,
        description=e.description,
        location=e.location,
        start_at=e.start_at,
        end_at=e.end_at,
        all_day=e.all_day,
        participants=list(e.participants or []),
        participants_resolved=cq.participants_resolved(db, list(e.participants or [])),
        metadata=dict(e.metadata_ or {}),
        operator_id=e.operator_id,
        active=e.active,
        created_at=e.created_at,
        updated_at=e.updated_at,
    )


def _resolve_target_tenant_or_400(
    operator: Operator, payload_tenant: Optional[str]
) -> str:
    tenant = cq.resolve_target_tenant(operator, payload_tenant)
    if not tenant:
        raise HTTPException(
            status_code=400,
            detail="Developer must call from a tenant context (org_id required)",
        )
    return tenant


def _validate_payload_metadata(metadata: dict, event_type: str) -> dict:
    md = normalize_metadata(metadata)
    if not is_valid_urgency(md.get("urgency", "normal")):
        raise HTTPException(status_code=422, detail="Invalid urgency value")
    if event_type == "urlaub" and not is_valid_urlaub_status(md.get("status", "approved")):
        raise HTTPException(status_code=422, detail="Invalid urlaub status value")
    return md


# ---------------------------------------------------------- LIST


@router.get("/events", response_model=list[EventListItem])
def list_events(
    *,
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = None,
    type: Optional[str] = None,
    person_id: Optional[int] = None,
    include_birthdays: bool = True,
    limit: int = Query(500, ge=1, le=2000),
    tenant_org_id: Optional[str] = Query(None, description="Nur für Developer"),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)

    q = cq.apply_read_filter(db, db.query(Event), operator, target)

    if from_:
        q = q.filter(Event.start_at >= from_)
    if to:
        q = q.filter(Event.start_at < to)
    if type:
        q = q.filter(Event.event_type == type)
    if person_id is not None:
        # GIN-Index auf participants @> [person_id]
        q = q.filter(Event.participants.contains([person_id]))

    rows = q.order_by(Event.start_at.asc()).limit(limit).all()
    items = [_to_list_item(e) for e in rows]

    # Virtuelle Geburtstage mergen
    if include_birthdays and from_ and to and not type:
        birthdays = cq.get_birthday_events(db, target, from_, to, operator)
        # filter optional auf person_id
        if person_id is not None:
            birthdays = [b for b in birthdays if person_id in b.get("participants", [])]
        for b in birthdays:
            items.append(EventListItem(**{k: v for k, v in b.items() if k != "metadata"}))
        items.sort(key=lambda x: x.start_at)

    return items


# ---------------------------------------------------------- DETAIL


@router.get("/events/{event_id}", response_model=EventOut)
def get_event(
    event_id: int,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)
    q = cq.apply_read_filter(db, db.query(Event), operator, target)
    e = q.filter(Event.id == event_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")
    return _to_out(db, e)


# ---------------------------------------------------------- CREATE


@router.post("/events", response_model=list[EventOut], status_code=201)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    target = _resolve_target_tenant_or_400(operator, payload.tenant_org_id)

    # Edition aus organizations resolvern (über operator.org_id-Brücke)
    from shiksha_engine.models.organization import Organization
    org = db.query(Organization).filter_by(id=target).first()
    edition = org.edition if org else "kita"

    if not is_valid_type(edition, payload.event_type):
        raise HTTPException(
            status_code=422,
            detail=f"event_type '{payload.event_type}' nicht zulässig für edition '{edition}'",
        )

    if not cq.can_create(operator, payload.event_type):
        raise HTTPException(status_code=403, detail="Rolle darf diesen Event-Type nicht anlegen")

    md = _validate_payload_metadata(payload.metadata, payload.event_type)

    # Multi-Insert wenn Repeat — gemeinsame recurrence_group
    if payload.repeat:
        group_id = cq.fresh_recurrence_group()
        expansions = cq.expand_repeat(
            payload.start_at, payload.end_at, payload.repeat.kind, payload.repeat.count
        )
    else:
        expansions = [(payload.start_at, payload.end_at, 1)]
        group_id = None

    created: list[Event] = []
    now = datetime.now(tz=timezone.utc)

    for start_at, end_at, idx in expansions:
        instance_md = dict(md)
        if group_id is not None:
            instance_md["recurrence_group"] = group_id
            instance_md["recurrence_index"] = idx
        e = Event(
            tenant_org_id=target,
            event_type=payload.event_type,
            title=payload.title,
            description=payload.description,
            location=payload.location,
            start_at=start_at,
            end_at=end_at,
            all_day=payload.all_day,
            participants=list(payload.participants),
            metadata_=instance_md,
            operator_id=operator.id,
            active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(e)
        created.append(e)

    db.commit()
    for e in created:
        db.refresh(e)

    return [_to_out(db, e) for e in created]


# ---------------------------------------------------------- PATCH


@router.patch("/events/{event_id}", response_model=EventOut)
def patch_event(
    event_id: int,
    payload: EventPatch,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)
    e = (
        db.query(Event)
        .filter(
            Event.id == event_id,
            Event.tenant_org_id == target,
            Event.deleted_at.is_(None),
        )
        .first()
    )
    if not e:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    if not cq.can_modify(operator, e):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Ändern")

    data = payload.model_dump(exclude_unset=True)

    if "event_type" in data:
        from shiksha_engine.models.organization import Organization
        org = db.query(Organization).filter_by(id=target).first()
        edition = org.edition if org else "kita"
        if not is_valid_type(edition, data["event_type"]):
            raise HTTPException(status_code=422, detail="Invalid event_type for edition")
        e.event_type = data.pop("event_type")

    if "metadata" in data:
        e.metadata_ = _validate_payload_metadata(data.pop("metadata"), e.event_type)

    for key, val in data.items():
        if hasattr(e, key):
            setattr(e, key, val)

    e.updated_at = datetime.now(tz=timezone.utc)
    db.commit()
    db.refresh(e)
    return _to_out(db, e)


# ---------------------------------------------------------- DELETE (soft)


@router.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: int,
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_operator_or_developer),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)
    e = (
        db.query(Event)
        .filter(
            Event.id == event_id,
            Event.tenant_org_id == target,
            Event.deleted_at.is_(None),
        )
        .first()
    )
    if not e:
        raise HTTPException(status_code=404, detail="Event nicht gefunden")

    if not cq.can_delete(operator, e):
        raise HTTPException(status_code=403, detail="Keine Berechtigung zum Löschen")

    e.deleted_at = datetime.now(tz=timezone.utc)
    e.active = False
    db.commit()


# ---------------------------------------------------------- STATS


@router.get("/stats", response_model=EventStats)
def get_stats(
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)
    return EventStats(**cq.compute_event_stats(db, target, operator))


# ---------------------------------------------------------- TODAY-SUMMARY


@router.get("/today_summary", response_model=TodaySummary)
def get_today_summary(
    tenant_org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    operator: Operator = Depends(require_authenticated),
):
    target = _resolve_target_tenant_or_400(operator, tenant_org_id)
    summary = cq.compute_today_summary(db, target, operator)
    next_event = summary["next_event"]
    return TodaySummary(
        event_count_today=summary["event_count_today"],
        staff_count_today=summary["staff_count_today"],
        next_event=_to_list_item(next_event) if next_event else None,
    )
