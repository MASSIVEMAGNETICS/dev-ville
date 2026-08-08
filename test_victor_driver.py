"""Contract tests for Victor Driver on the real Dev-Ville runtime."""
from __future__ import annotations

import tempfile
import unittest

from victor_driver import VictorDriver
from victor_driver_facade import VictorDriverCompanyFacade
from victor_vehicle import DriverControlledVille


class VictorDriverContractTests(unittest.TestCase):
    def test_start_scopes_authoritative_vehicle_and_gates_initial_phase(self):
        driver = VictorDriver()
        project = driver.start_project("Create a simple website")
        self.assertIsNotNone(project)
        task_types = {task.get("type") for task in project.tasks}
        self.assertNotIn("deployment", task_types)
        self.assertNotIn("marketing", task_types)

        research = next(task for task in project.tasks if task.get("type") == "research")
        design = next(task for task in project.tasks if task.get("type") == "design")
        self.assertIsNotNone(research.get("assigned_to"))
        self.assertIsNone(design.get("assigned_to"))
        self.assertEqual(len(driver.mission.deferred_work), 2)
        self.assertTrue(driver.vehicle.verify_chronos())

    def test_design_unlocks_only_after_research_ticket_is_done(self):
        driver = VictorDriver()
        project = driver.start_project("Create a simple website")
        design = next(task for task in project.tasks if task.get("type") == "design")
        driver.vehicle.assign_tasks([design])
        self.assertIsNone(design.get("assigned_to"))

        research_ticket = next(
            ticket for ticket in project.tickets if ticket.ticket_type == "research"
        )
        research_ticket.complete()
        driver.vehicle.assign_tasks([design])
        self.assertIsNotNone(design.get("assigned_to"))
        design_ticket = next(
            ticket for ticket in project.tickets if ticket.ticket_type == "design"
        )
        self.assertEqual(design_ticket.status, "in_progress")

    def test_testing_phase_is_materialized_from_real_code_receipts(self):
        driver = VictorDriver()
        project = driver.start_project("Create a simple website")
        code_types = {"design", "frontend", "backend"}
        for ticket in project.tickets:
            if ticket.ticket_type in code_types | {"research"}:
                ticket.complete()
        for task in project.tasks:
            if task.get("type") in code_types | {"research"}:
                task["progress"] = task.get("effort", 100)

        code_tickets = [
            ticket for ticket in project.tickets if ticket.ticket_type in code_types
        ]
        driver.vehicle.verification_receipts = [
            {
                "ticket_id": ticket.id,
                "passed": True,
                "artifact_sha256": f"artifact-{ticket.id}",
                "evidence_sha256": f"evidence-{ticket.id}",
            }
            for ticket in code_tickets
        ]
        driver.vehicle._materialize_verification_qa()

        qa_ticket = next(
            ticket for ticket in project.tickets if ticket.ticket_type == "testing"
        )
        qa_task = next(task for task in project.tasks if task.get("type") == "testing")
        self.assertEqual(qa_ticket.status, "in_review")
        self.assertEqual(
            qa_task.get("assigned_to"), DriverControlledVille.VERIFICATION_GATE_ACTOR
        )

    def test_facade_routes_mutating_controls_through_driver(self):
        driver = VictorDriver()
        facade = VictorDriverCompanyFacade(driver)
        project = facade.start_project("Create a backend API")
        self.assertIs(project, driver.vehicle.current_project)
        facade.work_cycle(0.1)
        self.assertEqual(driver.mission.cycle, 1)
        actions = [event.get("action") for event in driver.vehicle.get_trace0_events()]
        self.assertIn("authority_decision", actions)
        self.assertIn("heartbeat_started", actions)

    def test_driver_state_is_hash_bound_in_project_snapshot(self):
        driver = VictorDriver()
        driver.start_project("Create a backend API")
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/project.json"
            driver.save_project(path)
            restored = VictorDriver()
            restored.load_project(path)
            self.assertIsNotNone(restored.mission)
            self.assertEqual(restored.mission.directive, "Create a backend API")
            self.assertTrue(restored.vehicle.verify_chronos())


if __name__ == "__main__":
    unittest.main(verbosity=2)
