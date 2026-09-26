"""Rabby Host API: validated control-plane routes with explicit system boundaries."""
from datetime import datetime, timezone
from pathlib import Path
import os
import platform
import shutil
import socket
import subprocess
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
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
origins = [item.strip() for item in os.getenv("RABBY_HOST_CORS_ORIGINS", "http://localhost:3000,http://localhost:8787").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "Authorization", "X-Rabby-Host-Token"])


def require_admin(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_rabby_host_token: str | None = Header(default=None, alias="X-Rabby-Host-Token"),
) -> None:
    expected = os.getenv("RABBY_HOST_ADMIN_TOKEN") or os.getenv("RABBY_HOST_API_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Authentication is not configured")

    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token and x_rabby_host_token:
        token = x_rabby_host_token.strip()

    if not token or token != expected:
        raise HTTPException(status_code=401, detail="Authentication required")


class WebsiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*$")
    domain: str = Field(min_length=3, max_length=253)
    type: WebsiteType
    runtime: str = Field(min_length=1, max_length=32)
    port: int = Field(default=80, ge=1, le=65535)
    ssl: bool = False
    config: dict[str, str] = Field(default_factory=dict)

    @field_validator("domain", "runtime")
    @classmethod
    def safe_text(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Control characters are not allowed")
        return value.strip().lower() if cls.__name__ == "WebsiteCreate" and value != "runtime" else value.strip()

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, value: str) -> str:
        labels = value.split(".")
        if not all(label and len(label) <= 63 and label[0].isalnum() and label[-1].isalnum() and all(char.isalnum() or char == "-" for char in label) for label in labels):
            raise ValueError("Enter a valid hostname")
        return value


class StatusChange(BaseModel):
    status: Literal["Running", "Stopped"]


class WebsiteUpdate(BaseModel):
    domain: str | None = Field(default=None, min_length=3, max_length=253)
    runtime: str | None = Field(default=None, max_length=32)
    port: int | None = Field(default=None, ge=1, le=65535)
    ssl: bool | None = None

    @field_validator("domain")
    @classmethod
    def valid_domain_update(cls, value: str | None) -> str | None:
        if value is None:
            return value
        labels = value.strip().lower().split(".")
        if not all(label and len(label) <= 63 and label[0].isalnum() and label[-1].isalnum() and all(char.isalnum() or char == "-" for char in label) for label in labels):
            raise ValueError("Enter a valid hostname")
        return ".".join(labels)


class ServiceAction(BaseModel):
    action: Literal["start", "stop", "restart", "reload"]


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


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@app.get("/api/v1/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rabby-host", "version": VERSION, "environment": os.getenv("ENVIRONMENT", "debian"), "timestamp": now()}


@app.get("/api/v1/system", tags=["system"], dependencies=[Depends(require_admin)])
def system_info() -> dict[str, object]:
    total, used, free = shutil.disk_usage("/")
    memory = memory_info()
    load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    return {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "cpu": platform.processor() or "unknown",
        "cpu_count": os.cpu_count() or 0,
        "uptime_seconds": uptime_seconds(),
        "disk_total": total,
        "disk_used": used,
        "disk_free": free,
        "memory": memory,
        "load_average": load,
        "timestamp": now(),
    }


@app.get("/api/v1/activity", tags=["audit"], dependencies=[Depends(require_admin)])
def activity(limit: int = Query(20, ge=1, le=100)) -> dict[str, object]:
    items = repo.activities(limit)
    return {"items": items, "total": len(items)}


@app.get("/api/v1/websites", tags=["websites"], dependencies=[Depends(require_admin)])
def list_websites() -> dict[str, object]:
    items = repo.websites()
    return {"items": items, "total": len(items), "environment": os.getenv("ENVIRONMENT", "debian")}


@app.post("/api/v1/websites", status_code=status.HTTP_201_CREATED, tags=["websites"], dependencies=[Depends(require_admin)])
def create_website(payload: WebsiteCreate, request: Request) -> dict[str, object]:
    if any(item["domain"] == payload.domain or item["name"] == payload.name for item in repo.websites()):
        raise HTTPException(status_code=409, detail="Website name or domain already exists")
    item = repo.create_website({"id": str(uuid4()), **payload.model_dump(), "status": "Stopped", "created_at": now()})
    repo.audit("website.create", item["id"], "success", now(), client_ip(request))
    return item


