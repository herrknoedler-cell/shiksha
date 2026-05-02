#!/usr/bin/env bash
# ============================================================
# SHIKSHA · Marketing-Site-Generator Phase 1 · Deploy
# - Migration für marketing_sites + marketing_assets + marketing_llm_cache
# - Marketing-Router an kita_compliance_router.py anhängen
# - KITA-Frühlings-Template + Builder-UI + Pool-Importer
# - Mounts in accounting_router.py
# - httpx + jinja2 + anthropic im venv installieren
# - Erste Krummelus-Site automatisch anlegen
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Upload …"
scp -i "$KEY" \
  "$LOCAL/marketing/marketing_migration.sql" \
  "$LOCAL/marketing/marketing_router.py" \
  "$LOCAL/marketing/marketing_builder.html" \
  "$LOCAL/marketing/import_pool.py" \
  "$LOCAL/marketing/templates/kita_spring.html" \
  "$SRV:/tmp/"

echo "[2/3] Server-Install …"
ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
ROUTER=/opt/shiksha/kita_compliance_router.py
ACC=/opt/shiksha/accounting_router.py
cp "$ROUTER" "${ROUTER}.bak.$(date +%Y%m%d-%H%M%S)"
cp "$ACC"    "${ACC}.bak.$(date +%Y%m%d-%H%M%S)"

# Migration
sudo -u postgres psql shiksha < /tmp/marketing_migration.sql >/dev/null
echo "  ✓ Migration ok"

# Python-Deps
cd /opt/shiksha
source venv/bin/activate 2>/dev/null || true
pip install -q jinja2 httpx
echo "  ✓ jinja2 + httpx installiert"

# Templates-Verzeichnis + KITA-Frühling
mkdir -p /opt/shiksha/marketing_templates
cp /tmp/kita_spring.html /opt/shiksha/marketing_templates/kita_spring.html
echo "  ✓ Template platziert"

# Marketing-Assets-Dir + Pool-Subdirs
mkdir -p /opt/shiksha/marketing_assets/pool/kita/spring
mkdir -p /opt/shiksha/marketing_assets/pool/kita/summer
mkdir -p /opt/shiksha/marketing_assets/pool/kita/autumn
mkdir -p /opt/shiksha/marketing_assets/pool/kita/winter
chmod -R 755 /opt/shiksha/marketing_assets
echo "  ✓ Asset-Dirs angelegt"

# Pool-Importer ablegen
cp /tmp/import_pool.py /opt/shiksha/marketing_pool_import.py
chmod +x /opt/shiksha/marketing_pool_import.py
echo "  ✓ Pool-Importer platziert"

# Builder-UI
mkdir -p /opt/shiksha/ui/marketing
cp /tmp/marketing_builder.html /opt/shiksha/ui/marketing/builder.html
echo "  ✓ Builder-UI platziert"

# Marketing-Router idempotent anhängen
if ! grep -q "MARKETING-ROUTER" "$ROUTER"; then
  printf "\n\n# === MARKETING-ROUTER ===\n" >> "$ROUTER"
  cat /tmp/marketing_router.py             >> "$ROUTER"
  echo "  ✓ Marketing-Router angehängt"
else
  echo "  ↪ Marketing-Router war schon drin"
fi

# Mount für Builder-UI in accounting_router.py
ROUTER_VAR=$(grep -oE '^@[a-zA-Z_]+\.(get|post)\("/ui' "$ACC" | head -1 | sed -E 's/^@([a-zA-Z_]+).*/\1/')
ROUTER_VAR=${ROUTER_VAR:-router}
ROUTER_VAR=$ROUTER_VAR python3 - <<'PYEOF'
import os, pathlib
RV = os.environ["ROUTER_VAR"]
p = pathlib.Path("/opt/shiksha/accounting_router.py")
src = p.read_text()
if "/ui/marketing/builder" not in src:
    snippet = f'''
@{RV}.get("/ui/marketing/builder", include_in_schema=False)
async def marketing_builder_ui():
    from fastapi.responses import FileResponse
    return FileResponse("/opt/shiksha/ui/marketing/builder.html")
'''
    src = src.rstrip() + "\n\n# === Marketing-Builder Mount ===\n" + snippet + "\n"
    p.write_text(src)
    print("  ✓ /ui/marketing/builder Mount hinzugefügt")
else:
    print("  ↪ Mount war schon da")
