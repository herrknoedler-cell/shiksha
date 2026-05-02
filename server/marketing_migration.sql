-- ============================================================
-- SHIKSHA · Marketing-Sites
-- Multi-Tenant: pro Kunde eine Site, slug-basiert.
-- Inhalte werden auch in JSONB gehalten, damit wir flexibel
-- zwischen Editionen variieren können.
-- ============================================================

CREATE TABLE IF NOT EXISTS marketing_sites (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,        -- "krummelus" → krummelus.shiksha.world / /m/krummelus
    edition         TEXT NOT NULL DEFAULT 'kita',  -- 'kita' | 'camping' | 'surfschule' | ...
    business_name   TEXT NOT NULL,
    tagline         TEXT,
    description     TEXT,                         -- 2-3 Sätze Hero-Untertitel
    -- Standort
    address_line    TEXT,
    postal_code     TEXT,
    city            TEXT,
    country         TEXT DEFAULT 'AT',
    lat             DOUBLE PRECISION,
    lng             DOUBLE PRECISION,
    -- Kontakt
    contact_email   TEXT,
    phone           TEXT,
    website_external TEXT,
    opening_hours   TEXT,
    -- Inhaltliche Bausteine (LLM-generiert oder manuell)
    about_text      TEXT,
    concept_text    TEXT,         -- Pädagogisches Konzept / Camping-Konzept / …
    arrival_text    TEXT,         -- Anfahrt
    excursions_text TEXT,         -- Ausflugsziele / Knigge / Vokabeln
    -- Zusatz-Daten als JSONB (kontextspezifisch)
    extra           JSONB DEFAULT '{}'::jsonb,
    -- Layout / Theme
    accent_color    TEXT DEFAULT 'auto',         -- 'auto' = saisonal, sonst hex
    season_override TEXT,                         -- 'spring'/'summer'/'autumn'/'winter' oder NULL
    -- Assets-Referenzen
    logo_asset_id      INTEGER,
    hero_asset_id      INTEGER,
    gallery_asset_ids  INTEGER[] DEFAULT '{}',
    -- Sichtbarkeit & Status
    status          TEXT DEFAULT 'draft',         -- 'draft' | 'live' | 'sleeping'
    trial_until     DATE,
    -- Audit
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    last_published_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_marketing_slug ON marketing_sites(slug);
CREATE INDEX IF NOT EXISTS idx_marketing_status ON marketing_sites(status);

CREATE TABLE IF NOT EXISTS marketing_assets (
    id              SERIAL PRIMARY KEY,
    site_id         INTEGER REFERENCES marketing_sites(id) ON DELETE CASCADE,
    -- NULL für Pool-Assets (gemeinsam für alle Sites)
    pool_edition    TEXT,                  -- für Pool-Assets: 'kita' / 'camping' / …
    pool_season     TEXT,                  -- 'spring' / 'summer' / 'autumn' / 'winter' / 'all'
    pool_tags       TEXT[] DEFAULT '{}',   -- ['warm', 'aktiv', 'innen']
    file_path       TEXT NOT NULL,         -- /opt/shiksha/marketing_assets/...
    file_url        TEXT,                  -- public URL (/m/asset/123)
    mime_type       TEXT,
    width           INTEGER,
    height          INTEGER,
    file_size       INTEGER,
    alt_text        TEXT,
    caption         TEXT,
    source          TEXT,                  -- 'upload' | 'firefly' | 'pool'
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assets_site ON marketing_assets(site_id);
CREATE INDEX IF NOT EXISTS idx_assets_pool ON marketing_assets(pool_edition, pool_season) WHERE site_id IS NULL;

-- LLM-Cache, damit gleiche Eingaben nicht jedes Mal Tokens kosten
CREATE TABLE IF NOT EXISTS marketing_llm_cache (
    cache_key       TEXT PRIMARY KEY,
    response        JSONB,
    model           TEXT,
    tokens_used     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON marketing_sites TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON marketing_assets TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON marketing_llm_cache TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE marketing_sites_id_seq TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE marketing_assets_id_seq TO shiksha;
