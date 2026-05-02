# SHIKSHA · Deploy

Diese Doku ist für jemanden, der morgen das Repo erbt — sie sollte
ausreichen, um ohne Rückfrage einen Code-Deploy zu fahren. Die Kurzform
ist: aus Repo-Root `bash deploy/scripts/sync.sh --confirmed`.

---

## Stack-Überblick

| Komponente | Wert |
|---|---|
| Server | Hetzner CX21, Ubuntu 24.04 (`ubuntu-4gb-nbg1-1`, `88.99.174.186`) |
| Backend | Python 3.12 + FastAPI auf Port 8000 |
| Datenbank | PostgreSQL 16 (DB-User `shiksha`) |
| Reverse-Proxy | nginx + Let's Encrypt |
| systemd-Service | `shiksha.service` |
| App-Verzeichnis | `/opt/shiksha/` (flach, keine Modul-Subdirs) |
| Venv | `/opt/shiksha/venv/` |
| Statische Dateien | `/opt/shiksha/static/` |
| Aktive Domain | `kita.shiksha.tun.zone` (KITA-Pilot) |
| Geplante Domain | `shiksha.world` (Plattform-Site, Domain wird registriert) |

## Server-Zugang

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186
```

---

## Deploy-Pfade

### Standard: Code + Migrations + Templates

```bash
# Aus dem Repo-Root:
bash deploy/scripts/sync.sh                  # Dry-Run (Default — sicher)
bash deploy/scripts/sync.sh --confirmed      # Echter Sync
```

`sync.sh` macht in dieser Reihenfolge:

1. **Pre-flight** — `git status` clean, branch=main, `server/main.py` da,
   Deploy-Commit-Hash erfassen.
2. **Dry-Run mit `--delete`** — zeigt **zuerst** die Lösch-Liste, dann
   Transfer-Count.
3. **Confirmation-Gate** — ohne `--confirmed` passiert nichts.
4. **`rsync -a --delete server/ → /opt/shiksha/`** mit allen Excludes.
5. **`systemctl restart shiksha`** + `is-active`-Check.
6. **5 Curl-Smoke-Tests** (siehe unten).
7. **Bericht.** Kein Auto-Rollback (würde aus `.bak`-Files restoren —
   riskant).

### Schnell: Nur Templates + UIs

Wenn nur Marketing-Templates oder UIs geändert wurden — kein Service-
Restart nötig (Jinja lädt Templates zur Laufzeit, UIs sind statisch):

```bash
bash deploy/scripts/sync-templates.sh                # Dry-Run
bash deploy/scripts/sync-templates.sh --confirmed    # Push
```

Synct nur `server/marketing_templates/` und `server/ui/`.

---

## Excludes

`sync.sh` syncht alles aus `server/` AUSSER:

| Exclude | Grund |
|---|---|
| `*.bak`, `*.bak.*`, `*.bak.v*` | Auto-Backups historischer Deploy-Skripte |
| `__pycache__/`, `*.pyc` | Python-Build-Artefakte |
| `venv/` | Lokale Python-Umgebung |
| `uploads/` | User-Uploads (Identity-Fotos, Rechnungen) |
| `secrets/` | VAPID-Keys, andere Server-Geheimnisse |
| `archive/` | Runtime-PDF-Archiv der Anwesenheits-Daten |
| `marketing_assets/pool/` | Vom Cron befüllter Bilder-Pool — Runtime-Daten, nicht Repo-Inhalt |
| `*.log`, `tmp/`, `.DS_Store` | Lärm |

---

## Required Environment Variables

Alle Secrets und Konfigurations-Variablen leben außerhalb des Repos —
in Production über systemd-Drop-Ins, lokal über `.env`-Datei (kanonische
Vorlage: [`.env.example`](../.env.example) im Repo-Root). `server/database.py`
liest beim Import zentral, fehlt eine Pflicht-Variable: hard-fail mit
RuntimeError, die direkt auf die richtige Doku-Stelle zeigt.

| Name | Pflicht | Wo gesetzt | Hinweis |
|---|---|---|---|
| `DATABASE_URL` | **ja** | `database.conf` (für `shiksha.service`) **+** `/etc/cron.d/shiksha-insights` (für Cron-Jobs) | `postgresql://shiksha:<pass>@localhost/shiksha` |
| `ANTHROPIC_API_KEY` | für `/marketing/generate`, `/kita/ai/*` | `anthropic.conf` | `sk-ant-...` aus Anthropic Console |
| `VAPID_PRIVATE_KEY` | für Web-Push | `vapid.conf` | absoluter Pfad zur `.pem`-Datei |
| `VAPID_PUBLIC_KEY` | für Web-Push | `vapid.conf` | base64-string aus `vapid_setup.sh` |
| `VAPID_SUBJECT` | für Web-Push | `vapid.conf` | `mailto:thomas@shiksha.tun.zone` |
| `KITA_MAIL_FROM`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `KITA_LEITUNG_EMAIL` | optional | bisher kein eigenes Drop-In | wenn nicht gesetzt: Mail-Versand fällt auf Log-Eintrag zurück |
| `LEGACY_SQLITE_PATH` | nur für `scripts/migrate-kita-legacy/migrate_sqlite_to_pg.py` | shell-export | Default `/opt/shiksha-kita/shiksha_kita.db` |

