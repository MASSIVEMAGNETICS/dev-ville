"""TRACE-0 observation records and Chronos append-only hash-chain receipts.

TRACE-0 observes; it does not authorize or execute. Chronos records immutable,
causally linked event receipts. This module intentionally makes no claim of
cryptographic signatures: SHA-256 provides tamper evidence, not identity proof.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Informatron:
    schema_version: str
    sequence: int
    timestamp: str
    actor: str
    action: str
    entity_id: str
    payload: Dict[str, Any]
    provenance: Dict[str, Any]
    evidence: Dict[str, Any]
    authority: str
    parent_event_hash: Optional[str]
    event_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ChronosReceipt:
    sequence: int
    event_id: str
    event_hash: str
    previous_chain_hash: Optional[str]
    chain_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ChronosLedger:
    def __init__(self, jsonl_path: Optional[str] = None):
        self._events: List[Informatron] = []
        self._receipts: List[ChronosReceipt] = []
        self._lock = threading.RLock()
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None

    @property
    def last_event_hash(self) -> Optional[str]:
        return self._receipts[-1].event_hash if self._receipts else None

    @property
    def last_chain_hash(self) -> Optional[str]:
        return self._receipts[-1].chain_hash if self._receipts else None

    def append(self, event: Informatron) -> ChronosReceipt:
        with self._lock:
            expected_sequence = len(self._events) + 1
            if event.sequence != expected_sequence:
                raise ValueError(f"sequence must be {expected_sequence}, got {event.sequence}")
            if event.parent_event_hash != self.last_event_hash:
                raise ValueError("parent_event_hash does not match current Chronos head")

            event_hash = sha256_json(event.to_dict())
            receipt_core = {
                "sequence": event.sequence,
                "event_id": event.event_id,
                "event_hash": event_hash,
                "previous_chain_hash": self.last_chain_hash,
            }
            chain_hash = sha256_json(receipt_core)
            receipt = ChronosReceipt(chain_hash=chain_hash, **receipt_core)
            self._events.append(event)
            self._receipts.append(receipt)

            if self.jsonl_path:
                self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                with self.jsonl_path.open("a", encoding="utf-8") as handle:
                    handle.write(canonical_json({"event": event.to_dict(), "receipt": receipt.to_dict()}) + "\n")
            return receipt

    def verify_chain(self) -> bool:
        previous_event_hash: Optional[str] = None
        previous_chain_hash: Optional[str] = None
        for index, (event, receipt) in enumerate(zip(self._events, self._receipts), start=1):
            if event.sequence != index or receipt.sequence != index:
                return False
            if event.parent_event_hash != previous_event_hash:
                return False
            event_hash = sha256_json(event.to_dict())
            if event_hash != receipt.event_hash:
                return False
            expected_chain = sha256_json({
                "sequence": receipt.sequence,
                "event_id": receipt.event_id,
                "event_hash": receipt.event_hash,
                "previous_chain_hash": previous_chain_hash,
            })
            if expected_chain != receipt.chain_hash:
                return False
            previous_event_hash = receipt.event_hash
            previous_chain_hash = receipt.chain_hash
        return True

    def events(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    def receipts(self) -> List[Dict[str, Any]]:
        return [receipt.to_dict() for receipt in self._receipts]


class Trace0Observer:
    """Observation-only TRACE-0 emitter backed by Chronos."""

    def __init__(self, ledger: ChronosLedger, clock: Optional[Callable[[], datetime]] = None):
        self.ledger = ledger
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def observe(
        self,
        *,
        actor: str,
        action: str,
        entity_id: str,
        payload: Optional[Dict[str, Any]] = None,
        provenance: Optional[Dict[str, Any]] = None,
        evidence: Optional[Dict[str, Any]] = None,
        authority: str = "observation_only",
    ) -> tuple[Informatron, ChronosReceipt]:
        sequence = len(self.ledger.events()) + 1
        timestamp = self.clock().astimezone(timezone.utc).isoformat()
        core = {
            "schema_version": "informatron.trace0.v1",
            "sequence": sequence,
            "timestamp": timestamp,
            "actor": actor,
            "action": action,
            "entity_id": entity_id,
            "payload": payload or {},
            "provenance": provenance or {},
            "evidence": evidence or {},
            "authority": authority,
            "parent_event_hash": self.ledger.last_event_hash,
        }
        event_id = sha256_json(core)
        event = Informatron(event_id=event_id, **core)
        receipt = self.ledger.append(event)
        return event, receipt
