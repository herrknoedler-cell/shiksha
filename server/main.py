# ============================================================
# SHIKSHA — main.py
# FastAPI Server — erster operativer Endpunkt
# POST /orchestrate → KURS_001 Flow
# ============================================================

from accounting_router import accounting_router
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from models import OrchestratorRequest, OrchestratorObject
from orchestrator import process_request

app = FastAPI(
    title="SHIKSHA API",
    description="SHIKSHA Orchestrator — V1 Server Sketch",
    version="1.0.0",
)


# ------------------------------------------------------------
# HEALTH CHECK
# ------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "system": "SHIKSHA", "version": "1.0.0"}


# ------------------------------------------------------------
# HAUPT-ENDPUNKT
# POST /orchestrate
# Nimmt einen Request entgegen, gibt ein vollständiges
# Orchestrator-Objekt zurück.
# ------------------------------------------------------------

@app.post("/orchestrate", response_model=OrchestratorObject)
async def orchestrate(req: OrchestratorRequest) -> OrchestratorObject:
    """
    Verarbeitet eine Anfrage durch den SHIKSHA Orchestrator.

    Beispiel-Request für KURS_001:
    {
        "raw_input": "Kannst du den Segelkurs morgen verschieben? Es soll Sturm geben.",
        "edition": "camp.shiksha",
        "user_role": "operator",
        "source_type": "operator",
        "source_id": "op_camp_03",
        "session_id": "sess_operator_camp_20260417_007",
        "active_entity_ids": ["course_sail_042", "booking_221", "loc_lake_02"]
    }
    """
    try:
        result = await process_request(req)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/orchestrate/summary")
