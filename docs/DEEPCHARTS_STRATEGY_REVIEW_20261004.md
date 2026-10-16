# DeepCharts course and 6E strategy review

## Decision

Use the course to design **location-aware, sequential order-flow hypotheses**, not to certify a profitable strategy or supply automatic trade labels. The main improvement to investigate is the sequence from a known price level, through an aggressive attack, to either rejection or acceptance. CVD, absorption and replenishment describe parts of that sequence; none is an entry by itself.

Keep the present adapters quarantined and trading disabled. This review changed no trading code, checkpoints, datasets, risk configuration or collectors. No backtest, Qwen training, Qwen evaluation or trade was started. Local speech recognition was used only to analyse the user-provided course.

## What was analysed

The supplied directory contains 39 MP4 files. All 38 decodable videos were transcribed locally: **10 hours 48 minutes 36 seconds** of container duration, with 38,915.010 seconds of decoded audio. The small difference is audio/container rounding, within the per-block decode tolerance. Source and transcript SHA256 checks passed for every completed video. There are 1,316 thirty-second transcript segments and 82 decoded-block journal events, with no generation token-limit flags.

The semantic review concentrated on the order-flow and strategy lessons, including DOM, footprints, CVD, profiles, VWAP, LAT, range trading, breakouts, absorption, exhaustion, icebergs and stop runs. Foundation lessons and the four long Fabio and Andrea sessions were reviewed through selected passages. I inspected 72 sampled lesson frames and eight webinar frames; one webinar frame shows a chart loading rather than a usable chart. This is **not** a claim that every second or chart frame of the course was watched.

Limitations:

- **Fabio2.mp4 is excluded.** FFmpeg reports a missing `moov` atom; its declared media extent exceeds the file length. Replace or redownload that one file for a complete course review. No source file was repaired, overwritten or deleted.
- Automatic transcripts are not word-perfect. Timestamps locate thirty-second passages, not exact spoken words. Language was recorded as unknown and confidence statistics were not produced.
- Text heuristics flagged **24 passages, totalling 12 minutes**, for repetitive or punctuation-only output. These are not used as strategy evidence. Unflagged text is not guaranteed accurate either.
- The course's examples and performance statements are not independently verified trades. Selected screenshots illustrate a hypothesis, not its frequency or profitability.
- No course media was uploaded. Transcripts, frames, ASR tooling and evidence remain in ignored local `logs/deepcharts_review_20261004_1`. This document paraphrases findings; it does not redistribute the course or a full transcript.

Reproducibility evidence is in `analysis_coverage.json`, `asr_quality_flags.json`, `course_topic_index.json`, `asr_request.json` and `asr_complete.json` in that log directory. Whisper small used official weight SHA256 `9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794`. Completion receipt SHA256 is `80190203ead6c92d7894f1fd1299866e30ebac6c73bacfee5dd1bcd217e68b80`. Artifact verification establishes complete audio processing, **not semantic transcription accuracy**.

## Most useful lessons

Times below are approximate local video positions. The right column is a proposed translation into measurable research rules, not an implemented or validated policy.

