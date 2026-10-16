# Bybit BTCUSDT spot trade/book source-time audit

This is the second research gate for the raw 2026-09-24 Bybit spot sample. It
revalidates the pinned order-book ZIP with the separate OB200 reconstruction
audit, verifies the compressed trade CSV against its SHA256, and scans both
streams in their stored order. It emits summary metadata only; no joined rows,
features, labels, CVD, backtest, model call, or trade are produced.

The join rule is deliberately strict: a trade at archive timestamp `T` may
refer only to the latest book message with Bybit system timestamp `ts < T`.
A book update at exactly `T` is withheld because its cross-stream order is
unknown. The two post-midnight book messages remain in the source and are
counted, but cannot match an in-day trade. Bybit documents order-book `ts` as
system generation time and `cts` as matching-engine time; `cts` can be
correlated with the public-trade channel's `T`. Its public-trade API documents
`T` as fill time and `S` as taker side. The archive CSV does not independently
document how its `timestamp` and `side` columns map to those API fields, so
this audit treats them as source columns rather than certified execution-time
or aggressor-side labels.

Sources: [Bybit order-book protocol](https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook),
[Bybit public-trade protocol](https://bybit-exchange.github.io/docs/v5/websocket/public/trade).

Reproduce from the project root with a new output path:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.bybit_trade_book_alignment `
  --trades data/raw/bybit_spot_btcusdt_2026-09-24/BTCUSDT_2026-09-24.csv.gz `
  --trade-sha256 0c662a21adae9d2ef08339f73177ac414150946fa1ceb8e454b68e2cae78ae24 `
  --orderbook data/raw/bybit_spot_btcusdt_2026-09-24/2026-09-24_BTCUSDT_ob200.data.zip `
  --orderbook-sha256 51bfd2e4ece90bc2b4d460a7ee857da1771257f4be89e28f5820db224958441c `
  --date 2026-09-24 `
  --output logs/bybit_spot_btcusdt_2026-09-24_trade_book_alignment.json
```

Observed result: 1,060,210 trades and 810,884 book messages. Every trade had
some strictly earlier book message. For 10,585 trades, a book message had the
same millisecond timestamp and was withheld. The source-time age of the
selected earlier book was 1–100 ms for 1,035,297 trades, 101–500 ms for
24,440, 501–1,000 ms for 472, and above 1,000 ms for one trade (maximum
1,091 ms). Ten book messages came after the final trade and could not be
selected; two of those were the documented post-midnight records. The CSV
contained 924 rows flagged `rpi=1`. These age figures are source-time
differences, **not** network latency or fill-quality measurements.

This pass does not certify causal availability, cross-stream ordering within
one millisecond, archive trade-side semantics, exchange completeness, or
profitable execution. Keep it research-only. Before using Bybit history for
model training or paper policy evaluation, the project still needs a
venue-specific feature contract, session boundaries, fee/slippage assumptions,
and out-of-sample evaluation that does not reuse the audit day as holdout.
