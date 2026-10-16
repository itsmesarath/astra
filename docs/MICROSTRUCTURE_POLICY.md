# Registered microstructure research policy

Implemented 2026-09-24 in `trading/microstructure_policy.py` and
`research/microstructure_trial.py`. This adds a deterministic, research-only policy-to-case
adapter. It does not turn on the paper runner, choose a profitable strategy, fit a model,
download data, submit orders or alter existing datasets/journals.

## Hypothesis and abstention

The `bid_replenishment_cvd` hypothesis screens for an intact bid absorbing aggressive selling,
repeated bid replenishment, positive rolling CVD, positive best-level order-flow imbalance (OFI),
positive top-N book imbalance and sufficiently greater bid-side liquidity inside the configured
price band. Ask-side absorption vetoes the proposal. This conjunction is **not calibrated**;
it may abstain often or have no economic edge. Replenishment/absorption are existing L2/trade
heuristics, not confirmed iceberg identity, hidden size or order ownership.

Every threshold must be supplied explicitly. There are no tuned defaults, optimizers, outcome
inputs or model calls. The alternative `abstain` rule is a no-trade control; evaluating it requires
its own frozen registration/output. This does not yet provide economic comparison metrics.

Before considering a proposal, the adapter requires:

- A current depth observation matching the tick's source, timestamp, quote and content hash.
- A synchronized book, fresh quote/trades, completed rolling warmup, valid attribution interval
  and both-side top-N/liquidity-band coverage.
- No unmatched or pending trade attribution, existing inventory or unresolved orders.
- Consistent finite feature values, strict Boolean readiness flags, acceptable spread and every
  declared signal threshold. Malformed/mismatched input raises instead of inventing a case.

Snapshot, trade-only, gap, stale and footer frames produce explicit no-action cases. Signal
failures and risk rejections are retained, not filtered out. The first reason in the documented
code order is recorded; one no-action case does not imply every subsequent check passed.

## Units and sizing

`MicrostructurePolicyConfig` requires these declared settings:

| Settings | Meaning / units |
| --- | --- |
| `rule` | `bid_replenishment_cvd` or `abstain` |
| `minimum_cvd_btc`, `minimum_ofi_btc` | Positive base-BTC flow thresholds, not USDT volume |
| `minimum_book_imbalance` | Positive fraction below 1; existing `(bid_depth-ask_depth)/(bid_depth+ask_depth)` |
| `minimum_bid_ask_liquidity_ratio` | At least 1, comparing depth inside the registered price band |
| `minimum_replenishment_intervals` | Integer 2–1,000; current engine's repeated-evidence flag must also hold |
| `maximum_spread_bps` | Spread divided by best bid, in basis points |
| `maximum_trade_age_ns` | Local trade-receipt freshness, in nanoseconds |
| `entry_budget_usdt` | Maximum planned entry debit, including entry fee |
| `maximum_planned_loss_usdt` | Modeled stop-exit loss cap; **not** guaranteed maximum realized loss |
| `quantity_step_btc` | Explicit research rounding step; not verified Binance symbol filters |
| `stop_distance_bps`, `target_distance_bps` | Distances from current best bid, below 10,000 bps |
| `minimum_net_reward_risk` | At least 1, target reward/stop loss after both-side costs |
| `maximum_hold_ns`, `entry_ttl_ns` | Positive holding horizon and case lifetime, in nanoseconds |

Feature window/depth/attribution configuration, event lag/skew bounds, quote freshness, fees,
slippage and hard portfolio limits are separately frozen in the same registration using existing
typed configuration classes. Policy arithmetic uses a fixed 28-digit, round-half-even Decimal
context, independent of the caller's context.

With fee fraction `f`, adverse slippage fraction `s`, bid `b` and ask `a`:

```text
entry_price = a * (1+s)
entry_debit_per_btc = entry_price * (1+f)
stop_bid = b * (1-stop_bps/10000)
target_bid = b * (1+target_bps/10000)
stop_proceeds_per_btc = stop_bid * (1-s) * (1-f)
target_proceeds_per_btc = target_bid * (1-s) * (1-f)
planned_loss_per_btc = entry_debit_per_btc - stop_proceeds_per_btc
planned_reward_per_btc = target_proceeds_per_btc - entry_debit_per_btc
quantity = floor_to_declared_step(min(entry_budget/entry_debit_per_btc,
                                    planned_loss_budget/planned_loss_per_btc))
```

Reject a target that fails the configured after-cost reward/risk screen; reject a quantity below
one research step. Run the existing hard-risk engine, then check fee-inclusive cash and projected
drawdown after immediate entry costs. Hard-limit violations remain rejections with the original
proposal; they are not silently resized. Gaps, queue position, limited liquidity, partial fills,
latency and stop slippage beyond the scenario are not modeled here.

## Registration and protected data

