"""Typed, provenance-preserving world model for Victor.

Chronos remains the causal source of truth. This graph is a rebuildable view
materialized from Informatrons. Explicit graph mutations may be carried by an
Informatron payload; every event is also indexed generically as actor -> event
-> entity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from trace0_chronos import sha256_json


@dataclass
class GraphNode:
    node_id: str
    node_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_event_id: Optional[str] = None
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    edge_id: str
    source: str
    target: str
    edge_type: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    event_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VictorWorldModel:
    """Rebuildable typed multigraph materialized from Informatrons."""

    def __init__(self):
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.last_sequence = 0
        self.last_event_id: Optional[str] = None

    def _upsert_node(self, node_id: str, node_type: str, attributes: Optional[Dict[str, Any]], event_id: Optional[str]) -> None:
        node_id = str(node_id)
        node_type = str(node_type)
        attrs = dict(attributes or {})
        existing = self.nodes.get(node_id)
        if existing:
            if existing.node_type == "entity" and node_type != "entity":
                existing.node_type = node_type
            elif existing.node_type != node_type and node_type != "entity":
                raise ValueError(f"node {node_id!r} type conflict: {existing.node_type!r} vs {node_type!r}")
            existing.attributes.update(attrs)
            existing.last_event_id = event_id
            existing.version += 1
            return
        self.nodes[node_id] = GraphNode(node_id=node_id, node_type=node_type, attributes=attrs, last_event_id=event_id)

    def _add_edge(self, source: str, target: str, edge_type: str, attributes: Optional[Dict[str, Any]], event_id: Optional[str]) -> str:
        source = str(source)
        target = str(target)
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("graph edge endpoints must exist before edge creation")
        core = {
            "source": source,
            "target": target,
            "edge_type": str(edge_type),
            "attributes": dict(attributes or {}),
            "event_id": event_id,
        }
        edge_id = f"edge:{sha256_json(core)[:32]}"
        self.edges[edge_id] = GraphEdge(edge_id=edge_id, **core)
        return edge_id

    def _apply_explicit_mutations(self, event: Dict[str, Any]) -> None:
        payload = event.get("payload") or {}
        mutations = payload.get("graph_mutations") or []
        if not isinstance(mutations, list):
            raise ValueError("graph_mutations must be a list")
        event_id = str(event.get("event_id", ""))
        for mutation in mutations:
            if not isinstance(mutation, dict):
                raise ValueError("graph mutation must be an object")
            op = mutation.get("op")
            if op == "upsert_node":
                self._upsert_node(mutation["node_id"], mutation["node_type"], mutation.get("attributes"), event_id)
            elif op == "add_edge":
                self._add_edge(mutation["source"], mutation["target"], mutation["edge_type"], mutation.get("attributes"), event_id)
            else:
                raise ValueError(f"unsupported graph mutation op: {op!r}")

    def apply_informatron(self, event: Dict[str, Any]) -> None:
        sequence = int(event.get("sequence", 0))
        if sequence <= self.last_sequence:
            return
        if sequence != self.last_sequence + 1:
            raise ValueError(f"world-model sequence gap: expected {self.last_sequence + 1}, got {sequence}")

        event_id = str(event["event_id"])
        actor_id = f"actor:{event.get('actor', 'unknown')}"
        entity_id = str(event.get("entity_id") or "entity:unknown")
        event_node_id = f"event:{event_id}"

        self._upsert_node(actor_id, "actor", {"name": event.get("actor")}, event_id)
        self._upsert_node(entity_id, "entity", {}, event_id)
        self._upsert_node(event_node_id, "event", {
            "action": event.get("action"),
            "timestamp": event.get("timestamp"),
            "authority": event.get("authority"),
            "provenance": event.get("provenance") or {},
            "evidence": event.get("evidence") or {},
        }, event_id)
        self._add_edge(actor_id, event_node_id, "PRODUCED", {}, event_id)
        self._add_edge(event_node_id, entity_id, "OBSERVES", {}, event_id)
        self._apply_explicit_mutations(event)
        self.last_sequence = sequence
        self.last_event_id = event_id

    def rebuild(self, events: Iterable[Dict[str, Any]]) -> None:
        self.nodes = {}
        self.edges = {}
        self.last_sequence = 0
        self.last_event_id = None
        for event in events:
            self.apply_informatron(event)

    def sync(self, events: Iterable[Dict[str, Any]]) -> int:
        applied = 0
        for event in events:
            if int(event.get("sequence", 0)) <= self.last_sequence:
                continue
            self.apply_informatron(event)
            applied += 1
        return applied

    def neighbors(self, node_id: str, *, edge_type: Optional[str] = None, outgoing: bool = True) -> List[Dict[str, Any]]:
        rows = []
        for edge in self.edges.values():
            matches_direction = edge.source == node_id if outgoing else edge.target == node_id
            if not matches_direction:
                continue
            if edge_type is not None and edge.edge_type != edge_type:
                continue
            rows.append(edge.to_dict())
        return sorted(rows, key=lambda row: row["edge_id"])

    def snapshot(self) -> Dict[str, Any]:
        core = {
            "schema_version": "victor.world_model.v1",
            "last_sequence": self.last_sequence,
            "last_event_id": self.last_event_id,
            "nodes": [self.nodes[key].to_dict() for key in sorted(self.nodes)],
            "edges": [self.edges[key].to_dict() for key in sorted(self.edges)],
        }
        return {**core, "state_sha256": sha256_json(core)}
