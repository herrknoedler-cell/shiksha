"""SHIKSHA · Accounting Router V3 · Kategorisierung + Match-Engine"""
import json, uuid
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.responses import HTMLResponse
import sqlalchemy as sa
from accounting_models import ACCOUNTING_MODULE_PROFILE, AccountingInvoice, BankTransaction
from accounting_orchestrator import score_match, THRESHOLD_HIGH_CONFIDENCE, THRESHOLD_MEDIUM_CONFIDENCE
from bank_statement_parser import parse_csv, parse_camt053, parse_mt940, detect_duplicates
from database import engine

accounting_router = APIRouter(prefix="/accounting", tags=["accounting"])

def _read(filename):
    with open(f"/opt/shiksha/ui/{filename}") as f: return f.read()

@accounting_router.get("/profile")
async def accounting_profile(): return ACCOUNTING_MODULE_PROFILE

@accounting_router.get("/health")
async def accounting_health():
    try:
        with engine.connect() as conn: conn.execute(sa.text("SELECT 1"))
        return {"status":"alive","module":"accounting","version":"3.0","db_connected":True}
    except Exception:
        return {"status":"degraded","module":"accounting","version":"3.0","db_connected":False}

def _parse_amount(val):
    """Parst Beträge tolerant: '36,80', '1.234,56', '36.80', 36.80, None."""
    if val is None: return None
    if isinstance(val, (int, float)): return float(val)
    s = str(val).strip().replace('€','').replace('EUR','').strip()
    if '.' in s and ',' in s:  # 1.234,56 deutsch
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:              # 36,80 deutsch
        s = s.replace(',', '.')
    try: return float(s)
    except (ValueError, TypeError): return None


