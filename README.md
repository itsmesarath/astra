# AI Trader

An experimental cryptocurrency market-microstructure research system.

## Initial scope

- Market: BTCUSDT on Binance
- Mode: research, backtesting, and paper trading only
- Language: Python
- Hardware: NVIDIA RTX 5080 Laptop GPU with 16 GB VRAM

## Safety boundary

Live trading is disabled during development. Model decisions will never directly control an exchange account. A separate deterministic risk and execution layer must validate every proposed action.

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
