# Empire Synchronization Spine v1

**Status:** proposed control-plane integration; no new execution authority.

## Objective

Eliminate silent divergence between canonical state, derived repository state, deployment artifacts, public proof, and monitoring.

The rule is deliberately not “everything writes to everything.” Circular writers create races and ambiguous authority. Every domain has exactly one writer of canonical state; all other copies are projections that must reconcile or fail closed.

## Closed loop

```text
Canonical authority
    -> deterministic derivation
    -> repository validation
    -> build/deploy
    -> live verification
    -> cross-repo observer
    -> semantic status projection
    -> drift => repair derived state OR block promotion
    -> verified transition
```

## Authority graph

- **Chronos canonical execution ledger** owns authoritative Victor execution history.
- **CANONICAL_EXECUTION_MAP.md** is a current-state projection of that history and immutable evidence anchors.
- **Store sync contract** owns SKU -> canonical artwork selection.
- **Commerce registry** owns checkout status, formats, prices and Stripe payment-link metadata.
- **Asset registry and storefront HTML** are derived and may never contradict their authority sources.
- **Public Proof Ledger** is a bounded projection of independently checkable canonical evidence.
- **Frontier Radar status** is an observation surface, never execution authority.

## Repair boundary

Automatic repair is allowed only for deterministic derived state. For example, the storefront reconciler may recompute asset hashes and synchronize derived `checkout_state` fields from canonical registries.

Automatic repair may **not**:
- rewrite Chronos history;
- change canonical authority;
- merge PRs;
- deploy secrets;
- move funds;
- grant capabilities;
- upgrade evidence claims.

Those transitions remain governed by the existing Truth Compiler / authority / verifier / CTP / Chronos path.

## Failure semantics

A disagreement is not logged as a warning and ignored. Strict synchronization checks return non-zero and block the corresponding promotion path.

Unknown remote state is a failure in strict mode. Local PR validation can run local-only to prove the synchronization machinery itself before remote dependencies are merged.

## Extension contract

New systems join by adding a domain to `empire_sync/manifest.json` with:
1. one canonical authority;
2. one or more derived consumers;
3. machine-checkable invariants;
4. a deterministic repair policy if repair is safe;
5. a fail-closed verification path when repair is not safe.

This turns the meta-ledger into a graph of authorities, projections, receipts and state-transition checks instead of a pile of manually synchronized notes.
