#!/usr/bin/env bash
# ============================================================
# SHIKSHA · fix_url_rewrite.sh
# Fügt nginx /m/ → /kita/m/ Rewrite hinzu.
# Sodass /m/shiksha und /m/krummelus extern erreichbar sind.
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

# Lokales Helper-Script schreiben (vermeidet Quoting-Hölle)
cat > /tmp/_nginx_patcher.py <<'PYEOF'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
src = p.read_text()
new_block = """
    location /m/ {
        rewrite ^/m/(.*)$ /kita/m/$1 break;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Org-Slug "kita_pilot";
        proxy_read_timeout 90;
    }

    location / {"""
# Find the existing 'location / {' line — match flexibly with any whitespace
import re
pattern = re.compile(r'\n[ \t]*location[ \t]+/[ \t]*\{')
match = pattern.search(src)
if not match:
    print("ERROR: Pattern 'location / {' nicht gefunden")
    sys.exit(1)
new_src = src[:match.start()] + new_block + src[match.end():]
p.write_text(new_src)
print(f"OK: location /m/ Block eingefügt in {p}")
PYEOF

scp -i "$KEY" /tmp/_nginx_patcher.py "$SRV:/tmp/" >/dev/null

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e

# 1. Internal-Check ob /kita/m/* tatsächlich funktioniert
echo "→ Internal-Check (sollte 200 sein):"
echo "  /kita/m/shiksha    → $(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/kita/m/shiksha)"
echo "  /kita/m/krummelus  → $(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/kita/m/krummelus)"

# 2. Den richtigen nginx-config-File finden (kita.shiksha.tun.zone)
NGINX_FILE=""
for f in /etc/nginx/sites-enabled/*; do
    [ -f "$f" ] || continue
    if grep -q "server_name.*kita.shiksha" "$f" 2>/dev/null; then
        if [ -L "$f" ]; then
            NGINX_FILE=$(readlink -f "$f")
        else
            NGINX_FILE="$f"
        fi
        break
    fi
done

if [ -z "$NGINX_FILE" ]; then
    echo "✗ Kein nginx-Block für kita.shiksha gefunden"
    echo "  Vorhandene sites-enabled:"
    ls -la /etc/nginx/sites-enabled/
    exit 1
fi
echo "→ nginx-File: $NGINX_FILE"

# 3. Patch oder schon drin?
if grep -q "location /m/" "$NGINX_FILE"; then
    echo "↪ /m/ war schon konfiguriert — kein Patch nötig"
else
    cp "$NGINX_FILE" "${NGINX_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
    python3 /tmp/_nginx_patcher.py "$NGINX_FILE"
fi

# 4. Test + Reload
nginx -t && systemctl reload nginx
echo "✓ nginx neu geladen"
REMOTE

echo
echo "→ Externer Smoke-Test:"
for url in m/shiksha m/krummelus; do
    code=$(curl -s -o /dev/null -w "%{http_code}" "https://kita.shiksha.tun.zone/$url")
    icon="✓"
    [ "$code" != "200" ] && icon="✗"
    echo "  $icon  https://kita.shiksha.tun.zone/$url → $code"
done

echo
echo "✓ URL-Rewrite fertig."
echo
echo "Browser: hart neu laden (Cmd+Shift+R)"
echo "  Plattform-Site:    https://kita.shiksha.tun.zone/m/shiksha"
echo "  Krummelus-Marketing: https://kita.shiksha.tun.zone/m/krummelus"
