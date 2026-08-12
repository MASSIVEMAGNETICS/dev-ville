"""Topological Victor Driver.

This is the route-origin layer above the verified VictorDriver. It removes the
legacy Dev-Ville CEO/President planner from the authoritative start path:
owner directive -> MissionCompiler -> ChoiceKernel -> CapabilityRegistry ->
authorized task DAG -> DriverControlledVille.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from trace0_chronos import sha256_json
from victor_driver import CapabilityLease, MissionState, VictorDriver
from victor_topology_kernel import RouteDecision, VictorTopologyKernel
from victor_vehicle import DriverControlledVille


class TopologicalVictorDriver(VictorDriver):
    """Victor driver whose route is generated above Dev-Ville."""

    def __init__(
        self,
        *,
        vehicle: Optional[DriverControlledVille] = None,
        chronos_jsonl_path: Optional[str] = None,
        verification_timeout_seconds: float = 10.0,
        beta_timeout_seconds: float = 8.0,
        capability_lease: Optional[CapabilityLease] = None,
    ):
        super().__init__(
            vehicle=vehicle,
            chronos_jsonl_path=chronos_jsonl_path,
            verification_timeout_seconds=verification_timeout_seconds,
            beta_timeout_seconds=beta_timeout_seconds,
            capability_lease=capability_lease,
        )
        self.topology = VictorTopologyKernel(calibrator=self.vehicle.confidence_calibrator)
        self.topology.rebuild_from_chronos(self.vehicle.get_trace0_events())
        self.restored_route_id: Optional[str] = None

    def _observe(
        self,
        action: str,
        entity: str,
        payload: Dict[str, Any],
        evidence: Optional[Dict[str, Any]] = None,
        authority: str = "driver_decision",
    ) -> None:
        super()._observe(action, entity, payload, evidence, authority)
        if hasattr(self, "topology"):
            self.topology.sync_from_chronos(self.vehicle.get_trace0_events())

    def _route_or_halt(self, directive: str) -> RouteDecision:
        route = self.topology.compile_route(
            directive,
            lease_active_task_types=self.lease.active_task_types,
        )
        if route.feasible:
            return route

        mission_id = f"mission_{sha256_json({'directive': directive, 'route': route.route_id})[:24]}"
        self.mission = MissionState(
            mission_id=mission_id,
            directive=directive,
            status="halted",
            phase="ROUTE_REJECTED",
            halt_reason=route.choice.reason,
        )
        self._observe(
            "mission_route_rejected",
            f"mission:{mission_id}",
            {
                "route": route.to_dict(),
                "graph_mutations": self.topology.route_graph_mutations(mission_id, route),
            },
            evidence={"choice": route.choice.to_dict()},
            authority="choice_kernel_rejection",
        )
        raise RuntimeError(f"Victor Choice Kernel found no feasible route: {route.choice.reason}")

    def start_project(self, directive: str):
        if not isinstance(directive, str) or not directive.strip():
            raise ValueError("directive must be a non-empty string")
        directive = directive.strip()
        self._authorize("start_project", "Owner supplied a mission for Victor to compile.")

        route = self._route_or_halt(directive)
        mission_id = f"mission_{sha256_json({'directive': directive, 'route': route.route_id, 'parent': self.vehicle.chronos.last_chain_hash})[:24]}"
        self.mission = MissionState(
            mission_id=mission_id,
            directive=directive,
            status="starting",
            phase="ROUTE_SELECTED",
            deferred_work=[dict(x) for x in route.selected_plan.deferred_work],
        )

        self._observe(
            "mission_route_selected",
            f"mission:{mission_id}",
            {
                "route": route.to_dict(),
                "graph_mutations": self.topology.route_graph_mutations(mission_id, route),
            },
            evidence={
                "choice": route.choice.to_dict(),
                "capabilities": self.topology.capabilities.capabilities(),
            },
            authority="choice_kernel_decision",
        )

        plan = route.selected_plan
        project = self.vehicle.start_project_from_plan(
            directive,
            [task.to_vehicle_dict() for task in plan.tasks],
            [dict(x) for x in plan.deferred_work],
        )
        self.topology.sync_from_chronos(self.vehicle.get_trace0_events())
        self.mission.deferred_work = list(self.vehicle.deferred_work)
        self.mission.status = "running"
        self.mission.phase = self._phase()

        prediction = self.topology.register_route_prediction(mission_id, route)
        if prediction:
            self._observe(
                "route_prediction_registered",
                f"prediction:{prediction.prediction_id}",
                {
                    "prediction": prediction.to_dict(),
                    "graph_mutations": self.topology.prediction_graph_mutations(mission_id, prediction),
                },
                evidence={
                    "structural_evidence_strength": route.structural_evidence_strength,
                    "calibration_status": "not_a_probability_until_resolved_history_calibrates_it",
                },
                authority="prediction_registration",
            )

        self._observe(
            "vehicle_engaged_from_victor_plan",
            f"project:{project.name}",
            {
                "mission_id": mission_id,
                "route_id": route.route_id,
                "plan_id": plan.plan_id,
                "phase": self.mission.phase,
                "task_ids": [task.task_id for task in plan.tasks],
            },
            authority="driver_plan_execution",
        )
        return project

    def _resolve_route_once(self, outcome: bool, evidence: Dict[str, Any]) -> None:
        prediction_id = self.topology.active_prediction_id
        if not prediction_id:
            return
        current = self.topology.outcomes.predictions.get(prediction_id)
        if current is None or current.outcome is not None:
            return
        prediction = self.topology.resolve_active_route(outcome, evidence)
        if prediction:
            self._observe(
                "route_outcome_resolved",
                f"outcome:{prediction.prediction_id}",
                {
                    "prediction_id": prediction.prediction_id,
                    "outcome": bool(outcome),
                    "graph_mutations": self.topology.outcome_graph_mutations(prediction),
                },
                evidence=evidence,
                authority="outcome_resolution",
            )

    def heartbeat(self, time_delta: float = 1.0) -> Dict[str, Any]:
        state = super().heartbeat(time_delta)
        self.topology.sync_from_chronos(self.vehicle.get_trace0_events())
        if state.get("authoritative_build_complete"):
            self._resolve_route_once(
                True,
                {
                    "milestone": "VERIFIED_BUILD",
                    "ticket_summary": self.vehicle.get_ticket_summary(),
                    "verification_receipts": self.vehicle.get_verification_receipts(),
                    "chronos_head": self.vehicle.chronos.last_chain_hash,
                },
            )
        return self.status()

    def run(self, max_cycles: int = 500, time_delta: float = 2.0) -> Dict[str, Any]:
        result = super().run(max_cycles=max_cycles, time_delta=time_delta)
        if not result.get("authoritative_build_complete") and self.mission and self.mission.status == "halted":
            self._resolve_route_once(
                False,
                {
                    "halt_reason": self.mission.halt_reason,
                    "cycle": self.mission.cycle,
                    "chronos_head": self.vehicle.chronos.last_chain_hash,
                },
            )
        return self.status()

    def save_project(self, filepath: str) -> None:
        super().save_project(filepath)
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        topology_core = self.topology.state()
        data["victor_topology"] = {
            **topology_core,
            "state_sha256": sha256_json(topology_core),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._observe(
            "topology_snapshot_saved",
            f"mission:{self.mission.mission_id}" if self.mission else "company:dev-ville",
            {
                "filepath": filepath,
                "state_sha256": data["victor_topology"]["state_sha256"],
                "world_model_sequence": self.topology.world_model.last_sequence,
            },
            authority="continuity_commit",
        )

    def load_project(self, filepath: str) -> None:
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        saved_topology = snapshot.get("victor_topology")
        if saved_topology:
            topology_core = {key: value for key, value in saved_topology.items() if key != "state_sha256"}
            if saved_topology.get("state_sha256") != sha256_json(topology_core):
                raise ValueError("Victor topology snapshot hash mismatch")
        super().load_project(filepath)
        self.topology.outcomes.calibrator = self.vehicle.confidence_calibrator
        self.topology.rebuild_from_chronos(self.vehicle.get_trace0_events())
        if saved_topology:
            self.topology.restore_outcomes(saved_topology)
            active_route = saved_topology.get("active_route") or {}
            self.restored_route_id = active_route.get("route_id")
        self._observe(
            "topology_rebuilt_from_chronos",
            f"mission:{self.mission.mission_id}" if self.mission else "company:dev-ville",
            {
                "world_model_sequence": self.topology.world_model.last_sequence,
                "node_count": len(self.topology.world_model.nodes),
                "edge_count": len(self.topology.world_model.edges),
                "restored_route_id": self.restored_route_id,
            },
            evidence={"chronos_verified": self.vehicle.verify_chronos()},
            authority="continuity_materialization",
        )

    def status(self) -> Dict[str, Any]:
        state = super().status()
        topology = self.topology.state() if hasattr(self, "topology") else None
        state["driver"] = "TopologicalVictorDriver"
        state["topology"] = topology
        state["world_model"] = (
            {
                "nodes": len(self.topology.world_model.nodes),
                "edges": len(self.topology.world_model.edges),
                "last_sequence": self.topology.world_model.last_sequence,
                "state_sha256": self.topology.world_model.snapshot()["state_sha256"],
            }
            if hasattr(self, "topology")
            else None
        )
        return state
