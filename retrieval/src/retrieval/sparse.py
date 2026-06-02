"""BM25 sparse retrieval over the full corpus of small chunks."""
from __future__ import annotations

from typing import Any

from rank_bm25 import BM25Okapi

from .tokenizer import tokenize
from .types import SearchHit


class BM25Index:
    """
    In-memory BM25 index over the small-chunk corpus.

    Sparse retrieval complements dense recall by handling exact product terms,
    model numbers, and short keyword queries that embeddings may smooth away.
    """

    def __init__(self, chunks: list[dict[str, Any]]) -> None:
        self._chunks = chunks
        corpus = [tokenize(chunk.get("retrieval_text") or chunk.get("text") or "") for chunk in chunks]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, *, top_k: int) -> list[SearchHit]:
        """Score the query against the full sparse index and return the top-ranked hits."""
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)[:top_k]
        results: list[SearchHit] = []
        for rank, (idx, score) in enumerate(ranked, start=1):
            if score <= 0:
                continue
            chunk = self._chunks[idx]
            results.append(_chunk_to_hit(chunk, score=float(score), rank=rank, source="bm25"))
        return results


def _chunk_to_hit(
    chunk: dict[str, Any],
    *,
    score: float,
    rank: int,
    source: str,
    scores: dict[str, Any] | None = None,
) -> SearchHit:
    """Convert a raw chunk payload into the shared retrieval hit model."""
    return SearchHit(
        chunk_id=chunk["chunk_id"],
        score=score,
        rank=rank,
        doc_id=chunk.get("doc_id", ""),
        doc_name=chunk.get("doc_name", ""),
        product_name=chunk.get("product_name", ""),
        content=chunk.get("content", ""),
        retrieval_text=chunk.get("retrieval_text", ""),
        image_abs_paths=list(chunk.get("image_abs_paths") or []),
        token_count=int(chunk.get("token_count", 0)),
        section_title=chunk.get("section_title", ""),
        header_path=list(chunk.get("header_path") or []),
        big_chunk_id=chunk.get("big_chunk_id", ""),
        mid_chunk_id=chunk.get("mid_chunk_id", ""),
        retrieval_source=source,
        scores=scores or {},
    )
