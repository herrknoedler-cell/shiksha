"""
SHIKSHA · Accounting · invoices_v2_route.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 28.04.2026 via deploy-Skript an
/opt/shiksha/accounting_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/accounting_router.py  (omnibus router, ~70 KB)

Bei einem Refactor "accounting modular" kann dieses Snippet zurück
nach server/invoices_v2_route.py wandern.

Original: cowork/outputs/accounting/server/invoices_v2_route.py
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
Invoices V2 Endpoint — wird ans Ende von accounting_router.py angehängt.

Joined document_field_candidates und gibt das wirkliche Bild zurück:
  - invoice_date, invoice_number, amount_total aus den Candidates
  - supplier_name vs customer_name auto-direction-aware
  - outstanding_amount korrekt berechnet
  - partner-Feld für Dashboard-Anzeige

Stand: 28.04.2026
"""

# === ANHÄNGEN AN /opt/shiksha/accounting_router.py ===

@accounting_router.get("/invoices/v2")
async def list_invoices_v2(limit: int = 500, direction: str = None):
    """
    Erweiterte Invoice-Liste mit gejointen field_candidates.
    Liefert pro Rechnung die wichtigsten Felder zur Anzeige im Dashboard.
    """
    sql = """
    SELECT
        d.id,
        d.document_type,
        d.created_at,
        d.accounting_status,
        d.direction,
        d.account_id,
        d.paid_amount,

        -- Felder aus document_field_candidates (höchste confidence pro key)
        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'invoice_number'
         ORDER BY confidence DESC LIMIT 1) AS invoice_number,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key IN ('invoice_date','document_date','belegdatum')
         ORDER BY
           CASE field_key WHEN 'invoice_date' THEN 1 WHEN 'document_date' THEN 2 ELSE 3 END,
           confidence DESC LIMIT 1) AS invoice_date,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key IN ('due_date_strict','due_date')
         ORDER BY
           CASE field_key WHEN 'due_date_strict' THEN 1 ELSE 2 END,
           confidence DESC LIMIT 1) AS due_date,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'amount_total'
         ORDER BY confidence DESC LIMIT 1) AS amount_total_text,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'currency'
         ORDER BY confidence DESC LIMIT 1) AS currency,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'vat_amount'
         ORDER BY confidence DESC LIMIT 1) AS vat_amount,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'vat_rate'
         ORDER BY confidence DESC LIMIT 1) AS vat_rate,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'iban'
         ORDER BY confidence DESC LIMIT 1) AS iban,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'supplier_name'
         ORDER BY confidence DESC LIMIT 1) AS supplier_name,

        (SELECT field_value FROM document_field_candidates
         WHERE document_id = d.id AND field_key = 'customer_name'
         ORDER BY confidence DESC LIMIT 1) AS customer_name

    FROM documents d
    WHERE d.document_type IN ('invoice','dunning','reminder')
    """
    params = {"lim": limit}
    if direction:
        sql += " AND d.direction = :dir"
        params["dir"] = direction

    sql += " ORDER BY d.created_at DESC LIMIT :lim"

    invoices = []
    with engine.connect() as conn:
        rows = conn.execute(sa.text(sql), params).fetchall()

        for r in rows:
            (doc_id, doc_type, created_at, acc_status, direction_raw, account_id,
             paid_amount, inv_num, inv_date, due_date, amount_text, currency,
             vat_amount, vat_rate, iban, supplier_name, customer_name) = r

            # Auto-direction wenn NULL: wenn customer_name = eine eigene Firma → incoming
            OWN_NAMES = ("lunchbox", "lichtquelle", "inselwellen", "allweglehen", "knödler", "knodler")
            cust_lower = (customer_name or "").lower()
            if not direction_raw:
                if any(n in cust_lower for n in OWN_NAMES):
                    direction_eff = "incoming"
                else:
                    direction_eff = "outgoing"
            else:
                direction_eff = direction_raw

            # Partner = supplier bei eingehend, customer bei ausgehend
            if direction_eff == "incoming":
                partner = supplier_name or _strip_own(customer_name) or "—"
            else:
                partner = customer_name or "—"

            # amount: deutsche Komma → float
            amount_val = _parse_amount(amount_text)
            paid_val = float(paid_amount or 0)
            outstanding = max(0.0, amount_val - paid_val) if amount_val else 0.0

            invoices.append({
                "id": doc_id,
                "document_type": doc_type,
                "direction": direction_eff,
                "invoice_number": inv_num,
                "invoice_date": inv_date,
                "due_date": due_date,
                "amount_total": amount_val,
                "outstanding_amount": outstanding,
                "currency": currency or "EUR",
                "vat_amount": _parse_amount(vat_amount) if vat_amount else None,
                "vat_rate": vat_rate,
                "iban": iban,
                "supplier_name": supplier_name,
                "customer_name": customer_name,
                "partner": partner,
                "accounting_status": acc_status or "open",
                "account_id": account_id,
                "created_at": created_at.isoformat() if created_at else None,
            })

    return {"count": len(invoices), "invoices": invoices}


def _parse_amount(s):
    """Wandelt '14,16' oder '1.488,93' in float."""
    if not s:
        return 0.0
    s = str(s).strip().replace(' ', '').replace('€', '').replace('EUR', '')
    # deutsches Format: Punkt = Tausender, Komma = Dezimal
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _strip_own(name):
    """Entfernt 'Lunchbox/Knödler' etc. um den ECHTEN Lieferant am Briefkopf zu finden."""
    if not name:
        return None
    OWN = ("lunchbox", "lichtquelle", "inselwellen", "allweglehen", "knödler", "knodler", "thomas")
    parts = [p for p in name.split() if p.lower().rstrip('.,') not in OWN]
    return ' '.join(parts).strip() if parts else None
