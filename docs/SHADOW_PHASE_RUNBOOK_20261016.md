# Shadow phase runbook — NinjaTrader 6E book capture + candidate rule, no orders (16 Oct 2026)

Why: the only non-negative intraday candidate (failed-breakout reversal with the 4-hour trend,
London window, thick CME book) has ~70 historical trades. More CME book history is not being
bought, so it is captured for free from the NinjaTrader feed and the rule is evaluated on it
daily in shadow mode. The same months build the live pipeline toward the cTrader bridge (P4).

## One-time setup (owner)

1. NinjaTrader 8 with the customised CME plan that includes **Level 2** for 6E (≈ €16/month).
2. Import/compile `integrations/ninjatrader/AiTraderSixEDataCapture.cs` (packaged copy under
   `build/platform_capture_*`), add it to a 6E chart with `TotalHours = 24`, `MaximumFiles = 2000`.
   It writes `Documents/NinjaTrader 8/ai-trader-captures/ninjatrader-<id>.jsonl`, rotating daily.
   It never places orders (`trading_enabled: false` in every file header).
3. Leave NinjaTrader connected during the London window at minimum (07:00–09:00 UTC); the
   rule only fires there. Full 24h capture is better: the ATR, trend and depth median need
   the preceding 4 hours.

## Daily (one double-click, or Task Scheduler at 21:30 UTC)

`scripts/run/run_shadow_daily.cmd`:
1. `ai_trader.live.capture_minutes` merges every capture file into `data/live/6e_minutes/`
   (`bars/<date>.json`, `book/<date>.json`), the same formats as the historical stores.
2. `ai_trader.live.shadow_signals` replays history (warm-up) + live store through the exact
   study code and appends each would-be trade with its book state and simulated outcome to
   `logs/shadow/decisions.jsonl`; prints the running tally since 2026-10-01.

Check `logs/shadow/daily_<date>.log`. The replay of the historical store alone gives 44
closed trades, mean +3.0 ticks, win rate 0.41 (IC Markets cost 1.8 ticks); the live tally is
compared against that.

## What the live feed changes (documented approximations)

- No aggressor flag: trade at/above the ask = buyer, at/below the bid = seller.
- Depth is a 10-level ladder, not orders: `ofi`, `adds_*`, `cxl_*` are 0; the rule uses only
  `bid_d5 + ask_d5`, which the ladder gives exactly.
- Observation clock is the local callback clock (see `platform_capture.py` caveats); minute
  boundaries can shift by the callback latency. Irrelevant at 240-minute holds.

## Decision gates

- Lockbox Jul–Sep 2026 stays sealed (the loader refuses those dates). It is opened once, as
  the final check, when the live tally and the historical 70 point the same way.
- Promote to the cTrader demo (P4) when: ≥ 30 live shadow trades, positive mean, and the
  monthly sign agrees with history in most months. Kill the candidate if the live mean is
  negative after 40 trades.
- Trade frequency expectation: 3–6 per month on 6E alone. Breadth comes later from other
  CME books (ES/NQ for US indices, GC for gold), not from loosening the rule.
