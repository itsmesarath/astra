"""Counterfactual cost labels, feature isolation, session boundaries and selective policy."""

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

import databento_dbn as dbn
import numpy as np
import pytest

from ai_trader.research import databento_6e_cost_targets as data
from ai_trader.training import train_6e_cost_baseline as trainer

clock = data.clock
DAY = date(2025, 7, 7)
BID = 1_000_000_000
ASK = BID + clock.TICK
CONFIG = Path(__file__).resolve().parents[1] / "configs/databento_6e_cost_baseline_v1.json"


def ns(hour, minute, second, millis=0):
    return (
        int(datetime(2025, 7, 7, hour, minute, second, tzinfo=UTC).timestamp()) * clock.SECOND_NS
        + millis * 1_000_000
    )


def event(action, side, price, size, order_id, timestamp, flags=0):
    return dbn.MBOMsg(
        publisher_id=1,
        instrument_id=42,
        ts_event=timestamp,
        order_id=order_id,
        price=price,
        size=size,
        action=dbn.Action.from_str(action),
        side=dbn.Side.from_str(side),
        ts_recv=timestamp,
        flags=flags,
    )


def update(builder, timestamp, *, bq=10, aq=10, ticks=0):
    builder.consume(event("M", "B", BID + ticks * clock.TICK, bq, 1, timestamp))
    builder.consume(event("M", "A", ASK + ticks * clock.TICK, aq, 2, timestamp, dbn.F_LAST))


def seeded():
    builder = data.CostTargetBuilder((DAY.isoformat(),), minimum_resolved=1)
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 59, 50)
    builder.consume(event("R", "N", 0, 0, 0, at, dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, 10, 1, at, dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, at, dbn.F_SNAPSHOT))
    for second in (50, 55, 59):
        update(builder, ns(11, 59, second))
    return builder


def outcome(ticks=0, *, timestamp=None):
    now = ns(12, 0, 0) if timestamp is None else timestamp
    return {
        "status": "resolved",
        "entry_target_ts_ns": now + 100_000_000,
        "entry_ts_ns": now + 100_000_000,
        "entry_bid_nano": BID,
        "entry_ask_nano": ASK,
        "exit_ts_ns": now + 15_100_000_000,
        "exit_bid_nano": BID + ticks * clock.TICK,
        "exit_ask_nano": ASK + ticks * clock.TICK,
        "inactivity_exposed": False,
    }


def row(timestamp=None, ticks=0, *, session="2025-07-07"):
    now = ns(12, 0, 0) if timestamp is None else timestamp
    result = outcome(ticks, timestamp=now)
    targets, label = data.observed_targets(result)
    return {
        "source_session": session,
        "decision_ts_ns": now,
        "features": {name: 0.0 for name in data.FEATURES},
        "eligible": True,
        "eligibility_reason": None,
        "outcome": result,
        "net_targets_long_short_ticks": targets,
        "hindsight_action": label,
    }


@pytest.mark.parametrize(
    "ticks,targets,label", [(3, [1, -5], 1), (-3, [-5, 1], -1), (0, [-2, -2], 0), (2, [0, -4], 0)]
)
def test_both_sides_cross_spread_and_cost_before_label(ticks, targets, label):
    assert data.observed_targets(outcome(ticks)) == (targets, label)


@pytest.mark.parametrize(
    "status",
    [
        "no_entry_quote_timeout",
        "no_entry_spread_widened",
        "unresolved_exit_window_end",
        "not_eligible",
    ],
)
def test_unknown_is_not_a_no_trade_training_label(status):
    assert data.observed_targets({"status": status}) == (None, None)


def test_flat_queue_zero_ofi_is_labeled_and_future_events_do_not_change_features():
    builder = seeded()
    update(builder, ns(12, 0, 0))
    first = builder.rows[0]
    features = deepcopy(first["features"])
    assert first["eligible"] and features["queue_imbalance"] == features["normalized_ofi_5s"] == 0
    update(builder, ns(12, 0, 0, 100))
    for second in (4, 8, 12):
        update(builder, ns(12, 0, second), bq=30)
    update(builder, ns(12, 0, 15, 100), ticks=3)
    builder.finish_day()
    rows, _ = builder.finish()
    assert rows[0]["features"] == features
    assert rows[0]["net_targets_long_short_ticks"] == [1, -5]
    assert rows[0]["hindsight_action"] == 1
    assert "signal_direction" not in rows[0] and "latency_variants" not in rows[0]


