from __future__ import annotations

from dataclasses import asdict
import json
import logging
from pathlib import Path
from typing import Any, Iterable, Optional

from .chronos_adapter import RCPChronos
from .config import RCPConfig
from .github_client import GitHubError, GitHubRestClient
from .models import CaseState, RemediationCase, RepairOperation, RepairPlan, RiskTier, sha256_json
from .policy import PolicyDenied, PolicyGate
from .repair import RepairWorker
from .scanner import GitHubEstateScanner, LocalEstateScanner, findings_for_repo
from .store import RemediationStore
from .verifier import IndependentVerifier

LOG = logging.getLogger("rcp")


class RemediationEngine:
    def __init__(
        self,
        config: Optional[RCPConfig] = None,
        *,
        github_client: Optional[GitHubRestClient] = None,
    ):
        self.config = config or RCPConfig()
        self.state_dir = Path(self.config.state_dir).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.store = RemediationStore(self.state_dir / "remediation.sqlite3")
        self.policy = PolicyGate(
            self.state_dir,
            lease_minutes=self.config.lease_minutes,
            auto_max_risk=RiskTier(self.config.auto_max_risk),
        )
        self.worker = RepairWorker(self.policy, self.state_dir)
        self.verifier = IndependentVerifier(self.policy)
        self.chronos = RCPChronos(self.state_dir / "chronos.jsonl")
        self.github = github_client or GitHubRestClient()

    def close(self) -> None:
        self.store.close()

    def _transition(self, case_id: str, to_state: CaseState, reason: str, *, evidence: Optional[dict[str, Any]] = None) -> RemediationCase:
        case = self.store.get_case(case_id)
        if case.state == to_state:
            return case
        event_key = f"{case.case_id}:{case.state.value}->{to_state.value}"
        self.chronos.observe_once(
            event_key=event_key,
            action="remediation.case_transition",
            entity_id=case.case_id,
            payload={
                "from_state": case.state.value,
                "to_state": to_state.value,
                "reason": reason,
                "repository": case.repository_full_name,
                "head_sha": case.head_sha,
            },
            evidence=evidence or {},
            provenance={"rule_id": case.rule_id},
        )
        return self.store.transition(case_id, to_state, reason)

    def ingest_repositories(self, repos: Iterable) -> dict[str, Any]:
        repo_count = 0
        finding_count = 0
        new_cases = 0
        for repo in repos:
            repo_count += 1
            self.store.upsert_repository(repo)
            for finding in findings_for_repo(repo):
                finding_count += 1
                self.store.upsert_finding(finding)
                case = RemediationCase.from_finding(finding)
                try:
                    existing = self.store.get_case(case.case_id)
                    is_new = False
                except KeyError:
                    existing = None
                    is_new = True
                self.store.upsert_case(case)
                if is_new:
                    new_cases += 1
                    self._transition(case.case_id, CaseState.TRIAGED, "deterministic finding triage", evidence={"finding_id": finding.finding_id, "priority": finding.priority})
        return {
            "repositories": repo_count,
            "findings": finding_count,
            "new_cases": new_cases,
            "case_counts": self.store.counts(),
            "chronos_valid": self.chronos.verify(),
        }

    def scan_local(self, root: str | Path) -> dict[str, Any]:
        scanner = LocalEstateScanner(root, canonical=self.config.canonical_repos)
        return self.ingest_repositories(scanner.scan())

    def scan_github(self, org: Optional[str] = None, *, inspect_root: Optional[bool] = None) -> dict[str, Any]:
        target_org = org or self.config.github_org
        scanner = GitHubEstateScanner(self.github, target_org, canonical=self.config.canonical_repos)
        repos = scanner.scan(inspect_root=self.config.inspect_github_root if inspect_root is None else inspect_root)
        return self.ingest_repositories(repos)

    @staticmethod
    def _plan_from_payload(data: dict[str, Any]) -> RepairPlan:
        return RepairPlan(
            plan_id=data["plan_id"],
            case_id=data["case_id"],
            repository_full_name=data["repository_full_name"],
            base_sha=data["base_sha"],
            recipe=data["recipe"],
            operations=tuple(RepairOperation(**row) for row in data["operations"]),
            acceptance=tuple(data["acceptance"]),
        )

    def _ensure_plan(self, case: RemediationCase, lease) -> tuple[RepairPlan, Path]:
        payload = self.store.latest_artifact(case.case_id, "repair_plan")
        if payload:
            plan = self._plan_from_payload(payload)
        else:
            plan = self.worker.build_plan(case, lease)
            self.store.save_artifact(plan.plan_id, case.case_id, "repair_plan", plan.to_dict())
        worker_dir = self.worker.materialize(plan, lease)
        return plan, worker_dir

    def _pr_body(self, case: RemediationCase, plan: RepairPlan, verification: dict[str, Any]) -> str:
        changed = "\n".join(f"- `{op.path}` ({op.op})" for op in plan.operations)
        return f"""## Remediation Control Plane receipt

Case: `{case.case_id}`  
Rule: `{case.rule_id}`  
Base SHA: `{case.head_sha}`  
Risk: `{case.risk.value}`  
Priority: `{case.priority}`

### Changes
{changed}

### Independent verification
- verification: `{verification['verification_id']}`
- evidence SHA-256: `{verification['evidence_sha256']}`
- passed: `{verification['passed']}`

This PR was created as **draft only** by the bounded Remediation Control Plane. The RCP has no merge, deploy, secret-management, repository-deletion, or funds capability. Human review remains required before merge.
"""

    def run_case(
        self,
        case_id: str,
        *,
        publish: Optional[bool] = None,
        human_approved: bool = False,
    ) -> dict[str, Any]:
        do_publish = self.config.publish_draft_pr if publish is None else bool(publish)
        case = self.store.get_case(case_id)
        result: dict[str, Any] = {"case_id": case_id, "repository": case.repository_full_name}

        if case.state in {CaseState.BLOCKED, CaseState.FAILED, CaseState.DRAFT_PR}:
            result["state"] = case.state.value
            existing = self.store.latest_artifact(case_id, "draft_pr")
            if existing:
                result["draft_pr"] = existing
            return result

        try:
            if case.state in {CaseState.TRIAGED, CaseState.AWAITING_APPROVAL}:
                try:
                    lease = self.policy.issue(case, human_approved=human_approved)
                except PolicyDenied as exc:
                    if case.state == CaseState.TRIAGED and case.remediable and case.risk.rank > RiskTier(self.config.auto_max_risk).rank:
                        case = self._transition(case_id, CaseState.AWAITING_APPROVAL, str(exc))
                    result.update({"state": case.state.value, "authorization": "denied", "reason": str(exc)})
                    return result
                self.store.save_lease(lease)
                case = self._transition(case_id, CaseState.AUTHORIZED, f"lease {lease.lease_id} issued")
            else:
                lease = self.store.latest_lease(case_id)
                if lease is None:
                    raise PolicyDenied("in-flight case has no persisted lease")
                self.policy.verify(lease, case=case)

            if case.state == CaseState.AUTHORIZED:
                case = self._transition(case_id, CaseState.CLAIMED, "repair worker claimed leased case")
            if case.state == CaseState.CLAIMED:
                case = self._transition(case_id, CaseState.PATCHING, "bounded repair materialization started")

            if case.state == CaseState.PATCHING:
                plan, worker_dir = self._ensure_plan(case, lease)
                case = self._transition(
                    case_id,
                    CaseState.VERIFYING,
                    f"repair plan {plan.plan_id} materialized",
                    evidence={"plan_id": plan.plan_id},
                )
            else:
                plan, worker_dir = self._ensure_plan(case, lease)

            if case.state == CaseState.VERIFYING:
                verification = self.verifier.verify(plan, lease, worker_dir=worker_dir)
                self.store.save_artifact(verification.verification_id, case_id, "verification", verification.to_dict())
                if not verification.passed:
                    case = self._transition(
                        case_id,
                        CaseState.FAILED,
                        "independent verification failed",
                        evidence={"verification_id": verification.verification_id, "evidence_sha256": verification.evidence_sha256},
                    )
                    return {**result, "state": case.state.value, "verification": verification.to_dict()}
                case = self._transition(
                    case_id,
                    CaseState.PROVEN,
                    "independent verification passed",
                    evidence={"verification_id": verification.verification_id, "evidence_sha256": verification.evidence_sha256},
                )
            else:
                verification = self.verifier.verify(plan, lease, worker_dir=worker_dir)
                if not verification.passed:
                    raise RuntimeError("recovered verification no longer passes")

            if case.state == CaseState.PROVEN:
                receipt = self.chronos.observe_once(
                    event_key=f"{case.case_id}:verification:{verification.evidence_sha256}",
                    action="remediation.verification_proven",
                    entity_id=case.case_id,
                    payload={
                        "plan_id": plan.plan_id,
                        "verification_id": verification.verification_id,
                        "repository": case.repository_full_name,
                        "base_sha": case.head_sha,
                    },
                    evidence={"evidence_sha256": verification.evidence_sha256, "passed": True},
                    provenance={"lease_id": lease.lease_id, "rule_id": case.rule_id},
                )
                receipt_id = "RECEIPT-" + sha256_json(receipt)[:24]
                self.store.save_artifact(receipt_id, case_id, "chronos_receipt", receipt)
                case = self._transition(case_id, CaseState.RECEIPTED, f"Chronos receipt {receipt_id} committed")
            if case.state == CaseState.RECEIPTED:
                case = self._transition(case_id, CaseState.PR_READY, "verified repair is eligible for draft PR publication")

            result.update(
                {
                    "state": case.state.value,
                    "plan": plan.to_dict(),
                    "verification": verification.to_dict(),
                    "chronos_valid": self.chronos.verify(),
                }
            )

            if case.state == CaseState.PR_READY and do_publish:
                if not self.github.authenticated:
                    result["publish_error"] = "GitHub authentication unavailable; case remains PR_READY"
                    return result
                existing = self.store.latest_artifact(case_id, "draft_pr")
                if existing:
                    case = self._transition(case_id, CaseState.DRAFT_PR, "recovered persisted draft PR publication")
                    result.update({"state": case.state.value, "draft_pr": existing})
                    return result
                try:
                    publication = self.github.publish_plan(
                        plan,
                        title=f"RCP: {case.title}",
                        body=self._pr_body(case, plan, verification.to_dict()),
                    )
                except GitHubError as exc:
                    result["publish_error"] = str(exc)
                    return result
                artifact_id = f"PR-{case.case_id}-{publication['pr_number']}"
                self.store.save_artifact(artifact_id, case_id, "draft_pr", publication)
                case = self._transition(
                    case_id,
                    CaseState.DRAFT_PR,
                    f"draft PR #{publication['pr_number']} created",
                    evidence={"pr_number": publication["pr_number"], "commit_sha": publication["commit_sha"]},
                )
                result.update({"state": case.state.value, "draft_pr": publication})
            return result
        except Exception as exc:
            LOG.exception("RCP case %s failed", case_id)
            case = self.store.get_case(case_id)
            if case.state not in {CaseState.BLOCKED, CaseState.FAILED, CaseState.DRAFT_PR, CaseState.PR_READY}:
                try:
                    case = self._transition(case_id, CaseState.FAILED, f"{type(exc).__name__}: {exc}")
                except Exception:
                    pass
            return {**result, "state": self.store.get_case(case_id).state.value, "error": f"{type(exc).__name__}: {exc}"}

    def run_queue(self, *, limit: Optional[int] = None, publish: Optional[bool] = None) -> list[dict[str, Any]]:
        ceiling = RiskTier(self.config.auto_max_risk)
        cap = int(limit or self.config.max_auto_cases_per_run)
        candidates = [
            case
            for case in self.store.list_cases(states=[CaseState.TRIAGED], limit=10000)
            if case.remediable and case.risk.rank <= ceiling.rank
        ][:cap]
        return [self.run_case(case.case_id, publish=publish, human_approved=False) for case in candidates]

    def approve_and_run(self, case_id: str, *, publish: Optional[bool] = None) -> dict[str, Any]:
        return self.run_case(case_id, publish=publish, human_approved=True)

    def recover_inflight(self, *, publish: Optional[bool] = None) -> list[dict[str, Any]]:
        states = [
            CaseState.AUTHORIZED,
            CaseState.CLAIMED,
            CaseState.PATCHING,
            CaseState.VERIFYING,
            CaseState.PROVEN,
            CaseState.RECEIPTED,
            CaseState.PR_READY,
        ]
        return [self.run_case(case.case_id, publish=publish) for case in self.store.list_cases(states=states, limit=10000)]

    def status(self, *, limit: int = 25) -> dict[str, Any]:
        cases = self.store.list_cases(limit=limit)
        return {
            "state_dir": str(self.state_dir),
            "counts": self.store.counts(),
            "chronos_valid": self.chronos.verify(),
            "chronos_head": self.chronos.head(),
            "top_cases": [case.to_dict() for case in cases],
        }
