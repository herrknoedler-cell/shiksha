"""Migration 0008 — events table + organizations.timezone

Erstellt die events-Tabelle für das Calendar-Modul (Schritt 5.5.4) und ergänzt
organizations.timezone für tenant-spezifische Display-TZ (siehe Spec §2.5).

Revises: 0007_persons
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0008_events"
down_revision = "0007_persons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. organizations.timezone — Display-TZ pro Tenant
    # ------------------------------------------------------------------
    op.add_column(
        "organizations",
        sa.Column(
            "timezone",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'Europe/Berlin'"),
        ),
        schema="shiksha_core",
    )

    # Krummelus läuft in Vorarlberg
    op.execute(
        "UPDATE shiksha_core.organizations "
        "SET timezone = 'Europe/Vienna' WHERE id = 'krummelus'"
    )

    # ------------------------------------------------------------------
    # 2. events-Tabelle
    # ------------------------------------------------------------------
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Idempotenz für Legacy-Import (analog persons)
        sa.Column("legacy_id", sa.Text(), nullable=True),
        sa.Column("legacy_source", sa.Text(), nullable=True),

        # Typ + Inhalt
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),

        # Zeit (TIMESTAMPTZ — Storage immer UTC)
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "all_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),

        # Person-Verknüpfung als jsonb-Array von Integer-IDs
        sa.Column(
            "participants",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),

        # Edition-spezifisches (siehe Spec §2.4):
        # - subtype, urgency, recurrence_group, recurrence_index, status, legacy_raw
        sa.Column(
            "metadata_",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),

        # Audit
        sa.Column(
            "operator_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.operators.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),

        sa.UniqueConstraint(
            "legacy_id", "legacy_source",
            name="uq_events_legacy",
        ),
        schema="shiksha_core",
    )

    # ------------------------------------------------------------------
    # 3. Indizes
    # ------------------------------------------------------------------
    # Zeitraum-Queries (?from=&to=)
    op.create_index(
        "ix_events_tenant_start",
        "events",
        ["tenant_org_id", "start_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )

    # Type-Filter
    op.create_index(
        "ix_events_type",
        "events",
        ["tenant_org_id", "event_type", "start_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )

    # Person-Filter via @> auf participants
    op.execute(
        "CREATE INDEX ix_events_participants "
        "ON shiksha_core.events USING GIN (participants)"
    )

    # Metadata-Filter (für recurrence_group, status, subtype Queries)
    op.execute(
        "CREATE INDEX ix_events_metadata "
        "ON shiksha_core.events USING GIN (metadata_)"
    )


def downgrade() -> None:
    op.drop_index("ix_events_metadata", schema="shiksha_core")
    op.drop_index("ix_events_participants", schema="shiksha_core")
    op.drop_index("ix_events_type", table_name="events", schema="shiksha_core")
    op.drop_index("ix_events_tenant_start", table_name="events", schema="shiksha_core")
    op.drop_table("events", schema="shiksha_core")
    op.drop_column("organizations", "timezone", schema="shiksha_core")
