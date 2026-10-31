"""Deterministic lossless structural representation experiment; no neural claims."""
from __future__ import annotations
import hashlib
import json
import struct
import zlib

MAGIC = b"VSG1"
MAX_BYTES = 8_000_000

def _json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def validate(records):
    if not isinstance(records, list) or len(records) > 100000:
        raise ValueError("records must be a list of at most 100000 triples")
    for row in records:
        if not isinstance(row, dict) or set(row) != {"subject", "predicate", "object"}:
            raise ValueError("record must contain exactly subject, predicate, object")
        if any(not isinstance(v, str) or len(v) > 10000 for v in row.values()):
            raise ValueError("record values must be strings <= 10000 characters")

def encode(records):
    validate(records)
    symbols = sorted({v for row in records for v in row.values()})
    indexes = {v: i for i, v in enumerate(symbols)}
    matrix = [[indexes[row[k]] for k in ("subject", "predicate", "object")] for row in records]
    packed = _json([1, symbols, matrix])
    if len(packed) > MAX_BYTES:
        raise ValueError("uncompressed payload too large")
    return MAGIC + struct.pack(">I", len(packed)) + hashlib.sha256(packed).digest() + zlib.compress(packed, level=9)

def decode(payload):
    if not isinstance(payload, bytes) or len(payload) < 40 or payload[:4] != MAGIC:
        raise ValueError("invalid codec payload")
    length = struct.unpack(">I", payload[4:8])[0]
    if length > MAX_BYTES:
        raise ValueError("payload exceeds limit")
    decompressor = zlib.decompressobj()
    try:
        raw = decompressor.decompress(payload[40:], length + 1)
        if len(raw) != length or not decompressor.eof or decompressor.unused_data or decompressor.unconsumed_tail:
            raise ValueError("corrupt or trailing payload")
    except zlib.error as exc:
        raise ValueError("invalid compressed payload") from exc
    if hashlib.sha256(raw).digest() != payload[8:40]:
        raise ValueError("integrity check failed")
    try:
        version, symbols, matrix = json.loads(raw)
        if version != 1 or not isinstance(symbols, list) or symbols != sorted(set(symbols)):
            raise ValueError("invalid symbol table")
        if not isinstance(matrix, list) or len(matrix) > 100000:
            # Reject oversized matrices before allocating one dict per triple.
            raise ValueError("invalid matrix")
        if any(not isinstance(triple, list) or len(triple) != 3 or any(not isinstance(i, int) or isinstance(i, bool) or i < 0 or i >= len(symbols) for i in triple) for triple in matrix):
            raise ValueError("invalid matrix indexes")
        rows = [{k: symbols[idx] for k, idx in zip(("subject", "predicate", "object"), triple)} for triple in matrix]
        validate(rows)
        if encode(rows) != payload:
            raise ValueError("noncanonical payload")
        return rows
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise ValueError("invalid semantic encoding") from exc

def benchmark(records):
    validate(records)
    raw = _json(records)
    baseline = zlib.compress(raw, level=9)
    proposed = encode(records)
    return {
        "records": len(records),
        "json_bytes": len(raw),
        "zlib_json_bytes": len(baseline),
        "semantic_codec_bytes": len(proposed),
        "ratio_vs_json": round(len(proposed) / max(1, len(raw)), 4),
        "ratio_vs_zlib_json": round(len(proposed) / max(1, len(baseline)), 4),
        "roundtrip_exact": decode(proposed) == records,
    }
