#!/usr/bin/env bash
# ============================================================
# SHIKSHA · fix_greeting.sh
# 1. Knowledge-Bites world-readable machen
# 2. DATABASE_URL aus shiksha-Service in Cron-Job verdrahten
# 3. Insights-Cron einmal manuell testen
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
set -e

# ---------- 1. Knowledge-Bites readable ----------
chmod -R a+rX /opt/shiksha/data
ls -la /opt/shiksha/data/knowledge_bites.json
echo "  ✓ Knowledge-Bites: a+rX gesetzt"

# Test: wird die Datei gelesen?
python3 -c "
import json, pathlib
data = json.loads(pathlib.Path('/opt/shiksha/data/knowledge_bites.json').read_text())
print(f'  ✓ {len(data)} Wissens-Snippets ladbar')
"

# ---------- 2. DATABASE_URL aus shiksha-Service holen ----------
echo
echo "→ Suche DATABASE_URL aus systemd-Service …"

DB_URL=""

# (a) direkt in Environment=
DB_URL=$(systemctl show shiksha -p Environment --value 2>/dev/null \
         | tr ' ' '\n' | grep -E '^DATABASE_URL=' | head -1 | cut -d= -f2-)

# (b) in EnvironmentFiles
if [ -z "$DB_URL" ]; then
  for f in $(systemctl show shiksha -p EnvironmentFiles --value 2>/dev/null | tr ' ' '\n' | sed 's/^-//'); do
    if [ -f "$f" ]; then
      url=$(grep -E '^DATABASE_URL=' "$f" 2>/dev/null | head -1 | cut -d= -f2-)
      if [ -n "$url" ]; then DB_URL="$url"; break; fi
    fi
  done
fi

# (c) in drop-in conf-Files
if [ -z "$DB_URL" ]; then
  for cfg in /etc/systemd/system/shiksha.service.d/*.conf 2>/dev/null; do
    [ -f "$cfg" ] || continue
    url=$(grep -oE 'Environment="?DATABASE_URL=[^"]+' "$cfg" 2>/dev/null | head -1 | sed -E 's/^Environment="?DATABASE_URL=//')
    if [ -n "$url" ]; then DB_URL="$url"; break; fi
  done
fi

# (d) in /opt/shiksha/.env oder /etc/shiksha/.env
if [ -z "$DB_URL" ]; then
  for envf in /opt/shiksha/.env /etc/shiksha/.env; do
    if [ -f "$envf" ]; then
      url=$(grep -E '^DATABASE_URL=' "$envf" 2>/dev/null | head -1 | cut -d= -f2-)
      if [ -n "$url" ]; then DB_URL="$url"; break; fi
    fi
  done
fi

# Anführungszeichen abschneiden
DB_URL=$(echo "$DB_URL" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")

if [ -z "$DB_URL" ]; then
  echo "✗ Konnte DATABASE_URL nicht finden."
  echo "  Bitte manuell setzen: export DATABASE_URL=postgresql://..."
  echo "  Dann: /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py"
  exit 1
fi

echo "  ✓ DATABASE_URL gefunden (${#DB_URL} Zeichen, beginnt mit: ${DB_URL:0:25}…)"

# ---------- 3. Cron neu schreiben mit DB_URL ----------
cat > /etc/cron.d/shiksha-insights <<CRON
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
DATABASE_URL=$DB_URL
0 3 * * * root /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py >> /var/log/shiksha-insights.log 2>&1
CRON
chmod 644 /etc/cron.d/shiksha-insights
echo "  ✓ Cron-Job mit DATABASE_URL aktualisiert"

# ---------- 4. Insights-Cron einmal manuell testen ----------
echo
echo "→ Teste Insights-Cron manuell …"
DATABASE_URL="$DB_URL" /opt/shiksha/venv/bin/python /opt/shiksha/shiksha_insights_cron.py 2>&1 | tail -15

REMOTE

echo
echo "→ Greeting nochmal testen (knowledge sollte jetzt befüllt sein):"
curl -s -H "X-User-Id: heidi" \
  "https://kita.shiksha.tun.zone/kita/dashboard/card/greeting?role=traegerin&user=Heidi" \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('  greeting:', d.get('greeting'))
print('  mood:', d.get('mood'))
print('  knowledge:', d.get('knowledge', {}).get('title') if d.get('knowledge') else 'NULL')
print('  weekly_theme:', d.get('weekly_theme', {}).get('theme') if d.get('weekly_theme') else 'noch nicht gesetzt')
print('  insight:', d.get('insight', {}).get('title') if d.get('insight') else 'noch keiner')
"
echo
echo "✓ Fix fertig."
