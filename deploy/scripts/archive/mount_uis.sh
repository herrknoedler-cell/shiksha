#!/usr/bin/env bash
# ============================================================
# SHIKSHA · UI-Mounts in accounting_router.py ergänzen
# Idempotent — fügt nur fehlende Mounts hinzu.
#
#   bash mount_uis.sh
# ============================================================
set -e

KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

echo "→ Patche accounting_router.py auf $SRV ..."

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/accounting_router.py

# Backup
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

python3 <<'PYEOF'
import pathlib, re
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()

# Stelle sicher, dass FileResponse importiert ist
if "FileResponse" not in src:
    print("  ⚠ FileResponse nicht importiert — füge Import hinzu")
    # Nach dem ersten "from fastapi" einen neuen Import einfügen
    src = re.sub(
        r"(from fastapi[^\n]*\n)",
        r"\1from fastapi.responses import FileResponse\n",
        src, count=1,
    )

# Mount-Snippets — nur wenn noch nicht da
to_add = []

if "/ui/kita/personen" not in src:
    to_add.append('''
@router.get("/ui/kita/personen")
async def kita_personen_ui():
    return FileResponse("/opt/shiksha/ui/kita/personen.html")
''')

if "/ui/kita/push" not in src:
    to_add.append('''
@router.get("/ui/kita/push")
async def kita_push_ui():
    return FileResponse("/opt/shiksha/ui/kita/push.html")
''')

if "/ui/kita/calendar" not in src:
    to_add.append('''
@router.get("/ui/kita/calendar")
async def kita_calendar_ui():
    return FileResponse("/opt/shiksha/ui/kita/calendar.html")
''')

# Auch shiksha-push.js + service-worker.js als statisches File ausliefern
if "/ui/kita/shiksha-push.js" not in src and "/ui/kita/service-worker.js" not in src:
    to_add.append('''
@router.get("/ui/kita/shiksha-push.js")
async def kita_push_helper_js():
    return FileResponse("/opt/shiksha/ui/kita/shiksha-push.js", media_type="application/javascript")

@router.get("/ui/kita/service-worker.js")
async def kita_sw():
    return FileResponse("/opt/shiksha/ui/kita/service-worker.js", media_type="application/javascript")
''')

if to_add:
    src = src.rstrip() + "\n\n# === KITA-UI-Mounts (auto) ===\n" + "".join(to_add) + "\n"
    p.write_text(src)
    print(f"  ✓ {len(to_add)} Mount-Block(s) hinzugefügt")
else:
    print("  ↪ Alle Mounts waren bereits drin")
PYEOF

# Syntax check
python3 -c "import ast; ast.parse(open('$ROUTER').read())" \
  && echo "  ✓ Python-Syntax ok" \
  || { echo "  ✗ Syntax kaputt — restore:"; ls -1t ${ROUTER}.bak.* | head -3; exit 1; }

systemctl restart shiksha
sleep 3
echo "  ✓ Service neu gestartet"
REMOTE

echo
echo "[Smoke-Test]"
for path in personen push calendar; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/accounting/ui/kita/$path")
  echo "  /$path: $code"
done

echo
echo "✓ Mounts fertig."
