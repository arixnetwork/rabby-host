"""Rabby Host API with a persistent development repository and safe Debian adapters."""
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import shutil
import socket
import subprocess
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .database import repository

VERSION = "1.0.0"
DATA_ROOT = Path(os.getenv("RABBY_HOST_DATA_DIR", "/var/lib/rabby-host"))
LOG_ROOT = Path(os.getenv("RABBY_HOST_LOG_DIR", "/var/log/rabby-host"))
SUPPORTED_SERVICES = ("nginx", "mariadb", "mysql", "rabby-host")
WebsiteType = Literal["WordPress", "PHP", "Node.js", "Static"]
repo = repository(DATA_ROOT)
app = FastAPI(title="Rabby Host API", version=VERSION, docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json")
origins = [value.strip() for value in os.getenv("RABBY_HOST_CORS_ORIGINS", "http://localhost:3000,http://localhost:8787").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token"])

class WebsiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*$")
    domain: str = Field(min_length=3, max_length=253, pattern=r"^(?=.{1,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[A-Za-z]{2,63}$|^[a-zA-Z0-9][a-zA-Z0-9.-]{1,62}$")
    type: WebsiteType
    runtime: str = Field(min_length=1, max_length=32)
    port: int = Field(default=80, ge=1, le=65535)
    ssl: bool = False
    config: dict[str, str] = Field(default_factory=dict)

    @field_validator("runtime", "domain")
    @classmethod
    def reject_control_chars(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("Control characters are not allowed")
        return value.strip().lower() if value != "runtime" else value.strip()

class StatusChange(BaseModel):
    status: Literal["Running", "Stopped"]

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

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

def service_state(name: str) -> str:
    if name not in SUPPORTED_SERVICES:
        raise HTTPException(status_code=400, detail="Unsupported service")
    try:
        result = subprocess.run(["/usr/bin/systemctl", "is-active", name], check=False, capture_output=True, text=True, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unavailable"
    value = result.stdout.strip()
    return value if value in {"active", "inactive", "failed", "activating", "deactivating"} else "unknown"

@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rabby-host", "version": VERSION, "environment": os.getenv("ENVIRONMENT", "debian"), "timestamp": now()}

@app.get("/api/v1/system", tags=["system"])
def system_info() -> dict[str, object]:
    total, used, free = shutil.disk_usage("/")
    memory = memory_info()
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    return {"hostname": socket.gethostname(), "os": platform.platform(), "kernel": platform.release(), "architecture": platform.machine(), "cpu": platform.processor() or "unknown", "cpu_count": os.cpu_count() or 1, "load": {"1m": load[0], "5m": load[1], "15m": load[2]}, "memory": memory, "disk": {"total": total, "used": used, "free": free}, "uptime_seconds": uptime_seconds(), "timestamp": now()}

@app.get("/api/v1/activity", tags=["audit"])
def activity(limit: int = Query(20, ge=1, le=100)) -> dict[str, object]:
    return {"items": repo.activities(limit), "total": len(repo.activities(limit))}

@app.get("/api/v1/websites", tags=["websites"])
def list_websites() -> dict[str, object]:
    items = repo.websites()
    return {"items": items, "total": len(items), "environment": os.getenv("ENVIRONMENT", "debian")}

@app.post("/api/v1/websites", status_code=status.HTTP_201_CREATED, tags=["websites"])
def create_website(payload: WebsiteCreate, request: Request) -> dict[str, object]:
    if any(item["domain"] == payload.domain or item["name"] == payload.name for item in repo.websites()):
        raise HTTPException(status_code=409, detail="Website name or domain already exists")
    item = repo.create_website({"id": str(uuid4()), **payload.model_dump(), "status": "Stopped", "created_at": now()})
    repo.audit("website.create", item["id"], "success", now())
    return item

@app.get("/api/v1/websites/{website_id}", tags=["websites"])
def get_website(website_id: str) -> dict[str, object]:
    item = repo.website(website_id)
    if not item:
        raise HTTPException(status_code=404, detail="Website not found")
    return item

@app.post("/api/v1/websites/{website_id}/status", tags=["websites"])
def set_website_status(website_id: str, payload: StatusChange) -> dict[str, object]:
    if not repo.website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")
    item = repo.update_status(website_id, payload.status)
    repo.audit(f"website.{payload.status.lower()}", website_id, "success", now())
    return item or {}

@app.delete("/api/v1/websites/{website_id}", tags=["websites"])
def delete_website(website_id: str) -> dict[str, bool]:
    if not repo.delete_website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")
    repo.audit("website.delete", website_id, "success", now())
    return {"deleted": True}

@app.get("/api/v1/services", tags=["services"])
def list_services() -> dict[str, object]:
    return {"items": [{"name": name, "status": service_state(name)} for name in SUPPORTED_SERVICES]}

@app.get("/api/v1/logs", tags=["logs"])
def logs(source: str = Query("rabby-host", pattern=r"^[a-z0-9_.-]+$"), lines: int = Query(100, ge=1, le=500)) -> dict[str, object]:
    allowed = {"rabby-host": LOG_ROOT / "app.log", "security": LOG_ROOT / "security.log", "tasks": LOG_ROOT / "tasks.log"}
    path = allowed.get(source)
    if path is None:
        raise HTTPException(status_code=400, detail="Unsupported log source")
    if not path.exists():
        return {"source": source, "lines": [], "limit": lines}
    return {"source": source, "lines": path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:], "limit": lines}
