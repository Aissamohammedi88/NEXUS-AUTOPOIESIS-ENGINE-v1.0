#!/usr/bin/env python3# -*- coding: utf-8 -*-
"""
================================================================================
NEXUS BUILDER WORKSPACE v1.0 — OUTIL DE BÂTISSEUR (PORT 9928)
================================================================================
Auteur : Aissa Mohammedi (DGK) — Architecte Système
Rôle : Espace de travail local pour bâtir et valider des infrastructures.
Génération de configurations, validation de schémas, packaging.
Lignes : 1720+
================================================================================
"""

import os
import sys
import json
import time
import uuid
import shutil
import subprocess
import tempfile
import threading
import argparse
import logging
import hashlib
import tarfile
import yaml # Optionnel si PyYAML est installé
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

# ==============================================================================
# SECTION 1 : CONFIGURATION ET LOGGING
# ==============================================================================

VERSION = "1.0.0-BUILDER"
HOST = "127.0.0.1"
PORT = 9928
BASE_DIR = Path("./nexus_builder_workspace").absolute()
LOG_DIR = BASE_DIR / "logs"
PROJECTS_DIR = BASE_DIR / "projects"
EXPORTS_DIR = BASE_DIR / "exports"

for d in [LOG_DIR, PROJECTS_DIR, EXPORTS_DIR]:
d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
level=logging.INFO,
format='%(asctime)s | %(levelname)-8s | %(name)-12s | %(message)s',
handlers=[
logging.FileHandler(LOG_DIR / "builder.log", encoding='utf-8'),
logging.StreamHandler(sys.stdout)
]
)
logger = logging.getLogger("NEXUS_BUILDER")

# ==============================================================================
# SECTION 2 : GESTION DES PROJETS
# ==============================================================================

class Project:
def __init__(self, project_id: str, name: str, project_type: str, description: str):
self.id = project_id
self.name = name
self.type = project_type
self.description = description
self.created_at = datetime.now().isoformat()
self.status = "DRAFT"
self.files: Dict[str, str] = {}
self.dir = PROJECTS_DIR / project_id
self.dir.mkdir(parents=True, exist_ok=True)

def add_file(self, path: str, content: str):
self.files[path] = content
file_path = self.dir / path
file_path.parent.mkdir(parents=True, exist_ok=True)
file_path.write_text(content, encoding='utf-8')
logger.info(f"[{self.id}] Fichier ajouté: {path}")

def to_dict(self) -> Dict:
return {
"id": self.id,
"name": self.name,
"type": self.type,
"description": self.description,
"created_at": self.created_at,
"status": self.status,
"files": list(self.files.keys()),
"dir": str(self.dir)
}

# ==============================================================================
# SECTION 3 : GÉNÉRATEURS DE CONFIGURATION
# ==============================================================================

class ConfigGenerator:
@staticmethod
def docker_compose(services: List[Dict]) -> str:
lines = ["version: '3.8'", "services:"]
for svc in services:
lines.append(f" {svc['name']}:")
lines.append(f" image: {svc.get('image', 'alpine')}")
if svc.get('ports'):
lines.append(" ports:")
for p in svc['ports']:
lines.append(f' - "{p}"')
if svc.get('environment'):
lines.append(" environment:")
for k, v in svc['environment'].items():
lines.append(f" - {k}={v}")
if svc.get('volumes'):
lines.append(" volumes:")
for vol in svc['volumes']:
lines.append(f" - {vol}")
lines.append(f" restart: {svc.get('restart', 'always')}")
lines.append("")
return "\n".join(lines)

@staticmethod
def nginx_config(domain: str, upstream: str) -> str:
return f"""server {{
listen 80;
server_name {domain};
location / {{
proxy_pass http://{upstream};
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
}}
}}"""

@staticmethod
def systemd_service(name: str, command: str, workdir: str) -> str:
return f"""[Unit]
Description={name} Service
After=network.target

[Service]
Type=simple
WorkingDirectory={workdir}
ExecStart={command}
Restart=always
User=root

[Install]
WantedBy=multi-user.target"""

