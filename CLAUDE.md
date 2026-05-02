# SHIKSHA — Projektkontext

## Was ist SHIKSHA

Eine Multi-Edition-Plattform für KITAs, Campingplätze, Surf- und
Yogaschulen, Vereine und Schulen. Sechs Editionen aktuell sichtbar
(KITA live, Camping Beta, Schule/Surfschule/Yogaschule/Club geplant),
Plattform-Site unter `https://kita.shiksha.tun.zone/m/shiksha`.

Ein Server, ein Service, ein Deploy. Editionen sind Konfiguration,
nicht Codeforks.

## Stack

- **Server**: Hetzner Nürnberg, Ubuntu 24.04 (`ubuntu-4gb-nbg1-1`, `88.99.174.186`)
- **Backend**: Python 3.12 + FastAPI auf Port 8000, systemd-Service `shiksha`
- **Datenbank**: PostgreSQL 16 (DB-User `shiksha`)
- **Proxy**: Nginx (Let's Encrypt HTTPS)
- **App-Root**: `/opt/shiksha/` (flach — keine Modul-Subdirs)
- **Venv**: `/opt/shiksha/venv/`
- **Statische Dateien**: `/opt/shiksha/static/`
- **Nginx-Config**: `/etc/nginx/sites-available/shiksha`
- **Aktive Domain**: `kita.shiksha.tun.zone`

## Architektur in vier Schichten

1. **Plattform-Layer** — `world_router.py` (Plattform-Site, Editions-
   Galerie, community-Vorschläge, Live-Stats).
2. **Edition-Layer** — KITA (omnibus), Camping, Schule (Yoga/Surf/Reit/
   Tanz/Ski), Club. Pro Edition: eigene Modelle, eigener Orchestrator,
   eigene UIs.
3. **Cross-Edition-Module** — Identity, Calendar, Personen, Push,
   Greeting, Dashboard, Marketing, Archive, Safeguarding, Documents,
   Accounting.
4. **Operationaler Layer** — `main.py`, `database.py`, Crons, Importer.

Vollständige Modul-Übersicht: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Wichtige Dateien

- `server/main.py` — FastAPI App-Wurzel, Router-Registration
- `server/kita_compliance_router.py` — KITA-Edition-Omnibus (~5178 Zeilen,
  Decomposition läuft, world ist bereits raus)
- `server/world_router.py` — Plattform-Endpoints (Phase 4 extrahiert)
- `server/database.py` — DB-Connection (siehe `docs/tech-debt.md`)
- Alle weiteren `*_router.py` und `*_module.py` flat unter `server/` —
  passend zum flachen `/opt/shiksha/`-Layout

## Wichtige Endpoints

- `GET /health`
- `GET /m/shiksha` — Plattform-Site
- `GET /m/{slug}` — Marketing-Site einer KITA (Catch-all)
- `GET /kita/api/platform/editions` — alle Editionen
- `GET /kita/api/platform/live-stats` — Modul-Statistik
- `GET /accounting/ui/kita/dashboard_traegerin` — Trägerin-Dashboard
- `GET /calendar/upcoming` — Generic-Calendar
- `POST /accounting/entries`

## Architektur-Regeln

1. **Bestehende Routen nicht überschreiben** — Änderungen sind additiv.
   Bei Routing-Konflikten (Catch-all vs. Specific): eigenen Router
   schreiben und in `main.py` **vor** dem konfliktierenden Router
   registrieren — FastAPI evaluiert in Registrations-Reihenfolge.
2. **Keine neuen Endpoints an `kita_compliance_router.py` anhängen.**
   Historisch wurden viele Module via `echo >> kita_compliance_router.py`
   deployt — Phase 4 hat das umgekehrt. Neue Module sind eigenständige
   `APIRouter`-Module in `server/`, in `main.py` registriert.
3. **nginx-Änderungen immer mit Backup** (`.bak.YYYYMMDD-HHMMSS`).
4. **Service-Reload**: `systemctl restart shiksha` (FastAPI) bzw.
   `systemctl reload nginx`.
5. **Statische Dateien** in `/opt/shiksha/static/`, von nginx direkt
   ausgeliefert.
6. **Bei File-Overlays**: API-Kompatibilität zum Caller verifizieren.
   Datum allein reicht nicht — siehe Phase-4-Recovery in
   `docs/tech-debt.md` (compression.py-Refactor war Draft, brach den
   Service beim Overlay).

## Häufige Operationen

```bash
# Deploy: Code + Migrations + Templates
bash deploy/scripts/sync.sh                  # Dry-Run (Default — sicher)
bash deploy/scripts/sync.sh --confirmed      # Echter Sync

# Schneller Pfad: nur Templates + UIs (kein Restart)
bash deploy/scripts/sync-templates.sh --confirmed

# Service-Status / Logs
systemctl status shiksha
journalctl -u shiksha -n 50 --no-pager

# Health-Check
curl https://kita.shiksha.tun.zone/health

# DB-Schema (read-only)
sudo -u postgres psql -d shiksha -c "\dt"
```

Mehr in [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Dauerhaft erlaubt (nur lesend)

Folgende Routinen sind reine Lese-/Statusabfragen und dürfen ohne
Rückfrage ausgeführt werden:

- `sudo -u postgres psql -d shiksha -c "SELECT * FROM …"`
- `sudo -u postgres psql -d shiksha -c "\d …"`
- `curl -s https://kita.shiksha.tun.zone/health`
- `curl -s https://kita.shiksha.tun.zone/kita/api/platform/…`
- `curl -s https://kita.shiksha.tun.zone/calendar/upcoming*`
- `systemctl status shiksha`
- `journalctl -u shiksha -n <N> --no-pager`

Schreibende oder verändernde Operationen (INSERT/UPDATE/DELETE,
POST/PUT, `systemctl restart|reload`, Dateiänderungen) bleiben
weiterhin bestätigungspflichtig.

## Tech-Debt im Auge behalten

[`docs/tech-debt.md`](docs/tech-debt.md) ist die lebende Liste —
aktuell zwei offene Einträge: ein Critical Security Debt (hardcoded
DB-Credentials in `calendar_module.py`) und ein Unfinished Refactor
(Document-Compression-Split). Beide bekommen eigene Mini-Sprints
nach Phase 6.

## Nutzer

Thomas Knödler (`herrknoedler@gmail.com`). Solo-Founder. Kein SSH-Experte —
bevorzugt klare, durchdachte Schritte statt Kommando-Stakkato. Deutsche
Sprache im Dialog. SHIKSHA-Stimme: warmer älterer Kollege, klar, präzise,
kein Corporate-Sprech.
