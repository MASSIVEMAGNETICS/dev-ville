"""Deterministic mission compiler for the current Dev-Ville vehicle.

This compiler is intentionally not presented as general semantic intelligence.
It converts owner directives into typed requirements and candidate task DAGs
using explicit rules, so the legacy Dev-Ville CEO/President planner is no
longer authoritative.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Sequence

from trace0_chronos import sha256_json


@dataclass(frozen=True)
class MissionIntent:
    directive: str
    project_type: str
    requirements: tuple[str, ...]
    constraints: tuple[str, ...]
    requested_external_effects: tuple[str, ...]
    unsupported_requirements: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanTask:
    task_id: str
    task_type: str
    description: str
    effort: float
    depends_on: tuple[str, ...] = ()

    def to_vehicle_dict(self) -> Dict[str, Any]:
        return {
            "type": self.task_type,
            "description": self.description,
            "effort": float(self.effort),
            "progress": 0,
            "assigned_to": None,
            "depends_on": list(self.depends_on),
            "victor_task_id": self.task_id,
        }

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidatePlan:
    plan_id: str
    name: str
    project_type: str
    tasks: tuple[PlanTask, ...]
    deferred_work: tuple[Dict[str, Any], ...]
    rationale: tuple[str, ...]

    @property
    def task_types(self) -> tuple[str, ...]:
        return tuple(task.task_type for task in self.tasks)

    @property
    def total_effort(self) -> float:
        return sum(task.effort for task in self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "project_type": self.project_type,
            "tasks": [task.to_dict() for task in self.tasks],
            "deferred_work": [dict(x) for x in self.deferred_work],
            "rationale": list(self.rationale),
            "total_effort": self.total_effort,
        }


class MissionCompiler:
    """Compile owner intent into explicit candidate DAGs."""

    def parse(self, directive: str) -> MissionIntent:
        text = directive.strip()
        low = text.lower()

        if any(token in low for token in ("android", "ios", "mobile app", "flutter", "react native")):
            project_type = "mobile_application"
        elif any(token in low for token in ("api", "backend service", "rest service", "microservice")):
            project_type = "api_service"
        elif any(token in low for token in ("website", "web site", "landing page")):
            project_type = "website"
        elif any(token in low for token in ("web app", "web application", "dashboard")):
            project_type = "web_application"
        else:
            project_type = "general"

        requirements: List[str] = []
        if any(token in low for token in ("login", "auth", "authentication", "sign in")):
            requirements.append("authentication")
        if any(token in low for token in ("database", "persist", "storage", "save data")):
            requirements.append("persistence")
        if any(token in low for token in ("realtime", "real-time", "websocket")):
            requirements.append("realtime")
        if any(token in low for token in ("security", "secure")):
            requirements.append("security")
        if any(token in low for token in ("test", "tested", "production", "production-grade")):
            requirements.append("verification")

        constraints: List[str] = []
        if any(token in low for token in ("local", "offline", "sovereign")):
            constraints.append("local_first")
        if "no network" in low or "offline only" in low:
            constraints.append("no_external_network")

        external: List[str] = []
        if any(token in low for token in ("deploy", "publish", "go live", "production deployment")):
            external.append("production_deployment")
        if any(token in low for token in ("market", "promotion", "advertise", "campaign")):
            external.append("marketing_execution")
        if any(token in low for token in ("fetch from internet", "browse web", "external api")):
            external.append("network_execution")

        unsupported: List[str] = []
        if project_type == "mobile_application":
            unsupported.append("mobile_application_builder")

        return MissionIntent(
            directive=text,
            project_type=project_type,
            requirements=tuple(sorted(set(requirements))),
            constraints=tuple(sorted(set(constraints))),
            requested_external_effects=tuple(sorted(set(external))),
            unsupported_requirements=tuple(sorted(set(unsupported))),
        )

    @staticmethod
    def _task(project_type: str, task_type: str, effort: float, depends_on: Sequence[str], directive: str) -> PlanTask:
        descriptions = {
            "research": f"Collect evidence for {project_type}: {directive}",
            "design": f"Design {project_type} architecture for: {directive}",
            "frontend": f"Build frontend artifact for: {directive}",
            "backend": f"Build backend artifact for: {directive}",
            "testing": f"Verify exact build artifacts for: {directive}",
            "beta_testing": f"Execute integration/E2E beta for: {directive}",
        }
        core = {
            "project_type": project_type,
            "task_type": task_type,
            "description": descriptions[task_type],
            "depends_on": list(depends_on),
        }
        return PlanTask(
            task_id=f"task_{sha256_json(core)[:20]}",
            task_type=task_type,
            description=descriptions[task_type],
            effort=float(effort),
            depends_on=tuple(depends_on),
        )

    def _build_plan(self, intent: MissionIntent, *, include_frontend: bool, include_backend: bool, name: str) -> CandidatePlan:
        tasks: List[PlanTask] = []
        directive = intent.directive
        ptype = intent.project_type
        tasks.append(self._task(ptype, "research", 20, (), directive))
        tasks.append(self._task(ptype, "design", 30, ("research",), directive))

        build_deps = ("research", "design")
        build_types: List[str] = []
        if include_frontend:
            tasks.append(self._task(ptype, "frontend", 50, build_deps, directive))
            build_types.append("frontend")
        if include_backend:
            tasks.append(self._task(ptype, "backend", 60, build_deps, directive))
            build_types.append("backend")

        verify_deps = tuple(["design", *build_types])
        tasks.append(self._task(ptype, "testing", 30, verify_deps, directive))
        tasks.append(self._task(ptype, "beta_testing", 35, ("testing",), directive))

        deferred: List[Dict[str, Any]] = []
        for effect in intent.requested_external_effects:
            deferred.append({
                "type": "deployment" if effect == "production_deployment" else ("marketing" if effect == "marketing_execution" else "external_network"),
                "requested_effect": effect,
                "description": f"Deferred owner request: {effect}",
                "reason": "outside current local-software-build capability lease",
                "authoritative": False,
            })

        plan_core = {
            "name": name,
            "project_type": ptype,
            "tasks": [task.to_dict() for task in tasks],
            "deferred": deferred,
        }
        return CandidatePlan(
            plan_id=f"plan_{sha256_json(plan_core)[:24]}",
            name=name,
            project_type=ptype,
            tasks=tuple(tasks),
            deferred_work=tuple(deferred),
            rationale=(
                "Research precedes architecture.",
                "Build work requires accepted architecture evidence.",
                "Verification precedes executable beta.",
                "External effects are deferred outside the active lease.",
            ),
        )

    def candidates(self, intent: MissionIntent) -> List[CandidatePlan]:
        if intent.unsupported_requirements:
            return []
        if intent.project_type == "api_service":
            return [self._build_plan(intent, include_frontend=False, include_backend=True, name="api-evidence-route")]
        if intent.project_type in {"website", "web_application"}:
            return [
                self._build_plan(intent, include_frontend=True, include_backend=True, name="full-web-evidence-route"),
                self._build_plan(intent, include_frontend=True, include_backend=False, name="frontend-only-evidence-route"),
            ]
        return [self._build_plan(intent, include_frontend=False, include_backend=True, name="general-backend-evidence-route")]