Drop-Ins liegen alle unter `/etc/systemd/system/shiksha.service.d/<name>.conf`.
Nach Änderung **immer**:

```bash
systemctl daemon-reload && systemctl restart shiksha
```

`.gitignore` deckt `secrets/`, `*.pem`, `*.key`, `vapid_*.json`,
`anthropic_key*`, `.env`, `.env.*` ab — Ausnahme `!.env.example` darf rein.

### `DATABASE_URL`

systemd-Drop-In: `/etc/systemd/system/shiksha.service.d/database.conf`

```ini
[Service]
Environment="DATABASE_URL=postgresql://shiksha:<password>@localhost/shiksha"
```

Code-seitig zentral in `server/database.py`. Importeure (`main.py`,
`accounting_router.py`, `calendar_module.py`, …) holen `engine` von dort —
keine eigenen `create_engine()`-Aufrufe mehr im Repo.

**Cron-Jobs** (`shiksha_insights_cron.py`, `marketing_pool_import.py`,
`fixtures_importer.py`, `safeguarding_cron.py`) brauchen `DATABASE_URL`
ebenfalls. Sie laufen **nicht** als Teil von `shiksha.service` — das
systemd-Drop-In wird also nicht automatisch geerbt. Aktuelle Lösung:
eigene `Environment=`-Zeile in `/etc/cron.d/shiksha-insights`.

Beispiel:

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
DATABASE_URL=postgresql://shiksha:<pass>@localhost/shiksha

0 3 * * *  root  /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py >> /var/log/shiksha-insights.log 2>&1
```

Bei jeder Passwort-Rotation **beide** Stellen synchron updaten —
`database.conf` und `/etc/cron.d/shiksha-insights`. Siehe
[Secret Rotation](#secret-rotation).

### `ANTHROPIC_API_KEY`

systemd-Drop-In: `/etc/systemd/system/shiksha.service.d/anthropic.conf`

```ini
[Service]
Environment="ANTHROPIC_API_KEY=sk-ant-..."
```

### VAPID (Web-Push)

VAPID-Keys liegen unter `/opt/shiksha/secrets/.vapid/`. Erst-Setup auf
dem Server: `bash deploy/scripts/vapid_setup.sh` — generiert das Key-Paar
und schreibt das Drop-In `/etc/systemd/system/shiksha.service.d/vapid.conf`.
Public-Key wird vom Client (`shiksha-push.js`) zum Subscribe gebraucht.

---

## Secret Rotation

Standard-Vorgehen für eine DB-Passwort-Rotation. Ist im Phase-7-Sprint
am 2026-05-02 das erste Mal so durchgespielt worden — funktioniert mit
einer kurzen Auth-Lücke zwischen `ALTER USER` und `restart`, die im
Pilot-Betrieb akzeptabel ist.

```bash
# 1. Neues Passwort generieren (24 Bytes hex, lokal — nie ins Repo)
NEW_PASS=$(openssl rand -hex 24)

