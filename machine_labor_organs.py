"""Dev-Ville worker adapters that replace synthetic research and beta behavior."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from agents import Agent, BetaTesterAgent, ResearcherAgent
from beta_organ import ExecutableBetaOrgan
from research_organ import EvidenceResearchOrgan


TraceCallback = Callable[[str, Dict[str, Any]], None]


class EvidenceResearcherAgent(ResearcherAgent):
    """Researcher compatible with Company routing, backed by inspectable probes."""

    def __init__(
        self,
        name: str,
        organ: EvidenceResearchOrgan,
        trace_callback: Optional[TraceCallback] = None,
    ):
        super().__init__(name)
        self.organ = organ
        self.trace_callback = trace_callback

    @staticmethod
    def _project_type(description: str) -> str:
        text = description.lower().replace("_", " ")
        for project_type in ("web_application", "api_service", "mobile_application", "website"):
            if project_type.replace("_", " ") in text:
                return project_type
        if "api" in text or "backend" in text:
            return "api_service"
        if "mobile" in text:
            return "mobile_application"
        if "website" in text or "web" in text:
            return "website"
        return "general"

    def complete_task(self, task: Dict[str, Any]):
        Agent.complete_task(self, task)
        project_type = self._project_type(task.get("description", ""))
        result = self.organ.research(project_type)
        finding = result.to_dict()
        finding.update(
            {
                "task": task.get("description", ""),
                "technologies_evaluated": sorted(
                    {row["technology"] for row in finding["evidence"]}
                ),
                "recommended_technology": finding["recommendation"],
                "recommendations": (
                    [f"Use {finding['recommendation']} based on collected local evidence"]
                    if finding["recommendation"]
                    else ["No unique evidence-backed technology winner; collect comparative evidence"]
                ),
                "confidence_score": finding["confidence"],
                "confidence_status": finding["calibration_status"],
            }
        )
        self.research_findings.append(finding)
        self.log_activity(
            f"Evidence research complete for {project_type}; "
            f"recommendation={finding['recommended_technology'] or 'UNRESOLVED'}; "
            f"confidence={finding['confidence_status']}"
        )
        if self.trace_callback:
            self.trace_callback("research_evidence_collected", finding)


class ExecutableBetaTesterAgent(BetaTesterAgent):
    """Beta tester compatible with Company routing, backed by executable evidence."""

    def __init__(
        self,
        name: str,
        organ: ExecutableBetaOrgan,
        files_provider: Callable[[], List[Dict[str, Any]]],
        trace_callback: Optional[TraceCallback] = None,
    ):
        super().__init__(name)
        self.organ = organ
        self.files_provider = files_provider
        self.trace_callback = trace_callback

    @staticmethod
    def _issue_from_scenario(scenario: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        name = scenario.get("name", "unknown")
        severity = "critical" if name == "artifact_safety" else "high"
        category = "security" if name == "artifact_safety" else "functional"
        return {
            "severity": severity,
            "category": category,
            "description": scenario.get("detail", "Executable beta scenario failed"),
            "scenario": name,
            "task": task.get("description", ""),
            "reproducible": True,
            "evidence_based": True,
        }

    def complete_task(self, task: Dict[str, Any]):
        Agent.complete_task(self, task)
        files = list(self.files_provider() or [])
        receipt = self.organ.run(files)
        failed = [s for s in receipt.scenarios if s.get("required") and not s.get("passed")]
        issues = [self._issue_from_scenario(s, task) for s in failed]
        self.bugs_found.extend(issues)
        report = {
            "task": task.get("description", ""),
            "scenarios_tested": [s.get("name") for s in receipt.scenarios],
            "bugs_found": issues,
            "ux_score": None,
            "feedback": (
                "Executable beta passed all required scenarios. UX was not measured."
                if receipt.passed
                else f"Executable beta failed {len(failed)} required scenario(s). UX was not measured."
            ),
            "evidence_based": True,
            "beta_receipt": receipt.to_dict(),
        }
        self.test_reports.append(report)
        self.log_activity(
            f"Executable beta {'PASSED' if receipt.passed else 'FAILED'}; "
            f"receipt={receipt.evidence_sha256[:16]}; failures={len(failed)}"
        )
        if self.trace_callback:
            self.trace_callback("beta_evidence_collected", report)
