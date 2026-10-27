#!/usr/bin/env python3# -*- coding: utf-8 -*-
"""
================================================================================
NEXUS AUTOPOIESIS ENGINE v1.0 — USINE LOGICIELLE AUTONOME
================================================================================
Auteur : Aissa Mohammedi (DGK) - Meta Suprême Système
Port : 9930
Rôle : Générateur de SaaS multi-langages (Python, Rust, COBOL, JS).
Exécute de vrais compilateurs (rustc, cobc), capture les benchmarks,
et affiche l'arborescence et la console en temps réel.
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
import textwrap
import threading
import urllib.parse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ==============================================================================
# SECTION 1 : CONFIGURATION
# ==============================================================================

VERSION = "1.0.0-AUTOPOIESIS"
HOST = "0.0.0.0"
PORT = 9930
BASE_DIR = Path("./nexus_autopoiesis_workspace").absolute()
BASE_DIR.mkdir(exist_ok=True, parents=True)

class Logger:
@staticmethod
def log(level: str, msg: str):
t = datetime.now().strftime("%H:%M:%S")
colors = {"INFO": "\033[96m", "OK": "\033[92m", "ERR": "\033[91m", "WARN": "\033[93m", "EXEC": "\033[95m"}
c = colors.get(level, "\033[0m")
print(f"[{t}] {c}[{level}]\033[0m {msg}")

# ==============================================================================
# SECTION 2 : MODÈLES DE DONNÉES
# ==============================================================================

@dataclass
class FileNode:
path: str
content: str
language: str

@dataclass
class GenerationLog:
timestamp: str
level: str
message: str

@dataclass
class ProjectSpec:
id: str
name: str
prompt: str
stack: Dict[str, str]
files: List[FileNode] = field(default_factory=list)
logs: List[GenerationLog] = field(default_factory=list)
status: str = "PENDING"
build_output: str = ""
benchmark_result: str = ""
created_at: str = field(default_factory=lambda: datetime.now().isoformat())

def add_log(self, level: str, msg: str):
log_entry = GenerationLog(datetime.now().strftime("%H:%M:%S"), level, msg)
self.logs.append(log_entry)
Logger.log(level, f"[{self.id[:6]}] {msg}")

def to_dict(self):
return {
"id": self.id,
"name": self.name,
"status": self.status,
"stack": self.stack,
"files_count": len(self.files),
"tree": self.get_tree(),
"logs": [{"time": l.timestamp, "level": l.level, "msg": l.message} for l in self.logs],
"build_output": self.build_output,
"benchmark": self.benchmark_result
}

def get_tree(self) -> Dict:
tree = {}
for f in self.files:
parts = f.path.split("/")
current = tree
for part in parts[:-1]:
current = current.setdefault(part, {})
current[parts[-1]] = f.language
return tree

# ==============================================================================
# SECTION 3 : TEMPLATES DE CODE (PRODUCTION-GRADE)
# ==============================================================================

class CodeForge:
"""Banque de templates incluant Rust, COBOL, Python et JS."""

# --- RUST ---
RUST_MAIN = textwrap.dedent('''\
use std::io::{self, Write};

/// NEXUS Autopoiesis Engine - Rust Core
struct NexusCore {
version: String,
}

impl NexusCore {
fn new() -> Self {
NexusCore { version: String::from("1.0.0") }
}

fn run_benchmark(&self) -> f64 {
let start = std::time::Instant::now();
let mut sum: u64 = 0;
for i in 0..1_000_000 {
sum = sum.wrapping_add(i);
}
let duration = start.elapsed();
println!("Rust Benchmark: Sum = {}", sum);
duration.as_secs_f64() * 1000.0 // ms
}
}

fn main() {
println!("[RUST] Initializing NEXUS Core...");
let core = NexusCore::new();
let ms = core.run_benchmark();
println!("[RUST] Execution time: {:.2} ms", ms);
}
''')

RUST_CARGO = textwrap.dedent('''\
[package]
name = "nexus_rust_core"
version = "1.0.0"
edition = "2021"
[dependencies]
''')

# --- COBOL ---
COBOL_MAIN = textwrap.dedent('''\
IDENTIFICATION DIVISION.
PROGRAM-ID. NEXUS-COBOL.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-COUNTER PIC 9(6) VALUE 0.
01 WS-RESULT PIC 9(9) VALUE 0.
01 WS-DISPLAY PIC Z(8)9.
PROCEDURE DIVISION.
DISPLAY "[COBOL] Initializing NEXUS Core...".
PERFORM VARYING WS-COUNTER FROM 1 BY 1
UNTIL WS-COUNTER > 100000
ADD WS-COUNTER TO WS-RESULT
END-PERFORM.
MOVE WS-RESULT TO WS-DISPLAY.
DISPLAY "[COBOL] Benchmark Result: " WS-DISPLAY.
STOP RUN.
''')

# --- PYTHON ---
PYTHON_MAIN = textwrap.dedent('''\
import time

class NexusCore:
def __init__(self):
self.version = "1.0.0"

def run_benchmark(self):
start = time.perf_counter()
total = sum(range(1_000_000))
end = time.perf_counter()
print(f"Python Benchmark: Sum = {total}")
return (end - start) * 1000

if __name__ == "__main__":
print("[PYTHON] Initializing NEXUS Core...")
core = NexusCore()
ms = core.run_benchmark()
print(f"[PYTHON] Execution time: {ms:.2f} ms")
''')

# --- FRONTEND (React/Vite) ---
REACT_APP = textwrap.dedent('''\
import React, { useState, useEffect } from 'react';

export default function App() {
const [status, setStatus] = useState('Initializing...');

useEffect(() => {
setTimeout(() => setStatus('Online'), 1000);
}, []);

return (
<div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
<div className="text-center">
<h1 className="text-4xl font-bold text-blue-400 mb-4">NEXUS SaaS</h1>
<p className="text-xl">System Status: <span className="text-green-400">{status}</span></p>
</div>
</div>
);
}
''')

# --- INFRA ---
DOCKER_COMPOSE = textwrap.dedent('''\
version: '3.8'
services:
backend:
build: ./backend
ports:
- "8000:8000"
db:
image: postgres:15
environment:
POSTGRES_PASSWORD: nexus
''')

README = textwrap.dedent('''\
# {name}
Généré par NEXUS AUTOPOIESIS ENGINE.

## Stack
{stack}

## Structure
{tree}
''')

# ==============================================================================
# SECTION 4 : MOTEUR DE COMPILATION ET BENCHMARK
# ==============================================================================

class CompilerAgent:
"""Vérifie si les compilateurs sont présents et lance les tests réels."""

@staticmethod
def check_tool(tool: str) -> bool:
return shutil.which(tool) is not None

@staticmethod
def compile_rust(project_dir: Path) -> str:
if not CompilerAgent.check_tool("rustc"):
return "⚠️ rustc introuvable. Installe Rust (curl https://sh.rustup.rs)."

main_rs = project_dir / "backend_rust" / "src" / "main.rs"
if not main_rs.exists(): return "Erreur : main.rs manquant."

try:
result = subprocess.run(
["rustc", str(main_rs), "-o", str(project_dir / "backend_rust" / "nexus_rust")],
capture_output=True, text=True, timeout=30
)
if result.returncode == 0:
return "✅ Compilation Rust réussie."
else:
return f"❌ Erreur Rust : {result.stderr}"
except Exception as e:
return f"❌ Exception Rust : {str(e)}"

@staticmethod
def compile_cobol(project_dir: Path) -> str:
if not CompilerAgent.check_tool("cobc"):
return "⚠️ cobc introuvable. Installe GnuCOBOL (sudo apt install gnucobol)."

main_cob = project_dir / "legacy_cobol" / "main.cob"
if not main_cob.exists(): return "Erreur : main.cob manquant."

try:
result = subprocess.run(
["cobc", "-x", "-o", str(project_dir / "legacy_cobol" / "nexus_cobol"), str(main_cob)],
capture_output=True, text=True, timeout=30
)
if result.returncode == 0:
return "✅ Compilation COBOL réussie."
else:
return f"❌ Erreur COBOL : {result.stderr}"
except Exception as e:
return f"❌ Exception COBOL : {str(e)}"

@staticmethod
def run_benchmark(project_dir: Path, lang: str) -> str:
bin_path = None
if lang == "rust": bin_path = project_dir / "backend_rust" / "nexus_rust"
elif lang == "cobol": bin_path = project_dir / "legacy_cobol" / "nexus_cobol"

if bin_path and bin_path.exists():
try:
result = subprocess.run([str(bin_path)], capture_output=True, text=True, timeout=10)
return f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}"
except Exception as e:
return f"Erreur d'exécution : {str(e)}"
return "Binaire non trouvé."

# ==============================================================================
# SECTION 5 : L'ORCHESTRATEUR (AUTOPOIESIS)
# ==============================================================================

class AutopoiesisEngine:
def __init__(self):
self.forge = CodeForge()
self.projects: Dict[str, ProjectSpec] = {}
self.lock = threading.Lock()

def create_and_run(self, name: str, prompt: str, stack: Dict[str, str]) -> ProjectSpec:
pid = str(uuid.uuid4())[:8]
spec = ProjectSpec(id=pid, name=name, prompt=prompt, stack=stack)
with self.lock:
self.projects[pid] = spec

# Lancement en arrière-plan pour ne pas bloquer le serveur
threading.Thread(target=self._execute_forge, args=(spec,), daemon=True).start()
return spec

def _execute_forge(self, spec: ProjectSpec):
try:
spec.status = "GENERATING"
spec.add_log("INFO", "Démarrage de la Forge...")
proj_dir = BASE_DIR / spec.id
proj_dir.mkdir(exist_ok=True, parents=True)

# 1. Génération Backend
if spec.stack.get("backend") == "rust":
spec.add_log("INFO", "Génération Backend (Rust)...")
spec.files.append(FileNode("backend_rust/src/main.rs", self.forge.RUST_MAIN, "rust"))
spec.files.append(FileNode("backend_rust/Cargo.toml", self.forge.RUST_CARGO, "toml"))
elif spec.stack.get("backend") == "cobol":
spec.add_log("INFO", "Génération Backend (COBOL)...")
spec.files.append(FileNode("legacy_cobol/main.cob", self.forge.COBOL_MAIN, "cobol"))
else:
spec.add_log("INFO", "Génération Backend (Python)...")
spec.files.append(FileNode("backend_python/main.py", self.forge.PYTHON_MAIN, "python"))

# 2. Génération Frontend
if spec.stack.get("frontend") == "react":
spec.add_log("INFO", "Génération Frontend (React)...")
spec.files.append(FileNode("frontend/src/App.jsx", self.forge.REACT_APP, "javascript"))

# 3. Infra
spec.add_log("INFO", "Génération Infrastructure...")
spec.files.append(FileNode("docker-compose.yml", self.forge.DOCKER_COMPOSE, "yaml"))
spec.files.append(FileNode("README.md", self.forge.README.format(
name=spec.name, stack=json.dumps(spec.stack), tree=json.dumps(spec.get_tree(), indent=2)
), "markdown"))

# 4. Écriture sur disque
spec.add_log("INFO", "Écriture des fichiers sur le disque...")
for f in spec.files:
fpath = proj_dir / f.path
fpath.parent.mkdir(parents=True, exist_ok=True)
fpath.write_text(f.content)

# 5. Compilation et Benchmark
spec.status = "COMPILING"
spec.add_log("EXEC", "Lancement des compilateurs et benchmarks...")
bench_results = []

if spec.stack.get("backend") == "rust":
res = CompilerAgent.compile_rust(proj_dir)
spec.add_log("EXEC", res)
bench_results.append(CompilerAgent.run_benchmark(proj_dir, "rust"))
elif spec.stack.get("backend") == "cobol":
res = CompilerAgent.compile_cobol(proj_dir)
spec.add_log("EXEC", res)
bench_results.append(CompilerAgent.run_benchmark(proj_dir, "cobol"))

spec.benchmark_result = "\n\n".join(bench_results)

spec.status = "COMPLETED"
spec.add_log("OK", f"Projet {spec.name} généré avec succès.")

except Exception as e:
spec.status = "FAILED"
spec.add_log("ERR", f"Erreur critique : {str(e)}")

def get_zip(self, pid: str) -> Optional[Path]:
spec = self.projects.get(pid)
if not spec: return None
zip_path = BASE_DIR / f"{spec.name}_{pid}.zip"

# Attendre que le build soit fini
if spec.status not in ["COMPLETED", "FAILED"]:
return None

import zipfile
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
proj_dir = BASE_DIR / pid
for root, _, files in os.walk(proj_dir):
for file in files:
fpath = Path(root) / file
arcname = fpath.relative_to(proj_dir)
zipf.write(fpath, arcname)
return zip_path

# ==============================================================================
# SECTION 6 : INTERFACE HTML/JS (VISUEL DE L'ÉVOLUTION)
# ==============================================================================

HTML_UI = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NEXUS AUTOPOIESIS</title>
<style>
:root {
--bg: #050505; --panel: #0d0d12; --border: #1f1f2e;
--text: #e0e0e0; --accent: #00ffcc; --warn: #ffaa00; --err: #ff3366;
--font: 'JetBrains Mono', 'Fira Code', monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: var(--font); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

/* Header */
.header { padding: 15px 20px; background: var(--panel); border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
.logo { color: var(--accent); font-size: 20px; font-weight: bold; letter-spacing: 2px; text-shadow: 0 0 10px rgba(0,255,204,0.3); }

/* Layout */
.main { display: flex; flex: 1; overflow: hidden; }

/* Sidebar */
.sidebar { width: 380px; background: var(--panel); border-right: 1px solid var(--border); padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
label { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 5px; display: block; }
input, select, textarea { width: 100%; background: var(--bg); border: 1px solid var(--border); color: var(--accent); padding: 10px; border-radius: 4px; font-family: var(--font); outline: none; }
input:focus, select:focus, textarea:focus { border-color: var(--accent); box-shadow: 0 0 5px rgba(0,255,204,0.2); }
textarea { height: 80px; resize: vertical; }

button { background: var(--accent); color: #000; border: none; padding: 12px; border-radius: 4px; font-weight: bold; font-family: var(--font); cursor: pointer; text-transform: uppercase; letter-spacing: 1px; transition: 0.2s; }
button:hover { background: #00ccaa; box-shadow: 0 0 15px rgba(0,255,204,0.4); }
button:disabled { opacity: 0.5; cursor: not-allowed; box-shadow: none; }

/* Visualizer Area */
.visualizer { flex: 1; display: flex; flex-direction: column; background: #000; }

.top-pane { flex: 1; display: flex; border-bottom: 1px solid var(--border); }
.tree-pane { flex: 1; padding: 15px; overflow-y: auto; border-right: 1px solid var(--border); }
.console-pane { flex: 1; padding: 15px; overflow-y: auto; font-size: 13px; line-height: 1.6; }

.bottom-pane { height: 200px; padding: 15px; background: #0a0a0f; border-top: 1px solid var(--border); overflow-y: auto; }
.bottom-pane h3 { color: var(--warn); font-size: 12px; margin-bottom: 10px; text-transform: uppercase; }
.bench-output { color: #a0a0a0; white-space: pre-wrap; font-size: 12px; }

/* Elements */
.folder { color: var(--accent); font-weight: bold; display: block; margin-top: 5px; }
.file { color: #8899aa; margin-left: 20px; display: block; }
.file::before { content: "📄 "; }

.log-entry { margin-bottom: 4px; }
.log-INFO { color: #8899aa; }
.log-OK { color: var(--accent); }
.log-ERR { color: var(--err); }
.log-EXEC { color: var(--warn); }

.status-bar { padding: 10px 20px; background: var(--panel); border-top: 1px solid var(--border); display: flex; justify-content: space-between; font-size: 12px; }
.badge { padding: 2px 8px; border-radius: 10px; background: rgba(0,255,204,0.1); color: var(--accent); border: 1px solid var(--accent); }
</style>
</head>
<body>

<div class="header">
<div class="logo">⚡ NEXUS AUTOPOIESIS ENGINE</div>
</div>

<div class="main">
<div class="sidebar">
<div>
<label>Nom du SaaS</label>
<input type="text" id="projName" value="Nexus-SaaS" placeholder="Nom du projet">
</div>

<div>
<label>Prompt / Description</label>
<textarea id="projPrompt" placeholder="Génère un SaaS d'analyse de données..."></textarea>
</div>

<div>
<label>Langage Backend (Réel)</label>
<select id="stackBackend">
<option value="rust">Rust (Compilateur rustc)</option>
<option value="cobol">COBOL (GnuCOBOL cobc)</option>
<option value="python">Python (Interprété)</option>
</select>
</div>

<div>
<label>Frontend</label>
<select id="stackFrontend">
<option value="react">React + Vite</option>
<option value="none">Aucun</option>
</select>
</div>

<button id="genBtn" onclick="generate()">🚀 Forger le SaaS</button>
</div>

<div class="visualizer">
<div class="top-pane">
<div class="tree-pane" id="treeView">
<div style="color:#555; text-align:center; margin-top:50px;">En attente de génération...</div>
</div>
<div class="console-pane" id="consoleView">
<div style="color:#555; text-align:center; margin-top:50px;">Console d'exécution...</div>
</div>
</div>
<div class="bottom-pane">
<h3>⚙️ Benchmark & Compilation Output</h3>
<div class="bench-output" id="benchView">Aucun binaire compilé pour le moment.</div>
</div>
</div>
</div>

<div class="status-bar">
<div>Statut: <span id="statusText" style="color:var(--warn)">IDLE</span></div>
<div id="downloadContainer"></div>
</div>

<script>
let currentProjectId = null;
let pollInterval = null;

async function generate() {
const btn = document.getElementById('genBtn');
const name = document.getElementById('projName').value || 'NexusProject';
const prompt = document.getElementById('projPrompt').value;
const stack = {
backend: document.getElementById('stackBackend').value,
frontend: document.getElementById('stackFrontend').value
};

btn.disabled = true;
btn.textContent = '⏳ Forge en cours...';
document.getElementById('treeView').innerHTML = '';
document.getElementById('consoleView').innerHTML = '';
document.getElementById('benchView').textContent = 'En attente de compilation...';
document.getElementById('statusText').textContent = 'GENERATING';
document.getElementById('statusText').style.color = 'var(--warn)';
document.getElementById('downloadContainer').innerHTML = '';

try {
const res = await fetch('/api/generate', {
method: 'POST',
headers: {'Content-Type': 'application/json'},
body: JSON.stringify({ name, prompt, stack })
});
const data = await res.json();
currentProjectId = data.id;

if (pollInterval) clearInterval(pollInterval);
pollInterval = setInterval(() => pollStatus(currentProjectId), 1000);

} catch(e) {
document.getElementById('consoleView').innerHTML = `<div class="log-ERR">Erreur: ${e.message}</div>`;
btn.disabled = false;
btn.textContent = '🚀 Forger le SaaS';
}
}

async function pollStatus(id) {
try {
const res = await fetch(`/api/status?id=${id}`);
const data = await res.json();

if (data.error) return;

document.getElementById('statusText').textContent = data.status;

if (data.status === 'COMPLETED') {
document.getElementById('statusText').style.color = 'var(--accent)';
document.getElementById('genBtn').disabled = false;
document.getElementById('genBtn').textContent = '🚀 Forger le SaaS';
clearInterval(pollInterval);

document.getElementById('downloadContainer').innerHTML =
`<a href="/api/download?id=${id}" style="color:var(--accent); text-decoration:none;">📦 Télécharger le projet (.zip)</a>`;
} else if (data.status === 'FAILED') {
document.getElementById('statusText').style.color = 'var(--err)';
document.getElementById('genBtn').disabled = false;
document.getElementById('genBtn').textContent = '🚀 Forger le SaaS';
clearInterval(pollInterval);
}

renderTree(data.tree);
renderLogs(data.logs);
document.getElementById('benchView').textContent = data.benchmark || 'Aucune sortie de benchmark.';

} catch(e) {
console.error(e);
}
}

function renderTree(tree) {
let html = '';
function walk(node) {
for (const [key, value] of Object.entries(node)) {
if (typeof value === 'object') {
html += `<span class="folder">📁 ${key}/</span>`;
walk(value);
} else {
html += `<span class="file">${key}</span>`;
}
}
}
walk(tree);
document.getElementById('treeView').innerHTML = html || '<div style="color:#555">Arborescence vide</div>';
}

function renderLogs(logs) {
let html = '';
logs.forEach(l => {
html += `<div class="log-entry log-${l.level}">[${l.time}] ${l.msg}</div>`;
});
const c = document.getElementById('consoleView');
c.innerHTML = html;
c.scrollTop = c.scrollHeight;
}
</script>
</body>
</html>"""

