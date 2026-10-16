# First concurrent paper and strategy-validation run

Status, 2026-09-25: **paper recording completed; the frozen strategy did not qualify for training or deployment.** This was a bounded, public-data-only BTCUSDT Spot experiment. It used no account credentials, live orders, Qwen model calls or automatic retry. No service remains running.

## Paper collection and separation

The registered abstain-control service ran three consecutive 120-second sessions in one durable paper journal. Read-only inspection returned `recorded_complete`, matching capture hashes, 6,451 paper ticks, zero orders and zero open BTC inventory. The first two sessions had 2,406 and 2,154 paper frames with no paper freeze. The third had 1,891 frames and `paper_frozen: true` after breaching the stricter two-second simulated-action event-lag boundary; its complete raw recording remains retained but no action was allowed there. No results were discarded or replaced.

Local, Git-ignored service artifacts:

- Plan: `logs/realtime_paper_validation_20260925_1845_plan.json`, raw SHA256 `bfc0c160a28c2488a35dd60756295515b94448149dacb48ee68e4e2244ca9b95`; canonical plan SHA256 `dcb7cd7c5a601c28a2c810de8b3106fc0856e656f848d97a8e5d13a29e7837e4`.
- Manifest: `logs/realtime_paper_validation_20260925_1845_manifest.jsonl`, raw SHA256 `6d7e51259e50e51660cd21a3d924d784ce4cc4c1cb7e4bc67aed5df61f19df4b`.
- Journal: `data/processed/realtime_paper_validation_20260925_1845.sqlite`.
- Captures in `data/raw/realtime_paper_validation_20260925_1845/`: `s0001` SHA256 `0ce2536c6afc7b2f7ac3581ec96ca40be8fe45d8d67935d7fd35a229b65ee073`; `s0002` SHA256 `f81508a8e56bbbc971de9e4b4d85f0b49cdd65ff418150f624129e321d05a114`; `s0003` SHA256 `6d6cb370d1a94e0f5003b8acaa22592c2d1acdfb3b95f9267ddc4566efc30c4f`.

The separate local role declarations assigned `s0001` to training, `s0002` to validation and `s0003` to reserved. They were saved **after the first paper session started**, but before inspecting capture contents, labels, outcomes or orders. This is therefore exploratory, not an authenticated pristine holdout. The reserved file was hashed and its header/footer metadata checked for registration; its market rows, label data and model inputs were not opened.

## Frozen research checks

The event-label recipe reused the earlier 120-second experiment's 10-second horizon, 20-bps stop, 40-bps target, 10-bps taker fee and 2-bps slippage per side. Only source identities and the whole-session embargo (zero for this back-to-back service, with strictly nonoverlapping source times and source-local outcomes) differed. Both research captures were completely replayed with no market-fault frames and met the frozen 50-resolved/50%-resolved gates: 882/1,085 training eligible outcomes and 985/1,086 validation eligible outcomes. The fold verifier reported `reserved_sources_opened: 0`.

The one frozen NumPy baseline attempt returned `blocked_training_classes`: its 882 training labels were **882 modeled net losses, zero breakeven, zero gains**. It completed zero optimization epochs and did not evaluate or promote a model. A separate training-only cost audit found a modeled break-even ask-to-bid move of **24.03 bps** against at most **2.95 bps** of observed pre-cost move in these resolved training examples; mean modeled net return was **−24.67 bps**. These overlapping counterfactual labels are not 882 independent trades or realized paper PnL; the audit found at most ten nonoverlapping labeled intervals.

The separately frozen `bid_replenishment_cvd` shadow hypothesis emitted **no proposal** on either research source (2,406 and 2,154 evaluated frames). Its first failed signal was `bid_replenishment_not_confirmed` on 1,085 and 1,086 frames respectively. A training-only feature inspection found no `bid_repeated_replenishment_candidate: true`; of 1,189 feature-bearing training rows, 1,153 recorded zero bid replenishment intervals, 34 recorded one and two recorded two, below the frozen minimum of three. This diagnoses the first veto in this short sample, not an optimized replacement threshold. The shadow check is a stateless proposal audit, not a portfolio backtest. The live paper service itself used the abstain control, so zero orders are expected; no profitable/unprofitable live-paper strategy result exists.

Reproducible local research artifacts are under `data/processed/realtime_paper_validation_20260925_1845/`. The event registration and split raw SHA256 values are `cac16493f1bc099c98c5c2c7c13cdbbff2f018f882396a41dcc96edafc80c75b` and `c4611064989ffae4e41a1e2634eba865049a7584652418ac1058780702309396`. The fold report and blocked baseline raw SHA256 values are `ed9080e5707276a3f4a4a9bd6e763b53232e12362a47f30fa0c4620275d871d0` and `66a64fefbb9d02af7eacdd61dc7e8886acd58c4ae4a5ab5b1bde520e97b0407d`. The training-only cost audit is `logs/realtime_paper_validation_20260925_1845_train_cost_audit.json`, raw SHA256 `95bfab68dd17fd4a12f8ee34c611c89926fcbd22255f7ef2db9d4fa0daffd38d`.

## Decision and next gate

Do **not** fine-tune Qwen on these short, all-loss events, treat zero paper orders as profitability, loosen the frozen costs, or reuse the reserved session to find positives. Qwen's separate protected advisory evaluation registry is still empty, and actual CUDA/Qwen adapter fitting remains unverified. The next strategy hypothesis needs a separately frozen horizon, cost and signal protocol **before fresh independent sessions**, then whole-session out-of-sample evaluation across separated market windows. The historical L2 archive requires its own source-time/sequence replay contract before its rows can enter that experiment. An independently evaluated numerical baseline and realistic paper-account results should precede any model-controlled paper decisions; continuous local training must consume only completed, quality-accepted earlier sessions and never update an active policy mid-run.

Ruff lint/format and the full Python suite passed before the paper run: **2,871 passed, one optional Nautilus skip**. These software checks do not establish a trading edge.
