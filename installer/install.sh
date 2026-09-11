#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo 'Run as root: sudo bash installer/install.sh'; exit 1; fi
if [[ ! -r /etc/os-release ]]; then echo 'Unsupported system: /etc/os-release missing'; exit 1; fi
. /etc/os-release
if [[ "$ID" != debian || ("$VERSION_ID" != 12 && "$VERSION_ID" != 13) ]]; then echo "Rabby Host supports Debian 12 and 13 (found ${PRETTY_NAME:-unknown})."; exit 1; fi
case "$(dpkg --print-architecture)" in amd64|arm64) ;; *) echo 'Unsupported architecture. Use amd64 or arm64.'; exit 1;; esac
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv python3-pip nginx mariadb-server nodejs npm sqlite3 curl ca-certificates
install -d -o root -g root -m 0755 /opt/rabby-host /var/lib/rabby-host /var/log/rabby-host /var/www/rabby-host/sites
if id rabby-host >/dev/null 2>&1; then :; else useradd --system --home /var/lib/rabby-host --shell /usr/sbin/nologin --user-group rabby-host; fi
python3 -m venv /opt/rabby-host/venv
/opt/rabby-host/venv/bin/pip install --upgrade pip
/opt/rabby-host/venv/bin/pip install --requirement backend/requirements.txt
rm -rf /opt/rabby-host/app
cp -r backend/app /opt/rabby-host/app
chown -R root:rabby-host /opt/rabby-host /var/lib/rabby-host /var/log/rabby-host
chmod 0750 /var/lib/rabby-host /var/log/rabby-host
cp systemd/rabby-host.service /etc/systemd/system/rabby-host.service
systemctl daemon-reload
systemctl enable --now rabby-host.service
for attempt in $(seq 1 20); do curl --fail --silent http://127.0.0.1:8787/api/v1/health >/dev/null && break; sleep 1; done
curl --fail --silent http://127.0.0.1:8787/api/v1/health >/dev/null
echo 'Rabby Host installed successfully.'
echo "Dashboard: http://$(hostname -I | awk '{print $1}'):8787"
echo 'Service: rabby-host.service'
