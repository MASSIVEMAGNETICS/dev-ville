"""Deterministic tests for the receipt-backed MoneyFarm economic organ."""
import os
import tempfile
import threading

from victor_economic_company import VictorEconomicCompany

from moneyfarm_economic_organ import MoneyFarmEconomicOrgan


def _verify_fixture(receipt, proof):
    return proof.get("external_id") == receipt["external_id"] and proof.get("confirmed") is True


def test_scale_after_verified_profitable_runs():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        events = []
        organ = MoneyFarmEconomicOrgan(db, event_sink=lambda *args: events.append(args))
        organ.register_verifier("fixture", _verify_fixture)
        strategy = organ.register_strategy(
            "Receipt-backed test strategy",
            "service",
            min_samples=3,
            scale_min_avg_net_cents=500,
            scale_min_roi=0.25,
            scale_min_win_rate=0.60,
        )

        for index in range(3):
            run = organ.start_run(strategy, f"Project-{index}")
            cost = organ.record_receipt(
                run,
                kind="cost",
                amount_cents=1000,
                source="fixture",
                external_id=f"cost-{index}",
                evidence={"fixture": True},
            )
            revenue = organ.record_receipt(
                run,
                kind="revenue",
                amount_cents=2500,
                source="fixture",
                external_id=f"revenue-{index}",
                evidence={"fixture": True},
            )
            assert organ.verify_receipt(cost, "fixture", {"external_id": f"cost-{index}", "confirmed": True})
            assert organ.verify_receipt(revenue, "fixture", {"external_id": f"revenue-{index}", "confirmed": True})
            metrics = organ.close_run(run)
            assert metrics["verified_net_cents"] == 1500

        decision = organ.evaluate_strategy(strategy)
        assert decision.action == "SCALE"
        assert decision.metrics["samples"] == 3
        assert decision.metrics["verified_net_cents"] == 4500
        assert events
        organ.store.close()


def test_pending_receipt_blocks_close_and_duplicate_receipts_fail():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        organ = MoneyFarmEconomicOrgan(db)
        strategy = organ.register_strategy("Guardrail", "content", min_samples=1)
        run = organ.start_run(strategy)
        receipt = organ.record_receipt(
            run,
            kind="revenue",
            amount_cents=100,
            source="fixture",
            external_id="same-id",
            evidence={"fixture": True},
        )

        blocked = False
        try:
            organ.close_run(run)
        except RuntimeError:
            blocked = True
        assert blocked

        duplicate_blocked = False
        try:
            organ.record_receipt(
                run,
                kind="revenue",
                amount_cents=100,
                source="fixture",
                external_id="same-id",
                evidence={"fixture": True},
            )
        except ValueError:
            duplicate_blocked = True
        assert duplicate_blocked

        organ.register_verifier("fixture", _verify_fixture)
        assert organ.verify_receipt(receipt, "fixture", {"external_id": "same-id", "confirmed": True})
        organ.close_run(run)
        organ.store.close()


def test_budget_bound_and_abort_release_capacity():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        organ = MoneyFarmEconomicOrgan(db)
        strategy = organ.register_strategy(
            "Budget guard", "service", min_samples=1, max_parallel=1, max_budget_cents=500
        )
        run = organ.start_run(strategy)
        organ.record_receipt(
            run,
            kind="cost",
            amount_cents=400,
            source="fixture",
            external_id="cost-budget-1",
            evidence={"fixture": True},
        )
        budget_blocked = False
        try:
            organ.record_receipt(
                run,
                kind="cost",
                amount_cents=101,
                source="fixture",
                external_id="cost-budget-2",
                evidence={"fixture": True},
            )
        except RuntimeError:
            budget_blocked = True
        assert budget_blocked

        organ.abort_run(run, "fixture failure")
        replacement = organ.start_run(strategy)
        assert replacement != run
        organ.abort_run(replacement, "done")
        organ.store.close()



