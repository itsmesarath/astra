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

This basic command records and prepares features. It does not train a model or
submit orders.

## Predeclared delayed paper run

The optional paper bridge now fixes a policy, feature/replay settings, paper
costs, risk limits and starting cash **before** the first capture. After each
completed capture it replays the receipt-ordered frames into one durable paper
journal. The same cash, inventory, loss limits and kill switch carry into the
next session. A market gap, incomplete capture, changed plan/code, out-of-order
session, or exhausted frame/byte budget stops the run. It never reads credentials
or reaches an exchange order endpoint.

The shipped example is an abstain policy for a zero-order operational check:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.prospective_paper `
  --settings configs/paper_service_abstain_example.json `
  --output logs/paper_service_abstain_plan.json

.venv\Scripts\python.exe -m ai_trader.ingestion.paper_data_service `
  --enable-public-data --enable-paper-simulation `
  --service-id paper-service-abstain-example-v1 `
  --sessions 2 --seconds-per-session 120 --pause-seconds 3600 `
  --output-directory data/raw/paper_service_abstain `
  --paper-plan logs/paper_service_abstain_plan.json `
  --paper-journal data/processed/paper_service_abstain.sqlite `
  --max-paper-frames 10000
```

Each invocation must use a fresh plan path, service ID, output directory and
journal. The plan is tied to the current Python source and environment; changing
the code after registering it invalidates the plan. Paper work is bounded to 32
sessions, 64 MiB of aggregate captures and 10,000 frames. A run cannot be
silently resumed after a failed session; inspect the manifest, partial capture
and journal before starting a separately declared run.

This is a **delayed** paper simulation: orders are generated only after a
two-minute capture closes, using prices recorded during that capture. It is
appropriate for prospective research with a policy frozen first. It is not a
real-time paper execution service or a profitability claim. A real-time feed
handoff with restart, lag and fault tests remains a separate milestone. The
example's `abstain` rule intentionally records no entry orders; any candidate
entry policy needs its own versioned settings and paper evidence.

An operational one-session check on 2026-09-25 ran the 30-second service with
this abstain plan. It completed with 211 aggregate trades, 299 depth events,
290 causal feature observations and 491 durable paper ticks/cases. The journal
contained zero orders, the service manifest had a complete footer, the lock was
released, and the capture SHA-256 matched its manifest:
`00f4e7dbd5f2077bce3d0f3ccfac058b7d0afc6ddfe0a6bfb038acdcc8b6dab7`.
This verifies one short public-data handoff, not unattended recovery or strategy
performance.

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

The REST adapter uses Binance's public market-data host, OKX UTC candle bars,
and Coinbase Exchange windows below its 300-candle request limit. Binance
aggregate trades page by aggregate ID so multiple trades in one millisecond are
retained. Exhausting `--max-pages` fails before publishing output. Coinbase
may omit intervals without ticks, and these candle endpoints do not provide
historical L2 books. See the [Binance Spot API](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md),
[OKX market API](https://www.okx.com/docs-v5/en/) and
[Coinbase Exchange candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles).

On 2026-09-25, a bounded public request for the complete UTC day 2025-01-01
returned 1,440 one-minute BTC candles from each venue: Binance 2 pages, OKX 5,
Coinbase 5. The normalized SHA-256 values were, respectively,
`4deea23ab8f7ce9bcaaa2f278b48b5ac5f44c9040b9c66e01545e40659776d21`,
`7454350c53da18dda841cca5d19d28635503bdcef0686cc12b273fad26ef5b0f`,
and `27916946cb697c6fd431be2af5e9613705cc64df1925952c1d7cee97537875f1`.
This checks endpoint and pagination behavior, not cross-venue equivalence or L2
availability.

The public endpoints are read-only market-data paths. No API key, account
endpoint, live-order client, or live/paper mode switch is introduced by these
commands.
