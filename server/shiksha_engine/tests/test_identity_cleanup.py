"""Identity-Cleanup — Tests für Three-Tier-Auto-Delete (T-011)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from shiksha_engine.models import (
    IdentityAuditLog, IdentityDocument, IdentityPerson, Operator, Organization,
)
from shiksha_engine.services.identity_cleanup import (
    cleanup_tier_1_files, cleanup_tier_2_structured, cleanup_tier_3_audit_log,
)


@pytest.fixture
def krummelus_org(db) -> Organization:
    org = Organization(
        id="krummelus", edition="kita", name="Krummelus",
        timezone="Europe/Vienna", jurisdiction="AT-8", metadata_={},
    )
    db.add(org)
    db.commit()
    return org


@pytest.fixture
def leitung(db, krummelus_org) -> Operator:
    op = Operator(
        id="krummelus_leitung_cleanup", org_id=krummelus_org.id, edition="kita",
        kind="staff", role="leitung", display_name="L",
        email="l-cleanup@krummelus.example", metadata_={},
    )
    db.add(op)
    db.commit()
    return op


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ============================================================ Tier 1: Files


def test_cleanup_tier_1_respects_retention(db, krummelus_org, leitung, tmp_path, monkeypatch):
    """Old file (>30 Tage) → gelöscht; junges File → bleibt."""
    monkeypatch.setenv("IDENTITY_UPLOAD_ROOT", str(tmp_path))
    # neue Settings-Instanz erzwingen
    from shiksha_engine.settings import get_settings
    get_settings.cache_clear()

    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Old File Owner",
        consent_given=True, created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()

    # Älteres Doc (60 Tage)
    old_path = tmp_path / str(p.id) / "id_front.png"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(b"old")
    old_doc = IdentityDocument(
        identity_person_id=p.id, doc_kind="id_front",
        file_ref=f"{p.id}/id_front.png", original_hash="a" * 64,
        uploaded_by_operator_id=leitung.id,
        uploaded_at=_now() - timedelta(days=60),
    )
    db.add(old_doc)

    # Junges Doc (5 Tage)
    young_path = tmp_path / str(p.id) / "id_back.png"
    young_path.write_bytes(b"young")
    young_doc = IdentityDocument(
        identity_person_id=p.id, doc_kind="id_back",
        file_ref=f"{p.id}/id_back.png", original_hash="b" * 64,
        uploaded_by_operator_id=leitung.id,
        uploaded_at=_now() - timedelta(days=5),
    )
    db.add(young_doc)
    db.commit()

    result = cleanup_tier_1_files(db, tenant_org_id=krummelus_org.id, dry_run=False)
    assert result == {"krummelus": 1}

    db.refresh(old_doc)
    db.refresh(young_doc)
    assert old_doc.file_ref is None
    assert old_doc.file_deleted_at is not None
    assert young_doc.file_ref == f"{p.id}/id_back.png"
    assert not old_path.exists()
    assert young_path.exists()

    get_settings.cache_clear()


def test_cleanup_tier_1_respects_legal_hold(db, krummelus_org, leitung, tmp_path, monkeypatch):
    """File einer legal_hold=True Person bleibt."""
    monkeypatch.setenv("IDENTITY_UPLOAD_ROOT", str(tmp_path))
    from shiksha_engine.settings import get_settings
    get_settings.cache_clear()

    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Held",
        consent_given=True, legal_hold=True,
        created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()
    path = tmp_path / str(p.id) / "id_front.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"keep")
    doc = IdentityDocument(
        identity_person_id=p.id, doc_kind="id_front",
        file_ref=f"{p.id}/id_front.png", original_hash="c" * 64,
        uploaded_by_operator_id=leitung.id,
        uploaded_at=_now() - timedelta(days=90),
    )
    db.add(doc)
    db.commit()

    result = cleanup_tier_1_files(db, tenant_org_id=krummelus_org.id, dry_run=False)
    assert result == {"krummelus": 0}

    db.refresh(doc)
    assert doc.file_ref == f"{p.id}/id_front.png"
    assert path.exists()

    get_settings.cache_clear()


def test_cleanup_tier_1_dry_run_no_side_effects(db, krummelus_org, leitung, tmp_path, monkeypatch):
    """Dry-Run zählt aber löscht nichts."""
    monkeypatch.setenv("IDENTITY_UPLOAD_ROOT", str(tmp_path))
    from shiksha_engine.settings import get_settings
    get_settings.cache_clear()

    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Dry Run",
        consent_given=True, created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.flush()
    path = tmp_path / str(p.id) / "id_front.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"dry")
    doc = IdentityDocument(
        identity_person_id=p.id, doc_kind="id_front",
        file_ref=f"{p.id}/id_front.png", original_hash="d" * 64,
        uploaded_by_operator_id=leitung.id,
        uploaded_at=_now() - timedelta(days=60),
    )
    db.add(doc)
    db.commit()

    result = cleanup_tier_1_files(db, tenant_org_id=krummelus_org.id, dry_run=True)
    assert result == {"krummelus": 1}

    db.refresh(doc)
    assert doc.file_ref == f"{p.id}/id_front.png"  # NICHT geändert
    assert path.exists()

    get_settings.cache_clear()


# ============================================================ Tier 2: Structured


def test_cleanup_tier_2_deletes_expired(db, krummelus_org, leitung):
    """Person mit structured_delete_at in der Vergangenheit + kein legal_hold → weg."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Old Structured",
        consent_given=True, legal_hold=False,
        structured_delete_at=_now() - timedelta(days=1),
        created_at=_now() - timedelta(days=400), updated_at=_now(),
    )
    db.add(p)
    db.commit()
    pid = p.id

    result = cleanup_tier_2_structured(db, tenant_org_id=krummelus_org.id, dry_run=False)
    assert result == {"krummelus": 1}

    assert db.get(IdentityPerson, pid) is None

    # Audit-Log bleibt
    audits = db.query(IdentityAuditLog).filter_by(
        target_kind="identity_person", target_id=pid, action="identity_person.auto_deleted"
    ).all()
    assert len(audits) == 1


