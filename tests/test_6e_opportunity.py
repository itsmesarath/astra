"""Probabilistic cost labels, whole-session development separation and pinned intake."""

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from test_6e_cost_baseline import row

from ai_trader.training import train_6e_opportunity as trainer


def cohort():
    rows = []
    for session in trainer.SESSIONS:
        start = int(datetime.fromisoformat(session).replace(hour=12, tzinfo=UTC).timestamp())
        for index in range(102):
            ticks = (-3, 0, 3)[index % 3]
            r = row((start + index) * 1_000_000_000, ticks=ticks, session=session)
            r["features"] = {f: 0.0 for f in trainer.data.FEATURES}
            r["features"][trainer.data.FEATURES[0]] = float(ticks)
            rows.append(r)
    return rows


def write_rows(path, rows, monkeypatch):
    raw = b"".join(trainer.canonical(r) + b"\n" for r in rows)
    path.write_bytes(raw)
    monkeypatch.setattr(trainer, "ROWS_SHA256", trainer.hash_file(path, trainer.MAX_BYTES))


def test_protocol_uses_only_old_training_dates_and_no_independent_holdout():
    p = trainer.protocol()
    assert trainer.TRAIN == trainer.data.TRAIN[:7]
    assert trainer.DEVELOPMENT == trainer.data.TRAIN[7:]
    assert len(trainer.TRAIN) == 7 and len(trainer.DEVELOPMENT) == 3
    assert set(trainer.TRAIN).isdisjoint(trainer.DEVELOPMENT)
    assert set(trainer.SESSIONS).isdisjoint(p["excluded_sessions"])
    assert p["promotion_enabled"] is p["trading_enabled"] is p["qwen_training"] is False


def test_softmax_is_stable_normalized_deterministic_and_learns_synthetic_signal():
    x = np.tile([[-3.0, 2], [0.0, 2], [3.0, 2]], (40, 1))
    y = np.tile([-1, 0, 1], 40)
    model, prior = trainer.fit(x, y)
    before = asdict(model)
    p = model.predict(x)
    assert np.mean(p.argmax(axis=1) - 1 == y) == 1
    assert model.scales[1] == 1
    np.testing.assert_allclose(p.sum(axis=1), 1)
    np.testing.assert_allclose(prior, [1 / 3] * 3)
    assert (
        trainer.scores(y, p)["log_loss"]
        < trainer.scores(y, np.tile(prior, (len(y), 1)))["log_loss"]
    )
    assert asdict(trainer.fit(x, y)[0]) == before
    assert np.isfinite(model.predict([[1e10, -1e10]])).all()
    assert asdict(model) == before
    with pytest.raises(ValueError, match="dimension"):
        model.predict([[0]])
    np.testing.assert_allclose(trainer.softmax(np.array([[10000.0] * 3])), [[1 / 3] * 3])


@pytest.mark.parametrize(
    "labels",
    [[-1, 0], [-1, 0, 0], [-1, 0, 2], [True, False, True], [-1.0, 0.0, 1.0], [-1, None, 1]],
)
def test_fit_refuses_bad_or_missing_classes(labels):
    with pytest.raises(ValueError):
        trainer.fit([[-1], [0], [1]], labels)


def test_fit_refuses_nonfinite_features():
    with pytest.raises(ValueError, match="finite"):
        trainer.fit([[-1], [np.nan], [1]], [-1, 0, 1])


@pytest.mark.parametrize(
    "probabilities",
    [
        [[0, 0, 0]],
        [[-1, 1, 1]],
        [[0, 0, 2]],
        [[np.nan, 0, 1]],
        [[0, 1]],
    ],
)
def test_scores_refuse_invalid_probabilities(probabilities):
    with pytest.raises(ValueError, match="probabilities"):
        trainer.scores([0], np.array(probabilities))


def test_metrics_and_calibration_include_probability_one_and_empty_bins():
    score = trainer.scores([-1, 0, 1], np.eye(3))
    assert score["accuracy"] == 1 and score["brier_score"] == score["log_loss"] == 0
    bins = score["opportunity_calibration"]
    assert sum(b["rows"] for b in bins) == 3
    assert bins[0]["rows"] == 1 and bins[-1]["rows"] == 2
    assert bins[-1]["observed_positive_fraction"] == 1
    assert bins[1]["mean_predicted"] is None


