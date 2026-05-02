-- ============================================================
-- SHIKSHA · Dashboard-Layouts pro User
-- Gridstack-kompatibles JSON-Layout, persistiert pro
-- (user_id, dashboard_key)-Paar.
-- ============================================================

CREATE TABLE IF NOT EXISTS dashboard_layouts (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,           -- z.B. "traegerin", "paedagogin-mira", oder UUID
    dashboard_key   TEXT NOT NULL,           -- "traegerin" | "paedagogin" | "board"
    layout          JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- layout = Array von Cards: [{id, x, y, w, h, type, config}, ...]
    edit_mode       BOOLEAN DEFAULT false,
    updated_at      TIMESTAMP DEFAULT NOW(),
    created_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, dashboard_key)
);

CREATE INDEX IF NOT EXISTS idx_dashboard_user ON dashboard_layouts(user_id);
CREATE INDEX IF NOT EXISTS idx_dashboard_key ON dashboard_layouts(dashboard_key);

GRANT SELECT, INSERT, UPDATE, DELETE ON dashboard_layouts TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE dashboard_layouts_id_seq TO shiksha;
