"""Main retrieval orchestrator and public search entry points."""
from __future__ import annotations

import time
from typing import Any

from .config import RetrievalSettings
from .dense import embed_query, search_milvus
from .fusion import rrf_fuse
from .rerank import Reranker
from .sparse import BM25Index, _chunk_to_hit
from .types import BigHit, HierarchicalResult, MidHit, RetrievalMeta, SearchHit
from .utils import load_chunks_map

# The retrieval package caches corpus state at module scope so repeated interactive
# queries do not keep reloading JSON artifacts and rebuilding BM25 indexes.
_settings: RetrievalSettings | None = None
_small_chunks: list[dict[str, Any]] | None = None
_mid_chunks: dict[str, dict[str, Any]] | None = None
_big_chunks: dict[str, dict[str, Any]] | None = None
_bm25_index: BM25Index | None = None


def _get_settings() -> RetrievalSettings:
    global _settings
    if _settings is None:
        _settings = RetrievalSettings.load()
    return _settings


def _get_corpus() -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    global _small_chunks, _mid_chunks, _big_chunks
    if _small_chunks is None:
        settings = _get_settings()
        small_map, mid_map, big_map = load_chunks_map(settings.chunks_dir)
        _small_chunks = list(small_map.values())
        _mid_chunks = mid_map
        _big_chunks = big_map
    return _small_chunks, _mid_chunks, _big_chunks  # type: ignore[return-value]


def _get_bm25() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        small_chunks, _, _ = _get_corpus()
        _bm25_index = BM25Index(small_chunks)
    return _bm25_index


def reload() -> None:
    """Drop cached settings and corpus state so the next call reloads fresh artifacts."""
    global _settings, _small_chunks, _mid_chunks, _big_chunks, _bm25_index
    _settings = None
    _small_chunks = None
    _mid_chunks = None
    _big_chunks = None
    _bm25_index = None


def _raw_dense_search(
    query: str,
    *,
    settings: RetrievalSettings,
    small_chunks: list[dict[str, Any]],
    top_k: int,
    filter_expr: str | None = None,
    image_paths: list[str] | None = None,
) -> tuple[list[SearchHit], str | None]:
    """
    Run dense recall and return both hits and an optional error string.

    Dense retrieval is allowed to fail softly when configured, because BM25-only
    fallback is still preferable to failing the entire query path.
    """
    small_lookup = {c["chunk_id"]: c for c in small_chunks}
    try:
        qvec = embed_query(query, api_config=settings.api, config=settings.embedding, image_paths=image_paths)
        raw_hits = search_milvus(
            db_path=settings.db_path,
            query_vector=qvec,
            vs_config=settings.vector_store,
            top_k=top_k,
            filter_expr=filter_expr,
        )
        results: list[SearchHit] = []
        for item in raw_hits:
            chunk = small_lookup.get(item["chunk_id"])
            if chunk is None:
                continue
            results.append(_chunk_to_hit(chunk, score=item.get("score", 0.0), rank=item["rank"], source="dense"))
        return results, None
    except Exception as exc:
        if settings.params.allow_dense_fallback:
            return [], str(exc)
        raise


def _hybrid_search(
    query: str,
    *,
    settings: RetrievalSettings,
    small_chunks: list[dict[str, Any]],
    bm25_index: BM25Index,
    top_k: int,
    filter_expr: str | None = None,
    image_paths: list[str] | None = None,
) -> tuple[list[SearchHit], str | None]:
    """
    Run dense and BM25 recall, then fuse both ranked lists with RRF.

    First-stage recall intentionally over-generates candidates so rerank or later
    business logic can work from a more diverse candidate pool.
    """
    bm25_hits = bm25_index.search(query, top_k=settings.params.bm25_top_k)
    dense_hits, dense_error = _raw_dense_search(
        query,
        settings=settings,
        small_chunks=small_chunks,
        top_k=settings.params.dense_top_k,
        filter_expr=filter_expr,
        image_paths=image_paths,
    )

    candidate_k = max(top_k, settings.params.rerank_candidate_k)
    fused = rrf_fuse(
        {"dense": dense_hits, "bm25": bm25_hits},
        config=settings.fusion,
        top_k=candidate_k,
    )
    return fused, dense_error


