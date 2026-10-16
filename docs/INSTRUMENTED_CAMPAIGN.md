# Prospectively split captures with research-only timing

## Versioned acquisition contract

`planned_capture prepare --research-timing` creates a version-2 plan. Without the flag, the
version-1 plan and collector call remain unchanged. Existing historical plans/receipts are still
readable; their implementation pins are not rewritten or resumed after code changes.

The new plan freezes the same train -> validation -> reserved assignments, duration, gaps,
fixed recorder limits and current implementation/runtime, plus a fixed timing contract:

- Instrument train and validation only. Reserved collection uses the original untimed recorder;
  it gets no timing observer or sidecar. Acquisition still performs its usual integrity-only
  replay for every role. Raw reserved bytes are never research inputs.
- Each research capture gets a fresh `CaptureTiming` instance: the existing 50-ms QPC probe,
  fixed histograms and first-32-per-metric alert samples. Diagnostics do not change raw capture
  schema or replace receipt timestamps. See [measurement semantics](CAPTURE_TIMING.md).
- Publish `<capture>.timing.json` with a checksum envelope, capped at 256 KiB, before declaring
  the slot complete. Bind it to the original plan pin, exact session/role/filename and completed
  source hash. Receipt/audit pin its raw bytes, byte count and exact filename.
- Successful telemetry must account for all received/enqueued/written events, depth gaps,
  snapshot receipt and queue waiting, and contain an event-loop probe sample. Diagnostic alert
  thresholds themselves do not reject captures or alter label freshness gates.
- On capture/cancellation/integrity/counter failures, retain a failed timing report when disk
  publication permits, containing only the exception type. No packet-bearing error messages.
  Failure to publish diagnostics quarantines the entire campaign while retaining valid raw
  files. Disk failure can also prevent the failure report; no success is inferred from absence.
- One attempt per slot, no retry, replacement, resume or successful-subset selection. A partial
  timing publication also blocks completion. No new training/promotion/execution authority.

Research intake reads the four pinned campaign metadata files and the two (or more, if declared)
research timing sidecars, each within its byte cap. It checks the raw pin, envelope, source/plan
binding, counters and absence of partials. It never opens raw market data during preparation,
and refuses any reserved timing reference/file without opening it. Local pins establish
consistency, not authenticated custody or protection against a user rewriting all local evidence.

## Fixed longer-session experiment

One deliberately planned follow-up uses three **120-second** sessions, one per split, with
five-second pauses. That is 360 seconds of capture plus connection, integrity-check and shutdown
overhead. There is no ongoing service or automatic repetition. Instrumented versus uninstrumented
sessions are not a controlled latency comparison, and adjacent minutes lack regime diversity.

`configs/prospective_event_trial_120s_v1.json` differs from the previous label configuration only
in its trial identity and **5,000 frames per research source / 10,000 aggregate** budget. A test
enforces that comparison. Longer recordings can reduce boundary censoring, not repair stalls.
If the full source exceeds this processing budget, its fold must still be withheld; do not use
the successful prefix or expand the budget after seeing outcomes.

Unchanged assumptions: 500-ms quote freshness/continuity, 2-second event lag/trade age,
100-ms future skew, 10-second holding horizon, 1-second entry TTL, 20/40-bps stop/target,
10-bps taker fee plus 2-bps slippage per side, top-five-level/CVD/evidence features,
50 resolved labels and at least 50% resolved per research source, five-second embargo.
Fees are research assumptions, not a claim about an account's actual tier. No policy tuning.

After complete acquisition, prepare a new source-bound research trial, label only its two
research sources and run the unchanged fold verifier. No Qwen fitting or trading is part of
this acquisition milestone; Qwen's protected evaluation requirements remain separate. Preserve
the earlier failed-quality fold and all earlier reserved captures.

## Verification and measured outcome

Verified on 2026-09-25: **2,322 Python tests passed, one optional Nautilus skip** (98.04 seconds),
all **38 JavaScript tests passed**, and Ruff lint/format passed. Baseline before this change was
2,281 passed / one optional skip (100.30 seconds). The 41 new synthetic tests cover v1/v2
compatibility, immutable timing contracts, per-source counters, no reserved telemetry, metadata-only
research preparation, failure/cancellation retention, no retries, report publication faults,
re-pinned invalid reports, missing/oversized reports and unchanged longer-session quality settings.

One six-minute campaign was prepared before collection under
`data/raw/btcusdt_instrumented_20260925_1/`, with one 120-second session per split. Original plan
`logs/btcusdt_instrumented_plan_20260925_1.json`, prepared at `1790323998603343900` ns.
The source fingerprint is `78154d9de71b15671c6307bf2a1b300ee525c034891dab9eb9b36e76437760a1`.

| Pre-capture artifact | Raw SHA256 |
| --- | --- |
| Plan | `338ac61ea820f6e19003d4fa4d8dabacb64d584cb7001781e13328c6f67b7c49` |
| Longer-session settings | `48f9d29d84f62fc1927c1ad8b38d2276cc374e3bea0ea73d55021c07efbd8126` |
| Research intent | `9dc58b3b2c097ea9fec13d1be2e40ca1bba5337da860217029b80373cc38a316` |

The separate local `logs/btcusdt_instrumented_research_intent_20260925_1.json` fixes the settings
and allows at most one later bounded NumPy attempt through the existing source-quality/class
gates. It does not grant Qwen training or execution authority.

