# Bounded, health-gated paper controller

Implemented in `src/ai_trader/trading/paper_runner.py` on 2026-09-24. This controller processes
caller-supplied ticks and approved cases. It has no network client, inference model, background
thread, trading CLI or live adapter. It is not yet an unattended Binance paper-trading service.

## Data and entry boundary

`PaperMarketTick` records a unique tick ID, source session, observation/receipt times (Unix-epoch
nanoseconds), bid/ask, last trade receipt, synchronization/readiness flags, the current microstructure
observation hash and an optional already-stored candidate case ID. A timer tick may carry the last
known quote; its original receipt time must be retained, not refreshed to pretend new data arrived.

`PaperMarketTick.from_observation` bridges the existing `MicrostructureObservation` schema, including
order-book quotes and a canonical content fingerprint. Readiness requires completed rolling trade
warmup, a valid evidence interval, liquidity-band coverage and top-N coverage on both sides. It
does not use retrospective session quality to authorize an earlier trade. CVD, absorption and
replenishment evidence remain in the source observation; this controller does not invent a signal.

Synchronization and last-trade receipt are supplied by the caller. These fields are assertions,
not authenticated proof. The future feed adapter must propagate engine invalidation on gaps,
resynchronize with fresh warmup, retain real receipt times, and bound exchange-event latency/clock
skew. This slice does not implement that adapter or validate every numerical feature in an arbitrary
manually constructed observation. It validates the values/flags it consumes.

Entry requires all of:

- A synchronized book and quote no older than the gateway's configured receipt-age limit.
- Ready microstructure features and a sufficiently recent trade receipt.
- Spread at or below the runner's declared threshold, in bps of bid.
- An approved stored ENTER_LONG case for this source session and exact observation fingerprint.
- Case decision time between observation receipt and the processing tick, with unexpired plan.
- No previous entry order for this case, and no protective-exit activity/block on this tick.
- Bid still above the stop, and the modeled slippage-adjusted buy price below take profit.
- The gateway's current cash, configuration, kill/daily-loss/drawdown and order/position checks.

The default API does not convert model output or unreviewed candidates into cases. A rejected,
missing, mismatched or expired candidate records an entry reason; it does not prevent a valid
protective exit. The runner does not implicitly resume a manually prepared entry order.

## Per-tick protection

Every synchronized, fresh tick marks bid-valued equity through `gateway.mark_quote`, even if no
entry is proposed or feature/trade readiness is insufficient. An unhealthy quote instead advances
the risk clock through `gateway.heartbeat`, without changing the peak using an unreliable price.
No ticks means no processing: this is event-driven sampling, not a running timer/watchdog service.

For each remaining entry lot, exit priority is:

1. Daily realized-loss limit.
2. Drawdown from the persisted sampled equity peak.
3. Bid at/below the recorded stop.
4. Bid at/above take profit.
5. Maximum holding time reached, measured from the first recorded fill's execution time.

Exits run before entries and independently of feature warmup, recent trades, entry spread gates,
new analyst approval, original case expiry and entry kill-switch blocking. Kill switch alone still
means "block entries," not "flatten now." A protective-exit tick never opens a replacement position.
Daily-loss/drawdown exits use the existing gateway's documented realized-PnL/day-reset conventions.

Stop and target levels are triggers, not guaranteed prices. A gap through the stop fills at the
current simulated bid minus configured slippage, not at the stop level. Maximum hold is acted on
at the next usable tick, not retroactively. Unknown or reserved exit inventory is never resubmitted
or double-sold; the result identifies entry lots blocked by outstanding exit reservations.

An unsynchronized/stale quote blocks all marking and simulated execution. Open lots appear in
`blocked_exit_entry_ids` to report that protection cannot safely execute; this does not assert that
a price trigger occurred. With fresh data restored, plans are reevaluated. There is no stale-price
liquidation, guaranteed exit during a feed outage, or external alert service in this implementation.

## Persistence, bounds and API

Schema 5 adds append-only runner configuration and tick/result tables; the runner also supports
schema 6's replay bindings. Older schemas require an explicit, transactional `upgrade_schema()`;
versions 1–5 retain their previous supported APIs.
Back up closed files before migration. No user journal was migrated as part of development.

