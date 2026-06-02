#!/usr/bin/env python3
"""
Sequential Chinese agentic-rag runner.
逐题调用 codex exec subagent，遇到错误等几分钟跳过，继续下一题。
"""
from __future__ import annotations

import csv
import json
import os
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path("/home/amax01/lingchen/YanD")
TODO_PATH = PROJECT / "agentic-rag" / "ch-todo.csv"
QUESTION_PATH = PROJECT / "agentic-rag" / "ch-question.csv"
PER_QUESTION_DIR = PROJECT / "agentic-rag" / "tmp" / "ch-answers" / "per_question"
EVIDENCE_DIR = PROJECT / "agentic-rag" / "tmp" / "ch-answers" / "evidence-notes"
SYNC_SCRIPT = PROJECT / "agentic-rag" / ".codex" / "scripts" / "sync_zh_answers.py"
LOG_PATH = PROJECT / "agentic-rag" / "tmp" / "ch-answers" / "runner.log"
PID_FILE = PROJECT / "agentic-rag" / "tmp" / "ch-answers" / "runner.pid"

WAIT_ON_ERROR = 180
WAIT_BETWEEN = 15
MAX_RETRIES_PER_Q = 2


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_questions() -> dict[str, str]:
    qmap = {}
    with QUESTION_PATH.open("r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qmap[row["id"]] = row.get("clean") or row.get("raw") or ""
    return qmap


def get_pending_ids() -> list[str]:
    ids = []
    with TODO_PATH.open("r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("status", "").strip() == "pending":
                ids.append(row["id"])
    return ids


def validate_output(qid: str) -> tuple[bool, list[str]]:
    errors = []
    pq = PER_QUESTION_DIR / f"{qid}.json"
    ev = EVIDENCE_DIR / f"{qid}.md"
    if not pq.exists():
        errors.append(f"per_question/{qid}.json missing")
        return False, errors
    if not ev.exists():
        errors.append(f"evidence-notes/{qid}.md missing")
    try:
        payload = json.loads(pq.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"invalid json: {e}")
        return False, errors
    content = str(payload.get("content", ""))
    images = payload.get("images", [])
    if not isinstance(images, list):
        errors.append("images is not a list")
        return False, errors
    pic_count = content.count("<PIC>")
    if pic_count != len(images):
        errors.append(f"<PIC> count ({pic_count}) != images count ({len(images)})")
    if not payload.get("evidence_refs"):
        errors.append("missing evidence_refs")
    return len(errors) == 0, errors


def update_todo_done(qid: str):
    rows = []
    with TODO_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            if row["id"] == qid:
                row["status"] = "done"
                row["evidence_status"] = "checked"
                row["answer_path"] = f"agentic-rag/tmp/ch-answers/per_question/{qid}.json"
                row["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            rows.append(row)
    with TODO_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_sync():
    try:
        r = subprocess.run(
            [sys.executable, str(SYNC_SCRIPT)],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT),
        )
        out = r.stdout.strip()
        if out:
            log(f"sync: {out}")
        if r.returncode != 0 and r.stderr.strip():
            log(f"sync err: {r.stderr.strip()[:200]}")
    except Exception as e:
        log(f"sync error: {e}")


def build_prompt(qid: str, question: str) -> str:
    return (
        f"你是中文产品手册问答专家。请回答问题 id={qid}：\n\n"
        f"问题：{question}\n\n"
        "严格按以下流程：\n"
        "1. 读取并使用 agentic-rag/.codex/skills/answer-ch-agentic-rag/SKILL.md 中的完整流程\n"
        "2. 在 agentic-rag/ch-manual/ 中检索证据，优先用手册内容总览.md 路由\n"
        '3. 答案必须是 v2 格式 JSON：{"content":"...","images":["..."]}\n'
        "4. content 中用 <PIC> 标记图片，数量必须与 images 数组一致\n"
        "5. 图片 ID 仅用文件名主干（不含路径和扩展名）\n"
        "6. 答案必须基于手册证据，附上 evidence_refs\n"
        "7. evidence_refs 中每项需包含 source 或 file 字段、lines 字段、summary 或 text 字段\n"
        "8. 不要使用 Markdown 格式（无标题、无粗体、无列表符号），纯文本即可\n\n"
        "完成后必须：\n"
        f"A. 将完整答案（含 id, question, content, images, ret, manual_guess, evidence_refs, status, notes）写入 agentic-rag/tmp/ch-answers/per_question/{qid}.json\n"
        f"B. 将证据笔记写入 agentic-rag/tmp/ch-answers/evidence-notes/{qid}.md\n"
        "C. 运行 python3 agentic-rag/.codex/scripts/sync_zh_answers.py 同步聚合文件"
    )


def run_subagent(qid: str, question: str) -> bool:
    prompt = build_prompt(qid, question)
    cmd = [
        "codex", "exec",
        "-C", str(PROJECT),
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
        "--json",
        prompt,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
            cwd=str(PROJECT),
        )
    except subprocess.TimeoutExpired:
        log(f"[{qid}] TIMEOUT 600s")
        return False
    except Exception as e:
        log(f"[{qid}] exec exception: {e}")
        return False

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")
    output = stdout + stderr

    if "429" in output or "Too Many Requests" in output:
        log(f"[{qid}] 429 rate limited")
        return False
    if result.returncode != 0 and "exceeded retry limit" in output:
        log(f"[{qid}] retry limit exceeded")
        return False
    if result.returncode != 0:
        log(f"[{qid}] exit code {result.returncode}")
        # still try to validate - maybe files were written
    return True


def main():
    log("=" * 60)
    log("Chinese agentic-rag sequential runner started")
    log(f"PID: {os.getpid()}")
    log("=" * 60)

    # Write PID file
    try:
        PID_FILE.write_text(str(os.getpid()))
    except Exception:
        pass

    qmap = load_questions()
    log(f"Loaded {len(qmap)} questions")

    total_done = 0
    total_failed = 0
    total_skipped = 0

    while True:
        pending = get_pending_ids()
        if not pending:
            log("No more pending questions. ALL DONE!")
            break

        log(f"Pending: {len(pending)} | done:{total_done} failed:{total_failed} skipped:{total_skipped}")

        for qid in pending:
            question = qmap.get(qid, "")
            if not question:
                log(f"[{qid}] No question text, skipping")
                total_skipped += 1
                continue

            log(f"[{qid}] {question[:80]}")
            success = False

            for attempt in range(1, MAX_RETRIES_PER_Q + 1):
                log(f"[{qid}] attempt {attempt}/{MAX_RETRIES_PER_Q}")
                try:
                    ok = run_subagent(qid, question)
                except Exception as e:
                    log(f"[{qid}] unexpected error: {e}")
                    traceback.print_exc()
                    ok = False

                if ok:
                    valid, errs = validate_output(qid)
                    if valid:
                        update_todo_done(qid)
                        run_sync()
                        total_done += 1
                        log(f"[{qid}] DONE (total:{total_done})")
                        success = True
                        break
                    else:
                        log(f"[{qid}] validation fail: {errs}")
                else:
                    log(f"[{qid}] subagent fail")

                if attempt < MAX_RETRIES_PER_Q:
                    log(f"[{qid}] wait {WAIT_ON_ERROR}s...")
                    time.sleep(WAIT_ON_ERROR)

            if not success:
                total_failed += 1
                log(f"[{qid}] FAILED ({total_failed} total)")

            log(f"sleep {WAIT_BETWEEN}s...")
            time.sleep(WAIT_BETWEEN)

        remaining = get_pending_ids()
        if remaining:
            log(f"Pass done. {len(remaining)} left. Wait 60s...")
            time.sleep(60)

    log("=" * 60)
    log(f"COMPLETE. done:{total_done} failed:{total_failed} skipped:{total_skipped}")
    log("=" * 60)

    # Clean up PID file
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


if __name__ == "__main__":
    main()
