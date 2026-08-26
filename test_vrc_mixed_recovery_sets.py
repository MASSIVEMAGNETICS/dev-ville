"""Adversarial recovery-set selection tests for VRC-0.

Foreign or stale shards must not poison discovery of an otherwise valid quorum,
and multiple independently valid quorums must fail closed as ambiguous.
"""
from __future__ import annotations

from datetime import datetime, timezone
import unittest

from trace0_chronos import ChronosLedger, Trace0Observer
from victor_regenerative_continuity import (
    RecoveryQuorumError,
    ResilienceState,
    VictorGenome,
    VictorRegenerativeContinuity,
)


class VRCMixedRecoverySetTests(unittest.TestCase):
    def _freeze(self, marker: str):
        fixed = datetime(2026, 8, 26, 0, 0, tzinfo=timezone.utc)
        ledger = ChronosLedger()
        Trace0Observer(ledger, clock=lambda: fixed).observe(
            actor="victor.experience",
            action="continuity_marker",
            entity_id=f"marker:{marker}",
            payload={"marker": marker},
            provenance={"source": "mixed-recovery-set-regression"},
            evidence={"status": "observed"},
        )
        genome = VictorGenome(
            schema_version="victor.genome.v1",
            subject="VICTOR",
            identity_algorithm="HMAC-SHA256",
            identity_key_id="test-key-id-001",
            constitution_sha256="a" * 64,
        )
        vrc = VictorRegenerativeContinuity(genome)
        capsule, shards = vrc.enter_cryptobiosis(
            ledger,
            {"current_mission": {"marker": marker}},
            reason="mixed-set regression",
            created_at="2026-08-26T00:00:00+00:00",
        )
        return genome, capsule, shards

    def test_foreign_first_shard_does_not_hide_valid_quorum(self):
        genome, expected_capsule, expected_shards = self._freeze("expected")
        _foreign_genome, _foreign_capsule, foreign_shards = self._freeze("foreign")

        replacement = VictorRegenerativeContinuity(
            genome,
            state=ResilienceState.CRYPTOBIOSIS,
        )
        result = replacement.recover(
            (foreign_shards[0], expected_shards[0], expected_shards[2])
        )

        self.assertEqual(replacement.state, ResilienceState.RECOVERED)
        self.assertEqual(result.capsule.capsule_id, expected_capsule.capsule_id)
        self.assertEqual(result.used_shard_indices, (0, 2))
        self.assertEqual(result.reconstructed_shard_index, 1)

    def test_two_valid_recovery_sets_fail_closed_as_ambiguous(self):
        genome, _capsule_a, shards_a = self._freeze("set-a")
        _genome_b, _capsule_b, shards_b = self._freeze("set-b")

        replacement = VictorRegenerativeContinuity(
            genome,
            state=ResilienceState.CRYPTOBIOSIS,
        )
        with self.assertRaisesRegex(RecoveryQuorumError, "ambiguous"):
            replacement.recover(
                (shards_a[0], shards_b[2], shards_b[0], shards_a[2])
            )

        self.assertEqual(replacement.state, ResilienceState.HALTED)
        self.assertFalse(replacement.external_effects_allowed())


if __name__ == "__main__":
    unittest.main(verbosity=2)
