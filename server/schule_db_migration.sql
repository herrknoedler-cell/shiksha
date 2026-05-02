-- ============================================================================
-- SHIKSHA · SCHULE.EDITION · DB Migration V1
-- Stand: 25.04.2026
-- Ziel-DB: shiksha (PostgreSQL 16 auf 88.99.174.186)
-- Ausführen via:
--   sudo -u postgres psql -d shiksha -f /opt/shiksha/schule_db_migration.sql
-- Idempotent (alle CREATE mit IF NOT EXISTS)
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. SCHOOLS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schools (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    edition         TEXT NOT NULL DEFAULT 'schule.shiksha',
    type            TEXT NOT NULL,                  -- 'yoga', 'surf', 'ski', 'dance', 'riding', 'climbing'
    primary_address JSONB,
    secondary_locations JSONB DEFAULT '[]'::jsonb,
    contact         JSONB,
    uid_number      TEXT,
    reg_number      TEXT,
    tax_number      TEXT,
    bank_account    JSONB,
    business_hours  JSONB,
    weather_dependent BOOLEAN DEFAULT FALSE,
    has_minors      BOOLEAN DEFAULT FALSE,
    insurance_info  JSONB,
    weather_thresholds JSONB,
    rooms           JSONB DEFAULT '[]'::jsonb,
    tags            JSONB DEFAULT '[]'::jsonb,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_schools_type ON schools (type);
CREATE INDEX IF NOT EXISTS idx_schools_has_minors ON schools (has_minors) WHERE has_minors = TRUE;

-- ----------------------------------------------------------------------------
-- 2. GUARDIANS  (vor students wegen FK)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guardians (
    id              TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL,
    contact         JSONB,
    related_students TEXT[] DEFAULT '{}',
    consent_history JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. STUDENTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    full_name       TEXT NOT NULL,
    birthdate       DATE,
    is_minor        BOOLEAN GENERATED ALWAYS AS (
                        birthdate IS NOT NULL
                        AND birthdate > (CURRENT_DATE - INTERVAL '18 years')
                    ) STORED,
    guardian_ids    TEXT[] DEFAULT '{}',
    contact         JSONB,
    language        TEXT DEFAULT 'de',
    level           JSONB DEFAULT '{}'::jsonb,        -- pro Disziplin
    consent_records JSONB DEFAULT '[]'::jsonb,
    medical_notes   TEXT,
    wetsuit_size    TEXT,                              -- für Surf
    first_visit     DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_students_school ON students (school_id);
CREATE INDEX IF NOT EXISTS idx_students_minor ON students (is_minor) WHERE is_minor = TRUE;
CREATE INDEX IF NOT EXISTS idx_students_name ON students USING gin (to_tsvector('simple', full_name));

-- ----------------------------------------------------------------------------
-- 4. INSTRUCTORS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instructors (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    full_name       TEXT NOT NULL,
    role            TEXT,
    contact         JSONB,
    languages       TEXT[] DEFAULT ARRAY['de'],
    licenses        JSONB DEFAULT '[]'::jsonb,         -- [{type, level, valid_until, issued_by}]
    background_check JSONB,
    specialties     TEXT[] DEFAULT '{}',
    availability    JSONB,
    hourly_rate     NUMERIC(10,2),
    since           DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_instructors_school ON instructors (school_id);

-- ----------------------------------------------------------------------------
-- 5. COURSES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type            TEXT,
    level           TEXT,
    capacity_min    INTEGER DEFAULT 1,
    capacity_max    INTEGER DEFAULT 99,
    price           NUMERIC(10,2),
    currency        TEXT DEFAULT 'EUR',
    duration_minutes INTEGER,
    weather_dependent BOOLEAN DEFAULT FALSE,
    status          TEXT NOT NULL DEFAULT 'planned',  -- 'planned', 'enrollment_open', 'running', 'completed', 'cancelled', 'on_demand'
    schedule_pattern TEXT,
    instructor_id   TEXT REFERENCES instructors(id),
    start_date      DATE,
    end_date        DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_courses_school ON courses (school_id);
CREATE INDEX IF NOT EXISTS idx_courses_status ON courses (status);

-- ----------------------------------------------------------------------------
-- 6. COURSE_SESSIONS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS course_sessions (
    id              TEXT PRIMARY KEY,
    course_id       TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    scheduled_at    TIMESTAMPTZ NOT NULL,
    location        JSONB,
    instructor_id   TEXT REFERENCES instructors(id),
    status          TEXT NOT NULL DEFAULT 'scheduled', -- 'scheduled', 'running', 'completed', 'weather_postponed', 'cancelled'
    postponement_reason TEXT,
    rescheduled_to  TIMESTAMPTZ,
    expected_attendees TEXT[] DEFAULT '{}',
    actual_attendance JSONB DEFAULT '{}'::jsonb,
    notes           TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sessions_course ON course_sessions (course_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON course_sessions (status);
CREATE INDEX IF NOT EXISTS idx_sessions_scheduled ON course_sessions (scheduled_at);

-- ----------------------------------------------------------------------------
-- 7. ENROLLMENTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS enrollments (
    id              TEXT PRIMARY KEY,
    student_id      TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    course_id       TEXT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'inquiry',   -- 'inquiry', 'pending_consent', 'confirmed', 'cancelled', 'waitlist'
    consent_status  TEXT,                              -- 'all_valid', 'consent_partial', 'consent_pending', 'consent_missing'
    medical_clearance JSONB,
    trial_class_session_id TEXT,
    enrolled_at     TIMESTAMPTZ DEFAULT NOW(),
    cancelled_at    TIMESTAMPTZ,
    cancellation_reason TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_enroll_student ON enrollments (student_id);
CREATE INDEX IF NOT EXISTS idx_enroll_course ON enrollments (course_id);
CREATE INDEX IF NOT EXISTS idx_enroll_status ON enrollments (status);

-- ----------------------------------------------------------------------------
-- 8. PACKAGES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS package_templates (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    count           INTEGER NOT NULL,                  -- -1 = unbegrenzt
    price           NUMERIC(10,2) NOT NULL,
    currency        TEXT DEFAULT 'EUR',
    validity_days   INTEGER NOT NULL,
    applicable_course_types TEXT[] DEFAULT '{"all"}',
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS package_instances (
    id              TEXT PRIMARY KEY,
    template_id     TEXT NOT NULL REFERENCES package_templates(id),
    student_id      TEXT NOT NULL REFERENCES students(id),
    remaining_count INTEGER NOT NULL,
    purchased_at    TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',    -- 'active', 'paused', 'consumed', 'expired', 'refunded'
    purchase_document_id TEXT,                         -- Link zur Rechnung im document.module
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_pkginst_student ON package_instances (student_id);
CREATE INDEX IF NOT EXISTS idx_pkginst_status ON package_instances (status);
CREATE INDEX IF NOT EXISTS idx_pkginst_expires ON package_instances (expires_at) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS package_consumptions (
    id              TEXT PRIMARY KEY,
    package_instance_id TEXT NOT NULL REFERENCES package_instances(id),
    course_session_id TEXT REFERENCES course_sessions(id),
    consumed_at     TIMESTAMPTZ DEFAULT NOW(),
    note            TEXT
);
CREATE INDEX IF NOT EXISTS idx_pkgcons_inst ON package_consumptions (package_instance_id);

-- ----------------------------------------------------------------------------
-- 9. WEATHER WINDOWS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weather_windows (
    id              TEXT PRIMARY KEY,
    course_session_id TEXT NOT NULL REFERENCES course_sessions(id) ON DELETE CASCADE,
    forecast_data   JSONB,                             -- {wind_kn, wind_dir, wave_m, tide, source}
    decision_required_at TIMESTAMPTZ,
    decision        TEXT,                              -- 'go', 'no_go', 'postpone', 'pending'
    decided_by      TEXT REFERENCES instructors(id),
    decided_at      TIMESTAMPTZ,
    alternative_plan TEXT,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_weather_session ON weather_windows (course_session_id);

-- ----------------------------------------------------------------------------
-- 10. EQUIPMENT (für Surf besonders, aber generisch)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS equipment (
    id              TEXT PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,                     -- 'board', 'wetsuit', 'mat', 'block', etc.
    model           TEXT,
    size            TEXT,
    status          TEXT DEFAULT 'available',          -- 'available', 'in_use', 'damaged', 'retired'
    loaned_to_student_id TEXT REFERENCES students(id),
    loaned_to_session_id TEXT REFERENCES course_sessions(id),
    loaned_until    TIMESTAMPTZ,
    purchased_at    DATE,
    damage_note     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_equipment_school ON equipment (school_id);
CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment (status);

-- ----------------------------------------------------------------------------
-- 11. SCHULE_SIGNALS (für Pattern/State-Generierung)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schule_signals (
    id              SERIAL PRIMARY KEY,
    school_id       TEXT REFERENCES schools(id),
    signal_key      TEXT NOT NULL,                     -- 'schule.weather.threshold_breach' etc.
    severity        TEXT DEFAULT 'info',               -- 'high', 'mid', 'low', 'info'
    params          JSONB DEFAULT '{}'::jsonb,
    related_entities JSONB DEFAULT '{}'::jsonb,        -- {student_id?, instructor_id?, session_id?}
    status          TEXT DEFAULT 'open',               -- 'open', 'acknowledged', 'resolved', 'ignored'
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT
);
CREATE INDEX IF NOT EXISTS idx_signals_school ON schule_signals (school_id);
CREATE INDEX IF NOT EXISTS idx_signals_status ON schule_signals (status);
CREATE INDEX IF NOT EXISTS idx_signals_created ON schule_signals (created_at DESC);

-- ----------------------------------------------------------------------------
-- 12. SCHOOL_STATE_SNAPSHOTS (analog ClubState)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS school_state_snapshots (
    id              SERIAL PRIMARY KEY,
    school_id       TEXT REFERENCES schools(id),
    summary         TEXT,                              -- 1-2 Sätze in natürlicher Sprache
    patterns        JSONB DEFAULT '[]'::jsonb,
    uncertainties   JSONB DEFAULT '[]'::jsonb,
    recommended_focus JSONB DEFAULT '[]'::jsonb,
    pattern_count   INTEGER DEFAULT 0,
    signal_count    INTEGER DEFAULT 0,
    as_of           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_state_school ON school_state_snapshots (school_id, as_of DESC);

-- ----------------------------------------------------------------------------
-- 13. SUPPLIERS (kann auch in customers/partnership-Tabelle, hier separat für SCHULE-Bezug)
-- Wird bei Bedarf an existierende `customers`-Tabelle (V4) gemappt.
-- ----------------------------------------------------------------------------
-- (Verwende customers-Tabelle aus V4, ergänze nur Verknüpfung)
CREATE TABLE IF NOT EXISTS school_supplier_links (
    id              SERIAL PRIMARY KEY,
    school_id       TEXT NOT NULL REFERENCES schools(id) ON DELETE CASCADE,
    supplier_customer_id TEXT NOT NULL,                -- referenziert customers.id (V4)
    relationship_type TEXT,                            -- 'ausstatter', 'versicherung', 'behörde', 'kooperationspartner'
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 14. CONFIG: Edition registrieren
-- ----------------------------------------------------------------------------
-- (sofern entities-Tabelle bereits existiert, hier den Edition-Eintrag setzen)
-- INSERT INTO entities (id, entity_type, ...) VALUES (...) ON CONFLICT DO NOTHING;
-- → wird im Python-Bootstrap-Script gemacht, nicht im SQL

COMMIT;

-- ============================================================================
-- VERIFIKATION
-- ============================================================================
-- Nach Ausführung:
--   \dt
--   SELECT count(*) FROM schools;
--   SELECT * FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'schule%' OR table_name IN ('schools','students','instructors','courses','course_sessions','enrollments','package_templates','package_instances','weather_windows','equipment');
-- ============================================================================
