"""IdentityAuthorization — Was darf eine verifizierte Person?

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.4.
target_type='global' mit target_id=NULL bedeutet "alle Targets des Tenants"
(z.B. Voll-Sorge-Eltern). DB-CHECK-Constraint enforced die Konsistenz.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shiksha_engine.db import Base, schema_name
from ._base import schema_args

if TYPE_CHECKING:
    from .identity_person import IdentityPerson
    from .operator import Operator
    from .organization import Organization


TARGET_TYPES = ("child", "booking", "lesson", "global")
AUTH_METHODS = ("ausweis_scan", "passkey_signed", "manual_override")


class IdentityAuthorization(Base):
    __tablename__ = "identity_authorizations"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('child', 'booking', 'lesson', 'global')",
            name="ck_identity_authz_target_type",
        ),
        CheckConstraint(
            "auth_method IN ('ausweis_scan', 'passkey_signed', 'manual_override')",
            name="ck_identity_authz_method",
        ),
        CheckConstraint(
            "(target_type = 'global' AND target_id IS NULL) "
            "OR (target_type != 'global' AND target_id IS NOT NULL)",
            name="ck_identity_authz_target_consistency",
        ),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_identity_person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{schema_name()}.identity_persons.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Was darf die Person?
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Wie wurde authorisiert? Phase-2-Erweiterung: passkey_signed
    auth_method: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ausweis_scan",
    )

    # Gültigkeit
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Widerruf (kein Hard-Delete — Audit-Trail bleibt)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_operator_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Genehmigung (Pflicht — wer hat die Berechtigung erteilt?)
    granted_by_operator_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=False,
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    subject_identity_person: Mapped["IdentityPerson"] = relationship(
        back_populates="authorizations"
    )
    granted_by: Mapped["Operator"] = relationship(foreign_keys=[granted_by_operator_id])
    revoked_by: Mapped["Operator | None"] = relationship(foreign_keys=[revoked_by_operator_id])

    @property
    def is_active(self) -> bool:
        """Berechtigung gerade gültig?"""
        if self.revoked_at is not None:
            return False
        now = datetime.utcnow()
        if self.valid_to is not None and self.valid_to.replace(tzinfo=None) < now:
            return False
        return True

    def __repr__(self) -> str:  # pragma: no cover
        state = "active" if self.is_active else "inactive"
        return (
            f"<IdentityAuthorization id={self.id} "
            f"subject={self.subject_identity_person_id} "
            f"target={self.target_type}:{self.target_id} {state}>"
        )
