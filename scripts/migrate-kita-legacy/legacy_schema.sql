-- ============================================================
-- SHIKSHA · KITA · Legacy-Schema in PostgreSQL
-- 1:1 Kopie der alten SQLite-Tabellen
-- Stand: 29.04.2026
-- ============================================================

-- DROP IF EXISTS für saubere Re-Migration
DROP TABLE IF EXISTS kita_legacy_request_responses CASCADE;
DROP TABLE IF EXISTS kita_legacy_requests CASCADE;
DROP TABLE IF EXISTS kita_legacy_observations CASCADE;
DROP TABLE IF EXISTS kita_legacy_incidents CASCADE;
DROP TABLE IF EXISTS kita_legacy_time_entries CASCADE;
DROP TABLE IF EXISTS kita_legacy_child_absence CASCADE;
DROP TABLE IF EXISTS kita_legacy_child_attendance CASCADE;
DROP TABLE IF EXISTS kita_legacy_daily_sessions CASCADE;
DROP TABLE IF EXISTS kita_legacy_children CASCADE;
DROP TABLE IF EXISTS kita_legacy_staff CASCADE;
DROP TABLE IF EXISTS kita_legacy_groups CASCADE;
DROP TABLE IF EXISTS kita_legacy_rooms CASCADE;
DROP TABLE IF EXISTS kita_legacy_areas CASCADE;

CREATE TABLE kita_legacy_areas (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    icon VARCHAR(16),
    color VARCHAR(16),
    sort_order INTEGER NOT NULL DEFAULT 0,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_rooms (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    capacity INTEGER,
    notes TEXT,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    capacity INTEGER NOT NULL,
    room VARCHAR(100),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_staff (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(32) NOT NULL,
    group_id INTEGER REFERENCES kita_legacy_groups(id),
    employment_type VARCHAR(24) NOT NULL,
    weekly_hours FLOAT,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_children (
    id SERIAL PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    birth_year INTEGER,
    group_id INTEGER REFERENCES kita_legacy_groups(id),
    active BOOLEAN NOT NULL DEFAULT true,
    notes_safeguarding TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_daily_sessions (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    group_id INTEGER NOT NULL REFERENCES kita_legacy_groups(id),
    planned_staff_count INTEGER NOT NULL,
    actual_staff_count INTEGER NOT NULL,
    children_expected INTEGER NOT NULL,
    children_present INTEGER NOT NULL,
    handover_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
CREATE INDEX ix_legacy_sessions_date ON kita_legacy_daily_sessions(date);

CREATE TABLE kita_legacy_child_attendance (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    child_id INTEGER NOT NULL REFERENCES kita_legacy_children(id),
    status VARCHAR(16) NOT NULL,
    planned_dropoff TIME,
    planned_pickup TIME,
    actual_arrival TIMESTAMP,
    actual_departure TIMESTAMP,
    picked_up_by VARCHAR(120),
    note TEXT
);
CREATE INDEX ix_legacy_attendance_date ON kita_legacy_child_attendance(date);

CREATE TABLE kita_legacy_child_absence (
    id SERIAL PRIMARY KEY,
    child_id INTEGER NOT NULL REFERENCES kita_legacy_children(id),
    from_date DATE NOT NULL,
    to_date DATE,
    reason_type VARCHAR(24) NOT NULL,
    reason_detail TEXT,
    reportable_disease BOOLEAN NOT NULL DEFAULT false,
    reported_by_staff_id INTEGER REFERENCES kita_legacy_staff(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_time_entries (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL REFERENCES kita_legacy_staff(id),
    date DATE NOT NULL,
    hours_worked FLOAT,
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_observations (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES kita_legacy_children(id),
    staff_id INTEGER REFERENCES kita_legacy_staff(id),
    area_id INTEGER REFERENCES kita_legacy_areas(id),
    date DATE NOT NULL,
    text TEXT,
    informed_parents BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_incidents (
    id SERIAL PRIMARY KEY,
    child_id INTEGER REFERENCES kita_legacy_children(id),
    staff_id INTEGER REFERENCES kita_legacy_staff(id),
    date DATE NOT NULL,
    severity VARCHAR(24),
    description TEXT,
    resolved BOOLEAN DEFAULT false,
    informed_parents BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_requests (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    body TEXT,
    target VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE kita_legacy_request_responses (
    id SERIAL PRIMARY KEY,
    request_id INTEGER NOT NULL REFERENCES kita_legacy_requests(id),
    response TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

GRANT SELECT, INSERT, UPDATE, DELETE ON
  kita_legacy_areas, kita_legacy_rooms, kita_legacy_groups,
  kita_legacy_staff, kita_legacy_children,
  kita_legacy_daily_sessions, kita_legacy_child_attendance,
  kita_legacy_child_absence, kita_legacy_time_entries,
  kita_legacy_observations, kita_legacy_incidents,
  kita_legacy_requests, kita_legacy_request_responses
TO shiksha;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO shiksha;
