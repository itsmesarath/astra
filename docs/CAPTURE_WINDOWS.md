# Bounded UTC capture-window contract

## Implemented scope

`ai_trader.ingestion.capture_schedule` prepares and inspects a **metadata-only** acquisition
contract for separated observation windows. It reads one explicitly pinned research-settings
file and embeds its exact UTF-8 bytes and hash, original chronological session assignments,
UTC dispatch windows, finite resource bounds and failure policy in a write-once plan.

There is **no capture runner, sleeping process, background job, automatic retry, training or
execution in this module**. Preparation does not create the acquisition directory or read raw
captures, features, labels, validation or reserved data. No real campaign was prepared or run
during this development slice. CLI preparation/inspection were tested with synthetic fixtures.

The original wrapper has its own versioned kind, `prospective_capture_windows_v1`; the existing
back-to-back runner rejects it before creating an output directory or calling the collector.
Do not extract and run its embedded acquisition metadata: that would omit the frozen windows.
The subsequent [window-aware runtime](WINDOWED_CAPTURE_RUNTIME.md) requires an explicitly
prepared V2 plan (`prepare --runnable`). V1 stays metadata-only; there is no implicit migration.
Both versions retain the constraints below. Planning itself still never starts collection.

## Frozen constraints

| Contract | Bound or behavior |
| --- | --- |
| UTC input | Exact `YYYY-MM-DDTHH:MM:SSZ`, whole seconds; no local/DST/offset inference |
| First window | At least 60 seconds after plan preparation |
| Dispatch interval | Inclusive opening and last-dispatch times; width 0–60 seconds |
| Separation | Window openings at least one hour apart |
| Latest accepted capture footer | Last dispatch + 10-second connection allowance + nominal duration + 5 seconds |
| Inter-session boundary | Earlier latest footer + max(pause, embargo) strictly before next opening |
| Full deadline | At most seven days after preparation; never shifted automatically |
| Session counts and duration | Existing 1–6 per role, at most 8 total, 30–300 seconds each, 1,200 nominal seconds total |
| Research frames | Existing 10,000 aggregate cap across train and validation |
| Training compute | Existing 2,000,000 training-row × epoch cap; declaration only, no fitting |
| Raw capture bounds | Existing 32 MiB and 99,997 stream events per session |
| Metadata | Each settings file and published schedule at most 64 KiB |
| Failure policy | One attempt per slot; missed window, collection failure or clock regression aborts campaign |
| No substitution | No replacement, successful-subset processing, shifted windows or outcome-based stopping |
| Interrupted process | Retain claimed directory/partials; no automatic resume |

All sessions remain exclusively train, validation or reserved, in that order. Only research
sessions inherit the existing timing sidecar contract; reserved data remains acquisition-
integrity-only. The window contract is stricter about separation than the old back-to-back plan.
It does not alter that old plan's schema, runner or historical artifacts.

One-hour spacing is an engineering guard against adjacent-minute sampling, **not** a statistical
independence claim. Different UTC dates are reported, not required, and do not prove regime
coverage either. A real campaign should select times/dates before outcomes, retain all failures,
and never keep collecting until profitable labels appear.

Connection and snapshot allowances are planning assumptions. OS/DNS/disk stalls and cleanup
are not guaranteed to finish within them. The separate V2 runner rejects out-of-window evidence
and records failure; its 30-second completion/cleanup grace is not extra recording time.
These metadata limits are not a hard process-kill guarantee.
Nominal recording seconds exclude waiting, connection, processing and cleanup. Raw-byte/event
limits and research-frame limits are distinct; satisfying one does not establish the other.

## Research settings and temporal feasibility

The preflight reuses typed policy, replay, gateway and baseline configuration validators.
Unknown fields, credentials, nonfinite numbers, invalid quality thresholds and a non-abstain
research rule are refused. The original settings bytes are embedded rather than re-read later;
subsequent edits to the source file do not silently retune a frozen plan. A local hash establishes
consistency with supplied bytes, not independent custody or authenticity.

Declared session duration must be strictly greater than:

`10-second snapshot planning allowance + feature warmup + entry TTL + label horizon`.

For the current recipe that is 31 seconds, so the proposed 120-second sessions pass. This is a
necessary planning check, **not** a guarantee of healthy quotes, enough trades, sufficient
resolved labels or class diversity. Actual full-source reproduction and unchanged quality
gates remain mandatory. No synthetic source hashes or registrations are invented for preflight.

The candidate `configs/windowed_event_trial_v1.json` differs from the previous 120-second recipe
only in its new trial ID and a **3,000-frame/source processing cap**. Tests lock every other
setting unchanged: 10-bps per-side fees, 2-bps slippage, 10-second hold, 20/40-bps stop/target,
warmup, freshness, 50% resolved quality gate, minimum count and optimizer settings.

For a prospective two-train / one-validation / one-reserved plan:

