"""Victor strict v0 launch-gate integration.

Composes the existing canonical heartbeat with a hash-pinned external Truth
Compiler and a recovery explainer whose only inputs are Chronos and the rebuilt
world graph. It does not create a second sovereign Victor kernel.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from trace0_chronos import sha256_json
from victor_heartbeat_v0 import (
    AgencyPlanner,
    CTP0,
    CompletionEngine,
    CrossReferencer,
    DeepInterrogator,
    FutureField,
    IndependentVerifier,
    MeaningInterpreterSwarm,
    OrchEngine,
    PerceptionScoutSwarm,
    RealityLever,
    SemanticMapper,
    SemanticScanner,
    TaskCompiler,
    VictorHeartbeatV0,
    _stable_id,
    _utc_now,
)

TRUTH_COMPILER_REPOSITORY = "MASSIVEMAGNETICS/truth-compiler-ai"
TRUTH_COMPILER_COMMIT = "f06ff18698176d1ae6c83a2fd78dc8a75ec246ea"
TRUTH_COMPILER_FILE_SHA256 = "ea7404bf3f785986b1099ac050048be54abf6a2f3d566d76749e9521b4cac94e"
TRUTH_COMPILER_SCHEMA = "truth.compiler.contract.v1"


class TruthCompilerBridge:
    """Invoke the exact external Truth Compiler artifact selected by the launch gate."""

    def __init__(self, script_path: str, *, timeout_seconds: float = 5.0):
        self.script_path = Path(script_path).resolve()
        self.timeout_seconds = float(timeout_seconds)
        if not self.script_path.exists() or not self.script_path.is_file():
            raise ValueError(f"Truth Compiler script not found: {self.script_path}")
        actual = hashlib.sha256(self.script_path.read_bytes()).hexdigest()
        if actual != TRUTH_COMPILER_FILE_SHA256:
            raise ValueError(
                "Truth Compiler file hash mismatch: "
                f"expected {TRUTH_COMPILER_FILE_SHA256}, got {actual}"
            )

    @property
    def identity(self) -> Dict[str, Any]:
        return {
            "repository": TRUTH_COMPILER_REPOSITORY,
            "source_commit": TRUTH_COMPILER_COMMIT,
            "contract_schema": TRUTH_COMPILER_SCHEMA,
            "file_sha256": TRUTH_COMPILER_FILE_SHA256,
        }

    @staticmethod
    def _prov(value: Any) -> Dict[str, str]:
        return {"sha256": sha256_json(value)}

    def _request(
        self,
        *,
        heartbeat_id: str,
        candidate: Any,
        interrogation: Mapping[str, Any],
        variables: Sequence[Any],
    ) -> Dict[str, Any]:
        by_path = {row.path: row for row in variables}
        evidence: List[Dict[str, Any]] = []
        required_facts: List[str] = []

        for path in candidate.evidence_paths:
            fact_key = str(path).rsplit(".", 1)[-1]
            required_facts.append(fact_key)
            row = by_path.get(path)
            if row is None:
                core = {"heartbeat_id": heartbeat_id, "path": path, "missing": True}
                evidence.append({
                    "evidence_id": _stable_id("evidence", core),
                    "status": "UNKNOWN",
                    "source": "victor.perception",
                    "independence_group": "missing-observation",
                    "provenance": self._prov(core),
                    "facts": {},
                })
                continue

            if row.value is None:
                status = "UNKNOWN"
            elif row.value is False:
                status = "CONTRADICTED"
            else:
                status = "SUPPORTED"
            core = {
                "variable_id": row.variable_id,
                "path": row.path,
                "value": row.value,
                "provenance": row.provenance,
            }
            evidence.append({
                "evidence_id": _stable_id("evidence", core),
                "status": status,
                "source": "victor.perception",
                # Same originating percept/provenance is one evidence group even
                # when multiple semantic projections refer to it.
                "independence_group": "observation:" + sha256_json(row.provenance)[:24],
                "provenance": self._prov(core),
                "facts": {fact_key: row.value},
            })

        for unknown in candidate.unknowns:
            core = {
                "heartbeat_id": heartbeat_id,
                "candidate_id": candidate.candidate_id,
                "unknown": unknown,
            }
            evidence.append({
                "evidence_id": _stable_id("evidence", core),
                "status": "UNKNOWN",
                "source": "victor.candidate",
                "independence_group": "candidate-declared-unknowns",
                "provenance": self._prov(core),
                "facts": {},
            })

        contradiction_count = int(interrogation.get("contradiction_count", 0) or 0)
        if contradiction_count:
            core = {
                "heartbeat_id": heartbeat_id,
                "candidate_id": candidate.candidate_id,
                "contradiction_count": contradiction_count,
            }
            evidence.append({
                "evidence_id": _stable_id("evidence", core),
                "status": "CONTRADICTED",
                "source": "victor.semantic_scan",
                "independence_group": "semantic-scan-contradictions",
                "provenance": self._prov(core),
                "facts": {},
            })

        return {
            "schema_version": TRUTH_COMPILER_SCHEMA,
            "claim_id": candidate.candidate_id,
            "claim": {
                "type": "victor_candidate_action",
                "action": dict(candidate.action),
                "expected_delta": candidate.expected_delta,
                "risk": candidate.risk,
                "reversibility": candidate.reversibility,
            },
            "evidence": evidence,
            "policy": {
                "authority_allowed": not bool(interrogation.get("policy_violation")),
                "min_independent_support": 1,
                "max_contradictions": 0,
                "required_fact_keys": sorted(set(required_facts)),
            },
        }

    def compile_candidate(
        self,
        *,
        heartbeat_id: str,
        candidate: Any,
        interrogation: Mapping[str, Any],
        variables: Sequence[Any],
    ) -> Dict[str, Any]:
        request = self._request(
            heartbeat_id=heartbeat_id,
            candidate=candidate,
            interrogation=interrogation,
            variables=variables,
        )
        try:
            proc = subprocess.run(
                [sys.executable, str(self.script_path)],
                input=json.dumps(request, sort_keys=True),
                text=True,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
                cwd=str(self.script_path.parent),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "schema_version": TRUTH_COMPILER_SCHEMA,
                "claim_id": candidate.candidate_id,
                "verdict": "UNKNOWN",
                "bridge_error": type(exc).__name__,
                "message": str(exc),
                "compiler_identity": self.identity,
            }
        try:
            row = json.loads(proc.stdout)
        except json.JSONDecodeError:
            row = {
                "schema_version": TRUTH_COMPILER_SCHEMA,
                "claim_id": candidate.candidate_id,
                "verdict": "UNKNOWN",
                "bridge_error": "invalid_json",
                "message": proc.stdout[-1000:],
            }
        if proc.returncode != 0:
            row["verdict"] = "UNKNOWN"
            row["bridge_returncode"] = proc.returncode
        if row.get("schema_version") != TRUTH_COMPILER_SCHEMA:
            row = {
                "schema_version": TRUTH_COMPILER_SCHEMA,
                "claim_id": candidate.candidate_id,
                "verdict": "UNKNOWN",
                "bridge_error": "schema_mismatch",
            }
        row["compiler_identity"] = self.identity
        row["request_sha256"] = sha256_json(request)
        return row

    @staticmethod
    def orch_status(result: Mapping[str, Any]) -> str:
        return "SUPPORTED" if result.get("verdict") == "VERIFIED" else "UNKNOWN"


class RecoveryExplainer:
    """Recover one heartbeat solely from canonical events and rebuilt world state."""

    STAGES = frozenset({
        "heartbeat.perception",
        "heartbeat.interpretation",
        "heartbeat.mapping",
        "heartbeat.future_field",
        "heartbeat.orch1",
        "heartbeat.deep_interrogation",
        "heartbeat.orch2",
        "heartbeat.authorized",
        "heartbeat.execution_verified",
        "heartbeat.completed",
        "heartbeat.blocked",
    })

    @classmethod
    def explain(
        cls,
        *,
        events: Sequence[Mapping[str, Any]],
        world: Mapping[str, Any],
        heartbeat_id: str,
    ) -> Dict[str, Any]:
        rows: Dict[str, Mapping[str, Any]] = {}
        event_ids: Dict[str, str] = {}
        for event in events:
            if str(event.get("entity_id") or "") != heartbeat_id:
                continue
            stage = str(event.get("action") or "")
            if stage in cls.STAGES:
                rows[stage] = dict(event.get("payload") or {})
                event_ids[stage] = str(event.get("event_id") or "")

        perception = dict(rows.get("heartbeat.perception") or {})
        interpretation = dict(rows.get("heartbeat.interpretation") or {})
        mapping = dict(rows.get("heartbeat.mapping") or {})
        future = dict(rows.get("heartbeat.future_field") or {})
        deep = dict(rows.get("heartbeat.deep_interrogation") or {})
        orch1 = dict(rows.get("heartbeat.orch1") or {})
        orch2 = dict(rows.get("heartbeat.orch2") or {})
        authorized = dict(rows.get("heartbeat.authorized") or {})
        execution = dict(rows.get("heartbeat.execution_verified") or {})
        terminal = dict(rows.get("heartbeat.completed") or rows.get("heartbeat.blocked") or {})

        candidates = list(future.get("candidates") or [])
        interrogation = dict(deep.get("interrogation") or {})
        truth = dict(deep.get("truth_compiler") or {})
        chosen_id = ((orch2.get("decision") or {}).get("selected_candidate_id"))
        chosen = next((x for x in candidates if x.get("candidate_id") == chosen_id), None)

        unknown: List[Dict[str, Any]] = []
        for candidate in candidates:
            cid = str(candidate.get("candidate_id") or "")
            analysis = dict(interrogation.get(cid) or {})
            compiled = dict(truth.get(cid) or {})
            declared = list(candidate.get("unknowns") or [])
            missing = list(analysis.get("missing_evidence_paths") or [])
            if declared or missing or compiled.get("verdict") != "VERIFIED":
                unknown.append({
                    "candidate_id": cid,
                    "declared_unknowns": declared,
                    "missing_evidence_paths": missing,
                    "truth_verdict": compiled.get("verdict", "UNKNOWN"),
                    "truth_reasons": list(compiled.get("reasons") or []),
                })

        verification = dict(execution.get("verification") or {})
        ctp = dict(execution.get("ctp") or {})
        final_result = dict(terminal.get("result") or {})
        recovered = {
            "schema_version": "victor.recovery_explanation.v0",
            "heartbeat_id": heartbeat_id,
            "source": "chronos_plus_rebuilt_world_only",
            "perceived": {
                "variables": list(perception.get("variables") or []),
                "variable_count": perception.get("variable_count", 0),
            },
            "inferred": {
                "meaning_projections": list(interpretation.get("projections") or []),
                "relations": list(mapping.get("relations") or []),
                "scan": dict(mapping.get("scan") or {}),
            },
            "unknown": unknown,
            "considered": {
                "candidates": candidates,
                "orch1": dict(orch1.get("decision") or {}),
            },
            "chosen": {
                "candidate_id": chosen_id,
                "candidate": chosen,
                "orch2": dict(orch2.get("decision") or {}),
            },
            "authorized": {
                "plan": dict(authorized.get("plan") or {}),
                "lease": dict(authorized.get("lease") or {}),
            },
            "executed": dict(execution.get("execution") or {}),
            "observed": {
                "completed": execution.get("completed"),
                "execution_receipt": dict(execution.get("execution") or {}),
            },
            "verified": {
                "truth_compiler": dict(truth.get(chosen_id) or {}),
                "outcome": verification,
                "ctp": ctp,
            },
            "now_believed": {
                "terminal_status": final_result.get("status"),
                "selected_candidate_id": final_result.get("selected_candidate_id", chosen_id),
                "canonical_transition": ctp.get("state_transition"),
                "outcome_verified": bool(verification.get("verified", False)),
                "world_state_sha256": world.get("state_sha256"),
                "chronos_terminal_recorded": bool(terminal),
            },
            "chronos_stage_event_ids": event_ids,
        }
        recovered["explanation_sha256"] = sha256_json(recovered)
        return recovered


class VictorLaunchGateV0(VictorHeartbeatV0):
    """Heartbeat variant that requires the real pinned Truth Compiler."""

    def __init__(
        self,
        *,
        chronos_path: str,
        sandbox_root: str,
        truth_compiler_path: str,
        clock: Callable[[], datetime] = _utc_now,
    ):
        super().__init__(chronos_path=chronos_path, sandbox_root=sandbox_root, clock=clock)
        self.truth_compiler = TruthCompilerBridge(truth_compiler_path)
        self.perception = PerceptionScoutSwarm()
        self.interpreters = MeaningInterpreterSwarm()

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
            "truth_compiler": self.truth_compiler.identity,
        }
        heartbeat_id = _stable_id("heartbeat", heartbeat_core)
        prior = self._prior_result(heartbeat_id)
        if prior is not None:
            return prior

        variables = self.perception.extract(observation, provenance)
        self._observe(heartbeat_id, "heartbeat.perception", {
            "heartbeat_id": heartbeat_id,
            "variable_count": len(variables),
            "variables": [x.to_dict() for x in variables],
            "variables_sha256": sha256_json([x.to_dict() for x in variables]),
        })

        projections = self.interpreters.project(variables, context)
        self._observe(heartbeat_id, "heartbeat.interpretation", {
            "heartbeat_id": heartbeat_id,
            "dimensions": tuple(x.dimension for x in projections),
            "projections": [x.to_dict() for x in projections],
            "projections_sha256": sha256_json([x.to_dict() for x in projections]),
        })

        relations = CrossReferencer.relate(variables)
        scan = SemanticScanner.scan(variables, relations)
        mutations = SemanticMapper.graph_mutations(heartbeat_id, variables, projections, relations)
        self._observe(heartbeat_id, "heartbeat.mapping", {
            "heartbeat_id": heartbeat_id,
            "scan": scan,
            "relations": [x.to_dict() for x in relations],
            "relation_count": len(relations),
        }, mutations)

        candidates = FutureField.generate(candidate_actions)
        self._observe(heartbeat_id, "heartbeat.future_field", {
            "heartbeat_id": heartbeat_id,
            "candidate_count": len(candidates),
            "candidates": [x.to_dict() for x in candidates],
            "reality_lever_ranking": RealityLever.order(candidates),
        })

        orch1 = OrchEngine.pass1(candidates)
        self._observe(heartbeat_id, "heartbeat.orch1", {
            "heartbeat_id": heartbeat_id,
            "decision": orch1.to_dict(),
        })

        variable_paths = tuple(x.path for x in variables)
        interrogation = {
            x.candidate_id: DeepInterrogator.analyze(x, scan, variable_paths)
            for x in candidates
        }
        compiled = {
            x.candidate_id: self.truth_compiler.compile_candidate(
                heartbeat_id=heartbeat_id,
                candidate=x,
                interrogation=interrogation[x.candidate_id],
                variables=variables,
            )
            for x in candidates
        }
        truth_for_orch = {
            cid: self.truth_compiler.orch_status(result)
            for cid, result in compiled.items()
        }
        self._observe(heartbeat_id, "heartbeat.deep_interrogation", {
            "heartbeat_id": heartbeat_id,
            "interrogation": interrogation,
            "truth": truth_for_orch,
            "truth_compiler": compiled,
            "truth_compiler_identity": self.truth_compiler.identity,
        })

        orch2 = OrchEngine.pass2(candidates, interrogation, truth_for_orch)
        self._observe(heartbeat_id, "heartbeat.orch2", {
            "heartbeat_id": heartbeat_id,
            "decision": orch2.to_dict(),
        })
        by_id = {x.candidate_id: x for x in candidates}
        selected = by_id.get(orch2.selected_candidate_id or "")
        if selected is None:
            result = {
                "schema_version": "victor.launch_gate.result.v0",
                "heartbeat_id": heartbeat_id,
                "status": "blocked",
                "reason": "no_candidate_survived_orch2",
                "variable_count": len(variables),
                "meaning_dimensions": tuple(x.dimension for x in projections),
                "truth_compiler_identity": self.truth_compiler.identity,
                "truth_compiler": compiled,
                "orch1": orch1.to_dict(),
                "orch2": orch2.to_dict(),
                "chronos_head": self.ledger.last_chain_hash,
                "world_state_sha256": self.world.snapshot()["state_sha256"],
            }
            self._observe(heartbeat_id, "heartbeat.blocked", {
                "heartbeat_id": heartbeat_id,
                "result": result,
            })
            result["chronos_head"] = self.ledger.last_chain_hash
            result["world_state_sha256"] = self.world.snapshot()["state_sha256"]
            return result

        selected_truth = compiled[selected.candidate_id]
        if selected_truth.get("verdict") != "VERIFIED":
            raise RuntimeError("ORCH_2 selected a candidate not VERIFIED by Truth Compiler")

        plan = AgencyPlanner.plan(selected)
        lease = TaskCompiler(self.sandbox_root, clock=self.clock).compile(heartbeat_id, plan)
        self._observe(heartbeat_id, "heartbeat.authorized", {
            "heartbeat_id": heartbeat_id,
            "candidate_id": selected.candidate_id,
            "plan": plan,
            "lease": lease.to_dict(),
            "truth_compiler_result_sha256": selected_truth.get("result_sha256"),
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

        outcome_id = _stable_id("outcome", {
            "heartbeat_id": heartbeat_id,
            "ctp": ctp["transition_sha256"],
        })
        final_mutations = [
            {"op": "upsert_node", "node_id": selected.candidate_id, "node_type": "candidate", "attributes": {"label": selected.label, "truth_verdict": selected_truth.get("verdict")}},
            {"op": "upsert_node", "node_id": lease.lease_id, "node_type": "capability_lease", "attributes": {"action_type": lease.action_type}},
            {"op": "upsert_node", "node_id": outcome_id, "node_type": "outcome", "attributes": {"verified": True, "receipt_sha256": sha256_json(execution.to_dict())}},
            {"op": "add_edge", "source": heartbeat_id, "target": selected.candidate_id, "edge_type": "COLLAPSES_TO", "attributes": {"pass": "ORCH_2"}},
            {"op": "add_edge", "source": selected.candidate_id, "target": lease.lease_id, "edge_type": "AUTHORIZED_BY", "attributes": {}},
            {"op": "add_edge", "source": lease.lease_id, "target": outcome_id, "edge_type": "RESULTS_IN", "attributes": {"verified": True}},
        ]
        result = {
            "schema_version": "victor.launch_gate.result.v0",
            "heartbeat_id": heartbeat_id,
            "status": "completed",
            "selected_candidate_id": selected.candidate_id,
            "variable_count": len(variables),
            "meaning_dimensions": tuple(x.dimension for x in projections),
            "truth_compiler_identity": self.truth_compiler.identity,
            "truth_compiler": selected_truth,
            "orch1": orch1.to_dict(),
            "orch2": orch2.to_dict(),
            "lease": lease.to_dict(),
            "execution": execution.to_dict(),
            "verification": verification.to_dict(),
            "ctp": ctp,
            "recovery_ready": True,
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

    def recover_explanation(self, heartbeat_id: str) -> Dict[str, Any]:
        return RecoveryExplainer.explain(
            events=self.ledger.events(),
            world=self.world.snapshot(),
            heartbeat_id=heartbeat_id,
        )


def from_environment(
    *,
    chronos_path: str,
    sandbox_root: str,
    clock: Callable[[], datetime] = _utc_now,
) -> VictorLaunchGateV0:
    compiler = os.environ.get("VICTOR_TRUTH_COMPILER_PATH")
    if not compiler:
        raise ValueError("VICTOR_TRUTH_COMPILER_PATH is required")
    return VictorLaunchGateV0(
        chronos_path=chronos_path,
        sandbox_root=sandbox_root,
        truth_compiler_path=compiler,
        clock=clock,
    )
