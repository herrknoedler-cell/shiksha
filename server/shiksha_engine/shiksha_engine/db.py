"""Database — SQLAlchemy 2.0 engine + session factory."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .settings import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_connection, _):
    """Setze search_path damit unqualifizierte Queries shiksha_core finden."""
    if _settings.db_schema:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET search_path TO {_settings.db_schema}, public")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 Declarative-Base.

    Alle Models setzen __table_args__ = {"schema": shiksha_core_schema_name}.
    """


def get_db() -> Generator[Session, None, None]:
    """FastAPI-Dependency — gibt eine DB-Session pro Request."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Manueller Kontext-Manager für Scripts (Seeds, Migrations, Cron-Jobs)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def schema_name() -> str:
    """Wo alle Tabellen leben."""
    return _settings.db_schema
