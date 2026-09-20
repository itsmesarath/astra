# TradingAgents review and local adaptation

Reviewed 2026-09-20 at upstream commit
[`2d17df8da1536c121e4d7395ac5a5dcec9e96d6f`](https://github.com/TauricResearch/TradingAgents/tree/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f).
The inspected package identifies itself as version 0.5.0. Review covered graph construction and
routing, model configuration/providers, structured decision schemas, trader grounding, memory,
reflection, point-in-time data helpers, market validation, checkpoints, backtesting and relevant
tests. This is a targeted source review, not a security audit of every file. Upstream was cloned
into a temporary directory for inspection, not installed or executed.

## Can we run this architecture without API keys?

Yes. Roles are separate prompts and state transitions, not necessarily separate models or GPUs.
One local model can handle the roles sequentially. Upstream already declares a key-optional
Ollama provider at `http://localhost:11434/v1`; its SDK placeholder is not a paid service credential.
See the pinned [provider implementation](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/llm_clients/openai_client.py)
and [Ollama local authentication documentation](https://docs.ollama.com/api/authentication).

No paid model key does **not** mean no internet. The defaults route data to online vendors;
some are keyless, others require credentials. For strictly offline operation we must replace
those tools with archived, timestamped local inputs, preinstall weights, and deny network fallback.
Do not start the upstream default configuration: its default model provider is cloud-based.

Local hardware observed: RTX 5080 Laptop GPU, 16,303 MiB total VRAM, approximately 14,317 MiB free
at inspection. A 4B model's nominal weights are about 8 GB at 16 bits or 2 GB at 4 bits, excluding
quantization metadata, caches and runtime overhead. This arithmetic makes sequential small-model
inference plausible, not benchmarked. Training memory, long contexts and simultaneous roles are
separate constraints. Ollama was not found on PATH; no runtime or model was installed this turn.

For initial role-following experiments, prefer the post-trained
[Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B) over
[Qwen3-4B-Base](https://huggingface.co/Qwen/Qwen3-4B-Base), whose card identifies its training stage
as pretraining. This recommendation is for instruction following, not trading ability. Keep Base
as a separate later fine-tuning experiment; do not silently replace or rename the planned model.

## What the repository actually offers

The [graph](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/graph/setup.py)
sequences selected analysts, bull/bear researchers, a research manager, a trader, three risk
perspectives, and a portfolio manager. Analyst nodes can loop through data tools; debate counts
bound researcher/risk discussions. The quick/deep roles can share a local backend.

Useful adaptations for BTCUSDT Spot:

| Upstream component | Our adaptation | Status |
| --- | --- | --- |
| Specialist roles and bounded debates | One analyst and one critic, at most two calls per proposal | Implemented research interface |
| Structured recommendations | Strict JSON verdict, cited evidence IDs, bounded rationale; no executable prose fallback | Implemented |
| Verified market snapshot and date guards | Immutable numeric evidence with event and availability times; symbol/freshness checks before review | Implemented boundary, upstream producers still trusted |
| Risk discussion and final manager | Existing deterministic risk engine retains veto; opinions cannot resize or create entries | Implemented research preflight |
| Point-in-time decision memory | Only retrieve outcomes/lessons known before the decision, with experiment isolation | Planned |
| Resume/checkpoint state | Bind saved results to inputs, configuration, model and prompt versions | Input fingerprint implemented; durable checkpoint store planned |
| Reflection after resolution | Separate outcome diagnostics from model updates | Planned |
| Recommendation evaluation grid | Controlled ablations through our repaired economic replay | Planned; simulation fixes still required |

The [structured-output helper](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/agents/utils/structured.py)
falls back to free text after structured failure. We deliberately do not adopt that behavior for
entry permission: malformed or unavailable review means no entry. We also do not adopt prompts
that push the model toward taking a side. Abstention is a valid result.

The [memory log](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/agents/utils/memory.py)
filters resolved lessons by when outcomes became known. Our future version should always require
an explicit millisecond cutoff, including current-day runs, and also track when the lesson itself
was generated/available. Same-day end-of-day knowledge must not leak into an intraday decision.
Keep pending decisions and resolved outcomes separate; never let held-out experiments populate
training memory. Store structured records rather than parse model-written markdown delimiters.

The [backtest module](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/backtest.py)
explicitly evaluates recommendation quality, not a portfolio simulator with filled quantities and
carried cash. Its summary also warns that non-archived text feeds and model sampling limit
repeatability. Do not equate recommendation hit rate or benchmark-relative returns with our
fee/slippage-adjusted account PnL.

The [reflection module](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/tradingagents/graph/reflection.py)
generates text lessons for later prompts. This is contextual memory, not gradient training or
automatic fine-tuning. A persuasive explanation after a trade does not demonstrate causality.

## Implemented locally in this change

`src/ai_trader/research/council.py` provides a non-executing review boundary:

1. Accept an existing LONG signal, a BTCUSDT BUY proposal from a flat position, risk state/limits,
   and a bounded evidence snapshot.
2. Reject wrong-symbol, unavailable/future or stale evidence, and apply deterministic risk limits.
3. Ask an analyst, then a critic. Validate exact JSON fields and citations; deny on a veto or error.
4. Return an auditable result with role reports, cutoff and SHA-256 input fingerprint. There is
   no broker call, credential handling, HTTP client or dependency installation.

The included `CostStressReviewer` is an explicitly deterministic baseline, not an LLM. It checks
caller-provided baseline and stressed **net expectancy estimates** independently. It neither
estimates them nor learns them. Never feed future realized labels or convert uncalibrated softmax
confidence into these fields. Missing estimates produce no entry.

Run the synthetic demonstration:

```powershell
.venv\Scripts\python.exe -m ai_trader.research.council --demo
```

Expected result: analyst supports the positive reference estimate, critic vetoes the negative
stress estimate, and `entry_allowed` is false. This is a safety demonstration, not trading evidence.

The `Reviewer` protocol is an integration point for a future local model. It does not itself
sandbox arbitrary Python implementations or enforce their timeout. The shipped implementation is
network-free; a later backend must enforce process/time/token limits and local-only operation.
Known citation IDs establish provenance links, not whether an LLM's argument is true.

This module is opt-in research infrastructure, **not wired into the paper simulation or champion**.
It reviews entries only: denying entry must never be translated into a forced FLAT/exit order.
The caller remains responsible for truthful timestamps, known-at-the-time estimates, current
signal/order prices, cash availability and archival provenance. Recheck risk and execution costs
at any subsequent paper fill. The fingerprint binds inputs, not reviewer identity or output;
future durable records must additionally bind prompt/model versions and preserve raw responses.

## Local-model and training milestones

1. Finish existing timestamp/split isolation, stop-gap fill and capital-accounting repairs first.
   This architecture work does not fix those issues or make old backtests independent.
2. Add an opt-in local-only reviewer backend. Use one post-trained model sequentially with small
   contexts and bounded outputs. Prestage weights; prohibit automatic downloads, remote endpoints,
   tool execution and cloud fallbacks. Start in shadow research mode with no broker access.
3. Benchmark schema success, citation validity, latency, peak memory and repeatability. Preserve
   raw responses, exact prompts, model/quantization hashes, sampling configuration and input data.
4. Compare the same frozen candidate across rule-only, single-reviewer, two-role council and
   deterministic-cost-review variants. Count every experiment. Use the same chronological folds,
   costs and risk budget; do not change the underlying candidate to rescue a poor council result.
5. Record decisions before outcomes. Resolve only after the horizon and ingest lessons only after
   their availability time. Store failures, abstentions and losses as well as winners. Separate
   prompt-memory experiments from weight-training experiments.
6. If the council adds measurable value, build supervised examples from causal inputs and
   evaluated outcomes. Fine-tune a small adapter in batches, not after every tick. Independently
   evaluate the adapter against the unchanged baseline and paper champion before promotion.

Repeated roles using one model have correlated errors: two agreeing personas are not two
independent forecasts. Extra discussion can increase latency without adding information. Prefer
event-level reviews on slower candidate setups, not a debate for every order-book update.
Pretrained model weights may also encode later knowledge about historical dates. Point-in-time
tools alone cannot remove that contamination: include prospective/post-model-release evaluation
and assess anonymized numerical-input controls before claiming historical LLM performance.

## License and reuse boundary

The inspected upstream [LICENSE](https://github.com/TauricResearch/TradingAgents/blob/2d17df8da1536c121e4d7395ac5a5dcec9e96d6f/LICENSE)
is Apache-2.0. This change credits the architecture but copies no upstream source or prompts and
adds no TradingAgents dependency. If future work vendors source, preserve the applicable license,
copyright/attribution notices and change notices; review upstream NOTICE requirements then.
Do not import the entire cloud-provider/vendor stack for a small offline review workflow.
