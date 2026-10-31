import hashlib
import json
import struct
import unittest
from unittest.mock import patch
import zlib
from semantic_codec import MAGIC, MAX_FRAME_BYTES, benchmark, decode, encode

class CodecTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"subject": "victor", "predicate": "observed", "object": f"event-{i % 7}"} for i in range(200)]
    def test_roundtrip(self):
        self.assertEqual(decode(encode(self.rows)), self.rows)
    def test_deterministic(self):
        self.assertEqual(encode(self.rows), encode(self.rows))
    def test_unicode(self):
        rows = [{"subject": "Δ", "predicate": "relates", "object": "🧠"}]
        self.assertEqual(decode(encode(rows)), rows)
    def test_empty(self):
        self.assertEqual(decode(encode([])), [])
    def test_bad_schema(self):
        with self.assertRaises(ValueError):
            encode([{"subject": "x"}])
    def test_bitflip(self):
        payload = bytearray(encode(self.rows))
        payload[-3] ^= 1
        with self.assertRaises(ValueError):
            decode(bytes(payload))
    def test_trailing_bytes(self):
        with self.assertRaises(ValueError):
            decode(encode(self.rows) + b"x")
    def test_benchmark(self):
        result = benchmark(self.rows)
        self.assertTrue(result["roundtrip_exact"])
        self.assertGreater(result["json_bytes"], 0)

    def _frame(self, document):
        raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
        return MAGIC + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)

    def test_deeply_nested_json_fails_closed(self):
        # Well below MAX_BYTES, but deep enough to exceed CPython JSON
        # decoder recursion limits. The public API must raise ValueError.
        raw = b"[1,[]," + b"[" * 12000 + b"0" + b"]" * 12000 + b"]"
        frame = MAGIC + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(frame)

    def test_invalid_unicode_rejected_before_serialization(self):
        rows = [{"subject": "\ud800", "predicate": "observed", "object": "x"}]
        with self.assertRaises(ValueError):
            encode(rows)

    def test_oversized_compressed_frame_rejected(self):
        with self.assertRaises(ValueError):
            decode(encode([]) + b"x" * MAX_FRAME_BYTES)

    def test_declared_size_smaller_than_compressed_input_rejected(self):
        frame = bytearray(encode([]))
        frame[4:8] = struct.pack(">I", 1)
        with self.assertRaises(ValueError):
            decode(bytes(frame))

    def test_duplicate_symbol_table_rejected(self):
        with self.assertRaises(ValueError):
            decode(self._frame([1, ["x", "x"], [[0, 0, 0]]]))

    def test_non_string_symbol_rejected(self):
        with self.assertRaises(ValueError):
            decode(self._frame([1, ["x", 7], [[0, 0, 0]]]))

    def test_oversized_matrix_rejected_before_row_materialization(self):
        with self.assertRaises(ValueError):
            decode(self._frame([1, ["x"], [[0, 0, 0]] * 100001]))

    def test_high_compression_matrix_bomb_preflight(self):
        # Regression for the independent PR #36 P2 finding: a ~12 KiB
        # compressed frame could expand into almost a million Python dicts.
        # The stacked decoder must reject before even calling json.loads.
        from semantic_codec import MAX_RECORDS
        raw = b'[1,["x"],[' + b'[0,0,0],' * MAX_RECORDS + b'[0,0,0]]]'
        frame = MAGIC + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)
        with patch("semantic_codec.json.loads", side_effect=AssertionError("JSON object allocation attempted")):
            with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
                decode(frame)

    def test_matrix_preflight_preserves_escaped_symbols(self):
        # Force the large-input preflight on valid canonical data containing
        # JSON punctuation and escaped quotes inside a symbol.
        rows = [{"subject": 'x[\\\\\\",],', "predicate": "observed", "object": "ok"} for _ in range(20000)]
        self.assertEqual(decode(encode(rows)), rows)

    def test_bool_index_rejected(self):
        with self.assertRaises(ValueError):
            decode(self._frame([1, ["x"], [[True, 0, 0]]]))

    def test_non_integer_version_rejected(self):
        for version in (True, 1.0):
            with self.subTest(version=version):
                with self.assertRaises(ValueError):
                    decode(self._frame([version, [], []]))

    def test_noncanonical_extra_symbol_rejected(self):
        with self.assertRaises(ValueError):
            decode(self._frame([1, ["unused", "x"], [[1, 1, 1]]]))

if __name__ == "__main__":
    unittest.main()
