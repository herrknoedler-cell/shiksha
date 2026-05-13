"""Person — edition-agnostische Stammdaten-Entität.

Im Unterschied zu `operators` (alle Personen mit Login-Möglichkeit) hält
diese Tabelle alle Personen, von denen wir Stammdaten kennen — auch wenn
sie nie einloggen werden (z.B. Kinder, Eltern in Phase 1.5).

Kind-Discriminator:
  'kind'        — Kinder in KITA
  'staff'       — Mitarbeiter:innen (Pädagogen, Erzieher, ...)
  'eltern'      — Eltern in Phase 2 (vor Eltern-Login)
  'teilnehmer'  — Kursteilnehmer (Yoga, Schule, Surf, Club)
  'gast'        — Campingplatz-Gäste
  'trainer'     — Trainer für Yoga/Surf/Schule

operator_id (optional, FK) verbindet zur Login-Identity, falls die Person
einen Passkey hat (z.B. Mira selbst, oder ein Pädagoge mit eigenem Account).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .operator import Operator
    from .organization import Organization


# Erlaubte kind-Werte (Code-Constraint; Spec §3.1)
PERSON_KINDS = ("kind", "staff", "eltern", "teilnehmer", "gast", "trainer")

# Legacy-Quelle (für idempotenten Import)
LEGACY_SOURCES = ("kita_legacy_children", "kita_legacy_staff")


class Person(Base):
    """Eine Person mit Stammdaten im Kontext eines Tenants."""

    __tablename__ = "persons"
    __table_args__ = schema_args()

    id:            Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    legacy_id:     Mapped[int|None] = mapped_column(Integer, nullable=True)
    legacy_source: Mapped[str|None] = mapped_column(String(32), nullable=True)

    tenant_org_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind:          Mapped[str] = mapped_column(String(32), nullable=False)

    # Identität
    given_name:    Mapped[str]      = mapped_column(String(128), nullable=False)
    family_name:   Mapped[str|None] = mapped_column(String(128), nullable=True)
    birth_date:    Mapped[date|None] = mapped_column(Date, nullable=True)
    gender:        Mapped[str|None] = mapped_column(String(8), nullable=True)

    # Kontakt
    email:         Mapped[str|None] = mapped_column(String(255), nullable=True)
    phone:         Mapped[str|None] = mapped_column(String(64), nullable=True)
    address:       Mapped[str|None] = mapped_column(Text, nullable=True)

    # Organisation
    group_id:      Mapped[int|None] = mapped_column(Integer, nullable=True)
    entry_date:    Mapped[date|None] = mapped_column(Date, nullable=True)
    exit_date:     Mapped[date|None] = mapped_column(Date, nullable=True)

    # Notizen + polymorphe Detail-Daten
    notes:         Mapped[str|None] = mapped_column(Text, nullable=True)
    metadata_:     Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Verknüpfung zur Login-Identity
    operator_id:   Mapped[str|None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lifecycle
    active:        Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at:    Mapped[datetime] = now_col()
    updated_at:    Mapped[datetime] = now_col()
    deleted_at:    Mapped[datetime|None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization:  Mapped["Organization"] = relationship()
    operator:      Mapped["Operator|None"] = relationship()

    def __repr__(self) -> str:
        name = f"{self.given_name} {self.family_name or ''}".strip()
        return f"<Person #{self.id} {self.kind}: {name} ({self.tenant_org_id})>"

    @property
    def display_name(self) -> str:
        """Volle Namensanzeige."""
        return f"{self.given_name} {self.family_name or ''}".strip()
