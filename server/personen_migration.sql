-- ============================================================
-- SHIKSHA · KITA · Personen-Stammdaten Erweiterung
-- Erweitert kita_legacy_staff + kita_legacy_children um vollständige
-- Stammdaten. Idempotent (IF NOT EXISTS auf jeder Spalte).
-- Stand: 01.05.2026
-- ============================================================

-- ============================================================
-- MITARBEITER:INNEN
-- ============================================================
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS phone TEXT;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS emergency_contact TEXT;       -- "Name · Beziehung · Tel"
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS employment_start DATE;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS employment_end DATE;          -- NULL = aktiv
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS contract_type TEXT;           -- "unbefristet" / "befristet" / "geringfügig"
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS qualification TEXT;           -- "Pädagogin" / "Assistentin" / "Lehrling" / ...
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT true;
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
ALTER TABLE kita_legacy_staff ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_staff_birth_date ON kita_legacy_staff(birth_date);
CREATE INDEX IF NOT EXISTS idx_staff_active ON kita_legacy_staff(active);

-- ============================================================
-- KINDER
-- ============================================================
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS gender TEXT;               -- "w" / "m" / "d"
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS nationality TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS native_language TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS allergies TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS medications TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS medical_notes TEXT;        -- Impfstatus, Auffälligkeiten
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS dietary_notes TEXT;        -- vegetarisch, halal, ...
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS entry_date DATE;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS exit_date DATE;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS parents JSONB DEFAULT '[]'::jsonb;
   -- [{"name":"Anna F.","relation":"Mutter","phone":"...","email":"...","address":"...","primary":true}]
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS pickup_authorized JSONB DEFAULT '[]'::jsonb;
   -- [{"name":"Oma Maria","relation":"Großmutter","phone":"...","id_verified":true}]
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS emergency_contact TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS photo_consent BOOLEAN DEFAULT false;
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();
ALTER TABLE kita_legacy_children ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_children_birth_date ON kita_legacy_children(birth_date);
CREATE INDEX IF NOT EXISTS idx_children_active ON kita_legacy_children(active);
CREATE INDEX IF NOT EXISTS idx_children_entry_date ON kita_legacy_children(entry_date);

-- ============================================================
-- HINWEIS: birth_year (alt) bleibt bestehen für Backwards-Compat.
-- Beim Speichern von birth_date kopieren wir EXTRACT(YEAR FROM birth_date) → birth_year.
-- ============================================================
