"""Headless topological Victor Driver entrypoint for Dev-Ville."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from victor_topological_driver import TopologicalVictorDriver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Dev-Ville with topological Victor as the governed driver."
    )
    parser.add_argument("directive", help="Software-build mission directive")
    parser.add_argument(
        "--chronos",
        default="chronos/victor-devville.jsonl",
        help="Append-only Chronos JSONL path",
    )
    parser.add_argument("--max-cycles", type=int, default=500)
    parser.add_argument("--time-delta", type=float, default=2.0)
    parser.add_argument(
        "--export-dir",
        default=None,
        help="Optional local directory for verified build export",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    driver = TopologicalVictorDriver(chronos_jsonl_path=args.chronos)
    driver.start_project(args.directive)
    result = driver.run(max_cycles=args.max_cycles, time_delta=args.time_delta)
    if result.get("authoritative_build_complete") and args.export_dir:
        Path(args.export_dir).mkdir(parents=True, exist_ok=True)
        driver.export_files(args.export_dir)
        result = driver.status()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("authoritative_build_complete") else 2


if __name__ == "__main__":
    raise SystemExit(main())
