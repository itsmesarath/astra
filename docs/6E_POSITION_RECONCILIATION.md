# Persistent 6E scenario reconciliation

The new ledger preserves unresolved paper-simulation inventory across source-session boundaries and restarts. A missing exit, a cancellation request, or a reference quote cannot erase the position or turn it into a realized return. This is the accounting contract needed before a separately registered continuous-account replay can revise execution assumptions.

Implemented on 8 October 2026 in `src/ai_trader/research/six_e_position_ledger.py`, with synthetic tests in `tests/test_six_e_position_ledger.py`. It is a separate development-research library, not a running paper trader, broker adapter, funded futures account or cTrader EURUSD account. The BTC/USDT paper-account implementation and existing databases are unchanged.

## What persists

Each `.sqlite` file belongs to one fixed scenario, policy, exit plan, simulator version, source-manifest pin, quantity limit and extra round-trip cost assumption. It supports one open position at a time, with an explicit dated 6E contract, long/short side and integer contract quantity. The source-session date records the observation context; the position separately retains the execution date of its entry, including when the receipt arrives on a later day.

Inventory, unresolved exit reservations, cumulative closed quantities and costs survive session changes. Old quote references remain visibly dated; their age increases rather than becoming fresh at the next boundary. A roll boundary does not close or relabel an old contract. For example, a new `6EU5` quote or receipt cannot reconcile a carried `6EM5` position.

| Supplied record | Inventory effect | Exit reservation effect | Closed simulation total |
| --- | --- | --- | --- |
| `EntryFill` | Opens the recorded quantity, only when no liability remains | None | Unchanged |
| `ExitIntent` | Unchanged | Reserves no more than owned quantity | Unchanged |
| `UnresolvedExit` | Unchanged | Retains remainder as `UNKNOWN` | Unchanged |
| `CancelIntent` | Unchanged | Retained as `CANCEL_REQUESTED` | Unchanged |
| `CancelReceipt` | Unchanged | Releases exactly the reconciled remainder | Unchanged |
| `ExitFill` | Reduces by the incremental fill quantity | Reduces by the same quantity | Adds only that supplied fill's result and cost |
| `SessionBoundary` or `QuoteReference` | Unchanged | Unchanged | Unchanged |

An exit reservation blocks another exit request until it is filled or explicitly reconciled. Cancelling an exit releases the reservation, not the position: another reducing exit can then be recorded, but a new entry remains blocked. A cancellation receipt asserts that the simulator reconciled the exact remaining request quantity; a later fill for that cancelled request is refused rather than silently imported.

Delayed and out-of-order partial exit receipts are allowed if their quantities, request, contract and execution times remain valid. A persistent maximum execution timestamp prevents a later entry receipt from backdating a new position into already reconciled inventory. Observation times cannot regress, and a different observation day requires an explicit session-boundary record.

## Returns are incomplete while inventory remains

Prices are integer nano-prices on the existing 6E tick grid of 50,000 nano-units. Closed gross contract-ticks are the signed entry-to-exit price difference in ticks, multiplied by the closed quantity. The configured extra round-trip tick cost is charged once per closed contract, including partial fills. The default is one extra tick, an assumption rather than a measured broker fee.

`closed_net_contract_ticks` exposes known closed portions. `complete_simulated_net_contract_ticks` is `None` whenever any position remains open. There is no zero-return imputation, reference-mark liquidation, overnight reset, daily balance reset or inferred fill. No USD cash, margin, commission schedule, CFD spread, equity curve or profitability score is produced. A caller must not score only the resolved subset as if the whole scenario completed.

## Receipts and references are claims, not authentication

Fill and cancellation records require an evidence identifier and a SHA256 for the supplied incremental paper-simulator receipt. Reusing either under a new event identifier is rejected. The ledger validates the typed record and internal consistency; it does not open or authenticate the receipt file, prove broker execution, or establish that the supplied price crossed an executable book.

Likewise, `source_manifest_sha256` is a pinned caller lineage claim, not automatic verification of a source manifest or its archives. A `QuoteReference` includes the same dated contract, source session, receive timestamp, native cursor and bid/ask. Its cursor and clock cannot regress or be rewritten with different quote content. The caller is responsible for establishing that it was a completed published quote; the ledger cannot prove live feed health or provider provenance.

The existing development/reserved calendar guard is applied before price validation. This version accepts only the declared dated 6E development contracts and dates. It is not usable as a current live-account journal without a separate reviewed contract.

