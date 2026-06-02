#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
probe_path = ROOT / 'tests' / 'results' / 'cc_switch_probe.json'
out_path = ROOT / 'tests' / 'results' / 'upstream_scoreboard.json'
md_path = ROOT / 'tests' / 'results' / 'upstream_scoreboard.md'
rows = json.loads(probe_path.read_text(encoding='utf-8'))
scored = []
for row in rows:
    ok = bool(row.get('ok'))
    status = row.get('status_code')
    elapsed = row.get('elapsed_seconds') or 999.0
    score = 0.0
    if ok:
        score += 100.0
        score += max(0.0, 20.0 - elapsed * 5)
    elif status == 403:
        score += 30.0
    elif status == 404:
        score += 10.0
    scored.append({**row, 'score': round(score, 2)})
scored.sort(key=lambda x: x['score'], reverse=True)
out = {'ranked': scored}
out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
lines = ['# Upstream Scoreboard', '']
for idx, row in enumerate(scored, 1):
    lines.append(f"{idx}. {row['name']} | score={row['score']} | ok={row['ok']} | status={row['status_code']} | elapsed={row['elapsed_seconds']}")
md_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(out_path)
print(md_path)
for row in scored:
    print(row['name'], row['score'])
