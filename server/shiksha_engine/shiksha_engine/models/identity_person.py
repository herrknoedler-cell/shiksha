"""IdentityPerson — Stammdaten einer verifikationsfähigen Person.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.2.
Konventionen: SHIKSHA_REPO_MAP.md §3 (Schema-aware FKs, Mapped-Pattern).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shiksha_engine.db import Base, schema_name
from ._base import schema_args

if TYPE_CHECKING:
    from .identity_authorization import IdentityAuthorization
    from .identity_document import IdentityDocument
    from .organization import Organization
    from .operator import Operator
    from .person import Person


VERIFICATION_STATUS = ("pending", "verified", "rejected")
DOC_KINDS = ("personalausweis", "reisepass", "other")


class IdentityPerson(Base):
    __tablename__ = "identity_persons"
    __table_args__ = (
        CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name="ck_identity_persons_status",
        ),
        CheckConstraint(
            "doc_kind IS NULL OR doc_kind IN ('personalausweis', 'reisepass', 'other')",
            name="ck_identity_persons_doc_kind",
        ),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Ausweis-Daten (Datensparsamkeit: doc_number nur als gesalzener Hash)
    doc_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    doc_number_hash: Mapped[str | None] = mapped_column(String(24), nullable=True)
    doc_expiry: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Consent (verbatim Wortlaut, damit spätere Text-Änderungen rückwirkende
    # Einwilligungen nicht verfälschen — siehe Spec §7.1)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Verifikation
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    verified_by_operator_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Soft-Link zu persons (z.B. wenn die identity einem 'eltern'-persons-Record entspricht)
    linked_person_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(f"{schema_name()}.persons.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lifecycle
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    structured_delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    tenant_organization: Mapped["Organization"] = relationship(
        back_populates="identity_persons"
    )
    documents: Mapped[list["IdentityDocument"]] = relationship(
        back_populates="identity_person",
        cascade="all, delete-orphan",
    )
    authorizations: Mapped[list["IdentityAuthorization"]] = relationship(
        back_populates="subject_identity_person",
        cascade="all, delete-orphan",
    )
    verified_by: Mapped["Operator | None"] = relationship(
        foreign_keys=[verified_by_operator_id]
    )
    linked_person: Mapped["Person | None"] = relationship(
        foreign_keys=[linked_person_id]
    )

    # ---- Convenience-Properties ----

    @property
    def is_verified(self) -> bool:
        return self.verification_status == "verified"

    @property
    def is_pending(self) -> bool:
        return self.verification_status == "pending"

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IdentityPerson id={self.id} {self.full_name!r} "
            f"status={self.verification_status} tenant={self.tenant_org_id}>"
        )