### Actual acquisition: stopped, not eligible for training

The training slot completed: 978 aggregate trades, 1,200 depth events, 1,556,048 bytes and
120.0065811 seconds between header/footer. Validation recorded 1,188 trades and 1,199 depth
events but stopped with `CaptureInterrupted` before writing a footer. Its last event receipt
was 119.9408186 seconds after its header. The 1,712,962-byte `.partial` remains quarantined;
it is not a completed capture, even though its JSON lines can be inspected diagnostically.
The reserved slot was **not started**. No complete `receipt.json` exists. No retries, replacements,
labels, fold creation, NumPy attempt, Qwen calls, training or orders followed this failure.

| Diagnostic | Train | Validation (incomplete) |
| --- | --- | --- |
| Received/enqueued/processed messages | 2,178 | 2,387 |
| Maximum depth receipt gap, QPC | 145.9673 ms | 139.9890 ms |
| Depth receipt gaps above 500 ms | 0 | 0 |
| Maximum event-loop probe lag | 26.9258 ms | 27.5383 ms |
| Maximum streaming queue wait | 2.7503 ms | 1.7011 ms |
| Maximum snapshot-buffered wait | 1,370.1865 ms | 3,398.1491 ms |
| Maximum parse/write duration | 0.9075 ms | 0.8416 ms |
| Queue high-water (capacity 256) | 50 | 43 |

Read-only inspection of the validation partial found no recorded event/aggregate-trade execution
age above two seconds. Event age was 806.9296–853.9245 ms; maximum trade execution age was
829.4511 ms. Snapshot request-to-availability was 3,545.1872 ms. These are recorded timestamp
differences, not verified one-way network latency. The partial's missing footer is correctly
rejected by `CaptureReplay`; no synthetic footer or repaired source was produced. These limited
checks do not certify sequence integrity, label quality or the unrecorded end of the session.

The campaign persisted only the sanitized exception type, so the real interruption's exact
branch/cause is **not established**. It must not be described as a proven stale-data failure.
Neither this run nor the earlier one-minute diagnostic reproduced the old >500-ms depth stalls.

| Retained artifact | Raw SHA256 |
| --- | --- |
| Train capture | `b230573987b285fbf0e3466ff5841abbbabd057f6a1a7e0f2da6053b51efca48` |
| Train timing | `c0aaaf9b16d8e16a784c4050954d28875e3293e7297258a22229b93ab97f097a` |
| Validation partial, diagnostic identity only | `c7572baafcd26b0f1d5d143ea0368321467f6f0137a16cf464a4b130758bff3f` |
| Failed validation timing | `f8c2596e43ba3579bc912dd157a64af99be762978a924a541ed8b2824c2313f1` |
| Failure receipt | `50a07de6708118c5965787aab187e9cf5e9e34f43bcbeb8bae2a996e3d9d0fb7` |
| Audit | `7efa519fb8d6cffc86d05f17387fec605afd983fd5ec5364a7550f5ff294fd05` |

### Separately reproduced timeout defect and correction

Inspection of the installed Python event loop confirmed that it can release scheduled callbacks
within one loop-clock resolution before their nominal deadline. A deterministic synthetic test
made the wait return early, before a queued message arrived within budget. The old recorder
raised `TimeoutError` immediately and canceled that pending get; the test failed before the fix.
This is a confirmed code defect, **not proof it caused this particular public interruption**.

The recorder now uses QPC-backed `perf_counter()` deadlines for session duration and pending
waits. After an early timer wake-up it retains the same queue-get/snapshot task and keeps watching
the receiver/observer until the actual budget expires. A resolution-sized minimum repeat wait
avoids a sub-tick busy loop. A private elapsed-budget exception distinguishes our timer expiry
from a `TimeoutError` raised by a dependency, which must still fail the session. Timer scheduling
can overshoot by a tick; OS/network/disk waits remain outside hard-real-time guarantees.

Nine additional synthetic regressions cover retained task identity, unchanged deadline budget,
no sub-tick busy loop, dependency timeouts, cancellation/cleanup and complete timed/untimed
captures with injected early wakeups. Existing idle/failure/quota tests still apply. Market
receipt timestamps, raw schema, freshness and label rules are unchanged.

The correction changes the current implementation to
`5515070a8e29487e6b9f990a03a58a9b8b8a4001d34339b47d55c24a45b66e52`.
The failed campaign retains its original `78154d...` implementation pin. It is not resumed or
rehabilitated under the new code. No public capture has tested the correction yet.

Final verification after that correction: **2,331 Python tests passed, one optional Nautilus
skip** (100.90 seconds), **38 JavaScript tests passed**, Ruff lint/format passed (254 files),
and `git diff --check` passed. The focused capture/timing/handoff suite passed all 247 tests.
Changes remain local and uncommitted; unrelated prior development changes were preserved.

Next: record sanitized failure-stage/reason codes, then make a separately pinned bounded
acquisition under the corrected implementation and unchanged quality rules. Only a complete
campaign may proceed to the original label-quality and training-class gates. Preserve this
failure and all historical reserved sources; do not select the successful training slot alone.

Follow-up: [sanitized failure evidence and a separately planned campaign](CAPTURE_FAILURE_EVIDENCE.md)
are now complete. The new campaign passes label quality but its baseline is blocked by a single
training class. This failed campaign's files and outcome remain unchanged.
