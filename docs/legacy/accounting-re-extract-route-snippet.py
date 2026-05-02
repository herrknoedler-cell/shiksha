"""
SHIKSHA · Accounting · re_extract_route.py — Legacy Cowork-Quelle (nur Audit-Referenz)

⚠️ DIESE DATEI WIRD VOM SERVER NICHT GELADEN.

Original-Cowork-Quelle, am 28.04.2026 via deploy-Skript an
/opt/shiksha/accounting_router.py ANGEHÄNGT — nicht als
eigenständiger Router deployed.

Der deployed-Stand lebt heute in:
    server/accounting_router.py  (omnibus router, ~70 KB)

Bei einem Refactor "accounting modular" kann dieses Snippet zurück
nach server/re_extract_route.py wandern.

Original: cowork/outputs/accounting/server/re_extract_route.py
Importiert: 2026-05-02

— Original-Inhalt unverändert ab hier —
"""

"""
Re-Extract Route — wird ans Ende von accounting_router.py angehängt.
Läuft alle Documents nochmal durch den (gepatchten) Extractor.
Ergänzt fehlende field_keys, ohne bestehende mit höherer Confidence zu überschreiben.
"""

# === ANHÄNGEN AN /opt/shiksha/accounting_router.py ===

import uuid as _re_uuid
from extractor_extensions import re_extract_document as _re_extract_doc


@accounting_router.post("/invoices/re-extract")
async def re_extract_invoices(limit: int = 1000):
    """
    Re-runs the field extractor on all existing documents.
    - Schreibt neue field_candidates für Keys, die noch nicht existieren
    - Ersetzt bestehende NUR wenn neue confidence höher ist
    Returns: {"processed": N, "added": M, "replaced": K}
    """
    processed = 0
    added = 0
    replaced = 0

    with engine.begin() as conn:
        docs = conn.execute(sa.text("""
            SELECT id, raw_text, document_type
            FROM documents
            WHERE raw_text IS NOT NULL
              AND LENGTH(raw_text) > 50
            ORDER BY created_at DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()

        for doc in docs:
            doc_id = doc[0]
            raw_text = doc[1]
            doc_type = doc[2] or "invoice"

            try:
                new_cands = _re_extract_doc(raw_text, doc_type)
            except Exception as e:
                print(f"[re-extract] Fehler bei {doc_id}: {e}")
                continue

            # Existierende Candidates abfragen
            existing = conn.execute(sa.text("""
                SELECT id, field_key, confidence
                FROM document_field_candidates
                WHERE document_id = :did
            """), {"did": doc_id}).fetchall()
            existing_map = {row[1]: (row[0], row[2]) for row in existing}

            for c in new_cands:
                key = c["field_key"]
                val = c["field_value"]
                conf = c["confidence"]
                if key in existing_map:
                    old_id, old_conf = existing_map[key]
                    if conf > (old_conf or 0) + 0.05:
                        # Mit höherer Confidence ersetzen
                        conn.execute(sa.text("""
                            UPDATE document_field_candidates
                            SET field_value=:v, confidence=:c
                            WHERE id=:id
                        """), {"v": val, "c": conf, "id": old_id})
                        replaced += 1
                else:
                    # Neu einfügen
                    conn.execute(sa.text("""
                        INSERT INTO document_field_candidates
                          (id, document_id, field_key, field_value, confidence, created_at)
                        VALUES
                          (:id, :did, :k, :v, :c, NOW())
                    """), {
                        "id": str(_re_uuid.uuid4()),
                        "did": doc_id,
                        "k": key,
                        "v": val,
                        "c": conf,
                    })
                    added += 1

            processed += 1

    return {
        "processed": processed,
        "added": added,
        "replaced": replaced,
        "message": f"{processed} Dokumente neu extrahiert: {added} Felder hinzugefügt, {replaced} ersetzt",
    }
