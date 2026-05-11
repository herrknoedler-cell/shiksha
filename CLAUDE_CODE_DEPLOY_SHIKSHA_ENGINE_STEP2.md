# Claude Code — Deploy SHIKSHA-Engine Schritt 2

**Aufgabe:** API-Vervollständigung für die Frontend-Migration. Memory-CRUD, Sessions-Filter, Session-Close mit Insights-Extraction, Rate-Limit (SQL-Counter), pytest-Erweiterung, OpenAPI-Tags.

**Kontext:** Schritt 2 von 8. Foundation steht aus Schritt 1 (api.shiksha.world live). Diese Erweiterung baut die Bausteine, die das Frontend in Schritt 3 brauchen wird.

**Cowork-Output-Pfad:**

```
SRC="/Users/thomasknodler/Library/Application Support/Claude/local-agent-mode-sessions/afe14d15-f202-489c-993c-b4935c648d43/f7099d1a-0274-4431-9558-7e4f3bb5982b/local_fa970b76-e666-47d9-af8b-b52f0d727235/outputs"
```

---

## Was sich gegenüber Schritt 1 ändert — Übersicht

```
NEU:
  shiksha_engine/routers/memory.py           — CRUD über MemoryEntry
  shiksha_engine/services/insights_extractor.py — Session-Close-Insight-Engine
  shiksha_engine/models/rate_limit.py        — Counter-Tabelle
  shiksha_engine/middleware/rate_limit.py    — SQL-Counter-Middleware
  shiksha_engine/schemas/memory.py           — Pydantic-Schemas für Memory
  alembic/versions/20260512_0002_rate_limit_buckets.py — Migration
  tests/test_memory.py
  tests/test_sessions_filter.py
  tests/test_insights_extraction.py          — mit Anthropic-Mock
  tests/test_rate_limit.py

GEÄNDERT:
  shiksha_engine/main.py            — RateLimitMiddleware mounten, memory-Router,
                                      openapi_tags
  shiksha_engine/models/__init__.py — RateLimitBucket exportiert
  shiksha_engine/routers/sessions.py — Query-Params: edition, persona, since,
                                      until, has_summary, q, target_operator_id
  shiksha_engine/routers/chat.py    — /close/{session_id} ruft jetzt
                                      insights_extractor auf
```

---

## Pre-Flight

```bash
# 1. Repo clean, auf main
cd /Users/thomasknodler/code/shiksha
git status
git pull --rebase

# 2. Existing Engine läuft
curl -s https://api.shiksha.world/health | jq

# 3. Schritt-1 + jetzt 11 Tests grün — frisch laufen lassen vor Schritt 2
#    HINWEIS: grep MUSS als root laufen (Drop-In ist 0600 root:root),
#    DB_PW wird via env-Variable an shiksha-app durchgereicht
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 <<'REMOTE'
  DB_PW=$(grep -oP "shiksha:\K[^@\"']+" /etc/systemd/system/shiksha.service.d/database.conf | head -1)
  if [ -z "$DB_PW" ]; then
    echo "FEHLER: DB_PW konnte nicht extrahiert werden"
    exit 1
  fi
  sudo -u shiksha-app env DB_PW="$DB_PW" bash <<'INNER'
    cd /opt/shiksha-engine
    export SHIKSHA_TEST_DATABASE_URL="postgresql://shiksha:${DB_PW}@localhost:5432/shiksha"
    export DB_SCHEMA="shiksha_core_test"
    .venv/bin/pytest -v --tb=short 2>&1 | tail -20
INNER
REMOTE
# Erwartet: 11 passed
```

---

## Phase A — Code übernehmen

