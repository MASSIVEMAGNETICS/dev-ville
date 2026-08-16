import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from empire_chronos_bridge import ChronosBackedEmpire
from trace0_chronos import ChronosLedger


class EmpireChronosBridgeTests(unittest.TestCase):
    def write_manifest(self, root: Path, manifest: dict) -> Path:
        path = root / "empire_manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def make_bridge(self, root: Path, manifest: dict) -> ChronosBackedEmpire:
        return ChronosBackedEmpire(
            self.write_manifest(root, manifest),
            receipt_dir=root / "receipts",
            chronos_path=root / "chronos" / "empire.jsonl",
        )

    def test_demotion_run_writes_sidecar_and_one_verified_chronos_event(self):
        manifest = {"version": 1, "nodes": [
            {"id": "commerce", "capability": "commerce", "status": "planned", "dependencies": []},
            {"id": "revenue-worker", "capability": "revenue", "status": "active", "dependencies": ["commerce"]},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            result = bridge.run(apply=True)

            self.assertTrue((root / "receipts" / f"{result.control_plane.receipt_id}.json").exists())
            ledger = ChronosLedger(str(root / "chronos" / "empire.jsonl"))
            self.assertTrue(ledger.verify_chain())
            self.assertEqual(len(ledger.events()), 1)
            event = ledger.events()[0]
            self.assertEqual(event["action"], "control_plane_run_recorded")
            self.assertEqual(event["payload"]["receipt_id"], result.control_plane.receipt_id)
            self.assertEqual(event["evidence"]["manifest_hash_after"], result.control_plane.manifest_hash_after)
            updated = json.loads((root / "empire_manifest.json").read_text(encoding="utf-8"))
            statuses = {node["id"]: node["status"] for node in updated["nodes"]}
            self.assertEqual(statuses["revenue-worker"], "blocked")

    def test_consecutive_runs_link_to_previous_chronos_head(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "blocked", "dependencies": ["control"],
             "auto_fix": "promote_ready", "metadata": {
                 "readiness_verified": True,
                 "readiness_receipt": "verify:abc123"
             }},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            first = bridge.run(apply=True)
            second = bridge.run(apply=False)

            ledger = ChronosLedger(str(root / "chronos" / "empire.jsonl"))
            self.assertTrue(ledger.verify_chain())
            self.assertEqual(len(ledger.events()), 2)
            self.assertEqual(ledger.events()[1]["parent_event_hash"], first.chronos.event_hash)
            self.assertEqual(ledger.receipts()[-1]["chain_hash"], second.chronos.chain_hash)

    def test_check_only_preserves_manifest_but_records_assessment(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "planned", "dependencies": ["control"],
             "auto_fix": "promote_ready"},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            before = (root / "empire_manifest.json").read_text(encoding="utf-8")
            result = bridge.run(apply=False)
            after = (root / "empire_manifest.json").read_text(encoding="utf-8")

            self.assertEqual(before, after)
            ledger = ChronosLedger(str(root / "chronos" / "empire.jsonl"))
            self.assertTrue(ledger.verify_chain())
            self.assertEqual(len(ledger.events()), 1)
            self.assertFalse(ledger.events()[0]["payload"]["apply"])
            self.assertEqual(ledger.events()[0]["payload"]["receipt_id"], result.control_plane.receipt_id)

    def test_tampered_chronos_record_fails_replay(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            bridge.run(apply=False)

            chronos_path = root / "chronos" / "empire.jsonl"
            record = json.loads(chronos_path.read_text(encoding="utf-8").strip())
            record["event"]["payload"]["receipt_id"] = "tampered"
            chronos_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                ChronosLedger(str(chronos_path))

    def test_out_of_band_manifest_change_fails_closed_before_next_run(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            bridge.run(apply=False)

            altered = json.loads((root / "empire_manifest.json").read_text(encoding="utf-8"))
            altered["nodes"][0]["status"] = "planned"
            (root / "empire_manifest.json").write_text(json.dumps(altered), encoding="utf-8")

            before_events = ChronosLedger(str(root / "chronos" / "empire.jsonl")).events()
            with self.assertRaisesRegex(RuntimeError, "current manifest"):
                bridge.run(apply=False)
            after_events = ChronosLedger(str(root / "chronos" / "empire.jsonl")).events()
            self.assertEqual(before_events, after_events)

    def test_missing_latest_sidecar_fails_closed_before_next_run(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            first = bridge.run(apply=False)
            sidecar = root / "receipts" / f"{first.control_plane.receipt_id}.json"
            sidecar.unlink()

            before_count = len(ChronosLedger(str(root / "chronos" / "empire.jsonl")).events())
            with self.assertRaisesRegex(RuntimeError, "sidecar receipt is missing"):
                bridge.run(apply=False)
            after_count = len(ChronosLedger(str(root / "chronos" / "empire.jsonl")).events())
            self.assertEqual(before_count, after_count)

    def test_tampered_latest_sidecar_fails_closed_before_next_run(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            bridge = self.make_bridge(root, manifest)
            first = bridge.run(apply=False)
            sidecar = root / "receipts" / f"{first.control_plane.receipt_id}.json"
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
            payload["manifest_hash_after"] = "0" * 64
            sidecar.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "sidecar manifest_hash_after"):
                bridge.run(apply=False)


if __name__ == "__main__":
    unittest.main()
