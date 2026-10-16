# Prospective startup-staging diagnostic

## Declaration before acquisition (2026-09-25)

The user authorized starting the next diagnostic after the
[offline startup repair](CAPTURE_STARTUP_REPAIR.md). This is **one 120-second public BTCUSDT
capture**, one attempt, using the existing opt-in timing runner. It is not a training fold or
another multi-window campaign. No historical failed/canceled session is resumed or replaced.

Declaration: `logs/btcusdt_startup_diagnostic_20260925_1_plan.json`.
Raw declaration SHA256, recorded before launch:
`d6f9afe900ee37eda1fb7429a8ecbd3b47c237eccf386e770269c08726d70a98`.
Exclusive destination: `data/raw/btcusdt_startup_diagnostic_20260925_1/`.
Source: `cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b`.
Runtime: Python 3.12.10, NumPy 2.5.3, websockets 17.1. Previous full verification under this
unchanged source passed 2,682 Python tests, with one optional Nautilus skip, plus 38 JavaScript
tests. Three consecutive runs of the 45 startup/burst cases passed. Fresh Ruff lint/format and
source/runtime checks passed; destination was absent and 772,010,078,208 bytes were free.
No conflicting ingestion/training/model process was present at preflight.

The queue stays at 256, individual messages at 256 KiB, events at 99,997, idle timeout at five
seconds, and **staging plus final assembly share the existing 32-MiB ceiling**. Duration includes
snapshot and stream after connection. Connection, cleanup, assembly and validation add time;
OS/disk stalls cannot be hard-real-time bounded. No source/dependency edits during the run.

Frozen acceptance checks:

- Integrity-complete capture/report, no partials or residual staging, verified bounded hash,
  source/runtime/intent/authority bindings and original snapshot-first schema. Replay uses the
  existing 2-second freshness and 100-ms future-skew limits; no feature dataset is exported.
- Both streams present, matching receipt/enqueue/processed/footer totals, high-water 1–256,
  positive startup/streaming/watchdog/gap coverage and zero wall/depth-exchange regressions.
- Wall duration 119–125 seconds around the unchanged 120-second QPC acquisition deadline.
- Maximum wall/QPC receipt and depth gaps at most 500 ms. Streaming queue wait, parse/stage,
  event-loop lag and absolute wall/QPC gap difference at most 50 ms. Report startup queue wait
  separately; it ends at staging and excludes residence on disk, not at snapshot completion.
- Separately count receipts strictly before snapshot availability: more than 256 exercises
  the beyond-capacity startup condition. Otherwise that real-feed stress condition remains
  untested even if operational checks pass. Do not select another sample to change the result.

Stop after this single outcome. Failure/incomplete publication retains partial evidence without
opening/repairing it; only a completed new diagnostic may undergo bounded integrity replay.
No retries, replacement windows, labels, fitting, Qwen calls, credentials, simulated/live orders
or automatic multi-window campaign. One passing sample is not proof of sustained reliability,
causation, profitable trading, training eligibility or readiness for Qwen fine-tuning.

## Terminal result: snapshot timeout, not accepted

Launched once at **14:27:47.446 UTC / 15:27:47 Lisbon**, Python PID **23672**. The command
exited with code 1 at **14:28:00.494 UTC**, approximately 13.05 seconds after launch. Its
sanitized failure and checksum-enveloped report agree on `CaptureInterrupted` /
`snapshot.timeout`. The runner process was absent at the post-exit checks. The planned
120-second capture did not complete, and the frozen operational acceptance failed.

The timing report records **271 received, 271 enqueued and 271 parsed/staged**, with queue
high-water **2/256**. Snapshot availability remains null. This shows staging processed more
than the old queue capacity while the snapshot was pending, without queue overflow in this
attempt. It does not establish successful snapshot bridging, full-duration reliability or a
completed startup-stress assessment. No post-snapshot streaming samples exist. The reason the
snapshot request timed out is not established by this report.

| Observed pre-snapshot diagnostic | Result |
| --- | --- |
| Snapshot-buffered queue samples / maximum wait | 271 / 0.2927 ms |
| Parse/stage samples / maximum duration | 271 / 1.7870 ms |
| Watchdog samples / maximum lag | 181 / 28.1640 ms |
| All-message receipt gap, QPC / wall maximum | 115.9558 / 115.0876 ms |
| Depth receipt gap, QPC / wall maximum | 190.0458 / 188.8632 ms |
| Wall/depth-exchange regressions | 0 / 0 |
| Post-snapshot streaming queue samples | 0 |

All observed alert counters were zero, but missing snapshot/completion/streaming coverage means
this is **not** a passing diagnostic. The full receipt-causal validator and final raw/footer
accounting were not run after failure. Staged-event parsing alone does not establish freshness,
book reconstruction, usable features or training eligibility.

Post-exit verification read only bounded declaration, intent and timing metadata. Strict JSON,
raw hashes, report canonical digest, source/runtime/limits/role/authority and intent bindings
matched. Source stayed `cd760be6f423feddb22af9a29a17c7fa2fe192f5e526032c3928b011166d333b`.
The failed raw files were inspected only for filesystem metadata, never opened, hashed, repaired,
replayed or relabeled. Retained primary partial: **181 bytes**; stream partial: **223,847 bytes**.

| Metadata artifact | Raw SHA256 |
| --- | --- |
| Declaration in `logs/` | `d6f9afe900ee37eda1fb7429a8ecbd3b47c237eccf386e770269c08726d70a98` |
| `intent.json` (660 bytes) | `26ce3d6027deea540599da3b4554e0e6880f7ce9543d69df71b860e5f1538460` |
| `timing.json` (3,659 bytes) | `c0db253ca887eddf21ccca212d2932ffe3ed708bffd0a794137c0754c37c71d3` |

Timing payload SHA256: `05955c3c05ea68e4fb2894907be24f463323913a0a6e842c29565974401a9e2c`.
There is no final `capture.jsonl`. All acquired evidence remains unchanged. No retry, replacement,
label/feature export, fitting, Qwen call or order followed; no follow-up automation was needed.
Historical failed/canceled/reserved sources remain untouched. No source or dependencies changed,
so the previously recorded full regression remains applicable; only preflight Ruff/binding checks
were rerun in this launch-only slice. Work remains local and uncommitted.

Next investigate the snapshot-fetch timeout with offline code/tests first. Any further network
diagnostic needs a separate bounded declaration; do not extend the timeout, retry the failed
claim or start a new campaign automatically to obtain a passing outcome.
