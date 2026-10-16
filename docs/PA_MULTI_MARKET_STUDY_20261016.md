# Intraday price action across 8 CFD instruments, 2021 – Jun 2026 — 16 Oct 2026

Purpose: the owner wants an intraday bot (5–10 trades/day) trading breakouts, reversals,
trends and patterns, executing on IC Markets (cTrader) with Level 2 from NinjaTrader. The 6E
study (`docs/6E_SESSION_PRICE_ACTION_STUDY_20261016.md`) covered one market and 15 months.
This one asks whether the same price patterns carry an edge across many markets and years,
with IC Markets costs, so the trade count could come from breadth.

Data: free 1-minute bid candles, histdata.com (EST-fixed timestamps converted to UTC) with a
few hundred Dukascopy days, 2021-01-01 – 2026-06-30, lockbox Jul–Sep 2026 untouched.
EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD, US100 (Nasdaq), DE40 (DAX), US500 (S&P), ≈1,550–1,770
days each. Scripts: `scripts/data/fetch_histdata_minutes.py`, `fetch_dukascopy_minutes.py`.
Engine: `src/ai_trader/research/pa_multi_market_study.py` (reuses `six_e_session_pa_study`).
Results: `data/processed/pa_multi_market_study_1.json`, `logs/pa_multi_1/`.

Grid (192 per instrument): pattern {breakout 120-min, pullback continuation, failed-breakout
reversal, random} × 4-hour-trend filter {on, off} × window {London+overlap, 06–17 UTC, US cash
13:30–20:00} × stop {1.0, 1.5 ATR} × target {1, 2, 3, 4 × stop}; 240-min hold, flat 20:59 UTC;
market entries (no book in this history) with the IC Markets Raw Spread cost model in
`COSTS` (EURUSD 0.9 pip, GBPUSD/USDJPY/AUDUSD 1.2 pip, gold $0.25, US100/DE40 1.3 pt,
US500 0.5 pt — approximations, to be verified on the live account). Metric: mean net per
trade in multiples of that cost, so instruments are comparable (0 = break-even).

## Results (1,536 rows with ≥ 30 trades)

Marginals, mean net in cost multiples:

| Dimension | Values |
|---|---|
| pattern | breakout −1.13, reversal −0.86, pullback −0.83, random −0.76 |
| trend filter | off −1.01, **on −0.77** |
| window | day −0.92, sessions −0.91, US cash −0.86 |
| stop | 1.0 ATR −0.96, 1.5 ATR −0.83 |
| target | 1× −1.05, 2× −0.93, 3× −0.83, 4× −0.77 |
| instrument | AUDUSD −1.15, GBPUSD −1.08, EURUSD −1.06, USDJPY −0.96, US500 −0.83, DE40 −0.80, XAUUSD −0.68, US100 −0.59 |

Reading: −1.0 means the trades were a coin flip gross and lost exactly the cost. FX pairs sit
at −1.0 to −1.15: no information in the patterns at all. Breakouts are the worst pattern on
every instrument. The 4-hour trend filter, wider stops and larger targets each reduce the loss
a little and consistently, which is why they keep appearing, but none crosses zero.

Cross-market consistency (configs ranked by instruments with positive mean): the best is
reversal + trend + US cash + 1.5 ATR + 2× target, positive on 4/8 (XAUUSD +2.5, US500 +0.6,
DE40 +0.4, US100 +0.4; all four FX pairs −0.7 to −1.1). Random entries with the same filters
are positive on the same four instruments. By year and side for that configuration:

| | n | mean | long | short | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| XAUUSD reversal | 486 | +3.0 | +1.3 | +4.7 | +4.0 | +0.4 | −1.2 | −3.8 | +1.5 | +41.9 |
| XAUUSD random | 1707 | +2.4 | +2.4 | +2.5 | +0.5 | −0.0 | −0.6 | −0.5 | +1.4 | +28.7 |
| US100 reversal | 783 | +1.1 | +1.1 | +1.2 | −4.1 | −7.9 | −1.0 | +0.5 | +10.2 | +15.6 |
| US100 random | 1936 | +0.7 | +0.5 | +0.9 | +1.2 | +0.7 | +1.8 | −0.1 | +1.3 | −1.9 |
| EURUSD reversal | 339 | −0.5 | −1.0 | −0.0 | +0.1 | −0.4 | +2.9 | −1.5 | −3.4 | +0.2 |

The gold and index positives come from 2025–2026 volatility (gold at ~$4,000 with $100 median
daily ranges in H1 2026; a fixed $0.25 cost makes any move look huge) and are matched by
random entries with the same trend filter. They are regime, not pattern. 2023–2024 were
negative for the same rules.

## Conclusions

1. Intraday price patterns alone (no book) have no reliable edge on any of the 8 instruments
   over 5.5 years. Breadth does not rescue them: adding markets adds coin flips.
2. The things that help are filters that trade *with* the 4-hour move, hold longer, and aim
   for larger targets — they cut the loss from −1.1 to −0.6 cost multiples. That is real
   information but not enough to pay the spread.
3. Trade count: 5–10 trades a day of coin flips at IC Markets costs is a steady −0.8 to −1.0
   cost per trade ≈ −$5 to −$9 per standard lot per trade on EURUSD; at 0.01 lot that is cents,
   which is why a micro-lot live phase is a cheap way to learn, but not a way to earn.
4. The one candidate still standing is from the 6E study: reversal with the trend when the
   CME order book is thick (London window). It is the only filter that moved a pattern from
   negative to positive, and it is exactly the Level 2 role the owner described. It needs more
   book history to confirm (≈70 trades so far). The CFD archives cannot test it; only CME MBO
   can.

## Next steps

- Get more 6E MBO history (Databento, 2021–2024, same files as `downloads/`) to re-test the
  thick-book reversal with 4× the sample; this is the single highest-value purchase.
- In parallel, start P1/P4 plumbing: NinjaTrader book capture + cTrader demo bridge, so live
  book history accumulates from day one and the rule can be paper-traded as soon as it passes.
- Keep the multi-market engine: when the book filter is confirmed on 6E, the CFD instruments
  with a visible CME book (ES/NQ for US500/US100, GC for XAUUSD, 6B/6J/6A for FX) can be
  tested the same way with their own futures MBO.
