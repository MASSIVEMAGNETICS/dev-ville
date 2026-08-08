"""Contracts for Victor's world model, mission compiler, choice, and route origin."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import tempfile
import unittest

from trace0_chronos import ChronosLedger, Trace0Observer
from victor_choice_kernel import ChoiceKernel
from victor_mission_compiler import MissionCompiler
from victor_topological_driver import TopologicalVictorDriver
from victor_topology_kernel import VictorTopologyKernel
from victor_vehicle import DriverControlledVille
from victor_world_model import VictorWorldModel


class MissionCompilerChoiceTests(unittest.TestCase):
    def setUp(self):
        self.kernel = VictorTopologyKernel()
        self.lease_types = ("research", "design", "frontend", "backend", "testing", "beta_testing")

    def test_api_route_is_backend_only_and_feasible(self):
        route = self.kernel.compile_route(
            "Create a secure backend REST API with persistence",
            lease_active_task_types=self.lease_types,
        )
        self.assertTrue(route.feasible)
        task_types = {task.task_type for task in route.selected_plan.tasks}
        self.assertIn("backend", task_types)
        self.assertNotIn("frontend", task_types)
        self.assertEqual(route.choice.decision_status, "selected")

    def test_static_landing_page_chooses_smaller_frontend_route(self):
        route = self.kernel.compile_route(
            "Create a static landing page website, frontend only",
            lease_active_task_types=self.lease_types,
        )
        self.assertTrue(route.feasible)
        self.assertEqual(route.selected_plan.name, "frontend-only-evidence-route")
        self.assertNotIn("backend", {task.task_type for task in route.selected_plan.tasks})

    def test_mobile_request_is_rejected_instead_of_silently_rewritten(self):
        route = self.kernel.compile_route(
            "Create an Android mobile app",
            lease_active_task_types=self.lease_types,
        )
        self.assertFalse(route.feasible)
        self.assertEqual(route.choice.decision_status, "no_feasible_route")
        self.assertIn("mobile_application_builder", route.intent.unsupported_requirements)


class WorldModelTests(unittest.TestCase):
    def test_informatron_graph_mutations_materialize_and_rebuild(self):
        fixed = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        ledger = ChronosLedger()
        trace = Trace0Observer(ledger, clock=lambda: fixed)
        trace.observe(
            actor="victor.driver",
            action="route_selected",
            entity_id="mission:m1",
            payload={
                "graph_mutations": [
                    {"op": "upsert_node", "node_id": "mission:m1", "node_type": "mission", "attributes": {"status": "running"}},
                    {"op": "upsert_node", "node_id": "task:t1", "node_type": "task", "attributes": {"task_type": "research"}},
                    {"op": "add_edge", "source": "mission:m1", "target": "task:t1", "edge_type": "CONTAINS", "attributes": {}},
                ]
            },
        )
        world = VictorWorldModel()
        world.rebuild(ledger.events())
        self.assertEqual(world.nodes["mission:m1"].node_type, "mission")
        self.assertEqual(world.nodes["task:t1"].node_type, "task")
        self.assertEqual(len(world.neighbors("mission:m1", edge_type="CONTAINS")), 1)
        first_hash = world.snapshot()["state_sha256"]
        rebuilt = VictorWorldModel()
        rebuilt.rebuild(ledger.events())
        self.assertEqual(rebuilt.snapshot()["state_sha256"], first_hash)


class TopologicalDriverTests(unittest.TestCase):
    def test_authoritative_start_bypasses_legacy_planner(self):
        vehicle = DriverControlledVille()

        def legacy_must_not_run(_directive):
            raise AssertionError("legacy Dev-Ville planner was invoked")

        vehicle.start_project = legacy_must_not_run
        driver = TopologicalVictorDriver(vehicle=vehicle)
        project = driver.start_project("Create a backend API")
        self.assertIsNotNone(project)
        task_types = {task.get("type") for task in project.tasks}
        self.assertEqual(task_types, {"research", "design", "backend", "testing", "beta_testing"})
        self.assertTrue(driver.vehicle.verify_chronos())

    def test_route_materializes_mission_plan_task_and_capability_topology(self):
        driver = TopologicalVictorDriver()
        driver.start_project("Create a web application dashboard")
        world = driver.topology.world_model
        types = {node.node_type for node in world.nodes.values()}
        self.assertTrue({"mission", "route", "plan", "task", "capability", "prediction"}.issubset(types))
        edge_types = {edge.edge_type for edge in world.edges.values()}
        self.assertIn("SELECTS_ROUTE", edge_types)
        self.assertIn("CHOOSES", edge_types)
        self.assertIn("CONTAINS", edge_types)
        self.assertIn("DEPENDS_ON", edge_types)
        self.assertIn("ENABLES", edge_types)
        self.assertIn("PREDICTS", edge_types)

    def test_unsupported_route_halts_before_vehicle_project_exists(self):
        driver = TopologicalVictorDriver()
        with self.assertRaises(RuntimeError):
            driver.start_project("Create an iOS mobile app")
        self.assertIsNone(driver.vehicle.current_project)
        self.assertEqual(driver.mission.status, "halted")
        self.assertEqual(driver.mission.phase, "ROUTE_REJECTED")

    def test_outcome_resolution_updates_prediction_and_calibration_history(self):
        driver = TopologicalVictorDriver()
        driver.start_project("Create a backend API")
        prediction_id = driver.topology.active_prediction_id
        before = len(driver.vehicle.confidence_calibrator.to_dict()["history"])
        driver._resolve_route_once(True, {"receipt": "verified"})
        prediction = driver.topology.outcomes.predictions[prediction_id]
        after = len(driver.vehicle.confidence_calibrator.to_dict()["history"])
        self.assertTrue(prediction.outcome)
        self.assertEqual(after, before + 1)
        self.assertIn("RESULTS_IN", {edge.edge_type for edge in driver.topology.world_model.edges.values()})

    def test_topology_snapshot_is_hash_bound_and_world_model_rebuilds_from_chronos(self):
        driver = TopologicalVictorDriver()
        driver.start_project("Create a backend API")
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/project.json"
            driver.save_project(path)
            with open(path, "r", encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertIn("victor_topology", saved)

            restored = TopologicalVictorDriver()
            restored.load_project(path)
            self.assertTrue(restored.vehicle.verify_chronos())
            self.assertGreater(restored.topology.world_model.last_sequence, 0)
            self.assertEqual(restored.topology.active_prediction_id, driver.topology.active_prediction_id)

            saved["victor_topology"]["active_prediction_id"] = "tampered"
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(saved, handle)
            rejected = TopologicalVictorDriver()
            with self.assertRaises(ValueError):
                rejected.load_project(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
