"""Tests for knowledge graph retrieval against the built cold-start graph.

These tests run against the actual graph.db built from agentic-rag evidence.
They verify:
  1. Graph structure integrity (node/edge counts)
  2. CO_EVIDENCE traversal (chunk co-occurrence)
  3. SEMANTIC traversal (LLM-confirmed relationships)
  4. Multi-hop expansion scenarios
  5. Hierarchy reconstruction (small → mid → big)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import kuzu
import pytest


# ── Helpers ───────────────────────────────────────────────────────────

GRAPH_DB = Path(__file__).resolve().parent.parent / "state" / "graph.db"


def _get_conn(manual_id: str) -> kuzu.Connection:
    db_path = GRAPH_DB / f"{manual_id}.kuzu"
    if not db_path.exists():
        pytest.skip(f"Graph DB not found: {db_path}")
    db = kuzu.Database(str(db_path))
    return kuzu.Connection(db)


def _query(conn: kuzu.Connection, query: str, params: dict | None = None) -> list[list]:
    """Execute query and return all rows as lists."""
    r = conn.execute(query, parameters=params or {})
    rows = []
    while r.has_next():
        rows.append(r.get_next())
    return rows


def _get_chunk_ids_from_co_evidence(conn: kuzu.Connection, seed_id: str, limit: int = 20) -> list[str]:
    """Get chunk_ids connected to seed via CO_EVIDENCE (1-hop)."""
    rows = _query(conn,
        "MATCH (a:SmallChunk {id: $seed})-[:CO_EVIDENCE]->(b:SmallChunk) "
        "RETURN DISTINCT b.id LIMIT $limit",
        {"seed": seed_id, "limit": limit})
    return [r[0] for r in rows]


def _get_chunk_ids_from_semantic(conn: kuzu.Connection, seed_id: str, limit: int = 20) -> list[str]:
    """Get chunk_ids connected to seed via SEMANTIC (1-hop)."""
    rows = _query(conn,
        "MATCH (a:SmallChunk {id: $seed})-[rel:SEMANTIC]->(b:SmallChunk) "
        "RETURN DISTINCT b.id LIMIT $limit",
        {"seed": seed_id, "limit": limit})
    return [r[0] for r in rows]


def _get_chunk_text(conn: kuzu.Connection, chunk_id: str) -> str:
    rows = _query(conn,
        "MATCH (s:SmallChunk {id: $id}) RETURN s.txt",
        {"id": chunk_id})
    return rows[0][0] if rows else ""


def _get_hierarchy(conn: kuzu.Connection, chunk_id: str) -> dict:
    """Get the mid/big chunk hierarchy for a small chunk."""
    rows = _query(conn,
        "MATCH (m:MidChunk)-[:HAS_SMALL]->(s:SmallChunk {id: $id}) RETURN m.id, m.big_chunk_id",
        {"id": chunk_id})
    if not rows:
        return {}
    mid_id, big_id = rows[0]
    rows2 = _query(conn,
        "MATCH (b:BigChunk {id: $id}) RETURN b.section_title",
        {"id": big_id})
    big_title = rows2[0][0] if rows2 else ""
    return {"mid_chunk_id": mid_id, "big_chunk_id": big_id, "big_title": big_title}


def _expand_2hop(conn: kuzu.Connection, seed_ids: list[str], max_hops: int = 2) -> dict[str, list]:
    """Expand from seed chunks through CO_EVIDENCE and SEMANTIC edges."""
    visited = set(seed_ids)
    frontier = set(seed_ids)
    result = {"hop1": [], "hop2": []}

    for hop in range(1, max_hops + 1):
        next_frontier = set()
        for cid in frontier:
            # CO_EVIDENCE neighbors
            co_rows = _query(conn,
                "MATCH (a:SmallChunk {id: $id})-[:CO_EVIDENCE]->(b:SmallChunk) RETURN DISTINCT b.id",
                {"id": cid})
            # SEMANTIC neighbors
            sem_rows = _query(conn,
                "MATCH (a:SmallChunk {id: $id})-[:SEMANTIC]->(b:SmallChunk) RETURN DISTINCT b.id",
                {"id": cid})

            for row in co_rows + sem_rows:
                nid = row[0]
                if nid not in visited:
                    visited.add(nid)
                    next_frontier.add(nid)
                    result[f"hop{hop}"].append({"chunk_id": nid, "from": cid, "via": "CO_EVIDENCE" if row in co_rows else "SEMANTIC"})

        frontier = next_frontier

    return result


# ── Test: Graph Structure ─────────────────────────────────────────────

class TestGraphStructure:
    """Verify the cold-start graph has expected structure."""

    def test_all_manuals_have_small_chunks(self):
        """Every manual DB should have SmallChunk nodes."""
        for db_file in sorted(GRAPH_DB.glob("*.kuzu")):
            mid = db_file.stem
            conn = _get_conn(mid)
            rows = _query(conn, "MATCH (n:SmallChunk) RETURN count(*)")
            assert rows[0][0] > 0, f"{mid} has no SmallChunk nodes"

    def test_all_manuals_have_manual_node(self):
        """Every manual DB should have exactly 1 Manual node."""
        for db_file in sorted(GRAPH_DB.glob("*.kuzu")):
            mid = db_file.stem
            conn = _get_conn(mid)
            rows = _query(conn, "MATCH (n:Manual) RETURN count(*)")
            assert rows[0][0] == 1, f"{mid} has {rows[0][0]} Manual nodes"

    def test_hierarchy_edges_exist(self):
        """Manuals with mid/big chunks should have HAS_MID and HAS_SMALL edges."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        has_mid = _query(conn, "MATCH ()-[r:HAS_MID]->() RETURN count(*)")[0][0]
        has_small = _query(conn, "MATCH ()-[r:HAS_SMALL]->() RETURN count(*)")[0][0]
        assert has_mid > 0, "No HAS_MID edges"
        assert has_small > 0, "No HAS_SMALL edges"

    def test_co_evidence_edges_exist(self):
        """EN manuals should have CO_EVIDENCE edges."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        count = _query(conn, "MATCH ()-[r:CO_EVIDENCE]->() RETURN count(*)")[0][0]
        assert count > 100, f"Expected many CO_EVIDENCE edges, got {count}"

    def test_semantic_edges_exist(self):
        """At least some manuals should have SEMANTIC edges."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        count = _query(conn, "MATCH ()-[r:SEMANTIC]->() RETURN count(*)")[0][0]
        assert count > 0, "No SEMANTIC edges"

    def test_question_nodes_exist(self):
        """EN manuals should have Question nodes."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        count = _query(conn, "MATCH (n:Question) RETURN count(*)")[0][0]
        assert count > 0, "No Question nodes"

    def test_answers_edges_exist(self):
        """EN manuals should have ANSWERS edges."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        count = _query(conn, "MATCH ()-[r:ANSWERS]->() RETURN count(*)")[0][0]
        assert count > 0, "No ANSWERS edges"


