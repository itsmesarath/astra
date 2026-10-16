# Durable evidence, paper orders and account recovery

Implemented 2026-09-24 in `src/ai_trader/trading/trade_journal.py`, `paper_lifecycle.py` and
`paper_account.py`. This stores evidence, entry/exit orders and incremental fills, with opt-in
flat-start paper-account reconstruction. The opt-in [durable paper adapter](DURABLE_PAPER_GATEWAY.md)
now uses these records; the legacy intent-only gateway remains unchanged.

## Contract

- One SQLite file belongs to one `run_id` and one mode: `research_only` or `paper`.
  Opening with another identity fails. No live/testnet mode is accepted.
- `TradeJournal.create` exclusively creates a new file; existing files are never overwritten.
  The parent directory must already exist. Normal construction opens an existing file only.
- `append_case` and `append_review` return `True` after a committed new record, or `False`
  for a byte-equivalent retry. Reusing an ID with different content raises `JournalConflict`.
  Retries do not replace the original recording timestamp.
- Reviews must reference the exact case already stored. One trade ID cannot be linked to two
  cases. Distinct review IDs retain revisions separately; the journal does not choose a winner
  or treat the latest review as ground truth.
- Reads verify checksums, reconstruct validated immutable records, and check case/review bindings.
  SQL values are parameterized. Update/delete triggers protect normal SQL access, including
  metadata. An owner able to rewrite the database can defeat those triggers/hashes; this is not
  signed or tamper-proof storage, encryption or a substitute for backups.
- SQLite immediate transactions serialize writers. Inserts use `synchronous=FULL`; exceptions
  roll back and propagate. Use a separate connection per thread. Lock waits are bounded to five
  seconds, not silently retried forever. Read-only opens also enforce SQLite read-only access.
- Application/schema IDs reject unrelated databases and future schema versions. New files use
  schema 6. Version-1 files still support case/review access and version-2 files retain their
  entry-order API. Account/exit APIs require an explicit `journal.upgrade_schema()` call for older
  files. Schema 3 retains its funded-account API; the durable gateway supports schemas 4–6,
  the bounded runner supports 5–6, and replay source binding requires 6.
  Back up the closed file first. The v1-v5-to-v6 upgrade is one transaction, retains
  cases/reviews/order payloads/event sequences, checks foreign keys and never runs on open.
  Upgrading does not initialize funding or infer account history. A failed creation
  may leave its newly created file for diagnosis;
  it is not automatically deleted or reused.

## API usage

Use a selected path under an ignored local directory such as `data/processed/`. Do not commit
private journals or put them into model prompts. `case` and `review` below are validated records
from `trade_case.py`, created by the caller; this snippet is an API sketch, not a trading runner.

```python
from pathlib import Path
from ai_trader.trading.trade_journal import TradeJournal

path = Path("data/processed/research-run-1.sqlite")
with TradeJournal.create(path, run_id="run-1", mode="research_only") as journal:
    journal.append_case(case)
    journal.append_review("review-1", review)

with TradeJournal(path, run_id="run-1", mode="research_only", read_only=True) as journal:
    original = journal.get_case(case.case_id)
    stored_review = journal.get_review("review-1")
```

Creation/opening is separate deliberately. Do not recreate or truncate a journal to recover from
a failure. Close connections before moving/copying files; a consistent backup procedure still
needs implementation. Corruption or IO errors are failures, not permission to start an empty ledger.

## Paper-entry lifecycle contract

`PaperEntryOrder(order_id, case_id, case_sha256, quantity_btc, requested_at_ns)` binds to an
exact stored, approved `ENTER_LONG` paper case. Request time must lie between the decision
and exclusive expiry, and quantity cannot exceed the recorded risk approval. Only one entry
order per case is allowed, even if canceled/rejected; a replacement needs a fresh risk case.
BTCUSDT spot BUY is implicit in this entry-only type; exits use `PaperExitOrder` below.
Stored approval is evidence, not authorization to bypass fresh runtime risk checks.

