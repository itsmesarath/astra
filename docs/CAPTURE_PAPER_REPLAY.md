# Receipt-causal capture-to-paper replay

Implemented 2026-09-24 in `src/ai_trader/trading/capture_replay.py`. This connects an explicitly
selected Binance combined capture to the microstructure engine and bounded paper controller.
It is an offline library API, not a WebSocket client, background collector, trading CLI or model.

## Explicit input and limits

`CaptureReplay.from_path` requires the selected path, expected SHA256, source-session ID and a
typed `CaptureReplayConfig`. No globbing, "latest file" discovery, downloads or reserved-dataset
selection occurs. The file is read once into bounded immutable bytes and verified against the
expected hash. Later changes to the file cannot change an already constructed replay.

Limits are 32 MiB per capture, 100,000 records and 2,000,000 bytes per JSON record. Only complete
schema-1 combined captures are accepted. Framing checks enforce real integer timestamps/counts,
BTCUSDT stream identity, snapshot timing, monotonic receipts, footer counts, nonempty valid snapshot
levels, unique JSON keys and finite numbers. Required start/request/snapshot-receipt/end timestamps
cannot be guessed for legacy captures that omitted them. Framing failure occurs before journal
writes. This parser is separate from retrospective dataset QA and does not claim a malformed or
gapped market session is suitable training data just because its framing is valid.

## Snapshot availability and market health

The recorder writes the snapshot before buffered WebSocket messages, even when those messages
arrived while REST was in flight. Replay therefore follows these rules:

- A snapshot-only tick is explicitly unsynchronized and cannot execute anything.
- Records received at or before snapshot availability may stitch depth IDs into the book but
  emit no observation, CVD or warmup. Buffered aggregate IDs are checked for continuity but their
  volumes do not enter post-availability CVD.
- A fresh microstructure engine starts only after snapshot availability. An advancing depth update
  must bridge the reconstructed book before a synchronized quote is exposed. Warmup and evidence
  interval readiness restart normally; the first depth observation cannot authorize an entry.
- Every stream record checks local receipt minus exchange event time against configured maximum
  delay/future-skew bounds. Aggregate trades also check trade execution time, contiguous aggregate
  IDs and monotonic trade time. Depth IDs, payloads and bounded book coverage use the existing engine.
- A sequence gap, duplicate aggregate trade, malformed market payload, crossed book, coverage
  escape or excessive delay invalidates the rest of that source session. Later packets cannot
  silently recover it. Frames retain an explicit `resync_required:...` status and unsynchronized
  quote health, so the paper runner blocks execution instead of fabricating a price.
- Trade-only and already-covered depth records never refresh the last genuine quote receipt.
  They cannot reuse an older feature observation for a fresh entry. A session footer/disconnection
  emits an unsynchronized final tick, not a last-minute liquidation.

No future footer/quality score authorizes a trade. Complete framing/count checks are whole-file
integrity prerequisites only. Numerical features are rebuilt in receipt order; changing later prices
does not change earlier frames. `ReplayFrame.observation` exposes a typed observation only for a
newly applied healthy depth update. Snapshot availability rules intentionally differ from legacy
feature artifacts that included buffered pre-snapshot observations. Those artifacts are not reused
as execution-ready input, and existing builder output is not silently rewritten.

Recovery requires a separately identified capture with a fresh snapshot. Book state, CVD, trade-ID
baseline and feature warmup reset; account positions and risk checkpoints do not. The first usable
quote from the new session may protect an existing position even while entry features are warming.
This tests reconnection semantics using recorded sessions; it does not reconnect a network socket.

## Runner integration, binding and restart

Schema 6 adds append-only `paper_replay_sources`. Existing schema-1–5 APIs remain supported;
explicit `upgrade_schema()` is required for replay binding. No user journal was migrated during
development. Back up a closed journal before upgrading.

The durable binding fixes source session, exact capture bytes, feature/freshness configuration,
the current package's Python-source manifest hash and the optional candidate-case map/content hashes.
Changing any of these under the same session ID conflicts before new ticks execute. Hashes are local
integrity checks, not authentication, and do not fingerprint Python or third-party binary dependencies.
Do not rename sessions simply to evade a conflict in an existing paper run; resolve provenance and
account continuity explicitly. Code changes can intentionally prevent automatic replay continuation.

By default, replay proposes no entries. `candidate_cases` is an explicit mapping from generated tick
IDs to already-recorded case IDs, frozen in the binding even for a bounded prefix. Runner checks still
require the matching source/observation, causal case timestamps, health and current risk approval.
Supplying cases does not prove a historical strategy was free from human lookahead or overfitting;
research registration and held-out evaluation remain separate gates.

API sketch, with a funded initialized paper runner and declared inputs supplied by the caller:

```python
from ai_trader.trading.capture_replay import CaptureReplay

replay = CaptureReplay.from_path(
    selected_path,
    expected_sha256=declared_capture_sha256,
    source_session=declared_source_session,
    config=replay_config,
)
outcomes = replay.run(runner, max_frames=1000)  # No entry candidates by default.
```

All clocks use the recorded epoch nanoseconds. A historical replay must have a dedicated paper run
whose initial time precedes that capture, not a current-wall-clock seed that would force time travel.
Captures supplied to the same run must progress chronologically. The adapter is not a model-training
job or authorization to replay protected holdout data.

`max_frames` counts frames from the beginning, including previously committed frames. To continue a
prefix, reconstruct from the same bytes/config and increase the budget; do not skip raw records or
restore a guessed book. Stable tick IDs and the runner's persisted exact retries avoid duplicate
entries/exits. Each tick commits independently: a later failure preserves earlier committed ticks,
and a failed tick rolls back its marks/orders/results. The source binding may remain even if no tick
commits. There is no hidden restart cursor or exactly-once exchange guarantee.

## Actual verification

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_capture_replay.py
.venv\Scripts\python.exe -m pytest -q tests/test_capture_replay.py tests/test_paper_runner.py tests/test_durable_paper_gateway.py tests/test_paper_account.py tests/test_paper_lifecycle.py tests/test_trade_journal.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

Observed: 40 new replay tests pass; 233 combined replay/runner/gateway/ledger tests pass. Full attempt:
731 passed, 1 optional-Nautilus skip, 10 unchanged Windows Application Control/PyTorch collection
errors. Ruff lint/format pass. This is not a fully passing suite.

Tests use synthetic capture bytes and temporary SQLite files only: complete entry/target round trip,
snapshot-buffer timing, trade/depth gaps, stale event/quote distinction, sticky invalidation, reconnect
warmup/CVD reset with existing-position protection, prefix invariance, restart deduplication, changed
bindings, framing/corruption/budget rejection, and v5 migration/failure preservation. No real captures
were opened, no public feed started, no orders sent externally, and no model was trained.

## Remaining work

Quote fills still do not model L2 queue depth, liquidity consumption, latency or partial fills and
are not proof of profitability. The subsequent [capture-supervision and smoke slice](CAPTURE_SUPERVISION_AND_SMOKE.md)
now implements bounded buffers, receipt timing, recording quotas, shutdown, finite reconnect attempts
and an explicit zero-order operator command. Its tests are synthetic; operational failure recovery
still needs verification before an unattended campaign. Actual source clock skew,
network outages and feed resynchronization must be tested operationally rather than inferred from
these synthetic results. Numerical strategy evaluation, training readiness and native-library
environment blockers remain separate work. No live-trading switch or automatic promotion is enabled.
