# Bounded capture-timing diagnostics

The first [event-label experiment](PROSPECTIVE_EVENT_TRIAL.md) found 0.57–1.04-second receipt
gaps that censored pending labels. Its recorded timestamps cannot determine whether the delay
came from the network, buffering, application scheduling or clocks. This diagnostic addition
measures those components prospectively. It does not repair or relabel that experiment.

## Timing contract

The existing `collect(seconds, output_path=..., limits=...)` path remains unchanged by default.
An optional, single-use `CaptureTiming` instance adds bounded counters and a 50-ms event-loop
probe. No diagnostic fields are written into the market capture. Wall-clock receipt timestamps
are neither replaced nor interpolated; the capture remains schema version 1. Tests compare
complete raw bytes with diagnostics enabled/disabled under identical synthetic wall receipts.

The local Python 3.12.10 runtime reports:

| Clock | Backend | Reported resolution | Use |
| --- | --- | --- | --- |
| `time.time_ns` | `GetSystemTimeAsFileTime()` | 15.625 ms | Original market receipt time |
| `time.monotonic_ns` | `GetTickCount64()` | 15.625 ms | Not used for the new latency counters |
| `time.perf_counter_ns` | `QueryPerformanceCounter()` | 100 ns | New monotonic elapsed-time diagnostics |

These are reported clock resolutions, not measured end-to-end timing accuracy. The coarse
wall clock can explain equal timestamps, but it cannot by itself explain a one-second stall.
The sidecar records the runtime clock metadata, so a different host is not assumed to share
these backends or resolutions. QPC readings are process/host timing coordinates, not UTC.

Measured components:

- Receipt gaps in both wall-clock and high-resolution monotonic time, including their signed
  difference, equal wall receipts and wall regressions. Existing backwards-clock refusal remains.
- Queue high-water and counts of received, enqueued and successfully parsed/written messages.
  Snapshot-buffered waiting is accounted separately from normal streaming queue waiting.
- Queue waiting from application receipt until processing starts; this includes async queue
  delivery/scheduling. It does **not** measure time spent in the kernel or WebSocket library.
- Stream-event parsing, validation, JSON encoding and `file.write` duration. This is not disk
  persistence latency: snapshot/footer writes and final flush/fsync are outside that metric.
- Depth-stream receipt gaps alongside the difference between adjacent depth exchange-event
  timestamps. These are raw stream events, not necessarily applied-book observations.
- Event-loop probe lateness relative to a fixed 50-ms deadline. The next deadline starts from
  the observed wakeup; missed intervals are not replayed in a busy catch-up loop. It covers the
  connected capture/snapshot period, not connection setup, offline replay validation or shutdown.

Each metric uses fixed histogram buckets, exact counts/totals/maxima, and only the first 32
above-threshold samples. Thresholds are diagnostic selectors, not capture or trading gates:
500 ms for receipt gaps and 50 ms for other durations/clock-gap differences. Counts include
all observations after sample storage is full. The sidecar is bounded to 256 KiB. There is no
per-message diagnostic file write, unbounded event list, payload logging or extra network source.
Instrumentation has nonzero overhead and cannot prove absence of unobserved stalls.

The later [startup recording repair](CAPTURE_STARTUP_REPAIR.md) keeps this schema but changes
the write destination to bounded staging. Under that new source, `parse_write`/`processed_events`
measure parsing and staging, excluding final assembly. Snapshot-buffered queue waits end at
staging, not snapshot completion; they do not measure residence on disk. Causal availability is
unchanged. Interpret the historical measurements below under their original source pins.

