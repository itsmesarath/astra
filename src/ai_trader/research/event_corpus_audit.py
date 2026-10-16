"""Offline descriptive audit of pinned historical TRAIN artifacts, never fitting authority.

No raw replay, validation labels, reserved data, model fitting or execution. Historical
code pins remain historical; this report cannot make a stale trial eligible for training.
"""

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

from ai_trader.research.microstructure_trial import (
    MicrostructureRegistration,
    SourceDeclaration,
    _decode_gateway,
    _decode_policy,
    _decode_replay,
    _environment,
)
from ai_trader.trading.capture_replay import _implementation_hash
from ai_trader.trading.paper_lifecycle import _timestamp
from ai_trader.trading.trade_case import _digest
from ai_trader.trading.trade_journal import _constant, _decimal, _hash, _identifier, _pairs, _shape
from ai_trader.training.event_training_data import (
    MAX_INPUT_BYTES,
    MAX_MANIFEST_BYTES,
    _manifest,
    _quality,
    _read_bytes,
)
from ai_trader.training.microstructure_data import (
    BPS,
    DECIMAL_CONTEXT,
    FEATURE_SCHEMA_VERSION,
    FEATURE_UNITS,
    LABEL_VERSION,
    MAX_ARTIFACT_BYTES,
    _json,
    _protocol,
    _publish,
)


@dataclass(frozen=True, slots=True)
class PinnedArtifact:
    path: Path
    raw_sha256: str

    def __post_init__(self):
        if not isinstance(self.path, Path):
            raise ValueError("An explicit artifact Path is required.")
        _digest(self.raw_sha256)


@dataclass(frozen=True, slots=True)
class TrainingArtifact:
    source_session: str
    artifact: PinnedArtifact

    def __post_init__(self):
        _identifier(self.source_session)
        if type(self.artifact) is not PinnedArtifact:
            raise ValueError("A pinned training artifact is required.")


def _read(pinned, name, limit):
    if type(pinned) is not PinnedArtifact:
        raise ValueError("An explicit raw-file hash pin is required.")
    raw = _read_bytes(pinned.path, limit)
    if hashlib.sha256(raw).hexdigest() != pinned.raw_sha256:
        raise ValueError("Historical artifact raw-file pin mismatch.")
    envelope = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if (
        type(envelope) is not dict
        or set(envelope) != {name, name + "_sha256"}
        or type(envelope[name]) is not dict
        or envelope[name + "_sha256"] != _hash(_json(envelope[name]))
    ):
        raise ValueError("Invalid historical artifact envelope or checksum.")
    return envelope[name], len(raw)


def _historical_registration(payload):
    # Deliberately private to this descriptive audit. The guarded training/replay
    # load_registration API is unchanged and still refuses source/environment drift.
    value = _shape(payload, MicrostructureRegistration)
    if type(value["sources"]) is not list:
        raise ValueError("Expected historical source declarations.")
    value["sources"] = tuple(
        SourceDeclaration(**_shape(s, SourceDeclaration)) for s in value["sources"]
    )
    value["policy"] = _decode_policy(value["policy"])
    value["replay"] = _decode_replay(value["replay"])
    value["gateway"] = _decode_gateway(value["gateway"])
    value["initial_cash_usdt"] = _decimal(value["initial_cash_usdt"])
    record = MicrostructureRegistration(**value)
    if record.sha256 != _hash(_json(payload)):
        raise ValueError("Historical registration is not canonical.")
    return record


def _split(payload, registration):
    names = (
        "training_session_count",
        "max_frames_per_session",
        "embargo_ns",
        "minimum_resolved_per_session",
        "minimum_resolved_fraction",
    )
    if not set(names) <= payload.keys():
        raise ValueError("Missing historical split settings.")
    settings = {key: payload[key] for key in names}
    settings["minimum_resolved_fraction"] = _decimal(settings["minimum_resolved_fraction"])
    if _json(payload) != _json(_manifest(registration, **settings)):
        raise ValueError("Historical split differs from supported declared protocol/schema.")


def _number(value):
    # Labels use 100-digit Decimal arithmetic, not the ledger's narrower money type.
    if type(value) is not str or len(value) > 256:
        raise ValueError("Expected a bounded decimal string.")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid decimal string.") from error
    if not number.is_finite() or not -200 <= number.as_tuple().exponent <= 200:
        raise ValueError("Nonfinite or oversized historical number.")
    return number


def _stats(values):
    return (
        None
        if not values
        else {
            "count": len(values),
            "min": str(min(values)),
            "max": str(max(values)),
            "mean": str(sum(values) / len(values)),
        }
    )


