#!/usr/bin/env python3
"""KG 扩展效果验证：读取 data/queries.json，输出 results/metrics.json + conclusion.md"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "answer" / "src"))
sys.path.insert(0, str(ROOT / "retrieval" / "src"))
sys.path.insert(0, str(ROOT / "kg" / "src"))

from retrieval import search_hierarchical  # noqa: E402

try:
    from kg.config import KGSettings  # noqa: E402
    from kg.expander import ChunkExpander  # noqa: E402
    KG_AVAILABLE = True
except ImportError:
    KG_AVAILABLE = False

HERE = Path(__file__).resolve().parent


def run() -> dict:
    queries = json.loads((HERE / "data" / "queries.json").read_text())
    results = []

    print("KG 扩展效果验证\n")

    if not KG_AVAILABLE:
        print("  ⚠️  kuzu 未安装，使用已有测试数据")
        existing = ROOT / "kg" / "tests" / "kg_compare_results.json"
        if existing.exists():
            for item in json.loads(existing.read_text()):
                print(f"  [{item['label']}] {item['time_s']:.1f}s, hits={item['small_hits']}, kg={item['kg_expansion']}")
                results.append(item)
        summary = {"kg_available": False, "source": "kg_compare_results.json", "cases": results}
    else:
        settings = KGSettings.load()
        expander = ChunkExpander(settings)

        print(f"{'查询':<40} {'无KG':>6} {'有KG':>6} {'扩展':>5}")
        print("-" * 70)

        for q_info in queries:
            query = q_info["query"]
            t0 = time.monotonic()
            r_base = search_hierarchical(query, top_k=20)
            t_base = time.monotonic() - t0
            base_count = len(r_base.small_hits)
            base_ids = {h.chunk_id for h in r_base.small_hits}

            t0 = time.monotonic()
            try:
                expansion = expander.expand([h.to_dict() for h in r_base.small_hits], max_expanded=8)
                new_count = sum(1 for h in expansion.expanded_hits if h.get("chunk_id") not in base_ids)
            except Exception:
                new_count = 0
            t_kg = time.monotonic() - t0

            sq = query[:38] + ".." if len(query) > 40 else query
            print(f"  {sq:<40} {base_count:>5}  {base_count+new_count:>5}  {new_count:>4}")
            results.append({"query": query, "base_hits": base_count, "kg_expanded": new_count,
                            "has_effect": new_count > 0, "retrieval_s": round(t_base, 2), "kg_s": round(t_kg, 2)})
        expander.close()

        effective = sum(1 for r in results if r["has_effect"])
        total = len(results)
        summary = {"kg_available": True, "total": total, "effective": effective,
                   "effectiveness_pct": round(effective / total * 100, 1),
                   "avg_expansion": round(sum(r["kg_expanded"] for r in results) / total, 1),
                   "cases": results}

    (HERE / "results" / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n有效率: {summary.get('effectiveness_pct', 'N/A')}%")
    print(f"结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