def search(
    query: str,
    *,
    top_k: int | None = None,
    filter_expr: str | None = None,
    rerank: bool | None = None,
    image_paths: list[str] | None = None,
) -> list[SearchHit]:
    """
    Search small chunks with hybrid recall and optional second-stage reranking.

    This is the primary retrieval entry point used by the answer and chat layers.
    """
    settings = _get_settings()
    small_chunks, _, _ = _get_corpus()
    bm25_index = _get_bm25()
    limit = top_k or settings.params.hybrid_top_k

    hits, _dense_error = _hybrid_search(
        query,
        settings=settings,
        small_chunks=small_chunks,
        bm25_index=bm25_index,
        top_k=limit,
        filter_expr=filter_expr,
        image_paths=image_paths,
    )

    use_rerank = settings.rerank.enabled if rerank is None else rerank
    if use_rerank and hits:
        try:
            hits = Reranker(settings=settings).rerank(query, hits)
        except Exception:
            # Rerank failures should not break the main search path.
            pass

    return hits[:limit]


def search_small(
    query: str,
    *,
    top_k: int | None = None,
    filter_expr: str | None = None,
    rerank: bool | None = None,
    image_paths: list[str] | None = None,
) -> list[SearchHit]:
    """Alias kept for readability at call sites that want the explicit small-chunk level."""
    return search(query, top_k=top_k, filter_expr=filter_expr, rerank=rerank, image_paths=image_paths)


def _small_hits_to_mid_hits(small_hits: list[SearchHit], *, settings: RetrievalSettings) -> list[MidHit]:
    """
    Aggregate recalled small hits back into their parent mid chunks.

    The ordering rule keeps the first successful small-hit rank as the primary
    sorting signal so strong fine-grained evidence bubbles its parent chunk up.
    """
    _, mid_chunks, _ = _get_corpus()
    grouped: dict[str, list[SearchHit]] = {}
    mid_first_rank: dict[str, int] = {}
    for hit in small_hits:
        mid_id = hit.mid_chunk_id
        if not mid_id:
            continue
        grouped.setdefault(mid_id, []).append(hit)
        mid_first_rank[mid_id] = min(mid_first_rank.get(mid_id, 10**9), hit.rank)

    ordered_ids = sorted(
        grouped,
        key=lambda mid_id: (
            mid_first_rank.get(mid_id, 10**9),
            -max(h.score for h in grouped[mid_id]),
        ),
    )

    results: list[MidHit] = []
    for mid_id in ordered_ids:
        mid_chunk = mid_chunks.get(mid_id)
        if mid_chunk is None:
            continue
        children = sorted(grouped[mid_id], key=lambda h: (h.rank, -h.score))
        results.append(
            MidHit(
                chunk_id=mid_id,
                score=max(h.score for h in children),
                rank=len(results) + 1,
                doc_id=mid_chunk.get("doc_id", ""),
                doc_name=mid_chunk.get("doc_name", ""),
                product_name=mid_chunk.get("product_name", ""),
                content=mid_chunk.get("content", ""),
                retrieval_text=mid_chunk.get("retrieval_text", ""),
                image_abs_paths=list(mid_chunk.get("image_abs_paths") or []),
                token_count=int(mid_chunk.get("token_count", 0)),
                section_title=mid_chunk.get("section_title", ""),
                header_path=list(mid_chunk.get("header_path") or []),
                big_chunk_id=mid_chunk.get("big_chunk_id", ""),
                small_hits=children,
                small_count=len(children),
            )
        )
        if len(results) >= settings.params.return_mid_top_k:
            break
    return results


