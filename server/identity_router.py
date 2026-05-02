"""
SHIKSHA · Identity-Router
Cross-Edition Identitäts-Verifikation.

Endpoints:
  POST   /identity/persons              — Person anlegen
  GET    /identity/persons              — Liste (mit edition-Filter)
  GET    /identity/persons/{id}         — Detail
  PATCH  /identity/persons/{id}         — Stammdaten editieren
  DELETE /identity/persons/{id}         — Löschen
  POST   /identity/persons/{id}/verify  — Mitarbeiter bestätigt manuell
  POST   /identity/persons/{id}/upload  — Multi-Doc-Upload (front/back/selfie)
  GET    /identity/documents/{id}/file  — Original-Bild (auth-protected)
  POST   /identity/authorizations       — Berechtigung anlegen
  DELETE /identity/authorizations/{id}  — Berechtigung widerrufen
  GET    /identity/authorizations?target_type=child&target_id=...

Stand: 29.04.2026
"""
from __future__ import annotations

import hashlib as _id_hash
import json as _id_json
import re as _id_re
import subprocess as _id_subprocess
import tempfile as _id_temp
import uuid as _id_uuid
from datetime import date as _id_date, datetime as _id_dt, timedelta as _id_td
from pathlib import Path as _id_Path

import sqlalchemy as sa
from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from database import engine


identity_router = APIRouter(prefix="/identity", tags=["identity"])

IDENTITY_DIR = _id_Path("/opt/shiksha/uploads/identity")
IDENTITY_DIR.mkdir(parents=True, exist_ok=True)


def _id_new(prefix: str) -> str:
    return f"{prefix}_{_id_uuid.uuid4().hex[:12]}"


# ============================================================
# OCR + MRZ-Parser
# ============================================================

def _id_ocr(file_path: _id_Path) -> tuple[str, float]:
    """OCR mit tesseract — Deutsche Sprache. Return: (text, confidence)."""
    try:
        result = _id_subprocess.run(
            ["tesseract", str(file_path), "-", "-l", "deu", "--psm", "6"],
            capture_output=True, text=True, timeout=30,
        )
        text = result.stdout
        # Confidence-Schätzung: Anteil "echter" Wörter
        words = [w for w in _id_re.findall(r"\w{3,}", text)]
        conf = min(1.0, len(words) / 50.0) if words else 0.0
        return text, round(conf, 2)
    except Exception as e:
        print(f"[identity-ocr] {e}")
        return "", 0.0


