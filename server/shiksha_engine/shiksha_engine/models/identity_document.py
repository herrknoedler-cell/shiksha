"""IdentityDocument — Datei-Refs + OCR/MRZ-Output (whitelist-gefiltert).

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.3.
Two-Tier-Retention: file_ref wird nach jurisdiction.retention.scan_files_days
auf NULL gesetzt + Datei gelöscht; der Record bleibt als Audit-Nachweis
bis identity_person.structured_delete_at.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shiksha_engine.db import Base, schema_name
from ._base import schema_args

if TYPE_CHECKING:
    from .identity_person import IdentityPerson
    from .operator import Operator


DOC_KINDS = ("id_front", "id_back", "passport", "other")


class IdentityDocument(Base):
    __tablename__ = "identity_documents"
    __table_args__ = (
        CheckConstraint(
            "doc_kind IN ('id_front', 'id_back', 'passport', 'other')",
            name="ck_identity_documents_kind",
        ),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    identity_person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(f"{schema_name()}.identity_persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    doc_kind: Mapped[str] = mapped_column(String(20), nullable=False)

    # File-Ref — NULL nach Tier-1-Auto-Delete (~30 Tage in AT)
    file_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # SHA-256 des Original-Files — Integritäts-Nachweis bleibt auch nach
    # file_ref=NULL ("dieses File wurde verarbeitet")
    original_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # OCR + MRZ (mrz_parsed = nur whitelist-Felder, raw nie persistiert)
    ocr_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    mrz_parsed: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    mrz_check_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Audit
    uploaded_by_operator_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    identity_person: Mapped["IdentityPerson"] = relationship(back_populates="documents")
    uploaded_by: Mapped["Operator | None"] = relationship(
        foreign_keys=[uploaded_by_operator_id]
    )

    @property
    def has_file(self) -> bool:
        """Tier-1-Status: ist die Original-Datei noch da?"""
        return self.file_ref is not None

    def __repr__(self) -> str:  # pragma: no cover
        file_state = "file" if self.has_file else "file-deleted"
        return (
            f"<IdentityDocument id={self.id} person={self.identity_person_id} "
            f"kind={self.doc_kind} {file_state}>"
        )
