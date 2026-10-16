# Prospective burst-repair diagnostic

## Predeclared check (2026-09-25; before launch)

Following the [bounded scheduling repair](CAPTURE_BURST_REPAIR.md), use the existing
`capture_timing` runner for one new **120-second public BTCUSDT diagnostic**, one attempt,
no reconnect/retry/replacement. This is an operational observation, not another multi-window
research campaign and not an input to training, validation or reserved evaluation.

Exact declaration: `logs/btcusdt_burst_diagnostic_20260925_1_plan.json` (local/Git-ignored).
Raw SHA256, recorded before launch:
`fcaa53ea39321d95758274c059f98583aca8ecfc23207fdaff0793018cd96162`.
New exclusive destination: `data/raw/btcusdt_burst_diagnostic_20260925_1/`.
This declaration is not a runnable `capture_schedule` contract: it freezes this single
diagnostic's purpose, source/runtime, limits and assessment before invoking the existing runner.
The runner writes its own immutable intent and checksum-enveloped timing report.

Source pin: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Runtime: Python 3.12.10, NumPy 2.5.3, websockets 17.1. Default limits remain 256 queued
messages, 256 KiB/message, 99,997 stream events, 32 MiB raw bytes and a five-second idle
timeout. Duration includes snapshot/stream after connection; connection/cleanup/validation
are additional, and OS stalls prevent a hard total wall-clock guarantee.

Acceptance is fixed before observing this sample:

1. Collector integrity succeeds, with the unchanged 2-second event-lag / 100-ms future-skew
   limits, a final capture/report and no partial publications.
2. Bounded hashes and report payload digest match; intent, raw-source references, source/runtime,
   exact duration, limits, diagnostic role and disabled execution/training authority agree.
3. Received/enqueued/processed counts equal the positive raw event total; high-water is within
   1–256. Snapshot timing and positive receipt/depth/streaming-queue/watchdog coverage exist,
   with zero wall or depth-exchange regressions.
4. Maximum wall/QPC receipt and depth-receipt gaps are at most 500 ms. Maximum streaming queue
   wait, parse/write time, event-loop lag and absolute wall/QPC gap difference are at most 50 ms.
   Report startup snapshot-buffered waiting separately; it is not a streaming-queue violation.

These operational checks reuse the existing diagnostic alert thresholds; they do not change
collector, label, cost, training or strategy-promotion rules. Collector completion alone does
not mean these stricter diagnostic checks pass. Equal wall timestamps are not themselves a fault.
The run cannot establish independent custody, sustained reliability, profitability, the source
of the prior 2.87-second gap or controlled before/after performance attribution.

Before launch: verify the full regression, lint/format, source/runtime, a fresh destination,
adequate disk space and no conflicting ingestion/training/model process. Do not edit source or
dependencies while acquisition is running. After process exit, inspect only this new run's
bounded artifacts. Preserve the prior failed campaign and its raw/reserved contents untouched.
Stop after this single outcome; no labels, feature datasets, fitting, Qwen calls or trades.

## Outcome

**Completed and passed the predeclared diagnostic checks**, one attempt, no retries. The
declaration above was written and its raw hash recorded before launch. Command start was
13:42:06.866815 UTC; raw session boundaries were **13:42:07.908541–13:44:07.913083 UTC**
(120.004542 seconds). The command exited successfully at 13:44:12.142062 UTC, after cleanup,
integrity validation and sidecar publication. This was not an unattended service.

Preflight: **2,660 Python tests passed, one optional Nautilus skip** (123.19 seconds),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` passed. Source/runtime
matched the frozen declaration; the destination did not exist, about 772 GB of disk was free,
and no conflicting ingestion/training/model process was found. No configuration changed.

Post-exit verification checked bounded bytes and all declared hash references, the canonical
report digest, intent/source/runtime/limits/authority bindings, raw counts and duration. An
independent invocation of the existing receipt-causal replay validator found no market faults
and 1,186 post-snapshot observations across 6,311 replay frames. No feature dataset or labels
were exported. These transient integrity observations are not training eligibility evidence.

| Measurement | Observed result |
| --- | --- |
| Aggregate trades / depth events | 5,158 / 1,200 |
| Received / enqueued / processed | 6,358 / 6,358 / 6,358 |
| Capture bytes / physical records | 5,129,165 / 6,361 |
| Queue high-water / capacity | 49 / 256 |
| Largest all-message gap, QPC / wall | 259.7606 / 259.5782 ms |
| Largest depth-receipt gap, QPC / wall | 326.6413 / 326.6241 ms |
| Event-loop probe samples / maximum lag | 2,242 / 25.2460 ms |
| Streaming queue samples / maximum wait | 6,309 / 2.0376 ms |
| Parse/write samples / maximum duration | 6,358 / 1.9372 ms |
| Snapshot-buffered samples / maximum wait | 49 / 1,389.0913 ms |
| Maximum absolute wall/QPC gap difference | 1.7221 ms |
| Wall / depth-exchange regressions | 0 / 0 |
| Equal adjacent wall receipts | 3,356 |

All receipt/depth gaps stayed within 500 ms; streaming queue, parse/write, loop and clock-gap
metrics stayed within 50 ms. The 49 startup snapshot-buffer alerts were accounted separately,
exactly as predeclared. All other alert categories were zero. The complete directory contains
only `intent.json`, `capture.jsonl` and `timing.json`; no partial files remain. Orders and model
calls are zero; training, promotion and execution authority remain false.

Local artifact pins (raw SHA256):

| Artifact | SHA256 |
| --- | --- |
| Declaration in `logs/` | `fcaa53ea39321d95758274c059f98583aca8ecfc23207fdaff0793018cd96162` |
| `intent.json` (658 bytes) | `9a48df46eb39d90343f00186e0aeb44204dfb1dde5ed0a6ea7dcc1686f353071` |
| `capture.jsonl` | `1dceec829cfba669c2481c03cc2239677672f580073b7d6f191826917c72f576` |
| `timing.json` (6,470 bytes) | `673bbdef5da9570e1f6d783920e046bef43de23cc73e06fbee3d5960fdbd376f` |

Timing payload SHA256: `38656ca4a57dfdb350d1c84b49a99ada0d770b72ba9736807e4a2781c71e164b`.
Production source stayed `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
The declaration and acquired files are local/Git-ignored; these local hashes do not authenticate
independent custody. The prior failed campaign, its raw/reserved contents and all old datasets
were left untouched. No credentials, training, Qwen inference or orders were involved.

## Interpretation and next step

The repaired collector handled this public-feed sample successfully under the original capture
limits and the stricter prospective diagnostic checks. The prior overflow and >500-ms depth gaps
were not reproduced. This is not proof that the repair caused every latency result or that the
unexplained earlier 2.87-second gap cannot recur; market load and transport conditions differ.

Next prepare a **distinct** prospective multi-window research campaign under the repaired source,
with frozen train/validation/reserved session roles and unchanged cost, quality and class-diversity
gates. Decide future windows and host availability before launch. Do not relabel this diagnostic as
training data, reuse the failed campaign's successful subset or collect until profitable. No new
multi-window plan/capture or model fitting was started after this single terminal outcome.
The accumulated work remains local and uncommitted.
