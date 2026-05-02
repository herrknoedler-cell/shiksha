"""
SHIKSHA · Accounting · phase3_edit_endpoint.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 28.04.2026 via deploy-Skript an
/opt/shiksha/accounting_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/accounting_router.py  (omnibus router, ~70 KB)

Bei einem Refactor "accounting modular" kann dieses Snippet zurück
nach server/phase3_edit_endpoint.py wandern.

Original: cowork/outputs/accounting/server/phase3_edit_endpoint.py
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

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
