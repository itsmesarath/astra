"""Registered, bounded expanding-session evaluation; no trading or model promotion.

Each research evaluation session is predicted once, from earlier sessions only.
All planned folds remain visible; any blocked fold withholds pooled metrics.
"""

import argparse
import json
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from ai_trader.research.microstructure_trial import load_registration
from ai_trader.trading.paper_lifecycle import _timestamp
from ai_trader.training.event_training_data import (
    MAX_INPUT_BYTES,
    MAX_MANIFEST_BYTES,
    EventDatasetInput,
    _check_current,
    _load_dataset,
    _manifest,
    _partition,
    _quality,
    _read_envelope,
)
from ai_trader.training.microstructure_data import _hash, _json, _publish
from ai_trader.training.train_event_baseline import (
    MAX_ROW_EPOCHS,
    EventBaselineConfig,
    _decode_config,
    _fit,
    _metrics,
    _model_payload,
    _prediction_probabilities,
    _recipe,
    _score_predictions,
    _targets,
)

WALK_FORWARD_VERSION = "expanding_event_walk_forward_v1"
MAX_RESULT_BYTES = 8 * 1024 * 1024
SOURCE_SETTING_NAMES = {
    "initial_training_sessions",
    "max_frames_per_session",
    "embargo_ns",
    "minimum_resolved_per_session",
    "minimum_resolved_fraction",
}


def _plan(registration, *, config, initial_training_sessions, **source_settings):
    initial = _manifest(
        registration, training_session_count=initial_training_sessions, **source_settings
    )
    research = tuple(s for s in registration.sources if s.role == "research")
    reserved = tuple(s for s in registration.sources if s.role == "reserved")
    if len(research) - initial_training_sessions < 2:
        raise ValueError("Walk-forward requires at least two later evaluation sessions.")
    if type(config) is not EventBaselineConfig:
        raise ValueError("Typed event-baseline configuration required.")
    declared_work = (
        sum(range(initial_training_sessions, len(research)))
        * source_settings["max_frames_per_session"]
        * config.epochs
    )
    if declared_work > MAX_ROW_EPOCHS:
        raise ValueError("Aggregate walk-forward training compute budget exceeded.")
    # Every evaluation session is a future boundary, including its subsequent use as training.
    following = (*research[1:], reserved[0])
    for i in range(initial_training_sessions - 1, len(research)):
        end = research[i].ended_at_ns + source_settings["embargo_ns"]
        _timestamp(end)
        if end >= following[i].started_at_ns:
            raise ValueError("Walk-forward boundary violates the strict outcome embargo.")
    folds = []
    for index, i in enumerate(range(initial_training_sessions, len(research))):
        manifest = {
            **initial,
            "artifact_type": "event_walk_forward_fold",
            "split_version": WALK_FORWARD_VERSION,
            "fold_index": index,
            "training_session_count": i,
            "train_sessions": [s.source_session for s in research[:i]],
            "validation_sessions": [research[i].source_session],
            "future_research_sessions": [s.source_session for s in research[i + 1 :]],
            "train_outcome_cutoff_ns": research[i].started_at_ns,
            "validation_outcome_cutoff_ns": following[i].started_at_ns,
        }
        folds.append({"manifest": manifest, "recipe": _recipe(registration, manifest, config)})
    # Remove mutable aliasing between fold metadata and the returned public plan.
    return json.loads(
        _json(
            {
                "schema_version": 1,
                "artifact_type": "event_walk_forward_plan",
                "walk_forward_version": WALK_FORWARD_VERSION,
                "registration_sha256": registration.sha256,
                "configuration": asdict(config),
                "source_settings": {
                    **source_settings,
                    "initial_training_sessions": initial_training_sessions,
                },
                "research_sessions": [s.source_session for s in research],
                "reserved_sessions": [s.source_session for s in reserved],
                "declared_training_row_epochs": declared_work,
                "schedule": "expanding_prefix_train_then_one_next_session_once",
                "failure_policy": "retain_every_fold_no_pooled_metrics_if_any_blocked",
                "aggregation": "concatenated_out_of_sample_probabilities_not_mean_fold_metrics",
                "folds": folds,
                "mode": "research_only",
                "promotion_allowed": False,
                "live_trading_available": False,
            }
        )
    )


def register_event_walk_forward(
    *,
    registration_path: Path,
    output_path: Path,
    config: EventBaselineConfig,
    initial_training_sessions: int,
    max_frames_per_session: int,
    embargo_ns: int,
    minimum_resolved_per_session: int,
    minimum_resolved_fraction: Decimal,
) -> dict:
    """Read registration metadata only; freeze the entire fold schedule before viewing outcomes."""
    registration = load_registration(registration_path)
    plan = _plan(
        registration,
        config=config,
        initial_training_sessions=initial_training_sessions,
        max_frames_per_session=max_frames_per_session,
        embargo_ns=embargo_ns,
        minimum_resolved_per_session=minimum_resolved_per_session,
        minimum_resolved_fraction=minimum_resolved_fraction,
    )
    _check_current(registration)
    _publish(plan, output_path, payload_name="manifest", max_bytes=MAX_MANIFEST_BYTES)
    return plan