All authority flags remain false: `training_eligible`, `strategy_scoring_allowed`, `trading_enabled`, `promotion_allowed`, `broker_execution_confirmed` and `receipt_provenance_verified`.

## Durable, bounded writes

Opening an existing ledger is read-only by default. Explicit creation claims a new file exclusively and never overwrites, adopts, resets or migrates an existing database. Missing, empty, oversized, incompatible or corrupt evidence is refused, not repaired. A failed initialization retains the claimed file as evidence. Paths through symlinks or junctions are refused.

The pinned configuration, protocol and 39 implementation-source hashes are checked against the journal on every replay. Events form an ordered hash chain with immutable update/delete triggers and exact schema checks. Each append runs in one SQLite transaction with full synchronous commits and requires the caller's expected tip SHA256. Concurrent stale writers are refused. An exact duplicate event is an idempotent no-op, even with its original stale tip; changed content under that identity is rejected. Position and exit-request identifiers cannot be reused.

Limits are 10,000 events, 8,192 bytes per metadata/event record and a 128 MiB database. Every snapshot replays the complete bounded journal; this is not a high-frequency production storage engine. One SQLite connection is used per thread. Increasing bounds, changing costs or editing pinned source is not a supported way to resume an existing ledger.

An independently retained last trusted tip can detect valid-prefix truncation:

```python
from ai_trader.research.six_e_position_ledger import ScenarioLedger

# The caller supplies the existing path, original configuration and trusted tip.
with ScenarioLedger(existing_path, original_config) as ledger:
    state = ledger.snapshot(expected_tip_sha256=last_trusted_tip)
    assert state.complete_simulated_net_contract_ticks is None or state.position is None
```

This example reads only; it does not create a ledger or start a strategy. Local hashes and SQL triggers are not protection against a privileged actor rewriting both evidence and trusted pins. Without an external trusted tip, an otherwise valid truncated prefix can look valid. Synthetic abrupt-process-exit tests cover transactions before and after commit, not physical power-loss guarantees or exactly-once execution in an external system.

## Verification and unchanged research

Run the new synthetic tests from PowerShell:

```powershell
Set-Location C:\Users\pabta\Projects\ai-trader
.\.venv\Scripts\python.exe -m pytest -q tests/test_six_e_position_ledger.py
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check src/ai_trader/research/six_e_position_ledger.py tests/test_six_e_position_ledger.py
```

Tests exercise cross-day restart recovery, unknown reservations, cancellation reconciliation, partial and delayed fills, contract changes, costs, duplicate evidence, stale writers, transaction rollback, schema/source drift and bounded corruption refusal. They use temporary synthetic databases; no real paper account is imported or changed.

The final focused regression passed 409 Python tests: 78 new ledger tests, 183 existing liquidity/quote-research tests and 148 existing paper-account, lifecycle, journal and durable-gateway tests. All 38 JavaScript workbench tests also passed. Ruff and formatting checks passed for the new implementation and tests.

The complete project baseline run finished with 4,378 passed, one optional Nautilus skip and ten collection errors. The ten errors are the existing Windows Application Control block on PyTorch's `c10.dll`. Windows security settings and dependencies were not changed. That baseline collected before this ledger test file was added; the focused regression run covers the new code separately, with overlapping tests. A fully green project suite and new Qwen training remain blocked by the environment issue.

The original 38-source whole-cohort registration still validates all 196 accepted sessions. The original collection completion/verification, CPU model/evaluation and quote-observability artifact pins were rechecked unchanged. No historical replay, relabeling, fitting, model inference, reserved-price access, network capture, broker access or trading occurred in this work. See `docs/6E_QUOTE_OBSERVABILITY_REVIEW_20261008.md` for the prior findings and their limits.

## Next integration gate

Next, build a separately registered continuous-account replay/receipt adapter that selects only causal strategy actions, persists one account across the declared sessions, and carries missing exits without resetting or scoring a successful subset. Its complete simulator receipts and input provenance must be independently verifiable. Preserve the original labels and models as controls; do not infer a fill from quote age alone.

Before interpreting that replay economically, specify capital/risk constraints, broker-specific costs, latency and stale-feed refusal, pending-entry handling, roll/expiry treatment and termination with open liabilities. This ledger alone does not implement those features, scaling into a position, multiple simultaneous positions, external late-fill reconciliation, current live data or autonomous training. Futures signals still do not prove cTrader CFD fills. Retraining and promotion require defensible execution targets and a genuinely untouched cohort, not a more complete-looking closed-return total.
