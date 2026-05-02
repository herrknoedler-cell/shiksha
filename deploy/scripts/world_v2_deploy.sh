#!/usr/bin/env bash
# ============================================================
# SHIKSHA · world v2 Deploy
# - editions + edition_proposals Tabellen
# - 5 Editionen Initial-Daten
# - v2-Router (Editions/Proposals API)
# - platform_meta.html v2 — 20 Sektionen, 3 Mockups, Vorschlag-Form
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload …"
scp -i "$KEY" \
  "$LOCAL/world_v2/world_v2_migration.sql" \
  "$LOCAL/world_v2/world_v2_router.py" \
  "$LOCAL/world_v2/templates/platform_meta.html" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

# Migration
sudo -u postgres psql shiksha < /tmp/world_v2_migration.sql >/dev/null
echo "  ✓ editions + edition_proposals + 6 Initial-Editionen"

# Template ersetzen
cp /tmp/platform_meta.html /opt/shiksha/marketing_templates/platform_meta.html
echo "  ✓ Template v2 platziert"

# Router idempotent anhängen
if ! grep -q "WORLD-V2-ROUTER" "$ROUTER"; then
  printf "\n\n# === WORLD-V2-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/world_v2_router.py             >> "$ROUTER"
  echo "  ✓ World-v2-Router angehängt"
else
  echo "  ↪ World-v2-Router war schon drin"
fi

python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax kaputt"; exit 1; }
echo "  ✓ Python-Syntax ok"

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
echo "  Editionen-API:"
curl -s https://kita.shiksha.tun.zone/kita/api/platform/editions \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'    {d[\"count\"]} Editionen geliefert:')
for e in d['editions']:
    print(f'      {e[\"icon\"]} {e[\"name\"]:12s} · {e[\"status\"]}')
"
echo "  Proposals-API:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/kita/api/platform/proposals
echo
echo "✓ shiksha.world v2 fertig."
echo
echo "  URL: https://kita.shiksha.tun.zone/m/shiksha"
echo "  Im Browser hart neu laden (Cmd+Shift+R) für die neue Version."
