"""Classification metrics for directional market predictions."""

from __future__ import annotations

from dataclasses import dataclass

CLASS_LABELS = (-1, 0, 1)


@dataclass(frozen=True, slots=True)
class ClassMetrics:
    """Metrics for one direction class."""

    label: int
    support: int
    predicted: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True, slots=True)
class ClassificationReport:
    """Complete three-class evaluation report."""

    total: int
    correct: int
    accuracy: float
    balanced_accuracy: float
    macro_f1: float
    confusion_matrix: tuple[
        tuple[int, int, int],
        tuple[int, int, int],
        tuple[int, int, int],
    ]
    classes: tuple[
        ClassMetrics,
        ClassMetrics,
        ClassMetrics,
    ]

    @property
    def missing_actual_classes(self) -> tuple[int, ...]:
        """Return classes absent from the evaluated targets."""
        return tuple(metrics.label for metrics in self.classes if metrics.support == 0)


def safe_divide(numerator: int, denominator: int) -> float:
    """Divide counts while returning zero for an empty denominator."""
    if denominator == 0:
        return 0.0
    return numerator / denominator


def evaluate_classification(
    actual: list[int],
    predicted: list[int],
) -> ClassificationReport:
    """Evaluate predictions for DOWN, NEUTRAL, and UP classes."""
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted labels must have equal lengths.")
    if not actual:
        raise ValueError("At least one prediction is required.")

    allowed_labels = set(CLASS_LABELS)
    if any(label not in allowed_labels for label in actual):
        raise ValueError("Actual labels must be -1, 0, or 1.")
    if any(label not in allowed_labels for label in predicted):
        raise ValueError("Predicted labels must be -1, 0, or 1.")

    label_indices = {label: index for index, label in enumerate(CLASS_LABELS)}
    matrix = [[0, 0, 0] for _ in CLASS_LABELS]

    for actual_label, predicted_label in zip(
        actual,
        predicted,
        strict=True,
    ):
        actual_index = label_indices[actual_label]
        predicted_index = label_indices[predicted_label]
        matrix[actual_index][predicted_index] += 1

    class_metrics = []

    for index, label in enumerate(CLASS_LABELS):
        true_positive = matrix[index][index]
        support = sum(matrix[index])
        predicted_count = sum(row[index] for row in matrix)

        precision = safe_divide(
            true_positive,
            predicted_count,
        )
        recall = safe_divide(
            true_positive,
            support,
        )
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

        class_metrics.append(
            ClassMetrics(
                label=label,
                support=support,
                predicted=predicted_count,
                precision=precision,
                recall=recall,
                f1=f1,
            )
        )

    correct = sum(matrix[index][index] for index in range(len(CLASS_LABELS)))
    supported_recalls = [metrics.recall for metrics in class_metrics if metrics.support > 0]

    immutable_matrix = tuple(tuple(row) for row in matrix)

    return ClassificationReport(
        total=len(actual),
        correct=correct,
        accuracy=correct / len(actual),
        balanced_accuracy=(sum(supported_recalls) / len(supported_recalls)),
        macro_f1=(sum(metrics.f1 for metrics in class_metrics) / len(class_metrics)),
        confusion_matrix=immutable_matrix,
        classes=tuple(class_metrics),
    )