def test_all_eligible_decisions_have_targets_even_while_prior_candidate_is_pending():
    builder = seeded()
    for second in (0, 1, 2):
        update(builder, ns(12, 0, second))
    assert len(builder.rows) == len(builder.pending_rows) == 3
    assert all(r["eligible"] and r["latency_variants"] for r in builder.rows)
    assert builder.active_row is None  # labels are overlapping opportunities, not a portfolio


def test_completed_event_cvd_does_not_double_count_fill_or_leak_partial_trade():
    builder = seeded()
    builder.consume(event("T", "B", ASK, 5, 0, ns(12, 0, 0)))
    assert not builder.rows
    builder.consume(event("F", "A", ASK, 5, 2, ns(12, 0, 0, 100), dbn.F_LAST))
    features = builder.rows[0]["features"]
    assert features["normalized_cvd_5s"] == 0.5
    assert features["log_known_trades_5s"] == np.log1p(1)
    assert features["normalized_ofi_5s"] == 0


def test_no_entry_rejection_timestamp_retained_for_policy_clock():
    builder = seeded()
    update(builder, ns(12, 0, 0))
    builder.consume(event("M", "A", ASK + clock.TICK, 10, 2, ns(12, 0, 0, 100), dbn.F_LAST))
    target = builder.rows[0]["latency_variants"]["100"]
    assert target["status"] == "no_entry_spread_widened"
    assert target["entry_rejection_ts_ns"] == ns(12, 0, 0, 100)


def test_missing_coverage_not_silently_trained():
    builder = seeded()
    update(builder, ns(12, 0, 0))
    builder.finish_day()
    with pytest.raises(ValueError, match="Insufficient resolved"):
        builder.finish()


def test_training_feature_allowlist_and_metadata_independence():
    original = row()
    changed = deepcopy(original)
    changed["outcome"] = {"future": "different"}
    changed["hindsight_action"] = 1
    np.testing.assert_array_equal(
        trainer.feature_matrix([original]), trainer.feature_matrix([changed])
    )
    changed["features"]["future_profit"] = 100
    with pytest.raises(ValueError, match="allowlist"):
        trainer.feature_matrix([changed])
    changed = deepcopy(original)
    changed["features"][data.FEATURES[0]] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        trainer.feature_matrix([changed])


def test_ridge_train_only_scaler_is_frozen_and_deterministic():
    x = np.array([[0.0, 4.0], [1.0, 4.0], [2.0, 4.0], [3.0, 4.0]])
    y = np.array([[-2.0, -2.0], [-1.0, -3.0], [0.0, -4.0], [1.0, -5.0]])
    model = trainer.fit(x, y)
    assert model.means == [1.5, 4.0]
    assert model.scales[1] == 1
    before = deepcopy(asdict(model))
    assert np.isfinite(model.predict(np.array([[100000.0, -100000.0]]))).all()
    assert asdict(model) == before == asdict(trainer.fit(x, y))
    with pytest.raises(ValueError, match="two-sided"):
        trainer.fit(x, y[:2])


@pytest.mark.parametrize(
    "prediction,expected",
    [([0.5, -2], 0), ([0.51, -2], 1), ([-2, 0.51], -1), ([1, 1], 0), ([-2, -1], 0)],
)
def test_fixed_threshold_abstention_and_ties(prediction, expected):
    assert trainer.action(prediction) == expected


def test_policy_is_nonoverlapping_and_keeps_losing_positions():
    rows = [row(ns(12, 0, s), ticks=-3) for s in (0, 1, 15, 25, 26)]
    result = trainer.policy(rows, np.tile([1.0, -1.0], (len(rows), 1)))
    assert result["selected"] == 2 and result["closed"] == 2
    assert result["total_closed_net_ticks"] == -10
    assert [s["decision_ts_ns"] for s in result["selections"]] == [ns(12, 0, 0), ns(12, 0, 26)]


def test_future_no_entry_does_not_remove_the_selection_and_uses_expiry_clock():
    rows = [row(ns(12, 0, s)) for s in (0, 1, 11, 12)]
    rows[0].update(
        outcome={"status": "no_entry_quote_timeout", "entry_expiry_ts_ns": ns(12, 0, 1, 100) + 1},
        net_targets_long_short_ticks=None,
        hindsight_action=None,
    )
    result = trainer.policy(rows, np.tile([1.0, -1.0], (len(rows), 1)))
    assert result["selected"] == 2
    assert result["statuses"]["no_entry_quote_timeout"] == 1
    assert result["selections"][0]["net_ticks"] is None
    assert result["selections"][1]["decision_ts_ns"] == ns(12, 0, 12)


