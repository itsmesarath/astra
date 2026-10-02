# 6E past-only context and replenishment support audit

## Completed result

The registered experiment completed without a retry. It constructed context
over all 2,136,770 accepted decision rows: 1,242,509 early training rows and
894,261 later evaluation rows. It used the unchanged 26,187 causal training
cases, with 21,446 resolved targets and 4,741 unavailable targets. Both trees
fitted exactly those 21,446 resolved cases. Each produced fifteen nodes and
eight supported leaves.

**Both context and snapshot-only trees selected zero trades**, matching the
no-trade control across every later development month. This is not a model
promotion, improved trading accuracy or a profitable teacher policy.

| Supported training leaf statistic | Context tree | Snapshot-only tree |
| --- | ---: | ---: |
| Best leaf mean long net ticks | -1.8949 | -1.8949 |
| Best leaf mean short net ticks | -1.5265 | -1.9516 |
| Later selected attempts | 0 | 0 |

These are training leaf means, not later realized returns or a threshold search.
Every leaf's two net-return forecasts remain below the fixed positive entry
threshold. Thus no evaluation row can get an actionable tree prediction,
regardless of its eligibility. This explains the abstention without blaming an
empty dataset or loosening costs. With no selected attempts, win rate and mean
return are undefined; recosting empty selections establishes no cost robustness.

Independent post-run verification reconciled all 84 daily report hashes,
role/month summaries, unchanged model and implementation pins, complete
training-session support in every node and the metadata conservation audit.
It rehashed all consumed row/case shards (4,144,401,104 bytes), without opening
raw archives or reserved outcomes. There were 1,947 causal training-context
resets and 3,191 evaluation-context resets; no cross-session history was used.

## Why this experiment

The [activity/direction comparison](EURUSD_ACTIVITY_DIRECTION_BASELINE_20261002.md)
completed four ridge fits but selected no trades across 894,261 later
development decisions. This step tests whether a fixed nonlinear model can use
causal changes and persistence that a current-snapshot linear model misses.
It does not lower costs, force entries, choose a new holding period or open
reserved outcomes.

The lineage manifest still assigns exactly 112 early training sessions, 43 later
development-validation sessions and 41 development-test sessions. All 2025 data
is already exposed development data. The new registration grants independent
named permission for this two-tree experiment; the original manifest's
named-baseline permission and the census's research-only reports are unchanged.
No Qwen fit, broker connection, paper/live order or BTC collector change is
authorized by this protocol.

## What the replenishment audit establishes

