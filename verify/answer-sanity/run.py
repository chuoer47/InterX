#!/usr/bin/env python3
"""回答质量抽样验证：读取 data/samples.json，输出 results/metrics.json + conclusion.md"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "answer" / "src"))
sys.path.insert(0, str(ROOT / "retrieval" / "src"))
sys.path.insert(0, str(ROOT / "kg" / "src"))

from answer.config import QASettings  # noqa: E402
from answer.pipeline import answer  # noqa: E402

HERE = Path(__file__).resolve().parent


def run() -> dict:
    settings = QASettings.load()
    samples = json.loads((HERE / "data" / "samples.json").read_text())
    results = []

    print(f"回答质量验证 — {len(samples)} 个样本\n")

    for i, s in enumerate(samples):
        q = s["question"]
        print(f"--- 样本 {i+1}: {q} ---")
        t0 = time.monotonic()
        try:
            result = answer(q, settings=settings)
            success = True
        except Exception as e:
            result = None
            success = False
            print(f"  ❌ 错误: {e}")
        elapsed = time.monotonic() - t0

        if not success:
            results.append({"question": q, "type": s["type"], "success": False})
            continue

        content = result.final_answer.content
        images = result.final_answer.images
        content_lower = content.lower()

        checks = {
            "has_content": len(content) > 0,
            "has_answer": len(content) > 20,
            "no_markdown": not any(x in content for x in ["## ", "```"]),
            "images_format": isinstance(images, list),
            "content_length_ok": 50 < len(content) < 5000,
            "has_keywords": any(kw.lower() in content_lower for kw in s["expect_keywords"]),
        }
        passed = sum(checks.values())

        mark = "✅" if all(checks.values()) else "⚠️"
        print(f"  {mark} 检查: {passed}/{len(checks)} | {len(content)} 字符 | {len(images)} 图片 | {elapsed:.1f}s")

        layers = {}
        for level in ["small_answer", "mid_answer", "big_answer"]:
            if hasattr(result, level):
                la = getattr(result, level)
                layers[level] = {"length": len(la.answer.content), "context_chars": len(la.context_text)}

        results.append({"question": q, "type": s["type"], "success": True,
                        "total_time_s": round(elapsed, 1), "answer_length": len(content),
                        "image_count": len(images), "checks": checks,
                        "checks_passed": passed, "layers": layers})

    success_count = sum(1 for r in results if r.get("success"))
    all_pass = sum(1 for r in results if r.get("success") and r.get("checks_passed") == len(r.get("checks", {})))

    summary = {"total": len(results), "success": success_count, "all_checks_pass": all_pass, "cases": results}

    (HERE / "results" / "metrics.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n成功率: {success_count}/{len(results)}, 全检查通过: {all_pass}/{len(results)}")
    print(f"结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
