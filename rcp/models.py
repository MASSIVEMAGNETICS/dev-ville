from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from typing import Any, Mapping, Optional, Sequence


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class RiskTier(str, Enum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"

    @property
    def rank(self) -> int:
        return {RiskTier.R0: 0, RiskTier.R1: 1, RiskTier.R2: 2, RiskTier.R3: 3}[self]


class CaseState(str, Enum):
    DISCOVERED = "DISCOVERED"
    TRIAGED = "TRIAGED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    AUTHORIZED = "AUTHORIZED"
    CLAIMED = "CLAIMED"
    PATCHING = "PATCHING"
    VERIFYING = "VERIFYING"
    PROVEN = "PROVEN"
    RECEIPTED = "RECEIPTED"
    PR_READY = "PR_READY"
    DRAFT_PR = "DRAFT_PR"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RepositoryEvidence:
    repository_id: str
    name: str
    full_name: str
    source: str
    default_branch: str
    head_sha: str
    classification: str
    archived: bool = False
    fork: bool = False
    size_kb: int = 0
    local_path: Optional[str] = None
    root_files: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    scanned_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Finding:
    finding_id: str
    repository_id: str
    repository_full_name: str
    head_sha: str
    rule_id: str
    title: str
    severity: int
    risk: RiskTier
    blast_radius: int
    revenue_block: int
    proof_gap: int
    dependency_unlock: int
    irreversibility: int
    evidence: Mapping[str, Any]
    remediable: bool = False
    recipe: Optional[str] = None
    required_paths: tuple[str, ...] = ()

    @property
    def priority(self) -> int:
        return (
            5 * self.severity
            + 4 * self.blast_radius
            + 3 * self.revenue_block
            + 3 * self.proof_gap
            + 2 * self.dependency_unlock
            - 2 * self.irreversibility
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk"] = self.risk.value
        data["priority"] = self.priority
        return data

    @staticmethod
    def build(
        *,
        repo: RepositoryEvidence,
        rule_id: str,
        title: str,
        severity: int,
        risk: RiskTier,
        blast_radius: int,
        revenue_block: int,
        proof_gap: int,
        dependency_unlock: int,
        irreversibility: int,
        evidence: Mapping[str, Any],
        remediable: bool = False,
        recipe: Optional[str] = None,
        required_paths: Sequence[str] = (),
    ) -> "Finding":
        core = {
            "repository_id": repo.repository_id,
            "head_sha": repo.head_sha,
            "rule_id": rule_id,
            "evidence": evidence,
        }
        return Finding(
            finding_id="FND-" + sha256_json(core)[:24],
            repository_id=repo.repository_id,
            repository_full_name=repo.full_name,
            head_sha=repo.head_sha,
            rule_id=rule_id,
            title=title,
            severity=max(0, min(int(severity), 10)),
            risk=risk,
            blast_radius=max(0, min(int(blast_radius), 10)),
            revenue_block=max(0, min(int(revenue_block), 10)),
            proof_gap=max(0, min(int(proof_gap), 10)),
            dependency_unlock=max(0, min(int(dependency_unlock), 10)),
            irreversibility=max(0, min(int(irreversibility), 10)),
            evidence=dict(evidence),
            remediable=bool(remediable),
            recipe=recipe,
            required_paths=tuple(required_paths),
        )


@dataclass(frozen=True)
class RemediationCase:
    case_id: str
    finding_id: str
    repository_id: str
    repository_full_name: str
    head_sha: str
    rule_id: str
    title: str
    risk: RiskTier
    priority: int
    remediable: bool
    recipe: Optional[str]
    required_paths: tuple[str, ...]
    state: CaseState = CaseState.DISCOVERED
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk"] = self.risk.value
        data["state"] = self.state.value
        return data

    @staticmethod
    def from_finding(finding: Finding) -> "RemediationCase":
        core = {
            "finding_id": finding.finding_id,
            "repository_id": finding.repository_id,
            "head_sha": finding.head_sha,
            "rule_id": finding.rule_id,
        }
        return RemediationCase(
            case_id="REM-" + sha256_json(core)[:24],
            finding_id=finding.finding_id,
            repository_id=finding.repository_id,
            repository_full_name=finding.repository_full_name,
            head_sha=finding.head_sha,
            rule_id=finding.rule_id,
            title=finding.title,
            risk=finding.risk,
            priority=finding.priority,
            remediable=finding.remediable,
            recipe=finding.recipe,
            required_paths=finding.required_paths,
        )


@dataclass(frozen=True)
class CapabilityLease:
    lease_id: str
    case_id: str
    repository_full_name: str
    base_sha: str
    risk: RiskTier
    issued_at: str
    expires_at: str
    allowed_paths: tuple[str, ...]
    allowed_operations: tuple[str, ...]
    issuer: str
    signature: str

    def unsigned_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk"] = self.risk.value
        data.pop("signature", None)
        return data

    def to_dict(self) -> dict[str, Any]:
        data = self.unsigned_dict()
        data["signature"] = self.signature
        return data


@dataclass(frozen=True)
class RepairOperation:
    op: str
    path: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RepairPlan:
    plan_id: str
    case_id: str
    repository_full_name: str
    base_sha: str
    recipe: str
    operations: tuple[RepairOperation, ...]
    acceptance: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "case_id": self.case_id,
            "repository_full_name": self.repository_full_name,
            "base_sha": self.base_sha,
            "recipe": self.recipe,
            "operations": [op.to_dict() for op in self.operations],
            "acceptance": list(self.acceptance),
        }

    @staticmethod
    def build(
        *,
        case_id: str,
        repository_full_name: str,
        base_sha: str,
        recipe: str,
        operations: Sequence[RepairOperation],
        acceptance: Sequence[str],
    ) -> "RepairPlan":
        core = {
            "case_id": case_id,
            "repository_full_name": repository_full_name,
            "base_sha": base_sha,
            "recipe": recipe,
            "operations": [op.to_dict() for op in operations],
            "acceptance": list(acceptance),
        }
        return RepairPlan(
            plan_id="PLAN-" + sha256_json(core)[:24],
            case_id=case_id,
            repository_full_name=repository_full_name,
            base_sha=base_sha,
            recipe=recipe,
            operations=tuple(operations),
            acceptance=tuple(acceptance),
        )


@dataclass(frozen=True)
class VerificationResult:
    verification_id: str
    case_id: str
    plan_id: str
    passed: bool
    checks: tuple[Mapping[str, Any], ...]
    evidence_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "case_id": self.case_id,
            "plan_id": self.plan_id,
            "passed": self.passed,
            "checks": [dict(x) for x in self.checks],
            "evidence_sha256": self.evidence_sha256,
        }
