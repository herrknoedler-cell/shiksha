"""Organization — KITA, Camping, Schule, Surf, Yoga, Club."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ._base import Base, now_col, schema_args

if TYPE_CHECKING:
    from .operator import Operator
    from .session import Session


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = schema_args()

    id:         Mapped[str]      = mapped_column(String(64), primary_key=True)
    edition:    Mapped[str]      = mapped_column(String(32), nullable=False, index=True)
    name:       Mapped[str]      = mapped_column(String(128), nullable=False)
    legal_name: Mapped[str|None] = mapped_column(String(255), nullable=True)
    region:     Mapped[str|None] = mapped_column(String(64),  nullable=True)
    metadata_: Mapped[dict]      = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = now_col()

    operators: Mapped[list["Operator"]] = relationship(back_populates="organization")
    sessions:  Mapped[list["Session"]]  = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization {self.id} ({self.edition})>"
