"""Causal filters, whole-session permissions and independently checked CPU arithmetic."""

import json
import math
from copy import deepcopy
from datetime import date

import numpy as np
import pytest
from test_historical_6e_cohort import records_for, write_json
from test_historical_6e_manifest import census_root as census_root
from test_historical_6e_manifest import evidence as evidence
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import metadata_root as metadata_root
from test_historical_6e_manifest import protected_evidence as protected_evidence

from ai_trader.research import six_e_liquidity_study as s

r, t = s.rules, s.exits.target
DAY = "2025-04-07"
START = t.window(DAY)[0]


def row(second=0, direction=1):
    f = dict.fromkeys(r.flow.data.FEATURES, 0.0)
    f.update(
        log_bid_qty=math.log1p(5),
        log_ask_qty=math.log1p(5),
        log_bid_depth5=math.log1p(20),
        log_ask_depth5=math.log1p(20),
        bid_top_share5=0.25,
        ask_top_share5=0.25,
        bid_span5_ticks=4.0,
        ask_span5_ticks=4.0,
        log_known_trades_5s=math.log1p(20),
        log_quote_events_5s=math.log1p(20),
        normalized_cvd_5s=direction * 0.5,
        normalized_ofi_5s=direction * 0.5,
        mid_change_5s_ticks=float(direction),
        mid_range_5s_ticks=4.0,
    )
    return {
        "source_session": DAY,
        "contract": "6EM5",
        "partition": "development",
        "decision_ts_ns": START + second * t.SECOND,
        "features": f,
        "execution_features": dict.fromkeys(r.flow.FEATURES, 0.0),
        "outcome": object(),
        "eligible": object(),
    }


def label(source, available=True, long=4.0, short=-3.0):
    return {
        **{k: source[k] for k in ("source_session", "contract", "partition", "decision_ts_ns")},
        "eligible": True,
        "outcomes": {
            "bracket_exit": {
                "long": {
                    "status": "resolved" if available else "unresolved_exit_quote_timeout",
                    "net_ticks": long if available else object(),
                },
                "short": {
                    "status": "resolved" if available else "unresolved_exit_quote_timeout",
                    "net_ticks": short if available else object(),
                },
            }
        },
    }


def training():
    rows = [row(i * 60) for i in range(22)]
    labels = [label(x, i < 20) for i, x in enumerate(rows)]
    return rows, labels


@pytest.mark.parametrize("direction", [1, -1])
def test_mirrored_causal_follow_and_absorption_are_separate(direction):
    follow = row(direction=direction)
    assert r.rules([follow])["liquidity_follow"].tolist() == [direction]
    fade = deepcopy(follow)
    fade["features"]["mid_change_5s_ticks"] = 0
    fade["features"]["queue_imbalance"] = -direction * 0.5
    side = "ask" if direction > 0 else "bid"
    fade["execution_features"].update(
        {f"{side}_held_top_passive_5s": 0.25, f"{side}_other_id_reload_5s": 0.1}
    )
    directions = r.rules([fade])
    assert directions["absorption_fade"].tolist() == [-direction]
    assert directions["liquidity_follow"].tolist() == [0]


@pytest.mark.parametrize(
    "name,value",
    [
        ("log_prior_quote_gap_ms", math.log1p(250) + 1e-9),
        ("unknown_trade_fraction_5s", 0.1000001),
        ("log_bid_qty", math.log1p(5) - 1e-9),
        ("log_ask_qty", math.log1p(5) - 1e-9),
        ("log_bid_depth5", math.log1p(20) - 1e-9),
        ("log_ask_depth5", math.log1p(20) - 1e-9),
        ("bid_span5_ticks", 8.00000001),
        ("ask_span5_ticks", 8.00000001),
        ("log_quote_events_5s", math.log1p(20) - 1e-9),
        ("log_known_trades_5s", 0.0),
    ],
)
def test_liquidity_gate_boundary_refuses_only_causal_deficiencies(name, value):
    source = row()
    assert r.liquid(source["features"])
    source["features"][name] = value
    assert not r.liquid(source["features"])
    assert r.rules([source])["liquidity_follow"].tolist() == [0]


