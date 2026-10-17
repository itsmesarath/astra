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

## History connector (added 17 Oct 2026)

`integrations/ninjatrader/AiTraderHistoryConnector.cs` is installed as a NinjaScript AddOn
(bin/Custom/AddOns). It polls `Documents\NinjaTrader 8\ai-trader-requests\*.json` every 15 s and
fulfils each request through BarsRequest, one JSONL file per CME session day under
`ai-trader-history\<instrument>\tick_<date>.jsonl` (trade price, size, bid, ask) or `minute_<date>.jsonl`.
Finished requests become `.done` / `.error`. Its log lines appear only if a NinjaScript Output window
is open (Control Center → New → NinjaScript Output).

Python: `python -m ai_trader.live.nt_history request "6E 12-26" 2026-10-01 2026-10-16`,
`... status`, `... convert 6E_12-26 --output data/live/6e_history_bars` (buyer = trade at/above ask,
seller = at/below bid; refuses lockbox days unless `--allow-lockbox`).

Verified 17 Oct: 6E 12-26, 1–16 Oct 2026 → 1.2 M ticks, sessions 22:00–21:00 UTC, no overlaps;
converted to 14 UTC day files. Feed lookback observed: tick history back to late Dec 2025.
Level 2 is live-only; historical depth remains a Market Replay download (manual).
