"""Launch-gate contract tests for victor_heartbeat_v0."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from victor_heartbeat_v0 import MEANING_DIMENSIONS, VictorHeartbeatV0


class VictorCanonicalHeartbeatV0Tests(unittest.TestCase):
    def _request(self):
        observation = {
            "objective": "produce a bounded verified proof artifact",
            "project": "Victor",
            "evidence": {"owner_authorized": True},
            "context": {"source": "launch_gate"},
        }
        candidates = [
            {
                "label": "write verified heartbeat proof",
                "action": {
                    "type": "write_text",
                    "path": "proof/victor-heartbeat.txt",
                    "content": "VICTOR CANONICAL HEARTBEAT v0\n",
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

    def test_full_heartbeat_executes_verifies_and_canonicalizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = VictorHeartbeatV0(
                chronos_path=str(root / "chronos" / "heartbeat.jsonl"),
                sandbox_root=str(root / "aether-sandbox"),
            )
            observation, candidates = self._request()
            result = engine.run(
                observation=observation,
                provenance={"source": "unit_test", "authority": "test_owner"},
                context={"mode": "launch_gate"},
                candidate_actions=candidates,
            )

            self.assertEqual(result["status"], "completed")
            self.assertEqual(tuple(result["meaning_dimensions"]), MEANING_DIMENSIONS)
            self.assertEqual(len(result["meaning_dimensions"]), 12)
            self.assertTrue(result["verification"]["verified"])
            self.assertEqual(result["ctp"]["state_transition"], "AUTHORIZED->EXECUTED->VERIFIED->CANONICAL")
            self.assertTrue(engine.ledger.verify_chain())

            target = root / "aether-sandbox" / "proof" / "victor-heartbeat.txt"
            self.assertEqual(target.read_text(encoding="utf-8"), "VICTOR CANONICAL HEARTBEAT v0\n")

            snapshot = engine.continuity_snapshot()
            self.assertTrue(snapshot["chronos_valid"])
            node_types = {node["node_type"] for node in snapshot["world"]["nodes"]}
            self.assertIn("variable", node_types)
            self.assertIn("meaning_projection", node_types)
            self.assertIn("candidate", node_types)
            self.assertIn("capability_lease", node_types)
            self.assertIn("outcome", node_types)

    def test_restart_rebuilds_world_and_replay_does_not_execute_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ledger = root / "chronos" / "heartbeat.jsonl"
            sandbox = root / "aether-sandbox"
            observation, candidates = self._request()
            kwargs = {
                "observation": observation,
                "provenance": {"source": "unit_test", "authority": "test_owner"},
                "context": {"mode": "launch_gate"},
                "candidate_actions": candidates,
            }

            first = VictorHeartbeatV0(chronos_path=str(ledger), sandbox_root=str(sandbox))
            first_result = first.run(**kwargs)
            first_snapshot = first.continuity_snapshot()
            event_count = first_snapshot["chronos_events"]
            target = sandbox / "proof" / "victor-heartbeat.txt"
            first_bytes = target.read_bytes()

            restarted = VictorHeartbeatV0(chronos_path=str(ledger), sandbox_root=str(sandbox))
            rebuilt = restarted.continuity_snapshot()
            self.assertEqual(rebuilt["world"]["state_sha256"], first_snapshot["world"]["state_sha256"])
            self.assertEqual(rebuilt["chronos_head"], first_snapshot["chronos_head"])

            replay = restarted.run(**kwargs)
            self.assertEqual(replay["status"], "replayed")
            self.assertEqual(restarted.continuity_snapshot()["chronos_events"], event_count)
            self.assertEqual(target.read_bytes(), first_bytes)
            self.assertEqual(replay["heartbeat_id"], first_result["heartbeat_id"])

    def test_path_escape_is_rejected_before_capability_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = VictorHeartbeatV0(
                chronos_path=str(root / "chronos.jsonl"),
                sandbox_root=str(root / "sandbox"),
            )
            result = engine.run(
                observation={"evidence": {"owner_authorized": True}},
                candidate_actions=[
                    {
                        "label": "escape",
                        "action": {"type": "write_text", "path": "../escape.txt", "content": "bad"},
                        "expected_delta": 1.0,
                        "cost": 0.0,
                        "risk": 0.0,
                        "reversibility": 1.0,
                        "evidence_paths": ["evidence.owner_authorized"],
                    }
                ],
            )
            self.assertEqual(result["status"], "blocked")
            self.assertFalse((root / "escape.txt").exists())
            self.assertTrue(engine.ledger.verify_chain())

    def test_unknown_evidence_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            engine = VictorHeartbeatV0(
                chronos_path=str(root / "chronos.jsonl"),
                sandbox_root=str(root / "sandbox"),
            )
            result = engine.run(
                observation={"objective": "write proof"},
                candidate_actions=[
                    {
                        "label": "unsupported evidence",
                        "action": {"type": "write_text", "path": "proof.txt", "content": "x"},
                        "expected_delta": 1.0,
                        "cost": 0.0,
                        "risk": 0.0,
                        "reversibility": 1.0,
                        "evidence_paths": ["evidence.not_present"],
                    }
                ],
            )
            self.assertEqual(result["status"], "blocked")
            self.assertFalse((root / "sandbox" / "proof.txt").exists())


if __name__ == "__main__":
    unittest.main()
