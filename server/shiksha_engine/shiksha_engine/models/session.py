"""Session — eine Konversations-Sitzung (kennenlernen, tagesausklang, ...)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .friction import FrictionPoint
    from .message import Message
    from .observation import Observation
    from .operator import Operator
    from .organization import Organization


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = schema_args()

    id:           Mapped[str] = mapped_column(String(64), primary_key=True)
    operator_id:  Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    org_id:       Mapped[str|None] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    edition:      Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    persona:      Mapped[str] = mapped_column(String(64), nullable=False)
    started_at:   Mapped[datetime] = now_col()
    closed_at:    Mapped[datetime|None] = mapped_column(nullable=True)
    summary:      Mapped[str|None] = mapped_column(Text, nullable=True)
    insights:     Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    meta:         Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tokens_used:  Mapped[int]  = mapped_column(Integer, default=0, nullable=False)

    operator:     Mapped["Operator"]              = relationship(back_populates="sessions")
    organization: Mapped["Organization|None"]     = relationship(back_populates="sessions")
    messages:     Mapped[list["Message"]]         = relationship(
        back_populates="session", cascade="all, delete-orphan", order_by="Message.ts"
    )
    observations: Mapped[list["Observation"]]     = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    friction_points: Mapped[list["FrictionPoint"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Session {self.id} ({self.persona}, {self.edition})>"