PYEOF

# Syntax-Checks
python3 -c "import ast; ast.parse(open('$ROUTER').read())" || { echo "✗ Compliance-Router Syntax kaputt"; exit 1; }
python3 -c "import ast; ast.parse(open('$ACC').read())"    || { echo "✗ Accounting-Router Syntax kaputt"; exit 1; }
echo "  ✓ Python-Syntax ok"

# ANTHROPIC_API_KEY-Check
if [ -z "$(systemctl show shiksha -p Environment --value | tr ' ' '\n' | grep ANTHROPIC_API_KEY)" ] && \
   ! grep -q "ANTHROPIC_API_KEY" /etc/systemd/system/shiksha.service.d/*.conf 2>/dev/null && \
   ! grep -q "ANTHROPIC_API_KEY" /opt/shiksha/.env 2>/dev/null; then
  echo "  ⚠ ANTHROPIC_API_KEY ist NICHT gesetzt — Inhalt-Generierung wird 503 zurückgeben."
  echo "    Setze ihn in /etc/systemd/system/shiksha.service.d/anthropic.conf:"
  echo "    [Service]"
  echo "    Environment=ANTHROPIC_API_KEY=sk-ant-..."
  echo "    Dann: systemctl daemon-reload && systemctl restart shiksha"
fi

# Restart
systemctl restart shiksha
sleep 3
if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down"; journalctl -u shiksha -n 25 --no-pager; exit 1
fi
echo "  ✓ Service läuft"

# Pool-Importer einmal ausführen (wenn Bilder schon da sind)
DB_URL=$(systemctl show shiksha -p Environment --value | tr ' ' '\n' | grep -E '^DATABASE_URL=' | head -1 | cut -d= -f2-)
if [ -z "$DB_URL" ]; then
  for f in $(systemctl show shiksha -p EnvironmentFiles --value 2>/dev/null | tr ' ' '\n' | sed 's/^-//'); do
    [ -f "$f" ] && url=$(grep -E '^DATABASE_URL=' "$f" 2>/dev/null | head -1 | cut -d= -f2-)
    [ -n "$url" ] && DB_URL="$url" && break
  done
fi
DB_URL=$(echo "$DB_URL" | sed -e 's/^"//' -e 's/"$//')

if [ -n "$DB_URL" ]; then
  DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/marketing_pool_import.py 2>&1 | head -5
fi

# Krummelus-Site automatisch anlegen, falls noch nicht da
sudo -u postgres psql shiksha -c "
  INSERT INTO marketing_sites (slug, edition, business_name, address_line, postal_code, city, country, status)
  VALUES ('krummelus', 'kita', 'KITA Krummelus', 'Achstraße 1', '6850', 'Dornbirn', 'AT', 'draft')
  ON CONFLICT (slug) DO NOTHING;" 2>/dev/null
echo "  ✓ Krummelus-Site initialisiert (falls noch nicht da)"

REMOTE

echo
echo "[3/3] Smoke-Tests"
echo "  Builder-UI:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/accounting/ui/marketing/builder
echo "  Public Marketing-Site:"
curl -s -o /dev/null -w "    Status: %{http_code}\n" \
  https://kita.shiksha.tun.zone/m/krummelus
echo "  Site-API:"
curl -s -H "X-Org-Slug: kita_pilot" \
  https://kita.shiksha.tun.zone/kita/admin/marketing/sites/krummelus | head -c 300
echo
echo
echo "✓ Marketing-Phase-1 fertig."
echo "  Builder:           https://kita.shiksha.tun.zone/accounting/ui/marketing/builder?site=krummelus"
echo "  Krummelus-Site:    https://kita.shiksha.tun.zone/m/krummelus"
echo
echo "Noch zu tun (manuell):"
echo "  1. ANTHROPIC_API_KEY in systemd-Drop-in setzen (siehe oben)"
echo "  2. 30 Firefly-Bilder generieren (Prompts in marketing/firefly_prompts.md)"
echo "  3. Bilder hochladen: scp pool-bilder-*.jpg root@88.99.174.186:/opt/shiksha/marketing_assets/pool/kita/spring/"
echo "  4. /opt/shiksha/venv/bin/python /opt/shiksha/marketing_pool_import.py"
echo "  5. Im Builder klicken: 'Inhalte vorschlagen lassen' — Claude füllt alles"
