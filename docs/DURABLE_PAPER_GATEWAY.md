# Opt-in durable paper gateway

Implemented 2026-09-24 in `src/ai_trader/trading/durable_paper_gateway.py`. This is an
offline, quote-only simulator attached to the durable journal, not Binance connectivity,
an unattended runner, or evidence of strategy profitability. No model or market feed starts.

## Contract and initialization

- Schema 4 introduced append-only configuration, quote requests and risk checkpoints; schema 5
  adds the opt-in runner, and schema 6 adds replay bindings. The gateway supports schemas 4–6.
  Explicit `upgrade_schema()` moves older
  versions to the current journal schema transactionally; existing record APIs stay available.
  Back up a closed journal before upgrading. No real journal was migrated during development.
- Initialize a new paper account with positive USDT cash and zero BTC, then call
  `DurablePaperGateway.initialize(journal, config)` **before preparing any orders**. It does not
  adopt an old order history or guess its historical risk peak/daily-loss baseline.
- Normal `DurablePaperGateway(journal, config)` opens an initialized adapter without resetting
  anything. Limits, execution costs and maximum quote age are immutable per run. Config changes
  conflict, including reassigning the adapter's configuration during use.
- Entries still require the exact durable approved case. Its `risk_config_sha256` must equal
  `config.risk_config_sha256` (SHA256 of canonical serialized `RiskLimits`). Fresh deterministic
  risk checks are performed at execution, regardless of the case's recorded approval.
- `execute(PaperQuoteRequest(order_id, bid_usdt, ask_usdt, quote_at_ns, observed_at_ns))`
  acts on one untouched PREPARED entry or exit. It is **not** an implementation of the old
  intent-only `ExecutionGateway.submit` protocol: preparation is an explicit additional step.
  Existing `PaperExecutionGateway`, `PaperBroker`, runner routing and live stubs are unchanged.

API sketch (records/configuration supplied by the caller, not a trading command):

```python
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway, PaperQuoteRequest

# journal is a new funded paper TradeJournal; config is a validated PaperGatewayConfig.
gateway = DurablePaperGateway.initialize(journal, config)
journal.append_case(case)  # case.risk_config_sha256 matches config
journal.append_order(entry_order)  # immutable approved quantity and original case binding
receipt = gateway.execute(
    PaperQuoteRequest(
        entry_order.order_id,
        bid_usdt,
        ask_usdt,
        quote_at_ns,
        observed_at_ns,
    )
)

# After closing and reopening the same journal with its original run identity:
recovered = DurablePaperGateway(journal, config)
receipt = recovered.get_receipt(entry_order.order_id)
account = journal.account_state()
risk = recovered.risk_checkpoint()
```

The existing case and account contracts, amount precision limits, funding restrictions and
entry-specific exit reservations are documented in [TRADE_JOURNAL.md](TRADE_JOURNAL.md).

## Atomic simulation and retries

One SQLite immediate transaction records the immutable quote request, checks cash/risk,
appends either SUBMITTED + one incremental FILL or a REJECTED event, and checkpoints risk.
Journal writes compose through savepoints. Validation/IO/checkpoint failures roll back the
entire simulation. There is no mutable broker account or external exchange side effect to
reconcile: the committed journal is the account authority. Separate connections serialize
concurrent requests before reading current cash, preventing double spending.

An exact retry returns the original cumulative `ExecutionReceipt`, even after the case expires.
Changed prices/timestamps under the same order ID conflict rather than refilling. Rejected
requests are durable too; retrying one does not reevaluate it with newer risk settings. A new
decision needs a new approved entry case/order. Receipts are not additional incremental fills.

If the process dies before commit, a retry can simulate the original untouched request subject
to its original timestamp contract. If it dies after commit but before returning the receipt,
the original result is recovered without another fill. This is tested for local process exit,
not exactly-once remote execution or guaranteed physical power-loss durability on every device.

## Risk and time semantics

