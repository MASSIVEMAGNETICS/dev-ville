from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from victor_adapter import CAPABILITY, ContractError, JOB_SCHEMA, RECEIPT_SCHEMA, run_job, validate_job


def valid_job() -> dict:
    return {
        "schema": JOB_SCHEMA,
        "organ": "dev-ville",
        "job_id": "job-test-001",
        "work_order_id": "wo-test-001",
        "lease_id": "lease-test-001",
        "capability": CAPABILITY,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "directive": "Create a minimal backend API with validation and tests",
        "limits": {
            "max_cycles": 500,
            "time_delta": 10.0,
            "max_files": 128,
            "max_total_bytes": 2_000_000,
        },
    }


class VictorAdapterTests(unittest.TestCase):
    def test_rejects_expired_lease(self) -> None:
        job = valid_job()
        job["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        with self.assertRaises(ContractError):
            validate_job(job)

    def test_rejects_unknown_capability(self) -> None:
        job = valid_job()
        job["capability"] = "shell.exec"
        with self.assertRaises(ContractError):
            validate_job(job)

    def test_rejects_unsafe_identifier(self) -> None:
        job = valid_job()
        job["job_id"] = "../../escape"
        with self.assertRaises(ContractError):
            validate_job(job)

    def test_end_to_end_receipt_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "organ-output"
            receipt = run_job(valid_job(), output_root)

            self.assertEqual(receipt["schema"], RECEIPT_SCHEMA)
            self.assertEqual(receipt["organ"], "dev-ville")
            self.assertEqual(receipt["capability"], CAPABILITY)
            self.assertEqual(receipt["work_order_id"], "wo-test-001")
            self.assertEqual(receipt["lease_id"], "lease-test-001")
            self.assertEqual(receipt["status"], "completed")
            self.assertGreaterEqual(receipt["project"]["progress"], 100.0)
            self.assertGreater(len(receipt["artifacts"]), 0)

            receipt_path = Path(receipt["receipt_path"])
            self.assertTrue(receipt_path.is_file())
            stored = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["receipt_hash"], receipt["receipt_hash"])

            run_dir = receipt_path.parent
            for artifact in receipt["artifacts"]:
                path = (run_dir / artifact["path"]).resolve()
                path.relative_to(output_root.resolve())
                self.assertTrue(path.is_file())
                self.assertEqual(path.stat().st_size, artifact["bytes"])


if __name__ == "__main__":
    unittest.main()
