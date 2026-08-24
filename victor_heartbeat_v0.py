"""Victor v0 canonical heartbeat integration.

This module closes the topology gap between existing TRACE-0/Chronos receipts,
the rebuildable VictorWorldModel, bounded authority, deliberative collapse, and
independently verified execution.

It intentionally does NOT claim general intelligence. The built-in perception
and interpretation stages are deterministic reference implementations. They
define stable contracts that can later be replaced by stronger local models
without moving authority, verification, or continuity out of the kernel.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from trace0_chronos import ChronosLedger, Trace0Observer, sha256_json
from victor_world_model import VictorWorldModel


MEANING_DIMENSIONS: Tuple[str, ...] = (
    "literal_surface",
    "lexical_symbolic",
    "semantic_conceptual",
    "contextual_pragmatic",
    "relational",
    "temporal",
    "causal",
    "intentional_teleological",
    "affective_valence",
    "metaphorical_analogical",
    "epistemic_evidential",
    "narrative_identity",
)

SAFE_ACTION_TYPES = frozenset({"noop", "write_text"})


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_id(prefix: str, value: Any, n: int = 32) -> str:
    return f"{prefix}:{sha256_json(value)[:n]}"


def _bounded_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, number))


def _tokens(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    current = []
    token = []
    for char in value.lower():
        if char.isalnum() or char in {"_", "-"}:
            token.append(char)
        elif token:
            current.append("".join(token))
            token = []
    if token:
        current.append("".join(token))
    return tuple(current)


@dataclass(frozen=True)
class VariableRecord:
    variable_id: str
    path: str
    value: Any
    value_type: str
    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MeaningProjection:
    dimension: str
    summary: Dict[str, Any]
    evidence_variable_ids: Tuple[str, ...]
    flags: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationRecord:
    source_variable_id: str
    target_variable_id: str
    relation_type: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateTrajectory:
    candidate_id: str
    label: str
    action: Dict[str, Any]
    expected_delta: float
    cost: float
    risk: float
    reversibility: float
    evidence_paths: Tuple[str, ...]
    unknowns: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OrchDecision:
    pass_name: str
    selected_candidate_id: Optional[str]
    ranking: Tuple[Tuple[str, float], ...]
    rejected: Tuple[Tuple[str, str], ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityLease:
    schema_version: str
    lease_id: str
    heartbeat_id: str
    action_type: str
    sandbox_root: str
    issued_at: str
    expires_at: str
    max_output_bytes: int
    allowed_relative_path: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionReceipt:
    schema_version: str
    lease_id: str
    action_type: str
    status: str
    target: Optional[str]
    sha256: Optional[str]
    size_bytes: int
    detail: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerificationReceipt:
    schema_version: str
    verified: bool
    checks: Tuple[str, ...]
    failures: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PerceptionScoutSwarm:
    """Extract variables only. No candidate action or semantic interpretation."""

    @staticmethod
    def extract(observation: Mapping[str, Any], provenance: Mapping[str, Any]) -> Tuple[VariableRecord, ...]:
        rows: List[VariableRecord] = []

        def walk(path: str, value: Any) -> None:
            if isinstance(value, Mapping):
                for key in sorted(value, key=lambda x: str(x)):
                    child = f"{path}.{key}" if path else str(key)
                    walk(child, value[key])
                return
            if isinstance(value, (list, tuple)):
                for index, child_value in enumerate(value):
                    child = f"{path}[{index}]"
                    walk(child, child_value)
                return
            row_core = {
                "path": path or "$",
                "value": value,
                "value_type": type(value).__name__,
                "provenance": dict(provenance),
            }
            rows.append(
                VariableRecord(
                    variable_id=_stable_id("var", row_core),
                    path=row_core["path"],
                    value=value,
                    value_type=row_core["value_type"],
                    provenance=row_core["provenance"],
                )
            )

        walk("", observation)
        return tuple(rows)


class MeaningInterpreterSwarm:
    """Twelve parallel deterministic projections over the same variable set."""

    def project(self, variables: Sequence[VariableRecord], context: Mapping[str, Any]) -> Tuple[MeaningProjection, ...]:
        by_path = {row.path: row for row in variables}
        all_ids = tuple(row.variable_id for row in variables)
        string_rows = [row for row in variables if isinstance(row.value, str)]
        token_map = {row.path: _tokens(row.value) for row in string_rows}
        key_tokens = {row.path: _tokens(row.path.replace(".", " ")) for row in variables}

        def matching(*needles: str) -> Tuple[VariableRecord, ...]:
            result = []
            needles_l = tuple(n.lower() for n in needles)
            for row in variables:
                hay = row.path.lower()
                if any(n in hay for n in needles_l):
                    result.append(row)
            return tuple(result)

        literal = MeaningProjection(
            "literal_surface",
            {"variable_count": len(variables), "paths": tuple(sorted(by_path))},
            all_ids,
        )
        lexical = MeaningProjection(
            "lexical_symbolic",
            {
                "tokens": tuple(sorted({token for toks in token_map.values() for token in toks})),
                "path_symbols": tuple(sorted({token for toks in key_tokens.values() for token in toks})),
            },
            tuple(row.variable_id for row in string_rows),
        )
        semantic = MeaningProjection(
            "semantic_conceptual",
            {"concept_labels": tuple(sorted({p.split(".")[-1].split("[")[0] for p in by_path}))},
            all_ids,
        )
        contextual_rows = matching("context", "environment", "source", "channel", "location")
        contextual = MeaningProjection(
            "contextual_pragmatic",
            {"context": dict(context), "explicit_context_paths": tuple(row.path for row in contextual_rows)},
            tuple(row.variable_id for row in contextual_rows),
        )
        relational_rows = matching("actor", "entity", "owner", "parent", "child", "repo", "project")
        relational = MeaningProjection(
            "relational",
            {"entity_like_paths": tuple(row.path for row in relational_rows)},
            tuple(row.variable_id for row in relational_rows),
        )
        temporal_rows = matching("time", "date", "timestamp", "before", "after", "deadline")
        temporal = MeaningProjection(
            "temporal",
            {"temporal_paths": tuple(row.path for row in temporal_rows)},
            tuple(row.variable_id for row in temporal_rows),
        )
        causal_rows = matching("cause", "because", "depends", "block", "enable", "result", "effect")
        causal = MeaningProjection(
            "causal",
            {"causal_paths": tuple(row.path for row in causal_rows)},
            tuple(row.variable_id for row in causal_rows),
        )
        intent_rows = matching("intent", "goal", "objective", "target", "want", "request")
        intentional = MeaningProjection(
            "intentional_teleological",
            {"intent_paths": tuple(row.path for row in intent_rows)},
            tuple(row.variable_id for row in intent_rows),
        )
        affective_rows = matching("valence", "emotion", "mood", "priority", "urgency", "sentiment")
        affective = MeaningProjection(
            "affective_valence",
            {"explicit_valence_paths": tuple(row.path for row in affective_rows)},
            tuple(row.variable_id for row in affective_rows),
        )
        metaphor_rows = matching("metaphor", "analogy", "resembles", "like")
        metaphorical = MeaningProjection(
            "metaphorical_analogical",
            {"explicit_analogy_paths": tuple(row.path for row in metaphor_rows)},
            tuple(row.variable_id for row in metaphor_rows),
        )
        epistemic_rows = matching("evidence", "proof", "confidence", "uncertain", "unknown", "source", "provenance")
        unknown_paths = tuple(
            row.path
            for row in variables
            if row.value is None or (isinstance(row.value, str) and row.value.strip().lower() in {"unknown", "?", "uncertain"})
        )
        epistemic = MeaningProjection(
            "epistemic_evidential",
            {"evidence_paths": tuple(row.path for row in epistemic_rows), "unknown_paths": unknown_paths},
            tuple(row.variable_id for row in epistemic_rows),
            ("contains_unknowns",) if unknown_paths else (),
        )
        narrative_rows = matching("identity", "story", "history", "mission", "project", "actor", "name")
        narrative = MeaningProjection(
            "narrative_identity",
            {"narrative_paths": tuple(row.path for row in narrative_rows)},
            tuple(row.variable_id for row in narrative_rows),
        )
        projections = (
            literal, lexical, semantic, contextual, relational, temporal, causal,
            intentional, affective, metaphorical, epistemic, narrative,
        )
        assert tuple(row.dimension for row in projections) == MEANING_DIMENSIONS
        return projections


class CrossReferencer:
    @staticmethod
    def relate(variables: Sequence[VariableRecord]) -> Tuple[RelationRecord, ...]:
        relations: List[RelationRecord] = []
        for i, left in enumerate(variables):
            left_parent = left.path.rsplit(".", 1)[0] if "." in left.path else "$"
            for right in variables[i + 1:]:
                right_parent = right.path.rsplit(".", 1)[0] if "." in right.path else "$"
                if left_parent == right_parent:
                    relations.append(RelationRecord(left.variable_id, right.variable_id, "SIBLING_VARIABLE", {"parent": left_parent}))
                if left.value is not None and left.value == right.value:
                    relations.append(RelationRecord(left.variable_id, right.variable_id, "SAME_VALUE", {"value_sha256": sha256_json(left.value)}))
        return tuple(relations[:512])


class SemanticScanner:
    @staticmethod
    def scan(variables: Sequence[VariableRecord], relations: Sequence[RelationRecord]) -> Dict[str, Any]:
        unknowns = [
            row.path for row in variables
            if row.value is None or (isinstance(row.value, str) and row.value.strip().lower() in {"unknown", "?", "uncertain"})
        ]
        contradictions = [row.path for row in variables if "contradiction" in row.path.lower() and bool(row.value)]
        repeated = sum(1 for row in relations if row.relation_type == "SAME_VALUE")
        return {
            "unknown_paths": tuple(sorted(unknowns)),
            "contradiction_paths": tuple(sorted(contradictions)),
            "relation_count": len(relations),
            "repeated_value_relation_count": repeated,
        }


class SemanticMapper:
    @staticmethod
    def graph_mutations(
        heartbeat_id: str,
        variables: Sequence[VariableRecord],
        projections: Sequence[MeaningProjection],
        relations: Sequence[RelationRecord],
    ) -> List[Dict[str, Any]]:
        mutations: List[Dict[str, Any]] = [
            {"op": "upsert_node", "node_id": heartbeat_id, "node_type": "heartbeat", "attributes": {}},
        ]
        for row in variables:
            mutations.append({
                "op": "upsert_node",
                "node_id": row.variable_id,
                "node_type": "variable",
                "attributes": {"path": row.path, "value_type": row.value_type, "value_sha256": sha256_json(row.value)},
            })
        projection_ids: Dict[str, str] = {}
        for row in projections:
            projection_id = _stable_id("meaning", {"heartbeat_id": heartbeat_id, "dimension": row.dimension})
            projection_ids[row.dimension] = projection_id
            mutations.append({
                "op": "upsert_node",
                "node_id": projection_id,
                "node_type": "meaning_projection",
                "attributes": {"dimension": row.dimension, "summary_sha256": sha256_json(row.summary), "flags": row.flags},
            })
        for row in variables:
            mutations.append({"op": "add_edge", "source": heartbeat_id, "target": row.variable_id, "edge_type": "PERCEIVES_VARIABLE", "attributes": {}})
        for projection in projections:
            projection_id = projection_ids[projection.dimension]
            mutations.append({"op": "add_edge", "source": heartbeat_id, "target": projection_id, "edge_type": "INTERPRETS_AS", "attributes": {}})
        variable_ids = {row.variable_id for row in variables}
        for rel in relations:
            if rel.source_variable_id in variable_ids and rel.target_variable_id in variable_ids:
                mutations.append({
                    "op": "add_edge",
                    "source": rel.source_variable_id,
                    "target": rel.target_variable_id,
                    "edge_type": rel.relation_type,
                    "attributes": rel.evidence,
                })
        return mutations[:2048]


class FutureField:
    @staticmethod
    def generate(candidate_actions: Optional[Sequence[Mapping[str, Any]]]) -> Tuple[CandidateTrajectory, ...]:
        source = list(candidate_actions or [{
            "label": "observe_only",
            "action": {"type": "noop"},
            "expected_delta": 0.05,
            "cost": 0.0,
            "risk": 0.0,
            "reversibility": 1.0,
            "evidence_paths": (),
            "unknowns": ("no_action_candidates_supplied",),
        }])
        candidates: List[CandidateTrajectory] = []
        for raw in source[:32]:
            action = dict(raw.get("action") or {})
            core = {
                "label": str(raw.get("label") or action.get("type") or "candidate"),
                "action": action,
                "expected_delta": _bounded_float(raw.get("expected_delta"), 0.0),
                "cost": _bounded_float(raw.get("cost"), 1.0),
                "risk": _bounded_float(raw.get("risk"), 1.0),
                "reversibility": _bounded_float(raw.get("reversibility"), 0.0),
                "evidence_paths": tuple(sorted(str(x) for x in (raw.get("evidence_paths") or ()))),
                "unknowns": tuple(sorted(str(x) for x in (raw.get("unknowns") or ()))),
            }
            candidates.append(CandidateTrajectory(candidate_id=_stable_id("candidate", core), **core))
        return tuple(candidates)


class RealityAttractorEngine:
    @staticmethod
    def score(candidate: CandidateTrajectory) -> float:
        leverage = candidate.expected_delta / (0.10 + candidate.cost)
        evidence_bonus = min(0.25, 0.05 * len(candidate.evidence_paths))
        unknown_penalty = min(0.50, 0.10 * len(candidate.unknowns))
        return round(leverage + 0.35 * candidate.reversibility + evidence_bonus - candidate.risk - unknown_penalty, 6)


class RealityLever:
    @staticmethod
    def order(candidates: Sequence[CandidateTrajectory]) -> Tuple[Tuple[str, float], ...]:
        scored = [(row.candidate_id, RealityAttractorEngine.score(row)) for row in candidates]
        return tuple(sorted(scored, key=lambda row: (-row[1], row[0])))


class OrchEngine:
    @staticmethod
    def pass1(candidates: Sequence[CandidateTrajectory]) -> OrchDecision:
        ranking = RealityLever.order(candidates)
        return OrchDecision("ORCH_1", ranking[0][0] if ranking else None, ranking, ())

    @staticmethod
    def pass2(
        candidates: Sequence[CandidateTrajectory],
        interrogation: Mapping[str, Mapping[str, Any]],
        truth: Mapping[str, str],
    ) -> OrchDecision:
        accepted: List[Tuple[str, float]] = []
        rejected: List[Tuple[str, str]] = []
        by_id = {row.candidate_id: row for row in candidates}
        for candidate_id, base_score in RealityLever.order(candidates):
            row = by_id[candidate_id]
            analysis = dict(interrogation.get(candidate_id) or {})
            truth_status = truth.get(candidate_id, "UNKNOWN")
            if truth_status == "UNKNOWN":
                rejected.append((candidate_id, "truth_unknown"))
                continue
            if analysis.get("policy_violation"):
                rejected.append((candidate_id, str(analysis["policy_violation"])))
                continue
            if row.risk > 0.50:
                rejected.append((candidate_id, "risk_above_v0_ceiling"))
                continue
            adjusted = base_score
            if truth_status == "PARTIAL":
                adjusted -= 0.20
            if analysis.get("contradiction_count", 0):
                adjusted -= min(1.0, 0.25 * int(analysis["contradiction_count"]))
            accepted.append((candidate_id, round(adjusted, 6)))
        accepted.sort(key=lambda row: (-row[1], row[0]))
        return OrchDecision("ORCH_2", accepted[0][0] if accepted else None, tuple(accepted), tuple(rejected))


class DeepInterrogator:
    @staticmethod
    def analyze(
        candidate: CandidateTrajectory,
        scan: Mapping[str, Any],
        variable_paths: Iterable[str],
    ) -> Dict[str, Any]:
        paths = set(variable_paths)
        missing_evidence = tuple(path for path in candidate.evidence_paths if path not in paths)
        action_type = str(candidate.action.get("type") or "")
        violation: Optional[str] = None
        if action_type not in SAFE_ACTION_TYPES:
            violation = f"unsupported_action_type:{action_type or 'missing'}"
        if action_type == "write_text":
            path = str(candidate.action.get("path") or "")
            pure = Path(path)
            if not path or pure.is_absolute() or ".." in pure.parts:
                violation = "unsafe_relative_path"
        return {
            "null_hypothesis": "no external change",
            "missing_evidence_paths": missing_evidence,
            "contradiction_count": len(tuple(scan.get("contradiction_paths") or ())),
            "unknown_count": len(candidate.unknowns),
            "policy_violation": violation,
            "counterfactual": "candidate_not_executed",
        }


class TruthGate:
    @staticmethod
    def compile(candidate: CandidateTrajectory, interrogation: Mapping[str, Any]) -> str:
        if interrogation.get("policy_violation"):
            return "UNKNOWN"
        if interrogation.get("missing_evidence_paths"):
            return "UNKNOWN"
        if interrogation.get("contradiction_count", 0):
            return "PARTIAL"
        if candidate.evidence_paths:
            return "SUPPORTED"
        if candidate.action.get("type") == "noop":
            return "PARTIAL"
        return "UNKNOWN"


class AgencyPlanner:
    @staticmethod
    def plan(candidate: CandidateTrajectory) -> Dict[str, Any]:
        return {
            "candidate_id": candidate.candidate_id,
            "action": dict(candidate.action),
            "preconditions": {"risk_ceiling": 0.50, "truth_required": True},
        }


class TaskCompiler:
    def __init__(self, sandbox_root: str, clock: Callable[[], datetime] = _utc_now):
        self.sandbox_root = str(Path(sandbox_root).resolve())
        self.clock = clock

    def compile(self, heartbeat_id: str, plan: Mapping[str, Any]) -> CapabilityLease:
        action = dict(plan["action"])
        action_type = str(action.get("type") or "")
        if action_type not in SAFE_ACTION_TYPES:
            raise ValueError("unsupported action type")
        relative_path: Optional[str] = None
        max_bytes = 0
        if action_type == "write_text":
            relative_path = str(action.get("path") or "")
            pure = Path(relative_path)
            if not relative_path or pure.is_absolute() or ".." in pure.parts:
                raise ValueError("unsafe relative path")
            content = str(action.get("content") or "")
            max_bytes = len(content.encode("utf-8"))
            if max_bytes > 1_000_000:
                raise ValueError("write exceeds v0 byte ceiling")
        now = self.clock().astimezone(timezone.utc)
        core = {
            "heartbeat_id": heartbeat_id,
            "action_type": action_type,
            "sandbox_root": self.sandbox_root,
            "max_output_bytes": max_bytes,
            "allowed_relative_path": relative_path,
        }
        return CapabilityLease(
            schema_version="victor.capability_lease.v0",
            lease_id=_stable_id("lease", core),
            heartbeat_id=heartbeat_id,
            action_type=action_type,
            sandbox_root=self.sandbox_root,
            issued_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=5)).isoformat(),
            max_output_bytes=max_bytes,
            allowed_relative_path=relative_path,
        )


class SandboxAetherAdapter:
    """Bounded reference Aether adapter: no network, subprocess, or arbitrary path access."""

    def __init__(self, clock: Callable[[], datetime] = _utc_now):
        self.clock = clock

    @staticmethod
    def _target(lease: CapabilityLease) -> Optional[Path]:
        if lease.allowed_relative_path is None:
            return None
        root = Path(lease.sandbox_root).resolve()
        target = (root / lease.allowed_relative_path).resolve()
        if target != root and root not in target.parents:
            raise ValueError("lease path escapes sandbox")
        return target

    def execute(self, lease: CapabilityLease, action: Mapping[str, Any]) -> ExecutionReceipt:
        now = self.clock().astimezone(timezone.utc)
        if now > datetime.fromisoformat(lease.expires_at):
            raise ValueError("capability lease expired")
        if str(action.get("type") or "") != lease.action_type:
            raise ValueError("action type does not match lease")
        if lease.action_type == "noop":
            return ExecutionReceipt("victor.execution_receipt.v0", lease.lease_id, "noop", "completed", None, None, 0, {})
        if lease.action_type != "write_text":
            raise ValueError("unsupported leased action")

        content = str(action.get("content") or "")
        encoded = content.encode("utf-8")
        if len(encoded) > lease.max_output_bytes:
            raise ValueError("output exceeds lease byte ceiling")
        target = self._target(lease)
        if target is None:
            raise ValueError("write lease missing target")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".victor.tmp")
        tmp.write_bytes(encoded)
        os.replace(tmp, target)
        digest = hashlib.sha256(encoded).hexdigest()
        return ExecutionReceipt(
            "victor.execution_receipt.v0",
            lease.lease_id,
            "write_text",
            "completed",
            str(target),
            digest,
            len(encoded),
            {"relative_path": lease.allowed_relative_path},
        )


class CompletionEngine:
    @staticmethod
    def complete(receipt: ExecutionReceipt) -> bool:
        return receipt.status == "completed"


class IndependentVerifier:
    @staticmethod
    def verify(lease: CapabilityLease, action: Mapping[str, Any], receipt: ExecutionReceipt) -> VerificationReceipt:
        checks: List[str] = []
        failures: List[str] = []
        if receipt.lease_id == lease.lease_id:
            checks.append("lease_id_matches")
        else:
            failures.append("lease_id_mismatch")
        if receipt.action_type == lease.action_type:
            checks.append("action_type_matches")
        else:
            failures.append("action_type_mismatch")
        if lease.action_type == "noop":
            checks.append("noop_has_no_target")
            if receipt.target is not None:
                failures.append("noop_target_present")
        elif lease.action_type == "write_text":
            root = Path(lease.sandbox_root).resolve()
            target = Path(receipt.target or "").resolve()
            if target == root or root in target.parents:
                checks.append("target_inside_sandbox")
            else:
                failures.append("target_outside_sandbox")
            if target.exists() and target.is_file():
                checks.append("target_exists")
                actual = target.read_bytes()
                expected = str(action.get("content") or "").encode("utf-8")
                digest = hashlib.sha256(actual).hexdigest()
                if digest == receipt.sha256 == hashlib.sha256(expected).hexdigest():
                    checks.append("content_sha256_matches")
                else:
                    failures.append("content_sha256_mismatch")
                if len(actual) == receipt.size_bytes <= lease.max_output_bytes:
                    checks.append("byte_ceiling_respected")
                else:
                    failures.append("byte_ceiling_violation")
            else:
                failures.append("target_missing")
        return VerificationReceipt("victor.verification_receipt.v0", not failures, tuple(checks), tuple(failures))


class CTP0:
    @staticmethod
    def transition(
        heartbeat_id: str,
        selected: CandidateTrajectory,
        lease: CapabilityLease,
        execution: ExecutionReceipt,
        verification: VerificationReceipt,
    ) -> Dict[str, Any]:
        core = {
            "schema_version": "victor.ctp.v0",
            "heartbeat_id": heartbeat_id,
            "candidate_id": selected.candidate_id,
            "lease": lease.to_dict(),
            "execution": execution.to_dict(),
            "verification": verification.to_dict(),
            "state_transition": "AUTHORIZED->EXECUTED->VERIFIED->CANONICAL" if verification.verified else "AUTHORIZED->EXECUTED->REJECTED",
        }
        return {**core, "transition_sha256": sha256_json(core)}


class VictorHeartbeatV0:
    def __init__(
        self,
        *,
        chronos_path: str,
        sandbox_root: str,
        clock: Callable[[], datetime] = _utc_now,
    ):
        self.clock = clock
        self.ledger = ChronosLedger(chronos_path)
        self.trace0 = Trace0Observer(self.ledger, clock=clock)
        self.world = VictorWorldModel()
        self.world.rebuild(self.ledger.events())
        self.sandbox_root = str(Path(sandbox_root).resolve())
        self.perception = PerceptionScoutSwarm()
        self.interpreters = MeaningInterpreterSwarm()
        self.aether = SandboxAetherAdapter(clock=clock)

    def _observe(self, heartbeat_id: str, stage: str, payload: Mapping[str, Any], graph_mutations: Optional[List[Dict[str, Any]]] = None) -> None:
        body = dict(payload)
        if graph_mutations:
            body["graph_mutations"] = graph_mutations
        self.trace0.observe(
            actor="victor.heartbeat.v0",
            action=stage,
            entity_id=heartbeat_id,
            payload=body,
            provenance={"component": "victor_heartbeat_v0"},
            evidence={"payload_sha256": sha256_json(payload)},
            authority="record_of_bounded_victor_authority",
        )
        self.world.sync(self.ledger.events())

    def _prior_result(self, heartbeat_id: str) -> Optional[Dict[str, Any]]:
        for event in reversed(self.ledger.events()):
            if event.get("action") != "heartbeat.completed":
                continue
            payload = event.get("payload") or {}
            if payload.get("heartbeat_id") == heartbeat_id:
                result = dict(payload.get("result") or {})
                result["status"] = "replayed"
                result["chronos_head"] = self.ledger.last_chain_hash
                result["world_state_sha256"] = self.world.snapshot()["state_sha256"]
                return result
        return None

    def run(
        self,
        *,
        observation: Mapping[str, Any],
        provenance: Optional[Mapping[str, Any]] = None,
        context: Optional[Mapping[str, Any]] = None,
        candidate_actions: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> Dict[str, Any]:
        provenance = dict(provenance or {})
        context = dict(context or {})
        heartbeat_core = {
            "observation": observation,
            "provenance": provenance,
            "context": context,
            "candidate_actions": list(candidate_actions or []),
        }
        heartbeat_id = _stable_id("heartbeat", heartbeat_core)
        prior = self._prior_result(heartbeat_id)
        if prior is not None:
            return prior

        variables = self.perception.extract(observation, provenance)
        self._observe(heartbeat_id, "heartbeat.perception", {
            "heartbeat_id": heartbeat_id,
            "variable_count": len(variables),
            "variables_sha256": sha256_json([row.to_dict() for row in variables]),
        })

        projections = self.interpreters.project(variables, context)
        self._observe(heartbeat_id, "heartbeat.interpretation", {
            "heartbeat_id": heartbeat_id,
            "dimensions": tuple(row.dimension for row in projections),
            "projections_sha256": sha256_json([row.to_dict() for row in projections]),
        })

        relations = CrossReferencer.relate(variables)
        scan = SemanticScanner.scan(variables, relations)
        mutations = SemanticMapper.graph_mutations(heartbeat_id, variables, projections, relations)
        self._observe(heartbeat_id, "heartbeat.mapping", {
            "heartbeat_id": heartbeat_id,
            "scan": scan,
            "relation_count": len(relations),
        }, mutations)

        candidates = FutureField.generate(candidate_actions)
        self._observe(heartbeat_id, "heartbeat.future_field", {
            "heartbeat_id": heartbeat_id,
            "candidate_count": len(candidates),
            "candidates": [row.to_dict() for row in candidates],
        })

        orch1 = OrchEngine.pass1(candidates)
        self._observe(heartbeat_id, "heartbeat.orch1", {"heartbeat_id": heartbeat_id, "decision": orch1.to_dict()})

        variable_paths = tuple(row.path for row in variables)
        interrogation = {
            row.candidate_id: DeepInterrogator.analyze(row, scan, variable_paths)
            for row in candidates
        }
        truth = {
            row.candidate_id: TruthGate.compile(row, interrogation[row.candidate_id])
            for row in candidates
        }
        self._observe(heartbeat_id, "heartbeat.deep_interrogation", {
            "heartbeat_id": heartbeat_id,
            "interrogation": interrogation,
            "truth": truth,
        })

        orch2 = OrchEngine.pass2(candidates, interrogation, truth)
        self._observe(heartbeat_id, "heartbeat.orch2", {"heartbeat_id": heartbeat_id, "decision": orch2.to_dict()})
        by_id = {row.candidate_id: row for row in candidates}
        selected = by_id.get(orch2.selected_candidate_id or "")
        if selected is None:
            result = {
                "schema_version": "victor.heartbeat.result.v0",
                "heartbeat_id": heartbeat_id,
                "status": "blocked",
                "reason": "no_candidate_survived_orch2",
                "variable_count": len(variables),
                "meaning_dimensions": tuple(row.dimension for row in projections),
                "orch1": orch1.to_dict(),
                "orch2": orch2.to_dict(),
                "chronos_head": self.ledger.last_chain_hash,
                "world_state_sha256": self.world.snapshot()["state_sha256"],
            }
            self._observe(heartbeat_id, "heartbeat.blocked", {"heartbeat_id": heartbeat_id, "result": result})
            result["chronos_head"] = self.ledger.last_chain_hash
            result["world_state_sha256"] = self.world.snapshot()["state_sha256"]
            return result

        plan = AgencyPlanner.plan(selected)
        compiler = TaskCompiler(self.sandbox_root, clock=self.clock)
        lease = compiler.compile(heartbeat_id, plan)
        self._observe(heartbeat_id, "heartbeat.authorized", {
            "heartbeat_id": heartbeat_id,
            "candidate_id": selected.candidate_id,
            "lease": lease.to_dict(),
        })

        execution = self.aether.execute(lease, plan["action"])
        completed = CompletionEngine.complete(execution)
        verification = IndependentVerifier.verify(lease, plan["action"], execution)
        ctp = CTP0.transition(heartbeat_id, selected, lease, execution, verification)
        self._observe(heartbeat_id, "heartbeat.execution_verified", {
            "heartbeat_id": heartbeat_id,
            "completed": completed,
            "execution": execution.to_dict(),
            "verification": verification.to_dict(),
            "ctp": ctp,
        })

        if not completed or not verification.verified:
            raise RuntimeError("bounded execution failed independent verification")

        outcome_id = _stable_id("outcome", {"heartbeat_id": heartbeat_id, "ctp": ctp["transition_sha256"]})
        final_mutations = [
            {"op": "upsert_node", "node_id": selected.candidate_id, "node_type": "candidate", "attributes": {"label": selected.label}},
            {"op": "upsert_node", "node_id": lease.lease_id, "node_type": "capability_lease", "attributes": {"action_type": lease.action_type}},
            {"op": "upsert_node", "node_id": outcome_id, "node_type": "outcome", "attributes": {"verified": True, "receipt_sha256": sha256_json(execution.to_dict())}},
            {"op": "add_edge", "source": heartbeat_id, "target": selected.candidate_id, "edge_type": "COLLAPSES_TO", "attributes": {"pass": "ORCH_2"}},
            {"op": "add_edge", "source": selected.candidate_id, "target": lease.lease_id, "edge_type": "AUTHORIZED_BY", "attributes": {}},
            {"op": "add_edge", "source": lease.lease_id, "target": outcome_id, "edge_type": "RESULTS_IN", "attributes": {"verified": True}},
        ]
        result = {
            "schema_version": "victor.heartbeat.result.v0",
            "heartbeat_id": heartbeat_id,
            "status": "completed",
            "selected_candidate_id": selected.candidate_id,
            "variable_count": len(variables),
            "meaning_dimensions": tuple(row.dimension for row in projections),
            "orch1": orch1.to_dict(),
            "orch2": orch2.to_dict(),
            "lease": lease.to_dict(),
            "execution": execution.to_dict(),
            "verification": verification.to_dict(),
            "ctp": ctp,
            "chronos_head": None,
            "world_state_sha256": None,
        }
        self._observe(heartbeat_id, "heartbeat.completed", {
            "heartbeat_id": heartbeat_id,
            "result": result,
        }, final_mutations)
        result["chronos_head"] = self.ledger.last_chain_hash
        result["world_state_sha256"] = self.world.snapshot()["state_sha256"]
        return result

    def continuity_snapshot(self) -> Dict[str, Any]:
        return {
            "chronos_valid": self.ledger.verify_chain(),
            "chronos_events": len(self.ledger.events()),
            "chronos_head": self.ledger.last_chain_hash,
            "world": self.world.snapshot(),
        }