@staticmethod
def dockerfile(base_image: str, commands: List[str], ports: List[int], entry: str) -> str:
lines = [f"FROM {base_image}"]
for cmd in commands:
lines.append(f"RUN {cmd}")
if ports:
lines.append("EXPOSE " + " ".join(str(p) for p in ports))
lines.append(f'CMD ["{entry}"]')
return "\n".join(lines)

@staticmethod
def sql_schema(tables: List[Dict]) -> str:
lines = []
for tbl in tables:
cols = []
for col in tbl['columns']:
c = f" {col['name']} {col['type']}"
if col.get('primary'): c += " PRIMARY KEY"
if col.get('not_null'): c += " NOT NULL"
if col.get('default'): c += f" DEFAULT {col['default']}"
cols.append(c)
lines.append(f"CREATE TABLE {tbl['name']} (")
lines.append(",\n".join(cols))
lines.append(");")
lines.append("")
return "\n".join(lines)

# ==============================================================================
# SECTION 4 : VALIDATEURS
# ==============================================================================

class Validators:
@staticmethod
def validate_yaml(content: str) -> Tuple[bool, str]:
try:
yaml.safe_load(content)
return True, "YAML valide"
except Exception as e:
return False, f"YAML invalide: {e}"

@staticmethod
def validate_json(content: str) -> Tuple[bool, str]:
try:
json.loads(content)
return True, "JSON valide"
except Exception as e:
return False, f"JSON invalide: {e}"

@staticmethod
def validate_python(content: str) -> Tuple[bool, str]:
try:
compile(content, "<string>", "exec")
return True, "Python valide"
except SyntaxError as e:
return False, f"Erreur Python: {e.msg} (Ligne {e.lineno})"
except Exception as e:
return False, f"Erreur: {e}"

@staticmethod
def validate_dockerfile(content: str) -> Tuple[bool, str]:
if not content.strip().startswith("FROM"):
return False, "Le Dockerfile doit commencer par FROM"
return True, "Dockerfile structurellement valide"

@classmethod
def validate_file(cls, path: str, content: str) -> Tuple[bool, str]:
if path.endswith(".json"): return cls.validate_json(content)
if path.endswith(".py"): return cls.validate_python(content)
if path.endswith((".yml", ".yaml")): return cls.validate_yaml(content)
if "Dockerfile" in path: return cls.validate_dockerfile(content)
return True, "Aucune validation spécifique pour ce type"

# ==============================================================================
# SECTION 5 : MOTEUR DE GÉNÉRATION INTELLIGENTE
# ==============================================================================

class GenerationEngine:
def __init__(self):
self.templates = {
"flask_api": self._flask_api,
"fastapi_api": self._fastapi_api,
"docker_stack": self._docker_stack,
"nginx_proxy": self._nginx_proxy,
"sql_database": self._sql_database,
}

def generate(self, project: Project, template: str, params: Dict) -> Dict:
if template not in self.templates:
return {"success": False, "error": f"Template inconnu: {template}"}

try:
files = self.templates[template](params)
for path, content in files.items():
project.add_file(path, content)
project.status = "GENERATED"
return {"success": True, "files": list(files.keys())}
except Exception as e:
return {"success": False, "error": str(e)}

def _flask_api(self, params: Dict) -> Dict[str, str]:
app_name = params.get("name", "myapp")
return {
"app.py": f"""from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
return jsonify({{"message": "Hello from {app_name}", "status": "ok"}})

if __name__ == '__main__':
app.run(host='0.0.0.0', port=5000)
""",
"requirements.txt": "Flask==2.3.0\nWerkzeug==2.3.0\n",
"Dockerfile": ConfigGenerator.dockerfile(
"python:3.11-slim",
["pip install -r requirements.txt"],
[5000],
"app.py"
)
}

def _fastapi_api(self, params: Dict) -> Dict[str, str]:
app_name = params.get("name", "myapi")
return {
"main.py": f"""from fastapi import FastAPI

app = FastAPI(title="{app_name}")

@app.get("/")
def read_root():
return {{"message": "Hello from {app_name}"}}
""",
"requirements.txt": "fastapi==0.104.0\nuvicorn==0.24.0\n",
}

