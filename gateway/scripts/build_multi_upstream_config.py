#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
candidates = json.loads((ROOT / 'state' / 'upstream_candidates.json').read_text(encoding='utf-8'))
probe = {row['name']: row for row in json.loads((ROOT / 'tests' / 'results' / 'cc_switch_probe.json').read_text(encoding='utf-8'))}
usable = [row for row in candidates if probe.get(row['name'], {}).get('ok')]
usable.sort(key=lambda row: probe[row['name']]['elapsed_seconds'])

def normalize_base_url(url: str) -> str:
    if url.startswith('http://127.0.0.1:'):
        return url.replace('http://127.0.0.1', 'http://host.docker.internal')
    if url.startswith('http://localhost:'):
        return url.replace('http://localhost', 'http://host.docker.internal')
    return url

lines = ['model_list:']
for row in usable:
    alias = row['name'].lower().replace(' ', '-').replace('_', '-')
    base_url = normalize_base_url(row['base_url'])
    lines.extend([
        '  - model_name: interx-chat',
        '    litellm_params:',
        f'      model: openai/{row["model"]}',
        f'      api_base: {base_url}',
        f'      api_key: {row["api_key"]}',
        '      rpm: 3000',
        '      tpm: 120000',
        '      timeout: 120',
        '    model_info:',
        f'      id: {alias}',
    ])
lines.extend([
    '',
    'litellm_settings:',
    '  master_key: interx-local-master-key',
    '  set_verbose: true',
    '  drop_params: true',
    '  request_timeout: 120',
    '',
    'general_settings:',
    '  store_model_in_db: false',
    '  infer_model_from_keys: false',
    '  background_health_checks: false',
    '',
    'router_settings:',
    '  routing_strategy: simple-shuffle',
    '  allowed_fails: 1',
    '  cooldown_time: 15',
])
(ROOT / 'litellm' / 'config.multi.yaml').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('wrote', ROOT / 'litellm' / 'config.multi.yaml')
print('usable providers:', [row['name'] for row in usable])
