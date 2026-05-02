-- ============================================================
-- SHIKSHA · Begrüßung & Insights
-- - weekly_themes: vom Trägerin/Leitung gesetzte Wochen-Fokusse
-- - shiksha_insights: vom System statistisch generierte Hinweise
-- - shiksha_insight_dismisses: pro User dismissed
-- ============================================================

CREATE TABLE IF NOT EXISTS weekly_themes (
    id          SERIAL PRIMARY KEY,
    week_start  DATE NOT NULL,                 -- Montag der Woche
    theme       TEXT NOT NULL,
    set_by      TEXT,
    note        TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(week_start)
);

CREATE INDEX IF NOT EXISTS idx_weekly_themes_week ON weekly_themes(week_start);

CREATE TABLE IF NOT EXISTS shiksha_insights (
    id              SERIAL PRIMARY KEY,
    generated_at    TIMESTAMP DEFAULT NOW(),
    audience        TEXT NOT NULL DEFAULT 'all',   -- 'traegerin' | 'paedagogin' | 'all'
    severity        TEXT DEFAULT 'info',           -- 'info' | 'notice' | 'warn'
    icon            TEXT,
    title           TEXT NOT NULL,
    body            TEXT,
    action_label    TEXT,
    action_url      TEXT,
    valid_until     DATE,
    insight_key     TEXT UNIQUE,                   -- Idempotenz-Schlüssel
    metadata        JSONB DEFAULT '{}'::jsonb,
    active          BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_insights_audience ON shiksha_insights(audience, active, valid_until);
CREATE INDEX IF NOT EXISTS idx_insights_key ON shiksha_insights(insight_key);

CREATE TABLE IF NOT EXISTS shiksha_insight_dismisses (
    insight_id      INTEGER REFERENCES shiksha_insights(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL,
    dismissed_at    TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (insight_id, user_id)
);

GRANT SELECT, INSERT, UPDATE, DELETE ON weekly_themes TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON shiksha_insights TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON shiksha_insight_dismisses TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE weekly_themes_id_seq TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE shiksha_insights_id_seq TO shiksha;
