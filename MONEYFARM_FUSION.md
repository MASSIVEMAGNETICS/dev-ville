# Dev-Ville × MoneyFarm Fusion

## Verdict

MoneyFarm is now modeled as an **economic organ**, not a swarm of threads that self-report profit.

Dev-Ville remains the machine-labor runtime. Victor's verified runtime remains the evidence boundary. MoneyFarm adds a persistent strategy portfolio, bounded runs, external cost/revenue receipts, source verification, and deterministic scale/keep/cull decisions.

## Runtime

```text
Human economic objective
        ↓
Strategy registry
        ↓
Bounded economic run ───────────────┐
        ↓                           │
Dev-Ville project / machine labor   │
        ↓                           │
Verified artifact receipts          │
        ↓                           │
External execution / sale / payout  │
        ↓                           │
Pending economic receipt            │
        ↓                           │
Registered source verifier          │
        ↓                           │
Verified revenue/cost               │
        ↓                           │
Run close → portfolio metrics       │
        ↓                           │
HOLD / KEEP / SCALE / CULL          │
                                    ↓
                             TRACE-0 Informatrons
                                    ↓
                             Chronos hash chain
```

## Non-negotiable accounting law

`agent.profit` is not money.

Only receipts accepted by a registered verifier affect strategy economics. A newly recorded receipt is `pending`. Pending receipts block run closure. Rejected receipts contribute zero. Duplicate `(source, external_id, kind)` receipts are rejected by the database.

Money is represented in integer cents to avoid binary floating-point accounting drift.

## Persistence

`MoneyFarmStore` uses SQLite with:

- WAL journal mode;
- full synchronous durability;
- foreign keys;
- uniqueness constraints on external receipts;
- persistent strategies, runs, receipts, and portfolio decisions.

Default path: `state/moneyfarm.sqlite3`.

Chronos remains the causal event history. SQLite is the queryable economic state. Neither replaces the other.

## Safety / sovereignty boundary

This fusion intentionally does **not** contain wallet private keys, exchange trading logic, stealth/evasion behavior, automatic withdrawals, or fake platform adapters.

Real platforms should be integrated through explicit adapters that:

1. execute an authorized action;
2. capture the provider's transaction/payout identifier;
3. retrieve provider evidence;
4. register a verifier;
5. verify the receipt;
6. allow the portfolio policy to react only after verification.

## Run it

```bash
python devville_moneyfarm.py
```

Optional persistence locations:

```bash
DEVVILLE_CHRONOS_PATH=chronos/devville.jsonl
DEVVILLE_MONEYFARM_DB=state/moneyfarm.sqlite3
python devville_moneyfarm.py
```

## Programmatic example

```python
from victor_economic_company import VictorEconomicCompany

company = VictorEconomicCompany()
strategy_id = company.register_revenue_strategy(
    "B Heard direct digital product",
    "digital_product",
    min_samples=3,
    max_parallel=1,
    max_budget_cents=2500,
)

run = company.start_revenue_run(
    strategy_id,
    "Build and verify a sellable digital product with its landing-page assets",
)

# After an external commerce adapter sees a real transaction:
receipt_id = company.record_economic_receipt(
    kind="revenue",
    amount_cents=1999,
    source="commerce_provider",
    external_id="provider-transaction-id",
    evidence={"provider_payload_hash": "..."},
)

# The provider adapter must register a verifier before this can count.
```

## What remains to make it earn real money

The next layer is **external execution adapters**. The economic core is intentionally provider-agnostic. The first real adapter should be for a revenue surface that can legally support automation and exposes authoritative receipts or transaction APIs. Once one adapter exists, one end-to-end loop can be proven:

`objective → build → deploy → acquire → transact → verify → account → learn → scale`.
