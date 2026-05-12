"""MemoryEntry — was SHIKSHA über einen Operator über die Zeit weiß."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .operator import Operator


# Memory-Status:
#   active    — gilt im System-Prompt, Mira hat es bestätigt oder es kam
#               aus dem Close-Insights-Flow (manuell kuratiert).
#   proposed  — von einem Tool-Call inline während einer Session erzeugt.
#               Mira muss bestätigen, bevor es in den System-Prompt wandert.
#   dismissed — abgelehnt; bleibt für Audit, geht nicht mehr in den Prompt.
MEMORY_STATUSES = ("active", "proposed", "dismissed")


class MemoryEntry(Base):
    """Eine Erinnerung. Wird im System-Prompt mitgegeben für Wiederbeginn."""

    __tablename__ = "memory_entries"
    __table_args__ = schema_args()

    id:                Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator_id:       Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition:           Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    text:              Mapped[str] = mapped_column(Text, nullable=False)
    source_session_id: Mapped[str|None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status:            Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        server_default="active",
    )
    created_at:        Mapped[datetime] = now_col()
    deleted_at:        Mapped[datetime|None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    operator: Mapped["Operator"] = relationship(back_populates="memory_entries")

    def __repr__(self) -> str:
        return f"<MemoryEntry #{self.id} {self.operator_id} [{self.status}]: {self.text[:40]}...>"
