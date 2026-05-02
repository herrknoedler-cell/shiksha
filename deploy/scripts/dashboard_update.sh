#!/usr/bin/env bash
# ============================================================
# SHIKSHA · Dashboard Update — UI-Verfeinerungen
# - shiksha-cards.css/js + dashboard_traegerin.html austauschen
# - Default-Layout im Router updaten (Action-Round 1×2 → 2×2)
# - Bestehende Layouts in DB: Action-Round-Cards von 1×2 auf 2×2 hieven
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload UI-Files + Router …"
scp -i "$KEY" \
  "$LOCAL/dashboard/shiksha-cards.css" \
  "$LOCAL/dashboard/shiksha-cards.js" \
  "$LOCAL/dashboard/dashboard_traegerin.html" \
  "$LOCAL/dashboard/dashboard_router.py" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py

cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

# UI-Files austauschen
cp /tmp/shiksha-cards.css        /opt/shiksha/ui/kita/shiksha-cards.css
cp /tmp/shiksha-cards.js         /opt/shiksha/ui/kita/shiksha-cards.js
cp /tmp/dashboard_traegerin.html /opt/shiksha/ui/kita/dashboard_traegerin.html
echo "  ✓ UI-Files ersetzt"

# Default-Layout im Router updaten:
# Wir suchen den Block "_DEFAULT_TRAEGERIN_LAYOUT = [" ... "]" und ersetzen
python3 - <<'PYEOF'
import re, pathlib
p = pathlib.Path("/opt/shiksha/kita_compliance_router.py")
src = p.read_text()
new_block = open("/tmp/dashboard_router.py").read()
# Aus dem neuen Router den Block extrahieren
m = re.search(r"_DEFAULT_TRAEGERIN_LAYOUT\s*=\s*\[.*?\n\]\s*\n", new_block, re.DOTALL)
if not m:
    print("⚠ Konnte neuen Default-Block nicht extrahieren")
else:
    new_layout_str = m.group(0)
    # Im laufenden Router den alten ersetzen
    src_new = re.sub(r"_DEFAULT_TRAEGERIN_LAYOUT\s*=\s*\[.*?\n\]\s*\n",
                     new_layout_str, src, count=1, flags=re.DOTALL)
    if src_new != src:
        p.write_text(src_new)
        print("  ✓ Default-Layout im Router aktualisiert")
    else:
        print("  ↪ Default-Layout war schon aktuell oder Pattern nicht gefunden")
PYEOF

# Bestehende User-Layouts in DB: Action-Round Cards w=1 → w=2
sudo -u postgres psql shiksha <<'SQL'
UPDATE dashboard_layouts
SET layout = (
  SELECT jsonb_agg(
    CASE
      WHEN c->>'type' = 'action-round'
        THEN jsonb_set(jsonb_set(c, '{w}', '2'::jsonb), '{h}', '2'::jsonb)
      ELSE c
    END
  )
  FROM jsonb_array_elements(layout) AS c
)
WHERE EXISTS (
  SELECT 1 FROM jsonb_array_elements(layout) AS c
  WHERE c->>'type' = 'action-round' AND (c->>'w')::int < 2
);
SQL
echo "  ✓ Bestehende Layouts: Action-Round Cards auf 2×2 gehoben"

# Syntax-Check + Restart
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax kaputt"; exit 1; }
systemctl restart shiksha
sleep 3

if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down — Logs:"; journalctl -u shiksha -n 20 --no-pager; exit 1
fi
echo "  ✓ Service läuft"
REMOTE

echo
echo "[3/3] Smoke-Tests"
echo "  Dashboard-HTML:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin
echo "  Layout-API:"
curl -s -H "X-User-Id: traegerin" \
  https://kita.shiksha.tun.zone/kita/dashboard/layout | head -c 300
echo
echo "✓ Update fertig — im Browser Tab neu laden!"
