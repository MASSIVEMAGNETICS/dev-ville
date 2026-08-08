"""Sovereign Victor Driver: topological driver + persistent local identity proof."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from trace0_chronos import sha256_json
from victor_driver import CapabilityLease
from victor_identity_kernel import IdentityKernel
from victor_topological_driver import TopologicalVictorDriver
from victor_vehicle import DriverControlledVille


class VictorSovereignDriver(TopologicalVictorDriver):
    """Topological Victor with signed authority envelopes."""

    def __init__(
        self,
        *,
        vehicle: Optional[DriverControlledVille] = None,
        chronos_jsonl_path: Optional[str] = None,
        verification_timeout_seconds: float = 10.0,
        beta_timeout_seconds: float = 8.0,
        capability_lease: Optional[CapabilityLease] = None,
        identity_key_path: Optional[str] = None,
        identity_key: Optional[bytes] = None,
    ):
        resolved_path = identity_key_path
        if identity_key is None and resolved_path is None:
            resolved_path = os.environ.get("VICTOR_IDENTITY_KEY_PATH", "identity/victor.key")
        self.identity = IdentityKernel(key_path=resolved_path, key=identity_key)
        super().__init__(
            vehicle=vehicle,
            chronos_jsonl_path=chronos_jsonl_path,
            verification_timeout_seconds=verification_timeout_seconds,
            beta_timeout_seconds=beta_timeout_seconds,
            capability_lease=capability_lease,
        )

    def _observe(
        self,
        action: str,
        entity: str,
        payload: Dict[str, Any],
        evidence: Optional[Dict[str, Any]] = None,
        authority: str = "driver_decision",
    ) -> None:
        signed_core = {
            "actor": "victor.driver",
            "action": action,
            "entity_id": entity,
            "payload": payload,
            "authority": authority,
            "chronos_parent": self.vehicle.chronos.last_chain_hash,
        }
        proof = self.identity.sign(signed_core)
        self.vehicle.trace0.observe(
            actor="victor.driver",
            action=action,
            entity_id=entity,
            payload=payload,
            provenance={
                "source": "VictorSovereignDriver",
                "identity_proof": proof.to_dict(),
                "signed_core_sha256": sha256_json(signed_core),
            },
            evidence=evidence or {},
            authority=authority,
        )
        if hasattr(self, "topology"):
            self.topology.sync_from_chronos(self.vehicle.get_trace0_events())

    def save_project(self, filepath: str) -> None:
        super().save_project(filepath)
        path = Path(filepath)
        data = json.loads(path.read_text(encoding="utf-8"))
        core = {
            "schema_version": "victor.identity.v1",
            "algorithm": self.identity.ALGORITHM,
            "key_id": self.identity.key_id,
        }
        data["victor_identity"] = {**core, "state_sha256": sha256_json(core)}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_project(self, filepath: str) -> None:
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        saved = snapshot.get("victor_identity")
        if saved:
            core = {key: value for key, value in saved.items() if key != "state_sha256"}
            if saved.get("state_sha256") != sha256_json(core):
                raise ValueError("Victor identity snapshot hash mismatch")
            if saved.get("algorithm") != self.identity.ALGORITHM:
                raise ValueError("Victor identity algorithm mismatch")
            if saved.get("key_id") != self.identity.key_id:
                raise ValueError("Victor identity key mismatch; continuity cannot be authenticated")
        super().load_project(filepath)

    def status(self) -> Dict[str, Any]:
        state = super().status()
        state["driver"] = "VictorSovereignDriver"
        state["identity"] = {
            "algorithm": self.identity.ALGORITHM,
            "key_id": self.identity.key_id,
            "public_key_identity": False,
            "note": "Persistent local HMAC identity proof; asymmetric lineage remains a future backend.",
        }
        return state
