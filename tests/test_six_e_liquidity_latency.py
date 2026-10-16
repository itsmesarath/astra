"""Prediction timing is bounded and cannot imply execution or promotion readiness."""

import numpy as np
import pytest
from test_six_e_liquidity_status import run as run
from test_six_e_liquidity_status import terminal, write

from ai_trader.research import six_e_liquidity_latency as latency


class Fake:
    def __init__(self):
        self.calls = 0

    def predict(self, x):
        self.calls += 1
        assert x.shape == (1, 37) and x.dtype == np.float64 and not x.any()
        return np.zeros((1, 3))


def test_exact_synthetic_call_budget_and_false_authority():
    model = Fake()
    result = latency.measure(model)
    assert model.calls == 1010 and result["measured_calls"] == 1000
    assert result["end_to_end_latency_measured"] is False
    assert result["fixed_entry_exit_delay_changed"] is False
    assert result["trading_enabled"] is False and result["promotion_allowed"] is False
    m = result["prediction_milliseconds"]
    assert 0 <= m["minimum"] <= m["median"] <= m["p95"] <= m["p99"] <= m["maximum"]


def test_deadline_refuses_partial_measurement(monkeypatch):
    ticks = iter([0, 0, 31])
    monkeypatch.setattr(latency.time, "perf_counter", lambda: next(ticks))
    model = Fake()
    with pytest.raises(TimeoutError, match="no partial"):
        latency.measure(model)
    assert model.calls == 1


@pytest.mark.parametrize("shape,nonfinite", [((1, 2), False), ((1, 3), True)])
def test_bad_prediction_is_refused(shape, nonfinite):
    class Broken:
        def predict(self, x):
            return np.full(shape, np.nan if nonfinite else 0)

    with pytest.raises(ValueError, match="invalid predictions"):
        latency.measure(Broken())


def ready(run):
    run = list(run)
    run[4]["implementation_sha256"].update(latency.prediction_source_pins())
    run[2] = write(run[1], run[4])
    run[5]["registration_sha256"] = run[2]
    write(run[3] / "request.json", run[5])
    completed, receipt, _ = terminal(run, cpu=True)
    count = len(latency.rules.FEATURES)
    saved = {
        "model": latency.rules.Model(
            list(latency.rules.FEATURES),
            [0.0] * count,
            [1.0] * count,
            [[0.0] * 3 for _ in range(count)],
            [0.0] * 3,
        ).payload(),
        "flags": completed["flags"],
        "fit_accounting": {"synthetic_test": True},
    }
    completed["model_sha256"] = write(run[3] / "model.json", saved)
    completed["fit_accounting"] = saved["fit_accounting"]
    pin = write(run[3] / "completion.json", completed)
    receipt["completion_sha256"] = pin
    write(run[3] / "verification.json", receipt)
    return run, pin, saved


def test_complete_candidate_timing_does_not_read_inputs_or_fit(run, monkeypatch):
    run, pin, _ = ready(run)
    destination = run[0] / "data/processed/timing.json"
    original = latency.status._raw

    def metadata(root, path, *args):
        assert path.name in {
            run[1].name,
            "request.json",
            "progress.jsonl",
            "completion.json",
            "verification.json",
            "model.json",
        }
        return original(root, path, *args)

    def forbidden(*args, **kwargs):
        raise AssertionError("Timing must not fit or read feature/target inputs")

    monkeypatch.setattr(latency.status, "_raw", metadata)
    monkeypatch.setattr(latency.rules, "fit", forbidden)
    monkeypatch.setattr(latency.rules, "matrix", forbidden)
    result = latency.benchmark(*run[:4], pin, destination)
    assert result["measurement"]["measured_calls"] == 1000
    with pytest.raises(FileExistsError):
        latency.benchmark(*run[:4], pin, destination)


def test_model_pin_drift_blocks_timing_before_any_prediction(run, monkeypatch):
    run, pin, model = ready(run)
    model["model"]["bias"][0] = 0.5
    write(run[3] / "model.json", model)

    def forbidden(*args):
        raise AssertionError("Changed candidate cannot be timed")

    monkeypatch.setattr(latency, "measure", forbidden)
    destination = run[0] / "data/processed/timing.json"
    with pytest.raises(ValueError, match="candidate pin"):
        latency.benchmark(*run[:4], pin, destination)
    assert not destination.exists()


def test_incomplete_candidate_and_owned_directory_are_refused(run):
    destination = run[0] / "data/processed/timing.json"
    with pytest.raises(ValueError, match="complete pinned"):
        latency.benchmark(*run[:4], "0" * 64, destination)
    run, pin, _ = ready(run)
    with pytest.raises(ValueError, match="separate JSON"):
        latency.benchmark(*run[:4], pin, run[3] / "timing.json")


@pytest.mark.parametrize("during_measurement", [False, True])
def test_source_drift_never_publishes_timing(run, monkeypatch, during_measurement):
    run, pin, _ = ready(run)
    original = latency.prediction_source_pins()
    calls = 0

    def drift():
        nonlocal calls
        calls += 1
        return original if during_measurement and calls == 1 else {"six_e_liquidity.py": "f" * 64}

    monkeypatch.setattr(latency, "prediction_source_pins", drift)

    def forbidden(*args):
        raise AssertionError("Changed source cannot be timed")

    if not during_measurement:
        monkeypatch.setattr(latency, "measure", forbidden)
    destination = run[0] / "data/processed/timing.json"
    with pytest.raises(ValueError, match="source differs"):
        latency.benchmark(*run[:4], pin, destination)
    assert not destination.exists()
