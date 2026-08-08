"""Evidence/constraint-based Choice Kernel for Victor mission routes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from victor_capability_registry import CapabilityRegistry
from victor_mission_compiler import CandidatePlan, MissionIntent


@dataclass(frozen=True)
class PlanEvaluation:
    plan_id: str
    feasible: bool
    utility_score: float
    capability_coverage: float
    goal_coverage: float
    total_effort: float
    learned_success_rate: Optional[float]
    missing_task_types: tuple[str, ...]
    violations: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChoiceDecision:
    selected_plan_id: Optional[str]
    evaluations: tuple[PlanEvaluation, ...]
    decision_status: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_plan_id": self.selected_plan_id,
            "evaluations": [x.to_dict() for x in self.evaluations],
            "decision_status": self.decision_status,
            "reason": self.reason,
        }


class ChoiceKernel:
    """Select a feasible route without inventing probabilistic confidence."""

    @staticmethod
    def _required_goal_types(intent: MissionIntent) -> Set[str]:
        required = {"research", "design", "testing", "beta_testing"}
        if intent.project_type == "api_service":
            required.add("backend")
        elif intent.project_type in {"website", "web_application"}:
            required.add("frontend")
            low = intent.directive.lower()
            if not any(token in low for token in ("static", "landing page", "frontend only")):
                required.add("backend")
        else:
            required.add("backend")
        return required

    @staticmethod
    def _is_acyclic(plan: CandidatePlan) -> bool:
        task_types = {task.task_type for task in plan.tasks}
        deps = {task.task_type: {dep for dep in task.depends_on if dep in task_types} for task in plan.tasks}
        temporary: Set[str] = set()
        permanent: Set[str] = set()

        def visit(node: str) -> bool:
            if node in permanent:
                return True
            if node in temporary:
                return False
            temporary.add(node)
            for dep in deps.get(node, set()):
                if not visit(dep):
                    return False
            temporary.remove(node)
            permanent.add(node)
            return True

        return all(visit(node) for node in task_types)

    def evaluate(
        self,
        intent: MissionIntent,
        plan: CandidatePlan,
        registry: CapabilityRegistry,
        *,
        lease_active_task_types: Iterable[str],
        learned_success_rate: Optional[float] = None,
    ) -> PlanEvaluation:
        task_types = set(plan.task_types)
        capability = registry.assess(task_types, lease_active_task_types=lease_active_task_types)
        required_goals = self._required_goal_types(intent)
        covered_goals = required_goals & task_types
        goal_coverage = len(covered_goals) / len(required_goals) if required_goals else 1.0

        violations: List[str] = []
        if not self._is_acyclic(plan):
            violations.append("cyclic_task_graph")
        missing_deps = [f"{task.task_type}->{dep}" for task in plan.tasks for dep in task.depends_on if dep not in task_types]
        if missing_deps:
            violations.append("missing_dependency:" + ",".join(sorted(missing_deps)))
        if intent.unsupported_requirements:
            violations.append("unsupported_requirement:" + ",".join(intent.unsupported_requirements))

        feasible = capability.feasible and not violations and goal_coverage >= 1.0
        effort_penalty = min(1.0, plan.total_effort / 500.0)
        utility = 0.55 * goal_coverage + 0.35 * capability.coverage_ratio + 0.10 * (1.0 - effort_penalty)
        if not feasible:
            utility -= 1.0

        reasons = [
            f"goal_coverage={goal_coverage:.3f}",
            f"capability_coverage={capability.coverage_ratio:.3f}",
            f"total_effort={plan.total_effort:.1f}",
        ]
        if learned_success_rate is None:
            reasons.append("learned_route_preference=insufficient_history")
        else:
            reasons.append(f"learned_route_preference={learned_success_rate:.3f}")
        if capability.missing_task_types:
            reasons.append("missing_capabilities=" + ",".join(capability.missing_task_types))
        reasons.extend(violations)

        return PlanEvaluation(
            plan_id=plan.plan_id,
            feasible=feasible,
            utility_score=round(utility, 6),
            capability_coverage=round(capability.coverage_ratio, 6),
            goal_coverage=round(goal_coverage, 6),
            total_effort=plan.total_effort,
            learned_success_rate=(round(learned_success_rate, 6) if learned_success_rate is not None else None),
            missing_task_types=capability.missing_task_types,
            violations=tuple(violations),
            reasons=tuple(reasons),
        )

    def choose(
        self,
        intent: MissionIntent,
        plans: Sequence[CandidatePlan],
        registry: CapabilityRegistry,
        *,
        lease_active_task_types: Iterable[str],
        learned_preferences: Optional[Dict[str, float]] = None,
    ) -> ChoiceDecision:
        preferences = learned_preferences or {}
        evaluations = tuple(
            self.evaluate(
                intent,
                plan,
                registry,
                lease_active_task_types=lease_active_task_types,
                learned_success_rate=preferences.get(plan.plan_id),
            )
            for plan in plans
        )
        feasible = [evaluation for evaluation in evaluations if evaluation.feasible]
        if not feasible:
            return ChoiceDecision(
                selected_plan_id=None,
                evaluations=evaluations,
                decision_status="no_feasible_route",
                reason="No candidate satisfies current goals, dependencies, and capability lease.",
            )

        def ranking(row: PlanEvaluation):
            learned = row.learned_success_rate if row.learned_success_rate is not None else -1.0
            return (-row.utility_score, -learned, row.total_effort, row.plan_id)

        selected = sorted(feasible, key=ranking)[0]
        return ChoiceDecision(
            selected_plan_id=selected.plan_id,
            evaluations=evaluations,
            decision_status="selected",
            reason=(
                "Selected highest deterministic present-time utility; sufficiently sampled "
                "historical route success is used only as a tie-breaker."
            ),
        )