async def orchestrate_summary(req: OrchestratorRequest) -> dict:
    """
    Wie /orchestrate, aber gibt nur das Wesentliche zurück:
    output_mode, summary, next_steps, review_required.
    """
    try:
        result = await process_request(req)
        return {
            "request_id":      result.request_id,
            "edition":         result.edition,
            "output_mode":     result.output.mode,
            "summary":         result.output.summary,
            "proposal":        result.output.proposal.model_dump() if result.output.proposal else None,
            "next_steps":      [s.model_dump() for s in result.output.next_steps],
            "review_required": result.review_required.model_dump() if result.review_required else None,
            "policy_warnings": [w.model_dump() for w in result.policy_check.warnings],
            "weather":         result.domain_selection.supporting_domain_results[0].result
                               if result.domain_selection.supporting_domain_results else None,
            "learning_candidate": (
                result.learning.learning_candidate.model_dump()
                if result.learning.learning_candidate else None
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------
# DOCUMENT MODULE V1.2 — business.shiksha
# POST /documents/analyze
# POST /documents/confirm-link
# ----------------------------------------------------------

from document_models import (
    DocumentIntakeRequest,
    DocumentAnalysisResponse,
    DocumentConfirmLinkRequest,
    DocumentConfirmLinkResponse,
    SavedLink,
)
from document_module import build_document_analysis
from kita_compliance_router import kita_router
from world_router import world_router
from identity_router import identity_router
import extractor_extensions  # patches FIELD_EXTRACTORS
from compression import compress, DocumentSummary

import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine, MetaData, Table, Column, String, Float, Text, DateTime

# DB setup for document tables
_doc_engine = create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")
_doc_meta = MetaData()

_documents = Table("documents", _doc_meta,
    Column("id", String, primary_key=True),
    Column("edition", String),
    Column("document_type", String),
    Column("source_type", String),
    Column("raw_text", Text),
    Column("status", String),
    Column("created_at", DateTime),
    extend_existing=True,
)
_doc_fields = Table("document_field_candidates", _doc_meta,
    Column("id", String, primary_key=True),
    Column("document_id", String),
    Column("field_key", String),
    Column("field_value", String),
    Column("confidence", Float),
    Column("created_at", DateTime),
    extend_existing=True,
)
_doc_links = Table("document_links", _doc_meta,
    Column("id", String, primary_key=True),
    Column("document_id", String),
    Column("entity_type", String),
    Column("entity_id", String),
    Column("link_type", String),
    Column("confidence", Float),
    Column("review_status", String),
    Column("created_at", DateTime),
    Column("confirmed_at", DateTime),
    extend_existing=True,
)
_doc_meta.create_all(_doc_engine, checkfirst=True)


@app.post("/documents/analyze")
async def analyze_document(request: DocumentIntakeRequest):
    analysis = build_document_analysis(
        raw_text=request.raw_text,
        edition=request.edition,
        source_type=request.source_type,
    )
    now = datetime.now(timezone.utc)
    with _doc_engine.begin() as conn:
        conn.execute(_documents.insert().values(
            id=analysis.document_id,
            edition=analysis.edition,
            document_type=analysis.detected_document_type,
            source_type=request.source_type,
            raw_text=request.raw_text,
            status="analyzed",
            created_at=now,
        ))
        for f in analysis.extracted_fields:
            conn.execute(_doc_fields.insert().values(
                id=str(uuid.uuid4()),
                document_id=analysis.document_id,
                field_key=f.field_key,
                field_value=f.field_value,
                confidence=f.confidence,
                created_at=now,
            ))
    return analysis


@app.post("/documents/analyze/summary")
async def analyze_document_summary(request: DocumentIntakeRequest):
    analysis = build_document_analysis(
        raw_text=request.raw_text,
        edition=request.edition,
        source_type=request.source_type,
    )
    return compress(analysis)


@app.post("/documents/confirm-link")
async def confirm_document_link(request: DocumentConfirmLinkRequest):
    if request.operator_decision not in ("confirm", "correct"):
        raise HTTPException(status_code=400, detail="operator_decision must be 'confirm' or 'correct'")
    now = datetime.now(timezone.utc)
    link_id = str(uuid.uuid4())
    review_status = "confirmed" if request.operator_decision == "confirm" else "corrected"
    with _doc_engine.begin() as conn:
        conn.execute(_doc_links.insert().values(
            id=link_id,
            document_id=request.document_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            link_type="belongs_to",
            confidence=1.0,
            review_status=review_status,
            created_at=now,
            confirmed_at=now,
        ))
        conn.execute(_documents.update()
            .where(_documents.c.id == request.document_id)
            .values(status="reviewed")
        )
    return DocumentConfirmLinkResponse(
        success=True,
        document_status="reviewed",
        saved_link=SavedLink(
            link_id=link_id,
            document_id=request.document_id,
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            link_type="belongs_to",
            review_status=review_status,
            confirmed_at=now,
        ),
    )


# ----------------------------------------------------------
# CUSTOMER ENTITIES — GET + POST
# ----------------------------------------------------------

from sqlalchemy import text as _text

@app.get("/entities")
def get_entities():
    with _doc_engine.connect() as conn:
        rows = conn.execute(_text(
            "SELECT id, name, aliases, contacts, addresses, entity_type FROM customers ORDER BY entity_type, name"
        )).fetchall()
        return [{"id": r[0], "name": r[1], "entity_type": r[5] or "customer", "aliases": r[2] or [], "contacts": r[3] or [], "addresses": r[4] or []} for r in rows]

@app.post("/entities")
def create_entity(body: dict):
    import uuid, json
    eid = "cust_" + str(uuid.uuid4())[:8]
    with _doc_engine.begin() as conn:
        conn.execute(_text(
            "INSERT INTO customers (id,name,aliases,contacts,addresses) "
            "VALUES (:id,:name,:al,:co,:ad)"
        ), {"id": eid, "name": body.get("name",""),
            "al": json.dumps(body.get("aliases",[])),
            "co": json.dumps(body.get("contacts",[])),
            "ad": json.dumps(body.get("addresses",[]))})
    return {"id": eid, "name": body.get("name"), "status": "created"}


# ----------------------------------------------------------
# DOCUMENT UPLOAD — POST /documents/upload
# Accepts PDF or JPEG/PNG, extracts text, runs analyze flow
# ----------------------------------------------------------

from fastapi import UploadFile, File
import tempfile, os

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    edition: str = "business.shiksha",
    language: str = "de"
):
    filename = file.filename.lower()
    content = await file.read()

    # Determine source type and extract text
    raw_text = ""
    source_type = "unknown"

    if filename.endswith(".pdf"):
        source_type = "pdf"
        try:
            from pdfminer.high_level import extract_text
            import io
            raw_text = extract_text(io.BytesIO(content))
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"PDF extraction failed: {e}")

    elif filename.endswith((".jpg", ".jpeg", ".png")):
        source_type = "image_scan"
        raise HTTPException(
            status_code=415,
            detail="Image upload received. Please convert to PDF or use /documents/analyze with raw_text."
        )

    elif filename.endswith(".html"):
        raise HTTPException(
            status_code=415,
            detail="HTML file detected — not a document. Please upload a PDF."
        )

    else:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {filename}")

    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    # Run the standard analyze flow
    analysis = build_document_analysis(
        raw_text=raw_text.strip(),
        edition=edition,
        source_type=source_type,
    )

    # Persist to DB
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    with _doc_engine.begin() as conn:
        conn.execute(_documents.insert().values(
            id=analysis.document_id,
            edition=analysis.edition,
            document_type=analysis.detected_document_type,
            source_type=source_type,
            raw_text=raw_text.strip()[:10000],
            status="analyzed",
            created_at=now,
        ))
        for f in analysis.extracted_fields:
            conn.execute(_doc_fields.insert().values(
                id=str(uuid.uuid4()),
                document_id=analysis.document_id,
                field_key=f.field_key,
                field_value=f.field_value,
                confidence=f.confidence,
                created_at=now,
            ))

    return analysis