`append_order` durably records PREPARED; `append_order_event` appends a validated
`PaperOrderEvent`. `order_ids`, `order_events` and `order_state` support inspection/reconstruction.
Exact retries of the original event ID return False, including after restart. Changed content
or reuse of a fill ID under another event/order raises `JournalConflict`. Fill IDs are unique
within the journal run. Order/event SQL inserts and lifecycle validation share one immediate
transaction, preventing concurrent overfills. Events and orders have append-only triggers.

| Observation | Allowed prior state | Reconstructed state |
| --- | --- | --- |
| SUBMITTED | PREPARED, UNKNOWN | SUBMITTED or PARTIALLY_FILLED |
| UNKNOWN | PREPARED, SUBMITTED, PARTIALLY_FILLED, CANCELED | UNKNOWN |
| CANCELED | SUBMITTED, PARTIALLY_FILLED, UNKNOWN | CANCELED |
| CANCEL_CONFIRMED (schema 3) | CANCELED, UNKNOWN | CANCEL_CONFIRMED; reconciled terminal remainder |
| REJECTED | PREPARED, SUBMITTED, UNKNOWN; no fills | REJECTED |
| FILL | SUBMITTED, PARTIALLY_FILLED, UNKNOWN, CANCELED | FILLED at full quantity; otherwise preserve UNKNOWN/CANCELED, or PARTIALLY_FILLED |

SUBMITTED after UNKNOWN means **explicit reconciliation of the original order**, never an
instruction to submit again. FILLED, REJECTED and CANCEL_CONFIRMED are terminal in this simulator
contract. CANCEL_CONFIRMED asserts that the caller reconciled all fills and the canceled remainder;
it is not an automatic interpretation of a cancellation notice.
A delayed incremental fill can arrive after cancellation: the unfilled remainder stays canceled,
or the order becomes FILLED. Impossible transitions raise and roll back; a future runner must
halt/quarantine such incidents, not silently drop factual exchange reports or retry execution.

FILL contains `fill_id`, `executed_at_ns`, incremental `quantity_btc`, `price_usdt`, and `fee_usdt`.
It is **not** a cumulative gateway receipt. Converting gateway receipts to unique incremental
fills remains future integration work. Observed timestamps are nondecreasing per order; fill
execution must be between request and observation (late reporting is allowed). These supplied
timestamps are not authenticated and do not establish replay availability by themselves.

Amounts are finite Decimal, with at most 28 coefficient digits and exponent between -18 and 18;
quantities/prices are positive and fees nonnegative USDT. Non-USDT fees/rebates are unsupported.
Reconstruction uses a local 100-digit context, independent of caller precision, and sums quantity,
gross fill notional and fees separately. Order state alone does not calculate PnL/balances.
There are no trading/network side effects. New gateway submissions still use the existing
in-memory path unless the caller explicitly uses the separate durable adapter.

## Funded account and risk-reducing exits

For a new paper run, call `initialize_account(PaperAccountSeed(initial_cash_usdt,
initialized_at_ns))` **before any orders**. Starting cash is a positive Decimal in USDT; initial
BTC is zero. Funding is immutable, exact retries are harmless, and conflicting funding fails.
Do not use it as a deposit API. Existing unfunded order histories cannot be retroactively funded;
keep them as evidence and start a separately identified funded run when appropriate.

`append_exit_order(PaperExitOrder(order_id, entry_order_id, quantity_btc, requested_at_ns, reason))`
records a BTCUSDT spot SELL against that entry's known remaining BTC. It needs no new analyst
case or entry approval and works after the original case expiry, including when that entry is
UNKNOWN but has confirmed partial fills. It does not bypass inventory/account integrity checks.
The exit cannot reference another exit, exceed its entry's holdings or reuse another order ID.
The same `append_order_event` API records entry and exit fills; IDs remain run-global.

Outstanding exits reserve their unfilled BTC, including PREPARED, UNKNOWN and CANCELED exits.
This prevents concurrent exits or cancel/fill races from double-selling inventory. A CANCELED
notice does not release the reservation. After all fills are reconciled, CANCEL_CONFIRMED
releases only the canceled remainder; FILLED and zero-fill REJECTED also release reservations.
Any fill after terminal confirmation is an incident, not a reason to silently overwrite history.
The future runner must supply trustworthy simulator reconciliation before confirming cancellation.

