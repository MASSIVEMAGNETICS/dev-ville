"""Regression tests for the train-only synthetic BPE evaluation probe."""
import unittest
import struct
import zlib

from vsg1_bpe_probe import (
    apply_merge, decode_packed_tokens, detokenize, read_merge_table,
    run_probe, tokenize, train_bpe,
)


class SyntheticBPEProbeTests(unittest.TestCase):
    def test_pair_merge_is_nonoverlapping(self):
        self.assertEqual(apply_merge([65, 65, 65], (65, 65), 256), [256, 65])

    def test_training_is_deterministic_and_reversible(self):
        training = [b"banana banana", b"banana bandana"]
        first = train_bpe(training, 12)
        self.assertEqual(first, train_bpe(training, 12))
        unseen = b"bandana banana!\x00\xff"
        self.assertEqual(detokenize(tokenize(unseen, first), first), unseen)

    def test_zero_merge_baseline(self):
        self.assertEqual(train_bpe([b"hello"], 0), ())
        self.assertEqual(tokenize(b"hello", ()), list(b"hello"))
        self.assertEqual(detokenize(list(b"hello"), ()), b"hello")

    def test_invalid_training_and_model_rejected(self):
        for docs in ([], [b""], ["text"], None):
            with self.subTest(docs=docs), self.assertRaises(ValueError):
                train_bpe(docs)
        for budget in (-1, 129, True, 1.0):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                train_bpe([b"hello"], budget)
        with self.assertRaises(ValueError):
            detokenize([256], ())
        with self.assertRaises(ValueError):
            detokenize([256], ((256, 0),))

    def test_mission_disjoint_holdout_is_reproducible(self):
        first = run_probe(32, 12)
        second = run_probe(32, 12)
        self.assertEqual(first, second)
        self.assertEqual(first["train_records"] + first["test_records"], 32)
        self.assertEqual(first["train_missions"], 1)
        self.assertEqual(first["test_missions"], 1)
        self.assertTrue(first["exact_heldout_recovery"])
        self.assertTrue(first["serialized_frame_recovery_verified"])
        self.assertFalse(first["real_events"])
        self.assertFalse(first["semantic_accuracy_measured"])
        self.assertFalse(first["model_is_semantic"])
        self.assertGreaterEqual(first["bpe_total_bytes_including_model"],
                                first["heldout_bpe_zlib_token_bytes"])

    def test_serialized_frame_round_trip(self):
        merges = train_bpe([b"banana banana", b"bandana banana"], 12)
        raw = b"banana bandana!\x00\xff"
        model = b"".join(struct.pack(">HH", *pair) for pair in merges)
        restored_model = read_merge_table(model)
        self.assertEqual(restored_model, merges)
        tokens = tokenize(raw, merges)
        packed = b"".join(struct.pack(">H", item) for item in tokens)
        self.assertEqual(decode_packed_tokens(zlib.compress(packed), restored_model), raw)

    def test_reject_invalid_serialized_model(self):
        for raw in (None, "not bytes", b"\x00", b"\x01\x00\x00\x00",
                    b"\x00" * 516):
            with self.subTest(raw=repr(raw)[:30]), self.assertRaises(ValueError):
                read_merge_table(raw)

    def test_reject_truncated_trailing_and_invalid_token_frames(self):
        valid = zlib.compress(b"\x00\x01\x00\x02")
        invalid = (valid[:-1], valid + b"garbage", valid + valid,
                   zlib.compress(b"\x00"),
                   zlib.compress(b"\x02\x00"),
                   b"not zlib", None)
        for frame in invalid:
            with self.subTest(frame=repr(frame)[:30]), self.assertRaises(ValueError):
                decode_packed_tokens(frame, ())

    def test_reject_decompression_expansion_bomb(self):
        oversized = zlib.compress(b"\x00" * 8_000_001, level=9)
        with self.assertRaises(ValueError):
            decode_packed_tokens(oversized, ())

    def test_invalid_group_count_rejected(self):
        with self.assertRaises(ValueError):
            run_probe(16, 8)


if __name__ == "__main__":
    unittest.main()