# 2. Beide Drop-In-Dateien aktualisieren (Service + Cron)
sudo tee /etc/systemd/system/shiksha.service.d/database.conf <<EOF
[Service]
Environment="DATABASE_URL=postgresql://shiksha:${NEW_PASS}@localhost/shiksha"
EOF
sudo chmod 600 /etc/systemd/system/shiksha.service.d/database.conf

# Cron-Datei: Backup, dann ersetzen
sudo cp /etc/cron.d/shiksha-insights \
        /etc/cron.d/shiksha-insights.$(date +%Y%m%d-%H%M%S).bak
sudo sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://shiksha:${NEW_PASS}@localhost/shiksha|" \
        /etc/cron.d/shiksha-insights

# 3. systemd das neue Env mitteilen (lädt Drop-Ins, KEIN Restart)
sudo systemctl daemon-reload

# 4. PostgreSQL: Passwort umstellen
sudo -u postgres psql -d shiksha -c "ALTER USER shiksha WITH PASSWORD '${NEW_PASS}'"

# 5. Service neu starten — liest jetzt das neue Env
sudo systemctl restart shiksha

# 6. Verifikation
curl -s -o /dev/null -w 'health: %{http_code}\n'   https://kita.shiksha.tun.zone/health
curl -s -o /dev/null -w 'editions: %{http_code}\n' https://kita.shiksha.tun.zone/kita/api/platform/editions
# Altes Passwort muss FATAL geben — Sanity-Check (OLD_PASS lokal in der
# Shell aus dem Rotations-Vorlauf bekannt; nie ins Repo, nie in History):
PGPASSWORD="$OLD_PASS" psql -h localhost -U shiksha -d shiksha -c "SELECT 1" 2>&1 | grep -i 'authentication failed' && echo "✓ altes Passwort invalidiert"

# 7. Variable im Shell-Kontext löschen (kein History-Leak)
unset NEW_PASS
history -d $(history 1)
```

**Reihenfolge ist wichtig:** Step 3 (`daemon-reload`) lädt die Drop-In-
Werte in den Service-Manager, ohne den laufenden Prozess zu touchen.
Step 4 invalidiert das alte Passwort — neue DB-Connections schlagen
fehl, bestehende Connections laufen noch kurz weiter. Step 5 startet
den Service mit dem neuen Env neu, ab dann läuft alles mit dem neuen
Passwort. Auth-Lücke insgesamt ~1-2 Sekunden.

**Falls etwas schief geht** zwischen Step 4 und Step 5:

```bash
# Altes Passwort im PG wiederherstellen (Wert kennst Du aus dem Drop-In
# vor der Rotation oder dem Cron-Backup-File). Service hängt sonst.
sudo -u postgres psql -d shiksha -c "ALTER USER shiksha WITH PASSWORD '<previous-password>'"
sudo systemctl restart shiksha
# Dann Rotation neu starten, sauber.
```

**Audit-Spur:** Cron-Backup-Files in `/etc/cron.d/shiksha-insights.*.bak`
werden bei jeder Rotation automatisch erzeugt — nicht löschen, sind die
History.

---

## nginx-Konfiguration

| Pfad | Zweck |
|---|---|
| `/etc/nginx/sites-available/shiksha` | Haupt-Config |
| `/etc/nginx/sites-available/shiksha.bak.YYYYMMDD-HHMMSS` | Auto-Backups vor Änderungen |

**Wichtige Rewrites:**

- `/m/...` → `/kita/m/...` (FastAPI-Routes leben unter `/kita`-Prefix
  via `kita_router`)
- `/static/...` → direkt aus `/opt/shiksha/static/` ausgeliefert

Bei nginx-Änderungen:

```bash
# Backup vorher
cp /etc/nginx/sites-available/shiksha \
   /etc/nginx/sites-available/shiksha.bak.$(date +%Y%m%d-%H%M%S)

