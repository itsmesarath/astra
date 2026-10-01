"""Train-only thresholds, causal inputs, abstention and immutable CPU attempts."""

from copy import deepcopy
from datetime import date

import numpy as np
import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root

from ai_trader.research import historical_6e_selective as selective


@pytest.fixture
def rows():
    result = []
    for block in selective.v1.BLOCKS:
        for day in block.sessions:
            start = selective.v1.source._utc_ns(date.fromisoformat(day)) + 12 * 3600 * 10**9
            for i in range(600):
                now = start + i * 20 * 10**9
                entry_bid = 1_100_000_000
                exit_bid = entry_bid + (300_000 if i % 2 else 0)
                outcome = {
                    "status": "resolved",
                    "entry_ts_ns": now + 100_000_000,
                    "exit_ts_ns": now + 15_100_000_000,
                    "entry_bid_nano": entry_bid,
                    "entry_ask_nano": entry_bid + 50_000,
                    "exit_bid_nano": exit_bid,
                    "exit_ask_nano": exit_bid + 50_000,
                }
                target, label = selective.baseline.data.observed_targets(outcome)
                features = {k: 0.0 for k in selective.study.data.FEATURES}
                features["normalized_cvd_5s"] = 1.0 if i % 2 else -1.0
                result.append(
                    {
                        "source_session": day,
                        "contract": block.contract,
                        "block": block.name,
                        "partition": "development",
                        "decision_ts_ns": now,
                        "features": features,
                        "execution_features": {k: 0.0 for k in selective.study.flow.FEATURES},
                        "eligible": True,
                        "eligibility_reason": None,
                        "outcome": outcome,
                        "net_targets_long_short_ticks": target,
                        "hindsight_action": label,
                    }
                )
    return result


def test_later_targets_cannot_change_fitted_models_or_leaf_conditions(rows):
    first = selective.analyze(rows)
    changed = deepcopy(rows)
    for row in changed:
        if row["block"] == "april_2025":
            continue
        o = row["outcome"]
        o["exit_bid_nano"] = o["entry_bid_nano"] - 300_000
        o["exit_ask_nano"] = o["exit_bid_nano"] + 50_000
        row["net_targets_long_short_ticks"], row["hindsight_action"] = (
            selective.baseline.data.observed_targets(o)
        )
    second = selective.analyze(changed)
    for name in selective.MODELS:
        a, b = first["models"][name], second["models"][name]
        assert a["model_sha256"] == b["model_sha256"] and a["conditions"] == b["conditions"]
        assert a["later_exposed_diagnostics"]["mean_net_ticks"] > 0
        assert b["later_exposed_diagnostics"]["mean_net_ticks"] < 0
        assert all(
            set(c["training_sessions"]) == set(selective.v1.BLOCKS[0].sessions)
            for c in a["conditions"]
        )
    assert first["no_trade_control"]["selected"] == 0
    assert not first["promotion_enabled"]


def test_later_feature_distribution_cannot_fit_thresholds(rows):
    first = selective.analyze(rows)
    changed = deepcopy(rows)
    for r in changed:
        if r["block"] != "april_2025":
            r["features"]["normalized_cvd_5s"] *= 1000
    second = selective.analyze(changed)
    assert [x["model_sha256"] for x in first["models"].values()] == [
        x["model_sha256"] for x in second["models"].values()
    ]


@pytest.mark.parametrize("kind", ["duplicate", "reserved", "nonfinite", "future_feature"])
def test_invalid_or_leaky_rows_refused(rows, kind):
    if kind == "duplicate":
        rows.insert(1, deepcopy(rows[0]))
    elif kind == "reserved":
        rows[-1]["partition"] = "test_reserved"
    elif kind == "nonfinite":
        rows[0]["features"]["queue_imbalance"] = float("nan")
    else:
        rows[0]["features"]["future_profit"] = 1
    with pytest.raises(ValueError):
        selective.analyze(rows)


def test_unavailable_outcome_is_not_a_negative_training_label(rows):
    for r in rows:
        if r["block"] != "april_2025" and r["features"]["normalized_cvd_5s"] > 0:
            r["outcome"] = {
                "status": "no_entry_quote_timeout",
                "entry_expiry_ts_ns": r["decision_ts_ns"] + 1_100_000_001,
            }
            r["net_targets_long_short_ticks"] = r["hindsight_action"] = None
    result = selective.analyze(rows)
    for m in result["models"].values():
        p = m["later_exposed_diagnostics"]
        assert p["closed"] == 0 and p["statuses"]["no_entry_quote_timeout"] > 0
        assert m["training_resolved"] == 1800


def test_predictions_use_allowlisted_features_not_outcome_or_metadata(rows):
    x = selective.matrix(rows, selective.MODELS["microstructure_37"])
    for row in rows:
        row["outcome"] = {"future": "deliberately ignored"}
        row["model_score"] = 999999
    assert np.array_equal(x, selective.matrix(rows, selective.MODELS["microstructure_37"]))


def test_single_pinned_run_preserves_candidate_and_refuses_reuse(census_root, monkeypatch, rows):
    path = census_root / selective.ROWS
    path.write_bytes(b"".join(selective.common.canonical(r) + b"\n" for r in rows))
    monkeypatch.setattr(selective, "ROWS_PIN", selective.common.hash_file(path, 20 * 1024**2))
    reg = census_root / "selective.json"
    selective.prepare(census_root, reg)
    pin = selective.common.hash_file(reg, 1024**2)
    output = census_root / "candidate.json"
    result = selective.run(census_root, reg, pin, output)
    assert result["status"] == "completed"
    assert not result["promotion_enabled"] and not result["protocol"]["qwen_training"]
    assert reg.with_suffix(".attempt.json").exists()
    with pytest.raises(ValueError, match="reused"):
        selective.run(census_root, reg, pin, output)


def test_failed_fit_keeps_attempt_and_never_publishes(census_root, monkeypatch, rows):
    path = census_root / selective.ROWS
    path.write_bytes(b"".join(selective.common.canonical(r) + b"\n" for r in rows))
    monkeypatch.setattr(selective, "ROWS_PIN", selective.common.hash_file(path, 20 * 1024**2))
    reg = census_root / "selective.json"
    selective.prepare(census_root, reg)
    pin = selective.common.hash_file(reg, 1024**2)
    output = census_root / "candidate.json"

    def fail(*args):
        raise ValueError("synthetic fit error")

    monkeypatch.setattr(selective.tree, "fit", fail)
    with pytest.raises(ValueError, match="synthetic"):
        selective.run(census_root, reg, pin, output)
    assert reg.with_suffix(".failure.json").exists() and not output.exists()
