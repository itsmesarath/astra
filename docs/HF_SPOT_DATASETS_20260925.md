# Hugging Face spot microstructure intake (2026-09-25)

Research-only downloads. No training, strategy promotion, paper order, or live order
was started by this intake. The downloaded market data is ignored by Git.

## One-hour multi-venue tape

Source: [RabbitGo777 raw tapes](https://huggingface.co/datasets/RabbitGo777/btc_20260818T1100.v2.jsonl.zst),
revision `613c7b692c0de1fde2ca7e69934a9cc566bc2b8e`, plus its
[one-second aggregate](https://huggingface.co/datasets/RabbitGo777/btc_20260818T1100.v2.1s.parquet),
revision `4b2b4d65368e15c11900ab6b36ebca4379c8bab6`.
Local directory: `data/raw/hf_spot_microstructure_20260925_1`.
Coverage: 2026-08-18 11:00:00–11:59:59 UTC. License stated by the publisher:
CC BY 4.0, with source attribution required and venue terms still applicable.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `binance.btc_20260818T1100.v2.jsonl.zst` | 18,176,917 | `fe94b425ac8812b88ebbc7ca8c53a55fc41cee4d97301fe7491d5cdcd43dfeb0` |
| `bybit.btc_20260818T1100.v2.jsonl.zst` | 6,761,135 | `3b8e8e04503e2b5acacb51ffa1ed9c0f6be4e5ef7f44806c7a7d9b11e3e22a5a` |
| `okx.btc_20260818T1100.v2.jsonl.zst` | 8,148,277 | `6beb97be07b8afa1993bd435e4017dc208582e0de59b06c384922625aef22b0c` |
| `coinbase.btc_20260818T1100.v2.jsonl.zst` | 5,240,999 | `794eb803ffe8587dacb6a47627b1f2034a161a13d80f1e4139d31f876ad42ebb` |
| `binance.btc_20260818T1100.v2.1s.parquet` | 1,463,659 | `bec17747b029dc138e5bb3ed19bedcef8fb95c498da95c12dc42c927268da07e` |

The four raw files contain spot and perpetual messages; filter by venue and
instrument before any spot research. A raw line is `receive_us|channel|JSON`,
not a standalone JSON object. Binance's raw depth diffs lack a REST snapshot,
so they cannot independently anchor a complete Binance order book. The
publisher's one-second file has derived ten-level ladders but is lossy. Bybit,
OKX, and Coinbase carry self-contained snapshot/update book streams. This is a
parser and alignment test, not a training-sized study.

## Eight-hour Binance spot feed

Source: [lokima/polymarket-btc-eth-5m-updown-8h](https://huggingface.co/datasets/lokima/polymarket-btc-eth-5m-updown-8h),
revision `97d05eac7324a410db4dabb4f06b25cc21aae23f`.
Local directory: `data/raw/hf_binance_spot_8h_20260925_1`.
Coverage: 2026-07-29 20:40:00 to 2026-07-30 04:40:00 UTC.
License stated by the publisher: ODC-BY 1.0 for the compilation; venue terms
still apply to the underlying market data.

| File | Bytes | SHA-256 | Footer rows |
| --- | ---: | --- | ---: |
| `binance_spot.parquet` | 172,894,015 | `1fcdc822d4208ec2df63a8f17db58dd51858d34c2bba78c5c9583e229b4e62bb` | 7,524,661 |
| `binance_depth_snap.parquet` | 1,184,533 | `d8f7fd6a3a18bf3050d85b98598c609660f8c748ee2aab4b294a7516a5fdbfe3` | 100 |

The two Parquet hashes also match the publisher's downloaded
`checksums_parquet_sha256.txt`. The matching `PROVENANCE.md`, `SCHEMA.md`, and
`metadata_quality_report.json` were downloaded alongside them under filenames
with directory separators replaced by underscores. The spot feed contains BTC
and ETH; filter `sym` and channel before using it. It includes trades and best
quotes with local arrival timestamps, but the 100 REST depth snapshots are not
a continuous depth-diff feed. Do not infer iceberg, absorption, or a fully
reconstructed Binance L2 book from these snapshots alone.

## Acceptance boundary

The five one-hour files and two eight-hour Parquet files matched publisher
revision-specific size and SHA-256 metadata after download. This verifies exact
bytes, not market completeness, clock accuracy, sequence continuity, license
compliance, or fitness for trading. No rows were labelled or added to a model.
Keep all venues and spot/perpetual instruments separate. Before training, run
source-qualified stream/sequence audits, establish receipt-versus-exchange-time
semantics, preregister whole-session train/validation/reserved splits, and test
costed paper outcomes without using a reserved set for model selection.

The previously downloaded Goooddy June 2026 Binance BTCUSDT L2 archive remains
separate. Its documented sequence faults and source-time ambiguity still block
automatic training; see `docs/HF_LOB_INTAKE.md`.

## Local row-level quality audit

`ai_trader.research.hf_spot_quality` scanned the pinned files on 2026-09-25.
The final report is `data/processed/hf_spot_quality_20260925_4.json`, raw SHA-256
`477ac096bfb99d06cb6848d76dcb5117a1b9feca6b00c8496c11cf89b896e0ae`.
Earlier reports with suffixes `_1` through `_3` were diagnostic iterations of
the checker; `_4` correctly recognizes OKX plain `ping`/`pong` and non-market
control rows.

- All seven market files still match their pinned sizes and SHA-256 values.
- Four one-hour tapes: Binance 944,499 lines, Bybit 250,013, OKX 164,180,
  Coinbase 92,562. No malformed payloads after classifying 356 OKX protocol
  heartbeats. Explicit spot snapshot messages were observed in Bybit, OKX and
  Coinbase, but full venue-specific L2 replay/sequence validation was not run.
- Receive timestamps reverse locally 424 times in Binance, 15 in Bybit and 7
  in OKX; largest reversal 5,933 microseconds. Coinbase has none. Arrival-time
  sorting and exact cross-venue causality must not be assumed for this tape.
- The eight-hour Binance spot file decoded all 7,524,661 rows. Its BTCUSDT
  channel includes 951,713 individual trades, 296,939 aggregate-trade messages
  and 2,993,437 best-quote messages. The local scan found no individual-trade
  ID forward gaps or regressions, no invalid best quotes, and no stream-sequence
  or arrival-clock reversals. Those are scoped checks, not a full venue audit.
- All 100 REST depth snapshots decoded with valid top-of-book prices, but all
  100 lack explicit symbol metadata in their rows. The file mixes BTC and ETH;
  this prevents source-qualified book reconstruction without a separately
  justified symbol-identification method. It also contains no depth-diff feed.

**Training decision: blocked.** The two captures are only one hour and eight
hours, with no preregistered whole-source train/validation/reserved assignment
for these formats, no validated source-qualified L2 feature/label adapter, and
no costed independent evaluation. Raw tapes are not Qwen instruction targets.
No model weights were changed, and no paper/live policy was promoted.

The new quality checker has six focused tests. The full Python suite finished
with 2,928 passes and one optional Nautilus skip. Ruff lint passed. Ruff format
passed for the two new Python files; the repository-wide format check flagged
only the already-present, unrelated `bybit_trade_book_alignment.py`, which was
left unchanged.
