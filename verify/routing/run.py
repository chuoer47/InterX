#!/usr/bin/env python3
"""路由准确率验证：读取 data/test_cases.json，输出 results/metrics.json + conclusion.md"""
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
from answer.router import route_question  # noqa: E402

HERE = Path(__file__).resolve().parent


def run() -> dict:
    settings = QASettings.load()
    cases = json.loads((HERE / "data" / "test_cases.json").read_text())
    results = []

    print(f"路由准确率验证 — {len(cases)} 条测试用例\n")

    for c in cases:
        q, expected_manual = c["question"], c["label"]
        t0 = time.monotonic()
        try:
            is_manual = route_question(q, settings=settings)
        except Exception:
            is_manual = True
        elapsed = time.monotonic() - t0

        matched = is_manual == expected_manual
        label = "manual" if is_manual else "general"
        expected_label = "manual" if expected_manual else "general"
        mark = "✅" if matched else "❌"
        print(f"  {mark} [{label:7s}] (期望 {expected_label:7s}) {elapsed:.1f}s | {q}")
        results.append({"question": q, "expected": expected_label, "actual": label,
                        "correct": matched, "latency_s": round(elapsed, 2)})

    correct = sum(1 for r in results if r["correct"])
    total = len(results)
    accuracy = correct / total * 100

    general_c = sum(1 for r, c in zip(results, cases) if not c["label"] and r["correct"])
    manual_c = sum(1 for r, c in zip(results, cases) if c["label"] and r["correct"])
    general_t = sum(1 for c in cases if not c["label"])
    manual_t = sum(1 for c in cases if c["label"])

    summary = {
        "total": total, "correct": correct, "accuracy_pct": round(accuracy, 1),
        "general_accuracy_pct": round(general_c / general_t * 100, 1),
        "manual_accuracy_pct": round(manual_c / manual_t * 100, 1),
        "avg_latency_s": round(sum(r["latency_s"] for r in results) / total, 2),
        "cases": results,
    }

    print(f"\n{'='*50}")
    print(f"总准确率: {correct}/{total} ({accuracy:.1f}%)")
    print(f"通用: {general_c}/{general_t} ({summary['general_accuracy_pct']}%)")
    print(f"产品: {manual_c}/{manual_t} ({summary['manual_accuracy_pct']}%)")

    (HERE / "results" / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    (HERE / "results" / "conclusion.md").write_text(
        f"# 路由准确率验证\n\n"
        f"**总准确率：{accuracy:.1f}%（{correct}/{total}）**\n\n"
        f"| 分类 | 准确率 |\n|------|--------|\n"
        f"| 通用问题 | {summary['general_accuracy_pct']}%（{general_c}/{general_t}） |\n"
        f"| 产品问题 | {summary['manual_accuracy_pct']}%（{manual_c}/{manual_t}） |\n\n"
        f"平均延迟：{summary['avg_latency_s']}s\n")
    print(f"结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
