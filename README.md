# Rabby Host

Rabby Host is a lightweight Debian control panel for personal hosting. The repository contains a Next.js preview dashboard and a Debian-native FastAPI service foundation. The UI is intentionally explicit about the operations it presents; privileged production operations belong in the backend service layer and never in an arbitrary shell endpoint.

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
uvicorn backend.app.main:app --reload --port 8787
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

The installer installs Debian-native Nginx, MariaDB, PHP-FPM, Node.js, Python, creates the restricted `rabby-host` service user, and enables `rabby-host.service` on boot. The current panel foundation exposes health, system, services, websites, and bounded log API routes; website provisioning modules are being added behind explicit service boundaries.

## Security

Do not expose the panel directly to the public internet without HTTPS and firewall review. Keep `/var/lib/rabby-host`, service credentials, and generated Nginx configuration owned by root or the service account as appropriate. The application does not provide an arbitrary command execution endpoint.

## License

Apache-2.0
