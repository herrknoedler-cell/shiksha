#!/usr/bin/env bash
# ============================================================
# SHIKSHA · Greeting & Insights Deploy
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload …"
scp -i "$KEY" \
  "$LOCAL/greeting/greeting_migration.sql" \
  "$LOCAL/greeting/greeting_router.py" \
  "$LOCAL/greeting/knowledge_bites.json" \
  "$LOCAL/greeting/shiksha_insights_cron.py" \
  "$LOCAL/greeting/weekly_theme_ui.html" \
  "$LOCAL/dashboard/shiksha-cards.css" \
  "$LOCAL/dashboard/shiksha-cards.js" \
  "$LOCAL/dashboard/dashboard_router.py" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py
ACC=/opt/shiksha/accounting_router.py
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ACC"    "${ACC}.bak.$(date +%Y%m%d-%H%M%S)"

# Migration
sudo -u postgres psql shiksha < /tmp/greeting_migration.sql >/dev/null
echo "  ✓ Migration ok"

# Knowledge-Bites in /opt/shiksha/data/
mkdir -p /opt/shiksha/data
cp /tmp/knowledge_bites.json /opt/shiksha/data/knowledge_bites.json
echo "  ✓ Knowledge-Bites platziert"

# Cron-Script + Cron-Job
cp /tmp/shiksha_insights_cron.py /opt/shiksha/shiksha_insights_cron.py
chmod +x /opt/shiksha/shiksha_insights_cron.py
cat > /etc/cron.d/shiksha-insights <<'CRON'
# SHIKSHA · Tägliche Insights-Generierung
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 3 * * * root /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py >> /var/log/shiksha-insights.log 2>&1
CRON
echo "  ✓ Cron-Job installiert"

# Greeting-Router idempotent anhängen
if ! grep -q "GREETING-ROUTER" "$ROUTER"; then
  printf "\n\n# === GREETING-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/greeting_router.py             >> "$ROUTER"
  echo "  ✓ Greeting-Router angehängt"
else
  echo "  ↪ Greeting-Router war schon drin"
fi

# Dashboard-Router updaten (Default-Layouts mit greeting-Card)
python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("/opt/shiksha/kita_compliance_router.py")
src = p.read_text()
new_src = open("/tmp/dashboard_router.py").read()
for var in ("_DEFAULT_TRAEGERIN_LAYOUT", "_DEFAULT_PAEDAGOGIN_LAYOUT"):
    m = re.search(rf"{var}\s*=\s*\[.*?\n\]\s*\n", new_src, re.DOTALL)
    if m:
        new_block = m.group(0)
        src_after = re.sub(rf"{var}\s*=\s*\[.*?\n\]\s*\n", new_block, src, count=1, flags=re.DOTALL)
        if src_after != src:
            src = src_after
            print(f"  ✓ {var} aktualisiert")
p.write_text(src)
PYEOF

# UI-Files austauschen
cp /tmp/shiksha-cards.css       /opt/shiksha/ui/kita/shiksha-cards.css
cp /tmp/shiksha-cards.js        /opt/shiksha/ui/kita/shiksha-cards.js
cp /tmp/weekly_theme_ui.html    /opt/shiksha/ui/kita/weekly_theme.html
echo "  ✓ UI-Files ersetzt"

# Mount für Wochen-Motto-Editor in accounting_router.py
ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post)\("/ui' "$ACC" | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
ROUTER_VAR=${ROUTER_VAR:-router}
ROUTER_VAR=$ROUTER_VAR python3 - <<'PYEOF'
import os, pathlib
RV = os.environ["ROUTER_VAR"]
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()
if "/ui/kita/weekly-theme" not in src:
    snippet = f'''
@{RV}.get("/ui/kita/weekly-theme", include_in_schema=False)
async def kita_weekly_theme_ui():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/kita/weekly_theme.html")
'''
    src = src.rstrip() + "\n\n# === Wochen-Motto-Editor ===\n" + snippet + "\n"
    p.write_text(src)
    print("  ✓ /ui/kita/weekly-theme Mount hinzugefügt")
else:
    print("  ↪ Mount war schon da")
PYEOF

# Syntax-Checks
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Compliance-Router Syntax kaputt"; exit 1; }
python3 -c "import ast; ast.parse(open('$ACC').read())"    || { echo "✗ Accounting-Router Syntax kaputt"; exit 1; }
echo "  ✓ Python-Syntax ok"

# Restart
systemctl restart shiksha
sleep 3
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down"; journalctl -u shiksha -n 25 --no-pager; exit 1
fi
echo "  ✓ Service läuft"

# Erste Insights-Runde direkt ausführen, damit was zu sehen ist
echo "  Erstgeneration der Insights …"
/opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py 2>&1 | tail -10

REMOTE

echo
echo "[3/3] Smoke-Tests"
echo "  Greeting-Endpoint:"
curl -s -H "X-User-Id: heidi" \
  "https://kita.shiksha.tun.zone/kita/dashboard/card/greeting?role=traegerin&user=Heidi" \
  | head -c 600
echo
echo
echo "  Wochen-Theme-UI:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/weekly-theme
echo
echo "✓ Greeting-Modul fertig."
echo "  Dashboard:    https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin"
echo "  Wochen-Fokus: https://kita.shiksha.tun.zone/accounting/ui/kita/weekly-theme"
