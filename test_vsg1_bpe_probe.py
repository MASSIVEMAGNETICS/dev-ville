"""Regression tests for the train-only synthetic BPE evaluation probe."""
import unittest

from vsg1_bpe_probe import (
    apply_merge, detokenize, run_probe, tokenize, train_bpe,
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
        self.assertFalse(first["real_events"])
        self.assertFalse(first["semantic_accuracy_measured"])
        self.assertFalse(first["model_is_semantic"])
        self.assertGreaterEqual(first["bpe_total_bytes_including_model"],
                                first["heldout_bpe_zlib_token_bytes"])

    def test_invalid_group_count_rejected(self):
        with self.assertRaises(ValueError):
            run_probe(16, 8)


if __name__ == "__main__":
    unittest.main()
