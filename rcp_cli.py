from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import sys

from rcp.config import RCPConfig
from rcp.engine import RemediationEngine
from rcp.truth_adapter import load_truth_compiler_jsonl
from rcp.models import CaseState, RemediationCase


def emit(value) -> None:
    print(json.dumps(value, sort_keys=True, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rcp", description="Massive Magnetics autonomous remediation control plane")
    parser.add_argument("--config", default=None, help="JSON config path (default: built-in config)")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="write an example configuration")
    init.add_argument("path", nargs="?", default="rcp.json")

    sl = sub.add_parser("scan-local", help="scan local repositories and create remediation cases")
    sl.add_argument("root")

    sg = sub.add_parser("scan-github", help="scan the configured GitHub organization")
    sg.add_argument("--org", default=None)
    sg.add_argument("--metadata-only", action="store_true")

    it = sub.add_parser("ingest-truth", help="ingest Truth Compiler JSONL findings")
    it.add_argument("path")

    q = sub.add_parser("queue", help="show ranked cases")
    q.add_argument("--limit", type=int, default=50)
    q.add_argument("--state", action="append", choices=[state.value for state in CaseState])

    run = sub.add_parser("run", help="run autonomous R0/R1 cases")
    run.add_argument("--limit", type=int, default=None)
    run.add_argument("--publish", action="store_true", help="create draft PRs for proven repairs")

    one = sub.add_parser("run-case", help="run one case within autonomous policy")
    one.add_argument("case_id")
    one.add_argument("--publish", action="store_true")

    approve = sub.add_parser("approve", help="human-authorize one bounded case then run it")
    approve.add_argument("case_id")
    approve.add_argument("--publish", action="store_true")

    recover = sub.add_parser("recover", help="resume in-flight cases after interruption")
    recover.add_argument("--publish", action="store_true")

    sub.add_parser("status", help="show state counts and Chronos head")
    sub.add_parser("verify-ledger", help="verify the canonical Chronos hash chain")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    if args.command == "init":
        path = Path(args.path)
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing {path}")
        RCPConfig().save(path)
        emit({"created": str(path)})
        return 0

    config = RCPConfig.load(args.config)
    engine = RemediationEngine(config)
    try:
        if args.command == "scan-local":
            emit(engine.scan_local(args.root))
        elif args.command == "scan-github":
            emit(engine.scan_github(args.org, inspect_root=not args.metadata_only))
        elif args.command == "ingest-truth":
            repo_count = finding_count = new_cases = 0
            seen_repos: set[str] = set()
            for repo, finding in load_truth_compiler_jsonl(args.path):
                if repo.repository_id not in seen_repos:
                    engine.store.upsert_repository(repo)
                    seen_repos.add(repo.repository_id)
                    repo_count += 1
                engine.store.upsert_finding(finding)
                finding_count += 1
                case = RemediationCase.from_finding(finding)
                try:
                    engine.store.get_case(case.case_id)
                except KeyError:
                    engine.store.upsert_case(case)
                    engine._transition(case.case_id, CaseState.TRIAGED, "Truth Compiler finding ingested", evidence={"finding_id": finding.finding_id})
                    new_cases += 1
                else:
                    engine.store.upsert_case(case)
            emit({"repositories": repo_count, "findings": finding_count, "new_cases": new_cases, "case_counts": engine.store.counts(), "chronos_valid": engine.chronos.verify()})
        elif args.command == "queue":
            states = [CaseState(x) for x in args.state] if args.state else None
            emit([case.to_dict() for case in engine.store.list_cases(states=states, limit=args.limit)])
        elif args.command == "run":
            emit(engine.run_queue(limit=args.limit, publish=args.publish))
        elif args.command == "run-case":
            emit(engine.run_case(args.case_id, publish=args.publish))
        elif args.command == "approve":
            emit(engine.approve_and_run(args.case_id, publish=args.publish))
        elif args.command == "recover":
            emit(engine.recover_inflight(publish=args.publish))
        elif args.command == "status":
            emit(engine.status())
        elif args.command == "verify-ledger":
            valid = engine.chronos.verify()
            emit({"valid": valid, "head": engine.chronos.head()})
            return 0 if valid else 2
        else:
            raise AssertionError(args.command)
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