## One explicit operational sample

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_timing --output-dir data/raw/new_timing_run --seconds 60 --enable-public-capture
```

This is a single diagnostic research session, **not** an automatic train/validation/holdout
campaign. It requires a new output directory and explicit public-capture opt-in; duration is
1–300 seconds. The existing fixed byte/message/event/queue/freshness limits remain unchanged.
No retry or resume occurs, and no background service remains after completion/cancellation.

The directory contains an exclusive `intent.json`, the normal `capture.jsonl` (or retained
`.partial` on capture failure), and a checksum-enveloped `timing.json`. The intent pins code,
runtime and resource limits. A completed report pins the actual raw capture bytes. Failures
retain available counters and only the exception type; no packet-bearing error message is saved.
A diagnostic-publication error does not delete a valid raw capture, and a disk failure may
prevent the failure report itself. An incomplete directory is not a successful run.

Observer failure stops recording rather than silently producing a diagnostic success. Cleanup
cancels and awaits both receiver and observer. OS, DNS, socket-worker and disk stalls still
prevent a hard wall-clock guarantee. No market timestamps are changed and no freshness, label,
training, model-promotion or execution gate is relaxed. Reserved data is not an input.

## Current verification

Verified 2026-09-24: **2,281 Python tests passed, one optional Nautilus skip** (99.06 seconds),
all **38 JavaScript tests passed**, and Ruff lint/format passed. The 37 new synthetic tests cover
histogram boundaries, bounded samples, two-clock measurements, snapshot versus streaming wait,
unchanged raw bytes, cancellation/task cleanup, observer faults, limits, publication failures,
code drift, canonical CLI class identity and absence of retries.

One **60-second public-data diagnostic capture completed**, with the original limits unchanged
and no retries. It recorded 224 aggregate trades and 599 depth events (823 received/enqueued/
processed messages) in 508,583 bytes. No partial files remain in this diagnostic directory.
No old research/held-out capture was opened, relabeled or repaired.

| Measurement | Observed result |
| --- | --- |
| Largest depth receipt gap, QPC / wall clock | 437.0970 / 437.2956 ms |
| Depth receipt gaps above 500 ms | 0 |
| Largest all-message QPC receipt gap | 339.7985 ms |
| Event-loop probe samples / maximum lateness | 1,087 / 29.0149 ms |
| Event-loop delays above 50 ms | 0 |
| Streaming queue samples / maximum wait | 807 / 1.8903 ms |
| Snapshot-buffered queue samples / maximum wait | 16 / 1,420.7636 ms |
| Stream parse/write samples / maximum duration | 823 / 0.3462 ms |
| Queue high-water / configured capacity | 47 / 256 |
| Equal adjacent wall-clock receipts | 129 |
| Wall-clock / depth exchange timestamp regressions | 0 / 0 |
| Largest absolute wall-gap minus QPC-gap difference | 1.5033 ms |

Fifteen buffered startup messages waited more than 50 ms while the REST snapshot was pending;
these are explicitly separated from steady-state queue waiting. Every other diagnostic alert
category remained at zero. Reported platform clock resolution is not the same as observed
timestamp granularity; do not infer a 15.625-ms actual error from the clock metadata alone.

This run **did not reproduce the earlier >500-ms gaps**. It provides no evidence of a large
measured consumer-processing or event-loop bottleneck in this sample, but does not establish
the cause of earlier stalls, reliable sustained ingestion, or a profitable strategy. A new
recording with a different market load is not a controlled before/after performance comparison.
No latency fix, gate relaxation or claim that the old failed-quality fold now passes was made.

Artifacts are local/Git-ignored under `data/raw/btcusdt_timing_20260924_1/`:

| Artifact | Raw SHA256 |
| --- | --- |
| `intent.json` | `9f15cdbdcf3ba4a07266428263d869bad2a9bbd920a76e590fa9355a58f18915` |
| `capture.jsonl` | `e6d95c1b1fb8507d91e05a6c7903b23fe27ce869205351551cb1bd3022fb6c03` |
| `timing.json` | `cd8d585a55dd2bc4c2367feb59534a551655b65a6491f0ccef1ef3d811b2383c` |

The source and intent hashes match the final timing report. Its raw JSON file is 4,984 bytes,
well within the 256-KiB publication cap. The frozen implementation remained
`4723ec60ff1901e91300eabfd6d95ad1938ed828dab089e93e05682da33529c0` after completion.
The session is diagnostic research data, not prospectively reserved evaluation or a training fold.
No model fitting, Qwen calls, credentials, orders or reserved-source reads occurred.

Next: carry optional diagnostic sidecars into a newly planned longer multi-session campaign,
then repeat the fixed event-label quality checks without relaxing freshness or choosing only
successful intervals. Preserve the original failed-quality result and reserved raw session.

The [versioned multi-session extension](INSTRUMENTED_CAMPAIGN.md) now implements that handoff:
timing is frozen in the plan, pinned by receipt/audit and checked during research intake. Only
train/validation are instrumented; reserved telemetry is neither collected nor opened by research.
