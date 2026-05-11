"""pytest fixtures — Test-DB, Test-Client, seeded operators."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# Test-DB-URL via Env überschreibbar
TEST_DB_URL = os.environ.get(
    "SHIKSHA_TEST_DATABASE_URL",
    "postgresql+psycopg2://shiksha:shiksha@localhost:5432/shiksha_test",
)
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["JWT_SECRET"] = "test-secret-for-pytest"
os.environ["WEBAUTHN_RP_ID"] = "localhost"
os.environ["WEBAUTHN_ORIGIN"] = "http://localhost:8000"

from shiksha_engine.db import Base, engine, schema_name  # noqa: E402
from shiksha_engine.main import app  # noqa: E402
from shiksha_engine.models import Operator, Organization, PersonaPrompt  # noqa: E402


@pytest.fixture(scope="session")
def setup_database():
    """Erzeuge Schema + alle Tabellen einmal pro Session."""
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name()}"))
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_database) -> Generator[Session, None, None]:
    """Fresh DB session per test, mit Truncate aller Tables."""
    TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestSessionLocal()

    # Truncate alle Tables (in dependency order — child first)
    tables = ["audit_logs", "friction_points", "observations", "memory_entries",
              "messages", "sessions", "persona_prompts", "operators", "organizations"]
    for t in tables:
        session.execute(text(f"TRUNCATE TABLE {schema_name()}.{t} CASCADE"))
    session.commit()

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(setup_database) -> TestClient:
    return TestClient(app)


@pytest.fixture
def mira(db) -> Operator:
    """Mira als KITA-Operator, in Krummelus."""
    org = Organization(
        id="krummelus", edition="kita", name="Krummelus",
        legal_name="Krummelus Familien-KITA", region="Vorarlberg, AT",
        metadata_={"city": "Dornbirn"},
    )
    db.add(org)
    op = Operator(
        id="krummelus_mira", org_id="krummelus", edition="kita",
        display_name="Mira", role="operator", email="mira@krummelus.example",
        metadata_={},
    )
    db.add(op)
    db.commit()
    return op


@pytest.fixture
def thomas(db) -> Operator:
    """Thomas als Developer."""
    op = Operator(
        id="thomas", org_id=None, edition="kita",
        display_name="Thomas", role="developer", email="thomas@shiksha.world",
        metadata_={},
    )
    db.add(op)
    db.commit()
    return op


@pytest.fixture
def kennenlernen_persona(db) -> PersonaPrompt:
    """Eine Minimal-Persona zum Testen."""
    p = PersonaPrompt(
        name="kennenlernen", edition="*", version=1,
        system_prompt="Du bist SHIKSHA. Antworte in 1 kurzen Satz.",
        description="Test-Persona für conftest",
    )
    db.add(p)
    db.commit()
    return p
