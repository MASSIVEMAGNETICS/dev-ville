"""Destructive process-boundary acceptance test for Victor Regenerative Continuity.

This test proves more than object re-instantiation: a producer process persists a
VRC recovery set and derived-state marker, is hard-killed, one recovery shard and
the derived state are deleted, and a separate Python process must reconstruct
continuity from the surviving authenticated fragments. Consequential effects
must remain blocked until recovery verification completes and reactivation is
explicit.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


PRODUCER = r'''
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from trace0_chronos import ChronosLedger, Trace0Observer
from victor_regenerative_continuity import (
    VictorGenome,
    VictorRegenerativeContinuity,
    write_recovery_set_atomic,
)

root = Path(sys.argv[1])
fixed = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
ledger = ChronosLedger()
trace = Trace0Observer(ledger, clock=lambda: fixed)
trace.observe(
    actor="victor.runtime",
    action="fresh_process_continuity_marker",
    entity_id="runtime:pre-destruction",
    payload={"mission": "recover-after-process-destruction", "step": 91},
    provenance={"source": "vrc-fresh-process-acceptance"},
    evidence={"status": "observed"},
)

genome = VictorGenome(
    schema_version="victor.genome.v1",
    subject="VICTOR",
    identity_algorithm="HMAC-SHA256",
    identity_key_id="fresh-process-test-key",
    constitution_sha256="c" * 64,
)
source = VictorRegenerativeContinuity(genome)
capsule, shards = source.enter_cryptobiosis(
    ledger,
    {
        "current_mission": "recover-after-process-destruction",
        "current_step": 91,
        "authority_state": "effects-blocked-until-verified-reactivation",
    },
    reason="fresh-process destructive recovery acceptance",
    created_at="2026-08-27T00:00:01+00:00",
)
paths = write_recovery_set_atomic(root, shards)

# Simulated derived/materialized state. The recovery process must not depend on it.
(root / "derived-world-state.json").write_text(
    json.dumps({"derived": True, "step": 91}, sort_keys=True),
    encoding="utf-8",
)
(root / "expected.json").write_text(
    json.dumps(
        {
            "genome": genome.to_dict(),
            "genome_id": genome.genome_id,
            "capsule_id": capsule.capsule_id,
            "chronos_head": ledger.last_chain_hash,
            "shards": [str(path.name) for path in paths],
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
(root / "producer.ready").write_text("ready\n", encoding="utf-8")

# Stay alive so the parent can prove abrupt process destruction rather than a
# cooperative clean shutdown path.
while True:
    time.sleep(1)
'''


CONSUMER = r'''
import json
from pathlib import Path
import sys

from victor_regenerative_continuity import (
    EffectBlockedError,
    ResilienceState,
    VictorGenome,
    VictorRegenerativeContinuity,
    read_recovery_shard,
)

root = Path(sys.argv[1])
expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
genome = VictorGenome.from_dict(expected["genome"])
remaining = sorted(root.glob("vrc-*.json"))
shards = tuple(read_recovery_shard(path) for path in remaining)
replacement = VictorRegenerativeContinuity(
    genome,
    state=ResilienceState.CRYPTOBIOSIS,
)

blocked_before = False
try:
    replacement.require_external_effects_allowed()
except EffectBlockedError:
    blocked_before = True

result = replacement.recover(shards)

blocked_after_recovery = False
try:
    replacement.require_external_effects_allowed()
except EffectBlockedError:
    blocked_after_recovery = True

verified = (
    replacement.state == ResilienceState.RECOVERED
    and result.capsule.capsule_id == expected["capsule_id"]
    and result.capsule.genome.genome_id == expected["genome_id"]
    and result.ledger.last_chain_hash == expected["chronos_head"]
    and result.ledger.verify_chain()
    and result.capsule.continuity_payload["current_mission"]
        == "recover-after-process-destruction"
    and result.capsule.continuity_payload["current_step"] == 91
    and blocked_before
    and blocked_after_recovery
)
if not verified:
    raise SystemExit("fresh-process continuity verification failed")

replacement.reactivate()
replacement.require_external_effects_allowed()
(root / "consumer-result.json").write_text(
    json.dumps(
        {
            "state": replacement.state.value,
            "capsule_id": result.capsule.capsule_id,
            "chronos_head": result.ledger.last_chain_hash,
            "used_shard_indices": list(result.used_shard_indices),
            "reconstructed_shard_index": result.reconstructed_shard_index,
            "blocked_before": blocked_before,
            "blocked_after_recovery": blocked_after_recovery,
            "derived_state_present": (root / "derived-world-state.json").exists(),
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
'''


class VRCFreshProcessRecoveryTests(unittest.TestCase):
    def test_hard_kill_then_fresh_process_recovers_with_one_fragment_missing(self):
        with tempfile.TemporaryDirectory(prefix="victor-vrc-process-") as tmp:
            root = Path(tmp)
            producer = subprocess.Popen(
                [sys.executable, "-c", PRODUCER, str(root)],
                cwd=Path(__file__).resolve().parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and not (root / "producer.ready").exists():
                    if producer.poll() is not None:
                        stdout, stderr = producer.communicate()
                        self.fail(
                            "producer exited before destruction boundary\n"
                            f"stdout:\n{stdout}\nstderr:\n{stderr}"
                        )
                    time.sleep(0.05)
                self.assertTrue((root / "producer.ready").exists(), "producer never reached recovery-set boundary")

                # On POSIX this is SIGKILL; on Windows it is TerminateProcess.
                producer.kill()
                producer.wait(timeout=5)
                self.assertIsNotNone(producer.returncode)

                expected = json.loads((root / "expected.json").read_text(encoding="utf-8"))
                self.assertEqual(len(expected["shards"]), 3)

                # Destroy all materialized/derived state and one data fragment.
                derived = root / "derived-world-state.json"
                self.assertTrue(derived.exists())
                derived.unlink()
                missing = root / expected["shards"][1]
                self.assertTrue(missing.exists())
                missing.unlink()

                remaining = sorted(root.glob("vrc-*.json"))
                self.assertEqual(len(remaining), 2)

                consumer = subprocess.run(
                    [sys.executable, "-c", CONSUMER, str(root)],
                    cwd=Path(__file__).resolve().parent,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(
                    consumer.returncode,
                    0,
                    f"consumer failed\nstdout:\n{consumer.stdout}\nstderr:\n{consumer.stderr}",
                )
                result = json.loads((root / "consumer-result.json").read_text(encoding="utf-8"))
                self.assertEqual(result["state"], "ACTIVE")
                self.assertEqual(result["capsule_id"], expected["capsule_id"])
                self.assertEqual(result["chronos_head"], expected["chronos_head"])
                self.assertEqual(result["used_shard_indices"], [0, 2])
                self.assertEqual(result["reconstructed_shard_index"], 1)
                self.assertTrue(result["blocked_before"])
                self.assertTrue(result["blocked_after_recovery"])
                self.assertFalse(result["derived_state_present"])
            finally:
                if producer.poll() is None:
                    producer.kill()
                    producer.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
