# Bounded capture scheduling repair

## Scope (2026-09-25)

Implemented the next step from the [offline burst diagnosis](CAPTURE_BURST_DIAGNOSIS.md).
This is an offline implementation/test slice, not another acquisition experiment. The failed
`btcusdt-windowed-20260925-1` campaign remains quarantined as a whole. Its two completed training
slots are not eligible for successful-subset processing; validation failed and reserved never ran.
No raw capture, reserved content, label dataset or model file was opened in this repair.
No capture, retry, network request, model call, training or order was started.

## Implemented behavior

- The receiver timestamps a message immediately when returned by the WebSocket iterator, keeps
  `put_nowait`, then explicitly yields once. Buffered messages no longer monopolize the loop just
  because the library can return them without suspending. Full queues still raise overflow.
- The production writer uses `get_nowait` for ready FIFO items instead of creating a watched
  task per item. Only an empty queue needs the existing watched wait and idle-timeout handling.
- Each writer quantum ends after **64 events or 5 ms**, whichever is observed first. These are
  fixed scheduling constants, not user-tunable capture limits. Deadline and completed receiver/
  observer checks occur between individual writes. The finite shutdown tail also yields at
  the same boundaries, after the receiver and observer have been cancelled and drained.
- Counts, byte/event/message quotas, queue capacity (default **256**), receipt clocks, failure
  codes, snapshot-first framing, causal replay, timing schema and freshness gates stay intact.
  Pending gets are cancelled/drained; existing early-Windows-timer handling remains in place.

The time quantum is cooperative: it is checked **between** synchronous parse/write operations,
not inside one operation. It cannot interrupt an OS/disk stall or promise hard-real-time latency.
Application receipts remain application receipts, not wire timestamps. The newly explicit yields
can change actual receipt scheduling; the code does not fabricate, normalize or replace timestamps.
A slow writer may still cause upstream buffering/stale data even with a small application queue.
The existing refusal/quality gates remain necessary.

## Offline evidence

The revised [diagnostic harness](diagnostics/queue_burst.py) uses the installed websockets 17.1
assembler, prebuffered synthetic frames and the current production receiver. It has no socket or
capture-file IO. The production consumer now calls the same bounded writer helper as `collect`;
the direct and per-item-watched consumers remain explicitly labeled scheduling controls.

| Current synthetic case | Observed result |
| --- | --- |
| Production consumer; 256, 257, 1,024 or 4,096 prebuffered frames | All received and consumed in order; queue high-water 2/256 |
| Direct consumer; 257 frames | All consumed; high-water 1/256 |
| Old per-item-watched consumer; 1,024 frames, repaired receiver | Still overflows at received 385: 128 consumed, 256 pending |
| Blocked consumer; 257 frames | Correctly fails at received 257; 256 enqueued, none consumed |

This isolates why both sides of scheduling needed changes. These are tiny synthetic messages,
not exchange-rate, payload-size, disk-throughput or production-reliability benchmarks. The old
diagnosis table and historical harness pin remain separate from these new outcomes.
All seven revised scenarios repeated with the same outcomes on three runs.

Added **23 regression cases** covering timed/untimed 257/1,024-frame bursts, four repeated
1,024-frame bursts, exact receipt-object/timestamp preservation, FIFO order, nonblocking enqueue,
blocked/slow consumers, snapshot overflow, ready-queue count/time fairness, failure precedence,
deadlines, cancellation, shutdown draining, malformed input and event/byte quotas. Complete
synthetic 1,024-event files pass the actual receipt-causal validator. Failure paths retain partials
without a footer/publication and clean up their tasks. Existing early-timer, idle, message-size,
clock-regression and instrumentation-parity tests are retained.

```powershell
.venv\Scripts\python.exe -m pytest -q
node --test tests_js/review_workbench.test.cjs
.venv\Scripts\ruff.exe check .
.venv\Scripts\ruff.exe format --check .
.venv\Scripts\python.exe docs/diagnostics/queue_burst.py
```

Baseline: **2,637 Python tests passed, one optional Nautilus skip** (122.11 s).
Final verification: **2,660 Python tests passed, one optional Nautilus skip** (124.34 s),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` passed.
The new focused burst suite passed all 23 cases. Current production source fingerprint:
`e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Current harness raw SHA256:
`265dbed4904e0de9efe484c56416c9bd718c820336ec1783325fcc61b2344c43`.
Historical acquisition/diagnosis source remains
`c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.
Existing plans are not re-pinned or made runnable under changed code.
The accumulated dirty/untracked working tree was preserved; this work remains local and uncommitted.

## Next gate

Consider one distinct, predeclared, bounded diagnostic capture under the new source pin, with
unchanged quotas and timing instrumentation, before another multi-window research campaign.
Declare the diagnostic purpose, duration, acceptance checks and terminal no-retry policy before
acquisition; it is not a training source selected after inspecting results. This slice does not
prepare or launch that experiment. No successful diagnostic can repair the old campaign or by
itself authorize fitting, paper strategy promotion or live trading.

The origin of the real 2.87-second receipt gap remains unknown. Training still requires a complete
prospective fold that passes unchanged data-quality and class-diversity gates; local Qwen training
has its separate protected-case/evaluation requirements. No profitability is established.