Only BTCUSDT long/flat spot simulation is supported. Buy fills cross the ask; sells cross the
bid, with the existing adverse-slippage and USDT taker-fee calculation. Quantities fill completely;
there is no queue/depth/latency/partial-fill model in this adapter.

Before an entry fill, the adapter checks fresh/nonfuture bid/ask, execution-time case expiry,
risk-config identity, cash including fees, order/position quantity and notional limits, kill
switch, daily realized loss and drawdown. A projected post-buy bid-marked equity check includes
spread/slippage/fees in drawdown. Rejections are durable and do not change cash or inventory.

Equity is marked conservatively at bid on fresh execution requests and explicit `mark_quote` calls;
peaks include both pre/post
fill marks. Stale quotes cannot raise the peak. The checkpoint persists peak equity, kill switch,
UTC day, realized-PnL baseline/cumulative value, event cursor and observation timestamp.
Daily loss uses this journal's fee-inclusive **realized** PnL convention: buy fees are capitalized
until inventory is sold. It is not a daily total-equity-loss limit. Drawdown separately includes
unrealized loss at the sampled quote.

`set_kill_switch(active, observed_at_ns=...)` persists the Boolean state. Risk time cannot regress.
Time is caller-supplied Unix-epoch nanoseconds; UTC days are integer 86,400-second intervals. At
the first request/control observation of a later day, the prior cumulative realized PnL becomes
the new baseline. The all-time peak and kill switch do **not** reset at midnight or restart.
A future runner must provide a trusted clock and receipt-time freshness; these APIs alone do
not prove that a caller's quote/timestamp is honest or actually current.

Risk-reducing exits use recorded entry-specific inventory and bypass entry case expiry, new
analyst approval, kill-switch entry blocking, daily-loss and drawdown entry gates. They still
require a valid fresh quote, coherent accounting and sufficient unreserved BTC. An uncheckpointed
manual ledger event (including UNKNOWN) halts the adapter until explicit reconciliation; it is
never silently treated as permission to retry. Reconciliation tooling is not yet implemented.

## Scope limits and next step

This implements a narrow durable execution adapter, not the autonomous bot. `mark_quote` can persist
fresh bid marks without an order; `heartbeat` advances risk time without an unreliable price.
The opt-in [bounded controller](PAPER_RUNNER.md) uses them for supplied-tick health/protection.
No quote/timer arrives unless a caller supplies it. Outstanding orders are not auto-executed
after restart. Imported positions, deposits, non-USDT fees, live orders and broker-object restoration
are unsupported. Account reads currently replay the journal and are correctness-first, not a
high-throughput order-book engine. Optional read-only recovery never mutates the journal.

The [capture replay adapter](CAPTURE_PAPER_REPLAY.md) now bridges validated recorded sessions.
Next harden the operational public-feed supervisor and bounded smoke-test workflow.
Order-book/CVD/liquidity strategy decisions and realistic L2/trade
replay still need their separate validation gates; this quote simulator must not be used as proof
of microstructure execution quality. No automatic live promotion or model training is enabled.

## Verification

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_durable_paper_gateway.py
.venv\Scripts\python.exe -m pytest -q tests/test_trade_journal.py tests/test_paper_lifecycle.py tests/test_paper_account.py tests/test_durable_paper_gateway.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

At the gateway slice's implementation: 38 new tests; 148 combined persistence/account/gateway tests
passed. Full attempt then:
646 passed, 1 optional-Nautilus skip, 10 unchanged PyTorch collection errors caused by Windows
Application Control. Ruff lint/format pass. This is not a fully passing suite. No native security
policy was changed. Tests cover restart/retry conflicts, concurrent cash claims, pre-fill vetoes,
kill/UTC loss/peak recovery, slippage/fees, read-only and corrupt state, v3 migration rollback,
injected checkpoint failure and abrupt process exits on both sides of commit.
See [CAPTURE_PAPER_REPLAY.md](CAPTURE_PAPER_REPLAY.md) for subsequent integration tests and current results.