def test_development_features_and_labels_cannot_change_training_parameters():
    rows = cohort()
    first = trainer.train_once(rows)
    for r in rows:
        if r["source_session"] in trainer.DEVELOPMENT:
            r["features"] = {f: 1e5 for f in trainer.data.FEATURES}
            r["outcome"]["exit_bid_nano"] += 8 * trainer.data.clock.TICK
            r["outcome"]["exit_ask_nano"] += 8 * trainer.data.clock.TICK
            r["net_targets_long_short_ticks"], r["hindsight_action"] = (
                trainer.data.base.observed_targets(r["outcome"])
            )
    second = trainer.train_once(rows)
    assert first["model"] == second["model"]
    assert first["model_sha256"] == second["model_sha256"]
    assert first["training"] == second["training"]
    assert first["development"]["model"] != second["development"]["model"]
    assert first["promotion_enabled"] is first["trading_enabled"] is first["qwen_trained"] is False
    assert first["consistent_development_probability_improvement"] is True
    assert first["decision"] == "development_only_not_ready_for_promotion"


def test_unknown_outcomes_not_replaced_with_neither_and_inactivity_accounted():
    rows = cohort()
    original = trainer.train_once(rows)
    rows[0]["outcome"] = {"status": "no_entry_quote_timeout"}
    rows[0]["hindsight_action"] = rows[0]["net_targets_long_short_ticks"] = None
    rows[1]["outcome"]["inactivity_exposed"] = True
    result = trainer.train_once(rows)
    assert result["training"]["resolved"] == original["training"]["resolved"] - 1
    assert (
        result["training"]["class_counts_short_neither_long"][1]
        == original["training"]["class_counts_short_neither_long"][1]
    )
    assert result["training"]["statuses"]["no_entry_quote_timeout"] == 1
    assert result["training"]["resolved_inactivity_exposed"] == 1


@pytest.mark.parametrize(
    "failure",
    [
        "leaked_feature",
        "wrong_target",
        "missing_session",
        "duplicate",
        "wrong_session_time",
        "excluded_session",
    ],
)
def test_invalid_cohort_fails_before_fit(monkeypatch, failure):
    rows = cohort()
    if failure == "leaked_feature":
        rows[0]["features"]["future_profit"] = 100
    elif failure == "wrong_target":
        rows[0]["net_targets_long_short_ticks"] = [100, -1]
    elif failure == "missing_session":
        rows = rows[102:]
    elif failure == "duplicate":
        rows.insert(0, deepcopy(rows[0]))
    elif failure == "wrong_session_time":
        rows[0]["decision_ts_ns"] -= 12 * 3600 * 1_000_000_000
    else:
        rows[-1]["source_session"] = trainer.data.TEST[0]
    monkeypatch.setattr(trainer, "fit", lambda *_: pytest.fail("Invalid cohort reached fit"))
    with pytest.raises(ValueError):
        trainer.train_once(rows)


def source_cohort():
    # Excluded rows intentionally lack features/outcomes. Only their session metadata is read.
    return cohort() + [
        {"source_session": s} for s in (*trainer.data.VALIDATION, *trainer.data.TEST)
    ]


def test_intake_excludes_old_holdout_outcomes(tmp_path, monkeypatch):
    path = tmp_path / "rows.jsonl"
    write_rows(path, source_cohort(), monkeypatch)
    rows, evidence = trainer.load_rows(path)
    assert rows == cohort()
    assert evidence["excluded_rows"] == 5
    assert evidence["selected_rows"] == 1020
    with path.open("ab") as target:
        target.write(b" ")
    with pytest.raises(ValueError):
        trainer.load_rows(path)