def _id_parse_mrz(text: str) -> dict | None:
    """
    Parsed MRZ (Machine Readable Zone) aus OCR-Text.
    ID-Cards (TD1, 3 Zeilen × 30 Zeichen) und Pässe (TD3, 2×44).
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Suche MRZ-typische Zeilen mit < als Filler
    mrz_lines = [l for l in lines if "<<" in l and len(l) >= 28]
    if not mrz_lines:
        return None

    result = {"raw_lines": mrz_lines}

    # ID-Card TD1 (3 Zeilen, 30 Zeichen) — z.B. deutscher Personalausweis
    if len(mrz_lines) >= 3 and all(28 <= len(l) <= 32 for l in mrz_lines[:3]):
        l1, l2, l3 = mrz_lines[0], mrz_lines[1], mrz_lines[2]
        try:
            # L1: ID<DEU<<<<DOCNUMBER<<...
            result["doc_country"] = l1[2:5]
            result["doc_number"] = l1[5:14].replace("<", "")
            # L2: birth_date<gender<expiry<nationality
            result["birth_date_yymmdd"] = l2[0:6]
            result["gender"] = l2[7]
            result["expiry_yymmdd"] = l2[8:14]
            result["nationality"] = l2[15:18]
            # L3: surname<<given_names
            name_parts = l3.split("<<")
            if len(name_parts) >= 2:
                result["surname"] = name_parts[0].replace("<", " ").strip()
                result["given_names"] = name_parts[1].replace("<", " ").strip()
            result["mrz_format"] = "TD1"
        except Exception as e:
            result["parse_error"] = str(e)

    # Reisepass TD3 (2 Zeilen, 44 Zeichen)
    elif len(mrz_lines) >= 2 and all(40 <= len(l) <= 48 for l in mrz_lines[:2]):
        l1, l2 = mrz_lines[0], mrz_lines[1]
        try:
            result["doc_country"] = l1[2:5]
            name_parts = l1[5:].split("<<")
            if len(name_parts) >= 2:
                result["surname"] = name_parts[0].replace("<", " ").strip()
                result["given_names"] = name_parts[1].replace("<", " ").strip()
            result["doc_number"] = l2[0:9].replace("<", "")
            result["nationality"] = l2[10:13]
            result["birth_date_yymmdd"] = l2[13:19]
            result["gender"] = l2[20]
            result["expiry_yymmdd"] = l2[21:27]
            result["mrz_format"] = "TD3"
        except Exception as e:
            result["parse_error"] = str(e)

    return result


def _id_yymmdd_to_iso(yymmdd: str) -> str | None:
    """'940115' → '1994-01-15'. Heuristik: YY < 30 → 20xx, sonst 19xx."""
    if not yymmdd or len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = yymmdd[:2], yymmdd[2:4], yymmdd[4:6]
    full_year = (2000 + int(yy)) if int(yy) < 50 else (1900 + int(yy))
    try:
        return f"{full_year:04d}-{int(mm):02d}-{int(dd):02d}"
    except Exception:
        return None


def _id_extract_fields(text: str, mrz: dict | None) -> dict:
    """Extrahiert strukturierte Felder aus OCR + MRZ."""
    fields = {}
    if mrz:
        fields["surname"] = mrz.get("surname")
        fields["given_names"] = mrz.get("given_names")
        fields["doc_number"] = mrz.get("doc_number")
        fields["nationality"] = mrz.get("nationality")
        fields["gender"] = mrz.get("gender")
        bd = _id_yymmdd_to_iso(mrz.get("birth_date_yymmdd"))
        if bd:
            fields["birth_date"] = bd
        ex = _id_yymmdd_to_iso(mrz.get("expiry_yymmdd"))
        if ex:
            fields["expiry"] = ex
        return fields

    # Fallback: Regex auf OCR-Text (wenn keine MRZ)
    m = _id_re.search(r"(?:Geburtsdatum|Date of Birth)[:\s]+(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _id_re.IGNORECASE)
    if m:
        fields["birth_date_raw"] = m.group(1)
    m = _id_re.search(r"(?:Familienname|Surname)[:\s]+([A-ZÄÖÜa-zäöüß\-\s]{2,40})", text, _id_re.IGNORECASE)
    if m:
        fields["surname"] = m.group(1).strip().splitlines()[0]
    m = _id_re.search(r"(?:Vorname|Given Names?)[:\s]+([A-ZÄÖÜa-zäöüß\-\s]{2,40})", text, _id_re.IGNORECASE)
    if m:
        fields["given_names"] = m.group(1).strip().splitlines()[0]
    return fields


# ============================================================
# Audit-Log Helper
# ============================================================

def _id_audit(conn, person_id: str | None, action: str, actor: str = "system",
              edition: str = None, target_type: str = None, target_id: str = None,
              outcome: str = "success", notes: str = None):
    conn.execute(sa.text("""
        INSERT INTO identity_audit_log
          (id, person_id, action, actor, edition, target_type, target_id, outcome, notes)
        VALUES (:id, :p, :a, :ac, :ed, :tt, :ti, :o, :n)
    """), {
        "id": _id_new("audit"), "p": person_id, "a": action, "ac": actor,
        "ed": edition, "tt": target_type, "ti": target_id,
        "o": outcome, "n": notes,
    })


# ============================================================
# ENDPOINTS — PERSONS
# ============================================================

@identity_router.post("/persons")
async def identity_create_person(payload: dict = Body(...)):
    full_name = (payload.get("full_name") or "").strip()
    if not full_name:
        raise HTTPException(400, "full_name ist Pflicht")
    edition = payload.get("edition", "kita")

    pid = _id_new("idp")
    auto_del = _id_dt.now() + _id_td(days=365)

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO identity_persons
              (id, full_name, birth_date, contact_phone, contact_email, address,
               edition, person_role, document_type,
               consent_given, consent_text, consent_at, auto_delete_at, notes)
            VALUES (:id, :n, :bd, :p, :e, :a,
                    :ed, :r, :dt,
                    :cg, :ct, :cgat, :ad, :no)
        """), {
            "id": pid, "n": full_name, "bd": payload.get("birth_date"),
            "p": payload.get("contact_phone"), "e": payload.get("contact_email"),
            "a": payload.get("address"),
            "ed": edition, "r": payload.get("person_role", "pickup_person"),
            "dt": payload.get("document_type", "personalausweis"),
            "cg": payload.get("consent_given", False),
            "ct": payload.get("consent_text"),
            "cgat": _id_dt.now() if payload.get("consent_given") else None,
            "ad": auto_del, "no": payload.get("notes"),
        })
        _id_audit(conn, pid, "create", payload.get("actor", "system"), edition=edition)

    return {"id": pid, "full_name": full_name}


