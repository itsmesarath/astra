# Hugging Face BTCUSDT spot pilot

The user authorized downloading public datasets and training on suitable data on
2026-09-25. The first step is an explicit data intake, **not automatic training**.
The existing receipt-causal trainer and Qwen model remain unchanged.

## Frozen selection

`configs/hf_btcusdt_lob_pilot_v1.json` pins Goooddy/crypto-lob-stream revision
`2b8c544ae5b46dd57c6f8807a51965d61ea4b20c`, Binance **spot**, BTCUSDT,
June 2026. It requests precisely three files, totaling 446,107,380 bytes:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| snapshots | 299,002 | `6b4579b4fb8a06fe46c6f11a824c42490fb4b7833ecb8e1beb53b014969e6cdb` |
| trades | 59,876,309 | `b7a6cff63c4ae242a792fa42ae4dd32bbf5026de59a33a9bbb9b2f1e95af9339` |
| depth | 385,932,069 | `e6339adc0edfae9b62bc49f2056c8596bb431f58e99c516cba9916063a15470d` |

The pins and lengths came from the repository's revision-specific public metadata.
They identify the publisher's exact bytes; they are not an independent endorsement
of the data's truth, completeness or suitability. The publisher discloses lost
June-August depth/trade data caused by overwritten flushes. Its roughly 93% June
retention estimate is not a guarantee for any individual BTCUSDT session.

