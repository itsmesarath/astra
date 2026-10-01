# EURUSD order flow imbalance scalp experiment

Status on 2026-10-01: **stopped at the frozen quote availability gate, with no strategy score published.** The next seconds-scale hypothesis is implemented and tested, but the first July evaluation day did not meet its predeclared 70% fresh-grid requirement. This is not a profitability result, and it does not establish that the historical data is corrupt. No model was trained, no orders were placed, and the BTC collector was not changed.

## Frozen question and execution assumptions

The [OFI experiment](../src/ai_trader/research/databento_6e_ofi_scalp.py) compares best-book order-flow imbalance (OFI) plus queue pressure with an independent queue-only control. The five predetermined trading days are July 7–11, 2025, using only dated CME 6EU5. There is no contract stitching, volume-based roll selection, threshold search or model fitting. The original March–April CVD pilot is separate evidence.

The [configuration](../configs/databento_6e_ofi_scalp_v1.json) fixes decisions every five seconds from 12:00 through 16:00 UTC, a completed quote strictly before the grid and at most 500 ms old, and a one-tick decision and entry spread. OFI sums changes between completed best-book states over five seconds using the bid/ask price-change indicators, then divides by current average best-side depth. A primary signal requires magnitude at least one and agreement with a queue-weighted midpoint offset of at least 0.15 tick. The control uses the same midpoint-offset threshold without the OFI gate.