# ── Test: CO_EVIDENCE Traversal ───────────────────────────────────────

class TestCOEvidenceTraversal:
    """Test retrieval through CO_EVIDENCE edges."""

    def test_co_evidence_neighbors_exist(self):
        """A chunk with CO_EVIDENCE edges should have reachable neighbors."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        # Find a chunk that has CO_EVIDENCE edges
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
            "RETURN DISTINCT a.id LIMIT 1")
        assert len(rows) > 0, "No chunks with CO_EVIDENCE edges"
        seed_id = rows[0][0]

        neighbors = _get_chunk_ids_from_co_evidence(conn, seed_id)
        assert len(neighbors) > 0, f"No CO_EVIDENCE neighbors for {seed_id}"

    def test_co_evidence_different_sections(self):
        """CO_EVIDENCE should connect chunks from different sections (cross-chapter)."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
            "WHERE a.section_title <> b.section_title "
            "RETURN a.id, b.id, a.section_title, b.section_title LIMIT 5")
        assert len(rows) > 0, "No cross-section CO_EVIDENCE edges found"

    def test_2hop_via_question(self):
        """Should traverse chunk → ANSWERS → Question → ANSWERS → other chunk (2-hop)."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        # Find a chunk that answers a question
        rows = _query(conn,
            "MATCH (s:SmallChunk)-[:ANSWERS]->(q:Question) "
            "RETURN s.id, q.id LIMIT 1")
        assert len(rows) > 0
        seed_id, q_id = rows[0]

        # Find other chunks that answer the same question
        related = _query(conn,
            "MATCH (s:SmallChunk)-[:ANSWERS]->(q:Question {id: $qid}) "
            "WHERE s.id <> $seed RETURN s.id",
            {"qid": q_id, "seed": seed_id})

        assert len(related) > 0, f"No other chunks answer question {q_id}"

        # Verify the related chunks have CO_EVIDENCE or SEMANTIC edges
        related_id = related[0][0]
        co_exists = _query(conn,
            "MATCH (a:SmallChunk {id: $a})-[:CO_EVIDENCE]->(b:SmallChunk {id: $b}) RETURN a.id",
            {"a": seed_id, "b": related_id})
        assert len(co_exists) > 0, f"No CO_EVIDENCE edge between {seed_id} and {related_id}"


# ── Test: SEMANTIC Traversal ─────────────────────────────────────────

class TestSemanticTraversal:
    """Test retrieval through SEMANTIC edges (LLM-confirmed)."""

    def test_semantic_neighbors_exist(self):
        """A chunk with SEMANTIC edges should have reachable neighbors."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:SEMANTIC]->(b:SmallChunk) "
            "RETURN DISTINCT a.id LIMIT 1")
        assert len(rows) > 0, "No chunks with SEMANTIC edges"
        seed_id = rows[0][0]

        neighbors = _get_chunk_ids_from_semantic(conn, seed_id)
        assert len(neighbors) > 0, f"No SEMANTIC neighbors for {seed_id}"

    def test_semantic_has_description(self):
        """SEMANTIC edges should have a description property."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[r:SEMANTIC]->(b:SmallChunk) "
            "RETURN r.descr LIMIT 5")
        assert len(rows) > 0
        for row in rows:
            assert row[0], "SEMANTIC edge has empty description"

    def test_semantic_different_sections(self):
        """SEMANTIC edges should connect chunks from different sections."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[r:SEMANTIC]->(b:SmallChunk) "
            "WHERE a.section_title <> b.section_title "
            "RETURN a.id, b.id, a.section_title, b.section_title, r.descr LIMIT 3")
        assert len(rows) > 0, "No cross-section SEMANTIC edges"


