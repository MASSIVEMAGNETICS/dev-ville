"""Deterministic lossless structural representation experiment; no neural claims."""
from __future__ import annotations
import hashlib
import json
import struct
import zlib

MAGIC = b"VSG1"
MAX_BYTES = 8_000_000
MAX_RECORDS = 100_000

def _compress_bound(size):
    """zlib compressBound upper bound for a size-byte input."""
    return size + (size >> 12) + (size >> 14) + (size >> 25) + 13

MAX_FRAME_BYTES = 40 + _compress_bound(MAX_BYTES)

def _json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")

def validate(records):
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError("records must be a list of at most 100000 triples")
    for row in records:
        if not isinstance(row, dict) or set(row) != {"subject", "predicate", "object"}:
            raise ValueError("record must contain exactly subject, predicate, object")
        for value in row.values():
            if not isinstance(value, str) or len(value) > 10000:
                raise ValueError("record values must be strings <= 10000 characters")
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("record strings must be valid UTF-8") from exc

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
    if length < 1 or length > MAX_BYTES or len(payload) > MAX_FRAME_BYTES:
        raise ValueError("payload exceeds limit")
    if len(payload) - 40 > _compress_bound(length):
        raise ValueError("compressed payload exceeds declared-size bound")
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
        if type(version) is not int or version != 1:
            raise ValueError("invalid version")
        if not isinstance(symbols, list) or len(symbols) > 3 * MAX_RECORDS:
            raise ValueError("invalid symbol table")
        if any(type(symbol) is not str or len(symbol) > 10000 for symbol in symbols):
            raise ValueError("invalid symbol table entry")
        if symbols != sorted(set(symbols)):
            raise ValueError("noncanonical symbol table")
        if not isinstance(matrix, list) or len(matrix) > MAX_RECORDS:
            raise ValueError("invalid matrix")
        if any(not isinstance(triple, list) or len(triple) != 3 or any(type(i) is not int or i < 0 or i >= len(symbols) for i in triple) for triple in matrix):
            raise ValueError("invalid matrix indexes")
        rows = [{k: symbols[idx] for k, idx in zip(("subject", "predicate", "object"), triple)} for triple in matrix]
        validate(rows)
        if encode(rows) != payload:
            raise ValueError("noncanonical payload")
        return rows
    except (ValueError, TypeError, IndexError, KeyError, RecursionError, OverflowError) as exc:
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
