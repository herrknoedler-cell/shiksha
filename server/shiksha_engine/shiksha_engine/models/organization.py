"""Organization — KITA, Camping, Schule, Surf, Yoga, Club."""

from datetime import datetime
from typing import TYPE_CHECKING, Any
import secrets

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .identity_person import IdentityPerson
    from .operator import Operator
    from .session import Session


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = schema_args()

    id:         Mapped[str]      = mapped_column(String(64), primary_key=True)
    edition:    Mapped[str]      = mapped_column(String(32), nullable=False, index=True)
    name:       Mapped[str]      = mapped_column(String(128), nullable=False)
    legal_name: Mapped[str|None] = mapped_column(String(255), nullable=True)
    region:     Mapped[str|None] = mapped_column(String(64),  nullable=True)
    # Display-TZ pro Tenant — Backend speichert TIMESTAMPTZ als UTC,
    # Frontend rendert mit Intl.DateTimeFormat(..., {timeZone}). Siehe Spec §2.5.
    timezone:   Mapped[str]      = mapped_column(Text, nullable=False, server_default="Europe/Berlin")

    # Jurisdiktion (ISO 3166-2): "AT-8" für Vorarlberg, "DE-BY" für Bayern, …
    # Steuert DSGVO-Retention, MRZ-Whitelist, Aufsichtsbehörde — siehe
    # services/jurisdiction.py + editions/jurisdictions/<code>.yaml.
    # Default "AT-8" weil bisher nur AT-Tenants; bei neuen Tenants explicit setzen.
    jurisdiction: Mapped[str] = mapped_column(String(5), nullable=False, default="AT-8")

    # Per-Tenant-Salt für doc_number_hash (siehe SHIKSHA_IDENTITY_SPEC §7.1).
    # NIE über API exportieren — nur intern beim Hash-Compute lesen.
    identity_salt: Mapped[str] = mapped_column(
        String(64), nullable=False,
        default=lambda: secrets.token_hex(32),
    )

    metadata_: Mapped[dict]      = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = now_col()

    operators: Mapped[list["Operator"]] = relationship(back_populates="organization")
    sessions:  Mapped[list["Session"]]  = relationship(back_populates="organization")
    identity_persons: Mapped[list["IdentityPerson"]] = relationship(back_populates="tenant_organization")

    def __repr__(self) -> str:
        return f"<Organization {self.id} ({self.edition})>"

    def jurisdiction_yaml(self) -> dict[str, Any]:
        """Liefert die merged jurisdiction-Config (LRU-gecached im Service)."""
        from shiksha_engine.services.jurisdiction import load_jurisdiction_config
        return load_jurisdiction_config(self.jurisdiction)
