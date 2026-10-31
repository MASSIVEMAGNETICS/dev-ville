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

    def _raw_frame(self, raw):
        return b"VSG1" + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)

    def test_trailing_bomb_rejected_before_zlib(self):
        # Review P2: small canonical frame plus large attacker-controlled
        # suffix must be rejected before a slice or zlib unused_data copy.
        frame = encode([])
        with patch("semantic_codec.zlib.decompressobj",
                   side_effect=AssertionError("zlib allocation reached")):
            with self.assertRaisesRegex(ValueError, "compressed payload exceeds declared-size bound"):
                decode(frame + b"x" * 100_000)

    def test_global_compressed_frame_cap_before_zlib(self):
        # Declare the maximum allowed decoded size and exceed the global
        # compressed cap, without creating an 8 MB test fixture.
        from semantic_codec import MAX_BYTES, MAX_FRAME_BYTES, _compress_bound
        self.assertEqual(MAX_FRAME_BYTES, 40 + _compress_bound(MAX_BYTES))
        frame = bytearray(encode([]))
        frame[4:8] = struct.pack(">I", MAX_BYTES)
        with patch("semantic_codec.MAX_FRAME_BYTES", len(frame) + 10):
            with patch("semantic_codec.zlib.decompressobj",
                       side_effect=AssertionError("zlib allocation reached")):
                with self.assertRaisesRegex(ValueError, "payload exceeds limit"):
                    decode(bytes(frame) + b"x" * 11)

    def test_high_entropy_canonical_frame_within_compress_bound(self):
        # A valid high-entropy symbol table must not be rejected by the
        # conservative zlib compressBound calculation.
        rows = [{"subject": hashlib.sha256(str(i).encode()).hexdigest(),
                 "predicate": "observed",
                 "object": hashlib.sha256(("event" + str(i)).encode()).hexdigest()}
                for i in range(2000)]
        frame = encode(rows)
        from semantic_codec import _compress_bound
        raw = zlib.decompress(frame[40:])
        self.assertLessEqual(len(frame) - 40, _compress_bound(len(raw)))
        self.assertEqual(decode(frame), rows)

    def test_maximum_matrix_count_still_roundtrips(self):
        row = {"subject": "x", "predicate": "x", "object": "x"}
        self.assertEqual(len(decode(encode([row] * 100000))), 100000)

    def test_parser_stage_empty_array_bomb_rejected_before_json_loads(self):
        # Independent P2 finding: ~8 MB expands from a <12 KB frame.
        # json.loads must not materialize 2.6 million empty arrays.
        raw = b'[1,["x"],[' + b'[],' * 2666662 + b'[]]]'
        self.assertEqual(len(raw), 8_000_000)
        frame = self._raw_frame(raw)
        self.assertLess(len(frame), 12_000)
        with patch("semantic_codec.json.loads", side_effect=AssertionError("parser allocation reached")):
            with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
                decode(frame)

    def test_oversized_symbol_table_rejected_before_json_loads(self):
        # Bound another source of pre-validation container amplification.
        raw = b'[1,[' + b'"",' * 300001 + b'"x"],[]]'
        with patch("semantic_codec.json.loads", side_effect=AssertionError("parser allocation reached")):
            with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
                decode(self._raw_frame(raw))

    def test_decode_rejects_escaped_lone_surrogate_as_valueerror(self):
        # Valid frame length and SHA: JSON parses but re-encoding cannot
        # represent this Unicode surrogate in canonical UTF-8.
        raw = b'[1,["\\ud800"],[[0,0,0]]]'
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(self._raw_frame(raw))

    def test_decode_rejects_invalid_utf8_as_valueerror(self):
        # Valid frame integrity does not imply the JSON bytes are UTF-8.
        raw = b'[1,["\xff"],[[0,0,0]]]'
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(self._raw_frame(raw))

    def test_reject_alternate_json_encodings_before_parser(self):
        # Python json.loads(bytes) auto-detects UTF-16/32, unlike the
        # byte-oriented preflight. Even escaped quotes must not bypass it.
        source = json.dumps([1, ['"'], [[0, 0, 0]]], separators=(",", ":"))
        for encoding in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            with self.subTest(encoding=encoding):
                frame = self._raw_frame(source.encode(encoding))
                with patch("semantic_codec.json.loads",
                           side_effect=AssertionError("parser allocation reached")):
                    with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
                        decode(frame)

    def test_large_utf16_matrix_bomb_rejected_before_parser(self):
        # The review's bypass uses alternate-encoded JSON and escaped
        # quotes. The compressed frame is tiny relative to its matrix.
        source = json.dumps([1, ['"'], [[]] * 100001], separators=(",", ":"))
        raw = source.encode("utf-16-le")
        self.assertGreater(len(raw), 128000)
        frame = self._raw_frame(raw)
        self.assertLess(len(frame), 12000)
        with patch("semantic_codec.json.loads",
                   side_effect=AssertionError("parser allocation reached")):
            with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
                decode(frame)

    def test_canonical_escaped_nul_symbol_still_roundtrips(self):
        rows = [{"subject": "\x00", "predicate": "observed", "object": "x"}]
        self.assertEqual(decode(encode(rows)), rows)

if __name__ == "__main__":
    unittest.main()
