"""Machine-enforced constitutional invariants for the Bando-Victor Empire.

This module protects the empire's continuity identity and the provenance of its
Genesis Capital. Operational priorities and balances may change; the empire
identity and genesis event may not be silently rewritten.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


CANONICAL_EMPIRE_ID = "bando-victor-empire"
CANONICAL_GENESIS_SOURCE = "UnitedMasters"
CANONICAL_GENESIS_CURRENCY = "USD"
CANONICAL_USER_DESIGNATED_GENESIS_CENTS = 3000
CANONICAL_GENESIS_EVENT_ID = "empire-genesis-capital-0001"


class ConstitutionViolation(ValueError):
    """Raised when an immutable empire invariant is violated."""


def _load_json(path: Path | str) -> Dict[str, Any]:
    candidate = Path(path)
    with candidate.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ConstitutionViolation(f"{candidate} must contain a JSON object")
    return payload


def validate_constitution(
    constitution: Mapping[str, Any],
    genesis: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    if constitution.get("empire_id") != CANONICAL_EMPIRE_ID:
        raise ConstitutionViolation("empire identity may not be changed")

    continuity = constitution.get("continuity")
    if not isinstance(continuity, Mapping):
        raise ConstitutionViolation("constitution.continuity is required")
    required_continuity = {
        "immutable": True,
        "termination_permitted": False,
        "abandonment_permitted": False,
        "mission_may_be_deleted": False,
    }
    for key, expected in required_continuity.items():
        if continuity.get(key) is not expected:
            raise ConstitutionViolation(f"continuity invariant violated: {key} must be {expected!r}")

    genesis_policy = constitution.get("genesis_capital")
    if not isinstance(genesis_policy, Mapping):
        raise ConstitutionViolation("constitution.genesis_capital is required")
    if genesis_policy.get("source") != CANONICAL_GENESIS_SOURCE:
        raise ConstitutionViolation("Genesis Capital source may not be rewritten")
    if genesis_policy.get("currency") != CANONICAL_GENESIS_CURRENCY:
        raise ConstitutionViolation("Genesis Capital currency may not be rewritten")
    if genesis_policy.get("user_designated_amount_cents") != CANONICAL_USER_DESIGNATED_GENESIS_CENTS:
        raise ConstitutionViolation("Genesis Capital designation may not be rewritten")
    if genesis_policy.get("classification") != "receivable":
        raise ConstitutionViolation("Genesis Capital must remain a receivable until payout evidence changes its accounting state")
    if genesis_policy.get("provenance_immutable") is not True:
        raise ConstitutionViolation("Genesis Capital provenance must be immutable")
    if genesis_policy.get("balance_mutable") is not True:
        raise ConstitutionViolation("Genesis Capital balance must remain deployable and therefore mutable")

    if genesis.get("event_id") != CANONICAL_GENESIS_EVENT_ID:
        raise ConstitutionViolation("Genesis Capital event identity may not be rewritten")
    if genesis.get("empire_id") != CANONICAL_EMPIRE_ID:
        raise ConstitutionViolation("Genesis Capital must remain bound to the canonical empire")
    asset = genesis.get("asset")
    if not isinstance(asset, Mapping):
        raise ConstitutionViolation("genesis asset record is required")
    if asset.get("source") != CANONICAL_GENESIS_SOURCE:
        raise ConstitutionViolation("genesis asset source mismatch")
    if asset.get("currency") != CANONICAL_GENESIS_CURRENCY:
        raise ConstitutionViolation("genesis asset currency mismatch")
    if asset.get("user_designated_amount_cents") != CANONICAL_USER_DESIGNATED_GENESIS_CENTS:
        raise ConstitutionViolation("genesis asset amount mismatch")
    if asset.get("classification") != "receivable":
        raise ConstitutionViolation("genesis asset classification mismatch")

    governance = genesis.get("governance")
    if not isinstance(governance, Mapping):
        raise ConstitutionViolation("genesis governance record is required")
    if governance.get("role") != "Genesis Capital":
        raise ConstitutionViolation("genesis economic role may not be rewritten")
    if governance.get("provenance_may_be_deleted") is not False:
        raise ConstitutionViolation("genesis provenance deletion must remain forbidden")
    if governance.get("principal_may_be_deployed") is not True:
        raise ConstitutionViolation("genesis principal must remain deployable through governed execution")

    nodes = manifest.get("nodes")
    if not isinstance(nodes, list):
        raise ConstitutionViolation("manifest.nodes must be a list")
    node_by_id = {
        str(node.get("id")): node
        for node in nodes
        if isinstance(node, Mapping) and node.get("id")
    }
    constitution_node = node_by_id.get("empire.constitution")
    if not isinstance(constitution_node, Mapping):
        raise ConstitutionViolation("manifest must contain empire.constitution")
    if constitution_node.get("status") != "active" or constitution_node.get("canonical") is not True:
        raise ConstitutionViolation("empire.constitution must remain active and canonical")
    constitution_meta = constitution_node.get("metadata")
    if not isinstance(constitution_meta, Mapping) or constitution_meta.get("immutable") is not True:
        raise ConstitutionViolation("empire.constitution must remain immutable")

    capital_node = node_by_id.get("capital.genesis")
    if not isinstance(capital_node, Mapping):
        raise ConstitutionViolation("manifest must contain capital.genesis")
    if capital_node.get("status") != "active" or capital_node.get("canonical") is not True:
        raise ConstitutionViolation("capital.genesis must remain active and canonical")
    capital_meta = capital_node.get("metadata")
    if not isinstance(capital_meta, Mapping):
        raise ConstitutionViolation("capital.genesis metadata is required")
    if capital_meta.get("source") != CANONICAL_GENESIS_SOURCE:
        raise ConstitutionViolation("manifest Genesis Capital source mismatch")
    if capital_meta.get("user_designated_amount_cents") != CANONICAL_USER_DESIGNATED_GENESIS_CENTS:
        raise ConstitutionViolation("manifest Genesis Capital amount mismatch")
    if capital_meta.get("provenance_immutable") is not True:
        raise ConstitutionViolation("manifest must preserve Genesis Capital provenance")


def validate_files(
    constitution_path: Path | str = "empire_constitution.json",
    genesis_path: Path | str = "empire_genesis_capital.json",
    manifest_path: Path | str = "empire_manifest.json",
) -> None:
    validate_constitution(
        _load_json(constitution_path),
        _load_json(genesis_path),
        _load_json(manifest_path),
    )


def main() -> int:
    validate_files()
    print("Empire constitution: VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
