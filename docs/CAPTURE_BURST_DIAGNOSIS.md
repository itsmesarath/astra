# Windowed validation overflow: diagnosis, not a recorder patch

Historical diagnosis below describes the pre-repair implementation and harness. The subsequent
[bounded scheduling repair](CAPTURE_BURST_REPAIR.md) changes production code and the current
harness; it does not rewrite the failed campaign, its pins or these original measurements.

## Outcome and scope (2026-09-25)

Campaign `btcusdt-windowed-20260925-1` terminated with `receiver.queue_overflow` during its
12:30 UTC validation slot. Both earlier training slots were recorded complete; reserved was
never started. The runner exited, no complete campaign receipt exists, and the follow-up was
removed. Retain the whole failed campaign; do not train on a successful subset or resume it.

This investigation read only campaign metadata and the failed validation timing sidecar, plus
implementation/dependency source. It opened no raw capture, reserved content or label dataset.
The validation partial was only statted (151,623 bytes), not read, hashed or repaired. No source,
dependency, capture setting, quality threshold or data artifact was changed; no new Binance
connection, training, Qwen call or order ran. The added reproduction uses synthetic frames only.

## Evidence retained by the real run

| Measurement | Observed value | Interpretation |
| --- | --- | --- |
| Received / enqueued / processed | 402 / 401 / 145 | One attempted enqueue was rejected; 256 queued messages remained unprocessed |
| Application queue high-water | 256 | Exactly the unchanged configured capacity |
| Longest receipt gap (QPC) | 2,868.7162 ms | Application saw a receipt hiatus before the final burst; not a wire-time measurement |
| Maximum streaming queue wait, processed items | 5.2399 ms | Does not measure the unprocessed tail |
| Maximum parse/write, processed items | 1.276 ms | No measured multi-second writer stall in processed data |
| Maximum measured event-loop lag | 27.2741 ms | No comparable 2.87-second sampled loop stall; does not prove every interval was observed |
| Equal adjacent wall-clock receipts | 377 | Consistent with batched delivery and a coarse clock; not proof of exact transport batch size |
| Snapshot availability | About 1.526 s after capture start | Overflow occurred after snapshot availability, not solely in the initial snapshot buffer |

The timing report's raw SHA256 and its canonical payload digest were verified. Its plan/session/
failed-state bindings match the failed campaign. These local hashes establish consistency, not
independent custody or attribution to Binance, the ISP, TLS, the OS or the Python scheduler.

Relevant pins (raw-file SHA256 unless noted):

