#!/usr/bin/env bash
# ============================================================
# SHIKSHA · shiksha.world Plattform-Site Deploy
# - Migration für shiksha_modules (mit Initial-Daten)
# - world_router an kita_compliance_router.py anhängen
# - platform_meta.html als Template ablegen
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload …"
scp -i "$KEY" \
  "$LOCAL/shiksha_world/world_migration.sql" \
  "$LOCAL/shiksha_world/world_router.py" \
  "$LOCAL/shiksha_world/templates/platform_meta.html" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

# Migration (idempotent)
sudo -u postgres psql shiksha < /tmp/world_migration.sql >/dev/null
echo "  ✓ shiksha_modules + Initial-Daten gepflegt"

# Template-Verzeichnis sicherstellen + platform_meta ablegen
mkdir -p /opt/shiksha/marketing_templates
cp /tmp/platform_meta.html /opt/shiksha/marketing_templates/platform_meta.html
echo "  ✓ Template platziert"

# World-Router idempotent anhängen
if ! grep -q "WORLD-ROUTER" "$ROUTER"; then
  printf "\n\n# === WORLD-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/world_router.py             >> "$ROUTER"
  echo "  ✓ World-Router angehängt"
else
  echo "  ↪ World-Router war schon drin"
fi

# Syntax-Check
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax kaputt"; exit 1; }
echo "  ✓ Python-Syntax ok"

# Restart
systemctl restart shiksha
sleep 3
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down"; journalctl -u shiksha -n 25 --no-pager; exit 1
fi
echo "  ✓ Service läuft"

REMOTE

echo
echo "[3/3] Smoke-Tests"
echo "  Plattform-Site:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/m/shiksha
echo "  Module-API:"
curl -s https://kita.shiksha.tun.zone/kita/api/platform/modules \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    {d[\"count\"]} Module geliefert: {[m[\"slug\"] for m in d[\"modules\"][:3]]} …')"
echo "  Live-Stats:"
curl -s https://kita.shiksha.tun.zone/kita/api/platform/live-stats \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    {d[\"modules_live\"]} Module live, {d[\"kids_present_today\"]} Kinder heute, {d[\"active_organisations\"]} Organisationen')"
echo "  Greeting-API:"
curl -s https://kita.shiksha.tun.zone/kita/api/platform/greeting \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'    \"{d[\"line1\"]} · {d[\"weekday\"]} im {d[\"season_de\"]}\"')"
echo
echo "✓ shiksha.world MVP fertig."
echo
echo "  Aktuelle URL:  https://kita.shiksha.tun.zone/m/shiksha"
echo "  Sobald shiksha.world DNS+Cert hat: Direkt-Mapping auf diese Route."
echo
echo "Tipps:"
echo "  • Im Browser hart neu laden (Cmd+Shift+R) wenn Du noch alte Version siehst."
echo "  • Auf Mobile testen: Module-Showcase wechselt automatisch in horizontalen Scroll."
echo "  • Wenn neue Module gebaut werden, einfach in shiksha_modules INSERT — Site weiß automatisch davon."
