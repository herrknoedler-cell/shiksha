# calendar_module.py
# SHIKSHA calendar.module — Kernlogik Stufe 1
# Version: 1.0
#
# Verantwortung:
# - Termine anlegen, abrufen, abschließen
# - Fälligkeiten aus Ledger synchronisieren
# - Upcoming-View (nächste 30 Tage)
# - CRM-Basis: outcome, follow_up, tags
#
# Editionsunabhängig — Edition wird pro Event gespeichert

import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import sqlalchemy as sa

from calendar_models import (
    CalendarEvent,
    CalendarEventCreate,
    CalendarEventsResponse,
    EventOutcomeRequest,
    DeadlineSyncResponse,
)


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

from database import engine as _shared_engine

def _engine():
    return _shared_engine

def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# ROW → MODEL
# ---------------------------------------------------------------------------

def _row_to_event(r) -> CalendarEvent:
    tags = r.tags if isinstance(r.tags, list) else (json.loads(r.tags) if r.tags else [])
    return CalendarEvent(
        id=r.id,
        event_type=r.event_type,
        title=r.title,
        description=r.description,
        entity_id=r.entity_id,
        entity_name=getattr(r, 'entity_name', None),
        document_id=r.document_id,
        ledger_entry_id=getattr(r, 'ledger_entry_id', None),
        start_at=r.start_at,
        end_at=r.end_at,
        all_day=r.all_day or False,
        status=r.status or "scheduled",
        reminder_at=r.reminder_at,
        reminder_sent=r.reminder_sent or False,
        edition=r.edition or "business.shiksha",
        contact_name=r.contact_name,
        contact_email=r.contact_email,
        contact_phone=r.contact_phone,
        outcome=r.outcome,
        follow_up_at=r.follow_up_at,
        follow_up_done=r.follow_up_done or False,
        tags=tags,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


# ---------------------------------------------------------------------------
# 1. TERMIN ANLEGEN
# ---------------------------------------------------------------------------

def create_event(request: CalendarEventCreate) -> CalendarEvent:
    engine = _engine()
    now = _now()
    event_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO calendar_events (
                id, event_type, title, description,
                entity_id, document_id, ledger_entry_id,
                start_at, end_at, all_day, status,
                reminder_at, reminder_sent, edition,
                contact_name, contact_email, contact_phone,
                outcome, follow_up_at, follow_up_done,
                tags, created_at, updated_at
            ) VALUES (
                :id, :event_type, :title, :description,
                :entity_id, :document_id, :ledger_entry_id,
                :start_at, :end_at, :all_day, 'scheduled',
                :reminder_at, FALSE, :edition,
                :contact_name, :contact_email, :contact_phone,
                :outcome, :follow_up_at, FALSE,
                :tags, :created_at, :updated_at
            )
        """), {
            "id": event_id,
            "event_type": request.event_type,
            "title": request.title,
            "description": request.description,
            "entity_id": request.entity_id,
            "document_id": request.document_id,
            "ledger_entry_id": request.ledger_entry_id,
            "start_at": request.start_at,
            "end_at": request.end_at,
            "all_day": request.all_day,
            "reminder_at": request.reminder_at,
            "edition": request.edition,
            "contact_name": request.contact_name,
            "contact_email": request.contact_email,
            "contact_phone": request.contact_phone,
            "outcome": request.outcome,
            "follow_up_at": request.follow_up_at,
            "tags": json.dumps(request.tags or []),
            "created_at": now,
            "updated_at": now,
        })

    return CalendarEvent(
        id=event_id,
        event_type=request.event_type,
        title=request.title,
        description=request.description,
        entity_id=request.entity_id,
        document_id=request.document_id,
        ledger_entry_id=request.ledger_entry_id,
        start_at=request.start_at,
        end_at=request.end_at,
        all_day=request.all_day,
        status="scheduled",
        reminder_at=request.reminder_at,
        reminder_sent=False,
        edition=request.edition,
        contact_name=request.contact_name,
        contact_email=request.contact_email,
        contact_phone=request.contact_phone,
        outcome=request.outcome,
        follow_up_at=request.follow_up_at,
        follow_up_done=False,
        tags=request.tags or [],
        created_at=now,
    )


# ---------------------------------------------------------------------------
# 2. TERMINE ABRUFEN
# ---------------------------------------------------------------------------

def get_events(
    entity_id: Optional[str] = None,
    event_type: Optional[str] = None,
    edition: Optional[str] = None,
    status: Optional[str] = None,
) -> CalendarEventsResponse:

    query = """
        SELECT ce.*, c.name AS entity_name
        FROM calendar_events ce
        LEFT JOIN customers c ON c.id = ce.entity_id
        WHERE 1=1
    """
    params = {}

    if entity_id:
        query += " AND ce.entity_id = :entity_id"
        params["entity_id"] = entity_id
    if event_type:
        query += " AND ce.event_type = :event_type"
        params["event_type"] = event_type
    if edition:
        query += " AND ce.edition = :edition"
        params["edition"] = edition
    if status:
        query += " AND ce.status = :status"
        params["status"] = status

    query += " ORDER BY ce.start_at ASC NULLS LAST, ce.created_at DESC"

    with _engine().connect() as conn:
        rows = conn.execute(sa.text(query), params).fetchall()

    events = [_row_to_event(r) for r in rows]
    return CalendarEventsResponse(count=len(events), events=events)


# ---------------------------------------------------------------------------
# 3. UPCOMING — nächste 30 Tage
# ---------------------------------------------------------------------------

def get_upcoming(
    edition: Optional[str] = None,
    entity_id: Optional[str] = None,
    days: int = 30,
) -> CalendarEventsResponse:

    now = _now()
    until = now + timedelta(days=days)

    query = """
        SELECT ce.*, c.name AS entity_name
        FROM calendar_events ce
        LEFT JOIN customers c ON c.id = ce.entity_id
        WHERE ce.status = 'scheduled'
          AND (
            (ce.start_at >= :now AND ce.start_at <= :until)
            OR
            (ce.follow_up_at >= :now AND ce.follow_up_at <= :until AND ce.follow_up_done = FALSE)
          )
    """
    params = {"now": now, "until": until}

    if edition:
        query += " AND ce.edition = :edition"
        params["edition"] = edition
    if entity_id:
        query += " AND ce.entity_id = :entity_id"
        params["entity_id"] = entity_id

    query += " ORDER BY COALESCE(ce.start_at, ce.follow_up_at) ASC"

    with _engine().connect() as conn:
        rows = conn.execute(sa.text(query), params).fetchall()

    events = [_row_to_event(r) for r in rows]
    return CalendarEventsResponse(count=len(events), events=events)


# ---------------------------------------------------------------------------
# 4. TERMIN ABSCHLIESSEN
# ---------------------------------------------------------------------------

def mark_event_done(event_id: str) -> CalendarEvent:
    now = _now()

    with _engine().begin() as conn:
        conn.execute(sa.text("""
            UPDATE calendar_events
            SET status = 'done', updated_at = :now
            WHERE id = :id
        """), {"id": event_id, "now": now})

        row = conn.execute(sa.text("""
            SELECT ce.*, c.name AS entity_name
            FROM calendar_events ce
            LEFT JOIN customers c ON c.id = ce.entity_id
            WHERE ce.id = :id
        """), {"id": event_id}).fetchone()

    if not row:
        raise ValueError(f"Event nicht gefunden: {event_id}")

    return _row_to_event(row)


# ---------------------------------------------------------------------------
# 5. OUTCOME + FOLLOW-UP SETZEN — CRM
# ---------------------------------------------------------------------------

def set_outcome(event_id: str, request: EventOutcomeRequest) -> CalendarEvent:
    now = _now()

    with _engine().begin() as conn:
        conn.execute(sa.text("""
            UPDATE calendar_events
            SET outcome = :outcome,
                follow_up_at = :follow_up_at,
                tags = CASE WHEN :tags IS NOT NULL THEN :tags::jsonb ELSE tags END,
                updated_at = :now
            WHERE id = :id
        """), {
            "id": event_id,
            "outcome": request.outcome,
            "follow_up_at": request.follow_up_at,
            "tags": json.dumps(request.tags) if request.tags is not None else None,
            "now": now,
        })

        row = conn.execute(sa.text("""
            SELECT ce.*, c.name AS entity_name
            FROM calendar_events ce
            LEFT JOIN customers c ON c.id = ce.entity_id
            WHERE ce.id = :id
        """), {"id": event_id}).fetchone()

    if not row:
        raise ValueError(f"Event nicht gefunden: {event_id}")

    return _row_to_event(row)


# ---------------------------------------------------------------------------
# 6. DEADLINES AUS LEDGER SYNCHRONISIEREN
# ---------------------------------------------------------------------------

def sync_deadlines_from_ledger(edition: str = "business.shiksha") -> DeadlineSyncResponse:
    """
    Liest offene Ledger-Einträge mit due_date.
    Erstellt calendar_events vom Typ 'deadline' — nur wenn noch nicht vorhanden.
    """
    engine = _engine()

    with engine.connect() as conn:
        ledger_rows = conn.execute(sa.text("""
            SELECT le.id, le.entity_id, le.amount, le.currency, le.due_date,
                   le.entry_type, c.name AS entity_name
            FROM ledger_entries le
            LEFT JOIN customers c ON c.id = le.entity_id
            WHERE le.status IN ('open', 'overdue')
              AND le.due_date IS NOT NULL
        """)).fetchall()

        existing = conn.execute(sa.text("""
            SELECT ledger_entry_id FROM calendar_events
            WHERE event_type = 'deadline'
              AND ledger_entry_id IS NOT NULL
        """)).fetchall()

    existing_ids = {r.ledger_entry_id for r in existing}

    created = []
    skipped = 0

    for r in ledger_rows:
        if r.id in existing_ids:
            skipped += 1
            continue

        # due_date parsen
        try:
            if r.due_date and "." in r.due_date:
                parts = r.due_date.strip().split(".")
                start_at = datetime(int(parts[2]), int(parts[1]), int(parts[0]), tzinfo=timezone.utc)
            else:
                start_at = None
        except Exception:
            start_at = None

        amount_str = f"{r.amount} {r.currency}" if r.amount else ""
        title = f"Fälligkeit: {r.entity_name or r.entity_id} — {amount_str}"

        event = create_event(CalendarEventCreate(
            event_type="deadline",
            title=title,
            entity_id=r.entity_id,
            ledger_entry_id=r.id,
            start_at=start_at,
            all_day=True,
            edition=edition,
            tags=["fälligkeit", r.entry_type],
        ))
        created.append(event)

    return DeadlineSyncResponse(
        created=len(created),
        skipped=skipped,
        events=created,
    )