def test_cleanup_tier_2_respects_legal_hold(db, krummelus_org):
    """Person mit legal_hold=True wird NICHT gelöscht, auch wenn delete_at fällig."""
    p = IdentityPerson(
        tenant_org_id=krummelus_org.id, full_name="Held Structured",
        consent_given=True, legal_hold=True,
        structured_delete_at=_now() - timedelta(days=1),
        created_at=_now(), updated_at=_now(),
    )
    db.add(p)
    db.commit()
    pid = p.id

    result = cleanup_tier_2_structured(db, tenant_org_id=krummelus_org.id, dry_run=False)
    assert result == {"krummelus": 0}
    assert db.get(IdentityPerson, pid) is not None


# ============================================================ Tier 3: Audit-Log


def test_cleanup_tier_3_deletes_old_audit_entries(db, krummelus_org):
    """Audit-Eintrag älter als 7 Jahre → gelöscht."""
    old = IdentityAuditLog(
        tenant_org_id=krummelus_org.id, actor_kind="system",
        action="identity_person.create",
        target_kind="identity_person", target_id=999,
        details=None,
        created_at=_now() - timedelta(days=365 * 8),
    )
    young = IdentityAuditLog(
        tenant_org_id=krummelus_org.id, actor_kind="system",
        action="identity_person.create",
        target_kind="identity_person", target_id=1000,
        details=None,
        created_at=_now() - timedelta(days=30),
    )
    db.add_all([old, young])
    db.commit()

    result = cleanup_tier_3_audit_log(db, tenant_org_id=krummelus_org.id, dry_run=False)
    assert result == {"krummelus": 1}

    db.expire_all()
    assert db.query(IdentityAuditLog).filter_by(target_id=999).first() is None
    assert db.query(IdentityAuditLog).filter_by(target_id=1000).first() is not None
