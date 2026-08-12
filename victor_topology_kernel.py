"""Victor topology kernel: world model + mission compiler + choice + outcomes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from evidence_confidence import ConfidenceCalibrator
from trace0_chronos import sha256_json
from victor_capability_registry import CapabilityRegistry
from victor_choice_kernel import ChoiceDecision, ChoiceKernel
from victor_learning import LearningEdgeUpdater, RouteLearningRecord
from victor_mission_compiler import CandidatePlan, MissionCompiler, MissionIntent
from victor_outcome_resolver import OutcomeResolver, Prediction
from victor_world_model import VictorWorldModel


@dataclass(frozen=True)
class RouteDecision:
    route_id: str
    intent: MissionIntent
    candidates: tuple[CandidatePlan, ...]
    choice: ChoiceDecision
    selected_plan: Optional[CandidatePlan]
    structural_evidence_strength: float

    @property
    def feasible(self) -> bool:
        return self.selected_plan is not None and self.choice.decision_status == "selected"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "intent": self.intent.to_dict(),
            "candidates": [plan.to_dict() for plan in self.candidates],
            "choice": self.choice.to_dict(),
            "selected_plan": self.selected_plan.to_dict() if self.selected_plan else None,
            "structural_evidence_strength": self.structural_evidence_strength,
            "feasible": self.feasible,
        }


class VictorTopologyKernel:
    """Stable topology above replaceable inference and below owner authority."""

    def __init__(self, calibrator: Optional[ConfidenceCalibrator] = None):
        self.world_model = VictorWorldModel()
        self.capabilities = CapabilityRegistry()
        self.compiler = MissionCompiler()
        self.choice_kernel = ChoiceKernel()
        self.outcomes = OutcomeResolver(calibrator=calibrator)
        self.learning = LearningEdgeUpdater(min_samples=5)
        self.active_route: Optional[RouteDecision] = None
        self.active_prediction_id: Optional[str] = None
        self.last_learning_record: Optional[RouteLearningRecord] = None

    def compile_route(self, directive: str, *, lease_active_task_types: Sequence[str]) -> RouteDecision:
        intent = self.compiler.parse(directive)
        candidates = tuple(self.compiler.candidates(intent))
        learned_preferences = {
            plan.plan_id: preference
            for plan in candidates
            if (preference := self.learning.preference(plan.name)) is not None
        }
        choice = self.choice_kernel.choose(
            intent,
            candidates,
            self.capabilities,
            lease_active_task_types=lease_active_task_types,
            learned_preferences=learned_preferences,
        )
        selected = next((plan for plan in candidates if plan.plan_id == choice.selected_plan_id), None)
        selected_eval = next((row for row in choice.evaluations if row.plan_id == choice.selected_plan_id), None)
        structural_strength = 0.0
        if selected_eval:
            structural_strength = min(float(selected_eval.goal_coverage), float(selected_eval.capability_coverage))
        core = {
            "intent": intent.to_dict(),
            "choice": choice.to_dict(),
            "selected_plan_id": selected.plan_id if selected else None,
            "structural_evidence_strength": round(structural_strength, 6),
        }
        route = RouteDecision(
            route_id=f"route_{sha256_json(core)[:24]}",
            intent=intent,
            candidates=candidates,
            choice=choice,
            selected_plan=selected,
            structural_evidence_strength=round(structural_strength, 6),
        )
        self.active_route = route
        return route

    def register_route_prediction(self, mission_id: str, route: RouteDecision) -> Optional[Prediction]:
        if not route.feasible:
            return None
        prediction = self.outcomes.predict(
            claim="Selected mission route reaches VERIFIED_BUILD under the current capability lease.",
            evidence_strength=route.structural_evidence_strength,
            context={
                "mission_id": mission_id,
                "route_id": route.route_id,
                "plan_id": route.selected_plan.plan_id if route.selected_plan else None,
                "route_class": route.selected_plan.name if route.selected_plan else None,
            },
        )
        self.active_prediction_id = prediction.prediction_id
        return prediction

    def resolve_active_route(self, outcome: bool, evidence: Dict[str, Any]) -> Optional[Prediction]:
        if not self.active_prediction_id:
            return None
        prediction = self.outcomes.resolve(self.active_prediction_id, outcome, evidence)
        if self.active_route and self.active_route.selected_plan:
            evidence_sha = sha256_json(evidence)
            self.last_learning_record = self.learning.record(
                self.active_route.selected_plan.name,
                bool(outcome),
                evidence_sha256=evidence_sha,
            )
        return prediction

    def sync_from_chronos(self, events: Sequence[Dict[str, Any]]) -> int:
        return self.world_model.sync(events)

    def rebuild_from_chronos(self, events: Sequence[Dict[str, Any]]) -> None:
        self.world_model.rebuild(events)

    def route_graph_mutations(self, mission_id: str, route: RouteDecision) -> List[Dict[str, Any]]:
        mutations: List[Dict[str, Any]] = [
            {
                "op": "upsert_node",
                "node_id": f"mission:{mission_id}",
                "node_type": "mission",
                "attributes": {
                    "directive": route.intent.directive,
                    "project_type": route.intent.project_type,
                    "route_id": route.route_id,
                },
            },
            {
                "op": "upsert_node",
                "node_id": f"route:{route.route_id}",
                "node_type": "route",
                "attributes": {
                    "feasible": route.feasible,
                    "structural_evidence_strength": route.structural_evidence_strength,
                    "choice_status": route.choice.decision_status,
                },
            },
            {
                "op": "add_edge",
                "source": f"mission:{mission_id}",
                "target": f"route:{route.route_id}",
                "edge_type": "SELECTS_ROUTE",
                "attributes": {},
            },
        ]

        if not route.selected_plan:
            return mutations

        plan = route.selected_plan
        mutations.extend([
            {
                "op": "upsert_node",
                "node_id": f"plan:{plan.plan_id}",
                "node_type": "plan",
                "attributes": {"name": plan.name, "project_type": plan.project_type, "total_effort": plan.total_effort},
            },
            {
                "op": "add_edge",
                "source": f"route:{route.route_id}",
                "target": f"plan:{plan.plan_id}",
                "edge_type": "CHOOSES",
                "attributes": {},
            },
        ])

        task_node_ids: Dict[str, str] = {}
        for task in plan.tasks:
            node_id = f"task:{task.task_id}"
            task_node_ids[task.task_type] = node_id
            capability = self.capabilities.capability_for_task(task.task_type)
            mutations.append({
                "op": "upsert_node",
                "node_id": node_id,
                "node_type": "task",
                "attributes": {
                    "task_type": task.task_type,
                    "description": task.description,
                    "effort": task.effort,
                },
            })
            mutations.append({
                "op": "add_edge",
                "source": f"plan:{plan.plan_id}",
                "target": node_id,
                "edge_type": "CONTAINS",
                "attributes": {},
            })
            if capability:
                capability_node = f"capability:{capability.capability_id}"
                mutations.append({
                    "op": "upsert_node",
                    "node_id": capability_node,
                    "node_type": "capability",
                    "attributes": capability.to_dict(),
                })
                mutations.append({
                    "op": "add_edge",
                    "source": capability_node,
                    "target": node_id,
                    "edge_type": "ENABLES",
                    "attributes": {"requires_receipt": capability.requires_receipt},
                })

        for task in plan.tasks:
            for dependency in task.depends_on:
                source = task_node_ids.get(task.task_type)
                target = task_node_ids.get(dependency)
                if source and target:
                    mutations.append({
                        "op": "add_edge",
                        "source": source,
                        "target": target,
                        "edge_type": "DEPENDS_ON",
                        "attributes": {},
                    })
        return mutations

    def prediction_graph_mutations(self, mission_id: str, prediction: Prediction) -> List[Dict[str, Any]]:
        prediction_node = f"prediction:{prediction.prediction_id}"
        return [
            {
                "op": "upsert_node",
                "node_id": prediction_node,
                "node_type": "prediction",
                "attributes": {
                    "claim": prediction.claim,
                    "evidence_strength": prediction.evidence_strength,
                    "outcome": prediction.outcome,
                },
            },
            {
                "op": "add_edge",
                "source": f"mission:{mission_id}",
                "target": prediction_node,
                "edge_type": "PREDICTS",
                "attributes": {},
            },
        ]

    def outcome_graph_mutations(self, prediction: Prediction) -> List[Dict[str, Any]]:
        outcome_id = f"outcome:{prediction.prediction_id}"
        prediction_node = f"prediction:{prediction.prediction_id}"
        mutations: List[Dict[str, Any]] = [
            {
                "op": "upsert_node",
                "node_id": prediction_node,
                "node_type": "prediction",
                "attributes": {"outcome": prediction.outcome},
            },
            {
                "op": "upsert_node",
                "node_id": outcome_id,
                "node_type": "outcome",
                "attributes": {"success": prediction.outcome, "evidence": prediction.outcome_evidence or {}},
            },
            {
                "op": "add_edge",
                "source": prediction_node,
                "target": outcome_id,
                "edge_type": "RESULTS_IN",
                "attributes": {},
            },
        ]
        if self.active_route and self.active_route.selected_plan and self.last_learning_record:
            policy_id = f"policy:route:{self.active_route.selected_plan.name}"
            mutations.extend([
                {
                    "op": "upsert_node",
                    "node_id": policy_id,
                    "node_type": "route_policy",
                    "attributes": self.last_learning_record.to_dict(),
                },
                {
                    "op": "add_edge",
                    "source": outcome_id,
                    "target": policy_id,
                    "edge_type": "UPDATES_POLICY",
                    "attributes": {"bounded_tie_breaker_only": True},
                },
            ])
        return mutations

    def state(self) -> Dict[str, Any]:
        return {
            "schema_version": "victor.topology.v1",
            "active_route": self.active_route.to_dict() if self.active_route else None,
            "active_prediction_id": self.active_prediction_id,
            "outcomes": self.outcomes.to_dict(),
            "learning": self.learning.to_dict(),
            "world_model": {
                "last_sequence": self.world_model.last_sequence,
                "last_event_id": self.world_model.last_event_id,
                "node_count": len(self.world_model.nodes),
                "edge_count": len(self.world_model.edges),
            },
        }

    def restore_outcomes(self, data: Dict[str, Any]) -> None:
        self.active_prediction_id = data.get("active_prediction_id")
        self.outcomes.restore(data.get("outcomes") or {})
        self.learning.restore(data.get("learning") or {})
