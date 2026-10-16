# Bounded public capture and offline paper smoke check

Current measured update: one [60-second public capture and zero-order offline paper check](REAL_DATA_READINESS.md)
passed on 2026-09-24. That run also exposed and fixed a separate standalone feature-export
snapshot-boundary bug. The paper replay was already causal. This does not establish an unattended
service, profitability or a protected evaluation dataset; the historical failed partial stays excluded.

Implemented 2026-09-24. These are opt-in commands, not an unattended trading service.
Development used synthetic sockets, captures and temporary databases only. No feed was
started, real dataset opened, market-data training job run, credentials read or live orders enabled.

## Recorder integrity

`ingestion.collect_combined.collect` retains the existing `collect(seconds)` return contract.
It additionally accepts an exact new `.jsonl` destination and typed `CaptureLimits`.

- Capture duration is an integer from 1 to 3,600 seconds, covering REST snapshot and streaming
  after WebSocket connection establishment. Connection timeout is 10 seconds; close timeout is 2.
- Application receipts are timestamped immediately after WebSocket delivery. They are **not**
  kernel/wire timestamps. The library buffer is limited to 16 frames; the application queue
  defaults to 256 messages. Full queues fail loudly instead of blocking ingestion or dropping data.
  Exchange-event lag/future skew is checked again during validation; backpressure-free wire timing
  has not been demonstrated on a real connection.
- Default message limit is 256 KiB; aggregate application queue payload budget cannot exceed 64 MiB.
  Python object overhead and the separate WebSocket/validation buffers are additional.
- Each attempt is limited to 32 MiB and 99,997 stream events, leaving three framing records inside
  the replay limit. Snapshot bodies are limited to 1,900,000 bytes. JSON duplicates and nonfinite
  constants are rejected. Idle timeout defaults to 5 seconds while waiting for another message.
- REST reads check a 10-second monotonic deadline between chunks; each socket operation has its
  own 10-second timeout. Cancelling the async wrapper cannot kill its HTTP worker. A read already
  in progress can outlive the deadline; process shutdown may wait for it. OS DNS, disk and scheduler
  stalls are not hard real-time bounded. This is not a hard wall-clock guarantee.
- Receiver failures are observed during snapshot acquisition and queue waits. Shutdown cancels
  and awaits async tasks, including when the snapshot, parsing, quotas or caller fail.

Only a newly created `.jsonl.partial` is written. Failure/cancellation preserves that file and
never publishes a complete capture. After planned collection ends, queued receipts are drained,
counts/footer written, and the file flushed/fsynced. The same receipt-causal replay consumer
validates framing, depth/trade continuity, snapshot availability, coverage and event freshness,
using one book level and its default 2-second lag/100-ms future-skew limits. At least one healthy
post-snapshot depth observation is required. This is integrity screening, not training approval.

Successful publication uses a same-volume hard link that refuses to replace an existing file;
the owned partial link is then removed. Unsupported filesystems fail closed. A process crash
after linking can leave both names; a machine/power failure still depends on filesystem durability.
Treat local files as trusted single-writer artifacts, not a tamper-proof store. Never rename an
invalid partial into a complete capture to bypass validation or append a reconnect to it.

## Explicit reconnect budget

`ingestion.capture_supervisor.capture_with_retries` adds a separate opt-in supervisor. The older
multi-session campaign does **not** automatically gain retries. Every attempt uses a new path,
connection, snapshot and book/CVD/warmup baseline; no session stitching occurs.

The default is one attempt, maximum five, with an explicit 0–60 second retry delay. Only
`CaptureInterrupted` failures retry. Quota, disk, unexpected contract errors and cancellation
stop immediately. Each attempt's resource quota applies separately (at most five times 32 MiB
of recordings under default byte limits). Quotas can deliberately terminate busy/long sessions;
the system does not enlarge them automatically.

An exclusively created JSONL audit records configuration, each attempted final/partial path,
failure, completion or cancellation, flushing/fsyncing every record. An abrupt kill or failed
audit write can leave the audit without a terminal record: that is incomplete, not success.
Do not overwrite/reuse it. A completed capture is never deleted just because a later audit write
fails. Retained partials require an explicit operator retention decision; no cleanup loop runs.

