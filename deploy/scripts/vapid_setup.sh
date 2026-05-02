#!/usr/bin/env bash
# ============================================================
# SHIKSHA · vapid_setup.sh — VAPID-Keys generieren + verdrahten
#
# Generiert ein VAPID-Key-Pair, legt es als systemd drop-in für
# shiksha.service ab, restartet den Service, testet den Public-Key-
# Endpoint.
#
#   bash vapid_setup.sh
# ============================================================
set -e
KEY="${KEY:-$HOME/.ssh/shiksha_key}"
SRV="${SRV:-root@88.99.174.186}"
EMAIL="${EMAIL:-herrknoedler@gmail.com}"

ssh -i "$KEY" "$SRV" "EMAIL=$EMAIL bash -s" <<'REMOTE'
set -e
VAPID_DIR=/opt/shiksha/secrets/.vapid
PEM_PATH="$VAPID_DIR/private_key.pem"

# 1. Verzeichnis vorbereiten
mkdir -p "$VAPID_DIR"
cd "$VAPID_DIR"

# 2. Wenn noch keine Keys da: generieren
if [ ! -f "$PEM_PATH" ]; then
  /opt/shiksha/venv/bin/vapid --gen
  echo "✓ Neue VAPID-Keys erzeugt"
else
  echo "↪ Bestehende Keys gefunden (Re-Use)"
fi

chmod 600 "$PEM_PATH"

# 3. Public-Key auslesen
PUB=$(/opt/shiksha/venv/bin/vapid --applicationServerKey 2>&1 \
        | grep -oE 'Application Server Key = [A-Za-z0-9_-]+' \
        | sed 's/.*= //')
if [ -z "$PUB" ]; then
  # Fallback bei anderer py-vapid-Version
  PUB=$(cd "$VAPID_DIR" && /opt/shiksha/venv/bin/python -c "
from py_vapid import Vapid
v = Vapid.from_file('private_key.pem')
print(v.public_key.to_compressed_form().hex() if hasattr(v,'public_key') else '')
" 2>/dev/null)
fi
if [ -z "$PUB" ]; then
  PUB=$(cd "$VAPID_DIR" && /opt/shiksha/venv/bin/python <<'PYEOF'
from py_vapid import Vapid
import base64
v = Vapid.from_file('private_key.pem')
pk = v.public_key
# RFC 7515 url-safe base64 without padding
raw = pk.public_bytes(
    encoding=__import__('cryptography').hazmat.primitives.serialization.Encoding.X962,
    format=__import__('cryptography').hazmat.primitives.serialization.PublicFormat.UncompressedPoint
)
print(base64.urlsafe_b64encode(raw).rstrip(b'=').decode())
PYEOF
)
fi
echo "✓ Public-Key: ${PUB:0:24}..."

# 4. systemd drop-in schreiben
DROPIN_DIR=/etc/systemd/system/shiksha.service.d
mkdir -p "$DROPIN_DIR"
cat > "$DROPIN_DIR/vapid.conf" <<CONF
[Service]
Environment=VAPID_PRIVATE_KEY=$PEM_PATH
Environment=VAPID_PUBLIC_KEY=$PUB
Environment=VAPID_SUBJECT=mailto:$EMAIL
CONF
echo "✓ systemd drop-in geschrieben → $DROPIN_DIR/vapid.conf"

# 5. systemd reloaden + Service restarten
systemctl daemon-reload
systemctl restart shiksha
sleep 3

if [ "$(systemctl is-active shiksha)" != "active" ]; then
  echo "✗ Service down nach Restart — Logs:"
  journalctl -u shiksha -n 25 --no-pager
  exit 1
fi
echo "✓ Service läuft"

# 6. Test: vapid-public-key Endpoint
echo
echo "→ Endpoint-Test:"
curl -s https://kita.shiksha.tun.zone/kita/push/vapid-public-key
echo
REMOTE

echo
echo "→ Externer Test (sollte JSON mit public_key liefern):"
curl -s https://kita.shiksha.tun.zone/kita/push/vapid-public-key
echo
echo
echo "✓ VAPID fertig."
echo
echo "Nächster Schritt: Subscribe-Trigger in Pädagogen-App einbauen."
echo "  → Anleitung: outputs/personen/DEPLOY.md Schritt 5"
