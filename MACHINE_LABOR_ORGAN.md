# Dev-Ville → Victor Machine-Labor Organ

## Status

This migration slice removes four simulation-only claims from the authoritative Dev-Ville runtime:

1. random research → **inspectable evidence probes**;
2. random beta testing → **executable integration/E2E scenarios**;
3. arbitrary confidence numbers → **evidence strength + empirical calibration only after resolved outcomes**;
4. transient simulation events → **TRACE-0 Informatrons + Chronos hash-chain receipts**.

`VictorMachineLaborCompany` is the integration runtime. Legacy simulator classes remain available for demo compatibility, but the Victor runtime bypasses the randomized `ResearcherAgent.complete_task()` and `BetaTesterAgent.complete_task()` implementations.

## Research law

Research may state what it observed. It may not invent external facts.

The current sovereign source is the local runtime itself: Python version, importable modules, and installed executables. A technology is only reported as locally available when the runtime can reproduce that observation.

If multiple candidates are equally supported by the collected evidence, the organ returns **no winner** rather than breaking the tie arbitrarily.

External benchmark, advisory, ecosystem-health, and performance evidence are explicit unknowns until an evidence source is added.

## Confidence law

`evidence_strength` is not a probability. It is a deterministic ratio of weighted supporting versus contradictory evidence.

`confidence` remains `null` until enough prior predictions have been resolved against real outcomes. Once sufficient history exists, confidence is the empirical success frequency for the matching evidence-strength bin. Brier score is retained as a calibration diagnostic.

This means an uncalibrated system says **uncalibrated** instead of printing a fake `0.92`.

## Executable beta law

Beta outcomes come from exact artifact bytes. The beta organ:

- rejects unsafe artifact paths;
- hashes the bundle;
- compiles all Python artifacts;
- runs discovered test suites;
- executes artifact entrypoints;
- when both `FrontendController` and `BackendService` exist, executes a real frontend→backend data round trip;
- emits a SHA-256 evidence receipt.

A failed scenario becomes an observed issue. No bugs, severity counts, reproducibility flags, or UX scores are randomly generated.

`ux_score` is deliberately `null`: executable testing is not a valid substitute for human UX measurement.

## TRACE-0 / Chronos law

TRACE-0 is observation-only. It records runtime events but does not grant authority.

Each Informatron carries:

- schema version;
- causal sequence;
- UTC timestamp;
- actor/action/entity;
- payload;
- provenance;
- evidence;
- authority label;
- parent event hash;
- content-derived event ID.

Chronos verifies the event ID, event hash, previous chain hash, and chain hash for every append. Optional JSONL persistence reloads and verifies the existing ledger before new events can continue. Saved project snapshots may restore a chain only when the ledger is empty; if a persistent ledger already exists, the saved chain must be a verified prefix.

SHA-256 makes history tamper-evident. It does **not** authenticate actor identity; signed actor identity remains a separate Identity Kernel requirement.

## Runtime flow

```text
Human Directive
      ↓
Dev-Ville Scheduler
      ↓
Evidence Research ───────────────┐
      ↓                          │
Builder → Artifact              │
      ↓                          │
Verification Boundary           │
      ↓                          │
Executable Beta / E2E           │
      ↓                          │
Evidence Receipts               │
      ↓                          │
Verified DONE / REWORK          │
                                 ↓
                         TRACE-0 Informatrons
                                 ↓
                         Chronos hash chain
```

## Remaining non-authoritative simulation

This slice does **not** yet make the CEO/planner intelligent, make deployment real, provide signed actor identity, or provide an OS-grade untrusted-code sandbox. The existing code-generation templates also remain templates rather than a sovereign coding model.

Those boundaries must remain explicit until replaced.
