"""Initial — shiksha_core schema mit allen Tabellen.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from shiksha_engine.settings import get_settings

SCHEMA = get_settings().db_schema

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Schema (env.py legt es schon an, hier nochmal sicherheitshalber)
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")

    # ---- organizations ----
    op.create_table(
        "organizations",
        sa.Column("id",          sa.String(64), primary_key=True),
        sa.Column("edition",     sa.String(32), nullable=False, index=True),
        sa.Column("name",        sa.String(128), nullable=False),
        sa.Column("legal_name",  sa.String(255), nullable=True),
        sa.Column("region",      sa.String(64),  nullable=True),
        sa.Column("metadata",    sa.JSON,        nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- operators ----
    op.create_table(
        "operators",
        sa.Column("id",                   sa.String(64), primary_key=True),
        sa.Column("org_id",               sa.String(64), sa.ForeignKey(f"{SCHEMA}.organizations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("edition",              sa.String(32), nullable=False, index=True),
        sa.Column("display_name",         sa.String(128), nullable=False),
        sa.Column("role",                 sa.String(32),  nullable=False, server_default="operator"),
        sa.Column("email",                sa.String(255), nullable=True, unique=True),
        sa.Column("webauthn_credentials", sa.JSON,        nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("metadata",             sa.JSON,        nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at",           sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- persona_prompts ----
    op.create_table(
        "persona_prompts",
        sa.Column("name",          sa.String(64), primary_key=True),
        sa.Column("edition",       sa.String(32), primary_key=True, server_default="*"),
        sa.Column("version",       sa.Integer,    primary_key=True, server_default="1"),
        sa.Column("system_prompt", sa.Text,       nullable=False),
        sa.Column("description",   sa.Text,       nullable=True),
        sa.Column("updated_by",    sa.String(64), sa.ForeignKey(f"{SCHEMA}.operators.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at",    sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- sessions ----
    op.create_table(
        "sessions",
        sa.Column("id",          sa.String(64), primary_key=True),
        sa.Column("operator_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.operators.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("org_id",      sa.String(64), sa.ForeignKey(f"{SCHEMA}.organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("edition",     sa.String(32), nullable=False, index=True),
        sa.Column("persona",     sa.String(64), nullable=False),
        sa.Column("started_at",  sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at",   sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary",     sa.Text, nullable=True),
        sa.Column("insights",    sa.JSON, nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("meta",        sa.JSON, nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        schema=SCHEMA,
    )
    op.create_index("idx_sessions_op_started", "sessions", ["operator_id", "started_at"], schema=SCHEMA)
    op.create_index("idx_sessions_edition_started", "sessions", ["edition", "started_at"], schema=SCHEMA)

    # ---- messages ----
    op.create_table(
        "messages",
        sa.Column("id",         sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role",       sa.String(16), nullable=False),
        sa.Column("content",    sa.Text,       nullable=False),
        sa.Column("mode",       sa.String(16), nullable=True),
        sa.Column("ts",         sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("idx_messages_session_ts", "messages", ["session_id", "ts"], schema=SCHEMA)

    # ---- memory_entries ----
    op.create_table(
        "memory_entries",
        sa.Column("id",                sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("operator_id",       sa.String(64), sa.ForeignKey(f"{SCHEMA}.operators.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("edition",           sa.String(32), nullable=False, index=True),
        sa.Column("text",              sa.Text,       nullable=False),
        sa.Column("source_session_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at",        sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- observations ----
    op.create_table(
        "observations",
        sa.Column("id",         sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey(f"{SCHEMA}.sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("edition",    sa.String(32), nullable=False, index=True),
        sa.Column("kind",       sa.String(32), nullable=True),
        sa.Column("text",       sa.Text,       nullable=False),
        sa.Column("metadata",   sa.JSON,       nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("ts",         sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- friction_points ----
    op.create_table(
        "friction_points",
        sa.Column("id",          sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id",  sa.String(64), sa.ForeignKey(f"{SCHEMA}.sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("edition",     sa.String(32), nullable=False, index=True),
        sa.Column("where_label", sa.String(64), nullable=True),
        sa.Column("text",        sa.Text,       nullable=False),
        sa.Column("resolved",    sa.Boolean,    nullable=False, server_default=sa.text("false")),
        sa.Column("ts",          sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )

    # ---- audit_logs ----
    op.create_table(
        "audit_logs",
        sa.Column("id",             sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_id",       sa.String(64), nullable=True, index=True),
        sa.Column("actor_role",     sa.String(32), nullable=True),
        sa.Column("action",         sa.String(64), nullable=False, index=True),
        sa.Column("target_type",    sa.String(32), nullable=True),
        sa.Column("target_id",      sa.String(64), nullable=True),
        sa.Column("diff",           sa.JSON,       nullable=True),
        sa.Column("request_path",   sa.String(255), nullable=True),
        sa.Column("request_method", sa.String(8),  nullable=True),
        sa.Column("ip_address",     sa.String(45), nullable=True),
        sa.Column("ts",             sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema=SCHEMA,
    )
    op.create_index("idx_audit_ts_desc", "audit_logs", ["ts"], schema=SCHEMA, postgresql_using="btree")


def downgrade() -> None:
    op.drop_table("audit_logs",      schema=SCHEMA)
    op.drop_table("friction_points", schema=SCHEMA)
    op.drop_table("observations",    schema=SCHEMA)
    op.drop_table("memory_entries",  schema=SCHEMA)
    op.drop_table("messages",        schema=SCHEMA)
    op.drop_table("sessions",        schema=SCHEMA)
    op.drop_table("persona_prompts", schema=SCHEMA)
    op.drop_table("operators",       schema=SCHEMA)
    op.drop_table("organizations",   schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
