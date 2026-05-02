-- ============================================================
-- SHIKSHA · Archiv-Modul · Cross-Edition Migration
-- Stand: 30.04.2026
-- ============================================================

-- 1. Daily-Assignments: pro Person × Tag × Bereich (Mitarbeiter UND Kinder)
CREATE TABLE IF NOT EXISTS kita_daily_assignments (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    work_date       DATE NOT NULL,
    -- Person: entweder staff oder child
    person_type     TEXT NOT NULL,                  -- 'staff' | 'child'
    legacy_staff_id INTEGER,                        -- → kita_legacy_staff
    new_staff_id    TEXT,                           -- → kita_staff_members
    legacy_child_id INTEGER,                        -- → kita_legacy_children
    new_enrollment_id TEXT,                         -- → kita_child_enrollments
    -- Gruppen-Zuordnung
    group_legacy_id INTEGER,                        -- → kita_legacy_groups
    group_new_id    TEXT,                           -- → kita_groups
    -- Bereich + Status (Tortenstücke!)
    area            TEXT NOT NULL,                  -- 'vormittag'|'mittagessen'|'ruhe'|'nachmittag'|'vbz'|'pause'|'kuechendienst'
    status          TEXT NOT NULL DEFAULT 'planned', -- 'planned'|'present'|'absent'|'sick'|'vacation'|'course'|'other'
    -- Zeit-Range (optional, für genaue Tortenstück-Größe)
    time_from       TIME,
    time_to         TIME,
    -- Notizen
    note            TEXT,                           -- "Flora wird heute schon 11:30 abgeholt"
    note_visible_to_parents BOOLEAN DEFAULT false,  -- Mikronotiz für Eltern?
    -- Audit
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dassign_date ON kita_daily_assignments(work_date);
CREATE INDEX IF NOT EXISTS idx_dassign_group_legacy ON kita_daily_assignments(group_legacy_id, work_date);
CREATE INDEX IF NOT EXISTS idx_dassign_status ON kita_daily_assignments(status);

-- 2. Group-Merges: konfigurierbar, KITA-spezifisch
CREATE TABLE IF NOT EXISTS kita_group_merges (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    merged_name     TEXT NOT NULL,                  -- "Sommersprossen"
    from_group_legacy_ids INTEGER[],                -- {1, 2}
    from_group_new_ids TEXT[],                      -- {grp_xyz, grp_abc}
    -- Wann?
    valid_from_date DATE,
    valid_to_date   DATE,
    weekdays        TEXT[],                         -- {"monday","tuesday",...}
    time_from       TIME,                           -- 13:30
    time_to         TIME,                           -- 17:30
    -- Standort
    room_id         INTEGER,                        -- → kita_legacy_rooms
    notes           TEXT,
    active          BOOLEAN DEFAULT true,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- 3. Cross-Edition: Archive-Dokumente (PDFs, Bilder, JSON-Snapshots)
CREATE TABLE IF NOT EXISTS shiksha_archive_documents (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    edition         TEXT NOT NULL,                  -- 'kita' | 'accounting' | 'identity' | ...
    doc_type        TEXT NOT NULL,                  -- 'attendance_list' | 'duty_roster' | 'st_calc' | 'identity_dossier' | 'audit_report' | 'notification' | ...
    target_type     TEXT,                           -- 'group' | 'person' | 'org' | 'period' | 'global'
    target_id       TEXT,                           -- z.B. group_id, person_id, "2026-04"
    -- Datei
    file_path       TEXT NOT NULL,
    file_name       TEXT,
    file_mime       TEXT,
    file_size       INTEGER,
    file_hash       TEXT NOT NULL,                  -- SHA256 für Tamper-Detection
    -- Generation
    period_from     DATE,
    period_to       DATE,
    snapshot_for    DATE,                           -- bei Tages-PDFs
    generated_by    TEXT,                           -- 'cron' oder Mitarbeiter
    generated_at    TIMESTAMP DEFAULT NOW(),
    -- Retention (DSGVO-konform)
    retention_until DATE,                           -- z.B. 7 Jahre für Behörden-Pflicht
    legal_basis     TEXT,                           -- "KBBG §X" / "Art. 6 (1) c DSGVO"
    -- Metadata
    metadata        JSONB,                          -- frei: {generated_by, count_kinder, group_name, ...}
    -- Audit
    accessed_by     JSONB,                          -- Array von {user, timestamp, ip} bei jedem Zugriff
    is_sealed       BOOLEAN DEFAULT true,           -- nicht mehr veränderbar nach Generierung
    seal_method     TEXT DEFAULT 'sha256'           -- später: 'opentimestamps', 'blockchain'
);

CREATE INDEX IF NOT EXISTS idx_archive_edition ON shiksha_archive_documents(edition);
CREATE INDEX IF NOT EXISTS idx_archive_type ON shiksha_archive_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_archive_target ON shiksha_archive_documents(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_archive_snapshot ON shiksha_archive_documents(snapshot_for);
CREATE INDEX IF NOT EXISTS idx_archive_retention ON shiksha_archive_documents(retention_until);
CREATE INDEX IF NOT EXISTS idx_archive_hash ON shiksha_archive_documents(file_hash);

-- 4. Audit-Log: wer hat wann was gesehen/heruntergeladen
CREATE TABLE IF NOT EXISTS shiksha_archive_audit (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    archive_doc_id  TEXT REFERENCES shiksha_archive_documents(id) ON DELETE CASCADE,
    actor           TEXT,                           -- "kita-leitung" / "padagogin Mira"
    action          TEXT NOT NULL,                  -- 'view' | 'download' | 'verify_hash' | 'delete'
    ip_address      TEXT,
    user_agent      TEXT,
    occurred_at     TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_doc ON shiksha_archive_audit(archive_doc_id, occurred_at);

-- 5. Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON
  kita_daily_assignments, kita_group_merges,
  shiksha_archive_documents, shiksha_archive_audit
TO shiksha;

-- 6. Group-Merge für Krummelus (Sommer + Sprossen → Sommersprossen am NM)
-- Wird beim Pilot-Setup angelegt. Beispiel-Insert (auskommentiert):
-- INSERT INTO kita_group_merges (merged_name, from_group_legacy_ids, weekdays, time_from, time_to, notes)
-- VALUES ('Sommersprossen', ARRAY[2, 3], ARRAY['monday','tuesday','wednesday','thursday','friday'],
--         '13:30:00', '17:30:00', 'Sommer + Sprossen werden am Nachmittag zusammengelegt');
