"""Integration tests for the retrieval pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from retrieval.types import SearchHit, MidHit, BigHit, HierarchicalResult, RetrievalMeta
from retrieval.tokenizer import tokenize
from retrieval.fusion import rrf_fuse
from retrieval.config import FusionConfig
from retrieval.context import assemble_context


# ---------------------------------------------------------------------------
# types
# ---------------------------------------------------------------------------

def _make_hit(**overrides) -> SearchHit:
    defaults = {
        "chunk_id": "test_small_0000",
        "score": 0.5,
        "rank": 1,
        "doc_id": "test_doc",
        "doc_name": "Test Manual",
        "product_name": "Test Product",
        "content": "Test content about camera settings.",
        "retrieval_text": "Test content about camera settings.",
        "image_abs_paths": [],
        "token_count": 100,
        "section_title": "Camera Settings",
        "header_path": ["Manual", "Camera Settings"],
        "big_chunk_id": "test_big_0000",
        "mid_chunk_id": "test_mid_0000",
    }
    defaults.update(overrides)
    return SearchHit(**defaults)


def test_search_hit_to_dict():
    hit = _make_hit()
    d = hit.to_dict()
    assert d["chunk_id"] == "test_small_0000"
    assert d["doc_name"] == "Test Manual"
    assert d["score"] == 0.5


def test_mid_hit_aggregation():
    smalls = [
        _make_hit(chunk_id=f"s_{i}", rank=i + 1, score=0.9 - i * 0.1)
        for i in range(3)
    ]
    mid = MidHit(
        chunk_id="mid_0000",
        score=max(h.score for h in smalls),
        rank=1,
        doc_id="test_doc",
        doc_name="Test Manual",
        product_name="Test Product",
        content="Mid content",
        retrieval_text="Mid content",
        image_abs_paths=[],
        token_count=300,
        section_title="Section",
        header_path=["Manual"],
        big_chunk_id="big_0000",
        small_hits=smalls,
        small_count=3,
    )
    d = mid.to_dict()
    assert d["small_count"] == 3
    assert len(d["small_hits"]) == 3
    assert d["score"] == 0.9


def test_big_hit_aggregation():
    big = BigHit(
        chunk_id="big_0000",
        score=0.8,
        rank=1,
        doc_id="test_doc",
        doc_name="Test Manual",
        product_name="Test Product",
        content="Big content",
        retrieval_text="Big content",
        image_abs_paths=[],
        token_count=1000,
        section_title="Chapter",
        header_path=["Manual"],
        mid_hits=[],
        mid_count=2,
        small_count=5,
    )
    d = big.to_dict()
    assert d["mid_count"] == 2
    assert d["small_count"] == 5


# ---------------------------------------------------------------------------
# tokenizer
# ---------------------------------------------------------------------------

def test_tokenize_english():
    tokens = tokenize("How do I reset the camera?")
    assert "reset" in tokens
    assert "camera" in tokens


def test_tokenize_chinese():
    tokens = tokenize("如何重置相机？")
    assert len(tokens) > 0
    # Should have Chinese character unigrams
    chinese_tokens = [t for t in tokens if len(t) == 1 and "\u4e00" <= t <= "\u9fff"]
    assert len(chinese_tokens) > 0


def test_tokenize_empty():
    tokens = tokenize("")
    assert tokens == []


# ---------------------------------------------------------------------------
# fusion
# ---------------------------------------------------------------------------

def _make_hits(n: int, *, source: str) -> list[SearchHit]:
    return [
        _make_hit(chunk_id=f"chunk_{i}", rank=i + 1, score=1.0 - i * 0.1, retrieval_source=source)
        for i in range(n)
    ]


def test_rrf_fuse_single_channel():
    config = FusionConfig(method="rrf", rrf_k=60, channel_weights={"dense": 1.0})
    hits = _make_hits(5, source="dense")
    fused = rrf_fuse({"dense": hits}, config=config, top_k=3)
    assert len(fused) == 3
    assert fused[0].retrieval_source == "hybrid"
    assert fused[0].score > fused[1].score


def test_rrf_fuse_two_channels():
    config = FusionConfig(method="rrf", rrf_k=60, channel_weights={"dense": 0.65, "bm25": 0.35})
    dense_hits = _make_hits(5, source="dense")
    bm25_hits = _make_hits(5, source="bm25")
    # Make bm25 rank differently: chunk_3 first in BM25
    bm25_hits[0] = _make_hit(chunk_id="chunk_3", rank=1, score=2.0, retrieval_source="bm25")
    fused = rrf_fuse({"dense": dense_hits, "bm25": bm25_hits}, config=config, top_k=5)
    assert len(fused) == 5
    # chunk_0 appears in dense at rank 1, bm25 at rank 2 → should be highly ranked
    assert fused[0].chunk_id in ("chunk_0", "chunk_3")


def test_rrf_fuse_empty():
    config = FusionConfig(method="rrf", rrf_k=60, channel_weights={"dense": 1.0})
    fused = rrf_fuse({"dense": []}, config=config, top_k=5)
    assert fused == []


# ---------------------------------------------------------------------------
# context assembly
# ---------------------------------------------------------------------------

def test_assemble_context_small():
    hits = [_make_hit(chunk_id=f"s_{i}", content=f"Content block {i}") for i in range(3)]
    ctx = assemble_context(hits, level="small", max_tokens=12000)
    assert "Content block 0" in ctx
    assert "Test Manual" in ctx


def test_assemble_context_truncation():
    hits = [_make_hit(chunk_id=f"s_{i}", content="x" * 5000) for i in range(10)]
    ctx = assemble_context(hits, level="small", max_tokens=1000)
    assert "截断" in ctx


def test_assemble_context_mid():
    mid = MidHit(
        chunk_id="mid_0000",
        score=0.9,
        rank=1,
        doc_id="test_doc",
        doc_name="Test Manual",
        product_name="Test Product",
        content="Mid content here",
        retrieval_text="Mid content here",
        image_abs_paths=[],
        token_count=300,
        section_title="Section",
        header_path=["Manual", "Section"],
        big_chunk_id="big_0000",
        small_hits=[_make_hit()],
        small_count=1,
    )
    ctx = assemble_context([mid], level="mid")
    assert "中块: mid_0000" in ctx
    assert "Mid content here" in ctx


# ---------------------------------------------------------------------------
# HierarchicalResult
# ---------------------------------------------------------------------------

def test_hierarchical_result_to_dict():
    meta = RetrievalMeta(
        query="test", channels_used=["dense", "bm25"],
        dense_enabled=True, rerank_enabled=True,
        dense_top_k=20, bm25_top_k=20, hybrid_top_k=10,
        elapsed_seconds=1.5,
    )
    result = HierarchicalResult(
        query="test",
        small_hits=[_make_hit()],
        mid_hits=[],
        big_hits=[],
        meta=meta,
    )
    d = result.to_dict()
    assert d["query"] == "test"
    assert len(d["small_hits"]) == 1
    assert d["meta"]["channels_used"] == ["dense", "bm25"]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
