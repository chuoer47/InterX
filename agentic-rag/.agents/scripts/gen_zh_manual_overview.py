#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2] / 'ch-manual'
OUT = ROOT / '手册内容总览.md'


def extract_overview(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    title = path.stem
    for line in text:
        cleaned = line.strip().lstrip('# ')
        if cleaned:
            title = cleaned
            break
    top_sections: list[str] = []
    for line in text:
        m = re.match(r'^(#{1,2})\s+(.*)', line)
        if m:
            section = m.group(2).strip()
            if section and section != title:
                top_sections.append(section)
        if len(top_sections) >= 8:
            break
    return [f'# {title}', '', '主要章节：'] + [f'- {s}' for s in top_sections]


def main() -> int:
    manuals = sorted(ROOT.glob('*.md'))
    manuals = [m for m in manuals if m.name != '手册内容总览.md']
    lines = ['# 中文手册内容总览', '', '本文件用于快速查看 `agentic-rag/ch-manual/` 中的中文手册内容，并帮助路由中文问题到最可能的产品手册。', '']
    for idx, path in enumerate(manuals, start=1):
        lines.append(f'## {idx}. `{path.name}`')
        lines.append('')
        lines.extend(extract_overview(path))
        lines.append('')
    OUT.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
