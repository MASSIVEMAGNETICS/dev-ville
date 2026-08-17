from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Iterable, Optional

from .models import (
    CapabilityLease,
    CaseState,
    Finding,
    RemediationCase,
    RepositoryEvidence,
    RiskTier,
    utc_now,
)


_ALLOWED_TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.DISCOVERED: {CaseState.TRIAGED, CaseState.BLOCKED, CaseState.FAILED},
    CaseState.TRIAGED: {CaseState.AUTHORIZED, CaseState.AWAITING_APPROVAL, CaseState.BLOCKED, CaseState.FAILED},
    CaseState.AWAITING_APPROVAL: {CaseState.AUTHORIZED, CaseState.BLOCKED, CaseState.FAILED},
    CaseState.AUTHORIZED: {CaseState.CLAIMED, CaseState.BLOCKED, CaseState.FAILED},
    CaseState.CLAIMED: {CaseState.PATCHING, CaseState.FAILED},
    CaseState.PATCHING: {CaseState.VERIFYING, CaseState.FAILED},
    CaseState.VERIFYING: {CaseState.PROVEN, CaseState.FAILED},
    CaseState.PROVEN: {CaseState.RECEIPTED, CaseState.FAILED},
    CaseState.RECEIPTED: {CaseState.PR_READY, CaseState.FAILED},
    CaseState.PR_READY: {CaseState.DRAFT_PR, CaseState.FAILED},
    CaseState.DRAFT_PR: set(),
    CaseState.BLOCKED: set(),
    CaseState.FAILED: set(),
}


class StateTransitionError(ValueError):
    pass


class RemediationStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self._db.close()

    def _migrate(self) -> None:
        with self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS repositories (
                    repository_id TEXT PRIMARY KEY,
                    full_name TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    scanned_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    repository_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(repository_id) REFERENCES repositories(repository_id)
                );
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    repository_id TEXT NOT NULL,
                    repository_full_name TEXT NOT NULL,
                    head_sha TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    remediable INTEGER NOT NULL,
                    recipe TEXT,
                    required_paths_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    terminal_reason TEXT,
                    FOREIGN KEY(finding_id) REFERENCES findings(finding_id),
                    FOREIGN KEY(repository_id) REFERENCES repositories(repository_id)
                );
                CREATE INDEX IF NOT EXISTS idx_cases_queue ON cases(state, priority DESC, created_at ASC);
                CREATE TABLE IF NOT EXISTS leases (
                    lease_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(case_id) REFERENCES cases(case_id)
                );
                """
            )

    def upsert_repository(self, repo: RepositoryEvidence) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO repositories(repository_id, full_name, head_sha, classification, payload_json, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(repository_id) DO UPDATE SET
                    full_name=excluded.full_name,
                    head_sha=excluded.head_sha,
                    classification=excluded.classification,
                    payload_json=excluded.payload_json,
                    scanned_at=excluded.scanned_at
                """,
                (
                    repo.repository_id,
                    repo.full_name,
                    repo.head_sha,
                    repo.classification,
                    json.dumps(repo.to_dict(), sort_keys=True),
                    repo.scanned_at,
                ),
            )

    def upsert_finding(self, finding: Finding) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO findings(finding_id, repository_id, rule_id, priority, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(finding_id) DO UPDATE SET
                    priority=excluded.priority,
                    payload_json=excluded.payload_json
                """,
                (
                    finding.finding_id,
                    finding.repository_id,
                    finding.rule_id,
                    finding.priority,
                    json.dumps(finding.to_dict(), sort_keys=True),
                ),
            )

    def upsert_case(self, case: RemediationCase) -> None:
        now = utc_now()
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO cases(
                    case_id, finding_id, repository_id, repository_full_name, head_sha,
                    rule_id, title, risk, priority, remediable, recipe,
                    required_paths_json, state, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(case_id) DO UPDATE SET
                    title=excluded.title,
                    priority=excluded.priority,
                    remediable=excluded.remediable,
                    recipe=excluded.recipe,
                    required_paths_json=excluded.required_paths_json,
                    updated_at=excluded.updated_at
                """,
                (
                    case.case_id,
                    case.finding_id,
                    case.repository_id,
                    case.repository_full_name,
                    case.head_sha,
                    case.rule_id,
                    case.title,
                    case.risk.value,
                    case.priority,
                    1 if case.remediable else 0,
                    case.recipe,
                    json.dumps(list(case.required_paths)),
                    case.state.value,
                    case.created_at,
                    now,
                ),
            )

    def _row_to_case(self, row: sqlite3.Row) -> RemediationCase:
        return RemediationCase(
            case_id=row["case_id"],
            finding_id=row["finding_id"],
            repository_id=row["repository_id"],
            repository_full_name=row["repository_full_name"],
            head_sha=row["head_sha"],
            rule_id=row["rule_id"],
            title=row["title"],
            risk=RiskTier(row["risk"]),
            priority=int(row["priority"]),
            remediable=bool(row["remediable"]),
            recipe=row["recipe"],
            required_paths=tuple(json.loads(row["required_paths_json"])),
            state=CaseState(row["state"]),
            created_at=row["created_at"],
        )

    def get_case(self, case_id: str) -> RemediationCase:
        row = self._db.execute("SELECT * FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise KeyError(case_id)
        return self._row_to_case(row)

    def list_cases(
        self,
        states: Optional[Iterable[CaseState]] = None,
        *,
        limit: int = 100,
    ) -> list[RemediationCase]:
        limit = max(1, min(int(limit), 10000))
        if states:
            state_values = [s.value for s in states]
            placeholders = ",".join("?" for _ in state_values)
            rows = self._db.execute(
                f"SELECT * FROM cases WHERE state IN ({placeholders}) ORDER BY priority DESC, created_at ASC LIMIT ?",
                (*state_values, limit),
            ).fetchall()
        else:
            rows = self._db.execute(
                "SELECT * FROM cases ORDER BY priority DESC, created_at ASC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_case(row) for row in rows]

    def transition(self, case_id: str, to_state: CaseState, reason: str) -> RemediationCase:
        with self._lock:
            case = self.get_case(case_id)
            if to_state == case.state:
                return case
            allowed = _ALLOWED_TRANSITIONS[case.state]
            if to_state not in allowed:
                raise StateTransitionError(f"invalid transition {case.state.value} -> {to_state.value}")
            now = utc_now()
            terminal_reason = reason if to_state in {CaseState.BLOCKED, CaseState.FAILED} else None
            with self._db:
                self._db.execute(
                    "UPDATE cases SET state=?, updated_at=?, terminal_reason=? WHERE case_id=?",
                    (to_state.value, now, terminal_reason, case_id),
                )
                self._db.execute(
                    "INSERT INTO transitions(case_id, from_state, to_state, reason, at) VALUES (?, ?, ?, ?, ?)",
                    (case_id, case.state.value, to_state.value, reason, now),
                )
            return self.get_case(case_id)

    def save_lease(self, lease: CapabilityLease) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO leases(lease_id, case_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (lease.lease_id, lease.case_id, json.dumps(lease.to_dict(), sort_keys=True), utc_now()),
            )

    def latest_lease(self, case_id: str) -> Optional[CapabilityLease]:
        row = self._db.execute(
            "SELECT payload_json FROM leases WHERE case_id=? ORDER BY created_at DESC LIMIT 1", (case_id,)
        ).fetchone()
        if row is None:
            return None
        data = json.loads(row["payload_json"])
        return CapabilityLease(
            lease_id=data["lease_id"],
            case_id=data["case_id"],
            repository_full_name=data["repository_full_name"],
            base_sha=data["base_sha"],
            risk=RiskTier(data["risk"]),
            issued_at=data["issued_at"],
            expires_at=data["expires_at"],
            allowed_paths=tuple(data["allowed_paths"]),
            allowed_operations=tuple(data["allowed_operations"]),
            issuer=data["issuer"],
            signature=data["signature"],
        )

    def save_artifact(self, artifact_id: str, case_id: str, kind: str, payload: dict[str, Any]) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO artifacts(artifact_id, case_id, kind, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (artifact_id, case_id, kind, json.dumps(payload, sort_keys=True), utc_now()),
            )

    def artifact(self, artifact_id: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT payload_json FROM artifacts WHERE artifact_id=?", (artifact_id,)
        ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return json.loads(row["payload_json"])

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in self._db.execute("SELECT state, COUNT(*) AS n FROM cases GROUP BY state"):
            result[row["state"]] = int(row["n"])
        return result

    def latest_artifact(self, case_id: str, kind: str) -> Optional[dict[str, Any]]:
        row = self._db.execute(
            "SELECT payload_json FROM artifacts WHERE case_id=? AND kind=? ORDER BY created_at DESC LIMIT 1",
            (case_id, kind),
        ).fetchone()
        return json.loads(row["payload_json"]) if row is not None else None