```bash
SRC="/Users/thomasknodler/Library/Application Support/Claude/local-agent-mode-sessions/afe14d15-f202-489c-993c-b4935c648d43/f7099d1a-0274-4431-9558-7e4f3bb5982b/local_fa970b76-e666-47d9-af8b-b52f0d727235/outputs"
cd /Users/thomasknodler/code/shiksha

# Kompletten Engine-Source neu sync — viele Änderungen
rsync -av --delete \
  --exclude='.venv' --exclude='__pycache__' --exclude='.env' \
  --exclude='*.egg-info' --exclude='.pytest_cache' --exclude='.mypy_cache' \
  "$SRC/server/shiksha_engine/" \
  server/shiksha_engine/

git status
# Erwartet: ~10 Files geändert + 5-6 neue
```

**Sanity-Check vor Deploy:** schau einmal kurz drauf:
- `routers/memory.py` (~120 Zeilen)
- `services/insights_extractor.py` (~200 Zeilen — der wichtigste Code des Sprints)
- `middleware/rate_limit.py` (~120 Zeilen)
- `alembic/versions/20260512_0002_*.py` (Migration für rate_limit_buckets)

Falls offensichtlich was schief aussieht → STOPP, melde mir.

---

## Phase B — Local Sanity (optional, nur wenn lokale Dev-DB da ist)

```bash
cd /Users/thomasknodler/code/shiksha/server/shiksha_engine
source .venv/bin/activate

# Migration durchspielen
alembic upgrade head

# Tests
pytest tests/test_memory.py tests/test_sessions_filter.py \
       tests/test_insights_extraction.py tests/test_rate_limit.py \
       -v --tb=short

# Erwartet: alle neuen Tests passed (insights_extraction nutzt Anthropic-Mock,
# braucht also keinen API-Key)
```

Falls keine lokale Dev-DB: direkt Phase C, dort laufen die Tests auf dem Server.

---

## Phase C — Deploy via sync.sh

Jetzt zahlt sich die Investition aus Schritt 1.5 aus:

```bash
cd /Users/thomasknodler/code/shiksha
git add server/shiksha_engine/
git commit -m "$(cat <<'EOF'
feat(engine): Schritt 2 — API-Vervollständigung

- Memory-Router: CRUD über /api/v1/memory (target_operator_id für Developer)
- Sessions-Filter: edition, persona, since, until, has_summary, q
- Session-Close mit Insights-Extraction:
  Zweiter Anthropic-Call beim /close, strukturiertes JSON-Output,
  persistiert summary + observations + frictions + memory_candidates
- Rate-Limit-Middleware (SQL-Counter, rate_limit_buckets):
  200 Calls/Operator/Tag, Developer unlimited, X-RateLimit-Header
- pytest: +14 Tests (memory, sessions_filter, insights_extraction, rate_limit)
- OpenAPI-Tags + operation_ids (vorbereitend für Dev-Console)
EOF
)"
git push

# sync.sh kennt seit Schritt 1.5 das engine-Target
bash deploy/scripts/sync.sh --engine --confirmed
# Erwartet: Pre-Sync-Diff zeigt Files, Confirm, rsync, alembic upgrade head,
#           systemctl restart, sleep 4, Smoke /health → 200, /auth/... → 200
```

---

## Phase D — Production-Smoke (~5 Min)

