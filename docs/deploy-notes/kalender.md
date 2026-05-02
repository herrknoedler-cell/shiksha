# SHIKSHA · KITA-Kalender — Deploy-Block

Drei Dateien werden ausgespielt:
1. `calendar_migration.sql` → einmalig laufen lassen (DB-Schema)
2. `calendar_router.py` → ans Ende von `/opt/shiksha/kita_compliance_router.py` anhängen
3. `calendar_ui.html` → unter `/opt/shiksha/ui/kita/calendar.html`, gemounted in `accounting_router.py`

---

## 1️⃣ SCP — alle drei Dateien hochladen

```bash
cd outputs/kalender

scp calendar_migration.sql shiksha.tun.zone:/tmp/calendar_migration.sql
scp calendar_router.py     shiksha.tun.zone:/tmp/calendar_router_append.py
scp calendar_ui.html       shiksha.tun.zone:/tmp/calendar.html
```

---

## 2️⃣ SSH — Migration + Router-Patch + UI-Mount

```bash
ssh shiksha.tun.zone <<'EOF'
set -e

# === 2a. Migration ===
sudo -u postgres psql shiksha < /tmp/calendar_migration.sql

# === 2b. Router anhängen ===
echo "" | sudo tee -a /opt/shiksha/kita_compliance_router.py
echo "# === CALENDAR-ROUTER (angehängt) ===" | sudo tee -a /opt/shiksha/kita_compliance_router.py
sudo tee -a /opt/shiksha/kita_compliance_router.py < /tmp/calendar_router_append.py

# === 2c. UI ablegen ===
sudo mkdir -p /opt/shiksha/ui/kita
sudo cp /tmp/calendar.html /opt/shiksha/ui/kita/calendar.html

# === 2d. Mount in accounting_router.py prüfen ===
# (manuell ergänzen, falls noch nicht vorhanden:)
#   @router.get("/ui/kita/calendar")
#   async def kita_calendar_ui():
#       return FileResponse("/opt/shiksha/ui/kita/calendar.html")

# === 2e. Restart ===
sudo systemctl restart shiksha

# === 2f. Smoke-Test ===
sleep 2
curl -s https://shiksha.tun.zone/kita/calendar/event-types | head -c 400
echo
echo "--- Events (leer beim ersten Mal) ---"
curl -s "https://shiksha.tun.zone/kita/calendar/events?from_date=2026-01-01&to_date=2026-12-31" | head -c 400
echo
EOF
```

---

## 3️⃣ Mount in `accounting_router.py` (einmalig)

In `/opt/shiksha/accounting_router.py` ergänzen (irgendwo bei den anderen UI-Mounts):

```python
@router.get("/ui/kita/calendar")
async def kita_calendar_ui():
    return FileResponse("/opt/shiksha/ui/kita/calendar.html")
```

Danach erreichbar unter: **https://shiksha.tun.zone/accounting/ui/kita/calendar**

---

## 4️⃣ Erste Schritte nach Deploy

1. `https://shiksha.tun.zone/accounting/ui/kita/calendar` öffnen
2. Klick auf **🎂 Geburtstage generieren** → erstellt für jedes aktive Kind einen yearly-Geburtstag (Default: 1. Januar des Geburtsjahres)
3. Echte Geburtsdaten manuell pro Kind setzen (Klick auf Event → Datum ändern → Speichern)
4. Manuell anlegen: Schließtage, Sommerfest, Wandertag, Fortbildungen, Elterngespräche

---

## 5️⃣ Bekannte To-Dos / Erweiterungen

- **Recurrence-Expansion** ist aktuell nur für `yearly` (Geburtstage) implementiert — `daily/weekly/monthly` werden gespeichert, aber nicht expandiert. Bei Bedarf erweitern in `calendar_router.py` → `calendar_events_in_range`.
- **Audience-Filter**: Frontend sendet aktuell keinen `audience`-Parameter — alle Events werden für die Trägerin gezeigt. Für Pädagogen-/Eltern-View später `?audience=paedagogin` bzw. `=eltern` ergänzen.
- **Target-Gruppen-Picker**: Modal hat noch keinen UI-Picker für `target_legacy_group_ids` etc. — Backend speichert aber bereits Arrays.
- **Drag&Drop** zum Verschieben von Events: Phase 2.
- **Echtes Geburtsdatum** in `kita_legacy_children` ergänzen (aktuell nur `birth_year`):
  ```sql
  ALTER TABLE kita_legacy_children ADD COLUMN birth_date DATE;
  ```
  Dann `auto-birthdays`-Endpoint anpassen, um echtes Datum zu nehmen wenn vorhanden.
