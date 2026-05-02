#!/usr/bin/env bash
# ==============================================================================
# SHIKSHA · sync.sh — Deploy server/ → /opt/shiksha/ via rsync
# ==============================================================================
#
# Workflow:
#   1. Pre-flight: git status clean, auf main
#   2. Dry-run mit --delete: zuerst Lösch-Liste, dann Übertragungs-Zahl
#   3. Confirmation-Gate: ohne --confirmed passiert NICHTS
#   4. Echter rsync
#   5. systemctl restart shiksha
#   6. Curl-Smoke-Tests
#   7. Bericht — KEIN Auto-Rollback (manuelle Prüfung bei Fehlern)
#
# Usage:
#   bash deploy/scripts/sync.sh                Dry-run (Default — sicher)
#   bash deploy/scripts/sync.sh --confirmed    Echter Sync
#
# Env-Overrides:
#   SRV=root@<ip>           SSH-Target (Default: root@88.99.174.186)
#   KEY=~/.ssh/...          SSH-Key   (Default: ~/.ssh/shiksha_key)
#   DOMAIN=https://...      Smoke-Test-Basis (Default: https://kita.shiksha.tun.zone)
#
# Excludes spiegeln Phase 2 — nichts, was nicht ins Repo gehört, geht raus.
# --delete ist die Bandsäge im rsync-Toolkasten: ein versehentlich ge-
# .gitignore'tes Verzeichnis (z.B. uploads/) würde sonst auf dem Server
# gelöscht. Deshalb das Confirmation-Gate.
# ==============================================================================

set -euo pipefail

# --- config -----------------------------------------------------------------
SRV="${SRV:-root@88.99.174.186}"
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
DOMAIN="${DOMAIN:-https://kita.shiksha.tun.zone}"
SRC="server/"
DST="/opt/shiksha/"

EXCLUDES=(
  --exclude='*.bak'
  --exclude='*.bak.*'
  --exclude='*.bak.v*'
  --exclude='__pycache__/'
  --exclude='*.pyc'
  --exclude='venv/'
  --exclude='uploads/'
  --exclude='secrets/'
  --exclude='archive/'
  --exclude='marketing_assets/pool/'   # Runtime: Bilder werden vom Pool-Importer-Cron befüllt; gehört nicht in den Sync
  --exclude='*.log'
  --exclude='tmp/'
  --exclude='.DS_Store'
)

SSH_CMD="ssh -i $KEY -o StrictHostKeyChecking=no"

# --- args --------------------------------------------------------------------
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

# --- pre-flight --------------------------------------------------------------
echo "→ Pre-flight checks"

# Repo-Root erwarten — relative Pfade sonst falsch
if [ ! -d "server" ] || [ ! -f "server/main.py" ]; then
  echo "  ✗ server/main.py nicht gefunden. Aus dem Repo-Root ausführen."
  exit 1
fi

if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  echo "  ✗ git working tree nicht clean. Erst commit oder stash."
  git status --short
  exit 1
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$BRANCH" != "main" ]; then
  echo "  ⚠ Aktuell auf '$BRANCH', nicht 'main'."
  if [ $CONFIRMED -eq 1 ]; then
    echo "  → Mit --confirmed wird trotzdem deployed."
  else
    echo "  → Im Dry-Run okay; für Echt-Deploy auf main wechseln oder --confirmed setzen."
  fi
fi

echo "  ✓ git clean, branch=$BRANCH"
COMMIT=$(git rev-parse --short HEAD)
echo "  ✓ Deploy-Commit: $COMMIT"

# --- dry-run mit --delete ---------------------------------------------------
echo ""
echo "→ Dry-Run gegen $SRV:$DST"

DRY_OUT=$(rsync -av --dry-run --delete \
  "${EXCLUDES[@]}" \
  -e "$SSH_CMD" \
  "$SRC" "$SRV:$DST" 2>&1) || {
    echo "✗ Dry-Run fehlgeschlagen — SSH/rsync-Fehler."
    echo "$DRY_OUT"
    exit 1
  }

DELETIONS=$(echo "$DRY_OUT" | grep '^deleting ' || true)
TRANSFERS=$(echo "$DRY_OUT" | grep -vE '^(deleting |sending |building |sent |total |speedup|receiving |\.\.\./$|$)' | tail -n +1 | wc -l | tr -d ' ')

echo ""
if [ -n "$DELETIONS" ]; then
  COUNT=$(echo "$DELETIONS" | wc -l | tr -d ' ')
  echo "⚠️  $COUNT File(s) WÜRDEN auf $SRV:$DST GELÖSCHT:"
  echo "$DELETIONS" | sed 's/^/    /'
  echo ""
else
  echo "✓ Keine Löschungen geplant."
fi

echo "→ ~$TRANSFERS Files würden übertragen/aktualisiert."

# --- confirmation gate ------------------------------------------------------
if [ $CONFIRMED -eq 0 ]; then
  echo ""
  echo "ℹ Dry-Run-Modus. Für echten Sync: bash $0 --confirmed"
  exit 0
fi

# --- real rsync -------------------------------------------------------------
echo ""
echo "→ Applying rsync (echter Sync mit --delete)..."
rsync -a --delete \
  "${EXCLUDES[@]}" \
  -e "$SSH_CMD" \
  "$SRC" "$SRV:$DST"
echo "  ✓ rsync done."

# --- systemd restart --------------------------------------------------------
echo ""
echo "→ systemctl restart shiksha"
$SSH_CMD "$SRV" "systemctl restart shiksha"
sleep 2
$SSH_CMD "$SRV" "systemctl is-active shiksha" || {
  echo "✗ Service ist nicht active nach Restart."
  echo "  Status: $($SSH_CMD "$SRV" 'systemctl status shiksha --no-pager -l | head -20')"
  exit 2
}
echo "  ✓ Service active."

# --- smoke tests ------------------------------------------------------------
echo ""
echo "→ Smoke-Tests gegen $DOMAIN"
URLS=(
  "$DOMAIN/health"
  "$DOMAIN/kita/api/platform/editions"
  "$DOMAIN/kita/api/platform/live-stats"
  "$DOMAIN/m/krummelus"
  "$DOMAIN/accounting/ui/kita/dashboard_traegerin"
)

FAIL=0
FAIL_URLS=()
for url in "${URLS[@]}"; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" || echo "000")
  if [ "$CODE" = "200" ]; then
    printf "  ✓ %3s  %s\n" "$CODE" "$url"
  else
    printf "  ✗ %3s  %s\n" "$CODE" "$url"
    FAIL=$((FAIL+1))
    FAIL_URLS+=("$url ($CODE)")
  fi
done

# --- report -----------------------------------------------------------------
echo ""
echo "════════════════════════════════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
  echo "✓ Deploy $COMMIT erfolgreich. Alle ${#URLS[@]} Smoke-Tests grün."
  exit 0
else
  echo "⚠ Deploy $COMMIT angewandt, aber $FAIL von ${#URLS[@]} Smoke-Tests failen:"
  for u in "${FAIL_URLS[@]}"; do
    echo "    $u"
  done
  echo ""
  echo "  KEIN Auto-Rollback. Bitte manuell prüfen — entweder Code-Issue,"
  echo "  oder die fehlende URL ist erwartetes Behavior (z.B. /m/shiksha"
  echo "  bis Phase 4 noch 404)."
  exit 2
fi
