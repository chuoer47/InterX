"""Write cold-start knowledge graph to Kùzu from resolved evidence data.

Creates Question nodes, CO_EVIDENCE edges (from co-occurrence), and
optionally SEMANTIC edges (from LLM output).

Usage:
    # Build graph from evidence
    python write_graph.py build \
        --evidence InterX/kg/state/evidence_mapped.json \
        --graph-dir InterX/kg/state/graph.db \
        --process-dir InterX/process/artifacts/manuals

    # Optionally add LLM-extracted semantic edges
    python write_graph.py enrich \
        --graph-dir InterX/kg/state/graph.db \
        --semantic InterX/kg/state/semantic_edges.json

    # Print stats
    python write_graph.py stats --graph-dir InterX/kg/state/graph.db
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add kg package to path so we can import GraphStore
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))
import kuzu


def _exec(conn: kuzu.Connection, query: str, params: dict[str, Any] | None = None) -> None:
    """Execute a query, ignoring 'already exists' errors."""
    try:
        conn.execute(query, parameters=params or {})
    except RuntimeError as exc:
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            return
        raise


def _merge_node(conn: kuzu.Connection, label: str, node_id: str, props: dict[str, Any]) -> None:
    """Upsert a node with one MERGE per property (Kùzu workaround)."""
    for key, val in props.items():
        pname = f"p_{key}"
        conn.execute(
            f"MERGE (n:{label} {{id: $id}}) SET n.{key}=${pname}",
            parameters={"id": node_id, pname: val},
        )


class ColdStartGraphStore:
    """Graph store for cold-start KG building.

    Extends the base schema with Question nodes and CO_EVIDENCE/ANSWERS edges.
    Each manual gets its own Kùzu database file.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._dbs: dict[str, kuzu.Database] = {}
        self._conns: dict[str, kuzu.Connection] = {}

    def _db_path(self, manual_id: str) -> Path:
        return self._root / f"{manual_id}.kuzu"

    def _get_conn(self, manual_id: str) -> kuzu.Connection:
        if manual_id in self._conns:
            return self._conns[manual_id]
        db = kuzu.Database(self._db_path(manual_id))
        conn = kuzu.Connection(db)
        self._init_schema(conn)
        self._dbs[manual_id] = db
        self._conns[manual_id] = conn
        return conn

    def _init_schema(self, conn: kuzu.Connection) -> None:
        """Create all node and relation tables."""
        stmts = [
            # Structural nodes
            "CREATE NODE TABLE IF NOT EXISTS Manual(id STRING, name STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS BigChunk(id STRING, manual_id STRING, section_title STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS MidChunk(id STRING, manual_id STRING, big_chunk_id STRING, PRIMARY KEY(id))",
            "CREATE NODE TABLE IF NOT EXISTS SmallChunk(id STRING, manual_id STRING, mid_chunk_id STRING, txt STRING, section_title STRING, PRIMARY KEY(id))",
            # Question node (from agentic-rag)
            "CREATE NODE TABLE IF NOT EXISTS Question(id STRING, question_text STRING, answer_text STRING, lang STRING, manual_guess STRING, PRIMARY KEY(id))",
            # Structural edges
            "CREATE REL TABLE IF NOT EXISTS HAS_BIG(FROM Manual TO BigChunk)",
            "CREATE REL TABLE IF NOT EXISTS HAS_MID(FROM BigChunk TO MidChunk)",
            "CREATE REL TABLE IF NOT EXISTS HAS_SMALL(FROM MidChunk TO SmallChunk)",
            # Evidence edges
            "CREATE REL TABLE IF NOT EXISTS ANSWERS(FROM SmallChunk TO Question, weight DOUBLE)",
            "CREATE REL TABLE IF NOT EXISTS CO_EVIDENCE(FROM SmallChunk TO SmallChunk, question_id STRING, weight DOUBLE)",
            # LLM-extracted semantic edges
            "CREATE REL TABLE IF NOT EXISTS SEMANTIC(FROM SmallChunk TO SmallChunk, descr STRING, weight DOUBLE)",
        ]
        for s in stmts:
            _exec(conn, s)

    # ── Write methods ─────────────────────────────────────────────────

    def upsert_manual(self, manual_id: str, name: str) -> None:
        conn = self._get_conn(manual_id)
        _merge_node(conn, "Manual", manual_id, {"name": name})

    def upsert_small_chunk(self, manual_id: str, chunk: dict[str, Any]) -> None:
        conn = self._get_conn(manual_id)
        _merge_node(conn, "SmallChunk", chunk["chunk_id"], {
            "manual_id": manual_id,
            "mid_chunk_id": chunk.get("mid_chunk_id", ""),
            "txt": chunk.get("text", "")[:2000],
            "section_title": chunk.get("section_title", ""),
        })

    def upsert_mid_chunk(self, manual_id: str, chunk_id: str, big_chunk_id: str) -> None:
        conn = self._get_conn(manual_id)
        _merge_node(conn, "MidChunk", chunk_id, {
            "manual_id": manual_id,
            "big_chunk_id": big_chunk_id,
        })

    def upsert_big_chunk(self, manual_id: str, chunk_id: str, section_title: str) -> None:
        conn = self._get_conn(manual_id)
        _merge_node(conn, "BigChunk", chunk_id, {
            "manual_id": manual_id,
            "section_title": section_title,
        })

    def upsert_question(self, manual_id: str, q_id: str, question: str, answer: str, lang: str, manual_guess: str) -> None:
        conn = self._get_conn(manual_id)
        _merge_node(conn, "Question", q_id, {
            "question_text": question[:2000],
            "answer_text": answer[:4000],
            "lang": lang,
            "manual_guess": manual_guess,
        })

    def link_answers(self, manual_id: str, chunk_id: str, question_id: str) -> None:
        """Create ANSWERS edge: SmallChunk → Question."""
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (s:SmallChunk {id: $cid}), (q:Question {id: $qid}) "
              "CREATE (s)-[:ANSWERS {weight: 0.5}]->(q)",
              {"cid": chunk_id, "qid": question_id})

    def link_co_evidence(self, manual_id: str, chunk_a: str, chunk_b: str, question_id: str) -> None:
        """Create CO_EVIDENCE edge between two chunks (bidirectional)."""
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (a:SmallChunk {id: $a}), (b:SmallChunk {id: $b}) "
              "CREATE (a)-[:CO_EVIDENCE {question_id: $qid, weight: 0.5}]->(b)",
              {"a": chunk_a, "b": chunk_b, "qid": question_id})
        # Reverse direction for undirected traversal
        _exec(conn,
              "MATCH (b:SmallChunk {id: $b}), (a:SmallChunk {id: $a}) "
              "CREATE (b)-[:CO_EVIDENCE {question_id: $qid, weight: 0.5}]->(a)",
              {"a": chunk_a, "b": chunk_b, "qid": question_id})

    def link_semantic(self, manual_id: str, chunk_a: str, chunk_b: str, description: str) -> None:
        """Create SEMANTIC edge (from LLM extraction, bidirectional)."""
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (a:SmallChunk {id: $a}), (b:SmallChunk {id: $b}) "
              "CREATE (a)-[:SEMANTIC {descr: $d, weight: 1.0}]->(b)",
              {"a": chunk_a, "b": chunk_b, "d": description[:500]})
        _exec(conn,
              "MATCH (b:SmallChunk {id: $b}), (a:SmallChunk {id: $a}) "
              "CREATE (b)-[:SEMANTIC {descr: $d, weight: 1.0}]->(a)",
              {"a": chunk_a, "b": chunk_b, "d": description[:500]})

    def link_hierarchy(self, manual_id: str, small_id: str, mid_id: str, big_id: str) -> None:
        """Link chunk hierarchy: BigChunk → MidChunk → SmallChunk."""
        conn = self._get_conn(manual_id)
        _exec(conn,
              "MATCH (m:MidChunk {id: $mid}), (s:SmallChunk {id: $sm}) "
              "CREATE (m)-[:HAS_SMALL]->(s)",
              {"mid": mid_id, "sm": small_id})
        _exec(conn,
              "MATCH (b:BigChunk {id: $big}), (m:MidChunk {id: $mid}) "
              "CREATE (b)-[:HAS_MID]->(m)",
              {"big": big_id, "mid": mid_id})

    # ── Stats ─────────────────────────────────────────────────────────

    def count_all(self, manual_id: str) -> dict[str, int]:
        """Count nodes and edges for one manual."""
        conn = self._get_conn(manual_id)
        counts: dict[str, int] = {}
        for label in ("SmallChunk", "MidChunk", "BigChunk", "Manual", "Question"):
            try:
                r = conn.execute(f"MATCH (n:{label}) RETURN count(*)")
                counts[label] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[label] = 0
        for rel in ("HAS_SMALL", "HAS_MID", "HAS_BIG", "ANSWERS", "CO_EVIDENCE", "SEMANTIC"):
            try:
                r = conn.execute(f"MATCH ()-[r:{rel}]->() RETURN count(*)")
                counts[rel] = r.get_next()[0] if r.has_next() else 0
            except Exception:
                counts[rel] = 0
        return counts

    def list_manuals(self) -> list[str]:
        """List all manual databases in the graph directory."""
        manuals: list[str] = []
        for p in sorted(self._root.iterdir()):
            if p.is_file() and p.suffix == ".kuzu":
                manuals.append(p.stem)
        return manuals

    def close_all(self) -> None:
        """Close all open connections."""
        self._conns.clear()
        self._dbs.clear()

    def close_manual(self, manual_id: str) -> None:
        """Close connection for a specific manual."""
        self._conns.pop(manual_id, None)
        self._dbs.pop(manual_id, None)


