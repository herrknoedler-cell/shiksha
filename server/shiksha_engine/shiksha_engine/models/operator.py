"""Operator — Trägerin, Wirt, Lehrer, …, edition-agnostisch."""

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


class Operator(Base):
    """Eine Person, die mit SHIKSHA spricht. Rolle = operator|developer|observer."""

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
    role:         Mapped[str] = mapped_column(String(32), nullable=False, default="operator")
    email:        Mapped[str|None] = mapped_column(String(255), nullable=True, unique=True)

    # WebAuthn Public-Key-Credentials (mehrere möglich — pro Gerät einer)
    # Format: [{"credential_id": "...", "public_key": "...", "sign_count": 0,
    #           "transports": [...], "registered_at": "..."}]
    webauthn_credentials: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    metadata_:    Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at:   Mapped[datetime] = now_col()

    organization: Mapped["Organization|None"] = relationship(back_populates="operators")
    sessions:     Mapped[list["Session"]]     = relationship(back_populates="operator")
    memory_entries: Mapped[list["MemoryEntry"]] = relationship(back_populates="operator")

    def __repr__(self) -> str:
        return f"<Operator {self.id} ({self.role}, {self.edition})>"
