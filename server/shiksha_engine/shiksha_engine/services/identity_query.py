"""Identity-Query — Berechtigung, Audit-Writer, File-Storage, Authorization.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §4-7.

Lebt im services-Layer, damit Router-Code dünn bleibt und Audit-/Berechtigungs-
Logik an einer Stelle testbar ist.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from shiksha_engine.models.identity_audit_log import IdentityAuditLog
from shiksha_engine.models.identity_authorization import IdentityAuthorization
from shiksha_engine.models.identity_document import IdentityDocument
from shiksha_engine.models.identity_person import IdentityPerson
from shiksha_engine.models.operator import Operator
from shiksha_engine.models.person import Person
from shiksha_engine.settings import get_settings

log = logging.getLogger("shiksha.identity.query")


# ============================================================ Audit-Writer


def write_audit(
    db: Session,
    *,
    operator: Operator | None,
    action: str,
    target_kind: str,
    target_id: int,
    tenant_org_id: str,
    details: dict[str, Any] | None = None,
    actor_kind: str = "operator",
) -> IdentityAuditLog:
    """Schreibt IdentityAuditLog-Eintrag (Pflicht für jeden Endpoint).

    actor_kind = 'operator' für menschliche Aktionen, 'system' für Auto-Jobs
    (Cleanup-Worker), 'subject_self' reserviert für Phase 2.
    """
    entry = IdentityAuditLog(
        tenant_org_id=tenant_org_id,
        actor_operator_id=operator.id if operator else None,
        actor_kind=actor_kind,
        action=action,
        target_kind=target_kind,
        target_id=target_id,
        details=details,
        created_at=datetime.now(tz=timezone.utc),
    )
    db.add(entry)
    db.flush()
    return entry


# ============================================================ Berechtigung


def _is_leitung_or_developer(operator: Operator) -> bool:
    return operator.role in ("leitung", "developer", "operator")  # 'operator' legacy


def _is_staff(operator: Operator) -> bool:
    return operator.role in ("leitung", "padagoge", "trainer", "developer", "operator")


def check_tenant_or_404(person: IdentityPerson | None, operator: Operator) -> IdentityPerson:
    """Wirft 404 wenn Person nicht existiert oder anderer Tenant.

    Wir geben absichtlich 404 statt 403 — Existenz eines Records darf
    Cross-Tenant nicht leakable sein.
    """
    from fastapi import HTTPException
    if person is None:
        raise HTTPException(status_code=404, detail="IdentityPerson nicht gefunden")
    if person.tenant_org_id != operator.org_id and operator.role != "developer":
        raise HTTPException(status_code=404, detail="IdentityPerson nicht gefunden")
    return person


# ============================================================ Auto-Link


def try_auto_link(db: Session, identity_person: IdentityPerson) -> int | None:
    """Versucht IdentityPerson mit shiksha_core.persons zu verknüpfen.

    Match-Logik: gleicher Tenant, gleicher (case-insensitive trimmed) full_name,
    gleiches birth_date. Bei Mehrdeutigkeit (>1 Match) kein Auto-Link.

    Setzt identity_person.linked_person_id und gibt persons.id zurück, oder
    None wenn kein eindeutiger Match.
    """
    if not identity_person.full_name or not identity_person.birth_date:
        return None
    target_name = identity_person.full_name.strip().lower()
    matches = (
        db.query(Person)
        .filter(
            Person.tenant_org_id == identity_person.tenant_org_id,
            Person.birth_date == identity_person.birth_date,
            Person.deleted_at.is_(None),
        )
        .all()
    )
    matched = [
        p for p in matches
        if f"{p.given_name} {p.family_name or ''}".strip().lower() == target_name
    ]
    if len(matched) != 1:
        return None
    identity_person.linked_person_id = matched[0].id
    db.flush()
    return matched[0].id


# ============================================================ Authorization-Resolver


def list_active_authorizations(
    db: Session,
    *,
    tenant_org_id: str,
    subject_identity_person_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> list[IdentityAuthorization]:
    """Aktive Authorizations (nicht revoked + valid_to in Zukunft oder NULL)."""
    now = datetime.now(tz=timezone.utc)
    q = db.query(IdentityAuthorization).filter(
        IdentityAuthorization.tenant_org_id == tenant_org_id,
        IdentityAuthorization.revoked_at.is_(None),
        or_(
            IdentityAuthorization.valid_to.is_(None),
            IdentityAuthorization.valid_to > now,
        ),
    )
    if subject_identity_person_id is not None:
        q = q.filter(IdentityAuthorization.subject_identity_person_id == subject_identity_person_id)
    if target_type is not None:
        q = q.filter(IdentityAuthorization.target_type == target_type)
    if target_id is not None:
        q = q.filter(IdentityAuthorization.target_id == target_id)
    return q.order_by(IdentityAuthorization.granted_at.desc()).all()


def revoke_authorization(
    db: Session,
    *,
    authorization: IdentityAuthorization,
    operator: Operator,
    reason: str,
) -> IdentityAuthorization:
    """Soft-Delete via revoked_at + revoked_by + reason. KEIN Hard-Delete."""
    if authorization.revoked_at is not None:
        return authorization  # Idempotent
    authorization.revoked_at = datetime.now(tz=timezone.utc)
    authorization.revoked_by_operator_id = operator.id
    authorization.revoke_reason = reason
    db.flush()
    return authorization


# ============================================================ File-Storage


def _upload_root() -> Path:
    """Storage-Root als absoluter Pfad. Engine-Root + identity_upload_root."""
    settings = get_settings()
    base = Path(settings.identity_upload_root)
    if not base.is_absolute():
        # Relativ zur Engine-Wurzel (zwei Ebenen über services/)
        engine_root = Path(__file__).resolve().parents[2]
        base = engine_root / settings.identity_upload_root
    return base


_MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def store_document_file(
    *,
    identity_person_id: int,
    doc_kind: str,
    file_bytes: bytes,
    mime_type: str | None,
) -> tuple[str, str, int]:
    """Speichert Datei unter <UPLOAD_ROOT>/<person_id>/<doc_kind>.<ext>.

    Returns (file_ref, original_hash, file_size_bytes). file_ref ist
    relativer Pfad ab UPLOAD_ROOT.
    """
    ext = _MIME_TO_EXT.get((mime_type or "").lower(), "bin")
    root = _upload_root()
    person_dir = root / str(identity_person_id)
    person_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{doc_kind}.{ext}"
    target = person_dir / fname
    target.write_bytes(file_bytes)

    original_hash = hashlib.sha256(file_bytes).hexdigest()
    file_ref = f"{identity_person_id}/{fname}"
    return file_ref, original_hash, len(file_bytes)


def read_document_file(file_ref: str) -> bytes:
    """Liest Datei aus Storage. Service-Schicht macht role_scope-Check separat."""
    path = _upload_root() / file_ref
    if not path.exists():
        raise FileNotFoundError(f"Identity-Document file_ref={file_ref} nicht auf Disk")
    return path.read_bytes()


def delete_document_file(file_ref: str) -> bool:
    """Löscht Datei. Idempotent — keine Exception wenn schon weg.

    Returns True wenn etwas gelöscht wurde, False wenn nichts da war.
    """
    path = _upload_root() / file_ref
    if path.exists():
        path.unlink()
        # Wenn person_dir leer ist, auch das aufräumen
        parent = path.parent
        try:
            parent.rmdir()
        except OSError:
            pass  # Verzeichnis nicht leer — andere doc_kinds noch da
        return True
    return False


def delete_all_person_files(identity_person_id: int) -> int:
    """Löscht alle Files einer Person (rekursives Verzeichnis-Delete).

    Wird vor identity_persons-DELETE aufgerufen (DSGVO Art. 17).
    Returns Anzahl gelöschter Files.
    """
    person_dir = _upload_root() / str(identity_person_id)
    if not person_dir.exists():
        return 0
    count = sum(1 for _ in person_dir.iterdir())
    shutil.rmtree(person_dir, ignore_errors=True)
    return count


# ============================================================ Delete-Date-Berechnung


def compute_structured_delete_at(
    identity_person: IdentityPerson,
    jurisdiction_config: dict[str, Any],
) -> datetime:
    """Berechnet structured_delete_at gemäß jurisdiction.

    Vor Verifikation (pending): created_at + 30 Tage (verwaiste Drafts).
    Nach Verifikation: verified_at + structured_data_after_end_years Jahre.

    Wenn linked_person mit exit_date existiert, würde idealerweise
    exit_date + N Jahre genutzt — Phase-2-Erweiterung wenn persons.exit_date
    befüllt wird. Bis dahin: verified_at als Fallback.
    """
    retention = jurisdiction_config.get("identity", {}).get("retention", {})
    years = retention.get("structured_data_after_end_years", 3)

    if identity_person.verification_status == "verified" and identity_person.verified_at:
        base = identity_person.verified_at
        delta_days = years * 365
    else:
        base = identity_person.created_at or datetime.now(tz=timezone.utc)
        delta_days = 30

    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=delta_days)
