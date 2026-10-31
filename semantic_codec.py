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

MAX_RECORDS = 100_000
MAX_SYMBOLS = 3 * MAX_RECORDS

def _preflight_structure(raw):
    """Bound JSON container allocation before json.loads on untrusted frames.

    The canonical frame contains [version, symbols, matrix], with strings
    only in symbols and exactly one nested array per matrix row. This is a
    conservative lexical resource guard, not a replacement JSON parser.
    """
    if len(raw) <= 128_000:
        return
    depth = 0
    section = None
    root_commas = 0
    symbols_commas = 0
    matrix_commas = 0
    row_commas = 0
    matrix_rows = 0
    in_string = False
    escaped = False
    for byte in raw:
        if in_string:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                in_string = False
            continue
        if byte == 34:
            in_string = True
        elif byte == 91:
            depth += 1
            if depth > 3:
                raise ValueError("JSON nesting exceeds canonical structure")
            if depth == 2:
                if root_commas == 1:
                    section = "symbols"
                elif root_commas == 2:
                    section = "matrix"
                else:
                    raise ValueError("invalid root array")
            elif depth == 3:
                if section != "matrix":
                    raise ValueError("invalid nested array")
                matrix_rows += 1
                if matrix_rows > MAX_RECORDS:
                    raise ValueError("matrix exceeds record limit")
        elif byte == 93:
            if depth == 0:
                raise ValueError("unbalanced JSON")
            if depth == 2:
                section = None
            depth -= 1
        elif byte in (123, 125):
            raise ValueError("noncanonical JSON object")
        elif byte == 44:
            if depth == 1:
                root_commas += 1
                if root_commas > 2:
                    raise ValueError("invalid root element count")
            elif depth == 2 and section == "symbols":
                symbols_commas += 1
                if symbols_commas >= MAX_SYMBOLS:
                    raise ValueError("symbol table exceeds limit")
            elif depth == 2 and section == "matrix":
                matrix_commas += 1
                if matrix_commas >= MAX_RECORDS:
                    raise ValueError("matrix exceeds record limit")
            elif depth == 3 and section == "matrix":
                row_commas += 1
                if row_commas > 2 * MAX_RECORDS:
                    raise ValueError("matrix index count exceeds limit")
    if depth != 0 or in_string:
        raise ValueError("unterminated JSON")

def validate(records):
    if not isinstance(records, list) or len(records) > 100000:
        raise ValueError("records must be a list of at most 100000 triples")
    for row in records:
        if not isinstance(row, dict) or set(row) != {"subject", "predicate", "object"}:
            raise ValueError("record must contain exactly subject, predicate, object")
        if any(not isinstance(v, str) or len(v) > 10000 for v in row.values()):
            raise ValueError("record values must be strings <= 10000 characters")
        for value in row.values():
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ValueError("record values must be valid UTF-8") from exc

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
        # Canonical VSG1 frames are UTF-8 JSON, never UTF-16/UTF-32.
        # json.loads(bytes) auto-detects alternate encodings, which can
        # bypass the byte-oriented structural preflight and allocate huge
        # noncanonical matrices before validation. Reject NULs up front,
        # then parse explicitly decoded UTF-8 text only.
        if b"\x00" in raw:
            raise ValueError("NUL byte in canonical UTF-8 frame")
        text = raw.decode("utf-8")
        _preflight_structure(raw)
        version, symbols, matrix = json.loads(text)
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
    except (ValueError, TypeError, IndexError, KeyError, RecursionError, OverflowError, UnicodeError) as exc:
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
