# Agentic RAG English Manual QA Task PRD

## Task

Complete the long-running task of answering every English question in `agentic-rag/question.csv` using the English product manuals and images in `agentic-rag/en-manual/`.

## Source of Truth

Use `$answer-agentic-rag` for retrieval workflow, reasoning requirements, image handling, and v2 answer formatting.

Do not duplicate or override the skill rules in this PRD. If answer-quality or format rules are needed, read:

- `agentic-rag/.codex/skills/answer-agentic-rag/SKILL.md`
- `agentic-rag/.codex/skills/answer-agentic-rag/references/v2-format.md`

Do not reuse prior generated answers from `v2/artifacts`, old submissions, or any other answer artifact. Each question must be answered from scratch from the source question row plus `agentic-rag/en-manual`.

## Files

Inputs:

- `agentic-rag/question.csv`
- `agentic-rag/en-manual/*.md`
- `agentic-rag/en-manual/插图/*`

Control:

- `agentic-rag/todo.csv`

Per-question outputs:

- `agentic-rag/tmp/answers/per_question/{id}.json`
- `agentic-rag/tmp/answers/evidence-notes/{id}.md`

Aggregate outputs:

- `agentic-rag/tmp/answers/answers.csv`
- `agentic-rag/tmp/answers/answers.jsonl`

## Resume Protocol

1. Read this PRD.
2. Read and use `$answer-agentic-rag`.
3. Inspect `agentic-rag/todo.csv`.
4. Pick the next row with `status=pending`, unless the user asks for a specific ID or range.
5. If there are no pending rows, inspect `needs_review` rows.
6. Work one question per subagent. Each subagent must start from source files, not from prior generated answers.
7. Run only one per-question subagent at a time unless the user explicitly asks for parallel batches.
8. After each answer, validate the per-question JSON, aggregate it if valid, and update `todo.csv` before moving on.

## Todo Statuses

- `pending`: not started.
- `in_progress`: actively being worked on.
- `answered`: answer drafted, awaiting final self-check or artifact write.
- `needs_review`: answer exists but may have retrieval, image, format, or completeness risk.
- `blocked`: cannot answer with current evidence or tooling; explain the blocker in `notes`.
- `done`: final v2-format answer has been written and checked.

## Progress Rules

- Do not edit `question.csv` or the source manuals while answering.
- Do not read or reuse generated answers under `v2/artifacts`, old submissions, or previous non-source answer files.
- Keep the current answer artifact and `todo.csv` consistent.
- Update `manual_guess`, `answer_path`, `image_ids`, `status`, `notes`, and `updated_at` as work proceeds.
- If a later pass changes an answer, update the same todo row instead of creating a duplicate task.
- If context is resumed after a long interruption, trust `todo.csv` for status but reopen source evidence before revising any answer.

## Completion Criteria

The task is complete when every English question ID in `agentic-rag/question.csv` has a final v2-format answer artifact and `agentic-rag/todo.csv` marks every row as `done`.
