"""Tool-Use Felder: status, severity, first_observed_at, deleted_at.

Revision ID: 0003_tool_use
Revises: 0002_rate_limit
Create Date: 2026-05-12

Wird in Schritt 4 (Tool-Use Aktiv) benötigt:
- memory_entries.status: active | proposed | dismissed
  → Inline-Memory-Calls schreiben 'proposed', Trägerin bestätigt → 'active'.
- memory_entries.deleted_at: Soft-Delete (Spec Abschnitt 8).
- friction_points.severity: leicht | mittel | belastend (Spec Abschnitt 3.2).
- friction_points.first_observed_at: rückwirkende Erstdatierung.
- friction_points.deleted_at: Soft-Delete.
- observations.deleted_at: Soft-Delete.

Alle Spalten sind nullable bzw. haben Default — keine Backfill-Logik nötig
für bestehende Zeilen.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0003_tool_use"
down_revision: Union[str, None] = "0002_rate_limit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- memory_entries -----------------------------------------------------
    op.add_column(
        "memory_entries",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="active",
        ),
        schema=SCHEMA,
    )
    op.add_column(
        "memory_entries",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_memory_op_status",
        "memory_entries",
        ["operator_id", "status"],
        schema=SCHEMA,
    )

    # --- friction_points ----------------------------------------------------
    op.add_column(
        "friction_points",
        sa.Column("severity", sa.String(16), nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "friction_points",
        sa.Column("first_observed_at", sa.Date, nullable=True),
        schema=SCHEMA,
    )
    op.add_column(
        "friction_points",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )

    # --- observations -------------------------------------------------------
    op.add_column(
        "observations",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column("observations", "deleted_at", schema=SCHEMA)

    op.drop_column("friction_points", "deleted_at", schema=SCHEMA)
    op.drop_column("friction_points", "first_observed_at", schema=SCHEMA)
    op.drop_column("friction_points", "severity", schema=SCHEMA)

    op.drop_index("idx_memory_op_status", table_name="memory_entries", schema=SCHEMA)
    op.drop_column("memory_entries", "deleted_at", schema=SCHEMA)
    op.drop_column("memory_entries", "status", schema=SCHEMA)
