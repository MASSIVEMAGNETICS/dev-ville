# Empire Control Plane

## Purpose

The empire is treated as one dependency graph, not a pile of independent projects.

The control loop is:

```text
OBSERVE
  ↓
NORMALIZE STATE
  ↓
BUILD TOPOLOGY
  ↓
ASSESS GAPS
  ↓
PRIORITIZE BY SEVERITY + DEPENDENCY CENTRALITY
  ↓
PLAN REMEDIATION
  ↓
EXECUTE ALLOWLISTED FIXES ONLY
  ↓
VERIFY THE GRAPH AGAIN
  ↓
WRITE RECEIPT
  ↓
REPEAT
```

`empire_manifest.json` is the first canonical logical topology. It is deliberately about capabilities, not repository names. Repositories can be reorganized without changing the logical architecture.

## What the kernel detects

- missing dependencies;
- dependency cycles;
- multiple canonical authorities for the same capability;
- nodes claiming readiness while a dependency is blocked;
- planned or blocked nodes that are now safe to promote;
- external blockers on the critical path.

## What it may change automatically

Only registered remediation handlers may mutate state. The initial allowlist contains:

- `promote_ready`: promote a planned/blocked node to `ready` when all declared dependencies are operational;
- `demote_blocked`: demote a falsely active/ready node when a dependency is not operational.

Every mutation is followed by a fresh assessment and a receipt containing before/after manifest hashes and gap counts.

## What it must not fake

The control plane does not manufacture solutions to external reality. It cannot mark these complete without an authoritative adapter and verification:

- customer transactions;
- payouts;
- storefront/distributor publishing;
- DNS or hosting state;
- authenticated third-party APIs;
- wallet or bank movement;
- production deployment results.

Those become explicit Victor capabilities. Their adapters execute authorized actions and return evidence. The control plane then updates topology only after verification.

## Current critical path

```text
Victor control plane
  ↓
Chronos + verified Dev-Ville execution
  ↓
MoneyFarm receipt-backed accounting
  ↓
B Heard commerce/platform adapter   ← CURRENT HARD GAP
  ↓
First reliable revenue worker       ← BLOCKED BY ADAPTER
  ↓
verified sale / payout receipt
  ↓
MoneyFarm accounting
  ↓
KEEP / SCALE / CULL
```

The system therefore distinguishes architectural progress from economic proof. A generated artifact is not revenue. A worker report is not a sale. Only externally verified receipts close the loop.

## Run

Assessment without mutation:

```bash
python empire_control_plane.py --check
```

Apply registered safe remediations and emit a receipt:

```bash
python empire_control_plane.py
```

Fail CI only for unresolved structural criticals:

```bash
python empire_control_plane.py --check --fail-on-critical
```

## Extension contract

New automatic behavior should be added as a named remediation handler or a governed capability adapter. Never add generic arbitrary-shell execution to the control plane. The correct pattern is:

```text
gap
  ↓
explicit action contract
  ↓
authority / lease
  ↓
capability adapter
  ↓
external evidence
  ↓
verification
  ↓
receipt
  ↓
state transition
```

This keeps self-correction powerful without letting the system confuse assertions with reality.
