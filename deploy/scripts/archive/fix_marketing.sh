#!/usr/bin/env bash
# ============================================================
# SHIKSHA · fix_marketing.sh
# 1. Korrigierte knowledge_bites.json hochladen + lokal validieren
# 2. Pool-Importer mit DB-URL aus systemd ausführen
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

echo "→ Lokale JSON validieren …"
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('$LOCAL/greeting/knowledge_bites.json').read_text())
print(f'  ✓ {len(data)} Bites lokal gültig')
" || { echo "✗ JSON immer noch kaputt — Abbruch"; exit 1; }

echo
echo "→ Upload + Server-Test"
scp -i "$KEY" "$LOCAL/greeting/knowledge_bites.json" "$SRV:/tmp/" >/dev/null

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e

# Knowledge-Bites austauschen + read-test
cp /tmp/knowledge_bites.json /opt/shiksha/data/knowledge_bites.json
chmod 644 /opt/shiksha/data/knowledge_bites.json
python3 -c "
import json, pathlib
print(f'  ✓ Server liest {len(json.loads(pathlib.Path(\"/opt/shiksha/data/knowledge_bites.json\").read_text()))} Bites')
"

# DATABASE_URL aus systemd holen
DB_URL=$(systemctl show shiksha -p Environment --value 2>/dev/null \
         | tr ' ' '\n' | grep -E '^DATABASE_URL=' | head -1 | cut -d= -f2-)
if [ -z "$DB_URL" ]; then
  for f in $(systemctl show shiksha -p EnvironmentFiles --value 2>/dev/null | tr ' ' '\n' | sed 's/^-//'); do
    [ -f "$f" ] && url=$(grep -E '^DATABASE_URL=' "$f" 2>/dev/null | head -1 | cut -d= -f2-)
    [ -n "$url" ] && DB_URL="$url" && break
  done
fi
DB_URL=$(echo "$DB_URL" | sed -e 's/^"//' -e 's/"$//')
[ -z "$DB_URL" ] && { echo "✗ DATABASE_URL nicht gefunden"; exit 1; }

# Pool-Importer
echo
echo "→ Pool-Importer ausführen …"
DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/marketing_pool_import.py

# Insights-Cron auch nochmal — die Knowledge waren ja vorher kaputt
echo
echo "→ Greeting-Endpoint Test:"
DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py 2>&1 | tail -10

REMOTE

echo
echo "→ Greeting-API extern testen:"
curl -s -H "X-User-Id: heidi" \
  "https://kita.shiksha.tun.zone/kita/dashboard/card/greeting?role=traegerin&user=Heidi" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
k = d.get('knowledge')
print('  greeting :', d.get('greeting'))
print('  knowledge:', (k.get('title') + ' — ' + k.get('body','')[:65] + '…') if k else 'NULL ✗')
i = d.get('insight')
print('  insight  :', i.get('title') if i else '—')
"

echo
echo "✓ Marketing-Fixes fertig."
echo
echo "Damit /m/krummelus angezeigt wird, fehlt jetzt nur noch:"
echo "  1. ANTHROPIC_API_KEY in /etc/systemd/system/shiksha.service.d/anthropic.conf"
echo "  2. systemctl daemon-reload && systemctl restart shiksha"
echo "  3. Im Builder klicken: '✨ Inhalte vorschlagen lassen'"
echo "  4. Danach 'Veröffentlichen' → /m/krummelus geht live"