Source: [pinned dataset card](https://huggingface.co/datasets/Goooddy/crypto-lob-stream/blob/2b8c544ae5b46dd57c6f8807a51965d61ea4b20c/README.md).

## Intake controls

- Opt-in download, fresh exclusive destination, no overwrites or automatic retries.
- Exactly one pinned snapshot/trade/depth file; aggregate cap 512 MiB.
- Public HTTPS only, verified TLS, allowlisted publisher/CDN redirect hosts; no token,
  account login, remote dataset Python, pickle, capture process or trading connection.
- Optional `--ipv4` chooses IPv4 for this downloader only, preserving original TLS
  hostname/certificate verification. It does not change Windows settings or other
  processes, and does not fall back between addresses or address families.
- HEAD resolves the publisher's public CDN URL, then a single GET streams the file.
  Socket timeout is 30 seconds, with an additional checked 300-second elapsed budget
  per file. A blocked individual socket operation can extend the outer deadline by
  its remaining socket timeout; late success is never published.
- Pinned length and SHA256 must match before atomic no-replacement publication.
  Failures retain their evidence and any partial bytes; a failure is not a complete
  download receipt. Signed CDN URLs are not written into the receipt.
- Parquet support is the optional `historical` dependency, pinned to PyArrow 25.0.1.
  No publisher-supplied collector or reconstruction package is installed.

The `audit` command hashes each local file and inspects schema/footer metadata only,
with metadata limits. It does **not** decode market price/volume rows, reconstruct
a book, prove sequence continuity, derive CVD, label outcomes or fit a model.
Timestamp statistics from footers remain explicitly unverified hints. The audit
always reports training blocked: even a plausible schema does not satisfy all
training prerequisites. Its exit code 2 is a blocked diagnostic, not corruption.

## Commands

From the repository root, after installing the optional dependency:

```powershell
.venv\Scripts\python.exe -m pip install --only-binary=:all: --no-deps pyarrow==25.0.1
.venv\Scripts\python.exe -m ai_trader.ingestion.hf_lob_intake download --plan configs/hf_btcusdt_lob_pilot_v1.json --directory data/raw/NEW_HF_PILOT --enable-download
.venv\Scripts\python.exe -m ai_trader.ingestion.hf_lob_intake audit --plan configs/hf_btcusdt_lob_pilot_v1.json --directory data/raw/NEW_HF_PILOT --report data/processed/NEW_HF_AUDIT.json
```

The destination/report placeholders must be new paths. Existing attempts are never
silently resumed, repaired or overwritten.

## Training prerequisites

Before a numerical model can use this source, implement and test a source-qualified
adapter, audit actual sequence continuity and snapshot alignment, and establish the
meaning of event/receipt timestamps. Never invent received/requested timestamps or
trade aggregation IDs to make these files pass the native capture loader. A model
trained under an exchange-time-only protocol would require a distinct, explicitly
documented research contract and would not validate receipt-causal deployment.

Freeze chronological whole-session train/validation/reserved roles, costed outcome
definitions and a bounded fixed training recipe before inspecting outcomes. Keep
losses and unknown/censored intervals visible. Downloading a file does not make any
part of it a pristine holdout. No existing reserved campaign or Qwen holdout is read.

Qwen fine-tuning additionally needs grounded structured examples and its separate
evaluation safeguards. It does not learn trading decisions merely by receiving raw
Parquet data. No automatic paper promotion, live order, or active-model replacement
is part of this intake.

## Actual pilot result (2026-09-25)

**Download completed; training not started.** The completed directory is
`data/raw/hf_btcusdt_lob_june_20260925_5`. All three complete files match both pinned
sizes and SHA256 values. The final receipt is `download_receipt.json` inside that
directory. Total verified bytes: **446,107,380**, about 425.44 MiB.

Metadata raw-file SHA256 pins:

- Config: `9c9ee1ed96a831f0564e8c23ec16cb7cd0e572fd54f480cd869c9666f9af63c3`.
- Download receipt: `3cdc470c00a22acd094d9286a06230948ad1a4084e81632015f69dfae4c367f9`.
- Schema audit: `ca60f8f10e26d406bdd028de2e3432d9180ad853885e8044b0102eede2204f30`.

The receipt's `plan_sha256` hashes the normalized, sorted plan representation;
it intentionally differs from the configuration file's raw-byte hash above.

Four earlier explicit attempts (`..._1` through `..._4`) failed with connection
resets before completing any source file. Their plans, failure metadata and any
zero-byte partials remain unchanged. Each invocation made no automatic retries.
A bounded HEAD/CDN probe succeeded intermittently, including a 16-byte Parquet
header read. Windows curl reproduced a connection reset on the normal route.
DNS returned IPv6 addresses first for huggingface.co; curl restricted to IPv4
succeeded on HEAD and a 16-byte range request. The subsequent downloader invocation
with `--ipv4` completed all three archives. This supports a client-route workaround,
not a proven diagnosis of an ISP/router/firewall or a repair to Binance ingestion.
No Windows network, time-server, security or certificate settings changed.

The schema/footer audit is
`data/processed/hf_btcusdt_lob_june_20260925_1_audit.json`:

| Kind | Footer row count | Row groups | Relevant observation |
| --- | ---: | ---: | --- |
| snapshots | 34,000 | 1 | Contains last_update_id and one timestamp_ms column. |
| trades | 8,118,466 | 8 | Contains trade_id and buyer_maker; no exchange_ts column. |
| depth | 68,905,191 | 66 | Contains first_update_id/last_update_id; no exchange_ts column. |

These are **stored rows**, not independent samples, reconstructed books, complete
sessions or validated training examples. The current card describes newer schemas
with separate exchange timestamps, but this pinned June archive does not have them.
No actual price/volume rows or outcome labels were decoded by this audit. Snapshot
request/receipt availability, cross-stream arrival order and full sequence/gap
quality remain unverified. The audit returns `blocked_training_intake`, with zero
labels, zero epochs and no promotion or live authority.

Do not feed the files into the existing receipt-causal trainer by fabricating
timestamps or aggregation IDs. Further historical research needs a distinct,
source-qualified time/sequence contract, a bounded continuity/reconstruction audit,
and preregistered session splits/costs/targets before fitting. This is an ingestion
limitation, not a claim that the archive is unusable for every kind of research.

Verification: 51 focused intake/sequence tests; final full suite **2,831 Python passes,
one optional Nautilus skip**, **38 JavaScript passes**, Ruff lint/format clean,
dependency check clean. Work remains local and uncommitted.

## Sequence-audit result (2026-09-25)

The latest registered diagnostic is frozen in
`data/processed/hf_btcusdt_lob_june_20260925_2_sequence_protocol.json` with raw
registration SHA256
`fe16a550da69727c01196df4731b88feb31e4bccb747535ff745871a927b54ad`.
The completed report is
`data/processed/hf_btcusdt_lob_june_20260925_2_sequence_audit.json` with raw
SHA256
`b319308ae749655a1eae5e43b9bb2766899433f8399f473b98a67e50883764d4`.

It scanned every stored row in source order:

| Stream | Rows | Diagnostic units | Forward-ID gaps | Source-time idle gaps | Regressions |
| --- | ---: | ---: | ---: | ---: | ---: |
| snapshots | 34,000 | 17 | 0 | 16 | 0 |
| trades | 8,118,466 | 8,118,466 | 647 | 47,993 | 0 |
| depth | 68,905,191 | 1,966,112 | 647 | 649 | 0 |

The gap counts are sequence diagnostics, not estimates of missing executions or
messages. Idle gaps are source-clock differences, not proof of data loss. The audit
did not sort, deduplicate, fill, reconstruct a book, read price/quantity columns,
derive CVD, create labels or infer receipt times. It retained 17 snapshot bridge
candidates and reported no snapshot timestamp regressions. Training remains blocked
because the source-time meaning and cross-stream availability are unresolved, and
the measured sequence faults need an explicit segmentation policy.

The audit retained 17 snapshot segments, and detected 47,994 trade segments and
650 depth segments. The report stores the first 256 trade/depth segments under a
bounded metadata budget and marks both lists truncated; it does not claim that the
unlisted segments are clean or interchangeable. A segment is a diagnostic run
between an observed sequence/time fault, not a validated session.

The next implementation step is a separate source-time historical replay contract:
it must segment around the 647 sequence faults, bind every feature to a declared
source-time cutoff, exclude fault-spanning outcomes, and register whole-session
train/validation/reserved assignments before reading labels. It must never route
these rows through the live receipt-causal adapter or silently convert source time
into receipt time.
