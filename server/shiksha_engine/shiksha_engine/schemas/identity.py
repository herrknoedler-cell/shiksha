"""Identity-Schemas — Pydantic v2.

Spec: docs/specs/SHIKSHA_IDENTITY_SPEC.md §4 (Endpoints) — Schemas folgen
den Endpoint-Signaturen, die in 5.5.6.2 die Router-Bodies + Responses
formen.

DSGVO-Sparsamkeit in den Out-Schemas:
  - KEIN doc_number_hash (intern, nur für Re-Verifikations-Lookup)
  - KEIN consent_text (nur im Detail-Endpoint, für Audit-Replay)
  - KEIN file_ref im Documents-Out (interner Pfad)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================ IdentityPerson


class IdentityPersonCreate(BaseModel):
    """Wizard Step 1 — Person + Consent."""
    full_name: str
    birth_date: Optional[date] = None
    consent_text: str
    consent_given: bool = True


class IdentityPersonPatch(BaseModel):
    """Stammdaten-Update vor Verifikation. Service-Layer enforced was nach
    verified noch änderbar ist."""
    full_name: Optional[str] = None
    birth_date: Optional[date] = None
    legal_hold: Optional[bool] = None


class IdentityPersonOut(BaseModel):
    """Listen- + Detail-View. DSGVO-sparse — kein Hash, kein consent_text."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    tenant_org_id: str
    full_name: str
    birth_date: Optional[date] = None

    doc_kind: Optional[str] = None
    doc_expiry: Optional[date] = None

    verification_status: Literal["pending", "verified", "rejected"]
    verified_at: Optional[datetime] = None
    verified_by_operator_id: Optional[str] = None

    linked_person_id: Optional[int] = None
    legal_hold: bool

    structured_delete_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ============================================================ IdentityDocument


class IdentityDocumentOut(BaseModel):
    """Metadata-View für GET /persons/{id}/documents.

    file_ref bewusst NICHT exposed — Download nur via
    GET /documents/{id}/file (eigener Endpoint mit Audit-Log-Schreibung)."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    identity_person_id: int
    doc_kind: Literal["id_front", "id_back", "passport", "other"]

    has_file: bool = Field(description="True wenn file_ref != NULL (Tier-1 noch nicht ausgelöst)")
    file_deleted_at: Optional[datetime] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None

    ocr_confidence: Optional[float] = None
    mrz_check_ok: Optional[bool] = None
    # mrz_parsed bewusst NICHT in Out — enthält ggf. sensitive Whitelist-Werte,
    # für Audit-Replay über Detail-Endpoint freischalten falls nötig.

    uploaded_by_operator_id: Optional[str] = None
    uploaded_at: datetime


# ============================================================ IdentityAuthorization


class IdentityAuthorizationCreate(BaseModel):
    """POST /authorizations — Service-Layer prüft verification_status='verified'."""
    subject_identity_person_id: int
    target_type: Literal["child", "booking", "lesson", "global"]
    target_id: Optional[int] = None
    auth_method: Literal["ausweis_scan", "passkey_signed", "manual_override"] = "ausweis_scan"
    valid_to: Optional[datetime] = None
    notes: Optional[str] = None


class IdentityAuthorizationRevoke(BaseModel):
    """DELETE /authorizations/{id} body."""
    revoke_reason: str


class IdentityAuthorizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    tenant_org_id: str
    subject_identity_person_id: int

    target_type: Literal["child", "booking", "lesson", "global"]
    target_id: Optional[int] = None
    auth_method: Literal["ausweis_scan", "passkey_signed", "manual_override"]

    valid_from: datetime
    valid_to: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revoked_by_operator_id: Optional[str] = None
    revoke_reason: Optional[str] = None

    granted_by_operator_id: str
    granted_at: datetime
    notes: Optional[str] = None

    is_active: bool = Field(description="Service-Layer-Property: nicht revoked + valid_to in future")


# ============================================================ IdentityAuditLog


class IdentityAuditLogOut(BaseModel):
    """GET /audit-log (nur leitung). Details-JSONB unverändert durchgereicht."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    tenant_org_id: str
    actor_operator_id: Optional[str] = None
    actor_kind: Literal["operator", "system", "subject_self"]
    action: str
    target_kind: str
    target_id: int
    details: Optional[dict[str, Any]] = None
    created_at: datetime
