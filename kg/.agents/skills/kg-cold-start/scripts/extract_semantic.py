"""Phase 3: Extract SEMANTIC edges via LLM (serial, batched).

Key differences from phase3_extract_semantic.py:
  - Serial calls: one LLM request at a time, no concurrency
  - Batched prompt: 5 chunk pairs per call → ~261 calls total
  - 429 backoff: wait 2-3 minutes on rate limit, then retry
  - Separate success/failure logging

Usage:
    python phase3_batch.py \
        --evidence InterX/kg/state/evidence_mapped.json \
        --process-dir InterX/process/artifacts/manuals \
        --output InterX/kg/state/semantic_edges.json \
        --batch-size 5
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ── Logging ───────────────────────────────────────────────────────────

def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("phase3")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Main log file
    fh = logging.FileHandler(log_dir / "phase3_batch.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Success log
    sh = logging.FileHandler(log_dir / "phase3_success.log", encoding="utf-8")
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    sh.addFilter(lambda record: record.levelno == logging.INFO and "SUCCESS" in record.getMessage())
    logger.addHandler(sh)

    # Failure log
    fh2 = logging.FileHandler(log_dir / "phase3_failure.log", encoding="utf-8")
    fh2.setLevel(logging.DEBUG)
    fh2.setFormatter(fmt)
    fh2.addFilter(lambda record: record.levelno == logging.WARNING and "FAIL" in record.getMessage())
    logger.addHandler(fh2)

    return logger


# ── Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a knowledge graph edge extractor for product manuals.
Given a question and multiple pairs of text chunks used as evidence,
decide for EACH pair if the two chunks have a SEMANTIC relationship useful for multi-hop retrieval.

YES when:
- Cause-effect: one describes a problem/symptom, the other describes its cause
- Problem-solution: one describes an issue, the other provides the fix
- Sequential dependency: one describes a precondition for the other
- Conditional logic: "if X then Y" spans across chunks

NO when:
- Chunks merely co-occur in the same section
- Chunks describe unrelated topics that happen to answer the same question
- The connection is vague or topical

Output a JSON array, one element per pair, in the same order.
Keep description in the same language as the chunks. Concise: one sentence, ≤50 chars.
Output strict JSON array only, no markdown fences."""


def build_user_prompt(question: str, pairs: list[dict]) -> str:
    lines = [f"Question: {question[:500]}", ""]
    for i, p in enumerate(pairs):
        lines.append(f"Pair {i + 1}:")
        lines.append(f"Chunk A ({p['chunk_a_id']}) [{p['section_a']}]:")
        lines.append(p["text_a"][:1500])
        lines.append(f"Chunk B ({p['chunk_b_id']}) [{p['section_b']}]:")
        lines.append(p["text_b"][:1500])
        lines.append("")

    n = len(pairs)
    lines.append(f"Output a JSON array of {n} objects, each with: pair (1-{n}), has_semantic (bool), description (string).")
    return "\n".join(lines)


# ── LLM Call ──────────────────────────────────────────────────────────

