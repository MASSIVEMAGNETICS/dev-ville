# Dev-Ville Role Runtime v0.2

This repository integration turns role handoffs into persistent, inspectable
tickets. It runs actual local commands and packages tested input bytes. It does
not implement ten autonomous agents, authenticated reviewers, production
deployment, or a replacement authority system for Victor.

Python 3.11+; standard library only. Tested here on Linux / Python 3.12.
The GUI dependencies in requirements.txt are unnecessary for this CLI.

```bash
python devville_roles.py roles
python -m unittest -v test_devville_roles.py
```

## Role contracts

Each accepted handoff binds the latest preceding evidence IDs. Replacing an
earlier handoff invalidates downstream handoffs until they are performed again.
Documents are structurally accepted evidence, not proof that their contents
are correct. All reviewer names are local labels, not authenticated principals.

| Worker | Inputs | Permitted runtime action | Output / acceptance | Failure condition |
| --- | --- | --- | --- | --- |
| Product Manager | Owner problem | Attach problem evidence | Nonempty file inside workspace, reviewer label differs | Missing/altered file or invalid chain |
| Product Owner | Problem evidence | Attach acceptance evidence | acceptance document bound to problem revision | Missing/revised problem |
| Software Architect | Prior handoffs | Attach design evidence | architecture document with current dependencies | Invalid preceding evidence |
| Engineering Lead | Prior handoffs, actual source | Attach implementation record | implementation evidence; source later bound by QA | Invalid preceding evidence |
| Technical Program Manager | Prior handoffs | Attach delivery evidence | delivery record bound to current implementation | Stale implementation |
| QA Engineer | Prior handoffs, explicit files, trusted argv | Run test; attach its receipt | Runtime-recorded exit 0, unchanged file hashes, current predecessor IDs | Forged/edited report, failure, timeout, >4 MiB output, source change |
| Release Manager | Passing attached QA, explicit tested files | Create ZIP; attach readiness receipt | ZIP hash and input hashes match runtime receipt | Untested source, stale QA, changed archive |
| DevOps Engineer | Release candidate, external authority | No deployment adapter yet | Gate always blocked | Self-declared deployment is rejected |
| Product Marketing Manager | Verified deployment, launch evidence | Attach launch evidence after deployment gate | Launch record | Deployment gate unavailable |
| Product Operations Manager | Prior handoffs, live observations | Attach operations evidence after launch gate | Operations record | Missing operational evidence or deployment gate |

The director is currently the CLI operator. Semantic work for the five document
roles remains human/assistant supplied; the machine does not invent requirements
or code. Verifier responsibilities are document review for those roles, runtime
execution provenance for QA, and archive inspection for release readiness.
Runtime checks do not authenticate the people supplying reviewer labels.

## Working ticket

Create a dedicated workspace and put reviewed problem.md, acceptance.md,
architecture.md, implementation.md, delivery.md, actual source, and tests there.
Evidence --file paths may be absolute; relative paths are resolved from the
calling directory. Output paths resolve under --workspace. Use absolute input
paths to avoid ambiguity.

```bash
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work new --name 'Product defect' --problem 'Observed failure and reproduction'
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work attach --ticket 1 --role product-manager --kind problem --file /absolute/work/problem.md --actor author --verifier reviewer
```

Attach the other four documents in the order above with kinds acceptance,
architecture, implementation, delivery and their corresponding roles. Then:

```bash
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work test --ticket 1 --file /absolute/work/app.py --file /absolute/work/test_app.py --output qa.json --timeout 60 -- python -m unittest -v test_app
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work attach --ticket 1 --role qa-engineer --kind test --file /absolute/work/qa.json --actor qa-worker --verifier qa-reviewer
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work package --ticket 1 --file /absolute/work/app.py --file /absolute/work/test_app.py --archive candidate.zip --output readiness.json
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work attach --ticket 1 --role release-manager --kind readiness --file /absolute/work/readiness.json --actor release-worker --verifier release-reviewer
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work audit --ticket 1
python devville_roles.py --db /absolute/work/state.sqlite3 --workspace /absolute/work chronos --ticket 1 --output chronos.json
```

Successful readiness produces RELEASE_CANDIDATE and stops at DevOps. Strict
audit exits 2 and close is rejected because production gates remain incomplete.
Exploratory test runs without --ticket are allowed but cannot satisfy a ticket.

## Persistence and recovery

SQLite WAL persists tickets, execution reports, dependencies, and hash-linked
events. Attach, package, and close use immediate transactions. The event chain
must validate before mutation. Latest evidence per role determines current state;
old records remain history. New outputs cannot overwrite existing files. Reruns
must use new output names. Interrupted filesystem/DB operations can leave an
unaccepted orphan report or ZIP; inspect it and use a new name when retrying.
Never edit accepted artifacts in place: a source revision requires rerunning QA
and rebuilding the candidate. Copy/back up the complete workspace and SQLite
using SQLite's backup API (or after all connections close).

v0.1 databases gain the new tables automatically. Old test and deployment
declarations do not become trusted executions. Reattach downstream documents in
order and rerun QA; no silent trust migration is performed.

Chronos export uses existing trace0_chronos.py to create an observation-only
snapshot derived from the SQLite event stream. It does not append into Victor's
live canonical ledger, issue a lease, or authorize a release. Its new timestamps
are export times; original event hashes/timestamps remain provenance.

## Trust boundary and limits

Run only trusted local test commands. Working directory confinement is not an
OS sandbox: a command can read/write elsewhere and use network access. POSIX
process groups are killed on timeout/completion; on Windows only the direct
child is killed, so use an external sandbox for strict descendant cleanup.
Wall time is 1..600 seconds, captured output is capped at 4 MiB with 20,000-byte
tails. Input files are at most 8 MiB each, 128 files, 32 MiB total; accepted
evidence including a ZIP is at most 8 MiB.

Explicit input manifests prove which bytes were bound to execution; they do not
prove test coverage, declared dependency completeness, installed dependency
versions, offline execution, or reproducibility across environments. ZIP input
ordering, timestamps, and permissions are fixed for stable local packaging.

SQLite/filesystem access is trusted. An attacker able to rewrite the database
can forge reports and recompute its hash chain. SHA-256 detects accidental or
unreconciled mutation, not malicious authority rewriting or semantic truth.
Actor-label separation is bookkeeping only. Victor's existing IdentityKernel
is available in this repository but is not yet wired into role authorization;
do not present this runtime as authenticated independent verification.

## First product ticket: ChatGPT Export Studio

Repository located: MASSIVEMAGNETICS/chatgpt-export-studio.
Inspected main commit: c16c947704b9a1ab76be0b2d3401613feee983b9.
The GUI/CLI core selects one shortest archive member whose name ends with
conversations.json and requires a list root. It supports mapping nodes and a
direct messages list. A separate export_studio.py implementation has its own
import pipeline and basic tests. Both entry paths need compatibility coverage.

The user reports a changed export format. No representative changed-format
archive was supplied here, so the exact new schema and failure are unverified.
Do not claim that an invented fixture represents an official format.

Next acceptance work: obtain a sanitized representative failing export,
reproduce the failure on both import paths, preserve legacy search/chunking/
export/redaction behavior, define explicit format detection and unsupported
format diagnostics, and verify counts/IDs/text preservation and idempotence.
Only then implement the adapter and run this ticket through QA and packaging.
