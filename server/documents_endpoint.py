

# ----------------------------------------------------------
# GET /documents — offene Posten pro Entity
# ----------------------------------------------------------

@app.get("/documents")
async def get_documents(entity_id: str = None, status: str = None):
    """
    Gibt verlinkte Dokumente zurück.
    - entity_id: nur Dokumente dieser Entity (optional)
    - status:    filter auf "analyzed" | "linked" (optional)
    """
    try:
        import sqlalchemy as _sa
        from database import engine

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