@identity_router.get("/persons")
async def identity_list_persons(
    edition: str = None,
    role: str = None,
    status: str = None,
    limit: int = 200,
):
    sql = """
    SELECT p.id, p.full_name, p.birth_date, p.contact_phone, p.contact_email,
           p.edition, p.person_role, p.document_type, p.document_number, p.document_expires_at,
           p.verification_status, p.consent_given, p.created_at,
           (SELECT COUNT(*) FROM identity_documents WHERE person_id = p.id) AS doc_count,
           (SELECT COUNT(*) FROM identity_authorizations
            WHERE person_id = p.id AND revoked_at IS NULL) AS auth_count
    FROM identity_persons p
    WHERE 1=1
    """
    params = {"lim": limit}
    if edition:
        sql += " AND p.edition = :ed"
        params["ed"] = edition
    if role:
        sql += " AND p.person_role = :r"
        params["r"] = role
    if status:
        sql += " AND p.verification_status = :st"
        params["st"] = status
    sql += " ORDER BY p.created_at DESC LIMIT :lim"

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "persons": [
            {
                "id": r[0], "full_name": r[1],
                "birth_date": r[2].isoformat() if r[2] else None,
                "contact_phone": r[3], "contact_email": r[4],
                "edition": r[5], "person_role": r[6],
                "document_type": r[7], "document_number": r[8],
                "document_expires_at": r[9].isoformat() if r[9] else None,
                "verification_status": r[10],
                "consent_given": r[11],
                "created_at": r[12].isoformat() if r[12] else None,
                "doc_count": r[13] or 0, "auth_count": r[14] or 0,
            }
            for r in rows
        ],
    }


