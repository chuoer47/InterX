"""Multi-channel fusion helpers."""
from __future__ import annotations

from .config import FusionConfig
from .types import SearchHit


def rrf_fuse(
    channels: dict[str, list[SearchHit]],
    *,
    config: FusionConfig,
    top_k: int,
) -> list[SearchHit]:
    """
    Fuse multiple ranked lists with Reciprocal Rank Fusion.

    RRF is intentionally rank-based rather than score-based, which makes it much
    easier to combine BM25 and dense channels whose raw score distributions are
    not directly comparable.
    """
    merged: dict[str, dict] = {}
    k = config.rrf_k

    for channel_name, hits in channels.items():
        weight = config.channel_weights.get(channel_name, 1.0)
        for hit in hits:
            cid = hit.chunk_id
            if cid not in merged:
                merged[cid] = {
                    "hit": hit,
                    "rrf_score": 0.0,
                    "scores": {"rrf": 0.0},
                }
            merged[cid]["rrf_score"] += weight / (k + hit.rank)
            merged[cid]["scores"][f"{channel_name}_score"] = hit.score
            merged[cid]["scores"][f"{channel_name}_rank"] = hit.rank

    ranked = sorted(merged.values(), key=lambda item: item["rrf_score"], reverse=True)[:top_k]

    results: list[SearchHit] = []
    for rank, item in enumerate(ranked, start=1):
        hit = item["hit"]
        scores = item["scores"]
        scores["rrf"] = item["rrf_score"]
        results.append(
            SearchHit(
                chunk_id=hit.chunk_id,
                score=item["rrf_score"],
                rank=rank,
                doc_id=hit.doc_id,
                doc_name=hit.doc_name,
                product_name=hit.product_name,
                content=hit.content,
                retrieval_text=hit.retrieval_text,
                image_abs_paths=hit.image_abs_paths,
                token_count=hit.token_count,
                section_title=hit.section_title,
                header_path=hit.header_path,
                big_chunk_id=hit.big_chunk_id,
                mid_chunk_id=hit.mid_chunk_id,
                retrieval_source="hybrid",
                scores=scores,
            )
        )
    return results
