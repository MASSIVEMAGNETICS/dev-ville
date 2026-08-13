# Empire Control Plane: Chronos Receipt Continuity Gap

## Finding

`SelfCorrectingEmpire.run()` currently writes a standalone JSON receipt under `state/empire_receipts/` after assessment, remediation, and re-verification. That receipt is not appended to the TRACE-0 / Chronos hash chain.

This leaves a continuity defect: after restart, the manifest can show the current state and the standalone receipt can describe a prior mutation, but the canonical Chronos history does not itself prove why the Empire topology changed.

## Required invariant

```text
Empire assessment
  -> remediation decision
  -> bounded mutation
  -> re-verification
  -> ControlPlaneReceipt
  -> TRACE-0 Informatron
  -> Chronos append
  -> chain verification
```

The standalone JSON receipt may remain as a human-readable projection, but Chronos must become the canonical causal record.

## Patch contract

A compliant implementation should:

1. Reuse `trace0_chronos.ChronosLedger` and `Trace0Observer`; do not create a second ledger implementation.
2. Append exactly one Informatron for every completed control-plane run, including `--check` runs.
3. Bind the event payload/evidence to:
   - control-plane `receipt_id`;
   - `manifest_hash_before`;
   - `manifest_hash_after`;
   - gap counts;
   - unresolved critical count;
   - remediation results.
4. Persist the Chronos chain under a deterministic state path.
5. Re-open the ledger after writes and require `verify_chain()` to pass.
6. Preserve the existing standalone receipt for inspection/backward compatibility.
7. Fail closed if the Chronos append or chain verification fails; do not report the run as fully committed.

## Acceptance tests

- A demotion run writes the standalone receipt and one Chronos event.
- A verified-promotion run writes one additional Chronos event linked to the previous chain head.
- A check-only run does not mutate the manifest but still records the assessment receipt in Chronos.
- Reloading the JSONL ledger after each case verifies the full chain.
- Tampering with a persisted event or receipt causes restore/verification to fail.
- Existing `test_empire_control_plane.py` behavior remains unchanged.
- Full `python -m unittest discover -v -p "test_*.py"` passes on Python 3.11 and 3.12.

## Scope boundary

This maintenance item does not add arbitrary execution, new remediation handlers, network authority, production deployment capability, or broader self-modification. It only closes the causal-record continuity gap for operations the control plane already performs.
