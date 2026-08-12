"""Deterministic tests for Dev-Ville's evidence-producing machine-labor organs."""
from __future__ import annotations

from datetime import datetime, timezone
import tempfile
import unittest

from beta_organ import ExecutableBetaOrgan
from evidence_confidence import ConfidenceCalibrator, EvidenceItem
from research_organ import EvidenceResearchOrgan, TechnologyProbe
from trace0_chronos import ChronosLedger, Trace0Observer


GOOD_BACKEND = '''
class BackendService:
    def __init__(self):
        self.data = {}
        self.started = False
    def start(self):
        self.started = True
        return True
    def process_request(self, method, path, data=None):
        key = path.strip("/")
        if method == "POST":
            self.data[key] = dict(data or {})
            return {"status": 201}
        if method == "GET":
            return {"status": 200, "data": self.data[key]} if key in self.data else {"status": 404}
        return {"status": 405}
    def health_check(self):
        return {"status": "healthy" if self.started else "stopped"}
if __name__ == "__main__":
    service = BackendService()
    assert service.start()
    assert service.process_request("POST", "/x", {"v": 1})["status"] == 201
'''

GOOD_TEST = '''
import unittest
from backend_demo import BackendService
class BackendTests(unittest.TestCase):
    def test_round_trip(self):
        svc = BackendService()
        self.assertTrue(svc.start())
        self.assertEqual(svc.process_request("POST", "/x", {"v": 1})["status"], 201)
        self.assertEqual(svc.process_request("GET", "/x")["data"]["v"], 1)
if __name__ == "__main__":
    unittest.main()
'''

GOOD_FRONTEND = '''
class FrontendController:
    def __init__(self):
        self.initialized = False
    def initialize(self):
        self.initialized = True
        return True
    def render_view(self, name, data=None):
        assert self.initialized
        return {"view": name, "data": data or {}}
if __name__ == "__main__":
    c = FrontendController()
    assert c.initialize()
    assert c.render_view("home")["view"] == "home"
'''

BAD_BACKEND = GOOD_BACKEND.replace('return {"status": 201}', 'return {"status": 500}', 1)


class ConfidenceTests(unittest.TestCase):
    def test_refuses_fake_probability_before_calibration(self):
        c = ConfidenceCalibrator(min_samples=3, bins=2, min_bin_samples=2)
        item = EvidenceItem("claim", "source", True, 1, 1, 1, 1)
        result = c.evaluate([item])
        self.assertIsNone(result.confidence)
        self.assertEqual(result.calibration_status, "uncalibrated")

    def test_refuses_sparse_local_bin_after_global_minimum(self):
        c = ConfidenceCalibrator(min_samples=4, bins=2, min_bin_samples=2)
        c.record_resolution(0.1, True)
        c.record_resolution(0.2, True)
        c.record_resolution(0.3, False)
        c.record_resolution(0.9, True)
        item = EvidenceItem("claim", "source", True, 1, 1, 1, 1)
        result = c.evaluate([item])
        self.assertIsNone(result.confidence)
        self.assertEqual(result.calibration_status, "insufficient_local_bin")
        self.assertEqual(result.local_bin_samples, 1)

    def test_emits_empirical_confidence_after_resolution_history(self):
        c = ConfidenceCalibrator(min_samples=3, bins=2, min_bin_samples=3)
        c.record_resolution(0.9, True)
        c.record_resolution(0.8, True)
        c.record_resolution(0.7, False)
        item = EvidenceItem("claim", "source", True, 1, 1, 1, 1)
        result = c.evaluate([item])
        self.assertEqual(result.calibration_status, "empirically_calibrated")
        self.assertEqual(result.local_bin_samples, 3)
        self.assertAlmostEqual(result.confidence, 2 / 3, places=6)
        self.assertIsNotNone(result.confidence_interval_95)
        low, high = result.confidence_interval_95
        self.assertLess(low, result.confidence)
        self.assertGreater(high, result.confidence)


