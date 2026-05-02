-- ============================================================================
-- SHIKSHA · CAMPING.EDITION · DB Migration V1
-- Stand: 25.04.2026
-- Ziel-DB: shiksha (PostgreSQL 16 auf 88.99.174.186)
-- Ausführen via:
--   sudo -u postgres psql -d shiksha -f /opt/shiksha/camping_db_migration.sql
-- Idempotent (alle CREATE mit IF NOT EXISTS)
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- 1. CAMPSITES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campsites (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    edition         TEXT NOT NULL DEFAULT 'camping.shiksha',
    type            TEXT,                              -- 'family + glamping', 'outdoor + dauer­camper', etc.
    primary_address JSONB,
    contact         JSONB,
    uid_number      TEXT,
    tax_number      TEXT,
    reg_number      TEXT,
    bank_account    JSONB,
    season          JSONB,
    capacities      JSONB,
    infrastructure  TEXT[] DEFAULT '{}',
    weather_dependent BOOLEAN DEFAULT TRUE,
    has_minors      BOOLEAN DEFAULT FALSE,
    has_pool        BOOLEAN DEFAULT FALSE,
    has_playground  BOOLEAN DEFAULT FALSE,
    dog_friendly    BOOLEAN DEFAULT FALSE,
    languages_supported TEXT[] DEFAULT ARRAY['de'],
    insurance_info  JSONB,
    behoerden_auflagen TEXT[] DEFAULT '{}',
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_campsites_pool ON campsites (has_pool) WHERE has_pool = TRUE;
CREATE INDEX IF NOT EXISTS idx_campsites_dog ON campsites (dog_friendly) WHERE dog_friendly = TRUE;

-- ----------------------------------------------------------------------------
-- 2. PITCHES
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pitches (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,                     -- 'A01', 'B07' etc.
    category        TEXT NOT NULL,                     -- 'komfort', 'standard', 'naturplatz', 'dauer­camper', 'service', 'glamping'
    size_m2         INTEGER,
    electricity_amp INTEGER DEFAULT 0,                 -- 0 = keiner, 10, 16
    water           BOOLEAN DEFAULT FALSE,
    drain           BOOLEAN DEFAULT FALSE,
    shadow          TEXT,                              -- 'voll', 'halb', 'kein'
    dog_allowed     BOOLEAN DEFAULT FALSE,
    view            TEXT,
    status          TEXT DEFAULT 'available',          -- 'available', 'occupied', 'maintenance', 'blocked'
    metadata        JSONB DEFAULT '{}'::jsonb,
    UNIQUE (campsite_id, label)
);
CREATE INDEX IF NOT EXISTS idx_pitches_campsite ON pitches (campsite_id);
CREATE INDEX IF NOT EXISTS idx_pitches_status ON pitches (status);

-- ----------------------------------------------------------------------------
-- 3. ACCOMMODATIONS (Mobilheim, Glamping)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS accommodations (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,                     -- 'mobile_home', 'glamping_tent', 'cabin'
    name            TEXT,
    size_m2         INTEGER,
    beds            INTEGER,
    amenities       TEXT[] DEFAULT '{}',
    weekly_high     NUMERIC(10,2),
    weekly_low      NUMERIC(10,2),
    dog_allowed     BOOLEAN DEFAULT FALSE,
    status          TEXT DEFAULT 'available',
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_accom_campsite ON accommodations (campsite_id);

-- ----------------------------------------------------------------------------
-- 4. GUARDIANS (Camping-spezifisch — separater Table von schule)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guardians_camping (
    id              TEXT PRIMARY KEY,
    full_name       TEXT NOT NULL,
    contact         JSONB,
    related_minors  TEXT[] DEFAULT '{}',
    consent_history JSONB DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 5. GUESTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guests (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT REFERENCES campsites(id),
    full_name       TEXT NOT NULL,
    primary_adult   TEXT,
    address         JSONB,
    contact         JSONB,
    language        TEXT DEFAULT 'de',
    vehicle_plate   TEXT,
    is_minor        BOOLEAN DEFAULT FALSE,
    birthdate       DATE,
    guardian_ids    TEXT[] DEFAULT '{}',
    first_visit     DATE,
    visit_count     INTEGER DEFAULT 0,                 -- für journey.repeat_pattern
    last_visit      DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_guests_campsite ON guests (campsite_id);
CREATE INDEX IF NOT EXISTS idx_guests_lastvisit ON guests (last_visit);
CREATE INDEX IF NOT EXISTS idx_guests_repeat ON guests (visit_count) WHERE visit_count >= 3;

-- ----------------------------------------------------------------------------
-- 6. RESERVATIONS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reservations (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id),
    guest_id        TEXT NOT NULL REFERENCES guests(id),
    pitch_id        TEXT REFERENCES pitches(id),
    accommodation_id TEXT REFERENCES accommodations(id),
    from_date       DATE NOT NULL,
    to_date         DATE NOT NULL,
    persons         INTEGER DEFAULT 1,
    minors_count    INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'inquiry',   -- 'inquiry', 'pending_payment', 'confirmed', 'cancelled', 'no_show'
    deposit_paid    BOOLEAN DEFAULT FALSE,
    deposit_due     DATE,
    total_amount    NUMERIC(10,2),
    type            TEXT,                              -- 'standard', 'saisonpacht'
    cancellation_record JSONB,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CHECK (pitch_id IS NOT NULL OR accommodation_id IS NOT NULL),
    CHECK (to_date > from_date)
);
CREATE INDEX IF NOT EXISTS idx_resv_campsite ON reservations (campsite_id);
CREATE INDEX IF NOT EXISTS idx_resv_guest ON reservations (guest_id);
CREATE INDEX IF NOT EXISTS idx_resv_dates ON reservations (from_date, to_date);
CREATE INDEX IF NOT EXISTS idx_resv_status ON reservations (status);

-- ----------------------------------------------------------------------------
-- 7. STAYS (laufender Aufenthalt)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stays (
    id              TEXT PRIMARY KEY,
    reservation_id  TEXT REFERENCES reservations(id),
    campsite_id     TEXT NOT NULL REFERENCES campsites(id),
    guest_id        TEXT NOT NULL REFERENCES guests(id),
    pitch_id        TEXT REFERENCES pitches(id),
    accommodation_id TEXT REFERENCES accommodations(id),
    check_in        DATE NOT NULL,
    check_out       DATE,
    persons         INTEGER DEFAULT 1,
    minors_count    INTEGER DEFAULT 0,
    dog             TEXT,
    status          TEXT DEFAULT 'running',            -- 'running', 'completed', 'cancelled_during'
    notes           TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_stays_campsite ON stays (campsite_id);
CREATE INDEX IF NOT EXISTS idx_stays_running ON stays (status) WHERE status = 'running';

-- ----------------------------------------------------------------------------
-- 8. MELDESCHEINE (behördlich erforderlich)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meldescheine (
    id              TEXT PRIMARY KEY,
    stay_id         TEXT NOT NULL REFERENCES stays(id) ON DELETE CASCADE,
    person_data     JSONB NOT NULL,                    -- Name, Geburtsdatum, Anschrift, Pass-Nr.
    signed_at       TIMESTAMPTZ,
    signed_by       TEXT,
    document_id     TEXT,                              -- Foto/Scan im document.module
    retention_until DATE,                              -- Aufbewahrungsfrist
    anonymized_at   TIMESTAMPTZ                        -- Datum der Anonymisierung (Löschpflicht)
);

-- ----------------------------------------------------------------------------
-- 9. PRICING
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pricing_periods (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    from_date_pattern TEXT,                            -- 'MM-DD' für Saison-Wiederkehr
    to_date_pattern   TEXT,
    factor          NUMERIC(4,2) DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS pricing_rules (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    pitch_category  TEXT,
    rule_key        TEXT NOT NULL,                     -- 'komfort_2pers', 'kurtaxe_per_person_per_night', etc.
    base_price_eur  NUMERIC(10,2),
    metadata        JSONB DEFAULT '{}'::jsonb
);

-- ----------------------------------------------------------------------------
-- 10. UTILITY METERING
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meters (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    pitch_id        TEXT REFERENCES pitches(id),
    accommodation_id TEXT REFERENCES accommodations(id),
    type            TEXT NOT NULL,                     -- 'electricity', 'water'
    serial          TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS utility_readings (
    id              TEXT PRIMARY KEY,
    meter_id        TEXT NOT NULL REFERENCES meters(id) ON DELETE CASCADE,
    reading_value   NUMERIC(12,2) NOT NULL,
    unit            TEXT DEFAULT 'kWh',
    read_at         TIMESTAMPTZ DEFAULT NOW(),
    read_by         TEXT,
    document_id     TEXT,                              -- Foto-Beleg im document.module
    consumption_since_previous NUMERIC(12,2),
    expected_consumption NUMERIC(12,2),
    anomaly_flag    BOOLEAN DEFAULT FALSE,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_readings_meter ON utility_readings (meter_id, read_at DESC);
CREATE INDEX IF NOT EXISTS idx_readings_anomaly ON utility_readings (anomaly_flag) WHERE anomaly_flag = TRUE;

-- ----------------------------------------------------------------------------
-- 11. SERVICES (Brötchen, Wasch, Sauna)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS services (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    type            TEXT,                              -- 'breakfast', 'wash', 'sauna', 'rental_bike', 'rental_boat'
    base_price_eur  NUMERIC(10,2),
    bookable_in_advance BOOLEAN DEFAULT TRUE,
    metadata        JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS service_consumptions (
    id              TEXT PRIMARY KEY,
    service_id      TEXT NOT NULL REFERENCES services(id),
    stay_id         TEXT REFERENCES stays(id),
    guest_id        TEXT REFERENCES guests(id),
    consumed_at     TIMESTAMPTZ DEFAULT NOW(),
    quantity        INTEGER DEFAULT 1,
    total_eur       NUMERIC(10,2),
    notes           TEXT
);

-- ----------------------------------------------------------------------------
-- 12. GUEST REQUESTS (Anfragen, Beschwerden)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS guest_requests (
    id              TEXT PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id),
    stay_id         TEXT REFERENCES stays(id),
    guest_id        TEXT REFERENCES guests(id),
    request_type    TEXT,                              -- 'question', 'complaint', 'service', 'incident'
    subject         TEXT,
    body            TEXT,
    severity        TEXT DEFAULT 'low',
    status          TEXT DEFAULT 'open',               -- 'open', 'in_progress', 'resolved', 'closed'
    received_at     TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    document_id     TEXT,                              -- falls Foto-Beleg
    metadata        JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_requests_status ON guest_requests (status, severity);
CREATE INDEX IF NOT EXISTS idx_requests_campsite ON guest_requests (campsite_id);

-- ----------------------------------------------------------------------------
-- 13. JOURNEY EVENTS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS journey_events (
    id              SERIAL PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id),
    guest_id        TEXT REFERENCES guests(id),
    stay_id         TEXT REFERENCES stays(id),
    stage           TEXT NOT NULL,                     -- 'inquiry', 'booked', 'pre_stay', 'arrival', 'stay', 'departure', 'post_stay'
    event_key       TEXT NOT NULL,                     -- 'pre_arrival_info_sent', 'silent_during_stay_detected', etc.
    event_data      JSONB DEFAULT '{}'::jsonb,
    triggered_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_journey_guest ON journey_events (guest_id, triggered_at DESC);

-- ----------------------------------------------------------------------------
-- 14. CAMPING_SIGNALS
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS camping_signals (
    id              SERIAL PRIMARY KEY,
    campsite_id     TEXT REFERENCES campsites(id),
    signal_key      TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    polarity        TEXT DEFAULT 'neutral',            -- 'positiv', 'neutral', 'negativ'
    params          JSONB DEFAULT '{}'::jsonb,
    related_entities JSONB DEFAULT '{}'::jsonb,
    status          TEXT DEFAULT 'open',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolved_by     TEXT
);
CREATE INDEX IF NOT EXISTS idx_camp_signals_campsite ON camping_signals (campsite_id);
CREATE INDEX IF NOT EXISTS idx_camp_signals_status ON camping_signals (status);

-- ----------------------------------------------------------------------------
-- 15. CAMP_STATE_SNAPSHOTS (analog ClubState/SchoolState)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS camp_state_snapshots (
    id              SERIAL PRIMARY KEY,
    campsite_id     TEXT REFERENCES campsites(id),
    summary         TEXT,
    patterns        JSONB DEFAULT '[]'::jsonb,
    uncertainties   JSONB DEFAULT '[]'::jsonb,
    recommended_focus JSONB DEFAULT '[]'::jsonb,
    pattern_count   INTEGER DEFAULT 0,
    signal_count    INTEGER DEFAULT 0,
    occupancy_pct   NUMERIC(5,2),                      -- aktuelle Belegung %
    as_of           TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_camp_state ON camp_state_snapshots (campsite_id, as_of DESC);

-- ----------------------------------------------------------------------------
-- 16. SUPPLIER LINKS (auf customers-Tabelle aus V4)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS campsite_supplier_links (
    id              SERIAL PRIMARY KEY,
    campsite_id     TEXT NOT NULL REFERENCES campsites(id) ON DELETE CASCADE,
    supplier_customer_id TEXT NOT NULL,
    relationship_type TEXT,                            -- 'lieferant_food', 'versorger_strom', 'behoerde', etc.
    delivery_pattern TEXT,                             -- 'täglich 06:30', 'monatlich', etc.
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;

-- ============================================================================
-- VERIFIKATION
-- ============================================================================
-- \dt
-- SELECT count(*) FROM campsites;
-- SELECT table_name FROM information_schema.tables
--   WHERE table_schema='public' AND (
--     table_name LIKE 'camp%' OR table_name IN ('pitches','accommodations','guests','reservations','stays','meldescheine','meters','utility_readings','services','service_consumptions','guest_requests','journey_events','guardians_camping')
--   ) ORDER BY table_name;
-- ============================================================================
