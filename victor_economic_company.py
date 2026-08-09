"""Dev-Ville + Victor machine labor + receipt-backed MoneyFarm fusion."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from moneyfarm_economic_organ import MoneyFarmEconomicOrgan
from victor_machine_labor import VictorMachineLaborCompany


class VictorEconomicCompany(VictorMachineLaborCompany):
    """Victor machine-labor runtime with a bounded economic portfolio organ.

    Dev-Ville builds and verifies artifacts. The economic organ tracks strategies,
    runs, costs, and revenue. No economic receipt affects optimization until an
    explicitly registered verifier accepts it.
    """

    def __init__(
        self,
        verification_timeout_seconds: float = 10.0,
        beta_timeout_seconds: float = 8.0,
        chronos_jsonl_path: Optional[str] = None,
        economic_store_path: str = "state/moneyfarm.sqlite3",
    ) -> None:
        super().__init__(
            verification_timeout_seconds=verification_timeout_seconds,
            beta_timeout_seconds=beta_timeout_seconds,
            chronos_jsonl_path=chronos_jsonl_path,
        )
        self.economic_store_path = economic_store_path
        self.economic = MoneyFarmEconomicOrgan(
            store_path=economic_store_path,
            event_sink=self._economic_event_sink,
        )
        self.current_economic_run_id: Optional[str] = None

    def _economic_event_sink(
        self,
        action: str,
        entity_id: str,
        payload: Dict[str, Any],
        evidence: Dict[str, Any],
        authority: str,
    ) -> None:
        self._observe(
            action,
            entity_id,
            payload,
            evidence=evidence,
            authority=authority,
        )

    def register_receipt_verifier(
        self,
        name: str,
        verifier: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    ) -> None:
        self.economic.register_verifier(name, verifier)

    def register_revenue_strategy(self, name: str, major: str, **policy: Any) -> str:
        return self.economic.register_strategy(name, major, **policy)

    def start_revenue_run(self, strategy_id: str, directive: str) -> Dict[str, Any]:
        if self.current_economic_run_id is not None:
            current = self.economic.get_run(self.current_economic_run_id)
            if current["status"] == "open":
                raise RuntimeError("close or abort the current economic run first")

        project = self.start_project(directive)
        if project is None:
            raise RuntimeError("Dev-Ville failed to create a project")
        run_id = self.economic.start_run(strategy_id, project.name)
        self.current_economic_run_id = run_id
        return {
            "run_id": run_id,
            "strategy_id": strategy_id,
            "project_name": project.name,
            "directive": directive,
        }

    def record_economic_receipt(
        self,
        *,
        kind: str,
        amount_cents: int,
        source: str,
        external_id: str,
        evidence: Dict[str, Any],
        currency: str = "USD",
        run_id: Optional[str] = None,
    ) -> str:
        target = run_id or self.current_economic_run_id
        if target is None:
            raise RuntimeError("no economic run is active")
        return self.economic.record_receipt(
            target,
            kind=kind,
            amount_cents=amount_cents,
            source=source,
            external_id=external_id,
            evidence=evidence,
            currency=currency,
        )

    def verify_economic_receipt(
        self,
        receipt_id: str,
        verifier_name: str,
        proof: Dict[str, Any],
    ) -> bool:
        return self.economic.verify_receipt(receipt_id, verifier_name, proof)

    def abort_revenue_run(self, reason: str) -> Dict[str, Any]:
        if self.current_economic_run_id is None:
            raise RuntimeError("no economic run is active")
        run_id = self.current_economic_run_id
        metrics = self.economic.abort_run(run_id, reason)
        self.current_economic_run_id = None
        return metrics

    def close_revenue_run(self, notes: str = "") -> Dict[str, Any]:
        if self.current_economic_run_id is None:
            raise RuntimeError("no economic run is active")
        run_id = self.current_economic_run_id
        metrics = self.economic.close_run(run_id, notes)
        self.current_economic_run_id = None
        decision = self.economic.evaluate_strategy(metrics["strategy_id"])
        return {"metrics": metrics, "decision": decision.to_dict()}

    def economic_status(self) -> Dict[str, Any]:
        active_run = None
        if self.current_economic_run_id:
            active_run = self.economic.run_metrics(self.current_economic_run_id)
        return {
            "active_run": active_run,
            "portfolio": self.economic.portfolio_summary(),
            "chronos_verified": self.verify_chronos(),
        }

    def save_project(self, filepath: str):
        super().save_project(filepath)
        path = Path(filepath)
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        data["economic_organ"] = {
            "schema_version": "devville.moneyfarm.v1",
            "store_path": self.economic_store_path,
            "current_run_id": self.current_economic_run_id,
            "portfolio_summary": self.economic.portfolio_summary(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_project(self, filepath: str):
        path = Path(filepath)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        super().load_project(filepath)
        economic = snapshot.get("economic_organ", {})
        saved_run_id = economic.get("current_run_id")
        if saved_run_id:
            run = self.economic.get_run(saved_run_id)
            if run["status"] == "open":
                if self.current_project and run.get("project_name") != self.current_project.name:
                    raise ValueError("economic run/project continuity mismatch")
                self.current_economic_run_id = saved_run_id
            else:
                self.current_economic_run_id = None
