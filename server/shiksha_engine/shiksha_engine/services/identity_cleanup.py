"""Identity-Cleanup — Three-Tier Auto-Delete (T-011).

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §7.4, docs/SHIKSHA_TECH_DEBT.md T-011.

Drei Tiers, je tenant pro jurisdiction-Config:
  Tier 1 — Scan-Dateien älter als scan_files_days (AT: 30d)
  Tier 2 — IdentityPersons älter als structured_delete_at (AT: 3 Jahre)
  Tier 3 — Audit-Log älter als audit_log_years (AT: 7 Jahre)

Legal-Hold-Flag pausiert Tier 1 + 2 für betroffene Records. Tier 3 wird
durch legal_hold der referenzierten Records gestoppt (zur Read-Zeit
geprüft — komplex, MVP-Implementation respektiert nur Tier-2-Hold).

Dry-Run-Modus für Erst-Deploy-Verifikation. Cron-Verkabelung kommt
nach 5.5.6.6.b als systemd-Timer-Unit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from shiksha_engine.models.identity_audit_log import IdentityAuditLog
from shiksha_engine.models.identity_document import IdentityDocument
from shiksha_engine.models.identity_person import IdentityPerson
from shiksha_engine.models.organization import Organization
from shiksha_engine.services.identity_query import (
    delete_all_person_files,
    delete_document_file,
    write_audit,
)

log = logging.getLogger("shiksha.identity.cleanup")


# ============================================================ Tier 1: Files


def cleanup_tier_1_files(
    db: Session,
    *,
    tenant_org_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Löscht Scan-Dateien älter als jurisdiction.retention.scan_files_days.

    Pro Tenant: lade jurisdiction-Config, finde Documents mit
    uploaded_at + scan_files_days < now() AND file_ref IS NOT NULL AND
    nicht legal_hold auf der Identity.

    Setzt file_ref=NULL + file_deleted_at=now(), löscht Datei vom Storage.
    Audit-Eintrag actor_kind='system'.

    Returns {tenant_id: deleted_count}.
    """
    counts: dict[str, int] = {}
    tenants = _resolve_tenants(db, tenant_org_id)

    for tenant in tenants:
        config = tenant.jurisdiction_yaml()
        days = config.get("identity", {}).get("retention", {}).get("scan_files_days", 30)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)

        docs = (
            db.query(IdentityDocument)
            .join(IdentityPerson, IdentityDocument.identity_person_id == IdentityPerson.id)
            .filter(
                IdentityPerson.tenant_org_id == tenant.id,
                IdentityDocument.file_ref.is_not(None),
                IdentityDocument.uploaded_at < cutoff,
                IdentityPerson.legal_hold.is_(False),
            )
            .all()
        )

        n = 0
        for doc in docs:
            if dry_run:
                log.info("[dry-run] would delete file_ref=%s (doc.id=%s)", doc.file_ref, doc.id)
                n += 1
                continue
            try:
                delete_document_file(doc.file_ref)
            except Exception:
                log.exception("Tier-1: failed to delete file_ref=%s", doc.file_ref)
                continue
            doc.file_ref = None
            doc.file_deleted_at = datetime.now(tz=timezone.utc)
            write_audit(
                db,
                operator=None,
                action="identity_document.file_auto_deleted",
                target_kind="identity_document",
                target_id=doc.id,
                tenant_org_id=tenant.id,
                actor_kind="system",
                details={"retention_days": days, "tier": 1},
            )
            n += 1

        if not dry_run:
            db.commit()
        counts[tenant.id] = n

    return counts


# ============================================================ Tier 2: Structured Data


def cleanup_tier_2_structured(
    db: Session,
    *,
    tenant_org_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Hard-Delete IdentityPersons mit structured_delete_at < now(), legal_hold=false.

    Cascadet zu identity_documents (alle Files) und identity_authorizations.
    Audit-Log bleibt (Tier 3 zuständig).

    Returns {tenant_id: deleted_count}.
    """
    counts: dict[str, int] = {}
    tenants = _resolve_tenants(db, tenant_org_id)

    for tenant in tenants:
        now = datetime.now(tz=timezone.utc)
        persons = (
            db.query(IdentityPerson)
            .filter(
                IdentityPerson.tenant_org_id == tenant.id,
                IdentityPerson.legal_hold.is_(False),
                IdentityPerson.structured_delete_at.is_not(None),
                IdentityPerson.structured_delete_at < now,
            )
            .all()
        )

        n = 0
        for p in persons:
            if dry_run:
                log.info("[dry-run] would delete IdentityPerson id=%s name=%s",
                         p.id, p.full_name)
                n += 1
                continue
            # Files weg
            delete_all_person_files(p.id)
            # Audit-Eintrag VOR Delete (sonst FK-cascade weg)
            write_audit(
                db,
                operator=None,
                action="identity_person.auto_deleted",
                target_kind="identity_person",
                target_id=p.id,
                tenant_org_id=tenant.id,
                actor_kind="system",
                details={
                    "tier": 2,
                    "structured_delete_at": p.structured_delete_at.isoformat(),
                    "doc_number_hash": p.doc_number_hash,  # Hash bleibt im Audit
                },
            )
            db.delete(p)
            n += 1

        if not dry_run:
            db.commit()
        counts[tenant.id] = n

    return counts


# ============================================================ Tier 3: Audit-Log


def cleanup_tier_3_audit_log(
    db: Session,
    *,
    tenant_org_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Löscht Audit-Log-Einträge älter als jurisdiction.retention.audit_log_years.

    Note: kein Legal-Hold-Cross-Check zu target-Records (target könnte schon
    gelöscht sein, dann ist legal_hold nicht mehr aufflösbar). Wenn ein Tenant
    gerichtlich verpflichtet ist Audit-Logs länger zu halten, eigener
    Tenant-Override in jurisdiction-Config (audit_log_years: 10).
    """
    counts: dict[str, int] = {}
    tenants = _resolve_tenants(db, tenant_org_id)

    for tenant in tenants:
        config = tenant.jurisdiction_yaml()
        years = config.get("identity", {}).get("retention", {}).get("audit_log_years", 7)
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=years * 365)

        q = db.query(IdentityAuditLog).filter(
            IdentityAuditLog.tenant_org_id == tenant.id,
            IdentityAuditLog.created_at < cutoff,
        )

        if dry_run:
            n = q.count()
            log.info("[dry-run] tenant=%s would delete %d audit entries", tenant.id, n)
        else:
            n = q.delete(synchronize_session=False)
            db.commit()

        counts[tenant.id] = n

    return counts


# ============================================================ Helpers


def _resolve_tenants(db: Session, tenant_org_id: str | None) -> list[Organization]:
    """Wenn tenant_org_id gegeben: nur diesen Tenant. Sonst alle."""
    q = db.query(Organization)
    if tenant_org_id:
        q = q.filter(Organization.id == tenant_org_id)
    return q.all()


def run_all_tiers(
    db: Session,
    *,
    tenant_org_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, dict[str, int]]:
    """Convenience: alle drei Tiers nacheinander."""
    return {
        "tier_1": cleanup_tier_1_files(db, tenant_org_id=tenant_org_id, dry_run=dry_run),
        "tier_2": cleanup_tier_2_structured(db, tenant_org_id=tenant_org_id, dry_run=dry_run),
        "tier_3": cleanup_tier_3_audit_log(db, tenant_org_id=tenant_org_id, dry_run=dry_run),
    }