def call_llm_batch(
    user_prompt: str,
    base_url: str,
    api_key: str,
    model: str,
    log: logging.Logger,
    max_retries: int = 5,
) -> list[dict]:
    """Call LLM with a batched prompt. Handles 429 with exponential backoff."""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=180)

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=2048,
            )
            raw = (resp.choices[0].message.content or "").strip()
            # Clean markdown fences
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            result = json.loads(raw)
            if isinstance(result, list):
                return result
            log.warning("LLM returned non-array: %s", str(result)[:200])
            return []
        except json.JSONDecodeError as e:
            log.warning("JSON parse failed (attempt %d): %s", attempt + 1, str(e)[:100])
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate" in err_str.lower() or "too many" in err_str.lower():
                wait = 120 + attempt * 60  # 2-5 minutes
                log.warning("429 rate limited, waiting %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                time.sleep(wait)
            else:
                log.warning("LLM call failed (attempt %d): %s", attempt + 1, err_str[:200])
                time.sleep(10)

    return []


# ── Helpers ───────────────────────────────────────────────────────────

def load_chunks_map(process_dir: Path, manual_id: str) -> dict[str, dict[str, Any]]:
    chunk_file = process_dir / manual_id / "small_chunks.jsonl"
    result: dict[str, dict[str, Any]] = {}
    if not chunk_file.exists():
        return result
    with open(chunk_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                result[c["chunk_id"]] = c
    return result


def pair_key(a: str, b: str) -> str:
    return f"{min(a, b)}||{max(a, b)}"


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 3: Batched SEMANTIC edge extraction")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--process-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--batch-size", type=int, default=5, help="Chunk pairs per LLM call")
    parser.add_argument("--max-chunks-per-answer", type=int, default=8)
    parser.add_argument("--max-pairs-per-answer", type=int, default=10)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    # Load env
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    base_url = os.getenv("LLM_BASE_URL", "https://token-plan-cn.xiaomimimo.com/v1")
    api_key = os.getenv("LLM_API_KEY", "")
    model = os.getenv("LLM_MODEL", "mimo-v2.5-pro")

    if not api_key:
        print("ERROR: LLM_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log = setup_logging(log_dir)

    # Load evidence
    with open(args.evidence, encoding="utf-8") as f:
        evidence_data = json.load(f)

    process_dir = Path(args.process_dir)
    output_path = Path(args.output)

    # Group by answer
    answer_groups: dict[str, list[dict]] = defaultdict(list)
    for r in evidence_data["records"]:
        mid = r.get("manual_id")
        aid = r.get("answer_id")
        if mid and aid and r.get("chunk_ids"):
            answer_groups[f"{mid}||{aid}"].append(r)

    # Resume support
    done_pairs: set[str] = set()
    all_edges: list[dict] = []
    if args.resume and output_path.exists():
        with open(output_path, encoding="utf-8") as f:
            prev = json.load(f)
        for e in prev.get("edges", []):
            pk = pair_key(e["chunk_a"], e["chunk_b"])
            done_pairs.add(pk)
            all_edges.append(e)
        log.info("Resumed with %d existing edges", len(all_edges))

    # Build batched tasks
    # Each task = one LLM call = one answer's chunk pairs (up to batch_size pairs)
    batches: list[dict] = []
    for key, group in answer_groups.items():
        mid, aid = key.split("||", 1)

        all_cids: list[str] = []
        for r in group:
            for cid in r.get("chunk_ids", []):
                if cid not in all_cids:
                    all_cids.append(cid)

        if len(all_cids) < 2:
            continue
        if len(all_cids) > args.max_chunks_per_answer:
            all_cids = all_cids[:args.max_chunks_per_answer]

        question = group[0].get("question", "")
        chunk_map = load_chunks_map(process_dir, mid)

        # Build pairs, skip same big_chunk and already-done
        pairs: list[dict] = []
        for i, ca in enumerate(all_cids):
            for cb in all_cids[i + 1:]:
                pk = pair_key(ca, cb)
                if pk in done_pairs:
                    continue
                a_info = chunk_map.get(ca, {})
                b_info = chunk_map.get(cb, {})
                if a_info.get("big_chunk_id") == b_info.get("big_chunk_id") and a_info.get("big_chunk_id"):
                    continue
                if not a_info or not b_info:
                    continue
                pairs.append({
                    "chunk_a_id": ca,
                    "chunk_b_id": cb,
                    "section_a": a_info.get("section_title", "")[:100],
                    "section_b": b_info.get("section_title", "")[:100],
                    "text_a": a_info.get("text", ""),
                    "text_b": b_info.get("text", ""),
                })

        if len(pairs) > args.max_pairs_per_answer:
            pairs = pairs[:args.max_pairs_per_answer]

        if not pairs:
            continue

        # Split into batches of batch_size
        for batch_start in range(0, len(pairs), args.batch_size):
            batch_pairs = pairs[batch_start:batch_start + args.batch_size]
            batches.append({
                "manual_id": mid,
                "answer_id": aid,
                "question": question,
                "pairs": batch_pairs,
            })

    log.info("Total batches: %d (batch_size=%d, from %d answers)",
             len(batches), args.batch_size, len(answer_groups))

    if not batches:
        log.info("No batches to process")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"edges": all_edges}, f, ensure_ascii=False, indent=2)
        return

    # Process serially
    t0 = time.time()
    total_calls = 0
    total_semantic = 0
    total_failures = 0

    for idx, batch in enumerate(batches):
        mid = batch["manual_id"]
        pairs = batch["pairs"]

        user_prompt = build_user_prompt(batch["question"], pairs)

        log.debug("Batch %d/%d: %s Q=%s pairs=%d",
                  idx + 1, len(batches), mid, batch["answer_id"][:20], len(pairs))

        results = call_llm_batch(user_prompt, base_url, api_key, model, log)
        total_calls += 1

        if not results:
            total_failures += 1
            log.warning("FAIL batch %d/%d: %s q_%s - no valid result",
                        idx + 1, len(batches), mid, batch["answer_id"])
        else:
            # Process results
            batch_semantic = 0
            for i, pair_info in enumerate(pairs):
                if i >= len(results):
                    break
                r = results[i]
                if not isinstance(r, dict):
                    continue
                if r.get("has_semantic"):
                    edge = {
                        "manual_id": mid,
                        "answer_id": batch["answer_id"],
                        "chunk_a": pair_info["chunk_a_id"],
                        "chunk_b": pair_info["chunk_b_id"],
                        "has_semantic": True,
                        "description": r.get("description", ""),
                    }
                    all_edges.append(edge)
                    done_pairs.add(pair_key(pair_info["chunk_a_id"], pair_info["chunk_b_id"]))
                    batch_semantic += 1
                    total_semantic += 1

            log.info("SUCCESS batch %d/%d: %s q_%s - %d/%d semantic",
                     idx + 1, len(batches), mid, batch["answer_id"],
                     batch_semantic, len(pairs))

        # Progress
        if (idx + 1) % 10 == 0:
            elapsed = time.time() - t0
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (len(batches) - idx - 1) / rate if rate > 0 else 0
            log.info("=== Progress: %d/%d batches, %d calls, %d semantic, %d failures, %.1f/batch, ETA %.0fs ===",
                     idx + 1, len(batches), total_calls, total_semantic, total_failures, rate, eta)

        # Periodic save
        if (idx + 1) % 20 == 0:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump({"edges": all_edges}, f, ensure_ascii=False, indent=2)
            log.debug("Saved %d edges to %s", len(all_edges), output_path)

    # Final save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"edges": all_edges}, f, ensure_ascii=False, indent=2)

    elapsed = time.time() - t0
    log.info("=== DONE in %.0fs ===", elapsed)
    log.info("Total batches: %d, LLM calls: %d", len(batches), total_calls)
    log.info("SEMANTIC edges found: %d", total_semantic)
    log.info("Failures: %d", total_failures)
    log.info("Output: %s", output_path)
    log.info("Logs: %s", log_dir)


if __name__ == "__main__":
    main()
