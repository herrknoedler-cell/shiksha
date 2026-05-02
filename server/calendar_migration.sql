-- ============================================================
-- SHIKSHA · KITA · Universal-Kalender Migration
-- Stand: 30.04.2026
-- ============================================================

CREATE TABLE IF NOT EXISTS kita_calendar_events (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    -- Inhalt
    title           TEXT NOT NULL,
    description     TEXT,
    event_type      TEXT NOT NULL,            -- 'meeting' | 'birthday' | 'closing' | 'event' | 'training' | 'celebration' | 'parent_meeting' | 'other'
    -- Zeit
    start_date      DATE NOT NULL,
    start_time      TIME,                     -- NULL bei all_day
    end_date        DATE,                     -- NULL = gleiches Datum wie start_date
    end_time        TIME,
    all_day         BOOLEAN DEFAULT false,
    -- Rekurrenz
    recurrence      TEXT DEFAULT 'none',      -- 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly'
    recurrence_until DATE,
    recurrence_weekdays TEXT[],               -- bei 'weekly': z.B. {monday,tuesday}
    -- Zielgruppe
    target_type     TEXT DEFAULT 'all',       -- 'all' | 'group' | 'staff' | 'child' | 'parent'
    target_legacy_group_ids INTEGER[],
    target_legacy_staff_ids INTEGER[],
    target_legacy_child_ids INTEGER[],
    -- Sichtbarkeit
    visible_traegerin BOOLEAN DEFAULT true,
    visible_paedagogin BOOLEAN DEFAULT true,
    visible_eltern BOOLEAN DEFAULT false,
    -- Visualisierung
    color           TEXT,                     -- override default farbe
    location        TEXT,
    -- Auto-generated?
    auto_source     TEXT,                     -- 'birthday_from_child' | 'closing_holiday' | NULL
    auto_source_id  TEXT,                     -- Referenz zur Quelle
    -- Audit
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_calevent_date ON kita_calendar_events(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_calevent_type ON kita_calendar_events(event_type);
CREATE INDEX IF NOT EXISTS idx_calevent_recur ON kita_calendar_events(recurrence) WHERE recurrence != 'none';
CREATE INDEX IF NOT EXISTS idx_calevent_auto ON kita_calendar_events(auto_source, auto_source_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON kita_calendar_events TO shiksha;

-- Beispiel: Standard-Schließtage Vorarlberg/Österreich (lassen wir leer, User kann hinzufügen)
