# Level-revisit study (2026-10-19)

Question (owner's proposal): mark the levels where the market reversed sharply; when price comes back,
decide whether it will break or reverse, and trade accordingly.

Data: Dukascopy 1-minute bars, 9 CFDs, 2021 - Jun 2026 (lockbox untouched). Costs per symbol as in the
multi-market study. Code: `six_e...`-style helpers in `src/ai_trader/research/level_revisit_study.py`
(events + features + per-bucket outcome) and `level_fade_replay.py` (one-position sequential replay).

Level = swing high/low over +-30 min from which price moved >= 1 ATR(15-min) away within 60 min.
Revisit = first later touch within 0.2 ATR (within 3 days, not already through). Outcome within 120 min:
break (close 0.5 ATR beyond), hold (close 0.7 ATR back), neither. A "big level" variant (+-120 min
swings, 2 ATR) was run on four symbols.

## What is robust (all 9 symbols, both 2021-23 and 2024-26)

| fact | value |
|---|---|
| revisited level holds / breaks | 55-58 % / 39-43 % everywhere; same in big-level variant |
| trading the break at the revisit | -1 to -2 x cost on every symbol, every period |
| fading the revisit unconditionally | about -0.2 to -0.6 x cost |
| best slice: slow approach (30-min move <= 0.3 ATR) with the 4-h trend pushing into the level, fade | positive in dev and test on 8/9 symbols *when events are counted independently* |

## What happens when it is traded for real (one position at a time, stop 1 ATR, target 2 x, 240 min)

| symbol | trades/day | win | net per trade (x cost) | mean R | years positive (R) |
|---|---|---|---|---|---|
| GBPUSD | 3.7 | 0.40 | +0.03 | -0.04 | 1 of 6 |
| EURUSD | 3.6 | 0.39 | -0.28 | -0.08 | 0 of 6 |
| XAUUSD | 3.4 | 0.39 | +0.50 | -0.03 | 2 of 6 (2025, 2026 H1) |
| US500 | 3.4 | 0.39 | +0.35 | -0.02 | 2 of 6 |

rr 1 and rr 3, and the sessions-only window, give the same picture (mean R -0.02 to -0.07).
The independent-event numbers were inflated by overlapping touches of neighbouring levels; sequenced,
the rule is a coin flip after costs. Gold's and US500's positive cost-unit means come only from the
high-volatility years (ATR grew faster than the fixed cost), not from a better hit rate.

## Reading

- The owner's premise is right: sharp-reversal levels do hold more often than they break (57/43), and
  that asymmetry is the same across markets and years. The size of the move after a hold is just not
  big enough, relative to the stop and the cost, to pay with price information alone.
- "Breakout at a level" is the one thing clearly not to do: it loses on every market.
- The decisive input - what tells a hold from a break *at the moment of the revisit* - is not in the
  price history. The slow/fast approach helps a little (hold rate 65 % vs 55 %). The order book at the
  level (resting size, pulls, aggressor flow into it) is the natural candidate and is exactly what the
  NinjaTrader 6E capture records since 17 Oct 2026. This study provides the event list to test it on.

Decision: no change to the live rule. Next: log, for every 6E level revisit in live capture, the book
state at the touch (depth within 5 ticks of the level, add/cancel flow, aggressor imbalance in the last
2 minutes) and the hold/break outcome; evaluate after ~300 events (~4-6 weeks).
