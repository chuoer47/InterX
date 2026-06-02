#!/usr/bin/env python3
"""CLI tool for searching the retrieval index."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.context import assemble_context
from retrieval.retriever import reload, search as search_fn, search_hierarchical


def main() -> None:
    parser = argparse.ArgumentParser(description="Search InterX retrieval index.")
    parser.add_argument("query", help="Search query.")
    parser.add_argument("--top-k", type=int, default=None, help="Number of results.")
    parser.add_argument("--config", default=None, help="Config YAML path.")
    parser.add_argument("--level", choices=["small", "mid", "big", "all"], default="small", help="Return hits at this granularity level.")
    parser.add_argument("--no-rerank", action="store_true", help="Disable reranking.")
    parser.add_argument("--filter", default=None, help='Milvus filter expression, e.g. doc_name == "Canon EOS 20D".')
    parser.add_argument("--json", action="store_true", help="Output raw JSON.")
    parser.add_argument("--context", action="store_true", help="Output assembled LLM context.")
    parser.add_argument("--context-tokens", type=int, default=12000, help="Max tokens for context assembly.")
    args = parser.parse_args()

    if args.config:
        # Importing settings through the public retriever reload path keeps the CLI
        # behavior aligned with the rest of the package instead of mutating state here.
        import retrieval.config as cfg_mod
        cfg_mod.RetrievalSettings.load(args.config)

    reload()
    started = time.monotonic()

    if args.level == "all":
        result = search_hierarchical(
            args.query,
            top_k=args.top_k,
            filter_expr=args.filter,
            rerank=not args.no_rerank,
        )
        elapsed = time.monotonic() - started

        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Query: {result.query}")
            print(f"Time:  {elapsed:.3f}s")
            print(f"\n--- Big hits ({len(result.big_hits)}) ---")
            for h in result.big_hits:
                print(f"  [{h.rank}] {h.doc_name} > {h.section_title} (score={h.score:.4f}, mids={h.mid_count}, smalls={h.small_count})")
            print(f"\n--- Mid hits ({len(result.mid_hits)}) ---")
            for h in result.mid_hits:
                print(f"  [{h.rank}] {h.doc_name} > {h.section_title} (score={h.score:.4f}, smalls={h.small_count})")
            print(f"\n--- Small hits ({len(result.small_hits)}) ---")
            for h in result.small_hits:
                print(f"  [{h.rank}] {h.doc_name} > {h.section_title} (score={h.score:.4f}, source={h.retrieval_source})")
                print(f"         {h.content[:120]}...")
        return

    hits = search_fn(
        args.query,
        top_k=args.top_k,
        filter_expr=args.filter,
        rerank=not args.no_rerank,
    )
    elapsed = time.monotonic() - started

    if args.json:
        print(json.dumps([h.to_dict() for h in hits], ensure_ascii=False, indent=2))
    elif args.context:
        print(assemble_context(hits, max_tokens=args.context_tokens))
    else:
        print(f"Query: {args.query}")
        print(f"Time:  {elapsed:.3f}s")
        print(f"Results ({len(hits)}):")
        for h in hits:
            print(f"  [{h.rank}] {h.doc_name} > {h.section_title} (score={h.score:.4f}, source={h.retrieval_source})")
            print(f"         {h.content[:120]}...")


if __name__ == "__main__":
    main()