- Schedule: `8d997c8389fbe3a14e6b5d44b969d9ba3c7080d6f4dcaf7d47dc53ead80b4f73`.
- Failure: `f8332704b4424bc4473bb20eea8aafac37f8bb0d6be83ffc93ae97294a9b3b04`.
- Audit: `19904339ac9f852776c52c43e423c27df7c5173be52541273191dfe3ae28c680`.
- Validation timing: `83996792ededddd60cb509132d9d111012760602052cd65998f9d8c517fa0ced`.
- Timing payload: `7b43eef5191574d948a72667588c1b51ad9945de518862f6a8eda87db68f04be`.
- Acquisition/diagnosis source: `c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.

Files are under `data/raw/btcusdt_windowed_20260925_1`; the original schedule is
`logs/btcusdt_windowed_plan_20260925_1.json`.

## Reproduced scheduling weakness

`receive_messages` timestamps and enqueues each message without an explicit scheduling handoff.
An async iterator does not itself guarantee that another task runs. The installed websockets
17.1 `SimpleQueue.get` returns immediately when buffered frames exist; its `Assembler` can
therefore return successive complete buffered messages without suspending the receiver.

The library's `max_queue=16` is a flow-control high-water threshold, not a hard maximum batch
size. Its installed assembler source explicitly handles a single protocol callback producing
more frames than that threshold; requesting a transport pause cannot undo frames already parsed.
The writer meanwhile uses `_while_receiving` for each queue item, adding task/wait/cleanup turns.
These mechanisms allow a brief buffered burst to fill the application queue even with a ready
writer. This does not establish that average parsing or disk throughput is insufficient.

The upstream [asyncio FAQ](https://websockets.readthedocs.io/en/latest/faq/asyncio.html) explains
why an await need not suspend a coroutine. The [buffer documentation](https://websockets.readthedocs.io/en/latest/topics/memory.html)
describes the distinct buffering layers and why enlarging queues alone can increase latency.
Exact receive-path behavior above was inspected in the locally installed 17.1 source.

## Offline reproduction

[The diagnostic harness](diagnostics/queue_burst.py), at the historical hash below, used the installed
assembler with synthetic text frames and the then-unchanged receiver/256-slot queue. It started a
ready consumer before releasing the buffered burst, bounded the run, and cancelled/drained all
tasks. It read no data files, opened no sockets and wrote no capture. The watched consumer used the
`_while_receiving` helper; the direct consumer is a scheduling control, not the production writer.

| Synthetic case | Result |
| --- | --- |
| 256 frames, immediate source, direct consumer | All 256 consumed; high-water 256 |
| 257 frames, immediate source, direct or watched consumer | Overflow at message 257, before any consumer processing |
| 257 frames, yield between source messages, direct consumer | All consumed; high-water 1 |
| 257 frames, yield between source messages, watched consumer | All consumed; high-water 171 |
| 1,024 frames, yield between source messages, watched consumer | Overflow on received message 385; 128 consumed and 256 pending |
| 257 frames, yielding source, deliberately blocked consumer | Correctly refuses at the unchanged capacity |

All seven scenarios produced the same outcomes on three repeated runs. A direct consumer may
drain queued items after the receiver has already failed; that is not successful acquisition.
The counterfactual source yield changes simulated delivery scheduling; it is not a production
patch, a latency benchmark or proof of sufficient throughput. In particular, a one-line
`sleep(0)` addition alone does not solve the watched-consumer case at larger burst sizes.

```powershell
.venv\Scripts\python.exe docs/diagnostics/queue_burst.py
```

The command now exercises the repaired implementation; its current results are recorded separately
in the repair document. Historical harness raw SHA256:
`57190e2d3bb7f930cd9c409fddbbfb4094f3f4d21cbc8ee00873f9199cd5d9cb`.
Local dependency source hashes: `asyncio/messages.py`
`9d44c84b9aa3ea4d38dc0fedebd8ffe37424952c145ee8436c180c0122505178`, and
`asyncio/connection.py` `c3aca0018eefa58877776e71653ba904dd3a1d156b2f6d36c1feec63c8a7b58c`.

## What remains unproven and the next implementation step

The real telemetry is consistent with buffered-burst scheduling starvation, and the mechanism
is reproducible in the existing code. It does **not** identify where the preceding 2.87-second
receipt gap originated or prove the exact real transport batching sequence. Freshness failures
could remain after burst handling is improved; the old failure cannot be repaired retrospectively.

Next design and test a bounded receiver/writer scheduling handoff plus bounded draining of
already-ready queue items, avoiding a fresh watched task for every buffered item. Preserve:

- Original application receipt timestamps, stream order and snapshot causality.
- The existing queue/memory/message/event/byte ceilings and genuine-overload refusal.
- Prompt receiver/observer failure checks, deadline checks and cooperative cancellation.
- No dropped packets, unbounded drain loops, hidden blocking queue puts or relaxed freshness.
- No retry/replacement/relabeling of this campaign, even after a repair passes tests.

Required tests include bursts above capacity, repeated bursts, slow/absent consumers, slow
snapshots, original timestamp/order checks, deadline expiry, malformed messages, cancellation
and absence of leaked tasks. Only after a full verified repair should a distinct, predeclared
bounded diagnostic acquisition be considered. No new real campaign was prepared in this slice.

Verification: **2,637 Python tests passed, one optional Nautilus skip** (124.55 seconds),
**38 JavaScript tests passed**, Ruff lint/format passed, and all seven diagnostic scenarios
repeated three times. Production source fingerprint stayed unchanged throughout.