def _load_invoices(conn, direction=None, status=None, limit=500):
    sql = "SELECT id,document_type,direction,accounting_status,outstanding_amount,paid_amount,reminder_level,raw_text,created_at FROM documents WHERE document_type IN ('invoice','dunning')"
    params = {}
    if direction: sql += " AND direction = :direction"; params["direction"] = direction
    if status: sql += " AND accounting_status = :status"; params["status"] = status
    sql += " ORDER BY created_at DESC LIMIT :limit"; params["limit"] = limit
    rows = conn.execute(sa.text(sql), params).fetchall()
    invoices = []
    for r in rows:
        fields = {}
        try:
            fields = json.loads(r.raw_text) if r.raw_text else {}
            if not isinstance(fields, dict): fields = {}
        except Exception: fields = {}
        if not fields.get("customer_name") and r.raw_text:
            try:
                fc = conn.execute(sa.text("SELECT field_key, field_value, confidence FROM document_field_candidates WHERE document_id=:id ORDER BY confidence DESC"), {"id": r.id}).fetchall()
                for f in fc:
                    if f.field_key and f.field_value and f.field_key not in fields:
                        fields[f.field_key] = f.field_value
            except Exception as e:
                # Bei DB-Fehler: Connection rollback um aborted transaction state zu resetten
                try: conn.rollback()
                except Exception: pass
            if not fields.get("customer_name"):
                fields["raw_preview"] = (r.raw_text or "")[:120]
        invoices.append({
            "id": r.id, "document_type": r.document_type,
            "direction": r.direction or "incoming",
            "accounting_status": r.accounting_status or "open",
            "outstanding_amount": float(r.outstanding_amount or 0),
            "paid_amount": float(r.paid_amount or 0),
            "reminder_level": r.reminder_level or 0,
            "customer_name": fields.get("customer_name") or fields.get("supplier_name") or fields.get("authority_name"),
            "invoice_number": fields.get("invoice_number") or fields.get("case_number"),
            "due_date": fields.get("due_date"),
            "amount_total": _parse_amount(fields.get("amount_total")),
            "iban": fields.get("iban"), "raw_preview": fields.get("raw_preview"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return invoices

@accounting_router.get("/invoices")
def list_invoices(direction: Optional[str]=None, status: Optional[str]=None, limit: int=500):
    with engine.connect() as conn:
        invoices = _load_invoices(conn, direction, status, limit)
    return {"count": len(invoices), "invoices": invoices}

@accounting_router.get("/transactions")
def list_transactions(category: Optional[str]=None, status: Optional[str]=None, limit: int=1000):
    with engine.connect() as conn:
        sql = "SELECT id,value_date,booking_date,amount,currency,counterparty_name,counterparty_iban,purpose,status,transaction_type,bank_reference,category,notes FROM bank_transactions"
        wheres, params = [], {}
        if category: wheres.append("category=:category"); params["category"]=category
        if status: wheres.append("status=:status"); params["status"]=status
        if wheres: sql += " WHERE " + " AND ".join(wheres)
        sql += " ORDER BY value_date DESC, id DESC LIMIT :limit"; params["limit"]=limit
        rows = conn.execute(sa.text(sql), params).fetchall()
    txs = [{"id":r.id,"value_date":r.value_date.isoformat() if r.value_date else None,
            "booking_date":r.booking_date.isoformat() if r.booking_date else None,
            "amount":float(r.amount),"currency":r.currency,
            "counterparty_name":r.counterparty_name,"counterparty_iban":r.counterparty_iban,
            "purpose":r.purpose,"status":r.status,"transaction_type":r.transaction_type,
            "bank_reference":r.bank_reference,
            "category":r.category or "unclassified","notes":r.notes} for r in rows]
    return {"count": len(txs), "transactions": txs}

@accounting_router.patch("/transactions/{tx_id}")
async def patch_transaction(tx_id: str, payload: dict = Body(...)):
    allowed = {"category", "notes"}
    updates = {k:v for k,v in payload.items() if k in allowed}
    if not updates: raise HTTPException(400, "Keine erlaubten Felder (category, notes)")
    set_clause = ", ".join([f"{k}=:{k}" for k in updates])
    updates["id"] = tx_id
    with engine.begin() as conn:
        result = conn.execute(sa.text(f"UPDATE bank_transactions SET {set_clause} WHERE id=:id"), updates)
        if result.rowcount == 0: raise HTTPException(404, f"TX {tx_id} nicht gefunden")
    return {"id": tx_id, "updated": [k for k in updates if k!="id"]}

@accounting_router.post("/statements/upload")
async def upload_statement(file: UploadFile = File(...), iban_account: str = Form(""), file_format: str = Form("csv")):
    content_bytes = await file.read()
    if file_format == "csv":
        transactions, statement = parse_csv(content_bytes, iban_account=None)
        if statement.iban_account and statement.iban_account != "UNKNOWN":
            iban_account = statement.iban_account
            for tx in transactions: tx.iban_account = iban_account
    elif file_format == "camt053":
        transactions, statement = parse_camt053(content_bytes, iban_account)
    elif file_format == "mt940":
        transactions, statement = parse_mt940(content_bytes, iban_account)
    else:
        raise HTTPException(400, f"Unbekanntes Format: {file_format}")
    statement.file_name = file.filename or "upload"
    with engine.connect() as conn:
        existing = conn.execute(sa.text("SELECT bank_reference FROM bank_transactions WHERE iban_account=:iban AND bank_reference IS NOT NULL"), {"iban": iban_account}).fetchall()
    existing_refs = {r.bank_reference for r in existing}
    new_only, duplicates = detect_duplicates(transactions, existing_refs)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO statement_imports (id,file_name,file_format,bank_profile,iban_account,period_from,period_to,transactions_count,new_count,duplicate_count,parse_errors,file_hash) VALUES (:id,:name,:fmt,:prof,:iban,:pf,:pt,:tot,:new,:dup,:err,:hash)"),
            {"id":statement.id,"name":statement.file_name,"fmt":file_format,"prof":statement.bank_profile,"iban":iban_account,"pf":statement.period_from,"pt":statement.period_to,"tot":statement.transactions_count,"new":len(new_only),"dup":len(duplicates),"err":statement.parse_errors,"hash":statement.file_hash})
        for tx in new_only:
            conn.execute(sa.text("INSERT INTO bank_transactions (id,statement_import_id,iban_account,booking_date,value_date,amount,currency,counterparty_name,counterparty_iban,counterparty_bic,purpose,bank_reference,transaction_type,status,category,raw_record) VALUES (:id,:sid,:iban,:bd,:vd,:amt,:cur,:cn,:ci,:cb,:pur,:ref,:type,'unmatched','unclassified',:raw)"),
                {"id":tx.id,"sid":statement.id,"iban":tx.iban_account,"bd":tx.booking_date,"vd":tx.value_date,"amt":tx.amount,"cur":tx.currency,"cn":tx.counterparty_name,"ci":tx.counterparty_iban,"cb":tx.counterparty_bic,"pur":tx.purpose,"ref":tx.bank_reference,"type":tx.transaction_type,"raw":json.dumps(tx.raw_record) if tx.raw_record else None})
    return {"status":"imported","import_id":statement.id,"file_name":statement.file_name,"bank_profile":statement.bank_profile,"period_from":statement.period_from.isoformat() if statement.period_from else None,"period_to":statement.period_to.isoformat() if statement.period_to else None,"total_in_file":statement.transactions_count,"imported_new":len(new_only),"skipped_duplicates":len(duplicates),"parse_errors":statement.parse_errors}

@accounting_router.post("/invoices/manual")
async def create_invoice_manual(customer_name: str = Form(...), direction: str = Form("incoming"), document_type: str = Form("invoice"), invoice_number: Optional[str] = Form(None), invoice_date: Optional[str] = Form(None), due_date: Optional[str] = Form(None), amount_total: float = Form(...), currency: str = Form("EUR"), iban: Optional[str] = Form(None), notes: Optional[str] = Form(None)):
    invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
    fields = {"customer_name":customer_name,"invoice_number":invoice_number,"invoice_date":invoice_date,"due_date":due_date,"amount_total":amount_total,"currency":currency,"iban":iban,"notes":notes}
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO documents (id,document_type,direction,accounting_status,outstanding_amount,paid_amount,raw_text,created_at) VALUES (:id,:dt,:dir,'open',:amount,0,:raw,NOW())"),
            {"id":invoice_id,"dt":document_type,"dir":direction,"amount":amount_total,"raw":json.dumps(fields, ensure_ascii=False)})
    return {"id":invoice_id,"status":"created","fields":fields}

def _build_invoice_obj(d):
    if not d.get("amount_total"): return None
    try:
        return AccountingInvoice(id=d["id"], document_type=d["document_type"], direction=d["direction"],
            customer_name=d.get("customer_name"), invoice_number=d.get("invoice_number"),
            invoice_date=date.fromisoformat(d["due_date"]) if d.get("due_date") else None,
            due_date=date.fromisoformat(d["due_date"]) if d.get("due_date") else None,
            amount_total=_parse_amount(d.get("amount_total")) or 0,
            outstanding_amount=(_parse_amount(d.get("amount_total")) or 0) - (d.get("paid_amount") or 0),
            iban=d.get("iban"), accounting_status=d["accounting_status"])
    except Exception: return None

def _build_tx_obj(r):
    return BankTransaction(id=r.id, iban_account=r.iban_account, booking_date=r.booking_date,
        value_date=r.value_date, amount=float(r.amount), currency=r.currency,
        counterparty_name=r.counterparty_name, counterparty_iban=r.counterparty_iban,
        purpose=r.purpose, bank_reference=r.bank_reference, status=r.status)

@accounting_router.get("/match-proposals")
def list_match_proposals(min_score: int = 40, limit: int = 100):
    with engine.connect() as conn:
        tx_rows = conn.execute(sa.text("SELECT id,iban_account,booking_date,value_date,amount,currency,counterparty_name,counterparty_iban,purpose,bank_reference,status FROM bank_transactions WHERE status='unmatched' AND (category IS NULL OR category NOT IN ('private','ignore','shareholder_loan')) ORDER BY value_date DESC")).fetchall()
        invoices = _load_invoices(conn, status="open")
    invoice_objs = [_build_invoice_obj(i) for i in invoices]
    invoice_objs = [i for i in invoice_objs if i is not None]
    proposals = []
    for r in tx_rows:
        tx = _build_tx_obj(r)
        for inv in invoice_objs:
            if inv.direction == "incoming" and tx.amount > 0: continue
            if inv.direction == "outgoing" and tx.amount < 0: continue
            breakdown = score_match(inv, tx)
            if breakdown.total < min_score: continue
            tier = "high" if breakdown.total >= THRESHOLD_HIGH_CONFIDENCE else "mid" if breakdown.total >= THRESHOLD_MEDIUM_CONFIDENCE else "low"
            proposals.append({"tx_id":tx.id,"tx_value_date":tx.value_date.isoformat() if tx.value_date else None,
                "tx_amount":tx.amount,"tx_counterparty":tx.counterparty_name,
                "tx_purpose":(tx.purpose or "")[:80],"invoice_id":inv.id,
                "invoice_customer":inv.customer_name,"invoice_number":inv.invoice_number,
                "invoice_amount":inv.amount_total,"invoice_iban":inv.iban,
                "score":breakdown.total,"tier":tier,"score_breakdown":breakdown.model_dump()})
    proposals.sort(key=lambda p: p["score"], reverse=True)
    return {"count": len(proposals), "proposals": proposals[:limit]}

@accounting_router.post("/match-proposals/accept")
async def accept_match(payload: dict = Body(...)):
    tx_id = payload.get("tx_id"); invoice_id = payload.get("invoice_id")
    matched_amount = payload.get("matched_amount")
    confirmed_by = payload.get("confirmed_by", "operator")
    if not tx_id or not invoice_id: raise HTTPException(400, "tx_id und invoice_id erforderlich")
    match_id = f"pm_{uuid.uuid4().hex[:12]}"
    with engine.begin() as conn:
        tx = conn.execute(sa.text("SELECT amount FROM bank_transactions WHERE id=:id"), {"id":tx_id}).fetchone()
        if not tx: raise HTTPException(404, f"Bank-Buchung {tx_id} nicht gefunden")
        if matched_amount is None: matched_amount = abs(float(tx.amount))
        conn.execute(sa.text("INSERT INTO payment_matches (id,bank_transaction_id,document_id,match_type,matched_amount,confirmed_by,confirmed_at) VALUES (:id,:tx,:doc,'full',:amt,:by,NOW())"),
            {"id":match_id,"tx":tx_id,"doc":invoice_id,"amt":matched_amount,"by":confirmed_by})
        conn.execute(sa.text("UPDATE bank_transactions SET status='matched', category='business' WHERE id=:id"), {"id":tx_id})
        conn.execute(sa.text("UPDATE documents SET accounting_status='paid', paid_amount=COALESCE(paid_amount,0)+:amt WHERE id=:id"), {"id":invoice_id,"amt":matched_amount})
    return {"match_id":match_id,"tx_id":tx_id,"invoice_id":invoice_id,"matched_amount":matched_amount,"status":"confirmed"}


# Konten ----------------------------------------------------------------

@accounting_router.get("/accounts")
def list_accounts(active_only: bool = True):
    """Standard-Kontenplan."""
    with engine.connect() as conn:
        sql = "SELECT id,account_number,account_name,account_type,vat_rate,description,is_active FROM chart_of_accounts"
        if active_only:
            sql += " WHERE is_active=TRUE"
        sql += " ORDER BY account_number"
        rows = conn.execute(sa.text(sql)).fetchall()
    accounts = [{"id":r.id,"number":r.account_number,"name":r.account_name,"type":r.account_type,
                 "vat_rate":float(r.vat_rate) if r.vat_rate else None,"description":r.description,
                 "active":r.is_active} for r in rows]
    return {"count": len(accounts), "accounts": accounts}


@accounting_router.patch("/transactions/{tx_id}/account")
async def patch_transaction_account(tx_id: str, payload: dict = Body(...)):
    """Setzt Gegenkonto einer Bank-Buchung."""
    account_id = payload.get("account_id")
    with engine.begin() as conn:
        result = conn.execute(sa.text("UPDATE bank_transactions SET account_id=:acc WHERE id=:id"),
                              {"acc": account_id, "id": tx_id})
        if result.rowcount == 0:
            raise HTTPException(404, "TX nicht gefunden")
    return {"id": tx_id, "account_id": account_id}


@accounting_router.patch("/invoices/{inv_id}/account")
async def patch_invoice_account(inv_id: str, payload: dict = Body(...)):
    """Setzt Konto einer Rechnung."""
    account_id = payload.get("account_id")
    with engine.begin() as conn:
        result = conn.execute(sa.text("UPDATE documents SET account_id=:acc WHERE id=:id"),
                              {"acc": account_id, "id": inv_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Rechnung nicht gefunden")
    return {"id": inv_id, "account_id": account_id}


# PDF-Bulk-Upload ------------------------------------------------------

@accounting_router.post("/invoices/bulk-upload")
async def bulk_upload_pdfs(files: list[UploadFile] = File(...)):
    """Mehrere PDFs auf einmal hochladen, jeweils durch document.module."""
    import httpx
    results = []
    for file in files:
        content = await file.read()
        try:
            # Forward an V4-document.module
            async with httpx.AsyncClient(timeout=60.0) as client:
                r = await client.post(
                    "http://localhost:8000/documents/upload",
                    files={"file": (file.filename, content, file.content_type or "application/pdf")}
                )
                if r.status_code == 200:
                    results.append({"filename": file.filename, "status": "ok", "response": r.json()})
                else:
                    results.append({"filename": file.filename, "status": "error",
                                    "code": r.status_code, "detail": r.text[:200]})
        except Exception as e:
            results.append({"filename": file.filename, "status": "error", "detail": str(e)[:200]})
    return {"total": len(files), "results": results}

@accounting_router.get("/upload", response_class=HTMLResponse)
async def upload_ui():
    with open("/opt/shiksha/shiksha_upload.html") as f: return f.read()
@accounting_router.get("/cockpit", response_class=HTMLResponse)
async def cockpit_ui():
    with open("/opt/shiksha/shiksha_cockpit.html") as f: return f.read()
@accounting_router.get("/ui/schule/operator", response_class=HTMLResponse)
async def ui_so(): return _read("schule_operator.html")
@accounting_router.get("/ui/schule/dashboard", response_class=HTMLResponse)
async def ui_sd(): return _read("schule_dashboard.html")
@accounting_router.get("/ui/schule/teilnehmer", response_class=HTMLResponse)
async def ui_st(): return _read("schule_teilnehmer.html")
@accounting_router.get("/ui/camping/operator", response_class=HTMLResponse)
async def ui_co(): return _read("camping_operator.html")
@accounting_router.get("/ui/camping/dashboard", response_class=HTMLResponse)
async def ui_cd(): return _read("camping_dashboard.html")
@accounting_router.get("/ui/camping/gaeste", response_class=HTMLResponse)
async def ui_cg(): return _read("camping_gaeste.html")
@accounting_router.get("/ui/safeguarding", response_class=HTMLResponse)
async def ui_sg(): return _read("safeguarding_dashboard.html")
@accounting_router.get("/ui/accounting", response_class=HTMLResponse)
async def ui_ac(): return _read("accounting_dashboard.html")
@accounting_router.get("/ui/pilot-demo", response_class=HTMLResponse)
async def ui_pd(): return _read("pilot_demo.html")


# --- UI V4 Dashboard ---
@accounting_router.get("/ui/accounting/v4", include_in_schema=False)
async def ui_accounting_v4():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/accounting_dashboard_v4.html", media_type="text/html")


# === RE-EXTRACT (added 28.04.2026) ============================
import uuid as _re_uuid
from extractor_extensions import re_extract_document as _re_extract_doc

@accounting_router.post("/invoices/re-extract")
async def re_extract_invoices(limit: int = 1000):
    processed = 0; added = 0; replaced = 0
    with engine.begin() as conn:
        docs = conn.execute(sa.text("""
            SELECT id, raw_text, document_type FROM documents
            WHERE raw_text IS NOT NULL AND LENGTH(raw_text) > 50
            ORDER BY created_at DESC LIMIT :lim
        """), {"lim": limit}).fetchall()
        for doc in docs:
            doc_id, raw_text, doc_type = doc[0], doc[1], doc[2] or "invoice"
            try:
                new_cands = _re_extract_doc(raw_text, doc_type)
            except Exception as e:
                print(f"[re-extract] {doc_id}: {e}"); continue
            existing = conn.execute(sa.text("""
                SELECT id, field_key, confidence FROM document_field_candidates
                WHERE document_id = :did
            """), {"did": doc_id}).fetchall()
            existing_map = {r[1]: (r[0], r[2]) for r in existing}
            for c in new_cands:
                key, val, conf = c["field_key"], c["field_value"], c["confidence"]
                if key in existing_map:
                    old_id, old_conf = existing_map[key]
                    if conf > (old_conf or 0) + 0.05:
                        conn.execute(sa.text("""UPDATE document_field_candidates
                            SET field_value=:v, confidence=:c WHERE id=:id"""),
                            {"v": val, "c": conf, "id": old_id})
                        replaced += 1
                else:
                    conn.execute(sa.text("""INSERT INTO document_field_candidates
                        (id, document_id, field_key, field_value, confidence, created_at)
                        VALUES (:id, :did, :k, :v, :c, NOW())"""),
                        {"id": str(_re_uuid.uuid4()), "did": doc_id, "k": key, "v": val, "c": conf})
                    added += 1
            processed += 1
    return {"processed": processed, "added": added, "replaced": replaced}


# === INVOICES V2 (joined field_candidates) ====================
@accounting_router.get("/invoices/v2")
async def list_invoices_v2(limit: int = 500, direction: str = None):
    sql = """
    SELECT d.id, d.document_type, d.created_at, d.accounting_status,
           d.direction, d.account_id, d.paid_amount,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='invoice_number' ORDER BY confidence DESC LIMIT 1) AS invoice_number,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('invoice_date','document_date') ORDER BY CASE field_key WHEN 'invoice_date' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS invoice_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('due_date_strict','due_date') ORDER BY CASE field_key WHEN 'due_date_strict' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS due_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='amount_total' ORDER BY confidence DESC LIMIT 1) AS amount_total_text,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='currency' ORDER BY confidence DESC LIMIT 1) AS currency,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='vat_amount' ORDER BY confidence DESC LIMIT 1) AS vat_amount,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='vat_rate' ORDER BY confidence DESC LIMIT 1) AS vat_rate,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='iban' ORDER BY confidence DESC LIMIT 1) AS iban,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='supplier_name' ORDER BY confidence DESC LIMIT 1) AS supplier_name,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='customer_name' ORDER BY confidence DESC LIMIT 1) AS customer_name
    FROM documents d
    WHERE d.document_type IN ('invoice','dunning','reminder')
    """
    params = {"lim": limit}
    if direction:
        sql += " AND d.direction = :dir"
        params["dir"] = direction
    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    def _parse_amount(s):
        if not s: return 0.0
        s = str(s).strip().replace(' ','').replace('€','').replace('EUR','')
        if ',' in s and '.' in s: s = s.replace('.','').replace(',','.')
        elif ',' in s: s = s.replace(',','.')
        try: return float(s)
        except (ValueError, TypeError): return 0.0

    OWN = ("lunchbox","lichtquelle","inselwellen","allweglehen","knödler","knodler")
    invoices = []
    with engine.connect() as conn:
        for r in conn.execute(sa.text(sql), params).fetchall():
            (doc_id, doc_type, created_at, acc_status, direction_raw, account_id,
             paid_amount, inv_num, inv_date, due_date, amount_text, currency,
             vat_amount, vat_rate, iban, supplier_name, customer_name) = r
            cust_lower = (customer_name or "").lower()
            direction_eff = direction_raw or ("incoming" if any(n in cust_lower for n in OWN) else "outgoing")
            partner = (supplier_name or customer_name or "—") if direction_eff == "incoming" else (customer_name or "—")
            amount_val = _parse_amount(amount_text)
            paid_val = float(paid_amount or 0)
            outstanding = max(0.0, amount_val - paid_val) if amount_val else 0.0
            invoices.append({
                "id": doc_id, "document_type": doc_type, "direction": direction_eff,
                "invoice_number": inv_num, "invoice_date": inv_date, "due_date": due_date,
                "amount_total": amount_val, "outstanding_amount": outstanding,
                "currency": currency or "EUR",
                "vat_amount": _parse_amount(vat_amount) if vat_amount else None,
                "vat_rate": vat_rate, "iban": iban,
                "supplier_name": supplier_name, "customer_name": customer_name,
                "partner": partner,
                "accounting_status": acc_status or "open",
                "account_id": account_id,
                "created_at": created_at.isoformat() if created_at else None,
            })
    return {"count": len(invoices), "invoices": invoices}


@accounting_router.patch("/transactions/{tx_id}/categorize")
async def categorize_transaction(tx_id: str, payload: dict = Body(...)):
    """Setzt category einer Bank-Buchung (private/business/shareholder_loan/ignore)."""
    category = payload.get("category")
    valid = {None, "", "business", "private", "shareholder_loan", "ignore"}
    if category not in valid:
        raise HTTPException(400, f"Ungültige Kategorie: {category}")
    with engine.begin() as conn:
        result = conn.execute(
            sa.text("UPDATE bank_transactions SET category=:c WHERE id=:id"),
            {"c": category or None, "id": tx_id}
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Transaction nicht gefunden")
    return {"id": tx_id, "category": category}
"""
SHIKSHA · Phase 2 Endpoints — Lieferanten-Stammdaten
Wird ans Ende von /opt/shiksha/accounting_router.py angehängt.
"""

# === ANHÄNGEN AN /opt/shiksha/accounting_router.py ====================

import re as _re_p2

def _normalize_name(name: str) -> str:
    if not name: return ""
    return _re_p2.sub(r'[^a-z0-9 ]', '', name.lower()).strip()


@accounting_router.get("/suppliers")
async def list_suppliers(limit: int = 500):
    """Alle Lieferanten mit Stammdaten + Statistik."""
    with engine.connect() as conn:
        rows = conn.execute(sa.text("""
            SELECT s.id, s.name, s.iban, s.uid_number, s.default_account_id,
                   s.contact_email, s.contact_phone, s.address, s.notes,
                   s.transaction_count, s.invoice_count,
                   a.account_number AS account_number, a.account_name AS account_name
            FROM suppliers s
            LEFT JOIN chart_of_accounts a ON a.id = s.default_account_id
            ORDER BY (s.transaction_count + s.invoice_count) DESC, s.name ASC
            LIMIT :lim
        """), {"lim": limit}).fetchall()

    suppliers = []
    for r in rows:
        suppliers.append({
            "id": r[0],
            "name": r[1],
            "iban": r[2],
            "uid_number": r[3],
            "default_account_id": r[4],
            "contact_email": r[5],
            "contact_phone": r[6],
            "address": r[7],
            "notes": r[8],
            "transaction_count": r[9] or 0,
            "invoice_count": r[10] or 0,
            "account_label": f"{r[11]} {r[12]}" if r[11] else None,
        })
    return {"count": len(suppliers), "suppliers": suppliers}


@accounting_router.post("/suppliers")
async def create_supplier(payload: dict = Body(...)):
    """Manuell einen Lieferanten anlegen."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name ist Pflicht")
    sid = "sup_" + _re_p2.sub(r'[^a-z0-9]', '_', name.lower())[:30]
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO suppliers (id, name, normalized_name, iban, uid_number,
                                   default_account_id, contact_email, contact_phone,
                                   address, notes)
            VALUES (:id, :n, :nn, :iban, :uid, :acc, :em, :ph, :ad, :no)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": sid, "n": name, "nn": _normalize_name(name),
            "iban": payload.get("iban"), "uid": payload.get("uid_number"),
            "acc": payload.get("default_account_id"),
            "em": payload.get("contact_email"), "ph": payload.get("contact_phone"),
            "ad": payload.get("address"), "no": payload.get("notes"),
        })
    return {"id": sid, "name": name}


@accounting_router.patch("/suppliers/{sup_id}")
async def update_supplier(sup_id: str, payload: dict = Body(...)):
    """Stammdaten eines Lieferanten ergänzen/ändern."""
    fields = {}
    for key in ("name", "iban", "uid_number", "default_account_id",
                "contact_email", "contact_phone", "address", "notes"):
        if key in payload:
            fields[key] = payload[key]
    if not fields:
        raise HTTPException(400, "keine Felder im Payload")
    if "name" in fields:
        fields["normalized_name"] = _normalize_name(fields["name"])
    fields["updated_at"] = "NOW()"

    set_parts = []
    params = {"id": sup_id}
    for k, v in fields.items():
        if k == "updated_at":
            set_parts.append("updated_at = NOW()")
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v
    sql = f"UPDATE suppliers SET {', '.join(set_parts)} WHERE id = :id"
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), params)
        if result.rowcount == 0:
            raise HTTPException(404, "Lieferant nicht gefunden")
    return {"id": sup_id, "updated": list(fields.keys())}


@accounting_router.delete("/suppliers/{sup_id}")
async def delete_supplier(sup_id: str):
    with engine.begin() as conn:
        # Erst FK-Verweise lösen
        conn.execute(sa.text("UPDATE documents SET supplier_id=NULL WHERE supplier_id=:id"), {"id": sup_id})
        conn.execute(sa.text("UPDATE bank_transactions SET supplier_id=NULL WHERE supplier_id=:id"), {"id": sup_id})
        result = conn.execute(sa.text("DELETE FROM suppliers WHERE id=:id"), {"id": sup_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Lieferant nicht gefunden")
    return {"id": sup_id, "deleted": True}


@accounting_router.post("/suppliers/auto-match")
async def auto_match_suppliers():
    """
    Match bestehende Rechnungen + Bank-Buchungen gegen suppliers via:
    1. IBAN exact match
    2. Counterparty-Name match (für Bank-Buchungen)
    3. Customer/Supplier name fuzzy match (für Rechnungen)
    """
    matched_invoices = 0
    matched_transactions = 0

    with engine.begin() as conn:
        # Rechnungen via IBAN
        result = conn.execute(sa.text("""
            UPDATE documents d
            SET supplier_id = s.id
            FROM document_field_candidates c, suppliers s
            WHERE c.document_id = d.id
              AND c.field_key = 'iban'
              AND c.field_value = s.iban
              AND d.supplier_id IS NULL
        """))
        matched_invoices += result.rowcount

        # Rechnungen via Name (fuzzy: extrahierter customer_name oder supplier_name
        # könnte den echten Lieferanten-Namen enthalten)
        result = conn.execute(sa.text("""
            UPDATE documents d
            SET supplier_id = s.id
            FROM document_field_candidates c, suppliers s
            WHERE c.document_id = d.id
              AND c.field_key IN ('supplier_name','customer_name')
              AND LOWER(c.field_value) LIKE '%' || s.normalized_name || '%'
              AND LENGTH(s.normalized_name) >= 5
              AND d.supplier_id IS NULL
        """))
        matched_invoices += result.rowcount

        # Bank-Buchungen via Counterparty-Name
        result = conn.execute(sa.text("""
            UPDATE bank_transactions bt
            SET supplier_id = s.id
            FROM suppliers s
            WHERE LOWER(bt.counterparty_name) = LOWER(s.name)
              AND bt.supplier_id IS NULL
        """))
        matched_transactions += result.rowcount

        # Counter aktualisieren
        conn.execute(sa.text("""
            UPDATE suppliers s SET
                invoice_count = (SELECT COUNT(*) FROM documents WHERE supplier_id = s.id),
                transaction_count = (SELECT COUNT(*) FROM bank_transactions WHERE supplier_id = s.id)
        """))

    return {
        "matched_invoices": matched_invoices,
        "matched_transactions": matched_transactions,
    }


@accounting_router.patch("/invoices/{inv_id}/supplier")
async def assign_supplier_to_invoice(inv_id: str, payload: dict = Body(...)):
    """Manuell einen Lieferant einer Rechnung zuordnen."""
    sup_id = payload.get("supplier_id")
    with engine.begin() as conn:
        result = conn.execute(
            sa.text("UPDATE documents SET supplier_id=:s WHERE id=:id"),
            {"s": sup_id, "id": inv_id}
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Rechnung nicht gefunden")
        # Counter
        if sup_id:
            conn.execute(sa.text(
                "UPDATE suppliers SET invoice_count = (SELECT COUNT(*) FROM documents WHERE supplier_id=:s) WHERE id=:s"
            ), {"s": sup_id})
    return {"invoice_id": inv_id, "supplier_id": sup_id}


# === V2 Endpoint überschreiben — supplier-Lookup ergänzen =====
# Wir nutzen einen v3-Endpoint, damit v2 als Fallback bleibt.

@accounting_router.get("/invoices/v3")
async def list_invoices_v3(limit: int = 500, direction: str = None):
    """V3 = V2 + Lieferanten-Lookup."""
    sql = """
    SELECT d.id, d.document_type, d.created_at, d.accounting_status,
           d.direction, d.account_id, d.paid_amount, d.supplier_id,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='invoice_number' ORDER BY confidence DESC LIMIT 1) AS invoice_number,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('invoice_date','document_date') ORDER BY CASE field_key WHEN 'invoice_date' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS invoice_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('due_date_strict','due_date') ORDER BY CASE field_key WHEN 'due_date_strict' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS due_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='amount_total' ORDER BY confidence DESC LIMIT 1) AS amount_total_text,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='currency' ORDER BY confidence DESC LIMIT 1) AS currency,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='vat_amount' ORDER BY confidence DESC LIMIT 1) AS vat_amount,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='vat_rate' ORDER BY confidence DESC LIMIT 1) AS vat_rate,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='iban' ORDER BY confidence DESC LIMIT 1) AS iban,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='supplier_name' ORDER BY confidence DESC LIMIT 1) AS supplier_name_extr,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='customer_name' ORDER BY confidence DESC LIMIT 1) AS customer_name,
      s.name AS supplier_master_name,
      s.iban AS supplier_master_iban,
      s.default_account_id AS supplier_default_account
    FROM documents d
    LEFT JOIN suppliers s ON s.id = d.supplier_id
    WHERE d.document_type IN ('invoice','dunning','reminder')
    """
    params = {"lim": limit}
    if direction:
        sql += " AND d.direction = :dir"
        params["dir"] = direction
    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    def _parse_amount(s):
        if not s: return 0.0
        s = str(s).strip().replace(' ','').replace('€','').replace('EUR','')
        if ',' in s and '.' in s: s = s.replace('.','').replace(',','.')
        elif ',' in s: s = s.replace(',','.')
        try: return float(s)
        except (ValueError, TypeError): return 0.0

    OWN = ("lunchbox","lichtquelle","inselwellen","allweglehen","knödler","knodler")
    invoices = []
    with engine.connect() as conn:
        for r in conn.execute(sa.text(sql), params).fetchall():
            (doc_id, doc_type, created_at, acc_status, direction_raw, account_id,
             paid_amount, supplier_id, inv_num, inv_date, due_date, amount_text, currency,
             vat_amount, vat_rate, iban, supplier_name_extr, customer_name,
             supplier_master_name, supplier_master_iban, supplier_default_account) = r

            cust_lower = (customer_name or "").lower()
            direction_eff = direction_raw or ("incoming" if any(n in cust_lower for n in OWN) else "outgoing")

            # Partner: 1. Lieferant aus Stammdaten, 2. extrahiert, 3. customer
            partner = supplier_master_name or supplier_name_extr
            if not partner and direction_eff != "incoming":
                partner = customer_name
            if not partner:
                partner = customer_name or "—"

            # IBAN: Stammdaten priorisieren
            iban_eff = supplier_master_iban or iban

            # Konto: wenn Rechnung kein Konto hat, Standardkonto vom Lieferant nehmen (als Vorschlag)
            account_id_eff = account_id or supplier_default_account
            account_suggested = account_id is None and supplier_default_account is not None

            amount_val = _parse_amount(amount_text)
            paid_val = float(paid_amount or 0)
            outstanding = max(0.0, amount_val - paid_val) if amount_val else 0.0

            invoices.append({
                "id": doc_id, "document_type": doc_type, "direction": direction_eff,
                "invoice_number": inv_num, "invoice_date": inv_date, "due_date": due_date,
                "amount_total": amount_val, "outstanding_amount": outstanding,
                "currency": currency or "EUR",
                "vat_amount": _parse_amount(vat_amount) if vat_amount else None,
                "vat_rate": vat_rate, "iban": iban_eff,
                "supplier_id": supplier_id,
                "supplier_name": supplier_master_name or supplier_name_extr,
                "customer_name": customer_name,
                "partner": partner,
                "accounting_status": acc_status or "open",
                "account_id": account_id_eff,
                "account_suggested": account_suggested,
                "created_at": created_at.isoformat() if created_at else None,
            })
    return {"count": len(invoices), "invoices": invoices}


# === FILE STORAGE & VIEW (added 28.04.2026) ===================
import uuid as _f_uuid
from pathlib import Path as _f_Path
from fastapi.responses import FileResponse as _f_FileResponse

UPLOAD_DIR = _f_Path("/opt/shiksha/uploads/invoices")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@accounting_router.post("/invoices/bulk-upload-v2")
async def bulk_upload_pdfs_v2(files: list[UploadFile] = File(...)):
    """Wie bulk-upload, aber speichert auch das Original-PDF."""
    import httpx
    results = []

    for file in files:
        content = await file.read()
        # 1. PDF auf Disk speichern
        file_id = str(_f_uuid.uuid4())
        safe_name = "".join(c for c in (file.filename or "invoice.pdf") if c.isalnum() or c in '._-')[:80]
        disk_path = UPLOAD_DIR / f"{file_id}_{safe_name}"
        disk_path.write_bytes(content)

        # 2. An document.module forwarden (gleicher Code wie alter bulk-upload)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/documents/upload",
                    files={"file": (file.filename, content, "application/pdf")},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    doc_id = data.get("document_id") or data.get("id")
                    # 3. file_path zur DB schreiben
                    if doc_id:
                        with engine.begin() as conn:
                            conn.execute(sa.text("""
                                UPDATE documents SET
                                  file_path = :p, file_name = :n, file_size = :s, file_mime = 'application/pdf'
                                WHERE id = :id
                            """), {"p": str(disk_path), "n": file.filename, "s": len(content), "id": doc_id})
                    results.append({"filename": file.filename, "ok": True, "document_id": doc_id})
                else:
                    results.append({"filename": file.filename, "ok": False, "error": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"filename": file.filename, "ok": False, "error": str(e)})

    return {"results": results, "count": len(results)}


@accounting_router.get("/invoices/{inv_id}/file")
async def view_invoice_file(inv_id: str):
    """Liefert das Original-PDF einer Rechnung zurück."""
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT file_path, file_name, file_mime FROM documents WHERE id=:id"
        ), {"id": inv_id}).first()
    if not row or not row[0]:
        raise HTTPException(404, "Datei nicht gefunden — Rechnung wurde vor Phase 3 hochgeladen, bitte neu hochladen.")
    fp = _f_Path(row[0])
    if not fp.exists():
        raise HTTPException(404, "Datei auf Disk nicht gefunden.")
    return _f_FileResponse(
        path=fp,
        media_type=row[2] or "application/pdf",
        filename=row[1] or "rechnung.pdf",
    )


# === BULK-UPLOAD V3 mit Duplikat-Erkennung ====================
import hashlib as _h_hashlib

@accounting_router.post("/invoices/bulk-upload-v3")
async def bulk_upload_pdfs_v3(
    files: list[UploadFile] = File(...),
    force: bool = False,
):
    """
    Wie v2, aber prüft SHA256-Hash gegen DB.
    - Wenn Duplikat: 'duplicate=true' im Response, Datei NICHT importiert
    - Mit ?force=true: trotzdem importiert
    """
    import httpx
    results = []

    for file in files:
        content = await file.read()
        # 1. Hash berechnen
        file_hash = _h_hashlib.sha256(content).hexdigest()

        # 2. Duplikat-Check
        if not force:
            with engine.connect() as conn:
                existing = conn.execute(sa.text(
                    "SELECT id, file_name, created_at FROM documents WHERE file_hash = :h LIMIT 1"
                ), {"h": file_hash}).first()
            if existing:
                results.append({
                    "filename": file.filename,
                    "ok": False,
                    "duplicate": True,
                    "existing_id": existing[0],
                    "existing_name": existing[1],
                    "existing_date": existing[2].isoformat() if existing[2] else None,
                    "error": f"Datei existiert bereits als: {existing[1]} ({existing[2].date() if existing[2] else '?'})",
                })
                continue

        # 3. PDF auf Disk speichern
        file_id = str(_f_uuid.uuid4())
        safe_name = "".join(c for c in (file.filename or "invoice.pdf") if c.isalnum() or c in '._-')[:80]
        disk_path = UPLOAD_DIR / f"{file_id}_{safe_name}"
        disk_path.write_bytes(content)

        # 4. An document.module forwarden
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    "http://127.0.0.1:8000/documents/upload",
                    files={"file": (file.filename, content, "application/pdf")},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    doc_id = data.get("document_id") or data.get("id")
                    if doc_id:
                        with engine.begin() as conn:
                            conn.execute(sa.text("""
                                UPDATE documents SET
                                  file_path = :p, file_name = :n, file_size = :s,
                                  file_mime = 'application/pdf', file_hash = :h
                                WHERE id = :id
                            """), {"p": str(disk_path), "n": file.filename, "s": len(content),
                                   "h": file_hash, "id": doc_id})
                    results.append({"filename": file.filename, "ok": True, "document_id": doc_id})
                else:
                    results.append({"filename": file.filename, "ok": False, "error": f"HTTP {resp.status_code}"})
        except Exception as e:
            results.append({"filename": file.filename, "ok": False, "error": str(e)})

    duplicates = sum(1 for r in results if r.get("duplicate"))
    return {
        "results": results,
        "count": len(results),
        "duplicates": duplicates,
        "force_used": force,
    }
"""
Phase 3: Inline-Edit Endpoint für Rechnungs-Felder
Wird ans Ende von /opt/shiksha/accounting_router.py angehängt.
"""

# === ANHÄNGEN AN /opt/shiksha/accounting_router.py ===

import uuid as _e_uuid

ALLOWED_EDIT_FIELDS = {
    "invoice_number", "invoice_date", "due_date",
    "amount_total", "amount_net", "amount_tax", "vat_rate",
    "currency", "iban", "supplier_name", "customer_name",
}


@accounting_router.patch("/invoices/{inv_id}/fields")
async def edit_invoice_fields(inv_id: str, payload: dict = Body(...)):
    """
    Manuelle Feld-Korrektur durch User.
    Body: {"field_key": "amount_total", "field_value": "106.40"}
    Schreibt in document_field_candidates mit confidence=1.0 (höchste Priorität).
    Ersetzt bestehende User-Edits, ergänzt sonst.
    """
    field_key = payload.get("field_key")
    field_value = payload.get("field_value")
    if not field_key or field_key not in ALLOWED_EDIT_FIELDS:
        raise HTTPException(400, f"Ungültiges Feld: {field_key}. Erlaubt: {sorted(ALLOWED_EDIT_FIELDS)}")

    with engine.begin() as conn:
        # Doc existiert?
        exists = conn.execute(sa.text("SELECT id FROM documents WHERE id=:id"),
                              {"id": inv_id}).first()
        if not exists:
            raise HTTPException(404, "Rechnung nicht gefunden")

        if field_value is None or field_value == "":
            # Löschen aller candidates für diesen key
            conn.execute(sa.text("""
                DELETE FROM document_field_candidates
                WHERE document_id=:id AND field_key=:k
            """), {"id": inv_id, "k": field_key})
        else:
            # Existiert User-Edit (confidence=1.0)?
            existing = conn.execute(sa.text("""
                SELECT id FROM document_field_candidates
                WHERE document_id=:id AND field_key=:k AND confidence >= 0.99
            """), {"id": inv_id, "k": field_key}).first()

            if existing:
                conn.execute(sa.text("""
                    UPDATE document_field_candidates
                    SET field_value=:v, confidence=1.0
                    WHERE id=:cid
                """), {"v": str(field_value), "cid": existing[0]})
            else:
                conn.execute(sa.text("""
                    INSERT INTO document_field_candidates
                      (id, document_id, field_key, field_value, confidence, created_at)
                    VALUES (:id, :did, :k, :v, 1.0, NOW())
                """), {
                    "id": str(_e_uuid.uuid4()),
                    "did": inv_id, "k": field_key, "v": str(field_value),
                })

    return {"id": inv_id, "field_key": field_key, "field_value": field_value, "user_edited": True}


# === V3-Endpoint: amount_net hinzufügen, User-Edits priorisieren ===
@accounting_router.get("/invoices/v4")
async def list_invoices_v4(limit: int = 500, direction: str = None):
    """
    V4 = V3 + Brutto/Netto/MwSt + User-Edits haben höchste Priorität (confidence DESC).
    """
    sql = """
    SELECT d.id, d.document_type, d.created_at, d.accounting_status,
           d.direction, d.account_id, d.paid_amount, d.supplier_id,
           d.file_path,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='invoice_number' ORDER BY confidence DESC LIMIT 1) AS invoice_number,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('invoice_date','document_date') ORDER BY CASE field_key WHEN 'invoice_date' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS invoice_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('due_date_strict','due_date') ORDER BY CASE field_key WHEN 'due_date_strict' THEN 1 ELSE 2 END, confidence DESC LIMIT 1) AS due_date,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='amount_total' ORDER BY confidence DESC LIMIT 1) AS amount_total_text,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='amount_net' ORDER BY confidence DESC LIMIT 1) AS amount_net_text,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key IN ('amount_tax','vat_amount') ORDER BY confidence DESC LIMIT 1) AS amount_tax_text,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='vat_rate' ORDER BY confidence DESC LIMIT 1) AS vat_rate,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='currency' ORDER BY confidence DESC LIMIT 1) AS currency,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='iban' ORDER BY confidence DESC LIMIT 1) AS iban,
      (SELECT field_value FROM document_field_candidates WHERE document_id=d.id AND field_key='customer_name' ORDER BY confidence DESC LIMIT 1) AS customer_name,
      s.name AS supplier_master_name,
      s.iban AS supplier_master_iban,
      s.default_account_id AS supplier_default_account
    FROM documents d
    LEFT JOIN suppliers s ON s.id = d.supplier_id
    WHERE d.document_type IN ('invoice','dunning','reminder')
    """
    params = {"lim": limit}
    if direction:
        sql += " AND d.direction = :dir"
        params["dir"] = direction
    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    def _parse_amount(s):
        if not s: return 0.0
        s = str(s).strip().replace(' ','').replace('€','').replace('EUR','')
        if ',' in s and '.' in s: s = s.replace('.','').replace(',','.')
        elif ',' in s: s = s.replace(',','.')
        try: return float(s)
        except (ValueError, TypeError): return 0.0

    OWN = ("lunchbox","lichtquelle","inselwellen","allweglehen","knödler","knodler")
    invoices = []
    with engine.connect() as conn:
        for r in conn.execute(sa.text(sql), params).fetchall():
            (doc_id, doc_type, created_at, acc_status, direction_raw, account_id,
             paid_amount, supplier_id, file_path,
             inv_num, inv_date, due_date,
             amount_total_text, amount_net_text, amount_tax_text,
             vat_rate, currency, iban, customer_name,
             supplier_master_name, supplier_master_iban, supplier_default_account) = r

            cust_lower = (customer_name or "").lower()
            direction_eff = direction_raw or ("incoming" if any(n in cust_lower for n in OWN) else "outgoing")

            partner = supplier_master_name or customer_name or "—"
            iban_eff = supplier_master_iban or iban
            account_id_eff = account_id or supplier_default_account
            account_suggested = account_id is None and supplier_default_account is not None

            brutto = _parse_amount(amount_total_text)
            netto = _parse_amount(amount_net_text)
            mwst = _parse_amount(amount_tax_text)

            # Auto-Compute: wenn 2 von 3 da, das dritte berechnen
            if brutto > 0 and mwst > 0 and netto == 0:
                netto = round(brutto - mwst, 2)
            elif brutto > 0 and netto > 0 and mwst == 0:
                mwst = round(brutto - netto, 2)
            elif netto > 0 and mwst > 0 and brutto == 0:
                brutto = round(netto + mwst, 2)

            paid_val = float(paid_amount or 0)
            outstanding = max(0.0, brutto - paid_val) if brutto else 0.0

            invoices.append({
                "id": doc_id, "document_type": doc_type, "direction": direction_eff,
                "invoice_number": inv_num,
                "invoice_date": inv_date,
                "due_date": due_date,
                "amount_total": brutto,
                "amount_net": netto,
                "amount_tax": mwst,
                "outstanding_amount": outstanding,
                "currency": currency or "EUR",
                "vat_rate": vat_rate,
                "iban": iban_eff,
                "supplier_id": supplier_id,
                "supplier_name": supplier_master_name,
                "customer_name": customer_name,
                "partner": partner,
                "accounting_status": acc_status or "open",
                "account_id": account_id_eff,
                "account_suggested": account_suggested,
                "has_file": bool(file_path),
                "created_at": created_at.isoformat() if created_at else None,
            })
    return {"count": len(invoices), "invoices": invoices}
"""
SHIKSHA · Phase 4 Endpoints
- DELETE /accounting/invoices/{id}
- /accounting/cashbook (Kassabuch)
"""

# === ANHÄNGEN AN /opt/shiksha/accounting_router.py ===

from pathlib import Path as _cb_Path
import uuid as _cb_uuid
from datetime import date as _cb_date

CASHBOOK_DIR = _cb_Path("/opt/shiksha/uploads/receipts")
CASHBOOK_DIR.mkdir(parents=True, exist_ok=True)


# === DELETE INVOICE ============================================
@accounting_router.delete("/invoices/{inv_id}")
async def delete_invoice(inv_id: str):
    """Löscht eine Rechnung samt field_candidates und Original-PDF."""
    with engine.begin() as conn:
        # Datei-Pfad lesen, um sie auch von Disk zu löschen
        row = conn.execute(sa.text(
            "SELECT file_path FROM documents WHERE id=:id"
        ), {"id": inv_id}).first()
        if not row:
            raise HTTPException(404, "Rechnung nicht gefunden")
        file_path = row[0]

        # FK-Reihenfolge: erst dependents, dann document
        conn.execute(sa.text("DELETE FROM ledger_entries WHERE document_id=:id"), {"id": inv_id})
        conn.execute(sa.text("DELETE FROM document_field_candidates WHERE document_id=:id"), {"id": inv_id})
        conn.execute(sa.text("DELETE FROM documents WHERE id=:id"), {"id": inv_id})

    # Datei löschen falls vorhanden
    if file_path:
        try:
            p = _cb_Path(file_path)
            if p.exists():
                p.unlink()
        except Exception:
            pass

    return {"id": inv_id, "deleted": True}


# === KASSABUCH =================================================

@accounting_router.get("/cashbook")
async def list_cashbook(
    year: int = None,
    month: int = None,
    limit: int = 1000,
):
    """
    Kassabuch-Einträge sortiert nach Datum aufsteigend mit laufendem Saldo.
    """
    sql = """
    SELECT cb.id, cb.entry_date, cb.document_no, cb.description,
           cb.amount_in, cb.amount_out, cb.vat_rate, cb.vat_amount,
           cb.account_id, cb.supplier_id,
           cb.receipt_file_path, cb.receipt_file_name,
           cb.notes, cb.created_at,
           a.account_number, a.account_name,
           s.name AS supplier_name
    FROM cash_book_entries cb
    LEFT JOIN chart_of_accounts a ON a.id = cb.account_id
    LEFT JOIN suppliers s ON s.id = cb.supplier_id
    WHERE 1=1
    """
    params = {"lim": limit}
    if year:
        sql += " AND EXTRACT(YEAR FROM cb.entry_date) = :y"
        params["y"] = year
    if month:
        sql += " AND EXTRACT(MONTH FROM cb.entry_date) = :m"
        params["m"] = month
    sql += " ORDER BY cb.entry_date ASC, cb.created_at ASC LIMIT :lim"

    entries = []
    saldo = 0.0
    with engine.connect() as conn:
        for r in conn.execute(sa.text(sql), params).fetchall():
            (eid, edate, doc_no, desc, amt_in, amt_out, vat_rate, vat_amount,
             acc_id, sup_id, file_path, file_name, notes, created,
             acc_num, acc_name, sup_name) = r
            ai = float(amt_in or 0)
            ao = float(amt_out or 0)
            saldo += ai - ao
            entries.append({
                "id": eid,
                "entry_date": edate.isoformat() if edate else None,
                "document_no": doc_no,
                "description": desc,
                "amount_in": ai,
                "amount_out": ao,
                "vat_rate": float(vat_rate) if vat_rate is not None else None,
                "vat_amount": float(vat_amount) if vat_amount is not None else None,
                "account_id": acc_id,
                "account_label": f"{acc_num} {acc_name}" if acc_num else None,
                "supplier_id": sup_id,
                "supplier_name": sup_name,
                "has_receipt": bool(file_path),
                "receipt_name": file_name,
                "notes": notes,
                "saldo": round(saldo, 2),
                "created_at": created.isoformat() if created else None,
            })

    # Summen
    total_in = sum(e["amount_in"] for e in entries)
    total_out = sum(e["amount_out"] for e in entries)

    return {
        "count": len(entries),
        "entries": entries,
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "balance": round(total_in - total_out, 2),
    }


@accounting_router.post("/cashbook")
async def create_cashbook_entry(payload: dict = Body(...)):
    """Neuen Kassabuch-Eintrag anlegen."""
    desc = (payload.get("description") or "").strip()
    if not desc:
        raise HTTPException(400, "description ist Pflicht")

    entry_date = payload.get("entry_date") or _cb_date.today().isoformat()
    amount_in = float(payload.get("amount_in") or 0)
    amount_out = float(payload.get("amount_out") or 0)
    if amount_in == 0 and amount_out == 0:
        raise HTTPException(400, "Eingang oder Ausgang muss > 0 sein")

    # Auto Document-No: K-YYYY-NNN
    document_no = payload.get("document_no")
    if not document_no:
        with engine.connect() as conn:
            year = entry_date[:4]
            count = conn.execute(sa.text(
                "SELECT COUNT(*) FROM cash_book_entries WHERE EXTRACT(YEAR FROM entry_date) = :y"
            ), {"y": int(year)}).scalar()
        document_no = f"K-{year}-{(count or 0) + 1:04d}"

    # VAT auto-compute wenn vat_rate gegeben aber vat_amount nicht
    vat_rate = payload.get("vat_rate")
    vat_amount = payload.get("vat_amount")
    if vat_rate is not None and vat_amount is None:
        gross = max(amount_in, amount_out)
        vat_rate_f = float(vat_rate)
        if vat_rate_f > 0:
            vat_amount = round(gross - (gross / (1 + vat_rate_f / 100)), 2)

    eid = str(_cb_uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO cash_book_entries
              (id, entry_date, document_no, description, amount_in, amount_out,
               vat_rate, vat_amount, account_id, supplier_id, notes)
            VALUES
              (:id, :ed, :no, :desc, :ai, :ao, :vr, :va, :acc, :sup, :notes)
        """), {
            "id": eid, "ed": entry_date, "no": document_no, "desc": desc,
            "ai": amount_in, "ao": amount_out,
            "vr": vat_rate, "va": vat_amount,
            "acc": payload.get("account_id"),
            "sup": payload.get("supplier_id"),
            "notes": payload.get("notes"),
        })
    return {"id": eid, "document_no": document_no}


