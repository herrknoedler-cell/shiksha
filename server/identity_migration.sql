-- ============================================================
-- SHIKSHA · Identity-Modul · Cross-Edition Migration
-- Stand: 29.04.2026
-- ============================================================

-- 1. Personen (Abholpersonen, Mieter, Schüler etc.)
CREATE TABLE IF NOT EXISTS identity_persons (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    -- Stammdaten
    full_name       TEXT NOT NULL,
    birth_date      DATE,
    nationality     TEXT,
    contact_phone   TEXT,
    contact_email   TEXT,
    address         TEXT,
    -- Kontext (welche Edition + Sub-Typ)
    edition         TEXT NOT NULL,                  -- 'kita' | 'charter' | 'surfschule' | 'camping'
    person_role     TEXT,                           -- 'pickup_person' | 'renter' | 'student' | 'parent'
    -- Aus Ausweis extrahiert
    document_type   TEXT,                           -- 'personalausweis' | 'reisepass' | 'fuehrerschein'
    document_number TEXT,
    document_expires_at DATE,
    -- DSGVO
    consent_given   BOOLEAN NOT NULL DEFAULT false,
    consent_text    TEXT,                           -- "Ich erlaube SHIKSHA, ..."
    consent_at      TIMESTAMP,
    auto_delete_at  TIMESTAMP,                      -- z.B. 12 Monate nach letztem Gebrauch
    notes           TEXT,
    -- Verification-Status
    verification_status TEXT DEFAULT 'pending',     -- 'pending' | 'verified' | 'rejected'
    verified_by     TEXT,                           -- Mitarbeiter-Name
    verified_at     TIMESTAMP,
    --
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idperson_edition ON identity_persons(edition);
CREATE INDEX IF NOT EXISTS idx_idperson_status ON identity_persons(verification_status);
CREATE INDEX IF NOT EXISTS idx_idperson_expires ON identity_persons(document_expires_at);
CREATE INDEX IF NOT EXISTS idx_idperson_autodel ON identity_persons(auto_delete_at) WHERE auto_delete_at IS NOT NULL;

-- 2. Dokumente (Front, Back, Selfie + ggf. mehr)
CREATE TABLE IF NOT EXISTS identity_documents (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    person_id       TEXT REFERENCES identity_persons(id) ON DELETE CASCADE,
    doc_kind        TEXT NOT NULL,                  -- 'id_front' | 'id_back' | 'selfie' | 'passport_main'
    file_path       TEXT NOT NULL,
    file_name       TEXT,
    file_size       INTEGER,
    file_mime       TEXT,
    file_hash       TEXT,
    -- OCR-Ergebnisse
    raw_text        TEXT,
    extracted_fields JSONB,                          -- {"surname": "...", "given_names": "...", "doc_no": "...", "expiry": "..."}
    mrz_parsed      JSONB,                          -- nur bei doc_kind = 'id_back' / 'passport_main'
    ocr_confidence  NUMERIC(4,2),
    --
    captured_at     TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_iddoc_person ON identity_documents(person_id);
CREATE INDEX IF NOT EXISTS idx_iddoc_hash ON identity_documents(file_hash);

-- 3. Authorizations (welche Person darf welche Aktion?)
-- Beispiele:
--   Edition KITA: Person X darf Kind Y abholen (target_type='child', target_id=child_id)
--   Edition CHARTER: Person X darf Buchung Y starten (target_type='booking', target_id=booking_id)
--   Edition SURFSCHULE: Person X darf Kurs Y besuchen (target_type='lesson', target_id=lesson_id)
CREATE TABLE IF NOT EXISTS identity_authorizations (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    person_id       TEXT REFERENCES identity_persons(id) ON DELETE CASCADE,
    edition         TEXT NOT NULL,
    target_type     TEXT NOT NULL,                  -- 'child' | 'booking' | 'lesson' | 'global'
    target_id       TEXT,                           -- z.B. child_id, NULL bei 'global'
    role            TEXT NOT NULL,                  -- 'pickup' | 'renter' | 'participant'
    valid_from      DATE,
    valid_to        DATE,
    granted_by      TEXT,                           -- "Mutter Sarah Köb-Stadler"
    revoked_at      TIMESTAMP,
    revoke_reason   TEXT,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idauth_person ON identity_authorizations(person_id);
CREATE INDEX IF NOT EXISTS idx_idauth_target ON identity_authorizations(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_idauth_active ON identity_authorizations(edition)
  WHERE revoked_at IS NULL;

-- 4. Audit-Log (wer wann verifiziert wurde — DSGVO-Pflicht)
CREATE TABLE IF NOT EXISTS identity_audit_log (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    person_id       TEXT REFERENCES identity_persons(id) ON DELETE SET NULL,
    action          TEXT NOT NULL,                  -- 'capture' | 'verify' | 'reject' | 'access' | 'delete'
    actor           TEXT,                           -- Mitarbeiter-Name oder 'system'
    edition         TEXT,
    target_type     TEXT,
    target_id       TEXT,
    outcome         TEXT,                           -- 'success' | 'failure'
    notes           TEXT,
    occurred_at     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_idaudit_person ON identity_audit_log(person_id, occurred_at);

-- 5. Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON
  identity_persons, identity_documents, identity_authorizations, identity_audit_log
TO shiksha;
