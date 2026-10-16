"""Opt-in, registered NumPy event baseline; no execution, promotion or reserved reads.

Fixed-epoch training uses only training rows. Validation never selects weights,
preprocessing, epochs, thresholds or features. Outputs are research artifacts.
"""

import argparse
import json
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from ai_trader.research.microstructure_trial import load_registration
from ai_trader.trading.capture_replay import _digest
from ai_trader.trading.paper_lifecycle import _money
from ai_trader.training.event_training_data import (
    FEATURE_NAMES,
    MAX_MANIFEST_BYTES,
    EventDatasetInput,
    EventPartition,
    _check_current,
    _load_manifest,
    _read_envelope,
    load_event_split,
)
from ai_trader.training.metrics import CLASS_LABELS, evaluate_classification
from ai_trader.training.microstructure_data import _hash, _json, _publish
from ai_trader.training.standardize import fit_standardizer

BASELINE_VERSION = "numpy_event_softmax_v1"
MAX_ROW_EPOCHS = 2_000_000
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_RAW_MAGNITUDE = 1e100
STANDARDIZED_CLIP = 10.0
LOG_FLOOR = 1e-15
INPUT_COLUMNS = len(FEATURE_NAMES)
MODEL_COLUMNS = 2 * INPUT_COLUMNS


@dataclass(frozen=True, slots=True)
class EventBaselineConfig:
    epochs: int
    learning_rate: Decimal
    l2: Decimal

    def __post_init__(self):
        if type(self.epochs) is not int or not 1 <= self.epochs <= 1000:
            raise ValueError("Epoch budget must be an integer in [1, 1000].")
        _money(self.learning_rate)
        _money(self.l2, zero=True)
        if self.learning_rate > 1 or self.l2 > 1:
            raise ValueError("Learning rate and L2 must not exceed one.")


def _recipe(registration, manifest, config):
    if type(config) is not EventBaselineConfig:
        raise ValueError("Typed event-baseline configuration required.")
    row_budget = manifest["max_frames_per_session"] * len(manifest["train_sessions"])
    if row_budget * config.epochs > MAX_ROW_EPOCHS:
        raise ValueError("Declared training rows times epochs exceeds compute budget.")
    return {
        "schema_version": 1,
        "artifact_type": "event_baseline_recipe",
        "baseline_version": BASELINE_VERSION,
        "registration_sha256": registration.sha256,
        "manifest_sha256": _hash(_json(manifest)),
        "implementation_sha256": registration.implementation_sha256,
        "environment_json": registration.environment_json,
        "configuration": json.loads(_json(asdict(config))),
        "feature_names": list(FEATURE_NAMES),
        "class_order": list(CLASS_LABELS),
        "class_meaning": ["net_loss", "exact_net_breakeven", "net_profit"],
        "preprocessing": "train_median_then_missing_indicators_then_train_population_standardizer",
        "all_missing_train_column": "median_zero_and_value_channel_inactive",
        "constant_train_channel": "inactive_zero_in_all_partitions",
        "standardized_clip": STANDARDIZED_CLIP,
        "maximum_raw_magnitude": MAX_RAW_MAGNITUDE,
        "optimizer": "float64_full_batch_gradient_descent_zero_initialization",
        "objective": "unweighted_mean_cross_entropy_plus_half_l2_weight_norm_squared",
        "epoch_selection": "fixed_budget_no_validation_selection",
        "minimum_training_classes": 2,
        "controls": ["train_majority", "train_laplace_prior", "uniform"],
        "metrics": "classification_log_loss_multiclass_brier_top_label_ece_10_bins",
        "log_loss_floor": LOG_FLOOR,
        "mode": "research_only",
        "promotion_allowed": False,
        "live_trading_available": False,
    }


def register_event_baseline(
    *, registration_path: Path, manifest_path: Path, output_path: Path, config: EventBaselineConfig
) -> dict:
    """Freeze the full baseline recipe using metadata only, before outcomes are inspected."""
    registration = load_registration(registration_path)
    manifest = _load_manifest(manifest_path, registration)
    recipe = _recipe(registration, manifest, config)
    _check_current(registration)
    _publish(recipe, output_path, payload_name="manifest", max_bytes=MAX_MANIFEST_BYTES)
    return recipe