| Course source | Useful distinction | Translation for our research |
| --- | --- | --- |
| Lesson 18 Cumulative Volume Delta, about 03:30–09:27 | Price progress can weaken while aggression remains strong; alternatively, a new price extreme can attract less aggression. | Separate high-effort stalled progress from declining participation. Compare completed prior windows; CVD divergence alone does not determine direction. |
| Lesson 23 Absorption VS Exhaustion, about 00:30–03:08 | Absorption involves substantial execution with limited progress; exhaustion involves fading aggressive participation. | Give them different candidate states. A quiet or broken feed must never be labelled exhaustion. |
| Lesson 24 Auction Reversal, about 00:30–02:25 | Weak participation at an extreme followed by opposing aggression. | Require a minimum executed-volume sample and a subsequent causal confirmation. Do not copy its illustrative ratio thresholds. |
| Lessons 19 LAT and 20 Trading Ranges, especially 11:30–18:12 and 02:30–08:38 respectively | Failed attempts outside an established value region differ from an accepted move to a new region. | Establish the region before the attack; observe re-entry and a failed retest before considering a fade. |
| Lesson 21 Trading Breakouts, about 00:30–06:40 | Sustained initiative, a weaker counter-move, and renewed aggression are different from one isolated volume burst. | Track break, retest and resumption separately. Confirmation costs time and may consume the entire small-trade opportunity. |
| Lessons 15 DeepPrint and 22 Auction Footprints, especially 08:30–12:30 and 00:30–07:14 | Executed volume by price and diagonal trade imbalance are not the same as resting book size. | Build causal trade-at-price footprints. Keep queue imbalance, footprint imbalance and displayed reload as distinct fields. |
| Lesson 25 Big Orders And Icebergs, about 00:30–07:30 | A defended high-execution level can hold repeatedly or eventually fail. | Study level-hold and level-failure outcomes separately. Large executed volume is not proof of a hidden order or one institution. |
| Lesson 26 Stop Runs, about 01:30–07:55 | Fast aggressive sweeps and the subsequent response are observable; the original stop orders are not necessarily observable. | Call the event a sweep candidate. Distinguish sweep-and-reject from sweep-and-accept rather than automatically reversing it. |
| Lesson 16 Deep Profile and 16.1 VWAP | Traded-volume location can provide context for very short entries. | Use previous completed profiles or the developing prefix available at the decision time, never the day's final profile. |
| Lessons 27–31 on sessions, opening ranges and gaps | Behaviour depends on session and market context. | Treat these as secondary context. Do not import equity cash-session clocks, gap statistics or opening-range claims directly into 6E. |

Selected webinars reinforce waiting for a response rather than treating a big print as a trade: Fabio1 around 59:00–62:00 contrasts balance with a developing move outside it; Andrea1 around 22:00 and 48:00 discusses what happens after absorption; Andrea2 around 17:30–18:30 and 105:30–106:30 distinguishes responsiveness from a confirmed break. These passages do not establish an edge.

## Corrections before borrowing the logic

### Volume areas are not probability guarantees

A profile containing approximately 70% of traded volume is a volume-area construction. It is not automatically the mean plus or minus one standard deviation, and does not establish a 70% probability of future price staying inside it. A multimodal volume distribution need not be Gaussian. Likewise, below VWAP means below that calculated average, not necessarily economically cheap. Define the profile algorithm, tie handling, price bins, anchor and developing update rules explicitly.

### Icebergs require careful event evidence

CME explains that native iceberg refreshes retain an order ID, whereas synthetic refreshes can arrive with new IDs; public MBO IDs do not identify the participant. Our same-ID and other-ID fields should therefore remain **observable candidates**, not hidden-size or trader-identity labels. Generic depth replacement may also be new liquidity rather than an iceberg. [CME MBO FAQ](https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html)

### Course matching examples are not universal execution rules

Do not implement the lesson's generalised market-maker allocation percentages or assume that quoting both sides guarantees spread profits. CME assigns algorithms by product and describes specific allocation steps; queue priority and display-quantity refresh rules matter. Any future passive-fill simulator must use the applicable product and period rules, not a generic course illustration. [CME matching algorithm steps](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457218521/CME+Globex+Matching+Algorithm+Steps)

### Event completion and time matter

For Databento GLBX, `F_LAST` marks completion of the instrument's event. Trade summaries and fill records are different views, and a fill does not itself change the book. Preserve the existing separation: count trade volume once from `T`, use matched passive `F` records for attribution, and make decisions only from completed receive-time observations. Databento receipt time is not our future broker receipt time. [Databento GLBX documentation](https://databento.com/docs/venues-and-datasets/glbx-mdp3)

