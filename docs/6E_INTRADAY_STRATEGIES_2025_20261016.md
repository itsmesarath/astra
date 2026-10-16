# 6E rule-based intraday strategy families — 2025 (16 Oct 2026)

Code: `src/ai_trader/research/six_e_intraday_strategies.py`. Tests: `tests/test_six_e_intraday_strategies.py`, covering stop-before-target, time exit, daylight-saving times, ORB and the release fade.

Results are in `data/processed/6e_intraday_strategies_2025_1.json`.

**Families and setup:**
- **Strategy families**, 84 fixed configurations in total, all reported:
  - opening-range breakout at the London 08:00 and New York 08:30 opens;
  - New York 08:30 data-release follow and fade;
  - trend-day follow and fade.
- **Cost:** 2.6 ticks per round trip (1 tick slippage on entry, 1 tick on exit, 0.6 tick fees).
- **Fill model:** stops and targets are checked on minute highs and lows, and a stop is assumed to come first if both are touched in the same minute.
- **Data:** weekdays only, 2025.

**Result:** 17 of the 84 configurations were net positive over 2025.

**Every one of those 17 lost money in September–December.** Their profit came from April–August, when EUR/USD trended hard: +975 ticks in April, +963 in June, −786 in July.

| Best configuration (London ORB, 15-minute range, 2× target, 4 h) | Value |
|---|---|
| Mean net per trade, whole year | +3.89 ticks (196 trades) |
| April–August | +8.11 |
| September–December | −1.73 |
| Positive months | 5 of 10 |

Dropping the first 20 trading days (mostly the turbulent April) cuts another ORB variant's mean from +3.26 to +0.30 ticks.

A causal volatility filter, based on the recent 10-day range versus the history so far, did not rescue September–December.

**Conclusion.** These breakout and trend rules make money only in strongly trending months and lose otherwise. That is regime luck, not a stable edge. Testing more variants on the same 9 months would mostly find noise (data-mining).

No candidate is frozen. 2026 stays unopened.
