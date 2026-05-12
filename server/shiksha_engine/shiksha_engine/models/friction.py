"""FrictionPoint — eine Reibungsstelle, die SHIKSHA wahrnimmt."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .session import Session


# Stärkegrade für Reibung — Mira-Vokabular, nicht Skala 1-10.
FRICTION_SEVERITIES = ("leicht", "mittel", "belastend")


class FrictionPoint(Base):
    """Offene Stelle. „Da klingt etwas mit, was Dich beschäftigt." → log_friction."""

    __tablename__ = "friction_points"
    __table_args__ = schema_args()

    id:                Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id:        Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition:           Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    where_label:       Mapped[str|None] = mapped_column(String(64), nullable=True)
    text:              Mapped[str] = mapped_column(Text, nullable=False)
    severity:          Mapped[str|None] = mapped_column(String(16), nullable=True)
    first_observed_at: Mapped[date|None] = mapped_column(Date, nullable=True)
    resolved:          Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ts:                Mapped[datetime] = now_col()
    deleted_at:        Mapped[datetime|None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    session: Mapped["Session"] = relationship(back_populates="friction_points")

    def __repr__(self) -> str:
        sev = f" [{self.severity}]" if self.severity else ""
        return f"<FrictionPoint #{self.id} {self.where_label}{sev} ({'✓' if self.resolved else '○'})>"
