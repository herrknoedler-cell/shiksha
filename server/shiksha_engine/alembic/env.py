"""Alembic — Migration Environment.

Liest DATABASE_URL aus den Settings, registriert alle Models damit
autogenerate funktioniert, sorgt für das shiksha_core-Schema.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, text

from shiksha_engine.db import Base
from shiksha_engine.models import (  # noqa: F401  — Imports nötig für autogenerate
    AuditLog,
    FrictionPoint,
    MemoryEntry,
    Message,
    Observation,
    Operator,
    Organization,
    PersonaPrompt,
    Session,
)
from shiksha_engine.settings import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata
SCHEMA = settings.db_schema


def include_object(obj, name, type_, reflected, compare_to):
    """Nur Tabellen aus unserem Schema migrieren."""
    if type_ == "table" and getattr(obj, "schema", None) != SCHEMA:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (gibt SQL aus, führt nichts aus)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        version_table_schema=SCHEMA,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (führt SQL aus)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Schema anlegen falls nicht vorhanden
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            version_table_schema=SCHEMA,
            include_schemas=True,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
