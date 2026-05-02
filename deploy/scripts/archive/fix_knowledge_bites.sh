#!/usr/bin/env bash
# ============================================================
# SHIKSHA · fix_knowledge_bites.sh
# Lokale JSON validieren, hochladen, fix-greeting nochmal
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
LOCAL="$(cd "$(dirname "$0")" && pwd)"

# 1. Lokal validieren
echo "→ Lokale JSON validieren …"
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('$LOCAL/greeting/knowledge_bites.json').read_text())
print(f'  ✓ {len(data)} Bites gültig')
" || { echo "✗ JSON ist immer noch kaputt"; exit 1; }

# 2. Upload + Permission + Insights-Cron + Greeting-Test (alles in einem)
scp -i "$KEY" "$LOCAL/greeting/knowledge_bites.json" "$SRV:/tmp/"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e
cp /tmp/knowledge_bites.json /opt/shiksha/data/knowledge_bites.json
chmod 644 /opt/shiksha/data/knowledge_bites.json
echo "  ✓ JSON neu installiert"

# Read-Test als simulierter shiksha-Service
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('/opt/shiksha/data/knowledge_bites.json').read_text())
print(f'  ✓ Server kann {len(data)} Bites lesen')
"

# DATABASE_URL holen + Insights-Cron einmal triggern
DB_URL=$(systemctl show shiksha -p Environment --value 2>/dev/null \
         | tr ' ' '\n' | grep -E '^DATABASE_URL=' | head -1 | cut -d= -f2-)
if [ -z "$DB_URL" ]; then
  for f in $(systemctl show shiksha -p EnvironmentFiles --value 2>/dev/null | tr ' ' '\n' | sed 's/^-//'); do
    [ -f "$f" ] && url=$(grep -E '^DATABASE_URL=' "$f" 2>/dev/null | head -1 | cut -d= -f2-)
    [ -n "$url" ] && DB_URL="$url" && break
  done
fi
DB_URL=$(echo "$DB_URL" | sed -e 's/^"//' -e 's/"$//')

if [ -n "$DB_URL" ]; then
  echo
  echo "→ Insights-Cron mit DATABASE_URL ausführen …"
  DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py 2>&1 | tail -10
fi
REMOTE

echo
echo "→ Greeting-Test:"
curl -s -H "X-User-Id: heidi" \
  "https://kita.shiksha.tun.zone/kita/dashboard/card/greeting?role=traegerin&user=Heidi" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('  greeting:    ', d.get('greeting'))
print('  mood:        ', d.get('mood'))
k = d.get('knowledge')
print('  knowledge:   ', (k.get('title') + ' — ' + k.get('body', '')[:70] + '…') if k else 'NULL')
print('  weekly_theme:', (d.get('weekly_theme') or {}).get('theme') or 'noch nicht gesetzt')
i = d.get('insight')
print('  insight:     ', i.get('title') if i else 'noch keiner')
"
echo
echo "✓ Fertig."
