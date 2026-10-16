# User-requested earlier-start campaign

## Terminal result: failed before snapshot availability

The first train slot dispatched at **14:03:00 UTC / 15:03 Lisbon** and connected at
14:03:01.052 UTC. The runner recorded `receiver.queue_overflow` at **14:03:03.979 UTC**
(2.926 seconds after connection, measured by the monotonic diagnostic clock). The complete
four-row audit and failure receipt agree: first train failed; second train, validation and
reserved never started. There is no completion receipt or eligible fold. Both recorded process
IDs were absent on inspection at 14:07 UTC; a subsequent process inventory found no windowed
Python runner. The read-only follow-up was deleted after reporting the terminal failure.

Bounded, pinned metadata verification using the project virtual environment checked strict JSON,
schedule bindings, all four role/status assignments, matching failure evidence and the timing
report's canonical payload hash. The unchanged implementation pin also matched. It did not call
the completed-campaign loader because its completion precondition was not met.

Timing reports **257 received, 256 enqueued, zero processed, queue high-water 256/256**, and no
recorded snapshot-availability timestamp. Maximum sampled event-loop lag was 15.06 ms; maximum
message-receipt gap was 450.52 ms. This locates the overflow in startup buffering before the
snapshot was available to the collector; it does not establish why the snapshot was not yet
available or why messages arrived in that burst. It is not evidence of a streaming-writer stall,
nor does the preceding successful diagnostic prove sustained acquisition reliability.

Retained metadata raw SHA256 pins:

| File in the claimed directory | SHA256 |
| --- | --- |
| `failure.json` | `e994ca79a055bce0abf9bc3415a5fd1f450d2232f7f1e3dbc24a487f6c3a9846` |
| `audit.jsonl` | `e311dc68fed15a05845067af231070839c48fbffb25dea6352f1aaa083bb6ae3` |
| `btcusdt-windowed-20260925-3-01-train.jsonl.timing.json` | `02aef4f0a2e9978a880f09f2bf0fa8aee95ace2c94b067d0cd061c9017929901` |

Timing payload SHA256: `9a5d12a8fdcd7746707c189a08859212f3cd082359c74691754f43a4f7c1b18f`.
The original and copied schedule still match the schedule pin below. The 181-byte raw partial
was only inspected for filesystem metadata: never opened, hashed, repaired or processed. All
campaign files remain unchanged. No retry, replacement, successful subset, labels, fitting,
model calls or orders followed. This failed claim must never resume. Next is an offline startup
buffering diagnosis, not another capture or a retrospective queue/cap/quality relaxation.

## Why a new schedule

On 2026-09-25 the user requested an immediate start and confirmed the machine would remain
awake. Campaign -2 was still waiting for 14:15 UTC: it had only `schedule.json` and a 288-byte,
one-row `started` audit, with no session intent or market-data file. Verified exact process
creation times, executables, command lines, schedule pin and parent relationship before stopping
its sleeping Python child at 14:01:20 UTC. The launcher exited too. No files were removed.

The original schedule, claim and audit are retained unchanged. Audit raw SHA256 after stopping:
`2bc214664003d591c8b840171d9e7ea3edfe986d59229b74ea404cba818cc0b5`.
The separate operator note `logs/btcusdt_windowed_20260925_2_operator_cancellation.json` has
raw SHA256 `1476dac6c709efe3ab3eeff93bf7da937540986ef5c403eae75e907160d82864`. No runner
failure receipt was fabricated. Campaign -2 must not resume. This explicit user-directed change
before acquisition is not replacement of a failed/inspected source and does not authorize future
automatic window shifts, retries or replacements.

## Historical frozen schedule (not pending)

The first window was chosen by rounding the current UTC time plus 90 seconds up to the next
minute. This satisfies the unchanged minimum 60-second preparation lead time. Subsequent windows
remain exactly one hour apart, preserving roles and all resource, quality, cost and training gates.

| Role | UTC window, 2026-09-25 | Lisbon nominal start | Duration |
| --- | --- | --- | --- |
| Train 1 | 14:03:00–14:03:30 | 15:03 | 120 s |
| Train 2 | 15:03:00–15:03:30 | 16:03 | 120 s |
| Validation | 16:03:00–16:03:30 | 17:03 | 120 s |
| Reserved | 17:03:00–17:03:30 | 18:03 | 120 s |

- Original schedule: `logs/btcusdt_windowed_plan_20260925_3.json`.
- Raw schedule SHA256: `4232b60b17fbd0410107d2f525009bff6b8c2cf4c05620e7ffac04e9e332cd68`.
- New claimed directory: `data/raw/btcusdt_windowed_20260925_3/`.
- Last accepted footer: **17:05:45 UTC**; completion grace ends **17:06:15 UTC**.
- Source: `e49d701cd7f6ccc7cf02f0ad2bc0f4a4e24f0617925d93103cb4bf75680b65d5` (unchanged).
- Settings: `configs/windowed_event_trial_v1.json`, raw SHA256
  `9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a` (unchanged).
- Runtime unchanged: Python 3.12.10, NumPy 2.5.3, websockets 17.1.

Nominal capture: 480 seconds total; raw ceilings: 128 MiB / 399,988 events. Research remains
limited to 3,000 frames/source, 9,000 total and 600,000 declared row-epochs. The previously
disclosed busy-session processing-cap risk remains: complete acquisition does not guarantee a
complete eligible research fold. No retrospective cap increase, truncation, subset or relabeling.
Only train/validation receive timing sidecars; reserved remains acquisition-integrity-only.

## Historical launch and follow-up

Started the hidden runner at **14:02:04 UTC**, launcher PID **22796**, Python child PID **27840**.
Verified matching command lines/creation time and initial durable audit binding the original and
copied schedule hash. Initial state was waiting, not completion. No source/dependency/configuration
change was needed; the immediately preceding full verification remains 2,660 Python passes,
one optional Nautilus skip, 38 JavaScript passes and clean Ruff checks. Rechecked the unchanged
source pin and new schedule/destination before launch. Do not edit source while it is active.

The existing `check-bounded-binance-capture` follow-up was paused during the transition, then
updated and reactivated for **only campaign -3**, preserving its 15-minute cadence and quiet
normal-progress behavior. It must verify all-window metadata after matching processes exit using
`load_completed_schedule`; no raw/reserved reads or automatic research preparation/fitting.
Any failure, premature process disappearance or lack of verified completion after **17:08 UTC**
must be reported without restarting or killing anything; remove the follow-up after a terminal
report. Never extend this campaign to a later date or interpret always-awake availability as
permission for continuous recording.

OpenAI Docs guided the follow-up update using the
[official scheduled-task documentation](https://learn.chatgpt.com/docs/automations?surface=app).
Local follow-ups need the desktop app running. Collection stays public-data-only: no credentials,
model inference/training, order simulation or live orders. The failed campaign -1, canceled -2
and diagnostic sample are not inputs to this fold. Changes remain local/uncommitted.
