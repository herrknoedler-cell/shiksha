-- ============================================================
-- SHIKSHA · Phase 4: Kassabuch (Cash Book) + Delete-Support
-- Stand: 28.04.2026
-- ============================================================

-- 1. Kassabuch-Einträge
CREATE TABLE IF NOT EXISTS cash_book_entries (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    edition             TEXT DEFAULT 'business.shiksha',
    entry_date          DATE NOT NULL,
    document_no         TEXT,                          -- "K-2026-001" oder manuell
    description         TEXT NOT NULL,
    amount_in           NUMERIC(12,2) DEFAULT 0,       -- Einnahme
    amount_out          NUMERIC(12,2) DEFAULT 0,       -- Ausgabe
    vat_rate            NUMERIC(4,2),                  -- z.B. 10.00, 20.00
    vat_amount          NUMERIC(12,2),
    account_id          TEXT REFERENCES chart_of_accounts(id),
    supplier_id         TEXT REFERENCES suppliers(id),
    -- Belegfoto/-Scan
    receipt_file_path   TEXT,
    receipt_file_name   TEXT,
    receipt_mime        TEXT,
    receipt_size        INTEGER,
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cashbook_date ON cash_book_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_cashbook_account ON cash_book_entries(account_id);
CREATE INDEX IF NOT EXISTS idx_cashbook_supplier ON cash_book_entries(supplier_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON cash_book_entries TO shiksha;

-- Storage-Verzeichnis für Belege
\! mkdir -p /opt/shiksha/uploads/receipts
\! chmod 755 /opt/shiksha/uploads/receipts
