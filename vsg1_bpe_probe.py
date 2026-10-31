"""Train-only byte-pair vocabulary probe on synthetic, mission-disjoint Chronos events.

Research scaffold, not a semantic encoder or a production wire format.
No real events, model weights, network calls, or canonical Chronos writes.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import struct
import zlib

from vsg1_event_benchmark import (
    canonical_bytes, fixture_records, synthetic_holdout_manifest, verify_records,
)

MAX_MERGES = 128


def apply_merge(tokens, pair, new_id):
    """Apply one non-overlapping left-to-right pair merge deterministically."""
    output = []
    index = 0
    while index < len(tokens):
        if index + 1 < len(tokens) and (tokens[index], tokens[index + 1]) == pair:
            output.append(new_id)
            index += 2
        else:
            output.append(tokens[index])
            index += 1
    return output


def train_bpe(training_documents, max_merges=64):
    """Learn a frozen byte-pair vocabulary using training documents only."""
    if type(max_merges) is not int or not 0 <= max_merges <= MAX_MERGES:
        raise ValueError("invalid merge budget")
    if not isinstance(training_documents, list) or not training_documents:
        raise ValueError("training documents must be a nonempty list")
    if any(type(doc) is not bytes or not doc for doc in training_documents):
        raise ValueError("training documents must be nonempty bytes")
    sequences = [list(doc) for doc in training_documents]
    merges = []
    for _ in range(max_merges):
        counts = Counter(
            pair for tokens in sequences for pair in zip(tokens, tokens[1:])
        )
        candidates = [pair for pair, count in counts.items() if count >= 2]
        if not candidates:
            break
        # Maximum frequency, then smallest lexicographic pair: no random seed.
        pair = min(candidates, key=lambda item: (-counts[item], item))
        new_id = 256 + len(merges)
        sequences = [apply_merge(tokens, pair, new_id) for tokens in sequences]
        merges.append(pair)
    return tuple(merges)


def tokenize(raw, merges):
    if type(raw) is not bytes:
        raise ValueError("input must be bytes")
    tokens = list(raw)
    for offset, pair in enumerate(merges):
        tokens = apply_merge(tokens, pair, 256 + offset)
    return tokens


def detokenize(tokens, merges):
    """Preflight expansion length; materialize only symbols in the token stream.

    Avoid eagerly building potentially megabyte-sized *unused* vocabulary
    entries from a valid but adversarial merge table.
    """
    if type(merges) not in (tuple, list) or len(merges) > MAX_MERGES:
        raise ValueError("invalid learned merge table")
    lengths = [1] * 256
    for offset, pair in enumerate(merges):
        if (not isinstance(pair, tuple) or len(pair) != 2
                or any(type(i) is not int or i < 0 or i >= 256 + offset for i in pair)):
            raise ValueError("invalid learned merge table")
        a, b = pair
        expanded_length = lengths[a] + lengths[b]
        if expanded_length > 8_000_000:
            raise ValueError("token expansion exceeds limit")
        lengths.append(expanded_length)
    # Iterators are single-use; checking them before expansion could silently
    # consume them and return empty output. Require a stable finite sequence.
    if type(tokens) not in (list, tuple, _PackedTokenSequence):
        raise ValueError("tokens must be a repeatable bounded sequence")
    total = 0
    for token in tokens:
        if type(token) is not int or token < 0 or token >= len(lengths):
            raise ValueError("invalid token id")
        total += lengths[token]
        if total > 8_000_000:
            raise ValueError("decoded data exceeds limit")
    output = bytearray()
    for token in tokens:
        stack = [token]
        while stack:
            symbol = stack.pop()
            if symbol < 256:
                output.append(symbol)
            else:
                left, right = merges[symbol - 256]
                stack.append(right)
                stack.append(left)
    return bytes(output)



class _PackedTokenSequence:
    """Repeatable, allocation-light view of big-endian uint16 packed tokens.

    The decompressed byte frame remains immutable and owned by this object.
    Repeated iteration supports the detokenizer's validation and decode passes
    without materializing millions of Python integer objects in a list.
    """

    def __init__(self, packed):
        if type(packed) is not bytes or len(packed) % 2:
            raise ValueError("invalid packed token sequence")
        self._packed = packed

    def __iter__(self):
        return (token for (token,) in struct.iter_unpack(">H", self._packed))


MAX_PACKED_FRAME_BYTES = 8_000_000


def read_merge_table(raw):
    """Restore a bounded, structurally valid train-only merge table."""
    if type(raw) is not bytes or len(raw) % 4 or len(raw) > 4 * MAX_MERGES:
        raise ValueError("invalid serialized merge table")
    merges = []
    for (left, right) in struct.iter_unpack(">HH", raw):
        upper = 256 + len(merges)
        if left >= upper or right >= upper:
            raise ValueError("forward reference in merge table")
        merges.append((left, right))
    return tuple(merges)


def decode_packed_tokens(compressed, merges):
    """Decode the actual zlib-compressed uint16 stream, not in-memory tokens.

    Fail closed on oversized expansion, truncated/concatenated frames,
    trailing bytes, odd byte counts, and invalid learned token IDs.
    This is an experiment decoder, not an authenticated wire protocol.
    """
    if type(compressed) is not bytes:
        raise ValueError("compressed token stream must be bytes")
    # zlib compressBound(MAX_PACKED_FRAME_BYTES) from the zlib manual.
    limit = MAX_PACKED_FRAME_BYTES
    compressed_limit = limit + (limit >> 12) + (limit >> 14) + (limit >> 25) + 13
    if len(compressed) > compressed_limit:
        raise ValueError("compressed token frame exceeds limit")
    try:
        decompressor = zlib.decompressobj()
        packed = decompressor.decompress(compressed, limit + 1)
    except zlib.error as exc:
        raise ValueError("invalid compressed token frame") from exc
    if (len(packed) > limit or not decompressor.eof
            or decompressor.unconsumed_tail or decompressor.unused_data):
        raise ValueError("invalid or oversized compressed token frame")
    if len(packed) % 2:
        raise ValueError("odd-length packed token frame")
    return detokenize(_PackedTokenSequence(packed), merges)


def _mission(record):
    edges = [edge for edge in record["event"]["payload"]["graph_mutations"]
             if edge["op"] == "add_edge" and edge["edge_type"] == "CONTAINS"]
    if len(edges) != 1:
        raise ValueError("ambiguous synthetic mission")
    return edges[0]["source"]


def run_probe(count=128, max_merges=64):
    """Evaluate frozen train-only merges on previously unseen synthetic missions."""
    records = fixture_records(count)
    verify_records(records)
    manifest = synthetic_holdout_manifest(records)
    training_missions = set(manifest["train"]["groups"])
    testing_missions = set(manifest["test"]["groups"])
    train = [record for record in records if _mission(record) in training_missions]
    test = [record for record in records if _mission(record) in testing_missions]
    if (not train or not test or training_missions & testing_missions
            or len(train) + len(test) != len(records)):
        raise AssertionError("invalid group-disjoint partition")
    training_docs = [canonical_bytes(record) for record in train]
    merges = train_bpe(training_docs, max_merges)
    heldout = canonical_bytes(test)
    tokens = tokenize(heldout, merges)
    if detokenize(tokens, merges) != heldout:
        raise AssertionError("held-out tokenizer is not reversible")
    # 16-bit token IDs; all model pairs are also two 16-bit IDs.
    packed = struct.pack(">" + "H" * len(tokens), *tokens)
    model_bytes = b"".join(struct.pack(">HH", *pair) for pair in merges)
    encoded = zlib.compress(packed, level=9)
    restored_merges = read_merge_table(model_bytes)
    if restored_merges != merges or decode_packed_tokens(encoded, restored_merges) != heldout:
        raise AssertionError("serialized held-out tokenizer frame is not reversible")
    zlib_baseline = zlib.compress(heldout, level=9)
    return {
        "protocol": "vsg1_synthetic_train_only_bpe_probe_v1",
        "real_events": False,
        "semantic_accuracy_measured": False,
        "model_is_semantic": False,
        "train_missions": len(training_missions),
        "test_missions": len(testing_missions),
        "train_records": len(train),
        "test_records": len(test),
        "train_sha256": hashlib.sha256(canonical_bytes(train)).hexdigest(),
        "test_sha256": hashlib.sha256(heldout).hexdigest(),
        "full_chain_head": manifest["source_chain_head"],
        "split_manifest_sha256": hashlib.sha256(canonical_bytes(manifest)).hexdigest(),
        "merges_learned": len(merges),
        "byte_tokens": len(heldout),
        "learned_tokens": len(tokens),
        "token_reduction_vs_bytes": round(1 - len(tokens) / len(heldout), 6),
        "heldout_json_bytes": len(heldout),
        "heldout_zlib_json_bytes": len(zlib_baseline),
        "heldout_bpe_zlib_token_bytes": len(encoded),
        "merge_table_bytes": len(model_bytes),
        "bpe_total_bytes_including_model": len(encoded) + len(model_bytes),
        "exact_heldout_recovery": True,
        "serialized_frame_recovery_verified": True,
        "limitations": [
            "Synthetic mission-disjoint events only; not a real-world benchmark",
            "Byte-pair vocabulary is learned tokenization, NOT learned semantics",
            "Byte-token count is not a comparison to a production LLM tokenizer",
            "16-bit token stream is compressed with zlib; framing not production-ready",
            "Serialized model and compressed uint16 frame are now decoded end-to-end",
            "Experimental decoder has size/integrity checks but no authentication",
            "Model overhead is counted; no inference accuracy, latency or energy measured",
            "Original full Chronos chain verified before split; subsets are not standalone chains",
        ],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=128)
    parser.add_argument("--merges", type=int, default=64)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.records, args.merges), indent=2, sort_keys=True))
