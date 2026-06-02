# Graph Schema

## Node Types

| Node | Key Fields | Source |
|------|-----------|--------|
| Manual | id, name | process artifacts |
| BigChunk | id, manual_id, section_title | process chunks |
| MidChunk | id, manual_id, big_chunk_id | process chunks |
| SmallChunk | id, manual_id, mid_chunk_id, txt, section_title | process chunks |
| Question | id, question_text, answer_text, lang, manual_guess | agentic-rag answers |

## Edge Types

| Edge | From → To | Weight | Builder | Properties |
|------|----------|--------|---------|------------|
| HAS_BIG | Manual → BigChunk | - | script | - |
| HAS_MID | BigChunk → MidChunk | - | script | - |
| HAS_SMALL | MidChunk → SmallChunk | - | script | - |
| ANSWERS | SmallChunk → Question | 0.5 | script | - |
| CO_EVIDENCE | SmallChunk ↔ SmallChunk | 0.5 | script | question_id |
| SEMANTIC | SmallChunk ↔ SmallChunk | 1.0 | LLM | description |

## Retrieval Scoring

```
score(expanded_chunk) = edge_weight × hop_decay × seed_score
hop_decay = 1.0 / (1.0 + 0.3 × hops)
```

- SEMANTIC edge: weight 1.0 (LLM-confirmed relationship)
- CO_EVIDENCE edge: weight 0.5 (co-occurrence, no semantic confirmation)
- ANSWERS edge: weight 0.5 (chunk contributed to answering question)

## Kùzu Reserved Word Workaround

Column names must avoid: `description`, `text`, `label`, `type`
Use instead: `descr`, `txt`, `lbl`, `ptype`
