#!/usr/bin/env python3
"""CLI: test graph expansion on a query against a built manual."""
import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg.config import KGSettings
from kg.graph_store import GraphStore
from kg.retriever import GraphRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Test graph expansion")
    parser.add_argument("--manual", "-m", required=True, help="Manual ID")
    parser.add_argument("--chunks", nargs="+", required=True,
                        help="Seed chunk IDs (space-separated)")
    parser.add_argument("--config", "-c", help="Config file path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    settings = KGSettings.load(args.config)
    store = GraphStore(settings.graph_store.db_path)
    retriever = GraphRetriever(settings, store)

    seed_chunks = [{"chunk_id": cid, "doc_id": args.manual, "score": 1.0}
                   for cid in args.chunks]

    result = retriever.expand(seed_chunks, manual_id=args.manual)

    print(f"\nManual: {result.manual_id}")
    print(f"Expanded chunks ({len(result.expanded_chunk_ids)}):")
    for cid in result.expanded_chunk_ids:
        score = result.graph_scores.get(cid, 0.0)
        print(f"  {cid}  (graph_score={score})")

    print(f"\nPaths ({len(result.paths)}):")
    for p in result.paths[:20]:
        print(f"  {p['src_sp']} --[{p.get('rel_chain', ['?'])[0]}]--> {p['dst_sp']}  (hops={p['hops']})")

    stats = retriever.get_stats(args.manual)
    print(f"\nGraph stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
