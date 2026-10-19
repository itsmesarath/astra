# 6E burst-momentum study (2026-10-19)

Question: after a volume burst like the one at 10:38 UTC on 19 Oct 2026 (1,481 contracts in 10 s,
+10 ticks in a minute, all given back within three), is there follow-through worth trading once the
burst is detectable?

Data: NinjaTrader 6E tick history with bid/ask (front month per day), 143 trading days,
Dec 2025 - Jun 2026 and 1-19 Oct 2026. Lockbox days (Jul-Sep 2026) untouched.
Code: `src/ai_trader/research/six_e_burst_momentum.py` (tests in `tests/`).

Detector: rolling W-second volume >= k x trailing-hour average and >= vmin contracts, price moved
>= m ticks, aggressor share >= 60 % in that direction. Entry at the next tick, direction of the burst.
Exits: trailing stop / hard stop / time limit / 10-second imbalance flip. Costs: 1.8 ticks (IC Markets
EURUSD model); the merged grid file additionally charges the recorded spread on both legs.

## Result

| Threshold | Bursts/day | Gross follow-through after detection | Net at 1.8 ticks |
|---|---|---|---|
| vmin 150, 144 exit/threshold variants | 7-26 | -0.1 to -0.5 ticks (every variant, every month) | -1.9 to -2.3 |
| vmin 500 (k 20, W 10 s, m 5) | 3.2 | ~0 (trail+flip); +0.6 at 60 s | -1.9 |
| vmin 1000 | 1.4 | +0.3 (trail+flip); hold 300-600 s: mean -0.3 to -0.8, median -7 to -10 | -1.5 to -0.3 |

Monthly means for the 1,000-contract variants alternate sign (+3, -5, +1, -4, +3, -1, -6 ticks).
Bootstrap 95 % CI of every variant includes zero or is negative.

## Reading

- Once a burst is large enough to be detected, the average continuation is zero: the move is in the
  first seconds (today: 6 of 10 ticks inside one 10-second bucket), before any threshold can fire.
- The distribution is skewed: a few bursts (news) run on for 20-40 ticks, most retrace within a
  minute. The mean is carried by the tail and the median is a loss; costs take the rest.
- Fading the burst is not an edge either (gross +0.1 to +0.5, below cost).

Decision: no burst-chasing rule in the live loop. The event is worth recording as context (a
"burst" flag in the minute store) so the reversal rule can later be checked for interaction with it.
