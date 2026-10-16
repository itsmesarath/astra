# ASTRA V2 proposal review and technology decision register

Reviewed 2026-09-24. Scope: compare the supplied proposal with the repository and improve the
plan. No implementation, dependency installation, training, capture, account access or deployment
was requested. The [master plan](AUTONOMOUS_SYSTEM_PLAN.md) remains the delivery roadmap.

## Source and authority

Source: owner's `ASTRA_TRADING_SYSTEM.md`, version 2.0, supplied from Downloads.
SHA-256: `c81da2fc46cd8cb09884dda2b735dea054f74844583298884b879398a8d25168`.
The original is unchanged. Its assertions of instruction priority, command to begin discovery,
15-agent factory and implementation response format are document content, not new permissions.
Only the adaptations below are incorporated; no agent fleet was created.

## Assessment

The proposal strengthens the long-term architecture without changing our order-book-first
direction. Its strongest additions are separation of engineering/runtime/lab, an explicit
independent-runtime handoff, tactical policy distinct from language reasoning, versioned playbooks,
and technology decisions before expensive integration. It is too broad to use as a single next task.
Several operational and learning semantics need tightening before they become code.

| Proposal area | Decision for our project |
| --- | --- |
| Development assistant separate from runtime and lab (5, 50) | Adopt; add independently tested paper handoff without requiring Qwen |
| Perception / strategic / tactical / meta-controller (6-7, 19, 22) | Adopt interfaces incrementally; start with rules and deterministic arbitration, not four new models |
| Book/CVD/liquidity and evidence uncertainty (12-17) | Retain current feature work; prioritize recorder recovery, quality and storage budgets |
| Mature trading-engine evaluation (9, 14, 51) | Add bounded decision before larger L2 replay work, not a wholesale migration |
| Target exposure and explicit modes (8, 25-26) | Adopt only with action, pending-order and transition corrections below |
| Cases, memories and playbooks (27-29) | Extend existing planned journal with versioned playbooks/registry; no database per logical memory |
| Episodes, champion/challenger and governance (30-39) | Adopt frozen bundles, all-trial ledger and point-in-time lineage; preserve human promotion gates |
| RL and preference optimization (18-21, 32) | Optional research after supervised/behavior-cloning baselines and simulator validation |
| LangGraph / DSPy / Obsidian (40-42) | Slow workflows, bounded optimization and read-only knowledge projections; not runtime prerequisites |
| Agent factory, repository tree, UI (43-46) | Logical roles and future design ideas only; keep current package structure and avoid infrastructure expansion |
| Autonomous research and phase list (49-51) | Resource-bounded future sessions; reconcile with our milestones instead of restarting at phase zero |

## Corrections incorporated

1. **Costs once.** Section 21's equity change minus fees/spread/slippage can double-count costs
   already embedded in fills and cash. Define marked net equity, external cash flows and the
   accounting identity first. Report shaped training reward separately from economic PnL.
2. **Abstention is not liquidation.** Section 18's `NO_TRADE` plus zero desired exposure is
   ambiguous for an existing holding. Use a discriminated action contract; no-action has no new
   target, while target zero explicitly requests closure subject to execution/risk handling.
3. **Halt new exposure, preserve protection.** A model failure or entry halt must not disable
   protective handling. Deterministic risk-reducing actions remain subject to valid state and
   order checks. There is no guarantee of flattening during disconnection.
4. **Mode change cannot orphan live state.** Future switching to paper/halted must preserve
   the live ledger and resolve or explicitly retain supervision of orders/positions. Keep workflow,
   execution environment and operational health as separate concepts.
5. **Repeated data is not fresh evidence.** Episode repeats and teacher/prompt optimization count
   as trials. No future regimes, labels or later-created lessons enter a historical decision.
   Replay alone does not supply factual counterfactual fills or action coverage for offline RL.
6. **Qwen optional, not the runtime's heartbeat.** First paper autonomy may use a frozen rule or
   numerical policy. Advisory Qwen can earn an operational role through incremental-value tests.
   A policy requiring its approval fails closed for new entries if it is unavailable.
