# Read-only paper lifecycle evaluation

Implemented 2026-09-24 in `research/paper_evaluation.py`. This audits an existing registered
[offline microstructure simulation](MICROSTRUCTURE_PAPER.md). It does not run the policy, append
cases/orders, liquidate inventory, change risk state, download data or train/promote a model.

## Fixed scope and evidence

Supply explicit registration, capture, source-session and paper-journal paths. Unknown/reserved
sources are rejected before capture/journal access. The evaluator verifies registered source bytes,
times, code/environment, funding, gateway/runner configuration and the complete committed sequence
of tick/case/frame bindings. It checks order identities, exact quote requests, event order and
fill price/fee arithmetic against the registered full-fill simulator. Extra cases, unbound orders,
unreconciled/partial lifecycles or unexplained account state fail closed.

SQLite is opened with `mode=ro` and `query_only=ON`; all evaluation reads share one transaction
snapshot. Missing journals are not created and existing inputs are not rewritten. This is a local
consistency audit, not authentication or proof that someone never changed all related hashes.

`max_frames` is a strict integer budget from 1 to 10,000. It must cover **all committed ticks** in
the journal. It cannot select an earlier profitable prefix while omitting later recorded losses.
An incompletely simulated capture can still be inspected, but is explicitly `truncated`. A funded
or metadata-only journal without processed ticks is not accepted as a zero-return experiment.

The immutable protocol version fixes mark timing, costs, cash control and terminal handling; there
is no optimistic-valuation switch. The registration's package-source fingerprint includes this
evaluation implementation. A code change requires a new registration/run, not silent reinterpretation
of an old experiment. This is not trusted third-party preregistration or a cross-trial holdout lockbox.

Reports include protocol, registration, capture and ledger-snapshot fingerprints. The ledger
fingerprint binds seed, checkpoint, ordered ticks/results, cases, orders and events, excluding local
file paths and wall-clock report generation time. Repeated reads of unchanged inputs are identical.
`risk_checkpoint_observed_at_ns` identifies the latest stored risk state, which can include a manual
kill-switch change later than the last evaluated tick. Economic metrics end at `ended_at_ns`.

## Accounting and marks

Reconstruct holdings in committed tick order, preserving order/event identity even when timestamps
tie. Reuse the durable account reconstruction rather than summing proposed trades. Only actual
recorded FILL events count as executed volume; rejected orders are reported separately.

For every tick, sample equity **before and after its orders**:

```text
equity = cash + remaining_BTC * fresh_synchronized_bid
net_PnL = equity - initial_cash
unrealized_PnL = remaining_BTC * bid - remaining_cost_basis
net_return_fraction = net_PnL / initial_cash
drawdown = maximum_prior_sampled_equity - current_sampled_equity
```

Flat accounts are valued at cash even without a healthy quote. Open inventory with an unhealthy
quote has `null` equity, unrealized PnL, terminal return and exit-scenario value. There is no
forward-filling an old price. `last_valued_sample` retains its original timestamp and is never
substituted for unknown terminal equity. A footer does not magically make a position liquidatable.

Entry fees are already in cash/cost basis; exit fees reduce proceeds. Slippage is already in recorded
fill prices. `fees_paid_usdt` and `slippage_embedded_usdt` are explanatory totals: **do not subtract
them again** from net PnL. Spread crossing is already reflected by ask entry versus bid valuation.
Gross filled notional sums both buys and sells; turnover divides that sum by initial cash.

Drawdown uses the funding baseline plus both pre/post-order samples. Pre-exit marks prevent exit
costs from hiding the sampled peak. These are sampled drawdowns, not continuous/intrafeed maxima.
If any open-inventory sample is unvalued, `drawdown_path_fully_valued` is false; reported observed
drawdown is incomplete, not a claim of the full path's worst loss.

