# Chinese Agentic RAG Manual QA Task PRD

## Task

Complete the long-running task of answering every Chinese question in `agentic-rag/ch-question.csv` using the Chinese product manuals and images in `agentic-rag/ch-manual/`.

## Source of Truth

Use `$answer-ch-agentic-rag` for retrieval workflow, reasoning requirements, image handling, and v2 answer formatting.

Do not duplicate or override the skill rules in this PRD. If answer-quality or format rules are needed, read:

- `agentic-rag/.codex/skills/answer-ch-agentic-rag/SKILL.md`
- `agentic-rag/.codex/skills/answer-ch-agentic-rag/references/v2-format.md`

Do not reuse prior generated answers from Chinese answer artifacts, old submissions, or any other answer artifact. Each question must be answered from scratch from the source question row plus `agentic-rag/ch-manual`.

## Files

Inputs:

- `agentic-rag/ch-question.csv`
- `agentic-rag/ch-manual/*.md`
- `agentic-rag/ch-manual/插图/*`

Control:

- `agentic-rag/ch-todo.csv`

Per-question outputs:

- `agentic-rag/tmp/ch-answers/per_question/{id}.json`
- `agentic-rag/tmp/ch-answers/evidence-notes/{id}.md`

Aggregate outputs:

- `agentic-rag/tmp/ch-answers/ch-answers.csv`
- `agentic-rag/tmp/ch-answers/ch-answers.jsonl`

## Resume Protocol

1. Read this PRD.
2. Read and use `$answer-ch-agentic-rag`.
3. Inspect `agentic-rag/ch-todo.csv`.
4. Pick the next row with `status=pending`, unless the user asks for a specific ID or range.
5. If there are no pending rows, inspect `needs_review` rows.
6. Work one question per subagent. Each subagent must start from source files, not from prior generated answers.
7. Run only one per-question subagent at a time unless the user explicitly asks for parallel batches.
8. After each answer, validate the per-question JSON, aggregate it if valid, and update `ch-todo.csv` before moving on.

## Todo Statuses

- `pending`: not started.
- `in_progress`: actively being worked on.
- `answered`: answer drafted, awaiting final self-check or artifact write.
- `needs_review`: answer exists but may have retrieval, image, format, or completeness risk.
- `blocked`: cannot answer with current evidence or tooling; explain the blocker in `notes`.
- `done`: final v2-format answer has been written and checked.

## Progress Rules

- Do not edit `ch-question.csv` or the source manuals while answering.
- Keep the current answer artifact and `ch-todo.csv` consistent.
- Update `manual_guess`, `answer_path`, `image_ids`, `status`, `notes`, and `updated_at` as work proceeds.
- If a later pass changes an answer, update the same todo row instead of creating a duplicate task.
- If context is resumed after a long interruption, trust `ch-todo.csv` for status but reopen source evidence before revising any answer.

## Completion Criteria

The task is complete when every Chinese question ID in `agentic-rag/ch-question.csv` has a final v2-format answer artifact and `agentic-rag/ch-todo.csv` marks every row as `done`.
