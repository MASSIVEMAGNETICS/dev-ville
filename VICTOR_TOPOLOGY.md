# Victor Topology Kernel

## Canonical topology

```text
OWNER / BANDO
     |
     v
VICTOR SOVEREIGN DRIVER
     |
     +-- Identity Kernel -------- signed authority envelope
     +-- World Model ------------ rebuildable typed graph
     +-- Mission Compiler ------- directive -> typed candidate DAGs
     +-- Choice Kernel ---------- constraints/capabilities -> selected route
     +-- Capability Registry ---- what the vehicle can actually cause
     +-- Outcome Resolver ------- prediction -> resolved outcome
     +-- Learning Updater ------- bounded empirical route policy
     |
     v
DEV-VILLE VEHICLE
     |
     +-- evidence research
     +-- artifact builders
     +-- deterministic verification
     +-- executable loopback beta/E2E
     |
     v
TRACE-0 -> INFORMATRON -> CHRONOS
     |                       |
     +------ materialize ----+
                 |
                 v
           WORLD MODEL
```

The governing invariant is:

> Victor owns route selection, authority, continuity, and acceptance. Dev-Ville executes a bounded route. Chronos owns causal history. The World Model is derived state and must be rebuildable from Chronos.

## What changed

The authoritative project-start path no longer asks Dev-Ville's legacy CEO and President agents to create the route.

The new path is:

```text
owner directive
  -> MissionCompiler.parse()
  -> candidate typed DAGs
  -> CapabilityRegistry assessment
  -> ChoiceKernel evaluation
  -> selected authorized DAG
  -> DriverControlledVille.start_project_from_plan()
```

`DriverControlledVille.start_project()` remains only for legacy compatibility. `VictorSovereignDriver` and `TopologicalVictorDriver` use `start_project_from_plan()`.

## World Model

`VictorWorldModel` is a typed multigraph. It indexes every Informatron and applies explicit graph mutations carried inside an Informatron payload.

Current node types include:

- actor
- event
- mission
- route
- plan
- task
- capability
- prediction
- outcome
- route_policy

Current semantic edge types include:

- PRODUCED
- OBSERVES
- SELECTS_ROUTE
- CHOOSES
- CONTAINS
- DEPENDS_ON
- ENABLES
- PREDICTS
- RESULTS_IN
- UPDATES_POLICY

Chronos is still authoritative. The World Model is a materialized view and can be rebuilt from the append-only event history.

## Mission Compiler

The current Mission Compiler is deterministic and explicit. It is **not** claimed to be general semantic intelligence.

It currently recognizes bounded software mission classes such as:

- API service
- website
- web application
- general backend-oriented software

A mobile-app request is currently rejected because Dev-Ville does not possess a verified mobile builder capability. Victor fails closed instead of silently rewriting that request into something else.

Requested deployment, marketing, and external-network effects are represented as deferred work when they exceed the active local-software-build lease.

## Choice Kernel

The Choice Kernel evaluates candidate routes against:

1. goal coverage;
2. capability coverage;
3. dependency validity / DAG acyclicity;
4. bounded total effort;
5. sufficiently sampled historical route outcomes only as a tie-breaker.

`utility_score` is a deterministic ranking value. It is **not a probability**.

Historical learning cannot overpower a route that is currently infeasible or lower utility. It only breaks otherwise equal present-time choices after the learning minimum has been reached.

## Capability Registry

Capabilities describe executable mechanisms rather than fictional employees.

Current authoritative capability classes cover:

- local evidence research;
- architecture artifact generation;
- frontend artifact generation;
- backend artifact generation;
- deterministic Python verification;
- loopback HTTP beta/E2E.

Production deployment and unconstrained network execution remain outside the default lease.

## Identity Kernel

`VictorSovereignDriver` signs each Victor authority envelope with a persistent local HMAC-SHA256 key.

The signed core includes:

- actor;
- action;
- target entity;
- payload;
- authority label;
- previous Chronos chain hash.

The event provenance records the key ID, signature, signed-core hash, and parent chain hash so the envelope can be reconstructed and verified later.

The default key is stored at:

```text
identity/victor.key
```

and is ignored by Git.

This is a real symmetric authentication mechanism, but it is **not yet asymmetric/public-key bloodline identity**. The proof contract is deliberately backend-neutral so a future Ed25519/hardware-key Identity Kernel can replace HMAC without changing the authority topology.

## Outcome and learning loop

When Victor selects a route, it records a prediction:

```text
selected route -> predicts VERIFIED_BUILD under current lease
```

The prediction's structural evidence score comes from present goal/capability coverage. It is not presented as calibrated probability.

When the route resolves:

```text
prediction
  -> outcome
  -> ConfidenceCalibrator resolution history
  -> bounded route learning record
  -> UPDATES_POLICY graph edge
```

A route policy does not expose a learned preference until at least five resolved outcomes exist. Once available, that empirical rate is only a Choice Kernel tie-breaker.

## Continuity

Three distinct continuity artifacts now exist:

1. **Chronos JSONL** — causal append-only event chain;
2. **Victor driver/topology snapshot** — hash-bound materialized mission/outcome state;
3. **Identity key** — local authority-authentication continuity.

On load:

- Chronos history is verified;
- driver state hash is verified;
- topology state hash is verified;
- identity algorithm/key ID must match;
- the World Model is rebuilt from Chronos rather than trusted from a stale graph snapshot.

## Default runtime

GUI:

```bash
python devville_verified.py
```

Headless:

```bash
python victor_drive.py "Create a backend API"
```

The default headless paths are:

```text
Chronos:  chronos/victor-devville.jsonl
Identity: identity/victor.key
```

## Explicit remaining limits

This slice does not claim completion of Victor intelligence.

Still missing or intentionally bounded:

- the Mission Compiler is deterministic/rule-based rather than a native semantic Perceptron/Intellitron substrate;
- generated software is still produced by Dev-Ville's current template builders;
- capability execution is not an OS-grade untrusted-code sandbox;
- external evidence research is not yet connected through governed source capabilities;
- identity is symmetric HMAC, not asymmetric signature/lineage infrastructure;
- production deployment and marketing execution remain outside the default capability lease;
- the current World Model materializes typed state but is not yet the full Continuity Graph/Rograph ontology.

Those are now replaceable organs around a stable topology rather than reasons to redesign the runtime again.
