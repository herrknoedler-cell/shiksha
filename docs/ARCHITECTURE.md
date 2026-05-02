# SHIKSHA · Architektur

> "Editionen sind Konfiguration, nicht Codeforks."

SHIKSHA hat vier Schichten: ein Plattform-Layer, der die Editionen
sichtbar macht; ein Edition-Layer, der die domänenspezifische Logik
trägt; ein Cross-Edition-Layer mit Modulen, die jede Edition nutzen
kann; und ein operationaler Layer für Crons, Importer und Deploy-
Tooling. Ein Server, ein Service, ein Deploy.

---

## 1. Plattform-Layer (`shiksha.world`)

Außenseite der Plattform, public-facing.

| Element | Pfad | Zweck |
|---|---|---|
| `world_router.py` | `server/world_router.py` | Plattform-Site + community-Vorschläge + Live-Stats |
| `platform_meta.html` | `server/marketing_templates/platform_meta.html` | GSAP-Plattform-Site-Template |
| `editions` (DB) | — | Kuratierte Editions-Galerie |
| `edition_proposals` (DB) | — | Community-Vorschläge mit Upvote |
| `shiksha_modules` (DB) | — | Modul-Showcase für Live-Daten |

**Route-Beispiele:**

- `GET /m/shiksha` → Plattform-Site (53 KB GSAP-HTML)
- `GET /kita/api/platform/editions` → Editions-Liste
- `GET /kita/api/platform/live-stats` → Modul-Statistik (anonymisiert)
- `GET /kita/api/platform/greeting` → Tageszeit-Anrede für Hero
- `POST /kita/api/platform/proposals` → community Edition-Vorschlag

In Phase 4 als eigenständiges Modul aus dem KITA-Omnibus extrahiert
(Commit `cc9dc68`). Erstes Beispiel der Decomposition-Roadmap.

---

## 2. Edition-Layer

Eine Edition pro Domäne, mit eigenem Modell, Orchestrator, Routen, UIs.

| Edition | Status | Server-Files |
|---|---|---|
| KITA | **live** | `kita_compliance_router.py` (omnibus, ~5178 Zeilen), `kita_compliance_engine.py`, `kita_compliance_models.py`, plus `kita_ui/`, `paedagogen_ui/`, `ui/kita/` |
| Camping | **Beta** | `camping_models.py`, `camping_orchestrator.py`, `camping_db_migration.sql`, `ui/camping_*.html` |
| Schule (Yoga/Surf/Reit/Tanz/Ski) | **geplant** | `schule_models.py`, `schule_orchestrator.py`, `schule_db_migration.sql`, `ui/schule_*.html` |
| Club (Vereine) | **geplant** | nur Build-Pack ([`build-packs/club.md`](build-packs/club.md)) |

Status pro Edition + Roadmap: [`EDITIONS.md`](EDITIONS.md).

---

## 3. Cross-Edition-Module

Module, die von beliebigen Editionen genutzt werden. Jedes hat eigene
Tabellen, eigene Routen, eigenen Lifecycle.

| Modul | Server-Files | Was es tut |
|---|---|---|
| **Identity** | `identity_router.py`, `identity_migration.sql`, `identity_ui/` | Cross-Edition-Personenerfassung mit OCR/MRZ |
| **Calendar** | `calendar_module.py`, `calendar_models.py`, `calendar_migration.sql` (KITA-Erweiterung) | Termine, Geburtstage, Schließtage, Course-Sessions |
| **Personen** | `personen_router.py`, `personen_migration.sql` | Stammdaten + Auto-Birthday-Sync nach Calendar |
| **Push** | `push_router.py`, `push_migration.sql`, `service-worker.js`, `shiksha-push.js` | VAPID-signed Web-Push |
| **Greeting** | `greeting_router.py`, `greeting_migration.sql`, `data/knowledge_bites.json`, `shiksha_insights_cron.py` | 5-Layer-Begrüßung (Wochen-Thema, Knowledge-Bite, ST%-Insight, Anlässe, Cross-Edition-Lernen) |
| **Dashboard** | `dashboard_router.py`, `dashboard_migration.sql`, `shiksha-cards.{js,css}` | Gridstack-Card-System pro User-Rolle |
| **Marketing** | `marketing_router.py`, `marketing_migration.sql`, `marketing_templates/`, `marketing_pool_import.py` | Site-Generator mit Claude-AI |
| **Archive** | `anwesenheit_router.py`, `archive_migration.sql` | Anwesenheits-PDF-Archiv (Cron) |
| **Safeguarding** | `safeguarding_router.py`, `safeguarding_orchestrator.py`, `safeguarding_db_migration.sql`, `safeguarding_cron.py` | Aufsichtspflicht (Pool, Spielplatz, Werkstatt) |
| **Documents** | `document_module.py`, `document_models.py`, `compression.py`, `extractor_extensions.py`, `documents_endpoint.py` | OCR, MRZ, Field-Extraction |
| **Accounting** | `accounting_router.py`, `accounting_models.py`, `accounting_orchestrator.py`, `bank_statement_parser.py` | Ledger, Invoices, Cashbook, Lieferanten |

