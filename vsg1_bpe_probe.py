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
    """Reverse the learned merges, rejecting invalid references and expansion."""
    vocabulary = [bytes([value]) for value in range(256)]
    lengths = [1] * 256
    for offset, pair in enumerate(merges):
        if (not isinstance(pair, tuple) or len(pair) != 2
                or any(type(i) is not int or i < 0 or i >= 256 + offset for i in pair)):
            raise ValueError("invalid learned merge table")
        a, b = pair
        lengths.append(lengths[a] + lengths[b])
        if lengths[-1] > 8_000_000:
            raise ValueError("token expansion exceeds limit")
        vocabulary.append(vocabulary[a] + vocabulary[b])
    if any(type(token) is not int or token < 0 or token >= len(vocabulary) for token in tokens):
        raise ValueError("invalid token id")
    if sum(lengths[token] for token in tokens) > 8_000_000:
        raise ValueError("decoded data exceeds limit")
    return b"".join(vocabulary[token] for token in tokens)


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
        "limitations": [
            "Synthetic mission-disjoint events only; not a real-world benchmark",
            "Byte-pair vocabulary is learned tokenization, NOT learned semantics",
            "Byte-token count is not a comparison to a production LLM tokenizer",
            "16-bit token stream is compressed with zlib; framing not production-ready",
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
