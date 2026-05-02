-- ============================================================
-- SHIKSHA · KITA · Compliance & Audit Modul · DB-Migration
-- Stand: 28.04.2026
-- Pilot: Vorarlberg KBBG + Stadt Dornbirn
-- ============================================================

-- 1. REGELWERK-Tabellen
CREATE TABLE IF NOT EXISTS compliance_rulesets (
    id              TEXT PRIMARY KEY,
    level           TEXT NOT NULL CHECK (level IN ('land','stadt','gemeinde','traeger')),
    jurisdiction    TEXT NOT NULL,
    name            TEXT NOT NULL,
    valid_from      DATE NOT NULL,
    valid_to        DATE,
    source_url      TEXT,
    document_hash   TEXT,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS personnel_ratios (
    id              TEXT PRIMARY KEY,
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    group_type      TEXT NOT NULL,
    subtype         TEXT,
    age_min_months  INT,
    age_max_months  INT,
    children_max    INT NOT NULL,
    children_per_caregiver_max INT,
    fte_required    NUMERIC(5,2) NOT NULL,
    qual_paedagoge_min_pct INT NOT NULL DEFAULT 50,
    qual_assistent_max_pct INT,
    qual_helfer_max_pct INT,
    hours_threshold_low  INT DEFAULT 25,
    hours_threshold_high INT DEFAULT 45,
    fte_per_extra_hour   NUMERIC(5,4) DEFAULT 0.0250,
    preparation_hours_per_week_min INT DEFAULT 16,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS funding_rates (
    id              TEXT PRIMARY KEY,
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    group_type      TEXT NOT NULL,
    rate_per_day    NUMERIC(8,2) NOT NULL,
    rate_per_month  NUMERIC(10,2),
    valid_from      DATE,
    valid_to        DATE,
    notes           TEXT
);

-- 2. KITA-Stammdaten
CREATE TABLE IF NOT EXISTS kita_groups (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL DEFAULT 'kita_pilot',
    name            TEXT NOT NULL,
    group_type      TEXT NOT NULL,
    location        TEXT,
    capacity        INT NOT NULL,
    opened_at       DATE NOT NULL,
    closed_at       DATE,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kita_child_enrollments (
    id              TEXT PRIMARY KEY,
    group_id        TEXT REFERENCES kita_groups(id) ON DELETE CASCADE,
    child_anon_id   TEXT NOT NULL,
    age_months      INT,
    enrolled_from   DATE NOT NULL,
    enrolled_to     DATE,
    booked_hours_per_week NUMERIC(4,1),
    notes           TEXT
);

CREATE INDEX IF NOT EXISTS idx_enroll_group_period
  ON kita_child_enrollments(group_id, enrolled_from, enrolled_to);

CREATE TABLE IF NOT EXISTS kita_child_attendance (
    id              TEXT PRIMARY KEY,
    enrollment_id   TEXT REFERENCES kita_child_enrollments(id) ON DELETE CASCADE,
    attendance_date DATE NOT NULL,
    hours_present   NUMERIC(4,1),
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_attend_date ON kita_child_attendance(attendance_date);

-- 3. PERSONAL
CREATE TABLE IF NOT EXISTS kita_staff_members (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL DEFAULT 'kita_pilot',
    full_name       TEXT NOT NULL,
    qualification   TEXT NOT NULL CHECK (qualification IN ('paedagoge','assistent','helfer','leitung','springer','praktikant')),
    bafep_certified BOOLEAN DEFAULT false,
    quereinstieg_years INT DEFAULT 0,
    birth_year      INT,
    hired_at        DATE,
    left_at         DATE,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS kita_staff_contracts (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES kita_staff_members(id) ON DELETE CASCADE,
    valid_from      DATE NOT NULL,
    valid_to        DATE,
    contract_pct    NUMERIC(5,2) NOT NULL,
    weekly_hours    NUMERIC(4,1),
    paid_hours      NUMERIC(4,1),
    direct_care_hours NUMERIC(4,1),
    monthly_gross   NUMERIC(10,2),
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_contract_staff_period
  ON kita_staff_contracts(staff_id, valid_from, valid_to);

CREATE TABLE IF NOT EXISTS kita_staff_assignments (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES kita_staff_members(id) ON DELETE CASCADE,
    group_id        TEXT REFERENCES kita_groups(id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    hours_planned   NUMERIC(4,1),
    hours_actual    NUMERIC(4,1),
    role            TEXT,
    is_cooking      BOOLEAN DEFAULT false,
    is_preparation  BOOLEAN DEFAULT false,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_assign_group_date ON kita_staff_assignments(group_id, work_date);

CREATE TABLE IF NOT EXISTS kita_staff_absences (
    id              TEXT PRIMARY KEY,
    staff_id        TEXT REFERENCES kita_staff_members(id) ON DELETE CASCADE,
    absent_from     DATE NOT NULL,
    absent_to       DATE,
    reason          TEXT,
    has_substitute  BOOLEAN DEFAULT false,
    substitute_id   TEXT REFERENCES kita_staff_members(id),
    notes           TEXT
);

-- 4. AUDIT-Ergebnisse
CREATE TABLE IF NOT EXISTS kita_compliance_snapshots (
    id              TEXT PRIMARY KEY,
    group_id        TEXT REFERENCES kita_groups(id) ON DELETE CASCADE,
    snapshot_month  DATE NOT NULL,
    children_avg    NUMERIC(5,2),
    fte_actual      NUMERIC(5,2),
    fte_required    NUMERIC(5,2),
    ruleset_id      TEXT REFERENCES compliance_rulesets(id),
    fte_gap         NUMERIC(5,2),
    days_undercov   INT,
    funding_at_risk_eur  NUMERIC(10,2),
    risk_level      TEXT CHECK (risk_level IN ('green','yellow','red')),
    rule_versions_used JSONB,
    computed_at     TIMESTAMP DEFAULT NOW(),
    notes           TEXT,
    UNIQUE (group_id, snapshot_month)
);

CREATE TABLE IF NOT EXISTS kita_compliance_gaps (
    id              TEXT PRIMARY KEY,
    snapshot_id     TEXT REFERENCES kita_compliance_snapshots(id) ON DELETE CASCADE,
    group_id        TEXT REFERENCES kita_groups(id) ON DELETE CASCADE,
    gap_date        DATE NOT NULL,
    gap_type        TEXT NOT NULL,
    severity        TEXT,
    children_affected INT,
    fte_missing     NUMERIC(5,2),
    eur_at_risk     NUMERIC(10,2),
    description     TEXT,
    suggested_action TEXT,
    resolved_at     TIMESTAMP,
    resolved_by     TEXT,
    resolution_note TEXT
);

-- 5. Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON
  compliance_rulesets, personnel_ratios, funding_rates,
  kita_groups, kita_child_enrollments, kita_child_attendance,
  kita_staff_members, kita_staff_contracts, kita_staff_assignments, kita_staff_absences,
  kita_compliance_snapshots, kita_compliance_gaps
TO shiksha;

-- ============================================================
-- 6. SEED-DATEN: Vorarlberg KBBG + Stadt Dornbirn
-- ============================================================

-- Regelwerk Land Vorarlberg
INSERT INTO compliance_rulesets (id, level, jurisdiction, name, valid_from, source_url, notes)
VALUES
  ('rs_kbbg_vbg_2023', 'land', 'AT-8',
   'KBBG Vorarlberg (in Kraft seit 11.09.2023)',
   '2023-09-11',
   'https://ris.bka.gv.at/Dokumente/Landesnormen/LVB40043080/LVB40043080.html',
   'Aktuelle Fassung. Updates 2025/26: Betreuungsanspruch ab vollendetem 2. Lebensjahr.'),
  ('rs_dornbirn_2025', 'stadt', 'AT-8-DOR',
   'Förderrichtlinie Stadt Dornbirn (2025)',
   '2025-01-01',
   'https://www.dornbirn.at/leben-in-dornbirn/mensch/familien/kinderbetreuung',
   'Tarife laut Land VBG, Subvention einkommensabhängig')
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name, source_url = EXCLUDED.source_url, notes = EXCLUDED.notes;

-- Personalschlüssel
INSERT INTO personnel_ratios (
  id, ruleset_id, group_type, subtype,
  age_min_months, age_max_months,
  children_max, children_per_caregiver_max,
  fte_required, qual_paedagoge_min_pct, qual_assistent_max_pct, qual_helfer_max_pct,
  preparation_hours_per_week_min, notes
) VALUES
  ('pr_kbbg_kleinkind_unter2', 'rs_kbbg_vbg_2023', 'kleinkindgruppe', 'mehrheitlich_unter_2_jahre',
   0, 36, 9, 3, 3.00, 33, 67, 0, 16,
   'Mehrheit oder mehr als 4 Kinder unter 2 Jahren: max 3 Kinder pro Betreuungsperson'),
  ('pr_kbbg_kleinkind_normal', 'rs_kbbg_vbg_2023', 'kleinkindgruppe', 'normal',
   24, 36, 12, 5, 2.40, 50, 50, 0, 16,
   'Mehrheit über 2 Jahre: max 5 Kinder pro Betreuungsperson, max 12'),
  ('pr_kbbg_kiga', 'rs_kbbg_vbg_2023', 'kiga', 'regelgruppe',
   36, 72, 25, 12, 2.10, 50, 50, 25, 16,
   'BAfEP-Absolvent muss immer anwesend sein'),
  ('pr_kbbg_hort', 'rs_kbbg_vbg_2023', 'hort', 'schulkindgruppe',
   72, 168, 30, 25, 1.20, 50, 50, 50, 12,
   'Schulkindgruppe: max 25 Kinder pro Betreuungsperson')
ON CONFLICT (id) DO UPDATE SET
  fte_required = EXCLUDED.fte_required,
  children_max = EXCLUDED.children_max,
  notes = EXCLUDED.notes;

-- Förder-Tagsätze (vorläufig — bitte gegen Förderbescheid abgleichen)
INSERT INTO funding_rates (id, ruleset_id, group_type, rate_per_day, rate_per_month, valid_from, notes)
VALUES
  ('fr_dornbirn_kleinkind_2025', 'rs_dornbirn_2025', 'kleinkindgruppe', 18.50, 380.00, '2025-01-01',
   'Schätzwert — gegen aktuellen Förderbescheid abgleichen'),
  ('fr_dornbirn_kiga_2025', 'rs_dornbirn_2025', 'kiga', 11.20, 235.00, '2025-01-01',
   'Schätzwert — gegen Förderbescheid abgleichen'),
  ('fr_dornbirn_hort_2025', 'rs_dornbirn_2025', 'hort', 7.80, 165.00, '2025-01-01',
   'Schätzwert — gegen Förderbescheid abgleichen')
ON CONFLICT (id) DO UPDATE SET
  rate_per_day = EXCLUDED.rate_per_day, rate_per_month = EXCLUDED.rate_per_month,
  notes = EXCLUDED.notes;

-- Pilot-KITA Demo-Gruppe (kann später gelöscht werden)
INSERT INTO kita_groups (id, org_id, name, group_type, location, capacity, opened_at, notes)
VALUES
  ('grp_pilot_demo', 'kita_pilot', 'Demo-Gruppe Dornbirn', 'kiga', 'Dornbirn', 25, '2020-09-01',
   'Demo-Gruppe für Tests — bitte durch echte Gruppen ersetzen')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 7. STATISTIK
-- ============================================================
SELECT 'Regelwerke' AS metric, COUNT(*)::text AS value FROM compliance_rulesets
UNION ALL SELECT 'Personalschlüssel', COUNT(*)::text FROM personnel_ratios
UNION ALL SELECT 'Förder-Tagsätze', COUNT(*)::text FROM funding_rates
UNION ALL SELECT 'KITA-Gruppen', COUNT(*)::text FROM kita_groups;
