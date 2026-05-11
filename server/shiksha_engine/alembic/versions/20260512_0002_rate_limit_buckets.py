"""Add rate_limit_buckets table.

Revision ID: 0002_rate_limit
Revises: 0001_initial
Create Date: 2026-05-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0002_rate_limit"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("operator_id", sa.String(64),
                  sa.ForeignKey(f"{SCHEMA}.operators.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("day",         sa.Date,    primary_key=True),
        sa.Column("count",       sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at",  sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_rate_limit_day_op",
        "rate_limit_buckets",
        ["day", "operator_id"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_rate_limit_day_op", table_name="rate_limit_buckets", schema=SCHEMA)
    op.drop_table("rate_limit_buckets", schema=SCHEMA)
