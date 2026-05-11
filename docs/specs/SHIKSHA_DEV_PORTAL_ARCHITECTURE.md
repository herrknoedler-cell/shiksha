# SHIKSHA — Developer Portal & Backend-Proxy

**Status:** Architektur-Spec · strategisch · ohne Pilot-Druck
**Stand:** 11. Mai 2026
**Domain:** `api.shiksha.world` (Engine), `dev.shiksha.world` (Developer-Console)
**Datenbank:** zentral, edition-agnostisch (KITA, Camping, Schule, Surf, Yoga, Club)
**Auth:** WebAuthn/Passkey-basiert via Presence-Switch-UI
**Cross-Reference:**
- `master_vision.md` — strategische DNA
- `SHIKSHA_RESPONSE_ENGINE.md` — Reaktions-Engine (4 Modi)
- `VERDICHTEN_PHASE_SPEC.md` — Phase 2
- `WORDING_AND_LANGUAGE.md` — bindender Sprach-Codex
- `TAGESAUSKLANG_BUILD_PACK_V0_1.md` — Tool-Calling-Vorgaben
- `presence_switch.html` — Auth-UI-Prototyp

---

## 1. Warum

Der aktuelle Stand hat zwei Wunden, die zusammen heilen müssen:

**Wunde 1 — Browser-Direct-API.** Die Mira-App und das Kennenlernen-HTML rufen die Anthropic-API direkt aus dem Browser auf. Mira's Phone trägt einen Anthropic-Key in `localStorage`. Das funktioniert für den Pilot, ist aber:

- nicht sicher (Key liegt clientseitig)
- nicht skalierbar (jede Trägerin müsste einen eigenen Key haben)
- nicht steuerbar (Thomas kann Persona-Prompts nicht ändern ohne neuen Deployment)
- nicht beobachtbar (keine Sicht auf Sessions, Insights, Streaks)

**Wunde 2 — Keine Sicht für Entwickler.** Thomas sieht aktuell nicht, was Mira mit SHIKSHA bespricht. Keine Sessions-Übersicht, keine Live-Statistik, keine Möglichkeit, einzelne Prompts live zu tunen, keine Pilot-Auswertung außer „Mira sagt das war gut/nicht gut".

Das Dev-Portal heilt beides. Es ist **Backend-Proxy** (für die App-Calls) und **Developer-Console** (für Thomas) in einem System.

---

## 2. Zielbild

```
┌──────────────────────────────────────────────────────────────────┐
│  SHIKSHA Dev-Portal                                              │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────────┐    │
│  │ Mira-App   │  │ Kennen-    │  │ Developer-Console        │   │
│  │ (iOS PWA)  │  │ lernen     │  │ (dev.shiksha.world)   │   │
│  └─────┬──────┘  └─────┬──────┘  └──────────┬──────────────┘    │
│        │               │                    │                    │
│        │  Bearer Token │                    │ Bearer Token       │
│        │  (traegerin)  │                    │ (developer)        │
│        ▼               ▼                    ▼                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │           SHIKSHA-API                                       │ │
│  │           api.shiksha.world                              │ │
│  │                                                              │ │
│  │  /api/auth/login                                             │ │
│  │  /api/chat/respond            ←  Anthropic-Proxy             │ │
│  │  /api/chat/stream             ←  SSE-Streaming               │ │
│  │  /api/sessions                ←  CRUD                        │ │
│  │  /api/memory                  ←  CRUD                        │ │
│  │  /api/insights/extract                                        │ │
│  │  /api/tools/log_observation                                  │ │
│  │  /api/tools/log_friction                                     │ │
│  │  /api/dev/* (developer-only)                                 │ │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             │                                     │
│         ┌───────────────────┼────────────────────┐                │
│         ▼                   ▼                    ▼                │
│  ┌──────────────┐  ┌─────────────────┐  ┌──────────────┐         │
│  │ PostgreSQL   │  │  Anthropic-API  │  │  Secrets-    │         │
│  │ (Sessions,   │  │  (server-side   │  │  Vault       │         │
│  │  Memory,     │  │   API-Key)      │  │  (env, .env) │         │
│  │  Personae)   │  │                 │  │              │         │
│  └──────────────┘  └─────────────────┘  └──────────────┘         │
└──────────────────────────────────────────────────────────────────┘
```

