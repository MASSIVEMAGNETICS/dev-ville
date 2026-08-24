# Canonical Execution Ledger Policy

This file defines the repository-level handling rule for `chronos/canonical_execution.jsonl`.

- The ledger is an append-only evidence stream.
- Existing records are historical facts about what was recorded at that point in time; they are never rewritten to reflect later understanding.
- Corrections, invalidations, supersessions, reversals, and newly verified states are appended as later events.
- The ledger's CI gate verifies both the complete Chronos hash chain and the exact immutable prefix inherited from the target branch or previous `main` commit.
- A green ledger check is evidence that the recorded chain and append-only prefix are internally consistent. It is not authority to execute or a guarantee that every referenced external claim is independently true.
- `CANONICAL_EXECUTION_MAP.md` remains the human-readable current-state projection. The JSONL ledger preserves the historical transition sequence that produced that state.

This policy must be changed by a separate reviewed append-only-governance change; changing this policy does not retroactively alter any ledger record.
