"""Identity-Endpoints — Integrationstests gegen /api/v1/identity.

Tests gehen über TestClient, nutzen das Krummelus-Tenant aus conftest.
OCR/MRZ wird in test_identity_ocr.py separat geprüft; hier nur die
Endpoint-Verkabelung + Berechtigungs-Logik + Audit-Pflicht.
"""
from __future__ import annotations

import io

import pytest


def _png_bytes() -> bytes:
    """Minimales gültiges PNG (1x1 transparent). Kein OCR-Wert, aber multipart valid."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ============================================================ Person-CRUD


def test_create_person_minimum_fields(client, mira_token):
    r = client.post(
        "/api/v1/identity/persons",
        json={"full_name": "Oma Maria", "consent_text": "Ich willige ein.", "consent_given": True},
        headers=_h(mira_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["full_name"] == "Oma Maria"
    assert body["verification_status"] == "pending"
    assert body["id"] > 0


def test_list_persons_filter_by_status(client, mira_token):
    client.post("/api/v1/identity/persons",
                json={"full_name": "Pending Person", "consent_text": "x", "consent_given": True},
                headers=_h(mira_token))
    r = client.get("/api/v1/identity/persons?status=pending", headers=_h(mira_token))
    assert r.status_code == 200
    body = r.json()
    assert all(p["verification_status"] == "pending" for p in body)


def test_get_person_detail(client, mira_token):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Detail Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.get(f"/api/v1/identity/persons/{created['id']}", headers=_h(mira_token))
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


def test_patch_person_blocked_after_verify(client, mira_token):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Block Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    client.post(f"/api/v1/identity/persons/{created['id']}/verify", headers=_h(mira_token))
    r = client.patch(
        f"/api/v1/identity/persons/{created['id']}",
        json={"full_name": "Neuer Name"},
        headers=_h(mira_token),
    )
    assert r.status_code == 422


def test_verify_writes_audit_and_sets_delete_at(client, mira_token, db_session, calendar_mira):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Verify Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.post(f"/api/v1/identity/persons/{created['id']}/verify", headers=_h(mira_token))
    assert r.status_code == 200
    body = r.json()
    assert body["verification_status"] == "verified"
    assert body["verified_at"] is not None
    assert body["structured_delete_at"] is not None  # aus jurisdiction.yaml berechnet

    # Audit-Eintrag mit action='identity_person.verify' muss existieren
    from shiksha_engine.models import IdentityAuditLog
    db_session.expire_all()
    audits = db_session.query(IdentityAuditLog).filter_by(
        target_kind="identity_person", target_id=created["id"], action="identity_person.verify",
    ).all()
    assert len(audits) >= 1


def test_reject_person_with_reason(client, mira_token):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Reject Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.post(
        f"/api/v1/identity/persons/{created['id']}/reject",
        json={"reason": "Ausweis abgelaufen"},
        headers=_h(mira_token),
    )
    assert r.status_code == 200
    assert r.json()["verification_status"] == "rejected"


def test_verify_requires_consent(client, mira_token):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "No Consent", "consent_text": "", "consent_given": False},
                          headers=_h(mira_token)).json()
    r = client.post(f"/api/v1/identity/persons/{created['id']}/verify", headers=_h(mira_token))
    assert r.status_code == 422


# ============================================================ Upload


def test_upload_id_front_stores_file(client, mira_token, db_session):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Upload Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.post(
        f"/api/v1/identity/persons/{created['id']}/upload?doc_kind=id_front",
        files={"file": ("front.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=_h(mira_token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["doc_kind"] == "id_front"
    assert body["has_file"] is True
    assert body["mime_type"] == "image/png"


# ============================================================ File-Access (leitung-only)


def test_get_document_file_works_for_mira_leitung(client, mira_token):
    """Mira hat role='leitung' → darf File lesen."""
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "File Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    upload = client.post(
        f"/api/v1/identity/persons/{created['id']}/upload?doc_kind=id_front",
        files={"file": ("f.png", io.BytesIO(_png_bytes()), "image/png")},
        headers=_h(mira_token),
    ).json()
    r = client.get(f"/api/v1/identity/documents/{upload['id']}/file", headers=_h(mira_token))
    assert r.status_code == 200


# ============================================================ Authorizations


def test_create_authorization_requires_verified_status(client, mira_token):
    """Authorization auf pending-Identity → 422."""
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Authz Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.post(
        "/api/v1/identity/authorizations",
        json={
            "subject_identity_person_id": created["id"],
            "target_type": "child",
            "target_id": 42,
        },
        headers=_h(mira_token),
    )
    assert r.status_code == 422


def test_create_and_revoke_authorization(client, mira_token, db_session):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Authz OK", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    client.post(f"/api/v1/identity/persons/{created['id']}/verify", headers=_h(mira_token))

    r = client.post(
        "/api/v1/identity/authorizations",
        json={
            "subject_identity_person_id": created["id"],
            "target_type": "child",
            "target_id": 99,
            "notes": "Großmutter holt Mo+Mi ab",
        },
        headers=_h(mira_token),
    )
    assert r.status_code == 201, r.text
    authz_id = r.json()["id"]
    assert r.json()["is_active"] is True

    # Revoke (soft-delete)
    r = client.request(
        "DELETE",
        f"/api/v1/identity/authorizations/{authz_id}",
        json={"revoke_reason": "Sorgerechtsänderung"},
        headers=_h(mira_token),
    )
    assert r.status_code == 204

    # Row bleibt, mit revoked_at gesetzt
    from shiksha_engine.models import IdentityAuthorization
    db_session.expire_all()
    a = db_session.get(IdentityAuthorization, authz_id)
    assert a is not None
    assert a.revoked_at is not None
    assert a.revoke_reason == "Sorgerechtsänderung"


def test_authorization_global_target_id_must_be_null(client, mira_token):
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Global Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    client.post(f"/api/v1/identity/persons/{created['id']}/verify", headers=_h(mira_token))
    r = client.post(
        "/api/v1/identity/authorizations",
        json={
            "subject_identity_person_id": created["id"],
            "target_type": "global",
            "target_id": 42,  # ← muss NULL sein
        },
        headers=_h(mira_token),
    )
    assert r.status_code == 422


# ============================================================ Tenant-Isolation


def test_tenant_isolation_other_token_404s(client, mira_token, other_tenant_token):
    """Person in Tenant A ist für Tenant B unsichtbar (404, nicht 403)."""
    created = client.post("/api/v1/identity/persons",
                          json={"full_name": "Iso Test", "consent_text": "x", "consent_given": True},
                          headers=_h(mira_token)).json()
    r = client.get(f"/api/v1/identity/persons/{created['id']}", headers=_h(other_tenant_token))
    assert r.status_code == 404


# ============================================================ Audit-Log


def test_audit_log_endpoint_works_for_leitung(client, mira_token):
    """Audit-Log lesen funktioniert für Mira (leitung)."""
    client.post("/api/v1/identity/persons",
                json={"full_name": "Audit View", "consent_text": "x", "consent_given": True},
                headers=_h(mira_token))
    r = client.get("/api/v1/identity/audit-log?target_kind=identity_person", headers=_h(mira_token))
    assert r.status_code == 200
    body = r.json()
    # mindestens der gerade angelegte create-Eintrag
    assert any(e["action"] == "identity_person.create" for e in body)
