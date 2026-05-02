-- ============================================================
-- SHIKSHA · KITA · Notifications + Eltern-Accounts
-- Stand: 29.04.2026
-- ============================================================

-- 1. Eltern-Accounts (1:1 zu enrollment, oder N:1 für Geschwister)
CREATE TABLE IF NOT EXISTS kita_parent_accounts (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    full_name       TEXT NOT NULL,
    email           TEXT NOT NULL,
    phone           TEXT,
    role            TEXT,                       -- 'mutter' | 'vater' | 'erziehungsberechtigt'
    -- Kind-Verbindungen
    enrollment_ids  TEXT[],                     -- Array von kita_child_enrollments.id
    child_names     TEXT,                       -- "Flora Köb, Luca Köb"
    -- Anmelde-Kontext
    source_doc_id   TEXT REFERENCES kita_documents(id),
    consent_given   BOOLEAN DEFAULT false,
    -- Login-Token (statt Passwort: signed Token aus Mail)
    login_token     TEXT UNIQUE,                -- 32-stelliger Random-Token
    token_expires_at TIMESTAMP,
    last_login_at   TIMESTAMP,
    -- Push-Benachrichtigung
    push_subscription JSONB,                   -- Web-Push Endpoint
    notification_email_optin BOOLEAN DEFAULT true,
    notification_push_optin  BOOLEAN DEFAULT false,
    -- Lifecycle
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_parent_email ON kita_parent_accounts(email);
CREATE INDEX IF NOT EXISTS idx_parent_token ON kita_parent_accounts(login_token);

-- 2. Notifications (Mitteilungen)
CREATE TABLE IF NOT EXISTS kita_notifications (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    body_html       TEXT,
    -- Targeting
    target_type     TEXT NOT NULL,              -- 'all' | 'group' | 'children' | 'parent'
    target_group_id TEXT REFERENCES kita_groups(id),
    target_enrollment_ids TEXT[],               -- für Einzelkinder
    target_parent_ids TEXT[],                   -- für Einzeleltern
    include_staff   BOOLEAN DEFAULT false,
    -- Versand
    send_via_email  BOOLEAN DEFAULT true,
    send_via_push   BOOLEAN DEFAULT false,
    priority        TEXT DEFAULT 'normal',      -- 'low' | 'normal' | 'high' | 'urgent'
    -- Status
    status          TEXT DEFAULT 'draft',       -- 'draft' | 'sending' | 'sent' | 'failed'
    sent_at         TIMESTAMP,
    -- Author
    created_by      TEXT,                       -- Mitarbeiter-Name oder 'system'
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notif_status ON kita_notifications(status);
CREATE INDEX IF NOT EXISTS idx_notif_target_group ON kita_notifications(target_group_id);

-- 3. Recipient-Tracking (welche Mail an wen, wann gesendet, gelesen)
CREATE TABLE IF NOT EXISTS kita_notification_recipients (
    id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    notification_id TEXT REFERENCES kita_notifications(id) ON DELETE CASCADE,
    recipient_type  TEXT NOT NULL,              -- 'parent' | 'staff'
    parent_id       TEXT REFERENCES kita_parent_accounts(id),
    staff_id        TEXT REFERENCES kita_staff_members(id),
    email           TEXT,
    -- Status
    delivery_status TEXT DEFAULT 'pending',     -- 'pending' | 'sent' | 'failed' | 'opened'
    sent_at         TIMESTAMP,
    opened_at       TIMESTAMP,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_recip_notif ON kita_notification_recipients(notification_id);
CREATE INDEX IF NOT EXISTS idx_recip_parent ON kita_notification_recipients(parent_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON
  kita_parent_accounts, kita_notifications, kita_notification_recipients TO shiksha;
