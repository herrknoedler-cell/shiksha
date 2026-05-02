-- ============================================================
-- SHIKSHA · KITA · Document-Upload (Foto/PDF/Scan) Migration
-- Stand: 29.04.2026
-- ============================================================

CREATE TABLE IF NOT EXISTS kita_documents (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_type   TEXT,                     -- 'anmeldevertrag' | 'krankenstand' | 'dienstplan' | 'foerderbescheid' | 'mitarbeitervertrag' | 'unknown'
    detected_subtype TEXT,                    -- z.B. 'krummelus_format' | 'AOK_krankenstand'
    raw_text        TEXT,                     -- OCR-Output
    file_path       TEXT,
    file_name       TEXT,
    file_size       INTEGER,
    file_mime       TEXT,
    file_hash       TEXT,                     -- SHA256 zur Duplikat-Erkennung
    source_type     TEXT DEFAULT 'photo',     -- 'photo' | 'pdf' | 'scan'
    status          TEXT DEFAULT 'pending',   -- 'pending' | 'reviewed' | 'applied' | 'archived'
    -- Verknüpfung zu importierten Datensätzen
    applied_at      TIMESTAMP,
    applied_to_table TEXT,                    -- z.B. 'kita_child_enrollments'
    applied_to_id   TEXT,                     -- der erzeugte/aktualisierte Datensatz
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kdoc_hash ON kita_documents(file_hash) WHERE file_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_kdoc_type ON kita_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_kdoc_status ON kita_documents(status);

CREATE TABLE IF NOT EXISTS kita_document_fields (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    document_id     TEXT REFERENCES kita_documents(id) ON DELETE CASCADE,
    field_key       TEXT NOT NULL,
    field_value     TEXT,
    confidence      DOUBLE PRECISION,
    is_user_edited  BOOLEAN DEFAULT false,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kfield_doc ON kita_document_fields(document_id);
CREATE INDEX IF NOT EXISTS idx_kfield_key ON kita_document_fields(document_id, field_key);

GRANT SELECT, INSERT, UPDATE, DELETE ON kita_documents, kita_document_fields TO shiksha;

-- Storage-Verzeichnis (wird vom Endpoint angelegt, hier nur Hinweis)
-- mkdir -p /opt/shiksha/uploads/kita/documents
