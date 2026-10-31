"""Regression contracts for fail-closed Chronos JSONL persistence.

An I/O failure may have written a complete or partial record. The original
ledger instance must not retry from stale in-memory state; a new instance
must replay the on-disk chain before further writes.
"""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from trace0_chronos import ChronosLedger, Trace0Observer


def observe(ledger):
    return Trace0Observer(
        ledger, clock=lambda: datetime(2026, 10, 31, tzinfo=timezone.utc)
    ).observe(actor="victor.test", action="observation", entity_id="synthetic",
              evidence={"kind": "synthetic_test_only"})


class ChronosPersistenceTests(unittest.TestCase):
    def test_successful_append_survives_reopen(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "nested" / "chronos.jsonl"
            ledger = ChronosLedger(str(path))
            event, receipt = observe(ledger)
            restored = ChronosLedger(str(path))
            self.assertTrue(restored.verify_chain())
            self.assertEqual(restored.events()[0], event.to_dict())
            self.assertEqual(restored.receipts()[0], receipt.to_dict())

    def test_open_failure_does_not_advance_chain_and_blocks_retry(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            ledger = ChronosLedger(str(path))
            with patch.object(Path, "open", side_effect=OSError("read-only disk")):
                with self.assertRaises(OSError):
                    observe(ledger)
            self.assertEqual(ledger.events(), [])
            self.assertIsNone(ledger.last_chain_hash)
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                observe(ledger)
            fresh = ChronosLedger(str(path))
            observe(fresh)
            self.assertTrue(ChronosLedger(str(path)).verify_chain())

    def test_fsync_failure_quarantines_instance_even_if_line_exists(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            ledger = ChronosLedger(str(path))
            with patch("trace0_chronos.os.fsync", side_effect=OSError("I/O error")):
                with self.assertRaises(OSError):
                    observe(ledger)
            self.assertEqual(ledger.events(), [])
            self.assertIsNone(ledger.last_chain_hash)
            self.assertTrue(path.exists())
            with self.assertRaisesRegex(RuntimeError, "uncertain"):
                observe(ledger)
            fresh = ChronosLedger(str(path))
            self.assertTrue(fresh.verify_chain())
            self.assertEqual(len(fresh.events()), 1)
            observe(fresh)
            self.assertEqual(len(ChronosLedger(str(path)).events()), 2)

    def test_failed_second_append_preserves_prior_memory_head(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            ledger = ChronosLedger(str(path))
            observe(ledger)
            prior_head = ledger.last_chain_hash
            with patch("trace0_chronos.os.fsync", side_effect=OSError("I/O error")):
                with self.assertRaises(OSError):
                    observe(ledger)
            self.assertEqual(len(ledger.events()), 1)
            self.assertEqual(ledger.last_chain_hash, prior_head)
            with self.assertRaises(RuntimeError):
                observe(ledger)
            replay = ChronosLedger(str(path))
            self.assertEqual(len(replay.events()), 2)
            self.assertTrue(replay.verify_chain())

    def test_short_write_is_not_treated_as_committed(self):
        with TemporaryDirectory() as root:
            ledger = ChronosLedger(str(Path(root) / "chronos.jsonl"))
            handle = MagicMock()
            handle.__enter__.return_value.write.return_value = 0
            with patch.object(Path, "open", return_value=handle):
                with self.assertRaisesRegex(OSError, "short Chronos"):
                    observe(ledger)
            self.assertEqual(ledger.events(), [])
            with self.assertRaises(RuntimeError):
                observe(ledger)

    def test_memory_only_ledger_does_not_require_fsync(self):
        ledger = ChronosLedger()
        with patch("trace0_chronos.os.fsync", side_effect=AssertionError("unexpected")):
            observe(ledger)
        self.assertEqual(len(ledger.events()), 1)
        self.assertTrue(ledger.verify_chain())


if __name__ == "__main__":
    unittest.main()
