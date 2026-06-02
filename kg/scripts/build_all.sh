#!/bin/bash
# Build all manuals sequentially with concurrent LLM extraction
cd "$(dirname "$0")/.."
PYTHONPATH=src .venv/bin/python -c "
import logging, time, sys
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)

from kg.config import KGSettings
from kg.graph_store import GraphStore
from kg.builder import GraphBuilder
from pathlib import Path

settings = KGSettings.load()
store = GraphStore(settings.graph_store.db_path)
builder = GraphBuilder(settings, store, concurrent=True, max_workers=6)

manuals = sorted([d.name for d in settings.chunks_dir.iterdir()
                  if d.is_dir() and (d / 'small_chunks.jsonl').exists()])

total = len(manuals)
t0 = time.time()

for idx, mid in enumerate(manuals, 1):
    # Skip if already fully built (has SEMANTIC_REL edges)
    try:
        stats = store.count_nodes(mid)
        if stats.get('SEMANTIC_REL', 0) > 0:
            print(f'[{idx}/{total}] SKIP {mid} (already built, {stats[\"SEMANTIC_REL\"]} rels)')
            continue
    except Exception:
        pass

    print(f'[{idx}/{total}] Building {mid}...')
    sys.stdout.flush()
    report = builder.build_manual(mid)
    elapsed = time.time() - t0
    print(f'  -> {report.total_semantic_points} SPs, {report.total_relations} rels, {report.llm_calls} LLM calls, {len(report.errors)} errors')
    print(f'  -> Elapsed: {elapsed/60:.1f}min')
    sys.stdout.flush()

print(f'\nAll done in {(time.time()-t0)/60:.1f} minutes')
" 2>&1
