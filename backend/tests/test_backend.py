import os
import tempfile
from pathlib import Path

# Must set env vars before backend imports
_tmp_data = tempfile.mkdtemp()
_tmp_log = tempfile.mkdtemp()
_tmp_sites = tempfile.mkdtemp()

os.environ["RABBY_HOST_DATA_DIR"] = _tmp_data
os.environ["RABBY_HOST_LOG_DIR"] = _tmp_log
os.environ["RABBY_HOST_SITES_DIR"] = _tmp_sites

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.security import hash_password, verify_password
from backend.app.mariadb import MariaDBManager
from backend.app.files import FileManager
from backend.app.backups import BackupEngine
from backend.app.wordpress import WordPressManager

client = TestClient(app)


def test_health_check():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["service"] == "rabby-host"


def test_system_info():
    res = client.get("/api/v1/system")
    assert res.status_code == 200
    body = res.json()
    assert "cpu_count" in body
    assert "memory" in body
    assert "disk" in body


def test_password_hashing():
    pwd = "SecretPassword123!"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("WrongPassword", hashed) is False


def test_website_lifecycle():
    create_payload = {
        "name": "test-site",
        "domain": "testsite.local",
        "type": "Static",
        "runtime": "Nginx",
        "port": 80,
        "ssl": False,
    }
    res = client.post("/api/v1/websites", json=create_payload)
    assert res.status_code == 201
    site = res.json()
    site_id = site["id"]
    assert site["domain"] == "testsite.local"

    list_res = client.get("/api/v1/websites")
    assert list_res.status_code == 200
    assert any(s["id"] == site_id for s in list_res.json()["items"])

    status_res = client.post(f"/api/v1/websites/{site_id}/status", json={"status": "Stopped"})
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "Stopped"

    del_res = client.delete(f"/api/v1/websites/{site_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted"] is True


def test_file_manager_sandboxing():
    sites_root = Path(_tmp_sites)
    fm = FileManager(sites_root)

    write_res = fm.write_file("site-a/index.html", "<h1>Hello</h1>")
    assert write_res["path"] == "/site-a/index.html"
    assert (sites_root / "site-a/index.html").exists()

    with pytest.raises(PermissionError):
        fm.resolve_path("../../etc/passwd")


def test_backup_and_restore():
    data_root = Path(_tmp_data)
    sites_root = Path(_tmp_sites)
    be = BackupEngine(data_root / "backups", sites_root)

    domain = "backup-test.local"
    bck = be.create_website_backup("id-bck", domain)
    assert bck["status"] == "completed"
    assert (data_root / "backups" / bck["filename"]).exists()

    restored = be.restore_website_backup(bck["filename"], domain)
    assert restored is True

    with pytest.raises(PermissionError):
        be.restore_website_backup("../../etc/shadow", domain)


def test_wordpress_installer_generation():
    sites_root = Path(_tmp_sites)
    wp = WordPressManager(sites_root)
    res = wp.install_wordpress("wptest.local")
    assert res["status"] == "installed"
    wp_config = sites_root / "wptest.local" / "wp-config.php"
    assert wp_config.exists()
    assert "DB_NAME" in wp_config.read_text()


def test_mariadb_sanitization():
    db = MariaDBManager()
    with pytest.raises(ValueError):
        db.sanitize_identifier("DROP TABLE users; --")
