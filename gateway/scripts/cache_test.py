#!/usr/bin/env python3
from __future__ import annotations

import os
import requests

base = os.getenv('INTERX_SEM_CACHE_BASE', 'http://127.0.0.1:4010')
payload = {
    'model': 'interx-chat',
    'messages': [{'role': 'user', 'content': 'What is the warranty period for this product?'}],
    'stream': False,
}
for i in range(2):
    resp = requests.post(f'{base}/v1/cache/chat/completions', json=payload, timeout=180)
    print('run', i + 1, 'status=', resp.status_code)
    print(resp.text[:800])
    resp.raise_for_status()
print('cache test completed')
