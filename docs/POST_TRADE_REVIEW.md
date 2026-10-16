# Mechanical paper case and outcome reviews

`research/post_trade.py` creates a separate, checksummed review report from one registered offline
paper journal and its explicit capture. It shares the [paper evaluator](PAPER_EVALUATION.md)'s
read-only SQLite transaction: capture/tick/case/order/fill verification, account reconstruction and
review joins see one consistent snapshot. It never writes reviews back into the trading journal,
changes an original case, creates orders, fits a model or promotes a lesson.

## Two passes, separate meanings

The versioned, fixed rubric first reviews each sealed case **without outcome inputs**. It checks
paper mode, policy/feature/risk configuration bindings, evidence availability at decision time,
entry-plan expiry and approved quantity relative to the proposal. Protective-exit cases have their
own existing adapter-version contract. Non-applicable checks stay null. Failed checks are retained.

These are structural checks, not independent reproduction of every policy/risk verdict or a causal
assessment of the trading thesis. `decision_quality` therefore remains `UNKNOWN`; a profitable
outcome cannot turn a failed process check into a pass, and a compliant losing trade is not called
a bad decision. LLM interpretation and reviewed quality judgments remain future work.

Only the second pass joins verified entry lifecycles and evaluated trade outcomes. Every original
case remains present, with one of: `no_action`, `risk_rejected`, `not_submitted`, `order_rejected`,
`open` or `closed`. No-action is not liquidation; an unfilled case is not a breakeven trade.

Closed trades additionally produce the existing typed `PostTradeReview`, bound to the unchanged
case and verified ledger snapshot. Net PnL uses the evaluator's actual quote-paper fills and fees,
without subtracting costs twice. WIN/LOSS/BREAKEVEN is recorded separately from decision quality.
Open and unfilled cases have no fabricated closed-trade PnL or resolved review. Excursion fields
(MAE/MFE) stay unknown: portfolio equity is not a substitute for a per-trade executable-price path.

All lessons are `ANECDOTE`, with promotion disabled. A report is evidence for later controlled
research, not a training dataset or automatic update to an active policy.

## Scope, time and integrity

- The budget must cover the entire committed prefix, up to 10,000 frames; it cannot hide later losses.
- Reserved/unknown sources are refused before capture/journal access. The evaluator's existing
  identity, provenance, code/environment, cost and ledger-reconstruction checks remain in force.
- Review creation time is sampled now and must follow the registration and evaluated evidence.
  `available_at_ns` is this creation time, not the old trade time. Future memory retrieval must use it.
- Stable review identities bind case content, ledger snapshot and rubric version. A new ledger
  prefix is a different review context. Re-running does not rewrite an older report.
- Reports retain source/session completion, market faults, open trades, failure counts and every
  case. Corrupt source/ledger state aborts instead of yielding a passing subset.
- Publication is exclusive and capped at 32 MiB. Existing output or quarantined partial paths are
  refused. A failed publication never changes the source journal.

Safe commands:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.post_trade --help
.venv\Scripts\python.exe -m pytest -q tests/test_post_trade.py tests/test_paper_evaluation.py
```

For an explicitly approved existing single-source paper experiment, provide `--registration`,
`--capture`, `--source-session`, `--journal`, `--max-frames` and a new `--output`. This command does
not create a paper experiment. CLI output is compact counts, not the full case history. Exit 2
flags incomplete processing, market faults, process-check failures or open trades. Exit 0 does not
establish profitability, statistical validity, calibrated quality or permission to trade.

Tests use synthetic journals only. Cross-session campaign reviews, independent rule audits,
per-trade excursions, point-in-time decision memory and local-model review are later extensions.
