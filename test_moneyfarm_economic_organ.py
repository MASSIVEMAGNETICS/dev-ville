"""Deterministic tests for the receipt-backed MoneyFarm economic organ."""
import os
import tempfile

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


def main():
    test_scale_after_verified_profitable_runs()
    test_pending_receipt_blocks_close_and_duplicate_receipts_fail()
    test_budget_bound_and_abort_release_capacity()
    print("PASS: MoneyFarm economic organ tests")


if __name__ == "__main__":
    main()