# ==============================================================================
# SECTION 7 : SERVEUR HTTP
# ==============================================================================

class Handler(BaseHTTPRequestHandler):
engine = AutopoiesisEngine()

def log_message(self, fmt, *args): pass

def _send_json(self, code, data):
self.send_response(code)
self.send_header("Content-Type", "application/json")
self.send_header("Access-Control-Allow-Origin", "*")
self.end_headers()
self.wfile.write(json.dumps(data).encode())

def do_GET(self):
parsed = urllib.parse.urlparse(self.path)

if parsed.path == "/":
self.send_response(200)
self.send_header("Content-Type", "text/html; charset=utf-8")
self.end_headers()
self.wfile.write(HTML_UI.encode())

elif parsed.path == "/api/status":
qs = urllib.parse.parse_qs(parsed.query)
pid = qs.get("id", [""])[0]
spec = self.engine.projects.get(pid)
if spec:
self._send_json(200, spec.to_dict())
else:
self._send_json(404, {"error": "Projet introuvable"})

elif parsed.path == "/api/download":
qs = urllib.parse.parse_qs(parsed.query)
pid = qs.get("id", [""])[0]
zip_path = self.engine.get_zip(pid)

if zip_path and zip_path.exists():
self.send_response(200)
self.send_header("Content-Type", "application/zip")
self.send_header("Content-Disposition", f'attachment; filename="{zip_path.name}"')
self.send_header("Content-Length", str(zip_path.stat().st_size))
self.end_headers()
with open(zip_path, "rb") as f:
shutil.copyfileobj(f, self.wfile)
else:
self._send_json(404, {"error": "Archive non prête"})
else:
self.send_response(404)
self.end_headers()

