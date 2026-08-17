from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .models import Finding, RepositoryEvidence, RiskTier


def _repository_id(full_name: str) -> str:
    return "REPO-" + hashlib.sha256(f"truth-compiler:{full_name}".encode("utf-8")).hexdigest()[:24]


def load_truth_compiler_jsonl(path: str | Path) -> list[tuple[RepositoryEvidence, Finding]]:
    """Load the stable RCP Truth Compiler interchange contract.

    Each JSONL line must contain repository identity plus a finding. Unknown or
    malformed truth states are rejected instead of being promoted to PASS.
    """
    rows: list[tuple[RepositoryEvidence, Finding]] = []
    candidate = Path(path)
    for line_number, line in enumerate(candidate.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number} must be a JSON object")
        required = {"repository_full_name", "head_sha", "rule_id", "title", "evidence"}
        missing = required - set(record)
        if missing:
            raise ValueError(f"line {line_number} missing fields: {sorted(missing)}")
        full_name = str(record["repository_full_name"])
        name = full_name.rsplit("/", 1)[-1]
        repo = RepositoryEvidence(
            repository_id=_repository_id(full_name),
            name=name,
            full_name=full_name,
            source="truth-compiler",
            default_branch=str(record.get("default_branch") or "main"),
            head_sha=str(record["head_sha"]),
            classification=str(record.get("classification") or "UNKNOWN").upper(),
            archived=bool(record.get("archived", False)),
            fork=bool(record.get("fork", False)),
            size_kb=int(record.get("size_kb") or 0),
            root_files=tuple(str(x) for x in record.get("root_files", [])),
            metadata={"truth_state": str(record.get("truth_state") or "UNKNOWN"), "source_record_line": line_number},
        )
        truth_state = str(record.get("truth_state") or "UNKNOWN").upper()
        if truth_state not in {"PASS", "FAIL", "UNKNOWN", "PARTIAL"}:
            raise ValueError(f"line {line_number} has unsupported truth_state {truth_state!r}")
        evidence = dict(record["evidence"])
        evidence["truth_state"] = truth_state
        finding = Finding.build(
            repo=repo,
            rule_id=str(record["rule_id"]),
            title=str(record["title"]),
            severity=int(record.get("severity", 5)),
            risk=RiskTier(str(record.get("risk") or "R2")),
            blast_radius=int(record.get("blast_radius", 5)),
            revenue_block=int(record.get("revenue_block", 0)),
            proof_gap=int(record.get("proof_gap", 5)),
            dependency_unlock=int(record.get("dependency_unlock", 5)),
            irreversibility=int(record.get("irreversibility", 0)),
            evidence=evidence,
            remediable=bool(record.get("remediable", False)),
            recipe=record.get("recipe"),
            required_paths=tuple(str(x) for x in record.get("required_paths", [])),
        )
        rows.append((repo, finding))
    return rows
