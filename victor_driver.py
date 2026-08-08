"""Victor Driver: governed authority above the Dev-Ville vehicle."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from trace0_chronos import sha256_json
from victor_vehicle import ACTIVE_TASK_TYPES, DEFERRED_TASK_TYPES, DriverControlledVille


@dataclass(frozen=True)
class CapabilityLease:
    lease_id: str = "devville.local-software-build.v1"
    allowed_actions: tuple[str, ...] = (
        "start_project", "heartbeat", "steer", "feedback", "set_focus",
        "set_time_speed", "continue_project", "save_project", "load_project",
        "export_files", "export_logs", "read_status", "pause",
    )
    active_task_types: tuple[str, ...] = tuple(sorted(ACTIVE_TASK_TYPES))
    deferred_task_types: tuple[str, ...] = tuple(sorted(DEFERRED_TASK_TYPES))
    network_execution: bool = False
    production_deployment: bool = False

    def allows(self, action: str) -> bool:
        return action in self.allowed_actions

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MissionState:
    mission_id: str
    directive: str
    status: str = "created"
    phase: str = "RESEARCH"
    cycle: int = 0
    deferred_work: List[Dict[str, Any]] = field(default_factory=list)
    halt_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VictorDriver:
    """Mission/authority controller. Models are replaceable compute beneath it."""

    def __init__(self, *, vehicle: Optional[DriverControlledVille] = None,
                 chronos_jsonl_path: Optional[str] = None,
                 verification_timeout_seconds: float = 10.0,
                 beta_timeout_seconds: float = 8.0,
                 capability_lease: Optional[CapabilityLease] = None):
        self.lease = capability_lease or CapabilityLease()
        self.vehicle = vehicle or DriverControlledVille(
            verification_timeout_seconds, beta_timeout_seconds, chronos_jsonl_path
        )
        self.mission: Optional[MissionState] = None
        self.paused = False

    def _observe(self, action: str, entity: str, payload: Dict[str, Any],
                 evidence: Optional[Dict[str, Any]] = None,
                 authority: str = "driver_decision") -> None:
        self.vehicle.trace0.observe(
            actor="victor.driver", action=action, entity_id=entity, payload=payload,
            provenance={"source": "VictorDriver"}, evidence=evidence or {}, authority=authority,
        )

    def _authorize(self, action: str, reason: str) -> None:
        allowed = self.lease.allows(action)
        payload = {
            "action": action, "authorized": allowed, "reason": reason,
            "mission_id": self.mission.mission_id if self.mission else None,
            "phase": self.mission.phase if self.mission else None,
            "lease_id": self.lease.lease_id,
        }
        payload["decision_id"] = sha256_json({**payload, "chronos_parent": self.vehicle.chronos.last_chain_hash})
        entity = f"mission:{payload['mission_id']}" if payload["mission_id"] else "company:dev-ville"
        self._observe("authority_decision", entity, payload,
                      {"capability_lease": self.lease.to_dict()}, "capability_lease_decision")
        if not allowed:
            raise PermissionError(f"Victor Driver denied {action!r}: outside capability lease")

    def start_project(self, directive: str):
        if not isinstance(directive, str) or not directive.strip():
            raise ValueError("directive must be a non-empty string")
        self._authorize("start_project", "Owner supplied a software-build directive.")
        directive = directive.strip()
        mission_id = f"mission_{sha256_json({'directive': directive, 'lease': self.lease.lease_id, 'parent': self.vehicle.chronos.last_chain_hash})[:24]}"
        self.mission = MissionState(mission_id, directive, status="starting")
        self._observe(
            "mission_compiled", f"mission:{mission_id}",
            {"directive": directive, "active": list(self.lease.active_task_types), "deferred": list(self.lease.deferred_task_types)},
            authority="mission_scope_decision",
        )
        project = self.vehicle.start_project(directive)
        if not project:
            self.mission.status = "failed_to_start"
            self.mission.halt_reason = "vehicle returned no project"
            return None

        self.mission.deferred_work = list(self.vehicle.deferred_work)
        self.mission.status = "running"
        self.mission.phase = self._phase()
        accepted_plan = [
            {
                "type": task.get("type"),
                "description": task.get("description"),
                "effort": task.get("effort"),
            }
            for task in project.tasks
        ]
        self._observe(
            "mission_plan_accepted",
            f"mission:{mission_id}",
            {"task_graph": accepted_plan, "deferred_work": self.mission.deferred_work},
            evidence={"ticket_count": len(project.tickets)},
            authority="driver_plan_acceptance",
        )
        self._observe("vehicle_engaged", f"project:{project.name}",
                      {"mission_id": mission_id, "phase": self.mission.phase})
        return project

    def _present_types(self) -> Set[str]:
        return self.vehicle._present_task_types()

    def _done(self, ticket_type: str) -> bool:
        if not self.vehicle.current_project:
            return False
        rows = [ticket for ticket in self.vehicle.current_project.tickets if ticket.ticket_type == ticket_type]
        return bool(rows) and all(ticket.status == "done" for ticket in rows)

    def _phase(self) -> str:
        if not self.vehicle.current_project:
            return "IDLE"
        present = self._present_types()
        if "research" in present and not self._done("research"):
            return "RESEARCH"
        if "design" in present and not self._done("design"):
            return "ARCHITECTURE"
        build_types = {"frontend", "backend"} & present
        if any(not self._done(task_type) for task_type in build_types):
            return "BUILD"
        if "testing" in present and not self._done("testing"):
            return "VERIFY"
        if "beta_testing" in present and not self._done("beta_testing"):
            return "BETA"
        return "VERIFIED_BUILD"

    def heartbeat(self, time_delta: float = 1.0) -> Dict[str, Any]:
        self._authorize("heartbeat", "Advance one bounded vehicle work cycle.")
        if self.paused:
            return self.status()
        if not self.mission or not self.vehicle.current_project:
            raise RuntimeError("no active mission")
        if time_delta <= 0:
            raise ValueError("time_delta must be positive")
        before = self._phase()
        self.mission.cycle += 1
        self._observe("heartbeat_started", f"mission:{self.mission.mission_id}",
                      {"cycle": self.mission.cycle, "phase": before, "time_delta": float(time_delta)})
        self.vehicle.work_cycle(float(time_delta))
        if not self.vehicle.verify_chronos():
            self.mission.status = "halted"
            self.mission.halt_reason = "Chronos verification failed"
            raise RuntimeError(self.mission.halt_reason)
        after = self._phase()
        if after != before:
            self._observe("phase_transition", f"mission:{self.mission.mission_id}",
                          {"from": before, "to": after, "cycle": self.mission.cycle},
                          {"tickets": self.vehicle.get_ticket_summary()}, "phase_gate_decision")
        self.mission.phase = after
        if after == "VERIFIED_BUILD" and self.vehicle.authoritative_build_complete():
            self.mission.status = "verified_build_complete"
            self._observe(
                "mission_milestone_verified", f"mission:{self.mission.mission_id}",
                {"milestone": "VERIFIED_BUILD", "cycle": self.mission.cycle},
                {"tickets": self.vehicle.get_ticket_summary(), "verification_receipts": self.vehicle.get_verification_receipts()},
                "verified_evidence_gate",
            )
        return self.status()

    def run(self, max_cycles: int = 500, time_delta: float = 2.0) -> Dict[str, Any]:
        if max_cycles < 1:
            raise ValueError("max_cycles must be >= 1")
        for _ in range(max_cycles):
            state = self.heartbeat(time_delta)
            if state["authoritative_build_complete"]:
                return state
        if self.mission:
            self.mission.status = "halted"
            self.mission.halt_reason = "max_cycles_exhausted"
            self._observe("mission_halted", f"mission:{self.mission.mission_id}",
                          {"reason": self.mission.halt_reason, "cycle": self.mission.cycle},
                          authority="driver_safety_limit")
        return self.status()

    def steer(self, directive: str, priority: str = "normal", target_role: Optional[str] = None):
        self._authorize("steer", "Route owner steering through Victor.")
        return self.vehicle.steer(directive, priority=priority, target_role=target_role)

    def send_feedback(self, feedback: str, sentiment: str = "neutral", target_agent: Optional[str] = None):
        self._authorize("feedback", "Route owner feedback through Victor.")
        return self.vehicle.send_feedback(feedback, sentiment=sentiment, target_agent=target_agent)

    def set_focus(self, areas: Sequence[str]) -> None:
        self._authorize("set_focus", "Update mission focus inside the lease.")
        self.vehicle.set_focus(list(areas))

    def set_time_speed(self, value: float) -> None:
        self._authorize("set_time_speed", "Change vehicle simulation cadence without bypassing Victor.")
        speed = float(value)
        if speed <= 0:
            raise ValueError("time speed must be positive")
        self.vehicle.time_speed = speed
        entity = f"mission:{self.mission.mission_id}" if self.mission else "company:dev-ville"
        self._observe("time_speed_changed", entity, {"time_speed": speed})

    def continue_project(self) -> bool:
        self._authorize("continue_project", "Resume incomplete bounded work.")
        result = self.vehicle.continue_project()
        if self.mission:
            self.mission.phase = self._phase()
        return result

    def pause(self, value: bool = True) -> None:
        self._authorize("pause", "Pause scheduler movement without mutating evidence.")
        self.paused = bool(value)
        entity = f"mission:{self.mission.mission_id}" if self.mission else "company:dev-ville"
        self._observe("pause_changed", entity, {"paused": self.paused})

    def save_project(self, filepath: str) -> None:
        self._authorize("save_project", "Persist vehicle and driver continuity.")
        self.vehicle.save_project(filepath)
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        core = {
            "schema_version": "victor.driver.v1", "lease": self.lease.to_dict(),
            "mission": self.mission.to_dict() if self.mission else None,
            "paused": self.paused, "deferred_work": list(self.vehicle.deferred_work),
        }
        data["victor_driver"] = {**core, "state_sha256": sha256_json(core)}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        entity = f"mission:{self.mission.mission_id}" if self.mission else "company:dev-ville"
        self._observe("project_saved_by_driver", entity,
                      {"filepath": filepath, "state_sha256": data["victor_driver"]["state_sha256"]})

    def load_project(self, filepath: str) -> None:
        if not self.lease.allows("load_project"):
            raise PermissionError("load_project outside capability lease")
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        saved = snapshot.get("victor_driver")
        if saved:
            core = {key: value for key, value in saved.items() if key != "state_sha256"}
            if saved.get("state_sha256") != sha256_json(core):
                raise ValueError("Victor Driver snapshot hash mismatch")
            active_lease = json.loads(json.dumps(self.lease.to_dict()))
            if core.get("lease") != active_lease:
                raise ValueError("saved capability lease does not match active Victor Driver lease")

        self.vehicle.load_project(filepath)
        project = self.vehicle.current_project
        if saved:
            restored_deferred = list(saved.get("deferred_work", []))
            self.vehicle.deferred_work = restored_deferred
        else:
            restored_deferred = list(self.vehicle.deferred_work)

        if saved and saved.get("mission"):
            row = saved["mission"]
            self.mission = MissionState(
                mission_id=str(row["mission_id"]),
                directive=str(row["directive"]),
                status=str(row.get("status", "running")),
                phase=self._phase(),
                cycle=int(row.get("cycle", 0)),
                deferred_work=restored_deferred,
                halt_reason=row.get("halt_reason"),
            )
            self.paused = bool(saved.get("paused", False))
        elif project:
            mission_id = f"mission_{sha256_json({'directive': project.description, 'project': project.name})[:24]}"
            self.mission = MissionState(
                mission_id=mission_id,
                directive=project.description,
                status="running",
                phase=self._phase(),
                deferred_work=restored_deferred,
            )

        self._authorize("load_project", "Restore completed after preflight lease authorization.")
        self._observe("project_loaded_by_driver", f"project:{project.name}" if project else "company:dev-ville",
                      {"filepath": filepath, "restored_driver_state": bool(saved)},
                      {"chronos_verified": self.vehicle.verify_chronos()})

    def export_files(self, export_dir: str) -> None:
        self._authorize("export_files", "Export local build artifacts.")
        self.vehicle.export_files(export_dir)

    def export_logs(self, export_dir: str) -> None:
        self._authorize("export_logs", "Export local runtime logs.")
        self.vehicle.export_logs(export_dir)

    def status(self) -> Dict[str, Any]:
        self._authorize("read_status", "Read driver/vehicle state.")
        project = self.vehicle.current_project
        return {
            "driver": "VictorDriver", "vehicle": "Dev-Ville", "lease": self.lease.to_dict(),
            "mission": self.mission.to_dict() if self.mission else None,
            "project": ({"name": project.name, "status": project.status, "progress": round(project.progress, 4),
                         "tickets": self.vehicle.get_ticket_summary()} if project else None),
            "authoritative_build_complete": self.vehicle.authoritative_build_complete(),
            "chronos_verified": self.vehicle.verify_chronos(),
            "chronos_events": len(self.vehicle.get_trace0_events()),
            "chronos_head": self.vehicle.chronos.last_chain_hash,
            "verification_receipts": len(self.vehicle.get_verification_receipts()),
            "deferred_work": list(self.vehicle.deferred_work), "paused": self.paused,
        }
