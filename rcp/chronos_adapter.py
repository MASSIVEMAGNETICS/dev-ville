from __future__ import annotations

from pathlib import Path
from typing import Any


class ChronosUnavailable(RuntimeError):
    pass


class RCPChronos:
    """Adapter onto the canonical Dev-Ville TRACE-0 / Chronos implementation."""

    def __init__(self, ledger_path: str | Path):
        try:
            from trace0_chronos import ChronosLedger, Trace0Observer
        except Exception as exc:  # fail closed: do not invent another ledger
            raise ChronosUnavailable(
                "canonical trace0_chronos.py is required for RCP receipts"
            ) from exc
        self.ledger = ChronosLedger(str(ledger_path))
        self.observer = Trace0Observer(self.ledger)

    def observe(
        self,
        *,
        action: str,
        entity_id: str,
        payload: dict[str, Any],
        evidence: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        authority: str = "rcp_bounded_execution",
    ) -> dict[str, Any]:
        event, receipt = self.observer.observe(
            actor="remediation-control-plane",
            action=action,
            entity_id=entity_id,
            payload=payload,
            provenance=provenance or {},
            evidence=evidence or {},
            authority=authority,
        )
        return {"event": event.to_dict(), "receipt": receipt.to_dict()}

    def observe_once(
        self,
        *,
        event_key: str,
        action: str,
        entity_id: str,
        payload: dict[str, Any],
        evidence: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        authority: str = "rcp_bounded_execution",
    ) -> dict[str, Any]:
        for event, receipt in zip(self.ledger.events(), self.ledger.receipts()):
            if (
                event.get("action") == action
                and event.get("entity_id") == entity_id
                and isinstance(event.get("payload"), dict)
                and event["payload"].get("rcp_event_key") == event_key
            ):
                return {"event": event, "receipt": receipt}
        bound_payload = dict(payload)
        bound_payload["rcp_event_key"] = event_key
        return self.observe(
            action=action,
            entity_id=entity_id,
            payload=bound_payload,
            evidence=evidence,
            provenance=provenance,
            authority=authority,
        )

    def verify(self) -> bool:
        return bool(self.ledger.verify_chain())

    def head(self) -> dict[str, Any]:
        receipts = self.ledger.receipts()
        return receipts[-1] if receipts else {}
