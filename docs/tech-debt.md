# Tech-Schulden

Lebende Liste — offene Findings (**Critical Security Debt** +
**Unfinished Refactors**) sowie ein **Operational Audit Trail** über
bereits aufgelöste Einträge und operationale Cleanups. Sobald ein
Eintrag behoben ist: nicht löschen, sondern auf RESOLVED-Status mit
Datum + Commit-Hash umstellen — die Datei wird so zur lesbaren Historie.

---

## Critical Security Debt

### ✅ Hardcoded DB-Credentials in 9 server files — RESOLVED 2026-05-02

|                  |                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------ |
| **Status**       | **RESOLVED 2026-05-02** (Phase 7 — Audit + Refactor + Server-Rotation)                           |
| **Resolved-by**  | Commits [`0c4864a`](../../../commit/0c4864a) (refactor) + [`7576467`](../../../commit/7576467) (docs), plus server-side Rotation am gleichen Tag |
| **Found**        | 2026-05-02 (initial: Phase-2-Migration, A.5 Kalender; voller Umfang via Phase-7-Audit)           |
| **File(s)**      | `server/database.py`, `server/main.py` (4×), `server/calendar_module.py`, `server/accounting_module.py`, `server/accounting_router.py`, `server/documents_endpoint.py`, `server/document_module.py`, plus `scripts/migrate-kita-legacy/migrate_sqlite_to_pg.py` |

**Was passiert ist:**

1. **Code:** Zentrale env-driven Engine in `server/database.py` mit
   Hard-Fail-Pattern bei fehlender `DATABASE_URL`. Alle Caller importieren
   `engine` von dort, niemand ruft mehr `create_engine()` mit Klartext-URL.
2. **Server:** Neues Passwort generiert via `openssl rand -hex 24`, gesetzt
   in `/etc/systemd/system/shiksha.service.d/database.conf` (root-only)
   sowie `/etc/cron.d/shiksha-insights` (für Cron-Jobs, die nicht zur
   `shiksha.service` gehören und das Drop-In nicht erben).
3. **PostgreSQL:** `ALTER USER shiksha WITH PASSWORD '<new>'` — der
   alte Wert ist invalidiert.
4. **Naming-Vereinheitlichung:** psycopg-Scripts (`fixtures_importer`,
   `safeguarding_cron`) auf `DATABASE_URL` migriert; das vorherige
   `SHIKSHA_DB_*`-Schema ist abgeschafft.

**Audit-Spur:**

- Cron-Backup vor Rotation: `/etc/cron.d/shiksha-insights.20260502-123423.bak`
  (zeigt den State ohne `DATABASE_URL=`-Zeile).
- Git-History des alten Passworts wurde **nicht** rewritten — Rotation
  macht den alten Wert kraftlos.
- **Pre-Commit-Hook für Secret-Detection** (`gitleaks` / `trufflehog`)
  bleibt offen als eigener kleiner Folge-Sprint.

**Runbook für künftige Rotationen:** siehe
[`DEPLOY.md → Secret Rotation`](DEPLOY.md#secret-rotation).

---

## Unfinished Refactors

Angefangene Umbauten, deren beide Hälften nie zusammen deployt wurden.
Solche WIP-Drafts sind tickende Bomben: harmlos solange niemand sie
anfasst, aber bei der nächsten Migration brechen sie was — siehe
Phase-4-Recovery weiter unten.

### Document-Compression-Refactor (`compression.py` ↔ `document_module_extensions.py`)

|             |                                                              |
| ----------- | ------------------------------------------------------------ |
| **Risiko**  | Medium — Service-Crash beim nächsten falschen Overlay        |
| **Found**   | 2026-05-02 (Phase 4 — erster `sync.sh --confirmed`-Lauf)     |
| **Files**   | `server/compression.py` (production), `server/document_module_extensions.py` (orphan) |

**Befund:** In Cowork wurde ein Refactor begonnen, der die generische
`compress(analysis) → DocumentSummary`-API in Per-Document-Type-
Funktionen aufspaltet:

```
compress_invoice / _dunning / _enrollment_form / _meter_reading /
_behoerden_bescheid / _delivery_note / _weather_postponement /
_guest_complaint  →  DocumentDigest
```

`document_module_extensions.py` enthält die zugehörigen Pydantic-Models
für die neuen Doc-Types. **Aber:** `main.py` wurde nie auf die neue
API umgestellt, kein Doc-Type-Routing eingebaut. Die Files sind
zusammen nur halb da.

In Phase 4 hat ein "newer-wins"-Overlay die neue `compression.py`
deployt; Service ist im ImportError gelandet (`from compression import
compress` schlug fehl). Recovery: chirurgischer Revert zur alten Version
in Commit `181cd87`.

`document_module_extensions.py` liegt seither als **Orphan** im Repo —
nicht importiert, harmlos für den Moment, aber jeder, der es liest,
wird sich fragen, was es soll.

**Fix-Pfad — zwei Optionen:**

A) **Refactor zu Ende bringen.** `main.py` auf Doc-Type-Detection
   umstellen, Routing der eingehenden Documents in den richtigen
   `compress_*`-Pfad, `compression.py` auf die neue API ziehen,
   `document_module_extensions.py` ans Doc-Type-Routing andocken.
   Schätzung: 1-2 Stunden, plus Test.

