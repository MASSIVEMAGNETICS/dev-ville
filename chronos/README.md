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

## Authority boundary

This ledger records state and evidence. It does not grant execution authority, merge authority, deployment authority, or permission to weaken any existing Victor invariant.

## Genesis

The first record anchors the post-freeze canonical execution baseline documented by `CANONICAL_EXECUTION_MAP.md` and the bounded public Proof Ledger. Future state changes are appended; the genesis record is never rewritten.
