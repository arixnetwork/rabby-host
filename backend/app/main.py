"""Rabby Host FastAPI entry point.

The production service keeps privileged operations behind explicit service methods;
there is intentionally no arbitrary shell endpoint.
"""
from datetime import datetime, timezone
from pathlib import Path
import platform, shutil, socket, time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_ROOT = Path('/var/lib/rabby-host')
app = FastAPI(title='Rabby Host API', version='1.0.0', docs_url='/api/docs', openapi_url='/api/openapi.json')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:8787'], allow_credentials=True, allow_methods=['GET','POST','DELETE'], allow_headers=['*'])

@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'service': 'rabby-host', 'version': app.version}

@app.get('/api/v1/system')
def system_info():
    total, used, free = shutil.disk_usage('/')
    return {'hostname': socket.gethostname(), 'os': platform.platform(), 'kernel': platform.release(), 'architecture': platform.machine(), 'cpu': platform.processor() or 'unknown', 'disk': {'total': total, 'used': used, 'free': free}, 'uptime_seconds': int(time.time() - APP_ROOT.stat().st_ctime) if APP_ROOT.exists() else 0, 'timestamp': datetime.now(timezone.utc).isoformat()}

@app.get('/api/v1/websites')
def list_websites():
    return {'items': [], 'total': 0}

@app.get('/api/v1/services')
def list_services():
    return {'items': [{'name': 'nginx', 'status': 'unknown'}, {'name': 'mariadb', 'status': 'unknown'}, {'name': 'rabby-host', 'status': 'running'}]}

@app.get('/api/v1/logs')
def logs(source: str = 'rabby-host', lines: int = 100):
    safe_lines = max(1, min(lines, 500))
    return {'source': source, 'lines': [], 'limit': safe_lines}
