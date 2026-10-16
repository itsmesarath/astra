# Kaggle BTC microstructure pilot intake (2026-09-25)

The user requested suitable Kaggle datasets for the BTCUSDT spot research bot and
training. Two public, file-specific downloads were completed without account
credentials. They are local research inputs only; **no model was fitted or
promoted, and no paper or live order was placed**. Existing captures, reserved
sources, journals, Qwen weights and training artifacts were not changed.

## Selected sources and immutable local bytes

| Source | Local file | Bytes | Local SHA256 |
| --- | --- | ---: | --- |
| [Binance BTCUSDT trades and book, Kaggle version 1](https://www.kaggle.com/datasets/krrdev1/binance-btcusdt-l3-market-microstructure-data) | `data/raw/kaggle_binance_btcusdt_l2_20260418/trades_20260418.parquet` | 18,747,799 | `9a46ca05a87651cd8a6718232cc02b1d6be6a115bac03709f53dce6c03bcd049` |
| Same | `data/raw/kaggle_binance_btcusdt_l2_20260418/orderbook_snapshots_20260418.parquet` | 24,077,717 | `3ab6e0686b66bb3f166064d461132250f99c66fe2f04d2ed5228981b283bab9f` |
| Same | `data/raw/kaggle_binance_btcusdt_l2_20260418/orderbook_diffs_20260418.parquet` | 201,282,982 | `7536e1279ce024ac7adbe98900d5dd3b131034c342b12c3fcdfbac64fe956792` |
| [Coinbase LOB benchmark, Kaggle version 1](https://www.kaggle.com/datasets/martinsn/high-frequency-crypto-limit-order-book-data) | `data/raw/kaggle_coinbase_btc_lob_2021/BTC_1sec.csv.zip` | 332,328,327 | `b2338f3521335a891097d9a9e3611aa85e0f355afa12548a6ebbf8a138a75a61` |

Kaggle's public file-list API reported the three Binance Parquet byte lengths
above. Its single-file route supplied the Coinbase ZIP, which contains only
`BTC_1sec.csv` (1,755,134,589 uncompressed bytes). The ZIP CRC check passed.
These are **locally calculated** hashes, not publisher-signed checksums.
The Binance card lists CC BY-NC 4.0; the Coinbase card lists CC0. The Binance
sample must not be treated as cleared for a future commercial/live system.

## Initial read-only audits

The Binance files have 1,941,077 trades, 863,904 depth-diff rows and 1,434
snapshots. The snapshots contain 1,000 prices per side in the first inspected
row. The publisher calls this L3 in the slug, but the available changes are
aggregated **price-level L2** quantities, with null buyer/seller order IDs.
It cannot establish individual hidden orders.

The stored depth update ranges have one forward gap of 6,503 update IDs near
2026-04-18 08:02:07.914 UTC. Trade IDs are unique but, after sorting by ID,
have one gap of 35 IDs near 09:20:08.011 UTC. Trade rows sorted by their
`time` field are not monotonic by trade ID within identical timestamps, so
using stored row order as exact exchange matching order is unsafe. These are
observed identifier gaps, not a verified count of missed executions. There
were no source-time regressions in the projected columns inspected.

All three Binance files include a `received_at` column not explained in the
card's schema. Median `received_at - time` was 2,654 ms for trades, 2,646 ms
for depth diffs and about 2,642 ms for snapshots. These are differences
between stored fields, **not** measured network latency. The timestamp
semantics and collector clock require independent validation before any
receipt-causal feature or paper simulation uses them.

The Coinbase archive runs from 2021-04-07 11:32:42 to 2021-04-19 09:54:22 UTC
and contains 1,030,728 rows. Timestamps were strictly increasing in the
stream scan, with no identical adjacent timestamps. It has 156 columns with
1-second snapshots and derived market/limit/cancel notional fields, but no
native Binance spot receipt or trade-ID protocol. It is suitable for a
separately labeled **research benchmark**, not direct deployment on BTCUSDT.

## Training gate

Neither download is automatically eligible for the existing bot trainer.
The Binance sample is only one day, has explicit sequence faults, unclear
`received_at` semantics, and a non-commercial license. The Coinbase source
is an older different-venue BTC/USD benchmark. The previously downloaded
Hugging Face June spot archive also has recorded sequence faults (see
`HF_LOB_INTAKE.md`). Combining these sources as though they were one venue
or inventing native capture fields would create a misleading model.

The next engineering step is a source-qualified historical L2 replay contract:
validate file contents and snapshot bridges; segment at all observed faults;
define feature availability and a costed target before opening outcomes;
assign whole, chronologically separated sessions to train, validation and
reserved roles; and fit an offline numerical baseline only if those gates
pass. Qwen fine-tuning needs separately grounded examples and evaluation.
No downloaded dataset alone establishes a profitable trading policy.

## Source-qualified reconstruction audit

`ai_trader.research.kaggle_binance_l2_audit` now performs a read-only,
SHA256-pinned reconstruction audit of the Binance Parquet trio. It applies
absolute price-level quantities and zero removals, requires advancing depth
update ranges, and compares the reconstructed top 20 levels on both sides to
periodic snapshots at matching update IDs. A sequence gap invalidates the
current book until a later snapshot anchors a new diagnostic interval; the
audit does not fill missing messages. It also checks unique trade IDs without
mistaking same-timestamp stored-row order for exchange matching order.

The accepted report is
`data/processed/kaggle_binance_btcusdt_20260418_l2_audit_v4.json` with raw
SHA256 `8b5050b3c30017ae35e26f419fd92eecb96a537eba97e203cdbb6352bfdd5c76`.
The source module SHA256 at this run was
`e22b319816e36b845084b335d95ef6915173a94a6d2e6bd366ec0ea3a6044863`.
Earlier v1-v3 audit reports are retained as development diagnostics, not the
accepted result.

Of 1,434 snapshots, the first was the initial anchor. The audit matched the
reconstructed top 20 bid/ask levels against **1,431** subsequent snapshots.
One snapshot immediately after the 6,503-ID depth gap was unverified, and
one comparison at 2026-04-18 11:40:06.978 UTC differed. The latter is
**consistent with**, but not proved to be caused by, the 1,000-level REST
snapshot limit: three later top-20 bid levels were absent from the prior
snapshot and below its lowest stored bid. Binance explicitly warns that
levels outside a limited starting snapshot are unknown until they change
([local-book procedure](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md#how-to-manage-a-local-order-book-correctly)).
An immutable-anchor regression test guards this diagnosis; replay state must
never mutate the saved snapshot against which it is compared.

This result validates many one-minute reconstruction intervals, **not**
receipt-causal availability, complete source coverage, training examples, or
a one-day generalizable strategy. The report explicitly sets training, paper
trading and promotion permission to false. A later trainer must use a separate
historical source-time contract, exclude the gap and uncertain coverage
intervals, and retain the source's non-commercial restriction.

Verification after the audit: **2,922 Python tests passed**, one optional
Nautilus test skipped, and **38 JavaScript tests passed**; repository-wide
Ruff lint passed. The new module and tests pass Ruff formatting. The
repository-wide format check still flags the
pre-existing, unrelated `bybit_trade_book_alignment.py` formatting difference;
it was not edited during this intake.
