#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo 'Run as root: sudo bash installer/update.sh'; exit 1; fi
if [[ ! -d /opt/rabby-host ]]; then echo 'Rabby Host is not installed.'; exit 1; fi
backup="/var/lib/rabby-host/panel-backup-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -czf "$backup" --ignore-failed-read /var/lib/rabby-host /etc/systemd/system/rabby-host.service
python3 -m venv --clear /opt/rabby-host/venv
/opt/rabby-host/venv/bin/pip install --upgrade pip
/opt/rabby-host/venv/bin/pip install --requirement backend/requirements.txt
rm -rf /opt/rabby-host/app
cp -r backend/app /opt/rabby-host/app
chown -R root:rabby-host /opt/rabby-host
systemctl daemon-reload
systemctl restart rabby-host.service
curl --fail --silent http://127.0.0.1:8787/api/v1/health >/dev/null
echo "Rabby Host updated. Backup: $backup"