def _decode_config(config):
    if (
        type(config) is not dict
        or set(config) != {"epochs", "learning_rate", "l2"}
        or type(config["learning_rate"]) is not str
        or type(config["l2"]) is not str
    ):
        raise ValueError("Invalid baseline recipe configuration.")
    try:
        return EventBaselineConfig(
            config["epochs"], Decimal(config["learning_rate"]), Decimal(config["l2"])
        )
    except InvalidOperation as error:
        raise ValueError("Invalid baseline recipe decimals.") from error


def _load_recipe(path, registration, manifest):
    recipe, _ = _read_envelope(path, "manifest", MAX_MANIFEST_BYTES)
    settings = _decode_config(recipe.get("configuration"))
    if _json(recipe) != _json(_recipe(registration, manifest, settings)):
        raise ValueError("Recipe differs from the frozen split or current baseline protocol.")
    return recipe, settings


def _features(partition):
    if (
        type(partition) is not EventPartition
        or partition.feature_names != FEATURE_NAMES
        or type(partition.X) is not tuple
        or not 1 <= len(partition.X) <= 10_000
        or any(type(row) is not tuple or len(row) != INPUT_COLUMNS for row in partition.X)
    ):
        raise ValueError("Expected bounded event partition with the exact ordered feature schema.")
    for row in partition.X:
        for value in row:
            if value is not None and (
                type(value) not in (int, bool, Decimal)
                or (isinstance(value, Decimal) and not value.is_finite())
            ):
                raise ValueError("Only finite Decimal/int/bool features or explicit None allowed.")
    try:
        matrix = np.asarray(partition.X, dtype=np.float64)
    except (ValueError, OverflowError) as error:
        raise ValueError("Event features exceed numerical bounds.") from error
    observed = matrix[~np.isnan(matrix)]
    if not np.isfinite(observed).all() or np.any(np.abs(observed) > MAX_RAW_MAGNITUDE):
        raise ValueError("Event features exceed numerical bounds.")
    return matrix


def _targets(partition):
    if (
        type(partition.direction) is not tuple
        or len(partition.direction) != len(partition.X)
        or any(type(v) is not int or v not in CLASS_LABELS for v in partition.direction)
    ):
        raise ValueError("Expected one integer direction target per event row.")
    return np.asarray(partition.direction, dtype=np.int64) + 1


@dataclass(frozen=True, slots=True)
class EventBaselineModel:
    medians: tuple[float, ...]
    means: tuple[float, ...]
    scales: tuple[float, ...]
    active: tuple[bool, ...]
    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]

    def __post_init__(self):
        for vector, size in (
            (self.medians, INPUT_COLUMNS),
            (self.means, MODEL_COLUMNS),
            (self.scales, MODEL_COLUMNS),
            (self.bias, 3),
        ):
            if (
                type(vector) is not tuple
                or len(vector) != size
                or any(type(v) is not float or not np.isfinite(v) for v in vector)
            ):
                raise ValueError("Invalid event model parameter vector.")
        if any(v <= 0 for v in self.scales):
            raise ValueError("Model scales must be positive.")
        if (
            type(self.active) is not tuple
            or len(self.active) != MODEL_COLUMNS
            or any(type(v) is not bool for v in self.active)
            or type(self.weights) is not tuple
            or len(self.weights) != MODEL_COLUMNS
            or any(
                type(row) is not tuple
                or len(row) != 3
                or any(type(v) is not float or not np.isfinite(v) for v in row)
                for row in self.weights
            )
        ):
            raise ValueError("Invalid event model weight shape or active channels.")

    def transform(self, partition):
        matrix = _features(partition)
        missing = np.isnan(matrix)
        expanded = np.column_stack((np.where(missing, self.medians, matrix), missing.astype(float)))
        try:
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                result = (expanded - self.means) / self.scales
        except FloatingPointError as error:
            raise ValueError("Preprocessing exceeded numerical bounds.") from error
        result[:, ~np.asarray(self.active)] = 0.0
        return np.clip(result, -STANDARDIZED_CLIP, STANDARDIZED_CLIP)

    def predict_probabilities(self, partition):
        return _softmax(self.transform(partition), np.asarray(self.weights), np.asarray(self.bias))


