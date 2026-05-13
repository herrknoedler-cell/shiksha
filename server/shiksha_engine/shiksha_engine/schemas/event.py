"""Event-Schemas — Pydantic-Modelle für Calendar-Endpoints.

Schemas folgen dem Pattern aus persons. Konventionen siehe SHIKSHA_CALENDAR_SPEC.md §10.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------- Sub-Modelle

class ParticipantBrief(BaseModel):
    """Minimaler Person-Stempel für UI-Rendering (Avatar + Name)."""
    id: int
    given_name: str
    family_name: Optional[str] = None
    kind: str  # 'kind' | 'staff' | 'eltern' | …


class EventRepeat(BaseModel):
    """Optional bei POST: client-side Multi-Insert für Wiederholungen."""
    kind: Literal["daily", "weekly", "monthly"]
    count: int = Field(ge=2, le=104)  # max 2 Jahre wöchentlich


# ---------------------------------------------------------- Out-Schemas

class EventListItem(BaseModel):
    """Liste-Item — flache Daten ohne metadata für Performance."""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None  # None für virtuelle Events (Geburtstage)
    event_type: str
    title: str
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool
    location: Optional[str] = None
    participants: list[int] = []

    # Lightweight metadata-projection
    subtype: Optional[str] = None
    urgency: str = "normal"
    status: str = "approved"
    synthetic: bool = False


class EventOut(BaseModel):
    """Detail-View mit voller metadata + resolved participants."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: Optional[int] = None
    tenant_org_id: str
    event_type: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool
    participants: list[int] = []
    participants_resolved: list[ParticipantBrief] = []
    # Input-Alias liest von SQLAlchemy's metadata_ (Naming-Collision-Vermeidung).
    # Output bleibt JSON-Key 'metadata' (field-name) durch populate_by_name=True.
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    operator_id: Optional[str] = None
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------- In-Schemas

class EventCreate(BaseModel):
    """Payload für POST /events."""
    event_type: str
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: datetime
    end_at: Optional[datetime] = None
    all_day: bool = False
    participants: list[int] = []
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Multi-Tenant-Hint (nur für developer; sonst aus operator.org_id resolved)
    tenant_org_id: Optional[str] = None

    # Optional: Wiederholung als client-side Multi-Insert
    repeat: Optional[EventRepeat] = None

    @field_validator("end_at")
    @classmethod
    def end_after_start(cls, v, info):  # noqa: ANN001
        start = info.data.get("start_at")
        if v is not None and start is not None and v < start:
            raise ValueError("end_at darf nicht vor start_at liegen")
        return v


class EventPatch(BaseModel):
    """Payload für PATCH /events/{id} — alle Felder optional."""
    event_type: Optional[str] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=255)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    all_day: Optional[bool] = None
    participants: Optional[list[int]] = None
    metadata: Optional[dict[str, Any]] = None
    active: Optional[bool] = None


# ---------------------------------------------------------- Stats-Schemas (Spec §10)

class EventStats(BaseModel):
    """GET /api/v1/calendar/stats — Übersicht für UI-Stats-Line."""
    total: int
    today: int
    this_week: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class TodaySummary(BaseModel):
    """GET /api/v1/calendar/today_summary — Provider-Quelle für Heim-Karte 'Heute'."""
    event_count_today: int
    staff_count_today: int  # Staff ohne Urlaub/Abwesenheit heute
    next_event: Optional[EventListItem] = None