def _coverage(sources):
    return {
        "sessions": len(sources),
        "declared_duration_ns": sum(s.ended_at_ns - s.started_at_ns for s in sources),
        "first_started_at_ns": sources[0].started_at_ns,
        "last_ended_at_ns": sources[-1].ended_at_ns,
        "elapsed_span_ns": sources[-1].ended_at_ns - sources[0].started_at_ns,
        "distinct_utc_start_dates": len(
            {datetime.fromtimestamp(s.started_at_ns // 1_000_000_000, UTC).date() for s in sources}
        ),
        "regime_coverage": "not_established_from_declarations",
    }


def _rows(dataset, registration, manifest, source):
    protocol = _protocol(registration)
    bound = {
        "schema_version": 1,
        "artifact_type": "microstructure_event_labels",
        "label_version": LABEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_units": FEATURE_UNITS,
        "registration_sha256": registration.sha256,
        "implementation_sha256": registration.implementation_sha256,
        "environment_json": registration.environment_json,
        "source_session": source.source_session,
        "source_sha256": source.source_sha256,
        "source_started_at_ns": source.started_at_ns,
        "source_ended_at_ns": source.ended_at_ns,
        "protocol": protocol,
        "protocol_sha256": _hash(_json(protocol)),
        "max_frames": manifest["max_frames_per_session"],
        "mode": "research_only",
        "promotion_allowed": False,
        "training_started": False,
        "live_trading_available": False,
    }
    extra = {
        "frames_processed",
        "session_consumed",
        "market_fault_frames",
        "outcome_counts",
        "outcome_reason_counts",
        "examples",
        "limitation",
    }
    if set(dataset) != set(bound) | extra or any(
        _json(dataset[key]) != _json(value) for key, value in bound.items()
    ):
        raise ValueError("Training dataset binding/schema mismatch.")
    rows = dataset["examples"]
    if (
        type(rows) is not list
        or not 1 <= len(rows) <= manifest["max_frames_per_session"]
        or type(dataset["frames_processed"]) is not int
        or dataset["frames_processed"] != len(rows)
        or type(dataset["session_consumed"]) is not bool
        or type(dataset["limitation"]) is not str
    ):
        raise ValueError("Invalid training dataset frame accounting.")
    row_keys = {
        "example_id",
        "source_session",
        "source_line",
        "tick_id",
        "feature_available_at_ns",
        "observation_sha256",
        "frame_status",
        "features",
        "features_sha256",
        "eligibility_reason",
        "outcome",
    }
    outcome_keys = {
        "status",
        "reason",
        "known_at_ns",
        "entry_at_ns",
        "entry_price_usdt",
        "horizon_at_ns",
        "exit_at_ns",
        "exit_price_usdt",
        "net_return_fraction",
        "direction",
    }
    fee = registration.gateway.costs.taker_fee_bps / BPS
    seen, last_line, last_time, resolved = set(), 0, -1, []
    for row in rows:
        if type(row) is not dict or set(row) != row_keys:
            raise ValueError("Invalid training row schema.")
        _identifier(row["tick_id"])
        expected_id = _hash(LABEL_VERSION + ":" + registration.sha256 + ":" + row["tick_id"])
        if (
            row["source_session"] != source.source_session
            or row["example_id"] != expected_id
            or expected_id in seen
            or type(row["source_line"]) is not int
            or row["source_line"] <= last_line
        ):
            raise ValueError("Training row source, identity or ordering mismatch.")
        seen.add(expected_id)
        features = row["features"]
        if row["features_sha256"] != _hash(_json(features)) or (
            features is not None
            and (type(features) is not dict or features.keys() != FEATURE_UNITS.keys())
        ):
            raise ValueError("Training feature schema/checksum mismatch.")
        if features is not None:
            for key, unit in FEATURE_UNITS.items():
                value = features[key]
                if value is None:
                    continue
                if unit == "boolean":
                    if type(value) is not bool:
                        raise ValueError("Invalid boolean feature.")
                elif unit == "count":
                    if type(value) is not int or not 0 <= value <= 2**63 - 1:
                        raise ValueError("Invalid count feature.")
                else:
                    _number(value)
        if row["observation_sha256"] is not None:
            _digest(row["observation_sha256"])
        _identifier(row["frame_status"])
        _identifier(row["eligibility_reason"])
        outcome = row["outcome"]
        if type(outcome) is not dict or set(outcome) != outcome_keys:
            raise ValueError("Invalid training outcome schema.")
        available, known = row["feature_available_at_ns"], outcome["known_at_ns"]
        _timestamp(available)
        _timestamp(known)
        if (
            not source.started_at_ns <= available <= known <= source.ended_at_ns
            or available < last_time
            or known + manifest["embargo_ns"] >= manifest["train_outcome_cutoff_ns"]
        ):
            raise ValueError("Training outcome crosses source/order/embargo boundary.")
        last_line, last_time = row["source_line"], available
        status = outcome["status"]
        if status not in ("resolved", "censored", "not_entered", "excluded"):
            raise ValueError("Unknown or pending outcome in completed dataset.")
        _identifier(outcome["reason"])
        if (row["eligibility_reason"] == "eligible") != (status != "excluded"):
            raise ValueError("Outcome eligibility mismatch.")
        if status == "excluded" and (
            known != available or outcome["reason"] != row["eligibility_reason"]
        ):
            raise ValueError("Excluded outcome must retain its contemporaneous reason.")
        if outcome["entry_at_ns"] is not None:
            _timestamp(outcome["entry_at_ns"])
            _timestamp(outcome["horizon_at_ns"])
            if (
                not available < outcome["entry_at_ns"] <= known
                or outcome["entry_at_ns"] >= available + registration.policy.entry_ttl_ns
                or outcome["horizon_at_ns"]
                != outcome["entry_at_ns"] + registration.policy.maximum_hold_ns
                or _number(outcome["entry_price_usdt"]) <= 0
                or status in ("excluded", "not_entered")
            ):
                raise ValueError("Invalid causal entry/horizon.")
        elif outcome["entry_price_usdt"] is not None or outcome["horizon_at_ns"] is not None:
            raise ValueError("Entry fields must be jointly present or absent.")
        if status != "resolved":
            if any(
                outcome[k] is not None
                for k in (
                    "exit_at_ns",
                    "exit_price_usdt",
                    "net_return_fraction",
                    "direction",
                )
            ):
                raise ValueError("Unresolved outcomes cannot carry numeric targets.")
            continue
        entry = _number(outcome["entry_price_usdt"])
        exit_price = _number(outcome["exit_price_usdt"])
        net = _number(outcome["net_return_fraction"])
        _timestamp(outcome["exit_at_ns"])
        if (
            features is None
            or row["frame_status"] != "observation"
            or outcome["entry_at_ns"] is None
            or exit_price <= 0
            or not outcome["entry_at_ns"] < outcome["exit_at_ns"] == known
            or outcome["reason"] not in ("stop", "target", "horizon")
            or (outcome["reason"] == "horizon" and known < outcome["horizon_at_ns"])
            or type(outcome["direction"]) is not int
            or outcome["direction"] != (1 if net > 0 else -1 if net < 0 else 0)
        ):
            raise ValueError("Invalid resolved outcome.")
        debit = entry * (1 + fee)
        if net != (exit_price * (1 - fee) - debit) / debit:
            raise ValueError("Resolved net return differs from frozen fee arithmetic.")
        resolved.append(row)
    expected = {
        "outcome_counts": dict(Counter(r["outcome"]["status"] for r in rows)),
        "outcome_reason_counts": dict(Counter(r["outcome"]["reason"] for r in rows)),
        "market_fault_frames": sum(r["frame_status"].startswith("resync_required:") for r in rows),
    }
    if any(_json(dataset[key]) != _json(value) for key, value in expected.items()):
        raise ValueError("Training outcome/fault accounting mismatch.")
    return resolved


def _describe(rows, slip):
    net, pre_fee, quote, intervals = [], [], [], []
    counts = Counter(r["outcome"]["direction"] for r in rows)
    for row in rows:
        outcome = row["outcome"]
        ratio = _number(outcome["exit_price_usdt"]) / _number(outcome["entry_price_usdt"])
        net.append(_number(outcome["net_return_fraction"]) * BPS)
        pre_fee.append((ratio - 1) * BPS)
        quote.append((ratio * (1 + slip) / (1 - slip) - 1) * BPS)
        intervals.append((outcome["known_at_ns"], row["feature_available_at_ns"]))
    # Earliest-finish scheduling counts disjoint CLOSED intervals; it does not select
    # training rows or establish statistical independence/effective sample size.
    last, disjoint = -1, 0
    for end, start in sorted(intervals):
        if start > last:
            last, disjoint = end, disjoint + 1
    return {
        "resolved_rows": len(rows),
        "class_counts_loss_breakeven_profit": [counts[k] for k in (-1, 0, 1)],
        "observed_classes": len(counts),
        "maximum_nonoverlapping_label_intervals": disjoint,
        "net_return_bps": _stats(net),
        "slipped_exit_over_entry_return_bps_before_fees": _stats(pre_fee),
        "inferred_exit_bid_over_entry_ask_return_bps_before_costs": _stats(quote),
        "resolved_exit_reasons": dict(Counter(r["outcome"]["reason"] for r in rows)),
    }


def audit_event_corpus(*, registration, manifest, training, output_path=None):
    """Audit exact pinned training artifacts; never return a fit-ready partition/model."""
    audit_code, audit_environment = _implementation_hash(), _environment()
    if output_path is not None and (
        Path(output_path).exists() or Path(str(output_path) + ".partial").exists()
    ):
        raise FileExistsError(output_path)
    payload, used = _read(registration, "registration", MAX_MANIFEST_BYTES)
    record = _historical_registration(payload)
    split, size = _read(manifest, "manifest", MAX_MANIFEST_BYTES)
    used += size
    _split(split, record)
    if (
        type(training) is not tuple
        or any(type(t) is not TrainingArtifact for t in training)
        or [t.source_session for t in training] != split["train_sessions"]
    ):
        raise ValueError("Supply exactly every training session in declared order, no other roles.")
    with localcontext(DECIMAL_CONTEXT):
        fee, slip = (
            record.gateway.costs.taker_fee_bps / BPS,
            record.gateway.costs.slippage_bps / BPS,
        )
        if not 0 <= fee < 1 or not 0 <= slip < 1:
            raise ValueError("Cost fractions must be in [0, 1) for break-even arithmetic.")
        reports, pooled = [], []
        for selected in training:
            source = record.research_source(selected.source_session)
            dataset, size = _read(
                selected.artifact, "dataset", min(MAX_ARTIFACT_BYTES, MAX_INPUT_BYTES - used)
            )
            used += size
            rows = _rows(dataset, record, split, source)
            pooled.extend(rows)
            reports.append(
                {
                    "quality_from_artifact_not_replay": _quality(dataset, split),
                    "training_artifact_raw_sha256": selected.artifact.raw_sha256,
                    "description": _describe(rows, slip),
                }
            )
        description = _describe(pooled, slip)
        break_even = ((1 + slip) * (1 + fee) / ((1 - slip) * (1 - fee)) - 1) * BPS
        blockers = []
        if any(s["quality_from_artifact_not_replay"]["gate_failures"] for s in reports):
            blockers.append("training_artifact_quality_failure")
        if description["observed_classes"] < 2:
            blockers.append("insufficient_training_classes")
        groups = {
            group: tuple(
                s for s in record.sources if s.source_session in split[group + "_sessions"]
            )
            for group in ("train", "validation", "reserved")
        }
        report = {
            "schema_version": 1,
            "artifact_type": "historical_event_corpus_audit",
            "evidence_scope": "pinned_historical_artifacts_not_new_source_replay",
            "registration_sha256": record.sha256,
            "manifest_sha256": _hash(_json(split)),
            "registration_raw_sha256": registration.raw_sha256,
            "manifest_raw_sha256": manifest.raw_sha256,
            "historical_implementation_sha256": record.implementation_sha256,
            "historical_environment_json": record.environment_json,
            "audit_implementation_sha256": audit_code,
            "audit_environment_json": audit_environment,
            "declared_coverage_metadata_only": {k: _coverage(v) for k, v in groups.items()},
            "training_sources": reports,
            "training_summary": description,
            "observed_training_blockers": blockers,
            "fixed_protocol": _protocol(record),
            "break_even_exit_bid_over_entry_ask_return_bps": str(break_even),
            "verified_artifact_bytes": used,
            "raw_captures_opened": 0,
            "validation_datasets_opened": 0,
            "reserved_datasets_opened": 0,
            "readiness": "not_established_by_descriptive_audit",
            "mode": "research_only",
            "training_allowed": False,
            "training_started": False,
            "promotion_allowed": False,
            "live_trading_available": False,
            "limitations": [
                "Pins check consistency, not origin/authenticity or raw feature/quote correctness.",
                "Historical session-consumption and quality fields are not newly replay-verified.",
                "Overlapping counterfactuals are not trades, portfolio PnL or independent samples.",
                "Disjoint intervals do not establish statistical independence or regime coverage.",
                "Quote returns undo the recorded slippage assumption; they are not a fill model.",
                "Break-even uses entry ask and exit bid; barriers are anchored to the feature bid.",
                "No cost/target tuning, balancing, validation evaluation or training authority.",
            ],
        }
    if audit_code != _implementation_hash() or audit_environment != _environment():
        raise ValueError("Audit source/environment changed; nothing published.")
    if output_path is not None:
        _publish(report, output_path, payload_name="report", max_bytes=MAX_MANIFEST_BYTES)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", nargs=2, metavar=("PATH", "RAW_SHA256"), required=True)
    parser.add_argument("--manifest", nargs=2, metavar=("PATH", "RAW_SHA256"), required=True)
    parser.add_argument(
        "--training",
        nargs=3,
        action="append",
        metavar=("SESSION", "PATH", "RAW_SHA256"),
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_event_corpus(
        registration=PinnedArtifact(Path(args.registration[0]), args.registration[1]),
        manifest=PinnedArtifact(Path(args.manifest[0]), args.manifest[1]),
        training=tuple(
            TrainingArtifact(s, PinnedArtifact(Path(p), h)) for s, p, h in args.training
        ),
        output_path=args.output,
    )
    print(_json(report))


if __name__ == "__main__":
    main()
