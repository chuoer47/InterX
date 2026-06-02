---
name: kg-cold-start
description: >
  Build knowledge graphs from agentic-rag evidence refs for the InterX project.
  Use when the user asks to build, cold-start, bootstrap, or populate the KG layer
  using existing agentic-rag Q&A evidence. Covers evidence parsing, line-to-chunk
  mapping, graph construction, LLM-driven semantic edge extraction, and Kùzu graph writing.
---

# KG Cold-Start Skill

Build per-manual knowledge graphs from existing agentic-rag evidence data.
No blind LLM chunk-pair comparison — all edges are grounded in real Q&A evidence.

## Core Constraints

- **Zero LLM during retrieval.** LLM is only used during build time for edge extraction.
- **Two edge types only:**
  - `CO_EVIDENCE` (weight 0.5): script-built from evidence co-occurrence, no LLM needed
  - `SEMANTIC` (weight 1.0): LLM-extracted, with natural-language description
- **Retrieval uses deterministic BFS** with weight × hop-decay scoring.
- **Source files are identical** between `agentic-rag/{en,ch}-manual/` and `process/data/`.
- **Chunks have `source_span: {start_line, end_line}`** — enables exact line→chunk mapping.
- **Kùzu memory leak workaround**: process one manual at a time, close connection after each.

## Workflow (5 Phases)

### Phase 1: Resolve Evidence Refs

```bash
python scripts/resolve_refs.py \
  --answers-dir InterX/agentic-rag/answers \
  --process-dir InterX/process/artifacts/manuals \
  --output InterX/kg/state/evidence_resolved.json
```

Parses 350 agentic-rag answers. Handles dict/string ref formats, multiple line
number formats (dash range, bracket list, mixed). Result: 1699/1798 refs (94.5%).

### Phase 2: Map Lines to Chunks

```bash
python scripts/line_to_chunk.py \
  --evidence InterX/kg/state/evidence_resolved.json \
  --process-dir InterX/process/artifacts/manuals \
  --output InterX/kg/state/evidence_mapped.json
```

Uses `source_span` interval matching (binary search) to resolve line ranges to chunk_ids.
482 refs map to multiple chunks.

### Phase 3: Build Graph Structure + CO_EVIDENCE

```bash
python scripts/write_graph.py build \
  --evidence InterX/kg/state/evidence_mapped.json \
  --graph-dir InterX/kg/state/graph.db \
  --process-dir InterX/process/artifacts/manuals
```

Creates per-manual Kùzu databases with:
- Structural nodes (Manual, BigChunk, MidChunk, SmallChunk)
- Question nodes (from Q&A data)
- ANSWERS edges (SmallChunk → Question)
- CO_EVIDENCE edges (SmallChunk ↔ SmallChunk, from co-occurrence)

**Note:** If build crashes due to Kùzu memory leak, use `build_remaining.py` to resume:

```bash
python scripts/build_remaining.py \
  --graph-dir InterX/kg/state/graph.db \
  --evidence InterX/kg/state/evidence_mapped.json \
  --process-dir InterX/process/artifacts/manuals
```

### Phase 4: LLM Semantic Extraction

```bash
python scripts/extract_semantic.py \
  --evidence InterX/kg/state/evidence_mapped.json \
  --process-dir InterX/process/artifacts/manuals \
  --output InterX/kg/state/semantic_edges.json \
  --batch-size 5 \
  --max-chunks-per-answer 8 \
  --max-pairs-per-answer 10
```

Serial LLM calls with batched prompts (5 pairs per call). Handles 429 rate limits
with exponential backoff (2-5 min). Logs success/failure separately.
Supports `--resume` for interrupted runs. ~500 batches, ~7.5h total.

LLM config: `mimo-v2.5-pro`, temperature 0.1, via `https://token-plan-cn.xiaomimimo.com/v1`.

### Phase 5: Write SEMANTIC Edges + Validate

```bash
# Write SEMANTIC edges to graph
python scripts/enrich_remaining.py \
  --graph-dir InterX/kg/state/graph.db \
  --semantic InterX/kg/state/semantic_edges.json

# Validate
python scripts/write_graph.py stats --graph-dir InterX/kg/state/graph.db
```

## File Structure

```
kg-cold-start/
├── SKILL.md
├── scripts/
│   ├── resolve_refs.py           # Phase 1: parse evidence refs
│   ├── line_to_chunk.py          # Phase 2: line → chunk_id
│   ├── write_graph.py            # Phase 3: build graph + stats
│   ├── build_remaining.py        # Phase 3 resume: incremental build
│   ├── extract_semantic.py           # Phase 4: batched LLM extraction
│   ├── phase3_extract_semantic.py # Phase 4 alt: concurrent (deprecated)
│   └── enrich_remaining.py       # Phase 5: write SEMANTIC edges
├── references/
│   ├── graph_schema.md           # Graph schema + weight design
│   └── extraction_prompt.md      # LLM prompt for Phase 4
├── agents/
│   └── openai.yaml
└── logs/                         # Phase 4 runtime logs
    ├── phase3_batch.log
    ├── phase3_success.log
    └── phase3_failure.log
```

## Data Flow

```
agentic-rag/answers/ (350 Q&A)
    ↓ Phase 1: resolve_refs.py
evidence_resolved.json (1699 refs)
    ↓ Phase 2: line_to_chunk.py
evidence_mapped.json (chunk_ids resolved)
    ↓ Phase 3: write_graph.py build
Kùzu graph.db (structural nodes + Question + ANSWERS + CO_EVIDENCE)
    ↓ Phase 4: extract_semantic.py
semantic_edges.json (1053 SEMANTIC edges)
    ↓ Phase 5: enrich_remaining.py
Kùzu graph.db (complete)
```

## Current Graph Stats

| Nodes | Count | | Edges | Count | Weight |
|-------|-------|-|-------|-------|--------|
| Manual | 39 | | CO_EVIDENCE | 48,508 | 0.5 |
| SmallChunk | 7,215 | | SEMANTIC | 3,084 | 1.0 |
| MidChunk | 4,365 | | ANSWERS | 2,787 | 0.5 |
| BigChunk | 3,718 | | HAS_MID/HAS_SMALL | 9,514 | - |
| Question | 350 | | | | |