**Schlüssel-Idee:** Frontends sprechen nicht mehr mit Anthropic. Sie sprechen mit SHIKSHA's Backend. Das Backend hat den einzigen Anthropic-Key. Frontends authentifizieren sich mit Tokens, die das Backend ausgestellt hat.

---

## 3. Rollenmodell — edition-agnostisch

Drei Rollen, gelten cross-edition (KITA, Camping, Schule, Surf, Yoga, Club):

| Rolle | Wer | Darf |
|---|---|---|
| **operator** | Trägerin (KITA), Wirt (Camping), Lehrer (Schule, Surf), Studio-Leitung (Yoga), Club-Manager | Eigene Sessions starten, eigenes Memory lesen, Tagesausklang führen |
| **developer** | Thomas, Co-Devs | Alles: alle Sessions sehen, Persona-Prompts editieren, Memory-Einträge anlegen/ändern, Live-Statistik, cross-edition |
| **observer** | Pilot-Beobachter*innen, Research-Partner | Read-Only auf Sessions + Statistik, kein Editieren |

Edition-spezifische Sub-Rollen können später eingeführt werden (z.B. *kita_paedagogin*, *camping_gast*), bleiben aber operator-abgeleitet.

Token sind JWTs mit Claims `role`, `user_id`, `edition` (für operator), `org_id`.

---

## 4. API-Surface

Versionierter Prefix `/api/v1`. Alle Endpoints geben JSON zurück.

### 4.1 Auth

```
POST /api/v1/auth/login
  Body: { "username": "mira", "password": "..." }
  Response: { "token": "...", "role": "traegerin", "traegerin_id": "krummelus" }

POST /api/v1/auth/refresh
  Header: Authorization: Bearer <token>
  Response: { "token": "..." }

GET /api/v1/auth/me
  Header: Authorization: Bearer <token>
  Response: { "role": "...", "traegerin_id": "...", "name": "..." }
```

### 4.2 Chat (Anthropic-Proxy)

```
POST /api/v1/chat/respond
  Header: Authorization: Bearer <token>
  Body:
    {
      "session_id": "ses_...",   // optional, neu wenn weggelassen
      "user_message": "Heute war chaotisch …",
      "persona": "tagesausklang" | "kennenlernen"   // default: tagesausklang
    }
  Response:
    {
      "session_id": "ses_...",
      "shiksha_response": "Was war der Moment, der gekippt ist?",
      "mode": "FOKUS",          // welcher der 4 Modi
      "tokens_used": 142
    }

POST /api/v1/chat/stream
  Wie oben, aber SSE-Stream:
    data: { "delta": "Was" }
    data: { "delta": " war " }
    ...
    data: { "done": true, "session_id": "...", "mode": "FOKUS" }
```

Persona-Prompts werden **server-side** geladen aus `persona_prompts`-Tabelle, mit aktuellem Memory-Block injiziert. Frontends senden niemals Prompt-Inhalte.

### 4.3 Sessions

```
GET    /api/v1/sessions                  → eigene Sessions (traegerin), alle (developer)
GET    /api/v1/sessions/{id}             → Detail mit Messages
POST   /api/v1/sessions/{id}/close       → Session schließen, Insight-Extraktion triggern
DELETE /api/v1/sessions/{id}             → developer-only
```

### 4.4 Memory

```
GET    /api/v1/memory                    → eigenes (traegerin), aller (developer)
POST   /api/v1/memory                    → Eintrag hinzufügen
DELETE /api/v1/memory/{id}               → entfernen
PATCH  /api/v1/memory/{id}               → editieren
```

