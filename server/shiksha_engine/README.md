# SHIKSHA Engine

Backend-Proxy + Developer-Portal-API für SHIKSHA. Edition-agnostisch — funktioniert für KITA, Camping, Schule, Surf, Yoga, Club.

**Phase:** Schritt 1 der 8-stufigen Modular-Build-Roadmap (`SHIKSHA_MODULAR_BUILD_PLAN.md`).

---

## Was diese Engine kann (Stand Schritt 1)

```
✓ FastAPI-Server auf api.shiksha.world (HTTP + SSE)
✓ PostgreSQL-Schema shiksha_core mit allen Tabellen
✓ WebAuthn/Passkey-Auth (register + login + refresh + /me)
✓ JWT-Tokens (30 Tage, Rolle + Edition als Claims)
✓ Chat-Endpoints /respond (block) und /stream (SSE)
✓ Persona-Loader mit Edition-Fallback + Memory-Injection
✓ Tools-Skelett-Endpoints (log_observation, log_friction, save_day_summary, add_memory)
✓ Audit-Log-Middleware (alle Mutations werden geloggt)
✓ Developer-Endpoints (Stats, Personae, Operator-Liste, Audit-Logs)
✓ Edition-Configs (yaml) für KITA, Camping, Schule, Surf, Yoga, Club
✓ Seed-Scripts (Mira als KITA-Operator, Thomas als Developer, Personae)
✓ pytest-Skelett (Health, JWT, Persona-Loader)
```

---

## Setup (lokale Entwicklung)

```bash
# 1. Python-Env
cd server/shiksha_engine
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Env
cp .env.example .env
$EDITOR .env       # DATABASE_URL, JWT_SECRET, ANTHROPIC_API_KEY setzen

# 3. Datenbank
createdb shiksha
alembic upgrade head

# 4. Seed
python -m scripts.seed_operators
python -m scripts.seed_personas

# 5. Start
shiksha-engine
# Server läuft auf http://0.0.0.0:8000
# Docs unter http://localhost:8000/docs
```

## Setup (Production)

```bash
# 1. User anlegen
sudo useradd -r -m -d /opt/shiksha-engine shiksha-app

# 2. Code deployen
sudo -u shiksha-app git clone <repo> /opt/shiksha-engine
cd /opt/shiksha-engine
sudo -u shiksha-app python3.11 -m venv .venv
sudo -u shiksha-app .venv/bin/pip install -e .

# 3. .env (chmod 600!)
sudo cp deploy/.env.example /opt/shiksha-engine/.env
sudo $EDITOR /opt/shiksha-engine/.env
sudo chmod 600 /opt/shiksha-engine/.env
sudo chown shiksha-app:shiksha-app /opt/shiksha-engine/.env

# 4. DB-Migration
sudo -u shiksha-app .venv/bin/alembic upgrade head
sudo -u shiksha-app .venv/bin/python -m scripts.seed_personas

# 5. systemd + Caddy
sudo cp deploy/shiksha-engine.service /etc/systemd/system/
sudo cp deploy/Caddyfile.snippet /etc/caddy/snippets/shiksha-engine
# Caddyfile-Imports aktualisieren
sudo systemctl daemon-reload
sudo systemctl enable shiksha-engine
sudo systemctl start shiksha-engine
sudo systemctl reload caddy

# 6. Smoke
curl https://api.shiksha.world/health
```

---

## Architektur — kurz

```
┌──────────────────────────────────────────────────────────┐
│              api.shiksha.world (Caddy + TLS)             │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│          uvicorn 127.0.0.1:8000 (FastAPI)                │
│                                                          │
│  Routers:  /api/v1/auth     /api/v1/chat                 │
│            /api/v1/sessions /api/v1/tools                │
│            /api/v1/dev      /health                      │
│                                                          │
│  Middleware: AuditLog                                    │
│  Deps:       JWT-Auth, Operator-Loading, Rollen          │
└──────────────────────────────────────────────────────────┘
            │                       │
            ▼                       ▼
   ┌──────────────┐         ┌─────────────────┐
   │ PostgreSQL   │         │  Anthropic-API  │
   │ shiksha_core │         │  (server-side)  │
   └──────────────┘         └─────────────────┘
```

---

## API-Endpoints — Cheat Sheet

```
AUTH
  POST   /api/v1/auth/register/begin/{operator_id}    → WebAuthn-Challenge
  POST   /api/v1/auth/register/finish                  → Verifikation + Token
  POST   /api/v1/auth/login/begin                      → Authentication-Challenge
  POST   /api/v1/auth/login/finish                     → Verifikation + Token
  POST   /api/v1/auth/refresh                          → Token erneuern
  GET    /api/v1/auth/me                               → Wer bin ich

CHAT
  POST   /api/v1/chat/respond                          → Block-Antwort
  POST   /api/v1/chat/stream                           → SSE-Streaming
  POST   /api/v1/chat/close/{session_id}               → Session schließen

SESSIONS
  GET    /api/v1/sessions                              → eigene Sessions
  GET    /api/v1/sessions/{id}                         → mit Messages

TOOLS (in Phase 4 von Anthropic automatisch aufgerufen)
  POST   /api/v1/tools/log_observation
  POST   /api/v1/tools/log_friction
  POST   /api/v1/tools/save_day_summary
  POST   /api/v1/tools/add_memory

DEVELOPER (Token mit role=developer nötig)
  GET    /api/v1/dev/stats
  GET    /api/v1/dev/operators
  GET    /api/v1/dev/persona-prompts
  PUT    /api/v1/dev/persona-prompts
  GET    /api/v1/dev/audit-logs
```

---

## Tests

```bash
pytest                          # alle
pytest tests/test_jwt.py        # einzelne Datei
pytest -k persona               # nach Name
pytest --cov=shiksha_engine     # mit Coverage
```

Voraussetzung: Test-DB `shiksha_test` existiert. Override via:
```bash
export SHIKSHA_TEST_DATABASE_URL=postgresql+psycopg2://shiksha:shiksha@localhost:5432/shiksha_test
```

---

## Was kommt — Schritt 2 und weiter

Siehe `SHIKSHA_MODULAR_BUILD_PLAN.md`:

```
Schritt 2  Streaming-Refinement + Persona-Editor-API
Schritt 3  Frontend-Migration (Mira-App + Kennenlernen-HTML)
Schritt 4  Tool-Calling aktiv via Anthropic Function-Calling
Schritt 5  Wiederbeginn-Modul (Phase C der Hero-Journey)
Schritt 6  Generation-Modul (Phase D)
Schritt 7  Dashboard-Übergang + Anpassungs-Hooks
Schritt 8  Mobile-Handover + Server-Push (VAPID)
```

---

**v0.1.0 · Phase 1 Foundation · edition-agnostisch · Mira-UX-first**
