"""Receipt-backed economic optimization organ for Victor / Dev-Ville.

The organ does not claim revenue because a worker says it earned money. It stores
strategies and runs, records structurally valid receipts, requires explicit
source verifiers before receipts affect economics, and emits every material
state transition to an optional event sink (TRACE-0 in Dev-Ville).

Only Python's standard library is required.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import uuid
from typing import Any, Callable, Dict, List, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


ReceiptVerifier = Callable[[Dict[str, Any], Dict[str, Any]], bool]
EventSink = Callable[[str, str, Dict[str, Any], Dict[str, Any], str], None]


@dataclass(frozen=True)
class StrategyDecision:
    strategy_id: str
    action: str
    score: Optional[float]
    reason: str
    metrics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "action": self.action,
            "score": self.score,
            "reason": self.reason,
            "metrics": self.metrics,
        }


class MoneyFarmStore:
    """SQLite WAL store for strategies, runs, receipts, and decisions."""

    def __init__(self, path: str = "state/moneyfarm.sqlite3") -> None:
        self.path = str(path)
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=FULL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS strategies (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    major TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('active','paused','culled')),
                    min_samples INTEGER NOT NULL CHECK(min_samples > 0),
                    scale_min_avg_net_cents INTEGER NOT NULL,
                    scale_min_roi REAL NOT NULL,
                    scale_min_win_rate REAL NOT NULL CHECK(scale_min_win_rate BETWEEN 0 AND 1),
                    max_parallel INTEGER NOT NULL CHECK(max_parallel > 0),
                    max_budget_cents INTEGER NOT NULL CHECK(max_budget_cents >= 0),
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL REFERENCES strategies(id),
                    project_name TEXT,
                    status TEXT NOT NULL CHECK(status IN ('open','closed','aborted')),
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    notes TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL REFERENCES runs(id),
                    kind TEXT NOT NULL CHECK(kind IN ('revenue','cost')),
                    amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
                    currency TEXT NOT NULL,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    evidence_hash TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','verified','rejected')),
                    verifier TEXT,
                    verification_json TEXT,
                    verified_at TEXT,
                    UNIQUE(source, external_id, kind)
                );

                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    strategy_id TEXT NOT NULL REFERENCES strategies(id),
                    action TEXT NOT NULL CHECK(action IN ('HOLD','KEEP','SCALE','CULL')),
                    score REAL,
                    reason TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_runs_strategy ON runs(strategy_id, status);
                CREATE INDEX IF NOT EXISTS idx_receipts_run_status ON receipts(run_id, status);
                CREATE INDEX IF NOT EXISTS idx_decisions_strategy ON decisions(strategy_id, created_at);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock, self._conn:
            return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]


class MoneyFarmEconomicOrgan:
    """Bounded strategy portfolio manager with receipt-backed economics."""

    def __init__(
        self,
        store_path: str = "state/moneyfarm.sqlite3",
        event_sink: Optional[EventSink] = None,
    ) -> None:
        self.store = MoneyFarmStore(store_path)
        self.event_sink = event_sink
        self._verifiers: Dict[str, ReceiptVerifier] = {}
        self._lock = threading.RLock()

    def _emit(
        self,
        action: str,
        entity_id: str,
        payload: Dict[str, Any],
        evidence: Optional[Dict[str, Any]] = None,
        authority: str = "economic_observation",
    ) -> None:
        if self.event_sink:
            self.event_sink(action, entity_id, payload, evidence or {}, authority)

    def register_verifier(self, name: str, verifier: ReceiptVerifier) -> None:
        if not name or not callable(verifier):
            raise ValueError("verifier requires a non-empty name and callable")
        with self._lock:
            self._verifiers[name] = verifier

    def register_strategy(
        self,
        name: str,
        major: str,
        *,
        min_samples: int = 3,
        scale_min_avg_net_cents: int = 100,
        scale_min_roi: float = 0.25,
        scale_min_win_rate: float = 0.60,
        max_parallel: int = 2,
        max_budget_cents: int = 10_000,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not name.strip() or not major.strip():
            raise ValueError("strategy name and major are required")
        if min_samples <= 0 or max_parallel <= 0 or max_budget_cents < 0:
            raise ValueError("invalid strategy bounds")
        if not 0.0 <= scale_min_win_rate <= 1.0:
            raise ValueError("scale_min_win_rate must be between 0 and 1")

        strategy_id = f"strategy-{uuid.uuid4().hex}"
        now = _utc_now()
        self.store.execute(
            """
            INSERT INTO strategies(
                id,name,major,status,min_samples,scale_min_avg_net_cents,
                scale_min_roi,scale_min_win_rate,max_parallel,max_budget_cents,
                metadata_json,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                strategy_id,
                name.strip(),
                major.strip(),
                "active",
                int(min_samples),
                int(scale_min_avg_net_cents),
                float(scale_min_roi),
                float(scale_min_win_rate),
                int(max_parallel),
                int(max_budget_cents),
                _canonical_json(metadata or {}),
                now,
                now,
            ),
        )
        self._emit(
            "economic_strategy_registered",
            f"strategy:{strategy_id}",
            {"name": name.strip(), "major": major.strip(), "max_parallel": max_parallel},
            authority="portfolio_registry",
        )
        return strategy_id

    def get_strategy(self, strategy_id: str) -> Dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM strategies WHERE id=?", (strategy_id,))
        if not row:
            raise KeyError(f"unknown strategy: {strategy_id}")
        row["metadata"] = json.loads(row.pop("metadata_json"))
        return row

    def list_strategies(self) -> List[Dict[str, Any]]:
        return [self.get_strategy(row["id"]) for row in self.store.fetchall("SELECT id FROM strategies ORDER BY created_at")]

    def start_run(self, strategy_id: str, project_name: Optional[str] = None) -> str:
        strategy = self.get_strategy(strategy_id)
        if strategy["status"] != "active":
            raise ValueError(f"strategy is not active: {strategy['status']}")

        open_count_row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM runs WHERE strategy_id=? AND status='open'",
            (strategy_id,),
        )
        open_count = int(open_count_row["n"] if open_count_row else 0)
        if open_count >= int(strategy["max_parallel"]):
            raise RuntimeError("strategy max_parallel bound reached")

        run_id = f"run-{uuid.uuid4().hex}"
        self.store.execute(
            "INSERT INTO runs(id,strategy_id,project_name,status,started_at,notes) VALUES (?,?,?,?,?,?)",
            (run_id, strategy_id, project_name, "open", _utc_now(), ""),
        )
        self._emit(
            "economic_run_started",
            f"run:{run_id}",
            {"strategy_id": strategy_id, "project_name": project_name},
            authority="bounded_execution",
        )
        return run_id

    def get_run(self, run_id: str) -> Dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM runs WHERE id=?", (run_id,))
        if not row:
            raise KeyError(f"unknown run: {run_id}")
        return row

    def record_receipt(
        self,
        run_id: str,
        *,
        kind: str,
        amount_cents: int,
        source: str,
        external_id: str,
        evidence: Dict[str, Any],
        currency: str = "USD",
        observed_at: Optional[str] = None,
    ) -> str:
        run = self.get_run(run_id)
        if run["status"] != "open":
            raise ValueError("receipts may only be attached to open runs")
        if kind not in {"revenue", "cost"}:
            raise ValueError("kind must be revenue or cost")
        if amount_cents < 0:
            raise ValueError("amount_cents must be non-negative")
        if not source.strip() or not external_id.strip():
            raise ValueError("source and external_id are required")
        if not isinstance(evidence, dict) or not evidence:
            raise ValueError("evidence must be a non-empty object")

        if kind == "cost":
            strategy = self.get_strategy(run["strategy_id"])
            existing_cost = self.store.fetchone(
                """
                SELECT COALESCE(SUM(amount_cents), 0) AS total
                FROM receipts
                WHERE run_id=? AND kind='cost' AND status != 'rejected'
                """,
                (run_id,),
            )
            committed = int(existing_cost["total"] if existing_cost else 0)
            if committed + int(amount_cents) > int(strategy["max_budget_cents"]):
                raise RuntimeError(
                    f"run budget exceeded: {committed + int(amount_cents)} > "
                    f"{strategy['max_budget_cents']} cents"
                )

        core = {
            "run_id": run_id,
            "kind": kind,
            "amount_cents": int(amount_cents),
            "currency": currency.upper(),
            "source": source.strip(),
            "external_id": external_id.strip(),
            "observed_at": observed_at or _utc_now(),
            "evidence": evidence,
        }
        evidence_hash = _sha256(core)
        receipt_id = f"receipt-{uuid.uuid4().hex}"
        try:
            self.store.execute(
                """
                INSERT INTO receipts(
                    id,run_id,kind,amount_cents,currency,source,external_id,
                    observed_at,evidence_json,evidence_hash,status
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    receipt_id,
                    run_id,
                    kind,
                    int(amount_cents),
                    currency.upper(),
                    source.strip(),
                    external_id.strip(),
                    core["observed_at"],
                    _canonical_json(evidence),
                    evidence_hash,
                    "pending",
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("duplicate or invalid receipt") from exc

        self._emit(
            "economic_receipt_recorded",
            f"receipt:{receipt_id}",
            {
                "run_id": run_id,
                "kind": kind,
                "amount_cents": int(amount_cents),
                "currency": currency.upper(),
                "source": source.strip(),
                "external_id": external_id.strip(),
                "evidence_hash": evidence_hash,
            },
            evidence={"receipt_core_sha256": evidence_hash},
            authority="unverified_external_claim",
        )
        return receipt_id

    def get_receipt(self, receipt_id: str) -> Dict[str, Any]:
        row = self.store.fetchone("SELECT * FROM receipts WHERE id=?", (receipt_id,))
        if not row:
            raise KeyError(f"unknown receipt: {receipt_id}")
        row["evidence"] = json.loads(row.pop("evidence_json"))
        verification_json = row.pop("verification_json")
        row["verification"] = json.loads(verification_json) if verification_json else None
        return row

    def verify_receipt(self, receipt_id: str, verifier_name: str, proof: Dict[str, Any]) -> bool:
        receipt = self.get_receipt(receipt_id)
        if receipt["status"] == "verified":
            return True
        if receipt["status"] == "rejected":
            return False
        verifier = self._verifiers.get(verifier_name)
        if verifier is None:
            raise KeyError(f"receipt verifier is not registered: {verifier_name}")

        accepted = bool(verifier(receipt, proof))
        new_status = "verified" if accepted else "rejected"
        verified_at = _utc_now()
        verification = {
            "verifier": verifier_name,
            "proof": proof,
            "accepted": accepted,
            "verified_at": verified_at,
        }
        self.store.execute(
            """
            UPDATE receipts
            SET status=?, verifier=?, verification_json=?, verified_at=?
            WHERE id=? AND status='pending'
            """,
            (new_status, verifier_name, _canonical_json(verification), verified_at, receipt_id),
        )
        self._emit(
            "economic_receipt_verified" if accepted else "economic_receipt_rejected",
            f"receipt:{receipt_id}",
            {
                "run_id": receipt["run_id"],
                "kind": receipt["kind"],
                "amount_cents": receipt["amount_cents"],
                "verifier": verifier_name,
                "status": new_status,
            },
            evidence={"verification_sha256": _sha256(verification)},
            authority="receipt_verification_gate",
        )
        return accepted

    def run_metrics(self, run_id: str) -> Dict[str, Any]:
        run = self.get_run(run_id)
        rows = self.store.fetchall(
            "SELECT kind, amount_cents FROM receipts WHERE run_id=? AND status='verified'",
            (run_id,),
        )
        revenue = sum(int(row["amount_cents"]) for row in rows if row["kind"] == "revenue")
        cost = sum(int(row["amount_cents"]) for row in rows if row["kind"] == "cost")
        net = revenue - cost
        roi = (net / cost) if cost > 0 else None
        pending_row = self.store.fetchone(
            "SELECT COUNT(*) AS n FROM receipts WHERE run_id=? AND status='pending'",
            (run_id,),
        )
        return {
            "run_id": run_id,
            "strategy_id": run["strategy_id"],
            "verified_revenue_cents": revenue,
            "verified_cost_cents": cost,
            "verified_net_cents": net,
            "roi": roi,
            "pending_receipts": int(pending_row["n"] if pending_row else 0),
            "status": run["status"],
        }

    def abort_run(self, run_id: str, reason: str) -> Dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "open":
            raise ValueError("run is not open")
        if not reason.strip():
            raise ValueError("abort reason is required")
        self.store.execute(
            "UPDATE runs SET status='aborted', ended_at=?, notes=? WHERE id=?",
            (_utc_now(), reason.strip(), run_id),
        )
        metrics = self.run_metrics(run_id)
        metrics["status"] = "aborted"
        self._emit(
            "economic_run_aborted",
            f"run:{run_id}",
            {**metrics, "reason": reason.strip()},
            evidence={"metrics_sha256": _sha256(metrics)},
            authority="bounded_execution",
        )
        return metrics

    def close_run(self, run_id: str, notes: str = "") -> Dict[str, Any]:
        run = self.get_run(run_id)
        if run["status"] != "open":
            raise ValueError("run is not open")
        metrics = self.run_metrics(run_id)
        if metrics["pending_receipts"]:
            raise RuntimeError("cannot close a run while receipts remain pending")
        self.store.execute(
            "UPDATE runs SET status='closed', ended_at=?, notes=? WHERE id=?",
            (_utc_now(), notes, run_id),
        )
        metrics["status"] = "closed"
        self._emit(
            "economic_run_closed",
            f"run:{run_id}",
            metrics,
            evidence={"metrics_sha256": _sha256(metrics)},
            authority="economic_accounting",
        )
        return metrics

    def strategy_metrics(self, strategy_id: str) -> Dict[str, Any]:
        self.get_strategy(strategy_id)
        closed_runs = self.store.fetchall(
            "SELECT id FROM runs WHERE strategy_id=? AND status='closed' ORDER BY started_at",
            (strategy_id,),
        )
        run_metrics = [self.run_metrics(row["id"]) for row in closed_runs]
        samples = len(run_metrics)
        total_revenue = sum(row["verified_revenue_cents"] for row in run_metrics)
        total_cost = sum(row["verified_cost_cents"] for row in run_metrics)
        total_net = total_revenue - total_cost
        avg_net = (total_net / samples) if samples else 0.0
        wins = sum(1 for row in run_metrics if row["verified_net_cents"] > 0)
        win_rate = (wins / samples) if samples else 0.0
        roi = (total_net / total_cost) if total_cost > 0 else None
        return {
            "strategy_id": strategy_id,
            "samples": samples,
            "verified_revenue_cents": total_revenue,
            "verified_cost_cents": total_cost,
            "verified_net_cents": total_net,
            "average_net_cents": avg_net,
            "win_rate": win_rate,
            "roi": roi,
        }

    def evaluate_strategy(self, strategy_id: str) -> StrategyDecision:
        strategy = self.get_strategy(strategy_id)
        metrics = self.strategy_metrics(strategy_id)
        samples = int(metrics["samples"])

        if strategy["status"] == "culled":
            action = "CULL"
            reason = "strategy already culled"
            score = None
        elif samples < int(strategy["min_samples"]):
            action = "HOLD"
            reason = f"need {strategy['min_samples'] - samples} more closed verified run(s)"
            score = None
        else:
            avg_net = float(metrics["average_net_cents"])
            win_rate = float(metrics["win_rate"])
            roi = metrics["roi"]
            normalized_roi = float(roi) if roi is not None else (1.0 if avg_net > 0 else 0.0)
            score = round(avg_net * win_rate * max(0.0, 1.0 + normalized_roi), 6)

            scale_roi_ok = roi is None or float(roi) >= float(strategy["scale_min_roi"])
            if (
                avg_net >= int(strategy["scale_min_avg_net_cents"])
                and win_rate >= float(strategy["scale_min_win_rate"])
                and scale_roi_ok
            ):
                action = "SCALE"
                reason = "verified economics exceed configured scale thresholds"
            elif avg_net < 0 and (roi is None or float(roi) < 0):
                action = "CULL"
                reason = "verified average net is negative after minimum sample count"
            else:
                action = "KEEP"
                reason = "strategy is viable but has not crossed scale or cull thresholds"

        decision = StrategyDecision(strategy_id, action, score, reason, metrics)
        self.store.execute(
            "INSERT INTO decisions(id,strategy_id,action,score,reason,metrics_json,created_at) VALUES (?,?,?,?,?,?,?)",
            (
                f"decision-{uuid.uuid4().hex}",
                strategy_id,
                action,
                score,
                reason,
                _canonical_json(metrics),
                _utc_now(),
            ),
        )
        if action == "CULL" and strategy["status"] != "culled":
            self.store.execute(
                "UPDATE strategies SET status='culled', updated_at=? WHERE id=?",
                (_utc_now(), strategy_id),
            )
        self._emit(
            "economic_strategy_decision",
            f"strategy:{strategy_id}",
            decision.to_dict(),
            evidence={"metrics_sha256": _sha256(metrics)},
            authority="portfolio_policy",
        )
        return decision

    def portfolio_summary(self) -> Dict[str, Any]:
        strategies = self.list_strategies()
        rows = []
        for strategy in strategies:
            metrics = self.strategy_metrics(strategy["id"])
            rows.append(
                {
                    "id": strategy["id"],
                    "name": strategy["name"],
                    "major": strategy["major"],
                    "status": strategy["status"],
                    "metrics": metrics,
                }
            )
        return {"strategies": rows, "count": len(rows)}
