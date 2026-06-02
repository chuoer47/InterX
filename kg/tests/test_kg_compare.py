#!/usr/bin/env python3
"""Run answer pipeline with KG ON vs OFF and compare."""
import json, sys, time, logging
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, '/home/amax01/lingchen/YanD/InterX/answer/src')
sys.path.insert(0, '/home/amax01/lingchen/YanD/InterX/retrieval/src')
sys.path.insert(0, '/home/amax01/lingchen/YanD/InterX/kg/src')

from answer.config import QASettings
from answer.pipeline import answer

OUT = Path("/home/amax01/lingchen/YanD/InterX/kg/tests/kg_compare_results.json")
q = "How do I update the firmware on my camera?"
results = []

for kg_on, label in [(True, "KG-ON"), (False, "KG-OFF")]:
    settings = QASettings.load()
    if not kg_on:
        object.__setattr__(settings.kg, 'enabled', False)
    
    started = time.monotonic()
    try:
        result = answer(q, settings=settings)
        elapsed = time.monotonic() - started
        entry = {
            "label": label, "kg": kg_on, "time_s": round(elapsed, 2),
            "small_hits": result.recall_meta.small_hit_count,
            "kg_expansion": result.recall_meta.kg_expansion_count,
            "mid_hits": result.recall_meta.mid_hit_count,
            "big_hits": result.recall_meta.big_hit_count,
            "answer": result.final_answer.content[:500],
        }
    except Exception as e:
        elapsed = time.monotonic() - started
        entry = {"label": label, "kg": kg_on, "time_s": round(elapsed, 2), "error": str(e)}
    
    results.append(entry)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"[{label}] done in {entry.get('time_s', '?')}s", flush=True)

print("ALL DONE", flush=True)