def _softmax(matrix, weights, bias):
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise", under="ignore"):
            scores = matrix @ weights + bias
            scores -= scores.max(axis=1, keepdims=True)
            exp = np.exp(scores)
            probabilities = exp / exp.sum(axis=1, keepdims=True)
    except FloatingPointError as error:
        raise ValueError("Model produced non-finite probabilities.") from error
    if not np.isfinite(probabilities).all():
        raise ValueError("Model produced non-finite probabilities.")
    return probabilities


def _cross_entropy(encoded, probabilities):
    return float(
        -np.log(np.maximum(probabilities[np.arange(len(encoded)), encoded], LOG_FLOOR)).mean()
    )


def _fit(train, config):
    """Internal numerical primitive: no validation argument and no random/global RNG state."""
    matrix, encoded = _features(train), _targets(train)
    if len(np.unique(encoded)) < 2:
        raise ValueError("At least two observed training classes are required.")
    if len(matrix) * config.epochs > MAX_ROW_EPOCHS:
        raise ValueError("Training row-epoch compute budget exceeded.")
    missing = np.isnan(matrix)
    medians = np.asarray(
        [
            float(np.median(matrix[~missing[:, i], i])) if (~missing[:, i]).any() else 0.0
            for i in range(INPUT_COLUMNS)
        ]
    )
    expanded = np.column_stack((np.where(missing, medians, matrix), missing.astype(float)))
    standardizer = fit_standardizer(expanded)
    active = np.any(expanded != expanded[0], axis=0)
    x = np.clip(standardizer.transform(expanded), -STANDARDIZED_CLIP, STANDARDIZED_CLIP)
    x[:, ~active] = 0.0
    weights, bias = np.zeros((MODEL_COLUMNS, 3)), np.zeros(3)
    initial_loss = _cross_entropy(encoded, _softmax(x, weights, bias))
    rate, penalty = float(config.learning_rate), float(config.l2)
    for _ in range(config.epochs):
        residual = _softmax(x, weights, bias)
        residual[np.arange(len(encoded)), encoded] -= 1.0
        weights -= rate * (x.T @ residual / len(encoded) + penalty * weights)
        bias -= rate * residual.mean(axis=0)
        if not np.isfinite(weights).all() or not np.isfinite(bias).all():
            raise ValueError("Optimizer exceeded numerical bounds.")
    model = EventBaselineModel(
        tuple(medians.tolist()),
        tuple(standardizer.means.tolist()),
        tuple(standardizer.scales.tolist()),
        tuple(active.tolist()),
        tuple(tuple(row) for row in weights.tolist()),
        tuple(bias.tolist()),
    )
    return model, {
        "epochs_completed": config.epochs,
        "training_rows": len(encoded),
        "training_class_counts": np.bincount(encoded, minlength=3).tolist(),
        "initial_training_cross_entropy": initial_loss,
        "final_training_cross_entropy": _cross_entropy(encoded, model.predict_probabilities(train)),
        "active_model_channels": int(active.sum()),
        "all_missing_train_features": [
            FEATURE_NAMES[i] for i in range(INPUT_COLUMNS) if missing[:, i].all()
        ],
    }


