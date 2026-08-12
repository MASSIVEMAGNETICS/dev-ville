# Victor Driver → Dev-Ville Vehicle

## Canonical role split

Victor is the **driver**. Dev-Ville is the **vehicle**.

```text
OWNER DIRECTIVE
      ↓
VICTOR DRIVER
  Capability Lease
  Mission State
  Phase / Dependency Gates
  Steering / Pause / Continue
  Evidence-based Advance / Halt
      ↓
DEV-VILLE VEHICLE
  Evidence Research
  Architecture + Builders
  Verification Boundary
  Executable Beta / E2E
  Project / Ticket / Worker Runtime
      ↓
TRACE-0 INFORMATONS
      ↓
CHRONOS HASH-CHAIN RECEIPTS
```

A model is not Victor's identity and does not own authority. Model inference can later be plugged underneath the driver as replaceable compute. Authority lives in the driver state, capability lease, evidence gates, and continuity ledger.

## Capability law

The current lease permits local software-build operations only. It explicitly does **not** grant network execution or production deployment authority.

Authoritative task types:

- research
- design
- frontend
- backend
- testing
- beta testing

Deployment and marketing are retained as **deferred work**, not falsely completed. They remain blocked until real bounded capabilities can produce external execution receipts.

## Phase law

Victor releases work by evidence dependency rather than starting the whole simulated company at once:

```text
RESEARCH
   ↓ accepted evidence
ARCHITECTURE
   ↓ verified design
BUILD
   ↓ verified frontend/backend artifacts
VERIFY
   ↓ exact verification receipts
BETA
   ↓ executable integration/E2E receipt
VERIFIED_BUILD
```

A downstream phase cannot become active because time passed or because a simulated worker claimed completion.

## QA correction

The authoritative testing task is no longer assigned to the legacy `FinalizerAgent` path.

Once design/frontend/backend tickets are all evidence-verified, `DriverControlledVille` materializes the QA task from the exact verification receipts and submits that evidence for review. This prevents synthetic QA from laundering unverified code into `done`.

## Driver authority path

Normal GUI control flow is now:

```text
DevVille GUI
   ↓
VictorDriverCompanyFacade
   ↓
VictorDriver
   ↓
DriverControlledVille
```

The facade preserves the existing `Company`-shaped UI contract but routes project start, work cycles, steering, feedback, focus changes, continue, save/load, and exports through Victor.

Read/helper methods that do not mutate authority state may delegate to the vehicle.

## TRACE-0 / Chronos integration

Driver decisions are recorded into the same TRACE-0/Chronos chain as vehicle evidence. Driver events include:

- authority decisions;
- mission compilation;
- vehicle engagement;
- heartbeat start;
- phase transition;
- verified milestone acceptance;
- pause changes;
- save/load decisions.

Each authority decision includes the capability lease and a decision ID bound to the current Chronos head. TRACE-0 remains observation-only; the driver makes the decision and TRACE-0 records it.

## Persistence

`VictorDriver.save_project()` first persists the vehicle/machine-labor snapshot, then adds a `victor_driver` block containing:

- schema version;
- capability lease;
- mission state;
- current phase and cycle;
- pause state;
- deferred work;
- SHA-256 of the driver-state core.

`load_project()` verifies this state hash before restoring the driver. It deliberately performs the snapshot preflight before appending new Chronos events so it cannot contaminate the saved ledger before continuity is restored.

## Headless execution

```bash
python victor_drive.py "Create a local task-management application"
```

With a dedicated ledger and export directory:

```bash
python victor_drive.py \
  "Create a local task-management application" \
  --chronos chronos/task-manager.jsonl \
  --export-dir exports
```

A zero exit code means the active authoritative build reached `VERIFIED_BUILD`. Exit code 2 means the bounded run stopped before that evidence milestone.

## What this does not claim yet

This driver is a governed execution kernel, not finished AGI. Remaining work includes:

- a sovereign semantic requirements compiler / Choice Kernel rather than the legacy keyword planner;
- signed Identity Kernel authority rather than hash-only actor labels;
- an OS-grade sandbox for untrusted generated code;
- real deployment and marketing capabilities with external receipts;
- a sovereign coding/intelligence backend beneath the driver;
- richer causal world state and durable semantic memory beyond the current project/ledger scope.

Those are explicit boundaries. Victor may drive only capabilities that actually exist and can be verified.
