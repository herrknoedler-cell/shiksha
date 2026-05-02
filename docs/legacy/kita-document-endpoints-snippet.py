"""
SHIKSHA · KITA · kita_document_endpoints.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 29.04.2026 via deploy-Skript an
/opt/shiksha/kita_compliance_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/kita_compliance_router.py  (omnibus router, ~5389 Zeilen)

Bei einer späteren Modul-Trennung kann dieses Snippet zurück nach
server/kita_document_endpoints.py wandern.

Original: cowork/outputs/kita/server/kita_document_endpoints.py (2026-04-29)
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
SHIKSHA · KITA · Document-Upload-Endpoints (Foto/PDF/Scan)
Wird ans Ende von /opt/shiksha/kita_compliance_router.py angehängt.

Stand: 29.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/kita_compliance_router.py ===

import hashlib as _kd_hash
import re as _kd_re
import subprocess as _kd_subprocess
import tempfile as _kd_temp
import uuid as _kd_uuid
from datetime import date as _kd_date, datetime as _kd_dt
from pathlib import Path as _kd_Path

from fastapi import UploadFile as _kd_UploadFile, File as _kd_File, Body as _kd_Body, HTTPException as _kd_HTTP, Query as _kd_Query
from fastapi.responses import FileResponse as _kd_FileResponse

KITA_DOC_DIR = _kd_Path("/opt/shiksha/uploads/kita/documents")
KITA_DOC_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# OCR-PIPELINE
# ============================================================

def _kd_ocr_image(file_path: _kd_Path) -> str:
    """OCR mit tesseract (deutsch)."""
    try:
        result = _kd_subprocess.run(
            ["tesseract", str(file_path), "-", "-l", "deu", "--psm", "6"],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout
    except Exception as e:
        print(f"[kita-ocr] Fehler bei {file_path}: {e}")
        return ""


def _kd_ocr_pdf(file_path: _kd_Path) -> str:
    """PDF → Bilder → OCR. Probiert erst pdfplumber (Text-PDF), dann pdf2image+tesseract (Scan)."""
    text = ""
    # 1. Versuch: pdfplumber für native Text-PDFs
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if len(text.strip()) > 50:
            return text
    except Exception:
        pass

    # 2. Versuch: pdftoppm + tesseract (für Scans)
    try:
        with _kd_temp.TemporaryDirectory() as tmp:
            tmpdir = _kd_Path(tmp)
            _kd_subprocess.run(
                ["pdftoppm", "-r", "200", "-png", str(file_path), str(tmpdir / "page")],
                capture_output=True, timeout=120,
            )
            chunks = []
            for img in sorted(tmpdir.glob("page-*.png")):
                chunks.append(_kd_ocr_image(img))
            text = "\n".join(chunks)
    except Exception as e:
        print(f"[kita-ocr-pdf] Fehler bei {file_path}: {e}")

    return text


def _kd_extract_text(file_path: _kd_Path, mime: str) -> str:
    """Routet zur richtigen OCR-Methode."""
    if "pdf" in (mime or "").lower() or file_path.suffix.lower() == ".pdf":
        return _kd_ocr_pdf(file_path)
    return _kd_ocr_image(file_path)


# ============================================================
# DOCUMENT-TYPE DETECTION + FIELD-EXTRACTION
# ============================================================

def _kd_detect_type(text: str) -> tuple[str, str]:
    """Erkennt Dokumenttyp + Subtyp anhand Schlüsselwörtern."""
    t = text.lower()
    if "betreuungsvertrag" in t or "anmeldung" in t or "wochentag" in t and ("modul" in t or "halbtag" in t):
        sub = "krummelus" if "krummelus" in t else "generic"
        return "anmeldevertrag", sub
    if "krankenstand" in t or "arbeitsunfähig" in t or "ärztliche bestätigung" in t:
        return "krankenstand", "generic"
    if "dienstplan" in t or "schichtplan" in t:
        return "dienstplan", "generic"
    if "förderbescheid" in t or "subvention" in t and "tagsatz" in t:
        return "foerderbescheid", "stadt_dornbirn" if "dornbirn" in t else "generic"
    if "dienstvertrag" in t or "arbeitsvertrag" in t and ("kindergart" in t or "krippe" in t):
        return "mitarbeitervertrag", "generic"
    return "unknown", "generic"


def _kd_extract_anmeldevertrag(text: str) -> dict:
    """Felder aus Anmeldevertrag (Krummelus + ähnliche Vorlagen)."""
    fields = {}

    # Kind: Name
    m = _kd_re.search(r"NAME\s*DES\s*KINDES[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,50})", text, _kd_re.IGNORECASE)
    if m:
        fields["child_name"] = (m.group(1).strip().splitlines()[0]).strip()

    # Geburtsdatum
    m = _kd_re.search(r"Geburtsdatum[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["birth_date"] = _kd_normalize_date(m.group(1))

    # Adresse Kind
    m = _kd_re.search(r"Adresse[:\s]*([A-ZÄÖÜa-zäöüß0-9\s,\-\.]{5,80})", text, _kd_re.IGNORECASE)
    if m:
        fields["child_address"] = m.group(1).strip().splitlines()[0]

    # Sozialversicherungsnummer
    m = _kd_re.search(r"Sozialversicherungsnummer[:\s]*([\d\s]{6,14})", text, _kd_re.IGNORECASE)
    if m:
        fields["sv_number"] = _kd_re.sub(r"\s+", " ", m.group(1).strip())

    # Vertragslaufzeit
    m = _kd_re.search(r"vom\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})\s*bis\s*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["enrolled_from"] = _kd_normalize_date(m.group(1))
        fields["enrolled_to"] = _kd_normalize_date(m.group(2))

    # Eltern: Mutter / Vater
    m = _kd_re.search(r"MUTTER[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,60})", text, _kd_re.IGNORECASE)
    if m:
        fields["mother_name"] = m.group(1).strip().splitlines()[0].strip()
    m = _kd_re.search(r"VATER[:\s]*([A-ZÄÖÜa-zäöüß\-\s]{3,60})", text, _kd_re.IGNORECASE)
    if m:
        fields["father_name"] = m.group(1).strip().splitlines()[0].strip()

    # Telefon-Nummern (für Eltern-Kontakt)
    phones = _kd_re.findall(r"(?:Telefon[a-z]*[:\s]*|\b)(\+?\d[\d\s]{6,18})", text)
    if len(phones) >= 1:
        fields["phone_1"] = phones[0].strip()
    if len(phones) >= 2:
        fields["phone_2"] = phones[1].strip()

    # E-Mail-Adressen
    emails = _kd_re.findall(r"[\w\.\-]+@[\w\.\-]+\.\w+", text)
    if emails:
        fields["emails"] = "; ".join(emails[:3])

    # MODULE-MATRIX (das wichtigste!)
    # Heuristik: Suche nach Wochentag-Zeilen und versuche, gebuchte Spalten zu erkennen
    # Da OCR von Häkchen schwierig ist, geben wir die rohe Zeile zurück und der User markiert nach
    module_lines = {}
    for tag in ["MONTAG", "DIENSTAG", "MITTWOCH", "DONNERSTAG", "FREITAG"]:
        m = _kd_re.search(rf"{tag}\s+([^\n]{{0,80}})", text, _kd_re.IGNORECASE)
        if m:
            module_lines[tag.lower()] = m.group(1).strip()
    if module_lines:
        # Heuristik: ein "X", "✓", "x", oder gefüllter Kreis nahe einer Zeit-Spalte = gebucht
        # Spalten-Standard: 07:15-11:30 | 11:30-12:30 | 12:30-13:30 | 13:30-17:30
        slots = ["07:15-11:30", "11:30-12:30", "12:30-13:30", "13:30-17:30"]
        booked = {}
        for tag, line in module_lines.items():
            line_clean = line.lower()
            booked_slots = []
            # Versuch 1: Wenn ein Marker (X/✓/●) im OCR-Text auftaucht
            markers = _kd_re.findall(r"([Xx✓●■◉])", line)
            if markers:
                booked_slots = ["unknown_slot"]
            booked[tag] = {"raw_line": line, "booked_slots": booked_slots}
        fields["modules_raw"] = booked

    return fields


def _kd_extract_krankenstand(text: str) -> dict:
    fields = {}
    m = _kd_re.search(r"(?:Name|Mitarbeiter)[:\s]+([A-ZÄÖÜa-zäöüß\-\s]{3,50})", text, _kd_re.IGNORECASE)
    if m:
        fields["staff_name"] = m.group(1).strip().splitlines()[0]
    m = _kd_re.search(r"(?:von|ab|seit)[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["absent_from"] = _kd_normalize_date(m.group(1))
    m = _kd_re.search(r"(?:bis|voraussichtlich)[:\s]*(\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4})", text, _kd_re.IGNORECASE)
    if m:
        fields["absent_to"] = _kd_normalize_date(m.group(1))
    fields["reason"] = "krank"
    return fields


def _kd_normalize_date(s: str) -> str:
    """'08.01.2024' / '8.1.24' → '2024-01-08'."""
    s = s.strip().replace("/", ".").replace("-", ".")
    parts = s.split(".")
    if len(parts) != 3:
        return s
    d, m, y = parts
    if len(y) == 2:
        y = ("20" + y) if int(y) < 50 else ("19" + y)
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return s


def _kd_extract_fields(text: str, doc_type: str) -> dict:
    """Routet zur richtigen Extraction."""
    if doc_type == "anmeldevertrag":
        return _kd_extract_anmeldevertrag(text)
    if doc_type == "krankenstand":
        return _kd_extract_krankenstand(text)
    return {}


# ============================================================
# ENDPOINTS
# ============================================================

@kita_router.post("/documents/upload")
async def kita_upload_document(
    files: list[_kd_UploadFile] = _kd_File(...),
    force: bool = False,
):
    """
    Multi-File Upload für KITA-Dokumente (Foto/PDF/Scan).
    - Speichert Original
    - SHA256-Duplikat-Check (Override mit ?force=true)
    - OCR + Auto-Detection des Doc-Typs
    - Field-Extraction in kita_document_fields
    """
    results = []

    for file in files:
        content = await file.read()
        if not content:
            results.append({"filename": file.filename, "ok": False, "error": "leere Datei"})
            continue

        file_hash = _kd_hash.sha256(content).hexdigest()

        # Duplikat?
        if not force:
            with engine.connect() as conn:
                existing = conn.execute(sa.text(
                    "SELECT id, file_name, created_at FROM kita_documents WHERE file_hash = :h LIMIT 1"
                ), {"h": file_hash}).first()
            if existing:
                results.append({
                    "filename": file.filename, "ok": False, "duplicate": True,
                    "existing_id": existing[0], "existing_name": existing[1],
                    "error": f"Existiert bereits als: {existing[1]}",
                })
                continue

        # Speichern
        doc_id = _new_id("kdoc")
        safe_name = "".join(c for c in (file.filename or "doc") if c.isalnum() or c in "._-")[:80]
        disk_path = KITA_DOC_DIR / f"{doc_id}_{safe_name}"
        disk_path.write_bytes(content)
        mime = file.content_type or ""

        # OCR
        text = _kd_extract_text(disk_path, mime)
        doc_type, subtype = _kd_detect_type(text)
        fields = _kd_extract_fields(text, doc_type)

        # In DB
        with engine.begin() as conn:
            conn.execute(sa.text("""
                INSERT INTO kita_documents
                  (id, document_type, detected_subtype, raw_text, file_path, file_name,
                   file_size, file_mime, file_hash, source_type, status)
                VALUES (:id, :dt, :sub, :raw, :p, :n, :sz, :m, :h, :src, 'pending')
            """), {
                "id": doc_id, "dt": doc_type, "sub": subtype, "raw": text,
                "p": str(disk_path), "n": file.filename, "sz": len(content),
                "m": mime, "h": file_hash,
                "src": "pdf" if "pdf" in mime.lower() else "photo",
            })
            for key, val in fields.items():
                if isinstance(val, dict):
                    val = str(val)
                if not val:
                    continue
                conn.execute(sa.text("""
                    INSERT INTO kita_document_fields (id, document_id, field_key, field_value, confidence)
                    VALUES (:id, :did, :k, :v, 0.85)
                """), {
                    "id": _new_id("kfld"), "did": doc_id, "k": key, "v": str(val)[:1000],
                })

        results.append({
            "filename": file.filename, "ok": True,
            "document_id": doc_id, "document_type": doc_type, "subtype": subtype,
            "fields_extracted": len(fields),
            "ocr_chars": len(text),
        })

    return {"results": results, "count": len(results)}


@kita_router.get("/documents")
async def kita_list_documents(
    document_type: str = _kd_Query(default=None),
    status: str = _kd_Query(default=None),
    limit: int = 100,
):
    sql = """
    SELECT d.id, d.document_type, d.detected_subtype, d.status, d.file_name,
           d.file_size, d.created_at, d.applied_at, d.applied_to_table,
           (SELECT COUNT(*) FROM kita_document_fields WHERE document_id = d.id) AS field_count,
           LENGTH(d.raw_text) AS ocr_chars
    FROM kita_documents d
    WHERE 1=1
    """
    params = {"lim": limit}
    if document_type:
        sql += " AND d.document_type = :dt"
        params["dt"] = document_type
    if status:
        sql += " AND d.status = :st"
        params["st"] = status
    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()
    return {
        "count": len(rows),
        "documents": [
            {
                "id": r[0], "document_type": r[1], "subtype": r[2], "status": r[3],
                "file_name": r[4], "file_size": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "applied_at": r[7].isoformat() if r[7] else None,
                "applied_to": r[8],
                "field_count": r[9], "ocr_chars": r[10] or 0,
            }
            for r in rows
        ],
    }


@kita_router.get("/documents/{doc_id}")
async def kita_doc_detail(doc_id: str):
    with engine.connect() as conn:
        d = conn.execute(sa.text("""
            SELECT id, document_type, detected_subtype, raw_text, file_name, status,
                   applied_at, applied_to_table, applied_to_id, created_at
            FROM kita_documents WHERE id=:id
        """), {"id": doc_id}).first()
        if not d:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        fields = conn.execute(sa.text("""
            SELECT id, field_key, field_value, confidence, is_user_edited
            FROM kita_document_fields WHERE document_id=:id ORDER BY field_key
        """), {"id": doc_id}).fetchall()
    return {
        "document": {
            "id": d[0], "document_type": d[1], "subtype": d[2], "raw_text": d[3],
            "file_name": d[4], "status": d[5],
            "applied_at": d[6].isoformat() if d[6] else None,
            "applied_to": d[7], "applied_id": d[8],
            "created_at": d[9].isoformat() if d[9] else None,
        },
        "fields": [
            {
                "id": f[0], "field_key": f[1], "field_value": f[2],
                "confidence": float(f[3]) if f[3] else None,
                "is_user_edited": f[4],
            }
            for f in fields
        ],
    }


@kita_router.get("/documents/{doc_id}/file")
async def kita_doc_file(doc_id: str):
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
    if not row or not row[0]:
        raise _kd_HTTP(404, "Datei nicht gefunden")
    fp = _kd_Path(row[0])
    if not fp.exists():
        raise _kd_HTTP(404, "Datei nicht auf Disk")
    return _kd_FileResponse(path=fp, media_type=row[2] or "application/octet-stream", filename=row[1])


@kita_router.delete("/documents/{doc_id}")
async def kita_doc_delete(doc_id: str):
    with engine.begin() as conn:
        row = conn.execute(sa.text(
            "SELECT file_path FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not row:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        conn.execute(sa.text("DELETE FROM kita_documents WHERE id=:id"), {"id": doc_id})
    if row[0]:
        try:
            _kd_Path(row[0]).unlink(missing_ok=True)
        except Exception:
            pass
    return {"id": doc_id, "deleted": True}


@kita_router.patch("/documents/{doc_id}/fields")
async def kita_doc_edit_field(doc_id: str, payload: dict = _kd_Body(...)):
    """Manuelle Korrektur eines Felds."""
    field_key = payload.get("field_key")
    field_value = payload.get("field_value")
    if not field_key:
        raise _kd_HTTP(400, "field_key ist Pflicht")

    with engine.begin() as conn:
        existing = conn.execute(sa.text(
            "SELECT id FROM kita_document_fields WHERE document_id=:d AND field_key=:k LIMIT 1"
        ), {"d": doc_id, "k": field_key}).first()
        if existing:
            conn.execute(sa.text("""
                UPDATE kita_document_fields SET field_value=:v, confidence=1.0, is_user_edited=true
                WHERE id=:id
            """), {"v": str(field_value or ""), "id": existing[0]})
        else:
            conn.execute(sa.text("""
                INSERT INTO kita_document_fields (id, document_id, field_key, field_value, confidence, is_user_edited)
                VALUES (:id, :d, :k, :v, 1.0, true)
            """), {"id": _new_id("kfld"), "d": doc_id, "k": field_key, "v": str(field_value or "")})
    return {"document_id": doc_id, "field_key": field_key, "saved": True}


@kita_router.post("/documents/{doc_id}/apply")
async def kita_doc_apply(doc_id: str, payload: dict = _kd_Body(default_factory=dict)):
    """
    Applies extracted fields into the appropriate target table.
    For 'anmeldevertrag' → kita_child_enrollments.
    """
    target_group_id = payload.get("group_id")
    if not target_group_id:
        raise _kd_HTTP(400, "group_id im Payload nötig (welche Gruppe wird das Kind zugeordnet?)")

    with engine.connect() as conn:
        d = conn.execute(sa.text(
            "SELECT document_type, status FROM kita_documents WHERE id=:id"
        ), {"id": doc_id}).first()
        if not d:
            raise _kd_HTTP(404, "Dokument nicht gefunden")
        if d[0] != "anmeldevertrag":
            raise _kd_HTTP(400, f"Apply nur für anmeldevertrag implementiert, dies ist {d[0]}")

        fields = {
            f[0]: f[1] for f in conn.execute(sa.text(
                "SELECT field_key, field_value FROM kita_document_fields WHERE document_id=:id"
            ), {"id": doc_id}).fetchall()
        }

    enrollment_id = _new_id("enr")
    child_anon = _kd_hash.sha256((fields.get("child_name", "") + fields.get("birth_date", "")).encode()).hexdigest()[:16]

    # Alter berechnen
    age_months = 36
    if fields.get("birth_date") and fields.get("enrolled_from"):
        try:
            bd = _kd_dt.fromisoformat(fields["birth_date"]).date()
            ef = _kd_dt.fromisoformat(fields["enrolled_from"]).date()
            age_months = (ef.year - bd.year) * 12 + (ef.month - bd.month)
        except Exception:
            pass

    # Stunden aus modules_raw schätzen — als Fallback 25h/Wo
    booked_hours = float(payload.get("booked_hours_per_week", 25))

    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO kita_child_enrollments
              (id, group_id, child_anon_id, age_months, enrolled_from, enrolled_to,
               booked_hours_per_week, notes)
            VALUES (:id, :g, :a, :am, :f, :t, :h, :n)
        """), {
            "id": enrollment_id, "g": target_group_id, "a": "k_" + child_anon,
            "am": age_months,
            "f": fields.get("enrolled_from") or _kd_date.today().isoformat(),
            "t": fields.get("enrolled_to"),
            "h": booked_hours,
            "n": f"Importiert aus Anmeldevertrag {fields.get('child_name', '')}",
        })
        conn.execute(sa.text("""
            UPDATE kita_documents SET status='applied', applied_at=NOW(),
              applied_to_table='kita_child_enrollments', applied_to_id=:eid
            WHERE id=:id
        """), {"eid": enrollment_id, "id": doc_id})

    return {
        "document_id": doc_id, "enrollment_id": enrollment_id,
        "applied_to": "kita_child_enrollments", "child_anon_id": "k_" + child_anon,
    }
