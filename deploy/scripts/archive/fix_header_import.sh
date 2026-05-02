#!/usr/bin/env bash
# ============================================================
# SHIKSHA · fix_header_import.sh
# Ergänzt 'Header' in den FastAPI-Imports von kita_compliance_router.py
# (Dashboard-Router nutzt Header für X-User-Id, aber Import fehlte.)
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py

cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"

python3 <<'PYEOF'
import pathlib, re
p = pathlib.Path("/opt/shiksha/kita_compliance_router.py")
src = p.read_text()

if "Header" in re.findall(r"from fastapi import [^\n]+", src)[0] if re.findall(r"from fastapi import [^\n]+", src) else "":
    print("↪ Header ist schon importiert")
else:
    # Existierende "from fastapi import …" Zeile finden und Header dranhängen
    m = re.search(r"^(from fastapi import )([^\n]+)$", src, re.MULTILINE)
    if m:
        existing = m.group(2)
        if "Header" not in existing:
            new_line = m.group(1) + existing.rstrip() + ", Header"
            src = src[:m.start()] + new_line + src[m.end():]
            print("✓ Header zur fastapi-Import-Zeile hinzugefügt")
        else:
            print("↪ Header ist schon dabei")
    else:
        # Falls keine Import-Zeile existiert: am Anfang hinzufügen
        src = "from fastapi import Header\n" + src
        print("✓ Header-Import vorne ergänzt")

p.write_text(src)
PYEOF

# Syntax + Restart
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Syntax kaputt"; exit 1; }
systemctl restart shiksha
sleep 3

if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service immer noch down — Logs:"
  journalctl -u shiksha -n 30 --no-pager
  exit 1
fi
echo "✓ Service läuft"

# Schnelltest
echo
echo "→ Layout-Endpoint:"
curl -s -H "X-User-Id: traegerin" -H "Host: kita.shiksha.tun.zone" \
  http://127.0.0.1:8000/kita/dashboard/layout | head -c 400
echo
REMOTE

echo
echo "→ Externer Test Dashboard-HTML:"
curl -s -o /dev/null -w "  Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/kita/dashboard_traegerin
echo "→ Externer Test Layout-API:"
curl -s -H "X-User-Id: traegerin" \
  https://kita.shiksha.tun.zone/kita/dashboard/layout | head -c 200
echo
