# VSG1: Victor structural representation experiment

This is a **deterministic, reversible structural codec**, not a learned token successor or demonstrated improvement in reasoning. It is a prototype for subject/predicate/object records, using a sorted local symbol table with canonical JSON and zlib. The frame includes a version, SHA-256 integrity digest and 8 MB decompression limit. No network or external packages required.

Run: `python -m unittest -v test_semantic_codec.py`.

Benchmark: `from semantic_codec import benchmark` then `benchmark(records)`, comparing uncompressed canonical JSON, zlib(JSON), and VSG1. Use held-out, representative corpora; report task accuracy, lossless round-trip, sizes, latency, memory, energy and hardware. VSG1 can lose to zlib(JSON), especially on small or diverse corpora.

**Boundary:** This does not replace any neural model tokenization, Chronos canonical event data, or its provenance/authority receipts. A later adapter must keep complete source attribution, time and authority. SHA-256 detects corruption but is not signature authentication. No claims about intelligence or general superiority are established.