# Edit, dann
nginx -t && systemctl reload nginx
```

Letzten nginx-Backup finden:

```bash
ls -t /etc/nginx/sites-available/shiksha.bak.* | head -1
```

---

## Datenbank-Migrations

`sync.sh` synct die `*_migration.sql`-Files nach `/opt/shiksha/`, wendet
sie aber **nicht automatisch** an. Manuell mit:

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 \
  "sudo -u postgres psql -d shiksha -f /opt/shiksha/<migration>.sql"
```

Alle Migrations sind idempotent (`CREATE TABLE IF NOT EXISTS`,
`CREATE INDEX IF NOT EXISTS`) — safe re-run.

---

## Smoke-Test-URLs

Genau die Liste, die `sync.sh` automatisch nach Deploy testet:

- `GET /health`
- `GET /kita/api/platform/editions`     (sollte 6 Editionen liefern)
- `GET /kita/api/platform/live-stats`   (sollte `modules_live > 0`)
- `GET /m/krummelus`                    (Marketing-Site Krummelus, 200)
- `GET /accounting/ui/kita/dashboard_traegerin`

Bei einem Fehlschlag in einem davon: kein Auto-Rollback. Bericht zeigt
welche URL fehlt, manueller Eingriff. Häufigste Ursache: Service-Restart-
Fehler (siehe `journalctl -u shiksha -n 50 --no-pager`).

---

## Rollback

Falls ein Deploy schiefgeht:

1. `git revert <bad-commit>` lokal.
2. `bash deploy/scripts/sync.sh --confirmed` — synct den Revert.
3. Smoke-Tests grün?

Beispiel aus Phase 4: erster `--confirmed`-Lauf hatte ImportError wegen
inkompatibler `compression.py`-Version. Recovery: `git show <safe-commit>:server/compression.py > server/compression.py`,
neuer Commit `revert: restore working compression.py`, redeploy. ~30 Sekunden.

---

## Häufige Operationen

```bash
# Service-Status / Logs
systemctl status shiksha
journalctl -u shiksha -n 50 --no-pager

# Health-Check
curl https://kita.shiksha.tun.zone/health

# DB-Schema (read-only — siehe CLAUDE.md "Dauerhaft erlaubt")
sudo -u postgres psql -d shiksha -c "\dt"
sudo -u postgres psql -d shiksha -c "\d <tabelle>"

# Letzten nginx-Backup finden
ls -t /etc/nginx/sites-available/shiksha.bak.*
```

---

## Architektur-Regel: Keine neuen Endpoints an `kita_compliance_router.py` anhängen

Historisch wurden viele Module via `echo >> kita_compliance_router.py`
deployt. Resultat: ein 5178-Zeilen-Omnibus-Router mit Routing-Konflikten.
Phase 4 hat das erste Modul herausgelöst (`world_router.py`). Neue Module
gehören als **eigenständiger** `APIRouter` ins Repo, in `main.py` registriert
**vor** `kita_router` wenn sie spezifischere Routes als der dortige
Catch-all haben. Siehe [`ARCHITECTURE.md`](ARCHITECTURE.md) für die
Decomposition-Roadmap.

---

## Lessons aus Phase 4

- **Pre-flight check ist nicht Optional.** Ohne ihn würde ein dirty
  working tree silent in production landen.
- **Confirmation-Gate für `--delete`.** Erste Bug-Fang-Stelle: das
  Pool-Verzeichnis-Problem (`marketing_assets/pool/` nach `git clone`
  nicht da → `--delete` würde server-seitig löschen). Im Dry-Run-Output
  sofort sichtbar.
- **API-Kompatibilität bei File-Overlays prüfen.** Datum/Größe allein
  reicht nicht — siehe Phase-4-Recovery (compression.py-Inkompatibilität).
  Quick-Check: `diff <(grep '^def \|^class ' alt) <(grep '^def \|^class ' neu)`.
- **Smoke-Tests sind wertvoll, auch wenn sie nicht alles fangen.**
  In Phase 4 hat der Service-Status-Check den ImportError sofort offenbart.
  Smoke-Test-Failures != Auto-Rollback — manueller Eingriff.
