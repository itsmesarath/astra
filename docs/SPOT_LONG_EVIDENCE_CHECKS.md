# Deterministic Spot-long evidence checks

Status: implemented as an **offline research report**, not an execution gate or trained model.
`research/spot_long_checks.py` independently checks caller-supplied numbers. It does not read
case verdicts, reference rationales or Qwen output, and does not import a model runtime. A
separate `research/advisory_fact_audit.py` joins those facts to existing evaluations without
changing their raw replies, schemas, denominators or grades. No inference, download, training,
network connection or order is needed to use either report mode.

## What is checked

The version `spot_long_numeric_v1` requires exactly one observation for each exact metric name:

| Metric | Requirement |
| --- | --- |
| `estimated_gross_return_bps` | Finite, bounded supplied gross estimate |
| `estimated_round_trip_cost_bps` | Nonnegative cost estimate |
| `net_expectancy_bps` | Exactly gross minus costs, strictly positive |
| `stressed_net_expectancy_bps` | Strictly positive supplied stress estimate |

Missing or duplicate estimates veto the numeric rubric. Optional `kill_switch_active` and
`daily_loss_limit_reached` observations veto on any nonzero value, including negative/fractional
values; duplicates also veto even when equal or zero. These flags are caller-supplied evidence,
**not verified account risk state**. Missing flags do not establish clearance.

Unknown metric names are ignored for this rubric and reported by evidence ID; CVD, imbalance,
replenishment/iceberg proxies and classifier confidence cannot substitute for after-cost estimates.
The checker does not manufacture those estimates from order-book signals. All observations,
including ignored metrics, must still pass the source, time and numeric preflight.

Preflight requires typed immutable BTCUSDT evidence within the explicit source session, no
future availability and event age within the configured 0–300,000-ms window. Timestamps must
fit nonnegative signed-64-bit milliseconds. Input decimal coefficients are at most 64 digits,
with stored exponent between −128 and +128; this deliberately refuses extreme representations
rather than normalizing/rounding them into range. The canonical input budget is 32 KiB. These
are the checker's own bounds, not changes to historical Qwen prompt preflight. Bad configuration
raises an error; invalid evidence returns `preflight_refused` without arithmetic or a fingerprint.

Subtraction uses an isolated 322-digit decimal context with rounding/inexact traps. This is
sufficient for the accepted input domain, including the maximum exponent spread; caller context
settings cannot alter the calculation. Comparison is exact, without tolerance. Facts retain
evidence IDs and fixed-point decimal strings separately from `computed_net_bps`. The input
fingerprint binds original decimal representations, scope, age budget and checker version.

Results are `preflight_refused`, `veto`, or `conditional_support`. The last means **only that the
supplied numbers satisfy this research rubric**. Compatible bps units, horizons, definitions and
estimation/calibration remain assumptions; plausible numbers can be wrong about the market.
Stress is independently supplied, not recomputed from a stress scenario; no unversioned rule
requiring stress below baseline is added. This does not prove market edge or profitability.

Every result explicitly leaves execution, verified risk state, calibration, rationale semantics
and training export false. The checker is not wired into the paper runner, council permission,
Qwen inputs or training loaders. Output-schema checks, evidence arithmetic and free-text semantic
review remain separate. In particular, **the checker does not parse or grade numeric claims in
Qwen's prose**; a human can compare the facts with the unchanged reply.

## Reproduce offline

Use the ordinary core environment, not `.venv-qwen`. Output files must not already exist:

```powershell
$suitePin = '5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659'
$responsePin = '384e8d199891d396e60d3e1ebceb3637f8c3da8984ccec042facf14bcf9a4f6d'
.venv\Scripts\python.exe -m ai_trader.research.advisory_fact_audit --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --responses logs/qwen_development_v2_20260924_approval3/responses.json --artifact-sha256 $responsePin --output logs/YOUR_NEW_numeric_sidecar.json
.venv\Scripts\python.exe -m ai_trader.research.advisory_fact_audit --suite configs/qwen_review_cases_v1.json --suite-sha256 $suitePin --curriculum-review --output logs/YOUR_NEW_curriculum_fact_review.json
```

