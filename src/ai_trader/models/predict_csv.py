"""Run a saved linear checkpoint on causal feature CSV rows."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ai_trader.models.checkpoint import (
    LoadedLinearCheckpoint,
    load_linear_checkpoint,
)
from ai_trader.training.evaluate_majority import print_evaluation
from ai_trader.training.metrics import (
    ClassificationReport,
    evaluate_classification,
)
from ai_trader.training.model_data import (
    MODEL_FEATURE_NAMES,
    row_to_model_features,
)

DEFAULT_CHECKPOINT_DIRECTORY = Path("checkpoints")

OUTPUT_COLUMNS = (
    "schema_version",
    "source_row_index",
    "depth_event_time_ms",
    "update_id",
    "midpoint",
    "predicted_direction",
    "probability_down",
    "probability_neutral",
    "probability_up",
    "confidence",
)


@dataclass(frozen=True, slots=True)
class InferenceReport:
    """Summary of one offline inference run."""

    input_rows: int
    predicted_down: int
    predicted_neutral: int
    predicted_up: int
    evaluation: ClassificationReport | None


def find_latest_checkpoint() -> Path:
    """Return the newest complete linear checkpoint directory."""
    candidates = [
        path
        for path in DEFAULT_CHECKPOINT_DIRECTORY.glob("linear_*")
        if path.is_dir()
        and (path / "metadata.json").is_file()
        and (path / "model.pt").is_file()
        and (path / "scaler.npz").is_file()
    ]

    if not candidates:
        raise FileNotFoundError("No complete linear checkpoints were found.")

    return max(
        candidates,
        key=lambda path: (path / "metadata.json").stat().st_mtime,
    )


def default_input_path(
    checkpoint: LoadedLinearCheckpoint,
) -> Path:
    """Resolve the test partition recorded in checkpoint metadata."""
    training_metadata = checkpoint.metadata.get("training")
    if not isinstance(training_metadata, dict):
        raise ValueError("Checkpoint does not contain training metadata.")

    source_directory = training_metadata.get("source_split_directory")
    if not isinstance(source_directory, str) or not source_directory:
        raise ValueError("Checkpoint does not identify its source split.")

    return Path(source_directory) / "test.csv"


def create_output_path(
    input_path: Path,
    checkpoint_path: Path,
) -> Path:
    """Create a default prediction CSV path."""
    return input_path.with_name(f"{input_path.stem}_predictions_{checkpoint_path.name}.csv")


def read_inference_rows(
    path: Path,
) -> tuple[
    list[dict[str, str]],
    np.ndarray,
    np.ndarray | None,
]:
    """Load causal model features and optional audit targets."""
    rows: list[dict[str, str]] = []
    feature_rows: list[np.ndarray] = []
    targets: list[int] = []
    has_targets = False

    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError(f"{path.name} does not contain a header.")

        required_metadata = {
            "depth_event_time_ms",
            "update_id",
            "midpoint",
        }
        missing_metadata = required_metadata - set(reader.fieldnames)
        if missing_metadata:
            missing_text = ", ".join(sorted(missing_metadata))
            raise ValueError(f"{path.name} is missing audit columns: {missing_text}.")

        has_targets = "target_direction" in reader.fieldnames

        for line_number, row in enumerate(reader, start=2):
            try:
                feature_row = row_to_model_features(row)
            except ValueError as error:
                raise ValueError(f"{path.name} line {line_number}: {error}") from error

            rows.append(row)
            feature_rows.append(feature_row)

            if has_targets:
                try:
                    target = int(row["target_direction"])
                except ValueError as error:
                    raise ValueError(
                        f"{path.name} line {line_number}: invalid target direction."
                    ) from error

                if target not in {-1, 0, 1}:
                    raise ValueError(
                        f"{path.name} line {line_number}: target direction must be -1, 0, or 1."
                    )
                targets.append(target)

    if not rows:
        raise ValueError(f"{path.name} contains no data rows.")

    feature_matrix = np.vstack(feature_rows).astype(
        np.float64,
        copy=False,
    )
    target_vector = np.asarray(targets, dtype=np.int64) if has_targets else None

    return rows, feature_matrix, target_vector


def run_inference(
    checkpoint: LoadedLinearCheckpoint,
    input_path: Path,
    output_path: Path,
) -> InferenceReport:
    """Generate predictions without using historical targets as inputs."""
    if checkpoint.feature_names != MODEL_FEATURE_NAMES:
        raise ValueError("Checkpoint feature schema does not match the current model-input schema.")

    rows, features, targets = read_inference_rows(input_path)
    probabilities = checkpoint.predict_probabilities(features)
    predictions = checkpoint.predict(features)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(OUTPUT_COLUMNS)
    if targets is not None:
        fieldnames.append("actual_direction")

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )
        writer.writeheader()

        for index, (
            row,
            prediction,
            probability_row,
        ) in enumerate(
            zip(
                rows,
                predictions,
                probabilities,
                strict=True,
            )
        ):
            output_row: dict[str, str | int] = {
                "schema_version": 1,
                "source_row_index": index,
                "depth_event_time_ms": row["depth_event_time_ms"],
                "update_id": row["update_id"],
                "midpoint": row["midpoint"],
                "predicted_direction": int(prediction),
                "probability_down": (f"{probability_row[0]:.10f}"),
                "probability_neutral": (f"{probability_row[1]:.10f}"),
                "probability_up": (f"{probability_row[2]:.10f}"),
                "confidence": (f"{probability_row.max():.10f}"),
            }

            if targets is not None:
                output_row["actual_direction"] = int(targets[index])

            writer.writerow(output_row)

    evaluation = (
        evaluate_classification(
            targets.tolist(),
            predictions.tolist(),
        )
        if targets is not None
        else None
    )

    return InferenceReport(
        input_rows=len(rows),
        predicted_down=int(np.sum(predictions == -1)),
        predicted_neutral=int(np.sum(predictions == 0)),
        predicted_up=int(np.sum(predictions == 1)),
        evaluation=evaluation,
    )


def parse_args() -> argparse.Namespace:
    """Read checkpoint, input, and output paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint directory; defaults to the newest.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help=("Causal feature CSV; defaults to the checkpoint's recorded test partition."),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional prediction CSV path.",
    )
    return parser.parse_args()


def main() -> None:
    """Load a checkpoint and run offline inference."""
    args = parse_args()
    checkpoint_path = args.checkpoint or find_latest_checkpoint()
    checkpoint = load_linear_checkpoint(checkpoint_path)
    input_path = args.input or default_input_path(checkpoint)
    output_path = args.output or create_output_path(input_path, checkpoint_path)

    report = run_inference(
        checkpoint,
        input_path,
        output_path,
    )

    print(f"Checkpoint: {checkpoint_path.resolve()}")
    print(f"Input: {input_path.resolve()}")
    print(f"Rows: {report.input_rows}")
    print(
        "Predictions: "
        f"down={report.predicted_down}, "
        f"neutral={report.predicted_neutral}, "
        f"up={report.predicted_up}"
    )
    print(f"Output: {output_path.resolve()}")

    if report.evaluation is not None:
        print_evaluation(
            "Historical evaluation",
            report.evaluation,
        )


if __name__ == "__main__":
    main()
