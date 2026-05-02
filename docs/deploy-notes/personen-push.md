# SHIKSHA · Personen + Push — Deploy-Anleitung

## Übersicht der Files

| Datei | Wohin | Was |
|---|---|---|
| `personen/personen_migration.sql` | DB | erweitert kita_legacy_staff + kita_legacy_children um Stammdaten-Spalten |
| `personen/personen_router.py` | append → kita_compliance_router.py | CRUD + Auto-Birthday-Sync |
| `personen/personen_ui.html` | /opt/shiksha/ui/kita/personen.html | Trägerin-UI |
| `personen/calendar_types_patch.py` | manuell editieren | erweiterte EVENT_TYPE_*-Dicts |
| `push/push_migration.sql` | DB | push_subscriptions + push_send_log |
| `push/push_router.py` | append → kita_compliance_router.py | Subscribe + Send + Log |
| `push/service-worker.js` | /opt/shiksha/ui/kita/service-worker.js | Push-Handler |
| `push/shiksha-push.js` | /opt/shiksha/ui/kita/shiksha-push.js | Subscribe-Helper |
| `push/push_sender_ui.html` | /opt/shiksha/ui/kita/push.html | Send-UI für Trägerin |

---

## 1️⃣ VAPID-Keys generieren (einmalig)

Auf dem Server:

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186

# pywebpush + py-vapid installieren
cd /opt/shiksha
source venv/bin/activate
pip install pywebpush py-vapid

# Key-Pair erzeugen
cd /opt/shiksha/secrets   # oder /etc/shiksha/, je nachdem wo .env liegt
mkdir -p .vapid && cd .vapid
vapid --gen
# → erzeugt private_key.pem + public_key.pem

# Keys in .env-tauglichem Format ausgeben
echo "VAPID_PRIVATE_KEY=$(python3 -c 'from py_vapid import Vapid; v = Vapid.from_file("private_key.pem"); print(v.private_pem().decode().replace(chr(10), chr(92)+"n"))')"
echo "VAPID_PUBLIC_KEY=$(vapid --applicationServerKey)"
```

Dann in `/opt/shiksha/.env` (oder dem entsprechenden Env-File) ablegen:

```
VAPID_PRIVATE_KEY=-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----
VAPID_PUBLIC_KEY=BFx...   # url-safe base64
VAPID_SUBJECT=mailto:thomas@shiksha.tun.zone
```

---

## 2️⃣ Files hochladen (auf dem Mac)

```bash
PERS="/Users/thomasknodler/Library/Application Support/Claude/local-agent-mode-sessions/afe14d15-f202-489c-993c-b4935c648d43/f7099d1a-0274-4431-9558-7e4f3bb5982b/local_fa970b76-e666-47d9-af8b-b52f0d727235/outputs"

# Personen-Modul
scp -i ~/.ssh/shiksha_key \
  "$PERS/personen/personen_migration.sql" \
  "$PERS/personen/personen_router.py" \
  "$PERS/personen/personen_ui.html" \
  root@88.99.174.186:/tmp/

# Push-Modul
scp -i ~/.ssh/shiksha_key \
  "$PERS/push/push_migration.sql" \
  "$PERS/push/push_router.py" \
  "$PERS/push/service-worker.js" \
  "$PERS/push/shiksha-push.js" \
  "$PERS/push/push_sender_ui.html" \
  root@88.99.174.186:/tmp/

# Pädagogen-App (mit Bug-Fix)
scp -i ~/.ssh/shiksha_key \
  "$PERS/archive/ui/paedagogen_app.html" \
  root@88.99.174.186:/tmp/
```

---

## 3️⃣ Auf dem Server: alles zusammenfügen

```bash
ssh -i ~/.ssh/shiksha_key root@88.99.174.186 <<'EOF'
set -e

# Migrationen
sudo -u postgres psql shiksha < /tmp/personen_migration.sql
sudo -u postgres psql shiksha < /tmp/push_migration.sql

# Router anhängen
echo "" >> /opt/shiksha/kita_compliance_router.py
echo "# === PERSONEN-ROUTER ===" >> /opt/shiksha/kita_compliance_router.py
cat /tmp/personen_router.py >> /opt/shiksha/kita_compliance_router.py

echo "" >> /opt/shiksha/kita_compliance_router.py
echo "# === PUSH-ROUTER ===" >> /opt/shiksha/kita_compliance_router.py
cat /tmp/push_router.py >> /opt/shiksha/kita_compliance_router.py

