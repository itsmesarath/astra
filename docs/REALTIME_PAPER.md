# Bounded real-time paper session

`ai_trader.trading.realtime_paper` is an opt-in, **paper-only** BTCUSDT Spot
session. It consumes the public Binance aggregate-trade and depth streams,
reconstructs the local book, evaluates the predeclared microstructure policy,
and writes simulated decisions, risk checkpoints, fills, and provenance to a
durable SQLite journal. It has no credentials, account API, live-order route,
model call, or automatic training.

The example policy deliberately abstains. Copy
`configs/realtime_paper_abstain_example.json` to a new settings file and give
each run a new `plan_id`, `source_session`, plan path, capture path, and journal
path. Register **after** the code and environment are fixed, immediately
before the capture; source/environment changes invalidate the plan.

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.realtime_paper register `
  --settings configs/realtime_paper_abstain_example.json `
  --output logs/realtime_paper_abstain_plan.json

.venv\Scripts\python.exe -m ai_trader.trading.realtime_paper run `
  --plan logs/realtime_paper_abstain_plan.json `
  --capture data/raw/realtime_paper_abstain_example.jsonl `
  --journal data/processed/realtime_paper_abstain_example.sqlite `
  --seconds 120 --enable-public-data --enable-paper-simulation
```

The capture and journal parent directories must exist. The run is finite
(1–3,600 seconds) and refuses existing plan/capture/journal paths. The paper
policy is bound before the first market receipt. Each source line is flushed
and `fsync`ed before its callback can commit a paper decision. The journal
records the durable file offset and line hash, and final success requires an
exact tick-by-tick match against the published capture plus a completion row.
Events received before snapshot availability can bridge the book but cannot
warm CVD or produce an entry decision. A gap, stale decision, queue overflow,
callback/disk failure, code change, or incomplete capture stops the run. It
does not restart an uncertain partial session or silently continue from it.
The example allows up to five seconds of exchange-event lag for recording,
but a lag over two seconds permanently freezes simulated fills for that
session. Its report says `paper_frozen: true` when that happens. This avoids
discarding the evidence while treating a delayed quote as non-executable;
the next session needs a fresh snapshot.
Retain `.partial`, `.stream.partial`, and SQLite files for investigation; start
a *new* predeclared session only after reviewing the failure. A completed
session's final report includes the capture and plan SHA-256 hashes.

For unattended, finite paper operation, the same registered plan can run up to
32 back-to-back sessions in **one journal**. Its `source_session` must end in
`-s0001`; subsequent names are `-s0002`, and so on. The paper account, open
inventory, risk checkpoint, and kill switch carry forward. Use fresh output
paths; do not run the single-session command and service against the same
journal.

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.realtime_paper service `
  --plan logs/realtime_paper_abstain_plan.json `
  --output-directory data/raw/realtime_paper_service `
  --journal data/processed/realtime_paper_service.sqlite `
  --manifest logs/realtime_paper_service.jsonl `
  --sessions 32 --seconds-per-session 120 `
  --enable-public-data --enable-paper-simulation
```

The service predeclares session count and duration in a durable manifest,
holds an exclusive lock, stops on the first uncertain session, and will not
reuse a partial capture or silently restart. After a successful session, it
verifies previous capture hashes before opening the next. A planned session
boundary still creates a short connection/snapshot gap, during which paper
inventory cannot be protected. The final report explicitly includes
`open_paper_inventory_btc`; an open position is **not** liquidated at a
fabricated footer price. Inspect it before evaluating returns or planning the
next run.

Inspect a service without changing any process or file:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.realtime_paper inspect `
  --journal data/processed/realtime_paper_service.sqlite `
  --output-directory data/raw/realtime_paper_service `
  --manifest logs/realtime_paper_service.jsonl
```

`recorded_complete` means the journal has completion rows, the manifest has
its terminal footer, and the published capture hashes match. A failure or
missing capture is reported separately; inspection does **not** restart it.

On 2026-09-25, a bounded two-session 15-second public-data smoke completed
with 338 and 311 capture records, 326 and 292 paper frames, no frozen frames,
zero orders, no open inventory, and a released lock. Independent inspection
reported `recorded_complete`, 618 ticks/cases, and matching capture hashes
`3c24c756d8c64b23931028482be6880663e94a85c619c204ee8fe737122bdab4`
and `a5f96ad77a24607b3dcc5bbe979132f176bc390b9894b33975494b6f14153c21`.
This is an operational handoff check, not strategy performance evidence.

This is a bounded service, not an infinite self-healing daemon. Simulated
fills use the existing quote/fee/slippage model; they do not
prove queue priority, actual fillability, or profitability. A non-abstaining
policy should be used only after out-of-sample evaluation and a separate
paper-risk review. Qwen training and candidate promotion remain separate from
this live data path.
