# SHIKSHA — Projektkontext

## Was ist SHIKSHA
Ein produktives System zur Dokumentenanalyse, Entscheidungsunterstützung und
Orchestrierung. Läuft live unter https://shiksha.tun.zone.

## Stack
- **Server**: Hetzner Nürnberg, Ubuntu 24.04 (ubuntu-4gb-nbg1-1, 88.99.174.186)
- **Backend**: FastAPI auf Port 8000, systemd-Service `shiksha`
- **Datenbank**: PostgreSQL (User: shiksha)
- **Proxy**: Nginx (Let's Encrypt HTTPS)
- **App-Root**: /opt/shiksha
- **Venv**: /opt/shiksha/venv
- **Statische Dateien**: /opt/shiksha/static
- **Nginx-Config**: /etc/nginx/sites-available/shiksha

## Wichtige Dateien
- main.py — FastAPI App, enthält alle Endpoints
- calendar_models.py / calendar_module.py — Kalender-Modul (Stufe 1)
- static/result.html — erster visueller Result-Screen

## Module (Stand V5 + Calendar)
- Dokument-Ingestion und -Analyse
- Accounting (Ledger, Entries, Due Dates)
- Calendar: appointment | deadline | reminder | course_session
- CRM-Felder an Events (contact_name, email, phone, outcome, follow_up)
- Editions-System (business.shiksha)

## Wichtige Endpoints
- GET /health
- POST /accounting/entries
- POST /calendar/events, GET /calendar/events, GET /calendar/upcoming
- POST /calendar/events/{id}/done, /outcome
- POST /calendar/sync/deadlines

## Architektur-Regeln
1. Bestehende Routen niemals überschreiben — Änderungen sind additiv
2. Neue Module als eigene .py-Dateien neben main.py, Routen in main.py in
   klar markierten Blöcken registrieren
3. Nginx-Änderungen immer mit Backup (.bak.YYYYMMDD-HHMMSS)
4. Service-Reload: `systemctl reload shiksha` (FastAPI) bzw.
   `systemctl reload nginx`
5. Statische Dateien in /opt/shiksha/static/, von Nginx direkt ausgeliefert

## Häufige Operationen
- Deploy statische Datei: cp nach /opt/shiksha/static/, Nginx-Location
  existiert schon
- FastAPI-Restart: systemctl restart shiksha && sleep 2 &&
  curl https://shiksha.tun.zone/health
- Nginx-Reload: nginx -t && systemctl reload nginx
- Letztes Backup finden: ls -t /etc/nginx/sites-available/shiksha.bak.*

## Dauerhaft erlaubt (nur lesend)
Folgende Routinen sind reine Lese-/Statusabfragen und dürfen ohne
Rückfrage ausgeführt werden:

- `sudo -u postgres psql -d shiksha -c "SELECT * FROM calendar_events ..."`
- `sudo -u postgres psql -d shiksha -c "\d ..."`
- `curl -s https://shiksha.tun.zone/health`
- `curl -s https://shiksha.tun.zone/calendar/upcoming*`
- `systemctl status shiksha`

Schreibende oder verändernde Operationen (INSERT/UPDATE/DELETE, POST/PUT,
`systemctl restart|reload`, Dateiänderungen) bleiben weiterhin
bestätigungspflichtig.

## Nutzer
Thomas Knödler (herrknoedler@gmail.com). Kein SSH-Experte — bevorzugt klare,
durchdachte Schritte statt Kommando-Stakkato. Deutsche Sprache im Dialog.