`register_trial` writes a new bounded JSON envelope exclusively and fsyncs it. It reads no market
datasets. Declare `SourceDeclaration` records containing source-session ID, SHA256, header start
time, footer end time (epoch nanoseconds), and `research` or `reserved` role. The inventory must
contain both roles, be strictly chronological/non-overlapping, and put all reserved sessions after
research. Duplicate session IDs and duplicated capture hashes across aliases/roles are refused.

Registration freezes policy, features/replay, risk/cost settings, hypothetical cash, package Python
source fingerprint, Python/numpy/websockets versions, and a local registration time. It always
records `research_only` and `promotion_allowed: false`. This is a local reproducibility record,
not a signed approval, trusted timestamp, physical holdout lockbox or proof data were never seen.
It does not prevent declaring a different split in a separate trial; governance across trials and
formal train/validation/test model datasets remain separate work.

`evaluate_registered_capture` verifies registration/code/environment and rejects an unknown or
reserved session **before opening its supplied capture path or journal**. It then pins immutable
capture bytes, verifies the declared hash and header/footer times, and reconstructs features in
receipt order. Whole-file framing is an integrity prerequisite, not a predictive feature; future
prices and retrospective quality scores do not enter earlier decisions.

Research cases use the existing journal schema unchanged. Its immutable run ID hashes registration
identity plus source session. A new registration or another source requires a separate journal.
Case IDs bind that registration to stable replay tick IDs; case evidence hashes the observation
and as-of risk snapshot. These are local consistency checks, not authentication.

## Operator workflow (no automatic dataset selection)

Safe help checks and a complete synthetic CLI example:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.microstructure_trial --help
.venv\Scripts\python.exe -m ai_trader.research.microstructure_trial register --help
.venv\Scripts\python.exe -m ai_trader.research.microstructure_trial evaluate --help
.venv\Scripts\python.exe -m pytest -q tests/test_microstructure_trial.py::test_cli_register_and_evaluate_synthetic_spec
```

Registration can use the typed Python API or the `register` CLI. Its JSON specification requires
exactly `trial_id`, `sources`, `policy`, `replay`, `gateway`, and `initial_cash_usdt`, with all Decimal
values encoded as strings. Nested objects contain all fields of their corresponding dataclasses;
the synthetic CLI test supplies a complete example without recommending those fixture thresholds.
Existing files are refused; parents must already exist.

Templates below are **not** commands executed during development. Replace them only with approved
research inputs, actual declaration metadata and new output names:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.microstructure_trial register --spec data/processed/DECLARED_SPEC.json --output data/processed/NEW_REGISTRATION.json
.venv\Scripts\python.exe -m ai_trader.research.microstructure_trial evaluate --registration data/processed/NEW_REGISTRATION.json --capture data/raw/SELECTED_RESEARCH.jsonl --source-session DECLARED_RESEARCH_SESSION --journal data/processed/NEW_RESEARCH.sqlite --max-frames 1000
```

Each invocation evaluates at most 10,000 frames and commits atomically. Use `--resume` with the
same inputs and a larger prefix budget to continue; the budget counts from the beginning, including
previously stored cases. Exact retries deduplicate. A failure rolls back the current invocation,
preserving prior committed prefixes. New failed journals can retain metadata for diagnosis and an
explicit retry; nothing is deleted/reset automatically. Source/environment drift fails closed.
A registration alone does not prove evaluation completion. Exceptions before commit do not yet
create a separate incident/attempt report; retain the command failure output for diagnosis.

JSON output reports consumed frames, completion, market faults, reasons and case counts. Exit code
2 indicates a detected stream fault; exit code 0 can still describe a bounded/incomplete prefix or
only abstentions. Neither code means profitable, trained, ready or promoted.

## Authority and remaining work

All cases have `mode="research_only"`; paper journals reject them even when preliminary risk checks
say `APPROVED`. There is no option to promote them or enable paper/live execution in this module.
The evaluator assumes the **same flat hypothetical account on every frame**: no fills, cash depletion,
carried inventory, exposure trajectory, trade count, PnL or return metric is computed. It is a shadow
proposal audit, not a crypto backtester. The pure policy function can assess separately supplied
as-of risk snapshots, but does not read or modify actual account state.

A separate [offline paper simulation adapter](MICROSTRUCTURE_PAPER.md) now creates fresh paper cases
using ledger-derived risk, exits-first handling and explicit activation on every invocation. It does
not modify/promote this module's stored research cases or authorize forward paper deployment.
Next: separately authorize a small public capture/smoke run, and evaluate costs/outcomes under a
registered replay protocol with controls before model training or strategy promotion. No profitable
edge or training-ready dataset is established here.

Focused verification: 99 synthetic tests cover arithmetic, signal/health/risk abstention, malformed
evidence, future-data independence, immutable declarations, reserved-source refusal before loading,
code/config/source conflicts, source-specific restart identity and atomic failure recovery.
Final full-suite result: **1,022 passed, 1 optional-Nautilus skip**. Ruff lint/format pass.
Only synthetic fixtures/temp journals were evaluated. No market feed, market-data
training job, reserved source access, credentials, live connectivity, commit or push was performed.