# ── CLI commands ──────────────────────────────────────────────────────

def load_chunks_for_manual(manual_dir: Path, chunk_type: str = "small") -> list[dict[str, Any]]:
    """Load chunks from a jsonl file."""
    path = manual_dir / f"{chunk_type}_chunks.jsonl"
    chunks: list[dict[str, Any]] = []
    if not path.exists():
        return chunks
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def cmd_build(args: argparse.Namespace) -> None:
    """Build cold-start graph from evidence data."""
    evidence_path = Path(args.evidence)
    graph_dir = Path(args.graph_dir)
    process_dir = Path(args.process_dir)

    with open(evidence_path, encoding="utf-8") as f:
        evidence_data = json.load(f)
    records = evidence_data["records"]

    store = ColdStartGraphStore(graph_dir)

    # Group records by manual_id + answer_id to process per-answer
    from collections import defaultdict
    answer_groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        mid = r.get("manual_id")
        aid = r.get("answer_id")
        if mid and aid and r.get("chunk_ids"):
            key = f"{mid}||{aid}"
            answer_groups[key].append(r)

    # Track which chunks have been upserted
    upserted_chunks: dict[str, set[str]] = defaultdict(set)
    upserted_questions: set[str] = set()

    stats = {
        "manuals": set(),
        "questions": 0,
        "answers_edges": 0,
        "co_evidence_edges": 0,
        "chunks_upserted": 0,
    }

    # Collect all manuals
    for key, group in answer_groups.items():
        mid, aid = key.split("||", 1)
        stats["manuals"].add(mid)

    # Phase 1: Create structural nodes FIRST for all manuals
    print("Phase 1: Creating structural nodes...")
    for mid in stats["manuals"]:
        manual_dir = process_dir / mid
        small_chunks = load_chunks_for_manual(manual_dir, "small")
        mid_chunks = load_chunks_for_manual(manual_dir, "mid")
        big_chunks = load_chunks_for_manual(manual_dir, "big")

        if small_chunks:
            doc_name = small_chunks[0].get("doc_name", mid)
            store.upsert_manual(mid, doc_name)

            seen_big: set[str] = set()
            seen_mid: set[str] = set()

            for bc in big_chunks:
                if bc["chunk_id"] not in seen_big:
                    store.upsert_big_chunk(mid, bc["chunk_id"], bc.get("section_title", ""))
                    seen_big.add(bc["chunk_id"])
            for mc in mid_chunks:
                if mc["chunk_id"] not in seen_mid:
                    store.upsert_mid_chunk(mid, mc["chunk_id"], mc.get("big_chunk_id", ""))
                    seen_mid.add(mc["chunk_id"])

            for sc in small_chunks:
                store.upsert_small_chunk(mid, sc)
                upserted_chunks[mid].add(sc["chunk_id"])
                store.link_hierarchy(mid, sc["chunk_id"], sc.get("mid_chunk_id", ""), sc.get("big_chunk_id", ""))

            stats["chunks_upserted"] += len(small_chunks)
            print(f"  {mid}: {len(small_chunks)} small, {len(mid_chunks)} mid, {len(big_chunks)} big")
            
            # Close connection to free resources
            store.close_manual(mid)

    # Phase 2: Create Question nodes and edges
    print("\nPhase 2: Creating Question nodes and edges...")
    print(f"  Total answer groups: {len(answer_groups)}")
    for key, group in answer_groups.items():
        mid, aid = key.split("||", 1)

        all_chunk_ids: list[str] = []
        question_text = ""
        answer_text = ""
        lang = ""
        manual_guess = ""

        for r in group:
            question_text = r.get("question", question_text)
            lang = r.get("lang", lang)
            for cid in r.get("chunk_ids", []):
                if cid not in all_chunk_ids:
                    all_chunk_ids.append(cid)

        q_id = f"q_{aid}"
        if q_id not in upserted_questions:
            try:
                store.upsert_question(mid, q_id, question_text, answer_text, lang, manual_guess)
                upserted_questions.add(q_id)
                stats["questions"] += 1
            except Exception as e:
                print(f"  ERROR upserting question {q_id}: {e}")

        for cid in all_chunk_ids:
            try:
                store.link_answers(mid, cid, q_id)
                stats["answers_edges"] += 1
            except Exception as e:
                print(f"  ERROR linking answer {cid} -> {q_id}: {e}")

        for i, ca in enumerate(all_chunk_ids):
            for cb in all_chunk_ids[i + 1:]:
                try:
                    store.link_co_evidence(mid, ca, cb, aid)
                    stats["co_evidence_edges"] += 1
                except Exception as e:
                    print(f"  ERROR linking co_evidence {ca} <-> {cb}: {e}")

    store.close_all()

    print(f"\n=== Build Complete ===")
    print(f"Manuals: {len(stats['manuals'])}")
    print(f"Questions: {stats['questions']}")
    print(f"Chunks upserted: {stats['chunks_upserted']}")
    print(f"ANSWERS edges: {stats['answers_edges']}")
    print(f"CO_EVIDENCE edges: {stats['co_evidence_edges']}")


