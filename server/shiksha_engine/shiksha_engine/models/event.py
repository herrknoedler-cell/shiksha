"""Event-Model — Calendar-Modul.

SQLAlchemy-Model spiegelt die events-Tabelle aus Migration 0008.
Konventionen aus Spec §2 (SHIKSHA_CALENDAR_SPEC.md).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shiksha_engine.db import Base, schema_name
from ._base import schema_args


# ---------------------------------------------------------- Type-Konstanten

# Reserved core types (Cross-Edition, alle Editionen kennen sie)
CORE_EVENT_TYPES = ("termin",)

# Reserved virtual types (nicht in DB, vom Backend gemerged)
VIRTUAL_EVENT_TYPES = ("geburtstag",)

# Edition-spezifische Erweiterungen
KITA_EVENT_TYPES = CORE_EVENT_TYPES + ("urlaub", "abwesenheit", "kurs")
YOGA_EVENT_TYPES = CORE_EVENT_TYPES + ("urlaub", "workshop", "kurseinheit")
CAMPING_EVENT_TYPES = ("reservierung", "checkin", "checkout", "event")
SURF_EVENT_TYPES = CORE_EVENT_TYPES + ("session", "wave_window", "workshop")
SCHULE_EVENT_TYPES = CORE_EVENT_TYPES + ("urlaub", "klasse", "ferien")
CLUB_EVENT_TYPES = CORE_EVENT_TYPES + ("training", "spiel", "turnier")

EVENT_TYPES_BY_EDITION = {
    "kita": KITA_EVENT_TYPES,
    "yoga": YOGA_EVENT_TYPES,
    "camping": CAMPING_EVENT_TYPES,
    "surf": SURF_EVENT_TYPES,
    "schule": SCHULE_EVENT_TYPES,
    "club": CLUB_EVENT_TYPES,
}

# Urgency-Stufen (Spec §4.5)
URGENCY_LEVELS = ("normal", "important", "urgent")

# Urlaub-Status (Spec §6.3)
URLAUB_STATUS = ("approved", "pending", "rejected")

# Legacy-Sources für Daten-Import
LEGACY_SOURCES = ("kita_legacy_calendar",)


# ---------------------------------------------------------- Event-Model

class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("legacy_id", "legacy_source", name="uq_events_legacy"),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Idempotenz-Key für Legacy-Import
    legacy_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    legacy_source: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Typ + Inhalt
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Zeit (TIMESTAMPTZ — Storage UTC, Display-TZ aus organizations.timezone)
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Person-Verknüpfung — jsonb-Array von Person-IDs (Integer)
    participants: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list
    )

    # Edition-spezifisches (subtype, urgency, recurrence_group, status, …)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata_", JSONB, nullable=False, default=dict
    )

    # Audit
    operator_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Helper-Properties (read-side comfort)

    @property
    def subtype(self) -> str | None:
        return (self.metadata_ or {}).get("subtype")

    @property
    def urgency(self) -> str:
        return (self.metadata_ or {}).get("urgency", "normal")

    @property
    def status(self) -> str:
        return (self.metadata_ or {}).get("status", "approved")

    @property
    def recurrence_group(self) -> str | None:
        return (self.metadata_ or {}).get("recurrence_group")

    @property
    def is_synthetic(self) -> bool:
        return bool((self.metadata_ or {}).get("synthetic"))

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Event id={self.id} type={self.event_type} "
            f"title={self.title[:30]!r} start={self.start_at.isoformat()}>"
        )