@identity_router.get("/persons/{person_id}")
async def identity_person_detail(person_id: str):
    with engine.connect() as conn:
        p = conn.execute(sa.text("""
            SELECT id, full_name, birth_date, nationality, contact_phone, contact_email,
                   address, edition, person_role, document_type, document_number,
                   document_expires_at, consent_given, consent_text, consent_at,
                   verification_status, verified_by, verified_at, notes,
                   auto_delete_at, created_at
            FROM identity_persons WHERE id = :id
        """), {"id": person_id}).first()
        if not p:
            raise HTTPException(404, "Person nicht gefunden")
        docs = conn.execute(sa.text("""
            SELECT id, doc_kind, file_name, file_size, ocr_confidence, extracted_fields,
                   captured_at FROM identity_documents WHERE person_id = :id
            ORDER BY captured_at
        """), {"id": person_id}).fetchall()
        auths = conn.execute(sa.text("""
            SELECT id, edition, target_type, target_id, role, valid_from, valid_to,
                   granted_by, revoked_at, notes, created_at
            FROM identity_authorizations WHERE person_id = :id ORDER BY created_at DESC
        """), {"id": person_id}).fetchall()

    return {
        "person": {
            "id": p[0], "full_name": p[1],
            "birth_date": p[2].isoformat() if p[2] else None,
            "nationality": p[3], "contact_phone": p[4], "contact_email": p[5],
            "address": p[6], "edition": p[7], "person_role": p[8],
            "document_type": p[9], "document_number": p[10],
            "document_expires_at": p[11].isoformat() if p[11] else None,
            "consent_given": p[12], "consent_text": p[13],
            "consent_at": p[14].isoformat() if p[14] else None,
            "verification_status": p[15],
            "verified_by": p[16],
            "verified_at": p[17].isoformat() if p[17] else None,
            "notes": p[18],
            "auto_delete_at": p[19].isoformat() if p[19] else None,
            "created_at": p[20].isoformat() if p[20] else None,
        },
        "documents": [
            {
                "id": d[0], "doc_kind": d[1], "file_name": d[2], "file_size": d[3],
                "ocr_confidence": float(d[4]) if d[4] is not None else None,
                "extracted_fields": d[5],
                "captured_at": d[6].isoformat() if d[6] else None,
            }
            for d in docs
        ],
        "authorizations": [
            {
                "id": a[0], "edition": a[1], "target_type": a[2], "target_id": a[3],
                "role": a[4],
                "valid_from": a[5].isoformat() if a[5] else None,
                "valid_to": a[6].isoformat() if a[6] else None,
                "granted_by": a[7], "revoked_at": a[8].isoformat() if a[8] else None,
                "notes": a[9], "created_at": a[10].isoformat() if a[10] else None,
            }
            for a in auths
        ],
    }


@identity_router.patch("/persons/{person_id}")
async def identity_update_person(person_id: str, payload: dict = Body(...)):
    fields = {}
    for k in ("full_name", "birth_date", "nationality", "contact_phone",
              "contact_email", "address", "person_role", "document_type",
              "document_number", "document_expires_at", "consent_given",
              "consent_text", "notes"):
        if k in payload:
            fields[k] = payload[k]
    if not fields:
        raise HTTPException(400, "keine Felder im Payload")
    set_parts = [f"{k} = :{k}" for k in fields]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE identity_persons SET {', '.join(set_parts)} WHERE id = :id"
    fields["id"] = person_id
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Person nicht gefunden")
    return {"id": person_id, "updated": [k for k in fields if k != "id"]}


