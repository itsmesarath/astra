# 6E causal event study: bursts, progress and held-liquidity proxies

## Completed result

The single registered run completed without a retry and was independently
verified. It examined all **2,136,770 accepted one-second decisions across
196 sessions**. Calibration used all 26,187 original early cases, including
4,741 unknown outcomes. No target was used to choose the thresholds:
activity `2.833213344056216`, absolute normalized CVD `2.3125`, held passive
`1.0436758893280675`. There were 28,040 positive held-side observations.

Every one of the twelve hypotheses had a negative mean closed net result in
each development role and each calendar-month aggregate, under the original
cost assumptions. The fixed no-trade control selected zero attempts.
This does not establish a profitable policy, teacher or model improvement.
It rejects these particular fixed short-horizon rules at these costs; it does
not prove that every possible order-flow strategy is unprofitable.

The 84 later sessions contain 894,261 decision rows:

| Event family | Detected episodes | Resolved outcomes | Unknown/ineligible |
| --- | ---: | ---: | ---: |
| Activity control | 15,666 | 9,557 | 6,109 |
| Burst | 5,106 | 4,114 | 992 |
| Sweep proxy | 3,887 | 3,139 | 748 |
| Absorption/reload proxy | 1,538 | 1,248 | 290 |

Families overlap, so these are not additive counts of unique events. Unknown
includes ineligible events: 4,779 activity, 392 burst, 312 sweep-proxy and 80
absorption/reload episodes. The remainder are entry timeouts or widened entry
spreads; none become zero-return or negative teacher labels.

The following are **separate simulated one-position hypotheses**, not the
overlapping all-event summaries. They include crossed quotes and one extra
tick. Mean ticks apply only to closed attempts; unknown attempts are reported
separately, so these are not complete account returns.

| Family | Closed follow/reverse attempts | Follow mean net ticks | Reverse mean net ticks | Same-event queue mean net ticks |
| --- | ---: | ---: | ---: | ---: |
| Activity control | 5,350 | -2.0862 | -2.1310 | -2.0089 |
| Burst | 2,571 | -2.1684 | -2.0556 | -2.0300 |
| Sweep proxy | 2,121 | -2.2159 | -2.0141 | -2.0201 |
| Absorption/reload proxy | 968 | -2.3151 | -1.8967 | -2.0897 |

Queue controls can abstain on ties: their closed counts are 5,309, 2,535, 2,092
and 948 respectively. Follow/reverse unknown attempted outcomes are 749, 353,
269 and 159 respectively. Higher-cost recosting only worsens these totals.

Resolved all-event winners exist, but in 2,994 of 4,114 resolved burst episodes,
2,269 of 3,139 sweep-proxy episodes and 892 of 1,248 absorption/reload episodes,
**neither direction** was positive after the original costs. Selecting only
the winners would manufacture a hindsight edge. Support is not broadly
positive: sweep reversal and absorption reversal each have just one later
session with positive closed tick totals, only one tick each. Unknown attempts
and sparse sessions prevent interpreting those isolated days as validation.

Independent verification rehashed 4,144,401,104 bytes of consumed row/case
shards, all 196 daily report pins and the frozen thresholds. It reconciled
role/month aggregates, event accounting, cost arithmetic and unchanged
execution-credit conservation metadata without opening raw or reserved data.

## Scope and decision

This is a new, separately registered offline experiment, not an alteration of
the completed [context experiment](EURUSD_CAUSAL_CONTEXT_20261002.md).
It investigates short-lived execution-flow hypotheses after two model
comparisons abstained at the original costs. It does not train Qwen, run the
paper trader, connect a broker, change the BTC collector or promote a policy.

The unchanged manifest contains 196 accepted decision sessions: 112 early
training, 43 development-validation and 41 development-test sessions.
All 2025 outcomes are already exposed development; the labels "validation"
and "test" do not imply independent holdouts here. All 230 reserved inventory
dates remain metadata-only. Scope is the original 12:00–16:00 UTC window,
not all hours of each raw archive member.

## Predeclared inputs and events

Thresholds use all original causal 60-second cases in early training sessions,
including cases whose future trade outcomes were unavailable. Only feature
projections reach calibration; eligibility, targets, paths and hindsight
labels are prohibited. The fixed 90th percentiles use NumPy's linear method:

- Log known-trade activity, across every early case.
- Absolute normalized five-second CVD, across every early case.
- Strictly positive held-top passive execution observations, pooling both
  sides. If none exist, this threshold is absent and absorption is disabled.

These are normalized overlapping five-second snapshots, not additive raw
volume totals or native hidden-order labels. Four independent event families
are frozen before the evaluation:

| Family | Conditions at the current causal decision |
| --- | --- |
| Activity control | Positive known-trade activity at/above its cutoff, nonzero CVD and unknown aggressor fraction at most 10% |
| Burst | Activity conditions plus absolute CVD at/above its early cutoff |
| Sweep proxy | Burst plus CVD-aligned prior mid-price progress of at least one tick and aligned OFI |
| Absorption/reload proxy | Burst plus absolute prior mid-price progress at most one tick, aggression-side held passive execution at/above its positive cutoff, and positive other-ID reload on that same side |

