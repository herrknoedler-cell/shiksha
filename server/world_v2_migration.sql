-- ============================================================
-- SHIKSHA · world v2 — Editionen + Edition-Vorschläge
-- ============================================================

CREATE TABLE IF NOT EXISTS editions (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,        -- 'kita' | 'camping' | 'surfschule' | ...
    name            TEXT NOT NULL,               -- "KITA"
    headline        TEXT,                        -- "Software für KITAs, die mitwächst"
    tagline         TEXT,                        -- 1 Zeile poetisch
    description     TEXT,                        -- 2-3 Sätze
    icon            TEXT,                        -- Emoji
    accent_color    TEXT DEFAULT 'pink',
    pilot_count     INTEGER DEFAULT 0,           -- aktive Pilot-Kunden in dieser Edition
    status          TEXT DEFAULT 'planned',      -- 'live' | 'beta' | 'planned' | 'idea'
    page_url        TEXT,                        -- /kita, /camping, ... (auf shiksha.world)
    position        INTEGER DEFAULT 100,
    deployed_at     DATE,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS edition_proposals (
    id              SERIAL PRIMARY KEY,
    edition_name    TEXT NOT NULL,
    description     TEXT,
    use_case        TEXT,                        -- "Für wen, wofür?"
    proposer_email  TEXT,
    proposer_name   TEXT,
    upvotes         INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'new',          -- 'new' | 'considering' | 'planned' | 'declined'
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_editions_status ON editions(status, position);
CREATE INDEX IF NOT EXISTS idx_proposals_status ON edition_proposals(status, upvotes DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON editions TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON edition_proposals TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE editions_id_seq TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE edition_proposals_id_seq TO shiksha;

-- ============================================================
-- INITIAL EDITIONS
-- ============================================================
INSERT INTO editions (slug, name, headline, tagline, description, icon, accent_color, status, page_url, position, deployed_at, pilot_count) VALUES
  ('kita', 'KITA',
   'Für KITAs, die mitwachsen wollen.',
   'KBBG-konform, Eltern-nah, Team-stark.',
   'Stellenprozent, Anwesenheit, Eltern-Kommunikation, Compliance — alles in einer Software, die sich nicht wie Software anfühlt. Pilot in Vorarlberg, ausgerollt im DACH-Raum.',
   '🌱', 'pink', 'live', '/kita', 10, '2026-04-15', 1),

  ('camping', 'CAMPING',
   'Camping in vollautomatisch.',
   'Self-Service vom Buchen bis zur Schranke.',
   'Lageplan-Buchung, Kennzeichen-Erkennung, Stromzähler pro Stellplatz, Online-Anreise. Eine ganze Saison ohne Personal an der Rezeption.',
   '⛺', 'turquoise', 'beta', '/camping', 20, NULL, 0),

  ('surfschule', 'SURFSCHULE',
   'Wellenbasiert, nicht stundenbasiert.',
   'Trainer, Boards, Buchung, Wetter — eine App.',
   'Kursverwaltung mit Wellenvorhersage, Trainer-Verfügbarkeit, Online-Anmeldung, Erfahrungslevel-Matching. Für Spots an der Nordsee, am Atlantik, am Bodensee.',
   '🏄', 'turquoise', 'planned', '/surfschule', 30, NULL, 0),

  ('yogaschule', 'YOGASCHULE',
   'Studio-Software, die atmen kann.',
   'Stunden, Lehrer:innen, Mitgliedschaften — leicht.',
   'Drop-In, Karten, Abos, Eltern-Kind-Kurse, Workshops. Was Mindbody komplex macht, ist hier ein gutes Gefühl.',
   '🧘', 'purple', 'planned', '/yogaschule', 40, NULL, 0),

  ('schule', 'SCHULE',
   'Für freie Schulen mit eigenem Rhythmus.',
   'Stundenpläne, Eltern-Brief, Klassen — leise.',
   'Software für Privatschulen, Montessori, Waldorf, Demokratische Schulen. Compliance ohne Bürokratie-Erschöpfung.',
   '📚', 'orange', 'planned', '/schule', 50, NULL, 0),

  ('club', 'CLUB',
   'Vereine, die nicht mehr Excel-tauglich sind.',
   'Mitglieder, Beiträge, Termine — geordnet.',
   'Mitgliederverwaltung mit Beitrags-Automatik, Termin-Kalender, Eltern-Information für Jugendabteilungen, DSGVO-konformes Bilder-Modul.',
   '🤝', 'green', 'idea', '/club', 60, NULL, 0)
ON CONFLICT (slug) DO NOTHING;
