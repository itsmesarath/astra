"""Evaluate a linear baseline across expanding source-session windows."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

import numpy as np

from ai_trader.backtesting.candle_replay import CandleSession, ReplayConfig
from ai_trader.backtesting.economic_metrics import (
    EconomicConfig,
    EconomicEvaluation,
    aggregate_economic_evaluations,
    economic_evaluation_payload,
    evaluate_spot_economics,
)
from ai_trader.features.kline_dataset import TripleBarrierConfig, load_verified_sessions
from ai_trader.trading.decision_policy import DecisionPolicy
from ai_trader.trading.evaluate_decision_policy import (
    PolicyEvaluation,
    evaluate_probability_rows,
)
from ai_trader.training.feature_provenance import ReplayFeatureProvenance, verify_replay_features
from ai_trader.training.metrics import (
    CLASS_LABELS,
    ClassificationReport,
    evaluate_classification,
)
from ai_trader.training.model_data import KLINE_MODEL_FEATURE_NAMES, ModelPartition
from ai_trader.training.replay_evaluation import (
    FrozenPredictions,
    ReplayComparison,
    replay_comparison_payload,
    replay_frozen_predictions,
)
from ai_trader.training.session_data import (
    SessionMetadata,
    SessionPartition,
    load_session_dataset,
)
from ai_trader.training.train_linear import (
    TrainingConfig,
    fit_linear_baseline,
    predict_probabilities,
    resolve_device,
    to_feature_tensor,
)

DEFAULT_OUTPUT_DIRECTORY = Path("data/processed/walk_forward")


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    """One disjoint fit/tune/evaluate result; validation names mean evaluation."""

    index: int
    training_sessions: tuple[str, ...]
    tuning_sessions: tuple[str, ...]
    validation_session: str
    training_rows: int
    tuning_rows: int
    validation_rows: int
    best_epoch: int
    epochs_trained: int
    tuning: ClassificationReport
    validation: ClassificationReport
    policy: PolicyEvaluation
    economics: EconomicEvaluation | None
    predictions: FrozenPredictions


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    """Forward evidence with metadata-only access to reserved sessions."""

    source_path: Path
    source_sha256: str
    session_metadata: tuple[SessionMetadata, ...]
    embargo_ms: int
    feature_names: tuple[str, ...]
    economic_config: EconomicConfig
    total_sessions: int
    evaluated_sessions: tuple[str, ...]
    held_out_sessions: tuple[str, ...]
    folds: tuple[WalkForwardFold, ...]
    aggregate_validation: ClassificationReport
    aggregate_policy: PolicyEvaluation
    aggregate_economics: EconomicEvaluation | None
    decision_policy: DecisionPolicy
    candle_replay: ReplayComparison | None
    replay_feature_provenance: ReplayFeatureProvenance | None


def load_session_partitions(path: Path) -> tuple[SessionPartition, ...]:
    """Load all sessions with boundary checks; walk-forward reserves holdouts separately."""
    return load_session_dataset(path).sessions


def combine_partitions(sessions: tuple[SessionPartition, ...]) -> ModelPartition:
    """Combine chronological sessions into one model partition."""
    if not sessions:
        raise ValueError("At least one session is required.")

    feature_names = {session.partition.feature_names for session in sessions}
    if len(feature_names) != 1:
        raise ValueError("Source sessions must use one model feature schema.")
    return ModelPartition(
        features=np.vstack([session.partition.features for session in sessions]),
        targets=np.concatenate([session.partition.targets for session in sessions]),
        feature_names=feature_names.pop(),
    )


def aggregate_reports(reports: tuple[ClassificationReport, ...]) -> ClassificationReport:
    """Aggregate fold confusion matrices into one classification report."""
    if not reports:
        raise ValueError("At least one classification report is required.")

    actual: list[int] = []
    predicted: list[int] = []

    for report in reports:
        for actual_index, actual_label in enumerate(CLASS_LABELS):
            for predicted_index, predicted_label in enumerate(CLASS_LABELS):
                count = report.confusion_matrix[actual_index][predicted_index]
                actual.extend([actual_label] * count)
                predicted.extend([predicted_label] * count)

    return evaluate_classification(actual, predicted)


def aggregate_policy_evaluations(
    reports: tuple[PolicyEvaluation, ...],
) -> PolicyEvaluation:
    """Sum policy counts across independent validation sessions."""
    if not reports:
        raise ValueError("At least one policy evaluation is required.")

    reason_counts: Counter[str] = Counter()
    for report in reports:
        reason_counts.update(report.reason_counts)

    return PolicyEvaluation(
        rows=sum(report.rows for report in reports),
        short_signals=sum(report.short_signals for report in reports),
        flat_decisions=sum(report.flat_decisions for report in reports),
        long_signals=sum(report.long_signals for report in reports),
        correct_short_signals=sum(report.correct_short_signals for report in reports),
        correct_long_signals=sum(report.correct_long_signals for report in reports),
        short_outcomes=tuple(
            sum(report.short_outcomes[index] for report in reports)
            for index in range(len(CLASS_LABELS))
        ),
        long_outcomes=tuple(
            sum(report.long_outcomes[index] for report in reports)
            for index in range(len(CLASS_LABELS))
        ),
        reason_counts=dict(reason_counts),
    )


def run_walk_forward(
    source_path: Path,
    config: TrainingConfig,
    *,
    minimum_training_sessions: int = 2,
    tuning_session_count: int = 1,
    held_out_session_count: int = 1,
    embargo_ms: int = 0,
    policy: DecisionPolicy | None = None,
    economic_config: EconomicConfig | None = None,
    replay_manifest: Path | None = None,
    replay_config: ReplayConfig | None = None,
) -> WalkForwardReport:
    """Fit older sessions, tune on recent past sessions, then score the next session.

    minimum_training_sessions counts fitting sessions only, excluding tuning.
    The legacy validation report fields now describe evaluation-only results.
    """
    if type(minimum_training_sessions) is not int or minimum_training_sessions <= 0:
        raise ValueError("Minimum training sessions must be positive.")
    if type(held_out_session_count) is not int or held_out_session_count <= 0:
        raise ValueError("Held-out session count must be positive.")
    if type(tuning_session_count) is not int or tuning_session_count <= 0:
        raise ValueError("Tuning session count must be positive.")
    if (replay_manifest is None) != (replay_config is None):
        raise ValueError(
            "Replay requires both an explicit candle manifest and replay configuration."
        )

    dataset = load_session_dataset(
        source_path,
        held_out_session_count=held_out_session_count,
        embargo_ms=embargo_ms,
    )
    sessions = dataset.sessions
    active_policy = policy or DecisionPolicy(allow_short=False)
    active_economic_config = economic_config or EconomicConfig()
    first_evaluation = minimum_training_sessions + tuning_session_count
    required_sessions = first_evaluation + held_out_session_count + 1
    if len(dataset.metadata) < required_sessions:
        raise ValueError(
            "Walk-forward evaluation requires at least "
            f"{required_sessions} source sessions for this configuration."
        )

    validation_stop = len(sessions)
    replay_inputs = None
    replay_feature_provenance = None
    if replay_config is not None:
        replay_config.validate()
        if replay_config.capital != active_economic_config:
            raise ValueError("Replay and label economics must use identical capital/risk settings.")
        if active_policy.allow_short or replay_config.entry_delay_bars != 0:
            raise ValueError("Replay requires long/flat policy and zero-delay base configuration.")
        if sessions[0].partition.feature_names != KLINE_MODEL_FEATURE_NAMES:
            raise ValueError("Candle replay integration requires the kline feature schema.")
        selected_names = tuple(session.name for session in sessions[first_evaluation:])
        _, _, _, candle_sources = load_verified_sessions(
            replay_manifest, selected_sessions=selected_names
        )
        replay_inputs = tuple(CandleSession(name, tuple(bars)) for name, bars in candle_sources)
        replay_feature_provenance = verify_replay_features(
            sessions[first_evaluation:], replay_inputs
        )
    folds = []
    previous_economics = None

    for validation_position in range(first_evaluation, validation_stop):
        tuning_start = validation_position - tuning_session_count
        training_sessions = sessions[:tuning_start]
        tuning_sessions = sessions[tuning_start:validation_position]
        validation_session = sessions[validation_position]
        training_partition = combine_partitions(training_sessions)
        tuning_partition = combine_partitions(tuning_sessions)
        fit = fit_linear_baseline(
            training_partition,
            tuning_partition,
            config,
        )
        validation_features = to_feature_tensor(
            fit.standardizer.transform(validation_session.partition.features),
            resolve_device(fit.device),
        )
        probabilities = predict_probabilities(fit.model, validation_features)
        frozen = FrozenPredictions(
            source_session=validation_session.name,
            event_times_ms=validation_session.event_times_ms,
            probabilities=tuple(tuple(float(value) for value in row) for row in probabilities),
        )
        evaluation = evaluate_classification(
            validation_session.partition.targets.tolist(),
            [CLASS_LABELS[index] for index in probabilities.argmax(axis=1)],
        )
        policy_report = evaluate_probability_rows(
            probabilities.tolist(),
            validation_session.partition.targets.tolist(),
            active_policy,
        )
        economics = (
            evaluate_spot_economics(
                probabilities.tolist(),
                validation_session.outcomes,
                active_policy,
                active_economic_config,
                previous_evaluation=previous_economics,
            )
            if validation_session.outcomes is not None
            else None
        )
        previous_economics = economics
        folds.append(
            WalkForwardFold(
                index=len(folds) + 1,
                training_sessions=tuple(session.name for session in training_sessions),
                tuning_sessions=tuple(session.name for session in tuning_sessions),
                validation_session=validation_session.name,
                training_rows=training_partition.rows,
                tuning_rows=tuning_partition.rows,
                validation_rows=validation_session.partition.rows,
                best_epoch=fit.best_epoch,
                epochs_trained=fit.epochs_trained,
                tuning=fit.validation,
                validation=evaluation,
                policy=policy_report,
                economics=economics,
                predictions=frozen,
            )
        )

    immutable_folds = tuple(folds)
    fold_economics = tuple(fold.economics for fold in immutable_folds if fold.economics is not None)
    if fold_economics and len(fold_economics) != len(immutable_folds):
        raise ValueError("Economic outcome availability must be consistent across sessions.")
    return WalkForwardReport(
        source_path=source_path,
        source_sha256=dataset.source_sha256,
        session_metadata=dataset.metadata,
        embargo_ms=embargo_ms,
        feature_names=sessions[0].partition.feature_names,
        economic_config=active_economic_config,
        total_sessions=len(dataset.metadata),
        evaluated_sessions=tuple(fold.validation_session for fold in immutable_folds),
        held_out_sessions=dataset.held_out_sessions,
        folds=immutable_folds,
        aggregate_validation=aggregate_reports(
            tuple(fold.validation for fold in immutable_folds),
        ),
        aggregate_policy=aggregate_policy_evaluations(
            tuple(fold.policy for fold in immutable_folds),
        ),
        aggregate_economics=(
            aggregate_economic_evaluations(fold_economics, active_economic_config)
            if fold_economics
            else None
        ),
        decision_policy=active_policy,
        replay_feature_provenance=replay_feature_provenance,
        candle_replay=(
            replay_frozen_predictions(
                tuple(fold.predictions for fold in immutable_folds),
                replay_inputs,
                active_policy,
                replay_config,
                evaluated_sessions=tuple(fold.validation_session for fold in immutable_folds),
                held_out_sessions=dataset.held_out_sessions,
            )
            if replay_inputs is not None
            else None
        ),
    )


def classification_report_payload(report: ClassificationReport) -> dict[str, object]:
    """Convert classification metrics to JSON-safe metadata."""
    return {
        "total": report.total,
        "correct": report.correct,
        "accuracy": report.accuracy,
        "balanced_accuracy": report.balanced_accuracy,
        "macro_f1": report.macro_f1,
        "missing_actual_classes": list(report.missing_actual_classes),
        "confusion_matrix": [list(row) for row in report.confusion_matrix],
        "classes": [asdict(metrics) for metrics in report.classes],
    }


def policy_evaluation_payload(report: PolicyEvaluation) -> dict[str, object]:
    """Convert policy counts and derived metrics to JSON-safe metadata."""
    return {
        **asdict(report),
        "directional_signals": report.directional_signals,
        "coverage": report.coverage,
        "directional_precision": report.directional_precision,
        "short_precision": report.short_precision,
        "long_precision": report.long_precision,
    }


def write_walk_forward_report(
    path: Path,
    report: WalkForwardReport,
    config: TrainingConfig,
    policy: DecisionPolicy,
) -> None:
    """Write one auditable walk-forward evaluation report."""
    if policy != report.decision_policy:
        raise ValueError("Report policy must match the policy used for evaluation.")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 6,
        "prediction_class_order": list(CLASS_LABELS),
        "evaluation_protocol": "expanding_fit_past_tune_next_session_evaluate",
        "validation_fields_mean": "evaluation_only",
        "held_out_access": "csv_metadata_scanned_no_feature_or_outcome_conversion",
        "source_sha256": report.source_sha256,
        "session_metadata": [asdict(item) for item in report.session_metadata],
        "embargo_ms": report.embargo_ms,
        "boundary_policy": "reject_outcomes_at_or_after_next_session_start_minus_embargo",
        "model_type": "linear_direction_classifier",
        "source_dataset": str(report.source_path.resolve()),
        "feature_names": list(report.feature_names),
        "training_configuration": asdict(config),
        "decision_policy": asdict(policy),
        "economic_configuration": asdict(report.economic_config),
        "total_sessions": report.total_sessions,
        "evaluated_sessions": list(report.evaluated_sessions),
        "held_out_sessions": list(report.held_out_sessions),
        "aggregate_validation": classification_report_payload(report.aggregate_validation),
        "aggregate_policy": policy_evaluation_payload(report.aggregate_policy),
        "aggregate_economics": (
            economic_evaluation_payload(report.aggregate_economics)
            if report.aggregate_economics is not None
            else None
        ),
        "candle_replay": (
            replay_comparison_payload(report.candle_replay)
            if report.candle_replay is not None
            else None
        ),
        "replay_feature_provenance": (
            asdict(report.replay_feature_provenance)
            if report.replay_feature_provenance is not None
            else None
        ),
        "folds": [
            {
                "index": fold.index,
                "training_sessions": list(fold.training_sessions),
                "tuning_sessions": list(fold.tuning_sessions),
                "validation_session": fold.validation_session,
                "training_rows": fold.training_rows,
                "tuning_rows": fold.tuning_rows,
                "validation_rows": fold.validation_rows,
                "best_epoch": fold.best_epoch,
                "epochs_trained": fold.epochs_trained,
                "tuning": classification_report_payload(fold.tuning),
                "validation": classification_report_payload(fold.validation),
                "policy": policy_evaluation_payload(fold.policy),
                "economics": (
                    economic_evaluation_payload(fold.economics)
                    if fold.economics is not None
                    else None
                ),
                "predictions": asdict(fold.predictions),
            }
            for fold in report.folds
        ],
    }

    with path.open("x", encoding="utf-8", newline="\n") as output_file:
        json.dump(payload, output_file, indent=2)
        output_file.write("\n")


def parse_args() -> argparse.Namespace:
    """Read dataset, fold, training, and output arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Combined labeled multi-session CSV.")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--minimum-training-sessions",
        type=int,
        default=2,
        help="Minimum fitting sessions, excluding the tuning block.",
    )
    parser.add_argument(
        "--tuning-session-count",
        type=int,
        default=1,
        help="Recent past sessions reserved for checkpoint selection, not fitting.",
    )
    parser.add_argument("--held-out-session-count", type=int, default=1)
    parser.add_argument(
        "--embargo-ms",
        type=int,
        default=0,
        help="Required gap after outcomes before the next session; rejects crossings.",
    )
    parser.add_argument("--max-epochs", type=int, default=500)
    parser.add_argument("--patience", type=int, default=50)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--class-weight-power", type=float, default=1.0)
    parser.add_argument("--minimum-direction-probability", type=float, default=0.55)
    parser.add_argument("--minimum-probability-margin", type=float, default=0.10)
    parser.add_argument("--starting-balance", type=float, default=10_000.0)
    parser.add_argument("--position-fraction", type=float, default=1.0)
    parser.add_argument("--minimum-reentry-delay-minutes", type=int, default=0)
    parser.add_argument("--maximum-trades-per-session", type=int)
    parser.add_argument("--session-profit-target", type=float)
    parser.add_argument("--session-loss-limit", type=float)
    parser.add_argument("--replay-manifest", type=Path, help="Opt-in verified raw candle manifest.")
    parser.add_argument("--replay-holding-bars", type=int, help="Explicit replay holding horizon.")
    parser.add_argument("--replay-take-profit-bps", type=Decimal, default=Decimal("20"))
    parser.add_argument("--replay-stop-loss-bps", type=Decimal, default=Decimal("40"))
    parser.add_argument("--replay-taker-fee-bps", type=Decimal, default=Decimal("10"))
    parser.add_argument("--replay-slippage-bps", type=Decimal, default=Decimal("2"))
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Allow short signals; disabled by default for Spot compatibility.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--device",
        choices=("auto", "cpu", "cuda"),
        default="auto",
    )
    args = parser.parse_args()
    if (args.replay_manifest is None) != (args.replay_holding_bars is None):
        parser.error("--replay-manifest and --replay-holding-bars must be supplied together")
    return args


