"""Attendance-Models — attendance_records + attendance_settings.

Spec: SHIKSHA_ATTENDANCE_SPEC.md §2.
Konventionen siehe SHIKSHA_REPO_MAP.md §3 (Schema-aware FKs, metadata_-Pattern, …).
"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Time,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shiksha_engine.db import Base, schema_name
from ._base import schema_args


# ---------------------------------------------------------- Status-Konstanten

# KITA — sechs Status (siehe Spec §3) plus "unbekannt" als Default
KITA_STATUS = (
    "anwesend",
    "abwesend",
    "krank",
    "urlaub",
    "fortbildung",
    "gast",
    "unbekannt",
)

YOGA_STATUS = ("anwesend", "abgesagt", "verspätet", "unbekannt")
CAMPING_STATUS = ("eingecheckt", "ausgecheckt", "noshow", "verlängert", "unbekannt")
SURF_STATUS = ("anwesend", "abgesagt", "verspätet", "unbekannt")
SCHULE_STATUS = ("anwesend", "abwesend", "krank", "entschuldigt", "unbekannt")
CLUB_STATUS = ("anwesend", "abwesend", "verletzt", "urlaub", "unbekannt")

STATUS_BY_EDITION = {
    "kita": KITA_STATUS,
    "yoga": YOGA_STATUS,
    "camping": CAMPING_STATUS,
    "surf": SURF_STATUS,
    "schule": SCHULE_STATUS,
    "club": CLUB_STATUS,
}

# Status, die als "im Haus" zählen (für Personalschlüssel-Berechnung)
PRESENT_STATUS = ("anwesend", "eingecheckt", "verlängert")

# Status, die als "Calendar-Brücke" virtuell aus events.event_type kommen
CALENDAR_VIRTUAL_STATUS = {
    "urlaub": "urlaub",
    "abwesenheit": "abwesend",
}

# Source-Werte
SOURCE_MANUAL = "manual"
SOURCE_CALENDAR_SYNC = "calendar_sync"
SOURCE_LEGACY_IMPORT = "legacy_import"
SOURCE_CRON = "cron"


# ---------------------------------------------------------- AttendanceRecord

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        Index(
            "uq_attendance_person_date_active",
            "person_id", "date",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{schema_name()}.persons.id", ondelete="CASCADE"),
        nullable=False,
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False)

    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(Text, nullable=False, default=SOURCE_MANUAL)
    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(f"{schema_name()}.events.id", ondelete="SET NULL"),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata_", JSONB, nullable=False, default=dict
    )

    operator_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ---- Convenience Properties ----

    @property
    def is_present(self) -> bool:
        """True wenn Status als 'im Haus' zählt."""
        return self.status in PRESENT_STATUS

    @property
    def is_virtual(self) -> bool:
        """Sollte False sein für DB-Records — virtuelle haben id=None."""
        return self.id is None

    @property
    def late_arrival_minutes(self) -> int | None:
        """Konvenienz: aus metadata_, von Backend berechnet."""
        return (self.metadata_ or {}).get("late_arrival_minutes")

    @property
    def early_pickup_minutes(self) -> int | None:
        return (self.metadata_ or {}).get("early_pickup_minutes")

    @property
    def subtype(self) -> str | None:
        return (self.metadata_ or {}).get("subtype")

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AttendanceRecord id={self.id} person={self.person_id} "
            f"date={self.date.isoformat()} status={self.status}>"
        )


# ---------------------------------------------------------- AttendanceSettings

class AttendanceSettings(Base):
    """Tenant-Config: Öffnungszeiten + Personalschlüssel."""
    __tablename__ = "attendance_settings"
    __table_args__ = (schema_args(),)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )

    opens_at: Mapped[time] = mapped_column(Time, nullable=False, default=time(7, 0))
    closes_at: Mapped[time] = mapped_column(Time, nullable=False, default=time(17, 0))

    # Personalschlüssel: {"3": 6, "6": 12} = bis 3 Jahre 6 Kinder/Päd, bis 6 Jahre 12/Päd
    staff_ratio: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata_", JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # ---- Helpers ----

    @property
    def gast_counts(self) -> bool:
        """Phase 1-Default: gast zählt. Tenant kann via metadata.gast_counts=false overriden."""
        return (self.metadata_ or {}).get("gast_counts", True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<AttendanceSettings tenant={self.tenant_org_id} "
            f"opens={self.opens_at} closes={self.closes_at} ratio={self.staff_ratio}>"
        )
