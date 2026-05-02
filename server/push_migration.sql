-- ============================================================
-- SHIKSHA · Web-Push Subscriptions
-- Speichert Browser-Push-Subscriptions für PWA-Notifications.
-- ============================================================

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id              SERIAL PRIMARY KEY,
    audience        TEXT NOT NULL,           -- 'paedagogin' | 'eltern' | 'traegerin'
    person_type     TEXT,                    -- 'staff' | 'parent' | 'system'
    person_id       TEXT,                    -- legacy_staff_id, kita_legacy_children.id (für Eltern)
    endpoint        TEXT NOT NULL UNIQUE,    -- Browser-Push-Endpoint URL
    p256dh_key      TEXT NOT NULL,           -- ECDH public key
    auth_key        TEXT NOT NULL,           -- Auth secret
    user_agent      TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    last_used_at    TIMESTAMP,
    last_error      TEXT,
    active          BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_push_audience ON push_subscriptions(audience, active);
CREATE INDEX IF NOT EXISTS idx_push_person ON push_subscriptions(person_type, person_id);

-- Push-Send-Log (Audit + Re-Send)
CREATE TABLE IF NOT EXISTS push_send_log (
    id              SERIAL PRIMARY KEY,
    sent_at         TIMESTAMP DEFAULT NOW(),
    audience_filter TEXT,                    -- z.B. 'paedagogin'
    title           TEXT NOT NULL,
    body            TEXT,
    url             TEXT,                    -- Click-Ziel
    sent_count      INTEGER DEFAULT 0,
    failed_count    INTEGER DEFAULT 0,
    sender          TEXT
);

GRANT SELECT, INSERT, UPDATE, DELETE ON push_subscriptions TO shiksha;
GRANT SELECT, INSERT, UPDATE, DELETE ON push_send_log TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE push_subscriptions_id_seq TO shiksha;
GRANT USAGE, SELECT ON SEQUENCE push_send_log_id_seq TO shiksha;

-- ============================================================
-- VAPID-Keys (einmalig generieren via py-vapid):
--   pip install py-vapid pywebpush
--   vapid --gen   → erzeugt private_key.pem
--   vapid --applicationServerKey   → liefert den Public-Key (URL-safe Base64)
--
-- Beide in /opt/shiksha/.env ablegen:
--   VAPID_PRIVATE_KEY=...
--   VAPID_PUBLIC_KEY=...
--   VAPID_SUBJECT=mailto:thomas@shiksha.tun.zone
-- ============================================================
