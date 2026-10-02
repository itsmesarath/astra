# Historical 6E census: refusal diagnosis and resource correction

## Result

All 17 refused development members were decoded to EOF in a separate, pinned,
metadata-only diagnostic. The original census and failure artifacts were not
modified. No reserved 2026 member was opened.

The April 4 quote-storage refusal was resolved by a new opt-in disk-backed
replay. Its control day reproduced the original rows and movement cases
byte-for-byte. No book, receive-clock, feature, target, cost or path rule changed.

Neither result authorizes model promotion or trading. Qwen training has not
started in this step.

## What caused the refusals?

| Dates | Verified observation | Disposition |
| --- | --- | --- |
| 2025-04-04 | Strict replay produced 2,047,103 completed quotes, exceeding the frozen 2,000,000 bound | Separate registered resource correction completed; original refusal retained |
| 2025-04-18 | 865 target records, all snapshot records at 00:00 UTC; zero target events in 12:00–16:00 UTC | Empty observed decision window, not a losing/no-trade training label |
| 2025-12-25 | 39,031 target records, at 00:00, 22:00 and 23:00 UTC; zero target events in 12:00–16:00 UTC | Empty observed decision window; do not call the whole UTC day empty |
| Fourteen Sundays | Each has one non-snapshot clear (`R`, side `N`) with flag 8 (`F_BAD_TS_RECV`) inside 12:00–16:00 UTC | Frozen quality refusal retained; no filtering, timestamp repair or broader exception |

The flagged Sundays are April 27, May 18, June 15, June 22, August 3,
November 2/9/16/23/30 and December 7/14/21/28, 2025. In every flagged sample,
the existing weekly-session helper returns no open trading session. Nevertheless,
the frozen closed-clear exception explicitly excludes the decision window and
therefore refuses the record. That explains the replay error; it does not establish
the upstream reason for the vendor flag or certify the remaining book.

The two empty windows are consistent with holiday closures, but no 2025
product-specific Globex holiday schedule was verified here. The
[official CME trading-hours page](https://www.cmegroup.com/trading-hours.html)
distinguishes products, platforms and trading phases; a different platform's
schedule or a clearing notice is not a substitute for the dated 6E schedule.
The machine reports retain `holiday_calendar_verified=False`.

The diagnostic counts `F_LAST` records, not reconstructed quotes. April 4's
2,047,103 count is called completed quotes only after the strict resource replay
reconstructed and validated the book. No quote count was inferred for the
other diagnostic members.

## Resource correction and exact control

`ai_trader.research.historical_6e_resource_replay` uses three append-only,
little-endian int64 columns (receive time, bid and ask). The timestamp column is
memory-mapped contiguously for the unchanged path analyzer's searches. Only a
bounded write chunk or requested path slice is materialized in memory; there is
no resident whole-day Nx3 quote array.

The declared bounds are 12 million quotes (288 MB on disk) per day, 65,536 quotes
per write chunk, one million quotes per path slice, ten minutes per complete
day and twenty minutes for the two-day job. These are resource ceilings, not
quote-sampling rules. Crossing a ceiling refuses the job; it never drops quotes.
Quote-column files are retained locally, including partial evidence on failure.

The new builder inherits the original event consumption and quality checks.
Only whole-day quote storage/finalization is replaced. It invokes the original
path analyzer, including first-event ordering at equal timestamps, exact-deadline
inclusion, exclusion of late recovery quotes from scheduled paths, inactivity
checks, unavailable exits and exact 15-second target regression checks.

| UTC source session | Completed quotes | Decision rows | Causal cases | Result |
| --- | ---: | ---: | ---: | --- |
| 2025-04-03, control | 1,285,469 | 12,730 | 233 | Exact original row and case SHA256 parity |
| 2025-04-04, resource correction | 2,047,103 | 13,450 | 232 | Full member hash verified; zero clock disagreements |

Both days finished under the registered bounds. Independent post-run checks
verified all report, row, case and quote-column hashes (129,020,000 data bytes),
case counts, causal spacing, source-session identity, current implementation
pins and the unchanged original census receipt. This is a resource correction,
not another independent test or a successful-subset strategy experiment.

## Coverage and next training step

Keeping the original census as the immutable source and adding this correction
as a separate evidence layer gives 196 development decision sessions, 2 empty
observed windows, 40 Sunday reconstruction-only dates (26 originally accepted,
14 still refused), 3 vendor-degraded dates and 230 reserved dates: all 471
inventory dates remain visible. The control is not double-counted.

The candidate decision corpus would contain 2,136,770 rows and 45,816 causal
movement cases across those 196 sessions. This is still only the 12:00–16:00 UTC
decision scope; decoding full UTC members is not all-hours decision research.

Next, publish an explicit training manifest that names the original census and
the April 4 correction, retains every excluded/refused date, separates whole
source sessions chronologically and accounts for unavailable labels as unknown.
Do not silently flip the original reports' `training_eligible=False` fields.
The first model comparison remains an activity filter plus direction/net-return
estimator, with no-trade, CVD and queue-imbalance controls. All inspected 2025
evidence is development data, not independent validation. Reserved 2026 data
stays closed until a candidate and evaluation protocol are frozen.

Update: the [whole-session manifest and four-model CPU experiment](EURUSD_ACTIVITY_DIRECTION_BASELINE_20261002.md)
are complete. All 84 later development sessions were evaluated; every model
abstained at the unchanged cost-aware threshold. This is not a profitable
teacher policy, and no model was promoted or reserved outcome opened.

## Pins and local artifacts

- Diagnostic registration: `logs/6e_refusal_diagnostic_20261002_1_registration.json`, SHA256 `6cc8a108f4f2b56242212d5a4943d922660346e9eb292cf0e51aff7b752c69bb`.
- Diagnostic directory: `data/processed/6e_refusal_diagnostic_20261002_1`; completion SHA256 `07ed88bfec5b3b8fcb3acaa22a270e78c5c4313ca8b673400a0271a7758a3f15`.
- Resource registration: `logs/6e_resource_replay_20261002_1_registration.json`, SHA256 `bb265a0cfe8e930a0f2f36ed5b44eccfd5cc4d7b9ef04f2f6fa9e420121110d7`.
- Resource directory: `data/processed/6e_resource_replay_20261002_1`; completion SHA256 `3fb0df6fcca5885226c2deb01ff063ff9a80479deb1a34c45fa104e178486545`.

The commands expose `--prepare`, `--registration`, `--registration-sha256` and
`--output`. Existing output directories cannot be reused. Preparation opens
bounded census metadata, not raw market records. Execution is local/offline and
has no model calls, credential access, downloads or order connectivity.

## Validation

The baseline passed 3,384 tests with one optional Nautilus skip. This step adds
60 tests covering metadata accounting, flags, EOF/hash failures, reserved-date
isolation, bounded storage, exact path parity (including ten randomized tapes),
unchanged quality refusals, control mismatch and incomplete-job handling.
The final complete suite passed **3,444 tests, one optional skip**, in 171.91
seconds. Repository Ruff checks and formatting checks also passed.
