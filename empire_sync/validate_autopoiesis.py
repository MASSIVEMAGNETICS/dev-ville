#!/usr/bin/env python3
"""Validate machine-enforced autopoiesis safety invariants."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "empire_sync" / "autopoiesis.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    require(policy.get("schema_version") == "autopoiesis-policy/1.0", "unsupported autopoiesis schema")
    require(policy.get("authority_model") == "single-writer-multi-reader", "authority model must remain single-writer-multi-reader")

    pulse = policy.get("pulse_minutes")
    require(isinstance(pulse, int) and 5 <= pulse <= 60, "pulse_minutes must be between 5 and 60")

    observer = policy.get("observer") or {}
    require(observer.get("strict_attempts") == 3, "strict observer retry budget must remain exactly 3")
    require(observer.get("unknown_state") == "FAIL_CLOSED", "unknown state must fail closed")
    require(observer.get("external_deadman_required") is True, "independent external deadman is required")

    repair = policy.get("repair") or {}
    require(repair.get("max_attempts_per_incident") == 1, "repair budget must remain exactly one attempt")
    forbidden = set(repair.get("forbidden_classes") or [])
    required_forbidden = {
        "authority_change",
        "credential_or_secret_change",
        "security_policy_change",
        "identity_change",
        "unknown_or_ambiguous_state",
    }
    require(required_forbidden.issubset(forbidden), "forbidden repair classes may not be weakened")

    breaker = policy.get("circuit_breaker") or {}
    require(breaker.get("fail_closed_after_retry_exhaustion") is True, "retry exhaustion must fail closed")
    require(breaker.get("fail_closed_after_repair_failure") is True, "repair failure must fail closed")
    require(breaker.get("never_loop_repairs") is True, "repair loops are forbidden")
    require(breaker.get("never_expand_authority") is True, "self-expanding authority is forbidden")

    promotion = policy.get("promotion") or {}
    require(promotion.get("authority_changes_require_human_review") is True, "authority changes require human review")
    require(promotion.get("require_source_validation") is True, "source validation is required")
    require(promotion.get("require_derived_validation") is True, "derived validation is required")

    print("autopoiesis policy: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