def test_concurrent_budget_writers_cannot_exceed_ceiling():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        first = MoneyFarmEconomicOrgan(db)
        strategy = first.register_strategy(
            "Concurrent budget", "service", min_samples=1, max_budget_cents=500
        )
        run = first.start_run(strategy)
        second = MoneyFarmEconomicOrgan(db)
        barrier = threading.Barrier(2)
        outcomes = []
        outcome_lock = threading.Lock()

        def write_cost(organ, external_id):
            barrier.wait()
            try:
                organ.record_receipt(
                    run,
                    kind="cost",
                    amount_cents=300,
                    source=" Fixture ",
                    external_id=external_id,
                    evidence={"fixture": True},
                )
                outcome = "accepted"
            except RuntimeError:
                outcome = "blocked"
            with outcome_lock:
                outcomes.append(outcome)

        workers = [
            threading.Thread(target=write_cost, args=(first, "concurrent-1")),
            threading.Thread(target=write_cost, args=(second, "concurrent-2")),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        assert sorted(outcomes) == ["accepted", "blocked"]
        pending = first.store.fetchone(
            """
            SELECT COALESCE(SUM(amount_cents), 0) AS total
            FROM receipts
            WHERE run_id=? AND kind='cost' AND status != 'rejected'
            """,
            (run,),
        )
        assert pending["total"] == 300
        first.abort_run(run, "concurrency test complete")
        first.store.close()
        second.store.close()


def test_duplicate_identity_ignores_kind_and_normalizes_source():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        organ = MoneyFarmEconomicOrgan(db)
        strategy = organ.register_strategy("Duplicate identity", "service", min_samples=1)
        run = organ.start_run(strategy)
        organ.record_receipt(
            run,
            kind="revenue",
            amount_cents=100,
            source=" Provider ",
            external_id="txn-1",
            evidence={"fixture": True},
        )
        blocked = False
        try:
            organ.record_receipt(
                run,
                kind="cost",
                amount_cents=100,
                source="PROVIDER",
                external_id="txn-1",
                evidence={"fixture": True},
            )
        except ValueError:
            blocked = True
        assert blocked
        organ.abort_run(run, "duplicate test complete")
        organ.store.close()


def test_restart_recovers_pending_run_and_budget():
    with tempfile.TemporaryDirectory() as temp:
        db = os.path.join(temp, "moneyfarm.sqlite3")
        chronos = os.path.join(temp, "chronos.jsonl")
        first = VictorEconomicCompany(
            chronos_jsonl_path=chronos,
            economic_store_path=db,
        )
        strategy = first.register_revenue_strategy(
            "Restart safety",
            "service",
            min_samples=1,
            max_budget_cents=500,
        )
        run = first.economic.start_run(strategy, "Recovered Project")
        receipt = first.economic.record_receipt(
            run,
            kind="cost",
            amount_cents=400,
            source="fixture",
            external_id="restart-cost-1",
            evidence={"fixture": True},
        )
        first.economic.store.close()

        recovered = VictorEconomicCompany(
            chronos_jsonl_path=chronos,
            economic_store_path=db,
        )
        assert recovered.current_economic_run_id == run
        assert recovered.economic.run_metrics(run)["pending_receipts"] == 1

        budget_preserved = False
        try:
            recovered.record_economic_receipt(
                kind="cost",
                amount_cents=101,
                source="fixture",
                external_id="restart-cost-2",
                evidence={"fixture": True},
            )
        except RuntimeError:
            budget_preserved = True
        assert budget_preserved

        recovered.register_receipt_verifier(" FIXTURE ", _verify_fixture)
        assert recovered.verify_economic_receipt(
            receipt,
            "fixture",
            {"external_id": "restart-cost-1", "confirmed": True},
        )
        recovered.abort_revenue_run("restart recovery verified")
        recovered.economic.store.close()

def main():
    test_scale_after_verified_profitable_runs()
    test_pending_receipt_blocks_close_and_duplicate_receipts_fail()
    test_budget_bound_and_abort_release_capacity()
    test_concurrent_budget_writers_cannot_exceed_ceiling()
    test_duplicate_identity_ignores_kind_and_normalizes_source()
    test_restart_recovers_pending_run_and_budget()
    print("PASS: MoneyFarm economic organ tests")


if __name__ == "__main__":
    main()
