"""Contracts for a non-sensitive, end-to-end Chronos/VSG1 comparison."""
import json
import unittest

from semantic_codec import decode, encode
from vsg1_event_benchmark import (PREDICATE, fixture_records, from_triples,
                                  run_benchmark, to_triples, verify_records)


class VSG1EventBenchmarkTests(unittest.TestCase):
    def test_fixture_deterministic_and_receipts_valid(self):
        first = fixture_records(8)
        self.assertEqual(first, fixture_records(8))
        self.assertEqual(verify_records(first), first)
        self.assertEqual(first[1]["event"]["parent_event_hash"], first[0]["receipt"]["event_hash"])

    def test_complete_event_receipt_roundtrip(self):
        records = fixture_records(12)
        self.assertEqual(from_triples(decode(encode(to_triples(records)))), records)

    def test_subject_mismatch_rejected(self):
        rows = to_triples(fixture_records(2))
        rows[0]["subject"] = "tampered"
        with self.assertRaises(ValueError):
            from_triples(rows)

    def test_receipt_tampering_rejected(self):
        records = fixture_records(3)
        records[0]["receipt"]["chain_hash"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_records(records)

    def test_noncanonical_embedded_json_rejected(self):
        rows = to_triples(fixture_records(1))
        rows[0]["object"] = json.dumps(json.loads(rows[0]["object"]), indent=2)
        with self.assertRaises(ValueError):
            from_triples(rows)

    def test_wrong_predicate_rejected(self):
        rows = to_triples(fixture_records(1))
        rows[0]["predicate"] = PREDICATE + "-altered"
        with self.assertRaises(ValueError):
            from_triples(rows)

    def test_all_three_methods_report_exact_roundtrip(self):
        report = run_benchmark(4, 1)
        self.assertFalse(report["corpus"]["real_events"])
        self.assertEqual(set(report["methods"]),
                         {"canonical_json", "zlib_json_9", "vsg1_full_record_adapter"})
        for result in report["methods"].values():
            self.assertTrue(result["roundtrip_exact"])
            self.assertTrue(result["chronos_chain_verified"])
            self.assertGreater(result["encoded_bytes"], 0)
            self.assertGreaterEqual(result["decode_and_verify"]["python_peak_kib"], 0)

    def test_bounded_fixture_and_repeats(self):
        for count in (0, -1, 1025, True, 1.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                fixture_records(count)
        for repeats in (0, 31, True, 1.0):
            with self.subTest(repeats=repeats), self.assertRaises(ValueError):
                run_benchmark(1, repeats)


if __name__ == "__main__":
    unittest.main()
