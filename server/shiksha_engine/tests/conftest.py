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
    tables = [
        "audit_logs", "friction_points", "observations", "memory_entries",
        "messages", "sessions", "persona_prompts",
        "rate_limit_buckets", "tenant_heim_config",
        "attendance_records", "attendance_settings",
        "events", "persons",
        "operators", "organizations",
    ]
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
        id="thomas", org_id=None, edition="kita", kind="system",
        display_name="Thomas", role="developer", email="thomas@shiksha.world",
        metadata_={},
    )
    db.add(op)
    db.commit()
    return op


@pytest.fixture
def mira_leitung(db) -> Operator:
    """Mira als Trägerin mit neuer Identity-Klassifikation."""
    org = Organization(
        id="krummelus_v2", edition="kita", name="Krummelus",
        legal_name="Krummelus Familien-KITA", region="Vorarlberg, AT",
        metadata_={},
    )
    db.add(org)
    op = Operator(
        id="krummelus_mira_v2",
        org_id="krummelus_v2",
        edition="kita",
        display_name="Mira",
        kind="staff",
        role="leitung",
        email="mira_v2@krummelus.example",
        metadata_={},
    )
    db.add(op)
    db.commit()
    return op


@pytest.fixture
def pedagogin(db, mira_leitung) -> Operator:
    """Eine Pädagogin in Krummelus, im selben Tenant wie Mira."""
    op = Operator(
        id="krummelus_anna",
        org_id=mira_leitung.org_id,
        edition="kita",
        display_name="Anna",
        kind="staff",
        role="padagoge",
        email="anna@krummelus.example",
        metadata_={},
    )
    db.add(op)
    db.commit()
    return op


@pytest.fixture
def vater(db, mira_leitung) -> Operator:
    """Ein Vater, Klient von Krummelus."""
    op = Operator(
        id="krummelus_vater_lukas",
        org_id=mira_leitung.org_id,
        edition="kita",
        display_name="Markus",
        kind="klient",
        role="eltern",
        email="markus@example.com",
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


# ---------------------------------------------------------- Calendar-Fixtures
# Gebraucht von tests/test_calendar.py (Spec §6.4 vier Pflicht-Tests).

@pytest.fixture
def db_session(db):
    """Alias auf db — neuere Tests nutzen 'db_session', älterer Code 'db'."""
    return db


@pytest.fixture
def calendar_mira(db_session):
    """Mira als Leitung in 'krummelus' (Calendar-Tests).

    Separates ID-Namespace 'krummelus_mira_cal' / 'krummelus_cal' damit der
    Fixture nicht mit 'mira' / 'mira_leitung' kollidiert."""
    from shiksha_engine.models.organization import Organization
    org = Organization(
        id="krummelus_cal", edition="kita", name="Krummelus",
        timezone="Europe/Vienna", metadata_={},
    )
    db_session.add(org)
    op = Operator(
        id="krummelus_mira_cal", org_id="krummelus_cal", edition="kita",
        kind="staff", role="leitung", display_name="Mira",
        email="mira@krummelus-cal.example", metadata_={},
    )
    db_session.add(op)
    db_session.commit()
    return op


@pytest.fixture
def mira_token(calendar_mira):
    from shiksha_engine.services.jwt_service import issue_token
    return issue_token(
        operator_id=calendar_mira.id, role=calendar_mira.role,
        edition=calendar_mira.edition, org_id=calendar_mira.org_id,
        org_timezone="Europe/Vienna",
    )


@pytest.fixture
def padagogin(db_session, calendar_mira):
    """Pädagogin in calendar_mira's Tenant."""
    op = Operator(
        id="krummelus_cal_anna", org_id=calendar_mira.org_id, edition="kita",
        kind="staff", role="padagoge", display_name="Anna",
        email="anna@krummelus-cal.example", metadata_={},
    )
    db_session.add(op)
    db_session.commit()
    return op


@pytest.fixture
def padagogin_token(padagogin):
    from shiksha_engine.services.jwt_service import issue_token
    return issue_token(
        operator_id=padagogin.id, role=padagogin.role,
        edition=padagogin.edition, org_id=padagogin.org_id,
        org_timezone="Europe/Vienna",
    )


@pytest.fixture
def padagogin_id(padagogin):
    return padagogin.id


@pytest.fixture
def eltern_token(db_session, calendar_mira):
    op = Operator(
        id="krummelus_cal_eltern", org_id=calendar_mira.org_id, edition="kita",
        kind="klient", role="eltern", display_name="Eltern-Test",
        email="eltern@krummelus-cal.example", metadata_={},
    )
    db_session.add(op)
    db_session.commit()
    from shiksha_engine.services.jwt_service import issue_token
    return issue_token(
        operator_id=op.id, role="eltern", edition="kita",
        org_id=op.org_id, org_timezone="Europe/Vienna",
    )


@pytest.fixture
def other_tenant_token(db_session):
    """Anderer Tenant — für Cross-Tenant-Reject-Test."""
    from shiksha_engine.models.organization import Organization
    org = Organization(
        id="othertenant", edition="kita", name="Other",
        timezone="Europe/Berlin", metadata_={},
    )
    db_session.add(org)
    op = Operator(
        id="othertenant_leitung", org_id="othertenant", edition="kita",
        kind="staff", role="leitung", display_name="Other Leitung",
        email="lead@other.example", metadata_={},
    )
    db_session.add(op)
    db_session.commit()
    from shiksha_engine.services.jwt_service import issue_token
    return issue_token(
        operator_id=op.id, role="leitung", edition="kita",
        org_id="othertenant", org_timezone="Europe/Berlin",
    )


@pytest.fixture
def developer_token_no_org(db_session):
    """Developer ohne Tenant-Kontext — Test für 400-on-create."""
    op = Operator(
        id="thomas_cal", org_id=None, edition="kita",
        kind="system", role="developer", display_name="Thomas-Cal",
        email="thomas-cal@shiksha.world", metadata_={},
    )
    db_session.add(op)
    db_session.commit()
    from shiksha_engine.services.jwt_service import issue_token
    return issue_token(
        operator_id=op.id, role="developer", edition="kita",
        org_id=None, org_timezone=None,
    )


@pytest.fixture
def krummelus_with_birthdays(db_session, calendar_mira):
    """Stellt sicher dass mindestens ein Kind mit birth_date heute existiert."""
    from datetime import date, datetime
    from shiksha_engine.models.person import Person
    today = date.today()
    target = date(1990, today.month, today.day)
    p = Person(
        tenant_org_id=calendar_mira.org_id, kind="kind",
        given_name="Geburtstagskind", family_name="Test",
        birth_date=target, active=True, operator_id=calendar_mira.id,
        created_at=datetime.now(), updated_at=datetime.now(),
    )
    db_session.add(p)
    db_session.commit()
    return p
