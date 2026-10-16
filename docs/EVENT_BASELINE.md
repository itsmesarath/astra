# Registered numerical event baseline

Implemented in `training/train_event_baseline.py`, verified with synthetic training only. This is
an offline research classifier for the [costed event labels](MICROSTRUCTURE_EVENT_LABELS.md), not
Qwen, a trading policy, paper-runtime integration, profitable-strategy evidence or continuous learning.
It uses the existing NumPy dependency and does not import PyTorch, Transformers or a model provider.

## Freeze the recipe, then explicitly opt in

`register_event_baseline` reads a current-code research registration and its
[whole-session split manifest](EVENT_TRAINING_DATA.md), not captures or label rows. It writes an
exclusive recipe binding their checksums, implementation/environment, ordered feature names, class
meaning, preprocessing, optimizer settings, controls and evaluation definitions. Epoch count,
learning rate and L2 penalty are explicit arguments. There is no hyperparameter search or automatic
choice based on validation results. Choose the recipe before inspecting outcomes; checksums and
exclusive files are not proof that an operator has never seen the data or a complete trial registry.

`train_registered_event_baseline` requires `enable_training=True` on **every invocation**, before
any file access. The CLI requires `--enable-training`. All declared research inputs must pass the
existing source reproduction, split, availability, quality and sample gates before fitting. Reserved
sources remain unopened. An existing output or quarantined output partial is refused before fitting.

Training additionally requires at least two observed target classes. It does not require all three:
exact after-cost breakeven may legitimately be absent. Class order is fixed:

```text
[-1, 0, +1] = [net loss, exact modeled breakeven, net profit]
```

These are hypothetical Spot-long outcomes, not candle direction or SELL/HOLD/BUY instructions.
Unknown outcomes are excluded and accounted for by the loader; they never become breakeven targets.
All resolved signs are retained. Positive examples are not preferentially selected or oversampled.

## Training-only preprocessing and optimization

The loader's original feature values and missingness remain unchanged. The baseline recipe creates
a separate model matrix from the 30 allowlisted feature columns:

1. Convert finite Decimal/int/bool values to float64; `None` alone indicates missingness. Reject
   other types, non-finite values and raw magnitudes above `1e100`.
2. Fit one median per feature on observed **training** values. An all-missing training column uses
   zero as a stored placeholder, not a statement that the missing market evidence equals zero.
3. Median-impute and append 30 missing-value indicators, producing 60 fixed model channels.
4. Fit the existing population-mean/standard-deviation standardizer on these training channels.
   Channels constant in training are inactive and forced to zero in every partition. Thus a feature
   absent throughout training cannot unexpectedly become an effective signal in validation.
5. Apply those unchanged statistics to validation/inference and clip standardized values to
   `[-10, 10]`. Missingness patterns learned from training remain distinguishable through indicators.

Fit a three-output softmax linear classifier using zero-initialized float64 weights and bias, full
batch gradient descent and unweighted mean cross-entropy plus half-L2 weight penalty. Bias is not
penalized. The epoch count is fixed; validation does not choose an epoch, features, thresholds,
weights, class balancing or preprocessing. The fit function accepts training data only. There is
no random initialization, global RNG change, checkpoint selection, online update or early stopping.

Model parameters are frozen tuples. Prediction uses only the ordered feature names and X; it does
not read labels, outcome-resolution times, return values or source provenance. This alone does not
make a saved model causally deployable: a future shadow/runtime adapter must enforce model training
cutoffs, feature availability, approved policy version, risk and execution boundaries.

## Evaluation is predictive, not economic

After fitting, evaluate the same validation rows with the model and three predeclared controls:

- Training majority class, with ties resolved in fixed `[-1, 0, +1]` order.
- Training class-frequency probabilities with one Laplace pseudocount per class.
- Uniform probabilities across all three classes.

The majority/prior controls never use validation class frequencies. Report aggregate and per-source
accuracy, confusion matrices, precision/recall/F1 and missing actual classes using the existing
classification metrics. Balanced accuracy averages supported-class recalls; macro-F1 averages all
three classes, including absent ones. Also report:

- Log loss, flooring only the evaluated true-class probability at `1e-15` for finite diagnostics.
- Multiclass Brier score: mean sum of squared probability errors across the three classes, without
  dividing by three (range 0–2).
- Top-label expected calibration error and ten equal-width confidence bins. Empty-bin accuracy
  and confidence stay null; confidence 1 belongs in the last bin.

