"""Prediction/outcome resolver connecting evidence scores to empirical learning."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from evidence_confidence import ConfidenceCalibrator
from trace0_chronos import sha256_json


@dataclass
class Prediction:
    prediction_id: str
    claim: str
    evidence_strength: float
    context: Dict[str, Any]
    outcome: Optional[bool] = None
    outcome_evidence: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OutcomeResolver:
    """Resolve prior predictions and feed real outcomes into calibration."""

    def __init__(self, calibrator: Optional[ConfidenceCalibrator] = None):
        self.calibrator = calibrator or ConfidenceCalibrator()
        self.predictions: Dict[str, Prediction] = {}

    def predict(self, claim: str, evidence_strength: float, context: Optional[Dict[str, Any]] = None) -> Prediction:
        score = float(evidence_strength)
        if not 0.0 <= score <= 1.0:
            raise ValueError("evidence_strength must be within [0, 1]")
        core = {
            "claim": str(claim),
            "evidence_strength": round(score, 6),
            "context": dict(context or {}),
        }
        prediction_id = f"prediction_{sha256_json(core)[:24]}"
        existing = self.predictions.get(prediction_id)
        if existing:
            return existing
        prediction = Prediction(
            prediction_id=prediction_id,
            claim=str(claim),
            evidence_strength=score,
            context=dict(context or {}),
        )
        self.predictions[prediction_id] = prediction
        return prediction

    def resolve(self, prediction_id: str, outcome: bool, evidence: Optional[Dict[str, Any]] = None) -> Prediction:
        prediction = self.predictions[prediction_id]
        if prediction.outcome is not None:
            if prediction.outcome != bool(outcome):
                raise ValueError("prediction already resolved with a different outcome")
            return prediction
        prediction.outcome = bool(outcome)
        prediction.outcome_evidence = dict(evidence or {})
        self.calibrator.record_resolution(prediction.evidence_strength, bool(outcome))
        return prediction

    def unresolved(self) -> List[Dict[str, Any]]:
        return [prediction.to_dict() for prediction in self.predictions.values() if prediction.outcome is None]

    def to_dict(self) -> Dict[str, Any]:
        return {"predictions": [self.predictions[key].to_dict() for key in sorted(self.predictions)]}

    def restore(self, data: Dict[str, Any]) -> None:
        self.predictions = {}
        for row in data.get("predictions", []):
            prediction = Prediction(
                prediction_id=str(row["prediction_id"]),
                claim=str(row["claim"]),
                evidence_strength=float(row["evidence_strength"]),
                context=dict(row.get("context") or {}),
                outcome=row.get("outcome"),
                outcome_evidence=(dict(row["outcome_evidence"]) if row.get("outcome_evidence") is not None else None),
            )
            self.predictions[prediction.prediction_id] = prediction
