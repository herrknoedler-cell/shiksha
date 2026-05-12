"""Identity-Kind-Spalte für Multi-Role-Heim.

Revision ID: 0004_identity_kind
Revises: 0003_tool_use
Create Date: 2026-05-12

Wird in Schritt 5 (Heim — Multi-Role-Hub) benötigt:
- operators.kind: staff | klient | system
  → 'staff'  : Personen die zur Organisation gehören (Leitung, Pädagoge, Trainer)
  → 'klient' : Endnutzer-Personen (Eltern, Teilnehmer)
  → 'system' : Developer, Administrator

Die bestehende role-Spalte differenziert innerhalb von kind:
  kind=staff   → leitung, padagoge, trainer
  kind=klient  → eltern, teilnehmer
  kind=system  → developer

Bestehende Einträge: alle auf kind='system' wenn role='developer',
sonst kind='staff'. Default für neue Einträge: 'staff'.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0004_identity_kind"
down_revision: Union[str, None] = "0003_tool_use"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "operators",
        sa.Column(
            "kind",
            sa.String(16),
            nullable=False,
            server_default="staff",
        ),
        schema=SCHEMA,
    )

    # Backfill: bestehende Einträge nach role einordnen.
    op.execute(f"""
        UPDATE {SCHEMA}.operators
        SET kind = CASE
            WHEN role = 'developer' THEN 'system'
            WHEN role = 'operator'  THEN 'staff'
            ELSE 'staff'
        END
    """)

    op.create_index(
        "idx_operators_kind_role",
        "operators",
        ["kind", "role"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_operators_kind_role", table_name="operators", schema=SCHEMA)
    op.drop_column("operators", "kind", schema=SCHEMA)