### 4.5 Insights

```
POST   /api/v1/insights/extract          → läuft am Session-Ende automatisch
GET    /api/v1/insights?traegerin=...    → aggregierte Insights
```

### 4.6 Tools (Function-Calling von SHIKSHA aus)

```
POST   /api/v1/tools/log_observation
  Body: { "session_id": "...", "kind": "...", "text": "..." }
  
POST   /api/v1/tools/log_friction
  Body: { "session_id": "...", "where": "...", "text": "..." }
  
POST   /api/v1/tools/save_day_summary
  Body: { "session_id": "...", "summary": "...", "highlights": [...] }
```

Diese werden vom Backend selbst aufgerufen, wenn Claude im LLM-Call ein Tool nutzt.

### 4.7 Developer-Endpoints

```
GET    /api/v1/dev/stats                  → Streaks, Sessions-Counts, durchschn. Dauer
GET    /api/v1/dev/persona-prompts         → alle Personae listen
PUT    /api/v1/dev/persona-prompts/{name}  → live editieren
GET    /api/v1/dev/sessions/live           → SSE-Stream aller laufenden Sessions
GET    /api/v1/dev/logs                    → Server-Logs (gefiltert)
POST   /api/v1/dev/traegerinnen            → neue Trägerin anlegen
```

---

## 5. Datenbank-Schema — edition-agnostisch

Eine zentrale Datenbank für **alle Editionen** (KITA, Camping, Schule, Surf, Yoga, Club). Neues Schema `shiksha_core` in der existierenden Postgres-Instanz.

Edition ist **first-class Attribut** überall wo's zählt — Tabellen tragen es als Spalte, Cross-Edition-Joins sind über `edition` filterbar.

