#!/usr/bin/env bash
# ============================================================
# SHIKSHA · Trägerin-Dashboard Deploy
# - Migration
# - Router an kita_compliance_router.py anhängen (idempotent)
# - shiksha-cards.css/js + dashboard_traegerin.html platzieren
# - Mount in accounting_router.py
# - Restart + Smoke-Tests
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload …"
scp -i "$KEY" \
  "$LOCAL/dashboard/dashboard_migration.sql" \
  "$LOCAL/dashboard/dashboard_router.py" \
  "$LOCAL/dashboard/shiksha-cards.css" \
  "$LOCAL/dashboard/shiksha-cards.js" \
  "$LOCAL/dashboard/dashboard_traegerin.html" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e

ROUTER=/opt/shiksha/kita_compliance_router.py
ACC=/opt/shiksha/accounting_router.py

# Backups
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ACC"    "${ACC}.bak.$(date +%Y%m%d-%H%M%S)"

# Migration
sudo -u postgres psql shiksha < /tmp/dashboard_migration.sql >/dev/null
echo "  ✓ Migration ok"

# Router idempotent anhängen
if ! grep -q "DASHBOARD-ROUTER" "$ROUTER"; then
  printf "\n\n# === DASHBOARD-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/dashboard_router.py             >> "$ROUTER"
  echo "  ✓ Dashboard-Router angehängt"
else
  echo "  ↪ Dashboard-Router war schon drin"
fi

# UI-Files
mkdir -p /opt/shiksha/ui/kita
cp /tmp/shiksha-cards.css           /opt/shiksha/ui/kita/shiksha-cards.css
cp /tmp/shiksha-cards.js            /opt/shiksha/ui/kita/shiksha-cards.js
cp /tmp/dashboard_traegerin.html    /opt/shiksha/ui/kita/dashboard_traegerin.html
echo "  ✓ Card-Library und Dashboard-HTML platziert"

# Router-Variable in accounting_router.py detektieren
ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post)\("/ui' "$ACC" | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
ROUTER_VAR=${ROUTER_VAR:-router}

# Mounts in accounting_router.py (idempotent, function-local FileResponse)
ROUTER_VAR=$ROUTER_VAR python3 - <<'PYEOF'
import os, pathlib
RV = os.environ["ROUTER_VAR"]
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()

def mount(path, file, fn, mt=None):
    if path in src:
        return None
    media = f', media_type="{mt}"' if mt else ""
    return f'''
@{RV}.get("{path}", include_in_schema=False)
async def {fn}():
    from fastapi.responses import FileResponse
    return FileResponse("{file}"{media})
'''

new = [b for b in [
    mount("/ui/kita/dashboard_traegerin", "/opt/shiksha/ui/kita/dashboard_traegerin.html", "kita_ui_dashboard_traegerin"),
    mount("/ui/kita/shiksha-cards.css",   "/opt/shiksha/ui/kita/shiksha-cards.css",        "kita_ui_cards_css", "text/css"),
    mount("/ui/kita/shiksha-cards.js",    "/opt/shiksha/ui/kita/shiksha-cards.js",         "kita_ui_cards_js",  "application/javascript"),
] if b]

if new:
    src = src.rstrip() + "\n\n# === Trägerin-Dashboard Mounts ===\n" + "".join(new) + "\n"
    p.write_text(src)
    print(f"  ✓ {len(new)} Dashboard-Mount(s) hinzugefügt")
else:
    print("  ↪ Mounts schon vorhanden")
PYEOF

# Syntax-Check + Restart
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Router-Syntax kaputt"; exit 1; }
python3 -c "import ast; ast.parse(open('$ACC').read())"    || { echo "✗ Accounting-Router-Syntax kaputt"; exit 1; }
systemctl restart shiksha
sleep 3

if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down"; journalctl -u shiksha -n 25 --no-pager; exit 1
fi
echo "  ✓ Service läuft"
REMOTE

echo
echo "[3/3] Smoke-Tests:"
echo "  Dashboard-HTML:"
curl -s -o /dev/null -w "    /accounting/ui/kita/dashboard_traegerin: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin
echo "  Card-CSS:"
curl -s -o /dev/null -w "    /accounting/ui/kita/shiksha-cards.css: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/shiksha-cards.css
echo "  Card-JS:"
curl -s -o /dev/null -w "    /accounting/ui/kita/shiksha-cards.js: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/shiksha-cards.js
echo "  Layout-Endpoint:"
curl -s -o /dev/null -w "    /kita/dashboard/layout: %{http_code}\n" \
  -H "X-User-Id: traegerin" \
  https://kita.shiksha.tun.zone/kita/dashboard/layout
echo "  Anwesenheits-Card-Daten:"
curl -s https://kita.shiksha.tun.zone/kita/dashboard/card/anwesenheit-summary | head -c 200
echo
echo
echo "✓ Deploy fertig — Dashboard erreichbar unter:"
echo "  https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin"