@accounting_router.patch("/cashbook/{entry_id}")
async def update_cashbook_entry(entry_id: str, payload: dict = Body(...)):
    """Kassabuch-Eintrag editieren."""
    fields = {}
    for k in ("entry_date","description","amount_in","amount_out",
              "vat_rate","vat_amount","account_id","supplier_id","notes","document_no"):
        if k in payload:
            fields[k] = payload[k]
    if not fields:
        raise HTTPException(400, "keine Felder im Payload")
    set_parts = [f"{k} = :{k}" for k in fields.keys()]
    set_parts.append("updated_at = NOW()")
    sql = f"UPDATE cash_book_entries SET {', '.join(set_parts)} WHERE id = :id"
    fields["id"] = entry_id
    with engine.begin() as conn:
        result = conn.execute(sa.text(sql), fields)
        if result.rowcount == 0:
            raise HTTPException(404, "Eintrag nicht gefunden")
    return {"id": entry_id, "updated": [k for k in fields if k != "id"]}


@accounting_router.delete("/cashbook/{entry_id}")
async def delete_cashbook_entry(entry_id: str):
    """Kassabuch-Eintrag löschen samt Beleg."""
    with engine.begin() as conn:
        row = conn.execute(sa.text(
            "SELECT receipt_file_path FROM cash_book_entries WHERE id=:id"
        ), {"id": entry_id}).first()
        if not row:
            raise HTTPException(404, "Eintrag nicht gefunden")
        conn.execute(sa.text("DELETE FROM cash_book_entries WHERE id=:id"), {"id": entry_id})
    if row[0]:
        try:
            p = _cb_Path(row[0])
            if p.exists():
                p.unlink()
        except Exception:
            pass
    return {"id": entry_id, "deleted": True}