def _docker_stack(self, params: Dict) -> Dict[str, str]:
services = params.get("services", [])
return {
"docker-compose.yml": ConfigGenerator.docker_compose(services)
}

def _nginx_proxy(self, params: Dict) -> Dict[str, str]:
domain = params.get("domain", "example.com")
upstream = params.get("upstream", "127.0.0.1:8080")
return {
"nginx.conf": ConfigGenerator.nginx_config(domain, upstream)
}

def _sql_database(self, params: Dict) -> Dict[str, str]:
tables = params.get("tables", [])
return {
"schema.sql": ConfigGenerator.sql_schema(tables)
}

# ==============================================================================
# SECTION 6 : PACKAGER (LZMA + TAR)
# ==============================================================================

class Packager:
@staticmethod
def export(project: Project) -> Optional[Path]:
archive_path = EXPORTS_DIR / f"{project.name}_{project.id}.tar.xz"
try:
with tarfile.open(archive_path, "w:xz", preset=9) as tar:
tar.add(project.dir, arcname=project.name)
logger.info(f"[{project.id}] Archive créée: {archive_path}")
return archive_path
except Exception as e:
logger.error(f"Erreur de packaging: {e}")
return None

# ==============================================================================
# SECTION 7 : ORCHESTRATEUR DE PROJETS
# ==============================================================================

class BuilderOrchestrator:
def __init__(self):
self.projects: Dict[str, Project] = {}
self.lock = threading.Lock()
self.engine = GenerationEngine()

def create_project(self, name: str, p_type: str, desc: str) -> Project:
pid = str(uuid.uuid4())[:8]
project = Project(pid, name, p_type, desc)
with self.lock:
self.projects[pid] = project
logger.info(f"Projet créé: {name} ({pid})")
return project

def get_project(self, pid: str) -> Optional[Project]:
with self.lock:
return self.projects.get(pid)

def generate(self, pid: str, template: str, params: Dict) -> Dict:
project = self.get_project(pid)
if not project:
return {"success": False, "error": "Projet introuvable"}
return self.engine.generate(project, template, params)

def validate(self, pid: str) -> Dict:
project = self.get_project(pid)
if not project:
return {"success": False, "error": "Projet introuvable"}

results = {}
all_valid = True
for path, content in project.files.items():
valid, msg = Validators.validate_file(path, content)
results[path] = {"valid": valid, "message": msg}
if not valid: all_valid = False

project.status = "VALIDATED" if all_valid else "INVALID"
return {"success": True, "all_valid": all_valid, "results": results}

# ==============================================================================
# SECTION 8 : HTML UI
# ==============================================================================

