#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = Path('/home/amax01/.cc-switch/codex-chat-proxy.json')
out = ROOT / '.env'
obj = json.loads(source.read_text(encoding='utf-8'))
content = f"""LITELLM_MASTER_KEY=interx-local-master-key
LITELLM_SALT_KEY=interx-local-salt-key
REDIS_URL=redis://redis:6379/0
LITELLM_PROXY_URL=http://litellm:4000
UPSTREAM_1_BASE_URL={obj.get('upstream_base_url','')}
UPSTREAM_1_API_KEY={obj.get('upstream_api_key','')}
UPSTREAM_1_MODEL={obj.get('upstream_model','')}
UPSTREAM_1_TPM=120000
UPSTREAM_1_RPM=3000
UPSTREAM_2_BASE_URL=
UPSTREAM_2_API_KEY=
UPSTREAM_2_MODEL=
UPSTREAM_2_TPM=
UPSTREAM_2_RPM=
SEMANTIC_CACHE_ENABLED=true
SEMANTIC_CACHE_MODEL={obj.get('upstream_model','')}
SEMANTIC_CACHE_BASE_URL={obj.get('upstream_base_url','')}
SEMANTIC_CACHE_API_KEY={obj.get('upstream_api_key','')}
SEMANTIC_CACHE_THRESHOLD=0.92
SEMANTIC_CACHE_MAX_CANDIDATES=5
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin
"""
out.write_text(content, encoding='utf-8')
print(f'wrote {out}')
