"""Deterministic self-correcting control plane for the Bando/Victor empire.

The kernel is intentionally stdlib-only and side-effect constrained:
it analyzes a declarative topology, identifies structural gaps, applies only
allowlisted local remediations, re-assesses the graph, and emits receipts.

External actions (commerce APIs, deployments, credentials, money movement)
must be implemented as explicit capability adapters and are never invented
or executed by this kernel.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NodeStatus(str, Enum):
    ACTIVE = "active"
    READY = "ready"
    PLANNED = "planned"
    BLOCKED = "blocked"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class EmpireNode:
    node_id: str
    capability: str
    status: str
    dependencies: Tuple[str, ...] = ()
    canonical: bool = False
    auto_fix: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_mapping(raw: Mapping[str, Any]) -> "EmpireNode":
        node_id = str(raw.get("id", "")).strip()
        capability = str(raw.get("capability", "")).strip()
        status = str(raw.get("status", "")).strip()
        if not node_id:
            raise ValueError("node id is required")
        if not capability:
            raise ValueError(f"node {node_id!r} is missing capability")
        valid_statuses = {item.value for item in NodeStatus}
        if status not in valid_statuses:
            raise ValueError(
                f"node {node_id!r} has invalid status {status!r}; "
                f"expected one of {sorted(valid_statuses)}"
            )
        deps = tuple(str(dep).strip() for dep in raw.get("dependencies", []) if str(dep).strip())
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError(f"node {node_id!r} metadata must be an object")
        auto_fix = raw.get("auto_fix")
        if auto_fix is not None:
            auto_fix = str(auto_fix).strip() or None
        return EmpireNode(
            node_id=node_id,
            capability=capability,
            status=status,
            dependencies=deps,
            canonical=bool(raw.get("canonical", False)),
            auto_fix=auto_fix,
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class Gap:
    gap_id: str
    kind: str
    severity: Severity
    node_id: Optional[str]
    message: str
    auto_fix: Optional[str] = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RemediationResult:
    gap_id: str
    action: str
    applied: bool
    changed: bool
    message: str


@dataclass(frozen=True)
class ControlPlaneReceipt:
    receipt_id: str
    timestamp: str
    manifest_hash_before: str
    manifest_hash_after: str
    gaps_before: int
    gaps_after: int
    unresolved_critical: int
    remediations: Tuple[RemediationResult, ...]

    def to_mapping(self) -> Dict[str, Any]:
        data = asdict(self)
        data["remediations"] = [asdict(item) for item in self.remediations]
        return data


class EmpireTopology:
    """Loads and analyzes the canonical logical system graph."""

    def __init__(self, manifest: Mapping[str, Any]):
        self.manifest = self._validate_manifest(manifest)
        self.nodes = {
            node.node_id: node
            for node in (EmpireNode.from_mapping(item) for item in self.manifest["nodes"])
        }
        if len(self.nodes) != len(self.manifest["nodes"]):
            raise ValueError("duplicate node ids are not allowed")

    @staticmethod
    def _validate_manifest(manifest: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(manifest, Mapping):
            raise ValueError("manifest must be an object")
        version = int(manifest.get("version", 1))
        if version != 1:
            raise ValueError(f"unsupported manifest version: {version}")
        nodes = manifest.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("manifest.nodes must be a list")
        return {
            "version": version,
            "name": str(manifest.get("name", "Empire")),
            "nodes": [dict(item) for item in nodes],
        }

    def dependency_order(self) -> List[str]:
        """Return a topological ordering; raise on dependency cycles."""
        indegree = {node_id: 0 for node_id in self.nodes}
        dependents: Dict[str, List[str]] = {node_id: [] for node_id in self.nodes}

        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    continue
                indegree[node.node_id] += 1
                dependents[dep].append(node.node_id)

        queue = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
        order: List[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for dependent in sorted(dependents[current]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)
                    queue.sort()

        if len(order) != len(self.nodes):
            cyclic = sorted(node_id for node_id, degree in indegree.items() if degree > 0)
            raise ValueError(f"dependency cycle detected: {', '.join(cyclic)}")
        return order

    def centrality(self) -> Dict[str, int]:
        """Simple reverse-dependency centrality used for triage priority."""
        counts = {node_id: 0 for node_id in self.nodes}
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep in counts:
                    counts[dep] += 1
        return counts


class EmpireAssessor:
    """Find structural and readiness gaps without mutating state."""

    _SEVERITY_WEIGHT = {
        Severity.INFO: 1,
        Severity.LOW: 2,
        Severity.MEDIUM: 4,
        Severity.HIGH: 8,
        Severity.CRITICAL: 16,
    }

    def assess(self, topology: EmpireTopology) -> List[Gap]:
        gaps: List[Gap] = []
        nodes = topology.nodes

        for node in nodes.values():
            missing = sorted(dep for dep in node.dependencies if dep not in nodes)
            if missing:
                gaps.append(
                    self._gap(
                        "missing_dependency",
                        Severity.CRITICAL,
                        node.node_id,
                        f"{node.node_id} references missing dependencies: {', '.join(missing)}",
                        node.auto_fix,
                        {"missing": missing},
                    )
                )

        try:
            topology.dependency_order()
        except ValueError as exc:
            gaps.append(self._gap("dependency_cycle", Severity.CRITICAL, None, str(exc), None, {}))

        by_capability: Dict[str, List[EmpireNode]] = {}
        for node in nodes.values():
            if node.canonical and node.status != NodeStatus.ARCHIVED.value:
                by_capability.setdefault(node.capability, []).append(node)
        for capability, authorities in by_capability.items():
            if len(authorities) > 1:
                ids = sorted(node.node_id for node in authorities)
                gaps.append(
                    self._gap(
                        "duplicate_authority",
                        Severity.HIGH,
                        None,
                        f"capability {capability!r} has multiple canonical authorities: {', '.join(ids)}",
                        None,
                        {"capability": capability, "nodes": ids},
                    )
                )

        operational = {NodeStatus.ACTIVE.value, NodeStatus.READY.value}
        for node in nodes.values():
            if node.status not in operational:
                continue
            blocked_by = sorted(
                dep
                for dep in node.dependencies
                if dep in nodes and nodes[dep].status not in operational
            )
            if blocked_by:
                gaps.append(
                    self._gap(
                        "false_readiness",
                        Severity.HIGH,
                        node.node_id,
                        f"{node.node_id} is {node.status} but dependencies are not ready: {', '.join(blocked_by)}",
                        "demote_blocked",
                        {"blocked_by": blocked_by},
                    )
                )

        for node in nodes.values():
            if node.status not in {NodeStatus.PLANNED.value, NodeStatus.BLOCKED.value}:
                continue
            if not node.dependencies:
                continue
            deps_exist = all(dep in nodes for dep in node.dependencies)
            deps_ready = deps_exist and all(nodes[dep].status in operational for dep in node.dependencies)
            if deps_ready and node.auto_fix == "promote_ready":
                gaps.append(
                    self._gap(
                        "stale_block",
                        Severity.MEDIUM,
                        node.node_id,
                        f"{node.node_id} is {node.status} although all dependencies are ready",
                        "promote_ready",
                        {},
                    )
                )

        for node in nodes.values():
            blocker = str(node.metadata.get("external_blocker", "")).strip()
            if node.status == NodeStatus.BLOCKED.value and blocker:
                severity = Severity.HIGH if bool(node.metadata.get("critical_path")) else Severity.MEDIUM
                gaps.append(
                    self._gap(
                        "external_blocker",
                        severity,
                        node.node_id,
                        blocker,
                        None,
                        {"critical_path": bool(node.metadata.get("critical_path"))},
                    )
                )

        centrality = topology.centrality()
        return sorted(
            gaps,
            key=lambda gap: (
                -self._SEVERITY_WEIGHT[gap.severity],
                -centrality.get(gap.node_id or "", 0),
                gap.kind,
                gap.node_id or "",
            ),
        )

    @staticmethod
    def _gap(
        kind: str,
        severity: Severity,
        node_id: Optional[str],
        message: str,
        auto_fix: Optional[str],
        details: Mapping[str, Any],
    ) -> Gap:
        stable = json.dumps(
            {"kind": kind, "node_id": node_id, "message": message},
            sort_keys=True,
            separators=(",", ":"),
        )
        gap_id = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
        return Gap(gap_id, kind, severity, node_id, message, auto_fix, dict(details))


RemediationHandler = Callable[[MutableMapping[str, Any], Gap], Tuple[bool, str]]


class SelfCorrectingEmpire:
    """Observe -> assess -> remediate -> verify -> receipt.

    Only explicitly registered remediation handlers can mutate the manifest.
    """

    def __init__(self, manifest_path: Path | str, *, receipt_dir: Path | str = "state/empire_receipts"):
        self.manifest_path = Path(manifest_path)
        self.receipt_dir = Path(receipt_dir)
        self.assessor = EmpireAssessor()
        self.handlers: Dict[str, RemediationHandler] = {
            "promote_ready": self._promote_ready,
            "demote_blocked": self._demote_blocked,
        }

    def register_handler(self, name: str, handler: RemediationHandler) -> None:
        if not name or not name.strip():
            raise ValueError("handler name is required")
        self.handlers[name.strip()] = handler

    def run(self, *, apply: bool = True) -> ControlPlaneReceipt:
        manifest = self._load_manifest()
        before_hash = self._hash_manifest(manifest)
        gaps_before = self.assessor.assess(EmpireTopology(manifest))

        results: List[RemediationResult] = []
        changed = False
        if apply:
            for gap in gaps_before:
                action = gap.auto_fix
                if not action:
                    continue
                handler = self.handlers.get(action)
                if handler is None:
                    results.append(RemediationResult(gap.gap_id, action, False, False, f"no registered handler for {action}"))
                    continue
                did_change, message = handler(manifest, gap)
                changed = changed or did_change
                results.append(RemediationResult(gap.gap_id, action, True, did_change, message))

        if changed:
            self._atomic_write_json(self.manifest_path, manifest)

        verified_manifest = self._load_manifest()
        gaps_after = self.assessor.assess(EmpireTopology(verified_manifest))
        after_hash = self._hash_manifest(verified_manifest)
        unresolved_critical = sum(1 for gap in gaps_after if gap.severity == Severity.CRITICAL)

        timestamp = datetime.now(timezone.utc).isoformat()
        material = json.dumps(
            {
                "timestamp": timestamp,
                "before": before_hash,
                "after": after_hash,
                "gaps_before": len(gaps_before),
                "gaps_after": len(gaps_after),
                "results": [asdict(item) for item in results],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        receipt_id = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        receipt = ControlPlaneReceipt(
            receipt_id,
            timestamp,
            before_hash,
            after_hash,
            len(gaps_before),
            len(gaps_after),
            unresolved_critical,
            tuple(results),
        )
        self._write_receipt(receipt)
        return receipt

    def inspect(self) -> List[Gap]:
        return self.assessor.assess(EmpireTopology(self._load_manifest()))

    def _load_manifest(self) -> Dict[str, Any]:
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("manifest root must be an object")
        EmpireTopology(data)
        return data

    @staticmethod
    def _hash_manifest(manifest: Mapping[str, Any]) -> str:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _find_node(manifest: MutableMapping[str, Any], node_id: str) -> MutableMapping[str, Any]:
        nodes = manifest.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("manifest.nodes must be a list")
        for node in nodes:
            if isinstance(node, MutableMapping) and node.get("id") == node_id:
                return node
        raise KeyError(node_id)

    def _promote_ready(self, manifest: MutableMapping[str, Any], gap: Gap) -> Tuple[bool, str]:
        if not gap.node_id:
            return False, "gap has no node"
        node = self._find_node(manifest, gap.node_id)
        previous = str(node.get("status"))
        if previous == NodeStatus.READY.value:
            return False, "already ready"
        node["status"] = NodeStatus.READY.value
        return True, f"{gap.node_id}: {previous} -> ready"

    def _demote_blocked(self, manifest: MutableMapping[str, Any], gap: Gap) -> Tuple[bool, str]:
        if not gap.node_id:
            return False, "gap has no node"
        node = self._find_node(manifest, gap.node_id)
        previous = str(node.get("status"))
        if previous == NodeStatus.BLOCKED.value:
            return False, "already blocked"
        node["status"] = NodeStatus.BLOCKED.value
        return True, f"{gap.node_id}: {previous} -> blocked"

    def _write_receipt(self, receipt: ControlPlaneReceipt) -> None:
        self.receipt_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(self.receipt_dir / f"{receipt.receipt_id}.json", receipt.to_mapping())

    @staticmethod
    def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        tmp.replace(path)


def summarize_gaps(gaps: Sequence[Gap]) -> Dict[str, Any]:
    by_severity = {severity.value: 0 for severity in Severity}
    for gap in gaps:
        by_severity[gap.severity.value] += 1
    return {
        "total": len(gaps),
        "by_severity": by_severity,
        "critical_path": [asdict(gap) for gap in gaps if bool(gap.details.get("critical_path"))],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Assess and self-correct the empire topology.")
    parser.add_argument("--manifest", default="empire_manifest.json")
    parser.add_argument("--receipt-dir", default="state/empire_receipts")
    parser.add_argument("--check", action="store_true", help="Assess only; do not apply remediations")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args(argv)

    control = SelfCorrectingEmpire(args.manifest, receipt_dir=args.receipt_dir)
    receipt = control.run(apply=not args.check)
    gaps = control.inspect()
    print(json.dumps({
        "receipt": receipt.to_mapping(),
        "remaining_gaps": [asdict(gap) for gap in gaps],
        "summary": summarize_gaps(gaps),
    }, indent=2, default=str))
    if args.fail_on_critical and receipt.unresolved_critical:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
