#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

source = Path('/home/amax01/.cc-switch/codex-chat-proxy.json')
out = Path(__file__).resolve().parents[1] / 'docs' / 'cc_switch_template.md'
obj = json.loads(source.read_text(encoding='utf-8'))
content = f'''# cc-switch Template Notes

- listen host: `{obj.get('listen_host')}`
- listen port: `{obj.get('listen_port')}`
- upstream base url: `{obj.get('upstream_base_url')}`
- upstream model: `{obj.get('upstream_model')}`
- upstream chat path: `{obj.get('upstream_chat_path')}`
- timeout seconds: `{obj.get('request_timeout_seconds')}`
- api key present: `{'yes' if obj.get('upstream_api_key') else 'no'}`

Do not copy the raw API key into git-tracked files.
'''
out.write_text(content, encoding='utf-8')
print(f'wrote {out}')
