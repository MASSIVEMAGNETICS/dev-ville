"""Evidence strength and empirically calibrated confidence for Dev-Ville.

Evidence strength is a deterministic quality score. Confidence is only emitted
when enough resolved predictions exist to empirically calibrate that score.
This prevents arbitrary "92% confidence" values from masquerading as truth.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class EvidenceItem:
    claim: str
    source: str
    supports: bool
    source_reliability: float
    directness: float
    reproducibility: float
    freshness: float = 1.0

    def __post_init__(self) -> None:
        for name in ("source_reliability", "directness", "reproducibility", "freshness"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1]")

    @property
    def quality(self) -> float:
        values = (
            self.source_reliability,
            self.directness,
            self.reproducibility,
            self.freshness,
        )
        product = math.prod(values)
        return product ** (1.0 / len(values)) if product > 0 else 0.0


@dataclass(frozen=True)
class CalibrationObservation:
    raw_score: float
    outcome: bool


@dataclass(frozen=True)
class ConfidenceResult:
    evidence_strength: float
    support_weight: float
    contradiction_weight: float
    confidence: Optional[float]
    calibration_status: str
    calibration_samples: int
    brier_score: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfidenceCalibrator:
    """Map deterministic evidence strength to observed empirical accuracy."""

    def __init__(self, min_samples: int = 20, bins: int = 10):
        if min_samples < 1:
            raise ValueError("min_samples must be positive")
        if bins < 2:
            raise ValueError("bins must be >= 2")
        self.min_samples = min_samples
        self.bins = bins
        self._history: List[CalibrationObservation] = []

    @staticmethod
    def evidence_strength(items: Sequence[EvidenceItem]) -> tuple[float, float, float]:
        if not items:
            return 0.0, 0.0, 0.0
        support = sum(item.quality for item in items if item.supports)
        contradiction = sum(item.quality for item in items if not item.supports)
        total = support + contradiction
        if total <= 0:
            return 0.0, support, contradiction
        strength = support / total
        return strength, support, contradiction

    def record_resolution(self, raw_score: float, outcome: bool) -> None:
        if not 0.0 <= raw_score <= 1.0:
            raise ValueError("raw_score must be within [0, 1]")
        self._history.append(CalibrationObservation(float(raw_score), bool(outcome)))

    def extend_resolutions(self, observations: Iterable[CalibrationObservation]) -> None:
        for observation in observations:
            self.record_resolution(observation.raw_score, observation.outcome)

    def _bin_members(self, score: float) -> List[CalibrationObservation]:
        index = min(self.bins - 1, int(score * self.bins))
        low = index / self.bins
        high = (index + 1) / self.bins
        if index == self.bins - 1:
            return [x for x in self._history if low <= x.raw_score <= high]
        return [x for x in self._history if low <= x.raw_score < high]

    def brier_score(self) -> Optional[float]:
        if not self._history:
            return None
        return sum((x.raw_score - float(x.outcome)) ** 2 for x in self._history) / len(self._history)

    def evaluate(self, items: Sequence[EvidenceItem]) -> ConfidenceResult:
        raw, support, contradiction = self.evidence_strength(items)
        n = len(self._history)
        if n < self.min_samples:
            return ConfidenceResult(
                evidence_strength=round(raw, 6),
                support_weight=round(support, 6),
                contradiction_weight=round(contradiction, 6),
                confidence=None,
                calibration_status="uncalibrated",
                calibration_samples=n,
                brier_score=self.brier_score(),
            )

        members = self._bin_members(raw)
        if not members:
            return ConfidenceResult(
                evidence_strength=round(raw, 6),
                support_weight=round(support, 6),
                contradiction_weight=round(contradiction, 6),
                confidence=None,
                calibration_status="insufficient_local_bin",
                calibration_samples=n,
                brier_score=round(self.brier_score() or 0.0, 6),
            )

        empirical = sum(float(x.outcome) for x in members) / len(members)
        return ConfidenceResult(
            evidence_strength=round(raw, 6),
            support_weight=round(support, 6),
            contradiction_weight=round(contradiction, 6),
            confidence=round(empirical, 6),
            calibration_status="empirically_calibrated",
            calibration_samples=n,
            brier_score=round(self.brier_score() or 0.0, 6),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_samples": self.min_samples,
            "bins": self.bins,
            "history": [asdict(x) for x in self._history],
            "brier_score": self.brier_score(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfidenceCalibrator":
        obj = cls(min_samples=int(data.get("min_samples", 20)), bins=int(data.get("bins", 10)))
        for row in data.get("history", []):
            obj.record_resolution(float(row["raw_score"]), bool(row["outcome"]))
        return obj