class ResearchTests(unittest.TestCase):
    def test_research_uses_observed_probe_not_rng(self):
        probes = (
            TechnologyProbe("Python", "runtime", "python", ("api_service",)),
            TechnologyProbe("DefinitelyMissing", "executable", "__devville_missing_tool__", ("api_service",)),
        )
        organ = EvidenceResearchOrgan(ConfidenceCalibrator(min_samples=1), probes=probes)
        result = organ.research("api_service")
        self.assertEqual(result.recommendation, "Python")
        available = {x["technology"]: x["available"] for x in result.evidence}
        self.assertTrue(available["Python"])
        self.assertFalse(available["DefinitelyMissing"])
        self.assertEqual(result.calibration_status, "uncalibrated")


class TraceChronosTests(unittest.TestCase):
    def test_hash_chain_verifies(self):
        ledger = ChronosLedger()
        fixed = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        trace = Trace0Observer(ledger, clock=lambda: fixed)
        trace.observe(actor="a", action="one", entity_id="x", payload={"n": 1})
        trace.observe(actor="a", action="two", entity_id="x", payload={"n": 2})
        self.assertTrue(ledger.verify_chain())
        self.assertEqual(len(ledger.events()), 2)
        self.assertEqual(ledger.events()[1]["parent_event_hash"], ledger.receipts()[0]["event_hash"])

    def test_jsonl_restarts_with_same_chain_head(self):
        fixed = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/chronos.jsonl"
            ledger = ChronosLedger(path)
            trace = Trace0Observer(ledger, clock=lambda: fixed)
            trace.observe(actor="a", action="one", entity_id="x", payload={"n": 1})
            head = ledger.last_chain_hash
            reloaded = ChronosLedger(path)
            self.assertTrue(reloaded.verify_chain())
            self.assertEqual(reloaded.last_chain_hash, head)
            Trace0Observer(reloaded, clock=lambda: fixed).observe(
                actor="a", action="two", entity_id="x", payload={"n": 2}
            )
            self.assertEqual(len(reloaded.events()), 2)


class ExecutableBetaTests(unittest.TestCase):
    def setUp(self):
        self.beta = ExecutableBetaOrgan(timeout_seconds=5)

    def test_real_beta_passes_good_artifacts(self):
        receipt = self.beta.run([
            {"filename": "backend_demo.py", "content": GOOD_BACKEND},
            {"filename": "test_backend_demo.py", "content": GOOD_TEST},
        ])
        self.assertTrue(receipt.passed, receipt.scenarios)
        self.assertIsNone(receipt.ux_score)
        self.assertEqual(len(receipt.evidence_sha256), 64)

    def test_real_beta_fails_broken_behavior(self):
        receipt = self.beta.run([
            {"filename": "backend_demo.py", "content": BAD_BACKEND},
            {"filename": "test_backend_demo.py", "content": GOOD_TEST},
        ])
        self.assertFalse(receipt.passed)
        self.assertTrue(any(s["name"] == "test_suite" and not s["passed"] for s in receipt.scenarios))

    def test_frontend_backend_e2e_is_executed(self):
        receipt = self.beta.run([
            {"filename": "frontend_demo.py", "content": GOOD_FRONTEND},
            {"filename": "backend_demo.py", "content": GOOD_BACKEND},
            {"filename": "test_backend_demo.py", "content": GOOD_TEST},
        ])
        e2e = next(s for s in receipt.scenarios if s["name"] == "frontend_backend_e2e")
        self.assertTrue(e2e["required"])
        self.assertTrue(e2e["passed"], e2e)

    def test_path_traversal_is_observed_failure(self):
        receipt = self.beta.run([{"filename": "../escape.py", "content": "print(1)"}])
        self.assertFalse(receipt.passed)
        self.assertEqual(receipt.scenarios[0]["name"], "artifact_safety")


if __name__ == "__main__":
    unittest.main(verbosity=2)