`account_state()` reconstructs from a consistent SQLite snapshot in global event commit order:

- Cash in USDT, BTC holdings, entry-specific remaining cost basis and exit reservations.
- Realized net PnL, total USDT fees, unresolved order IDs and last event observation time.
- BUY deducts notional plus fee and capitalizes both into entry cost. SELL adds net proceeds
  and removes proportional average cost from its entry lot. A full close consumes its exact
  residual cost, avoiding stranded rounding dust. PnL is `cash + remaining_cost - initial_cash`;
  fees are already included and must not be subtracted again.

Partial cost allocation uses 100-digit Decimal arithmetic; repeating ratios are rounded at that
precision. This is a paper research convention, not exchange settlement/tax accounting. Events
must have nondecreasing observation times across the funded account. Backdated execution times
do not rewrite previously known account history. New requests cannot predate existing requests
or the last observed event. Requests/events that would overdraw cash, short a lot, overfill an
order or overreserve BTC roll back atomically, including their event insert.

Account validation is opt-in through initialization. Legacy unfunded entry journals still work
but cannot produce account state or accept exits. No BTC fees, rebates, deposits, withdrawals,
opening BTC balances, entry-cash reservation, mark-to-market equity, daily loss reset or drawdown
checkpoint is implemented. Negative-cash rejection is not a pre-execution buying-power gate.
A future gateway must validate before simulating a fill, not discard a real fill afterward.
Recovery returns an immutable view; it does not restore the existing broker object's balances.

These APIs perform no network or execution operations. They do not trigger stops or take profit.

## Runnable tests and actual results

No market data, credentials, torch, Nautilus or network is required:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_trade_journal.py tests/test_paper_lifecycle.py
.venv\Scripts\python.exe -m pytest -q tests/test_paper_account.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

Observed: **110 focused tests passed** (30 evidence-journal + 47 lifecycle + 33 account), Ruff lint
and formatting
passed. Full regression attempt:
**608 passed, 1 optional-Nautilus skip, 10 collection errors** from the pre-existing Windows
Application Control block on PyTorch. This is not a fully passing suite.

Tests cover exact retry after reopen, conflicting IDs, mode/run isolation, rejected/abstained
cases, review revisions/binding, read-only access, malformed typed payloads, corruption detection,
injected insert failure, SQL-like identifiers and concurrent independent connections. A child
process exits abruptly with an open transaction: committed data survives and its uncommitted
insert is rolled back on reopen. This tests process interruption, not physical power-loss behavior
on every filesystem/device. No runtime journal was created outside test temporary directories.
Lifecycle tests also cover canceled/late fills, UNKNOWN reconciliation, partial/full fills,
concurrent duplicates/overfills, global fill identity, precision, explicit migration/rollback,
read-only access, and abrupt process termination after a committed fill plus uncommitted event.
Account tests cover hand-calculated PnL/fees, proportional exits, cost residuals, global timestamps,
concurrent reservations, a consistent read during a concurrent WAL-mode fill, migration of populated
v2 journals and rollback, process interruption, corrupt funding, and exit independence from entry
case expiry/UNKNOWN status. All databases are temporary synthetic test fixtures.

## Remaining work

The legacy paper gateway remains unchanged and its request cache remains in-memory. The separate
durable quote adapter records atomic simulated outcomes and risk checkpoints (see its linked guide).
Neither adapter makes remote order submission exactly-once, restores the legacy broker's balances,
automatically reconciles unknown
orders or execute stops. It does not prove a case was saved before an external side effect or that
a reviewed trade actually filled. Those require a separately tested lifecycle/ledger integration.

Retrieval is explicit-ID/current-state, not historical as-of/fold-filtered memory. Stored wall-clock
recording time is not a monotonic clock or trustworthy historical availability proof. Do not feed
these records into replay/model training without the planned memory isolation contract.

The [bounded paper controller](PAPER_RUNNER.md) now supplies per-tick health gates, marks and
protective exits; the [capture replay bridge](CAPTURE_PAPER_REPLAY.md) supplies validated offline
observations. Next: operational capture/reconnect supervision. Recorder recovery and
native-library environment diagnosis remain separate open work.
