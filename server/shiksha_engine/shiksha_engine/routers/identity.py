"""Identity — REST-Endpoints für /api/v1/identity.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §4 (Endpoints), §6 (Berechtigung).
Router OHNE Prefix — wird in main.py registriert.

14 Endpoints:
  /persons                              POST  list  GET-detail  PATCH  DELETE
  /persons/{id}/verify                  POST
  /persons/{id}/reject                  POST
  /persons/{id}/upload                  POST  (multipart, OCR/MRZ-Pipeline)
  /persons/{id}/documents               GET
  /documents/{id}/file                  GET   (leitung-only, Audit)
  /documents/{id}                       DELETE (leitung-only, DSGVO-Korrektur)
  /authorizations                       POST  GET  GET-detail  DELETE
  /audit-log                            GET   (leitung-only)
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from shiksha_engine.db import get_db
from shiksha_engine.deps import require_leitung_or_developer, require_operator_or_developer
from shiksha_engine.models.identity_audit_log import IdentityAuditLog
from shiksha_engine.models.identity_authorization import IdentityAuthorization
from shiksha_engine.models.identity_document import IdentityDocument
from shiksha_engine.models.identity_person import IdentityPerson
from shiksha_engine.models.operator import Operator
from shiksha_engine.models.organization import Organization
from shiksha_engine.schemas.identity import (
    IdentityAuditLogOut,
    IdentityAuthorizationCreate,
    IdentityAuthorizationOut,
    IdentityAuthorizationRevoke,
    IdentityDocumentOut,
    IdentityPersonCreate,
    IdentityPersonOut,
    IdentityPersonPatch,
)
from shiksha_engine.services import identity_query as iq
from shiksha_engine.services.identity_ocr import (
    OCRError,
    filter_mrz_to_whitelist,
    hash_doc_number,
    normalize_doc_number,
    parse_mrz,
    run_ocr,
)


router = APIRouter(tags=["identity"])


# ============================================================ Helpers


def _now() -> datetime:
    from datetime import timezone
    return datetime.now(tz=timezone.utc)


def _get_person_or_404(db: Session, person_id: int, operator: Operator) -> IdentityPerson:
    p = db.get(IdentityPerson, person_id)
    return iq.check_tenant_or_404(p, operator)


def _get_doc_or_404(db: Session, doc_id: int, operator: Operator) -> IdentityDocument:
    doc = db.get(IdentityDocument, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document nicht gefunden")
    # Tenant-Check via Parent-Person
    iq.check_tenant_or_404(doc.identity_person, operator)
    return doc


def _doc_to_out(doc: IdentityDocument) -> IdentityDocumentOut:
    return IdentityDocumentOut(
        id=doc.id,
        identity_person_id=doc.identity_person_id,
        doc_kind=doc.doc_kind,
        has_file=doc.has_file,
        file_deleted_at=doc.file_deleted_at,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        ocr_confidence=float(doc.ocr_confidence) if doc.ocr_confidence is not None else None,
        mrz_check_ok=doc.mrz_check_ok,
        uploaded_by_operator_id=doc.uploaded_by_operator_id,
        uploaded_at=doc.uploaded_at,
    )


def _authz_to_out(authz: IdentityAuthorization) -> IdentityAuthorizationOut:
    return IdentityAuthorizationOut(
        id=authz.id,
        tenant_org_id=authz.tenant_org_id,
        subject_identity_person_id=authz.subject_identity_person_id,
        target_type=authz.target_type,
        target_id=authz.target_id,
        auth_method=authz.auth_method,
        valid_from=authz.valid_from,
        valid_to=authz.valid_to,
        revoked_at=authz.revoked_at,
        revoked_by_operator_id=authz.revoked_by_operator_id,
        revoke_reason=authz.revoke_reason,
        granted_by_operator_id=authz.granted_by_operator_id,
        granted_at=authz.granted_at,
        notes=authz.notes,
        is_active=authz.is_active,
    )


# ============================================================ Person-CRUD


@router.post("/persons", response_model=IdentityPersonOut, status_code=201)
def create_person(
    body: IdentityPersonCreate,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    """Step 1 des Wizards. Person + Consent, Status 'pending'."""
    if not operator.org_id:
        raise HTTPException(status_code=400, detail="Operator muss Tenant-Kontext haben")

    now = _now()
    person = IdentityPerson(
        tenant_org_id=operator.org_id,
        full_name=body.full_name,
        birth_date=body.birth_date,
        consent_given=body.consent_given,
        consent_text=body.consent_text,
        consent_given_at=now if body.consent_given else None,
        verification_status="pending",
        created_at=now,
        updated_at=now,
    )
    db.add(person)
    db.flush()

    iq.write_audit(
        db, operator=operator,
        action="identity_person.create",
        target_kind="identity_person", target_id=person.id,
        tenant_org_id=operator.org_id,
        details={"full_name_present": bool(body.full_name)},
    )
    db.commit()
    return IdentityPersonOut.model_validate(person)


@router.get("/persons", response_model=list[IdentityPersonOut])
def list_persons(
    status_filter: Optional[str] = Query(None, alias="status"),
    linked: Optional[bool] = Query(None),
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    if not operator.org_id:
        raise HTTPException(status_code=400, detail="Operator muss Tenant-Kontext haben")
    q = db.query(IdentityPerson).filter(IdentityPerson.tenant_org_id == operator.org_id)
    if status_filter:
        q = q.filter(IdentityPerson.verification_status == status_filter)
    if linked is True:
        q = q.filter(IdentityPerson.linked_person_id.is_not(None))
    elif linked is False:
        q = q.filter(IdentityPerson.linked_person_id.is_(None))
    persons = q.order_by(IdentityPerson.created_at.desc()).all()

    iq.write_audit(
        db, operator=operator,
        action="identity_person.list",
        target_kind="identity_person", target_id=0,
        tenant_org_id=operator.org_id,
        details={"count": len(persons), "filter_status": status_filter, "filter_linked": linked},
    )
    db.commit()
    return [IdentityPersonOut.model_validate(p) for p in persons]


@router.get("/persons/{person_id}", response_model=IdentityPersonOut)
def get_person(
    person_id: int,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    p = _get_person_or_404(db, person_id, operator)
    iq.write_audit(
        db, operator=operator,
        action="identity_person.read",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
    )
    db.commit()
    return IdentityPersonOut.model_validate(p)


@router.patch("/persons/{person_id}", response_model=IdentityPersonOut)
def patch_person(
    person_id: int,
    body: IdentityPersonPatch,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    p = _get_person_or_404(db, person_id, operator)
    if p.verification_status == "verified":
        # Nach Verify nur legal_hold änderbar (Mitarbeiter darf keine Stammdaten
        # nachträglich rewriten — DSGVO-Integrität)
        if body.full_name is not None or body.birth_date is not None:
            raise HTTPException(
                status_code=422,
                detail="Stammdaten nach Verifikation nicht änderbar — neue Person anlegen",
            )

    changes: dict = {}
    if body.full_name is not None:
        p.full_name = body.full_name
        changes["full_name"] = True
    if body.birth_date is not None:
        p.birth_date = body.birth_date
        changes["birth_date"] = body.birth_date.isoformat()
    if body.legal_hold is not None:
        p.legal_hold = body.legal_hold
        changes["legal_hold"] = body.legal_hold
    p.updated_at = _now()

    iq.write_audit(
        db, operator=operator,
        action="identity_person.update",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
        details=changes,
    )
    db.commit()
    return IdentityPersonOut.model_validate(p)


@router.delete("/persons/{person_id}", status_code=204)
def delete_person(
    person_id: int,
    operator: Operator = Depends(require_leitung_or_developer),
    db: Session = Depends(get_db),
):
    """Hard-Delete inkl. Files + Authorizations (DSGVO Art. 17). Audit-Log bleibt."""
    p = _get_person_or_404(db, person_id, operator)
    iq.delete_all_person_files(p.id)
    # Audit VOR Delete (target_id wäre danach orphan)
    iq.write_audit(
        db, operator=operator,
        action="identity_person.delete",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
        details={"doc_number_hash": p.doc_number_hash, "manual_delete": True},
    )
    db.delete(p)
    db.commit()


@router.post("/persons/{person_id}/verify", response_model=IdentityPersonOut)
def verify_person(
    person_id: int,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    """Mitarbeiter bestätigt Identität. Triggers auto_link + structured_delete_at."""
    p = _get_person_or_404(db, person_id, operator)
    if not p.consent_given:
        raise HTTPException(status_code=422, detail="Consent fehlt — Verifikation nicht möglich")

    p.verification_status = "verified"
    p.verified_at = _now()
    p.verified_by_operator_id = operator.id
    p.updated_at = _now()

    # Auto-Link versuchen
    linked_id = iq.try_auto_link(db, p)

    # structured_delete_at berechnen
    tenant = db.get(Organization, p.tenant_org_id)
    if tenant:
        cfg = tenant.jurisdiction_yaml()
        p.structured_delete_at = iq.compute_structured_delete_at(p, cfg)

    iq.write_audit(
        db, operator=operator,
        action="identity_person.verify",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
        details={"linked_person_id": linked_id},
    )
    db.commit()
    return IdentityPersonOut.model_validate(p)


@router.post("/persons/{person_id}/reject", response_model=IdentityPersonOut)
def reject_person(
    person_id: int,
    payload: dict = Body(default_factory=dict),
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    p = _get_person_or_404(db, person_id, operator)
    reason = payload.get("reason", "")
    p.verification_status = "rejected"
    p.updated_at = _now()
    iq.write_audit(
        db, operator=operator,
        action="identity_person.reject",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
        details={"reason": reason},
    )
    db.commit()
    return IdentityPersonOut.model_validate(p)


# ============================================================ Document-Upload


@router.post("/persons/{person_id}/upload", response_model=IdentityDocumentOut, status_code=201)
async def upload_document(
    person_id: int,
    doc_kind: str = Query(..., regex="^(id_front|id_back|passport|other)$"),
    file: UploadFile = File(...),
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    """OCR + MRZ + Whitelist-Filter + Hash. Auto-Fill Person-Felder wenn leer."""
    p = _get_person_or_404(db, person_id, operator)
    tenant = db.get(Organization, p.tenant_org_id)
    if tenant is None:
        raise HTTPException(status_code=500, detail="Tenant nicht ladbar")
    cfg = tenant.jurisdiction_yaml().get("identity", {})

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Leere Datei")

    # OCR — robust gegen tesseract-Probleme
    ocr_text = ""
    ocr_confidence: float | None = None
    parsed_raw: dict | None = None
    mrz_filtered: dict = {}
    mrz_check_ok: bool | None = None

    if doc_kind in ("id_front", "id_back", "passport"):
        try:
            ocr_text, ocr_confidence = run_ocr(image_bytes)
        except OCRError as exc:
            # OCR optional — Datei + Metadata trotzdem speichern
            ocr_text = ""
            ocr_confidence = 0.0
            iq.write_audit(
                db, operator=operator,
                action="identity_document.ocr_failed",
                target_kind="identity_person", target_id=p.id,
                tenant_org_id=p.tenant_org_id,
                details={"error": str(exc)[:200]},
            )
        if doc_kind in ("id_back", "passport") and ocr_text:
            parsed_raw = parse_mrz(ocr_text)
        if parsed_raw:
            allowed = cfg.get("mrz_fields_to_store", [])
            mrz_filtered = filter_mrz_to_whitelist(parsed_raw, allowed)
            mrz_check_ok = "parse_error" not in parsed_raw

            # doc_number → Hash → identity_persons.doc_number_hash (wenn leer)
            doc_num = parsed_raw.get("doc_number")
            if doc_num and not p.doc_number_hash:
                normalized = normalize_doc_number(doc_num)
                hex_len = cfg.get("hash_length_hex", 24)
                p.doc_number_hash = hash_doc_number(normalized, tenant.identity_salt, hex_len)

            # Stammdaten-Autofill (NICHT überschreiben)
            if parsed_raw.get("birth_date") and not p.birth_date:
                from datetime import date
                try:
                    p.birth_date = date.fromisoformat(parsed_raw["birth_date"])
                except ValueError:
                    pass
            if parsed_raw.get("expiry") and not p.doc_expiry:
                from datetime import date
                try:
                    p.doc_expiry = date.fromisoformat(parsed_raw["expiry"])
                except ValueError:
                    pass
            if parsed_raw.get("mrz_format") and not p.doc_kind:
                # TD1 = Personalausweis, TD3 = Reisepass
                p.doc_kind = "personalausweis" if parsed_raw["mrz_format"] == "TD1" else "reisepass"

    # File-Storage
    file_ref, original_hash, file_size = iq.store_document_file(
        identity_person_id=p.id,
        doc_kind=doc_kind,
        file_bytes=image_bytes,
        mime_type=file.content_type,
    )

    # Document-Record
    doc = IdentityDocument(
        identity_person_id=p.id,
        doc_kind=doc_kind,
        file_ref=file_ref,
        mime_type=file.content_type,
        file_size_bytes=file_size,
        original_hash=original_hash,
        ocr_output=ocr_text or None,
        ocr_confidence=ocr_confidence,
        mrz_parsed=mrz_filtered or None,
        mrz_check_ok=mrz_check_ok,
        uploaded_by_operator_id=operator.id,
        uploaded_at=_now(),
    )
    db.add(doc)
    p.updated_at = _now()
    db.flush()

    iq.write_audit(
        db, operator=operator,
        action="identity_document.upload",
        target_kind="identity_document", target_id=doc.id,
        tenant_org_id=p.tenant_org_id,
        details={
            "doc_kind": doc_kind,
            "ocr_confidence": ocr_confidence,
            "mrz_check_ok": mrz_check_ok,
            "file_size_bytes": file_size,
        },
    )
    db.commit()
    return _doc_to_out(doc)


@router.get("/persons/{person_id}/documents", response_model=list[IdentityDocumentOut])
def list_documents(
    person_id: int,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    p = _get_person_or_404(db, person_id, operator)
    docs = (
        db.query(IdentityDocument)
        .filter(IdentityDocument.identity_person_id == p.id)
        .order_by(IdentityDocument.uploaded_at)
        .all()
    )
    iq.write_audit(
        db, operator=operator,
        action="identity_document.list",
        target_kind="identity_person", target_id=p.id,
        tenant_org_id=p.tenant_org_id,
        details={"count": len(docs)},
    )
    db.commit()
    return [_doc_to_out(d) for d in docs]


@router.get("/documents/{doc_id}/file")
def get_document_file(
    doc_id: int,
    operator: Operator = Depends(require_leitung_or_developer),  # leitung-only!
    db: Session = Depends(get_db),
):
    """Datei-Inhalt streamen. NUR leitung+developer (DSGVO-Schärfung)."""
    doc = _get_doc_or_404(db, doc_id, operator)
    if not doc.has_file:
        raise HTTPException(status_code=404, detail="File bereits gelöscht (Tier-1)")
    try:
        content = iq.read_document_file(doc.file_ref)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File auf Disk nicht auffindbar")
    iq.write_audit(
        db, operator=operator,
        action="identity_document.read",
        target_kind="identity_document", target_id=doc.id,
        tenant_org_id=doc.identity_person.tenant_org_id,
    )
    db.commit()
    return StreamingResponse(
        BytesIO(content),
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{doc.doc_kind}"'},
    )


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(
    doc_id: int,
    operator: Operator = Depends(require_leitung_or_developer),
    db: Session = Depends(get_db),
):
    """Hard-Delete einzelnes Document (DSGVO-Korrektur-Pfad)."""
    doc = _get_doc_or_404(db, doc_id, operator)
    if doc.file_ref:
        iq.delete_document_file(doc.file_ref)
    iq.write_audit(
        db, operator=operator,
        action="identity_document.delete",
        target_kind="identity_document", target_id=doc.id,
        tenant_org_id=doc.identity_person.tenant_org_id,
    )
    db.delete(doc)
    db.commit()


# ============================================================ Authorizations


@router.post("/authorizations", response_model=IdentityAuthorizationOut, status_code=201)
def create_authorization(
    body: IdentityAuthorizationCreate,
    operator: Operator = Depends(require_leitung_or_developer),
    db: Session = Depends(get_db),
):
    p = _get_person_or_404(db, body.subject_identity_person_id, operator)
    if p.verification_status != "verified":
        raise HTTPException(
            status_code=422,
            detail="Authorization nur für verifizierte Identitäten möglich",
        )
    # target_type='global' verlangt target_id=NULL (DB-CHECK greift sonst)
    if body.target_type == "global" and body.target_id is not None:
        raise HTTPException(status_code=422, detail="target_id muss NULL sein für target_type='global'")
    if body.target_type != "global" and body.target_id is None:
        raise HTTPException(status_code=422, detail=f"target_id ist Pflicht für target_type='{body.target_type}'")

    now = _now()
    authz = IdentityAuthorization(
        tenant_org_id=p.tenant_org_id,
        subject_identity_person_id=p.id,
        target_type=body.target_type,
        target_id=body.target_id,
        auth_method=body.auth_method,
        valid_from=now,
        valid_to=body.valid_to,
        granted_by_operator_id=operator.id,
        granted_at=now,
        notes=body.notes,
    )
    db.add(authz)
    db.flush()
    iq.write_audit(
        db, operator=operator,
        action="identity_authorization.grant",
        target_kind="identity_authorization", target_id=authz.id,
        tenant_org_id=p.tenant_org_id,
        details={
            "subject": p.id,
            "target_type": body.target_type,
            "target_id": body.target_id,
        },
    )
    db.commit()
    return _authz_to_out(authz)


@router.get("/authorizations", response_model=list[IdentityAuthorizationOut])
def list_authorizations(
    subject: Optional[int] = Query(None),
    target_type: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    if not operator.org_id:
        raise HTTPException(status_code=400, detail="Operator muss Tenant-Kontext haben")
    authzs = iq.list_active_authorizations(
        db,
        tenant_org_id=operator.org_id,
        subject_identity_person_id=subject,
        target_type=target_type,
        target_id=target_id,
    )
    iq.write_audit(
        db, operator=operator,
        action="identity_authorization.list",
        target_kind="identity_authorization", target_id=0,
        tenant_org_id=operator.org_id,
        details={"count": len(authzs)},
    )
    db.commit()
    return [_authz_to_out(a) for a in authzs]


@router.get("/authorizations/{authz_id}", response_model=IdentityAuthorizationOut)
def get_authorization(
    authz_id: int,
    operator: Operator = Depends(require_operator_or_developer),
    db: Session = Depends(get_db),
):
    a = db.get(IdentityAuthorization, authz_id)
    if a is None or (a.tenant_org_id != operator.org_id and operator.role != "developer"):
        raise HTTPException(status_code=404, detail="Authorization nicht gefunden")
    iq.write_audit(
        db, operator=operator,
        action="identity_authorization.read",
        target_kind="identity_authorization", target_id=a.id,
        tenant_org_id=a.tenant_org_id,
    )
    db.commit()
    return _authz_to_out(a)


@router.delete("/authorizations/{authz_id}", status_code=204)
def revoke_authorization(
    authz_id: int,
    body: IdentityAuthorizationRevoke,
    operator: Operator = Depends(require_leitung_or_developer),
    db: Session = Depends(get_db),
):
    """Soft-Delete (setzt revoked_at), KEIN Hard-Delete — Audit-Trail bleibt."""
    a = db.get(IdentityAuthorization, authz_id)
    if a is None or (a.tenant_org_id != operator.org_id and operator.role != "developer"):
        raise HTTPException(status_code=404, detail="Authorization nicht gefunden")
    iq.revoke_authorization(db, authorization=a, operator=operator, reason=body.revoke_reason)
    iq.write_audit(
        db, operator=operator,
        action="identity_authorization.revoke",
        target_kind="identity_authorization", target_id=a.id,
        tenant_org_id=a.tenant_org_id,
        details={"reason": body.revoke_reason},
    )
    db.commit()


# ============================================================ Audit-Log


@router.get("/audit-log", response_model=list[IdentityAuditLogOut])
def get_audit_log(
    target_kind: Optional[str] = Query(None),
    target_id: Optional[int] = Query(None),
    actor_operator_id: Optional[str] = Query(None),
    from_: Optional[datetime] = Query(None, alias="from"),
    to: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    operator: Operator = Depends(require_leitung_or_developer),
    db: Session = Depends(get_db),
):
    """Audit-Log lesen — nur leitung+developer."""
    if not operator.org_id and operator.role != "developer":
        raise HTTPException(status_code=400, detail="Operator muss Tenant-Kontext haben")
    q = db.query(IdentityAuditLog)
    if operator.role != "developer":
        q = q.filter(IdentityAuditLog.tenant_org_id == operator.org_id)
    if target_kind:
        q = q.filter(IdentityAuditLog.target_kind == target_kind)
    if target_id is not None:
        q = q.filter(IdentityAuditLog.target_id == target_id)
    if actor_operator_id:
        q = q.filter(IdentityAuditLog.actor_operator_id == actor_operator_id)
    if from_:
        q = q.filter(IdentityAuditLog.created_at >= from_)
    if to:
        q = q.filter(IdentityAuditLog.created_at < to)
    entries = q.order_by(IdentityAuditLog.created_at.desc()).limit(limit).all()
    # Bewusst KEIN Audit-of-Audit hier (würde Infinite-Loop in Detail-Auswertungen verursachen).
    return [IdentityAuditLogOut.model_validate(e) for e in entries]
