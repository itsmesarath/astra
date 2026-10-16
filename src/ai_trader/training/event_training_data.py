"""Source-reproduced event datasets and metadata-frozen whole-session research folds.

No training, scaling, imputation, execution or reserved-source access. Failed source
quality gates retain their accounting and block the entire fold, not just losing rows.
"""

import argparse
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from ai_trader.research.microstructure_trial import _environment, load_registration
from ai_trader.trading.capture_replay import MAX_BYTES, CaptureReplay, _implementation_hash
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.trade_journal import JournalError, _constant, _hash, _identifier, _pairs
from ai_trader.training.microstructure_data import (
    DECIMAL_CONTEXT,
    FEATURE_SCHEMA_VERSION,
    FEATURE_UNITS,
    LABEL_VERSION,
    MAX_ARTIFACT_BYTES,
    _build_dataset,
    _json,
    _protocol,
    _publish,
)

SPLIT_VERSION = "whole_session_event_fold_v1"
MAX_MANIFEST_BYTES = 1_000_000
MAX_INPUT_BYTES = 64 * 1024 * 1024
MAX_SOURCES = 32
MAX_TOTAL_FRAMES = 10_000
FEATURE_NAMES = tuple(sorted(FEATURE_UNITS))


def _read_bytes(path, limit):
    if type(limit) is not int or limit <= 0:
        raise ValueError("Input byte budget exhausted.")
    path = Path(path)
    if path.name.endswith(".partial"):
        raise ValueError("Quarantined partial artifacts cannot be loaded.")
    with path.open("rb") as source:
        raw = source.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError("Empty input or input byte budget exceeded.")
    return raw


def _read_envelope(path, name, limit):
    raw = _read_bytes(path, limit)
    try:
        envelope = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (JournalError, RecursionError) as error:
        raise ValueError("Invalid artifact JSON.") from error
    if (
        type(envelope) is not dict
        or set(envelope) != {name, name + "_sha256"}
        or type(envelope[name]) is not dict
        or envelope[name + "_sha256"] != _hash(_json(envelope[name]))
    ):
        raise ValueError("Invalid artifact envelope or checksum.")
    return envelope[name], len(raw)


def _check_current(registration):
    if (
        registration.implementation_sha256 != _implementation_hash()
        or registration.environment_json != _environment()
    ):
        raise ValueError("Source/environment changed during event-fold verification.")


def _manifest(
    registration,
    *,
    training_session_count,
    max_frames_per_session,
    embargo_ns,
    minimum_resolved_per_session,
    minimum_resolved_fraction,
):
    research = tuple(s for s in registration.sources if s.role == "research")
    reserved = tuple(s for s in registration.sources if s.role == "reserved")
    if not 2 <= len(research) <= MAX_SOURCES:
        raise ValueError("An event fold requires 2-32 registered research sessions.")
    if type(training_session_count) is not int or not 1 <= training_session_count < len(research):
        raise ValueError("Training session count must leave nonempty train and validation groups.")
    if (
        type(max_frames_per_session) is not int
        or not 1 <= max_frames_per_session
        or max_frames_per_session * len(research) > MAX_TOTAL_FRAMES
    ):
        raise ValueError("Per-session frame budget must fit the 10000-frame aggregate cap.")
    _timestamp(embargo_ns)
    if (
        type(minimum_resolved_per_session) is not int
        or not 1 <= minimum_resolved_per_session <= max_frames_per_session
    ):
        raise ValueError("Positive minimum resolved count must fit the frame budget.")
    _money(minimum_resolved_fraction, zero=True)
    if minimum_resolved_fraction > 1:
        raise ValueError("Minimum resolved fraction must be in [0, 1].")
    train, validation = research[:training_session_count], research[training_session_count:]
    for earlier, later in ((train[-1], validation[0]), (validation[-1], reserved[0])):
        _timestamp(earlier.ended_at_ns + embargo_ns)
        if earlier.ended_at_ns + embargo_ns >= later.started_at_ns:
            raise ValueError("Whole-session boundary violates the strict outcome embargo.")
    return {
        "schema_version": 1,
        "artifact_type": "microstructure_event_split",
        "split_version": SPLIT_VERSION,
        "registration_sha256": registration.sha256,
        "implementation_sha256": registration.implementation_sha256,
        "environment_json": registration.environment_json,
        "label_version": LABEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "feature_units": dict(FEATURE_UNITS),
        "protocol_sha256": _hash(_json(_protocol(registration))),
        "training_session_count": training_session_count,
        "train_sessions": [s.source_session for s in train],
        "validation_sessions": [s.source_session for s in validation],
        "reserved_sessions": [s.source_session for s in reserved],
        "train_outcome_cutoff_ns": validation[0].started_at_ns,
        "validation_outcome_cutoff_ns": reserved[0].started_at_ns,
        "max_frames_per_session": max_frames_per_session,
        "embargo_ns": embargo_ns,
        "minimum_resolved_per_session": minimum_resolved_per_session,
        "minimum_resolved_fraction": str(minimum_resolved_fraction),
        "missingness": "preserve_null_no_imputation_or_scaling",
        "quality": "all_sessions_complete_fault_free_and_meet_declared_count_and_fraction",
        "selection": "resolved_only_with_all_other_statuses_accounted_for",
        "mode": "research_only",
        "training_started": False,
        "promotion_allowed": False,
        "live_trading_available": False,
    }


