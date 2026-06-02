"""Write SEMANTIC edges into Kùzu graph, one manual at a time.

Processes one manual at a time, opening/closing Kùzu connections to avoid
the buffer manager memory leak.

Usage:
    python enrich_remaining.py \
        --graph-dir InterX/kg/state/graph.db \
        --semantic InterX/kg/state/semantic_edges.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))
import kuzu


def _exec(conn: kuzu.Connection, query: str, params: dict[str, Any] | None = None) -> None:
    try:
        conn.execute(query, parameters=params or {})
    except RuntimeError as exc:
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            return
        raise


def enrich_one_manual(
    mid: str,
    db_path: Path,
    edges: list[dict],
) -> int:
    """Write SEMANTIC edges for one manual. Returns count of edges written."""
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    # Ensure SEMANTIC rel table exists
    _exec(conn, "CREATE REL TABLE IF NOT EXISTS SEMANTIC(FROM SmallChunk TO SmallChunk, descr STRING, weight DOUBLE)")

    count = 0
    for edge in edges:
        ca = edge["chunk_a"]
        cb = edge["chunk_b"]
        desc = edge.get("description", "")
        _exec(conn,
              "MATCH (a:SmallChunk {id: $a}), (b:SmallChunk {id: $b}) "
              "CREATE (a)-[:SEMANTIC {descr: $d, weight: 1.0}]->(b)",
              {"a": ca, "b": cb, "d": desc[:500]})
        _exec(conn,
              "MATCH (b:SmallChunk {id: $b}), (a:SmallChunk {id: $a}) "
              "CREATE (b)-[:SEMANTIC {descr: $d, weight: 1.0}]->(a)",
              {"a": ca, "b": cb, "d": desc[:500]})
        count += 1

    conn.close()
    del conn, db
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-dir", required=True)
    parser.add_argument("--semantic", required=True)
    args = parser.parse_args()

    graph_dir = Path(args.graph_dir)

    with open(args.semantic, encoding="utf-8") as f:
        semantic_data = json.load(f)

    all_edges = semantic_data.get("edges", [])
    print(f"Total SEMANTIC edges to write: {len(all_edges)}")

    # Group by manual_id
    by_manual: dict[str, list[dict]] = defaultdict(list)
    for e in all_edges:
        by_manual[e["manual_id"]].append(e)

    print(f"Manuals affected: {len(by_manual)}")

    total_written = 0
    for mid, edges in sorted(by_manual.items()):
        db_path = graph_dir / f"{mid}.kuzu"
        if not db_path.exists():
            print(f"  SKIP {mid}: no graph db")
            continue
        written = enrich_one_manual(mid, db_path, edges)
        total_written += written
        print(f"  {mid}: {written} edges written")

    print(f"\nDone: {total_written} SEMANTIC edges written to {len(by_manual)} manuals")


if __name__ == "__main__":
    main()
