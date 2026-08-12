"""Bounded empirical learning for Victor route policy.

Learning never invents a probability from one outcome. A route preference is
only exposed after a minimum number of resolved outcomes and is used by the
Choice Kernel only as a tie-breaker after present-time feasibility/utility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class RouteLearningRecord:
    route_class: str
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    last_evidence_sha256: Optional[str] = None

    @property
    def empirical_success_rate(self) -> Optional[float]:
        if self.attempts <= 0:
            return None
        return self.successes / self.attempts

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["empirical_success_rate"] = (
            round(self.empirical_success_rate, 6)
            if self.empirical_success_rate is not None
            else None
        )
        return data


class LearningEdgeUpdater:
    def __init__(self, min_samples: int = 5):
        if min_samples < 1:
            raise ValueError("min_samples must be positive")
        self.min_samples = int(min_samples)
        self.records: Dict[str, RouteLearningRecord] = {}

    def record(self, route_class: str, outcome: bool, evidence_sha256: Optional[str] = None) -> RouteLearningRecord:
        key = str(route_class)
        row = self.records.setdefault(key, RouteLearningRecord(route_class=key))
        row.attempts += 1
        if outcome:
            row.successes += 1
        else:
            row.failures += 1
        row.last_evidence_sha256 = evidence_sha256
        return row

    def preference(self, route_class: str) -> Optional[float]:
        row = self.records.get(str(route_class))
        if row is None or row.attempts < self.min_samples:
            return None
        return row.empirical_success_rate

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_samples": self.min_samples,
            "records": {key: self.records[key].to_dict() for key in sorted(self.records)},
        }

    def restore(self, data: Dict[str, Any]) -> None:
        self.min_samples = int(data.get("min_samples", self.min_samples))
        self.records = {}
        for key, row in (data.get("records") or {}).items():
            self.records[str(key)] = RouteLearningRecord(
                route_class=str(row.get("route_class", key)),
                attempts=int(row.get("attempts", 0)),
                successes=int(row.get("successes", 0)),
                failures=int(row.get("failures", 0)),
                last_evidence_sha256=row.get("last_evidence_sha256"),
            )
