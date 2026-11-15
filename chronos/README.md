# Canonical Execution Chronos Ledger

`canonical_execution.jsonl` is the append-only Chronos stream for canonical execution-state transitions that affect the Victor operating baseline.

## Ownership

This stream lives in `MASSIVEMAGNETICS/dev-ville` because this repository already owns the canonical execution map and the `ChronosLedger` implementation used to verify append-only SHA-256-linked receipts.

## Append-only law

Existing ledger lines are immutable historical evidence.

A valid change may only append one or more new JSONL records to the end of the file. It may not edit, delete, reorder, truncate, or replace an existing line. A correction or supersession is itself a new event that points to the current Chronos head.

Each appended record must:

1. use the next contiguous `sequence`;
2. set `parent_event_hash` to the previous event hash;
3. set `previous_chain_hash` to the previous receipt chain hash;
4. compute `event_id`, `event_hash`, and `chain_hash` with canonical JSON + SHA-256;
5. survive a complete replay through the Chronos verifier.

## Writer serialization

Persisted appends acquire an OS advisory lock on a sibling `<ledger>.lock` file (`flock` on POSIX, `msvcrt.locking` on Windows). The lock serializes cooperating local processes. A writer whose in-memory head is stale reloads and validates the existing append-only prefix before retrying; `Trace0Observer` retries a stale candidate up to three times. Direct stale `append()` calls fail with `StaleChronosHeadError`. If the on-disk prefix has been truncated or rewritten, the append fails closed and leaves the file untouched.

The lock is local-filesystem coordination, not a distributed lock or a guarantee for arbitrary network filesystems. All writers must use `ChronosLedger`; direct JSONL writes bypass the lock. Readers see the snapshot loaded by their ledger instance and should reopen to observe later appends. The `empire_sync/manifest.json` single-writer/multi-reader model remains unchanged.

## Authority boundary

This ledger records state and evidence. It does not grant execution authority, merge authority, deployment authority, or permission to weaken any existing Victor invariant.

## Genesis

The first record anchors the post-freeze canonical execution baseline documented by `CANONICAL_EXECUTION_MAP.md` and the bounded public Proof Ledger. Future state changes are appended; the genesis record is never rewritten.