# ----------------------------------------------------------
# PHOTO UPLOAD — POST /documents/photo
# Mobile: JPEG/PNG → preprocess → analyze pipeline
# ----------------------------------------------------------

@app.post("/documents/photo")
async def photo_upload(
    file: UploadFile = File(...),
    edition: str = "business.shiksha",
    language: str = "de"
):
    import io, uuid as _uuid
    from datetime import datetime, timezone
    from PIL import Image, ImageOps, ImageEnhance
    try:
        import pillow_heif; pillow_heif.register_heif_opener()
    except ImportError:
        pass
    content = await file.read()
    if len(content) < 500:
        raise HTTPException(status_code=422, detail="Bild zu klein oder leer.")

    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
        img = ImageEnhance.Contrast(img).enhance(1.3)
        img = ImageEnhance.Sharpness(img).enhance(1.5)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Bildverarbeitung fehlgeschlagen: {e}")

    raw_text = ""

    # Path A: img2pdf + pdfminer
    try:
        import img2pdf
        from pdfminer.high_level import extract_text as pdf_extract
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=92)
        pdf_bytes = img2pdf.convert(buf.getvalue())
        raw_text = pdf_extract(io.BytesIO(pdf_bytes)) or ""
    except Exception:
        pass

    # Path B: pytesseract fallback
    if not raw_text.strip():
        try:
            import pytesseract
            raw_text = pytesseract.image_to_string(img, lang="deu+eng") or ""
        except Exception:
            pass

    now = datetime.now(timezone.utc)

    if not raw_text.strip():
        doc_id = str(_uuid.uuid4())
        with _doc_engine.begin() as conn:
            conn.execute(_documents.insert().values(
                id=doc_id, edition=edition,
                document_type="unknown", source_type="photo",
                raw_text="", status="analyzed", created_at=now,
            ))
        return {
            "document_id": doc_id, "edition": edition,
            "detected_document_type": "unknown", "source_quality": "photo",
            "extracted_fields": [],
            "entity_suggestion": {"target_type":"customer","suggested_entity_id":None,
                "suggested_entity_name":None,"confidence":0.0,"review_required":True},
            "review_required": True, "status": "analyzed",
            "detection_debug": {"scores":{}, "winning_signals":[],
                "decision_note":"Kein Text erkannt — bitte manuell prüfen.",
                "runner_up":None,"runner_up_score":0},
            "created_at": now.isoformat()
        }

    analysis = build_document_analysis(
        raw_text=raw_text.strip(), edition=edition, source_type="image_scan"
    )
    with _doc_engine.begin() as conn:
        conn.execute(_documents.insert().values(
            id=analysis.document_id, edition=analysis.edition,
            document_type=analysis.detected_document_type,
            source_type="photo",
            raw_text=raw_text.strip()[:10000],
            status="analyzed", created_at=now,
        ))
        for f in analysis.extracted_fields:
            conn.execute(_doc_fields.insert().values(
                id=str(_uuid.uuid4()), document_id=analysis.document_id,
                field_key=f.field_key, field_value=f.field_value,
                confidence=f.confidence, created_at=now,
            ))
    summary = compress(analysis)
    return {**analysis.dict(), "summary": summary.dict()}


from fastapi.responses import FileResponse
import os

@app.get("/foto")
def foto_ui():
    path = "/opt/shiksha/shiksha_foto.html"
    if os.path.exists(path):
        return FileResponse(path, media_type="text/html")
    return {"error": "UI not found"}