def test_unresolved_selected_position_not_dropped_and_blocks_more_entries():
    rows = [row(), row(ns(12, 1, 0))]
    rows[0].update(
        outcome={"status": "unresolved_exit_window_end", "inactivity_exposed": True},
        net_targets_long_short_ticks=None,
        hindsight_action=None,
    )
    result = trainer.policy(rows, np.tile([1.0, -1.0], (2, 1)))
    assert (
        result["selected"]
        == result["unresolved_entered"]
        == result["inactivity_exposed_entered"]
        == 1
    )
    assert result["closed"] == 0 and result["mean_net_ticks"] is None


def cohort():
    return [
        row(
            int(datetime.fromisoformat(s).replace(hour=12, tzinfo=UTC).timestamp())
            * clock.SECOND_NS,
            session=s,
        )
        for s in data.SESSIONS
    ]


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda rs: rs.reverse(), "sessions"),
        (lambda rs: rs.append(deepcopy(rs[-1])), "Duplicate"),
        (lambda rs: rs[0].update(source_session=data.TRAIN[1]), "sessions"),
        (lambda rs: rs[0].update(hindsight_action=1), "arithmetic"),
        (lambda rs: rs[0]["outcome"].update(entry_ts_ns=rs[0]["decision_ts_ns"]), "latency"),
        (
            lambda rs: rs[0]["outcome"].update(
                exit_ts_ns=rs[0]["decision_ts_ns"] + 4 * 3600 * clock.SECOND_NS
            ),
            "boundary",
        ),
        (lambda rs: rs[0]["outcome"].update(status="entry_pending"), "Unfinished"),
    ],
)
def test_row_validation_fails_closed(mutation, match):
    rows = cohort()
    trainer.validate_rows(rows)
    mutation(rows)
    with pytest.raises(ValueError, match=match):
        trainer.validate_rows(rows)


def test_validation_test_features_and_targets_do_not_change_fitted_model():
    original = cohort()
    first = trainer.train_once(original)
    changed = deepcopy(original)
    for r in changed:
        if r["source_session"] not in data.TRAIN:
            r["features"][data.FEATURES[0]] = 10000
            r["outcome"]["exit_bid_nano"] += 3 * clock.TICK
            r["outcome"]["exit_ask_nano"] += 3 * clock.TICK
            r["net_targets_long_short_ticks"], r["hindsight_action"] = data.observed_targets(
                r["outcome"]
            )
    second = trainer.train_once(changed)
    assert first["model"] == second["model"]
    assert first["model_sha256"] == second["model_sha256"]
    assert first["training"]["rows"] == len(data.TRAIN)
    assert first["test"]["policies"]["model"]["selected"] == 0
    assert first["promotion_enabled"] is False
    assert "insufficient_test_trades" in first["blockers"]


def test_config_pin_session_partition_and_frozen_model_constants(tmp_path):
    config, pin = data.load_config(CONFIG)
    assert pin == data.CONFIG_SHA256
    assert config["features"] == list(data.FEATURES)
    assert config["train_sessions"] == list(data.TRAIN)
    assert config["validation_sessions"] == list(data.VALIDATION)
    assert config["test_sessions"] == list(data.TEST)
    assert len(set(data.SESSIONS)) == len(data.SESSIONS)
    assert set(data.TRAIN).isdisjoint(data.VALIDATION) and set(data.TRAIN).isdisjoint(data.TEST)
    assert config["qwen_training"] is config["trading_enabled"] is False
    altered = tmp_path / "changed.json"
    altered.write_bytes(CONFIG.read_bytes() + b" ")
    with pytest.raises(ValueError, match="configuration changed"):
        data.load_config(altered)


def test_wrong_source_cohort_and_existing_outputs_fail_before_fit(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "selected_sources", lambda *_: ({}, [{"day": DAY}], "unused"))
    with pytest.raises(ValueError, match="Unexpected cost-target"):
        data.build_targets({}, tmp_path)
    existing = tmp_path / "keep.json"
    existing.write_text("keep")
    with pytest.raises(ValueError, match="overwrite"):
        trainer.run(
            project_root=tmp_path,
            config_path=CONFIG,
            rows_output=existing,
            report_output=tmp_path / "new.json",
        )
    assert existing.read_text() == "keep" and len(list(tmp_path.iterdir())) == 1
