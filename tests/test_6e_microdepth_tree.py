"""Completed-event features, bounded train-only trees and fresh session separation."""

from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import databento_dbn as dbn
import numpy as np
import pytest
from test_6e_cost_baseline import ASK, BID, DAY, event, ns, row, update

from ai_trader.research import databento_6e_microdepth as data
from ai_trader.training import train_6e_cost_baseline as baseline
from ai_trader.training import train_6e_microdepth_tree as trainer

clock = data.clock
CONFIG = Path(__file__).resolve().parents[1] / "configs/databento_6e_microdepth_tree_v1.json"


def seeded(kind=data.MicrodepthBuilder):
    builder = kind((DAY.isoformat(),), minimum_resolved=1)
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


def test_deep_book_reads_only_completed_event_and_top_five_levels():
    builder = seeded()
    for level in range(1, 7):
        builder.consume(event("A", "B", BID - level * clock.TICK, 20, 10 + level, ns(12, 0, 0)))
        builder.consume(event("A", "A", ASK + level * clock.TICK, 30, 20 + level, ns(12, 0, 0)))
    assert builder.rows == []
    update(builder, ns(12, 0, 0))
    f = builder.rows[0]["features"]
    assert set(f) == set(data.FEATURES)
    assert f["log_bid_depth5"] == pytest.approx(np.log1p(90))
    assert f["log_ask_depth5"] == pytest.approx(np.log1p(130))
    assert f["depth5_imbalance"] == -40 / 220
    assert f["bid_top_share5"] == 10 / 90
    assert f["ask_top_share5"] == 10 / 130
    assert f["bid_span5_ticks"] == f["ask_span5_ticks"] == 4


def test_reload_matches_only_prior_same_price_depletion_once():
    builder = seeded()
    update(builder, ns(12, 0, 0), bq=4, aq=7)
    update(builder, ns(12, 0, 1), bq=8, aq=10)
    update(builder, ns(12, 0, 2), bq=20, aq=20)
    f = builder.rows[-1]["features"]
    assert f["normalized_bid_reload_5s"] == 6 / 40
    assert f["normalized_ask_reload_5s"] == 3 / 40
    assert f["buy_absorption_proxy_5s"] == f["sell_absorption_proxy_5s"] == 0
    update(builder, ns(12, 0, 3), bq=30, aq=30, ticks=1)
    update(builder, ns(12, 0, 4), bq=40, aq=40, ticks=1)
    assert builder.rows[-1]["features"]["normalized_bid_reload_5s"] == 6 / 80


def test_price_change_discards_old_depletion_credit():
    builder = seeded()
    update(builder, ns(12, 0, 0), bq=1)
    update(builder, ns(12, 0, 1), bq=1, ticks=1)
    update(builder, ns(12, 0, 2), bq=10, ticks=1)
    assert builder.rows[-1]["features"]["normalized_bid_reload_5s"] == 0


def test_reload_inclusive_expiry_and_old_credit_not_reused():
    h = data.QuoteHistory()
    for second, qty in ((0, 10), (1, 5), (6, 8), (7, 10), (11, 10), (12, 10)):
        h.observe(clock.Quote(second * clock.SECOND_NS, BID, ASK, qty, 10))
        if second == 6:
            assert sum(r[1] for r in h.reloads) == 3  # depletion exactly five seconds old
        if second == 7:
            assert sum(r[1] for r in h.reloads) == 3  # remaining credit expired
        if second == 11:
            assert sum(r[1] for r in h.reloads) == 3
    assert sum(r[1] for r in h.reloads) == 0


def test_temporal_change_range_travel_and_absorption_use_only_completed_quotes():
    builder = seeded()
    update(builder, ns(12, 0, 0))
    builder.consume(event("T", "B", ASK, 40, 0, ns(12, 0, 1)))
    assert len(builder.rows) == 1
    update(builder, ns(12, 0, 1), ticks=1)
    update(builder, ns(12, 0, 2), ticks=0)
    f = builder.rows[-1]["features"]
    assert f["mid_change_5s_ticks"] == 0
    assert f["mid_range_5s_ticks"] == 1
    assert f["mid_travel_5s_ticks"] == 2
    assert f["buy_absorption_proxy_5s"] == 40 / 20
    assert f["sell_absorption_proxy_5s"] == 0
    assert builder.rows[-2]["features"]["buy_absorption_proxy_5s"] == 40 / (20 * 2)


