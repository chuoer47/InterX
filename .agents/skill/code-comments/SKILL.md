---
name: code-comments
description: >
  Code commenting standards for the InterX project. Use when adding, reviewing,
  or auditing code comments across any InterX package (process, retrieval, answer,
  chat, web, kg). Use when the user asks to improve comment coverage, add comments
  to code, review comment quality, or enforce commenting standards.
---

# InterX Code Commenting Standards

## Core Principle

**Comment WHY, not WHAT.** Do not add comments just for coverage. Only comment where
the code's intent is non-obvious, where a key algorithm operates, or where a critical
design decision was made.

## Rules

### Must Follow

1. **Language**: All comments in English. No Chinese in code comments.
2. **Style**: Concise. One line preferred. Multi-line only for algorithms.
3. **Coverage**: Measured per-package, not per-file. Target ≥ 30%.
4. **Validation**: Run existing tests after every commenting pass.
5. **No boilerplate**: No copyright headers, no license blocks, no `# end of function`.

### What TO Comment

- Key algorithms (RRF fusion, BM25 scoring, graph traversal, chunk packing)
- Non-obvious design decisions (why a fallback exists, why a threshold was chosen)
- Workarounds with context (Kùzu MERGE+SET limitation, reasoning model token budget)
- Module-level purpose (one-line docstring per `.py` file)
- Class-level purpose (one-line docstring per class)
- Public API functions (brief docstring explaining contract)

### What NOT TO Comment

- Obvious assignments and simple getters
- Standard CRUD operations
- Type information already in annotations
- `to_dict()` methods
- Self-explanatory variable names
- `__init__` field assignments

## Docstring Format

### Module

```python
"""Main retrieval orchestrator and public search entry points."""
```

One sentence. No blank line after. Place before imports.

### Class

```python
class BM25Index:
    """
    In-memory BM25 index over the small-chunk corpus.

    Sparse retrieval complements dense recall by handling exact product terms,
    model numbers, and short keyword queries that embeddings may smooth away.
    """
```

First line: what it is. Blank line. Then why it exists or how it fits.

### Function — simple

```python
def reload() -> None:
    """Drop cached settings and corpus state so the next call reloads fresh artifacts."""
```

One line. Describe the effect, not the steps.

### Function — complex algorithm

```python
def rrf_fuse(channels, *, config, top_k):
    """
    Fuse multiple ranked lists with Reciprocal Rank Fusion.

    RRF is intentionally rank-based rather than score-based, which makes it much
    easier to combine BM25 and dense channels whose raw score distributions are
    not directly comparable.
    """
```

First line: what. Blank line. Then why this approach.

### Inline comments

```python
# The retrieval package caches corpus state at module scope so repeated interactive
# queries do not keep reloading JSON artifacts and rebuilding BM25 indexes.
_settings: RetrievalSettings | None = None
```

Use `#` for explaining intent of a block, not for describing individual lines.

## Anti-patterns

```python
# BAD: describing what the code does
x = x + 1  # increment x

# BAD: restating the type annotation
name: str  # string type

# BAD: padding for coverage
def get_name(self):
    # Get name
    return self.name

# GOOD: explaining non-obvious why
# Retry is limited to transient HTTP failures because embedding jobs are often
# part of long-running batch builds where occasional rate limiting is expected.
```

## Checklist Before Committing Comments

- [ ] No comment restates what the code obviously does
- [ ] Every algorithm has a docstring explaining the approach
- [ ] All comments are in English
- [ ] Tests still pass
- [ ] Package-level coverage ≥ 30%
