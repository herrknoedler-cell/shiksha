-- ============================================================================
-- SHIKSHA · ACCOUNTING MODUL · DB Migration V1
-- Stand: 25.04.2026
-- Idempotent.
--
-- Erweitert die V4-Tabellen `documents`, `customers`, `document_links`
-- um Bank-Buchungen, Statement-Imports, Match-History und Status-History.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. STATEMENT IMPORTS — Audit jeder Import-Operation
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS statement_imports (
    id              TEXT PRIMARY KEY,
    file_name       TEXT NOT NULL,
    file_format     TEXT NOT NULL,                     -- 'csv', 'camt053', 'mt940'
    bank_profile    TEXT,                              -- 'hypo_vorarlberg', 'sparkasse_bgl', etc.
    iban_account    TEXT NOT NULL,                     -- Konto, von dem importiert wurde
    period_from     DATE,
    period_to       DATE,
    transactions_count INTEGER DEFAULT 0,
    new_count       INTEGER DEFAULT 0,
    duplicate_count INTEGER DEFAULT 0,
    parse_errors    INTEGER DEFAULT 0,
    imported_at     TIMESTAMPTZ DEFAULT NOW(),
    imported_by     TEXT,
    file_hash       TEXT,                              -- SHA256 des Files für Duplikate-Erkennung
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_stmt_iban ON statement_imports (iban_account);
CREATE INDEX IF NOT EXISTS idx_stmt_imported ON statement_imports (imported_at DESC);

-- ----------------------------------------------------------------------------
-- 2. BANK TRANSACTIONS — einzelne Buchungen
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bank_transactions (
    id              TEXT PRIMARY KEY,
    statement_import_id TEXT REFERENCES statement_imports(id),
    iban_account    TEXT NOT NULL,                     -- unser Konto
    booking_date    DATE,                              -- Buchungstag
    value_date      DATE NOT NULL,                     -- Wertstellung
    amount          NUMERIC(12,2) NOT NULL,            -- + (Eingang) oder - (Ausgang)
    currency        TEXT DEFAULT 'EUR',
    direction       TEXT GENERATED ALWAYS AS (
                        CASE WHEN amount > 0 THEN 'in' ELSE 'out' END
                    ) STORED,
    counterparty_name TEXT,
    counterparty_iban TEXT,
    counterparty_bic  TEXT,
    purpose         TEXT,                              -- Verwendungszweck (Volltext)
    bank_reference  TEXT,                              -- Banken-eindeutige Referenz
    transaction_type TEXT,                             -- 'sepa_credit', 'sepa_debit', 'card', 'cash', 'standing_order', 'fee'
    status          TEXT DEFAULT 'unmatched',          -- 'unmatched', 'matched', 'partially_matched', 'ignored', 'review'
    raw_record      JSONB,                             -- Original-Datenzeile aus Statement
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bank_value_date ON bank_transactions (value_date DESC);
CREATE INDEX IF NOT EXISTS idx_bank_status ON bank_transactions (status);
CREATE INDEX IF NOT EXISTS idx_bank_counterparty ON bank_transactions (counterparty_iban);
CREATE INDEX IF NOT EXISTS idx_bank_amount ON bank_transactions (amount);

-- Eindeutigkeit: dieselbe Bank-Referenz darf nicht doppelt vorkommen
CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_reference ON bank_transactions (iban_account, bank_reference)
    WHERE bank_reference IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 3. PAYMENT MATCHES — bestätigte Verknüpfungen
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS payment_matches (
    id              TEXT PRIMARY KEY,
    bank_transaction_id TEXT NOT NULL REFERENCES bank_transactions(id),
    document_id     TEXT NOT NULL,                     -- referenziert documents.id (V4)
    match_type      TEXT NOT NULL,                     -- 'full', 'partial', 'overpayment', 'underpayment_skonto'
    matched_amount  NUMERIC(12,2) NOT NULL,            -- wie viel der bank_transaction der Rechnung zugeordnet ist
    score           INTEGER,                           -- 0-100 zum Audit (intern, nicht UI-sichtbar)
    score_breakdown JSONB,                             -- {iban: 40, amount: 30, purpose: 20, date: 10}
    confirmed_by    TEXT NOT NULL,                     -- Operator, der bestätigt hat
    confirmed_at    TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT,
    revoked_at      TIMESTAMPTZ,
    revoked_by      TEXT,
    revoke_reason   TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_match_tx ON payment_matches (bank_transaction_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_match_doc ON payment_matches (document_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_match_active ON payment_matches (confirmed_at DESC) WHERE revoked_at IS NULL;

-- ----------------------------------------------------------------------------
-- 4. INVOICE STATUS HISTORY — Audit-Spur jedes Status-Übergangs
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS invoice_status_history (
    id              SERIAL PRIMARY KEY,
    document_id     TEXT NOT NULL,                     -- referenziert documents.id
    from_status     TEXT,
    to_status       TEXT NOT NULL,                     -- 'open', 'matched', 'partially_matched', 'paid', 'overdue', 'reminder_1', 'reminder_2', 'reminder_3', 'written_off', 'disputed', 'archived'
    triggered_by    TEXT,                              -- 'operator', 'system_auto_match_proposal', 'system_overdue_check'
    triggered_at    TIMESTAMPTZ DEFAULT NOW(),
    payment_match_id TEXT REFERENCES payment_matches(id),
    notes           TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_status_doc ON invoice_status_history (document_id, triggered_at DESC);

-- ----------------------------------------------------------------------------
-- 5. MATCH PROPOSALS — gescorte Vorschläge, warten auf Operator
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS match_proposals (
    id              TEXT PRIMARY KEY,
    bank_transaction_id TEXT NOT NULL REFERENCES bank_transactions(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL,
    score           INTEGER NOT NULL,                  -- 0-100
    score_breakdown JSONB,
    suggested_match_type TEXT,                         -- 'full', 'partial', 'overpayment'
    language_key    TEXT,                              -- z.B. 'accounting.match.high_confidence'
    language_params JSONB,
    status          TEXT DEFAULT 'pending',            -- 'pending', 'accepted', 'rejected', 'superseded'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    decided_at      TIMESTAMPTZ,
    decided_by      TEXT,
    decision_notes  TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposals_tx ON match_proposals (bank_transaction_id);
CREATE INDEX IF NOT EXISTS idx_proposals_doc ON match_proposals (document_id);
CREATE INDEX IF NOT EXISTS idx_proposals_pending ON match_proposals (status, score DESC) WHERE status = 'pending';

-- ----------------------------------------------------------------------------
-- 6. INVOICE EXTENSION (Spalten an V4 documents-Tabelle)
-- ----------------------------------------------------------------------------
-- Wir erweitern die documents-Tabelle aus V4 um Accounting-Felder, ohne sie zu brechen.
-- Idempotent via ALTER TABLE IF EXISTS / DO blocks.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='accounting_status') THEN
        ALTER TABLE documents ADD COLUMN accounting_status TEXT DEFAULT 'open';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='paid_amount') THEN
        ALTER TABLE documents ADD COLUMN paid_amount NUMERIC(12,2) DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='outstanding_amount') THEN
        ALTER TABLE documents ADD COLUMN outstanding_amount NUMERIC(12,2);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='direction') THEN
        ALTER TABLE documents ADD COLUMN direction TEXT;  -- 'incoming' (Lieferanten-Rechnung) oder 'outgoing' (eigene Rechnung)
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='reminder_level') THEN
        ALTER TABLE documents ADD COLUMN reminder_level INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='documents' AND column_name='reminder_last_sent_at') THEN
        ALTER TABLE documents ADD COLUMN reminder_last_sent_at TIMESTAMPTZ;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_documents_accounting ON documents (accounting_status) WHERE accounting_status IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_documents_direction ON documents (direction);

-- ----------------------------------------------------------------------------
-- 7. AGING VIEW — gruppiert offene Posten nach Alter
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_invoice_aging AS
SELECT
    d.id AS document_id,
    d.document_type,
    d.direction,
    d.accounting_status,
    d.outstanding_amount,
    (CURRENT_DATE - (d.raw_text::jsonb->>'due_date')::date) AS days_overdue
FROM documents d
WHERE d.accounting_status IN ('open', 'partially_matched', 'overdue')
  AND d.outstanding_amount > 0;

-- ----------------------------------------------------------------------------
-- 8. ACCOUNTING SIGNALS — speist die Edition-Orchestratoren
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounting_signals (
    id              SERIAL PRIMARY KEY,
    organization_id TEXT,                              -- school_id, campsite_id, etc. (für Cross-Edition)
    edition         TEXT,                              -- welche Edition profitiert
    signal_key      TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    params          JSONB DEFAULT '{}'::jsonb,
    document_id     TEXT,                              -- Bezug zur Rechnung
    bank_transaction_id TEXT,                          -- Bezug zur Buchung
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT
);
CREATE INDEX IF NOT EXISTS idx_acc_signals_org ON accounting_signals (organization_id);
CREATE INDEX IF NOT EXISTS idx_acc_signals_status ON accounting_signals (status);

COMMIT;

-- ============================================================================
-- VERIFIKATION
-- ============================================================================
-- \dt
-- SELECT count(*) FROM bank_transactions;
-- SELECT count(*) FROM payment_matches WHERE revoked_at IS NULL;
-- SELECT * FROM v_invoice_aging ORDER BY days_overdue DESC LIMIT 10;
-- ============================================================================
