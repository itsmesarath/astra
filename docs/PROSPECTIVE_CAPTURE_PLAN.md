# Prospective whole-session acquisition

`ai_trader.ingestion.planned_capture` fixes chronological **train, validation, reserved**
assignments before any capture is collected or inspected. It is a bounded public BTCUSDT
data acquisition tool, not a trading service or a model-training launcher.

## Contract

The optional [version-2 research timing extension](INSTRUMENTED_CAMPAIGN.md) freezes diagnostic
sidecars for train/validation before collection. Reserved sessions remain uninstrumented and
unavailable to research. Version-1 plans and receipts retain the original contract below.

- Offline preparation declares each unique source-session ID and exact filename, counts,
  duration, inter-session gap, recorder limits, package implementation and Python/dependency
  versions. The runner requires the original file's raw SHA256 and explicit capture opt-in.
- Every session belongs to exactly one split. All training sessions precede validation;
  all validation precedes reserved evaluation. No random row split, stitching or retroactive
  assignment of the earlier inspected readiness sample.
- Require 1+ sessions in each role, at most 8 in total, 30–300 seconds each and at most
  1,200 seconds of acquisition. The fixed gap is 0–60 seconds. Actual recorded duration must
  be within -1/+5 seconds of its declared budget, to allow limited scheduling variation.
- Use the existing recorder's fixed 32 MiB/session, 99,997-event/session, 256 KiB/message,
  256-message application queue and 5-second idle limits. Maximum raw campaign storage is
  256 MiB, plus small metadata; in-memory replay parsing/object overhead is additional.
  Connection, validation and cleanup time is extra. OS/DNS/disk stalls are not hard-real-time
  bounded; this is not a guarantee of exact wall-clock completion.
- Exclusively claim a new output directory and fsync a session intent before its network call.
  Verify unchanged code/runtime before and after each capture. Require receipt chronology,
  the declared gap, snapshot availability and the existing 2-second lag/100-ms skew checks.
- Each slot gets **one attempt only**. Any fault, cancellation, quota, code drift or publication
  failure stops the campaign. Preserve completed files and partials; later slots remain
  `not_started`. No retry, replacement, relabeling, successful-subset selection or resume.
  A later deliberately planned campaign is a separate experiment; keep the failed history.
- Publish small metadata artifacts via fsynced, exclusive partials and same-volume no-overwrite
  hard links. Unsupported filesystems fail closed. The audit's `receipt_prepared` record is
  publication intent, not proof that final receipt publication succeeded. A usable completion
  requires the matching complete `receipt.json`, no failure record and no leftover publication
  partial. Abrupt process death or disk failures can leave incomplete audit state: never infer
  success or automatically repeat the run from it.

## Reserved means unavailable to research

The acquisition process itself opens and validates every raw capture, including reserved data.
It temporarily reconstructs the book/features to enforce identical fixed integrity rules, then
exports only source hashes, IDs, times, counts and status. It does not print prices, order-book
levels, CVD, targets, features, decisions or performance. Do not open the reserved file in a
research/export/training process. Research/validation declarations map to `research`, and the
reserved declaration to `reserved`, for the existing typed registration interfaces.

This is a prospective local split, **not authenticated independent custody or an OS sandbox**.
Local users can access these files. Adjacent short sessions can remain highly correlated.
The complete campaign is not itself an event-label fold or Qwen held-out case suite. A later
registration must bind the original split, feature/label protocol, embargo and source hashes,
and fail as a whole when data is inadequate. Do not quietly train on reserved data or consume
validation to fit model weights. No acquisition artifact grants training, promotion or execution
authority; all three flags remain false.

## Explicit commands

Preparation creates only the plan file; both its parent directory and the output parent must
already exist. Choose new names for a new experiment. The commands below are examples, not an
automatic loop:

```powershell
.venv\Scripts\python.exe -m ai_trader.ingestion.planned_capture prepare --plan logs/new_capture_plan.json --output-dir data/raw/new_capture_campaign --campaign-id btcusdt-new-campaign --train 1 --validation 1 --reserved 1 --seconds-per-session 60 --pause-seconds 5
.venv\Scripts\python.exe -m ai_trader.ingestion.planned_capture run --plan logs/new_capture_plan.json --plan-sha256 <RAW_SHA256_FROM_PREPARATION> --enable-public-capture
```