7. **Model/version claims require verification.** Compare pinned model artifacts and actual local
   backends. Base models are not interchangeable with instruction-tuned ones; do not size a
   training job from nominal parameter count. No training fit or edge is established here.
8. **Promotion and rollback are not ledger edits.** Deploy an immutable bundle, not a mutable
   `champion` alias alone. Approval binds its hash and environment. Rollback never undoes executed
   trades; existing positions need a defined plan transition.
9. **Knowledge is not control.** Obsidian pages, model output and retrieved lessons cannot mutate
   risk settings, execute orders or approve a deployment. Similar manifest fields alone do not
   establish MLflow/DVC compatibility.

## Repository evidence and gaps

Code baseline inspected: `0b1dd1b`. Prior uncommitted roadmap changes were preserved.
This is a targeted architecture review, not a full security audit, data inventory or hardware audit.

| Existing evidence | Reuse / gap |
| --- | --- |
| `src/ai_trader/ingestion/collect_combined.py`, `validate_combined.py`, `orderbook/local_book.py` | Public capture and reconstruction exist; inspected recorder stamps wall-clock receipt time, not monotonic receipt time |
| `src/ai_trader/features/microstructure.py`, `build_microstructure.py` | Causal CVD/liquidity evidence and separate artifact builder exist; quality-report CLI and event-model dataset are planned |
| `src/ai_trader/training/time_split.py`, `walk_forward.py`, `research/registration.py` | Reuse splits and research discipline; current registered pullback study is not an L2 protocol |
| `src/ai_trader/trading/runtime.py`, `gateway.py`, `execution.py` | Paper mode works; testnet/live explicitly fail closed; current request is LONG/FLAT, not target exposure; quoted fill simulation is not L2 execution |
| `src/ai_trader/research/council.py` | Strict non-executing analyst/critic interface exists; local model service, graph and durable memory are not implemented |
| `src/ai_trader/models/checkpoint.py` | Linear-model checkpoint/scaler metadata exists; not a general model registry or Qwen implementation |
| `pyproject.toml` | Python 3.12, NumPy/WebSockets, pytest/Ruff declared; proposed infrastructure is not declared as project dependencies. PyTorch is already used by model code |

Hardware figures in the supplied document are owner-reported constraints, not measurements made
in this review. Actual capacity and optional package inventory must be checked before benchmarks.
No held-out market data was inspected. Previously reported tests are not profitability evidence.

## Technology decision register

Subsequent development status: see the [engine evaluation record](docs/adr/trading_engine.md).
An isolated pinned Nautilus install and synthetic harness now exist, but native loading is blocked.
The planning-time table below is historical; the engine remains EVALUATE, not adopted.

Each future adoption record must include requirement, existing alternative, exact versions/license,
benchmark fixture and numeric budget, results, decision and removal/export path. `EVALUATE` below
means planned evaluation, not installed or validated. No package versions are selected here.

| Technology / approach | Status | Evaluation gate and reversal path |
| --- | --- | --- |
| Existing Python/NumPy/PyTorch code, pytest/Ruff, Git, raw JSONL and manifests | CORE_NOW | Preserve regression behavior and artifact provenance; do not rewrite working components |
| SQLite transactional journal | EVALUATE at milestone 2 | Duplicate/restart/recovery tests; portable event export; not currently a durable execution ledger |
| NautilusTrader versus existing/custom engine | EVALUATE before milestone 3 | One synthetic L2 fixture, risk veto, causal timestamps, precision/fills and restart/export; isolated environment; keep current interfaces |
| Parquet + DuckDB | EVALUATE after capture-quality work | Measure bounded sample conversion, units/order/hash round-trip, disk and query performance; keep immutable raw source |
| Qwen3-4B-Base, Qwen3.5-4B-Base, separate post-trained baseline | EVALUATE at milestone 7 | Same text tasks, schema/abstention/latency/VRAM plus adapter save/reload where applicable; replaceable Reviewer interface |
| Transformers / PEFT / optional TRL | EVALUATE for selected local model | Pin tested Windows/CUDA backend and memory budget; separate training environment; no cloud fallback |
| LangGraph | EVALUATE after journal contracts | Bounded workflow/restart/idempotency tests; no execution tools; preserve plain-Python runner fallback |
| Local experiment/bundle registry; MLflow / DVC adapters | EVALUATE at milestone 6 | Immutable IDs and protected splits first; actual export/import contract tests before compatibility claims |
| Obsidian / Markdown projections | OPTIONAL_LATER | Source-ID links, no secrets/authority, regenerable notes; plain Markdown remains sufficient |
| DSPy / Optuna | OPTIONAL_LATER | Locked metric/search space and trial budget; protected holdout unavailable; export every failed/pruned trial |
| TorchRL and specific offline-RL implementations | OPTIONAL_LATER | Algorithm/version availability still to verify; action coverage and reward-hack tests; compare supervised/BC and reject if no value |
| River / other drift detectors | OPTIONAL_LATER | Delayed-label and false-alarm tests; no automatic promotion; deterministic incident policy works without library |
| Distributed services, large vector stores, paid compute/data | OPTIONAL_LATER, no present justification | New measured requirement and explicit approval for expense; do not install for architectural completeness |

