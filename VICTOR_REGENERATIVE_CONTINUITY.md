# Victor Regenerative Continuity (VRC-0)

**Status:** PROPOSED / EVIDENCE-GATED

VRC-0 is not a new Victor core, not a cognitive organ, and not a second ledger. It is a cross-cutting continuity contract applied to the existing Victor topology.

The biological synthesis is precise:

- **Tardigrade principle:** when continuity cannot be trusted, reduce behavior before damage compounds. In Victor this becomes cryptobiosis: freeze consequential external effects, commit a verified canonical head, persist a minimal recovery capsule, and remain inert until continuity is independently re-established.
- **Deinococcus principle:** do not require one intact runtime. Preserve enough authenticated fragments that a fresh runtime can reconstruct the canonical organism after loss or corruption.
- **Experience-Based Intelligence principle:** the thing worth preserving is not only code or model weights. Preserve the provenance-bearing experience state that changed the organism: episodic state, semantic state, prediction state, salience/homeostasis, learned bindings, unresolved questions, current mission, and the canonical causal history that explains how those states were reached.

## Why this is a legal canonical change

The canonical execution map freezes architecture unless evidence exposes a failing invariant. Current Victor already proves several continuity properties:

1. Chronos is append-only authoritative causal history.
2. The World Model is derived and rebuildable from Chronos.
3. Driver/topology snapshots are hash-bound.
4. Identity continuity is locally authenticated by a persistent key ID.
5. Restart/load paths verify hashes and reject tampering.

That is strong restart continuity, but it does not yet prove **regenerative continuity** under destructive failure.

### Newly defined failing invariant

> A Victor runtime that loses the active process, replaceable model state, derived memory, and one continuity fragment must still be able to reconstruct identity, authoritative causal history, provenance-bearing experience state, current mission, and legal authority state on a fresh runtime; otherwise it must fail closed.

Current complete-snapshot restore does not establish that property. VRC-0 exists to falsify or satisfy it.

## The architectural decision

Do **not** attach a `ResilienceOrgan` beside Memory, Choice, or Ethica.

Resilience is a law of the organism:

```text
                    VICTOR REGENERATIVE CONTINUITY
                 (cross-cutting constitutional contract)
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
   Identity Genome          Chronos Canon             Experience State
        |                         |                         |
        +-------------------------+-------------------------+
                                  |
                           Recovery Capsule
                                  |
                         2 data + 1 parity shards
                                  |
               +------------------+------------------+
               |                                     |
               v                                     v
         Normal ACTIVE                         CRYPTOBIOSIS
                                                     |
                                              reconstruct fresh
                                                     |
                                              independent verify
                                                     |
                                          RECOVERED -> ACTIVE
```

The VRC contract applies beneath:

- Victor Kernel identity and legal state transitions;
- Chronos persistence and replay;
- Experience-Based Intelligence serialization;
- Choice/Capability authority;
- World Model reconstruction;
- restart/recovery paths.

## Current Victor -> VRC mapping

| Existing primitive | Current function | VRC interpretation |
| --- | --- | --- |
| TRACE-0 | observation-only event emission | records continuity/recovery evidence; never self-authorizes |
| Informatron | immutable typed transition | atomic causal unit carried through recovery |
| Chronos | append-only authoritative causal history | genomic history: must survive or reconstruct exactly |
| World Model / Continuity Graph | rebuildable materialized state | phenotype: disposable and regenerated from canonical history |
| Identity Kernel | persistent key-backed authority proof | identity lineage anchor; secret key is not stored in recovery capsule |
| Choice Kernel / Capability Lease | decides and scopes effects | external effects are illegal outside verified `ACTIVE` state |
| Independent Verifier | fresh reconstruction and acceptance | required before a recovered runtime can reactivate |
| Experience-Based Intelligence | learns from lived state transitions | continuity payload preserves the experience that changed future behavior |
| Model weights / replaceable organs | implementation substrate | expendable phenotype, not identity |

## VRC state machine

```text
ACTIVE
  |
  | continuity threat / destructive maintenance / migration
  v
QUIESCING
  |
  | verify Chronos + freeze continuity payload + build shards
  v
CRYPTOBIOSIS
  |
  | fresh runtime receives surviving fragments
  v
RECONSTRUCTING
  |
  | capsule bytes recovered
  v
VERIFYING
  |\
  | \ mismatch / ambiguity / insufficient quorum
  |  v
  | HALTED
  v
RECOVERED
  |
  | explicit reactivation after verification
  v
ACTIVE
```

`DEGRADED` is a non-active containment state for a known continuity problem that has not yet become a verified recovery.

**External effects are permitted only in `ACTIVE`.** `RECOVERED` is still inert until explicit reactivation.

## Identity genome

The VRC genome is intentionally tiny. It stores recognition anchors, not the whole organism:

```text
schema_version
subject
identity_algorithm
identity_key_id
constitution_sha256
invariants[]
```

It contains no secret/private key bytes.

The default invariants in VRC-0 are:

1. Victor identity is not model weights.
2. Chronos is authoritative causal history.
3. Derived state must be rebuildable.
4. External effects require active verified continuity.
5. Unknown or ambiguous recovery fails closed.
6. Experience state requires provenance.

## Recovery capsule

A capsule contains:

```text
Victor genome
Chronos events
Chronos receipts
Chronos head chain hash
opaque continuity payload
continuity payload SHA-256
creation timestamp
```