At a one-tick spread, the weighted midpoint offset is exactly half the queue imbalance. It is one queue feature, not a second independent confirmation and not a fitted microprice model. The [OFI paper](https://arxiv.org/abs/1011.6402) and [queue imbalance paper](https://arxiv.org/abs/1512.03492) motivate these hypotheses using equity-market evidence; neither supplies our numerical thresholds nor demonstrates a tradable EUR/USD edge.

The replay builds quotes only at completed `F_LAST` events. It does not count both Trade and Fill messages as book flow; actual queue changes determine OFI. An event spanning a decision grid cannot leak its final state into that earlier decision. [Databento venue documentation](https://databento.com/docs/venues-and-datasets) describes the event completion convention.

Each strategy has an independent primary position schedule: 100 ms entry delay, a 15-second hold, ten-second cooldown and at most one selection per signal episode. The 500 ms and 1,000 ms variants reprice that primary schedule, not independent portfolios. Longs cross the ask on entry and bid on exit; shorts reverse those sides. Additional round-trip costs are 0, 1, 2 and 4 ticks, with one tick the primary assumption, not a measured cTrader charge.

Unlike the earlier pilot, a late exit quote closes an entered position at its observed price and records the lateness. It is not dropped for missing the one-second exit target tolerance. Any position still unresolved at 16:00 remains explicit and blocks a positive research conclusion, including control and sensitivity positions. These are quote counterfactuals, not simulated fills: size, impact, broker spreads and actual cTrader execution remain untested.

## Why the run stopped

The July 6 preparatory member and July 7 member completed their pinned read and decode. The first evaluation day then failed with `fresh=1884/2880 required=2016`. The runner published neither `data/processed/databento_6e_ofi_scalp_v1_rows.jsonl` nor its summary. July 8–11 were not replayed, and no successful subset was scored. July 7 strategy rows were calculated internally before the daily gate rejected them, but their signals and returns were not inspected. Do not describe that day as wholly unexposed: its availability is now known.

A separate read-only diagnostic replayed only July 7, overriding the decision hook to record quote age without constructing signals, positions or returns. It reproduced the gate failure, verified the compressed member at EOF, checked archive size and modification time remained unchanged, and found a quote at all 2,880 grid points. Mapping was instrument ID 3624 for 6EU5.

| July 7 quote timing measurement | Observed value |
| --- | ---: |
| Grid quotes no more than 500 ms old | 1,884 of 2,880, or 65.42% |
| Median quote age at a grid | 286.03 ms |
| 90th percentile grid quote age | 1,306.42 ms |
| 99th percentile grid quote age | 3,198.37 ms |
| Maximum grid quote age | 9,821.42 ms |
| Completed quote events including ten-second warmup | 327,794 |
| Consecutive completed-event gap median | 0.128 ms |
| Consecutive completed-event gap 99th percentile | 955.86 ms |
| Maximum completed-event gap | 12,082.11 ms |

Fresh grids by UTC hour were 432, 520, 532 and 400 out of 720 for hours 12, 13, 14 and 15 respectively. The event-gap distribution weights events, while grid ages sample clock time; their differing medians are not contradictory. Bursts can contain many rapid events while a fixed clock often lands between bursts.

These measurements establish a mismatch with this fixed-clock availability rule, not the reason for every gap. Quote age is time since a completed target-contract event, not proof of a broken feed or a changed executable price. The diagnostic does not independently rule out upstream missing data. It is also not evidence that a 70% or 500 ms cutoff should be lowered. Both remain unchanged in this version.

## Evidence fingerprints and checks

All values below are SHA256 of raw bytes. Source and implementation fingerprints allow the failed run to be identified without publishing licensed MBO data.

| Evidence | SHA256 |
| --- | --- |
| Frozen OFI configuration | `93422798403e400ed59720e11e61e6a802065cff0507172a57061261913382e0` |
| Existing intake report | `de12f9833b951781f27b5ea46d2c6dc2302c422e1080bfc48914b2dc8a82b27a` |
| July 6 compressed member | `198359b72db0d812a4b5f8acffa274c317408b51042de179c83eeb21a050dc7c` |
| July 7 compressed member | `416631200f9ed824e3e78835ed3a802544bf3cfd67d828314d7760ec4e64ae5b` |
| OFI replay implementation | `05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24` |
| Shared seconds replay implementation | `7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b` |
| Scenario replay and strict book implementation | `d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff` |
| Training data decoder and book implementation | `9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3` |

The shared replay extension reproduced the earlier V2 pilot byte-for-byte: rows SHA256 `e687b1dbe01eacacd4ff92b4bfb238a1faea488fa07579723e2d0a38cca83cd8` and summary SHA256 `c985f5d8d4381da58c643b090468130120774bb44cd580c52ff45580f36152d2`. Regression copies have `v2_ofi_regression` in their filenames; original evidence was not overwritten. The 61 related tests passed, including event causality, OFI signs and thresholds, warmup/reset, entry vetoes, late/unresolved exits, pin mismatches and exclusive output publication.

Final workspace verification: Ruff lint passed; all three changed Python files passed Ruff formatting; the complete test suite reported 3,000 passed and one skipped in 148.88 seconds. The skip is the optional native Nautilus evaluation dependency. Unrelated existing worktree changes were preserved.

To reproduce this frozen experiment, run the module with `--config configs/databento_6e_ofi_scalp_v1.json`, `--rows-output` and `--summary-output` pointing at two new local paths. It requires the original pinned intake report and archives; no download or trading connection is used. The expected current result is the July 7 availability error, not a score.

## Next research step

Follow-up: the separate [event-triggered experiment](EURUSD_6E_EVENT_SCALP_20261001.md) has now been implemented and evaluated. It completed its frozen cohort but produced negative quote returns; it did not change or rerun this fixed-grid experiment's failed gate.

Keep this version stopped and unscored. The follow-up protocol makes decisions only when a complete fresh book event arrives, with a fixed decision-rate limit. It specified observability, inactivity detection, expiry, position exits and cost assumptions before inspecting new returns, and retained whole-session reporting with separate development and evaluation dates. Its results must not be presented as a passing rerun of this experiment.

For the user's eventual cTrader EUR/USD spot/CFD bot, synchronized broker bid/ask data and an execution-cost model are still necessary. A CME futures directional signal does not establish profitable broker execution. Keep model promotion and live orders disabled, and do not feed these unvalidated scenarios to Qwen as examples of a proven profitable strategy.
