# Executable role runtime v0.2

This integrates the previously standalone ten-role CLI into Dev-Ville. It
imports canonical JSON from TRACE-0; its SQLite ledger is a local work journal,
not a new Victor authority or canonical Chronos commit mechanism.

Python 3.11+; standard library only. Run from the repository root:

```bash
python -m unittest -v test_devville_roles.py
python devville_roles.py roles
python devville_roles.py --db work.sqlite3 --workspace . new --name "Export compatibility" --problem "Preserve legacy imports while supporting an observed new export fixture"
python devville_roles.py --db work.sqlite3 --workspace . audit --ticket 1
```

Attach actual reviewed documents in role order using:

```bash
python devville_roles.py --db work.sqlite3 --workspace . attach --ticket 1 --role product-manager --kind problem --file problem.md --actor product-worker --verifier requirements-reviewer
```

The first five roles establish problem, acceptance, architecture, implementation,
and delivery evidence. QA executes an explicit command and binds input hashes:

```bash
python devville_roles.py --db work.sqlite3 --workspace . test --ticket 1 --input devville_roles.py --input test_devville_roles.py --input trace0_chronos.py --output test_report.json --timeout 60 -- python -m unittest -v test_devville_roles.py
```

After preceding gates exist, attach that report as QA evidence:

```bash
python devville_roles.py --db work.sqlite3 --workspace . attach --ticket 1 --role qa-engineer --kind test --file test_report.json --actor qa-worker --verifier qa-reviewer
```

## Contracts

- Test attachment requires a recorded execution receipt for the same ticket,
  an unchanged report, zero exit status, and unchanged declared input files.
- Evidence rows must match their receipt. Handoffs bind predecessor evidence IDs.
  Changing or reattaching upstream evidence invalidates later handoffs.
- Reattach affected roles in order to recover. Historical superseded evidence
  remains recorded but is not used for current readiness.
- Both attachment and closure check the event chain under a SQLite write lock.
  Closed tickets reject further execution and evidence writes.
- Deployment declarations are rejected, including JSON with both booleans true.
  No external deployment adapter exists in this version.
- Consequently a full ticket cannot close yet. A release readiness document can
  be reviewed after QA; it is not proof of deployment or live operation.

## Trust boundary and failure modes

Actor and verifier names remain unauthenticated labels. A person with database
write access can rewrite an entire hash chain; there is no external head anchor.
The command runner runs trusted local code with the caller's OS permissions.
It is not a sandbox, capability lease, autonomous worker, or authenticated owner
approval mechanism. Timeout bounds the direct process; it is not containment
for spawned descendants. Output capture is intended for modest trusted tests.

Input coverage is caller-declared. Include all sources, dependencies and fixtures
relevant to acceptance. A zero exit code proves only that the selected command
exited successfully; selecting sufficient behavioral tests remains a review
responsibility. Files must not be concurrently modified during attachment.

Old v0.1 evidence lacks predecessor bindings and test receipts. Preserve its
database for history, then reattach evidence and rerun QA using v0.2; no old
deployment declaration is promoted.

## First product acceptance target: ChatGPT Studio

Status: blocked on source repository identification and an actual changed export
fixture. No export schema change or compatibility fix was verified by this work.
Use redacted fixtures; never commit private chat exports to a public repository.

Required acceptance evidence:

1. Locate Studio source and inventory existing importer features.
2. Reproduce the failure with an observed new-format fixture.
3. Write regression contracts for legacy and new fixtures, attachments, message
   branches, timestamps, unsupported schemas and malformed input as applicable.
4. Implement format detection and normalization without silent data loss.
5. Run tests against the exact sources and fixtures; package a hash-bound candidate.
6. Add Victor-authorized deployment and independent external verification before
   advancing the deployment gate.

This release supplies a concrete ticket/QA execution path. It does not supply
ten autonomous role workers or a complete software factory.