def _metrics(encoded, probabilities):
    if (
        probabilities.shape != (len(encoded), 3)
        or not np.isfinite(probabilities).all()
        or np.any(probabilities < 0)
        or np.any(probabilities > 1)
        or not np.allclose(probabilities.sum(axis=1), 1, rtol=0, atol=1e-12)
    ):
        raise ValueError("Expected normalized three-class probabilities.")
    predicted = probabilities.argmax(axis=1)
    classification = evaluate_classification((encoded - 1).tolist(), (predicted - 1).tolist())
    confidence = probabilities.max(axis=1)
    bins = np.minimum((confidence * 10).astype(int), 9)
    reliability, ece = [], 0.0
    for i in range(10):
        mask = bins == i
        count = int(mask.sum())
        accuracy = float((predicted[mask] == encoded[mask]).mean()) if count else None
        mean_confidence = float(confidence[mask].mean()) if count else None
        if count:
            ece += count * abs(accuracy - mean_confidence) / len(encoded)
        reliability.append(
            {
                "lower": i / 10,
                "upper": (i + 1) / 10,
                "count": count,
                "accuracy": accuracy,
                "mean_confidence": mean_confidence,
            }
        )
    return {
        **asdict(classification),
        "missing_actual_classes": list(classification.missing_actual_classes),
        "log_loss": _cross_entropy(encoded, probabilities),
        "brier_score": float(((probabilities - np.eye(3)[encoded]) ** 2).sum(axis=1).mean()),
        "top_label_ece": float(ece),
        "reliability_bins": reliability,
    }


def _prediction_probabilities(model, train, validation):
    """Frozen controls and model predictions, independent of validation targets."""
    count = len(validation.X)
    counts = np.bincount(_targets(train), minlength=3)
    return {
        "model": model.predict_probabilities(validation),
        "train_majority": np.tile(np.eye(3)[counts.argmax()], (count, 1)),
        "train_laplace_prior": np.tile((counts + 1) / (counts.sum() + 3), (count, 1)),
        "uniform": np.full((count, 3), 1 / 3),
    }


def _score_predictions(validation, probabilities):
    encoded = _targets(validation)
    sessions = tuple(dict.fromkeys(validation.source_sessions))
    session_ids = np.asarray(validation.source_sessions)
    return {
        "aggregate": {name: _metrics(encoded, p) for name, p in probabilities.items()},
        "by_session": [
            {
                "source_session": session,
                "metrics": {
                    name: _metrics(encoded[session_ids == session], p[session_ids == session])
                    for name, p in probabilities.items()
                },
            }
            for session in sessions
        ],
        "predictions": [
            {
                "example_id": identifier,
                "source_session": session,
                "available_at_ns": available,
                "known_at_ns": known,
                "actual_direction": int(actual - 1),
                "probabilities": p.tolist(),
            }
            for identifier, session, available, known, actual, p in zip(
                validation.example_ids,
                validation.source_sessions,
                validation.available_at_ns,
                validation.known_at_ns,
                encoded,
                probabilities["model"],
                strict=True,
            )
        ],
    }


def _evaluate(model, train, validation):
    return _score_predictions(validation, _prediction_probabilities(model, train, validation))


def _model_payload(model):
    return {
        "baseline_version": BASELINE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "class_order": list(CLASS_LABELS),
        "parameters": asdict(model),
    }


def train_registered_event_baseline(
    *,
    registration_path: Path,
    manifest_path: Path,
    recipe_path: Path,
    sources: tuple[EventDatasetInput, ...],
    output_path: Path,
    enable_training: bool = False,
) -> dict:
    """One explicit offline research run; source reproduction and fold gates precede fitting."""
    if enable_training is not True:
        raise ValueError("Explicit enable_training=True is required on every training call.")
    output_path = Path(output_path)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    registration = load_registration(registration_path)
    manifest = _load_manifest(manifest_path, registration)
    recipe, config = _load_recipe(recipe_path, registration, manifest)
    fold = load_event_split(
        registration_path=registration_path, manifest_path=manifest_path, sources=sources
    )
    if fold.report["manifest_sha256"] != recipe["manifest_sha256"]:
        raise ValueError("Split changed after baseline recipe validation.")
    model = fitting = evaluation = None
    status = "blocked_source_quality"
    if fold.report["fold_available"]:
        status = "blocked_training_classes"
        counts = np.bincount(_targets(fold.train), minlength=3).tolist()
        fitting = {"epochs_completed": 0, "training_class_counts": counts}
        if sum(c > 0 for c in counts) >= 2:
            model, fitting = _fit(fold.train, config)
            evaluation = _evaluate(model, fold.train, fold.validation)
            status = "completed"
    _check_current(registration)
    result = {
        "schema_version": 1,
        "artifact_type": "event_baseline_research_run",
        "status": status,
        "recipe_sha256": _hash(_json(recipe)),
        "recipe": recipe,
        "fold_verification": fold.report,
        "model": None if model is None else _model_payload(model),
        "fit": fitting,
        "validation": evaluation,
        "training_started": model is not None,
        "mode": "research_only",
        "promotion_allowed": False,
        "live_trading_available": False,
        "limitation": (
            "Fixed-split predictive research, not paper execution or trading profitability. "
            "Overlapping outcomes are dependent; event counts are not independent trials. "
            "Calibration diagnostics do not establish calibrated probabilities. "
            "No automatic promotion, test-set access, Qwen training or online learning."
        ),
    }
    result = json.loads(_json(result))
    _publish(result, output_path, payload_name="report", max_bytes=MAX_RESULT_BYTES)
    return result