def test_outcome_poison_and_future_suffix_never_change_features_or_rules():
    rows = [row(i) for i in range(5)]
    expected = r.rules(rows)
    poisoned = deepcopy(rows)
    for item in poisoned:
        item.update(
            outcome=object(),
            eligible=object(),
            hindsight_action=object(),
            net_targets_long_short_ticks=object(),
        )
    for name, values in r.rules(poisoned).items():
        np.testing.assert_array_equal(values, expected[name])
        np.testing.assert_array_equal(values[:3], r.rules(poisoned[:3])[name])
    np.testing.assert_array_equal(r.matrix(rows), r.matrix(poisoned))


@pytest.mark.parametrize(
    "change",
    [
        "reserved",
        "later_role",
        "contract",
        "timestamp",
        "bool",
        "nan",
        "extra",
        "negative_proxy",
        "imbalance",
        "log",
    ],
)
def test_strict_feature_training_permissions(change):
    rows, labels = training()
    if change == "reserved":
        rows[0]["source_session"] = "2026-01-01"
    elif change == "later_role":
        rows[0]["source_session"] = "2025-10-07"
    elif change == "contract":
        rows[0]["contract"] = "6EU5"
    elif change == "timestamp":
        rows[0]["decision_ts_ns"] += 86400 * t.SECOND
    elif change == "bool":
        rows[0]["features"]["queue_imbalance"] = True
    elif change == "nan":
        rows[0]["features"]["queue_imbalance"] = float("nan")
    elif change == "extra":
        rows[0]["features"]["future_profit"] = 1
    elif change == "negative_proxy":
        rows[0]["execution_features"][r.flow.FEATURES[0]] = -1
    elif change == "imbalance":
        rows[0]["features"]["queue_imbalance"] = 2
    else:
        rows[0]["features"]["log_bid_qty"] = -1
    with pytest.raises(ValueError):
        r.fit(rows, labels)


def test_joint_unknowns_train_availability_not_fake_zero_returns_and_verifier_never_fits(
    monkeypatch,
):
    rows, labels = training()
    model, stats = r.fit(rows, labels)
    assert stats["train_cases"] == 22 and stats["unknown"] == 2
    assert model.predict(r.matrix(rows))[0].tolist() == pytest.approx([20 / 22, 4, -3])
    monkeypatch.setattr(r.np.linalg, "solve", lambda *a: pytest.fail("verifier refitted"))
    r.verify_fit(model, rows, labels, stats)


@pytest.mark.parametrize("kind", ["weights", "scaler", "accounting"])
def test_repinned_model_arithmetic_still_requires_frozen_train_equations(kind):
    rows, labels = training()
    model, stats = r.fit(rows, labels)
    if kind == "weights":
        model.bias[1] += 0.01
    elif kind == "scaler":
        model.means[0] += 0.01
    else:
        stats["train_cases"] += 1
    with pytest.raises(ValueError):
        r.verify_fit(model, rows, labels, stats)


def test_negative_targets_retained_and_train_sampling_ignores_future_validity():
    rows, labels = training()
    for i, y in enumerate(labels[:20]):
        y["outcomes"]["bracket_exit"]["long"]["net_ticks"] = -10 if i < 10 else 4
    model, stats = r.fit(rows, labels)
    assert stats["conditional_target_means"] == [-3, -3]
    assert not r.actions(model.predict(r.matrix(rows))).any()
    all_rows = [row(i) for i in range(121)]
    all_labels = [label(x, False) for x in all_rows]
    assert r.sample(all_rows, all_labels) == [0, 60, 120]


