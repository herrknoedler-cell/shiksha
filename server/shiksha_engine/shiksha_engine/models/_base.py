"""Gemeinsame Type-Helpers und Schema-Konfiguration für alle Models."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import mapped_column

from ..db import Base, schema_name


def schema_args() -> dict[str, str]:
    """Standard __table_args__ Schema-Bestandteil."""
    return {"schema": schema_name()}


def now_col(default_factory: Any = None):
    """Convenience für created_at / ts."""
    return mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow if default_factory is None else default_factory,
        nullable=False,
    )


# Re-export
__all__ = ["Base", "schema_args", "now_col"]
