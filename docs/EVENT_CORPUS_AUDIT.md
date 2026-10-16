# Historical event-corpus audit

## Purpose and boundary

`ai_trader.research.event_corpus_audit` describes explicitly pinned **training artifacts**,
without reading captures, validation labels or reserved data. It reports declared temporal
coverage, training outcome accounting/class diversity, overlap and frozen-cost arithmetic.
It does not train a model, select examples, relabel data, tune parameters or establish an edge.

The previous experiment is bound to its original whole-package implementation hash. New source
files change that hash. This audit deliberately distinguishes the historical implementation and
environment from its own: it checks supported historical schemas, bindings and internal arithmetic,
**not fresh source-replay reproduction**. The normal registration, replay and training loaders
are unchanged and still refuse stale code/environment. A report never authorizes fitting,
promotion or execution, even if its observed-blocker list is empty.

Only exact declared training sessions, all in order and without duplication, are accepted.
Role selection is checked before any dataset read. Inputs require externally supplied raw-file
SHA256 pins as well as canonical envelope checksums. A matching pin is not a signature, proof
of historical authenticity or proof that a supplied path contains the claimed source. Incorrect
dataset identities/bindings are rejected after the bounded read. There is no directory discovery,
raw-capture argument, validation-dataset argument or reserved-dataset argument.

Registration and split are each capped at 1 MB; datasets at 32 MiB each; combined inputs at 64 MiB.
The existing split limits cap research sources at 32 and total declared processing at 10,000
frames. Partial inputs, existing output/staging paths, unsupported schemas, mixed registrations,
modified protocols, duplicate rows, inconsistent count/feature types, time-boundary violations,
invented unresolved targets and incorrect cost arithmetic are refused. Output is an exclusive,
checksum-enveloped report. A changed audit source/environment withholds publication.

Quality is explicitly **from the artifact, not new replay**. For example, this audit checks
counts against rows but cannot independently prove the original full-source consumption flag,
quote prices, market-fault detection or feature calculations. Those remain the original replay
verifier's responsibility. Validation/reserved coverage uses declaration metadata only; this
audit does not recheck their quality, classes, predictions or returns.

## Measures and units

- Coverage: per-role session count, total declared duration, elapsed span, first/last timestamps
  and number of distinct UTC **start dates**. These are not regime classifications.
- Class accounting: resolved net-loss / exact-breakeven / net-profit counts, separately from
  censored, excluded and not-entered outcomes. Unknown outcomes are never neutral examples.
- Overlap: maximum count of disjoint closed feature-availability-to-outcome-availability
  intervals, found by earliest-finish scheduling. This diagnostic does **not** filter the training
  rows and is **not** an effective sample size or proof of independent market opportunities.
- Returns: minimum/maximum/arithmetic mean in basis points (1 bp = 0.01 percentage point),
  both net of costs and before fees while retaining slippage. A third measure algebraically
  removes the recorded slippage assumption to infer exit-bid/entry-ask returns before costs.
  These remain overlapping unit-long quote counterfactuals, not realized fills or portfolio PnL.
- Break-even: with per-side fee fraction `f` and per-side slippage fraction `s`, the required
  `exit_bid / entry_ask` ratio is `(1+s)*(1+f) / ((1-s)*(1-f))`. Subtract one and multiply
  by 10,000 for bps. Spread is already present in the ask-to-bid ratio; do not add it twice.
  Stop/target distances remain recorded unchanged and are anchored to the **earlier feature bid**,
  a different reference. Their nominal bps cannot simply be subtracted from this requirement.

All numerical summaries use the label builder's fixed 100-digit Decimal context, unaffected
by the caller's precision. No cost sweep, alternate label calculation, resampling or optimization
occurs. The displayed precision is reproducibility, not economic certainty.

## Completed offline audit, 2026-09-25

Read only the pinned registration, split and training labels from
`data/processed/btcusdt_instrumented_events_20260925_2/`: **2,958,205 bytes** total.
The original trial and its [capture/label evidence](CAPTURE_FAILURE_EVIDENCE.md) remain unchanged.
No raw captures, validation datasets or reserved datasets were opened. No baseline retry, GPU
call, Qwen fitting, network access, credentials or order occurred.

| Training-only descriptive measure | Observed result |
| --- | --- |
| Declared sessions / distinct UTC start dates | 1 / 1 |
| Declared duration | 119.994169 seconds |
| Resolved / eligible labels | 856 / 1,079 (79.3327%) |
| Net-loss / exact-breakeven / net-profit | 856 / 0 / 0 |
| Maximum disjoint labeled intervals | 9, not 856 independent samples |
| Exit reasons | 856 at the frozen 10-second horizon |
| Inferred pre-cost ask-to-bid return range | -0.03084 to +1.10076 bps |
| Required ask-to-bid return for break-even | +24.02883 bps |
| Net label return range | -24.00200 to -22.87311 bps |
| Mean net label return | -23.76226 bps |

Frozen assumptions: 10-bps taker fee per side, 2-bps slippage per side, 10-second hold,
20-bps stop and 40-bps target from feature bid. These are the experiment's assumptions,
not a claim about the user's actual exchange fee tier or obtainable execution.

