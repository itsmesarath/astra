"""Timestamp-sealed numerical model predictions on later research captures; no orders.

No labels, fitting, outcome scoring, account state, credential access or model promotion.
The seal records observed wall-clock availability, not a backdated deployment claim.
"""

import argparse
import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import localcontext
from itertools import islice
from pathlib import Path

import numpy as np

from ai_trader.research.microstructure_trial import load_registration
from ai_trader.trading.capture_replay import MAX_BYTES, CaptureReplay, ReplayFrame
from ai_trader.trading.microstructure_policy import (
    DECIMAL_CONTEXT as OBSERVATION_CONTEXT,
)
from ai_trader.trading.microstructure_policy import _validate_observation
from ai_trader.trading.paper_lifecycle import _timestamp
from ai_trader.trading.trade_case import _digest
from ai_trader.training.event_training_data import (
    FEATURE_NAMES,
    MAX_MANIFEST_BYTES,
    EventPartition,
    _check_current,
    _load_manifest,
    _read_bytes,
    _read_envelope,
)
from ai_trader.training.microstructure_data import (
    DECIMAL_CONTEXT,
    _eligibility,
    _features,
    _hash,
    _json,
    _protocol,
    _publish,
)
from ai_trader.training.train_event_baseline import (
    _decode_config,
    _load_completed_result,
    _model_from_payload,
    _model_payload,
    _recipe,
)

SHADOW_VERSION = "sealed_event_shadow_v1"
MAX_RESULT_BYTES = 16 * 1024 * 1024


def _binding(registration, manifest, recipe, model, result_sha256, available_at_ns):
    _digest(result_sha256)
    _timestamp(available_at_ns)
    evidence_end = max(s.ended_at_ns for s in registration.sources if s.role == "research")
    if available_at_ns < max(registration.registered_at_ns, evidence_end):
        raise ValueError("Model seal precedes registration or model-selection evidence.")
    expected = _recipe(registration, manifest, _decode_config(recipe.get("configuration")))
    if _json(recipe) != _json(expected):
        raise ValueError("Model recipe differs from the pinned training scope/protocol.")
    return {
        "schema_version": 1,
        "artifact_type": "event_shadow_model_seal",
        "shadow_version": SHADOW_VERSION,
        "available_at_ns": available_at_ns,
        "evidence_ended_at_ns": evidence_end,
        "registration_sha256": registration.sha256,
        "manifest_sha256": _hash(_json(manifest)),
        "recipe": recipe,
        "recipe_sha256": _hash(_json(recipe)),
        "baseline_result_sha256": result_sha256,
        "model": _model_payload(model),
        "model_sha256": _hash(_json(_model_payload(model))),
        "mode": "research_only",
        "promotion_allowed": False,
        "live_trading_available": False,
    }


def seal_event_shadow_model(
    *,
    training_registration_path: Path,
    manifest_path: Path,
    result_path: Path,
    expected_result_sha256: str,
    output_path: Path,
) -> dict:
    """Seal an already fitted single-baseline model now; do not read captures or fit anything."""
    registration = load_registration(training_registration_path)
    manifest = _load_manifest(manifest_path, registration)
    result, model = _load_completed_result(result_path, expected_sha256=expected_result_sha256)
    recipe, verification = result.get("recipe"), result.get("fold_verification")
    if type(recipe) is not dict or type(verification) is not dict:
        raise ValueError("Missing model provenance.")
    if (
        result.get("recipe_sha256") != _hash(_json(recipe))
        or verification.get("manifest_sha256") != _hash(_json(manifest))
        or verification.get("registration_sha256") != registration.sha256
        or verification.get("fold_available") is not True
        or type(verification.get("reserved_sources_opened")) is not int
        or verification["reserved_sources_opened"] != 0
    ):
        raise ValueError("Baseline does not carry passing provenance for the declared fold.")
    seal = _binding(registration, manifest, recipe, model, expected_result_sha256, time.time_ns())
    _check_current(registration)
    _publish(seal, output_path, payload_name="manifest", max_bytes=MAX_MANIFEST_BYTES)
    return seal


def _load_seal(path, expected_sha256, registration, manifest):
    _digest(expected_sha256)
    seal, _ = _read_envelope(path, "manifest", MAX_MANIFEST_BYTES)
    if _hash(_json(seal)) != expected_sha256:
        raise ValueError("Model seal differs from the caller-pinned checksum.")
    if type(seal.get("recipe")) is not dict:
        raise ValueError("Missing sealed recipe.")
    model = _model_from_payload(seal.get("model"))
    expected = _binding(
        registration,
        manifest,
        seal["recipe"],
        model,
        seal.get("baseline_result_sha256"),
        seal.get("available_at_ns"),
    )
    if _json(seal) != _json(expected):
        raise ValueError("Model seal differs from the current provenance/schema.")
    if seal["available_at_ns"] > time.time_ns():
        raise ValueError("Future model seal cannot be used.")
    return seal, model


