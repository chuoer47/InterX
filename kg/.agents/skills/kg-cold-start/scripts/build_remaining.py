"""Rebuild remaining manuals that have structural nodes but no Question/CO_EVIDENCE edges.

Processes one manual at a time, opening and closing Kùzu connections to avoid
the buffer manager memory leak that occurs when too many databases are open.

Usage:
    python build_remaining.py \
        --graph-dir InterX/kg/state/graph.db \
        --evidence InterX/kg/state/evidence_mapped.json \
        --process-dir InterX/process/artifacts/manuals
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / "src"))
import kuzu


def _exec(conn: kuzu.Connection, query: str, params: dict[str, Any] | None = None) -> None:
    try:
        conn.execute(query, parameters=params or {})
    except RuntimeError as exc:
        if "already exists" in str(exc).lower() or "exist" in str(exc).lower():
            return
        raise


def _merge_node(conn: kuzu.Connection, label: str, node_id: str, props: dict[str, Any]) -> None:
    for key, val in props.items():
        pname = f"p_{key}"
        conn.execute(
            f"MERGE (n:{label} {{id: $id}}) SET n.{key}=${pname}",
            parameters={"id": node_id, pname: val},
        )


def init_schema(conn: kuzu.Connection) -> None:
    stmts = [
        "CREATE NODE TABLE IF NOT EXISTS Manual(id STRING, name STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE IF NOT EXISTS BigChunk(id STRING, manual_id STRING, section_title STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE IF NOT EXISTS MidChunk(id STRING, manual_id STRING, big_chunk_id STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE IF NOT EXISTS SmallChunk(id STRING, manual_id STRING, mid_chunk_id STRING, txt STRING, section_title STRING, PRIMARY KEY(id))",
        "CREATE NODE TABLE IF NOT EXISTS Question(id STRING, question_text STRING, answer_text STRING, lang STRING, manual_guess STRING, PRIMARY KEY(id))",
        "CREATE REL TABLE IF NOT EXISTS HAS_BIG(FROM Manual TO BigChunk)",
        "CREATE REL TABLE IF NOT EXISTS HAS_MID(FROM BigChunk TO MidChunk)",
        "CREATE REL TABLE IF NOT EXISTS HAS_SMALL(FROM MidChunk TO SmallChunk)",
        "CREATE REL TABLE IF NOT EXISTS ANSWERS(FROM SmallChunk TO Question, weight DOUBLE)",
        "CREATE REL TABLE IF NOT EXISTS CO_EVIDENCE(FROM SmallChunk TO SmallChunk, question_id STRING, weight DOUBLE)",
        "CREATE REL TABLE IF NOT EXISTS SEMANTIC(FROM SmallChunk TO SmallChunk, descr STRING, weight DOUBLE)",
    ]
    for s in stmts:
        _exec(conn, s)


def load_chunks(path: Path) -> list[dict[str, Any]]:
    chunks = []
    if not path.exists():
        return chunks
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def needs_rebuild(db_path: Path) -> bool:
    """Check if a manual needs rebuilding (has structural nodes but no Question nodes)."""
    try:
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)
        r = conn.execute("MATCH (n:Question) RETURN count(*)")
        q = r.get_next()[0]
        conn.close()
        del conn, db
        return q == 0
    except Exception:
        return True


def build_one_manual(
    mid: str,
    db_path: Path,
    evidence_groups: dict[str, list[dict]],
    process_dir: Path,
) -> dict[str, int]:
    """Build Question + ANSWERS + CO_EVIDENCE for one manual.

    Opens and closes the database connection within this function.
    """
    stats = {"questions": 0, "answers_edges": 0, "co_evidence_edges": 0}

    # Load chunks
    manual_dir = process_dir / mid
    small_chunks = load_chunks(manual_dir / "small_chunks.jsonl")
    if not small_chunks:
        return stats

    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    init_schema(conn)

    # Ensure structural nodes exist
    doc_name = small_chunks[0].get("doc_name", mid)
    _merge_node(conn, "Manual", mid, {"name": doc_name})

    mid_chunks = load_chunks(manual_dir / "mid_chunks.jsonl")
    big_chunks = load_chunks(manual_dir / "big_chunks.jsonl")

    seen_big: set[str] = set()
    for bc in big_chunks:
        if bc["chunk_id"] not in seen_big:
            _merge_node(conn, "BigChunk", bc["chunk_id"], {
                "manual_id": mid,
                "section_title": bc.get("section_title", ""),
            })
            seen_big.add(bc["chunk_id"])

    seen_mid: set[str] = set()
    for mc in mid_chunks:
        if mc["chunk_id"] not in seen_mid:
            _merge_node(conn, "MidChunk", mc["chunk_id"], {
                "manual_id": mid,
                "big_chunk_id": mc.get("big_chunk_id", ""),
            })
            seen_mid.add(mc["chunk_id"])

    chunk_ids_in_graph: set[str] = set()
    for sc in small_chunks:
        _merge_node(conn, "SmallChunk", sc["chunk_id"], {
            "manual_id": mid,
            "mid_chunk_id": sc.get("mid_chunk_id", ""),
            "txt": sc.get("text", "")[:2000],
            "section_title": sc.get("section_title", ""),
        })
        chunk_ids_in_graph.add(sc["chunk_id"])
        _exec(conn,
              "MATCH (m:MidChunk {id: $mid}), (s:SmallChunk {id: $sm}) CREATE (m)-[:HAS_SMALL]->(s)",
              {"mid": sc.get("mid_chunk_id", ""), "sm": sc["chunk_id"]})
        _exec(conn,
              "MATCH (b:BigChunk {id: $big}), (m:MidChunk {id: $mid}) CREATE (b)-[:HAS_MID]->(m)",
              {"big": sc.get("big_chunk_id", ""), "mid": sc.get("mid_chunk_id", "")})

    # Find evidence groups for this manual
    manual_groups = {k: v for k, v in evidence_groups.items() if k.startswith(f"{mid}||")}

    upserted_questions: set[str] = set()

    for key, group in manual_groups.items():
        _, aid = key.split("||", 1)

        all_chunk_ids: list[str] = []
        question_text = ""
        lang = ""

        for r in group:
            question_text = r.get("question", question_text)
            lang = r.get("lang", lang)
            for cid in r.get("chunk_ids", []):
                if cid not in all_chunk_ids and cid in chunk_ids_in_graph:
                    all_chunk_ids.append(cid)

        if not all_chunk_ids:
            continue

        q_id = f"q_{aid}"
        if q_id not in upserted_questions:
            _merge_node(conn, "Question", q_id, {
                "question_text": question_text[:2000],
                "answer_text": "",
                "lang": lang,
                "manual_guess": "",
            })
            upserted_questions.add(q_id)
            stats["questions"] += 1

        for cid in all_chunk_ids:
            _exec(conn,
                  "MATCH (s:SmallChunk {id: $cid}), (q:Question {id: $qid}) "
                  "CREATE (s)-[:ANSWERS {weight: 0.5}]->(q)",
                  {"cid": cid, "qid": q_id})
            stats["answers_edges"] += 1

        for i, ca in enumerate(all_chunk_ids):
            for cb in all_chunk_ids[i + 1:]:
                _exec(conn,
                      "MATCH (a:SmallChunk {id: $a}), (b:SmallChunk {id: $b}) "
                      "CREATE (a)-[:CO_EVIDENCE {question_id: $qid, weight: 0.5}]->(b)",
                      {"a": ca, "b": cb, "qid": aid})
                _exec(conn,
                      "MATCH (b:SmallChunk {id: $b}), (a:SmallChunk {id: $a}) "
                      "CREATE (b)-[:CO_EVIDENCE {question_id: $qid, weight: 0.5}]->(a)",
                      {"a": ca, "b": cb, "qid": aid})
                stats["co_evidence_edges"] += 2

    conn.close()
    del conn, db
    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph-dir", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--process-dir", required=True)
    args = parser.parse_args()

    graph_dir = Path(args.graph_dir)
    process_dir = Path(args.process_dir)

    with open(args.evidence, encoding="utf-8") as f:
        evidence_data = json.load(f)

    evidence_groups: dict[str, list[dict]] = defaultdict(list)
    for r in evidence_data["records"]:
        mid = r.get("manual_id")
        aid = r.get("answer_id")
        if mid and aid and r.get("chunk_ids"):
            evidence_groups[f"{mid}||{aid}"].append(r)

    # Find manuals that need rebuild
    to_rebuild = []
    for db_file in sorted(graph_dir.glob("*.kuzu")):
        mid = db_file.stem
        if needs_rebuild(db_file):
            to_rebuild.append((mid, db_file))

    print(f"Manuals to rebuild: {len(to_rebuild)}")

    grand_stats = {"questions": 0, "answers_edges": 0, "co_evidence_edges": 0}
    t0 = time.time()

    for idx, (mid, db_path) in enumerate(to_rebuild):
        t1 = time.time()
        stats = build_one_manual(mid, db_path, evidence_groups, process_dir)
        elapsed = time.time() - t1
        print(f"  [{idx+1}/{len(to_rebuild)}] {mid}: "
              f"Q={stats['questions']}, ANS={stats['answers_edges']}, "
              f"COE={stats['co_evidence_edges']} ({elapsed:.1f}s)")
        for k in grand_stats:
            grand_stats[k] += stats[k]

    total_time = time.time() - t0
    print(f"\n=== Done in {total_time:.0f}s ===")
    print(f"Questions: {grand_stats['questions']}")
    print(f"ANSWERS edges: {grand_stats['answers_edges']}")
    print(f"CO_EVIDENCE edges: {grand_stats['co_evidence_edges']}")


if __name__ == "__main__":
    main()