Databento distinguishes trade (`T`) summaries and fill (`F`) details from the
add/cancel/modify operations that update the displayed order book. For CME,
passive fill details follow their trade summary; an aggressing order already on
the book can also have a fill record. Implied trades may have no aggressor side.
Completed-book observations must follow the instrument's `F_LAST` event marker.
These distinctions support the existing conservative observer, not a claim of
verified hidden liquidity. See the [CME normalization specification](https://databento.com/docs/venues-and-datasets/glbx-mdp3)
and [order-action guide](https://databento.com/docs/examples/order-book/order-actions).

The new audit reads pinned metadata for all 196 accepted decision sessions,
including the April 4 correction. It does not reopen raw MBO members, change
source quality checks or reclassify previously unmatched records. Every daily
execution-credit conservation check must pass before any model fit.
The counters cover the original decision-window observer **including its
warmup**, not every event in a complete UTC raw member.

| Observed counter across 196 sessions | Quantity | Meaning |
| --- | ---: | --- |
| Matched passive execution | 11,266,582 | Execution volume linked under the frozen T/F/known-resting-ID rules |
| Bid other-ID reload | 716,259 | One-use depletion credit matched to another displayed order ID |
| Ask other-ID reload | 720,805 | Same conservative matching on the ask side |
| Bid same-ID reload | 48, across 22 sessions | Sparse matching by displayed ID, not proof of a native iceberg |
| Ask same-ID reload | 100, across 28 sessions | Sparse matching by displayed ID, not proof of a native iceberg |
| Same-ID net-refresh candidate | 0 | No supported same-event candidate under the frozen stricter identity rule |
| Matched fill quantity above prior displayed size | 0 | No observed excess under the matching rule; not proof that hidden orders were absent |

The conservation checks require reload credit not to exceed linked displayed
decreases, linked decreases not to exceed matched passive execution, and held
execution/net-refresh candidates not to exceed passive execution. Trade and
fill volume are separate views and are not added as independent traded volume.
Unlinked decreases are not asserted to be cancellations. Same-ID refresh and
reload would overlap if both occurred; they must not be summed as hidden volume.

Other-ID reload is present in every accepted session, but ordinary new orders
can produce it. Same-ID reload is genuinely sparse in these metadata counters,
although more sessions have a small event count than the 60-second case sample
suggested. No detector bug or confirmed iceberg teacher label follows from
this support audit alone.

## Causal context construction

`causal_6e_context.CausalContext` keeps three bounded rolling buffers. Each
contains only original observed feature vectors and receive timestamps, never
outcomes, targets, future paths, hindsight actions or eligibility fields.
It publishes a decision's features before appending that decision to history.
For each lookback, the past interval is `[now-lookback, now)`: the lower
boundary is inclusive and the current decision is excluded.

The 109 feature columns contain:

- The unchanged 37 current base/execution-proxy features.
- Four signed observable differences: passive pressure, held passive support,
  other-ID reload support and generic visible reload support.
- Current CVD × prior price-change and CVD × held-support interactions.
- For ten declared snapshot quantities, their past observation-weighted mean
  and current-minus-past-mean at 5, 15 and 30 seconds.
- Past sample counts and observed span fractions for each lookback.

The snapshot quantities include queue/depth imbalance, normalized OFI/CVD,
prior price change, quote activity and the four signed support differences.
Five-second rolling features overlap and their normalization can change with
displayed depth. **Their means/differences are not raw 15/30-second CVD or
cumulative execution volume.** No overlapping volume windows are summed.

Empty history uses a neutral zero mean with an explicit zero sample count and
span; no future interpolation or carry-forward occurs. State is fresh for
every UTC source session and dated contract. A decision gap greater than five
seconds, or the current causal prior-quote-gap feature greater than five
seconds, clears every context buffer. Decisions must retain their original
ordering and at least one-second spacing. Reserved dates are rejected before
feature access. The bound is 64 observations per window, with no dropping to
evade it.

Span is the age of the oldest included observation divided by the declared
lookback. Irregular original sampling normally gives a span below one even
after a long continuous history. The report's `incomplete_30s_span` is that
literal comparison, **not a count of failed warmup or missing raw data**. It is
never an outcome-availability filter or a changed entry gate.

## Fixed model comparison

Exactly two CPU quantile cost trees are fitted on the **same** resolved causal
60-second training cases. One sees all 109 context columns; the snapshot-only
control sees the original 37 columns. Full training decision rows supply past
context but do not supply additional densely overlapping training targets.
Each case must match the original causally thinned decision row exactly after
removing its future path payload.

The reused tested learner has maximum depth four, sixteen quantile bins,
minimum leaf size 500, at least three supported source sessions per leaf,
and at least fifty rows per supported session. Quantiles and splits see only
resolved early training inputs. No validation/test feature or outcome refits a
parameter. Unknown training targets remain unknown, not zero or no-trade labels.

All original one-second decisions from the later 84 sessions are evaluated,
including ineligible rows and unknown outcomes. Both models and the fixed
no-trade control use the unchanged threshold of 0.5 predicted net ticks,
100 ms entry delay, 15-second target, one-position/cooldown rule and original
quote availability/spread handling. Closed attempts are recosted at one, two
and four extra ticks without changing selections. Quote proxy totals are not
portfolio P&L or measured cTrader EUR/USD fills.

This experiment is bounded to 50,000 causal training cases and twenty minutes.
Every consumed row/case shard, metadata audit, model bundle, daily report,
implementation and registration is verified again before completion. Partial
jobs retain failure evidence and cannot publish successful-subset completion.
No tuning, retries, automatic winner selection or promotion is allowed.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_context `
  --prepare --manifest data/processed/6e_training_manifest_20261002_1.json `
  --manifest-sha256 ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b `
  --registration logs/NEW_context_registration.json

.\.venv\Scripts\python.exe -m ai_trader.training.train_6e_context `
  --registration logs/NEW_context_registration.json `
  --registration-sha256 REGISTRATION_RAW_SHA256 `
  --output data/processed/NEW_context_experiment
```

The examples show the interface, not authorization for an outcome-driven retry.
Outputs must be new and remain local under ignored `data/` and `logs/`. A
profitable teacher policy and autonomous paper deployment remain unproven.

## Local evidence pins

- Original lineage manifest: `data/processed/6e_training_manifest_20261002_1.json`; raw SHA256 `ba773292535c97402826e6b40b34d367379a2db899f0010d474628220f965c2b`.
- Context registration: `logs/6e_context_20261002_1_registration.json`; raw SHA256 `87e31fbb7cfdc694eb278ec91bbf760844507f0275f0a4d8c7c4d60e0727a36f`.
- Context completion: `data/processed/6e_context_20261002_1/completion.json`; raw SHA256 `6966daa8c69f0c713e825fce44047848976e9ed17a0ffb16d02803b9182e4cba`.
- Context model bundle: `data/processed/6e_context_20261002_1/models.json`; raw SHA256 `dbe7460edb056daffd6b27a937514f7659677cf5f1243d5f9b56834cd0e3aace`; canonical content SHA256 `b819b8d78948a2a80405bb17c5cfae934cd0c8e15757824af510d2edc9314789`.

The completion includes every daily report pin and the explicit source/runtime
protocol. Neither model file is approved for trading.

## Validation and next decision

The starting full suite passed 3,489 tests, one optional Nautilus skip. This
step adds 38 tests covering feature prefix invariance, future-field independence,
exact expiry, gap resets, missing history, observed-event sampling, bounds,
source-session/contract/reserved isolation, finite feature allowlists, identical
training cohorts, unknown targets, frozen fits, input/protocol drift, audit
conservation, complete evaluation and failed-subset refusal.
The final complete suite passed **3,527 tests, one optional skip**, in 215.06
seconds. Ruff lint and formatting checks passed. Source was stable throughout
the full regression run and actual registered experiment.

The next separately specified study should examine **causally triggered
execution bursts**, including observable sweep, absorption and replenishment
sequences, instead of changing these completed models' thresholds. Include
every triggered case, losses and unknown outcomes as well as hindsight
winners. Compare against matched activity/current-snapshot controls, retain
costs/latency and test whether pre-entry information distinguishes follow-through
from reversals. This is a hypothesis for a new experiment, not a conclusion
that such entries are profitable. The declared development roles stay fixed;
reserved data, Qwen teacher training and autonomous trading remain gated.
