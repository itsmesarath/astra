# Bybit BTCUSDT spot archive: first reconstruction gate

The 2026-09-24 Bybit spot trade and 200-level order-book archives are retained
separately in `data/raw/bybit_spot_btcusdt_2026-09-24/`. Their original URLs,
sizes, hashes, and boundary details are recorded in that directory's
`manifest.json`. No Binance capture, reserved holdout, model, or trading state
was changed to create this sample.

The offline audit replays the order-book ZIP in stored order. It pins the source
SHA256, bounds compressed/decoded bytes and message count, requires an initial
snapshot, validates message types, symbol, timestamps, prices and sizes, and
requires every delta update ID to advance by exactly one. It applies absolute
sizes and zero-size removals, checks that the book stays nonempty and uncrossed,
and compares the replayed 200-level book with the closing snapshot. It neither
sorts nor repairs the archive. The [Bybit order-book documentation](https://bybit-exchange.github.io/docs/v5/websocket/public/orderbook)
defines the snapshot/delta and zero-size rules used here.

Reproduce the audit from the project root:

```powershell
.\.venv\Scripts\python.exe -m ai_trader.research.bybit_orderbook_audit `
  --archive data/raw/bybit_spot_btcusdt_2026-09-24/2026-09-24_BTCUSDT_ob200.data.zip `
  --sha256 51bfd2e4ece90bc2b4d460a7ee857da1771257f4be89e28f5820db224958441c `
  --date 2026-09-24 `
  --output logs/bybit_spot_btcusdt_2026-09-24_ob200_audit.json
```

The output path must be new; the command refuses to overwrite an existing
report. The verified result is 810,884 messages: 2 snapshots and 810,882
deltas. Every delta advanced the update ID by one; the closing snapshot matched
the replayed bids and asks exactly. The reconstructed book never exceeded 200
levels per side. Two final records are timestamped 16 ms after midnight UTC on
2026-09-25. A separate source-time diagnostic found a maximum adjacent gap of
1,500 ms and 40 gaps above 1,000 ms; an idle interval alone does not prove lost
data. The compressed trade archive contains 1,060,210 rows, but trades were not
aligned to the order book in this gate.

This is a *research-only reconstruction result*, not a training or paper-trading
release. It cannot prove exchange-side completeness, causal receipt times,
cross-stream availability, or executable outcomes. The follow-on
[trade/book source-time audit](BYBIT_TRADE_BOOK_ALIGNMENT.md) handles the two
post-boundary records explicitly. Do not silently mix this archive with
Binance sessions.