For positive CVD the aggression-side passive liquidity is the ask; for negative
CVD it is the bid. A sweep proxy does **not** establish that an aggressor swept
multiple book levels. Held execution and other-ID reload do **not** establish
an iceberg. Both require a subsequent raw-event audit before stronger claims.

One event is emitted when a family's condition turns on or its CVD sign
changes. Sustained conditions are not repeated each second. The four families
rearm independently, and can overlap. State is fresh for every source session
and dated contract. A decision gap strictly above five seconds or the current
causal prior-quote-gap feature strictly above five seconds resets conditions.
No future eligibility/outcome is read by the detector. An unavailable or
ineligible event is still counted, and is never a fabricated negative label.

## Fixed hypotheses and comparisons

Each family has three separate hypotheses on exactly its event timeline:
follow the current CVD sign, reverse it, or use the current queue-imbalance sign.
Zero queue imbalance abstains and ties are counted. Activity-only episodes
provide an activity control; queue direction provides a same-event snapshot
control. This is not statistical matching or identification of a causal effect.
Every rule is reported; no winner is selected or automatically deployed.

The direction adapter is Boolean, **not a forecast of one net tick** and not
an AI model. It allows these fixed hypotheses to use the existing simulator's
100 ms entry delay, 15-second hold, original quote/spread/availability gates,
one-position rule and cooldown. Every unknown attempt remains unknown.
Closed selections cross the original quotes and pay one extra tick; exactly
the same selections are recosted at two and four extra ticks. No costs,
holding periods, thresholds or policies are optimized after seeing outcomes.

All-event summaries include resolved losses, winners, neither-side-positive
cases, ineligible events, unavailable outcomes and queue ties. They can overlap
and are not portfolio returns. Separately, non-overlapping policy summaries
report attempted/closed counts, unknowns, inactivity exposure, costs and
session support. Quote-proxy tick totals are not measured cTrader EUR/USD fills,
account P&L or validated broker execution.

## Integrity and reproduction

The runner calibrates once on early cases, freezes threshold file/content
hashes, and evaluates every accepted decision session, including early sessions
for descriptive comparison. Later sessions never recalibrate. Runtime is
bounded to twenty minutes and 50,000 calibration cases. Complete source roles,
all consumed row/case hashes, metadata execution-credit conservation, frozen
registration/source and all daily report hashes are rechecked before completion.
Failure evidence is retained; partial success, retries and overwritten outputs
are prohibited. Reports/data remain local in ignored directories.

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.study_6e_triggers `
  --prepare --manifest data/processed/6e_training_manifest_20261002_1.json `
  --manifest-sha256 ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b `
  --registration logs/NEW_trigger_registration.json

.\.venv\Scripts\python.exe -m ai_trader.training.study_6e_triggers `
  --registration logs/NEW_trigger_registration.json `
  --registration-sha256 REGISTRATION_RAW_SHA256 `
  --output data/processed/NEW_trigger_study
```

This interface is not authorization for an outcome-driven rerun. A profitable
teacher, independent replication, raw-event confirmation, broker basis/costs
and paper deployment remain separate unresolved steps.

## Local evidence and validation

- Registration: `logs/6e_triggers_20261002_1_registration.json`; raw SHA256 `8153d8e28be7e6ab85023476e4e8f8587780b126611bbbf235626d7e4585c8d0`.
- Completion: `data/processed/6e_triggers_20261002_1/completion.json`; raw SHA256 `340b7364e78b11ea539a879374cd378226ffb60c235a1c091d1b68e172bf93d4`.
- Threshold file: `data/processed/6e_triggers_20261002_1/thresholds.json`; raw SHA256 `64e28e8c3a422e25b908722dcc90aa946fe3bbce12a58a8fa1dd6979d953ffb6`; canonical content SHA256 `a1dc60bbad1408470b051201168cd2a00d45381bdc6dee44751dab5dd0e12c26`.
- Original manifest: `data/processed/6e_training_manifest_20261002_1.json`; raw SHA256 `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b`.

The baseline complete suite passed 3,527 tests and one optional Nautilus skip.
This step adds 32 tests covering future-field/prefix independence, event
rearming/sign changes, gaps, exact boundaries, bid/ask direction, missing
support, unknown aggressors, session/contract/reserved isolation, allowlists,
train-only target-free calibration, loss/unknown retention, same-event
controls, complete pinned reports, input mutation, failed-subset refusal and
no model fitting. The final complete suite passed **3,559 tests and one optional
skip** in 221.40 seconds. Ruff lint and formatting checks passed. Package
source was stable throughout the full regression run and real experiment.

## Next research step

Keep these results and costs unchanged. A separately registered **raw-event
timing diagnostic** should test whether the coarse overlapping five-second
snapshots miss the sequence of aggressive fills, held liquidity, depleted
levels and subsequent reload, and whether adverse motion occurs before an
entry could arrive. Choose any bounded early-session cohort chronologically
without selecting winning days; retain failed and unknown cases. Establish
actual observable sweep/replenishment support before assigning stronger
labels or fitting another policy. Do not tune on later outcomes or open
reserved data to rescue these rules. Qwen teacher training and autonomous
strategy deployment remain gated on a cost-aware, independently replicated
teacher and eventual broker-specific execution validation.
