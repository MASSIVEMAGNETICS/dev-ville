import unittest
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
    def test_benchmark(self):
        result = benchmark(self.rows)
        self.assertTrue(result["roundtrip_exact"])
        self.assertGreater(result["json_bytes"], 0)

if __name__ == "__main__":
    unittest.main()