@dataclass(frozen=True, slots=True)
class EventShadowConfig:
    max_frames: int
    decision_latency_ns: int
    prediction_ttl_ns: int

    def __post_init__(self):
        if type(self.max_frames) is not int or not 1 <= self.max_frames <= 10_000:
            raise ValueError("Frame budget must be an integer in [1, 10000].")
        _timestamp(self.decision_latency_ns)
        _timestamp(self.prediction_ttl_ns)
        if not self.prediction_ttl_ns:
            raise ValueError("Prediction TTL must be positive.")


def _source_scope(training, target, manifest, seal, source_session):
    source = target.research_source(source_session)  # Before any market-file read.
    if source.ended_at_ns > time.time_ns():
        raise ValueError("Future-dated shadow capture cannot be replayed.")
    if training.replay != target.replay or _protocol(training) != _protocol(target):
        raise ValueError(
            "Shadow feature/label protocol differs from the model's training contract."
        )
    for old in training.sources:
        if (
            old.source_session == source.source_session
            or old.source_sha256 == source.source_sha256
            or not (
                source.ended_at_ns < old.started_at_ns or source.started_at_ns > old.ended_at_ns
            )
        ):
            raise ValueError(
                "Shadow source reuses or overlaps a training/validation/reserved source."
            )
    if seal["available_at_ns"] + manifest["embargo_ns"] >= source.started_at_ns:
        raise ValueError("Shadow source must start strictly after model availability plus embargo.")
    return source


def _predict_frame(frame, model, registration, config):
    tick = frame.tick
    if frame.observation is not None:
        if frame.status != "observation":
            raise ValueError("Features must belong to a new depth observation.")
        with localcontext(OBSERVATION_CONTEXT):
            _validate_observation(frame.observation, tick, registration.replay.features)
    with localcontext(DECIMAL_CONTEXT):
        reason = _eligibility(frame, registration.policy, registration.gateway)
        features = None if frame.observation is None else _features(frame.observation)
    available = tick.observed_at_ns + config.decision_latency_ns
    expires = tick.observed_at_ns + config.prediction_ttl_ns
    _timestamp(available)
    _timestamp(expires)
    if frame.status.startswith("resync_required:"):
        reason = "market_fault"
    elif frame.status == "session_closed":
        reason = "session_closed"
    elif reason == "eligible":
        if available >= expires:
            reason = "prediction_expired_before_available"
        elif available - tick.quote_received_at_ns > registration.gateway.max_quote_age_ns:
            reason = "quote_stale_before_prediction_available"
        elif available - tick.last_trade_received_at_ns > registration.policy.maximum_trade_age_ns:
            reason = "trades_stale_before_prediction_available"
    probabilities = None
    if reason == "eligible":
        # Deliberately empty labels/outcome times. Inference consumes only schema and X.
        partition = EventPartition(
            FEATURE_NAMES, (), (), (), (), (tuple(features[k] for k in FEATURE_NAMES),), (), ()
        )
        values = model.predict_probabilities(partition)
        if (
            values.shape != (1, 3)
            or not np.isfinite(values).all()
            or np.any(values < 0)
            or np.any(values > 1)
            or not np.allclose(values.sum(axis=1), 1, rtol=0, atol=1e-12)
        ):
            raise ValueError("Invalid shadow probabilities.")
        probabilities = values[0].tolist()
    return {
        "tick_id": tick.tick_id,
        "source_line": frame.line_number,
        "observed_at_ns": tick.observed_at_ns,
        "observation_sha256": tick.observation_sha256,
        "frame_status": frame.status,
        "features": features,
        "features_sha256": _hash(_json(features)),
        "status": "predicted" if probabilities is not None else "abstained",
        "reason": reason,
        "probabilities": probabilities,
        "prediction_available_at_ns": available if probabilities is not None else None,
        "prediction_expires_at_ns": expires if probabilities is not None else None,
        "order_authorized": False,
    }