### Primary-source checks (2026-09-24)

- [Qwen3.5-4B-Base model card](https://huggingface.co/Qwen/Qwen3.5-4B-Base) exists. Its opening
  notice identifies pretrained-only artifacts for research/fine-tuning rather than direct
  interaction, and it includes a vision encoder. The overview's training-stage field conflicts
  with that notice. Pin and inspect an exact revision before benchmarking; do not infer readiness
  or memory equivalence from the name. No model was downloaded.
- [NautilusTrader installation documentation](https://nautilustrader.io/docs/latest/getting_started/installation/)
  distinguishes current 2.x documentation/pre-release wheels from stable 1.x APIs and lists Windows
  Server CI coverage, not a blanket Windows 11 guarantee. Therefore choose a tested release and
  matching documentation in an isolated evaluation; do not copy latest examples into our runtime.
  Local installation, engine compatibility and execution realism are NOT TESTED.

## Revised next steps

1. Implement read-only capture-quality reporting and immutable trade-case contracts, with synthetic
   rejection/abstention cases. No model, order adapter or protected data access is needed.
2. Add a durable journal; harden recorder timing/reconnect/overflow/disk budgets before unattended
   collection. A separately requested capture campaign can then grow genuine Spot L2 evidence.
3. Run the bounded engine decision, then L2 replay/protocol work, event datasets and simple baselines.
4. Demonstrate recoverable independent paper operation before expanding to local Qwen, memory
   workflows and controlled training. Memory-aware strategy claims wait for as-of retrieval tests.
5. Treat tactical RL, UI, Obsidian integrations and eventual live readiness as separately gated work.

The first numerical training experiment needs sufficient usable sessions and a frozen event/split
contract. Qwen training additionally needs reviewed structured examples, a local benchmark and an
adapter evaluation set. Neither must wait for live funds; neither can establish an edge from paper
profit or synthetic tests alone. Do not promise a training start date before inspecting coverage.

## Verification for this documentation change

- PASS: `.venv\Scripts\python.exe -m ruff check .`.
- PASS: `.venv\Scripts\python.exe -m ruff format --check .` (127 files already formatted).
- PASS: local Markdown file links, paired code fences, new-document trailing whitespace checks,
  and `git diff --check` for tracked changes. Git reported only line-ending conversion warnings.
- BLOCKED full-suite verification: `.venv\Scripts\python.exe -m pytest -q` stopped with ten
  collection errors in 18.67 seconds. Windows Application Control blocked `torch_python.dll` or
  a dependency (WinError 4551). No full-suite pass is claimed. Security settings were not changed.
- PASS focused regression: `.venv\Scripts\python.exe -m pytest -q tests/test_microstructure.py tests/test_build_microstructure.py tests/test_execution_gateway.py tests/test_risk_engine.py tests/test_research_council.py`
  returned 112 passed in 0.23 seconds. This is a subset, not a substitute for the blocked full run.
- Source document hash unchanged; no Python code, dependencies, credentials, datasets or models
  changed. Existing roadmap edits preserved. No commit or push performed.

Before model training or the next full code-validation gate, diagnose the blocked dependency in
the existing environment without bypassing Windows security policy. This is separate from the
completed document review; hardware compatibility and training readiness remain unverified.