Input files require exact SHA256 pins and the existing bounded strict-JSON loader. Outputs are
bounded at 2 MiB and created exclusively; no overwrite, retry or remote lookup occurs. Exit zero
means a report was written, **not** that a model or curriculum passed review. A failed write may
leave an incomplete output; inspect it and use a new path rather than silently overwriting it.

The sidecar preserves the original `model_score` in full and adds `numerical_checks`. Only
input-bound, schema-valid model reports are compared. Invalid/missing/failed/misbound outputs
and preflight refusals are `not_comparable`, never repaired or credited. `model_support_conflict_count`
counts valid-model supports opposed by the numeric rubric, not all unsafe text or total failures.
`combined_pass_or_promotion_metric` is null; there is no composite "improved Qwen" score.

The curriculum packet includes only the 14 `curriculum_draft` cases, excluding all 11 development
cases and their families/sessions. Model-visible input, numerical facts and original draft target
are distinct fields. Calculation happens before comparison with the draft verdict; disagreement
is flagged rather than corrected. All rows remain `operator_review: pending` and
`training_eligible: false`, even when their draft verdict matches. This is human review material,
not an SFT dataset, an approved training export or an input to a model. Never feed the whole packet
as a prompt: its review fields contain targets. Future refused curriculum cases remain visible
with no reference target and no training eligibility.

## Recorded artifact audit (2026-09-24)

Generated these reports by reading the two existing approved recordings; **zero new model calls**.
Both embedded scores exactly reproduce the separately SHA-pinned original score files.

- V1: five valid support replies conflict with numeric vetoes; the two positive controls agree.
  Eighteen remaining cases are not comparable (14 uninvoked curriculum and four preflight cases).
- V2: four valid vetoes agree. Twenty-one cases are not comparable: 14 uninvoked, four preflight,
  and three invalid model reports. Zero valid-support conflicts is not a safety pass; an invalid
  reply still expressed unsupported support. Original full model checks remain **1/7**, versus
  V1's **2/7**. Neither experiment is promoted.
- For `g006_a`, exact net is **35 − 30 = +5 bps**, costs do not exceed gross, and **−4-bps stress**
  independently vetoes. This fact summary does not repair the recorded false explanation or
  claim automatic prose-error detection.
- Across all 25 declared cases, the numeric rubric yields five conditional supports, 16 vetoes
  and four input refusals. This synthetic coverage is not evidence of market prediction quality.
  All 14 curriculum draft verdicts match their numeric checks, but human semantic review remains.

Local Git-ignored outputs and raw-file SHA256 pins:

| Artifact under `logs/` | SHA256 |
| --- | --- |
| `qwen_development_20260924_approval2_numeric_sidecar.json` | `6b83b87f2d9f15f2b005fd5f0d86a4d585b5758d8e1ab30a0bfccf09fe15025e` |
| `qwen_development_v2_20260924_approval3_numeric_sidecar.json` | `528dca9228f0070df32cf34f6f026cb05d043dcef2c85372cbc39f64bc54f4b5` |
| `qwen_curriculum_fact_review_20260924.json` | `d0cefeab0bc3585fb940037064add356679c4c5f3b1b8cef8fb2f048781b8d7c` |

Source response/score pins and interpretation remain in the
[V1 evaluation record](QWEN_ADVISORY_EVALUATION.md) and [V2 comparison](QWEN_REVIEW_CONTRACTS.md).
No frozen prompt, target, suite or model checkpoint was changed for this audit.

## Next gate

The [versioned curriculum review workflow](QWEN_CURRICULUM_APPROVAL.md) is now implemented, with
14 agent-reviewed target proposals and pending operator decisions. Candidate export requires
explicit case decisions/semantic attestations; no real candidate has been approved or exported.
Next: resolve operator review and protect evaluation data before enabling actual training. Consider a
separate structured-claim contract for machine-checkable explanations; do not retroactively
change V1/V2 replies or scores. A bounded adapter-training environment/trial still requires its
own resource approval and save/reload/evaluation checks. The quarantined public capture remains
ineligible; this synthetic language-review work does not provide market data or tactical edge.
