#!/usr/bin/env python3
"""Build graphs for all manuals sequentially."""
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from kg.config import KGSettings
from kg.graph_store import GraphStore
from kg.builder import GraphBuilder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

def main():
    settings = KGSettings.load()
    store = GraphStore(settings.graph_store.db_path)
    builder = GraphBuilder(settings, store, concurrent=True, max_workers=6)

    manuals = sorted([d.name for d in settings.chunks_dir.iterdir()
                      if d.is_dir() and (d / "small_chunks.jsonl").exists()])

    total = len(manuals)
    t0 = time.time()
    done = 0

    for idx, mid in enumerate(manuals, 1):
        try:
            stats = store.count_nodes(mid)
            if stats.get("SEMANTIC_REL", 0) > 0:
                log.info("[%d/%d] SKIP %s (already built, %d rels)", idx, total, mid, stats["SEMANTIC_REL"])
                done += 1
                continue
        except Exception:
            pass

        log.info("[%d/%d] Building %s...", idx, total, mid)
        sys.stdout.flush()
        try:
            report = builder.build_manual(mid)
            elapsed = time.time() - t0
            log.info("  -> %d SPs, %d rels, %d LLM calls, %d errors",
                     report.total_semantic_points, report.total_relations,
                     report.llm_calls, len(report.errors))
            log.info("  -> Elapsed: %.1fmin", elapsed / 60)
            done += 1
        except Exception as exc:
            log.error("  -> FAILED: %s", exc)
        sys.stdout.flush()

    log.info("\nDone: %d/%d manuals in %.1f minutes", done, total, (time.time() - t0) / 60)


if __name__ == "__main__":
    main()
