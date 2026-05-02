#!/usr/bin/env bash
# ==============================================================================
# SHIKSHA · sync-templates.sh — Schneller Sync für Templates und UIs
# ==============================================================================
#
# Pusht NUR server/marketing_templates/ und server/ui/ — kein Service-Restart.
# Jinja-Templates lädt FastAPI zur Laufzeit, UIs sind statisch und werden
# direkt von nginx ausgeliefert. Ergo: rsync genügt, kein systemctl restart.
#
# Für Code/Migration-Änderungen oder eine sichere Komplett-Synchronisation:
#   bash deploy/scripts/sync.sh --confirmed
#
# Usage:
#   bash deploy/scripts/sync-templates.sh             Dry-run (Default)
#   bash deploy/scripts/sync-templates.sh --confirmed Echter Push
#
# Env-Overrides: SRV, KEY (siehe sync.sh)
# ==============================================================================

set -euo pipefail

SRV="${SRV:-root@88.99.174.186}"
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SSH_CMD="ssh -i $KEY -o StrictHostKeyChecking=no"

CONFIRMED=0
for arg in "$@"; do
  case "$arg" in
    --confirmed) CONFIRMED=1 ;;
    -h|--help)
      sed -n '2,/^# ==.*=$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "✗ Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

if [ ! -d "server/marketing_templates" ] || [ ! -d "server/ui" ]; then
  echo "✗ server/marketing_templates oder server/ui nicht gefunden. Aus dem Repo-Root ausführen."
  exit 1
fi

DIRS=("marketing_templates" "ui")
RSYNC_FLAGS=(-a --delete --exclude='.DS_Store')
[ $CONFIRMED -eq 0 ] && RSYNC_FLAGS+=(--dry-run)

for dir in "${DIRS[@]}"; do
  echo "→ rsync server/$dir/ → /opt/shiksha/$dir/"
  OUT=$(rsync -v "${RSYNC_FLAGS[@]}" \
    -e "$SSH_CMD" \
    "server/$dir/" "$SRV:/opt/shiksha/$dir/" 2>&1) || {
      echo "✗ rsync für $dir fehlgeschlagen:"
      echo "$OUT"
      exit 1
    }

  DELETES=$(echo "$OUT" | grep '^deleting ' || true)
  if [ -n "$DELETES" ]; then
    COUNT=$(echo "$DELETES" | wc -l | tr -d ' ')
    echo "  ⚠ $COUNT Löschung(en) geplant/durchgeführt:"
    echo "$DELETES" | sed 's/^/    /'
  fi
done

if [ $CONFIRMED -eq 0 ]; then
  echo ""
  echo "ℹ Dry-Run-Modus. Für echten Push: bash $0 --confirmed"
  exit 0
fi

echo ""
echo "✓ Templates und UIs gepusht. Kein Service-Restart nötig."
