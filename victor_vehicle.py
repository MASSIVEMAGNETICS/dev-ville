"""Driver-controlled Dev-Ville vehicle."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from victor_machine_labor import VictorMachineLaborCompany

ACTIVE_TASK_TYPES = frozenset({"research", "design", "frontend", "backend", "testing", "beta_testing"})
DEFERRED_TASK_TYPES = frozenset({"deployment", "marketing"})
DEPENDENCIES: Dict[str, Set[str]] = {
    "research": set(),
    "design": {"research"},
    "frontend": {"research", "design"},
    "backend": {"research", "design"},
    "testing": {"design", "frontend", "backend"},
    "beta_testing": {"testing"},
}


class DriverControlledVille(VictorMachineLaborCompany):
    """Vehicle whose scheduler releases work only after prerequisite evidence."""

    VERIFICATION_GATE_ACTOR = "Victor Verification Gate"

    def __init__(self, verification_timeout_seconds: float = 10.0,
                 beta_timeout_seconds: float = 8.0,
                 chronos_jsonl_path: Optional[str] = None):
        self.deferred_work: List[Dict[str, Any]] = []
        super().__init__(verification_timeout_seconds, beta_timeout_seconds, chronos_jsonl_path)

    def _scope(self, source: str) -> None:
        if not self.current_project:
            return
        project = self.current_project
        deferred = [dict(task) for task in project.tasks if task.get("type") in DEFERRED_TASK_TYPES]
        self.deferred_work = deferred
        project.tasks = [task for task in project.tasks if task.get("type") in ACTIVE_TASK_TYPES]
        project.tickets = [ticket for ticket in project.tickets if ticket.ticket_type in ACTIVE_TASK_TYPES]
        project.calculate_progress()
        self.trace0.observe(
            actor="victor.driver.vehicle_gate",
            action="authoritative_scope_applied",
            entity_id=f"project:{project.name}",
            payload={
                "active": sorted(self._present_task_types()),
                "deferred": sorted({task.get("type") for task in deferred if task.get("type")}),
                "source": source,
            },
            provenance={"source": f"DriverControlledVille.{source}"},
            evidence={"deferred_work": self.deferred_work},
            authority="driver_scope_gate",
        )

    def start_project(self, directive: str):
        project = super().start_project(directive)
        if project:
            self._scope("start_project")
        return project

    def load_project(self, filepath: str):
        super().load_project(filepath)
        self._scope("load_project")

    def _present_task_types(self) -> Set[str]:
        if not self.current_project:
            return set()
        return {
            str(task.get("type"))
            for task in self.current_project.tasks
            if task.get("type") in ACTIVE_TASK_TYPES
        }

    def _tickets(self, types: Iterable[str]) -> List[Any]:
        if not self.current_project:
            return []
        allowed = set(types)
        return [ticket for ticket in self.current_project.tickets if ticket.ticket_type in allowed]

    def _deps_done(self, task_type: str) -> bool:
        required = DEPENDENCIES.get(task_type)
        if required is None:
            return False
        effective_required = set(required) & self._present_task_types()
        if not effective_required:
            return True
        tickets = self._tickets(effective_required)
        ticket_types = {ticket.ticket_type for ticket in tickets}
        return effective_required.issubset(ticket_types) and all(
            ticket.status == "done" for ticket in tickets
        )

    def assign_tasks(self, tasks: List[Dict[str, Any]]):
        if not self.current_project:
            return super().assign_tasks(tasks)
        tickets_exist = bool(self.current_project.tickets)
        ready: List[Dict[str, Any]] = []
        for task in tasks:
            task_type = str(task.get("type", ""))
            if task_type not in ACTIVE_TASK_TYPES or task_type == "testing":
                continue
            if not tickets_exist:
                if task_type == "research":
                    ready.append(task)
            elif self._deps_done(task_type):
                ready.append(task)
        super().assign_tasks(ready)

        if tickets_exist:
            for task in ready:
                assignee = task.get("assigned_to")
                if not assignee:
                    continue
                ticket = next(
                    (row for row in self.current_project.tickets if row.title == task.get("description")),
                    None,
                )
                if not ticket or ticket.status not in {"open", "in_progress"}:
                    continue
                if ticket.status == "open" or ticket.assigned_to != assignee:
                    ticket.assign(str(assignee))

    def _materialize_verification_qa(self) -> None:
        """Satisfy QA from exact code verification receipts, not synthetic QA."""
        if not self.current_project or not self._deps_done("testing"):
            return
        task = next((row for row in self.current_project.tasks if row.get("type") == "testing"), None)
        ticket = next((row for row in self.current_project.tickets if row.ticket_type == "testing"), None)
        if not task or not ticket or ticket.status == "done":
            return

        present_code_types = {"design", "frontend", "backend"} & self._present_task_types()
        code_tickets = self._tickets(present_code_types)
        code_ticket_types = {row.ticket_type for row in code_tickets}
        if not present_code_types or not present_code_types.issubset(code_ticket_types):
            return

        passed_ids = {
            int(receipt["ticket_id"])
            for receipt in self.verification_receipts
            if receipt.get("passed") is True and receipt.get("ticket_id") is not None
        }
        if any(code.id not in passed_ids for code in code_tickets):
            return

        task["assigned_to"] = self.VERIFICATION_GATE_ACTOR
        task["progress"] = task.get("effort", 100)
        if ticket.status == "open":
            ticket.assign(self.VERIFICATION_GATE_ACTOR)
        if ticket.status == "in_progress":
            ticket.submit_for_review()

        code_ids = {code.id for code in code_tickets}
        self.trace0.observe(
            actor="victor.driver.vehicle_gate",
            action="qa_satisfied_by_verification_receipts",
            entity_id=f"ticket:{ticket.id}",
            payload={"verified_code_ticket_ids": sorted(code_ids)},
            provenance={"source": "DriverControlledVille._materialize_verification_qa"},
            evidence={"verification_receipts": [r for r in self.verification_receipts if r.get("ticket_id") in code_ids]},
            authority="verified_evidence_gate",
        )

    def work_cycle(self, time_delta: float):
        self._materialize_verification_qa()
        super().work_cycle(time_delta)
        self._materialize_verification_qa()
        if self.current_project:
            idle = [
                task for task in self.current_project.tasks
                if task.get("progress", 0) < task.get("effort", 100) and not task.get("assigned_to")
            ]
            if idle:
                self.assign_tasks(idle)
            self.current_project.calculate_progress()
            if self.authoritative_build_complete():
                self.current_project.status = "completed"

    def authoritative_build_complete(self) -> bool:
        if not self.current_project or not self.current_project.tickets:
            return False
        expected = self._present_task_types()
        active = [ticket for ticket in self.current_project.tickets if ticket.ticket_type in expected]
        ticket_types = {ticket.ticket_type for ticket in active}
        return bool(expected) and expected.issubset(ticket_types) and all(
            ticket.status == "done" for ticket in active
        )
