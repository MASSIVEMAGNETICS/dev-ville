# Dev-Ville as a Victor organ

Dev-Ville can run as a bounded software-build organ under the canonical control plane in `MASSIVEMAGNETICS/victor_empire`.

## Contract

- Job schema: `victor.organ.job.v1`
- Receipt schema: `victor.organ.receipt.v1`
- Organ identity: `dev-ville`
- Capability: `devville.project.build`

The adapter does not accept arbitrary shell commands or Python snippets. It accepts a software directive inside a versioned job envelope containing a work-order ID, lease ID, lease expiry, and execution limits.

## Probe

```bash
python victor_adapter.py probe
```

## Standalone bounded execution

Victor normally creates this job file. For contract testing, the adapter can be invoked directly:

```bash
python victor_adapter.py run --job path/to/job.json --output-root path/to/output
```

The adapter creates a run directory under:

```text
<output-root>/<work-order-id>/<job-id>/
```

and writes:

- `artifacts/...` — generated Dev-Ville files
- `ORGAN_RECEIPT.json` — execution receipt with SHA-256 digests

## Runtime restrictions

The adapter enforces:

- exact capability allowlist
- non-expired lease
- bounded work cycles and time delta
- bounded file count and total output bytes
- safe identifiers and artifact paths
- output writes scoped to the supplied output root
- Python audit-hook denial of network connection attempts and child-process execution

The audit hook is defense in depth, **not an operating-system sandbox**. A hostile or untrusted codebase should additionally run under a restricted OS account, container, VM, or other real sandbox.

## Victor-side verification

Victor does not trust the receipt merely because Dev-Ville produced it. The control plane independently verifies:

1. receipt schema and organ identity
2. work-order, lease, job, and capability binding
3. completed project status and task completion
4. canonical receipt hash
5. every artifact path
6. every artifact byte length
7. every artifact SHA-256 digest
8. aggregate execution limits

Only after those checks pass may Victor commit the outcome into canonical state.
