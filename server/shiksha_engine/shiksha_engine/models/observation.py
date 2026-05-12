"""Observation — Beobachtung aus einem Gespräch (Tool-Output)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .session import Session


# Spezielle Observation-Kinds, die nicht edition-spezifisch sind.
OBSERVATION_KIND_SUMMARY = "summary"  # save_day_summary Tool-Output


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = schema_args()

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition:    Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    kind:       Mapped[str|None] = mapped_column(String(32), nullable=True)
    # Core-Kinds: "summary" (save_day_summary), "observation" (log_observation)
    # Edition-Kinds: KITA "kind_observation", Camping "gast_observation", ...
    text:       Mapped[str] = mapped_column(Text, nullable=False)
    metadata_:  Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    # metadata kann tool-spezifische Felder tragen, z.B.
    #   {"mood": "klar"} bei save_day_summary
    #   {"category": "personal"} bei log_observation
    ts:         Mapped[datetime] = now_col()
    deleted_at: Mapped[datetime|None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    session: Mapped["Session"] = relationship(back_populates="observations")

    def __repr__(self) -> str:
        return f"<Observation #{self.id} {self.kind} in {self.session_id}>"
