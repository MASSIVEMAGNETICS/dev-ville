# Victor Heartbeat v1 — Frozen Architecture Contract

**Status:** FROZEN

**Canonical repository:** `MASSIVEMAGNETICS/dev-ville`

**Purpose:** Lock the canonical Victor heartbeat topology and responsibility boundaries so future development extends the organism through organs, adapters, workers, and experiments instead of spawning competing Victor cores.

## Canonical topology

```text
Observation
  -> Perception / Cognition
  -> ORCH_1
  -> Truth Compiler
  -> ORCH_2
  -> Choice / Authority
  -> Capability Lease
  -> Operator / RCP
  -> Independent Verifier
  -> CTP-0
  -> Chronos
  -> Reconstructed State
```

## Canonical ownership

### Truth Compiler
Owns epistemic state and evidence-derived truth classification.

Canonical states include:

- `VERIFIED`
- `UNKNOWN`
- `DENIED`

Truth Compiler may prioritize or evaluate evidence but may never manufacture evidence, silently promote `UNKNOWN` to truth, or collapse policy denial into uncertainty.

### Victor Heartbeat
Owns orchestration topology: the ordered, typed passage of observations through cognition, truth gating, authority, execution, verification, canonical commit, and restart-safe state reconstruction.

The heartbeat does not own truth, execution authority, verification authority, or canonical history.

### Victor Kernel
Owns identity, authority, legal state transitions, continuity invariants, and capability semantics.

Victor identity is not model weights and is not delegated to any replaceable cognition organ.

### Operator / Remediation Control Plane
Owns bounded execution only.

Execution must be constrained by explicit scoped authority. Execution workers do not acquire policy authority merely because they can perform an action.

### Independent Verifier
Owns outcome validation independent of the worker that performed the action.

A worker may report an outcome but may not canonically verify its own success.

### CTP-0
Owns the verified transition contract between observed execution evidence and canonical completion state.

### Chronos
Owns append-only canonical causal history and receipts for authoritative state transitions.

Canonical state must be reconstructable from durable evidence rather than transcript continuity.

### Shared Completion Fabric
Owns portfolio discovery, normalization, scoring, shared-bottleneck ranking, and prioritization.

It does not become a second execution authority or Victor core.

### Models and cognition organs
Models are replaceable cognition organs.

They may produce interpretations, proposals, candidate plans, predictions, or semantic projections. They do not own Victor identity, canonical truth, final authority, verification, or canonical history.

## Frozen invariants

1. **No new Victor core.**
2. No component may duplicate another component's canonical responsibility without an explicit migration/deprecation plan.
3. `UNKNOWN` may never silently become `VERIFIED`.
4. External effects require explicit, bounded, scoped authority.
5. Workers may not self-verify canonical success.
6. `DONE` requires independent verification through the canonical completion path.
7. Every authoritative state transition must produce durable canonical evidence and a Chronos receipt.
8. Restart must reconstruct authoritative state from canonical evidence, not hidden transcript/model memory.
9. Hosted cognition may not silently replace sovereign local cognition or become Victor's authority layer.
10. New capabilities enter as **organs, adapters, workers, or experiments**, not competing architectures.
11. External services may provide data or bounded capabilities; they do not become Victor's cognitive or constitutional authority.
12. Evidence provenance must remain inspectable across observation, decision, execution, verification, and commit.

## Change-control rule

Victor Heartbeat v1 architectural boundaries change only when measured evidence demonstrates that a frozen boundary fails a defined requirement, safety invariant, integration contract, or falsification test.

A new idea, terminology change, model improvement, or architectural preference is not sufficient reason to rewrite the frozen topology.

Any proposed v1 boundary change must include:

1. the failing invariant or measurable requirement;
2. reproducible evidence of the failure;
3. the smallest proposed boundary change;
4. compatibility and migration impact;
5. rollback strategy;
6. verification demonstrating that the change fixes the failure without weakening another invariant.

## Development rule after freeze

The next phase is:

```text
integration -> falsification -> canonicalization -> shipping -> monetization
```

Priority work should prove the frozen topology across real cross-repository boundaries, especially:

```text
real observation
  -> heartbeat
  -> canonical Truth Compiler
  -> bounded decision
  -> capability lease
  -> actual permitted action
  -> independent verification
  -> CTP-0
  -> Chronos commit
  -> process termination
  -> restart
  -> exact authoritative-state reconstruction
```

Until evidence disproves the frozen boundary, development should finish and integrate the existing system rather than create additional Victor cores.
