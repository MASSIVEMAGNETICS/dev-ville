"""Evidence-backed Dev-Ville company runtime.

`VerifiedCompany` preserves the existing Dev-Ville orchestration model while
replacing random supervisor acceptance with deterministic verification.

This is deliberately implemented as a subclass so the existing emulator can
remain available for simulation/demo use while the verified runtime becomes the
safe migration target.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from company import Company
from agents import SupervisorAgent
from verification_boundary import VerificationBoundary, VerificationReceipt


class VerifiedCompany(Company):
    """Company runtime where `done` requires executable verification evidence."""

    def __init__(self, verification_timeout_seconds: float = 10.0):
        super().__init__()
        self.verification_boundary = VerificationBoundary(
            timeout_seconds=verification_timeout_seconds
        )
        self.verification_receipts: List[Dict[str, Any]] = []

    def _primary_files_for_ticket(self, ticket: Any) -> List[Dict[str, Any]]:
        if not self.current_project:
            return []
        primaries = [
            item
            for item in self.current_project.files
            if item.get("description") == ticket.title
            and str(item.get("filename", "")).endswith(".py")
            and not str(item.get("filename", "")).startswith("test_")
        ]
        return primaries[-1:]

    def _ensure_verified_tests(self, ticket: Any) -> List[Dict[str, Any]]:
        """Materialize deterministic behavioral tests into project artifacts."""
        if not self.current_project:
            return []

        primaries = self._primary_files_for_ticket(ticket)
        generated = self.verification_boundary.generate_test_artifacts(
            primaries, description=ticket.title
        )

        marker = f"Verified tests for {ticket.title}"
        self.current_project.files = [
            item
            for item in self.current_project.files
            if item.get("description") != marker
        ]
        self.current_project.files.extend(generated)
        return generated

    def _verification_bundle(self, ticket: Any) -> List[Dict[str, Any]]:
        if not self.current_project:
            return []
        primaries = self._primary_files_for_ticket(ticket)
        verified_tests = [
            item
            for item in self.current_project.files
            if item.get("description") == f"Verified tests for {ticket.title}"
        ]
        return primaries + verified_tests

    @staticmethod
    def _failure_summary(receipt: VerificationReceipt) -> str:
        failed = [
            check["name"]
            for check in receipt.checks
            if check.get("required") and not check.get("passed")
        ]
        return ", ".join(failed) if failed else "unknown verification failure"

    def _record_receipt(self, ticket: Any, receipt: VerificationReceipt) -> None:
        data = receipt.to_dict()
        self.verification_receipts.append(data)
        ticket.history.append(
            {
                "action": "verification_receipt",
                "detail": (
                    f"{'PASS' if receipt.passed else 'FAIL'} "
                    f"evidence={receipt.evidence_sha256} "
                    f"artifact={receipt.artifact_sha256}"
                ),
                "verification": data,
            }
        )

    def _reset_task_for_rework(self, ticket: Any) -> None:
        if not self.current_project:
            return
        for task in self.current_project.tasks:
            if task.get("description") == ticket.title:
                task["progress"] = 0
                task["assigned_to"] = None
                break

    def _supervisor_review_cycle(self, supervisor: SupervisorAgent):
        """Replace probabilistic supervisor review with an evidence gate."""
        if not self.current_project:
            return

        for ticket in self.current_project.tickets:
            if ticket.status != "in_review":
                continue

            self._ensure_verified_tests(ticket)
            bundle = self._verification_bundle(ticket)
            receipt = self.verification_boundary.verify(
                bundle,
                ticket_id=ticket.id,
                ticket_title=ticket.title,
            )
            self._record_receipt(ticket, receipt)

            if receipt.passed:
                notes = (
                    "Evidence-backed verification passed. "
                    f"receipt={receipt.evidence_sha256[:16]}"
                )
                ticket.approve(supervisor.name, notes)
                ticket.complete()
                supervisor.quality_score = min(1.0, supervisor.quality_score + 0.02)
                supervisor.reviews_completed.append(
                    {
                        "ticket_id": ticket.id,
                        "ticket_title": ticket.title,
                        "passed": True,
                        "notes": notes,
                        "verification_receipt": receipt.evidence_sha256,
                    }
                )
                supervisor.log_activity(
                    f"VERIFIED ticket #{ticket.id} '{ticket.title}' "
                    f"with receipt {receipt.evidence_sha256[:16]}"
                )
                self.demo_recorder.record_event(
                    "ticket_verified",
                    f"Ticket #{ticket.id} '{ticket.title}' verified and completed",
                    {
                        "ticket_id": ticket.id,
                        "reviewer": supervisor.name,
                        "evidence_sha256": receipt.evidence_sha256,
                        "artifact_sha256": receipt.artifact_sha256,
                    },
                )
            else:
                failure = self._failure_summary(receipt)
                notes = (
                    "Verification failed; task returned to rework. "
                    f"failed_checks={failure}; "
                    f"receipt={receipt.evidence_sha256[:16]}"
                )
                ticket.reject(supervisor.name, notes)
                supervisor.quality_score = max(0.0, supervisor.quality_score - 0.05)
                supervisor.reviews_completed.append(
                    {
                        "ticket_id": ticket.id,
                        "ticket_title": ticket.title,
                        "passed": False,
                        "notes": notes,
                        "verification_receipt": receipt.evidence_sha256,
                    }
                )
                supervisor.log_activity(
                    f"REJECTED ticket #{ticket.id} '{ticket.title}': {failure}"
                )
                self._reset_task_for_rework(ticket)
                self.demo_recorder.record_event(
                    "ticket_verification_failed",
                    f"Ticket #{ticket.id} '{ticket.title}' returned to rework",
                    {
                        "ticket_id": ticket.id,
                        "reviewer": supervisor.name,
                        "failed_checks": failure,
                        "evidence_sha256": receipt.evidence_sha256,
                    },
                )

            break

    def get_verification_receipts(
        self, ticket_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return verification evidence, optionally filtered by ticket."""
        receipts = self.verification_receipts
        if ticket_id is not None:
            receipts = [r for r in receipts if r.get("ticket_id") == ticket_id]
        return list(receipts)
