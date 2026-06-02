#!/usr/bin/env python3
"""语义缓存验证：测试两级缓存逻辑（精确匹配 + 语义等价判断）。

不依赖 Docker/Redis，直接测试缓存逻辑的正确性。
"""
from __future__ import annotations

import json
import sys
import time
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

# ── 模拟缓存逻辑（从 main.py 提取） ─────────────────────
def exact_key(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(text.encode("utf-8")).hexdigest()


def summarize_messages(messages: list[dict]) -> str:
    parts = []
    for msg in messages[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            flattened = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    flattened.append(item.get("text", ""))
                elif isinstance(item, dict):
                    flattened.append(f"<{item.get('type','item')}>")
            content = " ".join(flattened)
        parts.append(f"{role}: {content}")
    return "\n".join(parts)[:4000]


# ── 测试数据 ─────────────────────────────────────────────
TEST_CASES = [
    {
        "name": "精确匹配：完全相同的请求",
        "request_a": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "request_b": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "expect_exact": True,
        "expect_semantic": True,
    },
    {
        "name": "精确不匹配：同义改写",
        "request_a": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "request_b": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "如何清洁空调的过滤网？"}]},
        "expect_exact": False,
        "expect_semantic": True,
    },
    {
        "name": "精确不匹配：跨语言",
        "request_a": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "How to clean the air conditioner filter?"}]},
        "request_b": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调滤网怎么清洗？"}]},
        "expect_exact": False,
        "expect_semantic": True,
    },
    {
        "name": "精确不匹配：完全不同的问题",
        "request_a": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "request_b": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "你们的退货政策是什么？"}]},
        "expect_exact": False,
        "expect_semantic": False,
    },
    {
        "name": "精确不匹配：不同模型",
        "request_a": {"model": "qwen3.6-plus", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "request_b": {"model": "mimo-v2.5-pro", "messages": [{"role": "user", "content": "空调怎么清洗滤网？"}]},
        "expect_exact": False,
        "expect_semantic": False,
    },
    {
        "name": "精确不匹配：多轮对话中最后一条不同",
        "request_a": {"model": "qwen3.6-plus", "messages": [
            {"role": "user", "content": "空调制冷差"},
            {"role": "assistant", "content": "请检查滤网..."},
            {"role": "user", "content": "滤网怎么拆？"},
        ]},
        "request_b": {"model": "qwen3.6-plus", "messages": [
            {"role": "user", "content": "空调制冷差"},
            {"role": "assistant", "content": "请检查滤网..."},
            {"role": "user", "content": "滤网在哪里？"},
        ]},
        "expect_exact": False,
        "expect_semantic": True,
    },
]


def run() -> dict:
    print("语义缓存验证\n")
    print("=" * 70)

    results = []

    for tc in TEST_CASES:
        key_a = exact_key(tc["request_a"])
        key_b = exact_key(tc["request_b"])
        exact_match = key_a == key_b

        summary_a = summarize_messages(tc["request_a"]["messages"])
        summary_b = summarize_messages(tc["request_b"]["messages"])

        print(f"\n【{tc['name']}】")
        print(f"  请求 A: {tc['request_a']['messages'][-1]['content'][:50]}")
        print(f"  请求 B: {tc['request_b']['messages'][-1]['content'][:50]}")
        print(f"  精确匹配: {'✅' if exact_match == tc['expect_exact'] else '❌'} (实际={exact_match}, 期望={tc['expect_exact']})")

        results.append({
            "name": tc["name"],
            "exact_match": exact_match,
            "expected_exact": tc["expect_exact"],
            "exact_correct": exact_match == tc["expect_exact"],
            "expected_semantic": tc["expect_semantic"],
            "key_a": key_a[:16] + "...",
            "key_b": key_b[:16] + "...",
            "summary_a_length": len(summary_a),
            "summary_b_length": len(summary_b),
        })

    # 统计
    total = len(results)
    exact_correct = sum(1 for r in results if r["exact_correct"])

    print(f"\n{'='*70}")
    print(f"精确匹配逻辑: {exact_correct}/{total} 正确")
    print(f"语义匹配: 需要 LLM 在线测试（当前为离线逻辑验证）")

    summary = {
        "total": total,
        "exact_correct": exact_correct,
        "exact_accuracy_pct": round(exact_correct / total * 100, 1),
        "note": "语义匹配需要 LLM 在线测试，当前仅验证精确匹配逻辑",
        "cases": results,
    }

    (HERE / "results" / "metrics.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\n结果已写入 results/")
    return summary


if __name__ == "__main__":
    run()
