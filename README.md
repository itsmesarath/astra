# AI Trader

An experimental cryptocurrency market-microstructure research system.

## Initial scope

- Market: BTCUSDT on Binance
- Mode: research, backtesting, and paper trading only
- Language: Python
- Hardware: NVIDIA RTX 5080 Laptop GPU with 16 GB VRAM

## Safety boundary

Live trading is disabled during development. Model decisions will never directly control an exchange account. A separate deterministic risk and execution layer must validate every proposed action.

Agents and model inference run locally; public market data may use internet access. Execution
configuration now recognizes `paper`, `spot_testnet`, and `spot_live`, with paper as the default.
Only paper is implemented; testnet/live selections fail closed rather than place orders or pretend
to be paper. See [execution modes and the live-adapter roadmap](EXECUTION_MODES.md).

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.runtime --mode paper --check
```

## Research principles

- Use time-based train, validation, and test splits.
- Prevent future information from leaking into model inputs.
- Include fees, spread, slippage, and latency.
- Compare advanced models with simple baselines.
- Evaluate expected value and drawdown, not prediction accuracy alone.
- Require sustained paper-trading evidence before considering small live tests.

## Planned architecture

```text
Binance market data
    -> validated event storage
    -> order-book reconstruction
    -> microstructure features
    -> baseline models
    -> specialized neural models
    -> decision model
    -> hard risk engine
    -> paper-trading execution
    -> evaluation and retraining
```

## Public historical Spot data

The historical downloader uses Binance's unauthenticated public-data archive. It verifies each
published SHA-256 checksum, retains the original ZIP and checksum, and writes a normalized CSV with
millisecond timestamps plus a request manifest. It never reads API credentials or submits orders.

Download completed daily BTCUSDT 5-minute candles:

```cmd
python -m ai_trader.ingestion.download_binance_history --data-type klines --interval 5m --start-date 2024-01-01 --end-date 2024-01-31
```

Download completed daily aggregate trades:

```cmd
python -m ai_trader.ingestion.download_binance_history --data-type aggTrades --start-date 2024-01-01 --end-date 2024-01-02
```

Outputs go under `data/raw/binance_spot_history` by default. A request cannot include the current
UTC day because Binance daily archives are only reproducible after a day has completed. Historical
archives do not contain order-book depth, so kline/aggregate-trade models must use a separate
feature schema from the live depth-capture pipeline.

Build causal 1-, 5-, and 15-minute Spot datasets from a verified 1-minute kline manifest:

```cmd
python -m ai_trader.features.kline_dataset data\raw\binance_spot_history\manifest_BTCUSDT_klines_1m_2024-01-01_2024-01-31.json --output-directory data\processed\btcusdt_kline_research
```

Every UTC day is a distinct `source_session`. Sixty-bar rolling features reset at each session
boundary, labels enter at the next bar's open, and future barrier windows never cross into another
day. Labels subtract configured entry and exit fees plus slippage. If profit and stop barriers are
both touched within one candle, the label records the stop first to avoid optimistic intrabar bias.
The defaults model market-order execution and are research assumptions, not guaranteed fills.

The linear trainer and session-aware walk-forward evaluator detect this historical kline feature
schema explicitly and preserve its ordered feature names in checkpoints and reports. They reject
mixed or mismatched schemas even when the numeric dimensions happen to agree.

For kline datasets, walk-forward reports also simulate one non-overlapping long position at a time.
Use `--starting-balance` and `--position-fraction` to set research capital assumptions. Reports
include cost-adjusted PnL, closed-trade drawdown, turnover, exposure, profit factor, and signals
skipped while a prior trade was open. This remains offline evaluation and cannot place an order.
Optional CLI controls include `--minimum-reentry-delay-minutes`,
`--maximum-trades-per-session`, `--session-profit-target`, and `--session-loss-limit`; reports count
signals rejected by each control.

## Research validity and next milestone

Read the [strategy research reset](STRATEGY_RESEARCH_PLAN.md) before interpreting backtests.
Walk-forward report schema 3 separates fitting, past-session checkpoint tuning, and next-session
evaluation. `--minimum-training-sessions` counts fitting sessions only;
`--tuning-session-count` (default 1) adds a disjoint tuning block. For a 20-session initial prefix,
use `--minimum-training-sessions 15 --tuning-session-count 5`. Legacy `validation` metric fields
now mean evaluation-only; tuning metrics and session names are recorded separately. Schema 1
reports reused the scored session for checkpoint selection and remain exploratory.

The loader first inventories source-session names and feature timestamps, then reserves the final
sessions before converting features, labels or economic outcomes. It rejects unordered/overlapping
sessions and any research outcome reaching the next session's first feature timestamp. Optional
`--embargo-ms` adds a required gap: `outcome_time + embargo_ms < next_session_start` must hold for
every research row. Crossing rows cause an error, not silent trimming. Nonmonotonic exit times are
allowed; the check does not assume the last row is the longest trade. Both feature and outcome
timestamp columns are now mandatory, including for legacy depth datasets.

Schema 3 records the source SHA-256, session inventory, embargo and boundary policy. Reserved CSV
rows are still tokenized as text, and their names/feature timestamps are inspected; their features,
targets and returns are not converted or summarized. This is not physical lockbox isolation.
Schema 2 separated checkpoint tuning but still converted all held-out rows.

Kline labeling version 2 processes opening barrier hits before intrabar high/low touches, using
the opening price and timestamp for idealized market-triggered exits. Stops can lose more than
their configured threshold. Unknown intrabar ordering remains stop-first; costs remain fixed bps.
The common CSV row schema stays at 1, with an explicit `labeling_version` column; the kline manifest
is schema 2 and records the fill policy. Older labels are unchanged: regenerate into a new directory
before relying on these rules, and do not mix labeling versions in an experiment.

The label-based simulator still has capital-accounting and execution-model limitations. Fully isolated
per-session storage and complete code/environment manifests remain future work. No new historical
profitability claim has been made. Execution remains paper-only; public data ingestion may be online.

## Offline research council

The [TradingAgents architecture review](TRADINGAGENTS_REVIEW.md) documents what we can reuse
locally without paid model keys. An opt-in research council now supports bounded analyst/critic
reviews, timestamped evidence, strict JSON citations, and deterministic risk vetoes. It cannot
place orders and is not connected to the paper champion. The supplied reviewer is deterministic;
a local LLM backend has not yet been installed or integrated.

Run a synthetic, entirely offline safety demonstration:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.council --demo
```

## Local development setup

Open Command Prompt in the project directory, then run:

```cmd
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
python -m pip install -r requirements\gpu-cu132.txt
```

Verify the installation:

```cmd
python -m ai_trader.diagnostics
python -m ruff check .
python -m ruff format --check .
python -m pytest -v
```