def main() -> None:
    """Run and record session-aware expanding-window validation."""
    args = parse_args()
    output_path = args.output or (
        DEFAULT_OUTPUT_DIRECTORY / f"{args.path.stem}_linear_walk_forward.json"
    )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing report: {output_path}")
    config = TrainingConfig(
        max_epochs=args.max_epochs,
        patience=args.patience,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        class_weight_power=args.class_weight_power,
        seed=args.seed,
        device=args.device,
    )
    policy = DecisionPolicy(
        minimum_direction_probability=args.minimum_direction_probability,
        minimum_probability_margin=args.minimum_probability_margin,
        allow_short=args.allow_short,
    )
    economic_config = EconomicConfig(
        starting_balance=args.starting_balance,
        position_fraction=args.position_fraction,
        minimum_reentry_delay_ms=args.minimum_reentry_delay_minutes * 60_000,
        maximum_trades_per_session=args.maximum_trades_per_session,
        session_profit_target=args.session_profit_target,
        session_loss_limit=args.session_loss_limit,
    )
    report = run_walk_forward(
        args.path,
        config,
        minimum_training_sessions=args.minimum_training_sessions,
        tuning_session_count=args.tuning_session_count,
        held_out_session_count=args.held_out_session_count,
        embargo_ms=args.embargo_ms,
        policy=policy,
        economic_config=economic_config,
        replay_manifest=args.replay_manifest,
        replay_config=(
            ReplayConfig(
                capital=economic_config,
                holding_bars=args.replay_holding_bars,
                barriers=TripleBarrierConfig(
                    take_profit_bps=args.replay_take_profit_bps,
                    stop_loss_bps=args.replay_stop_loss_bps,
                    taker_fee_bps=args.replay_taker_fee_bps,
                    slippage_bps=args.replay_slippage_bps,
                ),
            )
            if args.replay_manifest is not None
            else None
        ),
    )
    write_walk_forward_report(output_path, report, config, policy)

    print("Mode: SESSION-AWARE FIT/TUNE/FORWARD EVALUATION")
    print(f"Source sessions: {report.total_sessions}")
    print(f"Held out from fitting and validation: {', '.join(report.held_out_sessions)}")
    for fold in report.folds:
        print(
            f"Fold {fold.index}: train_sessions={len(fold.training_sessions)}, "
            f"tuning_sessions={len(fold.tuning_sessions)}, "
            f"validation={fold.validation_session}, "
            f"rows={fold.validation_rows}, "
            f"balanced_accuracy={fold.validation.balanced_accuracy:.6f}, "
            f"macro_f1={fold.validation.macro_f1:.6f}, "
            f"coverage={fold.policy.coverage:.6f}, "
            f"directional_precision={fold.policy.directional_precision:.6f}"
        )
    aggregate = report.aggregate_validation
    print(
        "Aggregate validation: "
        f"rows={aggregate.total}, "
        f"balanced_accuracy={aggregate.balanced_accuracy:.6f}, "
        f"macro_f1={aggregate.macro_f1:.6f}"
    )
    print(
        "Aggregate policy: "
        f"signals={report.aggregate_policy.directional_signals}, "
        f"coverage={report.aggregate_policy.coverage:.6f}, "
        f"directional_precision={report.aggregate_policy.directional_precision:.6f}"
    )
    if report.aggregate_economics is not None:
        economics = report.aggregate_economics
        print(
            "Aggregate economics: "
            f"trades={economics.accepted_trades}, "
            f"net_pnl={economics.net_pnl:.2f}, "
            f"return={economics.return_pct:.4f}%, "
            f"closed_trade_drawdown={economics.maximum_closed_trade_drawdown_pct:.4f}%, "
            f"turnover={economics.turnover_multiple:.4f}x, "
            f"exposure={economics.exposure_ratio:.4f}"
        )
    if report.candle_replay is not None:
        for name, replay in (
            ("next_open", report.candle_replay.next_open),
            ("delayed_one_bar", report.candle_replay.delayed_one_bar),
        ):
            print(
                f"Candle replay {name}: trades={len(replay.trades)}, "
                f"net_pnl={replay.net_pnl:.2f}, "
                f"marked_drawdown={replay.maximum_marked_drawdown_pct:.4f}%, "
                f"turnover_quote={replay.turnover_quote:.2f}"
            )
    print(f"Report: {output_path.resolve()}")


if __name__ == "__main__":
    main()