# ----------------------------------------------------------
# GET /documents — offene Posten pro Entity
# ----------------------------------------------------------

@app.get("/documents")
async def get_documents(entity_id: str = None, status: str = None):
    """
    Gibt verlinkte Dokumente zurück.
    - entity_id: nur Dokumente dieser Entity (optional)
    - status:    filter auf "analyzed" | "reviewed" (optional)
    """
    try:
        import sqlalchemy as _sa
        engine = _sa.create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")

        with engine.connect() as conn:
            # Base query: documents + links join
            query = """
                SELECT
                    d.id            AS document_id,
                    d.document_type,
                    d.status,
                    d.created_at,
                    dl.entity_id,
                    dl.entity_type,
                    dl.review_status,
                    -- amount: bevorzuge amount_total, dann amount_due
                    (
                        SELECT fc.field_value
                        FROM document_field_candidates fc
                        WHERE fc.document_id = d.id
                          AND fc.field_key IN ('amount_total', 'amount_due')
                          AND fc.confidence >= 0.55
                        ORDER BY fc.confidence DESC
                        LIMIT 1
                    ) AS amount,
                    -- currency
                    (
                        SELECT fc.field_value
                        FROM document_field_candidates fc
                        WHERE fc.document_id = d.id
                          AND fc.field_key = 'currency'
                          AND fc.confidence >= 0.80
                        LIMIT 1
                    ) AS currency,
                    -- due_date > document_date > invoice_date
                    (
                        SELECT fc.field_value
                        FROM document_field_candidates fc
                        WHERE fc.document_id = d.id
                          AND fc.field_key IN ('due_date', 'document_date', 'invoice_date')
                          AND fc.confidence >= 0.50
                        ORDER BY
                            CASE fc.field_key
                                WHEN 'due_date'       THEN 1
                                WHEN 'invoice_date'   THEN 2
                                WHEN 'document_date'  THEN 3
                                ELSE 4
                            END
                        LIMIT 1
                    ) AS primary_date,
                    -- reference
                    (
                        SELECT fc.field_value
                        FROM document_field_candidates fc
                        WHERE fc.document_id = d.id
                          AND fc.field_key IN ('invoice_number', 'case_number', 'reference_number', 'referenced_invoice_number')
                          AND fc.confidence >= 0.60
                        ORDER BY fc.confidence DESC
                        LIMIT 1
                    ) AS reference
                FROM documents d
                LEFT JOIN document_links dl ON dl.document_id = d.id
                WHERE 1=1
            """

            params = {}

            if entity_id:
                query += " AND dl.entity_id = :entity_id"
                params["entity_id"] = entity_id

            if status:
                query += " AND d.status = :status"
                params["status"] = status

            query += " ORDER BY d.created_at DESC"

            rows = conn.execute(_sa.text(query), params).fetchall()

        results = []
        for r in rows:
            amount_str = None
            if r.amount:
                currency = r.currency or "EUR"
                amount_str = f"{r.amount} {currency}"

            results.append({
                "document_id":   r.document_id,
                "document_type": r.document_type,
                "status":        r.status,
                "entity_id":     r.entity_id,
                "entity_type":   r.entity_type,
                "review_status": r.review_status,
                "amount":        amount_str,
                "primary_date":  r.primary_date,
                "reference":     r.reference,
                "created_at":    r.created_at.isoformat() if r.created_at else None,
            })

        return {
            "count":     len(results),
            "entity_id": entity_id,
            "documents": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------
# ACCOUNTING MODULE — Stufe 1
# ----------------------------------------------------------

from accounting_models import LedgerFromDocumentRequest, PaymentConfirmRequest
from accounting_module import (
    create_entry_from_document,
    get_open_items,
    confirm_payment,
    get_monthly_summary,
)

@app.post("/accounting/entries")
async def accounting_create_entry(request: LedgerFromDocumentRequest):
    try:
        return create_entry_from_document(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/accounting/open")
async def accounting_open_items(entity_id: str = None, entry_type: str = None):
    return get_open_items(entity_id=entity_id, entry_type=entry_type)

@app.get("/accounting/entries")
async def accounting_get_entries(entity_id: str = None, status: str = None):
    import sqlalchemy as _sa
    engine = _sa.create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")
    query = "SELECT * FROM ledger_entries WHERE 1=1"
    params = {}
    if entity_id:
        query += " AND entity_id = :entity_id"
        params["entity_id"] = entity_id
    if status:
        query += " AND status = :status"
        params["status"] = status
    query += " ORDER BY created_at DESC"
    with engine.connect() as conn:
        rows = conn.execute(_sa.text(query), params).fetchall()
    return {"count": len(rows), "entries": [dict(r._mapping) for r in rows]}

@app.post("/accounting/entries/{entry_id}/pay")
async def accounting_confirm_payment(entry_id: str, request: PaymentConfirmRequest):
    request.ledger_entry_id = entry_id
    try:
        return confirm_payment(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.get("/accounting/summary/{year}/{month}")
async def accounting_monthly_summary(year: int, month: int):
    return get_monthly_summary(year=year, month=month)


@app.get("/accounting/export")
async def accounting_export(year: int, month: int, entity_id: str = None):
    """CSV-Export für Steuerberater — Jahr/Monat, optional nach Entity."""
    import csv, io
    from fastapi.responses import StreamingResponse
    import sqlalchemy as _sa

    engine = _sa.create_engine("postgresql://shiksha:shiksha2026@localhost/shiksha")

    query = """
        SELECT
            le.id, le.entry_type, le.amount, le.currency, le.tax_amount,
            le.due_date, le.status, le.note, le.created_at,
            c.name AS entity_name,
            d.document_type
        FROM ledger_entries le
        LEFT JOIN customers c ON c.id = le.entity_id
        LEFT JOIN documents d ON d.id = le.document_id
        WHERE EXTRACT(YEAR FROM le.created_at) = :year
          AND EXTRACT(MONTH FROM le.created_at) = :month
    """
    params = {"year": year, "month": month}

    if entity_id:
        query += " AND le.entity_id = :entity_id"
        params["entity_id"] = entity_id

    query += " ORDER BY le.created_at ASC"

    with engine.connect() as conn:
        rows = conn.execute(_sa.text(query), params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")

    # Header
    writer.writerow([
        "ID", "Typ", "Belegtyp", "Entity", "Betrag", "Währung",
        "Steuer", "Fälligkeit", "Status", "Notiz", "Erstellt"
    ])

    for r in rows:
        writer.writerow([
            r.id,
            r.entry_type,
            r.document_type or "",
            r.entity_name or "",
            str(r.amount).replace(".", ",") if r.amount else "",
            r.currency or "EUR",
            str(r.tax_amount).replace(".", ",") if r.tax_amount else "",
            r.due_date or "",
            r.status or "",
            r.note or "",
            r.created_at.strftime("%d.%m.%Y") if r.created_at else "",
        ])

    output.seek(0)
    filename = f"shiksha_export_{year}_{month:02d}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ----------------------------------------------------------
# CALENDAR MODULE — Stufe 1
# ----------------------------------------------------------

from calendar_models import CalendarEventCreate, EventOutcomeRequest
from calendar_module import (
    create_event,
    get_events,
    get_upcoming,
    mark_event_done,
    set_outcome,
    sync_deadlines_from_ledger,
)

@app.post("/calendar/events")
async def calendar_create_event(request: CalendarEventCreate):
    return create_event(request)

@app.get("/calendar/events")
async def calendar_get_events(entity_id: str = None, event_type: str = None, edition: str = None, status: str = None):
    return get_events(entity_id=entity_id, event_type=event_type, edition=edition, status=status)

@app.get("/calendar/upcoming")
async def calendar_upcoming(edition: str = None, entity_id: str = None, days: int = 30):
    return get_upcoming(edition=edition, entity_id=entity_id, days=days)

@app.post("/calendar/events/{event_id}/done")
async def calendar_mark_done(event_id: str):
    try:
        return mark_event_done(event_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/calendar/events/{event_id}/outcome")
async def calendar_set_outcome(event_id: str, request: EventOutcomeRequest):
    try:
        return set_outcome(event_id, request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/calendar/sync/deadlines")
async def calendar_sync_deadlines(edition: str = "business.shiksha"):
    return sync_deadlines_from_ledger(edition=edition)

app.include_router(accounting_router)
# world_router MUSS vor kita_router stehen — sonst fängt der dortige
# /m/{slug}-Catch-all spezifische Routes wie /m/shiksha ab.
app.include_router(world_router)
app.include_router(kita_router)
app.include_router(identity_router)
