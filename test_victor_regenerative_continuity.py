"""Destructive continuity tests for Victor Regenerative Continuity (VRC-0)."""
from __future__ import annotations

import base64
from dataclasses import replace
from datetime import datetime, timezone
import tempfile
import unittest

from trace0_chronos import ChronosLedger, Trace0Observer
from victor_regenerative_continuity import (
    EffectBlockedError,
    IntegrityError,
    RecoveryQuorumError,
    ResilienceState,
    VictorGenome,
    VictorRegenerativeContinuity,
    read_recovery_shard,
    verify_capsule,
    write_recovery_set_atomic,
)


class VRC0Tests(unittest.TestCase):
    def setUp(self) -> None:
        fixed = datetime(2026, 8, 24, 20, 27, tzinfo=timezone.utc)
        self.ledger = ChronosLedger()
        trace = Trace0Observer(self.ledger, clock=lambda: fixed)
        trace.observe(
            actor="victor.experience",
            action="episode_integrated",
            entity_id="episode:e1",
            payload={"salience": 0.82, "prediction_error": 0.19},
            provenance={"source": "experience-kernel-test"},
            evidence={"status": "observed"},
        )
        trace.observe(
            actor="victor.choice",
            action="mission_selected",
            entity_id="mission:m1",
            payload={"goal": "preserve continuity through destructive restart"},
            provenance={"source": "vrc-test"},
            evidence={"status": "observed"},
        )
        self.genome = VictorGenome(
            schema_version="victor.genome.v1",
            subject="VICTOR",
            identity_algorithm="HMAC-SHA256",
            identity_key_id="test-key-id-001",
            constitution_sha256="a" * 64,
        )
        self.payload = {
            "experience": {
                "episode_count": 1,
                "episodic_state": {"last_episode": "episode:e1"},
                "semantic_state": {"continuity": "reconstructible"},
                "prediction_state": {"last_error": 0.19},
                "homeostasis": {"stability": 0.73},
                "dictionary_bindings": {"signal": "surviving meaning"},
            },
            "current_mission": {
                "mission_id": "mission:m1",
                "goal": "preserve continuity through destructive restart",
                "phase": "VERIFYING",
            },
            "unresolved": ["prove reconstruction after one-fragment corruption"],
        }

    def _freeze(self):
        vrc = VictorRegenerativeContinuity(self.genome)
        capsule, shards = vrc.enter_cryptobiosis(
            self.ledger,
            self.payload,
            reason="destructive continuity drill",
            created_at="2026-08-24T20:27:00+00:00",
        )
        self.assertEqual(vrc.state, ResilienceState.CRYPTOBIOSIS)
        return vrc, capsule, shards

    def test_one_missing_data_shard_reconstructs_from_parity(self):
        vrc, capsule, shards = self._freeze()
        result = vrc.recover((shards[0], shards[2]))
        self.assertEqual(vrc.state, ResilienceState.RECOVERED)
        self.assertEqual(result.reconstructed_shard_index, 1)
        self.assertEqual(result.capsule.capsule_id, capsule.capsule_id)
        self.assertEqual(result.ledger.last_chain_hash, self.ledger.last_chain_hash)
        self.assertEqual(result.capsule.continuity_payload, self.payload)

    def test_one_detectably_corrupt_shard_is_ignored_and_reconstructed(self):
        vrc, capsule, shards = self._freeze()
        raw = bytearray(base64.b64decode(shards[0].payload_b64))
        raw[0] ^= 0xFF
        corrupt = replace(shards[0], payload_b64=base64.b64encode(bytes(raw)).decode("ascii"))

        result = vrc.recover((corrupt, shards[1], shards[2]))
        self.assertEqual(result.reconstructed_shard_index, 0)
        self.assertEqual(result.capsule.capsule_id, capsule.capsule_id)
        self.assertEqual(result.ledger.last_chain_hash, self.ledger.last_chain_hash)

    def test_two_missing_shards_fail_closed(self):
        vrc, _capsule, shards = self._freeze()
        with self.assertRaises(RecoveryQuorumError):
            vrc.recover((shards[2],))
        self.assertEqual(vrc.state, ResilienceState.HALTED)
        with self.assertRaises(EffectBlockedError):
            vrc.require_external_effects_allowed()

    def test_identity_genome_mismatch_fails_closed(self):
        _source_vrc, _capsule, shards = self._freeze()
        wrong_genome = replace(self.genome, identity_key_id="different-key")
        replacement = VictorRegenerativeContinuity(
            wrong_genome,
            state=ResilienceState.CRYPTOBIOSIS,
        )
        with self.assertRaises(IntegrityError):
            replacement.recover(shards)
        self.assertEqual(replacement.state, ResilienceState.HALTED)

    def test_continuity_payload_tampering_is_rejected(self):
        _vrc, capsule, _shards = self._freeze()
        tampered = replace(
            capsule,
            continuity_payload={"current_mission": {"goal": "attacker supplied goal"}},
        )
        with self.assertRaises(IntegrityError):
            verify_capsule(tampered, expected_genome=self.genome)

    def test_cryptobiosis_blocks_effects_until_verified_reactivation(self):
        vrc, _capsule, shards = self._freeze()
        with self.assertRaises(EffectBlockedError):
            vrc.require_external_effects_allowed()

        result = vrc.recover(shards)
        self.assertTrue(result.ledger.verify_chain())
        self.assertEqual(vrc.state, ResilienceState.RECOVERED)
        with self.assertRaises(EffectBlockedError):
            vrc.require_external_effects_allowed()

        vrc.reactivate()
        self.assertEqual(vrc.state, ResilienceState.ACTIVE)
        vrc.require_external_effects_allowed()

    def test_recovery_set_round_trip_through_atomic_files(self):
        _vrc, capsule, shards = self._freeze()
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_recovery_set_atomic(tmp, shards)
            loaded = tuple(read_recovery_shard(path) for path in paths)
            replacement = VictorRegenerativeContinuity(
                self.genome,
                state=ResilienceState.CRYPTOBIOSIS,
            )
            result = replacement.recover((loaded[0], loaded[2]))
            self.assertEqual(result.capsule.capsule_id, capsule.capsule_id)
            self.assertEqual(result.ledger.last_chain_hash, self.ledger.last_chain_hash)


if __name__ == "__main__":
    unittest.main(verbosity=2)
