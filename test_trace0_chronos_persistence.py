"""Regression contracts for fail-closed Chronos JSONL persistence.

An I/O failure may have written a complete or partial record. The original
ledger instance must not retry from stale in-memory state; a new instance
must replay the on-disk chain before further writes.
"""
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import json
import multiprocessing
from unittest.mock import MagicMock, patch

from trace0_chronos import ChronosLedger, Trace0Observer


def observe(ledger, actor="victor.test"):
    return Trace0Observer(
        ledger, clock=lambda: datetime(2026, 10, 31, tzinfo=timezone.utc)
    ).observe(actor=actor, action="observation", entity_id="synthetic",
              evidence={"kind": "synthetic_test_only"})


def _append_from_process(path, barrier, results, actor):
    ledger = ChronosLedger(path)
    observer = Trace0Observer(
        ledger, clock=lambda: datetime(2026, 10, 31, tzinfo=timezone.utc)
    )
    barrier.wait(timeout=20)
    event, receipt = observer.observe(
        actor=actor,
        action="concurrent_observation",
        entity_id=actor,
        evidence={"kind": "synthetic_multiprocess_test"},
    )
    results.put((event.sequence, event.event_id, receipt.chain_hash))


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
            original_open = Path.open
            def fail_ledger_open(target, *args, **kwargs):
                if target == path:
                    raise OSError("read-only disk")
                return original_open(target, *args, **kwargs)
            with patch.object(Path, "open", new=fail_ledger_open):
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
            original_open = Path.open
            def short_ledger_write(target, *args, **kwargs):
                if target == ledger.jsonl_path:
                    return handle
                return original_open(target, *args, **kwargs)
            with patch.object(Path, "open", new=short_ledger_write):
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


    def test_unterminated_but_valid_json_record_is_rejected_without_rewrite(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            observe(ChronosLedger(str(path)))
            path.write_bytes(path.read_bytes()[:-1])  # simulate lost final newline
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "unterminated record"):
                ChronosLedger(str(path))
            self.assertEqual(path.read_bytes(), before)

    def test_blank_record_is_not_silently_skipped(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            observe(ChronosLedger(str(path)))
            with path.open("ab") as handle:
                handle.write(b"\n")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "empty record at line 2"):
                ChronosLedger(str(path))
            self.assertEqual(path.read_bytes(), before)

    def test_partial_json_tail_fails_closed_without_truncation(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            observe(ChronosLedger(str(path)))
            with path.open("ab") as handle:
                handle.write(b'{"event":')
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "unterminated record"):
                ChronosLedger(str(path))
            self.assertEqual(path.read_bytes(), before)

    def test_complete_crlf_terminated_record_remains_readable(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            event, receipt = observe(ChronosLedger(str(path)))
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            replay = ChronosLedger(str(path))
            self.assertTrue(replay.verify_chain())
            self.assertEqual(replay.events()[0], event.to_dict())
            self.assertEqual(replay.receipts()[0], receipt.to_dict())


    def test_receipt_tampering_rejected_without_mutating_evidence(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            observe(ChronosLedger(str(path)))
            record = json.loads(path.read_text(encoding="utf-8"))
            record["receipt"]["chain_hash"] = "0" * 64
            path.write_text(json.dumps(record) + "\n", encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                ChronosLedger(str(path))
            self.assertEqual(path.read_bytes(), before)

    def test_valid_two_record_chain_replays_without_modification(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            ledger = ChronosLedger(str(path))
            observe(ledger)
            observe(ledger)
            before = path.read_bytes()
            restored = ChronosLedger(str(path))
            self.assertTrue(restored.verify_chain())
            self.assertEqual(len(restored.receipts()), 2)
            self.assertEqual(restored.last_chain_hash, ledger.last_chain_hash)
            self.assertEqual(path.read_bytes(), before)

    def test_stale_writer_refreshes_before_append(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            first = ChronosLedger(str(path))
            stale = ChronosLedger(str(path))
            observe(first, actor="writer.first")
            event, _ = observe(stale, actor="writer.stale")
            replay = ChronosLedger(str(path))
            self.assertEqual(event.sequence, 2)
            self.assertEqual([row["sequence"] for row in replay.events()], [1, 2])
            self.assertTrue(replay.verify_chain())

    def test_multiple_processes_serialize_stale_writers(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            observe(ChronosLedger(str(path)), actor="writer.seed")
            context = multiprocessing.get_context("spawn")
            barrier = context.Barrier(2)
            results = context.Queue()
            processes = [
                context.Process(target=_append_from_process, args=(str(path), barrier, results, f"writer.{index}"))
                for index in range(2)
            ]
            try:
                for process in processes:
                    process.start()
                for process in processes:
                    process.join(timeout=30)
                self.assertFalse(any(process.is_alive() for process in processes), "writer process timed out")
                self.assertEqual([process.exitcode for process in processes], [0, 0])
                rows = [results.get(timeout=5) for _ in processes]
                self.assertEqual(sorted(row[0] for row in rows), [2, 3])
                self.assertEqual(len({row[1] for row in rows}), 2)
                replay = ChronosLedger(str(path))
                self.assertTrue(replay.verify_chain())
                self.assertEqual([row["sequence"] for row in replay.events()], [1, 2, 3])
            finally:
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                        process.join()
                results.close()
                results.join_thread()

    def test_stale_writer_rejects_truncated_disk_prefix_without_repair(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            writer = ChronosLedger(str(path))
            observe(writer)
            stale = ChronosLedger(str(path))
            path.write_bytes(b"")
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "immutable prefix changed"):
                observe(stale, actor="writer.after_truncate")
            self.assertEqual(path.read_bytes(), before)

    def test_persisted_ledger_rejects_unpersisted_snapshot_restore(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "chronos.jsonl"
            source = ChronosLedger()
            observe(source)
            persisted = ChronosLedger(str(path))
            persisted.restore(source.events(), source.receipts())
            with self.assertRaisesRegex(RuntimeError, "memory-only ledger"):
                observe(persisted, actor="writer.invalid_restore")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
