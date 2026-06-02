# SEMANTIC Edge Extraction Prompt

## System Prompt (batched, used by phase3_batch.py)

You are a knowledge graph edge extractor for product manuals.
Given a question and multiple pairs of text chunks used as evidence,
decide for EACH pair if the two chunks have a SEMANTIC relationship useful for multi-hop retrieval.

YES when:
- Cause-effect: one describes a problem/symptom, the other describes its cause
- Problem-solution: one describes an issue, the other provides the fix
- Sequential dependency: one describes a precondition for the other
- Conditional logic: "if X then Y" spans across chunks

NO when:
- Chunks merely co-occur in the same section
- Chunks describe unrelated topics that happen to answer the same question
- The connection is vague or topical

Output a JSON array, one element per pair, in the same order.
Keep description in the same language as the chunks. Concise: one sentence, ≤50 chars.
Output strict JSON array only, no markdown fences.

## User Prompt Template (batched)

```
Question: {question}

Pair 1:
Chunk A ({chunk_a_id}) [{section_a}]:
{text_a}

Chunk B ({chunk_b_id}) [{section_b}]:
{text_b}

Pair 2:
...

Output a JSON array of N objects, each with: pair (1-N), has_semantic (bool), description (string).
```

## Output Format (batched)

```json
[
  {"pair": 1, "has_semantic": true, "description": "滤网堵塞导致出风量减小"},
  {"pair": 2, "has_semantic": false, "description": ""},
  {"pair": 3, "has_semantic": true, "description": "清洗步骤解决滤网堵塞问题"}
]
```

## Single-Pair Format (alternative, for manual testing)

System prompt is the same but for one pair only. Output:
```json
{"has_semantic": true, "description": "..."}
```

## Notes

- Batch size: 5 pairs per LLM call (configurable via --batch-size)
- Temperature: 0.1 for deterministic output
- Max tokens: 2048 (batched) / 512 (single)
- Keep description in the same language as the chunks (中文 or English)
- Description should be concise: one sentence, ≤50 chars
- Do NOT output markdown fences around JSON
- LLM config: mimo-v2.5-pro via https://token-plan-cn.xiaomimimo.com/v1
