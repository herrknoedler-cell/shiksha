"""MemoryEntry — was SHIKSHA über einen Operator über die Zeit weiß."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .operator import Operator


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
    created_at:        Mapped[datetime] = now_col()

    operator: Mapped["Operator"] = relationship(back_populates="memory_entries")

    def __repr__(self) -> str:
        return f"<MemoryEntry #{self.id} {self.operator_id}: {self.text[:40]}...>"
