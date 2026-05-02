#!/usr/bin/env bash
# Diagnose: was fehlt für /ui/kita/personen/push/calendar?
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"

ssh -i "$KEY" "$SRV" 'bash -s' <<'REMOTE'
echo "=== /opt/shiksha/ui/kita/ ==="
ls -la /opt/shiksha/ui/kita/ 2>/dev/null || echo "Verzeichnis fehlt!"

echo
echo "=== /tmp/ — sind die Quell-Files noch da? ==="
ls -la /tmp/personen_ui.html /tmp/push_sender_ui.html /tmp/calendar_ui.html \
       /tmp/shiksha-push.js  /tmp/service-worker.js 2>&1 | head -10

echo
echo "=== Letzte 30 Zeilen Service-Log (Fehler) ==="
journalctl -u shiksha -n 60 --no-pager | grep -iE "error|exception|traceback|filenotfound" | tail -20

echo
echo "=== Wo gibt es bereits service-worker.js Mounts? ==="
grep -n "service-worker" /opt/shiksha/accounting_router.py | head -10
REMOTE
