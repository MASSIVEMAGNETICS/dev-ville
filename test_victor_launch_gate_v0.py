from __future__ import annotations

import os
from pathlib import Path
import shutil
import tempfile
import unittest

from victor_launch_gate_v0_runtime import (
    TRUTH_COMPILER_COMMIT,
    TRUTH_COMPILER_FILE_SHA256,
    TruthCompilerBridge,
    VictorLaunchGateV0,
)

COMPILER_PATH = os.environ.get("VICTOR_TRUTH_COMPILER_PATH")


@unittest.skipUnless(COMPILER_PATH, "external Truth Compiler path not configured")
class VictorLaunchGateV0Tests(unittest.TestCase):
    def _request(self):
        observation = {
            "objective": "produce a bounded verified proof artifact",
            "project": "Victor",
            "evidence": {"owner_authorized": True},
            "context": {"source": "launch_gate"},
        }
        candidates = [
            {
                "label": "write verified launch proof",
                "action": {
                    "type": "write_text",
                    "path": "proof/victor-launch-gate.txt",
                    "content": "VICTOR LAUNCH GATE v0 VERIFIED\n",
                },
                "expected_delta": 0.95,
                "cost": 0.10,
                "risk": 0.05,
                "reversibility": 1.0,
                "evidence_paths": ["evidence.owner_authorized"],
            },
            {
                "label": "do nothing",
                "action": {"type": "noop"},
                "expected_delta": 0.01,
                "cost": 0.0,
                "risk": 0.0,
                "reversibility": 1.0,
                "evidence_paths": [],
                "unknowns": ["does_not_satisfy_objective"],
            },
        ]
        return observation, candidates

    def test_real_truth_compiler_executes_and_recovery_survives_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "chronos" / "launch.jsonl"
            sandbox = root / "aether"
            observation, candidates = self._request()
            kwargs = {
                "observation": observation,
                "provenance": {"source": "launch_test", "authority": "test_owner"},
                "context": {"mode": "strict_launch_gate"},
                "candidate_actions": candidates,
            }

            first = VictorLaunchGateV0(
                chronos_path=str(ledger),
                sandbox_root=str(sandbox),
                truth_compiler_path=str(COMPILER_PATH),
            )
            result = first.run(**kwargs)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["truth_compiler"]["verdict"], "VERIFIED")
            self.assertEqual(result["truth_compiler_identity"]["source_commit"], TRUTH_COMPILER_COMMIT)
            self.assertEqual(result["truth_compiler_identity"]["file_sha256"], TRUTH_COMPILER_FILE_SHA256)
            self.assertTrue(result["verification"]["verified"])
            self.assertEqual(result["ctp"]["state_transition"], "AUTHORIZED->EXECUTED->VERIFIED->CANONICAL")
            self.assertTrue(first.ledger.verify_chain())

            target = sandbox / "proof" / "victor-launch-gate.txt"
            self.assertTrue(target.exists())
            event_count = len(first.ledger.events())
            heartbeat_id = result["heartbeat_id"]

            # New runtime object: no transcript, no prior in-memory reasoning.
            restarted = VictorLaunchGateV0(
                chronos_path=str(ledger),
                sandbox_root=str(sandbox),
                truth_compiler_path=str(COMPILER_PATH),
            )
            explanation = restarted.recover_explanation(heartbeat_id)
            self.assertEqual(explanation["source"], "chronos_plus_rebuilt_world_only")
            self.assertTrue(explanation["perceived"]["variables"])
            self.assertEqual(len(explanation["inferred"]["meaning_projections"]), 12)
            self.assertGreaterEqual(len(explanation["considered"]["candidates"]), 2)
            self.assertEqual(explanation["chosen"]["candidate_id"], result["selected_candidate_id"])
            self.assertTrue(explanation["authorized"]["lease"])
            self.assertEqual(explanation["executed"]["status"], "completed")
            self.assertTrue(explanation["verified"]["outcome"]["verified"])
            self.assertEqual(explanation["verified"]["truth_compiler"]["verdict"], "VERIFIED")
            self.assertEqual(
                explanation["now_believed"]["canonical_transition"],
                "AUTHORIZED->EXECUTED->VERIFIED->CANONICAL",
            )
            self.assertTrue(explanation["now_believed"]["outcome_verified"])
            self.assertTrue(explanation["explanation_sha256"])

            replay = restarted.run(**kwargs)
            self.assertEqual(replay["status"], "replayed")
            self.assertEqual(len(restarted.ledger.events()), event_count)
            self.assertTrue(restarted.ledger.verify_chain())

    def test_truth_unknown_blocks_external_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = VictorLaunchGateV0(
                chronos_path=str(root / "chronos.jsonl"),
                sandbox_root=str(root / "aether"),
                truth_compiler_path=str(COMPILER_PATH),
            )
            observation = {"objective": "test unknown"}
            candidates = [{
                "label": "requires missing authority evidence",
                "action": {"type": "write_text", "path": "proof/blocked.txt", "content": "NO\n"},
                "expected_delta": 0.9,
                "cost": 0.1,
                "risk": 0.1,
                "reversibility": 1.0,
                "evidence_paths": ["evidence.owner_authorized"],
            }]
            result = engine.run(
                observation=observation,
                provenance={"source": "launch_test"},
                context={},
                candidate_actions=candidates,
            )
            self.assertEqual(result["status"], "blocked")
            only = next(iter(result["truth_compiler"].values()))
            self.assertEqual(only["verdict"], "UNKNOWN")
            self.assertFalse((root / "aether" / "proof" / "blocked.txt").exists())
            self.assertTrue(engine.ledger.verify_chain())

    def test_compiler_hash_pin_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            tampered = Path(tmp) / "truth_compiler_contract.py"
            shutil.copyfile(str(COMPILER_PATH), tampered)
            tampered.write_text(tampered.read_text(encoding="utf-8") + "\n# tampered\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                TruthCompilerBridge(str(tampered))


if __name__ == "__main__":
    unittest.main()