Safe help checks (no network):

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.collect_combined --help
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_supervisor --help
.venv\Scripts\python.exe -m ai_trader.trading.paper_smoke --help
```

Only after separately authorizing an actual public-data capture, an operator can use this example
with a **new** audit filename in an existing directory. This command contacts Binance; it was not
run during development:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_supervisor --manifest data/raw/NEW_AUDIT.jsonl --seconds 30 --attempts 2 --retry-delay-seconds 2
```

## Offline, zero-order paper smoke command

The smoke command requires a selected capture, independently declared SHA256, source-session ID,
new journal path, run ID, initial simulated USDT cash and frame budget. No dataset discovery or
automatic source/hash selection occurs. Do not select reserved/held-out datasets for convenience.
The source hash pins bytes; it does not authenticate their origin or authorize research use.

Example template only; substitute approved inputs and a new output filename yourself:

```powershell
.venv\Scripts\python.exe -m ai_trader.trading.paper_smoke --capture data/raw/SELECTED.jsonl --sha256 DECLARED_SHA256 --source-session DECLARED_SESSION --journal data/processed/NEW_SMOKE.sqlite --run-id NEW_SMOKE_RUN --initial-cash-usdt 1000 --max-frames 1000 --levels 5 --rolling-window-ms 10000
```

This command has **no network client, model, signal generation or candidate-entry option**.
It starts flat, seeds time from the recorded snapshot receipt, and durably activates the kill
switch. Fixed risk/fee settings are smoke-test scaffolding, not a recommended strategy/allocation.
Any existing order history, including unfilled orders, prevents use of the smoke workflow.

One invocation wraps all its ticks in a single database transaction, preventing concurrent writers
and rolling back if processing fails or an unexpected order appears. This differs from the library
replay's default per-tick commits. A failed first invocation can leave a metadata-only journal for
diagnosis; it is not silently deleted/reinitialized. Choose a new output after investigating.

To extend an interrupted **successful prefix**, repeat exactly the same inputs with `--resume` and
a larger `--max-frames` (maximum 10,000). The budget counts from the start, including existing ticks.
Stable identities deduplicate retries; configuration, bytes, code-source binding, run identity,
account seed and kill-switch state must match. Missing journals, old schemas and mismatched
configuration fail instead of creating, migrating or resetting state. Concurrent readers are
possible, but this bounded transaction is not a multi-writer paper-service design.

JSON output separates session consumption, frame-budget exhaustion, market faults, quote-health
counts, and `check_result` (`passed`, `incomplete`, `failed`). A full replay without any healthy
quote fails the check. Reported market faults also fail a bounded prefix. CLI exit code 2 indicates
a failed check; other exceptions fail nonzero. Exit code 0 with `incomplete` is **not** readiness.
Zero orders, unchanged cash and a passed plumbing check are not evidence of a profitable strategy.

## Verification and next gates

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_collect_combined.py tests/test_capture_supervisor.py tests/test_paper_smoke.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

Focused coverage: 73 new tests. Includes publication races, disconnect during REST, malformed
data, overflow, backwards receipt clock, quotas, disk/REST deadlines, cancellation, bounded retries,
source/config conflicts, full and prefix rollback, order-history refusal and actual synthetic CLI
execution. Final full-suite result: **923 passed, 1 optional-Nautilus skip**; Ruff lint and formatting
pass (159 Python files). The initial baseline still had ten Windows/PyTorch collection errors,
but both final full runs loaded PyTorch successfully without environment/security changes by this
task. The cause of that external state change is not established. No native-policy bypass or
replacement environment was introduced.

The subsequent [registered microstructure policy slice](MICROSTRUCTURE_POLICY.md) now implements
research-only policy-to-case screening with synthetic no-lookahead/risk tests. Next: an explicitly
authorized small public-data capture and offline smoke check, plus a bounded strategy-to-paper
adapter with ledger-derived risk and explicit activation. Then operator-approved forward paper
operation and cost-aware event labels/baseline training.
Unattended operation, automatic strategy selection, Qwen integration and live connectivity remain
unimplemented. Optional Nautilus native evaluation remains unverified here; this test run does not
establish that its separate environment's earlier native-policy blocker is resolved.
