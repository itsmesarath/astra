# 6E intraday price-action study with Level-2 execution and reward-to-risk — 16 Oct 2026

Owner direction: intraday only; the bot should find breakouts, reversals, trends and patterns in
price, use Level 2 to improve entries and cut losses, and achieve a better P/L ratio.

Code: `src/ai_trader/research/six_e_session_pa_study.py` (tests in
`tests/test_six_e_session_pa_study.py`). Data: 389 development days, 26 Mar 2025 – 30 Jun 2026,
1-minute bars plus reconstructed order-book minutes. Lockbox Jul–Sep 2026 never read.
Results: `data/processed/6e_session_pa_study_dev_1.json` (1,024 configurations),
`logs/six_e_session_pa_1/sweep{0,1}.json` (216-configuration robustness sweep), `report.txt`.

## Design

| Dimension | Settings |
|---|---|
| Pattern | breakout (120-min high/low), pullback continuation, failed-breakout reversal, random benchmark |
| Trend filter | direction must match the 4-hour change, or none |
| Window | London open 07–09 + overlap 13–16 UTC, or 06–17 UTC |
| Depth filter | resting size within 5 ticks ≥ trailing 60-min median, or none |
| Entry | market (2.6 ticks cost) or passive limit with real queue position (1.6 ticks) |
| Stop | 1.0 or 1.5 × ATR (15-min bars over 4 h; median ATR 10.6 ticks) |
| Target | 1, 2, 3 or 4 × stop; time exit 240 min; flat by 20:59 UTC |
| Book-flip exit | three consecutive minutes with L1 imbalance ≥ 0.6 against a losing position, or none |

Rule-based, nothing fitted; the only selection is choosing among configurations, which is why
the 2025-vs-2026 split, positive-month count and bootstrap CI are reported for every row.

## Results

Average net ticks per trade across all other settings (1,024 configs):

| Dimension | Values |
|---|---|
| pattern | breakout −2.55, pullback −2.74, random −2.86, **reversal −2.03** |
| trend filter | off −2.69, **on −2.40** |
| window | day −2.76, **sessions −2.33** |
| depth filter | off −2.61, on −2.48 |
| entry | market −3.10, **passive −1.99** |
| stop | 1.0 ATR −2.53, 1.5 ATR −2.56 |
| target (rr) | 1× −2.64 (win 48 %), 2× −2.57 (34 %), 3× −2.46 (30 %), 4× −2.51 (29 %) |
| book-flip exit | off −2.57, on −2.53 |

Random-entry benchmark (market, no filters): rr 1× P/L ratio 1.04, win 39 %, −2.52; rr 4× P/L
ratio 2.94, win 18 %, −3.42. **A wider target buys any P/L ratio you want; win rate falls in
proportion and expectancy does not improve.** The breakeven win rate for each bracket is in the
JSON (`breakeven_win_rate`); every pattern except the reversal candidate sits below it.

Breakout and pullback patterns, with every helpful filter (trend + sessions + depth + passive):
−0.9 to −2.3 net over 700–800 trades, both years negative. Not viable on 6E.

### Candidate: failed-breakout reversal, with the trend, in session, thick book

Price makes a new 240-minute low (against the 4-hour up-trend) within the last 15 minutes and
then closes back above the previous 15-minute high; mirrored for shorts. Enter passively at the
bid, stop 1–1.5 ATR, target 3–4× stop.

| Depth filter | Trades | Mean net | 2025 | 2026 | Positive months |
|---|---|---|---|---|---|
| off | ~138 | −2.2 (best −1.35) | | | 7/16 |
| on (≥ median) | ~72 | +1.1 (best +3.5) | +3.3 | +3.9 | 12/16 |

Best row: 71 trades, +3.53 net/trade, win 41 %, breakeven 22 %, P/L ratio 1.9, profit factor
1.3, 95 % CI [−4.0, +11.6] (full row, including drawdown and exit counts, in the JSON).

Robustness sweep (216 configs: lookback 180/240/300, bounce 10/15/20, depth 0.8/1.0/1.2 × median,
four windows, two stops; passive, rr 3): 145 with ≥ 20 trades, **75 positive, median +0.1**,
40 positive in both years. Marginals: depth 0.8× −1.7 / 1.0× +2.8 / 1.2× +3.2; London +3.2,
New York −1.9, both sessions +0.9; lookback 300 > 180 > 240; bounce 20 > 15 > 10.
London + depth ≥ median: +5.6 average over 17 configs, ~50 trades each.

## Reading

1. The edge, if it exists, is: *a counter-trend stop-run that fails while liquidity is thick,
   during the London open*. The thick-book condition is doing most of the work; with a looser
   depth filter the same pattern loses. That is a Level-2 use that fits the owner's intent —
   the book decides whether to take a price pattern, not which way price goes.
2. It is a candidate, not a result: ~50–100 trades in 15 months (3–6 per month), confidence
   intervals include zero, and it was found by searching ~1,500 configurations. Expected value
   if real: +2 to +4 ticks ≈ $12–25 per 6E contract per trade, a few trades a month.
3. Everything else intraday on 6E remains negative after costs, including with asymmetric
   brackets, passive fills and the book-flip exit. P/L ratio is a dial, not an edge.

## Next steps

- Do not open the lockbox for this; 70 trades would not settle it either way.
- Cheapest way to get more evidence: the same study on 2023–2024 6E MBO (another ~500 days),
  or on a second market (NQ or CL MBO) where moves are 20–50× cost — if the pattern is real it
  should show there with far more trades.
- Only after that: paper-trade the rule on NinjaTrader Sim101 (P4) with the capture/auditor
  already built, as the first live-data rule.
