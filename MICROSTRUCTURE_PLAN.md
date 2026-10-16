# Order-book-first research roadmap

The overall workflow, trade journal, memory, local-model roles and delivery sequence are defined
in [AUTONOMOUS_SYSTEM_PLAN.md](AUTONOMOUS_SYSTEM_PLAN.md). This document remains the detailed
microstructure feature contract. Its research stages below fit inside that broader sequence.

Direction confirmed by the maintainer on 2026-09-21: the primary trading hypothesis must use
order-book state and aggressive trade flow, including CVD, liquidity, replenishment and absorption.
The candle trend-pullback implementation is a comparison baseline, not the primary strategy.
No economic edge has been established. Execution remains paper-only, with no credentials or
live-order adapter added by this work.

## Implemented foundation

Existing combined captures contain a depth snapshot, sequenced depth updates, aggregate trades,
and local receipt timestamps. Existing features include top-N depth, imbalance, spread, midpoint,
microprice and interval trade delta. The new `features.microstructure` engine adds:

- Session CVD in base and quote units, plus rolling buy/sell volume and base CVD. Positive delta
  means aggressive buying; `buyer_is_maker=True` contributes negative delta. Values cover only the
  observed capture, not all historical activity. New sessions reset all state.
- Liquidity within a configured basis-point band from each side's best quote, with separate
  coverage flags, plus separate top-N coverage flags. Changes outside the original snapshot
  boundary cannot expand known coverage. If the best quote leaves the known snapshot range,
  invalidate the session and obtain a fresh synchronized snapshot.
- Best-level order-flow imbalance: bid additions/improvements are positive, ask additions/
  improvements negative. Price-level removal contributes the old queue; quantity at an unchanged
  best price contributes its change. This is a displayed-queue measure, not signed trade volume.
- Exact-old-best-price aggressive volume, displayed quantity before/after, and the proxy
  `max(0, displayed_after - displayed_before + matched_execution_volume)` for net additions.
- Absorption candidates when aggressive execution at the old best quote reaches its previous
  displayed quantity, the best price remains unchanged, and at least 80% of displayed depth remains.
- Consecutive replenishment intervals at an unchanged best price with positive matched execution
  and positive net-addition proxy. Three consecutive qualifying intervals flag repeated
  replenishment; interruption or quote movement resets the count. Thresholds are research defaults.

These are **proxies, not confirmed iceberg orders**. Displayed L2 updates do not reveal order
identity, cancellations separately from executions, or hidden reserve quantity. Multiple unrelated
orders can replenish one level. A replenishment flag is not a buy/sell instruction.

## Causality and quality contract

Observations are emitted only after applied depth updates, in recorded receipt order. Rolling
windows use `(receipt_time - window, receipt_time]`; elapsed-window coverage is reported separately.
The first applied depth update establishes the attribution baseline, not the REST snapshot.

For evidence matching, only already-received trades with
`previous_depth_event_time < trade_time <= current_depth_event_time` are eligible. Trades with
later exchange timestamps wait in a bounded buffer; late/boundary trades are counted as unmatched
and never revise previous evidence. Session/rolling CVD still includes trades when they are received.
This is an explicit cross-stream matching heuristic, not matching-engine ordering proof.

Equal-time or >1-second depth intervals suppress OFI and replenishment/absorption evidence and
reset consecutive counters. Configurable limits are saved with each artifact. Sequence gaps,
duplicate trade IDs, malformed values, backward receipt times and buffer overflow invalidate the
engine. A caller must start a new session with a fresh synchronized snapshot; no silent recovery
or missing-trade imputation occurs. Stale depth updates produce no row or duplicate evidence.

`features.build_microstructure` validates an explicitly named capture and emits a separate
`receipt_causal_microstructure_v1` JSONL artifact. It records source/code hashes, Python version,
configuration, arithmetic and timing policies, per-row evidence and a completion footer. The
source is hashed before validation and after generation. Complete temporary files are published
without overwrite using a same-directory hard link; partial output is not published. Storage must
support hard links. Existing CSV/model schemas are unchanged; these fields are not yet model inputs.

## Next stages, in order

1. Validate capture completeness, latency and usable liquidity coverage on explicitly selected
   research sessions. Add monotonic local timing and reconnect/session boundaries to ingestion
   where needed; keep receipt and exchange clocks distinct. Alongside quality reporting, define
   immutable trade-case contracts so theses/rejections can be recorded before any new paper policy.
2. Define a small, predeclared event hypothesis using CVD + liquidity + absorption/replenishment.
   Preserve negative/no-trade examples; evaluate false positives, not just attractive chart moves.
3. Add L2/trade replay execution with latency, available liquidity and conservative queue/fill
   assumptions. Candle replay cannot validate execution of this microstructure strategy.
4. Freeze session-exclusive fit/tune/evaluate partitions and code/data provenance. Compare the
   rule with simple order-flow baselines and matched random events, including fees and uncertainty.
5. Train a small event-level baseline. Consider a LOB encoder and local Qwen3-4B adaptation only
   after the data/evaluation pipeline is validated. Keep deterministic risk outside the model.

Do not train continuously into the active paper policy. Capture continuously if explicitly started,
train versioned challengers in batches, and promote only through a separately validated evidence
gate. Stop-run and iceberg classifiers need observable definitions and uncertainty; hidden state
must not be treated as ground-truth labels inferred from price movements alone.

## Feed reference

The [official Binance Spot stream specification](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)
defines aggregate-trade maker flags, absolute depth quantities, update-ID synchronization and
snapshot depth limits. The detection formulas above are this project's research definitions;
they are not Binance-provided classifications or verified hidden-order identifiers.
