#!/usr/bin/env bash
# ==============================================================================
# SHIKSHA · sync.sh — Deploy via rsync
# ==============================================================================
#
# Default-Target: shiksha (FastAPI auf :8000, /opt/shiksha/)
# Opt-In-Target:  engine  (FastAPI auf :8001, /opt/shiksha-engine/)
#
# Workflow:
#   1. Pre-flight: target-spezifischer Indikator-File, git clean, branch
#   2. Dry-run mit --delete: Lösch-Liste + Transfer-Zahl
#   3. Confirmation-Gate: ohne --confirmed passiert NICHTS
#   4. Echter rsync
#   5. Post-rsync chown/chmod  (nur engine — Mac-UID-Fix wie bei STITCH)
#   6. alembic upgrade head    (nur engine)
#   7. systemctl restart $SERVICE
#   8. Curl-Smoke-Tests
#   9. Bericht — KEIN Auto-Rollback
#
# Usage:
#   bash deploy/scripts/sync.sh                        Dry-run shiksha
#   bash deploy/scripts/sync.sh --confirmed            Sync shiksha
#   bash deploy/scripts/sync.sh --engine               Dry-run engine
#   bash deploy/scripts/sync.sh --engine --confirmed   Sync engine
#
# Env-Overrides:
#   SRV=root@<ip>     SSH-Target (Default: root@88.99.174.186)
#   KEY=~/.ssh/...    SSH-Key   (Default: ~/.ssh/shiksha_key)
#   DOMAIN=https://.. Smoke-Test-Basis (Default je Target)
#
# Hinweis zu --delete: ein versehentlich ge-.gitignore'tes Verzeichnis
# (z.B. uploads/) würde sonst auf dem Server gelöscht. Deshalb das
# Confirmation-Gate plus die Excludes-Liste pro Target.
# ==============================================================================

set -euo pipefail

# --- args (Target-Auswahl + Flags) ------------------------------------------
TARGET="shiksha"
CONFIRMED=0
for arg in "$@"; do
  case "$arg" in
    --engine)    TARGET="engine" ;;
    --confirmed) CONFIRMED=1 ;;
    -h|--help)
      sed -n '2,/^# ==.*=$/p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "✗ Unknown arg: $arg" >&2; exit 1 ;;
  esac
done

# --- common config -----------------------------------------------------------
SRV="${SRV:-root@88.99.174.186}"
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SSH_CMD="ssh -i $KEY -o StrictHostKeyChecking=no"

# --- target-specific config --------------------------------------------------
case "$TARGET" in
  shiksha)
    SRC="server/"
    DST="/opt/shiksha/"
    SERVICE="shiksha"
    DOMAIN="${DOMAIN:-https://kita.shiksha.tun.zone}"
    PREFLIGHT_FILE="server/main.py"
    NEEDS_CHOWN=0
    NEEDS_MIGRATE=0
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
      --exclude='marketing_assets/pool/'
      --exclude='*.log'
      --exclude='tmp/'
      --exclude='.DS_Store'
      --exclude='shiksha_engine/'    # engine ist eigenes Target
    )
    SMOKE_URLS=(
      "$DOMAIN/health"
      "$DOMAIN/kita/api/platform/editions"
      "$DOMAIN/kita/api/platform/live-stats"
      "$DOMAIN/m/krummelus"
      "$DOMAIN/accounting/ui/kita/dashboard_traegerin"
    )
    ;;
  engine)
    SRC="server/shiksha_engine/"
    DST="/opt/shiksha-engine/"
    SERVICE="shiksha-engine"
    DOMAIN="${DOMAIN:-https://api.shiksha.world}"
    PREFLIGHT_FILE="server/shiksha_engine/pyproject.toml"
    NEEDS_CHOWN=1
    NEEDS_MIGRATE=1
    SERVICE_USER="shiksha-app"
    DROPIN_DB="/etc/systemd/system/shiksha-engine.service.d/database.conf"
    EXCLUDES=(
      --exclude='.venv/'           # server-side build artifact
      --exclude='.env'             # server-side secret
      --exclude='logs/'            # server-side write target
      --exclude='__pycache__/'
      --exclude='*.pyc'
      --exclude='.pytest_cache/'
      --exclude='.mypy_cache/'
      --exclude='*.egg-info/'
      --exclude='*.bak'
      --exclude='*.log'
      --exclude='.DS_Store'
    )
    SMOKE_URLS=(
      "$DOMAIN/health"
    )
    ;;
  *) echo "✗ Unknown TARGET: $TARGET" >&2; exit 1 ;;
