"""Reproducible, synthetic TRACE-0/Chronos record benchmark for VSG1.

No real user events, secrets, private ledgers, or model-performance claims.
This module never writes to the canonical Chronos ledger.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
import zlib

from semantic_codec import decode as vsg1_decode, encode as vsg1_encode
from trace0_chronos import ChronosLedger, Trace0Observer

SOURCE_REPO = "MASSIVEMAGNETICS/dev-ville"
SOURCE_COMMIT = "f4d340c48d6b23af6bc708c45ece7872499c3273"
PREDICATE = "chronos_record_json"
MAX_FIXTURE_RECORDS = 1024
# Keep benchmark baseline decoders bounded to the VSG1 raw-frame limit.
MAX_JSON_BYTES = 8_000_000
MAX_ZLIB_BYTES = (MAX_JSON_BYTES + (MAX_JSON_BYTES >> 12)
                  + (MAX_JSON_BYTES >> 14) + (MAX_JSON_BYTES >> 25) + 13)


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def fixture_records(count):
    """Generate linked, hash-verified records through Victor's actual TRACE-0 API."""
    if type(count) is not int or not 1 <= count <= MAX_FIXTURE_RECORDS:
        raise ValueError("count must be an integer from 1 through 1024")
    fixed_time = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    ledger = ChronosLedger()
    observer = Trace0Observer(ledger, clock=lambda: fixed_time)
    for index in range(count):
        mission = f"mission:synthetic-{index // 16:04d}"
        task = f"task:synthetic-{index:05d}"
        observer.observe(
            actor=("victor.driver", "victor.verifier", "victor.memory")[index % 3],
            action=("route_selected", "evidence_observed", "outcome_checked", "memory_linked")[index % 4],
            entity_id=task,
            payload={
                "graph_mutations": [
                    {"op": "upsert_node", "node_id": task, "node_type": "task",
                     "attributes": {"status": ("ready", "running", "verified")[index % 3]}},
                    {"op": "add_edge", "source": mission, "target": task,
                     "edge_type": "CONTAINS", "attributes": {}},
                ],
                "fixture_step": index,
                "result": ("unknown", "pass", "fail")[index % 3],
            },
            provenance={"origin": "public_synthetic_fixture", "schema": "informatron.trace0.v1"},
            evidence={"kind": "synthetic_test_only", "real_world_execution": False},
        )
    if not ledger.verify_chain():
        raise AssertionError("synthetic Chronos chain invalid")
    return [{"event": event, "receipt": receipt}
            for event, receipt in zip(ledger.events(), ledger.receipts())]


def verify_records(records, *, expected_chain_hash=None):
    """Verify internal receipts and, when supplied, a separately trusted head."""
    if expected_chain_hash is not None:
        if (type(expected_chain_hash) is not str or len(expected_chain_hash) != 64
                or any(ch not in "0123456789abcdef" for ch in expected_chain_hash)):
            raise ValueError("expected_chain_hash must be a lowercase SHA-256 hex digest")
    if not isinstance(records, list) or not records:
        raise ValueError("records must be a nonempty list")
    if any(not isinstance(item, dict) or set(item) != {"event", "receipt"}
           or not isinstance(item["event"], dict)
           or not isinstance(item["receipt"], dict) for item in records):
        raise ValueError("invalid Chronos record envelope")
    ledger = ChronosLedger()
    try:
        ledger.restore([item["event"] for item in records],
                       [item["receipt"] for item in records])
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("Chronos provenance or receipt verification failed") from exc
    if not ledger.verify_chain():
        raise ValueError("Chronos chain verification failed")
    if expected_chain_hash is not None and ledger.last_chain_hash != expected_chain_hash:
        raise ValueError("Chronos trusted chain head mismatch")
    return records


def to_triples(records):
    """Wrap the *entire* event+receipt as JSON; no lossy semantic projection."""
    triples = []
    for record in records:
        event, receipt = record["event"], record["receipt"]
        event_id = event["event_id"]
        if receipt["event_id"] != event_id:
            raise ValueError("event/receipt identity mismatch")
        triples.append({"subject": event_id, "predicate": PREDICATE,
                        "object": canonical_bytes(record).decode("utf-8")})
    return triples


