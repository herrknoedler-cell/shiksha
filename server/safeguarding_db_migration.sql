-- ============================================================================
-- SHIKSHA · SAFEGUARDING MODUL · DB Migration V1 (Cross-Edition)
-- Stand: 25.04.2026
-- Idempotent.
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. PROTECTION POLICIES (Schutzkonzept pro Organisation)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS protection_policies (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,                     -- school_id, campsite_id, club_id
    organization_type TEXT NOT NULL,                   -- 'school', 'campsite', 'club'
    title           TEXT NOT NULL,
    document_id     TEXT,                              -- Foto/Scan im document.module
    valid_from      DATE,
    valid_until     DATE,
    last_review_at  DATE,
    next_review_due DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_protpol_org ON protection_policies (organization_id, organization_type);

-- ----------------------------------------------------------------------------
-- 2. PERSON PROTECTION STATUS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS person_protection_status (
    id              TEXT PRIMARY KEY,
    person_id       TEXT NOT NULL,                     -- person.id (cross-edition)
    organization_id TEXT NOT NULL,
    organization_type TEXT NOT NULL,
    role            TEXT,                              -- 'instructor', 'lifeguard', 'staff', 'volunteer'
    background_check_valid_until DATE,
    first_aid_valid_until DATE,
    rescue_swim_valid_until DATE,
    notes           TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_protstatus_person ON person_protection_status (person_id);
CREATE INDEX IF NOT EXISTS idx_protstatus_org ON person_protection_status (organization_id);

-- ----------------------------------------------------------------------------
-- 3. BACKGROUND CHECKS (Historie)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS background_checks (
    id              TEXT PRIMARY KEY,
    person_id       TEXT NOT NULL,
    type            TEXT NOT NULL,                     -- 'erweitertes Führungszeugnis', 'EHBO NL', etc.
    issued_by       TEXT,
    issued_at       DATE NOT NULL,
    valid_until     DATE NOT NULL,
    document_id     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_bgcheck_person ON background_checks (person_id);
CREATE INDEX IF NOT EXISTS idx_bgcheck_validity ON background_checks (valid_until);

-- ----------------------------------------------------------------------------
-- 4. SAFEGUARDING CONSENTS (zentralisiert, cross-edition)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_consents (
    id              TEXT PRIMARY KEY,
    subject_id      TEXT NOT NULL,                     -- person.id (Schüler, Gast, Kind)
    consent_type    TEXT NOT NULL,                     -- 'kursteilnahme', 'fotoeinverständnis', etc.
    consenter_id    TEXT NOT NULL,                     -- Guardian oder Subject selbst
    consent_text    TEXT,
    document_id     TEXT,
    given_at        TIMESTAMPTZ DEFAULT NOW(),
    valid_until     DATE,
    revoked_at      TIMESTAMPTZ,
    organization_id TEXT,
    organization_type TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_consents_subject ON safeguarding_consents (subject_id);
CREATE INDEX IF NOT EXISTS idx_consents_active ON safeguarding_consents (subject_id, consent_type) WHERE revoked_at IS NULL;

-- ----------------------------------------------------------------------------
-- 5. INCIDENT REPORTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incident_reports (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    organization_type TEXT NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL,
    reported_by     TEXT,
    severity        TEXT NOT NULL,                     -- 'low', 'mid', 'high', 'critical'
    category        TEXT,                              -- 'pool', 'playground', 'animal', 'minor_safety', 'other'
    description     TEXT NOT NULL,
    persons_involved JSONB DEFAULT '[]'::jsonb,
    follow_up       TEXT,
    status          TEXT DEFAULT 'open',               -- 'open', 'under_review', 'resolved', 'archived'
    document_id     TEXT,
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_incident_org ON incident_reports (organization_id);
CREATE INDEX IF NOT EXISTS idx_incident_status ON incident_reports (status);

-- ----------------------------------------------------------------------------
-- 6. SAFEGUARDING SIGNALS (cross-edition)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_signals (
    id              SERIAL PRIMARY KEY,
    organization_id TEXT,
    organization_type TEXT,
    edition         TEXT,                              -- ursprüngliche Edition
    signal_key      TEXT NOT NULL,
    severity        TEXT DEFAULT 'mid',
    params          JSONB DEFAULT '{}'::jsonb,
    related_person_id TEXT,
    related_entity  JSONB DEFAULT '{}'::jsonb,
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT,
    resolution_action TEXT                             -- für Severity-Lerner
);
CREATE INDEX IF NOT EXISTS idx_sg_signals_org ON safeguarding_signals (organization_id);
CREATE INDEX IF NOT EXISTS idx_sg_signals_key ON safeguarding_signals (signal_key);
CREATE INDEX IF NOT EXISTS idx_sg_signals_status ON safeguarding_signals (status);
CREATE INDEX IF NOT EXISTS idx_sg_signals_history ON safeguarding_signals (signal_key, created_at DESC);

-- ----------------------------------------------------------------------------
-- 7. PATTERN CANDIDATES (gelernte Hypothesen, NICHT aktiv)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_pattern_candidates (
    id              SERIAL PRIMARY KEY,
    pattern_type    TEXT NOT NULL,                     -- 'frequency_cluster', 'seasonal', 'cross_edition', 'recurring_entity'
    pattern_key     TEXT NOT NULL,                     -- z.B. 'safeguarding.dog_repeat_complaint.recurring_entity_familie_maier'
    description     TEXT,
    confidence      NUMERIC(3,2) NOT NULL,
    occurrences     INTEGER NOT NULL,
    related_signal_keys TEXT[] DEFAULT '{}',
    related_entities JSONB DEFAULT '{}'::jsonb,
    applicable_editions TEXT[] DEFAULT '{}',
    suggested_action TEXT,
    first_seen      TIMESTAMPTZ,
    last_seen       TIMESTAMPTZ,
    status          TEXT DEFAULT 'pending',            -- 'pending', 'promoted', 'dismissed'
    promoted_at     TIMESTAMPTZ,
    promoted_by     TEXT,
    dismissed_at    TIMESTAMPTZ,
    dismissed_by    TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (pattern_key)
);
CREATE INDEX IF NOT EXISTS idx_sg_candidates_status ON safeguarding_pattern_candidates (status);
CREATE INDEX IF NOT EXISTS idx_sg_candidates_type ON safeguarding_pattern_candidates (pattern_type);

-- ----------------------------------------------------------------------------
-- 8. PROMOTED PATTERNS (vom Operator bestätigt, aktiv)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_pattern_promoted (
    id              SERIAL PRIMARY KEY,
    candidate_id    INTEGER REFERENCES safeguarding_pattern_candidates(id),
    pattern_key     TEXT NOT NULL UNIQUE,
    description     TEXT,
    pattern_type    TEXT NOT NULL,
    active_since    TIMESTAMPTZ DEFAULT NOW(),
    deactivated_at  TIMESTAMPTZ,
    deactivated_by  TEXT,
    fires_signal    TEXT,                              -- welcher Signal-Key wird produziert
    fires_severity  TEXT DEFAULT 'mid',
    affecting_organizations JSONB DEFAULT '[]'::jsonb,
    last_fired_at   TIMESTAMPTZ,
    fire_count      INTEGER DEFAULT 0,
    metadata        JSONB DEFAULT '{}'::jsonb
);

-- ----------------------------------------------------------------------------
-- 9. SEVERITY FEEDBACK AGGREGATE
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_severity_feedback (
    signal_key      TEXT PRIMARY KEY,
    current_default_severity TEXT NOT NULL,
    feedback_count  INTEGER DEFAULT 0,
    feedback_score_sum NUMERIC(8,2) DEFAULT 0,
    proposed_severity TEXT,                            -- gesetzt wenn ein Vorschlag offen ist
    proposed_at     TIMESTAMPTZ,
    last_resolution_at TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'::jsonb
);

-- ----------------------------------------------------------------------------
-- 10. ACTION TEMPLATES (was tut SHIKSHA wenn Pattern aktiv)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_action_templates (
    id              SERIAL PRIMARY KEY,
    pattern_key     TEXT NOT NULL,
    action_type     TEXT NOT NULL,                     -- 'alert', 'pre_warn', 'block_action'
    text_key        TEXT NOT NULL,
    params_template JSONB DEFAULT '{}'::jsonb,
    timing          TEXT,                              -- 'immediate', 'X days before', etc.
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_sg_actiontmpl_pattern ON safeguarding_action_templates (pattern_key);

-- ----------------------------------------------------------------------------
-- 11. CROSS-EDITION HINTS LOG (für Demo-Zwecke und Audit)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safeguarding_cross_edition_hints (
    id              SERIAL PRIMARY KEY,
    source_edition  TEXT NOT NULL,
    target_edition  TEXT NOT NULL,
    pattern_key     TEXT NOT NULL,
    hint_text_key   TEXT NOT NULL,
    sent_at         TIMESTAMPTZ DEFAULT NOW(),
    accepted_by_target BOOLEAN DEFAULT FALSE,
    metadata        JSONB DEFAULT '{}'::jsonb
);

COMMIT;

-- ============================================================================
-- VERIFIKATION
-- ============================================================================
-- \dt safeguarding*
-- SELECT count(*) FROM safeguarding_signals;
-- SELECT signal_key, count(*) FROM safeguarding_signals GROUP BY signal_key ORDER BY count DESC;
-- SELECT * FROM safeguarding_pattern_candidates WHERE status = 'pending';
-- ============================================================================
