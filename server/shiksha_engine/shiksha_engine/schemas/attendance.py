"""Attendance-Schemas — Pydantic v2.

Spec: SHIKSHA_ATTENDANCE_SPEC.md §10.
Konventionen: validation_alias statt alias (Repo-Map §5).

Datetime-Hinweis (Spec L3):
  check_in_at/check_out_at/expected_in_at/expected_out_at sind ECHTE datetime,
  nicht time. Frontend muss "08:10" + date + tenant-TZ zu vollem ISO-Datetime
  kombinieren. URL-Param-Tests müssen Z-Suffix erzwingen.
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------- Sub-Modelle


class PersonBrief(BaseModel):
    """Mini-Stempel für UI-Render. Wiederverwendet aus calendar-Pattern."""
    id: int
    given_name: str
    family_name: Optional[str] = None
    kind: str
    group_id: Optional[int] = None


# ---------------------------------------------------------- Out-Schemas


class AttendanceOut(BaseModel):
    """Detail-View, inkl. resolved person brief + metadata."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: Optional[int] = None  # None für virtuelle Records (aus Calendar-Merge)
    person_id: int
    person_brief: Optional[PersonBrief] = None
    date: date
    status: str

    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None

    group_id: Optional[int] = None
    notes: Optional[str] = None

    source: str = "manual"
    source_event_id: Optional[int] = None

    metadata: dict[str, Any] = Field(
        default_factory=dict, validation_alias="metadata_"
    )

    operator_id: Optional[str] = None
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    virtual: bool = False  # True wenn aus Calendar gemerged


# ---------------------------------------------------------- In-Schemas


class AttendanceCreate(BaseModel):
    """
    Payload für POST /records.

    Spezialfall — Promotion eines virtuellen Records:
      Wenn source_event_id gesetzt ist UND ein Calendar-Event mit dieser ID
      existiert, wird der echte Record als 'overrides virtual' interpretiert.
      Frontend nutzt das, wenn Mira auf einen virtuellen Record tippt und
      den Status ändert.

    late_arrival_minutes / early_pickup_minutes werden NICHT vom Client gesetzt —
    Backend rechnet sie aus check_in_at - expected_in_at automatisch.
    """
    person_id: int
    date: date
    status: str

    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None

    group_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    source: str = "manual"
    source_event_id: Optional[int] = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    # Developer-Override für Tenant-Kontext
    tenant_org_id: Optional[str] = None


class AttendancePatch(BaseModel):
    """Payload für PATCH /records/{id} — alle Felder optional."""
    status: Optional[str] = None

    check_in_at: Optional[datetime] = None
    check_out_at: Optional[datetime] = None
    expected_in_at: Optional[datetime] = None
    expected_out_at: Optional[datetime] = None

    group_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=2000)

    metadata: Optional[dict[str, Any]] = None
    active: Optional[bool] = None


# ---------------------------------------------------------- Settings-Schemas


class AttendanceSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    tenant_org_id: str
    opens_at: time
    closes_at: time
    staff_ratio: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(
        default_factory=dict, validation_alias="metadata_"
    )


class AttendanceSettingsPatch(BaseModel):
    opens_at: Optional[time] = None
    closes_at: Optional[time] = None
    staff_ratio: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------- Live-Counts / Heim-Provider


RatioStatus = Literal["green", "yellow", "red"]


class LiveCounts(BaseModel):
    """
    Provider-Output für Heim-Karten 'Wer ist da' und 'Personalschlüssel'.

    Wird vom Endpoint GET /api/v1/attendance/live_counts geliefert
    UND vom Heim-Provider attendance.live_counts genutzt.
    """
    kids_present_count: int
    staff_present_count: int

    ratio_status: RatioStatus = "green"
    ratio_status_label: str = "grün ✓"
    ratio_explanation: Optional[str] = None  # "1 Päd. fehlt ab 13:00" oder None

    next_check_at: Optional[datetime] = None  # nächste Spitzenzeit


class WeekSummary(BaseModel):
    """Provider-Output für Heim-Karte 'Anwesenheit Woche'."""
    avg_present_count: float  # ø Kinder/Tag der letzten 7 Tage
    days_observed: int        # wie viele Tage zur Berechnung


# ---------------------------------------------------------- Day-View / Overview


class DayView(BaseModel):
    """GET /api/v1/attendance/day — der ganze Tag in einer Antwort."""
    date: date
    records: list[AttendanceOut]
    settings: AttendanceSettingsOut
    live_counts: LiveCounts


class OverviewDay(BaseModel):
    date: date
    is_open_day: bool        # opens_at < closes_at gibt's
    is_holiday: bool         # explizit als Schließtag im Kalender
    present_count: int
    expected_count: int


class Overview(BaseModel):
    """GET /api/v1/attendance/overview?from=…&to=… — kompakte Tagesübersicht."""
    days: list[OverviewDay]