def _load_completed_result(path: Path, *, expected_sha256: str):
    """Read one pinned completed result once, including validated data-only parameters."""
    _digest(expected_sha256)
    result, _ = _read_envelope(path, "report", MAX_RESULT_BYTES)
    if _hash(_json(result)) != expected_sha256:
        raise ValueError("Baseline result differs from the pinned checksum.")
    if (
        type(result.get("schema_version")) is not int
        or result.get("schema_version") != 1
        or result.get("artifact_type") != "event_baseline_research_run"
        or result.get("status") != "completed"
        or result.get("training_started") is not True
        or result.get("mode") != "research_only"
        or result.get("promotion_allowed") is not False
        or result.get("live_trading_available") is not False
    ):
        raise ValueError("Only completed research baseline parameters may be loaded.")
    return result, _model_from_payload(result.get("model"))


def _model_from_payload(payload):
    if type(payload) is not dict or type(payload.get("parameters")) is not dict:
        raise ValueError("Missing data-only model parameters.")
    values = payload["parameters"]
    if set(values) != {f.name for f in fields(EventBaselineModel)}:
        raise ValueError("Invalid event model fields.")
    if any(type(v) is not list for v in values.values()) or any(
        type(v) is not list for v in values["weights"]
    ):
        raise ValueError("Model parameters must be JSON arrays.")
    model = EventBaselineModel(
        **{
            k: tuple(tuple(row) for row in v) if k == "weights" else tuple(v)
            for k, v in values.items()
        }
    )
    if _json(payload) != _json(_model_payload(model)):
        raise ValueError("Model schema/version differs from the current baseline.")
    return model


def load_event_baseline_model(path: Path, *, expected_sha256: str) -> EventBaselineModel:
    """Read data-only parameters against a caller-pinned result digest; never pickle/code."""
    return _load_completed_result(path, expected_sha256=expected_sha256)[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="Freeze recipe from metadata; no fitting.")
    register.add_argument("--epochs", type=int, required=True)
    register.add_argument("--learning-rate", type=Decimal, required=True)
    register.add_argument("--l2", type=Decimal, required=True)
    train = commands.add_parser("train", help="Explicitly opt in to bounded research training.")
    train.add_argument("--recipe", type=Path, required=True)
    train.add_argument(
        "--source",
        nargs=3,
        action="append",
        required=True,
        metavar=("SESSION", "CAPTURE", "DATASET"),
    )
    train.add_argument("--enable-training", action="store_true")
    for command in (register, train):
        command.add_argument("--registration", type=Path, required=True)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        recipe = register_event_baseline(
            registration_path=args.registration,
            manifest_path=args.manifest,
            output_path=args.output,
            config=EventBaselineConfig(args.epochs, args.learning_rate, args.l2),
        )
        print(json.dumps({"recipe_sha256": _hash(_json(recipe)), "training_started": False}))
    else:
        result = train_registered_event_baseline(
            registration_path=args.registration,
            manifest_path=args.manifest,
            recipe_path=args.recipe,
            sources=tuple(EventDatasetInput(s, Path(c), Path(d)) for s, c, d in args.source),
            output_path=args.output,
            enable_training=args.enable_training,
        )
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "training_started": result["training_started"],
                    "result_sha256": _hash(_json(result)),
                    "promotion_allowed": False,
                }
            )
        )
        if result["status"] != "completed":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
