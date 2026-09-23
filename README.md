# Rabby Host

Rabby Host is a lightweight Debian control panel for personal hosting. The repository contains a Next.js preview dashboard and a Debian-native FastAPI service foundation. The UI is intentionally designed as a local management dashboard for a single Debian host.

## Development

```bash
pnpm install
pnpm dev
pnpm build
```

Backend development:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export RABBY_HOST_ADMIN_TOKEN="change-me"
uvicorn backend.app.main:app --reload --port 8787
```

For the admin dashboard and API calls, set the same token in the browser environment and on the API server:

```bash
export RABBY_HOST_ADMIN_TOKEN="replace-with-a-long-random-secret"
export NEXT_PUBLIC_RABBY_HOST_API_TOKEN="replace-with-the-same-secret"
```

## Debian installation

Supported: Debian 12 Bookworm and Debian 13 Trixie on amd64 or arm64. The remote bootstrap validates the OS and architecture, clones the selected repository ref into a temporary directory, and runs the versioned installer. It does not execute arbitrary downloaded commands outside the repository installer.

Recommended installation from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/arixnetwork/rabby-host/main/install.sh | sudo bash
```

Install a specific branch or release ref:

```bash
curl -fsSL https://raw.githubusercontent.com/arixnetwork/rabby-host/main/install.sh | sudo RABBY_HOST_VERSION=v1.0.0 bash
```

Install from a fork or mirror:

```bash
curl -fsSL https://raw.githubusercontent.com/arixnetwork/rabby-host/main/install.sh | sudo RABBY_HOST_REPO_URL=https://github.com/OWNER/REPO.git bash
```

For a checked-out source tree:

```bash
sudo bash installer/install.sh
systemctl status rabby-host
```

The installer installs Debian-native Nginx, MariaDB, PHP-FPM, Node.js, Python, creates the restricted `rabby-host` service user, and enables `rabby-host.service` on boot. The current panel foundation expects the control interface to run behind a trusted local network boundary and to use a configured admin token.

## Security

Do not expose the panel directly to the public internet without HTTPS and firewall review. Keep `/var/lib/rabby-host`, service credentials, and generated Nginx configuration owned by root or the service account, and set `RABBY_HOST_ADMIN_TOKEN` before the control panel is used in a shared environment.

## License

Apache-2.0
