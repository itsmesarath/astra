# Single-use UTC-window acquisition and research intake

## Implemented scope

`ai_trader.ingestion.windowed_capture` runs an explicitly opted-in public-market-data campaign
against a pinned V2 window schedule. `ai_trader.research.windowed_trial` verifies the completed
campaign's metadata and prepares research artifacts using only its embedded pre-capture settings.
No real windowed schedule, public connection, training, model call or order was started while
developing this slice. Tests use synthetic clocks/data; one crash test terminates a synthetic
child process. Existing real campaigns and reserved contents remain untouched.

Preparation defaults to the original metadata-only V1 contract. `capture_schedule prepare
--runnable` explicitly creates V2 (`prospective_capture_windows_v2`); it still starts no capture.
V1 cannot be executed or silently upgraded. The old back-to-back runner rejects both wrappers.
Never extract their embedded acquisition object to bypass the frozen windows.

All existing [window constraints](CAPTURE_WINDOWS.md), whole-session roles, quotas, costs,
quality thresholds, timing settings and no-replacement rules remain intact. Runtime availability
is not action authority: all authority flags remain false, and public collection requires a
separate `--enable-public-capture` flag. There are no credentials or order/account endpoints.

## Claims, clocks and durable evidence

The runner exclusively creates the new output directory before waiting. That directory is a
single-use claim, including after cancellation, machine sleep, process death or failed publication.
A concurrent or subsequent invocation refuses it without modifying its evidence. No resume,
automatic retry, slot replacement, successful-subset selection or outcome-based stopping exists.

The process retains one wall-clock and monotonic origin. Both clocks must reach a window opening;
either exceeding its inclusive last-dispatch deadline aborts the campaign. Wall/monotonic
regressions, invalid clock values and a stalled monotonic wait refuse. A wall-clock adjustment
cannot extend a deadline or force an early dispatch. Waiting polls at most once per second and
does not generate unbounded audit rows. This is a foreground process, not an installed scheduler,
daemon or wake-from-sleep service; the host must remain running through its predeclared windows.

For each slot the runner:

1. Checks current source/environment, then records, flushes and fsyncs intent before calling the collector.
2. Rechecks dispatch after that IO, before the actual collector call.
3. After connection, checks the start timestamp and both clocks against the fixed 10-second
   connection allowance. It records connection evidence, rechecks after hashing/fsync, then admits
   snapshot acquisition and stream processing. Rejected admission closes the connection first.
4. Verifies the published raw source's integrity, actual start/footer and frozen duration. Research
   timing sidecars bind the outer schedule hash; reserved sessions receive no sidecar.
5. Records completion only within the slot's latest footer plus 30 seconds for verification/cleanup.
   The grace is not additional recording time: the original footer bound is checked separately.

The watchdog uses cooperative asyncio cancellation and drains its child task. It cannot hard-kill
blocked OS/DNS/disk calls, a stalled event loop or uncooperative cleanup. The final slot's cleanup
can extend beyond the plan's seven-day latest-footer bound by the fixed 30-second grace; publication
is not a guaranteed hard wall-clock deadline. Machine suspension/missed windows fail on resumption,
not by moving the schedule. Do not edit source or dependencies while a campaign is running.

Successful output contains `schedule.json`, `audit.jsonl`, the assigned captures, research-only
timing sidecars and `receipt.json`. It deliberately contains no legacy `plan.json`. The exact audit
is one `started` event, three events per slot (`session_started`, `session_connected`,
`session_completed`), and `receipt_prepared`. Dispatch timestamps are distinct from durable intent.
Receipts bind source hashes, original roles, actual times and clock evidence for every frozen slot.

On failure, prior successes remain on disk but no successful-subset receipt is produced. Where IO
permits, `failure.json` and a terminal audit row retain fixed allowlisted stage/reason/type fields,
not exception messages, packet contents or tracebacks. Clock failures use the last valid sample.
Abrupt process death or disk failure may prevent a failure record: its absence never proves
completion. Even a fully written receipt is quarantined when publication subsequently failed.
Retain all claimed directories and partials; do not delete a claim to restart the experiment.

## Strict metadata-only research intake

The caller supplies raw-file SHA256 pins for the original schedule, final receipt and audit.
Intake checks the pinned schedule copy, exact audit sequence, every original slot/role, bounded
clock evidence, actual start/footer/gaps, quotas and matching research timing reports. It rejects
partials, a failure record, a legacy-plan alias, duplicate source hashes and reserved sidecars.
Rehashing inconsistent edited metadata is not sufficient to pass these semantic checks.

Intake opens no raw capture, label, validation dataset or reserved contents. Acquisition integrity
checks remain distinct from research access. It accepts structurally supported historical
acquisition bindings without rewriting them, then creates a fresh research registration bound to
the current research implementation/environment. Raw-source reproduction is still required before
labels or fitting; local pins are consistency evidence, not independently authenticated custody.

Only the exact settings bytes embedded before capture can produce the registration/split/recipe.
There is no external settings override. Research output requires a fresh directory and grants no
training, promotion or trading authority. The prior one-class numerical-training blocker and
Qwen's separate protected-case/custody requirements remain unresolved.

## Commands and operational boundary

These offline help/check commands do not collect data:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_schedule prepare --help
.venv\Scripts\python.exe -m ai_trader.ingestion.windowed_capture --help
.venv\Scripts\python.exe -m ai_trader.research.windowed_trial --help
.venv\Scripts\python.exe -m pytest -q tests/test_windowed_capture.py tests/test_windowed_trial.py
```

The following are templates only, **not executed campaigns**. First prepare a fresh V2 schedule
with fixed UTC times, a new output path and the verified source/environment. Launching the first
command connects to Binance public market data at those times and requires the host to stay awake:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.windowed_capture `
  --schedule "REPLACE_WITH_V2_SCHEDULE_PATH" --schedule-sha256 "REPLACE_WITH_RAW_SHA256" `
  --enable-public-capture

.venv\Scripts\python.exe -m ai_trader.research.windowed_trial `
  --schedule "REPLACE_WITH_V2_SCHEDULE_PATH" --schedule-sha256 "REPLACE_WITH_RAW_SHA256" `
  --receipt-sha256 "REPLACE_WITH_RECEIPT_SHA256" --audit-sha256 "REPLACE_WITH_AUDIT_SHA256" `
  --output-dir "REPLACE_WITH_NEW_RESEARCH_DIRECTORY"
```

The next operational milestone is one predeclared bounded campaign and intake verification,
not ongoing capture or automatic training. Choose times before observing outcomes. A failed slot
ends the entire campaign; a different experiment needs a new plan, not a repaired or reused claim.

## Verification

Baseline: 2,560 Python passes and one optional Nautilus skip. Added 67 dedicated runtime/intake
cases plus expanded failure-code checks. Focused new/related tests: **407 passed** (18.85 seconds).
An existing timing-sensitive collector assertion failed in the first full run; its synthetic
clock and snapshot-first delivery are now explicit. It passed five repetitions without changing
recorder rules. Final full suite: **2,637 passed, one optional Nautilus skip** (121.38 seconds).
All **38 JavaScript tests**, Ruff lint/format and diff checks passed. CLI help checks passed.
The source fingerprint remained stable through both full runs:
`c38b89a86e1be5b25f94d5e23fa66fd9cf04846d4b9d9f7315f5bbae6ced7d8a`.
Synthetic success does not establish multi-hour host reliability, market-data quality,
statistical independence, a profitable strategy or successful AI training.