# UI-Files
mkdir -p /opt/shiksha/ui/kita
cp /tmp/personen_ui.html        /opt/shiksha/ui/kita/personen.html
cp /tmp/push_sender_ui.html     /opt/shiksha/ui/kita/push.html
cp /tmp/service-worker.js       /opt/shiksha/ui/kita/service-worker.js
cp /tmp/shiksha-push.js         /opt/shiksha/ui/kita/shiksha-push.js

# Pädagogen-App ersetzen
cp /tmp/paedagogen_app.html /opt/shiksha/paedagogen_ui/app.html

# Restart
systemctl restart shiksha
sleep 2

# Smoke-Tests
echo "=== Children-List ==="
curl -s https://shiksha.tun.zone/kita/children | head -c 400
echo
echo "=== Staff-List ==="
curl -s https://shiksha.tun.zone/kita/staff | head -c 400
echo
echo "=== VAPID-Public-Key ==="
curl -s https://shiksha.tun.zone/kita/push/vapid-public-key
echo
EOF
```

---

## 4️⃣ Manuell editieren (nicht automatisierbar)

### a) `EVENT_TYPE_COLORS` und `EVENT_TYPE_LABELS` in `kita_compliance_router.py` ersetzen

Im Calendar-Bereich der Datei (Anfang nach `# === CALENDAR-ROUTER ===`) die beiden Dicts durch die Versionen aus `personen/calendar_types_patch.py` ersetzen — neue Typen `vacation`, `absence`, `course`.

### b) `accounting_router.py`: drei UI-Mounts dazufügen

```python
@router.get("/ui/kita/personen")
async def kita_personen_ui():
    return FileResponse("/opt/shiksha/ui/kita/personen.html")

@router.get("/ui/kita/push")
async def kita_push_ui():
    return FileResponse("/opt/shiksha/ui/kita/push.html")
```

(`service-worker.js` und `shiksha-push.js` werden bereits über die bestehende statische Route serviert.)

---

## 5️⃣ Pädagogen-App / Eltern-App: Push-Subscribe-Button einbauen

**Pädagogen-App** (`/opt/shiksha/paedagogen_ui/app.html`) — am Ende `<head>` ergänzen:

```html
<script src="/accounting/ui/kita/shiksha-push.js"></script>
```

Im Mitteilungs-Tab (oder Header) einen Button hinzufügen:

```html
<button class="btn primary" onclick="enablePush()">🔔 Benachrichtigungen aktivieren</button>
<script>
  ShikshaPush.init({ audience: "paedagogin", personType: "staff", personId: null });
  async function enablePush() {
    try {
      await ShikshaPush.subscribe();
      alert("Benachrichtigungen aktiviert ✓");
    } catch (e) { alert(e.message); }
  }
</script>
```

Service-Worker-Pfad anpassen — die Pädagogen-App registriert aktuell `/accounting/ui/kita/service-worker.js`. Das passt schon.

**Eltern-App** analog: `audience: "eltern", personType: "parent"`, optional `personId` = Kind-ID.

---

## 6️⃣ Erste Schritte

1. Trägerin öffnet `https://shiksha.tun.zone/accounting/ui/kita/personen` → legt Stammdaten an / pflegt Geburtsdaten ein → Geburtstage tauchen automatisch im Kalender auf.
2. Pädagog:in öffnet die App **als PWA** (Home-Screen-Install!) → Mitteilungs-Tab → 🔔 Benachrichtigungen aktivieren.
3. Trägerin öffnet `https://shiksha.tun.zone/accounting/ui/kita/push` → Titel + Text + „Pädagog:innen" → Senden.
4. Push erscheint auf allen abonnierten Geräten.

---

## 7️⃣ iOS-Hinweise (wichtig für Eltern-App)

- iOS 16.4+ vorausgesetzt
- PWA muss **„Zum Home-Bildschirm hinzufügen"** sein — kein Push im normalen Safari-Tab
- Beim ersten Öffnen der installierten App muss der User Notification-Permission geben
- iOS gruppiert Pushes nach `tag` — gleicher Tag = ersetzt vorherige Push der App
- Apple zeigt Pushes nicht zwingend mit Sound/Banner, das hängt von den iOS-Einstellungen des Users ab

---

## 8️⃣ Optional: Auto-Reminders (Cron)

Um bei Events automatisch Erinnerungen zu schicken, später ein Cron-Script schreiben:

```python
# /opt/shiksha/cron_push_reminders.py
# Läuft täglich z.B. 18:00 — schickt Reminder für morgen
# Holt Events von /kita/calendar/events?from_date=morgen&to_date=morgen
# Schickt /kita/push/send mit audience je nach event.target_type
```

Das wäre ein nächster Aufschlag — sag Bescheid wenn Du das willst.