def _mid_hits_to_big_hits(mid_hits: list[MidHit], *, settings: RetrievalSettings) -> list[BigHit]:
    """Aggregate mid-level results into their parent big chunks."""
    _, _, big_chunks = _get_corpus()
    grouped: dict[str, list[MidHit]] = {}
    big_first_rank: dict[str, int] = {}
    for mid in mid_hits:
        big_id = mid.big_chunk_id
        if not big_id:
            continue
        grouped.setdefault(big_id, []).append(mid)
        big_first_rank[big_id] = min(big_first_rank.get(big_id, 10**9), mid.rank)

    ordered_ids = sorted(
        grouped,
        key=lambda big_id: (
            big_first_rank.get(big_id, 10**9),
            -max(m.score for m in grouped[big_id]),
        ),
    )

    results: list[BigHit] = []
    for big_id in ordered_ids:
        big_chunk = big_chunks.get(big_id)
        if big_chunk is None:
            continue
        children = sorted(grouped[big_id], key=lambda m: (m.rank, -m.score))
        total_small = sum(m.small_count for m in children)
        results.append(
            BigHit(
                chunk_id=big_id,
                score=max(m.score for m in children),
                rank=len(results) + 1,
                doc_id=big_chunk.get("doc_id", ""),
                doc_name=big_chunk.get("doc_name", ""),
                product_name=big_chunk.get("product_name", ""),
                content=big_chunk.get("content", ""),
                retrieval_text=big_chunk.get("retrieval_text", ""),
                image_abs_paths=list(big_chunk.get("image_abs_paths") or []),
                token_count=int(big_chunk.get("token_count", 0)),
                section_title=big_chunk.get("section_title", ""),
                header_path=list(big_chunk.get("header_path") or []),
                mid_hits=children,
                mid_count=len(children),
                small_count=total_small,
            )
        )
        if len(results) >= settings.params.return_big_top_k:
            break
    return results


def search_mid(
    query: str,
    *,
    top_k: int | None = None,
    filter_expr: str | None = None,
    rerank: bool | None = None,
    image_paths: list[str] | None = None,
) -> list[MidHit]:
    """Search and return mid-level aggregated hits."""
    settings = _get_settings()
    small_hits = search(query, top_k=top_k, filter_expr=filter_expr, rerank=rerank, image_paths=image_paths)
    return _small_hits_to_mid_hits(small_hits, settings=settings)


def search_big(
    query: str,
    *,
    top_k: int | None = None,
    filter_expr: str | None = None,
    rerank: bool | None = None,
    image_paths: list[str] | None = None,
) -> list[BigHit]:
    """Search and return big-level aggregated hits."""
    settings = _get_settings()
    small_hits = search(query, top_k=top_k, filter_expr=filter_expr, rerank=rerank, image_paths=image_paths)
    mid_hits = _small_hits_to_mid_hits(small_hits, settings=settings)
    return _mid_hits_to_big_hits(mid_hits, settings=settings)


def search_hierarchical(
    query: str,
    *,
    top_k: int | None = None,
    filter_expr: str | None = None,
    rerank: bool | None = None,
    image_paths: list[str] | None = None,
) -> HierarchicalResult:
    """
    Return the full three-level retrieval result with execution metadata.

    This structure is tailored for the answer layer, which may ask different LLM
    sub-chains to reason over small, mid, and big evidence separately.
    """
    settings = _get_settings()
    started = time.monotonic()

    small_hits = search(query, top_k=top_k, filter_expr=filter_expr, rerank=rerank, image_paths=image_paths)
    mid_hits = _small_hits_to_mid_hits(small_hits, settings=settings)
    big_hits = _mid_hits_to_big_hits(mid_hits, settings=settings)

    elapsed = time.monotonic() - started
    meta = RetrievalMeta(
        query=query,
        channels_used=["dense", "bm25"],
        dense_enabled=True,
        rerank_enabled=settings.rerank.enabled,
        dense_top_k=settings.params.dense_top_k,
        bm25_top_k=settings.params.bm25_top_k,
        hybrid_top_k=settings.params.hybrid_top_k,
        elapsed_seconds=round(elapsed, 3),
    )

    return HierarchicalResult(
        query=query,
        small_hits=small_hits,
        mid_hits=mid_hits,
        big_hits=big_hits,
        meta=meta,
    )
