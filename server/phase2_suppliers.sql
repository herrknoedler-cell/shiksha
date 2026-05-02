-- ============================================================
-- SHIKSHA · Phase 2: Lieferanten-Stammdaten
-- Stand: 28.04.2026
-- ============================================================

-- 1. Tabelle für Lieferanten-Stammdaten
CREATE TABLE IF NOT EXISTS suppliers (
    id                  TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name                TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,         -- lowercase, ohne Sonderzeichen, für fuzzy-match
    iban                TEXT,
    uid_number          TEXT,
    default_account_id  TEXT REFERENCES chart_of_accounts(id),
    contact_email       TEXT,
    contact_phone       TEXT,
    address             TEXT,
    notes               TEXT,
    transaction_count   INTEGER DEFAULT 0,     -- aus wievielen Bank-Buchungen abgeleitet
    invoice_count       INTEGER DEFAULT 0,     -- wieviele Rechnungen verknüpft
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suppliers_normalized ON suppliers(normalized_name);
CREATE INDEX IF NOT EXISTS idx_suppliers_iban ON suppliers(iban) WHERE iban IS NOT NULL;

-- 2. supplier_id auf documents
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS supplier_id TEXT REFERENCES suppliers(id);
CREATE INDEX IF NOT EXISTS idx_documents_supplier ON documents(supplier_id);

-- 3. supplier_id auf bank_transactions (für späteren Match)
ALTER TABLE bank_transactions
  ADD COLUMN IF NOT EXISTS supplier_id TEXT REFERENCES suppliers(id);
CREATE INDEX IF NOT EXISTS idx_bank_supplier ON bank_transactions(supplier_id);

-- 4. Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON suppliers TO shiksha;

-- ============================================================
-- 5. AUTO-SEED: Lieferanten aus Bank-Buchungen extrahieren
-- ============================================================
-- Gruppiert counterparty_name + counterparty_iban,
-- nimmt die Buchung mit häufigster IBAN als Master.

INSERT INTO suppliers (name, normalized_name, iban, transaction_count)
SELECT
    name,
    LOWER(REGEXP_REPLACE(name, '[^a-z0-9 ]', '', 'gi')) AS normalized_name,
    iban,
    cnt
FROM (
    SELECT
        counterparty_name AS name,
        counterparty_iban AS iban,
        COUNT(*) AS cnt,
        ROW_NUMBER() OVER (PARTITION BY LOWER(counterparty_name) ORDER BY COUNT(*) DESC) AS rn
    FROM bank_transactions
    WHERE counterparty_name IS NOT NULL
      AND LENGTH(counterparty_name) >= 3
      -- Eigene Konten ausschließen
      AND counterparty_name !~* 'lunchbox|lichtquelle|inselwellen|allweglehen'
    GROUP BY counterparty_name, counterparty_iban
) ranked
WHERE rn = 1
ON CONFLICT DO NOTHING;

-- 6. Match: Rechnungen → Lieferanten via IBAN (exact match)
-- Nutzt die bereits extrahierten IBANs aus document_field_candidates
UPDATE documents d
SET supplier_id = s.id
FROM document_field_candidates c, suppliers s
WHERE c.document_id = d.id
  AND c.field_key = 'iban'
  AND c.field_value = s.iban
  AND d.supplier_id IS NULL;

-- 7. Match: Bank-Buchungen → Lieferanten via Name
UPDATE bank_transactions bt
SET supplier_id = s.id
FROM suppliers s
WHERE LOWER(bt.counterparty_name) = LOWER(s.name)
  AND bt.supplier_id IS NULL;

-- 8. invoice_count und transaction_count aktualisieren
UPDATE suppliers s
SET
    invoice_count = (SELECT COUNT(*) FROM documents WHERE supplier_id = s.id),
    transaction_count = (SELECT COUNT(*) FROM bank_transactions WHERE supplier_id = s.id);

-- 9. Statistik
SELECT
    'Lieferanten gesamt' AS metric, COUNT(*)::text AS value FROM suppliers
UNION ALL SELECT
    'Lieferanten mit IBAN', COUNT(*)::text FROM suppliers WHERE iban IS NOT NULL
UNION ALL SELECT
    'Rechnungen verknüpft', COUNT(*)::text FROM documents WHERE supplier_id IS NOT NULL
UNION ALL SELECT
    'Bank-Buchungen verknüpft', COUNT(*)::text FROM bank_transactions WHERE supplier_id IS NOT NULL;
