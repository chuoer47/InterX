#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT
TODO_PATH = PROJECT / 'ch-todo.csv'
SYNC_PATH = PROJECT / '.codex' / 'scripts' / 'sync_zh_answers.py'
LOG_DIR = PROJECT / 'tmp' / 'ch-answers' / 'run-logs'
WORKDIR = PROJECT.parent


PROMPT_TEMPLATE = '''You are a fresh Chinese agentic-rag subagent.
Answer exactly one Chinese manual question with id {qid} from `agentic-rag/ch-question.csv`.

Use the skill `$answer-ch-agentic-rag`.
Start from source files only:
- `agentic-rag/ch-question.csv`
- `agentic-rag/ch-manual/*.md`
- `agentic-rag/ch-manual/手册内容总览.md`
- `agentic-rag/ch-manual/插图/*`

Hard constraints:
- Do not read or reuse prior generated answers.
- Edit only these files:
  - `agentic-rag/tmp/ch-answers/per_question/{qid}.json`
  - `agentic-rag/tmp/ch-answers/evidence-notes/{qid}.md`
  - `agentic-rag/ch-todo.csv`
- Keep the answer in valid v2 format.
- After writing the per-question JSON, update `agentic-rag/ch-todo.csv` for id {qid} to `done` with reasonable metadata.
- Before finishing, run `python3 agentic-rag/.codex/scripts/sync_zh_answers.py`.

Final message:
Return only a short summary with:
1) chosen manual
2) whether images were used
3) updated todo status for id {qid}
'''


async def run_one(qid: str, semaphore: asyncio.Semaphore, timeout: int) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f'{qid}.log'
    cmd = [
        'codex', 'exec',
        '-C', str(WORKDIR),
        '--dangerously-bypass-approvals-and-sandbox',
        '--dangerously-bypass-hook-trust',
        PROMPT_TEMPLATE.format(qid=qid),
    ]

    async with semaphore:
        start = datetime.now(timezone.utc)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {'id': qid, 'status': 'timeout', 'log': str(log_path)}

            log_path.write_text(
                f'start={start.isoformat()}\nreturncode={proc.returncode}\n\n--- stdout ---\n{stdout.decode(errors="replace")}\n\n--- stderr ---\n{stderr.decode(errors="replace")}\n',
                encoding='utf-8',
            )
            return {'id': qid, 'status': 'completed' if proc.returncode == 0 else 'failed', 'log': str(log_path)}
        except Exception as exc:
            log_path.write_text(f'start={start.isoformat()}\nerror={exc}\n', encoding='utf-8')
            return {'id': qid, 'status': 'failed', 'log': str(log_path)}


def load_pending_ids(limit: int | None) -> list[str]:
    with TODO_PATH.open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    pending = [row['id'] for row in rows if row.get('status') == 'pending']
    if limit is not None:
        pending = pending[:limit]
    return pending


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--concurrency', type=int, default=1)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--batch-size', type=int, default=None)
    args = parser.parse_args()

    ids = load_pending_ids(args.limit or args.batch_size)
    if not ids:
        print('no_pending_questions')
        return 0

    semaphore = asyncio.Semaphore(args.concurrency)
    stagger = asyncio.Semaphore(1)
    results = []
    for qid in ids:
        result = await run_one(qid, semaphore, args.timeout)
        proc = await asyncio.create_subprocess_exec('python3', str(SYNC_PATH), cwd=str(WORKDIR))
        await proc.wait()

        todo_row = None
        if TODO_PATH.exists():
            with TODO_PATH.open(newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    if row.get('id') == qid:
                        todo_row = row
                        break

        per_json = (PROJECT / 'tmp' / 'ch-answers' / 'per_question' / f'{qid}.json').exists()
        ev_note = (PROJECT / 'tmp' / 'ch-answers' / 'evidence-notes' / f'{qid}.md').exists()
        status_ok = bool(todo_row and todo_row.get('status') == 'done' and per_json and ev_note)

        if not status_ok:
            result['quality'] = 'invalid'
            result['todo_status'] = (todo_row or {}).get('status')
            result['per_question_exists'] = per_json
            result['evidence_note_exists'] = ev_note
        else:
            result['quality'] = 'valid'

        results.append(result)

    summary = {
        'requested': len(ids),
        'completed': sum(1 for r in results if r.get('status') == 'completed'),
        'failed': sum(1 for r in results if r.get('status') == 'failed'),
        'timeout': sum(1 for r in results if r.get('status') == 'timeout'),
    }
    print(json.dumps({'summary': summary, 'results': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
