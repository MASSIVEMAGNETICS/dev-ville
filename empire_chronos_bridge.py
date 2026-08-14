"""Chronos-backed execution wrapper for the Empire control plane.

This module closes the causal-record gap without expanding Empire mutation authority.
The existing SelfCorrectingEmpire remains responsible for assessment, allowlisted
remediation, re-verification, and the backwards-compatible sidecar receipt. This
bridge records each completed run as a sanitized TRACE-0 Informatron in the
existing Chronos hash chain and immediately reopens/verifies the persisted chain.

Important boundary: if Chronos append or replay verification fails, this wrapper
raises and must not be reported as a fully committed run. The sidecar receipt and
manifest may already exist because cross-file atomicity is not claimed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
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
    """Execute the existing control plane, then commit its receipt to Chronos."""

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

    def run(self, *, apply: bool = True) -> ChronosBackedControlPlaneReceipt:
        receipt = self.control.run(apply=apply)
        sidecar_path = self.receipt_dir / f"{receipt.receipt_id}.json"
        if not sidecar_path.exists():
            raise RuntimeError("control-plane sidecar receipt missing after completed run")

        ledger = ChronosLedger(str(self.chronos_path))
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
        # and independently verifies the complete hash chain.
        try:
            reopened = ChronosLedger(str(self.chronos_path))
        except Exception as exc:  # preserve fail-closed semantics at the bridge boundary
            raise RuntimeError("Chronos replay verification failed after Empire receipt append") from exc
        if not reopened.verify_chain():
            raise RuntimeError("Chronos chain verification failed after Empire receipt append")
        if reopened.last_chain_hash != chronos_receipt.chain_hash:
            raise RuntimeError("reopened Chronos head does not match appended Empire receipt")

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