```sql
CREATE SCHEMA shiksha_core;

-- Organisationen (KITA Krummelus, Camping Klausenhof, Surfschule Sylt, …)
CREATE TABLE shiksha_core.organizations (
  id           VARCHAR(64) PRIMARY KEY,           -- z.B. "krummelus"
  edition      VARCHAR(32) NOT NULL,               -- "kita", "camping", "schule", "surf", "yoga", "club"
  name         VARCHAR(128) NOT NULL,              -- "Krummelus"
  legal_name   VARCHAR(255),                       -- "Krummelus GmbH"
  region       VARCHAR(64),                        -- "Vorarlberg, AT"
  metadata     JSONB DEFAULT '{}'::jsonb,          -- edition-spezifische Felder
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Operators (Trägerin/Wirt/Lehrer/…) — eine Person pro Edition pro Org
CREATE TABLE shiksha_core.operators (
  id              VARCHAR(64) PRIMARY KEY,         -- z.B. "krummelus_mira"
  org_id          VARCHAR(64) REFERENCES shiksha_core.organizations(id) ON DELETE CASCADE,
  edition         VARCHAR(32) NOT NULL,
  display_name    VARCHAR(128) NOT NULL,           -- "Mira"
  role            VARCHAR(32) NOT NULL DEFAULT 'operator',  -- operator/developer/observer
  email           VARCHAR(255),
  webauthn_credentials JSONB DEFAULT '[]'::jsonb,   -- Passkey-Public-Keys (mehrere möglich)
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  metadata        JSONB DEFAULT '{}'::jsonb        -- accessLevel, season-Präferenz, etc.
);

-- Persona-Prompts (cross-edition oder edition-spezifisch)
CREATE TABLE shiksha_core.persona_prompts (
  name            VARCHAR(64) NOT NULL,             -- "tagesausklang", "kennenlernen", …
  edition         VARCHAR(32) NOT NULL DEFAULT '*', -- "*" = cross-edition, sonst edition-spezifisch
  version         INTEGER NOT NULL DEFAULT 1,
  system_prompt   TEXT NOT NULL,
  description     TEXT,
  updated_by      VARCHAR(64) REFERENCES shiksha_core.operators(id),
  updated_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (name, edition, version)
);

-- Sessions
CREATE TABLE shiksha_core.sessions (
  id             VARCHAR(64) PRIMARY KEY,
  operator_id    VARCHAR(64) REFERENCES shiksha_core.operators(id) ON DELETE CASCADE,
  org_id         VARCHAR(64) REFERENCES shiksha_core.organizations(id),
  edition        VARCHAR(32) NOT NULL,
  persona        VARCHAR(64) NOT NULL,
  started_at     TIMESTAMPTZ DEFAULT NOW(),
  closed_at      TIMESTAMPTZ,
  summary        TEXT,
  insights       JSONB DEFAULT '[]'::jsonb,
  meta           JSONB DEFAULT '{}'::jsonb,
  tokens_used    INTEGER DEFAULT 0
);

CREATE TABLE shiksha_core.messages (
  id             SERIAL PRIMARY KEY,
  session_id     VARCHAR(64) REFERENCES shiksha_core.sessions(id) ON DELETE CASCADE,
  role           VARCHAR(16) NOT NULL,
  content        TEXT NOT NULL,
  mode           VARCHAR(16),
  ts             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shiksha_core.memory_entries (
  id             SERIAL PRIMARY KEY,
  operator_id    VARCHAR(64) REFERENCES shiksha_core.operators(id) ON DELETE CASCADE,
  edition        VARCHAR(32) NOT NULL,
  text           TEXT NOT NULL,
  source_session_id VARCHAR(64) REFERENCES shiksha_core.sessions(id) ON DELETE SET NULL,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shiksha_core.observations (
  id             SERIAL PRIMARY KEY,
  session_id     VARCHAR(64) REFERENCES shiksha_core.sessions(id) ON DELETE CASCADE,
  edition        VARCHAR(32) NOT NULL,
  kind           VARCHAR(32),
  text           TEXT,
  metadata       JSONB DEFAULT '{}'::jsonb,
  ts             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shiksha_core.friction_points (
  id             SERIAL PRIMARY KEY,
  session_id     VARCHAR(64) REFERENCES shiksha_core.sessions(id) ON DELETE CASCADE,
  edition        VARCHAR(32) NOT NULL,
  where_label    VARCHAR(64),
  text           TEXT,
  resolved       BOOLEAN DEFAULT FALSE,
  ts             TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE shiksha_core.audit_logs (
  id             SERIAL PRIMARY KEY,
  actor_id       VARCHAR(64),                       -- wer hat's getan
  action         VARCHAR(64) NOT NULL,              -- "persona_edit", "memory_create", …
  target_type    VARCHAR(32),                       -- "persona_prompts", "memory_entries", …
  target_id      VARCHAR(64),
  diff           JSONB,                             -- alter + neuer Zustand
  ts             TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sessions_operator ON shiksha_core.sessions(operator_id, started_at DESC);
CREATE INDEX idx_sessions_edition  ON shiksha_core.sessions(edition, started_at DESC);
CREATE INDEX idx_messages_session  ON shiksha_core.messages(session_id, ts);
CREATE INDEX idx_memory_operator   ON shiksha_core.memory_entries(operator_id);
CREATE INDEX idx_operators_org     ON shiksha_core.operators(org_id, edition);
CREATE INDEX idx_audit_ts          ON shiksha_core.audit_logs(ts DESC);
```

**Persona-Resolution-Regel:** Bei `chat/respond` mit `persona="tagesausklang"`:
1. Suche `persona_prompts` mit `name="tagesausklang"`, `edition=<user's edition>`, höchste Version.
2. Falls keine: fallback auf `edition="*"` (cross-edition).
3. Falls auch keine: 404.

---

## 6. Tech-Stack

