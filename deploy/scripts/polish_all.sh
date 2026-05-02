#!/usr/bin/env bash
# ============================================================
# SHIKSHA · polish_all.sh
# Schließt alle offenen Stränge vor der Repo-Migration:
# 1. shiksha_modules Tabelle + Initial-Daten (14 Module)
# 2. world_router.py mit /m/shiksha-Endpoint
# 3. Knowledge-Bites korrigierte JSON
# 4. Insights-Cron einmal manuell triggern
# 5. Pool-Importer (falls Firefly-Bilder schon da)
# 6. Smoke-Tests aller URLs
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "═══════════════════════════════════════════════════════"
echo "  SHIKSHA · Final Polish vor der Repo-Migration"
echo "═══════════════════════════════════════════════════════"
echo

# Lokale JSON Validierung (knowledge_bites)
echo "[Pre-Check] Knowledge-Bites lokal validieren …"
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('$LOCAL/greeting/knowledge_bites.json').read_text())
print(f'  ✓ {len(data)} Bites lokal gültig')
" || { echo "✗ JSON kaputt — Abbruch"; exit 1; }

# Upload aller offenen Files
echo
echo "[1/4] Upload …"
scp -i "$KEY" \
  "$LOCAL/shiksha_world/world_migration.sql" \
  "$LOCAL/shiksha_world/world_router.py" \
  "$LOCAL/greeting/knowledge_bites.json" \
  "$SRV:/tmp/" >/dev/null
echo "  ✓ 3 Files hochgeladen"

# Server-seitige Reparatur
echo
echo "[2/4] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

# 2a. shiksha_modules Migration + Initial-Daten
sudo -u postgres psql shiksha < /tmp/world_migration.sql >/dev/null
echo "  ✓ shiksha_modules + 14 Module Initial-Daten"

# 2b. world_router.py idempotent anhängen (für /m/shiksha + Module/Stats/Greeting)
if ! grep -q "WORLD-ROUTER" "$ROUTER"; then
  printf "\n\n# === WORLD-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/world_router.py             >> "$ROUTER"
  echo "  ✓ World-Router angehängt (/m/shiksha + APIs)"
else
  echo "  ↪ World-Router war schon drin"
fi

# 2c. Knowledge-Bites korrigierte JSON
cp /tmp/knowledge_bites.json /opt/shiksha/data/knowledge_bites.json
chmod 644 /opt/shiksha/data/knowledge_bites.json
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('/opt/shiksha/data/knowledge_bites.json').read_text())
print(f'  ✓ Server liest {len(data)} Bites')
"

# Syntax-Check + Restart
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax kaputt"; exit 1; }
echo "  ✓ Python-Syntax ok"

systemctl restart shiksha
sleep 3
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down"; journalctl -u shiksha -n 25 --no-pager; exit 1
fi
echo "  ✓ Service läuft"

# 2d. DATABASE_URL holen + Insights-Cron + Pool-Importer
DB_URL=$(systemctl show shiksha -p Environment --value 2>/dev/null \
         | tr ' ' '\n' | grep -E '^DATABASE_URL=' | head -1 | cut -d= -f2-)
if [ -z "$DB_URL" ]; then
  for f in $(systemctl show shiksha -p EnvironmentFiles --value 2>/dev/null | tr ' ' '\n' | sed 's/^-//'); do
    [ -f "$f" ] && url=$(grep -E '^DATABASE_URL=' "$f" 2>/dev/null | head -1 | cut -d= -f2-)
    [ -n "$url" ] && DB_URL="$url" && break
  done
fi
DB_URL=$(echo "$DB_URL" | sed -e 's/^"//' -e 's/"$//')

if [ -n "$DB_URL" ]; then
  echo
  echo "  → Insights-Cron …"
  DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py 2>&1 | tail -10
  echo
  echo "  → Pool-Importer (falls Bilder da) …"
  DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/marketing_pool_import.py 2>&1 | tail -3 || true
fi
REMOTE

# Smoke-Tests von extern
echo
echo "[3/4] Externe Smoke-Tests …"
echo
echo "  KITA-Pilot Module:"
for url in dashboard_traegerin paedagogen/app eltern/app kita/personen kita/calendar kita/push; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/$url")
  echo "    /accounting/ui/$url → $code"
done
echo
echo "  shiksha.world Plattform:"
for url in m/shiksha m/krummelus; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/$url")
  echo "    /$url → $code"
done
echo
echo "  Plattform-APIs:"
for path in editions modules live-stats greeting proposals; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/kita/api/platform/$path")
  echo "    /api/platform/$path → $code"
done
echo
echo "  Greeting-Endpoint (mit Wissens-Snippet?):"
curl -s -H "X-User-Id: heidi" \
  "https://kita.shiksha.tun.zone/kita/dashboard/card/greeting?role=traegerin&user=Heidi" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
k = d.get('knowledge')
print('    greeting :', d.get('greeting'))
print('    knowledge:', k.get('title') if k else 'NULL ✗')
i = d.get('insight')
print('    insight  :', i.get('title') if i else '—')
"

echo
echo "[4/4] Status-Bilanz"
echo "  ▸ shiksha.world v2 Plattform-Site:  https://kita.shiksha.tun.zone/m/shiksha"
echo "  ▸ Krummelus Marketing (Pilot):       https://kita.shiksha.tun.zone/m/krummelus"
echo "  ▸ Trägerin-Dashboard:                https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin"
echo "  ▸ Marketing-Builder:                  https://kita.shiksha.tun.zone/accounting/ui/marketing/builder?site=krummelus"
echo
echo "✓ Polish abgeschlossen."
echo
echo "Falls Plattform-Site /m/shiksha noch 404 zeigt: Browser hart neu laden (Cmd+Shift+R)"
echo "Falls Greeting noch knowledge=NULL zeigt: 1 Min warten + neu laden"