def cmd_enrich(args: argparse.Namespace) -> None:
    """Add LLM-extracted SEMANTIC edges to existing graph."""
    graph_dir = Path(args.graph_dir)
    semantic_path = Path(args.semantic)

    with open(semantic_path, encoding="utf-8") as f:
        semantic_data = json.load(f)

    store = ColdStartGraphStore(graph_dir)
    count = 0

    for edge in semantic_data.get("edges", []):
        mid = edge.get("manual_id")
        ca = edge.get("chunk_a")
        cb = edge.get("chunk_b")
        desc = edge.get("description", "")
        if mid and ca and cb and edge.get("has_semantic"):
            store.link_semantic(mid, ca, cb, desc)
            count += 1

    store.close_all()
    print(f"Added {count} SEMANTIC edges")


def cmd_stats(args: argparse.Namespace) -> None:
    """Print graph statistics."""
    graph_dir = Path(args.graph_dir)
    store = ColdStartGraphStore(graph_dir)
    manuals = store.list_manuals()

    if not manuals:
        print("No graph databases found")
        return

    grand_total: dict[str, int] = {}
    for mid in manuals:
        counts = store.count_all(mid)
        print(f"\n--- {mid} ---")
        for k, v in sorted(counts.items()):
            print(f"  {k}: {v}")
            grand_total[k] = grand_total.get(k, 0) + v

    print(f"\n=== Grand Total ({len(manuals)} manuals) ===")
    for k, v in sorted(grand_total.items()):
        print(f"  {k}: {v}")

    store.close_all()


def main():
    parser = argparse.ArgumentParser(description="Cold-start KG graph writer")
    sub = parser.add_subparsers(dest="command")

    # build subcommand
    p_build = sub.add_parser("build", help="Build graph from evidence data")
    p_build.add_argument("--evidence", required=True)
    p_build.add_argument("--graph-dir", required=True)
    p_build.add_argument("--process-dir", required=True)

    # enrich subcommand
    p_enrich = sub.add_parser("enrich", help="Add SEMANTIC edges from LLM output")
    p_enrich.add_argument("--graph-dir", required=True)
    p_enrich.add_argument("--semantic", required=True)

    # stats subcommand
    p_stats = sub.add_parser("stats", help="Print graph statistics")
    p_stats.add_argument("--graph-dir", required=True)

    args = parser.parse_args()
    if args.command == "build":
        cmd_build(args)
    elif args.command == "enrich":
        cmd_enrich(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
