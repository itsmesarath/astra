"""Synthetic sealed-model shadow replay; never market/account/network activity."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal, localcontext

import numpy as np
import pytest
from test_event_training_data import tamper
from test_microstructure_campaign import shifted
from test_microstructure_data import rows_with_quote
from test_microstructure_policy import MS, capture_bytes
from test_train_event_baseline import setup as baseline_setup

from ai_trader.research import event_shadow as module
from ai_trader.research.microstructure_trial import SourceDeclaration, register_trial
from ai_trader.training import train_event_baseline as baseline


@pytest.fixture(autouse=True)
def no_external_side_effects(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network"))


def setup(tmp_path, monkeypatch, *, gap=False, bid="100", source_offset=100000):
    clock = [100000 * MS]
    monkeypatch.setattr(module.time, "time_ns", lambda: clock[0])
    train_dir = tmp_path / "train"
    train_dir.mkdir()
    training, _ = baseline_setup(train_dir)
    result = baseline.train_registered_event_baseline(**training)
    pin = module._hash(module._json(result))
    options = dict(
        training_registration_path=training["registration_path"],
        manifest_path=training["manifest_path"],
        result_path=training["output_path"],
        expected_result_sha256=pin,
        output_path=tmp_path / "seal.json",
    )
    seal = module.seal_event_shadow_model(**options)
    record = module.load_registration(training["registration_path"])
    rows = shifted(
        rows_with_quote(gap=gap, bid=bid, ask=str(Decimal(bid) + Decimal("0.01"))), ms=source_offset
    )
    raw = capture_bytes(rows)
    source = SourceDeclaration(
        "shadow-source",
        hashlib.sha256(raw).hexdigest(),
        rows[0]["started_at_ns"],
        rows[-1]["ended_at_ns"],
        "research",
    )
    clock[0] = 200000 * MS
    registration_path = tmp_path / "shadow-registration.json"
    register_trial(
        registration_path,
        trial_id="synthetic-shadow",
        sources=(
            source,
            SourceDeclaration(
                "shadow-reserved",
                "e" * 64,
                source.ended_at_ns + MS,
                source.ended_at_ns + 1000 * MS,
                "reserved",
            ),
        ),
        policy=record.policy,
        replay=record.replay,
        gateway=record.gateway,
        initial_cash_usdt=record.initial_cash_usdt,
    )
    capture = tmp_path / "shadow.jsonl"
    capture.write_bytes(raw)
    return (
        dict(
            training_registration_path=training["registration_path"],
            manifest_path=training["manifest_path"],
            seal_path=options["output_path"],
            expected_seal_sha256=module._hash(module._json(seal)),
            source_registration_path=registration_path,
            source_session=source.source_session,
            capture_path=capture,
            config=module.EventShadowConfig(100, 1 * MS, 100 * MS),
            output_path=tmp_path / "shadow-report.json",
            enable_shadow=True,
        ),
        options,
        training,
        clock,
    )


def test_seal_is_metadata_only_timestamped_pinned_and_exclusive(tmp_path, monkeypatch):
    args, options, training, clock = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_read_bytes", lambda *a: pytest.fail("Capture opened"))
    monkeypatch.setattr(baseline, "_fit", lambda *a: pytest.fail("Unexpected fitting"))
    seal = module.seal_event_shadow_model(**(options | {"output_path": tmp_path / "new-seal.json"}))
    assert seal["available_at_ns"] == clock[0]
    assert seal["available_at_ns"] > seal["evidence_ended_at_ns"]
    assert seal["baseline_result_sha256"] == options["expected_result_sha256"]
    assert seal["model_sha256"] == module._hash(module._json(seal["model"]))
    with pytest.raises(FileExistsError):
        module.seal_event_shadow_model(**options)
    assert not seal["promotion_allowed"] and not seal["live_trading_available"]


def test_shadow_infers_without_any_labels_refitting_or_execution(tmp_path, monkeypatch):
    args, _, training, _ = setup(tmp_path, monkeypatch)
    original, calls = baseline.EventBaselineModel.predict_probabilities, []

    def predict(self, partition):
        assert partition.direction == partition.known_at_ns == partition.net_return_fraction == ()
        calls.append(partition)
        return original(self, partition)

    monkeypatch.setattr(baseline.EventBaselineModel, "predict_probabilities", predict)
    monkeypatch.setattr(baseline, "_fit", lambda *a: pytest.fail("Unexpected fitting"))
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    report = module.replay_event_shadow(**args)
    assert report["status"] == "completed" and report["session_consumed"]
    assert report["predictions"] == len(calls) == 3
    assert report["frames_processed"] == 12 and report["orders"] == 0
    assert not report["training_started"] and not report["promotion_allowed"]
    assert report["reserved_sources_opened"] == 0
    assert {p: p.read_bytes() for p in before} == before
    assert not list(tmp_path.rglob("*.sqlite"))
    for row in report["records"]:
        assert "outcome" not in row and row["order_authorized"] is False
        if row["status"] == "predicted":
            assert row["prediction_available_at_ns"] == row["observed_at_ns"] + MS
            assert row["prediction_expires_at_ns"] == row["observed_at_ns"] + 100 * MS
            assert sum(row["probabilities"]) == pytest.approx(1)
        else:
            assert row["probabilities"] is row["prediction_available_at_ns"] is None


def test_source_feature_vectors_match_existing_causal_extractor(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    report = module.replay_event_shadow(**args)
    target = module.load_registration(args["source_registration_path"])
    replay = module.CaptureReplay.from_path(
        args["capture_path"],
        source_session=args["source_session"],
        config=target.replay,
        expected_sha256=target.sources[0].source_sha256,
    )
    for frame, row in zip(replay.frames(), report["records"], strict=True):
        if frame.observation is not None:
            with localcontext(module.DECIMAL_CONTEXT):
                features = module._features(frame.observation)
            assert row["features"] == json.loads(module._json(features))
            assert row["features_sha256"] == module._hash(module._json(features))


@pytest.mark.parametrize("gap", [False, True])
def test_later_price_or_fault_cannot_change_earlier_prediction(tmp_path, monkeypatch, gap):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    first_args, _, _, _ = setup(left, monkeypatch)
    first = module.replay_event_shadow(**first_args)
    later_args, _, _, _ = setup(right, monkeypatch, gap=gap, bid="101.2")
    later = module.replay_event_shadow(**later_args)

    def early(report):
        return [v for v in report["records"] if v["observed_at_ns"] < 101300 * MS]

    assert early(first) == early(later)
    if gap:
        assert later["status"] == "incomplete" and later["market_fault_frames"] == 2
        assert all(r["probabilities"] is None for r in later["records"][-2:])


@pytest.mark.parametrize(
    "latency,ttl,reason",
    [
        (100, 100, "prediction_expired_before_available"),
        (101, 100, "prediction_expired_before_available"),
        (1000, 2000, "quote_stale_before_prediction_available"),
    ],
)
def test_expiry_and_freshness_at_prediction_availability(
    tmp_path, monkeypatch, latency, ttl, reason
):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    result = module.replay_event_shadow(
        **(
            args
            | {
                "config": module.EventShadowConfig(100, latency * MS, ttl * MS),
            }
        )
    )
    assert result["predictions"] == 0
    assert result["reason_counts"][reason] == 3


def test_truncated_run_keeps_predictions_but_is_not_complete(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    result = module.replay_event_shadow(
        **(args | {"config": replace(args["config"], max_frames=5)})
    )
    assert result["status"] == "incomplete" and not result["session_consumed"]
    assert result["frames_processed"] == 5 and result["predictions"] == 1


@pytest.mark.parametrize("flag", [False, 1, "yes", None])
def test_activation_before_all_input_access(tmp_path, monkeypatch, flag):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "load_registration", lambda *a: pytest.fail("Input read"))
    with pytest.raises(ValueError, match="enable_shadow"):
        module.replay_event_shadow(**(args | {"enable_shadow": flag}))


@pytest.mark.parametrize(
    "changes",
    [
        {"max_frames": 0},
        {"max_frames": True},
        {"max_frames": 10001},
        {"decision_latency_ns": True},
        {"decision_latency_ns": -1},
        {"prediction_ttl_ns": 0},
        {"prediction_ttl_ns": 1.5},
    ],
)
def test_invalid_budgets_and_timestamps(changes):
    with pytest.raises(ValueError):
        module.EventShadowConfig(
            **(dict(max_frames=100, decision_latency_ns=0, prediction_ttl_ns=10) | changes)
        )


@pytest.mark.parametrize("source", ["shadow-reserved", "unknown"])
def test_reserved_or_unknown_source_denied_before_capture_read(tmp_path, monkeypatch, source):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "_read_bytes", lambda *a: pytest.fail("Capture read"))
    with pytest.raises(ValueError, match="research session"):
        module.replay_event_shadow(**(args | {"source_session": source}))


@pytest.mark.parametrize(
    "fault", ["identity", "alias", "overlap", "before_seal", "boundary", "future"]
)
def test_scope_time_and_alias_guards_before_capture_read(tmp_path, monkeypatch, fault):
    args, _, _, clock = setup(tmp_path, monkeypatch)
    training = module.load_registration(args["training_registration_path"])
    target = module.load_registration(args["source_registration_path"])
    source = target.sources[0]
    if fault == "identity":
        source = replace(source, source_session=training.sources[-1].source_session)
    elif fault == "alias":
        source = replace(source, source_sha256=training.sources[-1].source_sha256)
    elif fault == "overlap":
        source = replace(source, started_at_ns=training.sources[-1].started_at_ns)
    elif fault in ("before_seal", "boundary"):
        source = replace(source, started_at_ns=(99999 if fault == "before_seal" else 100000) * MS)
    else:
        clock[0] = source.ended_at_ns - 1
    target = replace(target, sources=(source, target.sources[1]))
    original = module.load_registration
    monkeypatch.setattr(
        module,
        "load_registration",
        lambda p: target if p == args["source_registration_path"] else original(p),
    )
    monkeypatch.setattr(module, "_read_bytes", lambda *a: pytest.fail("Capture read"))
    with pytest.raises(ValueError):
        module.replay_event_shadow(**(args | {"source_session": source.source_session}))


@pytest.mark.parametrize("fault", ["config", "protocol", "pin", "model", "provenance", "seal_time"])
def test_protocol_or_pinned_artifact_mismatch_fails_closed(tmp_path, monkeypatch, fault):
    args, options, _, _ = setup(tmp_path, monkeypatch)
    if fault in ("config", "protocol"):
        target = module.load_registration(args["source_registration_path"])
        target = (
            replace(target, replay=replace(target.replay, max_event_lag_ns=1))
            if fault == "config"
            else replace(target, policy=replace(target.policy, maximum_hold_ns=1))
        )
        original = module.load_registration
        monkeypatch.setattr(
            module,
            "load_registration",
            lambda p: target if p == args["source_registration_path"] else original(p),
        )
    elif fault == "pin":
        args["expected_seal_sha256"] = "0" * 64
    else:

        def change(seal):
            if fault == "model":
                seal["model"]["parameters"]["bias"] = [1, 2, 3]
            elif fault == "provenance":
                seal["recipe"]["feature_names"].reverse()
            else:
                seal["available_at_ns"] = 0

        tamper(args["seal_path"], "manifest", change)
        envelope = json.loads(args["seal_path"].read_bytes())
        args["expected_seal_sha256"] = envelope["manifest_sha256"]
    monkeypatch.setattr(module, "_read_bytes", lambda *a: pytest.fail("Capture read"))
    with pytest.raises(ValueError):
        module.replay_event_shadow(**args)
    assert not args["output_path"].exists()


def test_incorrect_result_pin_or_rehashed_provenance_cannot_be_sealed(tmp_path, monkeypatch):
    args, options, _, _ = setup(tmp_path, monkeypatch)
    output = tmp_path / "bad-seal.json"
    with pytest.raises(ValueError, match="pinned"):
        module.seal_event_shadow_model(
            **(options | {"output_path": output, "expected_result_sha256": "0" * 64})
        )
    tamper(
        options["result_path"],
        "report",
        lambda r: r["fold_verification"].update(fold_available=False),
    )
    bad_pin = json.loads(options["result_path"].read_bytes())["report_sha256"]
    with pytest.raises(ValueError, match="provenance"):
        module.seal_event_shadow_model(
            **(options | {"output_path": output, "expected_result_sha256": bad_pin})
        )
    assert not output.exists()


def test_prediction_rows_and_output_are_deterministic(tmp_path, monkeypatch):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    first = module.replay_event_shadow(**args)
    with localcontext() as context:
        context.prec = 7
        other = tmp_path / "other.json"
        assert module.replay_event_shadow(**(args | {"output_path": other})) == first
    assert args["output_path"].read_bytes() == other.read_bytes()
    with pytest.raises(FileExistsError):
        module.replay_event_shadow(**args)


@pytest.mark.parametrize("fault", ["checksum", "partial", "output_bytes", "drift", "probabilities"])
def test_corruption_limits_and_drift_never_publish_final_report(tmp_path, monkeypatch, fault):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    if fault == "checksum":
        args["capture_path"].write_bytes(args["capture_path"].read_bytes() + b"\n")
    elif fault == "partial":
        args["capture_path"] = tmp_path / "missing.partial"
    elif fault == "output_bytes":
        monkeypatch.setattr(module, "MAX_RESULT_BYTES", 1)
    elif fault == "drift":
        monkeypatch.setattr(
            module, "_check_current", lambda *a: (_ for _ in ()).throw(ValueError("drift"))
        )
    else:
        monkeypatch.setattr(
            baseline.EventBaselineModel,
            "predict_probabilities",
            lambda *a: np.array([[0.1, 0.2, float("nan")]]),
        )
    with pytest.raises(ValueError):
        module.replay_event_shadow(**args)
    assert not args["output_path"].exists()


def test_cli_shadow_compact_no_order_status(tmp_path, monkeypatch, capsys):
    args, _, _, _ = setup(tmp_path, monkeypatch)
    argv = [
        "shadow",
        "replay",
        "--enable-shadow",
        "--max-frames",
        "100",
        "--decision-latency-ns",
        "0",
        "--prediction-ttl-ns",
        str(100 * MS),
    ]
    for arg, key in (
        ("training-registration", "training_registration_path"),
        ("manifest", "manifest_path"),
        ("seal", "seal_path"),
        ("source-registration", "source_registration_path"),
        ("capture", "capture_path"),
        ("output", "output_path"),
        ("source-session", "source_session"),
        ("expected-seal-sha256", "expected_seal_sha256"),
    ):
        argv += ["--" + arg, str(args[key])]
    monkeypatch.setattr(sys, "argv", argv)
    module.main()
    assert json.loads(capsys.readouterr().out) == {
        "status": "completed",
        "predictions": 3,
        "orders": 0,
    }
