"""Evaluate a non-executable decision policy on saved predictions."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from ai_trader.trading.decision_policy import (
    DecisionPolicy,
    decide_position,
)

DEFAULT_DATA_DIRECTORY = Path("data/processed")


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    """Coverage and directional precision for one policy."""

    rows: int
    short_signals: int
    flat_decisions: int
    long_signals: int
    correct_short_signals: int
    correct_long_signals: int
    short_outcomes: tuple[int, int, int]
    long_outcomes: tuple[int, int, int]
    reason_counts: dict[str, int]

    @property
    def directional_signals(self) -> int:
        """Return accepted SHORT plus LONG decisions."""
        return self.short_signals + self.long_signals

    @property
    def coverage(self) -> float:
        """Return the fraction of rows with directional exposure."""
        return self.directional_signals / self.rows

    @property
    def directional_precision(self) -> float:
        """Return accuracy among accepted directional signals."""
        if self.directional_signals == 0:
            return 0.0

        correct = self.correct_short_signals + self.correct_long_signals
        return correct / self.directional_signals

    @property
    def short_precision(self) -> float:
        """Return correctness among accepted SHORT decisions."""
        if self.short_signals == 0:
            return 0.0
        return self.correct_short_signals / self.short_signals

    @property
    def long_precision(self) -> float:
        """Return correctness among accepted LONG decisions."""
        if self.long_signals == 0:
            return 0.0
        return self.correct_long_signals / self.long_signals


def find_latest_prediction_file() -> Path:
    """Return the newest historical prediction CSV."""
    candidates = list(DEFAULT_DATA_DIRECTORY.rglob("*_predictions_linear_*.csv"))
    if not candidates:
        raise FileNotFoundError("No historical prediction files were found.")

    return max(candidates, key=lambda path: path.stat().st_mtime)


def evaluate_probability_rows(
    probabilities: Sequence[Sequence[float]],
    actual_directions: Sequence[int],
    policy: DecisionPolicy,
) -> PolicyEvaluation:
    """Evaluate fixed probability thresholds on in-memory targets."""
    if len(probabilities) != len(actual_directions):
        raise ValueError("Probabilities and actual directions must have equal lengths.")
    if len(probabilities) == 0:
        raise ValueError("At least one probability row is required.")

    short_signals = 0
    flat_decisions = 0
    long_signals = 0
    correct_short_signals = 0
    correct_long_signals = 0
    short_outcomes = [0, 0, 0]
    long_outcomes = [0, 0, 0]
    reason_counts: Counter[str] = Counter()
    for probability_row, actual_direction in zip(
        probabilities,
        actual_directions,
        strict=True,
    ):
        if actual_direction not in {-1, 0, 1}:
            raise ValueError("Row has an invalid actual direction; expected -1, 0, or 1.")

        decision = decide_position(
            probability_row,
            policy,
        )
        reason_counts[decision.reason] += 1

        if decision.intent == "SHORT":
            short_signals += 1
            short_outcomes[actual_direction + 1] += 1
            if actual_direction == -1:
                correct_short_signals += 1
        elif decision.intent == "LONG":
            long_signals += 1
            long_outcomes[actual_direction + 1] += 1
            if actual_direction == 1:
                correct_long_signals += 1
        else:
            flat_decisions += 1

    return PolicyEvaluation(
        rows=len(probabilities),
        short_signals=short_signals,
        flat_decisions=flat_decisions,
        long_signals=long_signals,
        correct_short_signals=correct_short_signals,
        correct_long_signals=correct_long_signals,
        short_outcomes=tuple(short_outcomes),
        long_outcomes=tuple(long_outcomes),
        reason_counts=dict(reason_counts),
    )


def evaluate_prediction_file(
    path: Path,
    policy: DecisionPolicy,
) -> PolicyEvaluation:
    """Evaluate fixed probability thresholds on historical targets."""
    required_columns = {
        "probability_down",
        "probability_neutral",
        "probability_up",
        "actual_direction",
    }
    probability_rows = []
    actual_directions = []

    with path.open(encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)

        if reader.fieldnames is None:
            raise ValueError(f"{path.name} does not contain a header.")

        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            missing_text = ", ".join(sorted(missing_columns))
            raise ValueError(f"{path.name} is missing columns: {missing_text}.")

        for line_number, row in enumerate(reader, start=2):
            try:
                probability_rows.append(
                    (
                        float(row["probability_down"]),
                        float(row["probability_neutral"]),
                        float(row["probability_up"]),
                    )
                )
                actual_directions.append(int(row["actual_direction"]))
            except ValueError as error:
                raise ValueError(
                    f"{path.name} line {line_number} contains an invalid numeric value."
                ) from error

    if not probability_rows:
        raise ValueError(f"{path.name} contains no prediction rows.")

    try:
        return evaluate_probability_rows(
            probability_rows,
            actual_directions,
            policy,
        )
    except ValueError as error:
        raise ValueError(f"{path.name}: {error}") from error


def parse_args() -> argparse.Namespace:
    """Read prediction path and fixed policy thresholds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="Prediction CSV; defaults to the newest file.",
    )
    parser.add_argument(
        "--minimum-direction-probability",
        type=float,
        default=0.55,
    )
    parser.add_argument(
        "--minimum-probability-margin",
        type=float,
        default=0.10,
    )
    return parser.parse_args()


def main() -> None:
    """Evaluate a decision policy without executing trades."""
    args = parse_args()
    path = args.path or find_latest_prediction_file()
    policy = DecisionPolicy(
        minimum_direction_probability=(args.minimum_direction_probability),
        minimum_probability_margin=(args.minimum_probability_margin),
    )
    report = evaluate_prediction_file(path, policy)

    print(f"Predictions: {path.resolve()}")
    print(
        "Policy: "
        f"minimum_direction_probability="
        f"{policy.minimum_direction_probability:.2f}, "
        f"minimum_probability_margin="
        f"{policy.minimum_probability_margin:.2f}"
    )
    print(f"Rows: {report.rows}")
    print(
        "Decisions: "
        f"short={report.short_signals}, "
        f"flat={report.flat_decisions}, "
        f"long={report.long_signals}"
    )
    print(f"Directional coverage: {report.coverage:.4f}")
    print(f"Directional precision: {report.directional_precision:.4f}")
    print(f"SHORT precision: {report.short_precision:.4f}")
    print(f"LONG precision: {report.long_precision:.4f}")
    print(f"SHORT outcomes (DOWN, NEUTRAL, UP): {report.short_outcomes}")
    print(f"LONG outcomes (DOWN, NEUTRAL, UP): {report.long_outcomes}")
    print("Decision reasons:")
    for reason, count in sorted(report.reason_counts.items()):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
