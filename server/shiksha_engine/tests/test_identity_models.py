"""Identity-Modul — Smoke-Tests für Models, Migration, Jurisdiction-Loader.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §11 (Akzeptanzkriterien 5.5.6.1).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from shiksha_engine.models import (
    IdentityAuditLog,
    IdentityAuthorization,
    IdentityDocument,
    IdentityPerson,
    Operator,
    Organization,
)
from shiksha_engine.services.jurisdiction import (
    clear_jurisdiction_cache,
    load_jurisdiction_config,
)


# ============================================================ Fixtures


@pytest.fixture
def krummelus_org(db) -> Organization:
    """Krummelus mit jurisdiction='AT-8' + identity_salt aus Model-Default."""
    org = Organization(
        id="krummelus", edition="kita", name="Krummelus",
        region="Vorarlberg, AT", timezone="Europe/Vienna",
        jurisdiction="AT-8",
        metadata_={},
    )
    db.add(org)
    db.commit()
    return org


@pytest.fixture
def leitung_operator(db, krummelus_org) -> Operator:
    op = Operator(
        id="krummelus_leitung_test", org_id=krummelus_org.id, edition="kita",
        kind="staff", role="leitung", display_name="Test-Leitung",
        email="leitung-test@krummelus.example", metadata_={},
    )
    db.add(op)
    db.commit()
    return op


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ============================================================ 1. CRUD


def test_identity_person_crud(db, krummelus_org):
    """Create/Read/Delete einer IdentityPerson — Basis-Sanity."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id,
        full_name="Maria Großmutter",
        consent_given=True,
        consent_text="Ich willige ein…",
        consent_given_at=_now(),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(p)
    db.commit()

    fetched = db.query(IdentityPerson).filter_by(full_name="Maria Großmutter").first()
    assert fetched is not None
    assert fetched.verification_status == "pending"
    assert fetched.is_pending is True
    assert fetched.is_verified is False
    assert fetched.legal_hold is False


# ============================================================ 2. Cascade-Delete


def test_document_cascade_on_person_delete(db, krummelus_org, leitung_operator):
    """IdentityDocument wird mit IdentityPerson hart mit-gelöscht."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="X", consent_given=True,
        created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()
    doc = IdentityDocument(
        identity_person_id=p.id, doc_kind="id_front",
        file_ref="/tmp/x.jpg", original_hash="a" * 64,
        uploaded_by_operator_id=leitung_operator.id,
        uploaded_at=_now(),
    )
    db.add(doc)
    db.commit()

    doc_id = doc.id
    db.delete(p)
    db.commit()

    assert db.query(IdentityDocument).filter_by(id=doc_id).first() is None


# ============================================================ 3. CHECK-Constraint


def test_authorization_target_consistency_check(db, krummelus_org, leitung_operator):
    """target_type='child' OHNE target_id → IntegrityError (DB-CHECK)."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Y", consent_given=True,
        created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()

    bad = IdentityAuthorization(
        tenant_org_id=krummelus_org.id,
        subject_identity_person_id=p.id,
        target_type="child",
        target_id=None,                  # ← inkonsistent
        granted_by_operator_id=leitung_operator.id,
        granted_at=_now(),
        valid_from=_now(),
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_authorization_target_global_must_have_null_target_id(db, krummelus_org, leitung_operator):
    """target_type='global' MIT target_id → IntegrityError."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Z", consent_given=True,
        created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()

    bad = IdentityAuthorization(
        tenant_org_id=krummelus_org.id,
        subject_identity_person_id=p.id,
        target_type="global",
        target_id=42,                    # ← muss NULL sein für 'global'
        granted_by_operator_id=leitung_operator.id,
        granted_at=_now(),
        valid_from=_now(),
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# ============================================================ 4. Jurisdiction-Loader


def test_jurisdiction_loader_deep_merge():
    """at-8.yaml überschreibt regional_oversight, erbt retention aus at.yaml."""
    clear_jurisdiction_cache()  # frische Lade-Pfad-Verifikation
    config = load_jurisdiction_config("AT-8")
    assert "identity" in config
    identity = config["identity"]

    # geerbt aus at.yaml
    assert identity["retention"]["scan_files_days"] == 30
    assert identity["retention"]["structured_data_after_end_years"] == 3
    assert identity["retention"]["audit_log_years"] == 7
    assert identity["hash_algorithm"] == "sha256"
    assert identity["hash_length_hex"] == 24

    # überschrieben aus at-8.yaml
    assert identity["regional_oversight"] == "Bildungsdirektion Vorarlberg"


def test_jurisdiction_loader_case_insensitive():
    """'at-8' und 'AT-8' liefern dasselbe."""
    clear_jurisdiction_cache()
    a = load_jurisdiction_config("AT-8")
    b = load_jurisdiction_config("at-8")
    assert a == b


def test_jurisdiction_loader_country_only():
    """'AT' ohne Region-Override liefert pure country-config."""
    clear_jurisdiction_cache()
    config = load_jurisdiction_config("AT")
    assert config["identity"]["retention"]["scan_files_days"] == 30
    # regional_oversight kommt NUR aus Bundesland-Override → bei country-only fehlt es
    assert "regional_oversight" not in config["identity"]


def test_jurisdiction_loader_unknown_country_raises():
    """Unbekannter country-code → FileNotFoundError."""
    clear_jurisdiction_cache()
    with pytest.raises(FileNotFoundError, match="zz.yaml"):
        load_jurisdiction_config("ZZ-99")


# ============================================================ 5. Organization.jurisdiction_yaml()


def test_organization_jurisdiction_yaml(krummelus_org):
    """Convenience-Method auf Organization liefert merged config."""
    clear_jurisdiction_cache()
    config = krummelus_org.jurisdiction_yaml()
    assert config["identity"]["regional_oversight"] == "Bildungsdirektion Vorarlberg"


# ============================================================ 6. identity_salt randomness


def test_identity_salt_random_per_tenant(db):
    """Zwei Organizations haben unterschiedliche identity_salts (Cross-Tenant-Trennung)."""
    org_a = Organization(
        id="tenant_a", edition="kita", name="A",
        jurisdiction="AT-8", metadata_={},
    )
    org_b = Organization(
        id="tenant_b", edition="kita", name="B",
        jurisdiction="AT-8", metadata_={},
    )
    db.add_all([org_a, org_b])
    db.commit()

    assert len(org_a.identity_salt) == 64
    assert len(org_b.identity_salt) == 64
    assert org_a.identity_salt != org_b.identity_salt


# ============================================================ 7. Audit-Log


def test_identity_audit_log_insert(db, krummelus_org, leitung_operator):
    """IdentityAuditLog mit JSONB-details."""
    log = IdentityAuditLog(
        tenant_org_id=krummelus_org.id,
        actor_operator_id=leitung_operator.id,
        actor_kind="operator",
        action="identity_person.verify",
        target_kind="identity_person",
        target_id=42,
        details={"old_status": "pending", "new_status": "verified"},
        created_at=_now(),
    )
    db.add(log)
    db.commit()

    fetched = db.query(IdentityAuditLog).filter_by(action="identity_person.verify").first()
    assert fetched is not None
    assert fetched.details == {"old_status": "pending", "new_status": "verified"}
