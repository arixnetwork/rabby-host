#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${RABBY_HOST_REPO_URL:-https://github.com/arixnetwork/rabby-host.git}"
REPO_REF="${RABBY_HOST_VERSION:-main}"
WORK_DIR="${RABBY_HOST_WORK_DIR:-/tmp/rabby-host-install}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root: curl -fsSL https://raw.githubusercontent.com/arixnetwork/rabby-host/main/install.sh | sudo bash" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "Unsupported system: /etc/os-release is missing." >&2
  exit 1
fi

. /etc/os-release
if [[ "${ID:-}" != "debian" || ("${VERSION_ID:-}" != "12" && "${VERSION_ID:-}" != "13") ]]; then
  echo "Rabby Host supports Debian 12 and 13 (found ${PRETTY_NAME:-unknown})." >&2
  exit 1
fi

case "$(dpkg --print-architecture)" in
  amd64|arm64) ;;
  *) echo "Unsupported architecture. Rabby Host supports amd64 and arm64." >&2; exit 1 ;;
esac

command -v git >/dev/null 2>&1 || {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y --no-install-recommends git ca-certificates
}

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
echo "Downloading Rabby Host (${REPO_REF})..."
git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$WORK_DIR/source"

exec bash "$WORK_DIR/source/installer/install.sh"