@accounting_router.post("/cashbook/{entry_id}/receipt")
async def upload_cashbook_receipt(entry_id: str, file: UploadFile = File(...)):
    """Beleg-Datei (Foto/PDF) zu einem Kassabuch-Eintrag hochladen."""
    content = await file.read()
    if not content:
        raise HTTPException(400, "Leere Datei")

    safe_name = "".join(c for c in (file.filename or "receipt") if c.isalnum() or c in '._-')[:80]
    file_id = str(_cb_uuid.uuid4())
    disk_path = CASHBOOK_DIR / f"{entry_id}_{file_id}_{safe_name}"
    disk_path.write_bytes(content)

    mime = file.content_type or "application/octet-stream"

    with engine.begin() as conn:
        result = conn.execute(sa.text("""
            UPDATE cash_book_entries
            SET receipt_file_path=:p, receipt_file_name=:n, receipt_mime=:m,
                receipt_size=:s, updated_at=NOW()
            WHERE id=:id
        """), {"p": str(disk_path), "n": file.filename, "m": mime,
               "s": len(content), "id": entry_id})
        if result.rowcount == 0:
            disk_path.unlink(missing_ok=True)
            raise HTTPException(404, "Eintrag nicht gefunden")

    return {"id": entry_id, "file_name": file.filename, "size": len(content)}


