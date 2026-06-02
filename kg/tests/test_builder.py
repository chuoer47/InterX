"""Tests for GraphBuilder (with mocked LLM)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kg.builder import GraphBuilder, _load_chunks
from kg.config import KGSettings, LLMConfig, GraphStoreConfig, BuilderConfig, RetrieverConfig
from kg.graph_store import GraphStore


def _make_settings(chunks_dir: Path, store_dir: Path) -> KGSettings:
    return KGSettings(
        root=Path("/tmp"),
        chunks_dir=chunks_dir,
        artifacts_dir=store_dir / "artifacts",
        llm=LLMConfig(base_url="http://fake", api_key="fake", model="fake"),
        graph_store=GraphStoreConfig(backend="kuzu", db_path=store_dir),
        builder=BuilderConfig(),
        retriever=RetrieverConfig(),
    )


class TestLoadChunks:

    def test_load_valid_jsonl(self, manual_dir: Path):
        chunks = _load_chunks(manual_dir / "small_chunks.jsonl")
        assert len(chunks) == 3
        assert chunks[0]["chunk_id"] == "test_manual_small_0001"

    def test_load_missing_file(self, tmp_path: Path):
        chunks = _load_chunks(tmp_path / "nonexistent.jsonl")
        assert chunks == []


class TestGraphBuilder:

    @patch("kg.builder.LLMClient")
    def test_build_manual_writes_graph(self, MockLLM, tmp_path: Path, manual_dir: Path):
        """Builder should create structural nodes even if LLM returns nothing."""
        store_dir = tmp_path / "kg_state"
        settings = _make_settings(manual_dir.parent, store_dir)
        store = GraphStore(store_dir)

        # Mock LLM to return no relations (empty extraction)
        mock_llm = MagicMock()
        mock_llm.extract_relations.return_value = ([], [])
        mock_llm.call_count = 0
        MockLLM.return_value = mock_llm

        builder = GraphBuilder(settings, store)
        builder._llm = mock_llm

        report = builder.build_manual("test_manual")

        assert report.manual_id == "test_manual"
        assert report.total_small_chunks == 3
        # Even with no LLM output, structural nodes exist
        counts = store.count_nodes("test_manual")
        assert counts["SmallChunk"] == 3

    @patch("kg.builder.LLMClient")
    def test_build_manual_with_mock_relations(self, MockLLM, tmp_path: Path, manual_dir: Path):
        """Builder should store LLM-extracted semantic points and relations."""
        store_dir = tmp_path / "kg_state"
        settings = _make_settings(manual_dir.parent, store_dir)
        store = GraphStore(store_dir)

        from kg.types import SemanticPoint, SemanticRelation

        # Mock LLM to return one SP + one relation per pair
        def fake_extract(a, b):
            sp_a = SemanticPoint(f"sp_{a['chunk_id']}", "symptom", f"Point from {a['section_title']}",
                                 f"Desc {a['chunk_id']}", [a["chunk_id"]], a["doc_id"])
            sp_b = SemanticPoint(f"sp_{b['chunk_id']}", "cause", f"Point from {b['section_title']}",
                                 f"Desc {b['chunk_id']}", [b["chunk_id"]], b["doc_id"])
            rel = SemanticRelation(sp_a.sp_id, sp_b.sp_id, "CAUSES", 0.85, "test evidence")
            return [sp_a, sp_b], [rel]

        mock_llm = MagicMock()
        mock_llm.extract_relations.side_effect = fake_extract
        mock_llm.call_count = 0
        MockLLM.return_value = mock_llm

        builder = GraphBuilder(settings, store)
        builder._llm = mock_llm

        report = builder.build_manual("test_manual")

        assert report.llm_calls == 2  # 3 chunks, 2 different big_chunks = 2 cross-big pairs
        assert report.total_semantic_points == 4  # 2 per pair x 2 pairs
        assert report.total_relations == 2