Validation evidence records example/source IDs, availability and resolution times, actual direction
and model probabilities separately from features. Fit diagnostics record training counts, epochs,
initial/final training cross-entropy, active channels and all-missing training features. Absent
classes and losses remain visible. Calibration diagnostics are not a fitted calibration model or
proof that these probabilities are reliable.

There is **no** trading threshold, selected-trade return, summed hypothetical PnL, Sharpe ratio,
significance claim or automatic promotion. Overlapping labels are dependent; event counts are not
independent trades. Repeated validation-guided changes are additional experiments, not a free final
test. The reserved test set is not exposed by this command.

## Results, limits and reload

The result is one checksummed JSON report containing recipe, fold-verification evidence, numerical
parameters, fit diagnostics and validation metrics/predictions. Publication uses exclusive fsynced
partial staging and atomic no-replacement linking; existing outputs are never overwritten.

- A failed source-quality gate publishes `blocked_source_quality`, with no model or fitting.
- Fewer than two training classes publishes `blocked_training_classes`, with class counts and no fit.
- A successful fit publishes `completed` and `training_started=true`; promotion and live-trading
  flags remain false. This is not a runtime deployment or evidence that paper performance improved.
- Corrupt inputs, code/environment drift, numerical errors or publication failures abort the call;
  no successful final result is published. A failed staging file remains quarantined.

Epochs must be integers from 1–1,000, learning rate in `(0, 1]` and L2 in `[0, 1]`. The declared
training-frame budget times epochs cannot exceed 2,000,000; actual fitting also checks this bound.
Existing fold limits remain 10,000 declared frames, 2–32 research sessions and 64 MiB aggregate source
reads. Recipes use the 1,000,000-byte metadata cap; complete result envelopes are limited to 8 MiB.
These are resource/engineering limits, not statistically sufficient sample sizes.

`load_event_baseline_model(path, expected_sha256=...)` reloads only a completed research artifact
against a caller-pinned **result** checksum. It validates model schema, dimensions, finite parameters,
positive scales and boolean active channels. It reads JSON data only, never pickle or executable
model code. Retain the checksum from the original run in trusted experiment records; a checksum
supplied by the same untrusted file is not authentication. Reloading grants no trading authority.
Synthetic repeat/reload tests verify identical predictions; cross-platform BLAS/hardware bit-for-bit
identity is not promised by the Python/NumPy version fingerprint alone.

## Commands

Safe help and synthetic tests from the repository root:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.train_event_baseline register --help
.venv\Scripts\python.exe -m ai_trader.training.train_event_baseline train --help
.venv\Scripts\python.exe -m pytest -q tests/test_train_event_baseline.py
```

Operator examples only; no actual market-data training was run during development. First freeze a
recipe for an existing current-code research registration and split, before reviewing outcomes:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.train_event_baseline register --registration data/processed/REGISTRATION.json --manifest data/processed/SPLIT.json --output data/processed/NEW_RECIPE.json --epochs 50 --learning-rate 0.05 --l2 0.001
```

After approved research captures/artifacts meet meaningful predeclared quality/sample gates, this
explicit opt-in command starts a real numerical fit. The example filenames/settings are placeholders,
not a recommendation that a particular dataset is sufficient:

```powershell
.venv\Scripts\python.exe -m ai_trader.training.train_event_baseline train --registration data/processed/REGISTRATION.json --manifest data/processed/SPLIT.json --recipe data/processed/NEW_RECIPE.json --source RESEARCH_ONE data/raw/ONE.jsonl data/processed/ONE_LABELS.json --source RESEARCH_TWO data/raw/TWO.jsonl data/processed/TWO_LABELS.json --output data/processed/NEW_BASELINE_RESULT.json --enable-training
```

CLI output is a compact status/checksum, not the prediction matrix. Exit 0 means the fit completed;
exit 2 means a diagnostic blocked result was published. Neither means profitable or deployment-ready.

[Registered walk-forward evaluation](EVENT_WALK_FORWARD.md) now reuses this fixed recipe across
expanding earlier-session prefixes, with once-only later-session predictions and explicit blocked
fold accounting. A [sealed model shadow adapter](EVENT_SHADOW.md) now records predictions without
orders on strictly later research sources. Real-data readiness must be reviewed before fitting
actual captures. Qwen fine-tuning, paper promotion, a supervised
forward service and live connectivity are not implemented by this slice.
