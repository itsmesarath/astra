# Flow-pressure research candidate

Status: implemented and synthetically tested; **no fresh market-data evaluation, model fitting or trading authorization**. This is a new hypothesis, not a retuning or rehabilitation of the 2026-09-25 `bid_replenishment_cvd` trial. Its first real evaluation must use new captures whose session starts are strictly after registration.

The earlier trial found no confirmed three-interval bid replenishment in its training sample and no policy proposals in either research session. Its ten-second, taker-costed unit-long labels were all losses in training. These observations motivated separating a *flow-pressure diagnostic* from the unproven hidden-liquidity heuristic. They do not validate the new candidate or justify lowering the old threshold and rescoring exposed validation data.

## Hypothesis and boundary

For a receipt-causal, newly applied BTCUSDT depth observation, require complete warmup, synchronized/fresh book and trades, unambiguous trade attribution and covered top-N/liquidity bands. Veto excessive spread and opposing ask absorption. The candidate then asks whether rolling aggressive-buy-minus-sell CVD, best-level order-flow imbalance, book imbalance and bid/ask band-liquidity ratio all exceed separately frozen positive thresholds. Bid absorption and repeated replenishment are counted as *supporting diagnostics*, never claimed as iceberg identities and never required for a signal.

This produces `diagnostic_signal_only` or the first explicit veto reason. It creates no `EntryPlan`, order, risk approval, fill, label, return, model feature selection, paper-policy change or live route. A qualifying frame is **not** a profitable opportunity. The motivating order-flow-imbalance literature concerns short-horizon price response, not this BTCUSDT rule's after-cost performance: [Cont, Kukanov and Stoikov](https://arxiv.org/abs/1011.6402). Binance's [Spot fee schedule](https://www.binance.com/en/fee/trading) and [commission FAQ](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/commission_faq.md) underscore that account/pair/discount fees must be established separately; this diagnostic deliberately has no assumed PnL.

## Plan and evaluator

`research.flow_pressure_trial register` accepts an exact settings schema and exclusively writes a checksum-bound plan. It freezes the candidate, replay configuration, chronological whole-source train/validation/reserved IDs, 1–10,000 total research-frame budget, current Python-source fingerprint, runtime versions and registration timestamp. Three to 32 sessions are allowed; each group must be nonempty. The example in `configs/flow_pressure_candidate_v1.json` declares two train, one validation and one reserved session, without opening or scheduling any market feed.

After full source verification, that example was registered locally at `data/processed/btcusdt_flow_pressure_v1_plan.json`: canonical plan SHA256 `99aca2e8022bcff99746f8b92ab6f461f95e70dda40ae2b11c35782fadca2d89`, raw file SHA256 `637eaf6001da0659cb3ec37dae117b5c34220a6354cdd8007de7eed152d19d77`, source fingerprint `d691df0753dcb46d29ccecd50d034f7f88ad28128b2e6732ac9f1cc177cae88d`. The settings raw SHA256 is `56020403763b2e07929a65118358866dfb43018de6cbd07eab0a0c5d615a27d2`. No source capture, process, order or model training was started by registration. If source code changes, this plan becomes stale and must not be repinned or reused.

`evaluate` requires **all** train and validation captures once, in declaration order, each with an external raw SHA256 pin. It refuses reserved/unknown/missing sources before opening a capture path. Every capture must begin after registration; research sources must be strictly chronological and nonoverlapping, with distinct bytes. Each source is fully replayed, including failed/abstaining frames, under 64 MiB aggregate capture bytes and the frozen frame budget. A budget excess or corruption publishes no successful subset. Market faults remain counted and mark the report `market_fault`. Reserved market rows are never opened.

Reports contain per-source reason counts, qualifying-frame counts and bid absorption/replenishment diagnostics, but no targets, PnL or selected-threshold metric. Both plan and report use exclusive fsynced creation; an interrupted partial output is retained and must not be treated as complete. Local SHA256 bindings detect byte drift, not independent custody or that someone never saw a dataset. The plan freezes roles and parameters, **not collection times**: a separate finite acquisition schedule and one-attempt stopping rule are required before claiming a prospective out-of-sample experiment. No current paper service consumes this candidate.

Safe commands:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.flow_pressure_trial register --help
.venv\Scripts\python.exe -m ai_trader.research.flow_pressure_trial evaluate --help
.venv\Scripts\python.exe -m pytest -q tests/test_flow_pressure_trial.py
```

After a separately registered, completed fresh capture schedule, use exact declared IDs and capture pins; never supply the reserved path:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.flow_pressure_trial evaluate `
  --plan data/processed/NEW_FLOW_PLAN.json `
  --source TRAIN_ONE data/raw/TRAIN_ONE.jsonl EXACT_SHA256 `
  --source TRAIN_TWO data/raw/TRAIN_TWO.jsonl EXACT_SHA256 `
  --source VALIDATION data/raw/VALIDATION.jsonl EXACT_SHA256 `
  --output data/processed/NEW_FLOW_REPORT.json
```

Do not interpret a nonzero signal count as strategy validation. The next *economic* protocol must independently predeclare a holding horizon, costs, entry/exit model, source-quality gates and an untouched later test, then evaluate the complete fixed source inventory. A candidate may reach paper execution only after that out-of-sample and paper-risk review. Qwen remains a separate protected-evaluation and local-training project; continuous training must never consume an active or reserved session or change a running paper policy.
