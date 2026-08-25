"""Victor Regenerative Continuity (VRC-0).

VRC-0 is a cross-cutting continuity contract, not a cognitive organ and not a
second history system. It composes Victor's existing canonical primitives:

* Chronos remains the authoritative causal history.
* Model weights and derived state remain replaceable.
* A minimal identity/constitution genome anchors reconstruction.
* Cryptobiosis blocks external effects while continuity is unsafe.
* A 2-data + 1-parity recovery set tolerates loss or corruption of one shard.
* Recovery is fail-closed: identity, payload, and Chronos must independently
  verify before the runtime may return to ACTIVE.

The XOR parity codec is deliberately small and dependency-free. It proves the
reconstruction semantics for VRC-0; production multi-fault storage can replace
it with a stronger erasure code without changing the contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from trace0_chronos import ChronosLedger, canonical_json, sha256_json


class ResilienceError(RuntimeError):
    """Base class for VRC failures."""


class IntegrityError(ResilienceError):
    """Raised when supplied continuity material cannot be trusted."""


class RecoveryQuorumError(ResilienceError):
    """Raised when too few valid fragments survive to reconstruct state."""


class EffectBlockedError(ResilienceError):
    """Raised when an external effect is attempted outside ACTIVE state."""


class ResilienceState(str, Enum):
    ACTIVE = "ACTIVE"
    QUIESCING = "QUIESCING"
    CRYPTOBIOSIS = "CRYPTOBIOSIS"
    RECONSTRUCTING = "RECONSTRUCTING"
    VERIFYING = "VERIFYING"
    RECOVERED = "RECOVERED"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"


DEFAULT_INVARIANTS: Tuple[str, ...] = (
    "victor_identity_is_not_model_weights",
    "chronos_is_authoritative_causal_history",
    "derived_state_must_be_rebuildable",
    "external_effects_require_active_verified_continuity",
    "unknown_or_ambiguous_recovery_fails_closed",
    "experience_state_requires_provenance",
)


@dataclass(frozen=True)
class VictorGenome:
    """Minimal identity/constitution anchor required to recognize Victor.

    The genome intentionally contains identifiers and hashes, never private key
    material. A real deployment should keep the secret/private key in an
    independently protected identity substrate.
    """

    schema_version: str
    subject: str
    identity_algorithm: str
    identity_key_id: str
    constitution_sha256: str
    invariants: Tuple[str, ...] = DEFAULT_INVARIANTS

    @property
    def genome_id(self) -> str:
        return sha256_json(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        row = asdict(self)
        row["invariants"] = list(self.invariants)
        return row

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "VictorGenome":
        return cls(
            schema_version=str(row["schema_version"]),
            subject=str(row["subject"]),
            identity_algorithm=str(row["identity_algorithm"]),
            identity_key_id=str(row["identity_key_id"]),
            constitution_sha256=str(row["constitution_sha256"]),
            invariants=tuple(str(v) for v in row.get("invariants", DEFAULT_INVARIANTS)),
        )


@dataclass(frozen=True)
class RecoveryCapsule:
    """Canonical material needed to reconstruct a fresh runtime.

    `continuity_payload` is deliberately opaque to VRC. The Experience-Based
    Intelligence layer can place its episodic/semantic state, predictive state,
    homeostasis, learned bindings, unresolved goals, and current mission here.
    VRC preserves and authenticates the bytes without becoming cognition.
    """

    schema_version: str
    created_at: str
    genome: VictorGenome
    chronos_events: Tuple[Dict[str, Any], ...]
    chronos_receipts: Tuple[Dict[str, Any], ...]
    chronos_head_chain_hash: Optional[str]
    continuity_payload: Dict[str, Any]
    continuity_payload_sha256: str

    @property
    def capsule_id(self) -> str:
        return sha256_json(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "genome": self.genome.to_dict(),
            "chronos_events": list(self.chronos_events),
            "chronos_receipts": list(self.chronos_receipts),
            "chronos_head_chain_hash": self.chronos_head_chain_hash,
            "continuity_payload": self.continuity_payload,
            "continuity_payload_sha256": self.continuity_payload_sha256,
        }

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "RecoveryCapsule":
        return cls(
            schema_version=str(row["schema_version"]),
            created_at=str(row["created_at"]),
            genome=VictorGenome.from_dict(row["genome"]),
            chronos_events=tuple(dict(v) for v in row.get("chronos_events", [])),
            chronos_receipts=tuple(dict(v) for v in row.get("chronos_receipts", [])),
            chronos_head_chain_hash=row.get("chronos_head_chain_hash"),
            continuity_payload=dict(row.get("continuity_payload", {})),
            continuity_payload_sha256=str(row["continuity_payload_sha256"]),
        )


@dataclass(frozen=True)
class RecoveryShard:
    """One member of a VRC 2+1 recovery set."""

    schema_version: str
    set_id: str
    index: int
    role: str
    original_size: int
    shard_size: int
    payload_b64: str
    payload_sha256: str

    def payload_bytes(self) -> bytes:
        try:
            raw = base64.b64decode(self.payload_b64.encode("ascii"), validate=True)
        except Exception as exc:  # binascii.Error is implementation detail
            raise IntegrityError(f"invalid base64 in recovery shard {self.index}") from exc
        if len(raw) != self.shard_size:
            raise IntegrityError(f"recovery shard {self.index} has unexpected length")
        if hashlib.sha256(raw).hexdigest() != self.payload_sha256:
            raise IntegrityError(f"recovery shard {self.index} digest mismatch")
        return raw

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> "RecoveryShard":
        return cls(
            schema_version=str(row["schema_version"]),
            set_id=str(row["set_id"]),
            index=int(row["index"]),
            role=str(row["role"]),
            original_size=int(row["original_size"]),
            shard_size=int(row["shard_size"]),
            payload_b64=str(row["payload_b64"]),
            payload_sha256=str(row["payload_sha256"]),
        )


@dataclass(frozen=True)
class ReconstructionResult:
    capsule: RecoveryCapsule
    ledger: ChronosLedger
    used_shard_indices: Tuple[int, ...]
    reconstructed_shard_index: Optional[int]


@dataclass
class VictorRegenerativeContinuity:
    """Lifecycle gate for cryptobiosis and verified reconstruction."""

    genome: VictorGenome
    state: ResilienceState = ResilienceState.ACTIVE
    last_reason: Optional[str] = None
    transition_log: List[Tuple[str, str]] = field(default_factory=list)

    def _transition(self, new_state: ResilienceState, reason: str) -> None:
        self.state = new_state
        self.last_reason = reason
        self.transition_log.append((new_state.value, reason))

    def external_effects_allowed(self) -> bool:
        return self.state == ResilienceState.ACTIVE

    def require_external_effects_allowed(self) -> None:
        if not self.external_effects_allowed():
            raise EffectBlockedError(
                f"Victor external effects are blocked while resilience state={self.state.value}"
            )

    def enter_cryptobiosis(
        self,
        ledger: ChronosLedger,
        continuity_payload: Mapping[str, Any],
        *,
        reason: str,
        created_at: Optional[str] = None,
    ) -> Tuple[RecoveryCapsule, Tuple[RecoveryShard, ...]]:
        if self.state != ResilienceState.ACTIVE:
            raise ResilienceError(f"cannot enter cryptobiosis from {self.state.value}")
        self._transition(ResilienceState.QUIESCING, reason)
        try:
            capsule = build_capsule(
                ledger,
                self.genome,
                continuity_payload,
                created_at=created_at,
            )
            shards = encode_capsule_shards(capsule)
        except Exception:
            self._transition(ResilienceState.HALTED, "cryptobiosis capsule creation failed")
            raise
        self._transition(ResilienceState.CRYPTOBIOSIS, reason)
        return capsule, shards

    def recover(self, shards: Sequence[RecoveryShard]) -> ReconstructionResult:
        if self.state not in {
            ResilienceState.CRYPTOBIOSIS,
            ResilienceState.DEGRADED,
            ResilienceState.HALTED,
        }:
            raise ResilienceError(f"cannot recover from {self.state.value}")
        self._transition(ResilienceState.RECONSTRUCTING, "recovery initiated")
        try:
            capsule, used, reconstructed = decode_capsule_shards(shards)
            self._transition(ResilienceState.VERIFYING, "capsule reconstructed; verifying identity and Chronos")
            ledger = verify_capsule(capsule, expected_genome=self.genome)
        except Exception:
            self._transition(ResilienceState.HALTED, "recovery verification failed")
            raise
        self._transition(ResilienceState.RECOVERED, "identity, payload, and Chronos verified")
        return ReconstructionResult(
            capsule=capsule,
            ledger=ledger,
            used_shard_indices=used,
            reconstructed_shard_index=reconstructed,
        )

    def reactivate(self) -> None:
        if self.state != ResilienceState.RECOVERED:
            raise ResilienceError("reactivation requires a fully verified RECOVERED state")
        self._transition(ResilienceState.ACTIVE, "verified continuity resumed")

    def mark_degraded(self, reason: str) -> None:
        if self.state == ResilienceState.ACTIVE:
            self._transition(ResilienceState.DEGRADED, reason)
        elif self.state != ResilienceState.DEGRADED:
            raise ResilienceError(f"cannot mark degraded from {self.state.value}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_capsule(
    ledger: ChronosLedger,
    genome: VictorGenome,
    continuity_payload: Mapping[str, Any],
    *,
    created_at: Optional[str] = None,
) -> RecoveryCapsule:
    """Freeze a verified canonical head plus opaque experience/mission state."""

    if not ledger.verify_chain():
        raise IntegrityError("cannot create trusted recovery capsule from invalid Chronos chain")
    payload = dict(continuity_payload)
    payload_hash = sha256_json(payload)
    return RecoveryCapsule(
        schema_version="victor.vrc.capsule.v1",
        created_at=created_at or _utc_now(),
        genome=genome,
        chronos_events=tuple(ledger.events()),
        chronos_receipts=tuple(ledger.receipts()),
        chronos_head_chain_hash=ledger.last_chain_hash,
        continuity_payload=payload,
        continuity_payload_sha256=payload_hash,
    )


def verify_capsule(
    capsule: RecoveryCapsule,
    *,
    expected_genome: Optional[VictorGenome] = None,
) -> ChronosLedger:
    """Independently verify identity, experience payload, and causal history."""

    if capsule.schema_version != "victor.vrc.capsule.v1":
        raise IntegrityError(f"unsupported capsule schema: {capsule.schema_version}")
    if expected_genome is not None and capsule.genome.genome_id != expected_genome.genome_id:
        raise IntegrityError("Victor genome mismatch")
    if sha256_json(capsule.continuity_payload) != capsule.continuity_payload_sha256:
        raise IntegrityError("continuity payload digest mismatch")

    ledger = ChronosLedger()
    try:
        ledger.restore(capsule.chronos_events, capsule.chronos_receipts)
    except Exception as exc:
        raise IntegrityError("Chronos reconstruction failed") from exc
    if not ledger.verify_chain():
        raise IntegrityError("reconstructed Chronos chain is invalid")
    if ledger.last_chain_hash != capsule.chronos_head_chain_hash:
        raise IntegrityError("reconstructed Chronos head does not match capsule anchor")
    return ledger


def _xor_bytes(left: bytes, right: bytes) -> bytes:
    if len(left) != len(right):
        raise ValueError("xor inputs must have equal length")
    return bytes(a ^ b for a, b in zip(left, right))


def encode_capsule_shards(capsule: RecoveryCapsule) -> Tuple[RecoveryShard, RecoveryShard, RecoveryShard]:
    """Encode a capsule as two data shards plus one XOR parity shard.

    Any two valid shards reconstruct the complete capsule. This tolerates one
    missing or detectably corrupted fragment.
    """

    payload = canonical_json(capsule.to_dict()).encode("utf-8")
    original_size = len(payload)
    shard_size = max(1, (original_size + 1) // 2)
    padded = payload + (b"\x00" * ((2 * shard_size) - original_size))
    data0 = padded[:shard_size]
    data1 = padded[shard_size:]
    parity = _xor_bytes(data0, data1)
    set_id = hashlib.sha256(payload).hexdigest()

    shards: List[RecoveryShard] = []
    for index, role, raw in (
        (0, "data", data0),
        (1, "data", data1),
        (2, "parity", parity),
    ):
        shards.append(
            RecoveryShard(
                schema_version="victor.vrc.shard.v1",
                set_id=set_id,
                index=index,
                role=role,
                original_size=original_size,
                shard_size=shard_size,
                payload_b64=base64.b64encode(raw).decode("ascii"),
                payload_sha256=hashlib.sha256(raw).hexdigest(),
            )
        )
    return tuple(shards)  # type: ignore[return-value]


def _valid_shards(shards: Iterable[RecoveryShard]) -> Dict[int, Tuple[RecoveryShard, bytes]]:
    valid: Dict[int, Tuple[RecoveryShard, bytes]] = {}
    metadata: Optional[Tuple[str, int, int, str]] = None
    for shard in shards:
        if shard.index not in {0, 1, 2}:
            continue
        if shard.schema_version != "victor.vrc.shard.v1":
            continue
        current_meta = (shard.set_id, shard.original_size, shard.shard_size, shard.schema_version)
        if metadata is None:
            metadata = current_meta
        elif current_meta != metadata:
            continue
        try:
            raw = shard.payload_bytes()
        except IntegrityError:
            continue
        valid[shard.index] = (shard, raw)
    return valid


def decode_capsule_shards(
    shards: Sequence[RecoveryShard],
) -> Tuple[RecoveryCapsule, Tuple[int, ...], Optional[int]]:
    """Reconstruct and authenticate a capsule from any two valid VRC shards."""

    valid = _valid_shards(shards)
    if len(valid) < 2:
        raise RecoveryQuorumError("VRC requires any two valid shards from the same recovery set")

    sample = next(iter(valid.values()))[0]
    reconstructed_index: Optional[int] = None

    if 0 in valid and 1 in valid:
        data0 = valid[0][1]
        data1 = valid[1][1]
        used = (0, 1)
    elif 0 in valid and 2 in valid:
        data0 = valid[0][1]
        data1 = _xor_bytes(data0, valid[2][1])
        reconstructed_index = 1
        used = (0, 2)
    elif 1 in valid and 2 in valid:
        data1 = valid[1][1]
        data0 = _xor_bytes(data1, valid[2][1])
        reconstructed_index = 0
        used = (1, 2)
    else:
        raise RecoveryQuorumError("available VRC shards do not form a reconstructible quorum")

    payload = (data0 + data1)[: sample.original_size]
    if hashlib.sha256(payload).hexdigest() != sample.set_id:
        raise IntegrityError("reconstructed capsule digest does not match recovery-set identity")
    try:
        row = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("reconstructed capsule is not canonical UTF-8 JSON") from exc
    capsule = RecoveryCapsule.from_dict(row)
    if canonical_json(capsule.to_dict()).encode("utf-8") != payload:
        raise IntegrityError("reconstructed capsule is not canonical JSON")
    return capsule, used, reconstructed_index


def write_recovery_set_atomic(directory: str | os.PathLike[str], shards: Sequence[RecoveryShard]) -> Tuple[Path, ...]:
    """Persist shards atomically so interruption never leaves trusted partial files.

    This writes all provided shard files into one directory. Distribution across
    independent devices/media is a deployment responsibility; VRC does not
    pretend three files on one disk are three independent failure domains.
    """

    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for shard in shards:
        target = root / f"vrc-{shard.set_id[:16]}-{shard.index}.json"
        temp = root / f".{target.name}.tmp"
        temp.write_text(canonical_json(shard.to_dict()) + "\n", encoding="utf-8")
        os.replace(temp, target)
        written.append(target)
    return tuple(written)


def read_recovery_shard(path: str | os.PathLike[str]) -> RecoveryShard:
    row = json.loads(Path(path).read_text(encoding="utf-8"))
    return RecoveryShard.from_dict(row)
