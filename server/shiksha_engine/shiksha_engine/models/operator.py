"""Operator — Identity-Tabelle für alle Personen, die mit SHIKSHA interagieren.

Trotz des historischen Namens "operators" deckt diese Tabelle seit Schritt 5
ALLE Identity-Typen ab — Trägerin, Pädagoge, Trainer (kind=staff), Eltern
und Teilnehmer (kind=klient), Developer (kind=system).

Die saubere Umbenennung auf 'identities' kommt in Phase 3, falls die
Praxis es verlangt.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .memory import MemoryEntry
    from .organization import Organization
    from .session import Session


# Identity-Hauptklassifikation (Spec §3)
IDENTITY_KINDS = ("staff", "klient", "system")

# Rollen pro Kind (Spec §4)
STAFF_ROLES   = ("leitung", "padagoge", "trainer")
KLIENT_ROLES  = ("eltern", "teilnehmer")
SYSTEM_ROLES  = ("developer",)

# Legacy-Rollen — bleiben gültig für bestehende Operator-Einträge.
# Migration nach Schritt 5: 'operator' wird zu 'leitung'/'padagoge' nach Funktion.
LEGACY_ROLES  = ("operator",)

ALL_ROLES = STAFF_ROLES + KLIENT_ROLES + SYSTEM_ROLES + LEGACY_ROLES


class Operator(Base):
    """Eine Person, die mit SHIKSHA interagiert.

    Felder:
      kind         — staff | klient | system (Hauptklassifikation)
      role         — feinere Sicht: leitung, padagoge, trainer, eltern,
                     teilnehmer, developer (legacy: operator)
      org_id       — Tenant-Bindung (genau eine Organisation in Phase 1)
      edition      — KITA, Yoga, Surf, ... (folgt aus org)
    """

    __tablename__ = "operators"
    __table_args__ = schema_args()

    id:           Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id:       Mapped[str|None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    edition:      Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    kind:         Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="staff",
        server_default="staff",
    )
    role:         Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    email:        Mapped[str|None] = mapped_column(String(255), nullable=True, unique=True)

    # WebAuthn Public-Key-Credentials (mehrere möglich — pro Gerät einer)
    webauthn_credentials: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    metadata_:    Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at:   Mapped[datetime] = now_col()

    organization: Mapped["Organization|None"] = relationship(back_populates="operators")
    sessions:     Mapped[list["Session"]]     = relationship(back_populates="operator")
    memory_entries: Mapped[list["MemoryEntry"]] = relationship(back_populates="operator")

    def __repr__(self) -> str:
        return f"<Operator {self.id} ({self.kind}/{self.role}, {self.edition})>"

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"

    @property
    def is_klient(self) -> bool:
        return self.kind == "klient"

    @property
    def is_system(self) -> bool:
        return self.kind == "system"