# ── Test: Multi-hop Expansion ────────────────────────────────────────

class TestMultiHopExpansion:
    """Test realistic multi-hop retrieval scenarios."""

    def test_expand_from_seed(self):
        """Given a seed chunk, expand through graph to find related chunks."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        # Pick a seed chunk
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
            "RETURN DISTINCT a.id LIMIT 1")
        seed_id = rows[0][0]

        result = _expand_2hop(conn, [seed_id], max_hops=2)

        # Should find at least some chunks at hop 1
        assert len(result["hop1"]) > 0, f"No chunks found at hop 1 from {seed_id}"

    def test_expand_multi_seed(self):
        """Multiple seed chunks should discover more related chunks."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        # Get 3 seed chunks
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
            "RETURN DISTINCT a.id LIMIT 3")
        seed_ids = [r[0] for r in rows]

        result = _expand_2hop(conn, seed_ids, max_hops=2)

        # Should find chunks not in seed set
        all_expanded = set()
        for hop_data in result.values():
            for item in hop_data:
                all_expanded.add(item["chunk_id"])

        new_chunks = all_expanded - set(seed_ids)
        assert len(new_chunks) > 0, "No new chunks discovered from multi-seed expansion"

    def test_expand_preserves_hierarchy(self):
        """Expanded chunks should be traceable back to mid/big chunks."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
            "RETURN DISTINCT a.id LIMIT 1")
        seed_id = rows[0][0]

        neighbors = _get_chunk_ids_from_co_evidence(conn, seed_id, limit=5)
        for nid in neighbors:
            hierarchy = _get_hierarchy(conn, nid)
            # Each neighbor should have a mid_chunk_id
            assert hierarchy.get("mid_chunk_id"), f"No hierarchy for {nid}"


# ── Test: Question → Chunk Traversal ─────────────────────────────────

class TestQuestionTraversal:
    """Test retrieval through Question nodes."""

    def test_question_connected_to_chunks(self):
        """Question nodes should be connected to SmallChunks via ANSWERS."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        rows = _query(conn,
            "MATCH (s:SmallChunk)-[:ANSWERS]->(q:Question) "
            "RETURN q.id, q.question_text LIMIT 3")
        assert len(rows) > 0, "No ANSWERS edges found"
        for row in rows:
            assert row[1], f"Question {row[0]} has empty text"

    def test_question_to_related_chunks(self):
        """From a Question, find all chunks that answered it, then their CO_EVIDENCE neighbors."""
        conn = _get_conn("Bosch_Microwave_70767fb09e75")
        # Get a question
        questions = _query(conn, "MATCH (q:Question) RETURN q.id, q.question_text LIMIT 1")
        assert len(questions) > 0
        q_id = questions[0][0]

        # Get chunks that answered this question
        answering_chunks = _query(conn,
            "MATCH (s:SmallChunk)-[:ANSWERS]->(q:Question {id: $qid}) RETURN s.id",
            {"qid": q_id})
        assert len(answering_chunks) > 0

        # From those chunks, find CO_EVIDENCE neighbors
        all_related = set()
        for row in answering_chunks:
            cid = row[0]
            neighbors = _get_chunk_ids_from_co_evidence(conn, cid)
            all_related.update(neighbors)

        # Remove the answering chunks themselves
        answering_ids = {r[0] for r in answering_chunks}
        new_related = all_related - answering_ids
        # Should find additional related chunks
        assert len(new_related) > 0 or len(answering_chunks) > 1, \
            "No additional related chunks found via CO_EVIDENCE"


