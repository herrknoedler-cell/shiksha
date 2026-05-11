"""Message — einzelne Chat-Nachricht (user oder assistant)."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import schema_name
from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .session import Session


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = schema_args()

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role:       Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content:    Mapped[str] = mapped_column(Text,       nullable=False)
    mode:       Mapped[str|None] = mapped_column(String(16), nullable=True)
    # Für assistant: PRÄSENZ | FOKUS | VERDICHTEN | AUSKLANG
    ts:         Mapped[datetime] = now_col()

    session:    Mapped["Session"] = relationship(back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message #{self.id} {self.role} in {self.session_id}>"
