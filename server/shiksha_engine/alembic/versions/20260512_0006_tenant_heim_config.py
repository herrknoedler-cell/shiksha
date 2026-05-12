"""Tenant-Heim-Konfiguration Tabelle.

Revision ID: 0006_tenant_heim
Revises: 0005_op_to_leitung
Create Date: 2026-05-12

Pro-(org, role, card_id)-Override-Tabelle für Heim-Karten (Spec §6.2).
Die Leitung kann Karten aus dem Edition-Pool aktivieren/deaktivieren
oder mit eigenen Texten überschreiben.

Wenn kein Eintrag existiert, gilt der Default aus editions/<edition>.yaml.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0006_tenant_heim"
down_revision: Union[str, None] = "0005_op_to_leitung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_heim_config",
        sa.Column("org_id",          sa.String(64), nullable=False),
        sa.Column("role",            sa.String(32), nullable=False),
        sa.Column("card_id",         sa.String(64), nullable=False),
        sa.Column("enabled",         sa.Boolean,    nullable=False, server_default=sa.true()),
        sa.Column("custom_title",    sa.String(128), nullable=True),
        sa.Column("custom_subtitle", sa.String(255), nullable=True),
        sa.Column("extra_config",    sa.JSON,       nullable=True),
        sa.Column("updated_by",      sa.String(64), nullable=True),
        sa.Column("updated_at",      sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("org_id", "role", "card_id"),
        sa.ForeignKeyConstraint(
            ["org_id"], [f"{SCHEMA}.organizations.id"],
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_heim_config_org_role",
        "tenant_heim_config",
        ["org_id", "role"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_heim_config_org_role", table_name="tenant_heim_config", schema=SCHEMA)
    op.drop_table("tenant_heim_config", schema=SCHEMA)
