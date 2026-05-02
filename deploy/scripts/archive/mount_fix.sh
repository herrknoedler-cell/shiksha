#!/usr/bin/env bash
# ============================================================
# SHIKSHA · mount_fix.sh — selbst-heilendes Recovery
#
#   bash mount_fix.sh
#
# 1. Restored das letzte Backup von accounting_router.py
# 2. Detektiert die Router-Variable (@router / @app / @kita_router …)
# 3. Patched die Mounts mit der richtigen Variable
# 4. Rollback wenn der Service nicht hochkommt
# ============================================================
set -e

KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/accounting_router.py

# ---------- 1. Letztes Backup zurückrollen ----------
LATEST_BAK=$(ls -1t ${ROUTER}.bak.* 2>/dev/null | head -1 || true)
if [ -z "$LATEST_BAK" ]; then
  echo "⚠ Kein Backup gefunden — abbrechen."; exit 1
fi
cp "$LATEST_BAK" "$ROUTER"
echo "✓ Restored from $(basename "$LATEST_BAK")"

systemctl restart shiksha
sleep 3
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service kommt selbst nach Restore nicht hoch — Logs:"
  journalctl -u shiksha -n 30 --no-pager
  exit 1
fi
echo "✓ Service ist nach Restore wieder oben"

# ---------- 2. Router-Variable detektieren ----------
echo
echo "→ Detektiere Router-Variable aus existierenden Routen ..."
# Suche nach @<name>.get("/ui/...") — das nehmen wir als gesetzt vorhanden an
ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post)\("/ui' "$ROUTER" \
              | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
if [ -z "$ROUTER_VAR" ]; then
  # Fallback: irgendeine Route
  ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post|put|delete)\(' "$ROUTER" \
                | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
fi
if [ -z "$ROUTER_VAR" ]; then
  echo "✗ Konnte keine Router-Variable finden!"; exit 1
fi
echo "✓ Verwende @$ROUTER_VAR"

# ---------- 3. Smart-Patch ----------
NEW_BAK="${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ROUTER" "$NEW_BAK"

ROUTER_VAR=$ROUTER_VAR python3 - <<'PYEOF'
import os, pathlib, re
RV = os.environ["ROUTER_VAR"]
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()

# FileResponse-Import sicherstellen
if "FileResponse" not in src:
    src = re.sub(r"(from fastapi\b[^\n]*\n)",
                 r"\1from fastapi.responses import FileResponse\n",
                 src, count=1)

mounts = []
def add(path, file, mt=None):
    if path not in src:
        media = f', media_type="{mt}"' if mt else ""
        fn = f"_kita_ui_{path.replace('/','_').replace('-','_').replace('.','_').strip('_')}"
        mounts.append(f'''
@{RV}.get("{path}")
async def {fn}():
    return FileResponse("{file}"{media})
''')

add("/ui/kita/personen",          "/opt/shiksha/ui/kita/personen.html")
add("/ui/kita/push",              "/opt/shiksha/ui/kita/push.html")
add("/ui/kita/calendar",          "/opt/shiksha/ui/kita/calendar.html")
add("/ui/kita/shiksha-push.js",   "/opt/shiksha/ui/kita/shiksha-push.js",   "application/javascript")
add("/ui/kita/service-worker.js", "/opt/shiksha/ui/kita/service-worker.js", "application/javascript")

if mounts:
    src = src.rstrip() + "\n\n# === KITA-UI-Mounts (auto v2) ===\n" + "".join(mounts) + "\n"
    p.write_text(src)
    print(f"✓ {len(mounts)} Mount(s) hinzugefügt mit @{RV}")
else:
    print("↪ Keine neuen Mounts nötig — alle bereits vorhanden")
PYEOF

# Syntax-Check
if ! python3 -c "import ast; ast.parse(open('$ROUTER').read())"; then
  echo "✗ Syntax kaputt — rollback"
  cp "$NEW_BAK" "$ROUTER"
  exit 1
fi

systemctl restart shiksha
sleep 3

# ---------- 4. Auto-Rollback wenn Service kaputt ----------
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service nach Patch unten — Logs:"
  journalctl -u shiksha -n 25 --no-pager
  echo
  echo "→ Auto-Rollback ..."
  cp "$NEW_BAK" "$ROUTER"
  systemctl restart shiksha
  sleep 3
  echo "Service nach Rollback: $(systemctl is-active shiksha)"
  exit 1
fi
echo "✓ Service läuft nach Patch"
REMOTE

# ---------- Smoke-Tests ----------
echo
echo "→ Smoke-Tests:"
for path in personen push calendar; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/$path")
  echo "  /$path: $code"
done
echo "  shiksha-push.js: $(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/shiksha-push.js")"
echo "  service-worker.js: $(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/service-worker.js")"
