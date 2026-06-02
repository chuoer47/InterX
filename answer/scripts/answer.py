#!/usr/bin/env python3
"""CLI tool for answering a single question."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from answer.config import QASettings
from answer.pipeline import answer


def main() -> None:
    parser = argparse.ArgumentParser(description="Answer a question using the multi-granularity pipeline.")
    parser.add_argument("question", help="User question.")
    parser.add_argument("--config", default=None, help="Config YAML path.")
    parser.add_argument("--top-k", type=int, default=None, help="Retrieval top_k.")
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    args = parser.parse_args()

    settings = QASettings.load(args.config)
    result = answer(args.question, settings=settings, top_k=args.top_k)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return

    print(f"Question: {result.question}")
    print(f"Time: {result.elapsed_seconds:.1f}s")
    print(
        f"Recall: {result.recall_meta.small_hit_count} small, "
        f"{result.recall_meta.mid_hit_count} mid, "
        f"{result.recall_meta.big_hit_count} big"
    )
    if result.recall_meta.rewritten_queries:
        print(f"Rewrites: {result.recall_meta.rewritten_queries}")
    print(f"\n--- Small answer ---\n{result.small_answer.answer.content}")
    print(f"\n--- Mid answer ---\n{result.mid_answer.answer.content}")
    print(f"\n--- Big answer ---\n{result.big_answer.answer.content}")
    print(f"\n--- Final (ensemble) ---\n{result.final_answer.content}")
    if result.final_answer.images:
        print(f"\nImages: {result.final_answer.images}")


if __name__ == "__main__":
    main()
