# Tests

## Structure
- `integration/`: automated API-level tests
- `manual/`: manual verification notes and captured issues
- `results/`: test outputs and snapshots (git-ignored if needed later)

## Current Flow
1. Start stack
2. Run smoke test
3. Run stream test
4. Run semantic cache test
5. Record failures in `manual/issues.md`
