# Provider architecture

Rabby Host separates UI/API contracts from host operations. `lib/providers.ts` defines the provider interfaces used by the dashboard and future API layer.

## DevelopmentProvider

The Vercel deployment is a safe development/demo environment. It must expose only persisted application records and must never execute privileged Linux commands. Demo data is labeled in the UI.

## DebianProvider

The Debian deployment will implement the same interfaces in FastAPI using explicit adapters for Nginx, systemd, MariaDB, PHP-FPM, filesystem, certbot, firewall, and cloudflared. No arbitrary shell endpoint is permitted.

## API boundary

The UI should call `/api/v1/*` contracts. Each operation returns typed status, task identifiers for long-running work, and human-readable errors without secrets or stack traces.
