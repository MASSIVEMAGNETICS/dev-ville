from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
from typing import Any, Optional

from .models import CapabilityLease, RepairPlan, VerificationResult, canonical_json, sha256_json
from .policy import PolicyDenied, PolicyGate


class IndependentVerifier:
    """Independent, deterministic verification of a worker-produced plan.

    It reconstructs the patch from the plan in a fresh temporary directory and
    compares the worker materialization against the canonical plan. It never
    consumes a worker-provided success boolean.
    """

    def __init__(self, policy: PolicyGate):
        self.policy = policy

    @staticmethod
    def _check(name: str, passed: bool, detail: str, required: bool = True) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed), "required": bool(required), "detail": detail}

    def verify(
        self,
        plan: RepairPlan,
        lease: CapabilityLease,
        *,
        worker_dir: Optional[str | Path] = None,
    ) -> VerificationResult:
        checks: list[dict[str, Any]] = []

        try:
            self.policy.verify(lease)
            checks.append(self._check("lease_signature_and_expiry", True, f"lease {lease.lease_id} valid"))
        except PolicyDenied as exc:
            checks.append(self._check("lease_signature_and_expiry", False, str(exc)))

        checks.append(
            self._check(
                "plan_case_binding",
                plan.case_id == lease.case_id and plan.repository_full_name == lease.repository_full_name,
                f"plan={plan.case_id} lease={lease.case_id}",
            )
        )
        checks.append(
            self._check(
                "base_sha_binding",
                plan.base_sha == lease.base_sha,
                f"plan={plan.base_sha} lease={lease.base_sha}",
            )
        )

        seen_paths: set[str] = set()
        path_ok = True
        content_ok = True
        for op in plan.operations:
            try:
                self.policy.authorize_operation(lease, op=op.op, path=op.path)
            except PolicyDenied:
                path_ok = False
            normalized = PurePosixPath(op.path.replace("\\", "/")).as_posix()
            if normalized in seen_paths:
                path_ok = False
            seen_paths.add(normalized)
            encoded = op.content.encode("utf-8")
            if not encoded or len(encoded) > 262_144 or "\x00" in op.content:
                content_ok = False
        checks.append(self._check("lease_scope_exact", path_ok, f"paths={sorted(seen_paths)}"))
        checks.append(self._check("bounded_text_payload", content_ok, "all writes are non-empty UTF-8 text <= 256 KiB"))

        if plan.recipe == "safe_gitignore_v1":
            recipe_ok = len(plan.operations) == 1 and plan.operations[0].op == "write" and plan.operations[0].path == ".gitignore"
            content = plan.operations[0].content if plan.operations else ""
            required_markers = (".env", "*.key", "__pycache__/", "node_modules/", ".rcp/")
            recipe_ok = recipe_ok and all(marker in content for marker in required_markers)
            dangerous = {"*", "src/", "tests/", ".github/", "README.md", "LICENSE"}
            exact_lines = {line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")}
            recipe_ok = recipe_ok and not bool(exact_lines & dangerous)
            checks.append(
                self._check(
                    "recipe_safe_gitignore_v1",
                    recipe_ok,
                    "only .gitignore is written; safety markers present; no broad source/documentation exclusions",
                )
            )
        else:
            checks.append(self._check("known_recipe", False, f"unsupported verifier recipe {plan.recipe!r}"))

        canonical_artifact = {
            "case_id": plan.case_id,
            "plan_id": plan.plan_id,
            "operations": [op.to_dict() for op in plan.operations],
        }
        artifact_hash = sha256_json(canonical_artifact)
        checks.append(self._check("artifact_hash", True, artifact_hash))

        with tempfile.TemporaryDirectory(prefix="rcp-independent-verify-") as temp:
            independent_root = Path(temp)
            reconstruction_ok = True
            for op in plan.operations:
                target = independent_root / op.path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(op.content, encoding="utf-8")
                if target.read_text(encoding="utf-8") != op.content:
                    reconstruction_ok = False
            checks.append(self._check("independent_reconstruction", reconstruction_ok, "plan reconstructed in fresh verifier directory"))

        if worker_dir is not None:
            worker_root = Path(worker_dir)
            worker_match = True
            details: list[str] = []
            for op in plan.operations:
                path = worker_root / op.path
                if not path.exists():
                    worker_match = False
                    details.append(f"missing:{op.path}")
                    continue
                actual = path.read_text(encoding="utf-8")
                if actual != op.content:
                    worker_match = False
                    details.append(f"mismatch:{op.path}")
            checks.append(
                self._check(
                    "worker_materialization_matches_plan",
                    worker_match,
                    ",".join(details) if details else "worker bytes match canonical plan",
                )
            )

        passed = all(check["passed"] for check in checks if check["required"])
        evidence_core = {
            "case_id": plan.case_id,
            "plan_id": plan.plan_id,
            "passed": passed,
            "checks": checks,
        }
        evidence_sha = sha256_json(evidence_core)
        return VerificationResult(
            verification_id="VERIFY-" + evidence_sha[:24],
            case_id=plan.case_id,
            plan_id=plan.plan_id,
            passed=passed,
            checks=tuple(checks),
            evidence_sha256=evidence_sha,
        )
