#!/usr/bin/env python3
from __future__ import annotations

import os
import requests

base = os.getenv('INTERX_GATEWAY_BASE', 'http://127.0.0.1:4000')
key = os.getenv('LITELLM_MASTER_KEY', '')
headers = {'Authorization': f'Bearer {key}'} if key else {}

payload = {
    'model': 'interx-chat',
    'messages': [{'role': 'user', 'content': 'Count from 1 to 5.'}],
    'stream': True,
}
with requests.post(f'{base}/v1/chat/completions', json=payload, headers=headers, stream=True, timeout=120) as resp:
    print('status=', resp.status_code)
    resp.raise_for_status()
    for idx, line in enumerate(resp.iter_lines(decode_unicode=True)):
        if line:
            print(line)
        if idx > 20:
            break
print('stream test completed')
