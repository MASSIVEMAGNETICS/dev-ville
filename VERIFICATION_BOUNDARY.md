# Dev-Ville Evidence-Backed Verification Boundary

## Status

This is the first migration slice from **software-company simulation** to an **evidence-backed machine-labor runtime**.

The legacy emulator may still be used for UI/demo simulation. `VerifiedCompany` is the migration target for authoritative execution.

## Invariant

> A ticket MUST NOT enter `done` because of a probabilistic supervisor decision. It enters `done` only after the exact artifact bundle passes deterministic executable verification and a SHA-256-bound receipt is recorded.

## What changed

### `verification_boundary.py`

Provides a standard-library-only verification engine that:

1. rejects unsafe artifact paths;
2. hashes the exact artifact bundle deterministically;
3. materializes artifacts into a temporary verification directory;
4. compiles every Python source with `py_compile`;
5. requires `test_verified_*.py` behavioral acceptance tests;
6. executes those tests with `unittest` under a timeout;
7. records every check result;
8. emits `artifact_sha256` and `evidence_sha256` receipts.

It also synthesizes deterministic acceptance tests for the artifact contracts Dev-Ville currently emits:

- `FrontendController`
- `BackendService`
- `SystemArchitecture`
- one generic `*Module` class

These tests import and exercise the generated code. They are not `assertTrue(True)` placeholders.

### `verified_company.py`

Subclasses the current `Company` runtime and overrides supervisor review semantics.

The new lifecycle is:

```text
worker completes task
        ↓
primary artifact exists
        ↓
generate deterministic acceptance test
        ↓
SHA-256 artifact bundle
        ↓
compile sources
        ↓
execute behavioral tests
        ↓
verification receipt
       / \
    PASS  FAIL
     ↓      ↓
   done   rework
```

On failure the matching task is reset to `progress=0` and unassigned so the existing scheduler can route it back through work instead of silently completing it.

## Explicit non-goals for this slice

This PR does **not** claim to solve all Dev-Ville simulation problems. In particular, these still need separate migration work:

- rule-based CEO/planning intelligence;
- randomized research recommendations/confidence;
- randomized beta-testing reports;
- static/demo dashboard telemetry;
- local-model inference integration;
- OS-grade sandboxing/network isolation;
- Chronos/Informatron event persistence;
- TRACE-0 instrumentation.

The objective of this slice is narrower and foundational: **make `done` mean something measurable.**

## Security boundary

The verifier uses `subprocess` without `shell=True`, an isolated temporary working directory, a constrained environment, and hard timeouts. This is process isolation, not a complete security sandbox. Generated code should therefore still be treated as untrusted until Dev-Ville gains a stronger execution sandbox (container, VM, seccomp/AppContainer, or equivalent governed capability runtime).

## Run tests

```bash
python -m unittest -v test_verification_boundary.py
```

## Next migration slice

Replace simulation-only QA/research/beta outcomes with evidence-producing organs and route all authoritative state transitions through a shared verification/receipt interface.