# ── Test: Cross-manual Consistency ────────────────────────────────────

class TestCrossManualConsistency:
    """Verify consistency across multiple manuals."""

    def test_en_manuals_have_evidence(self):
        """EN manuals (named like Product_Hash) should have CO_EVIDENCE edges."""
        en_manuals = [
            "Bosch_Microwave_70767fb09e75",
            "Canon_EOS_20D_33c91568ab63",
            "Instant_Pot_Duo_Crisp_9233d99d3fae",
        ]
        for mid in en_manuals:
            conn = _get_conn(mid)
            count = _query(conn, "MATCH ()-[r:CO_EVIDENCE]->() RETURN count(*)")[0][0]
            assert count > 0, f"{mid} has no CO_EVIDENCE edges"

    def test_ch_manuals_have_evidence(self):
        """CH manuals (named like manual_hash) should have CO_EVIDENCE edges."""
        ch_manuals = [
            "manual_cea3fea3ecc0",
            "manual_413facd93068",
        ]
        for mid in ch_manuals:
            conn = _get_conn(mid)
            count = _query(conn, "MATCH ()-[r:CO_EVIDENCE]->() RETURN count(*)")[0][0]
            assert count > 0, f"{mid} has no CO_EVIDENCE edges"

    def test_small_chunk_count_matches_process(self):
        """SmallChunk count should match process artifacts."""
        process_dir = Path(__file__).resolve().parent.parent.parent / "process" / "artifacts" / "manuals"
        if not process_dir.exists():
            pytest.skip("Process artifacts not found")

        for db_file in sorted(GRAPH_DB.glob("*.kuzu"))[:5]:
            mid = db_file.stem
            conn = _get_conn(mid)
            graph_count = _query(conn, "MATCH (n:SmallChunk) RETURN count(*)")[0][0]

            chunk_file = process_dir / mid / "small_chunks.jsonl"
            if chunk_file.exists():
                with open(chunk_file) as f:
                    process_count = sum(1 for line in f if line.strip())
                assert graph_count == process_count, \
                    f"{mid}: graph has {graph_count} SmallChunks, process has {process_count}"