B) **Refactor verwerfen.** `document_module_extensions.py` löschen,
   alte `compression.py` als kanonisch markieren. Schätzung: 5 Minuten.

Entscheidung hängt davon ab, ob die Per-Doc-Type-Compression einen
echten Mehrwert bringt (besseres Field-Extraction-Routing, klarere
Domain-Models pro Doc-Type) oder nur Komplexität ohne Gegenleistung.

**Plan:** Eigener Mini-Sprint nach Phase 7.

### ⏳ Setup-Token-Service ist process-local (in-memory dict) — OPEN

|              |                                                              |
| ------------ | ------------------------------------------------------------ |
| **Severity** | Low — bei Multi-Worker oder Service-Restart Token-Verlust    |
| **Found**    | 2026-05-12 (Schritt-3-Deploy, Phase E)                       |
| **File(s)**  | `server/shiksha_engine/services/setup_token_service.py`      |
| **Resolves** | Schritt 4 (Tool-Calling) oder eigener Refactor-Sprint        |

**Symptom:** `_tokens: dict[str, ...]` lebt im Prozess-Speicher des
uvicorn-Workers. Bei `--workers 2`: nur einer der Worker sieht den Token.
Bei `systemctl restart`: Token weg. Bei `python -m scripts.issue_token`:
isolierter Subprozess, Token NIE im Worker.

**Workaround heute:** Token ausschließlich via API erzeugen
(POST /api/v1/dev/setup-tokens mit Developer-JWT) — der Endpoint läuft
im Worker, also ist der Token sofort dort verfügbar. Für Erst-Setup
ohne bestehende Credentials braucht's keinen Token (auth.py-Logik).

**Fix-Pfad:** Redis als Token-Store, oder PostgreSQL-Tabelle
`setup_tokens(token PK, operator_id, expires_at, consumed_at)`. SQL ist
konsistent mit Rate-Limit-Pattern aus Schritt 2.4 — Redis nur wenn
mehrere Server.

**Lesson:** Bei jedem in-memory Store: testen *welcher Prozess
genau* schreibt vs. liest. uvicorn Workers haben getrennten Speicher.

---

## Operational Audit Trail

Nicht-Sicherheits-Cleanups, die wir gemacht haben — dokumentiert
inklusive Restore-Pfad für den unwahrscheinlichen Fall, dass jemand
sie rückgängig machen muss.

### shiksha-kita Legacy-Service archiviert (2026-05-02)

|              |                                                                                                                                          |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Status**   | **ARCHIVED 2026-05-02** (Phase-7-Side-Discovery)                                                                                         |
| **Where**    | `/opt/_archive/shiksha-kita-20260502-123423/` (App-Verzeichnis), `/etc/systemd/system/shiksha-kita.service.20260502-123423.bak` (Service-Datei-Backup) |

**Kontext:** Beim Audit für Phase 7 (Secret-Rotation) wurde der Legacy-
KITA-Service auf Port 8001 (alte SQLite-App) entdeckt. Die echten Pilot-
Daten — 18 Kinder + 5 Mitarbeiter — sind seit der Compliance-Engine-
Migration in der PostgreSQL-DB; der Legacy-Service war seither inaktiv
im Workflow, lief aber weiter und hatte das alte DB-Passwort hardcoded.
Statt mit-zu-rotieren: sauber stillgelegt.

**Was passiert ist:**

