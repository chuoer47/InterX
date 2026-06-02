"""Tests for the ChunkExpander that bridges retrieval hits to KG expansion."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure kg src is importable
_KG_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _KG_SRC not in sys.path:
    sys.path.insert(0, _KG_SRC)

from kg.expander import ChunkExpander, ExpansionResult, expand_hits


class TestExpansionResult:
    """Basic dataclass sanity checks."""

    def test_defaults(self):
        r = ExpansionResult()
        assert r.expanded_hits == []
        assert r.seed_ids == []
        assert r.expansion_count == 0
        assert r.elapsed_seconds == 0.0


class TestChunkExpanderUnit:
    """Unit tests with mocked Kùzu connections."""

    def _make_settings(self, tmp_path: Path):
        """Build a minimal KGSettings pointing at a temp dir."""
        from kg.config import KGSettings, GraphStoreConfig, RetrieverConfig, LLMConfig, BuilderConfig
        return KGSettings(
            root=tmp_path,
            chunks_dir=tmp_path / "chunks",
            artifacts_dir=tmp_path / "artifacts",
            llm=LLMConfig(base_url="", api_key="", model="test"),
            graph_store=GraphStoreConfig(backend="kuzu", db_path=tmp_path / "graph.db"),
            builder=BuilderConfig(),
            retriever=RetrieverConfig(max_hops=2, max_expanded_chunks=5, seed_count=3),
        )

    def test_expand_empty_seeds(self, tmp_path):
        settings = self._make_settings(tmp_path)
        expander = ChunkExpander(settings)
        result = expander.expand([])
        assert result.expansion_count == 0
        assert result.seed_ids == []
        expander.close()

    def test_expand_missing_db(self, tmp_path):
        """When the graph db doesn't exist, expansion should return empty gracefully."""
        settings = self._make_settings(tmp_path)
        expander = ChunkExpander(settings)
        hits = [{"chunk_id": "test_001", "doc_id": "nonexistent_manual", "score": 0.9}]
        result = expander.expand(hits)
        assert result.expansion_count == 0
        assert result.seed_ids == ["test_001"]
        expander.close()


class TestExpandHitsFunction:
    """Test the convenience function."""

    def test_expand_hits_returns_result(self):
        """With no real DB, should return empty expansion gracefully."""
        # This will fail to find the db but should not raise
        result = expand_hits(
            [{"chunk_id": "x", "doc_id": "missing", "score": 0.5}],
        )
        assert isinstance(result, ExpansionResult)
        assert result.expansion_count == 0


class TestExpanderIntegration:
    """Integration tests using real graph DB (requires built graph)."""

    @pytest.fixture(autouse=True)
    def _require_graph(self):
        """Skip if graph DB hasn't been built."""
        graph_root = Path(__file__).resolve().parents[1] / "state" / "graph.db"
        if not graph_root.exists():
            pytest.skip("Graph DB not built yet")
        self._graph_root = graph_root

    def _find_seed_with_edges(self):
        """Find a SmallChunk that has at least one CO_EVIDENCE or SEMANTIC edge."""
        import kuzu
        for db_file in sorted(self._graph_root.glob("*.kuzu"))[:5]:
            db = kuzu.Database(str(db_file))
            conn = kuzu.Connection(db)
            r = conn.execute(
                "MATCH (a:SmallChunk)-[:CO_EVIDENCE]->(b:SmallChunk) "
                "RETURN a.id LIMIT 1"
            )
            if r.has_next():
                manual_id = db_file.stem
                return r.get_next()[0], manual_id
        pytest.skip("No chunks with edges found in first 5 manuals")

    def test_expand_returns_results(self):
        seed_id, manual_id = self._find_seed_with_edges()
        from kg.config import KGSettings
        settings = KGSettings.load()
        result = expand_hits(
            [{"chunk_id": seed_id, "doc_id": manual_id, "score": 0.8}],
            settings=settings,
        )
        assert result.expansion_count > 0
        assert len(result.expanded_hits) > 0
        # Each expanded hit should have the required fields
        for h in result.expanded_hits:
            assert "chunk_id" in h
            assert "graph_score" in h
            assert "edge_type" in h
            assert h["edge_type"] in ("SEMANTIC", "CO_EVIDENCE")

    def test_expand_respects_max_limit(self):
        seed_id, manual_id = self._find_seed_with_edges()
        from kg.config import KGSettings
        settings = KGSettings.load()
        result = expand_hits(
            [{"chunk_id": seed_id, "doc_id": manual_id, "score": 0.8}],
            settings=settings,
            max_expanded=2,
        )
        assert result.expansion_count <= 2

    def test_expand_deduplicates(self):
        """Expanded chunks should not include seed chunks."""
        seed_id, manual_id = self._find_seed_with_edges()
        from kg.config import KGSettings
        settings = KGSettings.load()
        result = expand_hits(
            [{"chunk_id": seed_id, "doc_id": manual_id, "score": 0.8}],
            settings=settings,
        )
        expanded_ids = {h["chunk_id"] for h in result.expanded_hits}
        assert seed_id not in expanded_ids