def test_gap_resets_history_and_requires_new_warmup():
    builder = seeded()
    update(builder, ns(12, 0, 0), bq=1)
    update(builder, ns(12, 0, 6), bq=10, ticks=4)
    r = builder.rows[-1]
    assert r["eligibility_reason"] == "insufficient_feature_warmup"
    f = r["features"]
    assert f["mid_change_5s_ticks"] == f["mid_range_5s_ticks"] == 0
    assert f["normalized_bid_reload_5s"] == 0
    assert len(builder.history.quotes) == 1


def test_extended_features_do_not_change_original_targets_or_past_features():
    old, new = seeded(data.base.CostTargetBuilder), seeded()
    frozen = None
    for second, millis, ticks in (
        (0, 0, 0),
        (0, 100, 0),
        (4, 0, 0),
        (8, 0, 1),
        (12, 0, 1),
        (15, 100, 3),
    ):
        for builder in (old, new):
            update(builder, ns(12, 0, second, millis), ticks=ticks)
        if frozen is None:
            frozen = deepcopy(new.rows[0]["features"])
    assert new.rows[0]["features"] == frozen
    for builder in (old, new):
        builder.finish_day()
    old_rows, _ = old.finish()
    new_rows, _ = new.finish()
    for a, b in zip(old_rows, new_rows, strict=True):
        reduced = deepcopy(b)
        reduced["features"] = {k: b["features"][k] for k in data.base.FEATURES}
        assert reduced == a


def synthetic_training():
    x = np.tile(np.repeat([-1.0, 0.0, 1.0], 100), 6)[:, None]
    y = np.where(abs(x) > 0, [[1.0, -5.0]], [[-5.0, 1.0]])
    sessions = [f"day-{i}" for i in range(6) for _ in range(300)]
    return x, y, sessions


def test_tree_learns_nonlinear_pattern_with_supported_leaves_and_frozen_predictions():
    x, y, sessions = synthetic_training()
    model = trainer.fit(x, y, sessions)
    before = asdict(model)
    np.testing.assert_array_equal(model.predict([[-1], [0], [1]]), [[1, -5], [-5, 1], [1, -5]])
    assert len(model.nodes) == 5
    assert asdict(trainer.fit(x, y, sessions)) == before
    assert asdict(model) == before
    for node in model.nodes:
        assert node["rows"] >= trainer.MIN_LEAF
        assert sum(n >= trainer.MIN_SESSION_ROWS for n in node["session_counts"].values()) >= 3
        assert node["depth"] <= trainer.MAX_DEPTH
    with pytest.raises(ValueError, match="dimension"):
        model.predict([[0, 1]])


@pytest.mark.parametrize("failure", ["one_session", "short", "nonfinite", "misaligned"])
def test_tree_rejects_bad_training_inputs(failure):
    x, y, sessions = synthetic_training()
    if failure == "one_session":
        sessions = ["same"] * len(x)
    elif failure == "short":
        x, y, sessions = x[:499], y[:499], sessions[:499]
    elif failure == "nonfinite":
        y[0, 0] = np.nan
    else:
        sessions.pop()
    with pytest.raises(ValueError):
        trainer.fit(x, y, sessions)


def test_session_concentrated_split_is_refused_even_with_enough_rows():
    x = np.repeat([0.0, 1.0], 600)[:, None]
    y = np.where(x == 0, [[1.0, -5.0]], [[-5.0, 1.0]])
    sessions = [f"day-{i}" for i in range(4) for _ in range(300)]
    assert len(trainer.fit(x, y, sessions).nodes) == 1  # each child only has two sessions


def cohort():
    rows = []
    for session in data.SESSIONS:
        start = int(datetime.fromisoformat(session).replace(hour=12, tzinfo=UTC).timestamp())
        for offset in range(100):
            r = row((start + offset) * clock.SECOND_NS, session=session)
            r["features"] = {f: 0.0 for f in data.FEATURES}
            rows.append(r)
    return rows


