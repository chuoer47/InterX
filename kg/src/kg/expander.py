"""Expand retrieval hits via the knowledge graph (CO_EVIDENCE + SEMANTIC edges).

This module is the bridge between the retrieval layer and the KG layer.
It accepts first-hop small-chunk hits and discovers related chunks by
traversing direct CO_EVIDENCE and SEMANTIC edges in the Kùzu graph.

Usage:
    from kg.expander import expand_hits
    expanded = expand_hits(small_hits, max_expanded=8)
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import kuzu

from .config import KGSettings

log = logging.getLogger(__name__)

# Edge weights used for scoring expanded chunks
_EDGE_WEIGHTS: dict[str, float] = {
    "SEMANTIC": 1.0,     # LLM-confirmed relationship
    "CO_EVIDENCE": 0.5,  # co-occurrence based
}


@dataclass(slots=True)
class ExpansionResult:
    """Result of graph expansion for a set of seed hits."""
    expanded_hits: list[dict[str, Any]] = field(default_factory=list)
    seed_ids: list[str] = field(default_factory=list)
    expansion_count: int = 0
    elapsed_seconds: float = 0.0


class ChunkExpander:
    """Expands small-chunk hits by traversing the KG's direct edges.

    Unlike the older GraphRetriever (which goes through SemanticPoint nodes),
    this class queries CO_EVIDENCE and SEMANTIC edges directly between
    SmallChunk nodes — matching the cold-start graph structure.
    """

    def __init__(self, settings: KGSettings | None = None) -> None:
        if settings is None:
            settings = KGSettings.load()
        self._db_root: Path = settings.graph_store.db_path
        self._max_expanded: int = settings.retriever.max_expanded_chunks
        # Cache connections per manual to avoid repeated open/close
        self._conns: dict[str, kuzu.Connection] = {}

    def _get_conn(self, manual_id: str) -> kuzu.Connection | None:
        """Open a Kùzu connection for a manual, returning None if db missing."""
        if manual_id in self._conns:
            return self._conns[manual_id]
        db_path = self._db_root / f"{manual_id}.kuzu"
        if not db_path.exists():
            log.warning("KG db not found for manual %s", manual_id)
            return None
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)
        self._conns[manual_id] = conn
        return conn

    def close(self) -> None:
        """Release all cached connections."""
        self._conns.clear()

    def expand(
        self,
        seed_hits: list[dict[str, Any]],
        *,
        max_expanded: int | None = None,
    ) -> ExpansionResult:
        """Expand seed small-chunk hits via KG edges.

        Parameters
        ----------
        seed_hits : list of dicts
            First-hop retrieval results. Each must contain ``chunk_id``,
            ``doc_id``, ``score``, and other SearchHit fields.
        max_expanded : int or None
            Override for the maximum number of expanded chunks to return.

        Returns
        -------
        ExpansionResult
            Contains expanded hits (as dicts matching SearchHit format)
            and metadata.
        """
        started = time.monotonic()
        limit = max_expanded or self._max_expanded
        seed_ids = [h["chunk_id"] for h in seed_hits]
        seed_set = set(seed_ids)

        if not seed_ids:
            return ExpansionResult(seed_ids=seed_ids)

        # Group seeds by manual for per-db queries
        seeds_by_manual: dict[str, list[dict[str, Any]]] = {}
        for h in seed_hits:
            mid = h.get("doc_id", "")
            if mid:
                seeds_by_manual.setdefault(mid, []).append(h)

        candidate_ids: dict[str, dict[str, Any]] = {}

        for manual_id, hits in seeds_by_manual.items():
            conn = self._get_conn(manual_id)
            if conn is None:
                continue

            for hit in hits:
                cid = hit["chunk_id"]
                seed_score = hit.get("score", 1.0)

                # Query both edge types in one pass
                for edge_type, edge_weight in _EDGE_WEIGHTS.items():
                    try:
                        rows = self._query_neighbors(conn, cid, edge_type)
                    except Exception as exc:
                        log.debug("Query %s from %s failed: %s", edge_type, cid, exc)
                        continue

                    for neighbor_id, edge_weight_db in rows:
                        if neighbor_id in seed_set:
                            continue
                        score = edge_weight_db * seed_score * edge_weight
                        existing = candidate_ids.get(neighbor_id)
                        if existing is None or score > existing["graph_score"]:
                            candidate_ids[neighbor_id] = {
                                "chunk_id": neighbor_id,
                                "manual_id": manual_id,
                                "graph_score": score,
                                "edge_type": edge_type,
                                "seed_chunk": cid,
                            }

        # Sort by score descending and cap
        sorted_candidates = sorted(
            candidate_ids.values(), key=lambda c: c["graph_score"], reverse=True
        )[:limit]

        # Fetch full chunk content for expanded hits
        expanded_hits = self._hydrate_expanded(sorted_candidates)

        return ExpansionResult(
            expanded_hits=expanded_hits,
            seed_ids=seed_ids,
            expansion_count=len(expanded_hits),
            elapsed_seconds=round(time.monotonic() - started, 4),
        )

    def _query_neighbors(
        self, conn: kuzu.Connection, chunk_id: str, edge_type: str
    ) -> list[tuple[str, float]]:
        """Query outgoing neighbors of a SmallChunk via one edge type."""
        query = (
            f"MATCH (a:SmallChunk {{id: $cid}})-[r:{edge_type}]->(b:SmallChunk) "
            "RETURN DISTINCT b.id, r.weight LIMIT 20"
        )
        result = conn.execute(query, {"cid": chunk_id})
        out: list[tuple[str, float]] = []
        while result.has_next():
            row = result.get_next()
            out.append((row[0], float(row[1]) if row[1] is not None else 0.5))
        return out

    def _hydrate_expanded(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Fetch full SmallChunk data for expanded chunk IDs."""
        hits: list[dict[str, Any]] = []
        for cand in candidates:
            manual_id = cand["manual_id"]
            conn = self._get_conn(manual_id)
            if conn is None:
                continue
            try:
                result = conn.execute(
                    "MATCH (s:SmallChunk {id: $cid}) "
                    "RETURN s.id, s.txt, s.section_title, s.mid_chunk_id",
                    {"cid": cand["chunk_id"]},
                )
                if result.has_next():
                    row = result.get_next()
                    hits.append({
                        "chunk_id": row[0],
                        "content": row[1] or "",
                        "section_title": row[2] or "",
                        "mid_chunk_id": row[3] or "",
                        "doc_id": manual_id,
                        "graph_score": cand["graph_score"],
                        "edge_type": cand["edge_type"],
                        "seed_chunk": cand["seed_chunk"],
                    })
            except Exception as exc:
                log.debug("Hydrate %s failed: %s", cand["chunk_id"], exc)
        return hits


def expand_hits(
    seed_hits: list[dict[str, Any]],
    *,
    settings: KGSettings | None = None,
    max_expanded: int | None = None,
) -> ExpansionResult:
    """Convenience function: expand seed hits and close connections."""
    expander = ChunkExpander(settings)
    try:
        return expander.expand(seed_hits, max_expanded=max_expanded)
    finally:
        expander.close()
