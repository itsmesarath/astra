# Snapshot-pending capture repair

## Evidence and scope (2026-09-25)

[Campaign -3](WINDOWED_CAMPAIGN_20260925_3.md) failed before snapshot availability, with
257 received messages, 256 queued and zero processed. Offline source inspection confirms the
writer previously started only after the snapshot returned. A new synthetic test held the
snapshot pending while delivering a burst; both timed and untimed cases reproduced overflow
at message 257 under the previous source. This establishes a reproducible startup bottleneck,
not the reason for the real snapshot delay or incoming burst.

This slice changes and tests local code only. No public capture, network request, retry, model
call, label generation, fitting or order occurred. No historical raw, reserved, label or model
contents were opened. The failed/canceled campaign claims remain unchanged and cannot resume.

## Implemented recording lifecycle

1. Exclusively create the normal `.jsonl.partial` and a sibling `.jsonl.stream.partial`.
   Existing destinations/staging files refuse before connection; never overwrite or resume.
2. After the connection/start guard, run the receiver and bounded writer immediately, alongside
   snapshot acquisition. Parse and encode events once into the staging file, retaining original
   application receipt timestamps and FIFO order. No model, feature engine or order path runs.
3. Record the actual snapshot availability in the main partial. Continue staging until the
   unchanged acquisition deadline; snapshot waits also observe writer failures. Receiver,
   writer, snapshot wait and optional observer are canceled/drained on failure or cancellation.
4. After stopping acquisition and draining its bounded FIFO tail, copy staging into the main
   partial in at most 64-KiB chunks, yielding between chunks. Append the counted footer and
   flush/fsync. The existing snapshot-first schema and receipt-causal validation remain intact.
5. Only after successful validation, remove this run's redundant staging file and publish by
   the existing no-overwrite hard link. Failures before that cleanup retain both partials;
   later publication failures retain the complete main partial. No automatic repair follows.

The acquisition metadata checker also refuses a final capture accompanied by residual staging.
A crash or partial file is not a complete session, even if some events were successfully staged.
The legacy supervisor's primary partial pointer is unchanged; a failed run may now also retain
the sibling stream partial. Both are evidence, not independently replayable/training inputs.

## Bounds and tradeoffs

- The application queue remains **256**, with immediate refusal on overflow and no blocking
  enqueue. The receiver still yields after each message; writer batches remain 64 events/5 ms.
  There is no new growing in-memory buffer or snapshot retry.
- **The 32-MiB byte ceiling includes staging and assembly together.** Before accepting an event,
  reserve its staged encoding and eventual final copy. Header/snapshot/footer bytes also count.
  This is stricter than final-file-only accounting: effective final event capacity is roughly
  half the former byte ceiling. No capture, message, event or research-processing cap increases.
- The idle watchdog now also covers startup; a silent feed need not wait for a slow snapshot.
  Connection, snapshot worker and capture deadlines are not extended. Genuine overload, byte/
  event exhaustion, malformed input, stale receipts and missing book bridges still fail closed.
- The extra disk write/copy has overhead. Synchronous parse/disk work and OS stalls are not
  hard-real-time bounded; low queue occupancy does not prove feed freshness or sustained capacity.
  Assembly/validation take time after acquisition and remain subject to campaign completion gates.

Timing schema stays unchanged. `processed_events` and `parse_write` now count successful parsing
and staging, not final assembly or fsync. Events processed while the snapshot is pending count
as snapshot-buffered queue waits, even though that timestamp is not known yet. Their queue-wait
measurement ends at staging and does not include subsequent residence on disk. Final replay
still excludes receipts at/before snapshot availability from feature warmup and CVD. Historical
timing values remain bound to their old source and must not be compared as identical workloads.

## Verification

Initial complete-suite baseline: **2,659 passed, one failed, one optional Nautilus skip**
(176.49 s). The failure was an existing burst fixture whose watchdog advanced the same synthetic
wall clock used for exact per-message timestamp assertions. That fixture now disables only its
synthetic watchdog; dedicated production-watchdog tests remain unchanged. The two added startup
regressions then failed as expected before implementation, both with queue overflow.

The new startup suite covers timed/untimed 257/1,024/4,096-message pending-snapshot bursts,
exact receipt/order preservation, real causal replay, snapshot failure/deadline, malformed and
stale input, byte/event quotas, cancellation, pre-snapshot CVD exclusion, existing staging
refusal, acquisition intake, shared disk accounting, bounded assembly and partial IO faults.
Existing collector, scheduling, timing, campaign and failure-code regressions remain in use.

Final verification: **2,682 Python tests passed, one optional Nautilus skip** (171.65 s),
**38 JavaScript tests passed**, and Ruff lint/format plus `git diff --check` passed. The new
startup suite contains 22 cases. The collector/timing/failure focused run passed 191 cases;
the expanded startup/campaign/intake run passed 198. All **45 startup/burst cases passed on
three consecutive runs** (14.76 s, 15.10 s, 16.56 s). Source fingerprint:
`cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b`.
Historical campaign -3 source remains
`e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5`.
Existing plans/settings were not re-pinned. The accumulated dirty working tree is preserved;
these changes remain local and uncommitted.

## Next gate

Consider one distinct, prospectively declared diagnostic capture under the new implementation,
with its purpose, duration, byte accounting, unchanged quality gates and no-retry outcome rule
declared before acquisition. It must not become a training fold selected after inspection.
This slice does not prepare or launch it. A successful diagnostic alone cannot establish stable
multi-window acquisition, class diversity, trading profitability or readiness for Qwen training.
