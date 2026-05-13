"""Persons-Tabelle für KITA-Kinder, Mitarbeiter, später auch Teilnehmer/Gäste.

Revision ID: 0007_persons
Revises: 0006_tenant_heim
Create Date: 2026-05-12

Edition-agnostische Stammdaten-Tabelle. Eine Person hat einen `kind`-
Discriminator (kind | staff | eltern | teilnehmer | gast | trainer)
und gehört zu genau einem Tenant.

Polymorphe Detail-Daten leben in `metadata` JSONB:
  KITA Kind:  {medical: {...}, parents: [...], pickup_authorized: [...],
               photo_consent: bool, dietary, nationality, native_language}
  KITA Staff: {employment: {contract_type, qualification, emergency_contact},
               employment_start, employment_end}

Phase 1.5.6 zieht pickup_authorized in eine eigene Tabelle
`pickup_authorizations` (Identity-Modul).

legacy_id-Spalte: für idempotenten Import aus der alten Welt
(kita_legacy_children.id / kita_legacy_staff.id).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

revision: str = "0007_persons"
down_revision: Union[str, None] = "0006_tenant_heim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),

        # Verknüpfung zur alten Welt (für idempotenten Import)
        sa.Column("legacy_id",     sa.Integer, nullable=True),
        sa.Column("legacy_source", sa.String(32), nullable=True),
        # legacy_source: 'kita_legacy_children' | 'kita_legacy_staff'

        # Tenant-Bindung
        sa.Column(
            "tenant_org_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.organizations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),

        # Hauptklassifikation
        sa.Column("kind", sa.String(32), nullable=False),
        # 'kind' | 'staff' | 'eltern' | 'teilnehmer' | 'gast' | 'trainer'

        # Identität
        sa.Column("given_name",  sa.String(128), nullable=False),
        sa.Column("family_name", sa.String(128), nullable=True),
        sa.Column("birth_date",  sa.Date, nullable=True),
        sa.Column("gender",      sa.String(8),  nullable=True),

        # Kontakt
        sa.Column("email",   sa.String(255), nullable=True),
        sa.Column("phone",   sa.String(64),  nullable=True),
        sa.Column("address", sa.Text, nullable=True),

        # Gruppe (für Kinder: KITA-Gruppe, für Teilnehmer: Kurs-Gruppe)
        sa.Column("group_id", sa.Integer, nullable=True),

        # Lebenszyklus in der Organisation
        sa.Column("entry_date", sa.Date, nullable=True),  # Eintritt KITA / Kurs-Anmeldung
        sa.Column("exit_date",  sa.Date, nullable=True),  # Austritt / Abmeldung

        # Notizen + Polymorphe Daten
        sa.Column("notes",    sa.Text, nullable=True),
        sa.Column("metadata", sa.JSON, nullable=False, server_default="{}"),

        # Verknüpfung zu Login (operator) — nullable, weil nicht jede Person einloggt
        sa.Column(
            "operator_id", sa.String(64),
            sa.ForeignKey(f"{SCHEMA}.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Lifecycle
        sa.Column("active",     sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

        schema=SCHEMA,
    )

    # Indexe
    op.create_index(
        "idx_persons_tenant_kind", "persons",
        ["tenant_org_id", "kind"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_persons_legacy", "persons",
        ["legacy_source", "legacy_id"],
        schema=SCHEMA,
    )
    op.create_index(
        "idx_persons_active", "persons",
        ["active"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema=SCHEMA,
    )
    op.create_index(
        "idx_persons_birth_date", "persons",
        ["birth_date"],
        postgresql_where=sa.text("birth_date IS NOT NULL"),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("idx_persons_birth_date",  table_name="persons", schema=SCHEMA)
    op.drop_index("idx_persons_active",      table_name="persons", schema=SCHEMA)
    op.drop_index("idx_persons_legacy",      table_name="persons", schema=SCHEMA)
    op.drop_index("idx_persons_tenant_kind", table_name="persons", schema=SCHEMA)
    op.drop_table("persons", schema=SCHEMA)
