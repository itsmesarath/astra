# Independent public-data and paper workflow

The project can now be left running after the Codex session ends. The supported
worker is deliberately finite and public-data only:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.paper_data_service `
  --enable-public-data `
  --sessions 4 `
  --seconds-per-session 120 `
  --pause-seconds 3600 `
  --output-directory data/raw/paper_service
```

Each session gets a unique source ID, an immutable `.jsonl` capture, and (unless
`--skip-features` is supplied) a causal microstructure JSONL artifact containing
order-book features, CVD and the existing replenishment/absorption proxies. A
durable JSONL manifest records starts, successful hashes, counts, and failures.
The lock prevents two workers from writing the same directory. A failed session
stops the run and leaves its `.partial` files for inspection; there is no hidden
retry loop or unbounded `--forever` mode.

This worker does not train a model or submit orders. The current paper engine is
an explicit offline replay of a pre-registered capture, so it cannot safely be
silently attached to a future live WebSocket file. The next paper milestone is a
separate session-registration/forward-paper adapter that preserves the same
account and risk journal while consuming a validated session. Until that gate is
implemented, the service is the recorder and feature-preparation side of the
paper workflow, not a claim of profitability.

## Historical public data

The existing checksum-verified Binance archive downloader remains the preferred
long-range source:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.download_binance_history `
  --symbol BTCUSDT --data-type klines --interval 1m `
  --start-date 2025-01-01 --end-date 2025-01-07 `
  --output-directory data/raw/binance_spot_history
```

For bounded recent public REST ranges, the provider-separated adapter supports
Binance, OKX, and Coinbase candles, plus Binance aggregate trades:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.download_public_history `
  --provider okx --product BTC-USDT --data-type candles `
  --start-ms 1735689600000 --end-ms 1735776000000 `
  --interval-seconds 60 --output data/raw/okx_btcusdt_1m.jsonl
```

Every output has a companion manifest with the request, venue, row/page counts,
SHA-256, and `credentials_used: false`. Files are never merged across venues;
normalization and clock/market semantics must be reviewed before a cross-venue
training dataset is created. OKX and Coinbase trade-history adapters are
intentionally not guessed into the Binance schema yet.

The public endpoints are read-only market-data paths. No API key, account
endpoint, live-order client, or live/paper mode switch is introduced by these
commands.
