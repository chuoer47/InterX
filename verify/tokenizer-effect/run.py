#!/usr/bin/env python3
"""五重分词效果验证：对比纯 jieba vs 五重分词的 BM25 召回率。

逻辑：
1. 加载 ground_truth.json（350 条问题 + evidence_refs）
2. 加载 process 包的 small_chunks 构建 BM25 语料
3. 分别用纯 jieba 和五重分词构建 BM25 索引
4. 对每条问题运行 BM25 检索，对比 Recall@K
5. 输出两种分词策略的召回率差异
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

from retrieval.tokenizer import CHINESE_RE, ASCII_TOKEN_RE  # noqa: E402

try:
    import jieba
except ImportError:
    jieba = None

from rank_bm25 import BM25Okapi  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE.parent / "retrieval-quality" / "data"

# ── 分词策略 ─────────────────────────────────────────────
def tokenize_jieba_only(text: str) -> list[str]:
    """纯 jieba 分词（基线）。"""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    words = []
    if jieba is not None:
        words = [t.strip().lower() for t in jieba.lcut(normalized) if t.strip() and not t.isspace()]
    ascii_tokens = [t.lower() for t in ASCII_TOKEN_RE.findall(normalized)]
    return ascii_tokens + words or [normalized.lower()]


def tokenize_five_layer(text: str) -> list[str]:
    """五重分词（ASCII + jieba + unigram + bigram + trigram）。"""
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []
    ascii_tokens = [t.lower() for t in ASCII_TOKEN_RE.findall(normalized)]
    chinese_chars = [c for c in normalized if CHINESE_RE.fullmatch(c)]
    char_bigrams = ["".join(chinese_chars[i:i+2]) for i in range(len(chinese_chars)-1)]
    char_trigrams = ["".join(chinese_chars[i:i+3]) for i in range(len(chinese_chars)-2)]
    words = []
    if jieba is not None:
        words = [t.strip().lower() for t in jieba.lcut(normalized) if t.strip() and not t.isspace()]
    tokens = ascii_tokens + words + chinese_chars + char_bigrams + char_trigrams
    return tokens or [normalized.lower()]


# ── evidence → chunk_id 映射（复用 retrieval-quality 逻辑）──
def _parse_line_ranges(lines_str) -> list[tuple[int, int]]:
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


def evidence_to_chunk_ids(refs, manual_lookup, line_indexes) -> list[str]:
    all_cids = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        path = ref.get("file") or ref.get("source", "")
        lines_str = ref.get("lines", "")
        if not path or not lines_str:
            continue
        display_name = os.path.basename(path)
        manual_id = manual_lookup.get(display_name)
        if not manual_id:
            continue
        intervals = line_indexes.get(manual_id, [])
        if not intervals:
            continue
        for start, end in _parse_line_ranges(lines_str):
            for s, e, cid in intervals:
                if e < start:
                    continue
                if s > end:
                    break
                if cid not in all_cids:
                    all_cids.append(cid)
    seen = set()
    return [c for c in all_cids if c not in seen and not seen.add(c)]


# ── 主逻辑 ──────────────────────────────────────────────
def run(max_questions: int = 350) -> dict:
    # 加载数据
    manual_lookup = json.loads((DATA_DIR / "manual_lookup.json").read_text())
    line_indexes = json.loads((DATA_DIR / "line_indexes.json").read_text())
    ground_truth = json.loads((DATA_DIR / "ground_truth.json").read_text())

    # 加载语料
    manuals_dir = ROOT / "process" / "artifacts" / "manuals"
    corpus_chunks = []
    for folder in sorted(manuals_dir.iterdir()):
        if not folder.is_dir():
            continue
        chunk_file = folder / "small_chunks.jsonl"
        if not chunk_file.exists():
            continue
        with open(chunk_file) as f:
            for line in f:
                chunk = json.loads(line.strip())
                corpus_chunks.append(chunk)

    print(f"五重分词效果验证")
    print(f"语料: {len(corpus_chunks)} chunks\n")

    # 构建两个 BM25 索引
    print("构建纯 jieba BM25 索引...")
    t0 = time.monotonic()
    corpus_jieba = [tokenize_jieba_only(c.get("retrieval_text") or c.get("text") or "") for c in corpus_chunks]
    bm25_jieba = BM25Okapi(corpus_jieba)
    t_jieba_build = time.monotonic() - t0
    print(f"  耗时: {t_jieba_build:.1f}s, token 总数: {sum(len(t) for t in corpus_jieba)}")

    print("构建五重分词 BM25 索引...")
    t0 = time.monotonic()
    corpus_five = [tokenize_five_layer(c.get("retrieval_text") or c.get("text") or "") for c in corpus_chunks]
    bm25_five = BM25Okapi(corpus_five)
    t_five_build = time.monotonic() - t0
    print(f"  耗时: {t_five_build:.1f}s, token 总数: {sum(len(t) for t in corpus_five)}")

    # 采样
    if max_questions < len(ground_truth):
        zh = [g for g in ground_truth if g["lang"] == "zh"]
        en = [g for g in ground_truth if g["lang"] == "en"]
        half = max_questions // 2
        sampled = zh[:half] + en[:half]
    else:
        sampled = ground_truth

    print(f"\n测试: {len(sampled)} 条问题\n")

    # 对比检索
    results = []
    jieba_hits = {"k5": 0, "k10": 0, "k20": 0}
    five_hits = {"k5": 0, "k10": 0, "k20": 0}
    valid = 0

    for gt in sampled:
        q = gt["question"]
        gt_chunks = evidence_to_chunk_ids(gt.get("evidence_refs", []), manual_lookup, line_indexes)
        if not gt_chunks:
            continue
        valid += 1
        gt_set = set(gt_chunks)

        # 纯 jieba BM25
        scores_j = bm25_jieba.get_scores(tokenize_jieba_only(q))
        ranked_j = sorted(enumerate(scores_j), key=lambda x: x[1], reverse=True)[:20]
        top_ids_j = [corpus_chunks[i]["chunk_id"] for i, s in ranked_j if s > 0]

        # 五重分词 BM25
        scores_f = bm25_five.get_scores(tokenize_five_layer(q))
        ranked_f = sorted(enumerate(scores_f), key=lambda x: x[1], reverse=True)[:20]
        top_ids_f = [corpus_chunks[i]["chunk_id"] for i, s in ranked_f if s > 0]

        # 统计命中
        for k, key in [(5, "k5"), (10, "k10"), (20, "k20")]:
            if gt_set & set(top_ids_j[:k]):
                jieba_hits[key] += 1
            if gt_set & set(top_ids_f[:k]):
                five_hits[key] += 1

        # 记录差异案例
        j5 = bool(gt_set & set(top_ids_j[:5]))
        f5 = bool(gt_set & set(top_ids_f[:5]))
        if f5 and not j5:
            results.append({"id": gt["id"], "question": q, "lang": gt["lang"],
                            "jieba_k5": False, "five_k5": True, "diff": "five_only"})
        elif j5 and not f5:
            results.append({"id": gt["id"], "question": q, "lang": gt["lang"],
                            "jieba_k5": True, "five_k5": False, "diff": "jieba_only"})

    # 汇总
    n = valid
    summary = {
        "valid_questions": n,
        "jieba_build_time_s": round(t_jieba_build, 1),
        "five_build_time_s": round(t_five_build, 1),
        "jieba_corpus_tokens": sum(len(t) for t in corpus_jieba),
        "five_corpus_tokens": sum(len(t) for t in corpus_five),
        "jieba_recall": {
            "k5": round(jieba_hits["k5"] / n * 100, 1) if n else 0,
            "k10": round(jieba_hits["k10"] / n * 100, 1) if n else 0,
            "k20": round(jieba_hits["k20"] / n * 100, 1) if n else 0,
        },
        "five_layer_recall": {
            "k5": round(five_hits["k5"] / n * 100, 1) if n else 0,
            "k10": round(five_hits["k10"] / n * 100, 1) if n else 0,
            "k20": round(five_hits["k20"] / n * 100, 1) if n else 0,
        },
        "improvement": {
            "k5": round((five_hits["k5"] - jieba_hits["k5"]) / n * 100, 1) if n else 0,
            "k10": round((five_hits["k10"] - jieba_hits["k10"]) / n * 100, 1) if n else 0,
            "k20": round((five_hits["k20"] - jieba_hits["k20"]) / n * 100, 1) if n else 0,
        },
        "diff_cases": results[:20],
        "diff_count": len(results),
    }

    print(f"{'指标':<12} {'纯jieba':>10} {'五重分词':>10} {'提升':>8}")
    print("-" * 45)
    for k in ["k5", "k10", "k20"]:
        j = summary["jieba_recall"][k]
        f = summary["five_layer_recall"][k]
        imp = summary["improvement"][k]
        print(f"  Recall@{k:<4} {j:>9.1f}% {f:>9.1f}% {imp:>+7.1f}%")

    print(f"\n五重分词独有命中: {sum(1 for r in results if r['diff'] == 'five_only')}")
    print(f"纯jieba独有命中: {sum(1 for r in results if r['diff'] == 'jieba_only')}")

    (HERE / "results" / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