Output contains `plan.json`, `audit.jsonl`, exactly the planned capture filenames on success,
and `receipt.json`. Failures normally produce `failure.json` instead; disk failure can prevent
even that write. Hashes of copied canonical plan bytes can differ from an externally formatted
original; both original and copy hashes are recorded separately.

The older `collect_campaign` API remains compatible but does not gain this contract. It must not
be treated as prospective protected acquisition merely because its files can be split later.

## Current status

Verification on 2026-09-24: **2,192 Python tests passed, one optional Nautilus skip**, plus all
**38 JavaScript workbench tests**, with Ruff lint and formatting passing. The new module has
68 synthetic tests, including contract/budget limits,
whole-session assignments, pin/code drift, byte publication, cancellation and failures without
replacement or successful-subset selection. A first full-suite run correctly rejected a source
edit made during a registration test; the clean rerun held implementation files fixed and passed.

The first real campaign **completed all three sessions**, with no retries, substitutions, source
changes or limit changes. No Qwen fitting, credentials, account connection or order capability
is part of this change. No source prices, feature rows, labels or performance were inspected by
the research process; only the acquisition integrity code consumed the raw captures.

- Original plan: `logs/btcusdt_prospective_plan_20260924_1.json`
- Raw SHA256: `697f53f53227097d1370d9fc2458769b04f245b1b5d7167fe7d73d2ebcacbc44`
- Frozen package implementation: `8ef2fa4acb3ea7666c00582de86fec9259e6e9e0d7498baef0abb60eea924afb`
- Plan preparation: `1790283239793163800` ns; one 60-second session per role, five-second gaps.
- Output: `data/raw/btcusdt_prospective_20260924_1/` (local/Git-ignored).

Source IDs and filenames share the prefix `btcusdt-prospective-20260924-1-`:

| Suffix / split | Recorded duration | Aggregate trades | Depth events | Bytes |
| --- | --- | --- | --- | --- |
| `01-train` | 60.017 s | 1,025 | 600 | 1,132,765 |
| `02-validation` | 60.009 s | 338 | 599 | 737,955 |
| `03-reserved` | 60.021 s | 381 | 599 | 728,500 |

The measured inter-session gaps were 9.587 and 9.402 seconds, both beyond the frozen five-second
minimum (connection/validation time is additional). Total: 2,599,220 raw bytes, 1,744 aggregate
trades and 1,798 depth events. These are transport counts, not independent training examples.
There are no retained partials or failure files in this completed campaign. The historical failed
capture remains in its original, separate location and has not been repaired or included.

| Artifact | Raw SHA256 |
| --- | --- |
| `01-train.jsonl` (with prefix above) | `6697cc2a8aef5f2986aba24632329fd90337dd5a4effb719781b964005fc0ccb` |
| `02-validation.jsonl` (with prefix above) | `57ba66294c8168ae82b7f1f0b9488f403b143ef9a8e58fc965d82740fd3ea890` |
| `03-reserved.jsonl` (with prefix above) | `d6b4bb2283b87a6dad73cc8b3ab47cd0a046de551bfcfbe1c72741c23b43edc4` |
| `receipt.json` | `c4c1a10b2fdcf504f27030ffb72e6ce36e39df8e53b62e1d16feecac5bbf3baf` |
| `audit.jsonl` | `2019d2a80a0107206237cf8e62826b7ada882ed9ba309d2580e0a0f3dd310972` |

The receipt hash matches the final audit publication intent. Its plan-copy hash matches the
original plan, and the package implementation remained unchanged after completion. The receipt
explicitly records zero model calls, optimization steps and orders; all authority flags stay false.
Three adjacent minutes do not establish regime diversity, independence, profitability or readiness
to fit Qwen. The reserved raw session is not automatically a reviewed protected Qwen case suite.

Subsequent milestone: the [first event-label trial](PROSPECTIVE_EVENT_TRIAL.md) froze its protocol
and numerical recipe, then inspected the declared research sources while preserving this split.
Its 50% resolved-fraction gate failed on training data (31.9%); the whole fold and fitting remained
blocked. The original reserved source remains outside research. Next instrument receipt timing
and plan longer captures without changing these outcomes or relaxing their rules. Qwen's separate
protected-case/custody gate remains unchanged.
