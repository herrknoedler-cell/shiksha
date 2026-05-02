-- ============================================================
-- SHIKSHA · KITA · Stellenprozent-Rechner (KKG nach Vorarlberg)
-- Stand: 29.04.2026
-- ============================================================

-- 1. Gruppen-Erweiterung: Gründungsdatum für Förder-Staffel
ALTER TABLE kita_groups ADD COLUMN IF NOT EXISTS founded_at DATE;
ALTER TABLE kita_groups ADD COLUMN IF NOT EXISTS funding_basis TEXT DEFAULT 'KV'; -- 'KV' (39h) oder 'GAG' (40h)
ALTER TABLE kita_groups ADD COLUMN IF NOT EXISTS group_format TEXT DEFAULT 'kkg'; -- 'kkg' = Kleinkindgruppe, 'kiga', 'hort'

-- 2. Stellenprozent-Snapshots pro Gruppe pro Monat
CREATE TABLE IF NOT EXISTS kita_st_calculations (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    group_id        TEXT REFERENCES kita_groups(id) ON DELETE CASCADE,
    snapshot_month  DATE NOT NULL,                       -- 1. Tag des Monats
    -- Eingabedaten (Halbtags-Belegung als JSON)
    halfday_data    JSONB NOT NULL,                      -- {"montag_vm": {"oz": 4.5, "0_1": 2, "2j": 5, ...}, ...}
    -- Berechnungen
    st_kinderdienst NUMERIC(7,2) NOT NULL DEFAULT 0,     -- ST% Kinderdienst aller Halbtage
    st_vbz_gruppe   NUMERIC(7,2) NOT NULL DEFAULT 0,     -- ST% Vor-/Nachbereitungszeit
    st_vbz_leitung  NUMERIC(7,2) NOT NULL DEFAULT 0,     -- ST% Leitungs-VBZ
    st_ikind        NUMERIC(7,2) NOT NULL DEFAULT 0,     -- ST% I-Kind-Zusatz
    st_total        NUMERIC(7,2) NOT NULL DEFAULT 0,     -- ST% Gesamt
    -- Förder-Aufteilung
    land_pct        NUMERIC(5,2),                        -- 80, 75, 70, 60 je nach Jahr
    stadt_pct       NUMERIC(5,2),                        -- 100 - land_pct
    funding_year    INTEGER,                             -- 1, 2, 3, 4+ seit Gründung
    -- Validierung
    variant_used    TEXT,                                -- 'variante_1' oder 'variante_2' oder 'mixed'
    has_kiga_warning BOOLEAN DEFAULT false,              -- ≥3-Jährige in Mehrheit?
    notes           TEXT,
    -- Author + Trail
    created_by      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    UNIQUE (group_id, snapshot_month)
);

CREATE INDEX IF NOT EXISTS idx_stcalc_group_month ON kita_st_calculations(group_id, snapshot_month);

-- 3. Konstanten für Berechnung (hartcodiert, aber abrufbar)
CREATE TABLE IF NOT EXISTS kita_st_constants (
    key             TEXT PRIMARY KEY,
    value           NUMERIC(8,4) NOT NULL,
    notes           TEXT
);

INSERT INTO kita_st_constants (key, value, notes) VALUES
    ('variante_1_st_pro_kind', 0.33, 'KKG mit überw. 0-1J: 1:3 Schlüssel, max 9 Kinder'),
    ('variante_1_max_kinder', 9, 'Max Kinder bei Variante 1'),
    ('variante_1_min_quote_0_1', 0.5, 'Mindest-Anteil 0-1J für Variante 1 (oder >4 absolut)'),
    ('variante_2_st_pro_kind', 0.20, 'KKG mit überw. 2J: 1:5 Schlüssel, max 12 Kinder'),
    ('variante_2_max_kinder', 12, 'Max Kinder bei Variante 2'),
    ('vbz_min_pro_gruppe_h', 16, 'Mindest VB-Zeit pro Gruppe in Stunden/Woche'),
    ('vbz_leitung_1gruppe', 1, 'Leitungs-VBZ bei 1 Gruppe'),
    ('vbz_leitung_2gruppen', 2, 'Leitungs-VBZ bei 2 Gruppen'),
    ('vbz_leitung_3gruppen', 4, 'Leitungs-VBZ bei 3 Gruppen'),
    ('vbz_leitung_4plus_gruppen', 6, 'Leitungs-VBZ bei 4-8 Gruppen'),
    ('kv_st_pro_stunde', 2.5641, 'KV: 1 Std/Wo = 2,564 ST% (39h Vollzeit)'),
    ('gag_st_pro_stunde', 2.5000, 'GAG: 1 Std/Wo = 2,5 ST% (40h Vollzeit)'),
    ('foerderung_jahr_1', 80, 'Land-Förderung Jahr 1 in %'),
    ('foerderung_jahr_2', 75, 'Land-Förderung Jahr 2 in %'),
    ('foerderung_jahr_3', 70, 'Land-Förderung Jahr 3 in %'),
    ('foerderung_jahr_4plus', 60, 'Land-Förderung ab Jahr 4 in %')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, notes = EXCLUDED.notes;

GRANT SELECT, INSERT, UPDATE, DELETE ON kita_st_calculations TO shiksha;
GRANT SELECT ON kita_st_constants TO shiksha;