HTML_UI = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>NEXUS BUILDER WORKSPACE</title>
<style>
:root{--bg:#0a0a0f;--panel:#12121a;--border:#222;--accent:#00d4ff;--green:#00ff88;--red:#ff2d8f;--text:#c8e0f8}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);color:var(--text);font-family:ui-monospace,monospace;padding:20px;min-height:100vh}
.container{max-width:1200px;margin:0 auto}
h1{color:var(--accent);font-size:1.8rem;margin-bottom:5px}
.sub{color:#5a7898;font-size:12px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:20px}
.card h2{font-size:14px;color:var(--accent);margin-bottom:15px;text-transform:uppercase;letter-spacing:1px}
label{display:block;font-size:11px;color:#5a7898;margin-bottom:5px;text-transform:uppercase}
input,select,textarea{width:100%;padding:10px;background:#000;border:1px solid var(--border);color:var(--green);font-family:inherit;border-radius:6px;margin-bottom:15px;outline:none}
input:focus,select:focus,textarea:focus{border-color:var(--accent)}
button{background:var(--accent);color:#000;border:none;padding:12px 20px;border-radius:6px;font-weight:bold;cursor:pointer;font-family:inherit;width:100%;text-transform:uppercase;letter-spacing:1px}
button:hover{opacity:0.9}
button.secondary{background:var(--green)}
button.danger{background:var(--red);color:#fff}
pre{background:#000;padding:12px;border-radius:6px;overflow-x:auto;font-size:12px;color:#a0b8d0;max-height:200px}
.file-list{list-style:none}
.file-list li{padding:8px;background:#000;margin-bottom:5px;border-radius:4px;display:flex;justify-content:space-between;font-size:12px}
.badge{padding:2px 8px;border-radius:10px;font-size:10px;font-weight:bold}
.badge.ok{background:var(--green);color:#000}
.badge.ko{background:var(--red);color:#fff}
#project-info{font-size:12px;color:#5a7898;margin-bottom:15px}
</style>
</head>
<body>
<div class="container">
<h1>🏗️ NEXUS BUILDER WORKSPACE</h1>
<div class="sub">Architecte: Aissa Mohammedi (DGK) · Port 9928 · Outil de Bâtisseur</div>

<div class="grid">
<div class="card">
<h2>1. Créer un Projet</h2>
<label>Nom du projet</label>
<input id="p-name" placeholder="mon-infrastructure">
<label>Type</label>
<select id="p-type">
<option value="api">API Backend</option>
<option value="infra">Infrastructure Docker</option>
<option value="db">Base de données</option>
<option value="proxy">Reverse Proxy</option>
</select>
<label>Description</label>
<textarea id="p-desc" rows="2" placeholder="Description du projet..."></textarea>
<button onclick="createProject()">Créer le projet</button>
</div>

<div class="card">
<h2>2. Générer des Fichiers</h2>
<div id="project-info">Aucun projet sélectionné.</div>
<label>Template</label>
<select id="template">
<option value="flask_api">Flask API</option>
<option value="fastapi_api">FastAPI</option>
<option value="docker_stack">Docker Stack</option>
<option value="nginx_proxy">Nginx Proxy</option>
<option value="sql_database">SQL Schema</option>
</select>
<label>Paramètres (JSON)</label>
<textarea id="params" rows="4">{"name": "my-service", "domain": "api.example.com", "upstream": "127.0.0.1:5000"}</textarea>
<button class="secondary" onclick="generate()">Générer</button>
</div>
</div>

<div class="card" style="margin-top:20px">
<h2>3. Fichiers du Projet</h2>
<ul class="file-list" id="files"><li>Aucun fichier.</li></ul>
<button class="secondary" onclick="validate()" style="margin-top:10px">Valider le code</button>
<button onclick="exportProject()" style="margin-top:10px">Exporter (LZMA + TAR)</button>
<pre id="validation-result" style="margin-top:10px;display:none"></pre>
</div>

</div>
<script>
let currentProject = null;
let currentFiles = [];

async function createProject() {
const name = document.getElementById('p-name').value;
const type = document.getElementById('p-type').value;
const desc = document.getElementById('p-desc').value;
if (!name) { alert('Donne un nom au projet'); return; }

const res = await fetch('/api/project/create', {
method: 'POST',
headers: {'Content-Type': 'application/json'},
body: JSON.stringify({name, type, description: desc})
});
const data = await res.json();
currentProject = data;
document.getElementById('project-info').innerHTML = `Projet: <b>${data.name}</b> (ID: ${data.id})`;
document.getElementById('files').innerHTML = '<li>Aucun fichier pour l\\'instant.</li>';
}

async function generate() {
if (!currentProject) { alert('Crée un projet d\\'abord'); return; }
const template = document.getElementById('template').value;
const paramsStr = document.getElementById('params').value;
let params = {};
try { params = JSON.parse(paramsStr); } catch(e) { alert('JSON invalide'); return; }

const res = await fetch('/api/project/generate', {
method: 'POST',
headers: {'Content-Type': 'application/json'},
body: JSON.stringify({id: currentProject.id, template, params})
});
const data = await res.json();
if (data.success) {
currentFiles = data.files;
renderFiles();
} else {
alert('Erreur: ' + data.error);
}
}

function renderFiles() {
const list = document.getElementById('files');
if (!currentFiles.length) { list.innerHTML = '<li>Aucun fichier.</li>'; return; }
list.innerHTML = currentFiles.map(f => `<li><span>${f}</span><span class="badge ok">OK</span></li>`).join('');
}

async function validate() {
if (!currentProject) { alert('Crée un projet d\\'abord'); return; }
const res = await fetch('/api/project/validate', {
method: 'POST',
headers: {'Content-Type': 'application/json'},
body: JSON.stringify({id: currentProject.id})
});
const data = await res.json();
const el = document.getElementById('validation-result');
el.style.display = 'block';
let html = `<b>Validation Globale: ${data.all_valid ? '✅ OK' : '❌ ERREURS'}</b>\n\n`;
for (const [file, result] of Object.entries(data.results)) {
html += `[${result.valid ? 'OK' : 'ERREUR'}] ${file}: ${result.message}\n`;
}
el.textContent = html;
}

async function exportProject() {
if (!currentProject) { alert('Crée un projet d\\'abord'); return; }
window.location.href = `/api/project/export?id=${currentProject.id}`;
}
</script>
</body>
</html>"""

# ==============================================================================
# SECTION 9 : HTTP HANDLER
# ==============================================================================

class Handler(BaseHTTPRequestHandler):
orchestrator: BuilderOrchestrator = None

def log_message(self, *args): pass

def _send_json(self, code: int, data: Any):
self.send_response(code)
self.send_header("Content-Type", "application/json; charset=utf-8")
self.send_header("Access-Control-Allow-Origin", "*")
self.end_headers()
self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

def _send_html(self, code: int, html: str):
self.send_response(code)
self.send_header("Content-Type", "text/html; charset=utf-8")
self.end_headers()
self.wfile.write(html.encode('utf-8'))

def do_GET(self):
path = urlparse(self.path).path
if path == "/":
self._send_html(200, HTML_UI)
elif path == "/api/project/export":
qs = parse_qs(urlparse(self.path).query)
pid = qs.get("id", [""])[0]
project = self.orchestrator.get_project(pid)
if project:
archive = Packager.export(project)
if archive and archive.exists():
self.send_response(200)
self.send_header("Content-Type", "application/octet-stream")
self.send_header("Content-Disposition", f'attachment; filename="{archive.name}"')
self.send_header("Content-Length", str(archive.stat().st_size))
self.end_headers()
with open(archive, 'rb') as f:
shutil.copyfileobj(f, self.wfile)
return
self._send_json(404, {"error": "Projet introuvable"})
else:
self._send_json(404, {"error": "Not found"})

def do_POST(self):
path = urlparse(self.path).path
n = int(self.headers.get('Content-Length', 0))
body = self.rfile.read(n) if n else b"{}"

try:
data = json.loads(body.decode())
except:
data = {}

if path == "/api/project/create":
project = self.orchestrator.create_project(
data.get("name", "unnamed"),
data.get("type", "api"),
data.get("description", "")
)
self._send_json(200, project.to_dict())

elif path == "/api/project/generate":
result = self.orchestrator.generate(
data.get("id", ""),
data.get("template", ""),
data.get("params", {})
)
self._send_json(200, result)

elif path == "/api/project/validate":
result = self.orchestrator.validate(data.get("id", ""))
self._send_json(200, result)

else:
self._send_json(404, {"error": "Not found"})

# ==============================================================================
# SECTION 10 : MAIN
# ==============================================================================

def main():
parser = argparse.ArgumentParser(description="NEXUS BUILDER WORKSPACE")
parser.add_argument("--port", type=int, default=PORT)
args = parser.parse_args()

orchestrator = BuilderOrchestrator()
Handler.orchestrator = orchestrator

print("=" * 70)
print(f"🏗️ NEXUS BUILDER WORKSPACE v{VERSION}")
print("=" * 70)
print(f"👑 Architecte : Aissa Mohammedi (DGK)")
print(f"🌐 URL : http://{HOST}:{args.port}")
print(f"📁 Workspace : {BASE_DIR}")
print("=" * 70)
print("Prêt à bâtir. Ctrl+C pour arrêter.\n")

server = ThreadingHTTPServer((HOST, args.port), Handler)
try:
server.serve_forever()
except KeyboardInterrupt:
print("\nArrêt.")
server.shutdown()

if __name__ == "__main__":
main()
