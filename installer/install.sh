#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

if [[ $EUID -ne 0 ]]; then echo 'Run as root: sudo bash installer/install.sh' >&2; exit 1; fi
if [[ ! -r /etc/os-release ]]; then echo 'Unsupported system: /etc/os-release missing' >&2; exit 1; fi
. /etc/os-release
if [[ "${ID:-}" != debian || ("${VERSION_ID:-}" != 12 && "${VERSION_ID:-}" != 13) ]]; then echo "Rabby Host supports Debian 12 and 13 (found ${PRETTY_NAME:-unknown})." >&2; exit 1; fi
case "$(dpkg --print-architecture)" in amd64|arm64) ;; *) echo 'Unsupported architecture. Use amd64 or arm64.' >&2; exit 1;; esac

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip nginx mariadb-server nodejs npm sqlite3 curl ca-certificates

install -d -o root -g root -m 0755 /opt/rabby-host /etc/rabby-host /var/lib/rabby-host /var/log/rabby-host /var/www/rabby-host/sites
if id rabby-host >/dev/null 2>&1; then :; else useradd --system --home /var/lib/rabby-host --shell /usr/sbin/nologin --user-group rabby-host; fi

ENV_FILE=/etc/rabby-host/rabby-host.env
if [[ ! -s "$ENV_FILE" ]] || ! grep -q '^RABBY_HOST_ADMIN_TOKEN=' "$ENV_FILE"; then
  umask 077
  TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  cat > "$ENV_FILE" <<EOF
RABBY_HOST_ADMIN_TOKEN=$TOKEN
RABBY_HOST_DATA_DIR=/var/lib/rabby-host
RABBY_HOST_LOG_DIR=/var/log/rabby-host
ENVIRONMENT=debian
EOF
  chmod 0600 "$ENV_FILE"
  chown root:rabby-host "$ENV_FILE"
fi

python3 -m venv /opt/rabby-host/venv
/opt/rabby-host/venv/bin/pip install --upgrade pip
/opt/rabby-host/venv/bin/pip install --requirement "$PROJECT_DIR/backend/requirements.txt"
rm -rf -- /opt/rabby-host/app
cp -a -- "$PROJECT_DIR/backend/app" /opt/rabby-host/app
chown -R root:rabby-host /opt/rabby-host /var/lib/rabby-host /var/log/rabby-host
chmod 0750 /var/lib/rabby-host /var/log/rabby-host

install -m 0644 -- "$PROJECT_DIR/systemd/rabby-host.service" /etc/systemd/system/rabby-host.service
systemctl daemon-reload
systemctl enable --now rabby-host.service

healthy=0
for attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8787/api/v1/health >/dev/null; then healthy=1; break; fi
  sleep 1
done
if [[ "$healthy" -ne 1 ]]; then
  systemctl --no-pager --full status rabby-host.service || true
  echo 'Rabby Host failed its health check.' >&2
  exit 1
fi

echo 'Rabby Host installed successfully.'
LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Dashboard: http://${LAN_IP:-127.0.0.1}:8787"
echo 'Service: rabby-host.service'
