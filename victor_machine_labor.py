"""Victor machine-labor runtime for Dev-Ville.

This migration layer keeps Dev-Ville's existing scheduler/UI contracts while
replacing randomized research and beta outcomes, adding calibrated evidence,
and routing runtime observations through TRACE-0 + Chronos receipts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents import (
    CEOAgent,
    DeploymentAgent,
    DeveloperAgent,
    FinalizerAgent,
    MarketingAgent,
    PresidentOfOperationsAgent,
    SupervisorAgent,
)
from beta_organ import ExecutableBetaOrgan
from evidence_confidence import ConfidenceCalibrator
from machine_labor_organs import EvidenceResearcherAgent, ExecutableBetaTesterAgent
from research_organ import EvidenceResearchOrgan
from trace0_chronos import ChronosLedger, Trace0Observer
from verified_company import VerifiedCompany


class VictorMachineLaborCompany(VerifiedCompany):
    """Evidence-producing Dev-Ville company runtime."""

    def __init__(
        self,
        verification_timeout_seconds: float = 10.0,
        beta_timeout_seconds: float = 8.0,
        chronos_jsonl_path: Optional[str] = None,
    ):
        self.confidence_calibrator = ConfidenceCalibrator()
        self.research_organ = EvidenceResearchOrgan(self.confidence_calibrator)
        self.beta_organ = ExecutableBetaOrgan(beta_timeout_seconds)
        self.chronos = ChronosLedger(chronos_jsonl_path)
        self.trace0 = Trace0Observer(self.chronos)
        super().__init__(verification_timeout_seconds=verification_timeout_seconds)

    def _trace_worker_event(self, action: str, payload: Dict[str, Any]) -> None:
        entity = "project:none"
        if getattr(self, "current_project", None):
            entity = f"project:{self.current_project.name}"
        self.trace0.observe(
            actor="devville.machine_labor",
            action=action,
            entity_id=entity,
            payload=payload,
            provenance={"source": "worker_organ"},
            evidence={"evidence_based": True},
            authority="observation_only",
        )

    def initialize_agents(self):
        """Install evidence-backed workers while preserving legacy role routing."""
        self.agents = [
            CEOAgent("Alexandra Chen"),
            PresidentOfOperationsAgent("Marcus Rodriguez"),
            EvidenceResearcherAgent("Dr. Sarah Kim", self.research_organ, self._trace_worker_event),
            EvidenceResearcherAgent("Dr. James Wilson", self.research_organ, self._trace_worker_event),
            DeveloperAgent("Emily Zhang", "Frontend"),
            DeveloperAgent("Chris Taylor", "Frontend"),
            DeveloperAgent("Michael Brown", "Backend"),
            DeveloperAgent("Jessica Martinez", "Backend"),
            DeveloperAgent("David Lee", "Backend"),
            FinalizerAgent("Lisa Anderson"),
            FinalizerAgent("Robert Thompson"),
            ExecutableBetaTesterAgent("Ryan Mitchell", self.beta_organ, self._project_files, self._trace_worker_event),
            ExecutableBetaTesterAgent("Priya Sharma", self.beta_organ, self._project_files, self._trace_worker_event),
            ExecutableBetaTesterAgent("Carlos Santos", self.beta_organ, self._project_files, self._trace_worker_event),
            DeploymentAgent("Kevin Patel"),
            DeploymentAgent("Michelle Wong"),
            MarketingAgent("Sophie Laurent"),
            MarketingAgent("Daniel Cooper"),
            SupervisorAgent("James O'Brien"),
            SupervisorAgent("Natasha Volkov"),
        ]

    def _project_files(self) -> List[Dict[str, Any]]:
        if not getattr(self, "current_project", None):
            return []
        return list(self.current_project.files)

    def _observe(
        self,
        action: str,
        entity_id: str,
        payload: Dict[str, Any],
        *,
        evidence: Optional[Dict[str, Any]] = None,
        authority: str = "observation_only",
    ) -> None:
        self.trace0.observe(
            actor="devville.runtime",
            action=action,
            entity_id=entity_id,
            payload=payload,
            provenance={"source": "devville_runtime"},
            evidence=evidence or {},
            authority=authority,
        )

    def start_project(self, directive: str):
        self._observe(
            "directive_received",
            "company:dev-ville",
            {"directive": directive},
            authority="human_directive_observed",
        )
        project = super().start_project(directive)
        if project:
            self._observe(
                "project_started",
                f"project:{project.name}",
                {"description": project.description, "task_count": len(project.tasks)},
            )
        return project

    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        super()._emit_event(event_name, data)
        entity = "company:dev-ville"
        if getattr(self, "current_project", None):
            entity = f"project:{self.current_project.name}"
        self._observe(event_name, entity, data)

    def _record_receipt(self, ticket: Any, receipt: Any) -> None:
        super()._record_receipt(ticket, receipt)
        self._observe(
            "verification_receipt_recorded",
            f"ticket:{ticket.id}",
            {
                "ticket_title": ticket.title,
                "passed": receipt.passed,
                "artifact_sha256": receipt.artifact_sha256,
                "evidence_sha256": receipt.evidence_sha256,
            },
            evidence=receipt.to_dict(),
            authority="verified_evidence_gate",
        )

    def get_trace0_events(self) -> List[Dict[str, Any]]:
        return self.chronos.events()

    def get_chronos_receipts(self) -> List[Dict[str, Any]]:
        return self.chronos.receipts()

    def verify_chronos(self) -> bool:
        return self.chronos.verify_chain()

    def save_project(self, filepath: str):
        super().save_project(filepath)
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["machine_labor"] = {
            "schema_version": "devville.machine_labor.v1",
            "trace0_events": self.get_trace0_events(),
            "chronos_receipts": self.get_chronos_receipts(),
            "chronos_verified": self.verify_chronos(),
            "confidence_calibration": self.confidence_calibrator.to_dict(),
            "verification_receipts": list(self.verification_receipts),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_project(self, filepath: str):
        """Load project state and re-establish verified machine-labor continuity."""
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        super().load_project(filepath)
        machine = snapshot.get("machine_labor", {})

        events = machine.get("trace0_events", [])
        receipts = machine.get("chronos_receipts", [])
        if events or receipts:
            if self.chronos.events():
                current = self.chronos.receipts()
                if len(receipts) > len(current):
                    raise ValueError("saved Chronos history extends beyond persistent ledger")
                if receipts and current[len(receipts) - 1]["chain_hash"] != receipts[-1]["chain_hash"]:
                    raise ValueError("saved Chronos history is not a prefix of persistent ledger")
            else:
                self.chronos.restore(events, receipts)
            self.trace0 = Trace0Observer(self.chronos)

        calibration = machine.get("confidence_calibration")
        if calibration:
            self.confidence_calibrator = ConfidenceCalibrator.from_dict(calibration)
            self.research_organ.calibrator = self.confidence_calibrator
            for agent in self.agents:
                if isinstance(agent, EvidenceResearcherAgent):
                    agent.organ = self.research_organ

        self.verification_receipts = list(machine.get("verification_receipts", self.verification_receipts))
        self._observe(
            "project_loaded",
            f"project:{self.current_project.name}" if self.current_project else "company:dev-ville",
            {"filepath": str(path), "saved_chronos_events": len(events)},
            evidence={"chronos_verified": self.verify_chronos()},
        )

    def get_research_summary(self) -> Dict[str, Any]:
        """Evidence-aware research summary; never averages missing confidence."""
        researchers = [a for a in self.agents if isinstance(a, EvidenceResearcherAgent)]
        findings: List[Dict[str, Any]] = []
        for researcher in researchers:
            findings.extend(researcher.research_findings)

        calibrated = [
            float(f["confidence_score"])
            for f in findings
            if f.get("confidence_score") is not None
        ]
        return {
            "total_findings": len(findings),
            "researchers": len(researchers),
            "evidence_based": True,
            "technologies_evaluated": sorted(
                {tech for f in findings for tech in f.get("technologies_evaluated", [])}
            ),
            "recommendations": [
                f.get("recommended_technology") for f in findings if f.get("recommended_technology")
            ],
            "calibrated_confidence_count": len(calibrated),
            "average_calibrated_confidence": (
                round(sum(calibrated) / len(calibrated), 6) if calibrated else None
            ),
            "calibration_status": "empirically_calibrated" if calibrated else "uncalibrated",
            "findings": findings,
        }

    def get_beta_test_summary(self) -> Dict[str, Any]:
        """Executable beta summary; UX remains unmeasured unless actually measured."""
        testers = [a for a in self.agents if isinstance(a, ExecutableBetaTesterAgent)]
        reports: List[Dict[str, Any]] = []
        issues: List[Dict[str, Any]] = []
        for tester in testers:
            reports.extend(tester.test_reports)
            issues.extend(tester.bugs_found)

        receipts = [r.get("beta_receipt", {}) for r in reports if r.get("beta_receipt")]
        passed = sum(1 for r in receipts if r.get("passed") is True)
        failed = sum(1 for r in receipts if r.get("passed") is False)
        return {
            "evidence_based": True,
            "testers": len(testers),
            "total_test_reports": len(reports),
            "passed_receipts": passed,
            "failed_receipts": failed,
            "total_observed_issues": len(issues),
            "ux_score": None,
            "ux_status": "not_measured_by_executable_beta",
            "reports": reports,
        }

    def record_research_outcome(self, raw_evidence_strength: float, outcome: bool) -> None:
        """Resolve a prior research prediction when a real outcome becomes known."""
        self.confidence_calibrator.record_resolution(raw_evidence_strength, outcome)
        self._observe(
            "research_outcome_resolved",
            "company:dev-ville",
            {"raw_evidence_strength": raw_evidence_strength, "outcome": bool(outcome)},
            evidence={"resolution_recorded": True},
            authority="observed_outcome",
        )
