#!/usr/bin/env bash
# ============================================================
# SHIKSHA · One-Shot-Deploy für kita.shiksha.tun.zone
#
# Ausführen vom Mac, aus dem outputs/-Ordner heraus:
#   cd "/Users/thomasknodler/.../outputs"
#   bash deploy_full.sh
#
# Idempotent — kann beliebig oft laufen.
# ============================================================
set -e

KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "→ Quelle: $LOCAL"
echo "→ Server: $SRV"
echo

# ---------- 1. Files hochladen ----------
echo "[1/3] Upload..."
scp -i "$KEY" \
    "$LOCAL/personen/personen_migration.sql" \
    "$LOCAL/personen/personen_router.py" \
    "$LOCAL/personen/personen_ui.html" \
    "$LOCAL/push/push_migration.sql" \
    "$LOCAL/push/push_router.py" \
    "$LOCAL/push/service-worker.js" \
    "$LOCAL/push/shiksha-push.js" \
    "$LOCAL/push/push_sender_ui.html" \
    "$LOCAL/archive/ui/paedagogen_app.html" \
    "$LOCAL/kalender/calendar_ui.html" \
    "$SRV:/tmp/"

# ---------- 2. Server-Install ----------
echo "[2/3] Server-Install..."
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e

ROUTER=/opt/shiksha/kita_compliance_router.py

# Backup vor jedem Deploy
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

# Migrationen (idempotent, IF NOT EXISTS)
sudo -u postgres psql shiksha < /tmp/personen_migration.sql >/dev/null
sudo -u postgres psql shiksha < /tmp/push_migration.sql >/dev/null
echo "  ✓ Migrationen ok"

# pywebpush
cd /opt/shiksha
source venv/bin/activate 2>/dev/null || true
pip install -q pywebpush 2>/dev/null
echo "  ✓ pywebpush installiert"

# Personen-Router anhängen — nur wenn nicht schon drin
if ! grep -q "PERSONEN-ROUTER" "$ROUTER"; then
  printf "\n\n# === PERSONEN-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/personen_router.py             >> "$ROUTER"
  echo "  ✓ Personen-Router angehängt"
else
  echo "  ↪ Personen-Router war schon drin"
fi

# Push-Router anhängen — nur wenn nicht schon drin
if ! grep -q "PUSH-ROUTER" "$ROUTER"; then
  printf "\n\n# === PUSH-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/push_router.py             >> "$ROUTER"
  echo "  ✓ Push-Router angehängt"
else
  echo "  ↪ Push-Router war schon drin"
fi

# Erweiterte Event-Typen
python3 <<'PYEOF'
import re, pathlib
p = pathlib.Path("/opt/shiksha/kita_compliance_router.py")
src = p.read_text()
new_colors = '''EVENT_TYPE_COLORS = {
    "meeting":         "#a855f7",
    "birthday":        "#ffd93d",
    "closing":         "#a0391f",
    "event":           "#ff8c42",
    "training":        "#00d4d4",
    "celebration":     "#ff4d8d",
    "parent_meeting":  "#6dd47e",
    "vacation":        "#5ec5ff",
    "absence":         "#b8a8c4",
    "course":          "#ffb347",
    "other":           "#9a8e9e",
}'''
new_labels = '''EVENT_TYPE_LABELS = {
    "meeting":         "Meeting",
    "birthday":        "Geburtstag 🎂",
    "closing":         "KITA geschlossen",
    "event":           "Veranstaltung",
    "training":        "Fortbildung",
    "celebration":     "Feier",
    "parent_meeting":  "Elterngespräch",
    "vacation":        "Urlaub",
    "absence":         "Abwesenheit",
    "course":          "Kurs",
    "other":           "Sonstiges",
}'''
src = re.sub(r"EVENT_TYPE_COLORS\s*=\s*\{[^}]*?\}", new_colors, src, count=1, flags=re.DOTALL)
src = re.sub(r"EVENT_TYPE_LABELS\s*=\s*\{[^}]*?\}", new_labels, src, count=1, flags=re.DOTALL)
p.write_text(src)
print("  ✓ Event-Typen aktualisiert")
PYEOF

# UI-Files
mkdir -p /opt/shiksha/ui/kita
cp /tmp/personen_ui.html        /opt/shiksha/ui/kita/personen.html
cp /tmp/push_sender_ui.html     /opt/shiksha/ui/kita/push.html
cp /tmp/calendar_ui.html        /opt/shiksha/ui/kita/calendar.html
cp /tmp/service-worker.js       /opt/shiksha/ui/kita/service-worker.js
cp /tmp/shiksha-push.js         /opt/shiksha/ui/kita/shiksha-push.js
cp /tmp/paedagogen_app.html     /opt/shiksha/paedagogen_ui/app.html
echo "  ✓ UIs platziert"

# Syntax-Check vor Restart
python3 -c "import ast; ast.parse(open('/opt/shiksha/kita_compliance_router.py').read())" \
  && echo "  ✓ Python-Syntax ok" \
  || { echo "  ✗ Python-Syntax kaputt — restore aus Backup:"; ls -1t ${ROUTER}.bak.* | head -3; exit 1; }

# Restart
systemctl restart shiksha
sleep 3
echo "  ✓ Service neu gestartet"

REMOTE

# ---------- 3. Smoke-Tests vom Mac ----------
echo
echo "[3/3] Smoke-Tests..."
echo
echo "→ Event-Types:"
curl -s https://kita.shiksha.tun.zone/kita/calendar/event-types \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('   ', len(d['types']), 'Typen:', [t['key'] for t in d['types']])"

echo
echo "→ Children:"
curl -s -w "    Status: %{http_code}\n" https://kita.shiksha.tun.zone/kita/children -o /dev/null

echo "→ Staff:"
curl -s -w "    Status: %{http_code}\n" https://kita.shiksha.tun.zone/kita/staff -o /dev/null

echo "→ Personen-UI:"
curl -s -w "    Status: %{http_code}\n" https://kita.shiksha.tun.zone/accounting/ui/kita/personen -o /dev/null

echo "→ Pädagogen-App:"
curl -s -w "    Status: %{http_code}\n" https://kita.shiksha.tun.zone/accounting/ui/paedagogen/app -o /dev/null

echo
echo "✓ Deploy fertig."
echo
echo "Bei Status 404 für /accounting/ui/kita/personen oder /push:"
echo "  → Mounts in /opt/shiksha/accounting_router.py noch ergänzen (siehe outputs/personen/DEPLOY.md)"
