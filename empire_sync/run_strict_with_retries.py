#!/usr/bin/env python3
"""Run strict Empire Sync verification with bounded retries.

This wrapper treats network/API instability as potentially transient without
weakening the verifier. Every attempt runs the same fail-closed checks. After
the configured retry budget is exhausted, the final failing report remains on
disk for the workflow to persist as the semantic status receipt.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "empire_sync" / "check_empire_sync.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--write-report", type=Path, default=Path("empire_sync/status.json"))
    args = parser.parse_args()

    if args.attempts < 1 or args.attempts > 5:
        parser.error("--attempts must be between 1 and 5")

    report = args.write_report
    if not report.is_absolute():
        report = ROOT / report

    final_code = 1
    for attempt in range(1, args.attempts + 1):
        print(f"Empire Sync strict attempt {attempt}/{args.attempts}", flush=True)
        completed = subprocess.run(
            [sys.executable, str(CHECKER), "--write-report", str(report)],
            cwd=ROOT,
            text=True,
            check=False,
        )
        final_code = completed.returncode
        if final_code == 0:
            return 0
        if attempt < args.attempts:
            delay = 2 ** (attempt - 1)
            print(f"Strict verification failed; retrying in {delay}s.", flush=True)
            time.sleep(delay)

    print("Empire Sync retry budget exhausted; failing closed.", flush=True)
    return final_code or 1


if __name__ == "__main__":
    raise SystemExit(main())
