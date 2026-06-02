"""Graph builder: constructs per-manual knowledge graphs from chunk artifacts.

Supports both sequential and concurrent LLM extraction modes.
For production use, concurrent mode is recommended (10-20x faster).
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
from typing import Any

from .config import KGSettings
from .graph_store import GraphStore
from .llm_client import LLMClient
from .types import BuildReport, SemanticPoint, SemanticRelation

log = logging.getLogger(__name__)


def _load_chunks(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    if not path.exists():
        return chunks
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def _pair_key(a_id: str, b_id: str) -> str:
    return f"{min(a_id, b_id)}||{max(a_id, b_id)}"


class GraphBuilder:
    """Builds a knowledge graph for a single manual.

    Pipeline:
      1. Load small / mid / big chunks from process artifacts.
      2. Create structural nodes.
      3. For every pair of small chunks, call LLM to extract semantic points
         and inter-chunk relations.
      4. Write results to graph store.
    """

    def __init__(self, settings: KGSettings, store: GraphStore, concurrent: bool = True, max_workers: int = 4) -> None:
        self._settings = settings
        self._store = store
        self._llm = LLMClient(settings.llm)
        self._processed_pairs: set[str] = set()
        self._concurrent = concurrent
        self._max_workers = max_workers

    def _detect_processed_pairs(self, manual_id: str) -> set[str]:
        """Infer which chunk pairs were already processed from existing graph data."""
        processed: set[str] = set()
        try:
            conn = self._store._get_conn(manual_id)
            # Get all SPs and their grounded chunk IDs
            r = conn.execute(
                "MATCH (sp:SemanticPoint)-[:GROUNDED_IN]->(s:SmallChunk) "
                "RETURN sp.id, s.id"
            )
            sp_chunks: dict[str, set[str]] = {}
            while r.has_next():
                row = r.get_next()
                sp_id, chunk_id = row[0], row[1]
                sp_chunks.setdefault(sp_id, set()).add(chunk_id)

            # For each SEMANTIC_REL, find the source chunks of both endpoints
            r2 = conn.execute(
                "MATCH (a:SemanticPoint)-[:SEMANTIC_REL]->(b:SemanticPoint) "
                "RETURN a.id, b.id"
            )
            while r2.has_next():
                row = r2.get_next()
                a_id, b_id = row[0], row[1]
                a_chunks = sp_chunks.get(a_id, set())
                b_chunks = sp_chunks.get(b_id, set())
                for ca in a_chunks:
                    for cb in b_chunks:
                        processed.add(_pair_key(ca, cb))
        except Exception:
            pass
        return processed

    def _extract_one_pair(self, a: dict[str, Any], b: dict[str, Any]) -> tuple[list[SemanticPoint], list[SemanticRelation]]:
        """Extract relations from a single chunk pair."""
        pk = _pair_key(a["chunk_id"], b["chunk_id"])
        if pk in self._processed_pairs:
            return [], []
        self._processed_pairs.add(pk)
        return self._llm.extract_relations(a, b)

    def build_manual(self, manual_id: str) -> BuildReport:
        """Build the graph for one manual end-to-end."""
        manual_dir = self._settings.chunks_dir / manual_id
        small_chunks = _load_chunks(manual_dir / "small_chunks.jsonl")
        mid_chunks = _load_chunks(manual_dir / "mid_chunks.jsonl")
        big_chunks = _load_chunks(manual_dir / "big_chunks.jsonl")

        report = BuildReport(manual_id=manual_id, total_small_chunks=len(small_chunks))
        if not small_chunks:
            log.warning("No small chunks found for %s", manual_id)
            return report

        doc_name = small_chunks[0].get("doc_name", manual_id)

        # 1. Structural nodes
        log.info("[%s] Creating structural nodes (%d small, %d mid, %d big)",
                 manual_id, len(small_chunks), len(mid_chunks), len(big_chunks))
        self._store.upsert_manual(manual_id, doc_name)

        seen_mid: set[str] = set()
        seen_big: set[str] = set()
        for mc in mid_chunks:
            if mc["chunk_id"] not in seen_mid:
                self._store.upsert_mid_chunk(manual_id, mc["chunk_id"], mc.get("big_chunk_id", ""))
                seen_mid.add(mc["chunk_id"])
        for bc in big_chunks:
            if bc["chunk_id"] not in seen_big:
                self._store.upsert_big_chunk(manual_id, bc["chunk_id"], bc.get("section_title", ""))
                seen_big.add(bc["chunk_id"])

        for sc in small_chunks:
            self._store.upsert_small_chunk(
                manual_id, sc["chunk_id"], sc.get("mid_chunk_id", ""),
                sc.get("text", ""), sc.get("section_title", ""),
            )
            self._store.link_chunk_hierarchy(
                manual_id, sc["chunk_id"], sc.get("mid_chunk_id", ""), sc.get("big_chunk_id", ""),
            )

        # 2. LLM-based pair extraction
        # Detect already-processed pairs for resume capability
        self._processed_pairs = self._detect_processed_pairs(manual_id)
        if self._processed_pairs:
            log.info("[%s] Resuming: %d pairs already processed", manual_id, len(self._processed_pairs))

        # Skip pairs from the same big_chunk — already handled by hierarchy
        pairs = []
        for i, a in enumerate(small_chunks):
            for b in small_chunks[i + 1:]:
                if a.get("big_chunk_id") != b.get("big_chunk_id"):
                    pairs.append((a, b))

        # Cap total pairs per manual to avoid prohibitive LLM costs on large manuals.
        # For manuals exceeding the cap, sample evenly across chunk index ranges.
        max_pairs = 3000
        if len(pairs) > max_pairs:
            import random
            random.seed(42)  # reproducible
            pairs = random.sample(pairs, max_pairs)
            log.info("[%s] Sampled %d pairs from %d total (cap=%d)",
                     manual_id, max_pairs, len(pairs), max_pairs)
        log.info("[%s] Extracting relations from %d chunk pairs (concurrent=%s, workers=%d)",
                 manual_id, len(pairs), self._concurrent, self._max_workers)

        all_sp: list[SemanticPoint] = []
        all_rel: list[SemanticRelation] = []
        errors: list[str] = []
        llm_calls = 0
        t0 = time.time()

        if self._concurrent and len(pairs) > 1:
            all_sp, all_rel, errors, llm_calls = self._extract_concurrent(pairs, manual_id)
        else:
            all_sp, all_rel, errors, llm_calls = self._extract_sequential(pairs, manual_id)

        elapsed = time.time() - t0
        report.total_semantic_points = len(all_sp)
        report.total_relations = len(all_rel)
        report.llm_calls = llm_calls
        report.errors = errors

        log.info("[%s] Build complete in %.1fs: %d SPs, %d relations, %d LLM calls, %d errors",
                 manual_id, elapsed, len(all_sp), len(all_rel), llm_calls, len(errors))
        return report

    def _extract_sequential(self, pairs: list[tuple], manual_id: str) -> tuple[list[SemanticPoint], list[SemanticRelation], list[str], int]:
        """Sequential extraction (for debugging or small manuals)."""
        all_sp: list[SemanticPoint] = []
        all_rel: list[SemanticRelation] = []
        errors: list[str] = []
        llm_calls = 0

        for i, (a, b) in enumerate(pairs):
            try:
                sps, rels = self._extract_one_pair(a, b)
                llm_calls += 1
                self._write_results(manual_id, sps, rels)
                all_sp.extend(sps)
                all_rel.extend(rels)
            except Exception as exc:
                errors.append(f"Pair {a['chunk_id']} x {b['chunk_id']}: {exc}")

            if (i + 1) % 10 == 0:
                log.info("[%s] %d/%d pairs done", manual_id, i + 1, len(pairs))

        return all_sp, all_rel, errors, llm_calls

    def _extract_concurrent(self, pairs: list[tuple], manual_id: str) -> tuple[list[SemanticPoint], list[SemanticRelation], list[str], int]:
        """Concurrent extraction using thread pool."""
        all_sp: list[SemanticPoint] = []
        all_rel: list[SemanticRelation] = []
        errors: list[str] = []
        llm_calls = 0

        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_pair = {
                executor.submit(self._extract_one_pair, a, b): (a, b)
                for a, b in pairs
            }
            done_count = 0
            for future in as_completed(future_to_pair):
                a, b = future_to_pair[future]
                done_count += 1
                try:
                    sps, rels = future.result()
                    llm_calls += 1
                    # Write to store (thread-safe via per-manual connection)
                    self._write_results(manual_id, sps, rels)
                    all_sp.extend(sps)
                    all_rel.extend(rels)
                except Exception as exc:
                    errors.append(f"Pair {a['chunk_id']} x {b['chunk_id']}: {exc}")

                if done_count % 10 == 0:
                    log.info("[%s] %d/%d pairs done", manual_id, done_count, len(pairs))

        return all_sp, all_rel, errors, llm_calls

    def _write_results(self, manual_id: str, sps: list[SemanticPoint], rels: list[SemanticRelation]) -> None:
        """Write extracted points and relations to the graph store."""
        for sp in sps:
            sp.manual_id = manual_id
            self._store.upsert_semantic_point(manual_id, sp)
            for cid in sp.source_chunk_ids:
                self._store.link_chunk_to_sp(manual_id, cid, sp.sp_id)
        for rel in rels:
            self._store.upsert_relation(manual_id, rel)

    def build_all(self) -> list[BuildReport]:
        """Build graphs for every manual that has chunk artifacts."""
        reports = []
        manual_dirs = sorted(self._settings.chunks_dir.iterdir())
        for d in manual_dirs:
            if d.is_dir() and (d / "small_chunks.jsonl").exists():
                mid = d.name
                log.info("=== Building graph for %s ===", mid)
                r = self.build_manual(mid)
                reports.append(r)
        return reports
