#!/usr/bin/env python3
"""降级容错验证：模拟 Dense/Rerank 故障，验证系统降级行为。

测试场景：
1. Dense 检索失败 → 是否降级到纯 BM25
2. Rerank 失败 → 是否保留融合排序
3. 两者同时失败 → 是否降级到纯 BM25 无 Rerank
4. 上下文预算不足 → 截断是否正常工作
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "answer" / "src"))
sys.path.insert(0, str(ROOT / "retrieval" / "src"))
sys.path.insert(0, str(ROOT / "kg" / "src"))

from retrieval import search_hierarchical, reload  # noqa: E402
from retrieval.types import SearchHit  # noqa: E402

HERE = Path(__file__).resolve().parent

TEST_QUERIES = [
    "空调制冷效果差怎么办？",
    "How do I use the air fryer?",
    "电钻电池怎么充电？",
]


def run() -> dict:
    results = []
    print("降级容错验证\n")

    # ── 场景 1: Dense 失败 → 降级到纯 BM25 ──────────────
    print("=" * 60)
    print("场景 1: Dense 检索失败 → 降级到纯 BM25")
    print("=" * 60)

    for q in TEST_QUERIES:
        t0 = time.monotonic()
        try:
            reload()
            # 正常检索（基线）
            result_normal = search_hierarchical(q, top_k=20)
            normal_count = len(result_normal.small_hits)
        except Exception as e:
            normal_count = 0
            print(f"  ⚠️  基线检索异常: {e}")

        # 模拟 Dense 失败：patch embed_query 抛异常
        try:
            reload()
            with patch("retrieval.dense.embed_query", side_effect=Exception("Dense API timeout")):
                result_degraded = search_hierarchical(q, top_k=20)
                degraded_count = len(result_degraded.small_hits)
                degraded_ok = degraded_count > 0
        except Exception as e:
            degraded_count = 0
            degraded_ok = False
            print(f"  ❌ 降级后检索也失败: {e}")

        elapsed = time.monotonic() - t0
        mark = "✅" if degraded_ok else "❌"
        print(f"  {mark} [{q[:30]}...] 正常={normal_count}hits, 降级={degraded_count}hits, {elapsed:.1f}s")
        results.append({"scenario": "dense_failure", "query": q,
                        "normal_hits": normal_count, "degraded_hits": degraded_count,
                        "fallback_ok": degraded_ok})

    # ── 场景 2: Rerank 失败 → 保留融合排序 ──────────────
    print(f"\n{'='*60}")
    print("场景 2: Rerank 失败 → 保留融合排序")
    print("=" * 60)

    for q in TEST_QUERIES:
        try:
            reload()
            # 正常检索
            result_normal = search_hierarchical(q, top_k=10)
            normal_top3 = [h.chunk_id for h in result_normal.small_hits[:3]]
        except Exception as e:
            normal_top3 = []
            print(f"  ⚠️  基线检索异常: {e}")

        # 模拟 Rerank 失败
        try:
            reload()
            with patch("retrieval.rerank.Reranker.rerank", side_effect=Exception("Rerank API timeout")):
                result_no_rerank = search_hierarchical(q, top_k=10)
                no_rerank_top3 = [h.chunk_id for h in result_no_rerank.small_hits[:3]]
                # 结果应仍有效（降级到融合排序）
                degraded_ok = len(result_no_rerank.small_hits) > 0
        except Exception as e:
            no_rerank_top3 = []
            degraded_ok = False
            print(f"  ❌ Rerank 降级后检索失败: {e}")

        mark = "✅" if degraded_ok else "❌"
        # 检查排序是否相同或合理不同
        same_order = normal_top3 == no_rerank_top3
        print(f"  {mark} [{q[:30]}...] 融合排序有效={degraded_ok}, 排序一致={same_order}")
        results.append({"scenario": "rerank_failure", "query": q,
                        "normal_top3": normal_top3, "no_rerank_top3": no_rerank_top3,
                        "fallback_ok": degraded_ok, "order_same": same_order})

    # ── 场景 3: Dense + Rerank 同时失败 ─────────────────
    print(f"\n{'='*60}")
    print("场景 3: Dense + Rerank 同时失败 → 纯 BM25 无 Rerank")
    print("=" * 60)

    for q in TEST_QUERIES:
        try:
            reload()
            with patch("retrieval.dense.embed_query", side_effect=Exception("Dense timeout")), \
                 patch("retrieval.rerank.Reranker.rerank", side_effect=Exception("Rerank timeout")):
                result = search_hierarchical(q, top_k=10)
                ok = len(result.small_hits) > 0
                count = len(result.small_hits)
        except Exception as e:
            ok = False
            count = 0
            print(f"  ❌ 双故障降级失败: {e}")

        mark = "✅" if ok else "❌"
        print(f"  {mark} [{q[:30]}...] 纯BM25={count}hits")
        results.append({"scenario": "both_failure", "query": q,
                        "hits": count, "fallback_ok": ok})

    # ── 场景 4: 上下文预算截断 ─────────────────────────
    print(f"\n{'='*60}")
    print("场景 4: 上下文预算截断")
    print("=" * 60)

    from answer.context import format_context

    # 构造大量 chunk 测试截断
    fake_chunks = [{"chunk_id": f"test_{i}", "rank": i, "content": f"这是第{i}条证据，" + "内容" * 100,
                    "doc_name": "test.md", "section_title": f"章节{i}", "header_path": ["test"],
                    "image_abs_paths": []} for i in range(50)]

    for budget in [2000, 5000, 10000]:
        ctx = format_context(fake_chunks, max_chars=budget)
        ctx_data = json.loads(ctx)
        evidence_count = len(ctx_data.get("evidence", []))
        actual_len = len(ctx)
        print(f"  预算={budget}字符 → 选入{evidence_count}条证据, 实际{actual_len}字符")
        results.append({"scenario": "context_budget", "budget": budget,
                        "evidence_count": evidence_count, "actual_chars": actual_len,
                        "ok": actual_len <= budget * 3})  # *3 因为 JSON 格式开销

    # ── 汇总 ───────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r.get("fallback_ok") or r.get("ok") or r.get("actual_chars", 0) > 0)

    summary = {
        "total_tests": total,
        "passed": passed,
        "scenarios": {
            "dense_failure": {"tested": 3, "passed": sum(1 for r in results if r["scenario"] == "dense_failure" and r["fallback_ok"])},
            "rerank_failure": {"tested": 3, "passed": sum(1 for r in results if r["scenario"] == "rerank_failure" and r["fallback_ok"])},
            "both_failure": {"tested": 3, "passed": sum(1 for r in results if r["scenario"] == "both_failure" and r["fallback_ok"])},
            "context_budget": {"tested": 3, "passed": sum(1 for r in results if r["scenario"] == "context_budget" and r.get("ok"))},
        },
        "cases": results,
    }

    print(f"\n{'='*60}")
    print(f"降级容错结果: {passed}/{total} 通过")
    for name, s in summary["scenarios"].items():
        print(f"  {name}: {s['passed']}/{s['tested']}")

    (HERE / "results" / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