The separate `hypothetical_terminal_exit_equity_usdt` scenario, when the terminal quote is usable,
equals `cash + BTC * bid * (1-slippage_fraction) * (1-fee_fraction)`. It neither books an exit nor
changes PnL, win rate or position state. It assumes the same quote-only costs, not executable depth,
exchange filters, market impact or a guaranteed liquidation price. For flat accounts it equals cash.

## Trades, exposure and control

Per-entry-lot records distinguish open and fully closed trades. Only fully closed lots have a
completed net PnL and enter winning/losing/breakeven counts and the closed-trade win fraction.
No closed trades means a `null` win fraction, not 0% or 100%. Realized loss and a later open position
remain separate. The selected adapter supports atomic full fills/rejections only; this evaluator
does not silently generalize to arbitrary imported or partial-fill journals.

`exposure_ns` sums intervals during which inventory was held, from snapshot availability to the
last committed tick; gaps still count as exposure. A fill on the final tick does not invent time
held beyond it. Time-in-position fraction is null for a zero-duration run. All timestamps/durations
use nanoseconds, money uses USDT, quantities use BTC, and ratios are fractions, not percentages.
Decimal outputs are strings; equivalent amounts may retain different trailing-zero precision.

The control holds the same initial cash, without interest or trades, so net PnL is zero. It is an
arithmetic no-trade baseline, not an independently simulated competing strategy. Excess return vs
cash is exposed only for a fully consumed, fault-free, flat-ended run with a fully valued sampled
path. Other runs retain descriptive metrics but set `full_session_flat_comparison_available=false`.
Never discard those incomplete/faulted runs when summarizing a research campaign: that would bias
results. Comparison availability is not profitability, readiness or statistical significance.

## Commands and verification

Safe checks using synthetic temporary inputs only:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.paper_evaluation --help
.venv\Scripts\python.exe -m pytest -q tests/test_paper_evaluation.py
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m ruff format --check .
.venv\Scripts\python.exe -m pytest -q
```

Template for separately approved research inputs; **not executed during development**:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.paper_evaluation --registration data/processed/REGISTRATION.json --capture data/raw/SELECTED_RESEARCH.jsonl --source-session DECLARED_RESEARCH_SESSION --journal data/processed/EXISTING_PAPER.sqlite --max-frames 1000
```

There is no execution-activation flag because this command cannot execute. JSON is printed to
stdout; no report file is automatically created or overwritten. Exit code 0 means a full-session
flat comparison is available, including losing or no-trade runs. Exit code 2 still prints an audit
but marks comparison unavailable due to truncation, faults or open/unvalued inventory. Other errors
raise without a success report. All reports retain `promotion_allowed=false` and no live capability.

Synthetic tests verify arithmetic, costs exactly once, stop/gap losses, sampled peaks, multiple
lots, unknown footer marks, prefix truncation, rejected orders, fixed protocol, read-only enforcement,
stable fingerprints, source/case/request corruption, protected-source rejection and CLI status.
See [the research log](../RESEARCH_LOG.md) for the final regression count.

## Next gates

This is not a full crypto L2 backtester: queueing, depth consumption, latency, partial fills and
impact remain unmodeled. This command audits one capture; a separate
[campaign command](MICROSTRUCTURE_CAMPAIGN.md) now reuses the same valuation protocol across a fixed
sequence with one continuous account, retaining unknown marks/exposure through disconnects.
Performance is correctness-first and unbenchmarked; no high-throughput or unattended service is claimed.

[Mechanical post-trade review](POST_TRADE_REVIEW.md) now shares this evaluator's read-only snapshot,
retaining every case and separating structural process checks from outcomes. Costed event labels,
verified session splits, a numerical baseline and registered walk-forward evaluation are also
implemented and synthetic-tested; they are not real-market evidence.

Next operational gates: explicitly authorized small public capture/zero-order smoke validation
and supervised forward-runtime verification. Actual-data comparisons across regimes/cost scenarios,
quality/sample review and explicit promotion remain necessary. Qwen and live connectivity remain future work.
