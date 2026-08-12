"""Local cryptographic identity proof for Victor authority events.

This uses HMAC-SHA256 with a persistent local 256-bit secret. It authenticates
that authority envelopes were produced by a runtime possessing that secret and
binds them to a Chronos parent. It is not an asymmetric/public-key lineage
scheme; that can replace this backend without changing the proof contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
from pathlib import Path
import secrets
from typing import Any, Dict, Optional

from trace0_chronos import canonical_json


@dataclass(frozen=True)
class IdentityProof:
    algorithm: str
    key_id: str
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IdentityKernel:
    ALGORITHM = "HMAC-SHA256"

    def __init__(self, key_path: Optional[str] = None, key: Optional[bytes] = None):
        if key is not None and key_path is not None:
            raise ValueError("provide key or key_path, not both")
        self.key_path = Path(key_path) if key_path else None
        if key is not None:
            self._key = bytes(key)
        elif self.key_path is not None:
            self._key = self._load_or_create(self.key_path)
        else:
            self._key = secrets.token_bytes(32)
        if len(self._key) < 32:
            raise ValueError("Victor identity key must be at least 256 bits")
        self.key_id = hashlib.sha256(self._key).hexdigest()[:32]

    @staticmethod
    def _load_or_create(path: Path) -> bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raw = path.read_bytes()
            if len(raw) < 32:
                raise ValueError("existing Victor identity key is too short")
            return raw
        raw = secrets.token_bytes(32)
        path.write_bytes(raw)
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return raw

    def sign(self, value: Dict[str, Any]) -> IdentityProof:
        message = canonical_json(value).encode("utf-8")
        signature = hmac.new(self._key, message, hashlib.sha256).hexdigest()
        return IdentityProof(self.ALGORITHM, self.key_id, signature)

    def verify(self, value: Dict[str, Any], proof: Dict[str, Any] | IdentityProof) -> bool:
        row = proof.to_dict() if isinstance(proof, IdentityProof) else dict(proof)
        if row.get("algorithm") != self.ALGORITHM or row.get("key_id") != self.key_id:
            return False
        expected = self.sign(value).signature
        supplied = str(row.get("signature", ""))
        return hmac.compare_digest(expected, supplied)
