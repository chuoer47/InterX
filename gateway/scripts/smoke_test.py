#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import requests

base = os.getenv('INTERX_GATEWAY_BASE', 'http://127.0.0.1:4000')
key = os.getenv('LITELLM_MASTER_KEY', '')
headers = {'Authorization': f'Bearer {key}'} if key else {}

payload = {
    'model': 'interx-chat',
    'messages': [{'role': 'user', 'content': 'Reply with the single word OK.'}],
    'stream': False,
}
resp = requests.post(f'{base}/v1/chat/completions', json=payload, headers=headers, timeout=300)
print('status=', resp.status_code)
print(resp.text[:1200])
resp.raise_for_status()
content = resp.json()['choices'][0]['message']['content']
if 'OK' not in content.upper():
    print('unexpected content', content)
    sys.exit(2)
print('smoke test passed')
