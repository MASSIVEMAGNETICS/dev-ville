import hashlib
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
        for bad in ("\u005cud800", "\u005cudfff"):
            with self.subTest(bad=repr(bad)):
                rows = [{"subject": bad, "predicate": "observed", "object": "x"}]
                with self.assertRaisesRegex(ValueError, "valid UTF-8"):
                    encode(rows)

    def test_decode_rejects_escaped_lone_surrogate_as_valueerror(self):
        # Valid frame length and SHA: JSON parses but re-encoding cannot
        # represent this Unicode surrogate in canonical UTF-8.
        raw = b'[1,["\\\\ud800"],[[0,0,0]]]'
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(self._raw_frame(raw))

    def test_decode_rejects_invalid_utf8_as_valueerror(self):
        # Valid frame integrity does not imply the JSON bytes are UTF-8.
        raw = b'[1,["\\xff"],[[0,0,0]]]'
        with self.assertRaisesRegex(ValueError, "invalid semantic encoding"):
            decode(self._raw_frame(raw))

    def test_benchmark(self):
        result = benchmark(self.rows)
        self.assertTrue(result["roundtrip_exact"])
        self.assertGreater(result["json_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
