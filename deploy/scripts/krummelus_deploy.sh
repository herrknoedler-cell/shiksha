#!/usr/bin/env bash
# ============================================================
# SHIKSHA · Subdomain-Setup für eine Pilot-KITA
# Direkt auf dem Hetzner-Server (88.99.174.186) ausführen.
#
# Usage:
#   bash krummelus_deploy.sh                      # interaktiv
#   bash krummelus_deploy.sh DOMAIN EMAIL ORG     # mit Argumenten
# ============================================================
set -e

DOMAIN="${1:-}"
EMAIL="${2:-}"
ORG_SLUG="${3:-kita_pilot}"

if [ -z "$DOMAIN" ]; then read -p "Domain (z.B. krummelus.tun.zone): " DOMAIN; fi
if [ -z "$EMAIL" ];  then read -p "E-Mail für Let's Encrypt: " EMAIL; fi

echo "→ Domain:   $DOMAIN"
echo "→ E-Mail:   $EMAIL"
echo "→ Org-Slug: $ORG_SLUG"

# DNS-Check
echo "→ DNS-Auflösung testen ..."
RESOLVED=$(dig +short "$DOMAIN" | head -1)
if [ -z "$RESOLVED" ]; then
  echo "❌ $DOMAIN löst noch nicht auf. Bitte DNS-Eintrag prüfen und 1–5 Min warten."
  exit 1
fi
echo "   → $RESOLVED"

# certbot installieren falls fehlt
if ! command -v certbot >/dev/null; then
  echo "→ certbot wird installiert ..."
  apt-get update -qq
  apt-get install -y certbot python3-certbot-nginx
fi

# nginx-Server-Block
echo "→ nginx-Block für $DOMAIN schreiben ..."
cat > /etc/nginx/sites-available/$DOMAIN <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Org-Slug "$ORG_SLUG";
        proxy_read_timeout 90;
        client_max_body_size 20m;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN

echo "→ nginx-Config testen ..."
nginx -t
systemctl reload nginx

# SSL via Let's Encrypt
echo "→ SSL-Zertifikat anfordern ..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL --redirect

# Smoke-Test
echo
echo "=== HTTP-Header (sollte 301 → HTTPS sein) ==="
curl -sI http://$DOMAIN | head -3
echo
echo "=== HTTPS-Backend ==="
curl -s https://$DOMAIN/kita/calendar/event-types | head -c 400
echo
echo
echo "✅ Fertig. Trägerin-Dashboard: https://$DOMAIN/accounting/ui/kita/dashboard"
