# Handover — 17 Oct 2026 (branch wip/2026-10-16-snapshot)

## Verified today
- CME Level 2 for 6E is entitled on the NinjaTrader feed: trace shows
  `MarketDepthSubscribeResponse instrument='6E DEC26' mode='RealTime'`; SuperDOM shows 10 levels/side.
  Live depth flows from Sunday 23:00 UTC; capture indicator still has to be put on a 6E chart.
- History connector (`integrations/ninjatrader/AiTraderHistoryConnector.cs`, installed as an AddOn)
  fetched ~10 months of 6E tick history with bid/ask stamps (6E 03-26 … 12-26, Dec 2025 – 16 Oct 2026)
  into `Documents\NinjaTrader 8\ai-trader-history\`. Feed lookback ≈ late Dec 2025.
- NinjaTrader ticks vs Databento, 3 overlapping days: identical daily volume, 99.5 % identical minute
  closes, buyer/seller split within 2–3 % of the official aggressor flag. Live source is trustworthy.
- `ctrader-open-api` installed in `.venv`.

## Built today (13 live-module tests pass)
- `ai_trader.live.nt_history` request/status/convert (lockbox guard).
- `ai_trader.live.ctrader_bridge`: demo-only Open API bridge (TLS framed protobuf), kill switch,
  0.01-lot / 1-position limits, EURUSD allowlist, masked audit, decision→bracket translation.
- `ai_trader.live.live_loop`: per-minute London-window loop capture→rule→demo order, idempotent
  state in `logs/live/sent.jsonl`, 240-min and 20:55 UTC exits. Unarmed by default (`--arm` to trade).
- `scripts/run/run_live_loop.cmd`, `install_ctrader_api.cmd`, `config/ctrader_demo.example.json`.

## Owner to-do (cannot be done by Claude: logins / trading app is view-only)
1. Sunday ≥ 23:00 UTC: NinjaScript Editor → Indicators → import/paste `AiTraderSixEDataCapture.cs`
   (`build/platform_capture_20261001`), compile, add to a 6E 12-26 chart, `TotalHours = 24`.
2. cTrader Open API portal: create application; authorise it for the IC Markets DEMO account
   (trading scope); fill `config/ctrader_demo.json` from the example. Then
   `python -m ai_trader.live.ctrader_bridge --check`.
3. Optional: Tools → Historical Data → Market Replay download for 6E 12-26 (historical depth).

## Then
- Run `run_shadow_daily.cmd` daily; start `run_live_loop.cmd` unarmed during London hours, armed
  once `--check` passes. Promote/kill gates in docs/SHADOW_PHASE_RUNBOOK_20261016.md.
