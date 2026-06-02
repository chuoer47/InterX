#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT / 'litellm' / 'config.template.yaml').read_text(encoding='utf-8')
replacements = {
    'os.environ/UPSTREAM_1_MODEL': os.getenv('UPSTREAM_1_MODEL', ''),
    'os.environ/UPSTREAM_1_BASE_URL': os.getenv('UPSTREAM_1_BASE_URL', ''),
    'os.environ/UPSTREAM_1_API_KEY': os.getenv('UPSTREAM_1_API_KEY', ''),
    'os.environ/UPSTREAM_1_RPM': os.getenv('UPSTREAM_1_RPM', ''),
    'os.environ/UPSTREAM_1_TPM': os.getenv('UPSTREAM_1_TPM', ''),
    'os.environ/LITELLM_MASTER_KEY': os.getenv('LITELLM_MASTER_KEY', ''),
}
text = template
for old, new in replacements.items():
    text = text.replace(old, str(new))
output = ROOT / 'litellm' / 'config.yaml'
output.write_text(text, encoding='utf-8')
print(f'wrote {output}')