Initialize a runner explicitly on an initialized, funded `DurablePaperGateway`. Its existing ledger
must match the gateway's risk checkpoint. This may include existing paper positions: original plans,
fill times, cash and risk are read from durable state rather than reset or guessed. Configuration
is immutable for the run. No action occurs just because the controller was opened.

```python
from ai_trader.trading.paper_runner import PaperRunner

# gateway and runner_config are explicitly prepared by the caller.
runner = PaperRunner.initialize(gateway, runner_config)
results = runner.run(ticks, max_ticks=100)

# After reopening the same journal/gateway, without reinitializing balances:
resumed = PaperRunner(gateway, runner_config)
original = resumed.get_result(tick_id)
```

`process(tick)` performs one transaction covering the tick input/result, risk marks, generated
entry/exit orders and simulated outcomes. Exact tick retries return the original result without
another mark or trade; changed content under the same ID conflicts. Regressing observation time
or receipt time within the current source session fails closed. Read-only `get_result` verifies
the stored content and receipt bindings. Imported/uncheckpointed ledger events still require
explicit reconciliation; the runner never automatically clears UNKNOWN states.

`process_with_case_builder(tick, case_id=..., build_case=...)` is a separate opt-in synchronous
policy seam. It requires a candidate-free tick and provides an immutable `PaperDecisionContext`
after marks/protection, before entries: tick, quote health, protection flag, account and durable
risk checkpoint. The trusted builder must return a new paper case matching the ID, source, time,
observation hash and gateway risk configuration. It must not perform IO or mutate the journal;
detected SQLite changes and coroutine returns roll back the tick. This is not a sandbox for
untrusted code. Exceptions also roll back simulated protective fills in that transaction.

The caller must bind policy/configuration identity to its case IDs and run identity. Exact retries
validate and return the saved case/result without invoking the builder against a later account.
Protection still vetoes same-tick entry even if a builder returns an approved proposal. The
gateway independently rechecks risk; a generated approval cannot override its kill switch.
The [offline microstructure adapter](MICROSTRUCTURE_PAPER.md) implements this contract for one
frozen research hypothesis and skips entry-policy evaluation entirely during protection.

`run(ticks, max_ticks=...)` requires an integer budget from 1 to 10,000 and consumes no extra item
beyond that budget. It does not sleep, poll, fetch data or continue after exhaustion. Input iterators
must themselves be bounded/nonblocking; this API cannot interrupt a blocking producer. Journal
reconstruction is correctness-first and not optimized for high-throughput L2 replay. Disk retention,
capture quotas, real-time latency limits, a supervisor and shutdown/alert policies remain future work.

## Verification and next step

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_paper_runner.py
.venv\Scripts\python.exe -m pytest -q tests/test_trade_journal.py tests/test_paper_lifecycle.py tests/test_paper_account.py tests/test_durable_paper_gateway.py tests/test_paper_runner.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

At this controller slice's implementation: 45 new tests and 193 combined persistence/account/gateway/
runner tests passed. Full suite attempt then: 691 passed, 1 optional-Nautilus skip, 10 collection errors caused by Windows
Application Control loading PyTorch. Ruff lint/format pass. This is not a fully passing suite.

Tests cover causal microstructure readiness, exact stop/target/time boundaries, gap pricing, daily
loss and between-trade drawdown protection, reserved inventory, stale-feed deferral/recovery,
duplicate/concurrent ticks, corruption, migration rollback, and abrupt process exit on both sides
of commit. All market inputs and databases are synthetic temporary fixtures; no feed was started,
no real account was contacted, no security policy was changed and no model was trained.

The [capture replay adapter](CAPTURE_PAPER_REPLAY.md) now tests recorded snapshot timing, sequence gaps,
reconnection/warmup and receipt-time propagation end to end; see that guide for current test results.
The [bounded capture/smoke workflow](CAPTURE_SUPERVISION_AND_SMOKE.md) and explicitly activated
[offline strategy simulation](MICROSTRUCTURE_PAPER.md) are now available and tested synthetically.
Operational feed validation and a supervised forward paper service remain. Proposals must remain
order-book/CVD/liquidity-based and separately evaluated. Quote-only fills are not evidence of L2
execution realism or profitability; protected historical evaluation/model-training gates remain.