| Schicht | Wahl | Grund |
|---|---|---|
| Sprache | Python 3.11+ | Bestand: KITA-Edition läuft schon in Python |
| Framework | FastAPI | Async, OpenAPI-Auto-Gen, Streaming-tauglich |
| ORM | SQLAlchemy 2.0 + Alembic | Migrations, Type-Safety |
| Auth | python-jose (JWT) + passlib (bcrypt) | Standard, robust |
| LLM-Client | `anthropic` SDK | Offiziell |
| DB | PostgreSQL 15 | Bestand |
| Reverse-Proxy | Caddy | Bestand |
| Hosting | tun.zone (existierender Server) | Bestand |
| Streaming | SSE (Server-Sent-Events) | Einfacher als WebSockets, reicht für 1-Way |
| Frontend (Dev-Console) | HTML + Vanilla JS + Web-Components | Konsistent mit Bestand, kein Build-Step |

Keine Microservices. Eine FastAPI-Instanz. Datenbank ist Single-Source-of-Truth.

---

## 7. Sicherheitsmodell

**API-Key (Anthropic):** lebt nur in `.env` auf dem Server. Niemals im Code, niemals in Git, niemals im Browser.

**Operator-Auth:** WebAuthn/Passkey statt Passwort. Eintrittsgeste via **Presence-Switch-UI** (siehe `presence_switch.html`). Operator wählt seine Karte → Browser authentifiziert mit lokalem Passkey (Face ID, Touch ID, Windows Hello, Hardware-Key) → Backend verifiziert Public-Key-Signatur → JWT ausgestellt.

Vorteile gegenüber Passwort/Magic-Link:
- Kein Passwort zu merken, keine Mail-Latenz, kein Reset-Flow.
- Phishing-resistent per Design.
- Mira erlebt's als Eintrittsgeste, nicht als Login.
- Mehrere Geräte pro Operator möglich (Phone + Laptop), je eigener Passkey.

Fallback wenn Passkey nicht verfügbar (alter Browser, kein TPM): E-Mail-Code als Notausgang. Magic-Link nicht Default.

**Token-Lifetime:** 30 Tage, Refresh-Endpoint vorhanden. Verlust eines Geräts → in Dev-Console Passkey revoken.

**Developer-Auth:** Wie Operator, aber zusätzlich Master-Passkey + Recovery-Code. Tokens revocierbar.

**Rate-Limit:** pro Operator 200 Chat-Requests/Tag (verhindert Runaway-Loops). Developer-Endpoints unlimitiert.

**Audit-Log:** alle Mutations (Persona-Editing, Memory-Edits, Passkey-Revocations) in Tabelle `audit_logs` mit `who/when/what/diff`.

**DSGVO:** Operator kann eigene Daten exportieren (`GET /api/v1/me/export`) und löschen (`DELETE /api/v1/me` → soft-delete mit 30-Tage-Karenz, dann hard-delete).

**Secrets-Management:** Tomls-Datei `secrets.toml` auf Server, `chmod 600`, Owner `shiksha-app`. Niemals in Git.

---

## 8. Migrations-Pfad

Frontends laufen heute mit Anthropic-Direct. Übergang sauber:

```
Phase A — Backend läuft parallel
  Backend ist deploybar, Endpoints funktionieren.
  Frontends bleiben unverändert.
  Wir testen das Backend mit curl + Developer-Console.

Phase B — Mira-App und Kennenlernen-HTML migrieren
  Anthropic-Calls werden durch /api/v1/chat/respond ersetzt.
  Token statt API-Key in localStorage.
  Memory wandert vom localStorage auf den Server (mit Sync-Mechanik
  für Offline-Modus).

Phase C — Browser-Direct ausschalten
  Code im Frontend entfernt, der Anthropic direkt aufrufen würde.
  Saubere Linie.
```

---

## 9. Developer-Console — Tabs

`dev.shiksha.world` (oder eigene Subdomain `dev.shiksha.tun.zone`).

