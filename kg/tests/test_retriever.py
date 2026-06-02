"""Tests for GraphRetriever expansion logic."""
from __future__ import annotations

from pathlib import Path

import pytest

from kg.config import RetrieverConfig
from kg.graph_store import GraphStore
from kg.retriever import GraphRetriever
from kg.types import SemanticPoint, SemanticRelation


def _seed_graph(store: GraphStore, mid: str = "test_manual"):
    """Populate a small graph for retrieval testing."""
    store.upsert_manual(mid, "Test")
    store.upsert_small_chunk(mid, "sc1", "mc1", "WiFi setup instructions", "WiFi Setup")
    store.upsert_small_chunk(mid, "sc2", "mc2", "WiFi troubleshooting: check permissions", "Troubleshooting")
    store.upsert_small_chunk(mid, "sc3", "mc2", "Factory reset erases network config", "Factory Reset")

    sp1 = SemanticPoint("sp1", "task", "Connect WiFi", "Set up WiFi connection", ["sc1"], mid)
    sp2 = SemanticPoint("sp2", "symptom", "WiFi fails", "WiFi connection failure", ["sc2"], mid)
    sp3 = SemanticPoint("sp3", "cause", "Permission disabled", "Network permission off", ["sc2"], mid)
    sp4 = SemanticPoint("sp4", "resolution", "Factory reset", "Reset device to defaults", ["sc3"], mid)
    for sp in (sp1, sp2, sp3, sp4):
        store.upsert_semantic_point(mid, sp)
    for cid, sp in [("sc1", sp1), ("sc2", sp2), ("sc2", sp3), ("sc3", sp4)]:
        store.link_chunk_to_sp(mid, cid, sp.sp_id)

    store.upsert_relation(mid, SemanticRelation("sp2", "sp3", "CAUSES", 0.9))
    store.upsert_relation(mid, SemanticRelation("sp3", "sp4", "RESOLVED_BY", 0.8))


def _make_retriever(store: GraphStore) -> GraphRetriever:
    retriever = GraphRetriever.__new__(GraphRetriever)
    retriever._cfg = RetrieverConfig(max_hops=2, max_expanded_chunks=8, seed_count=2, graph_bonus_weight=0.15)
    retriever._store = store
    return retriever


class TestGraphRetriever:

    def test_empty_seed_returns_empty(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        retriever = _make_retriever(store)
        result = retriever.expand([], manual_id="test")
        assert result.expanded_chunk_ids == []

    def test_expand_2hop_chain(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        _seed_graph(store)
        retriever = _make_retriever(store)

        # Seed with sc2 (Troubleshooting) - sp2 -> CAUSES -> sp3 -> RESOLVED_BY -> sp4
        # sp4 is grounded in sc3, which is not in seed set
        seeds = [{"chunk_id": "sc2", "doc_id": "test_manual", "score": 0.9}]
        result = retriever.expand(seeds, manual_id="test_manual")

        assert result.manual_id == "test_manual"
        # sc3 should be discoverable via 2-hop chain
        assert "sc3" in result.expanded_chunk_ids
        assert len(result.paths) >= 2  # at least sp2->sp3 and sp3->sp4

    def test_seed_chunks_excluded_from_expansion(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        _seed_graph(store)
        retriever = _make_retriever(store)

        # Seed with both sc2 and sc3 — sc3 should NOT appear in expanded
        seeds = [
            {"chunk_id": "sc2", "doc_id": "test_manual", "score": 0.9},
            {"chunk_id": "sc3", "doc_id": "test_manual", "score": 0.8},
        ]
        result = retriever.expand(seeds, manual_id="test_manual")
        assert "sc2" not in result.expanded_chunk_ids
        assert "sc3" not in result.expanded_chunk_ids

    def test_stats(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        _seed_graph(store)
        retriever = _make_retriever(store)

        stats = retriever.get_stats("test_manual")
        assert stats["SmallChunk"] == 3
        assert stats["SemanticPoint"] == 4
        assert stats["SEMANTIC_REL"] == 2

    def test_no_manual_id_returns_empty(self, tmp_root: Path):
        store = GraphStore(tmp_root)
        retriever = _make_retriever(store)
        # doc_id empty
        result = retriever.expand([{"chunk_id": "x", "doc_id": "", "score": 1.0}])
        assert result.expanded_chunk_ids == []