def _load_plan(path, registration):
    plan, _ = _read_envelope(path, "manifest", MAX_MANIFEST_BYTES)
    settings = plan.get("source_settings")
    if (
        type(settings) is not dict
        or set(settings) != SOURCE_SETTING_NAMES
        or type(settings["minimum_resolved_fraction"]) is not str
    ):
        raise ValueError("Invalid walk-forward source settings.")
    settings = dict(settings)
    try:
        settings["minimum_resolved_fraction"] = Decimal(settings["minimum_resolved_fraction"])
    except InvalidOperation as error:
        raise ValueError("Invalid walk-forward fraction.") from error
    config = _decode_config(plan.get("configuration"))
    if _json(plan) != _json(_plan(registration, config=config, **settings)):
        raise ValueError("Walk-forward plan differs from the registered schedule/protocol.")
    return plan, config


def _load_sources(registration, plan, sources):
    research = tuple(s for s in registration.sources if s.role == "research")
    if (
        type(sources) is not tuple
        or any(type(s) is not EventDatasetInput for s in sources)
        or tuple(s.source_session for s in sources) != tuple(s.source_session for s in research)
    ):
        raise ValueError("Supply every research source, in declared order, exactly once.")
    used, rows, reports = 0, {}, {}
    settings = plan["source_settings"]
    for selected, declared in zip(sources, research, strict=True):
        dataset, size = _load_dataset(
            registration,
            selected,
            byte_budget=MAX_INPUT_BYTES - used,
            expected_frames=settings["max_frames_per_session"],
        )
        used += size
        for row in dataset["examples"]:
            if not (
                declared.started_at_ns
                <= row["feature_available_at_ns"]
                <= row["outcome"]["known_at_ns"]
                <= declared.ended_at_ns
            ):
                raise ValueError("Outcome availability crosses its declared source boundary.")
        # Keep unknown/excluded accounting even though only resolved rows enter a model matrix.
        rows[declared.source_session] = dataset["examples"]
        reports[declared.source_session] = _quality(dataset, settings)
    _check_current(registration)
    return rows, reports, used


def _fold_partition(rows, sessions, cutoff, embargo):
    selected = []
    for session in sessions:
        for row in rows[session]:
            if row["outcome"]["known_at_ns"] + embargo >= cutoff:
                raise ValueError("Outcome availability violates the strict fold embargo.")
            if row["outcome"]["status"] == "resolved":
                selected.append(row)
    return _partition(selected)


