"""IdentityAuditLog — DSGVO-Pflicht, jeder Zugriff auf Identity-Daten.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §3.5.
Retention: 7 Jahre (Art. 5(2) DSGVO Rechenschaftspflicht).
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shiksha_engine.db import Base, schema_name
from ._base import schema_args

if TYPE_CHECKING:
    from .operator import Operator


ACTOR_KINDS = ("operator", "system", "subject_self")


class IdentityAuditLog(Base):
    __tablename__ = "identity_audit_log"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('operator', 'system', 'subject_self')",
            name="ck_audit_actor_kind",
        ),
        schema_args(),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    tenant_org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    actor_operator_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="operator")

    # Was wurde gemacht?
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Action-spezifische Details (z.B. {old_status, new_status, doc_number_hash})
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    actor: Mapped["Operator | None"] = relationship(foreign_keys=[actor_operator_id])

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<IdentityAuditLog id={self.id} {self.action} "
            f"target={self.target_kind}:{self.target_id} actor={self.actor_operator_id}>"
        )
