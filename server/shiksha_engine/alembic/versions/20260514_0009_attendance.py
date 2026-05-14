"""Migration 0009 — attendance_records + attendance_settings

Erstellt die zwei Tabellen für das Anwesenheits-Modul (Schritt 5.5.5).
Spec: SHIKSHA_ATTENDANCE_SPEC.md §2.

Wichtig (siehe Spec L1):
- UNIQUE(person_id, date) WHERE deleted_at IS NULL ist als CREATE UNIQUE INDEX
  realisiert, weil Postgres kein UNIQUE … WHERE im CREATE TABLE unterstützt.

Revises: 0008_events
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_attendance"
down_revision = "0008_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. attendance_settings
    # ------------------------------------------------------------------
    op.create_table(
        "attendance_settings",
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("opens_at", sa.Time(), nullable=False, server_default=sa.text("'07:00'::time")),
        sa.Column("closes_at", sa.Time(), nullable=False, server_default=sa.text("'17:00'::time")),
        sa.Column(
            "staff_ratio",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "metadata_",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        schema="shiksha_core",
    )

    # Krummelus-Seed (Vorarlberg-KGG-Defaults)
    op.execute("""
        INSERT INTO shiksha_core.attendance_settings (
            tenant_org_id, opens_at, closes_at, staff_ratio, metadata_
        ) VALUES (
            'krummelus',
            '07:30'::time,
            '15:30'::time,
            '{"3": 6, "6": 12}'::jsonb,
            '{"jurisdiction": "vorarlberg", "kgg_version": "2024"}'::jsonb
        )
        ON CONFLICT (tenant_org_id) DO NOTHING;
    """)

    # ------------------------------------------------------------------
    # 2. attendance_records
    # ------------------------------------------------------------------
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tenant_org_id",
            sa.Text(),
            sa.ForeignKey("shiksha_core.organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),

        # Person + Tag — UNIQUE als partial Index, siehe weiter unten
        sa.Column(
            "person_id",
            sa.Integer(),
            sa.ForeignKey("shiksha_core.persons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),

        # Status — Pflicht
        sa.Column("status", sa.Text(), nullable=False),

        # Optionale Zeitstempel
        sa.Column("check_in_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("check_out_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expected_in_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("expected_out_at", sa.TIMESTAMP(timezone=True), nullable=True),

        # Gruppen-Zuordnung für DEN Tag
        sa.Column("group_id", sa.Integer(), nullable=True),

        # Auto-Sync-Marker
        sa.Column(
            "source",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column(
            "source_event_id",
            sa.Integer(),
            sa.ForeignKey("shiksha_core.events.id", ondelete="SET NULL"),
            nullable=True,
        ),

        # Notizen
        sa.Column("notes", sa.Text(), nullable=True),

        # Edition-spezifisches
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

        schema="shiksha_core",
    )

    # ------------------------------------------------------------------
    # 3. Indizes (siehe Spec §2.1)
    # ------------------------------------------------------------------

    # Tag-Range-Query (?date=… / GET /day)
    op.create_index(
        "ix_attendance_tenant_date",
        "attendance_records",
        ["tenant_org_id", "date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )

    # Person-Verlauf (GET /person/{id}?from=…)
    op.create_index(
        "ix_attendance_person_date",
        "attendance_records",
        ["person_id", sa.text("date DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )

    # Status-Filter
    op.create_index(
        "ix_attendance_status",
        "attendance_records",
        ["tenant_org_id", "status", "date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )

    # Partial UNIQUE: nur aktive Records sind eindeutig pro (person, date)
    op.create_index(
        "uq_attendance_person_date_active",
        "attendance_records",
        ["person_id", "date"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="shiksha_core",
    )


def downgrade() -> None:
    op.drop_index("uq_attendance_person_date_active", table_name="attendance_records", schema="shiksha_core")
    op.drop_index("ix_attendance_status", table_name="attendance_records", schema="shiksha_core")
    op.drop_index("ix_attendance_person_date", table_name="attendance_records", schema="shiksha_core")
    op.drop_index("ix_attendance_tenant_date", table_name="attendance_records", schema="shiksha_core")
    op.drop_table("attendance_records", schema="shiksha_core")
    op.drop_table("attendance_settings", schema="shiksha_core")
