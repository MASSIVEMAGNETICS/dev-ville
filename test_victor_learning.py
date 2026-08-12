"""Contracts for bounded route-policy learning."""
from __future__ import annotations

import unittest

from victor_capability_registry import CapabilityRegistry
from victor_choice_kernel import ChoiceKernel
from victor_learning import LearningEdgeUpdater
from victor_mission_compiler import CandidatePlan, MissionCompiler
from victor_topology_kernel import VictorTopologyKernel


class LearningEdgeTests(unittest.TestCase):
    def test_preference_is_withheld_until_minimum_resolved_history(self):
        learning = LearningEdgeUpdater(min_samples=5)
        for _ in range(4):
            learning.record("route-a", True)
        self.assertIsNone(learning.preference("route-a"))
        learning.record("route-a", False)
        self.assertAlmostEqual(learning.preference("route-a"), 0.8)

    def test_choice_uses_learning_only_to_break_equal_present_time_utility(self):
        compiler = MissionCompiler()
        intent = compiler.parse("Create a backend API")
        original = compiler.candidates(intent)[0]
        alternate = CandidatePlan(
            plan_id="plan_alternate_equal",
            name="alternate-api-route",
            project_type=original.project_type,
            tasks=original.tasks,
            deferred_work=original.deferred_work,
            rationale=original.rationale,
        )
        choice = ChoiceKernel().choose(
            intent,
            [original, alternate],
            CapabilityRegistry(),
            lease_active_task_types=("research", "design", "frontend", "backend", "testing", "beta_testing"),
            learned_preferences={original.plan_id: 0.2, alternate.plan_id: 0.8},
        )
        self.assertEqual(choice.selected_plan_id, alternate.plan_id)
        evaluations = {row.plan_id: row for row in choice.evaluations}
        self.assertEqual(evaluations[original.plan_id].utility_score, evaluations[alternate.plan_id].utility_score)

    def test_topology_exposes_learned_rate_only_after_bounded_history(self):
        kernel = VictorTopologyKernel()
        for _ in range(5):
            kernel.learning.record("api-evidence-route", True)
        route = kernel.compile_route(
            "Create a backend API",
            lease_active_task_types=("research", "design", "frontend", "backend", "testing", "beta_testing"),
        )
        selected = next(row for row in route.choice.evaluations if row.plan_id == route.choice.selected_plan_id)
        self.assertEqual(selected.learned_success_rate, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
