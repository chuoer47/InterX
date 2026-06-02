#!/usr/bin/env python3
"""CLI: build knowledge graph for one or all manuals."""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg.config import KGSettings
from kg.graph_store import GraphStore
from kg.builder import GraphBuilder


def main() -> None:
    parser = argparse.ArgumentParser(description="Build KG from chunk artifacts")
    parser.add_argument("--manual", "-m", help="Manual ID (omit for all)")
    parser.add_argument("--config", "-c", help="Config file path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = KGSettings.load(args.config)
    store = GraphStore(settings.graph_store.db_path)
    builder = GraphBuilder(settings, store)

    if args.manual:
        reports = [builder.build_manual(args.manual)]
    else:
        reports = builder.build_all()

    for r in reports:
        print(f"\n{'='*60}")
        print(f"Manual:    {r.manual_id}")
        print(f"Chunks:    {r.total_small_chunks}")
        print(f"SPs:       {r.total_semantic_points}")
        print(f"Relations: {r.total_relations}")
        print(f"LLM calls: {r.llm_calls}")
        print(f"Errors:    {len(r.errors)}")
        for e in r.errors:
            print(f"  - {e}")


if __name__ == "__main__":
    main()
