"""Contracts for a non-sensitive, end-to-end Chronos/VSG1 comparison."""
import hashlib
import json
import unittest
import zlib
from unittest.mock import patch

from semantic_codec import decode, encode
from vsg1_event_benchmark import (PREDICATE, canonical_bytes, fixture_records,
                                  from_triples, json_decode, run_benchmark,
                                  synthetic_holdout_manifest,
                                  to_triples, verify_records, vsg1_event_decode,
                                  zlib_json_decode)


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

    def test_trusted_head_rejects_valid_but_wrong_snapshot(self):
        expected = fixture_records(3)[-1]["receipt"]["chain_hash"]
        other = fixture_records(4)
        self.assertEqual(verify_records(other), other)
        with self.assertRaisesRegex(ValueError, "trusted chain head mismatch"):
            verify_records(other, expected_chain_hash=expected)

    def test_all_decoders_enforce_pinned_head(self):
        records = fixture_records(3)
        expected = records[-1]["receipt"]["chain_hash"]
        variants = (
            (json_decode, canonical_bytes(records)),
            (zlib_json_decode, zlib.compress(canonical_bytes(records), 9)),
            (vsg1_event_decode, encode(to_triples(records))),
        )
        for decoder, payload in variants:
            with self.subTest(decoder=decoder.__name__):
                self.assertEqual(decoder(payload, expected_chain_hash=expected), records)
                with self.assertRaisesRegex(ValueError, "trusted chain head mismatch"):
                    decoder(payload, expected_chain_hash="0" * 64)

    def test_malformed_trusted_head_rejected(self):
        records = fixture_records(1)
        for anchor in ("", "g" * 64, "A" * 64, 7, True):
            with self.subTest(anchor=anchor), self.assertRaises(ValueError):
                verify_records(records, expected_chain_hash=anchor)

    def test_json_baseline_rejects_ambiguous_encodings(self):
        raw = canonical_bytes(fixture_records(1))
        duplicate_key = raw.replace(b'{"event":', b'{"event":null,"event":', 1)
        for malformed in (b" " + raw, raw + b" ", duplicate_key,
                          b'[{"event":NaN,"receipt":null}]'):
            with self.subTest(payload=malformed[:40]), self.assertRaises(ValueError):
                json_decode(malformed)
        for invalid_type in (None, raw.decode("utf-8"), bytearray(raw)):
            with self.subTest(type=type(invalid_type)), self.assertRaises(ValueError):
                json_decode(invalid_type)

    def test_zlib_baseline_rejects_trailing_truncated_and_corrupt_frames(self):
        payload = zlib.compress(canonical_bytes(fixture_records(1)), level=9)
        for malformed in (payload + b"trailing", payload[:-1], b"invalid-zlib"):
            with self.subTest(length=len(malformed)), self.assertRaises(ValueError):
                zlib_json_decode(malformed)

    def test_json_baselines_enforce_size_and_expansion_limits(self):
        raw = canonical_bytes(fixture_records(1))
        with patch("vsg1_event_benchmark.MAX_JSON_BYTES", 16):
            with self.assertRaisesRegex(ValueError, "oversized"):
                json_decode(raw)
        with patch("vsg1_event_benchmark.MAX_ZLIB_BYTES", 4):
            with self.assertRaisesRegex(ValueError, "oversized"):
                zlib_json_decode(zlib.compress(raw, 9))
        # A small compressed frame must not expand beyond the configured bound.
        with patch("vsg1_event_benchmark.MAX_JSON_BYTES", 64):
            with self.assertRaisesRegex(ValueError, "oversized decompressed"):
                zlib_json_decode(zlib.compress(b"x" * 65, 9))

    def test_all_three_methods_report_exact_roundtrip(self):
        report = run_benchmark(4, 1)
        self.assertFalse(report["corpus"]["real_events"])
        self.assertEqual(report["corpus"]["expected_chain_head"],
                         fixture_records(4)[-1]["receipt"]["chain_hash"])
        self.assertEqual(report["corpus"]["anchor_origin"],
                         "synthetic_fixture_pre_encoding_not_external_trust")
        self.assertEqual(set(report["methods"]),
                         {"canonical_json", "zlib_json_9", "vsg1_full_record_adapter"})
        for result in report["methods"].values():
            self.assertTrue(result["roundtrip_exact"])
            self.assertTrue(result["chronos_chain_verified"])
            self.assertTrue(result["expected_chain_head_matched"])
            self.assertGreater(result["encoded_bytes"], 0)
            self.assertGreaterEqual(result["decode_and_verify"]["python_peak_kib"], 0)

    def test_mission_holdout_is_deterministic_disjoint_and_traceable(self):
        records = fixture_records(128)
        first = synthetic_holdout_manifest(records)
        self.assertEqual(first, synthetic_holdout_manifest(fixture_records(128)))
        self.assertFalse(first["real_events"])
        self.assertTrue(first["source_chain_verified"])
        self.assertFalse(first["downstream_task_accuracy_measured"])
        self.assertEqual(first["partition_chain_verification"], "full_corpus_only")
        train, test = first["train"], first["test"]
        self.assertFalse(set(train["groups"]) & set(test["groups"]))
        self.assertEqual(len(train["groups"]) + len(test["groups"]), 8)
        self.assertEqual(train["records"] + test["records"], 128)
        self.assertEqual(first["source_corpus_sha256"],
                         hashlib.sha256(canonical_bytes(records)).hexdigest())
        self.assertEqual(first["source_chain_head"],
                         records[-1]["receipt"]["chain_hash"])
        for partition in (train, test):
            ids = [record["event"]["event_id"] for record in records
                   if any(edge.get("source") in partition["groups"]
                          for edge in record["event"]["payload"]["graph_mutations"])]
            self.assertEqual(partition["ordered_event_ids_sha256"],
                             hashlib.sha256(canonical_bytes(ids)).hexdigest())

    def test_holdout_rejects_single_group_and_tampered_chain(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            synthetic_holdout_manifest(fixture_records(16))
        records = fixture_records(32)
        records[0]["event"]["provenance"]["origin"] = "production"
        with self.assertRaises(ValueError):
            synthetic_holdout_manifest(records)

    def test_benchmark_artifact_contains_split_without_claiming_accuracy(self):
        report = run_benchmark(32, 1)
        split = report["evaluation_split"]
        self.assertEqual(split["protocol"], "synthetic_mission_disjoint_holdout_v1")
        self.assertFalse(split["downstream_task_accuracy_measured"])
        self.assertEqual(split["train"]["records"] + split["test"]["records"], 32)
        self.assertFalse(set(split["train"]["groups"]) & set(split["test"]["groups"]))
        small = run_benchmark(4, 1)["evaluation_split"]
        self.assertFalse(small["available"])
        self.assertFalse(small["real_events"])

    def test_bounded_fixture_and_repeats(self):
        for count in (0, -1, 1025, True, 1.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                fixture_records(count)
        for repeats in (0, 31, True, 1.0):
            with self.subTest(repeats=repeats), self.assertRaises(ValueError):
                run_benchmark(1, repeats)


if __name__ == "__main__":
    unittest.main()
