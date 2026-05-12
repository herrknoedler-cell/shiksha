"""Legacy-Rolle 'operator' → 'leitung' migrieren.

Revision ID: 0005_op_to_leitung
Revises: 0004_identity_kind
Create Date: 2026-05-12

Vor Schritt 5 hatten alle staff-Personen role='operator' (Legacy aus Phase 1).
Mit der Identity-Erweiterung (kind + spezifische Rollen) wird das jetzt
präzisiert: existierende role='operator' AND kind='staff' werden zu
'leitung' — das war ihre faktische Funktion.

Der Legacy-Wert 'operator' bleibt im Code als Alias akzeptiert (siehe
deps.py), falls noch alte Einträge auftauchen. Aber die produktive
Datenlage ist nach dieser Migration sauber.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0005_op_to_leitung"
down_revision: Union[str, None] = "0004_identity_kind"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(f"""
        UPDATE {SCHEMA}.operators
        SET role = 'leitung'
        WHERE role = 'operator' AND kind = 'staff'
    """)


def downgrade() -> None:
    # Rückwärts: leitung → operator (für staff-Einträge)
    op.execute(f"""
        UPDATE {SCHEMA}.operators
        SET role = 'operator'
        WHERE role = 'leitung' AND kind = 'staff'
    """)
