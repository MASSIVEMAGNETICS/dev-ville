"""Typed capability registry for Victor.

Capabilities describe what the runtime can actually cause. They are not agent
personas and they do not imply authority. Authority comes from the active lease;
this registry answers whether a proposed mission route is executable inside it.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    task_types: tuple[str, ...]
    actions: tuple[str, ...]
    risk: str = "low"
    external_effect: bool = False
    requires_receipt: bool = True
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_CAPABILITIES: tuple[CapabilitySpec, ...] = (
    CapabilitySpec("research.local_evidence.v1", ("research",), ("probe_runtime", "inspect_local_environment"), description="Inspect local runtime/module/executable availability."),
    CapabilitySpec("architecture.python.v1", ("design",), ("generate_artifact",), description="Generate the current SystemArchitecture artifact contract."),
    CapabilitySpec("build.frontend.python.v1", ("frontend",), ("generate_artifact",), description="Generate the current FrontendController artifact contract."),
    CapabilitySpec("build.backend.python.v1", ("backend",), ("generate_artifact",), description="Generate the current BackendService artifact contract."),
    CapabilitySpec("verify.python.v1", ("testing",), ("compile", "execute_tests", "hash_artifacts"), description="Compile and execute deterministic verification checks."),
    CapabilitySpec("beta.loopback_http.v1", ("beta_testing",), ("execute_tests", "loopback_http"), description="Execute local integration/E2E scenarios over loopback only."),
)


@dataclass(frozen=True)
class CapabilityAssessment:
    feasible: bool
    required_task_types: tuple[str, ...]
    covered_task_types: tuple[str, ...]
    missing_task_types: tuple[str, ...]
    external_effects_requested: tuple[str, ...]

    @property
    def coverage_ratio(self) -> float:
        if not self.required_task_types:
            return 1.0
        return len(self.covered_task_types) / len(self.required_task_types)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["coverage_ratio"] = round(self.coverage_ratio, 6)
        return data


class CapabilityRegistry:
    """Registry of concrete machine capabilities available to Victor."""

    def __init__(self, capabilities: Sequence[CapabilitySpec] = DEFAULT_CAPABILITIES):
        self._capabilities = {cap.capability_id: cap for cap in capabilities}

    def capabilities(self) -> List[Dict[str, Any]]:
        return [self._capabilities[key].to_dict() for key in sorted(self._capabilities)]

    def covered_task_types(self) -> Set[str]:
        return {task_type for capability in self._capabilities.values() for task_type in capability.task_types}

    def assess(self, task_types: Iterable[str], *, lease_active_task_types: Iterable[str], network_execution: bool = False, production_deployment: bool = False) -> CapabilityAssessment:
        required = tuple(sorted(set(str(x) for x in task_types)))
        covered_by_registry = self.covered_task_types()
        lease_types = set(str(x) for x in lease_active_task_types)
        covered = tuple(sorted(set(required) & covered_by_registry & lease_types))
        missing = tuple(sorted(set(required) - set(covered)))
        external: List[str] = []
        if network_execution:
            external.append("network_execution")
        if production_deployment:
            external.append("production_deployment")
        return CapabilityAssessment(
            feasible=not missing and not external,
            required_task_types=required,
            covered_task_types=covered,
            missing_task_types=missing,
            external_effects_requested=tuple(external),
        )

    def capability_for_task(self, task_type: str) -> Optional[CapabilitySpec]:
        matches = [capability for capability in self._capabilities.values() if task_type in capability.task_types]
        return sorted(matches, key=lambda x: x.capability_id)[0] if matches else None