def replay_event_shadow(
    *,
    training_registration_path: Path,
    manifest_path: Path,
    seal_path: Path,
    expected_seal_sha256: str,
    source_registration_path: Path,
    source_session: str,
    capture_path: Path,
    config: EventShadowConfig,
    output_path: Path,
    enable_shadow: bool = False,
) -> dict:
    """Observe one later source, retaining abstentions; never read labels or create orders."""
    if enable_shadow is not True:
        raise ValueError("Explicit enable_shadow=True is required before any input access.")
    if type(config) is not EventShadowConfig:
        raise ValueError("Typed event shadow configuration required.")
    output_path = Path(output_path)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    training = load_registration(training_registration_path)
    manifest = _load_manifest(manifest_path, training)
    seal, model = _load_seal(seal_path, expected_seal_sha256, training, manifest)
    target = load_registration(source_registration_path)
    source = _source_scope(training, target, manifest, seal, source_session)
    raw = _read_bytes(capture_path, MAX_BYTES)
    replay = CaptureReplay(
        raw,
        expected_sha256=source.source_sha256,
        source_session=source_session,
        config=target.replay,
    )
    framing = replay._framing()
    if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
        source.started_at_ns,
        source.ended_at_ns,
    ):
        raise ValueError("Capture times differ from shadow declaration.")
    records, seen, prior_line, prior_time = [], set(), 0, -1
    for frame in islice(replay.frames(), config.max_frames):
        if type(frame) is not ReplayFrame:
            raise ValueError("Typed replay frame required.")
        tick = frame.tick
        if (
            tick.source_session != source_session
            or tick.tick_id in seen
            or frame.line_number <= prior_line
            or tick.observed_at_ns < prior_time
            or not source.started_at_ns <= tick.observed_at_ns <= source.ended_at_ns
        ):
            raise ValueError("Shadow frames must be ordered, unique and inside the source.")
        seen.add(tick.tick_id)
        prior_line, prior_time = frame.line_number, tick.observed_at_ns
        records.append(_predict_frame(frame, model, target, config))
    consumed = prior_line == replay.record_count
    faults = sum(r["reason"] == "market_fault" for r in records)
    _check_current(training)
    _check_current(target)
    report = json.loads(
        _json(
            {
                "schema_version": 1,
                "artifact_type": "event_model_shadow_replay",
                "shadow_version": SHADOW_VERSION,
                "seal_sha256": expected_seal_sha256,
                "model_sha256": seal["model_sha256"],
                "model_available_at_ns": seal["available_at_ns"],
                "source_registration_sha256": target.sha256,
                "source_session": source_session,
                "source_sha256": source.source_sha256,
                "configuration": asdict(config),
                "status": "completed" if consumed and not faults else "incomplete",
                "session_consumed": consumed,
                "market_fault_frames": faults,
                "frames_processed": len(records),
                "predictions": sum(r["status"] == "predicted" for r in records),
                "reason_counts": dict(Counter(r["reason"] for r in records)),
                "records": records,
                "mode": "research_only",
                "training_started": False,
                "orders": 0,
                "reserved_sources_opened": 0,
                "promotion_allowed": False,
                "live_trading_available": False,
                "limitation": (
                    "Non-executing sealed single-baseline shadow probabilities; "
                    "not calibrated trade signals, PnL or forward-service verification. "
                    "Latency is a declared simulation parameter, not measured compute time. "
                    "Consumers must recheck current source/state, "
                    "health and exclusive expiry; these records grant no execution authority."
                ),
            }
        )
    )
    _publish(report, output_path, payload_name="report", max_bytes=MAX_RESULT_BYTES)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    seal = commands.add_parser("seal", help="Seal one completed single-baseline model now.")
    seal.add_argument("--result", type=Path, required=True)
    seal.add_argument("--expected-result-sha256", required=True)
    replay = commands.add_parser("replay", help="Explicit non-executing later-source shadow.")
    for name in ("seal", "source-registration", "capture"):
        replay.add_argument("--" + name, type=Path, required=True)
    replay.add_argument("--source-session", required=True)
    replay.add_argument("--expected-seal-sha256", required=True)
    for name in ("max-frames", "decision-latency-ns", "prediction-ttl-ns"):
        replay.add_argument("--" + name, type=int, required=True)
    replay.add_argument("--enable-shadow", action="store_true")
    for command in (seal, replay):
        for name in ("training-registration", "manifest", "output"):
            command.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    common = dict(
        training_registration_path=args.training_registration,
        manifest_path=args.manifest,
        output_path=args.output,
    )
    if args.command == "seal":
        result = seal_event_shadow_model(
            **common,
            result_path=args.result,
            expected_result_sha256=args.expected_result_sha256,
        )
        print(json.dumps({"seal_sha256": _hash(_json(result)), "orders": 0}))
    else:
        result = replay_event_shadow(
            **common,
            seal_path=args.seal,
            expected_seal_sha256=args.expected_seal_sha256,
            source_registration_path=args.source_registration,
            source_session=args.source_session,
            capture_path=args.capture,
            enable_shadow=args.enable_shadow,
            config=EventShadowConfig(
                args.max_frames,
                args.decision_latency_ns,
                args.prediction_ttl_ns,
            ),
        )
        print(json.dumps({k: result[k] for k in ("status", "predictions", "orders")}))
        if result["status"] != "completed":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
