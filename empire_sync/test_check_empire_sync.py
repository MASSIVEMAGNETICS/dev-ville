"""Regression tests for strict Empire Sync frontier radar health receipts."""
import json
import unittest
from unittest.mock import patch

from empire_sync.check_empire_sync import evaluate_frontier_radar, validate_remote_surface


class FrontierRadarHealthTests(unittest.TestCase):
    def test_valid_radar(self):
        self.assertEqual(
            evaluate_frontier_radar({"healthy": True, "healthy_source_count": 3, "error_count": 0}),
            (True, "healthy=True sources=3 errors=0"),
        )

    def test_nonzero_errors(self):
        self.assertFalse(evaluate_frontier_radar({"healthy": True, "healthy_source_count": 3, "error_count": 8})[0])

    def test_insufficient_sources(self):
        self.assertFalse(evaluate_frontier_radar({"healthy": True, "healthy_source_count": 1, "error_count": 0})[0])

    def test_explicit_unhealthy(self):
        self.assertFalse(evaluate_frontier_radar({"healthy": False, "healthy_source_count": 3, "error_count": 0})[0])

    def test_invalid_roots(self):
        for radar in (None, [], "invalid", 3):
            with self.subTest(radar=radar):
                self.assertFalse(evaluate_frontier_radar(radar)[0])

    def test_invalid_counts(self):
        for key, value in (
            ("healthy_source_count", "3"),
            ("error_count", "0"),
            ("healthy_source_count", True),
            ("error_count", None),
        ):
            with self.subTest(key=key, value=value):
                data = {"healthy": True, "healthy_source_count": 3, "error_count": 0}
                data[key] = value
                self.assertFalse(evaluate_frontier_radar(data)[0])

    def test_missing_field(self):
        self.assertFalse(evaluate_frontier_radar({"healthy": True, "healthy_source_count": 3})[0])

    def test_invalid_healthy_type(self):
        self.assertFalse(evaluate_frontier_radar({"healthy": "true", "healthy_source_count": 3, "error_count": 0})[0])

    def test_remote_surface_records_malformed_radar_as_failure(self):
        blobs = {
            "store/sync-contract.json": json.dumps({"schema_version": "store-sync/1.0", "releases": []}).encode(),
            "store/assets/assets.json": json.dumps({
                "assets": [], "products": [],
                "storefront": {"checkout_state": "active", "canonical_path": "/store/"}
            }).encode(),
            "store/commerce.json": json.dumps({
                "status": "active", "catalog_skus": [], "canonical_path": "/store/"
            }).encode(),
            "proof/ledger.json": b"{}",
            "frontier-radar/data/status.json": json.dumps({
                "healthy": True, "healthy_source_count": "3", "error_count": "0"
            }).encode(),
            "store/index.html": b"<html></html>",
        }
        manifest = {
            "remote_surface": {
                "repository": "example/repo",
                "branch": "main",
                "required_paths": list(blobs),
            },
            "canonical_anchors": [],
        }
        checks = {}
        with patch(
            "empire_sync.check_empire_sync.remote_raw",
            side_effect=lambda _repo, _branch, path: blobs[path],
        ):
            validate_remote_surface(manifest, checks)
        self.assertTrue(checks["remote_surface_parse"]["ok"])
        self.assertTrue(checks["remote_surface_reachable"]["ok"])
        self.assertFalse(checks["frontier_radar_health"]["ok"])
        self.assertIn("invalid frontier radar field types", checks["frontier_radar_health"]["detail"])


if __name__ == "__main__":
    unittest.main()