@accounting_router.get("/cashbook/{entry_id}/receipt")
async def view_cashbook_receipt(entry_id: str):
    """Beleg-Datei (Foto/PDF) eines Kassabuch-Eintrags anzeigen."""
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT receipt_file_path, receipt_file_name, receipt_mime FROM cash_book_entries WHERE id=:id"
        ), {"id": entry_id}).first()
    if not row or not row[0]:
        raise HTTPException(404, "Beleg nicht gefunden")
    fp = _cb_Path(row[0])
    if not fp.exists():
        raise HTTPException(404, "Datei auf Disk nicht gefunden")
    return _f_FileResponse(
        path=fp,
        media_type=row[2] or "application/octet-stream",
        filename=row[1] or "beleg",
    )


@accounting_router.get("/ui/kita/dashboard", include_in_schema=False)
async def ui_kita_dashboard():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/dashboard.html", media_type="text/html")


@accounting_router.get("/ui/kita/anmeldung", include_in_schema=False)
async def ui_kita_anmeldung():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/anmeldung.html", media_type="text/html")


@accounting_router.get("/ui/kita/eltern", include_in_schema=False)
async def ui_kita_eltern():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/eltern.html", media_type="text/html")

@accounting_router.get("/ui/kita/manifest.json", include_in_schema=False)
async def ui_kita_manifest():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/manifest.json", media_type="application/manifest+json")