```
┌─────────────────────────────────────────────────────────────┐
│ SHIKSHA Dev-Portal                          Thomas · Logout │
├─────────────────────────────────────────────────────────────┤
│ Dashboard │ Sessions │ Personae │ Memory │ Tools │ Logs    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [aktuelle Tab-Inhalt]                                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Dashboard:** Pilot-Stats. Sessions-Count, Streaks pro Trägerin, durchschn. Session-Dauer, durchschn. Tokens, Latenz, Top-Pfad-Modus-Verteilung.

**Sessions:** Tabelle aller Sessions. Filterbar nach Trägerin, Datum, Persona, Modus. Klick auf Zeile öffnet Modal mit komplettem Transkript + Insights.

**Personae:** Editor für die `persona_prompts` Tabelle. Live-Preview. Versionsverwaltung. Beim Speichern wird neue Version angelegt, alte bleibt erhalten.

**Memory:** Pro Trägerin alle Memory-Einträge. Editierbar. Manuelle Einträge ergänzbar (z.B. *„Aus Termin 2: Mira will Wochenend-Bereitschaft"*).

**Tools:** Tool-Inventar mit Doku. Welche Tools existieren, was tun sie, wann wurden sie zuletzt aufgerufen. Aktivieren/Deaktivieren pro Persona.

**Logs:** Live-Stream + Suchfunktion. Filter nach Trägerin, Level, Zeitraum.

---

## 10. Live-Stream über SSE

Developer-Console abonniert `/api/v1/dev/sessions/live`. Jede Mira-Eingabe und jede SHIKSHA-Antwort wird als SSE-Event gepusht:

```
event: message
data: { "session_id": "ses_...", "role": "user", "content": "..." }

event: message
data: { "session_id": "ses_...", "role": "assistant", "content": "...", "mode": "PRÄSENZ" }
```

Thomas kann in Echtzeit zuschauen, was Mira mit SHIKSHA bespricht — datenschutzkonform nur mit ihrer Pilot-Zustimmung (steht im `PILOT_VERTRAG_TEMPLATE`).

---

## 11. Architektur-Entscheidungen (getroffen 11. Mai 2026)

```
✓ Subdomain      → api.shiksha.world (Engine), dev.shiksha.world (Console)
✓ DB             → existierende Postgres, neues Schema shiksha_core
                   edition-agnostisch, multi-tenant ready
✓ Auth           → WebAuthn/Passkey via Presence-Switch-UI
                   E-Mail-Code als Notausgang
✓ Streaming      → SSE schon in Phase 1
✓ Tool-Calling   → Skelett in Phase 1, aktive Nutzung in Phase 4
✓ Audit-Log      → in Phase 1 mit dabei
```

---

## 12. Was diese Spec **nicht** abdeckt

- Public API für externe Entwickler (SDK, API-Keys, Rate-Limit-Tiers): kommt in `SHIKSHA_PUBLIC_API_SPEC.md`, nachdem das interne Portal steht.
- Mobile-Native-Apps (iOS/Android Swift/Kotlin): aktuell PWA, native erst wenn der Pilot trägt.
- Multi-Tenant-Billing: nicht relevant bis es zahlende Kunden gibt.
- Voice / Audio-Input: separater Spec, hängt nicht am Backend-Proxy.

---

## 13. Erfolgskriterien

Das Dev-Portal ist „fertig genug" wenn:

```
□ Mira-App kann ohne lokalen API-Key sprechen
□ Thomas sieht alle Sessions in einem Browser-Tab
□ Thomas kann Persona-Prompts live editieren ohne Deployment
□ Neue Pilotin in <5 Min anlegbar
□ Tagesausklang läuft mit Tool-Calling (save_observation etc.)
□ Live-Stream funktioniert
□ DSGVO-konformer Daten-Export + Löschung
□ Audit-Log über Developer-Actions
```

Phase 1+2 erreicht die ersten vier. Phase 3+4 die restlichen.

---

**Spec · 11. Mai 2026 · Backend-Proxy + Developer-Console · FastAPI + PostgreSQL · Strategisch, ohne Pilot-Druck**
