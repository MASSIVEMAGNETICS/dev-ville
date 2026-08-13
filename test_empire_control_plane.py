import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from empire_control_plane import EmpireAssessor, EmpireTopology, SelfCorrectingEmpire, Severity


class EmpireControlPlaneTests(unittest.TestCase):
    def write_manifest(self, root: Path, manifest: dict) -> Path:
        path = root / "empire_manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return path

    def test_dependency_order_and_duplicate_authority_detection(self):
        manifest = {"version": 1, "nodes": [
            {"id": "victor", "capability": "control", "status": "active", "canonical": True, "dependencies": []},
            {"id": "victor-shadow", "capability": "control", "status": "active", "canonical": True, "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "ready", "dependencies": ["victor"]},
        ]}
        topology = EmpireTopology(manifest)
        self.assertEqual(topology.dependency_order(), ["victor", "victor-shadow", "worker"])
        gaps = EmpireAssessor().assess(topology)
        duplicate = [gap for gap in gaps if gap.kind == "duplicate_authority"]
        self.assertEqual(len(duplicate), 1)
        self.assertEqual(duplicate[0].severity, Severity.HIGH)

    def test_missing_dependency_is_critical(self):
        manifest = {"version": 1, "nodes": [
            {"id": "revenue-worker", "capability": "revenue", "status": "blocked", "dependencies": ["commerce-adapter"]}
        ]}
        gaps = EmpireAssessor().assess(EmpireTopology(manifest))
        self.assertTrue(any(gap.kind == "missing_dependency" for gap in gaps))
        self.assertTrue(any(gap.severity == Severity.CRITICAL for gap in gaps))

    def test_cycle_is_detected(self):
        manifest = {"version": 1, "nodes": [
            {"id": "a", "capability": "a", "status": "active", "dependencies": ["b"]},
            {"id": "b", "capability": "b", "status": "active", "dependencies": ["a"]},
        ]}
        gaps = EmpireAssessor().assess(EmpireTopology(manifest))
        self.assertTrue(any(gap.kind == "dependency_cycle" for gap in gaps))

    def test_false_readiness_is_demoted_and_receipted(self):
        manifest = {"version": 1, "nodes": [
            {"id": "commerce", "capability": "commerce", "status": "planned", "dependencies": []},
            {"id": "revenue-worker", "capability": "revenue", "status": "active", "dependencies": ["commerce"]},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self.write_manifest(root, manifest)
            receipts = root / "receipts"
            receipt = SelfCorrectingEmpire(manifest_path, receipt_dir=receipts).run(apply=True)
            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            status = {node["id"]: node["status"] for node in updated["nodes"]}
            self.assertEqual(status["revenue-worker"], "blocked")
            self.assertTrue(any(item.changed for item in receipt.remediations))
            self.assertTrue((receipts / f"{receipt.receipt_id}.json").exists())

    def test_verified_promotion_requires_receipt(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "blocked", "dependencies": ["control"],
             "auto_fix": "promote_ready", "metadata": {"readiness_verified": True, "readiness_receipt": "verify:abc123"}},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self.write_manifest(root, manifest)
            receipt = SelfCorrectingEmpire(manifest_path, receipt_dir=root / "receipts").run(apply=True)
            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            status = {node["id"]: node["status"] for node in updated["nodes"]}
            self.assertEqual(status["worker"], "ready")
            self.assertLess(receipt.gaps_after, receipt.gaps_before)

    def test_unverified_promotion_is_refused(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "planned", "dependencies": ["control"], "auto_fix": "promote_ready"},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self.write_manifest(root, manifest)
            receipt = SelfCorrectingEmpire(manifest_path, receipt_dir=root / "receipts").run(apply=True)
            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            status = {node["id"]: node["status"] for node in updated["nodes"]}
            self.assertEqual(status["worker"], "planned")
            self.assertFalse(any(item.changed for item in receipt.remediations))
            self.assertTrue(any(gap.kind == "unverified_promotion" for gap in SelfCorrectingEmpire(manifest_path, receipt_dir=root / "receipts2").inspect()))

    def test_check_mode_does_not_mutate_manifest(self):
        manifest = {"version": 1, "nodes": [
            {"id": "control", "capability": "control", "status": "active", "dependencies": []},
            {"id": "worker", "capability": "execution", "status": "blocked", "dependencies": ["control"],
             "auto_fix": "promote_ready", "metadata": {"readiness_verified": True, "readiness_receipt": "verify:def456"}},
        ]}
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = self.write_manifest(root, manifest)
            before = manifest_path.read_text(encoding="utf-8")
            SelfCorrectingEmpire(manifest_path, receipt_dir=root / "receipts").run(apply=False)
            self.assertEqual(before, manifest_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
