import hashlib
import json
import struct
import unittest
import zlib
from unittest.mock import patch
from semantic_codec import benchmark, decode, encode

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

    def test_reject_oversized_matrix_before_record_expansion(self):
        # Valid digest and length: small compressed input with 100001 triples.
        raw = b'[1,["x"],[' + b'[0,0,0],' * 100000 + b'[0,0,0]]]'
        frame = b"VSG1" + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)
        self.assertLess(len(frame), 2000)
        with patch("semantic_codec.validate", side_effect=AssertionError("record expansion reached")):
            with self.assertRaises(ValueError):
                decode(frame)

    def test_maximum_matrix_count_still_roundtrips(self):
        row = {"subject": "x", "predicate": "x", "object": "x"}
        self.assertEqual(len(decode(encode([row] * 100000))), 100000)

    def _raw_frame(self, raw):
        return b"VSG1" + struct.pack(">I", len(raw)) + hashlib.sha256(raw).digest() + zlib.compress(raw, 9)

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

    def test_nested_malformed_payload_fails_closed(self):
        raw = b'[1,[],' + b'[' * 12000 + b'0' + b']' * 12000 + b']'
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(self._raw_frame(raw))

    def test_encode_rejects_lone_surrogates_as_valueerror(self):
        for bad in ("\ud800", "\udfff"):
            with self.subTest(bad=repr(bad)):
                rows = [{"subject": bad, "predicate": "observed", "object": "x"}]
                with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                    encode(rows)

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

    def test_benchmark(self):
        result = benchmark(self.rows)
        self.assertTrue(result["roundtrip_exact"])
        self.assertGreater(result["json_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