@accounting_router.get("/ui/kita/service-worker.js", include_in_schema=False)
async def ui_kita_sw():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/service-worker.js", media_type="application/javascript")

@accounting_router.get("/ui/kita/app-icon.svg", include_in_schema=False)
async def ui_kita_icon():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/kita_ui/app-icon.svg", media_type="image/svg+xml")


@accounting_router.get("/ui/identity/wizard", include_in_schema=False)
async def ui_identity_wizard():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/identity_ui/wizard.html", media_type="text/html")


@accounting_router.get("/ui/identity/manifest.json", include_in_schema=False)
async def ui_identity_manifest():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/identity_ui/manifest.json", media_type="application/manifest+json")


@accounting_router.get("/ui/paedagogen/app", include_in_schema=False)
async def ui_paedagogen_app():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/paedagogen_ui/app.html", media_type="text/html")

@accounting_router.get("/ui/paedagogen/shiksha-avatar.js", include_in_schema=False)
async def ui_paedagogen_avatar_js():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/paedagogen_ui/shiksha-avatar.js", media_type="application/javascript")

@accounting_router.get("/ui/paedagogen/manifest.json", include_in_schema=False)
async def ui_paedagogen_manifest():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/paedagogen_ui/manifest.json", media_type="application/manifest+json")