The continuity payload is deliberately opaque to VRC so this layer does not become cognition.

The Experience-Based Intelligence runtime should serialize at least:

```text
experience.episodic_state
experience.semantic_state
experience.predictive_state
experience.salience_state
experience.homeostatic_state
experience.dictionary_bindings
experience.sleep/consolidation state when material
current_mission
current_phase
unresolved_questions
active assumptions / contradictions
relevant provenance roots
```

VRC authenticates and reconstructs those bytes. The Experience-Based Intelligence layer remains responsible for their semantics.

## Fragment reconstruction

VRC-0 uses a dependency-free `2 data + 1 XOR parity` recovery set.

```text
D0 = first half of canonical capsule bytes
D1 = second half
P  = D0 XOR D1
```

Any two valid shards can reconstruct the capsule:

```text
D0 + D1 -> original
D0 + P  -> D1 = D0 XOR P
D1 + P  -> D0 = D1 XOR P
```

Each shard has an independent SHA-256 digest. The complete recovered capsule must also match the recovery-set SHA-256 identity.

This proves one-fragment loss/corruption semantics without dependencies. It is **not** a claim that XOR parity is the final storage system. Production VRC should move to a stronger erasure code and geographically/physically independent failure domains while preserving the same verification contract.

Three shard files on one disk are not three failure domains.

## How Experience-Based Intelligence changes when fused with VRC

Without VRC, persistence means roughly:

```text
experience -> update state -> save state -> restart -> continue
```

With VRC:

```text
experience
  -> evidence/provenance
  -> canonical transition
  -> Chronos
  -> derived episodic/semantic/predictive state
  -> continuity capsule
  -> distributed authenticated fragments

catastrophic loss
  -> reconstruct capsule
  -> verify identity genome
  -> rebuild Chronos exactly
  -> recover experience payload
  -> rebuild derived world/semantic state
  -> verify current mission and authority
  -> explicit reactivation
  -> continue learning
```

The conceptual upgrade is important:

> Experience no longer merely survives a restart. Experience becomes regenerable from authenticated history and fragments.

This makes the Experience-Based Intelligence architecture substantially closer to an organism whose learned identity is carried by continuity and causal history rather than by one process image or one set of weights.

## What VRC-0 code implements now

`victor_regenerative_continuity.py` implements:

- a minimal hash-addressed Victor genome;
- cryptobiosis lifecycle states;
- hard blocking of external effects outside `ACTIVE`;
- verified recovery capsule creation from a valid Chronos chain;
- opaque Experience-Based Intelligence continuity payload preservation;
- 2+1 authenticated fragment encoding;
- recovery after one missing shard;
- recovery after one detectably corrupted shard;
- independent capsule/identity/payload/Chronos verification;
- atomic shard file writes;
- fail-closed recovery state transitions.

`test_victor_regenerative_continuity.py` specifies destructive acceptance tests.

## Destructive acceptance tests

VRC-0 is not canonical merely because the code exists. Promotion requires evidence.

| Test | Required result |
| --- | --- |
| Kill active runtime; start fresh process | reconstruct without original runtime memory |
| Delete derived World Model | rebuild from recovered Chronos |
| Remove model weights | identity and continuity still verify |
| Remove one data shard | reconstruct using remaining data + parity |
| Corrupt one shard without matching digest | ignore it and reconstruct from other two |
| Lose/corrupt two shards | fail closed; no external effects |
| Replace identity key ID | fail closed |
| Mutate continuity payload | fail closed |
| Mutate Chronos event/receipt | fail closed |
| Recover valid state | remain inert in `RECOVERED` until explicit reactivation |
| Rebuild Experience-Based state | same canonical continuity digest and mission anchor |

## Promotion path

VRC should not rewrite the existing canonical execution ledger in the proposal PR.

Correct sequence:

```text
1. Merge VRC implementation only after tests pass.
2. Run destructive continuity tests from the merged exact head.
3. Independently verify reconstruction evidence.
4. Update CANONICAL_EXECUTION_MAP.md with VRC responsibility and evidence anchor.
5. Append a new Informatron to chronos/canonical_execution.jsonl.
6. Preserve sequences 1..N byte-for-byte; append N+1 only.
7. Gate the ledger prefix and full Chronos chain in CI.
```

That preserves the repository's append-only evidence law: the ledger records a verified merged fact, not an aspiration.

## Next integration after VRC-0 proves itself

The strongest next step is **not more architecture**. It is one destructive experiment that joins the two research lines:

1. serialize the current Experience-Based Intelligence state into `continuity_payload`;
2. build a VRC recovery set;
3. terminate the runtime;
4. delete the derived semantic/world state;
5. remove one recovery shard;
6. reconstruct on a clean process;
7. rebuild state from Chronos + recovered experience payload;
8. present the same cross-episode question used before failure;
9. compare identity, mission, graph state, semantic bindings, prediction behavior, and answer provenance before vs. after destruction.

### Success criterion

Victor passes only if the recovered organism demonstrates **continuity of learned causal state**, not merely identical files.

The measurable target is:

```text
identity anchor: exact match
Chronos chain head: exact match
continuity payload digest: exact match
current mission anchor: exact match
rebuildable graph state: exact canonical hash
provenance links: preserved
external effects during recovery: zero
post-recovery answer provenance: valid
post-recovery learned behavior: within defined tolerance of pre-failure behavior
```

That is the first experiment that can justify the phrase **regenerative experience-based intelligence** with evidence instead of metaphor.