---

## 4. Operationaler Layer

| File | Zweck |
|---|---|
| `main.py` | FastAPI-App-Wurzel, Router-Registration |
| `database.py` | DB-Connection (siehe [`tech-debt.md`](tech-debt.md) — hardcoded credentials) |
| `shiksha_insights_cron.py` | Tägliches Insights-Update für Greeting |
| `kita_compliance_cron.py` | KITA-Compliance-Jobs |
| `safeguarding_cron.py` | Safeguarding-Checks + Eskalation |
| `fixtures_importer.py` | Edition-Seed-Importer (idempotent, `--schule` / `--camping` / `--all-in`) |
| `marketing_pool_import.py` | Firefly-Bilder-Pool-Importer |

---

## Der Omnibus-Router — und seine Decomposition

`server/kita_compliance_router.py` ist auf 5178 Zeilen gewachsen, weil
viele Cowork-Module historisch via `*_deploy.sh`-`echo >>` an ihn
angehängt wurden statt als eigenständige Router registriert. Phase 4
hat den ersten Schritt der Decomposition gemacht — `world` ist raus.

| Bereich | Status | Audit-Snippet |
|---|---|---|
| World (Plattform-Endpoints) | **extrahiert** in `server/world_router.py` (Commit `cc9dc68`) | — |
| KITA-Calendar | appended | `docs/legacy/calendar-router-snippet.py` |
| KITA-Anmeldung | appended | `docs/legacy/kita-anmeldung-endpoint-snippet.py` |
| KITA-Documents | appended | `docs/legacy/kita-document-endpoints-snippet.py` |
| KITA-Notifications | appended | `docs/legacy/kita-notifications-endpoints-snippet.py` |
| KITA-ST%-Rechner | appended | `docs/legacy/kita-st-calc-{endpoints,auto}-snippet.py` |
| Marketing `/m/{slug}` | appended | (kein Snippet — `marketing_router.py` als dangling File auf der Disk vorhanden, aber nicht von `main.py` importiert; der wirksame Code lebt im Omnibus) |
| Accounting Phasen-Endpoints | appended | `docs/legacy/accounting-{invoices-v2,phase2-endpoints,phase3-edit,phase4-endpoints,re-extract-route}-snippet.py` |

**Decomposition-Roadmap** (jeweils eigener Sprint, nicht im Akkord):

1. **Calendar-Router** — mittel; eigene Tabellen-Domäne (`kita_calendar_events`), klar abgegrenzt
2. **Notifications-Router** — mittel
3. **ST%-Rechner** — klein; kompakte Endpoint-Gruppe
4. **Anmeldung-Router** — groß; 2-Signaturen-Wizard, viele Flows
5. **Documents-Router** — groß; OCR + MRZ + Field-Extraction
6. **Accounting-Router** — groß; viele Phasen, eigene UIs

Pattern für jede Extraktion: Snippet aus `docs/legacy/` als Ausgangspunkt,
neuer `APIRouter` mit passendem Prefix, in `main.py` **vor** `kita_router`
registrieren. Routing-Konflikte vermeiden: Specific Routes vor Catch-alls.

---

## Architektur-Regel: Keine neuen Endpoints an `kita_compliance_router.py` anhängen

Phase 4 hat gezeigt, was passiert, wenn der Omnibus weiter wächst:
Routing-Konflikte (`/m/shiksha` 404 weil `/m/{slug}`-Catch-all
zuerst registriert), API-Kollisionen, unleserliche Diffs, brüchige
Refactors. Neue Module gehören als **eigenständiger** `APIRouter`
ins Repo, in `main.py` registriert in der richtigen Reihenfolge.

---

## Datenfluss-Skizze

Siehe [`architecture-map.md`](architecture-map.md) für die kontinuierlich
gepflegte Modul-Map mit Status-Matrix und bekannten Verbindungs-Lücken
zwischen Modulen (z.B. KITA-Legacy ↔ Compliance-Engine).

---

**Verwandte Dokumente:**

- [`EDITIONS.md`](EDITIONS.md) — alle 6 Editionen mit Status und Roadmap
- [`DEPLOY.md`](DEPLOY.md) — Server-Setup, Secrets, sync.sh-Workflow
- [`COWORK.md`](COWORK.md) — was bleibt in Cowork
- [`tech-debt.md`](tech-debt.md) — bekannte offene Schulden
- [`architecture-map.md`](architecture-map.md) — Living-Map mit Status pro Modul
- [`build-packs/`](build-packs/) — Edition-Specs und Module-Konzepte
- [`legacy/`](legacy/) — Audit-Snippets für noch-im-Omnibus-lebende Code-Fragmente
