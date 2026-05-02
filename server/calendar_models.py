# calendar_models.py
# SHIKSHA calendar.module — Pydantic Models
# Version: 1.0
# Editionsunabhängig — CRM-Basis vorbereitet

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ---------------------------------------------------------------------------
# EVENT CREATE
# ---------------------------------------------------------------------------

class CalendarEventCreate(BaseModel):
    event_type: str                         # appointment | deadline | reminder | course_session
    title: str
    description: Optional[str] = None
    entity_id: Optional[str] = None
    document_id: Optional[str] = None
    ledger_entry_id: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    reminder_at: Optional[datetime] = None
    edition: str = "business.shiksha"
    # CRM
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    outcome: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    tags: Optional[List[str]] = []


# ---------------------------------------------------------------------------
# EVENT FULL
# ---------------------------------------------------------------------------

class CalendarEvent(BaseModel):
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None      # aufgelöst aus customers
    document_id: Optional[str] = None
    ledger_entry_id: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: bool = False
    status: str = "scheduled"
    reminder_at: Optional[datetime] = None
    reminder_sent: bool = False
    edition: str = "business.shiksha"
    # CRM
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    outcome: Optional[str] = None
    follow_up_at: Optional[datetime] = None
    follow_up_done: bool = False
    tags: List[str] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# EVENT LIST RESPONSE
# ---------------------------------------------------------------------------

class CalendarEventsResponse(BaseModel):
    count: int
    events: List[CalendarEvent]


# ---------------------------------------------------------------------------
# OUTCOME UPDATE — CRM
# ---------------------------------------------------------------------------

class EventOutcomeRequest(BaseModel):
    outcome: str
    follow_up_at: Optional[datetime] = None
    tags: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# DEADLINE SYNC — aus Ledger
# ---------------------------------------------------------------------------

class DeadlineSyncResponse(BaseModel):
    created: int
    skipped: int
    events: List[CalendarEvent]
