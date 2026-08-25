"""Cross-episode falsification test: VRC must reconstruct learned state from authenticated ExperienceTransition history."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from trace0_chronos import ChronosLedger, Trace0Observer, sha256_json
from victor_regenerative_continuity import (
    EffectBlockedError,
    ResilienceState,
    VictorGenome,
    VictorRegenerativeContinuity,
)


CONTRACT_NAME = "ExperienceTransition"
CONTRACT_VERSION = "1.0.0"
REDUCER_VERSION = "victor.experience_reducer.v1"
REQUIRED_FIELDS = (
    "transition_id",
    "prior_state_ref",
    "observation",
    "interpretation",
    "prediction",
    "chosen_action",
    "actual_outcome",
    "verification",
    "contradictions",
    "learning_delta",
    "policy_delta",
    "confidence_delta",
    "provenance",
    "timestamp",
    "parent_transition_ref",
)
LEARNING_KEYS = ("experience_count", "prediction_total", "prediction_correct")
POLICY_KEYS = ("share_bias", "question_bias", "adaptation_score")


def state_ref(state):
    return "sha256:" + sha256_json(state)


def field_delta(before, after):
    delta = after - before if isinstance(before, (int, float)) and isinstance(after, (int, float)) else None
    return {"before": before, "after": after, "delta": delta}


def prediction_accuracy(state):
    total = int(state["prediction_total"])
    return (int(state["prediction_correct"]) / total) if total else None


def build_transition(*, before, after, source_event_id, parent_transition_ref, timestamp, label):
    before_accuracy = prediction_accuracy(before)
    after_accuracy = prediction_accuracy(after)
    transition = {
        "transition_id": "",
        "prior_state_ref": state_ref(before),
        "observation": {
            "source_event_id": source_event_id,
            "label": label,
        },
        "interpretation": {
            "kind": "bounded_experience_adaptation",
            "foundation_model_weights_changed": False,
        },
        "prediction": {
            "claim": f"{label}: next bounded policy update is replayable",
            "captured_pre_outcome": True,
        },
        "chosen_action": {
            "type": "apply_bounded_policy_update",
            "reducer_version": REDUCER_VERSION,
        },
        "actual_outcome": {"learning_state": dict(after)},
        "verification": {
            "status": "verified",
            "evidence_refs": [source_event_id],
            "method": "chronos_event_linkage+deterministic_reducer",
        },
        "contradictions": [],
        "learning_delta": {key: field_delta(before[key], after[key]) for key in LEARNING_KEYS},
        "policy_delta": {key: field_delta(before[key], after[key]) for key in POLICY_KEYS},
        "confidence_delta": {
            "prediction_accuracy": field_delta(before_accuracy, after_accuracy),
        },
        "provenance": {
            "sources": [{"evidence_ref": source_event_id}],
            "system_id": "victor:vrc-cross-episode-test",
            "reducer_version": REDUCER_VERSION,
            "contract_name": CONTRACT_NAME,
            "contract_version": CONTRACT_VERSION,
        },
        "timestamp": timestamp,
        "parent_transition_ref": parent_transition_ref,
    }
    identity_core = {key: value for key, value in transition.items() if key != "transition_id"}
    transition["transition_id"] = "ET-" + sha256_json(identity_core)[:28]
    return transition


def validate_and_reduce(current, transition, *, known_event_ids, expected_parent):
    missing = [key for key in REQUIRED_FIELDS if key not in transition]
    if missing:
        raise AssertionError(f"missing ExperienceTransition fields: {missing}")
    if transition["parent_transition_ref"] != expected_parent:
        raise AssertionError("ExperienceTransition parent chain mismatch")
    if transition["prior_state_ref"] != state_ref(current):
        raise AssertionError("ExperienceTransition prior_state_ref mismatch")
    if transition["provenance"].get("reducer_version") != REDUCER_VERSION:
        raise AssertionError("reducer version mismatch")
    if transition["provenance"].get("contract_name") != CONTRACT_NAME:
        raise AssertionError("contract name mismatch")
    evidence_refs = transition["verification"].get("evidence_refs") or []
    if transition["verification"].get("status") != "verified" or not evidence_refs:
        raise AssertionError("transition is not evidence-verified")
    if any(ref not in known_event_ids for ref in evidence_refs):
        raise AssertionError("transition evidence does not exist in recovered Chronos")

    out = dict(current)
    for group in ("learning_delta", "policy_delta"):
        for key, change in transition[group].items():
            if out.get(key) != change["before"]:
                raise AssertionError(f"delta-before mismatch for {key}")
            out[key] = change["after"]
    if out != transition["actual_outcome"]["learning_state"]:
        raise AssertionError("reducer output != recorded actual outcome")
    return out


def replay_recovered_experience(ledger):
    events = ledger.events()
    known_event_ids = set()
    current = None
    expected_parent = None
    transition_count = 0

    for event in events:
        known_event_ids.add(event["event_id"])
        if event["action"] == "experience_genesis":
            if current is not None:
                raise AssertionError("multiple experience genesis events")
            current = dict(event["payload"]["state"])
            if event["payload"]["state_ref"] != state_ref(current):
                raise AssertionError("genesis state hash mismatch")
        elif event["action"] == "experience_transition":
            if current is None:
                raise AssertionError("transition encountered before experience genesis")
            transition = dict(event["payload"]["experience_transition"])
            current = validate_and_reduce(
                current,
                transition,
                known_event_ids=known_event_ids,
                expected_parent=expected_parent,
            )
            expected_parent = transition["transition_id"]
            transition_count += 1

    if current is None:
        raise AssertionError("missing experience genesis")
    if transition_count == 0:
        raise AssertionError("no ExperienceTransitions recovered")
    return current, expected_parent, transition_count


class RegenerativeExperienceReconstructionTest(unittest.TestCase):
    def test_fresh_runtime_reconstructs_learned_state_from_chronos_transitions(self):
        fixed = datetime(2026, 8, 25, 20, 9, tzinfo=timezone.utc)
        ledger = ChronosLedger()
        trace = Trace0Observer(ledger, clock=lambda: fixed)

        genesis = {
            "experience_count": 0,
            "prediction_total": 0,
            "prediction_correct": 0,
            "share_bias": 0.0,
            "question_bias": 0.0,
            "adaptation_score": 0.0,
        }
        trace.observe(
            actor="victor.experience",
            action="experience_genesis",
            entity_id="experience:genesis",
            payload={"state": genesis, "state_ref": state_ref(genesis)},
            provenance={"source": "cross-episode-vrc-falsification"},
            evidence={"status": "observed"},
        )

        states = [
            {
                "experience_count": 1,
                "prediction_total": 1,
                "prediction_correct": 0,
                "share_bias": -0.015,
                "question_bias": 0.025,
                "adaptation_score": 0.027,
            },
            {
                "experience_count": 2,
                "prediction_total": 2,
                "prediction_correct": 1,
                "share_bias": -0.005,
                "question_bias": 0.022,
                "adaptation_score": 0.031,
            },
            {
                "experience_count": 3,
                "prediction_total": 3,
                "prediction_correct": 2,
                "share_bias": 0.005,
                "question_bias": 0.019,
                "adaptation_score": 0.028,
            },
        ]

        before = genesis
        parent_transition_ref = None
        transition_ids = []
        for index, after in enumerate(states, start=1):
            evidence_event, _ = trace.observe(
                actor="victor.world",
                action="experience_observed",
                entity_id=f"observation:o{index}",
                payload={"ordinal": index, "prediction_correct": after["prediction_correct"] > before["prediction_correct"]},
                provenance={"source": "synthetic-world-falsification-fixture"},
                evidence={"status": "observed"},
            )
            transition = build_transition(
                before=before,
                after=after,
                source_event_id=evidence_event.event_id,
                parent_transition_ref=parent_transition_ref,
                timestamp=f"2026-08-25T20:09:0{index}+00:00",
                label=f"experience-{index}",
            )
            trace.observe(
                actor="victor.experience",
                action="experience_transition",
                entity_id=transition["transition_id"],
                payload={"experience_transition": transition},
                provenance={
                    "source": "ExperienceTransition",
                    "contract_version": CONTRACT_VERSION,
                    "reducer_version": REDUCER_VERSION,
                },
                evidence={"status": "verified", "refs": [evidence_event.event_id]},
            )
            parent_transition_ref = transition["transition_id"]
            transition_ids.append(parent_transition_ref)
            before = after

        self.assertTrue(ledger.verify_chain())
        predestruction_state = dict(states[-1])
        predestruction_state_ref = state_ref(predestruction_state)
        predestruction_chronos_head = ledger.last_chain_hash

        genome = VictorGenome(
            schema_version="victor.genome.v1",
            subject="VICTOR",
            identity_algorithm="HMAC-SHA256",
            identity_key_id="cross-episode-test-key",
            constitution_sha256="b" * 64,
        )
        source_runtime = VictorRegenerativeContinuity(genome)

        # Deliberately do NOT save the learned state as an opaque memory dump.
        # Only replay metadata/commitments are carried outside Chronos.
        replay_commitment = {
            "experience_reconstruction": {
                "contract": f"{CONTRACT_NAME}@{CONTRACT_VERSION}",
                "reducer_version": REDUCER_VERSION,
                "expected_state_ref": predestruction_state_ref,
                "transition_head": transition_ids[-1],
            }
        }
        _capsule, shards = source_runtime.enter_cryptobiosis(
            ledger,
            replay_commitment,
            reason="destructive ExperienceTransition regeneration test",
            created_at="2026-08-25T20:09:10+00:00",
        )

        # Destruction boundary: source runtime and materialized learned state are no
        # longer used. A fresh VRC instance receives only the genome and surviving shards.
        del source_runtime
        del predestruction_state

        replacement = VictorRegenerativeContinuity(
            genome,
            state=ResilienceState.CRYPTOBIOSIS,
        )
        with self.assertRaises(EffectBlockedError):
            replacement.require_external_effects_allowed()

        # Lose one data fragment; parity must reconstruct it.
        result = replacement.recover((shards[0], shards[2]))
        self.assertEqual(replacement.state, ResilienceState.RECOVERED)
        self.assertEqual(result.reconstructed_shard_index, 1)
        self.assertEqual(result.ledger.last_chain_hash, predestruction_chronos_head)
        self.assertTrue(result.ledger.verify_chain())
        with self.assertRaises(EffectBlockedError):
            replacement.require_external_effects_allowed()

        reconstructed_state, reconstructed_transition_head, count = replay_recovered_experience(result.ledger)
        commitment = result.capsule.continuity_payload["experience_reconstruction"]

        self.assertEqual(count, 3)
        self.assertEqual(reconstructed_transition_head, commitment["transition_head"])
        self.assertEqual(state_ref(reconstructed_state), predestruction_state_ref)
        self.assertEqual(state_ref(reconstructed_state), commitment["expected_state_ref"])
        self.assertEqual(result.capsule.genome.genome_id, genome.genome_id)

        # Only after independent replay verification may the fresh runtime regain effects.
        replacement.reactivate()
        replacement.require_external_effects_allowed()
        self.assertEqual(replacement.state, ResilienceState.ACTIVE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