def from_triples(triples, *, expected_chain_hash=None):
    if not isinstance(triples, list):
        raise ValueError("triples must be a list")
    records = []
    for row in triples:
        if not isinstance(row, dict) or set(row) != {"subject", "predicate", "object"}:
            raise ValueError("invalid triple")
        if row["predicate"] != PREDICATE or not isinstance(row["subject"], str) or not isinstance(row["object"], str):
            raise ValueError("invalid Chronos triple type")
        try:
            record = json.loads(row["object"], parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if canonical_bytes(record).decode("utf-8") != row["object"]:
                raise ValueError("noncanonical embedded record")
            if record["event"]["event_id"] != row["subject"]:
                raise ValueError("event identity mismatch")
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise ValueError("invalid embedded Chronos record") from exc
        records.append(record)
    return verify_records(records, expected_chain_hash=expected_chain_hash)


def json_decode(encoded, *, expected_chain_hash=None):
    """Decode only bounded canonical UTF-8 JSON, then verify Chronos."""
    if type(encoded) is not bytes or not 1 <= len(encoded) <= MAX_JSON_BYTES:
        raise ValueError("invalid or oversized canonical JSON payload")
    try:
        records = json.loads(
            encoded, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if canonical_bytes(records) != encoded:
            raise ValueError("noncanonical JSON payload")
    except (ValueError, TypeError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError("invalid canonical JSON payload") from exc
    return verify_records(records, expected_chain_hash=expected_chain_hash)


def zlib_json_decode(encoded, *, expected_chain_hash=None):
    """Bound compressed input and expansion; reject incomplete/trailing frames."""
    if type(encoded) is not bytes or not 1 <= len(encoded) <= MAX_ZLIB_BYTES:
        raise ValueError("invalid or oversized compressed JSON payload")
    inflater = zlib.decompressobj()
    try:
        raw = inflater.decompress(encoded, MAX_JSON_BYTES + 1)
        if (len(raw) > MAX_JSON_BYTES or not inflater.eof
                or inflater.unused_data or inflater.unconsumed_tail):
            raise ValueError("invalid or oversized decompressed JSON payload")
    except zlib.error as exc:
        raise ValueError("invalid compressed JSON payload") from exc
    return json_decode(raw, expected_chain_hash=expected_chain_hash)


def vsg1_event_decode(encoded, *, expected_chain_hash=None):
    return from_triples(vsg1_decode(encoded), expected_chain_hash=expected_chain_hash)


def _measure(function, repeats):
    wall_ms, cpu_ms = [], []
    for _ in range(repeats):
        wall_start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
        function()
        wall_ms.append((time.perf_counter_ns() - wall_start) / 1e6)
        cpu_ms.append((time.process_time_ns() - cpu_start) / 1e6)
    tracemalloc.start()
    try:
        function()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"wall_ms_median": round(statistics.median(wall_ms), 3),
            "cpu_ms_median": round(statistics.median(cpu_ms), 3),
            "python_peak_kib": round(peak / 1024, 1)}


def run_benchmark(count=128, repeats=5):
    if type(repeats) is not int or not 1 <= repeats <= 30:
        raise ValueError("repeats must be an integer from 1 through 30")
    records = fixture_records(count)
    raw = canonical_bytes(records)
    # Pinned before encoding; this synthetic fixture is NOT external proof.
    expected_chain_hash = records[-1]["receipt"]["chain_hash"]
    methods = {
        "canonical_json": (lambda: canonical_bytes(records), json_decode),
        "zlib_json_9": (lambda: zlib.compress(canonical_bytes(records), level=9), zlib_json_decode),
        "vsg1_full_record_adapter": (lambda: vsg1_encode(to_triples(records)), vsg1_event_decode),
    }
    results = {}
    for name, (encoder, decoder) in methods.items():
        encoded = encoder()
        restored = decoder(encoded, expected_chain_hash=expected_chain_hash)
        if restored != records:
            raise AssertionError(f"lossy or incorrect roundtrip: {name}")
        results[name] = {"encoded_bytes": len(encoded),
                         "roundtrip_exact": True,
                         "chronos_chain_verified": True,
                         "expected_chain_head_matched": True,
                         "encode": _measure(encoder, repeats),
                         "decode_and_verify": _measure(
                             lambda: decoder(encoded, expected_chain_hash=expected_chain_hash), repeats)}
    baseline_size = results["zlib_json_9"]["encoded_bytes"]
    results["vsg1_full_record_adapter"]["size_ratio_vs_zlib_json"] = round(
        results["vsg1_full_record_adapter"]["encoded_bytes"] / baseline_size, 4)
    return {
        "corpus": {"kind": "synthetic_trace0_chronos_schema", "real_events": False,
                   "source_repo": SOURCE_REPO, "source_commit": SOURCE_COMMIT,
                   "records": count, "sha256_canonical_json": hashlib.sha256(raw).hexdigest(),
                   "expected_chain_head": expected_chain_hash,
                   "anchor_origin": "synthetic_fixture_pre_encoding_not_external_trust",
                   "canonical_json_bytes": len(raw)},
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "machine": platform.machine(), "repeats": repeats},
        "methods": results,
        "limitations": ["Synthetic public-schema events, not production/held-out corpus",
                        "VSG1 stores complete event+receipt JSON strings, not learned semantics",
                        "tracemalloc measures Python allocations, not native zlib memory",
                        "No neural downstream accuracy or energy measurement; CPU time is not energy",
                        "Pinned head is derived from this synthetic fixture, not an external authenticated anchor"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=128)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, help="optional JSON report destination")
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(args.records, args.repeats)
    except (ValueError, AssertionError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
