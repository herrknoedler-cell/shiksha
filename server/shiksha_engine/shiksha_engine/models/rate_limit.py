"""RateLimitBucket — pro Operator pro Tag ein Counter."""

from datetime import date as DateType
from datetime import datetime

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import schema_name
from ._base import Base, now_col, schema_args


class RateLimitBucket(Base):
    """Counter pro Operator pro Tag.

    Bei jedem Chat-/Tool-Call wird incrementiert. Bei Überschreitung
    der Operator-Quota (Default 200/Tag) gibt das Middleware 429 zurück.
    """

    __tablename__ = "rate_limit_buckets"
    __table_args__ = schema_args()

    operator_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey(f"{schema_name()}.operators.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day:         Mapped[DateType] = mapped_column(Date, primary_key=True)
    count:       Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at:  Mapped[datetime] = now_col()

    def __repr__(self) -> str:
        return f"<RateLimitBucket {self.operator_id} {self.day} count={self.count}>"
