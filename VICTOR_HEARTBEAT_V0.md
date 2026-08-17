# Victor Canonical Heartbeat v0

This slice turns the current Victor continuity/authority substrate into one executable,
falsifiable heartbeat without replacing the existing sovereign driver.

## Canonical path

```text
observation
  -> perception scouts (variables only)
  -> 12 parallel meaning projections
  -> cross-reference / dependency relations
  -> semantic scan + graph mapping
  -> future-field candidate trajectories
  -> reality-attractor / reality-lever ranking
  -> ORCH_1 coarse collapse
  -> deep interrogation + bounded truth gate
  -> ORCH_2 final collapse
  -> agency plan
  -> capability lease
  -> bounded Aether reference adapter
  -> Completion Engine
  -> independent verification
  -> CTP-0 transition
  -> TRACE-0 / Chronos
  -> rebuildable VictorWorldModel
```

## Why this exists

The repository already has strong pieces: TRACE-0/Chronos, the reconstructable world
model, capability-aware choice, identity continuity, bounded organs, independent
verification, and restart tests. The missing launch-gate property was one explicit
contract connecting perception through verified action and canonical state.

`victor_heartbeat_v0.py` is that integration seam.

## Hard boundaries

The built-in Aether adapter is intentionally narrow:

- allowed actions: `noop`, `write_text`;
- writes are restricted to an explicit sandbox root;
- absolute paths and `..` traversal are rejected before lease issuance;
- output bytes are capped by the lease;
- leases expire;
- no network access is introduced;
- no subprocess execution is introduced;
- no repository merge/deploy/payment/secret authority is introduced;
- execution receipts are independently reconstructed and verified before canonicalization.

The deterministic perception/interpreter implementation is a **reference contract**,
not a claim of general semantic intelligence. Stronger local neural/symbolic organs can
replace those stages later while the authority and verification boundaries remain fixed.

## Three collapses stay separate

1. **Cognitive collapse** — ORCH_2 selects the candidate Victor believes should be acted on.
2. **Reality collapse** — the leased Aether adapter actually performs the bounded action.
3. **Canonical collapse** — independent verification permits the outcome into CTP/Chronos.

A worker success claim alone can never become canonical truth.

## Restart invariant

A completed heartbeat has a deterministic heartbeat identity over its observation,
provenance, context, and candidate set. On restart:

1. Chronos reloads and verifies its chain.
2. `VictorWorldModel` rebuilds from Informatrons.
3. Re-submitting the identical heartbeat returns the persisted result.
4. The action is **not executed twice** and no duplicate Chronos event is appended.

## Verification

The dedicated tests cover:

- full perception -> dual-ORCH -> lease -> write -> verification -> CTP -> Chronos path;
- all twelve meaning dimensions;
- graph materialization of variables, projections, candidate, lease, and outcome;
- chain validity;
- kill/restart-style reconstruction;
- idempotent replay without repeated side effects;
- path traversal rejection before lease issuance;
- missing-evidence fail-closed behavior.

The repository-wide `Victor Driver Tests` workflow already executes
`python -m unittest discover -v -p "test_*.py"` on Python 3.11 and 3.12, so this slice
joins the canonical regression gate automatically.

## Non-claims

This slice does not prove AGI, consciousness, superior general reasoning, or arbitrary
real-world autonomy. It proves a narrower and more valuable engineering property:

> one bounded Victor heartbeat can preserve a typed causal path from observation,
> through deliberation and authority, into a verified external state change and then
> survive process restart without losing or duplicating that history.
