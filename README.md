# Dev-Ville / Victor: Verifiable Agent Runtime

Dev-Ville began as a local software-company emulator. The current Victor layer turns it into a more interesting systems project: a **model-independent agent runtime with deterministic evidence, causal state continuity, capability-aware routing, verification receipts, outcome tracking, and bounded learning**.

The useful claim is not "AGI." The useful claim is that important agent state can be made **reconstructable and falsifiable instead of living only inside a model's context window**.

## Start with the proof

Read [`FRONTIER_PROOF.md`](FRONTIER_PROOF.md), then run the authoritative contracts:

```bash
git clone https://github.com/MASSIVEMAGNETICS/dev-ville.git
cd dev-ville
python -m unittest -v \
  test_verification_boundary.py \
  test_machine_labor_organs.py \
  test_victor_driver.py \
  test_victor_topology_kernel.py \
  test_victor_identity_kernel.py \
  test_victor_learning.py
```

GitHub Actions executes the same contract suite on Python 3.11 and 3.12 for pull requests into `main`; the hardened workflow also runs on pushes to `main`.

## Core architecture

```text
observation
    -> TRACE-0 / Informatron
    -> Chronos causal receipt
    -> identity + authority boundary
    -> capability registry
    -> mission compiler
    -> choice kernel
    -> execution vehicle
    -> deterministic verification
    -> outcome resolution
    -> bounded route learning
    -> reconstructable world state
```

### TRACE-0 + Chronos

`trace0_chronos.py` provides:

- canonical JSON encoding;
- deterministic Informatron event IDs;
- strict event sequencing;
- parent-event linkage;
- append-only hash-chain receipts;
- JSONL persistence;
- snapshot restore;
- full-chain verification.

Chronos receipts are tamper evidence. SHA-256 does not prove semantic truth or actor identity.

### Local identity continuity

`victor_identity_kernel.py` provides a replaceable identity-proof contract. The current backend is HMAC-SHA256 using a local secret.

The tests verify that altered authority envelopes fail, modified signed Victor events fail, and saved identity continuity cannot be restored with the wrong key.

### Capability-aware mission routing

`victor_topology_kernel.py` composes:

- `VictorWorldModel`;
- `CapabilityRegistry`;
- `MissionCompiler`;
- `ChoiceKernel`;
- `OutcomeResolver`;
- bounded route learning.

Unsupported requirements can halt with `no_feasible_route` instead of being silently rewritten into something the runtime happens to support.

### Evidence-backed artifact verification

`verification_boundary.py` validates artifact paths, hashes the exact bundle, compiles Python sources, executes authoritative behavioral tests in an isolated temporary directory, and emits a hash-bound verification receipt.

Acceptance is therefore tied to inspectable evidence rather than a model self-rating or random confidence score.

## Adversarial contracts already in the test suite

The repository does not only test happy paths. Existing regression contracts check that:

- changing a signed authority envelope makes authentication fail;
- changing a signed Victor authority event makes verification fail;
- loading persisted identity under the wrong key fails;
- mutating a hash-bound saved topology makes restoration fail;
- unsupported mobile work halts before a vehicle project exists;
- deterministic world-model reconstruction yields the same state hash;
- route outcomes feed evidence into the bounded learning layer.

See [`FRONTIER_PROOF.md`](FRONTIER_PROOF.md) for the proof matrix and reviewer path.

## Run the system

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the GUI:

```bash
python devville.py
```

Run the CLI:

```bash
python devville_cli.py
```

## Dev-Ville application layer

The original Dev-Ville runtime remains useful as the execution vehicle and interactive laboratory. It includes:

- specialized software-development agents;
- ticket lifecycle management;
- supervisor review and escalation;
- research findings;
- generated frontend/backend/architecture artifacts;
- companion test generation;
- interactive user steering;
- event-driven collaboration;
- project persistence and continuation;
- demo/event recording;
- GUI and CLI interfaces.

The Victor architecture sits above this vehicle so the execution layer can be changed without making the execution layer itself the identity or continuity root.

## Important boundaries

This repository does **not** claim that its tests prove consciousness, AGI, superintelligence, universal safety, or superior general reasoning.

The current HMAC identity backend is symmetric, not public-key lineage. Hash chains provide tamper evidence, not truth. The verification boundary proves configured software-artifact contracts, not arbitrary program correctness. Topology tests prove routing and state invariants, not general intelligence.

Those limits are deliberate: **the claim should stop where the evidence stops.**

## Documentation

- [`FRONTIER_PROOF.md`](FRONTIER_PROOF.md) — fastest technical review path
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — system architecture
- [`VICTOR_TOPOLOGY.md`](VICTOR_TOPOLOGY.md) — topology layer
- [`VICTOR_DRIVER.md`](VICTOR_DRIVER.md) — driver model
- [`VERIFICATION_BOUNDARY.md`](VERIFICATION_BOUNDARY.md) — verification design
- [`MACHINE_LABOR_ORGAN.md`](MACHINE_LABOR_ORGAN.md) — machine labor layer
- [`MONEYFARM_FUSION.md`](MONEYFARM_FUSION.md) — economic-organ integration

## License

MIT License