@identity_router.delete("/persons/{person_id}")
async def identity_delete_person(person_id: str):
    with engine.begin() as conn:
        files = conn.execute(sa.text(
            "SELECT file_path FROM identity_documents WHERE person_id = :id"
        ), {"id": person_id}).fetchall()
        result = conn.execute(sa.text(
            "DELETE FROM identity_persons WHERE id = :id"
        ), {"id": person_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Person nicht gefunden")
    for fp in files:
        try:
            _id_Path(fp[0]).unlink(missing_ok=True)
        except Exception:
            pass
    return {"id": person_id, "deleted": True}


@identity_router.post("/persons/{person_id}/verify")
async def identity_verify_person(person_id: str, payload: dict = Body(default_factory=dict)):
    """Mitarbeiter bestätigt manuell die Identität."""
    actor = payload.get("verified_by", "kita-leitung")
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE identity_persons SET
              verification_status = 'verified',
              verified_by = :a, verified_at = NOW(), updated_at = NOW()
            WHERE id = :id
        """), {"a": actor, "id": person_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Person nicht gefunden")
        _id_audit(conn, person_id, "verify", actor)
    return {"id": person_id, "verification_status": "verified", "verified_by": actor}


# ============================================================
# UPLOAD: Front, Back, Selfie
# ============================================================

@identity_router.post("/persons/{person_id}/upload")
async def identity_upload(
    person_id: str,
    doc_kind: str = Query(..., description="id_front | id_back | selfie | passport_main"),
    file: UploadFile = File(...),
):
    if doc_kind not in ("id_front", "id_back", "selfie", "passport_main"):
        raise HTTPException(400, f"Unbekannter doc_kind: {doc_kind}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Leere Datei")

    file_hash = _id_hash.sha256(content).hexdigest()
    safe_name = "".join(c for c in (file.filename or "doc") if c.isalnum() or c in '._-')[:80]
    doc_id = _id_new("iddoc")
    disk_path = IDENTITY_DIR / f"{doc_id}_{doc_kind}_{safe_name}"
    disk_path.write_bytes(content)

    # OCR (nur für Ausweis-Seiten, nicht für Selfie)
    raw_text = ""
    ocr_conf = 0.0
    mrz = None
    extracted = {}
    if doc_kind in ("id_front", "id_back", "passport_main"):
        raw_text, ocr_conf = _id_ocr(disk_path)
        if doc_kind in ("id_back", "passport_main"):
            mrz = _id_parse_mrz(raw_text)
        extracted = _id_extract_fields(raw_text, mrz)

    mime = file.content_type or "application/octet-stream"

    # JSON robust serialisieren (json.dumps macht None→null, escapt korrekt)
    extracted_json = _id_json.dumps(extracted) if extracted else None
    mrz_json = _id_json.dumps(mrz) if mrz else None

    with engine.begin() as conn:
        # CAST(...) statt ::jsonb damit SQLAlchemy text() die Parameter sauber bindet
        conn.execute(sa.text("""
            INSERT INTO identity_documents
              (id, person_id, doc_kind, file_path, file_name, file_size, file_mime, file_hash,
               raw_text, extracted_fields, mrz_parsed, ocr_confidence)
            VALUES (:id, :pid, :dk, :p, :n, :sz, :m, :h,
                    :rt, CAST(:ef AS jsonb), CAST(:mz AS jsonb), :oc)
        """), {
            "id": doc_id, "pid": person_id, "dk": doc_kind,
            "p": str(disk_path), "n": file.filename, "sz": len(content),
            "m": mime, "h": file_hash, "rt": raw_text,
            "ef": extracted_json,
            "mz": mrz_json,
            "oc": ocr_conf,
        })

        # Auto-fill Stammdaten in identity_persons wenn vorhanden
        if extracted:
            updates = []
            params = {"id": person_id}
            if extracted.get("birth_date"):
                updates.append("birth_date = :bd")
                params["bd"] = extracted["birth_date"]
            if extracted.get("nationality"):
                updates.append("nationality = :nt")
                params["nt"] = extracted["nationality"]
            if extracted.get("doc_number"):
                updates.append("document_number = :dn")
                params["dn"] = extracted["doc_number"]
            if extracted.get("expiry"):
                updates.append("document_expires_at = :ex")
                params["ex"] = extracted["expiry"]
            if extracted.get("surname") and extracted.get("given_names"):
                updates.append("full_name = COALESCE(NULLIF(:fn, ''), full_name)")
                params["fn"] = f"{extracted['given_names']} {extracted['surname']}".strip()
            if updates:
                sql = f"UPDATE identity_persons SET {', '.join(updates)}, updated_at = NOW() WHERE id = :id"
                conn.execute(sa.text(sql), params)

        _id_audit(conn, person_id, f"capture_{doc_kind}",
                  actor="upload", outcome="success",
                  notes=f"OCR conf {ocr_conf}")

    return {
        "document_id": doc_id, "doc_kind": doc_kind,
        "file_size": len(content), "ocr_confidence": ocr_conf,
        "extracted_fields": extracted, "mrz_parsed": mrz,
    }


@identity_router.get("/documents/{doc_id}/file")
async def identity_doc_file(doc_id: str):
    with engine.connect() as conn:
        r = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime, person_id FROM identity_documents WHERE id = :id"
        ), {"id": doc_id}).first()
    if not r:
        raise HTTPException(404, "Dokument nicht gefunden")
    fp = _id_Path(r[0])
    if not fp.exists():
        raise HTTPException(404, "Datei nicht auf Disk")
    # Audit-Log: Wer hat zugegriffen?
    with engine.begin() as conn:
        _id_audit(conn, r[3], "access", actor="dashboard", notes=f"doc {doc_id}")
    return FileResponse(path=fp, media_type=r[2] or "application/octet-stream", filename=r[1])


# ============================================================
# AUTHORIZATIONS
# ============================================================

@identity_router.post("/authorizations")
async def identity_create_auth(payload: dict = Body(...)):
    """
    Body:
      person_id, edition, target_type, target_id, role,
      valid_from, valid_to (optional), granted_by, notes
    """
    person_id = payload.get("person_id")
    if not person_id:
        raise HTTPException(400, "person_id Pflicht")
    aid = _id_new("idauth")
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO identity_authorizations
              (id, person_id, edition, target_type, target_id, role,
               valid_from, valid_to, granted_by, notes)
            VALUES (:id, :p, :ed, :tt, :ti, :r,
                    :vf, :vt, :gb, :n)
        """), {
            "id": aid, "p": person_id,
            "ed": payload.get("edition", "kita"),
            "tt": payload.get("target_type", "child"),
            "ti": payload.get("target_id"),
            "r": payload.get("role", "pickup"),
            "vf": payload.get("valid_from"),
            "vt": payload.get("valid_to"),
            "gb": payload.get("granted_by"),
            "n": payload.get("notes"),
        })
        _id_audit(conn, person_id, "authorize",
                  actor=payload.get("granted_by", "system"),
                  edition=payload.get("edition"),
                  target_type=payload.get("target_type"),
                  target_id=payload.get("target_id"))
    return {"id": aid, "person_id": person_id}


