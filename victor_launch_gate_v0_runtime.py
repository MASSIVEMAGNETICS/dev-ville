"""Immutable event-boundary wrapper for the strict Victor launch gate v0."""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Mapping, Optional

from trace0_chronos import sha256_json
from victor_launch_gate_v0 import (
    TRUTH_COMPILER_COMMIT,
    TRUTH_COMPILER_FILE_SHA256,
    TRUTH_COMPILER_REPOSITORY,
    TRUTH_COMPILER_SCHEMA,
    RecoveryExplainer,
    TruthCompilerBridge,
    VictorLaunchGateV0 as _ReferenceVictorLaunchGateV0,
)


class VictorLaunchGateV0(_ReferenceVictorLaunchGateV0):
    """Strict launch runtime with immutable TRACE-0 payload boundaries."""

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
            actor="victor.launch_gate.v0",
            action=stage,
            entity_id=heartbeat_id,
            payload=body,
            provenance={
                "component": "victor_launch_gate_v0_runtime",
                "truth_compiler_repository": TRUTH_COMPILER_REPOSITORY,
                "truth_compiler_commit": TRUTH_COMPILER_COMMIT,
                "truth_compiler_file_sha256": TRUTH_COMPILER_FILE_SHA256,
            },
            evidence={"payload_sha256": sha256_json(evidence_payload)},
            authority="record_of_bounded_victor_authority",
        )
        self.world.sync(self.ledger.events())


__all__ = [
    "TRUTH_COMPILER_COMMIT",
    "TRUTH_COMPILER_FILE_SHA256",
    "TRUTH_COMPILER_REPOSITORY",
    "TRUTH_COMPILER_SCHEMA",
    "RecoveryExplainer",
    "TruthCompilerBridge",
    "VictorLaunchGateV0",
]
