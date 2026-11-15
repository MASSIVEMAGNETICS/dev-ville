"""TRACE-0 observation records and Chronos append-only hash-chain receipts.

TRACE-0 observes; it does not authorize or execute. Chronos records immutable,
causally linked event receipts. SHA-256 provides tamper evidence, not actor
identity proof; signatures remain a later identity-layer concern.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence


@contextmanager
def _exclusive_append_lock(jsonl_path: Path):
    """Lock a sibling file so cooperating processes serialize JSONL appends."""
    lock_path = jsonl_path.with_name(f"{jsonl_path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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

    def identity_core(self) -> Dict[str, Any]:
        data = self.to_dict()
        data.pop("event_id", None)
        return data


@dataclass(frozen=True)
class ChronosReceipt:
    sequence: int
    event_id: str
    event_hash: str
    previous_chain_hash: Optional[str]
    chain_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StaleChronosHeadError(ValueError):
    """The event was built against a ledger head superseded by another writer."""


class ChronosLedger:
    def __init__(self, jsonl_path: Optional[str] = None):
        self._events: List[Informatron] = []
        self._receipts: List[ChronosReceipt] = []
        self._lock = threading.RLock()
        self._persistence_uncertain = False
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        self._disk_signature = None
        self._disk_head_hash = None
        if self.jsonl_path and self.jsonl_path.exists():
            with _exclusive_append_lock(self.jsonl_path):
                self._reload_from_disk_locked()

    def _current_disk_signature(self):
        if self.jsonl_path is None:
            return None
        try:
            stat = self.jsonl_path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_dev, getattr(stat, "st_ino", 0), stat.st_size, stat.st_mtime_ns)

    def _reload_from_disk_locked(self) -> None:
        """Validate a fresh disk snapshot before replacing this instance's cache."""
        assert self.jsonl_path is not None
        previous_events = self._events
        previous_receipts = self._receipts
        fresh_events: List[Informatron] = []
        fresh_receipts: List[ChronosReceipt] = []
        if self.jsonl_path.exists() and self.jsonl_path.stat().st_size:
            fresh = ChronosLedger()
            fresh.jsonl_path = self.jsonl_path
            fresh._load_jsonl()
            fresh_events = fresh._events
            fresh_receipts = fresh._receipts
        if (
            len(fresh_events) < len(previous_events)
            or fresh_events[:len(previous_events)] != previous_events
            or fresh_receipts[:len(previous_receipts)] != previous_receipts
        ):
            raise ValueError("Chronos JSONL immutable prefix changed; reconcile before append")
        self._events = fresh_events
        self._receipts = fresh_receipts
        self._disk_signature = self._current_disk_signature()
        self._disk_head_hash = self.last_chain_hash

    @property
    def last_event_hash(self) -> Optional[str]:
        return self._receipts[-1].event_hash if self._receipts else None

    @property
    def last_chain_hash(self) -> Optional[str]:
        return self._receipts[-1].chain_hash if self._receipts else None

    @staticmethod
    def _receipt_for(event: Informatron, previous_chain_hash: Optional[str]) -> ChronosReceipt:
        if event.event_id != sha256_json(event.identity_core()):
            raise ValueError("event_id does not match canonical Informatron identity core")
        event_hash = sha256_json(event.to_dict())
        receipt_core = {
            "sequence": event.sequence,
            "event_id": event.event_id,
            "event_hash": event_hash,
            "previous_chain_hash": previous_chain_hash,
        }
        return ChronosReceipt(chain_hash=sha256_json(receipt_core), **receipt_core)

    def _append(self, event: Informatron, *, persist: bool) -> ChronosReceipt:
        expected_sequence = len(self._events) + 1
        if event.sequence != expected_sequence:
            raise ValueError(f"sequence must be {expected_sequence}, got {event.sequence}")
        if event.parent_event_hash != self.last_event_hash:
            raise ValueError("parent_event_hash does not match current Chronos head")

        if persist and self._persistence_uncertain:
            raise RuntimeError("Chronos append outcome uncertain; reopen ledger before retry")

        receipt = self._receipt_for(event, self.last_chain_hash)
        if persist and self.jsonl_path:
            # Do not advance the in-memory chain until the append is flushed.
            # An I/O failure may leave a complete or partial line on disk:
            # quarantine this instance until a fresh replay reconciles it.
            try:
                self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                line = canonical_json({"event": event.to_dict(), "receipt": receipt.to_dict()}) + "\n"
                with self.jsonl_path.open("a", encoding="utf-8") as handle:
                    if handle.write(line) != len(line):
                        raise OSError("short Chronos JSONL append")
                    handle.flush()
                    os.fsync(handle.fileno())
            except BaseException:
                self._persistence_uncertain = True
                raise
        self._events.append(event)
        self._receipts.append(receipt)
        return receipt

    def append(self, event: Informatron) -> ChronosReceipt:
        with self._lock:
            if self.jsonl_path is None:
                return self._append(event, persist=True)
            if self._persistence_uncertain:
                raise RuntimeError("Chronos append outcome uncertain; reopen ledger before retry")
            with _exclusive_append_lock(self.jsonl_path):
                if self._persistence_uncertain:
                    raise RuntimeError("Chronos append outcome uncertain; reopen ledger before retry")
                try:
                    if self._current_disk_signature() != self._disk_signature:
                        self._reload_from_disk_locked()
                except Exception:
                    self._persistence_uncertain = True
                    raise
                if self.last_chain_hash != self._disk_head_hash:
                    raise RuntimeError("in-memory Chronos snapshot is not persisted; use a memory-only ledger")
                expected_sequence = len(self._events) + 1
                if event.sequence != expected_sequence:
                    raise StaleChronosHeadError(
                        f"stale Chronos append: expected sequence {expected_sequence}, got {event.sequence}"
                    )
                if event.parent_event_hash != self.last_event_hash:
                    raise StaleChronosHeadError("stale Chronos append: parent event hash changed")
                try:
                    receipt = self._append(event, persist=True)
                    self._disk_signature = self._current_disk_signature()
                    if self._disk_signature is None:
                        raise OSError("Chronos JSONL disappeared after append")
                    self._disk_head_hash = self.last_chain_hash
                    return receipt
                except BaseException:
                    self._persistence_uncertain = True
                    raise

    def _load_jsonl(self) -> None:
        assert self.jsonl_path is not None
        with self._lock:
            # A crash can leave a syntactically valid JSON object without its
            # terminating newline. Do not silently accept that ambiguous tail.
            # Likewise, blank records must not disappear from the evidence stream.
            raw = self.jsonl_path.read_bytes()
            if not raw.endswith(b"\n"):
                raise ValueError("Chronos JSONL has an unterminated record; reconcile before replay")
            for line_number, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
                if not line.strip():
                    raise ValueError(f"Chronos JSONL has an empty record at line {line_number}")
                record = json.loads(line)
                event = Informatron(**record["event"])
                expected = ChronosReceipt(**record["receipt"])
                actual = self._append(event, persist=False)
                if actual != expected:
                    raise ValueError(f"Chronos receipt mismatch at JSONL line {line_number}")
            if not self.verify_chain():
                raise ValueError("Chronos JSONL chain verification failed")

    def restore(self, events: Sequence[Dict[str, Any]], receipts: Sequence[Dict[str, Any]]) -> None:
        """Restore a saved chain snapshot into an empty ledger and verify every receipt."""
        with self._lock:
            if self._events or self._receipts:
                raise ValueError("restore requires an empty Chronos ledger")
            if len(events) != len(receipts):
                raise ValueError("event/receipt counts differ")
            for index, (event_row, receipt_row) in enumerate(zip(events, receipts), start=1):
                event = Informatron(**event_row)
                expected = ChronosReceipt(**receipt_row)
                actual = self._append(event, persist=False)
                if actual != expected:
                    raise ValueError(f"Chronos snapshot receipt mismatch at sequence {index}")
            if not self.verify_chain():
                raise ValueError("restored Chronos chain verification failed")

    def verify_chain(self) -> bool:
        previous_event_hash: Optional[str] = None
        previous_chain_hash: Optional[str] = None
        for index, (event, receipt) in enumerate(zip(self._events, self._receipts), start=1):
            if event.sequence != index or receipt.sequence != index:
                return False
            if event.parent_event_hash != previous_event_hash:
                return False
            if event.event_id != sha256_json(event.identity_core()):
                return False
            try:
                expected = self._receipt_for(event, previous_chain_hash)
            except ValueError:
                return False
            if expected != receipt:
                return False
            previous_event_hash = receipt.event_hash
            previous_chain_hash = receipt.chain_hash
        return len(self._events) == len(self._receipts)

    def events(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    def receipts(self) -> List[Dict[str, Any]]:
        return [receipt.to_dict() for receipt in self._receipts]


class Trace0Observer:
    """Observation-only TRACE-0 emitter backed by Chronos."""

    def __init__(self, ledger: ChronosLedger, clock: Optional[Callable[[], datetime]] = None):
        self.ledger = ledger
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.RLock()

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
        with self._lock:
            for attempt in range(3):
                timestamp = self.clock().astimezone(timezone.utc).isoformat()
                core = {
                    "schema_version": "informatron.trace0.v1",
                    "sequence": len(self.ledger.events()) + 1,
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
                event = Informatron(event_id=sha256_json(core), **core)
                try:
                    receipt = self.ledger.append(event)
                    return event, receipt
                except StaleChronosHeadError:
                    if attempt == 2:
                        raise
            raise RuntimeError("Chronos append retry budget exhausted")
