"""Evidence-backed local research organ for Dev-Ville.

The organ only recommends technologies it can support with inspectable local
runtime evidence. It does not invent external benchmarks, popularity, or
confidence values. External research can later be added through an explicit
evidence-source interface without changing the result contract.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import platform
import shutil
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

from evidence_confidence import ConfidenceCalibrator, EvidenceItem


@dataclass(frozen=True)
class TechnologyProbe:
    name: str
    kind: str
    locator: str
    project_types: tuple[str, ...]


@dataclass(frozen=True)
class ResearchEvidence:
    technology: str
    source_type: str
    locator: str
    observed: str
    available: bool
    evidence_item: Dict[str, Any]


@dataclass(frozen=True)
class ResearchResult:
    project_type: str
    recommendation: Optional[str]
    alternatives: List[str]
    evidence: List[Dict[str, Any]]
    evidence_strength: float
    support_weight: float
    contradiction_weight: float
    confidence: Optional[float]
    confidence_interval_95: Optional[Tuple[float, float]]
    calibration_status: str
    calibration_samples: int
    local_bin_samples: int
    brier_score: Optional[float]
    unknowns: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_PROBES: tuple[TechnologyProbe, ...] = (
    TechnologyProbe("python-stdlib", "runtime", "python", ("general", "web_application", "api_service", "website")),
    TechnologyProbe("FastAPI", "python_module", "fastapi", ("api_service", "web_application")),
    TechnologyProbe("Flask", "python_module", "flask", ("api_service", "web_application", "website")),
    TechnologyProbe("Django", "python_module", "django", ("api_service", "web_application", "website")),
    TechnologyProbe("Node.js", "executable", "node", ("web_application", "website")),
    TechnologyProbe("npm", "executable", "npm", ("web_application", "website")),
    TechnologyProbe("git", "executable", "git", ("general", "web_application", "api_service", "website", "mobile_application")),
    TechnologyProbe("Docker", "executable", "docker", ("general", "web_application", "api_service", "website")),
    TechnologyProbe("Flutter", "executable", "flutter", ("mobile_application",)),
)


class EvidenceResearchOrgan:
    def __init__(
        self,
        calibrator: Optional[ConfidenceCalibrator] = None,
        probes: Sequence[TechnologyProbe] = DEFAULT_PROBES,
    ):
        self.calibrator = calibrator or ConfidenceCalibrator()
        self.probes = tuple(probes)

    @staticmethod
    def _probe(probe: TechnologyProbe) -> tuple[bool, str]:
        if probe.kind == "runtime":
            return True, f"Python {platform.python_version()} at {sys.executable}"
        if probe.kind == "python_module":
            spec = importlib.util.find_spec(probe.locator)
            return (spec is not None, f"module={probe.locator}; origin={getattr(spec, 'origin', None)}")
        if probe.kind == "executable":
            path = shutil.which(probe.locator)
            return (path is not None, f"executable={probe.locator}; path={path}")
        raise ValueError(f"unsupported probe kind: {probe.kind}")

    def research(self, project_type: str) -> ResearchResult:
        candidates = [p for p in self.probes if project_type in p.project_types or "general" in p.project_types]
        evidence_rows: List[ResearchEvidence] = []
        scores: Dict[str, float] = {}

        for probe in candidates:
            available, observed = self._probe(probe)
            relevance = 1.0 if project_type in probe.project_types else 0.6
            item = EvidenceItem(
                claim=f"{probe.name} is locally available for {project_type}",
                source=f"local:{probe.kind}:{probe.locator}",
                supports=available,
                source_reliability=1.0,
                directness=relevance,
                reproducibility=1.0,
                freshness=1.0,
            )
            quality = item.quality
            scores[probe.name] = quality if available else 0.0
            evidence_rows.append(
                ResearchEvidence(
                    technology=probe.name,
                    source_type=probe.kind,
                    locator=probe.locator,
                    observed=observed,
                    available=available,
                    evidence_item=asdict(item),
                )
            )

        ranked_pairs = [(name, score) for name, score in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])) if score > 0]
        ranked = [name for name, _ in ranked_pairs]
        if ranked_pairs and (len(ranked_pairs) == 1 or ranked_pairs[0][1] > ranked_pairs[1][1] + 1e-12):
            recommendation = ranked_pairs[0][0]
            alternatives = ranked[1:4]
        else:
            recommendation = None
            alternatives = ranked[:4]

        if recommendation:
            recommendation_items = [
                EvidenceItem(**row.evidence_item)
                for row in evidence_rows
                if row.technology == recommendation
            ]
            confidence = self.calibrator.evaluate(recommendation_items)
        else:
            confidence = self.calibrator.evaluate([])

        unknowns = [
            "No external benchmark, security-advisory, ecosystem-health, or performance evidence was collected.",
            "Local availability proves executability, not suitability for every requirement.",
        ]
        if recommendation is None:
            if ranked:
                unknowns.append("Available candidates are tied on collected evidence; no evidence-backed winner is claimed.")
            else:
                unknowns.append("No locally available candidate was found for this project type.")
        if confidence.confidence is None:
            unknowns.append(
                "No calibrated probability is claimed until both global and matching-bin outcome support are sufficient."
            )

        return ResearchResult(
            project_type=project_type,
            recommendation=recommendation,
            alternatives=alternatives,
            evidence=[asdict(row) for row in evidence_rows],
            evidence_strength=confidence.evidence_strength,
            support_weight=confidence.support_weight,
            contradiction_weight=confidence.contradiction_weight,
            confidence=confidence.confidence,
            confidence_interval_95=confidence.confidence_interval_95,
            calibration_status=confidence.calibration_status,
            calibration_samples=confidence.calibration_samples,
            local_bin_samples=confidence.local_bin_samples,
            brier_score=confidence.brier_score,
            unknowns=unknowns,
        )
