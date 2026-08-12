"""Evidence strength and empirically calibrated confidence for Dev-Ville.

Evidence strength is a deterministic quality score. Confidence is only emitted
when enough resolved predictions exist globally *and* in the matching score bin.
This prevents arbitrary or one-sample "92% confidence" values from masquerading
as calibrated probability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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
        product = 1.0
        for value in values:
            product *= value
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
    confidence_interval_95: Optional[Tuple[float, float]]
    calibration_status: str
    calibration_samples: int
    local_bin_samples: int
    brier_score: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfidenceCalibrator:
    """Map deterministic evidence strength to observed empirical accuracy."""

    def __init__(self, min_samples: int = 20, bins: int = 10, min_bin_samples: int = 5):
        if min_samples < 1:
            raise ValueError("min_samples must be positive")
        if bins < 2:
            raise ValueError("bins must be >= 2")
        if min_bin_samples < 1:
            raise ValueError("min_bin_samples must be positive")
        self.min_samples = int(min_samples)
        self.bins = int(bins)
        self.min_bin_samples = int(min_bin_samples)
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
        """Diagnostic Brier score of raw evidence-strength predictions."""
        if not self._history:
            return None
        return sum((x.raw_score - float(x.outcome)) ** 2 for x in self._history) / len(self._history)

    @staticmethod
    def _wilson_interval(successes: int, n: int) -> Tuple[float, float]:
        if n <= 0:
            raise ValueError("Wilson interval requires n > 0")
        z = 1.959963984540054
        p = successes / n
        z2 = z * z
        denom = 1.0 + z2 / n
        center = (p + z2 / (2.0 * n)) / denom
        margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / denom
        return max(0.0, center - margin), min(1.0, center + margin)

    def evaluate(self, items: Sequence[EvidenceItem]) -> ConfidenceResult:
        raw, support, contradiction = self.evidence_strength(items)
        n = len(self._history)
        members = self._bin_members(raw)
        local_n = len(members)
        brier = self.brier_score()
        common = {
            "evidence_strength": round(raw, 6),
            "support_weight": round(support, 6),
            "contradiction_weight": round(contradiction, 6),
            "calibration_samples": n,
            "local_bin_samples": local_n,
            "brier_score": round(brier, 6) if brier is not None else None,
        }

        if n < self.min_samples:
            return ConfidenceResult(
                confidence=None,
                confidence_interval_95=None,
                calibration_status="uncalibrated",
                **common,
            )

        if local_n < self.min_bin_samples:
            return ConfidenceResult(
                confidence=None,
                confidence_interval_95=None,
                calibration_status="insufficient_local_bin",
                **common,
            )

        successes = sum(1 for x in members if x.outcome)
        empirical = successes / local_n
        low, high = self._wilson_interval(successes, local_n)
        return ConfidenceResult(
            confidence=round(empirical, 6),
            confidence_interval_95=(round(low, 6), round(high, 6)),
            calibration_status="empirically_calibrated",
            **common,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "min_samples": self.min_samples,
            "bins": self.bins,
            "min_bin_samples": self.min_bin_samples,
            "history": [asdict(x) for x in self._history],
            "brier_score": self.brier_score(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConfidenceCalibrator":
        obj = cls(
            min_samples=int(data.get("min_samples", 20)),
            bins=int(data.get("bins", 10)),
            min_bin_samples=int(data.get("min_bin_samples", 5)),
        )
        for row in data.get("history", []):
            obj.record_resolution(float(row["raw_score"]), bool(row["outcome"]))
        return obj
