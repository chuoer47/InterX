#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import requests
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title='InterX Local Monitor')


def run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, timeout=5)
    except Exception as exc:
        return f'ERROR: {exc}'


def http_status(url: str, headers: dict[str, str] | None = None, timeout: int = 4) -> dict[str, Any]:
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        return {'ok': r.ok, 'status_code': r.status_code, 'text': r.text[:300]}
    except Exception as exc:
        return {'ok': False, 'error': repr(exc)}


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/api/status')
def api_status() -> JSONResponse:
    headers = {'Authorization': 'Bearer interx-local-master-key'}
    payload = {
        'litellm_models': http_status('http://127.0.0.1:4000/v1/models', headers=headers, timeout=4),
        'semantic_cache_health': http_status('http://127.0.0.1:4010/health', timeout=3),
        'semantic_cache_metrics': http_status('http://127.0.0.1:4010/metrics', timeout=3),
        'redis_ping': run(['redis-cli', '-h', '127.0.0.1', '-p', '6379', 'ping']) if Path('/usr/bin/redis-cli').exists() else 'redis-cli missing',
        'scoreboard': load_json(ROOT / 'tests' / 'results' / 'upstream_scoreboard.json'),
        'routing_probe': load_json(ROOT / 'tests' / 'results' / 'routing_probe.json'),
    }
    return JSONResponse(payload)


@app.get('/', response_class=HTMLResponse)
def index() -> str:
    return '''
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>InterX Gateway Dashboard</title>
  <style>
    body { font-family: Inter, Arial, sans-serif; margin: 24px; background: #0b1020; color: #e5e7eb; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 16px; }
    .card { background: #111827; border-radius: 12px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,.2); }
    pre { white-space: pre-wrap; word-break: break-word; }
    .ok { color: #34d399; }
    .bad { color: #f87171; }
    h1,h2 { margin-top: 0; }
    table { width: 100%; border-collapse: collapse; }
    td, th { border-bottom: 1px solid #1f2937; padding: 6px; text-align: left; }
  </style>
</head>
<body>
  <h1>InterX Gateway Dashboard</h1>
  <div id="app">Loading...</div>
  <script>
    function badge(ok){ return ok ? '<span class="ok">OK</span>' : '<span class="bad">FAIL</span>'; }
    function table(rows){
      if(!rows || !rows.length) return '<p>No data</p>';
      const head = '<tr><th>Name</th><th>Score</th><th>Status</th><th>Elapsed</th></tr>';
      const body = rows.map(r => `<tr><td>${r.name}</td><td>${r.score}</td><td>${r.status_code}</td><td>${r.elapsed_seconds}</td></tr>`).join('');
      return `<table>${head}${body}</table>`;
    }
    async function load(){
      const res = await fetch('/api/status');
      const data = await res.json();
      const routingCounts = data.routing_probe && data.routing_probe.status_counts ? JSON.stringify(data.routing_probe.status_counts, null, 2) : 'No probe yet';
      const ranked = data.scoreboard && data.scoreboard.ranked ? data.scoreboard.ranked : [];
      document.getElementById('app').innerHTML = `
        <div class="grid">
          <div class="card"><h2>LiteLLM Models ${badge(data.litellm_models.ok)}</h2><pre>${JSON.stringify(data.litellm_models, null, 2)}</pre></div>
          <div class="card"><h2>Semantic Cache ${badge(data.semantic_cache_health.ok)}</h2><pre>${JSON.stringify(data.semantic_cache_health, null, 2)}</pre></div>
          <div class="card"><h2>Redis</h2><pre>${data.redis_ping}</pre></div>
          <div class="card"><h2>Routing Probe</h2><pre>${routingCounts}</pre></div>
        </div>
        <div class="card" style="margin-top:16px;"><h2>Upstream Scoreboard</h2>${table(ranked)}</div>
      `;
    }
    load();
    setInterval(load, 10000);
  </script>
</body>
</html>
'''
