"""Data models for retrieval results at small, mid, and big granularity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SearchHit:
    """
    First-stage hit at the small-chunk level.

    Small chunks are the retrieval anchor because they are precise enough for
    recall, while the hierarchy above them is reconstructed later as needed.
    """
    chunk_id: str
    score: float
    rank: int
    doc_id: str
    doc_name: str
    product_name: str
    content: str
    retrieval_text: str
    image_abs_paths: list[str]
    token_count: int
    section_title: str
    header_path: list[str]
    big_chunk_id: str
    mid_chunk_id: str
    retrieval_source: str = ""
    scores: dict[str, Any] = field(default_factory=dict)
    rerank_score: float | None = None
    rerank_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "rank": self.rank,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "product_name": self.product_name,
            "content": self.content,
            "retrieval_text": self.retrieval_text,
            "image_abs_paths": self.image_abs_paths,
            "token_count": self.token_count,
            "section_title": self.section_title,
            "header_path": self.header_path,
            "big_chunk_id": self.big_chunk_id,
            "mid_chunk_id": self.mid_chunk_id,
            "retrieval_source": self.retrieval_source,
            "scores": self.scores,
            "rerank_score": self.rerank_score,
            "rerank_applied": self.rerank_applied,
        }


@dataclass(slots=True)
class MidHit:
    """Aggregated mid-level hit reconstructed from one or more child small hits."""
    chunk_id: str
    score: float
    rank: int
    doc_id: str
    doc_name: str
    product_name: str
    content: str
    retrieval_text: str
    image_abs_paths: list[str]
    token_count: int
    section_title: str
    header_path: list[str]
    big_chunk_id: str
    small_hits: list[SearchHit] = field(default_factory=list)
    small_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "rank": self.rank,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "product_name": self.product_name,
            "content": self.content,
            "retrieval_text": self.retrieval_text,
            "image_abs_paths": self.image_abs_paths,
            "token_count": self.token_count,
            "section_title": self.section_title,
            "header_path": self.header_path,
            "big_chunk_id": self.big_chunk_id,
            "small_count": self.small_count,
            "small_hits": [h.to_dict() for h in self.small_hits],
        }


@dataclass(slots=True)
class BigHit:
    """Aggregated big-level hit reconstructed from child mid hits."""
    chunk_id: str
    score: float
    rank: int
    doc_id: str
    doc_name: str
    product_name: str
    content: str
    retrieval_text: str
    image_abs_paths: list[str]
    token_count: int
    section_title: str
    header_path: list[str]
    mid_hits: list[MidHit] = field(default_factory=list)
    mid_count: int = 0
    small_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "rank": self.rank,
            "doc_id": self.doc_id,
            "doc_name": self.doc_name,
            "product_name": self.product_name,
            "content": self.content,
            "retrieval_text": self.retrieval_text,
            "image_abs_paths": self.image_abs_paths,
            "token_count": self.token_count,
            "section_title": self.section_title,
            "header_path": self.header_path,
            "mid_count": self.mid_count,
            "small_count": self.small_count,
            "mid_hits": [h.to_dict() for h in self.mid_hits],
        }


@dataclass(slots=True)
class RetrievalMeta:
    """Execution metadata describing how a retrieval result was produced."""
    query: str
    channels_used: list[str]
    dense_enabled: bool
    rerank_enabled: bool
    dense_top_k: int
    bm25_top_k: int
    hybrid_top_k: int
    elapsed_seconds: float
    dense_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "channels_used": self.channels_used,
            "dense_enabled": self.dense_enabled,
            "rerank_enabled": self.rerank_enabled,
            "dense_top_k": self.dense_top_k,
            "bm25_top_k": self.bm25_top_k,
            "hybrid_top_k": self.hybrid_top_k,
            "elapsed_seconds": self.elapsed_seconds,
            "dense_error": self.dense_error,
        }


@dataclass(slots=True)
class HierarchicalResult:
    """Full retrieval result spanning small, mid, and big levels."""
    query: str
    small_hits: list[SearchHit]
    mid_hits: list[MidHit]
    big_hits: list[BigHit]
    meta: RetrievalMeta

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "small_hits": [h.to_dict() for h in self.small_hits],
            "mid_hits": [h.to_dict() for h in self.mid_hits],
            "big_hits": [h.to_dict() for h in self.big_hits],
            "meta": self.meta.to_dict(),
        }
