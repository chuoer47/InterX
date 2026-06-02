"""Graph-based retrieval: semantic expansion from seed small chunks."""
from __future__ import annotations

import logging
from typing import Any

from .config import KGSettings, RetrieverConfig
from .graph_store import GraphStore
from .types import GraphExpansion

log = logging.getLogger(__name__)

# Priority weights for relation types (higher = more valuable)
_REL_WEIGHTS: dict[str, float] = {
    "REQUIRES": 1.0,
    "CAUSES": 0.95,
    "RESOLVED_BY": 0.95,
    "AFFECTS": 0.85,
    "NEXT_STEP": 0.8,
    "RELATED_TO": 0.4,
}


class GraphRetriever:
    """Expands first-hop retrieval results using the knowledge graph.

    The retriever does NOT replace dense/sparse retrieval. It sits
    between first-hop recall and hierarchy aggregation:

      query -> hybrid retrieval -> top small chunks
        -> GraphRetriever.expand(seed_chunks)
        -> merge expanded chunks -> mid/big reconstruction -> answer
    """

    def __init__(self, settings: KGSettings, store: GraphStore) -> None:
        self._cfg = settings.retriever
        self._store = store

    def expand(
        self,
        seed_chunks: list[dict[str, Any]],
        manual_id: str | None = None,
    ) -> GraphExpansion:
        """Expand seed small chunks through the knowledge graph.

        Parameters
        ----------
        seed_chunks : list of dicts
            First-hop retrieval results, each must contain ``chunk_id`` and
            optionally ``score``.
        manual_id : str or None
            If provided, only expand within this manual. Otherwise infer
            from the top seed.

        Returns
        -------
        GraphExpansion
            Contains ``expanded_chunk_ids`` (newly discovered chunk ids),
            ``paths`` (traversal explanations), and ``graph_scores``.
        """
        if not seed_chunks:
            return GraphExpansion()

        if manual_id is None:
            manual_id = seed_chunks[0].get("doc_id", "")
        if not manual_id:
            log.warning("Cannot determine manual_id from seed chunks")
            return GraphExpansion()

        # Step 1: select seeds
        seeds = seed_chunks[: self._cfg.seed_count]
        seed_ids = [s["chunk_id"] for s in seeds]
        seed_scores = {s["chunk_id"]: s.get("score", 1.0) for s in seeds}

        # Step 2: collect semantic points from seed chunks
        all_sp_ids: list[str] = []
        for sid in seed_ids:
            sps = self._store.get_chunk_semantic_points(manual_id, sid)
            all_sp_ids.extend(sp["sp_id"] for sp in sps)

        if not all_sp_ids:
            log.info("No semantic points found for seed chunks in %s", manual_id)
            return GraphExpansion(manual_id=manual_id)

        # Step 3: traverse graph from seed SPs
        paths = self._store.traverse_from_sp(manual_id, all_sp_ids, max_hops=self._cfg.max_hops)

        # Step 4: collect destination SP ids
        dst_sp_ids: list[str] = []
        for p in paths:
            if p["dst_sp"] not in all_sp_ids:  # skip self-loops back to seed
                dst_sp_ids.append(p["dst_sp"])
        dst_sp_ids = list(set(dst_sp_ids))

        if not dst_sp_ids:
            return GraphExpansion(manual_id=manual_id, paths=paths)

        # Step 5: map expanded SPs back to small chunks
        expanded_chunks = self._store.sp_to_chunks(manual_id, dst_sp_ids)
        expanded_ids = [c["chunk_id"] for c in expanded_chunks]

        # Remove chunks already in seed set
        seed_set = set(seed_ids)
        expanded_ids = [cid for cid in expanded_ids if cid not in seed_set]

        # Cap total expanded chunks
        expanded_ids = expanded_ids[: self._cfg.max_expanded_chunks]

        # Step 6: compute graph scores
        graph_scores = self._compute_graph_scores(paths, expanded_ids, seed_scores, all_sp_ids)

        return GraphExpansion(
            expanded_chunk_ids=expanded_ids,
            paths=paths,
            graph_scores=graph_scores,
            manual_id=manual_id,
        )

    def _compute_graph_scores(
        self,
        paths: list[dict[str, Any]],
        expanded_ids: list[str],
        seed_scores: dict[str, float],
        seed_sp_ids: list[str],
    ) -> dict[str, float]:
        """Compute a bonus score for each expanded chunk based on graph paths."""
        scores: dict[str, float] = {}
        for cid in expanded_ids:
            # Find all paths that lead to chunks grounded in cid
            best = 0.0
            for p in paths:
                if p["dst_sp"] in seed_sp_ids:
                    continue
                rel_chain = p.get("rel_chain", [])
                hops = p.get("hops", 1)
                # Base score from relation type
                rel_score = max((_REL_WEIGHTS.get(r, 0.3) for r in rel_chain), default=0.3)
                # Decay by hop count
                hop_decay = 1.0 / (1.0 + 0.3 * (hops - 1))
                val = rel_score * hop_decay * self._cfg.graph_bonus_weight
                if val > best:
                    best = val
            scores[cid] = round(best, 4)
        return scores

    def get_stats(self, manual_id: str) -> dict[str, int]:
        """Return node/edge counts for one manual's graph."""
        return self._store.count_nodes(manual_id)