- Three research sessions × 3,000 frames = 9,000 maximum research frames.
- Two train sessions × 3,000 frames × 100 epochs = 600,000 declared row-epochs.
- Four raw sessions = at most 128 MiB and 399,988 stream events.
- Four nominal 120-second sessions = 480 recording seconds, plus separated waiting windows.

The old 5,000-frame/source recipe correctly refuses this larger research inventory because
three research sessions would total 15,000 frames. The new cap is a quota, **not a forecast**:
busy sessions may exceed it and cause full-session quality refusal. Do not truncate and call
that complete, silently raise the cap afterward, drop a source or replace a failed slot.

Candidate settings raw SHA256:
`9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a`.
This file is a candidate recipe, not training authorization or a registered actual experiment.

## API and commands

`prepare_schedule` returns validated metadata without creating directories. `write_new` makes
an exclusive durable plan file, retaining owned partials on publication failure. `load_schedule`
requires an explicit raw-file pin and current implementation/environment equality. Unknown,
partial, oversized or altered artifacts refuse. Structural `validate_schedule` can inspect
historical contracts without claiming current operational eligibility.

`inspect_unstarted_schedule` distinguishes waiting, the first open dispatch window and an
expired unstarted campaign. Both window endpoints are inclusive; one nanosecond after the last
dispatch is expired. It rejects a clock before preparation and never shifts dates. It has no
record of real progress and must not be treated as an assessment of a running/completed job.

`validate_completion_times` is a pure helper used by the V2 runner and intake: it requires every slot in
original order, checks dispatch/start/footer timing and strict gaps, and rejects duplicate,
reordered, late, too-short, overrun or partial inventories. Its inputs are caller claims, not
authenticated acquisition evidence. Success returns no registration, model or permission.

Run the available offline checks from the project directory:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_schedule --help
.venv\Scripts\python.exe -m pytest -q tests/test_capture_schedule.py
```

An illustrative metadata preparation command follows. It was **not run** on real project data.
Choose fresh future UTC times and a new plan path against the verified, frozen implementation;
source changes invalidate operational use of older plans. This command creates a plan file,
not an OS/app scheduled task or a capture:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.capture_schedule prepare `
  --campaign-id btcusdt-windowed-example `
  --output-dir data/raw/btcusdt_windowed_example `
  --settings configs/windowed_event_trial_v1.json `
  --settings-sha256 9fb76e9fd3f6b1467a76dd666ba3b813c82f2e6d2d682d0d52f2d604fa79b05a `
  --train 2 --validation 1 --reserved 1 --seconds-per-session 120 `
  --window 2026-09-26T08:00:00Z 2026-09-26T08:00:30Z `
  --window 2026-09-26T16:00:00Z 2026-09-26T16:00:30Z `
  --window 2026-09-27T08:00:00Z 2026-09-27T08:00:30Z `
  --window 2026-09-27T16:00:00Z 2026-09-27T16:00:30Z `
  --plan logs/btcusdt_windowed_example.json
```

Expected output includes the new raw-file `plan_sha256` and `runtime_available=false`.
Adding `--runnable` explicitly selects V2 and reports `runtime_available=true`, still without
collection. The separate runner requires its own explicit public-capture opt-in.
`inspect --plan PATH --plan-sha256 HASH --at-utc YYYY-MM-DDTHH:MM:SSZ` prints a read-only,
caller-time assessment. There is deliberately no `run` command or public-capture opt-in here.

## Original V1 verification and subsequent work

Baseline: 2,470 Python tests passed, one optional Nautilus skip (112.97 seconds).
Added 90 synthetic regressions covering strict UTC/integer boundaries, quotas, warmup/horizon
feasibility, exact settings preservation, source/runtime drift, metadata-only IO, inclusive
deadlines, all-slot completion checks, tampering, exclusive publication, CLI and old-runner
refusal. Focused scheduling/acquisition/intake checks: 251 passed (5.80 seconds).

Final full regression: **2,560 Python tests passed, one optional Nautilus skip** (113.70 seconds),
**38 JavaScript tests passed**, Ruff lint/format and `git diff --check` passed (existing Git
CRLF conversion advisories only). Source remained unchanged during the full suite; fingerprint
`d85f04c2da3fe450cb64415fe18182dd9b094159613ec8616c26dd93f8817049`.

The subsequent [V2 runtime/intake slice](WINDOWED_CAPTURE_RUNTIME.md) implements durable
single-use claims, monotonic/wall-clock checks, missed-window failure evidence, post-connection
admission and frozen-settings metadata intake. It has been tested with injected clocks and
collectors, including actual subprocess death, but not a real multi-window public campaign.
Freeze new real windows only against the fully verified implementation.

No network, credentials, actual capture, raw-data audit, Qwen run, training or trading occurred.
Qwen's protected-case/custody requirements and the existing one-class training blocker are unchanged.
Changes remain local and uncommitted.
