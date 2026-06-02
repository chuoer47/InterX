#!/usr/bin/env python3
"""检索质量验证：ground truth (evidence_refs) vs 检索结果，计算 Recall@K。

逻辑：
1. 读取 ground_truth.json（350 条问题 + evidence_refs）
2. 通过 manual_lookup + line_index 将 evidence_refs 映射为 chunk_ids
3. 对每条问题运行 search_hierarchical（原始问题）
4. 检查 ground truth chunk_ids 是否在 top-K 结果中
5. 计算 Recall@5 / Recall@10 / Recall@20
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "answer" / "src"))
sys.path.insert(0, str(ROOT / "retrieval" / "src"))
sys.path.insert(0, str(ROOT / "kg" / "src"))

from retrieval import search_hierarchical, reload  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"

# ── 加载预计算数据 ──────────────────────────────────────
_manual_lookup: dict[str, str] = {}
_line_indexes: dict[str, list] = {}


def _load_data():
    global _manual_lookup, _line_indexes
    _manual_lookup = json.loads((DATA_DIR / "manual_lookup.json").read_text())
    _line_indexes = json.loads((DATA_DIR / "line_indexes.json").read_text())


# ── evidence_ref → chunk_ids 映射 ───────────────────────
def _parse_line_ranges(lines_str) -> list[tuple[int, int]]:
    """解析行号字符串为 (start, end) 列表。"""
    if not lines_str:
        return []
    if isinstance(lines_str, list):
        lines_str = str(lines_str[0]) if lines_str else ""
    if not isinstance(lines_str, str):
        lines_str = str(lines_str)
    cleaned = lines_str.strip("[] ")
    ranges = []
    for part in cleaned.split(","):
        part = part.strip()
        m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", part)
        if m:
            ranges.append((int(m.group(1)), int(m.group(2))))
            continue
        m = re.match(r"^(\d+)\s*[～~]\s*(\d+)$", part)
        if m:
            ranges.append((int(m.group(1)), int(m.group(2))))
            continue
        m = re.match(r"^(\d+)$", part)
        if m:
            n = int(m.group(1))
            ranges.append((n, n))
    return ranges


def _resolve_line_range(start: int, end: int, intervals: list) -> list[str]:
    """线性扫描找所有重叠的 chunk_id。"""
    ids = []
    for s, e, cid in intervals:
        if e < start:
            continue
        if s > end:
            break
        if cid not in ids:
            ids.append(cid)
    return ids


def evidence_to_chunk_ids(refs: list) -> list[str]:
    """将 evidence_refs 列表映射为 chunk_ids。"""
    all_cids = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = ref.get("file") or ref.get("source", "")
        lines_str = ref.get("lines", "")
        if not path or not lines_str:
            continue

        # 文件名 → manual_id
        display_name = os.path.basename(path)
        manual_id = _manual_lookup.get(display_name)
        if not manual_id:
            continue

        # 行号 → chunk_ids
        intervals = _line_indexes.get(manual_id, [])
        if not intervals:
            continue

        for start, end in _parse_line_ranges(lines_str):
            cids = _resolve_line_range(start, end, intervals)
            all_cids.extend(cids)

    # 去重保序
    seen = set()
    unique = []
    for cid in all_cids:
        if cid not in seen:
            seen.add(cid)
            unique.append(cid)
    return unique


# ── 主验证逻辑 ──────────────────────────────────────────
def run(max_questions: int = 350) -> dict:
    _load_data()
    ground_truth = json.loads((DATA_DIR / "ground_truth.json").read_text())

    # 采样
    if max_questions < len(ground_truth):
        zh = [g for g in ground_truth if g["lang"] == "zh"]
        en = [g for g in ground_truth if g["lang"] == "en"]
        half = max_questions // 2
        sampled = zh[:half] + en[:half]
    else:
        sampled = ground_truth

    print(f"检索质量验证 — {len(sampled)} 条\n")

    results = []
    hit_5 = hit_10 = hit_20 = 0
    mapped_count = 0
    unmapped_count = 0

    for i, gt in enumerate(sampled):
        q = gt["question"]

        # 映射 evidence_refs → chunk_ids
        gt_chunk_ids = evidence_to_chunk_ids(gt.get("evidence_refs", []))

        if not gt_chunk_ids:
            unmapped_count += 1
            results.append({"id": gt["id"], "question": q, "lang": gt["lang"],
                            "gt_chunks": 0, "mapped": False})
            continue

        mapped_count += 1

        # 检索
        t0 = time.monotonic()
        try:
            reload()
            result = search_hierarchical(q, top_k=20)
        except Exception as e:
            print(f"  ❌ Q{gt['id']}: {e}")
            results.append({"id": gt["id"], "question": q, "lang": gt["lang"],
                            "gt_chunks": len(gt_chunk_ids), "error": str(e)})
            continue
        elapsed = time.monotonic() - t0

        # 收集检索到的 chunk_ids
        retrieved_ids = [h.chunk_id for h in result.small_hits]
        retrieved_set = set(retrieved_ids)
        gt_set = set(gt_chunk_ids)

        k5 = bool(gt_set & set(retrieved_ids[:5]))
        k10 = bool(gt_set & set(retrieved_ids[:10]))
        k20 = bool(gt_set & set(retrieved_ids[:20]))

        if k5: hit_5 += 1
        if k10: hit_10 += 1
        if k20: hit_20 += 1

        mark = "✅" if k5 else ("⚠️" if k10 else "❌")
        sq = q[:33] + ".." if len(q) > 35 else q
        print(f"  {mark} [{gt['lang']}] Q{gt['id']:>3} | gt={len(gt_chunk_ids)} chunks | "
              f"top5={'Y' if k5 else 'N'} top10={'Y' if k10 else 'N'} top20={'Y' if k20 else 'N'} | "
              f"{elapsed:.1f}s | {sq}")

        results.append({
            "id": gt["id"], "question": q, "lang": gt["lang"],
            "gt_chunk_count": len(gt_chunk_ids),
            "retrieved_count": len(retrieved_ids),
            "hit_at_5": k5, "hit_at_10": k10, "hit_at_20": k20,
            "latency_s": round(elapsed, 2),
        })

    # 汇总
    n = mapped_count
    summary = {
        "total_questions": len(sampled),
        "mapped_to_chunks": mapped_count,
        "unmapped": unmapped_count,
        "hit_at_5": hit_5, "hit_at_10": hit_10, "hit_at_20": hit_20,
        "recall_at_5_pct": round(hit_5 / n * 100, 1) if n else 0,
        "recall_at_10_pct": round(hit_10 / n * 100, 1) if n else 0,
        "recall_at_20_pct": round(hit_20 / n * 100, 1) if n else 0,
        "avg_latency_s": round(sum(r["latency_s"] for r in results
                                   if "latency_s" in r) / max(1, n), 2),
        "cases": results,
    }

    print(f"\n{'='*60}")
    print(f"有效问题: {n}/{len(sampled)}（{unmapped_count} 条无法映射到 chunk）")
    print(f"Recall@5:  {hit_5}/{n} ({summary['recall_at_5_pct']}%)")
    print(f"Recall@10: {hit_10}/{n} ({summary['recall_at_10_pct']}%)")
    print(f"Recall@20: {hit_20}/{n} ({summary['recall_at_20_pct']}%)")
    print(f"平均延迟: {summary['avg_latency_s']}s")

    (HERE / "results" / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n结果已写入 results/")
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="跑全量 350 题")
    args = parser.parse_args()
    run(max_questions=350 if args.full else 350)
