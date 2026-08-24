# Remediation Control Plane (RCP) v1

RCP is the local-first closed-loop remediation product for the Massive Magnetics repository estate.

It is deliberately **not** another Victor core. It composes the existing canonical primitives in `dev-ville`:

```text
Truth Compiler / estate scan
        ↓
RepositoryEvidence + Finding
        ↓
RemediationCase (SQLite ranked queue)
        ↓
PolicyGate (HMAC capability lease, default DENY)
        ↓
RepairWorker (leased paths only)
        ↓
IndependentVerifier (fresh reconstruction; ignores worker success claims)
        ↓
TRACE-0 / Chronos canonical receipt
        ↓
PR_READY
        ↓
GitHub Git-Data API → one commit → DRAFT PR
```

The product contains **no merge, deploy, repository-delete, secret-management, permission-management, or funds API**. The terminal autonomous external effect is a draft pull request.

## What is real in v1

- deterministic repository, finding, case, plan, verification, lease and receipt identities;
- GitHub organization inventory with pagination;
- local multi-repository inventory;
- root-source evidence inspection;
- canonical repository classification (`CORE`, `EXPERIMENT`, `FORK`, `ARCHIVE`, `UNKNOWN`);
- priority scoring using the audit formula;
- SQLite WAL-backed queue and state machine;
- HMAC-SHA256 capability leases with local 0600 key generation;
- risk ceiling: autonomous execution defaults to `R1` or lower;
- bounded repair recipe registry;
- isolated worker materialization that never edits the source checkout;
- independent verification that reconstructs the patch separately and compares worker bytes;
- canonical `trace0_chronos.py` integration; RCP refuses to invent a second ledger;
- interruption recovery for in-flight cases;
- Truth Compiler JSONL interchange contract;
- one-commit GitHub publication using the Git Data API;
- draft PR creation only;
- base-SHA drift detection before publication;
- deterministic branch names and recovery checks;
- standard-library runtime only.

## Current autonomous repair library

`safe_gitignore_v1` is intentionally narrow. It is issued only for a repository that has no root `.gitignore`, and the lease permits exactly one write path: `.gitignore`.

The verifier rejects path expansion, duplicate paths, oversized/NUL payloads, broad ignore rules such as `*`, and any worker output that differs from the verified plan.

Other findings remain evidence-backed queue items until a bounded recipe exists. RCP does **not** turn model confidence into authority.

## Quick start — Windows PowerShell

From a `dev-ville` checkout:

```powershell
python rcp_cli.py init rcp.json
python rcp_cli.py --config rcp.json scan-local C:\path\to\your\repos
python rcp_cli.py --config rcp.json queue --limit 50
python rcp_cli.py --config rcp.json run --limit 10
python rcp_cli.py --config rcp.json status
python rcp_cli.py --config rcp.json verify-ledger
```

For the GitHub estate:

```powershell
$env:GITHUB_TOKEN="<token>"
python rcp_cli.py --config rcp.json scan-github --org MASSIVEMAGNETICS
python rcp_cli.py --config rcp.json run --limit 10 --publish
```

The token is read from `GITHUB_TOKEN` or `GH_TOKEN`; it is never written to the SQLite database, config, worker artifact, or Chronos event.

For draft-PR publication, grant the narrowest repository permissions that permit metadata read, contents write, and pull-request write. RCP does not call merge endpoints.

## Truth Compiler interchange

`ingest-truth` accepts one JSON object per line. Required fields:

```json
{
  "repository_full_name": "MASSIVEMAGNETICS/example",
  "head_sha": "0123456789abcdef",
  "rule_id": "proof.runtime_unknown",
  "title": "Runtime state is not independently proven",
  "evidence": {"source": "truth-compiler"},
  "truth_state": "UNKNOWN",
  "risk": "R0"
}
```

Optional fields include `default_branch`, `classification`, `severity`, `blast_radius`, `revenue_block`, `proof_gap`, `dependency_unlock`, `irreversibility`, `remediable`, `recipe`, `required_paths`, `root_files`, `archived`, `fork`, and `size_kb`.

Allowed truth states are exactly `PASS`, `FAIL`, `UNKNOWN`, and `PARTIAL`. Anything else is rejected. `UNKNOWN` is preserved as unknown.

```powershell
python rcp_cli.py --config rcp.json ingest-truth .\truth-findings.jsonl
```

## Queue state machine

```text
DISCOVERED
  ↓
TRIAGED
  ├──→ AWAITING_APPROVAL
  └──→ AUTHORIZED
          ↓
       CLAIMED
          ↓
       PATCHING
          ↓
       VERIFYING
        ↙     ↘
     FAILED   PROVEN
                ↓
             RECEIPTED
                ↓
              PR_READY
                ↓
              DRAFT_PR
```

`BLOCKED` and `FAILED` are terminal. `PR_READY` is intentionally recoverable: the verified patch can be published later when authenticated GitHub access is available.

## Priority score

RCP preserves the audit scoring model:

```text
priority =
    5 × severity
  + 4 × blast_radius
  + 3 × revenue_block
  + 3 × proof_gap
  + 2 × dependency_unlock
  - 2 × irreversibility
```

Each input is clamped to 0–10.

## Recovery behavior

RCP persists queue state, leases, plans and verification artifacts in `.rcp/remediation.sqlite3`. Chronos persists canonical receipts in `.rcp/chronos.jsonl`.

After interruption:

```powershell
python rcp_cli.py --config rcp.json recover
```

For an authorized in-flight case, RCP revalidates the signed lease, rebuilds the deterministic plan, rematerializes the worker output, independently re-verifies it, and resumes from the stored state. Chronos event keys are deduplicated by semantic event identity so recovery does not intentionally manufacture duplicate proof events.

## Hard boundaries

The following are absent from the runtime and therefore cannot be granted by prompt:

- merge pull request;
- deploy to production;
- delete or transfer repository;
- delete branch;
- edit organization permissions;
- read/write secrets;
- move money or call payment APIs;
- rewrite Git history;
- mark an UNKNOWN finding as PASS;
- expand a lease beyond explicit paths and operations.

The GitHub publisher checks the repository default branch head immediately before publication. If it differs from the case base SHA, publication fails closed and the case remains `PR_READY`.

## Tests

```powershell
python -m unittest -v test_rcp.py
python -m compileall -q rcp rcp_cli.py test_rcp.py
```

The suite covers deterministic case identity, lease signing/tamper rejection, worker/verifier separation, source-checkout isolation, draft-PR-only publication, and Truth Compiler UNKNOWN preservation.

## Next recipe expansion

Do not add arbitrary shell-command or unrestricted model-generated patches. Every new recipe should define:

1. exact finding rule(s);
2. maximum risk tier;
3. exact path allowlist;
4. supported operations;
5. deterministic plan construction;
6. independent acceptance checks;
7. rollback semantics;
8. a test proving path escape and capability escalation fail closed.

That keeps the worker useful without turning it into an unbounded code-execution daemon.
