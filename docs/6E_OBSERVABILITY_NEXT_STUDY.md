# 6E Next Observability Study Design

This is an unlaunched research design, not permission to fit another model, alter existing labels or enable trading. The October 4 whole-cohort experiment is complete and negative: all active rule closed-trade averages are negative, and the fixed CPU candidate abstains. Preserve that result and its original pins.

## Question and current evidence

The current exit definition requires a newly completed quote at or after the delayed liquidation request, within a one-second wait. Among unknown directional outcomes, 95.37 percent of bracket outcomes and 96.27 percent of time-exit outcomes lack the existing path-gap-over-five-seconds marker. A short quote-wait timeout is not automatically a long outage or corrupted session. Nor does an unchanged last known book prove an order would have filled.

The next useful question is therefore about observability and account treatment, before another optimizer or Qwen fine-tune: when an exit cannot be observed under this definition, what is known about the previously completed book, and what remains genuinely unverified?

The missingness proportions are descriptive after seeing the result. They do not establish a profitable correction, validate a standing-price execution model or justify searching for a better-looking target definition.

## Implemented synthetic foundation

`src/ai_trader/research/six_e_quote_reference.py` supplies a pure completed-quote reference selector. It requires an explicit last-published native cursor as well as a receive-time request boundary. It preserves equal-time order, excludes later events, validates the declared development session and contract before touching quotes, and returns the four fixed descriptive age bands. It performs no I/O, prediction, fitting or execution.

All source-lineage, local/broker-receipt, execution, training, promotion and trading authority fields remain false. An empty or unpublished prefix returns no price, not an invented fill. Old or widened states remain reference-only observations. Thirty-two synthetic tests passed, including future-prefix invariance, equal-time cursor boundaries, reserved-session refusal, nonfinite/incorrect types, crossed or off-tick quotes and resource bounds.

This helper has not been run against historical data and is not connected to the completed candidate or paper engine. The proposed full-cohort study below is still unlaunched. Its current per-call validation scans the supplied array; it is a correctness foundation, not a measured hot-path implementation. Any future bulk integration must validate pinned immutable inputs once, retain publication boundaries and budget memory and runtime explicitly. The CPU prediction benchmark does not measure this helper.

## Freeze the comparison before replay

A future implementation needs a new versioned registration with explicit authorization, source and input pins, exclusive output, all-cohort coverage and checked resource bounds. It must not edit or reuse the completed version one collection, model or forecasts.

Keep all 196 accepted exposed development sessions, all 2,136,770 original decision rows, original dated contracts and the 45 retained non-decision development dispositions. Reserved prices stay unopened. Keep the entry definition, both fixed exit plans, delays, extra-cost conventions and original outcomes as a reference. Do not discard a sparse contract, a losing day or an unresolved path.

The first comparison should produce descriptive observability records only. No new strategy, parameter search, fitting, winner selection or broker orders belong in this phase. Any later change in targets or training requires a separately approved protocol, not a silent continuation of this audit.

## Separate quote states from fills

For every original entered counterfactual and exit request, retain these separate observations:

| Observation | How to determine it | What it does not establish |
| --- | --- | --- |
| Original fresh exit | Preserve the current first allowed completed quote and its original status | An actual broker fill |
| Last completed state at the delayed request | Select only the last fully completed same-contract quote at or before that time, preserving native equal-time order | That its displayed liquidity remained available for our order |
| State age and intervening observations | Retain the age in nanoseconds, source quality and original path-inactivity marker | End to end feed latency or broker connectivity |
| Later completed observation | Record whether a later observation exists within the already declared bounds, without choosing a more favorable price | A fill at the earlier requested time |
| Unresolved account position | Retain the original entry and unresolved liability explicitly | Zero profit, overnight liquidation or permission to continue with a fresh account |

Use the already published completed-event state, never an intermediate MBO update. Retain its native event cursor as well as receive timestamp so equal-time events do not acquire information that had not yet been published at the chosen boundary. Vendor receipt time is not evidence of future local or broker receipt time. Distinguish target-symbol event inactivity from transport failure; a heartbeat or other-symbol message would be separate evidence, not something to invent from a quiet instrument.

Describe age support using all fixed reporting bands: at most 100 milliseconds, over 100 through 250, over 250 through 1,000, and over 1,000. These bands are reports, not candidate executable-age thresholds. Report every band and original role/contract group. Do not select whichever band produces the largest return.

Any price calculated from a standing state must be named a reference mark, not a closed return or execution label. Leave the original unavailable fill unavailable. Do not synthesize hidden size, exact stop fills, queue priority or broker EURUSD quotes from a futures BBO.

## Account boundary before economic scoring

The current daily schedules block after an unknown entered exit but reset on the next date. A continuous-account simulator cannot silently reset that unresolved position. Define the liability carry, deterministic failure policy, capital and risk accounting, and proof of closure before summing complete strategy returns.

A conservative operational option is to block any further account activity until closure or reconciliation is evidenced. A reference mark can assist diagnostics but cannot satisfy reconciliation by itself. This design does not change the existing paper engine or start a broker connection.

Keep unknown exposure visible at every account boundary. Do not impute a zero return, a maximum stop loss or a profit without an independently justified liquidation model. Commission, spread, slippage, latency and market impact assumptions must be identified explicitly before any new economic target is eligible for training.

## Required checks

- Causal prefix invariance: appending strictly later received events cannot change the state known at an earlier request; equal-time boundaries must respect the retained publication cursor.
- Native event ordering: preserve equal-time completed events and refuse intermediate updates, reversed clocks, cross-session or cross-contract quotes.
- Complete denominators: every original row and entered side is accounted for; no successful-subset output or favorable-date filtering.
- Reference parity: original version one entries, exits, unknowns and cost selections remain byte and metric comparable.
- Missingness integrity: marks do not turn unknown fills into zeros or resolved trades, and unknown liability survives the account boundary.
- Offline resource and failure behavior: source drift, oversized output, missing rows or deadline failure prevents a complete receipt; no retry or partial model fit.
- Authority separation: descriptors, reference marks and receipts cannot authorize Qwen training, model promotion or paper/live orders.

## Decision after the study

A successful descriptive study would clarify label censoring, not prove a trading edge. Only then decide whether a separately registered causal temporal model study is worthwhile. Train-only fitting and untouched prospective evidence remain necessary; exposed development roles cannot be renamed independent holdouts.

The prior course hypotheses concern location and a sequence of attack, response and retest. More expressive features might help, but confirmation takes time and must be charged to the opportunity window. No improvement is assumed in advance. Before EURUSD paper strategy activation, synchronized broker observations and realistic execution evidence remain a separate gate.

The BTC collector, cloud infrastructure, credentials and live-order connectivity are outside this design and remain unchanged.