def register_event_split(
    *,
    registration_path: Path,
    output_path: Path,
    training_session_count: int,
    max_frames_per_session: int,
    embargo_ns: int,
    minimum_resolved_per_session: int,
    minimum_resolved_fraction: Decimal,
) -> dict:
    """Freeze assignments/settings from declaration metadata only; no dataset/capture IO."""
    registration = load_registration(registration_path)
    manifest = _manifest(
        registration,
        training_session_count=training_session_count,
        max_frames_per_session=max_frames_per_session,
        embargo_ns=embargo_ns,
        minimum_resolved_per_session=minimum_resolved_per_session,
        minimum_resolved_fraction=minimum_resolved_fraction,
    )
    _check_current(registration)
    _publish(manifest, output_path, payload_name="manifest", max_bytes=MAX_MANIFEST_BYTES)
    return manifest


def _load_manifest(path, registration):
    manifest, _ = _read_envelope(path, "manifest", MAX_MANIFEST_BYTES)
    names = (
        "training_session_count",
        "max_frames_per_session",
        "embargo_ns",
        "minimum_resolved_per_session",
        "minimum_resolved_fraction",
    )
    if not set(names) <= manifest.keys() or type(manifest["minimum_resolved_fraction"]) is not str:
        raise ValueError("Invalid event split settings.")
    settings = {k: manifest[k] for k in names}
    try:
        settings["minimum_resolved_fraction"] = Decimal(settings["minimum_resolved_fraction"])
    except InvalidOperation as error:
        raise ValueError("Invalid minimum resolved fraction.") from error
    expected = _manifest(registration, **settings)
    if _json(manifest) != _json(expected):
        raise ValueError("Event split differs from registered scope or current protocol/schema.")
    return manifest


@dataclass(frozen=True, slots=True)
class EventDatasetInput:
    source_session: str
    capture_path: Path
    dataset_path: Path

    def __post_init__(self):
        _identifier(self.source_session)
        if not isinstance(self.capture_path, Path) or not isinstance(self.dataset_path, Path):
            raise ValueError("Explicit Path objects are required for event inputs.")


def _load_dataset(registration, selected, *, byte_budget, expected_frames=None):
    source = registration.research_source(selected.source_session)  # Before either input read.
    dataset, used = _read_envelope(
        selected.dataset_path, "dataset", min(MAX_ARTIFACT_BYTES, byte_budget)
    )
    budget = dataset.get("max_frames")
    if (
        dataset.get("source_session") != source.source_session
        or dataset.get("source_sha256") != source.source_sha256
        or dataset.get("registration_sha256") != registration.sha256
        or type(budget) is not int
        or not 1 <= budget <= 10_000
        or (expected_frames is not None and budget != expected_frames)
    ):
        raise ValueError("Event dataset source, registration or frame budget mismatch.")
    raw = _read_bytes(selected.capture_path, min(MAX_BYTES, byte_budget - used))
    replay = CaptureReplay(
        raw,
        expected_sha256=source.source_sha256,
        source_session=source.source_session,
        config=registration.replay,
    )
    expected = _build_dataset(registration, replay, budget)
    # Exact canonical comparison also rejects bool/int/float substitutions and extra fields.
    if _json(dataset) != _json(expected):
        raise ValueError("Event artifact differs from source-reproduced features/outcomes.")
    return dataset, used + len(raw)