# === KITA-UI-Mounts (auto v3) ===

@accounting_router.get("/ui/kita/personen", include_in_schema=False)
async def kita_ui_personen():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/personen.html")

@accounting_router.get("/ui/kita/push", include_in_schema=False)
async def kita_ui_push():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/push.html")

@accounting_router.get("/ui/kita/calendar", include_in_schema=False)
async def kita_ui_calendar():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/calendar.html")

@accounting_router.get("/ui/kita/shiksha-push.js", include_in_schema=False)
async def kita_ui_shiksha_push_js():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/shiksha-push.js", media_type="application/javascript")

# === Trägerin-Dashboard Mounts ===

@accounting_router.get("/ui/kita/dashboard_traegerin", include_in_schema=False)
async def kita_ui_dashboard_traegerin():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/dashboard_traegerin.html")

@accounting_router.get("/ui/kita/shiksha-cards.css", include_in_schema=False)
async def kita_ui_cards_css():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/shiksha-cards.css", media_type="text/css")

@accounting_router.get("/ui/kita/shiksha-cards.js", include_in_schema=False)
async def kita_ui_cards_js():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/shiksha-cards.js", media_type="application/javascript")

# === Wochen-Motto-Editor ===

@accounting_router.get("/ui/kita/weekly-theme", include_in_schema=False)
async def kita_weekly_theme_ui():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/weekly_theme.html")

# === Marketing-Builder Mount ===

@accounting_router.get("/ui/marketing/builder", include_in_schema=False)
async def marketing_builder_ui():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/marketing/builder.html")