def do_POST(self):
if self.path == "/api/generate":
length = int(self.headers.get('Content-Length', 0))
body = self.rfile.read(length)
try:
data = json.loads(body.decode())
name = data.get("name", "SaaS")
prompt = data.get("prompt", "")
stack = data.get("stack", {})

spec = self.engine.create_and_run(name, prompt, stack)
self._send_json(200, {"id": spec.id})
except Exception as e:
self._send_json(500, {"error": str(e)})
else:
self._send_json(404, {"error": "Not found"})

# ==============================================================================
# SECTION 8 : MAIN
# ==============================================================================

def main():
print(f"""
\033[96m
╔══════════════════════════════════════════════════════════════════════════╗
║ NEXUS AUTOPOIESIS ENGINE v{VERSION} ║
║ Usine Logicielle Autonome (Rust / COBOL / Python / React) ║
║ Architecte: Aissa Mohammedi (DGK) ║
╚══════════════════════════════════════════════════════════════════════════╝
\033[0m
🌐 Dashboard : http://localhost:{PORT}
📁 Workspace : {BASE_DIR}

\033[93m[!] Vérification des compilateurs locaux :\033[0m
\033[92m - Rust (rustc) : {shutil.which('rustc') or 'NON INSTALLÉ'}\033[0m
\033[92m - COBOL (cobc) : {shutil.which('cobc') or 'NON INSTALLÉ'}\033[0m
\033[92m - Python (py) : {sys.executable}\033[0m

\033[93m[!] Prêt. Ctrl+C pour arrêter.\033[0m
""")

server = ThreadingHTTPServer((HOST, PORT), Handler)
try:
server.serve_forever()
except KeyboardInterrupt:
print("\n\033[91mArrêt du serveur.\033[0m")

if __name__ == "__main__":
main()
