# Paper now, live-capable architecture later

## Connectivity and mode are separate choices

Public Binance market data can arrive over the internet while agents, inference, training and
storage run locally. Paper execution simulates orders; it does not require the data feed to be
offline. Historical evaluation remains local and must never submit exchange orders.

The operator chooses one execution environment at startup:

| Mode | Current implementation | Credentials |
| --- | --- | --- |
| `paper` | Working Spot execution gateway around the existing paper broker | None |
| `spot_testnet` | Recognized configuration; startup fails closed | Future testnet-only credentials |
| `spot_live` | Recognized configuration; startup fails closed | Future restricted Binance account credentials |

This is the execution seam and mode-selection foundation, **not a working live Binance adapter**.
No authenticated client, signing logic, account lookup or order endpoint is added in this change.
Changing a setting does not enable real-money execution, and unsupported modes never silently
fall back to paper. There is no profit-triggered or model-controlled mode switch.

Check mode availability without starting a feed or submitting an order:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.runtime --mode paper --check
.venv\Scripts\python.exe -m ai_trader.trading.runtime --mode spot_live --check
```

The first command succeeds. The second exits with code 2 and explains the missing live prerequisites.
The CLI is a startup check, not a trading loop or a switch for the historical backtester.

## Stable boundary for strategy and execution

New runners call `create_execution_gateway(ExecutionConfig(...), ...)`, then use the common
`ExecutionGateway` protocol. An `ExecutionRequest` contains a caller-generated request ID, a
BTCUSDT LONG/FLAT intention, sizing and an observed quote. Strategies and local agents do not
receive account credentials or construct exchange requests.

The implemented paper gateway:

- Retains the existing deterministic risk checks and fee/slippage simulation.
- Restricts the new interface to Spot long/flat behavior and checks cash including fees/slippage.
- Deduplicates repeated requests; reusing an ID for different inputs is an error.
- Serializes submissions so concurrent duplicate requests cannot create duplicate paper fills.
- Preserves the kill switch: reject new exposure while allowing a long position to close.
- Returns cumulative receipts through a common status model rather than assuming submission is
  execution. Pending, partial, canceled and unknown states are reserved for future adapters.

Paper deduplication is in-memory, per gateway instance, capped at 10,000 requests without eviction.
It is not restart-safe or an exchange reconciliation mechanism. Cached rejections/no-ops stay
unchanged; a new attempt uses a new ID. A repeated receipt must not be booked as a second fill.
At the cap, stop/archive the run before starting a new paper session; do not silently forget IDs.

Each factory call creates an independent paper portfolio. Configuration exposes separate
`execution/paper`, `execution/spot_testnet` and `execution/spot_live` namespaces for future
persistence, but does not yet create durable mode-specific ledgers. Never transfer paper cash,
positions or execution acknowledgements into a live account. Switching environments will require
stopping the old runner and reconciling the new account, not changing a flag mid-position.

Existing historical simulations keep their paper-only broker path, including legacy research
short simulations. The new Spot gateway does not make those historical paths live-capable.

## What must exist before live mode can be enabled

1. An authenticated Binance Spot adapter with an explicit environment and restricted credentials.
   Local model inference needs no paid model API key; Binance trading still requires exchange
   authentication. See [Binance new-order documentation](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints).
2. Exchange filters, available/locked balances, fee assets, clock synchronization, stale-quote
   rejection, rate-limit handling and a validated symbol allowlist.
3. Durable request IDs and execution events, order-status reconciliation, cancellation and partial
   fill accounting. An ambiguous timeout must trigger reconciliation, not blind resubmission.
   Exchange client IDs alone are not permanent deduplication: Binance documents reuse after a
   previous order has filled.
4. Independent risk checks on actual account state, cash/exposure caps, session-loss and drawdown
   stops, emergency cancellation/flattening procedures, and restart recovery tests.
5. Tested testnet behavior plus prospective paper evidence under realistic costs. Testnet checks
   operational correctness; it does not establish production liquidity or profitability.
6. Explicit operator arming tied to the selected account, mode, strategy version and capital/risk
   limits. Arming must be separate from model promotion and revalidated after restart.

The interface reduces future strategy rewrites; it does not eliminate the substantial adapter,
reconciliation and operational testing needed for live execution. Existing simulator and
timestamp-isolation repairs remain necessary before interpreting paper profitability.

## Training from Binance data and paper trading

Start with archived public Binance data and recorded prospective market streams. Build causal
features and labels after their outcome horizons, with session-exclusive chronological splits.
Log paper decisions, costs, rejections, fills and outcomes with model/data versions. A paper run
produces training/evaluation evidence; it does not automatically train Qwen.

Train numerical baselines and later LOB/Qwen adapters in versioned batches. Include losing and
abstained examples; use counterfactual labels only where the replay can support them and identify
them as simulated. Evaluate candidates against fixed baselines, stress costs and untouched future
blocks. Keep the active paper model stable until a candidate passes promotion checks.

Profitable simulated results are a prerequisite to investigate, not a guarantee of live returns.
Neither training, agent memory, nor a successful promotion gate may change the execution mode.
