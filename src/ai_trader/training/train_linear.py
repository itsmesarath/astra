"""Train and evaluate a class-balanced linear direction baseline."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from ai_trader.models.linear_classifier import (
    LinearDirectionClassifier,
    calculate_class_weights,
    decode_directions,
    encode_directions,
)
from ai_trader.training.evaluate_majority import (
    find_latest_split_directory,
    print_evaluation,
)
from ai_trader.training.metrics import (
    ClassificationReport,
    evaluate_classification,
)
from ai_trader.training.model_data import (
    ModelPartition,
    load_model_partition,
)
from ai_trader.training.standardize import (
    Standardizer,
    fit_standardizer,
)


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """Hyperparameters for the linear baseline."""

    max_epochs: int = 500
    patience: int = 50
    learning_rate: float = 0.01
    weight_decay: float = 0.0001
    class_weight_power: float = 1.0
    seed: int = 42
    device: str = "auto"


@dataclass(frozen=True, slots=True)
class LinearFitResult:
    """Result of fitting and selecting a model with validation data only."""

    model: LinearDirectionClassifier
    standardizer: Standardizer
    best_epoch: int
    epochs_trained: int
    class_weights: np.ndarray
    validation: ClassificationReport
    device: str


@dataclass(frozen=True, slots=True)
class LinearTrainingResult(LinearFitResult):
    """Validation-selected result with one final test evaluation."""

    test: ClassificationReport


def validate_config(config: TrainingConfig) -> None:
    """Reject invalid training hyperparameters."""
    if config.max_epochs <= 0:
        raise ValueError("Maximum epochs must be greater than zero.")
    if config.patience <= 0:
        raise ValueError("Patience must be greater than zero.")
    if config.learning_rate <= 0:
        raise ValueError("Learning rate must be greater than zero.")
    if config.weight_decay < 0:
        raise ValueError("Weight decay cannot be negative.")
    if not 0 <= config.class_weight_power <= 1:
        raise ValueError("Class-weight power must be between zero and one.")
    if config.seed < 0:
        raise ValueError("Random seed cannot be negative.")
    if config.device not in {"auto", "cpu", "cuda"}:
        raise ValueError("Device must be 'auto', 'cpu', or 'cuda'.")


def resolve_device(requested: str) -> torch.device:
    """Resolve an explicit or automatic PyTorch device."""
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available.")
    return torch.device(requested)


def set_reproducible_seed(seed: int) -> None:
    """Seed NumPy and PyTorch random-number generators."""
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def to_feature_tensor(
    features: np.ndarray,
    device: torch.device,
) -> torch.Tensor:
    """Convert standardized NumPy features to float32 tensors."""
    values = np.asarray(features, dtype=np.float32)
    return torch.from_numpy(values).to(device)


def to_target_tensor(
    targets: np.ndarray,
    device: torch.device,
) -> torch.Tensor:
    """Encode direction labels and move them to a device."""
    encoded = encode_directions(targets)
    return torch.from_numpy(encoded).to(device)


def predict_directions(
    model: LinearDirectionClassifier,
    features: torch.Tensor,
) -> np.ndarray:
    """Return decoded direction predictions."""
    probabilities = predict_probabilities(model, features)
    class_indices = probabilities.argmax(axis=1)
    return decode_directions(class_indices)


def predict_probabilities(
    model: LinearDirectionClassifier,
    features: torch.Tensor,
) -> np.ndarray:
    """Return DOWN, NEUTRAL, and UP probabilities."""
    model.eval()

    with torch.no_grad():
        logits = model(features)
        probabilities = torch.softmax(logits, dim=1)

    return probabilities.detach().cpu().numpy()


def evaluate_model(
    model: LinearDirectionClassifier,
    features: torch.Tensor,
    actual_targets: np.ndarray,
) -> ClassificationReport:
    """Evaluate a model on one partition."""
    predicted_targets = predict_directions(model, features)
    return evaluate_classification(
        actual_targets.tolist(),
        predicted_targets.tolist(),
    )


def clone_state_dict(
    model: nn.Module,
) -> dict[str, torch.Tensor]:
    """Copy model parameters to independent CPU tensors."""
    return {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}


def soften_class_weights(
    class_weights: np.ndarray,
    power: float,
) -> np.ndarray:
    """Reduce inverse-frequency weighting while preserving class order."""
    if not 0 <= power <= 1:
        raise ValueError("Class-weight power must be between zero and one.")

    return np.power(
        np.asarray(class_weights, dtype=np.float32),
        power,
    ).astype(np.float32, copy=False)


def fit_linear_baseline(
    train: ModelPartition,
    validation: ModelPartition,
    config: TrainingConfig,
) -> LinearFitResult:
    """Train on earlier data and select an epoch using validation only."""
    validate_config(config)

    if train.columns != validation.columns:
        raise ValueError("Train and validation feature counts must match.")
    if bool(train.feature_names) != bool(validation.feature_names):
        raise ValueError("Train and validation feature schemas must both be identified.")
    if train.feature_names != validation.feature_names:
        raise ValueError("Train and validation feature schemas must match.")

    set_reproducible_seed(config.seed)
    device = resolve_device(config.device)

    standardizer = fit_standardizer(train.features)
    standardized_train = standardizer.transform(train.features)
    standardized_validation = standardizer.transform(validation.features)

    train_features = to_feature_tensor(
        standardized_train,
        device,
    )
    validation_features = to_feature_tensor(
        standardized_validation,
        device,
    )
    train_targets = to_target_tensor(train.targets, device)

    class_weights = soften_class_weights(
        calculate_class_weights(train.targets),
        config.class_weight_power,
    )
    weight_tensor = torch.from_numpy(class_weights).to(device)

    model = LinearDirectionClassifier(input_features=train.columns).to(device)

    loss_function = nn.CrossEntropyLoss(
        weight=weight_tensor,
    )
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    best_state: dict[str, torch.Tensor] | None = None
    best_validation_score = float("-inf")
    best_epoch = 0
    epochs_without_improvement = 0
    epochs_trained = 0

    for epoch in range(1, config.max_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)

        logits = model(train_features)
        loss = loss_function(logits, train_targets)
        loss.backward()
        optimizer.step()

        validation_report = evaluate_model(
            model,
            validation_features,
            validation.targets,
        )
        validation_score = validation_report.macro_f1
        epochs_trained = epoch

        if validation_score > best_validation_score + 1e-12:
            best_validation_score = validation_score
            best_state = clone_state_dict(model)
            best_epoch = epoch
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= config.patience:
            break

    if best_state is None:
        raise RuntimeError("Training did not produce a model checkpoint.")

    model.load_state_dict(best_state)
    model.to(device)

    final_validation_report = evaluate_model(
        model,
        validation_features,
        validation.targets,
    )
    return LinearFitResult(
        model=model,
        standardizer=standardizer,
        best_epoch=best_epoch,
        epochs_trained=epochs_trained,
        class_weights=class_weights,
        validation=final_validation_report,
        device=str(device),
    )


def train_linear_baseline(
    train: ModelPartition,
    validation: ModelPartition,
    test: ModelPartition,
    config: TrainingConfig,
) -> LinearTrainingResult:
    """Train on train, select on validation, then evaluate test once."""
    if not (train.columns == validation.columns == test.columns):
        raise ValueError("Train, validation, and test feature counts must match.")
    feature_schemas = [partition.feature_names for partition in (train, validation, test)]
    if any(feature_schemas) and not all(feature_schemas):
        raise ValueError("Train, validation, and test feature schemas must all be identified.")
    named_schemas = {schema for schema in feature_schemas if schema}
    if len(named_schemas) > 1:
        raise ValueError("Train, validation, and test feature schemas must match.")

    fit = fit_linear_baseline(train, validation, config)
    device = resolve_device(fit.device)
    standardized_test = fit.standardizer.transform(test.features)
    test_features = to_feature_tensor(standardized_test, device)
    test_report = evaluate_model(
        fit.model,
        test_features,
        test.targets,
    )

    return LinearTrainingResult(
        model=fit.model,
        standardizer=fit.standardizer,
        best_epoch=fit.best_epoch,
        epochs_trained=fit.epochs_trained,
        class_weights=fit.class_weights,
        validation=fit.validation,
        device=fit.device,
        test=test_report,
    )


def parse_args() -> argparse.Namespace:
    """Read training command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "split_directory",
        nargs="?",
        type=Path,
        help="Split directory; defaults to the newest complete split.",
    )
    parser.add_argument(
        "--max-epochs",
        type=int,
        default=500,
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
    )
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.01,
    )
    parser.add_argument(
        "--weight-decay",
        type=float,
        default=0.0001,
    )
    parser.add_argument(
        "--class-weight-power",
        type=float,
        default=1.0,
        help=("Inverse-frequency weight exponent from 0 (unweighted) to 1 (fully balanced)."),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
    )
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
    )
    return parser.parse_args()


def main() -> None:
    """Train and evaluate the linear baseline."""
    args = parse_args()
    split_directory = args.split_directory or find_latest_split_directory()

    print(f"Loading split: {split_directory.resolve()}")

    train = load_model_partition(split_directory / "train.csv")
    validation = load_model_partition(split_directory / "validation.csv")
    test = load_model_partition(split_directory / "test.csv")

    config = TrainingConfig(
        max_epochs=args.max_epochs,
        patience=args.patience,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        class_weight_power=args.class_weight_power,
        seed=args.seed,
        device=args.device,
    )

    result = train_linear_baseline(
        train,
        validation,
        test,
        config,
    )

    print(f"Device: {result.device}")
    print(f"Training class weights (DOWN, NEUTRAL, UP): {result.class_weights.tolist()}")
    print(f"Best epoch: {result.best_epoch}")
    print(f"Epochs trained: {result.epochs_trained}")

    print_evaluation("Validation", result.validation)
    print_evaluation("Test", result.test)


if __name__ == "__main__":
    main()
