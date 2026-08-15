"""Chronos-backed execution wrapper for the Empire control plane.

This module closes the causal-record gap without expanding Empire mutation authority.
The existing SelfCorrectingEmpire remains responsible for assessment, allowlisted
remediation, re-verification, and the backwards-compatible sidecar receipt. This
bridge records each completed run as a sanitized TRACE-0 Informatron in the
existing Chronos hash chain and immediately reopens/verifies the persisted chain.

The manifest, sidecar, and JSONL ledger cannot be made one filesystem transaction.
Instead this wrapper enforces crash consistency by reconciling the current manifest
and latest sidecar against the latest committed Chronos event before every new run.
Any divergence fails closed and requires explicit human recovery instead of silently
continuing from ambiguous state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from empire_control_plane import ControlPlaneReceipt, SelfCorrectingEmpire
from trace0_chronos import ChronosLedger, ChronosReceipt, Informatron, Trace0Observer


DEFAULT_CHRONOS_PATH = Path("state/chronos/empire_control_plane.jsonl")
DEFAULT_RECEIPT_DIR = Path("state/empire_receipts")


@dataclass(frozen=True)
class ChronosBackedControlPlaneReceipt:
    control_plane: ControlPlaneReceipt
    event: Informatron
    chronos: ChronosReceipt
    chronos_path: str

    def to_mapping(self) -> Dict[str, Any]:
        return {
            "control_plane": self.control_plane.to_mapping(),
            "event": self.event.to_dict(),
            "chronos": self.chronos.to_dict(),
            "chronos_path": self.chronos_path,
        }


class ChronosBackedEmpire:
    """Execute the existing control plane with fail-closed Chronos reconciliation."""

    def __init__(
        self,
        manifest_path: Path | str,
        *,
        receipt_dir: Path | str = DEFAULT_RECEIPT_DIR,
        chronos_path: Path | str = DEFAULT_CHRONOS_PATH,
    ) -> None:
        self.manifest_path = Path(manifest_path)
        self.receipt_dir = Path(receipt_dir)
        self.chronos_path = Path(chronos_path)
        self.control = SelfCorrectingEmpire(self.manifest_path, receipt_dir=self.receipt_dir)

    @staticmethod
    def _hash_manifest(manifest: Dict[str, Any]) -> str:
        canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _current_manifest_hash(self) -> str:
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        if not isinstance(manifest, dict):
            raise RuntimeError("Empire manifest root must be an object")
        return self._hash_manifest(manifest)

    def _load_sidecar(self, receipt_id: str) -> Dict[str, Any]:
        sidecar_path = self.receipt_dir / f"{receipt_id}.json"
        if not sidecar_path.exists():
            raise RuntimeError(
                f"Empire/Chronos divergence: latest sidecar receipt is missing: {sidecar_path}"
            )
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Empire/Chronos divergence: latest sidecar receipt is unreadable: {sidecar_path}"
            ) from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Empire/Chronos divergence: latest sidecar receipt is not an object")
        return payload

    def assert_consistent(self, ledger: Optional[ChronosLedger] = None) -> None:
        """Fail closed when persisted Empire state diverges from the Chronos head.

        An empty/missing Chronos ledger is treated as the explicit migration/genesis
        boundary. Once the first bridge event exists, every later run must begin from
        exactly the manifest and sidecar state committed by the latest event.
        """
        if ledger is None:
            try:
                ledger = ChronosLedger(str(self.chronos_path))
            except Exception as exc:
                raise RuntimeError("Chronos replay verification failed before Empire run") from exc
        if not ledger.verify_chain():
            raise RuntimeError("Chronos chain verification failed before Empire run")

        events = ledger.events()
        if not events:
            return

        latest = events[-1]
        if latest.get("actor") != "empire_control_plane" or latest.get("action") != "control_plane_run_recorded":
            raise RuntimeError("Empire/Chronos divergence: dedicated ledger head is not a control-plane receipt")

        payload = latest.get("payload") or {}
        evidence = latest.get("evidence") or {}
        receipt_id = str(payload.get("receipt_id", "")).strip()
        expected_manifest_hash = str(evidence.get("manifest_hash_after", "")).strip()
        if not receipt_id or not expected_manifest_hash:
            raise RuntimeError("Empire/Chronos divergence: latest event is missing receipt/hash evidence")

        actual_manifest_hash = self._current_manifest_hash()
        if actual_manifest_hash != expected_manifest_hash:
            raise RuntimeError(
                "Empire/Chronos divergence: current manifest does not match the latest committed Chronos state"
            )

        sidecar = self._load_sidecar(receipt_id)
        if str(sidecar.get("receipt_id", "")) != receipt_id:
            raise RuntimeError("Empire/Chronos divergence: sidecar receipt_id does not match Chronos")
        if str(sidecar.get("manifest_hash_after", "")) != expected_manifest_hash:
            raise RuntimeError("Empire/Chronos divergence: sidecar manifest_hash_after does not match Chronos")
        expected_before = str(evidence.get("manifest_hash_before", "")).strip()
        if expected_before and str(sidecar.get("manifest_hash_before", "")) != expected_before:
            raise RuntimeError("Empire/Chronos divergence: sidecar manifest_hash_before does not match Chronos")

    def run(self, *, apply: bool = True) -> ChronosBackedControlPlaneReceipt:
        # A prior crash or out-of-band mutation must never be silently overwritten by
        # a new run. Reconcile before SelfCorrectingEmpire is allowed to mutate state.
        ledger = ChronosLedger(str(self.chronos_path))
        self.assert_consistent(ledger)

        receipt = self.control.run(apply=apply)
        sidecar_path = self.receipt_dir / f"{receipt.receipt_id}.json"
        if not sidecar_path.exists():
            raise RuntimeError("control-plane sidecar receipt missing after completed run")

        observer = Trace0Observer(ledger)
        event, chronos_receipt = observer.observe(
            actor="empire_control_plane",
            action="control_plane_run_recorded",
            entity_id="empire.topology",
            payload={
                "receipt_id": receipt.receipt_id,
                "apply": bool(apply),
                "gaps_before": receipt.gaps_before,
                "gaps_after": receipt.gaps_after,
                "unresolved_critical": receipt.unresolved_critical,
                "remediations": [asdict(item) for item in receipt.remediations],
            },
            provenance={
                "source": "SelfCorrectingEmpire.run",
                "sidecar_receipt": sidecar_path.as_posix(),
            },
            evidence={
                "manifest_hash_before": receipt.manifest_hash_before,
                "manifest_hash_after": receipt.manifest_hash_after,
            },
            authority="observation_only",
        )

        # Persistence is not considered committed until a fresh reader reconstructs
        # and independently verifies both the hash chain and cross-artifact state.
        try:
            reopened = ChronosLedger(str(self.chronos_path))
        except Exception as exc:
            raise RuntimeError("Chronos replay verification failed after Empire receipt append") from exc
        if not reopened.verify_chain():
            raise RuntimeError("Chronos chain verification failed after Empire receipt append")
        if reopened.last_chain_hash != chronos_receipt.chain_hash:
            raise RuntimeError("reopened Chronos head does not match appended Empire receipt")
        self.assert_consistent(reopened)

        return ChronosBackedControlPlaneReceipt(
            control_plane=receipt,
            event=event,
            chronos=chronos_receipt,
            chronos_path=self.chronos_path.as_posix(),
        )

    def inspect(self):
        return self.control.inspect()


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the Empire control plane and commit the completed receipt to Chronos."
    )
    parser.add_argument("--manifest", default="empire_manifest.json")
    parser.add_argument("--receipt-dir", default=str(DEFAULT_RECEIPT_DIR))
    parser.add_argument("--chronos", default=str(DEFAULT_CHRONOS_PATH))
    parser.add_argument("--check", action="store_true", help="Assess only; do not apply remediations")
    parser.add_argument("--fail-on-critical", action="store_true")
    args = parser.parse_args(argv)

    bridge = ChronosBackedEmpire(
        args.manifest,
        receipt_dir=args.receipt_dir,
        chronos_path=args.chronos,
    )
    result = bridge.run(apply=not args.check)
    gaps = bridge.inspect()
    print(json.dumps({
        "receipt": result.to_mapping(),
        "remaining_gaps": [asdict(gap) for gap in gaps],
    }, indent=2, default=str))
    if args.fail_on_critical and result.control_plane.unresolved_critical:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
