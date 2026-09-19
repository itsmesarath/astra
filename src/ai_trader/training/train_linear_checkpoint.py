"""Train, evaluate, and save a versioned linear checkpoint."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ai_trader.models.checkpoint import save_linear_checkpoint
from ai_trader.training.evaluate_majority import (
    find_latest_split_directory,
    print_evaluation,
)
from ai_trader.training.metrics import ClassificationReport
from ai_trader.training.model_data import load_model_partition
from ai_trader.training.train_linear import (
    LinearFitResult,
    TrainingConfig,
    fit_linear_baseline,
)

DEFAULT_CHECKPOINT_DIRECTORY = Path("checkpoints")


def classification_report_to_dict(
    report: ClassificationReport,
) -> dict[str, object]:
    """Convert classification metrics into JSON-safe metadata."""
    return {
        "total": report.total,
        "correct": report.correct,
        "accuracy": report.accuracy,
        "balanced_accuracy": report.balanced_accuracy,
        "macro_f1": report.macro_f1,
        "missing_actual_classes": list(report.missing_actual_classes),
        "confusion_matrix": [list(row) for row in report.confusion_matrix],
        "classes": [
            {
                "label": metrics.label,
                "support": metrics.support,
                "predicted": metrics.predicted,
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1": metrics.f1,
            }
            for metrics in report.classes
        ],
    }


def create_checkpoint_path(
    *,
    created_at: datetime | None = None,
) -> Path:
    """Create a UTC-stamped default checkpoint path."""
    timestamp = created_at or datetime.now(UTC)

    if timestamp.tzinfo is None:
        raise ValueError("Checkpoint timestamp must include a timezone.")

    timestamp_text = timestamp.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_CHECKPOINT_DIRECTORY / f"linear_{timestamp_text}"


def create_training_metadata(
    *,
    split_directory: Path,
    config: TrainingConfig,
    result: LinearFitResult,
    created_at: datetime,
) -> dict[str, object]:
    """Create complete JSON-safe training metadata."""
    if created_at.tzinfo is None:
        raise ValueError("Training timestamp must include a timezone.")

    return {
        "created_at_utc": (created_at.astimezone(UTC).isoformat()),
        "source_split_directory": str(split_directory.resolve()),
        "configuration": asdict(config),
        "device": result.device,
        "best_epoch": result.best_epoch,
        "epochs_trained": result.epochs_trained,
        "class_weights": result.class_weights.tolist(),
        "validation": classification_report_to_dict(result.validation),
    }


def parse_args() -> argparse.Namespace:
    """Read training and checkpoint arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "split_directory",
        nargs="?",
        type=Path,
        help="Split directory; defaults to the newest complete split.",
    )
    parser.add_argument(
        "--checkpoint-directory",
        type=Path,
        help="Optional exact output checkpoint directory.",
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
    """Train, evaluate, and save one linear checkpoint."""
    args = parse_args()
    split_directory = args.split_directory or find_latest_split_directory()
    checkpoint_directory = args.checkpoint_directory or create_checkpoint_path()

    config = TrainingConfig(
        max_epochs=args.max_epochs,
        patience=args.patience,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        class_weight_power=args.class_weight_power,
        seed=args.seed,
        device=args.device,
    )

    print(f"Loading split: {split_directory.resolve()}")

    train = load_model_partition(split_directory / "train.csv")
    validation = load_model_partition(split_directory / "validation.csv")

    result = fit_linear_baseline(
        train,
        validation,
        config,
    )

    print(f"Device: {result.device}")
    print(f"Training class weights (DOWN, NEUTRAL, UP): {result.class_weights.tolist()}")
    print(f"Best epoch: {result.best_epoch}")
    print(f"Epochs trained: {result.epochs_trained}")

    print_evaluation("Validation", result.validation)

    created_at = datetime.now(UTC)
    training_metadata = create_training_metadata(
        split_directory=split_directory,
        config=config,
        result=result,
        created_at=created_at,
    )

    saved_path = save_linear_checkpoint(
        checkpoint_directory,
        result.model,
        result.standardizer,
        feature_names=train.feature_names,
        training_metadata=training_metadata,
    )

    print(f"\nCheckpoint saved: {saved_path.resolve()}")


if __name__ == "__main__":
    main()