def test_action_availability_margin_and_tie_guards():
    p = np.array(
        [[0.90, 0.500001, 0], [0.899999, 5, 0], [1, 0.5, -2], [1, 5, 5], [1, -2, 5], [1, -1, -2]]
    )
    assert r.actions(p).tolist() == [1, 0, 0, 0, -1, 0]
    with pytest.raises(ValueError):
        r.actions(np.array([[1.01, 4, -3]]))


def native(tmp_path):
    builder = s.resource.DiskDailyBuilder(DAY, "6EM5", tmp_path / "quotes")
    builder.start_day(date.fromisoformat(DAY))
    for record in records_for(date.fromisoformat(DAY), "6EM5"):
        builder.consume(record)
    builder.finish_day()
    rows, _, _ = builder.finish()
    return rows, builder.spool.count


def test_segmented_disk_targets_equal_native_full_array_and_overflow_is_not_truncation(
    tmp_path, monkeypatch
):
    rows, count = native(tmp_path)
    with s.resource.QuoteView(tmp_path / "quotes", count) as view:
        expected = t.targets(rows, view[:])
        monkeypatch.setattr(s, "CHUNK_ROWS", 3)
        assert s.targets(rows, view) == expected
        monkeypatch.setattr(s.resource, "CHUNK_QUOTES", 20)
        monkeypatch.setattr(t.previous.census.paths, "MAX_QUOTES", 60)
        with pytest.raises(ValueError):
            t.targets(rows, view[:])
        assert s.targets(rows, view) == expected


def test_reserved_target_guard_precedes_native_quote_access():
    with pytest.raises(ValueError):
        s.targets([{"source_session": "2026-01-01"}], object())


@pytest.fixture
def study(manifest_evidence, monkeypatch):
    root, manifest_path, manifest_pin, _ = manifest_evidence
    monkeypatch.setattr(r, "SAMPLE_NS", t.SECOND)
    monkeypatch.setattr(s, "MIN_JOINT_TRAIN", 10)
    monkeypatch.setattr(s, "MIN_UNKNOWN_TRAIN", 1)
    registration = root / "logs/liquidity-registration.json"
    registration.parent.mkdir(exist_ok=True)
    s.prepare(root, manifest_path, manifest_pin, registration, True)
    return root, registration, s.common.hash_file(registration, 2 * 1024**2)


def test_complete_cohort_collection_fit_and_readonly_verifiers(study, monkeypatch):
    root, path, pin = study
    output = root / "data/processed/liquidity-build"
    built = s.collect(root, path, pin, output)
    assert built["sessions"] == 9 and built["rows"] == 1170
    assert not any(built["flags"].values())
    cost = root / "data/processed/liquidity-cost"
    result = s.evaluate(root, path, pin, output, built["completion_sha256"], cost)
    assert result["sessions"] == 9 and result["flags"]["cpu_training"] is True
    assert not result["flags"]["trading_enabled"]
    monkeypatch.setattr(r, "fit", lambda *a: pytest.fail("verification fits"))
    assert (
        s.verify_evaluation(
            root, path, pin, output, built["completion_sha256"], cost, result["completion_sha256"]
        )
        == result
    )
    with pytest.raises(FileExistsError):
        s.collect(root, path, pin, output)
    with pytest.raises(FileExistsError):
        s.evaluate(root, path, pin, output, built["completion_sha256"], cost)


@pytest.mark.parametrize("kind", ["targets", "pooled", "flags", "coverage"])
def test_collection_repinned_mutations_cannot_pass_recomputation(study, kind):
    root, path, pin = study
    output = root / "data/processed/liquidity-build"
    s.collect(root, path, pin, output)
    completion = output / "completion.json"
    report = json.loads(completion.read_bytes())
    if kind == "targets":
        target = output / f"{report['days'][0]['utc_date']}.targets.jsonl"
        labels = [json.loads(line) for line in target.read_bytes().splitlines()]
        labels[0]["hindsight_states"]["bracket_exit"] = "long_only"
        target.write_bytes(s.census.encode_rows(labels))
        report["days"][0]["targets_sha256"] = s.common.hash_file(target, s.census.MAX_DAY_BYTES)
    elif kind == "pooled":
        report["summaries"]["overall"]["rows"] += 1
    elif kind == "flags":
        report["flags"]["trading_enabled"] = True
    else:
        report["days"].pop()
    write_json(completion, report)
    with pytest.raises(ValueError):
        s.verify_collection(root, path, pin, output, s.common.hash_file(completion, 2 * 1024**2))