@identity_router.delete("/authorizations/{auth_id}")
async def identity_revoke_auth(auth_id: str, payload: dict = Body(default_factory=dict)):
    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE identity_authorizations
            SET revoked_at = NOW(), revoke_reason = :r
            WHERE id = :id AND revoked_at IS NULL
        """), {"r": payload.get("reason", "manual"), "id": auth_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Berechtigung nicht gefunden oder bereits widerrufen")
    return {"id": auth_id, "revoked": True}


@identity_router.get("/authorizations")
async def identity_list_auths(
    target_type: str = None,
    target_id: str = None,
    edition: str = None,
):
    sql = """
    SELECT a.id, a.person_id, p.full_name, p.verification_status,
           a.edition, a.target_type, a.target_id, a.role,
           a.valid_from, a.valid_to, a.granted_by, a.revoked_at, a.notes
    FROM identity_authorizations a
    JOIN identity_persons p ON p.id = a.person_id
    WHERE a.revoked_at IS NULL
    """
    params = {}
    if target_type:
        sql += " AND a.target_type = :tt"
        params["tt"] = target_type
    if target_id:
        sql += " AND a.target_id = :ti"
        params["ti"] = target_id
    if edition:
        sql += " AND a.edition = :ed"
        params["ed"] = edition
    sql += " ORDER BY p.full_name"
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "authorizations": [
            {
                "id": r[0], "person_id": r[1], "person_name": r[2],
                "verification_status": r[3],
                "edition": r[4], "target_type": r[5], "target_id": r[6], "role": r[7],
                "valid_from": r[8].isoformat() if r[8] else None,
                "valid_to": r[9].isoformat() if r[9] else None,
                "granted_by": r[10],
                "notes": r[12],
            }
            for r in rows
        ],
    }