```bash
systemctl disable --now shiksha-kita
mv /opt/shiksha-kita /opt/_archive/shiksha-kita-20260502-123423
cp /etc/systemd/system/shiksha-kita.service \
   /etc/systemd/system/shiksha-kita.service.20260502-123423.bak
```

**Restore-Pfad** (sehr unwahrscheinlich nötig):

```bash
mv /opt/_archive/shiksha-kita-20260502-123423 /opt/shiksha-kita
cp /etc/systemd/system/shiksha-kita.service.20260502-123423.bak \
   /etc/systemd/system/shiksha-kita.service
systemctl daemon-reload
systemctl enable --now shiksha-kita
```

Cutover-Tooling unter [`scripts/migrate-kita-legacy/`](../scripts/migrate-kita-legacy/)
bleibt im Repo — falls jemals rückwärts migriert oder aus der archivierten
SQLite-DB nachgelesen werden muss.

### ✅ Transitive Deps explizit deklarieren — RESOLVED 2026-05-11

|              |                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------ |
| **Severity** | Medium — Service-Crashloop beim ersten Start, vor erstem produktiven Traffic gefangen            |
| **Found**    | 2026-05-11 (Schritt-1-Deploy SHIKSHA-Engine)                                                     |
| **File(s)**  | `server/shiksha_engine/pyproject.toml`                                                           |
| **Fixed-by** | Commit [`79b4cc6`](../../../commit/79b4cc6)                                                      |

**Symptom:** Auf dem Server `ModuleNotFoundError: email_validator` beim
Service-Start der SHIKSHA-Engine. `pydantic.EmailStr` (genutzt via WebAuthn-
Schemas) braucht `email-validator`; das war in der lokalen Entwicklungs-
Umgebung transitiv über `pydantic` da, in der frischen Production-venv
aber nicht.

**Fix:** `pyproject.toml` deklariert jetzt `pydantic[email]` statt `pydantic`
— der `[email]`-Extra-Marker zieht `email-validator` explizit. Niemals auf
transitive Pulls verlassen, wenn ein optionaler Extra gebraucht wird.

**Lesson:** Bei pydantic + WebAuthn-Schemas (oder allem, was `EmailStr`
nutzt): immer `pydantic[email]` mit Extra-Marker deklarieren. Gleiches
Prinzip gilt für `pydantic[timezone]`, `passlib[bcrypt]`, `python-jose
[cryptography]` — alle bereits korrekt im pyproject mit Extras.

### ✅ sync.sh-.venv-chmod-Bug — RESOLVED 2026-05-12

|              |                                                                                                  |
| ------------ | ------------------------------------------------------------------------------------------------ |
| **Severity** | High — latenter Production-Killer beim nächsten Engine-Sync                                      |
| **Found**    | 2026-05-12 (Schritt-2-Pre-Flight)                                                                |
| **File(s)**  | `deploy/scripts/sync.sh`                                                                         |
| **Fixed-by** | Commit [`820fdfa`](../../../commit/820fdfa)                                                      |

**Symptom:** sync.sh setzt nach rsync `chmod -R 644` auf den Engine-Zielpfad.
Das überschreibt auch die Executable-Bits in `/opt/shiksha-engine/.venv/bin/*`
(uvicorn, python, alembic, pytest), wodurch beim nächsten `systemctl restart`
der Service nicht mehr startet.

**Fix:** chmod-Aufruf schließt `.venv/` aus —
`find ... -not -path '*/.venv*' -exec chmod 644 {} +`. Plus: chmod-Block kommt
erst nach den rsync-Excludes, damit das Pattern wirkt.

**Lesson:** Bei post-rsync-Permissionizing immer venv/dist/build-Pfade
ausnehmen — Executable-Bits in venv-Symlinks sind nicht regenerierbar ohne
`pip install -e`.

---

## Wie ein neuer Eintrag aussieht

```markdown
### <kurze Beschreibung des Befunds>

|             |                                |
| ----------- | ------------------------------ |
| **Severity** oder **Risiko** | Critical / High / Medium / Low |
| **Found**   | YYYY-MM-DD (Quelle / Sprint)   |
| **File(s)** | `pfad/zur/datei.py:Zeile`      |

**Befund:** <was ist los, in einem Absatz>

**Fix-Pfad:** <konkrete Schritte>

**Plan:** <wann / Sprint>
```