def test_failure_retains_evidence_and_never_fits_successful_subset(study, monkeypatch):
    root, path, pin = study
    monkeypatch.setattr(
        s.resource, "replay_day", lambda *a: (_ for _ in ()).throw(ValueError("failed replay"))
    )
    output = root / "data/processed/failure"
    with pytest.raises(ValueError):
        s.collect(root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    with pytest.raises(FileExistsError):
        s.collect(root, path, pin, output)


def test_permission_and_protocol_drift_fail_before_raw_access(study, monkeypatch):
    root, path, pin = study
    frozen = s.registration(root, path, pin)
    with pytest.raises(ValueError):
        s.prepare(
            root,
            root / frozen["manifest"]["path"],
            frozen["manifest"]["sha256"],
            root / "logs/new.json",
            False,
        )
    monkeypatch.setattr(s.resource, "replay_day", lambda *a: pytest.fail("raw replay after drift"))
    monkeypatch.setattr(r, "EDGE", 0.1)
    with pytest.raises(ValueError):
        s.collect(root, path, pin, root / "data/processed/drift")


def test_fit_support_refusal_retains_full_build_but_never_calls_fitter(study, monkeypatch):
    root, path, pin = study
    frozen = s.registration(root, path, pin)
    monkeypatch.setattr(s, "MIN_JOINT_TRAIN", 1000)
    fresh = root / "logs/support-registration.json"
    s.prepare(root, s.Path(frozen["manifest"]["path"]), frozen["manifest"]["sha256"], fresh, True)
    new_pin = s.common.hash_file(fresh, 2 * 1024**2)
    build = root / "data/processed/support-build"
    built = s.collect(root, fresh, new_pin, build)
    monkeypatch.setattr(r, "fit", lambda *a: pytest.fail("fit after insufficient support"))
    cost = root / "data/processed/support-cost"
    with pytest.raises(ValueError, match="support gate"):
        s.evaluate(root, fresh, new_pin, build, built["completion_sha256"], cost)
    assert (cost / "failure.json").exists() and not (cost / "model.json").exists()
    assert (build / "verification.json").exists()


@pytest.mark.parametrize("kind", ["model", "predictions", "flags"])
def test_evaluation_repin_cannot_change_model_predictions_or_authority(study, kind):
    root, path, pin = study
    build = root / "data/processed/build"
    built = s.collect(root, path, pin, build)
    cost = root / "data/processed/cost"
    s.evaluate(root, path, pin, build, built["completion_sha256"], cost)
    completion = cost / "completion.json"
    report = json.loads(completion.read_bytes())
    if kind == "model":
        model_path = cost / "model.json"
        model = json.loads(model_path.read_bytes())
        model["model"]["bias"][1] += 0.1
        write_json(model_path, model)
        report["model_sha256"] = s.common.hash_file(model_path, 1024**2)
    elif kind == "predictions":
        pp = cost / f"{report['days'][0]['utc_date']}.predictions.f64"
        predictions = np.frombuffer(pp.read_bytes(), dtype="<f8").copy()
        predictions[1] += 0.1
        pp.write_bytes(predictions.tobytes())
        report["days"][0]["predictions_sha256"] = s.common.hash_file(pp, 14400 * 24)
    else:
        report["flags"]["trading_enabled"] = True
    write_json(completion, report)
    with pytest.raises(ValueError):
        s.verify_evaluation(
            root,
            path,
            pin,
            build,
            built["completion_sha256"],
            cost,
            s.common.hash_file(completion, 2 * 1024**2),
        )