@app.get("/api/v1/websites/{website_id}", tags=["websites"], dependencies=[Depends(require_admin)])
def get_website(website_id: str) -> dict[str, object]:
    item = repo.website(website_id)
    if not item:
        raise HTTPException(status_code=404, detail="Website not found")
    return item


@app.patch("/api/v1/websites/{website_id}", tags=["websites"], dependencies=[Depends(require_admin)])
def update_website(website_id: str, payload: WebsiteUpdate, request: Request) -> dict[str, object]:
    current = repo.website(website_id)
    if not current:
        raise HTTPException(status_code=404, detail="Website not found")
    changes = payload.model_dump(exclude_none=True)
    if "domain" in changes and any(item["id"] != website_id and item["domain"] == changes["domain"] for item in repo.websites()):
        raise HTTPException(status_code=409, detail="Domain already exists")
    item = repo.update_website(website_id, changes)
    repo.audit("website.update", website_id, "success", now(), client_ip(request))
    return item or {}


@app.post("/api/v1/websites/{website_id}/status", tags=["websites"], dependencies=[Depends(require_admin)])
def set_website_status(website_id: str, payload: StatusChange, request: Request) -> dict[str, object]:
    if not repo.website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")
    item = repo.update_status(website_id, payload.status)
    repo.audit(f"website.{payload.status.lower()}", website_id, "success", now(), client_ip(request))
    return item or {}


@app.delete("/api/v1/websites/{website_id}", tags=["websites"], dependencies=[Depends(require_admin)])
def delete_website(website_id: str, request: Request) -> dict[str, bool]:
    if not repo.delete_website(website_id):
        raise HTTPException(status_code=404, detail="Website not found")
    repo.audit("website.delete", website_id, "success", now(), client_ip(request))
    return {"deleted": True}


@app.get("/api/v1/services", tags=["services"], dependencies=[Depends(require_admin)])
def list_services() -> dict[str, object]:
    return {"items": [{"name": name, "status": service_state(name)} for name in SUPPORTED_SERVICES]}


@app.post("/api/v1/services/{service_name}/actions", tags=["services"], dependencies=[Depends(require_admin)])
def service_action(service_name: str, payload: ServiceAction, request: Request) -> dict[str, str]:
    if service_name not in SUPPORTED_SERVICES:
        raise HTTPException(status_code=400, detail="Unsupported service")
    if service_name == "rabby-host" and payload.action in {"restart", "stop"}:
        raise HTTPException(status_code=400, detail="The control panel cannot be stopped or restarted through the API")
    try:
        result = subprocess.run(["/usr/bin/systemctl", payload.action, service_name], check=False, capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        raise HTTPException(status_code=503, detail="systemd is unavailable")
    if result.returncode != 0:
        raise HTTPException(status_code=502, detail="Service action failed")
    repo.audit(f"service.{payload.action}", service_name, "success", now(), client_ip(request))
    return {"name": service_name, "status": service_state(service_name)}


@app.get("/api/v1/logs", tags=["logs"], dependencies=[Depends(require_admin)])
def logs(source: str = Query("rabby-host", pattern=r"^[a-z0-9_.-]+$"), lines: int = Query(100, ge=1, le=500), contains: str | None = Query(None, max_length=100)) -> dict[str, object]:
    allowed = {"rabby-host": LOG_ROOT / "app.log", "security": LOG_ROOT / "security.log", "tasks": LOG_ROOT / "tasks.log"}
    path = allowed.get(source)
    if path is None:
        raise HTTPException(status_code=400, detail="Unsupported log source")
    if not path.exists():
        return {"source": source, "lines": [], "limit": lines}
    selected = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if contains:
        selected = [line for line in selected if contains.casefold() in line.casefold()]
    return {"source": source, "lines": selected[-lines:], "limit": lines}


@app.get("/api/v1/tasks/{task_id}", tags=["tasks"], dependencies=[Depends(require_admin)])
def get_task(task_id: str) -> dict[str, object]:
    item = repo.task(task_id)
    if not item:
        raise HTTPException(status_code=404, detail="Task not found")
    return item


__all__ = ["app"]
