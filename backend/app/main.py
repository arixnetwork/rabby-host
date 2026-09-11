"""Rabby Host FastAPI service.

Only explicit, allow-listed read operations live in this starter service. Privileged
website operations are intentionally kept out of HTTP until their adapters exist.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import shutil
import socket
import subprocess
import time

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

APP_ROOT = Path(os.getenv("RABBY_HOST_DATA_DIR", "/var/lib/rabby-host"))
LOG_ROOT = Path(os.getenv("RABBY_HOST_LOG_DIR", "/var/log/rabby-host"))
VERSION = "1.0.0"
SUPPORTED_SERVICES = ("nginx", "mariadb", "mysql", "php8.2-fpm", "php8.3-fpm", "php8.4-fpm", "rabby-host")

app = FastAPI(
    title="Rabby Host API",
    version=VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
origins = [origin.strip() for origin in os.getenv("RABBY_HOST_CORS_ORIGINS", "http://localhost:8787").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)


def service_state(name: str) -> str:
    """Read systemd state without accepting arbitrary service names."""
    if name not in SUPPORTED_SERVICES:
        raise HTTPException(status_code=400, detail="Unsupported service")
    try:
        result = subprocess.run(
            ["/usr/bin/systemctl", "is-active", name],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unavailable"
    state = result.stdout.strip()
    return state if state in {"active", "inactive", "failed", "activating", "deactivating"} else "unknown"


def memory_info() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0]) * 1024
    except (FileNotFoundError, ValueError):
        return {"total": 0, "available": 0, "used": 0}
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return {"total": total, "available": available, "used": max(0, total - available)}


def uptime_seconds() -> int:
    try:
        return int(float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0]))
    except (FileNotFoundError, ValueError):
        return 0


@app.exception_handler(Exception)
async def unexpected_error(_, exc: Exception):
    reference = f"RH-{int(time.time() * 1000)}"
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with (LOG_ROOT / "app.log").open("a", encoding="utf-8") as log:
        log.write(f"{reference} {type(exc).__name__}: {exc}\n")
    return JSONResponse(status_code=500, content={"error": "Unexpected server error", "reference": reference})


@app.get("/api/v1/health", tags=["system"])
def health():
    return {"status": "ok", "service": "rabby-host", "version": VERSION, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/system", tags=["system"])
def system_info():
    total, used, free = shutil.disk_usage("/")
    memory = memory_info()
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    return {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 1,
        "load": {"1m": load[0], "5m": load[1], "15m": load[2]},
        "memory": memory,
        "disk": {"total": total, "used": used, "free": free},
        "uptime_seconds": uptime_seconds(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/websites", tags=["websites"])
def list_websites():
    return {"items": [], "total": 0, "available": False, "message": "Website repository is not initialized yet."}


@app.get("/api/v1/services", tags=["services"])
def list_services():
    return {"items": [{"name": name, "status": service_state(name)} for name in ("nginx", "mariadb", "rabby-host")]}


@app.get("/api/v1/logs", tags=["logs"])
def logs(source: str = Query("rabby-host", pattern="^[a-z0-9_.-]+$"), lines: int = Query(100, ge=1, le=500)):
    allowed = {"rabby-host": LOG_ROOT / "app.log", "security": LOG_ROOT / "security.log", "tasks": LOG_ROOT / "tasks.log"}
    path = allowed.get(source)
    if path is None:
        raise HTTPException(status_code=400, detail="Unsupported log source")
    if not path.exists():
        return {"source": source, "lines": [], "limit": lines}
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    return {"source": source, "lines": content, "limit": lines}
