from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS websites (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL CHECK(type IN ('WordPress','PHP','Node.js','Static')),
  status TEXT NOT NULL DEFAULT 'Stopped',
  runtime TEXT NOT NULL,
  port INTEGER NOT NULL,
  ssl INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  config_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  target TEXT NOT NULL,
  result TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_websites_created_at ON websites(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_logs(created_at);
"""

class Repository:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def websites(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM websites ORDER BY created_at DESC").fetchall()
        return [self._website(row) for row in rows]

    def website(self, website_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM websites WHERE id = ?", (website_id,)).fetchone()
        return self._website(row) if row else None

    def create_website(self, values: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO websites (id,name,domain,type,status,runtime,port,ssl,created_at,config_json) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (values["id"], values["name"], values["domain"], values["type"], values["status"], values["runtime"], values["port"], int(values["ssl"]), values["created_at"], json.dumps(values.get("config", {}))),
            )
        return self.website(values["id"])  # type: ignore[return-value]

    def update_status(self, website_id: str, status: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("UPDATE websites SET status = ? WHERE id = ?", (status, website_id))
        return self.website(website_id)

    def delete_website(self, website_id: str) -> bool:
        with self.connect() as connection:
            result = connection.execute("DELETE FROM websites WHERE id = ?", (website_id,))
        return result.rowcount == 1

    def audit(self, action: str, target: str, result: str, created_at: str) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO audit_logs (action,target,result,created_at) VALUES (?,?,?,?)", (action, target, result, created_at))

    def activities(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT action,target,result,created_at FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _website(row: sqlite3.Row) -> dict[str, Any]:
        return {"id": row["id"], "name": row["name"], "domain": row["domain"], "type": row["type"], "status": row["status"], "runtime": row["runtime"], "port": row["port"], "ssl": bool(row["ssl"]), "created_at": row["created_at"], "config": json.loads(row["config_json"])}


def repository(data_dir: Path) -> Repository:
    return Repository(data_dir / "rabby-host.sqlite3")
