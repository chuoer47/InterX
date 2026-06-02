"""Tests for GraphStore CRUD and traversal."""
from __future__ import annotations

from pathlib import Path

import pytest

from kg.graph_store import GraphStore
from kg.types import SemanticPoint, SemanticRelation


class TestGraphStore:

    def test_init_creates_root(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        assert tmp_root.exists()

    def test_upsert_and_count(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")
        store.upsert_small_chunk(mid, "sc1", "mc1", "Hello world", "Section A")
        store.upsert_mid_chunk(mid, "mc1", "bc1")
        store.upsert_big_chunk(mid, "bc1", "Section A")
        store.link_chunk_hierarchy(mid, "sc1", "mc1", "bc1")

        counts = store.count_nodes(mid)
        assert counts["SmallChunk"] == 1
        assert counts["MidChunk"] == 1
        assert counts["BigChunk"] == 1

    def test_semantic_point_and_relation(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")

        sp1 = SemanticPoint(sp_id="sp1", point_type="symptom", label="WiFi fails",
                            description="Connection failure", manual_id=mid)
        sp2 = SemanticPoint(sp_id="sp2", point_type="cause", label="Permission off",
                            description="Network permission disabled", manual_id=mid)
        store.upsert_semantic_point(mid, sp1)
        store.upsert_semantic_point(mid, sp2)

        rel = SemanticRelation(src_sp_id="sp1", dst_sp_id="sp2",
                               rel_type="CAUSES", confidence=0.9,
                               evidence="WiFi failure caused by disabled permission")
        store.upsert_relation(mid, rel)

        counts = store.count_nodes(mid)
        assert counts["SemanticPoint"] == 2
        assert counts["SEMANTIC_REL"] == 1

    def test_traverse_bfs(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")

        sp1 = SemanticPoint("sp_a", "symptom", "A", "A desc", [], mid)
        sp2 = SemanticPoint("sp_b", "cause", "B", "B desc", [], mid)
        sp3 = SemanticPoint("sp_c", "resolution", "C", "C desc", [], mid)
        for sp in (sp1, sp2, sp3):
            store.upsert_semantic_point(mid, sp)

        store.upsert_relation(mid, SemanticRelation("sp_a", "sp_b", "CAUSES", 0.9))
        store.upsert_relation(mid, SemanticRelation("sp_b", "sp_c", "RESOLVED_BY", 0.8))

        paths = store.traverse_from_sp(mid, ["sp_a"], max_hops=2)
        assert len(paths) >= 2
        dsts = {p["dst_sp"] for p in paths}
        assert "sp_c" in dsts

    def test_link_chunk_to_sp(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")
        store.upsert_small_chunk(mid, "sc1", "mc1", "text", "sec")
        sp = SemanticPoint("sp1", "concept", "X", "X desc", [], mid)
        store.upsert_semantic_point(mid, sp)
        store.link_chunk_to_sp(mid, "sc1", "sp1")

        sps = store.get_chunk_semantic_points(mid, "sc1")
        assert len(sps) == 1
        assert sps[0]["sp_id"] == "sp1"

    def test_sp_to_chunks(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")
        store.upsert_small_chunk(mid, "sc1", "mc1", "wifi setup text", "WiFi Setup")
        sp = SemanticPoint("sp1", "task", "Connect", "Connect wifi", [], mid)
        store.upsert_semantic_point(mid, sp)
        store.link_chunk_to_sp(mid, "sc1", "sp1")

        chunks = store.sp_to_chunks(mid, ["sp1"])
        assert len(chunks) == 1
        assert chunks[0]["chunk_id"] == "sc1"

    def test_drop_manual(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        mid = "test_manual"
        store.upsert_manual(mid, "Test")
        assert store._db_path(mid).exists()
        store.drop_manual(mid)
        assert not store._db_path(mid).exists()
