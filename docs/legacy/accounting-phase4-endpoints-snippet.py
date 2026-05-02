"""
SHIKSHA · Accounting · phase4_endpoints.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 28.04.2026 via deploy-Skript an
/opt/shiksha/accounting_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/accounting_router.py  (omnibus router, ~70 KB)

Bei einem Refactor "accounting modular" kann dieses Snippet zurück
nach server/phase4_endpoints.py wandern.

Original: cowork/outputs/accounting/server/phase4_endpoints.py
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

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
        conn.execute(sa.text("DELETE FROM payment_records WHERE invoice_id=:id"), {"id": inv_id})
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