Also, a zero footprint cell is not proof that displayed liquidity was absent, a stop order fired, or a level must be revisited. A final wick, last auction or full candle is available only after its actual observation or close.

### Futures evidence is not CFD performance

FX execution is fragmented across venues and bilateral arrangements. Our 6E exchange book is not a consolidated EURUSD spot book. [BIS FX execution analysis](https://www.bis.org/publications/qr-202512/fx-trade-execution-landscape-through-prism-2025-bis-triennial-survey)

Project implication: eventual cTrader paper validation needs synchronised broker EURUSD quotes, measured spread and commission, futures/spot basis checks, feed age and actual decision-to-execution delay. A 6E quote-opportunity score alone cannot demonstrate EURUSD CFD profitability. No broker connection is needed or proposed for this review.

Do not adopt the course's quoted stop-run reversal rates, iceberg break rates, opening-range performance or gap-fill probabilities as training priors. Their population, execution assumptions and out-of-sample support were not established here. ES thresholds such as 1,000 contracts, or footprint ratios such as 10:1 and 300–400%, need instrument-specific calibration and minimum-volume guards.

## Review of our current strategy

The infrastructure is stronger than the demonstrated trading edge. We already have strict MBO reconstruction, receive-time gating, conservative execution-linked reload candidates, past-only context, session/contract resets and cost-aware targets. Preserve these safeguards.

The present Qwen context contract contains **43 current values and 36 past summary values**. Its five-, fifteen- and thirty-second histories are observation-weighted means of feature snapshots. In particular, averaging overlapping five-second CVD snapshots does not reconstruct raw fifteen- or thirty-second traded volume.

That compact contract does **not** give the model a price-by-price footprint, a previously established value boundary, a defended-level episode or an explicit attack/retest/resumption sequence. Asking it to reproduce these course setups from the present prompt would overstate what it can see. The underlying historical MBO events can support richer causal research; the condensed rows cannot recover discarded price-level detail.

Existing recorded results remain a warning:

- The [causal trigger study](EURUSD_CAUSAL_TRIGGER_STUDY_20261002.md) examined 2,136,770 accepted decisions across 196 sessions. All twelve frozen short-horizon hypotheses had negative mean closed net results in every development role and month under the original cost assumptions.
- In that study, later-session sweep reversal averaged about **−2.01 net ticks** and absorption/reload reversal about **−1.90 net ticks**, including crossed quotes and one extra tick. These are means of resolved simulated attempts, not complete account returns; unknown attempts remain separate.
- The [execution-linked study](EURUSD_EXECUTION_LINKED_RESEARCH_20261001.md) found that passive execution pressure largely duplicated contemporaneous CVD. Additional names for the same signal do not create independent confirmation.
- The [causal context study](EURUSD_CAUSAL_CONTEXT_20261002.md) did not establish positive-cost entries. The latest [balanced Qwen pilot](QWEN_6E_CONTEXT_BALANCED_TRIAL_20261004.json) completed 196 fit-only updates, but its report records zero evaluation forecasts. Successful training is not validation.

These are previously recorded research results inspected for this review, not newly recomputed experiments. The accepted decision coverage is **12:00–16:00 UTC across those 196 sessions**, not every hour of all historical archives. All 2025 outcomes are exposed development; 230 reserved inventory dates remain metadata-only.

The course suggests a meaningful next hypothesis—condition on location and subsequent response—but it does **not** overturn those negative results or prove that the new sequence will work.

## Proposed small-trade playbooks

Start with three families, mirrored for long and short. These are proposed event state machines; every transition must occur before entry. Reject malformed, stale or incomplete data at every stage.

| Family | Setup and causal confirmation | Invalidation and main risk |
| --- | --- | --- |
| Failed auction fade | A previously known range/value edge is attacked. Aggression stalls or fades. Price returns inside and a retest cannot sustain acceptance outside; opposing aggression then appears. | Sustained acceptance outside, renewed attack, missing confirmation or insufficient room after costs. A strong breakout must not be faded just because CVD is extreme. |
| Accepted breakout retest | Price leaves a known boundary with persistent execution and progress. The counter-move has weaker participation; price holds outside and original-side aggression resumes. | Return inside, strong counter-aggression, widening spread or delay consuming the remaining opportunity. Do not enter merely because a high-volume candle exists. |
| Defended level hold or failure | A price zone accumulates execution while resisting progress. Track a hold/rejection branch separately from a failure branch with continued progress and aggression through the zone. | Expired level, stale book, unexplained reload or repeated retries. Track the zone's history; do not repeatedly buy every apparent wall. |

The first family can include sweep rejection; the second or failure branch can include sweep acceptance. This avoids treating every visually labelled stop run as a compulsory reversal. CVD is supporting evidence for the state, not the state itself.

For the user's goal of many small trades, measure eligible episodes per hour **and net expectancy**. More entries in a negative-expectancy rule compound costs. Low-liquidity anomalies can be clearer visually while still being worse to execute. These are short-horizon scalping research ideas, not a claim that a local LLM can compete in exchange-latency HFT.

## Next implementation and validation plan

1. **Create a separate versioned causal feature builder.** Keep frozen studies and the current forecast contract unchanged. Add trade-at-price volumes, known/unknown aggressor coverage, diagonal footprint ratios with zero-denominator and minimum-volume handling, genuine non-double-counted flow windows, price progress per attacking volume, and executed-versus-unlinked depth changes.
2. **Add prior-known location and episode state.** Candidate fields include developing VWAP, completed prior profile boundaries where covered, fixed past-only range edges, distance in ticks, attack count, level age, rejection/acceptance, counter-move strength and resumption. Do not manufacture a full-session profile from four hours of coverage or carry book/CVD state across a roll, gap or reset. Prior completed-profile context, if added, needs its own dated provenance and permission boundary.
3. **Test causality before economics.** Use synthetic fixtures for trade/fill double-counting, event completion, unknown side, genuine executions versus cancellations, missing data, late arrivals, denominator zeros, bar availability, prefix invariance, session/contract boundaries and DST-aware session anchors. Future records must never alter earlier features or triggers.
4. **Register a bounded comparison.** Use at most the three families and their two directions initially; do not search a large conjunction/parameter grid. Derive any normalisation and thresholds from permitted early training prefixes only, then freeze them. Compare with no-trade and the existing simple CVD/queue controls. Keep the existing 100 ms delayed crossed-quote entry and 15-second hold for the first like-for-like comparison; separately predeclare cost/delay stress rather than changing exits after seeing winners.
5. **Account for every detected attempt.** One position per episode, capped retries, explicit cooldown and invalidation. Retain losses, no-opportunities, unknown outcomes, unavailable entries and invalid data separately. Report closed net expectancy, sample coverage, episodes per hour, adverse excursion and session/month stability. Do not optimise from hindsight winners or pretend quote touches guarantee passive fills. Later add independently calibrated paper fills before portfolio drawdown claims.
6. **Train only against a defensible task.** First evaluate the already trained balanced pilot for output validity and collapse; that is a separate authorised run, not part of this review. If a numerical playbook subsequently earns credible support, create reproducible causal examples with opportunity, no-opportunity and unknown states. Qwen can classify context or explain an abstention; deterministic data and risk engines should remain in the time-critical path.

Any new use of exposed 2025 data is development, not an independent holdout. Reserved data stays closed until a separate frozen protocol authorises it. Choosing only successful paper trades would bias the next training set. Course concepts can inform research notes, but the full commercial transcript should not be automatically redistributed or used as fine-tuning material without checking rights.

**Immediate next step:** implement and test the new causal location/sequence feature contract on permitted development inputs, then run one preregistered cost-aware playbook comparison. Do not start another large Qwen training run just because the course sounds convincing. No live account, credential, order or collector changes are part of this plan.