def evaluate_registered_event_walk_forward(
    *,
    registration_path: Path,
    plan_path: Path,
    sources: tuple[EventDatasetInput, ...],
    output_path: Path,
    enable_training: bool = False,
) -> dict:
    """Reproduce inputs once, freshly fit each prefix and evaluate every scheduled later session."""
    if enable_training is not True:
        raise ValueError("Explicit enable_training=True is required for walk-forward fitting.")
    output_path = Path(output_path)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    registration = load_registration(registration_path)
    plan, config = _load_plan(plan_path, registration)
    rows, source_reports, used = _load_sources(registration, plan, sources)
    folds, pooled_targets, pooled_probabilities, seen = [], [], {}, set()
    for declared in plan["folds"]:
        manifest, recipe = declared["manifest"], declared["recipe"]
        scope = manifest["train_sessions"] + manifest["validation_sessions"]
        blocked = [s for s in scope if source_reports[s]["gate_failures"]]
        fold = {
            "fold_index": manifest["fold_index"],
            "recipe_sha256": _hash(_json(recipe)),
            "train_sessions": manifest["train_sessions"],
            "validation_session": manifest["validation_sessions"][0],
            "status": "blocked_source_quality",
            "blocked_sources": blocked,
            "model": None,
            "model_sha256": None,
            "fit": None,
            "validation": None,
            "training_outcomes_available_by_ns": None,
        }
        if not blocked:
            train = _fold_partition(
                rows,
                manifest["train_sessions"],
                manifest["train_outcome_cutoff_ns"],
                manifest["embargo_ns"],
            )
            validation = _fold_partition(
                rows,
                manifest["validation_sessions"],
                manifest["validation_outcome_cutoff_ns"],
                manifest["embargo_ns"],
            )
            counts = np.bincount(_targets(train), minlength=3).tolist()
            fold.update(
                status="blocked_training_classes",
                fit={"epochs_completed": 0, "training_class_counts": counts},
            )
            if sum(c > 0 for c in counts) >= 2:
                model, fit = _fit(train, config)
                # Predictions/controls are frozen before consulting the evaluation targets.
                probabilities = _prediction_probabilities(model, train, validation)
                evaluation = _score_predictions(validation, probabilities)
                ids = validation.example_ids
                if len(ids) != len(set(ids)) or seen.intersection(ids):
                    raise ValueError("Duplicate out-of-sample prediction identity.")
                seen.update(ids)
                pooled_targets.append(_targets(validation))
                for name, values in probabilities.items():
                    pooled_probabilities.setdefault(name, []).append(values)
                payload = _model_payload(model)
                fold.update(
                    status="completed",
                    model=payload,
                    model_sha256=_hash(_json(payload)),
                    fit=fit,
                    validation=evaluation,
                    training_outcomes_available_by_ns=max(train.known_at_ns),
                )
        folds.append(fold)
        _check_current(registration)
    complete = all(f["status"] == "completed" for f in folds)
    aggregate = None
    if complete:
        targets = np.concatenate(pooled_targets)
        aggregate = {
            name: _metrics(targets, np.concatenate(values))
            for name, values in pooled_probabilities.items()
        }
    completed = sum(f["status"] == "completed" for f in folds)
    _check_current(registration)
    result = json.loads(
        _json(
            {
                "schema_version": 1,
                "artifact_type": "event_walk_forward_research_run",
                "walk_forward_version": WALK_FORWARD_VERSION,
                "plan_sha256": _hash(_json(plan)),
                "plan": plan,
                "status": "completed" if complete else "incomplete",
                "verified_input_bytes": used,
                "sources": list(source_reports.values()),
                "folds": folds,
                "completed_folds": completed,
                "blocked_folds": len(folds) - completed,
                "pooled_metrics_available": complete,
                "aggregate": aggregate,
                "out_of_sample_rows_in_completed_folds": len(seen),
                "reserved_sources_opened": 0,
                "training_started": completed > 0,
                "mode": "research_only",
                "promotion_allowed": False,
                "live_trading_available": False,
                "limitation": (
                    "Fixed-recipe expanding-session predictive research; "
                    "no tuning, best-fold selection or final refit. "
                    "Past evaluation outcomes may train later folds only after availability. "
                    "Blocked folds remain visible and suppress pooled metrics. "
                    "Overlapping labels are dependent; metrics do not establish trading "
                    "profitability, calibration or significance. No held-out test evaluation, "
                    "latency model, paper execution or model promotion."
                ),
            }
        )
    )
    _publish(result, output_path, payload_name="report", max_bytes=MAX_RESULT_BYTES)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser(
        "register", help="Metadata-only schedule and recipe registration."
    )
    for name in (
        "initial-training-sessions",
        "max-frames-per-session",
        "embargo-ns",
        "minimum-resolved-per-session",
        "epochs",
    ):
        register.add_argument("--" + name, type=int, required=True)
    for name in ("minimum-resolved-fraction", "learning-rate", "l2"):
        register.add_argument("--" + name, type=Decimal, required=True)
    evaluate = commands.add_parser("evaluate", help="Opt-in bounded walk-forward research fitting.")
    evaluate.add_argument("--plan", type=Path, required=True)
    evaluate.add_argument(
        "--source",
        nargs=3,
        action="append",
        required=True,
        metavar=("SESSION", "CAPTURE", "DATASET"),
    )
    evaluate.add_argument("--enable-training", action="store_true")
    for command in (register, evaluate):
        command.add_argument("--registration", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        plan = register_event_walk_forward(
            registration_path=args.registration,
            output_path=args.output,
            config=EventBaselineConfig(args.epochs, args.learning_rate, args.l2),
            **{k: getattr(args, k) for k in SOURCE_SETTING_NAMES},
        )
        print(
            json.dumps(
                {
                    "plan_sha256": _hash(_json(plan)),
                    "folds": len(plan["folds"]),
                    "training_started": False,
                }
            )
        )
    else:
        result = evaluate_registered_event_walk_forward(
            registration_path=args.registration,
            plan_path=args.plan,
            output_path=args.output,
            sources=tuple(EventDatasetInput(s, Path(c), Path(d)) for s, c, d in args.source),
            enable_training=args.enable_training,
        )
        print(
            json.dumps(
                {
                    "result_sha256": _hash(_json(result)),
                    "status": result["status"],
                    "completed_folds": result["completed_folds"],
                    "blocked_folds": result["blocked_folds"],
                    "training_started": result["training_started"],
                    "promotion_allowed": False,
                }
            )
        )
        if result["status"] != "completed":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
