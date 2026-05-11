"""Observation — Beobachtung aus einem Gespräch (Tool-Output)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .session import Session


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
    # z.B. KITA: "kind_observation", "team_observation", "parent_communication"
    # z.B. Camping: "gast_observation", "weather_event"
    text:       Mapped[str] = mapped_column(Text, nullable=False)
    metadata_:  Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    ts:         Mapped[datetime] = now_col()

    session: Mapped["Session"] = relationship(back_populates="observations")

    def __repr__(self) -> str:
        return f"<Observation #{self.id} {self.kind} in {self.session_id}>"
