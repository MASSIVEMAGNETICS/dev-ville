from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

from .models import RiskTier
from .scanner import DEFAULT_CANONICAL


@dataclass
class RCPConfig:
    state_dir: str = ".rcp"
    github_org: str = "MASSIVEMAGNETICS"
    canonical_repos: list[str] = field(default_factory=lambda: sorted(DEFAULT_CANONICAL))
    auto_max_risk: str = RiskTier.R1.value
    lease_minutes: int = 20
    inspect_github_root: bool = True
    publish_draft_pr: bool = False
    max_auto_cases_per_run: int = 10

    @classmethod
    def load(cls, path: str | Path | None) -> "RCPConfig":
        if path is None:
            return cls()
        candidate = Path(path)
        if not candidate.exists():
            raise FileNotFoundError(candidate)
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("RCP config must be a JSON object")
        allowed = set(cls.__dataclass_fields__)
        unknown = set(data) - allowed
        if unknown:
            raise ValueError(f"unknown RCP config keys: {sorted(unknown)}")
        config = cls(**data)
        RiskTier(config.auto_max_risk)
        if config.lease_minutes <= 0:
            raise ValueError("lease_minutes must be positive")
        if config.max_auto_cases_per_run <= 0:
            raise ValueError("max_auto_cases_per_run must be positive")
        return config

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), sort_keys=True, indent=2) + "\n", encoding="utf-8")
