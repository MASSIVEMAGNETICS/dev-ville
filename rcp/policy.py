from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from pathlib import Path, PurePosixPath
import secrets
from typing import Iterable, Optional

from .models import CapabilityLease, RemediationCase, RiskTier, canonical_json, sha256_json


class PolicyDenied(PermissionError):
    pass


def _safe_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    candidate = PurePosixPath(normalized)
    if not normalized or candidate.is_absolute() or ".." in candidate.parts:
        raise PolicyDenied(f"unsafe repository path: {path!r}")
    return candidate.as_posix()


class PolicyGate:
    """Fail-closed capability lease issuer.

    Auto authorization stops at R1 and only for explicitly remediable recipes.
    R2/R3 requires an explicit human-approved call. R3 still cannot gain any
    capability that the repair worker does not implement.
    """

    def __init__(self, state_dir: str | Path, *, lease_minutes: int = 20, auto_max_risk: RiskTier = RiskTier.R1):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.lease_minutes = max(1, int(lease_minutes))
        self.auto_max_risk = auto_max_risk
        self.key_path = self.state_dir / "lease.key"
        self._key = self._load_or_create_key()

    def _load_or_create_key(self) -> bytes:
        env_key = os.environ.get("RCP_LEASE_KEY")
        if env_key:
            return hashlib.sha256(env_key.encode("utf-8")).digest()
        if self.key_path.exists():
            data = self.key_path.read_bytes().strip()
            if len(data) < 32:
                raise PolicyDenied(f"lease key at {self.key_path} is too short")
            return data
        data = secrets.token_bytes(32)
        self.key_path.write_bytes(data)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return data

    def _sign(self, payload: dict) -> str:
        return hmac.new(self._key, canonical_json(payload).encode("utf-8"), hashlib.sha256).hexdigest()

    def issue(self, case: RemediationCase, *, human_approved: bool = False, now: Optional[datetime] = None) -> CapabilityLease:
        if not case.remediable or not case.recipe:
            raise PolicyDenied("case has no bounded repair recipe")
        if not human_approved and case.risk.rank > self.auto_max_risk.rank:
            raise PolicyDenied(f"{case.risk.value} exceeds autonomous authorization ceiling {self.auto_max_risk.value}")
        allowed_paths = tuple(_safe_repo_path(path) for path in case.required_paths)
        if not allowed_paths:
            raise PolicyDenied("lease cannot be issued without explicit allowed paths")
        issued = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expires = issued + timedelta(minutes=self.lease_minutes)
        core = {
            "case_id": case.case_id,
            "repository_full_name": case.repository_full_name,
            "base_sha": case.head_sha,
            "risk": case.risk.value,
            "issued_at": issued.isoformat(),
            "expires_at": expires.isoformat(),
            "allowed_paths": list(allowed_paths),
            "allowed_operations": ["write"],
            "issuer": "authorized_human_owner" if human_approved else "rcp.policy.v1:auto",
        }
        lease_id = "LEASE-" + sha256_json(core)[:24]
        unsigned = {"lease_id": lease_id, **core}
        signature = self._sign(unsigned)
        return CapabilityLease(
            lease_id=lease_id,
            case_id=case.case_id,
            repository_full_name=case.repository_full_name,
            base_sha=case.head_sha,
            risk=case.risk,
            issued_at=core["issued_at"],
            expires_at=core["expires_at"],
            allowed_paths=allowed_paths,
            allowed_operations=("write",),
            issuer=core["issuer"],
            signature=signature,
        )

    def verify(self, lease: CapabilityLease, *, case: Optional[RemediationCase] = None, now: Optional[datetime] = None) -> None:
        expected = self._sign(lease.unsigned_dict())
        if not hmac.compare_digest(expected, lease.signature):
            raise PolicyDenied("lease signature verification failed")
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expires = datetime.fromisoformat(lease.expires_at).astimezone(timezone.utc)
        if current >= expires:
            raise PolicyDenied("lease expired")
        if case is not None:
            if lease.case_id != case.case_id:
                raise PolicyDenied("lease case mismatch")
            if lease.repository_full_name != case.repository_full_name:
                raise PolicyDenied("lease repository mismatch")
            if lease.base_sha != case.head_sha:
                raise PolicyDenied("lease base SHA mismatch")
        for path in lease.allowed_paths:
            _safe_repo_path(path)
        if set(lease.allowed_operations) - {"write"}:
            raise PolicyDenied("lease contains unsupported operations")

    def authorize_operation(self, lease: CapabilityLease, *, op: str, path: str) -> None:
        self.verify(lease)
        safe = _safe_repo_path(path)
        if op not in lease.allowed_operations:
            raise PolicyDenied(f"operation {op!r} is not leased")
        if safe not in set(lease.allowed_paths):
            raise PolicyDenied(f"path {safe!r} is outside lease scope")
