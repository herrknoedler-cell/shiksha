"""
SHIKSHA · Accounting · phase2_endpoints.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 28.04.2026 via deploy-Skript an
/opt/shiksha/accounting_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/accounting_router.py  (omnibus router, ~70 KB)

Bei einem Refactor "accounting modular" kann dieses Snippet zurück
nach server/phase2_endpoints.py wandern.

Original: cowork/outputs/accounting/server/phase2_endpoints.py
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

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
                   a.number AS account_number, a.name AS account_name
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
