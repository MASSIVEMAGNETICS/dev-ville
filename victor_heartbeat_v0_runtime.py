"""Immutable event-boundary wrapper for the Victor canonical heartbeat v0."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional

from trace0_chronos import sha256_json
from victor_heartbeat_v0 import MEANING_DIMENSIONS
from victor_heartbeat_v0 import VictorHeartbeatV0 as _ReferenceVictorHeartbeatV0


class VictorHeartbeatV0(_ReferenceVictorHeartbeatV0):
    """Canonical launch runtime with immutable TRACE-0 payload boundaries."""

    def _observe(
        self,
        heartbeat_id: str,
        stage: str,
        payload: Mapping[str, Any],
        graph_mutations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        body = copy.deepcopy(dict(payload))
        if graph_mutations:
            body["graph_mutations"] = copy.deepcopy(graph_mutations)
        evidence_payload = copy.deepcopy(dict(payload))
        self.trace0.observe(
            actor="victor.heartbeat.v0",
            action=stage,
            entity_id=heartbeat_id,
            payload=body,
            provenance={"component": "victor_heartbeat_v0_runtime"},
            evidence={"payload_sha256": sha256_json(evidence_payload)},
            authority="record_of_bounded_victor_authority",
        )
        self.world.sync(self.ledger.events())


__all__ = ["MEANING_DIMENSIONS", "VictorHeartbeatV0"]