def load_verified_event_dataset(
    *, registration_path: Path, source_session: str, capture_path: Path, dataset_path: Path
) -> dict:
    """Verify, but do not quality-filter, one artifact including incomplete/faulted diagnostics."""
    registration = load_registration(registration_path)
    selected = EventDatasetInput(source_session, capture_path, dataset_path)
    dataset, _ = _load_dataset(registration, selected, byte_budget=MAX_INPUT_BYTES)
    _check_current(registration)
    return dataset


@dataclass(frozen=True, slots=True)
class EventPartition:
    """Features only in X; all targets/provenance separate. No fitted transformations."""

    feature_names: tuple[str, ...]
    source_sessions: tuple[str, ...]
    example_ids: tuple[str, ...]
    available_at_ns: tuple[int, ...]
    known_at_ns: tuple[int, ...]
    X: tuple[tuple[Decimal | int | bool | None, ...], ...]
    direction: tuple[int, ...]
    net_return_fraction: tuple[Decimal, ...]


@dataclass(frozen=True, slots=True)
class VerifiedEventSplit:
    train: EventPartition | None
    validation: EventPartition | None
    report: dict


def _partition(rows):
    return EventPartition(
        FEATURE_NAMES,
        tuple(r["source_session"] for r in rows),
        tuple(r["example_id"] for r in rows),
        tuple(r["feature_available_at_ns"] for r in rows),
        tuple(r["outcome"]["known_at_ns"] for r in rows),
        tuple(
            tuple(
                Decimal(value) if isinstance(value, str) else value
                for value in (r["features"][k] for k in FEATURE_NAMES)
            )
            for r in rows
        ),
        tuple(r["outcome"]["direction"] for r in rows),
        tuple(Decimal(r["outcome"]["net_return_fraction"]) for r in rows),
    )


def _quality(dataset, manifest):
    counts = dataset["outcome_counts"]
    resolved = counts.get("resolved", 0)
    eligible = resolved + counts.get("censored", 0) + counts.get("not_entered", 0)
    reasons = []
    if not dataset["session_consumed"]:
        reasons.append("incomplete_session")
    if dataset["market_fault_frames"]:
        reasons.append("market_fault")
    if resolved < manifest["minimum_resolved_per_session"]:
        reasons.append("insufficient_resolved_count")
    with localcontext(DECIMAL_CONTEXT):
        fraction = Decimal(resolved) / eligible if eligible else None
        if eligible == 0 or resolved < Decimal(manifest["minimum_resolved_fraction"]) * eligible:
            reasons.append("insufficient_resolved_fraction")
    return {
        "source_session": dataset["source_session"],
        "dataset_sha256": _hash(_json(dataset)),
        "source_sha256": dataset["source_sha256"],
        "frames_processed": dataset["frames_processed"],
        "session_consumed": dataset["session_consumed"],
        "market_fault_frames": dataset["market_fault_frames"],
        "outcome_counts": counts,
        "outcome_reason_counts": dataset["outcome_reason_counts"],
        "eligible_count": eligible,
        "resolved_fraction": None if fraction is None else str(fraction),
        "gate_failures": reasons,
    }


