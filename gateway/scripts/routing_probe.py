#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
base = os.getenv('INTERX_GATEWAY_BASE', 'http://127.0.0.1:4000')
key = os.getenv('LITELLM_MASTER_KEY', 'interx-local-master-key')
headers = {'Authorization': f'Bearer {key}'}

rows = []
for i in range(12):
    payload = {
        'model': 'interx-chat',
        'messages': [{'role': 'user', 'content': f'Reply with token ROUTE-{i}'}],
        'stream': False,
    }
    started = time.perf_counter()
    try:
        resp = requests.post(f'{base}/v1/chat/completions', json=payload, headers=headers, timeout=45)
        elapsed = round(time.perf_counter() - started, 3)
        row = {
            'i': i,
            'status_code': resp.status_code,
            'elapsed_seconds': elapsed,
            'text': resp.text[:500],
        }
    except Exception as exc:
        elapsed = round(time.perf_counter() - started, 3)
        row = {
            'i': i,
            'status_code': None,
            'elapsed_seconds': elapsed,
            'error': repr(exc),
        }
    rows.append(row)

summary = Counter(str(row.get('status_code')) for row in rows)
out = {
    'rows': rows,
    'status_counts': dict(summary),
}
out_path = ROOT / 'tests' / 'results' / 'routing_probe.json'
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(out_path)
print(json.dumps(out['status_counts'], ensure_ascii=False, indent=2))
