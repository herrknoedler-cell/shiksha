#!/usr/bin/env bash
# ============================================================
# SHIKSHA · mount_fix2.sh — Final-Fix
# - Räumt alte auto-Mount-Blöcke weg
# - Fügt neue Mounts mit FUNCTION-LOCAL FileResponse-Import ein
# - Kopiert neuen Service-Worker auch an /opt/shiksha/kita_ui/
# - Auto-Rollback bei Fehler
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/accounting_router.py

# 1. Backup
NEW_BAK="${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ROUTER" "$NEW_BAK"
echo "✓ Backup → $NEW_BAK"

# 2. Alte (kaputte) Auto-Blöcke entfernen
python3 - <<'PYEOF'
import pathlib, re
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()
# entferne ALLE bisherigen "# === KITA-UI-Mounts (auto*)" Blöcke bis zum nächsten "# ===" oder Dateiende
src = re.sub(
    r"\n# === KITA-UI-Mounts \(auto[^=]*?\) ===.*?(?=\n# ===|\Z)",
    "",
    src, flags=re.DOTALL,
)
src = src.rstrip() + "\n"
p.write_text(src)
print("✓ Alte Auto-Blöcke gepurged")
PYEOF

# 3. Router-Variable detektieren (aus existierender UI-Route)
ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post)\("/ui' "$ROUTER" \
              | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
echo "✓ Router-Variable: @$ROUTER_VAR"

# 4. Neue Mounts — FUNCTION-LOCAL Import (kein Scoping-Problem)
ROUTER_VAR=$ROUTER_VAR python3 - <<'PYEOF'
import os, pathlib
RV = os.environ["ROUTER_VAR"]
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()

def mount(path, file, fn_name, media=None):
    if path in src:
        return None
    mt = f', media_type="{media}"' if media else ""
    return f'''
@{RV}.get("{path}", include_in_schema=False)
async def {fn_name}():
    from fastapi.responses import FileResponse
    return FileResponse("{file}"{mt})
'''

new_blocks = [b for b in [
    mount("/ui/kita/personen",        "/opt/shiksha/ui/kita/personen.html",   "kita_ui_personen"),
    mount("/ui/kita/push",            "/opt/shiksha/ui/kita/push.html",       "kita_ui_push"),
    mount("/ui/kita/calendar",        "/opt/shiksha/ui/kita/calendar.html",   "kita_ui_calendar"),
    mount("/ui/kita/shiksha-push.js", "/opt/shiksha/ui/kita/shiksha-push.js", "kita_ui_shiksha_push_js", "application/javascript"),
] if b]

if new_blocks:
    src = src.rstrip() + "\n\n# === KITA-UI-Mounts (auto v3) ===\n" + "".join(new_blocks) + "\n"
    p.write_text(src)
    print(f"✓ {len(new_blocks)} Mount(s) mit function-local Import")
else:
    print("↪ Alle Mounts schon da")
PYEOF

# 5. Service-Worker auch an alten Pfad kopieren — damit /accounting/ui/kita/service-worker.js
#    den neuen Push-fähigen SW liefert (alte Route an Zeile 1317 zeigt auf /opt/shiksha/kita_ui/).
if [ -d /opt/shiksha/kita_ui ]; then
  cp /opt/shiksha/ui/kita/service-worker.js /opt/shiksha/kita_ui/service-worker.js
  cp /opt/shiksha/ui/kita/shiksha-push.js   /opt/shiksha/kita_ui/shiksha-push.js 2>/dev/null || true
  echo "✓ Service-Worker auch an alten Pfad gespiegelt"
fi

# 6. Syntax-Check & Restart
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax"; cp "$NEW_BAK" "$ROUTER"; exit 1; }
echo "✓ Syntax ok"

systemctl restart shiksha
sleep 3

if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down — Logs:"
  journalctl -u shiksha -n 30 --no-pager | tail -25
  cp "$NEW_BAK" "$ROUTER"
  systemctl restart shiksha
  exit 1
fi
echo "✓ Service läuft"

# 7. Schneller Internal-Test (vom Server gegen sich selbst)
sleep 1
echo
echo "→ Server-interne Smoke-Tests (Host-Header gesetzt):"
for p in personen push calendar shiksha-push.js; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -H "Host: kita.shiksha.tun.zone" "http://127.0.0.1:8000/accounting/ui/kita/$p")
  echo "  /$p: $code"
done
REMOTE

echo
echo "→ Externe Smoke-Tests (vom Mac):"
for p in personen push calendar; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/$p")
  echo "  /$p: $code"
done
echo "  shiksha-push.js: $(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/shiksha-push.js")"
