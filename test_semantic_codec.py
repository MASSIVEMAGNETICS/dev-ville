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

    def test_benchmark(self):
        result = benchmark(self.rows)
        self.assertTrue(result["roundtrip_exact"])
        self.assertGreater(result["json_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