```bash
# 1. /health
curl -s https://api.shiksha.world/health | jq

# 2. OpenAPI-Endpoints-Liste (production hat /docs zwar disabled, /openapi.json
#    auch. Wir checken nur dass der Server frisch hochgekommen ist.)
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 'curl -s http://127.0.0.1:8001/openapi.json | jq ".paths | keys"'
# Erwartet: Liste enthält /api/v1/memory, /api/v1/memory/{memory_id},
#           /api/v1/memory/count, /api/v1/sessions, /api/v1/chat/close/...

# 3. Rate-Limit-Header sichtbar?
# (Wir können hier nicht authentifiziert testen ohne Mira's Passkey.
#  Anon-Call gibt 401 — das reicht als Smoke. Echter Rate-Limit-Test
#  läuft in pytest auf Production.)
curl -i -X POST https://api.shiksha.world/api/v1/chat/respond \
  -H "Content-Type: application/json" -d '{"user_message":"x"}' 2>&1 | head -10
# Erwartet: 401 Unauthorized

# 4. Migration ist drauf?
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'sudo -u postgres psql -d shiksha -c "\dt shiksha_core.*"'
# Erwartet: 10 Tabellen (+ rate_limit_buckets)

# 5. pytest auf Server, frisch — grep als root, dann env durchreichen
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 <<'REMOTE'
  DB_PW=$(grep -oP "shiksha:\K[^@\"']+" /etc/systemd/system/shiksha.service.d/database.conf | head -1)
  sudo -u shiksha-app env DB_PW="$DB_PW" bash <<'INNER'
    cd /opt/shiksha-engine
    export SHIKSHA_TEST_DATABASE_URL="postgresql://shiksha:${DB_PW}@localhost:5432/shiksha"
    export DB_SCHEMA="shiksha_core_test"
    .venv/bin/pytest -v --tb=short 2>&1 | tail -30
INNER
REMOTE
# Erwartet: 25+ tests passed (11 alte + 14 neue)

# 6. Existing-Services unangetastet
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'systemctl is-active shiksha.service stitch.engine.service shiksha-engine'

# 7. Logs sauber
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'journalctl -u shiksha-engine --since "5 minutes ago" --no-pager | grep -E "ERROR|CRITICAL" || echo "no errors"'
```

---

## Phase E — Smoke-Bericht zurück

```
✓ rsync via sync.sh --engine --confirmed → 0 errors
✓ alembic upgrade head                   → rate_limit_buckets Tabelle da
✓ systemctl restart shiksha-engine        → active (running)
✓ /health (HTTPS)                         → 200, env=production
✓ /openapi.json paths                     → memory + sessions-Filter sichtbar
✓ DB shiksha · shiksha_core               → 10 Tabellen + rate_limit_buckets
✓ pytest auf Server                       → 25+ grün
✓ existing shiksha.service                → active
✓ existing stitch.engine.service          → active
✓ journalctl letzte 5 Min                 → no ERROR
✓ commit + push                           → <commit-hash>
```

---

## Diagnose wenn was hängt

```bash
# Logs
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 'journalctl -u shiksha-engine -n 100 --no-pager'

# Specific: Insights-Extraction-Fehler
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'journalctl -u shiksha-engine -n 200 --no-pager | grep -i "insights\|extract"'

# Migration-Status
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'sudo -u shiksha-app /opt/shiksha-engine/.venv/bin/alembic current'

# rate_limit_buckets-Tabelle existiert?
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  'sudo -u postgres psql -d shiksha -c "SELECT * FROM shiksha_core.rate_limit_buckets LIMIT 5;"'
```

---

## Rollback (falls Migration brennt)

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 <<'REMOTE'
sudo -u shiksha-app bash <<'INNER'
cd /opt/shiksha-engine
DB_PW=$(grep -oP "shiksha:\K[^@\"']+" /etc/systemd/system/shiksha.service.d/database.conf | head -1)
export DATABASE_URL="postgresql://shiksha:${DB_PW}@localhost:5432/shiksha"
export DB_SCHEMA="shiksha_core"
.venv/bin/alembic downgrade -1
INNER

# Code-Rollback per Git
cd /tmp
git clone https://github.com/herrknoedler-cell/shiksha.git shiksha_rollback
cd shiksha_rollback
git checkout <previous-commit-hash>
# rsync nach /opt/shiksha-engine
# systemctl restart shiksha-engine
REMOTE
```

---

## Was DU NICHT tun darfst

```
✗ pytest-Suite übergehen wenn rot — STOPP, melde dich
✗ Migration 0002 manuell ohne alembic auf der Production-DB
✗ Rate-Limit-Middleware-Werte hardcoden (nutzt settings.rate_limit_per_operator_per_day)
✗ ANTHROPIC_API_KEY-Drop-In anfassen (bleibt wie aus Schritt 1)
✗ Existing /opt/shiksha oder /opt/stitch.engine touchen
```

---

**Drop-in-Prompt · 12. Mai 2026 · Schritt 2 von 8 · API-Vervollständigung · Vorbereitung für Frontend-Migration**
