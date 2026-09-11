#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo 'Run as root: sudo bash installer/uninstall.sh'; exit 1; fi
read -r -p 'Remove Rabby Host service and panel files? Type REMOVE to continue: ' confirmation
[[ "$confirmation" == "REMOVE" ]] || { echo 'Cancelled.'; exit 0; }
systemctl disable --now rabby-host.service 2>/dev/null || true
rm -f /etc/systemd/system/rabby-host.service
systemctl daemon-reload
rm -rf /opt/rabby-host
if [[ "${1:-}" == "--with-data" ]]; then
  read -r -p 'Also remove panel data, logs, and websites? Type DELETE-DATA to continue: ' data_confirmation
  if [[ "$data_confirmation" == "DELETE-DATA" ]]; then
    rm -rf /var/lib/rabby-host /var/log/rabby-host /var/www/rabby-host
  else
    echo 'Data removal cancelled; panel data was preserved.'
  fi
else
  echo 'Panel data and websites were preserved. Pass --with-data for an explicit second confirmation.'
fi
echo 'Rabby Host removed.'
