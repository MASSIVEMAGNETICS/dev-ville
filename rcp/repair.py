from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Callable

from .models import CapabilityLease, RemediationCase, RepairOperation, RepairPlan
from .policy import PolicyGate


SAFE_GITIGNORE = """# Massive Magnetics RCP safe baseline
# Generated only when the repository had no .gitignore.

# Secrets / local environment
.env
.env.*
!.env.example
*.pem
*.key
*.p12
*.pfx

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.venv/
venv/

# Node / JS
node_modules/
.npm/

# Build / coverage / temp
build/
dist/
coverage/
.coverage
*.log
*.tmp
*.swp

# OS / editors
.DS_Store
Thumbs.db
.vscode/
.idea/

# RCP local state
.rcp/
"""


class RepairError(RuntimeError):
    pass


Recipe = Callable[[RemediationCase], RepairPlan]


def _safe_gitignore_plan(case: RemediationCase) -> RepairPlan:
    return RepairPlan.build(
        case_id=case.case_id,
        repository_full_name=case.repository_full_name,
        base_sha=case.head_sha,
        recipe="safe_gitignore_v1",
        operations=(RepairOperation(op="write", path=".gitignore", content=SAFE_GITIGNORE),),
        acceptance=(
            "plan touches only .gitignore",
            "content includes secret, Python, Node, build, editor, and .rcp exclusions",
            "no source, CI, dependency, deployment, permission, or credential files are modified",
        ),
    )


RECIPES: dict[str, Recipe] = {
    "safe_gitignore_v1": _safe_gitignore_plan,
}


class RepairWorker:
    """Bounded repair worker. It can only materialize leased write operations."""

    def __init__(self, policy: PolicyGate, state_dir: str | Path):
        self.policy = policy
        self.state_dir = Path(state_dir)
        self.work_root = self.state_dir / "work"
        self.work_root.mkdir(parents=True, exist_ok=True)

    def build_plan(self, case: RemediationCase, lease: CapabilityLease) -> RepairPlan:
        self.policy.verify(lease, case=case)
        if not case.recipe or case.recipe not in RECIPES:
            raise RepairError(f"unsupported bounded repair recipe: {case.recipe!r}")
        plan = RECIPES[case.recipe](case)
        for operation in plan.operations:
            self.policy.authorize_operation(lease, op=operation.op, path=operation.path)
        return plan

    def materialize(self, plan: RepairPlan, lease: CapabilityLease) -> Path:
        self.policy.verify(lease)
        if plan.case_id != lease.case_id:
            raise RepairError("plan/lease case mismatch")
        target = self.work_root / plan.case_id / plan.plan_id
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=False)
        for operation in plan.operations:
            self.policy.authorize_operation(lease, op=operation.op, path=operation.path)
            if operation.op != "write":
                raise RepairError(f"unsupported repair operation: {operation.op}")
            destination = target / operation.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            resolved_parent = destination.parent.resolve()
            if target.resolve() not in {resolved_parent, *resolved_parent.parents}:
                raise RepairError("materialized path escaped worker root")
            destination.write_text(operation.content, encoding="utf-8")
        (target / "repair-plan.json").write_text(
            json.dumps(plan.to_dict(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        return target