The audit reports `insufficient_training_classes`; readiness remains
`not_established_by_descriptive_audit`, and all authority flags remain false. The small observed
training moves were below the frozen break-even requirement. This explains this sample's
single class; it does not establish that the hypothesis fails in every regime or justify making
fees artificially smaller, using validation outcomes, or collecting until positives appear.

Report: `logs/btcusdt_event_corpus_audit_20260925_1.json`.
Raw report SHA256: `b4edfd3157de34fbc331eba26d2a6e50048ef0f7f73af1f9617b7abb10d37b10`.
Canonical report digest: `7618f9eb3a837aecc384d934bda50904150050f97ac01b42f19501844f48b549`.
Historical implementation: `e07e992f614382bef00e4340739b471732bf1699b520ef72dbd6d2da21bf8022`.
Audit implementation: `df6df3386d071f56bf4f02505164545b04e07d70133f5835af120fa2c8e963fa`.
The audit introduces no general-purpose unguarded historical training loader.

### Reproduce the descriptive report

From the project directory, choose a **new** output path; the original report is write-once.
The following command reads the three pinned historical artifacts, not market captures:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.event_corpus_audit `
  --registration data/processed/btcusdt_instrumented_events_20260925_2/registration.json bb4c3032f4d211747df0d49e35690fd9b826f86ffd502710c8bbea896b38278e `
  --manifest data/processed/btcusdt_instrumented_events_20260925_2/split.json cf18ff9e8dd80d2ce6d6edf00475eb64f7770948414fc1c751502687b6ea4b79 `
  --training btcusdt-instrumented-20260925-2-01-train data/processed/btcusdt_instrumented_events_20260925_2/train_events.json b01f6bbb918cdad9ea72229adf4697009f7b9ae7005aff863bfda5d4360f46bf `
  --output logs/btcusdt_event_corpus_audit_recheck.json
```

Expected: a descriptive report with the same training summaries and separate current audit pin,
not training approval. Subsequent audit implementation changes require fresh verification and
may refuse unsupported historical contracts. Never rewrite historical registrations to match.

## Next development slice: predeclared, separated observation windows

The next deliverable should be a bounded multi-window acquisition contract and synthetic tests,
before further collection. It should:

1. Freeze UTC collection windows, source roles, session duration, pause/missed-window handling,
   total bytes/events/frames and a finite campaign end before observing new outcomes. Validate
   that the schedule, warmup/horizon and existing per-fold frame budgets fit together. Do not
   start an ongoing service or silently raise processing limits.
2. Spread scheduled windows across separate times/dates rather than treating adjacent minutes
   as regime coverage. Record causal activity/spread/liquidity descriptors without selecting or
   discarding sessions by their eventual PnL. Time separation alone does not prove independence.
3. Retain one attempt per slot, recorded failures and whole-session chronological assignments.
   No failed-slot replacement, successful-subset fold, reserved-source reuse or "until profitable"
   stopping rule. Define missed-window behavior before running, not after seeing labels.
4. Keep the current costs, labeling, quality checks and abstain-first execution boundary for the
   first coverage replication. If a different horizon/target hypothesis is proposed, register it
   separately **before fresh data**, retain the old result, and count it as another experiment.
5. Assess the complete fixed inventory once. Actual fitting still needs the existing source-
   reproduction, quality and training-class gates. Passing them is not promotion or evidence of
   profit; later chronological evaluation and realistic paper execution are separate milestones.

This is a development plan, not a scheduled acquisition or newly registered experiment.
Qwen remains installed but untrained. Its protected-case/custody and supervised adapter-training
gates are separate; reserved market capture metadata does not satisfy them.

## Verification

Baseline: 2,401 Python tests passed, one optional Nautilus skip (103.41 seconds).
Added 69 synthetic audit tests, including source-role refusal before dataset IO, explicit
read allowlists, no raw inputs, zero/one/two-class cases, frozen-cost arithmetic, overlap,
caller Decimal precision, inconsistent rehashed/repinned artifacts, bounded IO, no overwrite,
unchanged training code-drift guards and CLI output. Focused audit/fold/baseline suite:
184 passed (23.06 seconds).

The first full regression found an existing timing-test race: its real worker-thread snapshot
could finish after the fake stream's first event in one run but before it in the other, changing
the incrementing fake wall-clock assignments. The test now gates synthetic receipt until the
fake clock records snapshot availability, while retaining exact raw-byte equality assertions.
No recorder behavior or source fingerprint changed. Focused timing/audit suite: 106 passed
(12.08 seconds). The original failed test output and the descriptive audit are not relabeled
as successful training or a newly reproduced historical capture.

The synchronized byte-equality test passed five further runs. Final full regression:
**2,470 Python tests passed, one optional Nautilus skip** (112.96 seconds), **38 JavaScript
tests passed**, Ruff lint/format and `git diff --check` passed (only Git's existing CRLF
conversion advisories). The audit source fingerprint remained unchanged through final checks.
Changes remain local and uncommitted.