@pytest.mark.parametrize(
    "failure",
    [
        "hash",
        "duplicate_key",
        "truncated",
        "line_limit",
        "byte_limit",
        "row_limit",
        "missing_session",
        "reordered",
        "nan",
        "unknown_session",
    ],
)
def test_bounded_intake_refuses_bad_files(tmp_path, monkeypatch, failure):
    path = tmp_path / "rows.jsonl"
    rows = source_cohort()
    if failure == "missing_session":
        rows.pop()
    elif failure == "reordered":
        rows[-1], rows[-2] = rows[-2], rows[-1]
    elif failure == "unknown_session":
        rows[-1]["source_session"] = "2050-01-01"
    write_rows(path, rows, monkeypatch)
    if failure == "hash":
        monkeypatch.setattr(trainer, "ROWS_SHA256", "f" * 64)
    elif failure in {"duplicate_key", "truncated", "nan"}:
        path.write_bytes(
            {"duplicate_key": b'{"x":1,"x":2}\n', "truncated": b"{}", "nan": b'{"x":NaN}\n'}[
                failure
            ]
        )
    elif failure in {"line_limit", "byte_limit", "row_limit"}:
        monkeypatch.setattr(
            trainer,
            {"line_limit": "MAX_LINE", "byte_limit": "MAX_BYTES", "row_limit": "MAX_ROWS"}[failure],
            1,
        )
    with pytest.raises(ValueError):
        trainer.load_rows(path)


def setup_run(tmp_path, monkeypatch):
    rows_path, report_path = tmp_path / trainer.ROWS_PATH, tmp_path / trainer.REPORT_PATH
    rows_path.parent.mkdir(parents=True)
    write_rows(rows_path, source_cohort(), monkeypatch)
    report_path.write_bytes(b"{}\n")
    monkeypatch.setattr(trainer, "REPORT_SHA256", trainer.hash_file(report_path, 1024))
    registration, output = tmp_path / "registration.json", tmp_path / "result.json"
    trainer.prepare(registration)
    return dict(root=tmp_path, registration=registration, output=output)


def test_prepare_does_not_open_market_data_and_does_not_overwrite(tmp_path):
    path = tmp_path / "registration.json"
    result = trainer.prepare(path)
    assert result["protocol"] == trainer.protocol()
    assert result["implementation_sha256"] == trainer.fingerprints()
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        trainer.prepare(path)
    assert path.read_bytes() == before


def test_full_run_writes_plain_json_model_and_refuses_overwrite(tmp_path, monkeypatch):
    kwargs = setup_run(tmp_path, monkeypatch)
    result = trainer.run(**kwargs)
    saved = trainer.loads(kwargs["output"].read_bytes())
    assert saved == trainer.loads(trainer.canonical(result))
    assert result["model_sha256"] == trainer.digest(result["model"])
    assert result["excluded_rows"] == 5
    assert result["protocol"]["train_sessions"] == list(trainer.TRAIN)
    before = kwargs["output"].read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        trainer.run(**kwargs)
    assert kwargs["output"].read_bytes() == before


@pytest.mark.parametrize("failure", ["protocol", "code", "report", "rows"])
def test_changed_registered_inputs_fail_before_fit(tmp_path, monkeypatch, failure):
    kwargs = setup_run(tmp_path, monkeypatch)
    if failure in {"protocol", "code"}:
        frozen = trainer.loads(kwargs["registration"].read_bytes())
        if failure == "protocol":
            frozen["protocol"]["epochs"] += 1
        else:
            frozen["implementation_sha256"] = {}
        kwargs["registration"].write_bytes(trainer.canonical(frozen))
    else:
        target = tmp_path / (trainer.REPORT_PATH if failure == "report" else trainer.ROWS_PATH)
        with target.open("ab") as stream:
            stream.write(b" ")
    monkeypatch.setattr(trainer, "fit", lambda *_: pytest.fail("Invalid input reached fit"))
    with pytest.raises(ValueError):
        trainer.run(**kwargs)
    assert not kwargs["output"].exists()


def test_changed_evidence_during_training_is_not_published(tmp_path, monkeypatch):
    kwargs = setup_run(tmp_path, monkeypatch)
    original = trainer.train_once

    def changed(rows):
        result = original(rows)
        with (tmp_path / trainer.REPORT_PATH).open("ab") as target:
            target.write(b" ")
        return result

    monkeypatch.setattr(trainer, "train_once", changed)
    with pytest.raises(ValueError, match="changed during"):
        trainer.run(**kwargs)
    assert not kwargs["output"].exists()


def test_source_has_no_network_or_model_execution_hooks():
    source = Path(trainer.__file__).read_text()
    for forbidden in (
        "requests.",
        "httpx.",
        "torch.",
        "transformers.",
        "subprocess.",
        "place_order",
        "submit_order",
        "pickle",
    ):
        assert forbidden not in source