esac

# --- pre-flight --------------------------------------------------------------
echo "→ Pre-flight checks (target=$TARGET)"

if [ ! -f "$PREFLIGHT_FILE" ]; then
  echo "  ✗ $PREFLIGHT_FILE nicht gefunden. Aus dem Repo-Root ausführen."
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
  echo "ℹ Dry-Run-Modus. Für echten Sync: bash $0${TARGET:+ --$TARGET} --confirmed"
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

# --- post-rsync: chown + chmod (engine only) --------------------------------
if [ $NEEDS_CHOWN -eq 1 ]; then
  echo ""
  echo "→ Normalize Owner + Perms ($SERVICE_USER:$SERVICE_USER, 755/644)"
  $SSH_CMD "$SRV" "chown -R $SERVICE_USER:$SERVICE_USER '$DST' && \
                   find '$DST' -type d -exec chmod 755 {} + && \
                   find '$DST' -type f -exec chmod 644 {} +"
  echo "  ✓ chown/chmod done."
fi

# --- alembic upgrade head (engine only) -------------------------------------
if [ $NEEDS_MIGRATE -eq 1 ]; then
  echo ""
  echo "→ alembic upgrade head"
  # DATABASE_URL aus dem Engine-Drop-In holen — Drop-In ist Single Source of Truth.
  $SSH_CMD "$SRV" "
    set -e
    DB_PW=\$(grep -oP 'shiksha:\K[^@]+' $DROPIN_DB | head -1)
    if [ -z \"\$DB_PW\" ]; then
      echo '  ✗ DB-Passwort aus $DROPIN_DB nicht extrahierbar.'
      exit 1
    fi
    sudo -u $SERVICE_USER bash -c \"
      cd $DST
      export DATABASE_URL='postgresql://shiksha:\$DB_PW@localhost:5432/shiksha'
      export DB_SCHEMA='shiksha_core'
      .venv/bin/alembic upgrade head
    \"
  "
  echo "  ✓ migration done."
fi

# --- systemd restart --------------------------------------------------------
echo ""
echo "→ systemctl restart $SERVICE"
$SSH_CMD "$SRV" "systemctl restart $SERVICE"
sleep 2
$SSH_CMD "$SRV" "systemctl is-active $SERVICE" || {
  echo "✗ Service ist nicht active nach Restart."
  echo "  Status: $($SSH_CMD "$SRV" "systemctl status $SERVICE --no-pager -l | head -20")"
  exit 2
}
echo "  ✓ Service active."

# --- smoke tests ------------------------------------------------------------
echo ""
echo "→ Smoke-Tests gegen $DOMAIN"

FAIL=0
FAIL_URLS=()
for url in "${SMOKE_URLS[@]}"; do
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
  echo "✓ Deploy $COMMIT (target=$TARGET) erfolgreich. Alle ${#SMOKE_URLS[@]} Smoke-Tests grün."
  exit 0
else
  echo "⚠ Deploy $COMMIT (target=$TARGET) angewandt, aber $FAIL von ${#SMOKE_URLS[@]} Smoke-Tests failen:"
  for u in "${FAIL_URLS[@]}"; do
    echo "    $u"
  done
  echo ""
  echo "  KEIN Auto-Rollback. Bitte manuell prüfen — entweder Code-Issue,"
  echo "  oder die fehlende URL ist erwartetes Behavior."
  exit 2
fi