def load_event_split(
    *,
    registration_path: Path,
    manifest_path: Path,
    sources: tuple[EventDatasetInput, ...],
    report_path: Path | None = None,
) -> VerifiedEventSplit:
    """Verify ALL declared research sources; one failed quality gate blocks both partitions."""
    registration = load_registration(registration_path)
    manifest = _load_manifest(manifest_path, registration)
    research = tuple(s for s in registration.sources if s.role == "research")
    if (
        type(sources) is not tuple
        or any(type(s) is not EventDatasetInput for s in sources)
        or tuple(s.source_session for s in sources) != tuple(s.source_session for s in research)
    ):
        raise ValueError("Supply every research source, in declared order, exactly once.")
    used, reports = 0, []
    rows = {"train": [], "validation": []}
    for selected, declared in zip(sources, research, strict=True):
        dataset, size = _load_dataset(
            registration,
            selected,
            byte_budget=MAX_INPUT_BYTES - used,
            expected_frames=manifest["max_frames_per_session"],
        )
        used += size
        group = "train" if selected.source_session in manifest["train_sessions"] else "validation"
        cutoff = manifest[group + "_outcome_cutoff_ns"]
        for row in dataset["examples"]:
            available, known = row["feature_available_at_ns"], row["outcome"]["known_at_ns"]
            if not declared.started_at_ns <= available <= known <= declared.ended_at_ns:
                raise ValueError("Outcome availability crosses its declared source boundary.")
            if known + manifest["embargo_ns"] >= cutoff:
                raise ValueError("Outcome availability violates the strict fold embargo.")
            if row["outcome"]["status"] == "resolved":
                rows[group].append(row)
        reports.append({**_quality(dataset, manifest), "partition": group})
    _check_current(registration)
    passed = all(not s["gate_failures"] for s in reports)
    report = {
        "schema_version": 1,
        "artifact_type": "microstructure_event_split_verification",
        "manifest_sha256": _hash(_json(manifest)),
        "registration_sha256": registration.sha256,
        "split_version": SPLIT_VERSION,
        "verified_input_bytes": used,
        "sources": reports,
        "reserved_sessions": manifest["reserved_sessions"],
        "reserved_sources_opened": 0,
        "fold_available": passed,
        "train_rows": len(rows["train"]) if passed else 0,
        "validation_rows": len(rows["validation"]) if passed else 0,
        "mode": "research_only",
        "training_started": False,
        "promotion_allowed": False,
        "live_trading_available": False,
        "limitation": (
            "Declared engineering gates only, not statistical sufficiency or trading edge. "
            "Overlapping counterfactual labels are not independent trades. "
            "No test partition, model fitting, scaling or missing-value imputation."
        ),
    }
    result = VerifiedEventSplit(
        _partition(rows["train"]) if passed else None,
        _partition(rows["validation"]) if passed else None,
        report,
    )
    if report_path is not None:
        _publish(report, report_path, payload_name="report", max_bytes=MAX_MANIFEST_BYTES)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="Metadata only; freeze an event fold.")
    register.add_argument("--registration", type=Path, required=True)
    register.add_argument("--output", type=Path, required=True)
    register.add_argument("--training-session-count", type=int, required=True)
    register.add_argument("--max-frames-per-session", type=int, required=True)
    register.add_argument("--embargo-ns", type=int, required=True)
    register.add_argument("--minimum-resolved-per-session", type=int, required=True)
    register.add_argument("--minimum-resolved-fraction", type=Decimal, required=True)
    verify = commands.add_parser("verify", help="Reproduce artifacts; do not fit a model.")
    verify.add_argument("--registration", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument(
        "--source",
        nargs=3,
        action="append",
        required=True,
        metavar=("SESSION", "CAPTURE", "DATASET"),
    )
    verify.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        manifest = register_event_split(
            registration_path=args.registration,
            output_path=args.output,
            **{
                k: v
                for k, v in vars(args).items()
                if k not in ("command", "registration", "output")
            },
        )
        print(json.dumps({"manifest_sha256": _hash(_json(manifest)), "training_started": False}))
    else:
        result = load_event_split(
            registration_path=args.registration,
            manifest_path=args.manifest,
            sources=tuple(EventDatasetInput(s, Path(c), Path(d)) for s, c, d in args.source),
            report_path=args.report,
        )
        print(json.dumps(result.report, sort_keys=True))
        if not result.report["fold_available"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