def test_holdout_features_and_labels_cannot_change_model_thresholds_or_fit():
    rows = cohort()
    first = trainer.train_once(rows)
    for r in rows:
        if r["source_session"] not in data.TRAIN:
            r["features"] = {f: 10000.0 for f in data.FEATURES}
            r["outcome"]["exit_bid_nano"] += 8 * clock.TICK
            r["outcome"]["exit_ask_nano"] += 8 * clock.TICK
            r["net_targets_long_short_ticks"], r["hindsight_action"] = data.base.observed_targets(
                r["outcome"]
            )
    second = trainer.train_once(rows)
    assert first["model_sha256"] == second["model_sha256"]
    assert first["model"] == second["model"]
    assert first["test"]["policies"]["model"]["selected"] == 0
    assert first["promotion_enabled"] is False
    rows[0]["features"]["future_profit"] = 1
    with pytest.raises(ValueError, match="allowlist"):
        trainer.train_once(rows)


def test_config_matches_registered_implementation_and_has_fresh_holdouts(tmp_path):
    config, pin = data.load_config(CONFIG)
    assert pin == data.CONFIG_SHA256
    for name in ("train", "validation", "test"):
        assert config[f"{name}_sessions"] == list(getattr(data, name.upper()))
    assert config["source_sessions"] == list(data.SESSIONS)
    assert config["features"] == list(data.FEATURES)
    assert data.TRAIN == data.base.SESSIONS
    assert len(set(data.SESSIONS)) == len(data.SESSIONS) == 15
    assert set(data.base.SESSIONS).isdisjoint((*data.VALIDATION, *data.TEST))
    assert config["model"]["max_depth"] == trainer.MAX_DEPTH
    assert config["model"]["minimum_leaf_rows"] == trainer.MIN_LEAF
    assert config["model"]["minimum_leaf_sessions"] == trainer.MIN_SESSIONS
    assert config["model"]["minimum_rows_per_supported_session"] == trainer.MIN_SESSION_ROWS
    assert config["model"]["quantile_bins"] == trainer.BINS
    assert (
        config["trading_enabled"] is config["promotion_enabled"] is config["qwen_training"] is False
    )
    altered = tmp_path / "altered.json"
    altered.write_bytes(CONFIG.read_bytes() + b" ")
    with pytest.raises(ValueError, match="configuration changed"):
        data.load_config(altered)


def test_output_overwrite_and_input_mutation_fail_closed(tmp_path, monkeypatch):
    rows_path, report_path = tmp_path / "rows.jsonl", tmp_path / "report.json"
    kwargs = dict(
        project_root=tmp_path, config_path=CONFIG, rows_output=rows_path, report_output=report_path
    )
    rows_path.write_text("keep")
    with pytest.raises(ValueError, match="overwrite"):
        trainer.run(**kwargs)
    assert rows_path.read_text() == "keep"
    fresh = tmp_path / "fresh.jsonl"
    kwargs["rows_output"] = fresh
    monkeypatch.setattr(data, "build_targets", lambda *_: ([], {}))
    monkeypatch.setattr(trainer, "train_once", lambda *_: {})
    calls = iter(({"source": "first"}, {"source": "changed"}))
    monkeypatch.setattr(trainer, "fingerprints", lambda: next(calls))
    with pytest.raises(ValueError, match="Frozen inputs changed"):
        trainer.run(**kwargs)
    assert not report_path.exists() and not fresh.exists()


def test_missing_session_or_changed_target_fails_before_fit():
    rows = cohort()
    with pytest.raises(ValueError, match="sessions"):
        trainer.train_once(rows[:-100])
    rows[0]["net_targets_long_short_ticks"] = [100, -1]
    with pytest.raises(ValueError, match="arithmetic"):
        trainer.train_once(rows)


def test_registered_builder_cannot_silently_use_other_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(data.base, "selected_sources", lambda *_: ({}, [{"day": DAY}], "unused"))
    with pytest.raises(ValueError, match="Builder sessions differ"):
        data.base.build_targets({}, tmp_path, source_days=(DAY.isoformat(),))


def test_features_are_independent_of_outcome_and_metadata():
    r = cohort()[0]
    first = baseline.feature_matrix([r], data.FEATURES)
    r.update(outcome={"future": "different"}, hindsight_action=1, source_session="future")
    np.testing.assert_array_equal(first, baseline.feature_matrix([r], data.FEATURES))
