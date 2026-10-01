"""Paired-entry timing, full observed paths, frozen evidence and no false fills."""

from copy import deepcopy

import databento_dbn as dbn
import numpy as np
import pytest
from test_6e_cost_baseline import ASK, BID, event, ns, update
from test_6e_microdepth_tree import seeded

from ai_trader.research import historical_6e_paths as study

TICK = study.clock.TICK
SECOND = study.clock.SECOND_NS


def quotes(points):
    return np.asarray(
        [(round(s * SECOND), BID + b * TICK, BID + a * TICK) for s, b, a in points], dtype=np.int64
    )


def original(q, end=100 * SECOND):
    """Small independent 15s reference resolver for the unit-test tape."""
    entry = q[0]
    matches = [tuple(row) for row in q if row[0] >= entry[0] + 15 * SECOND]
    exit_quote = matches[0] if matches else None
    deadline = int(exit_quote[0]) if exit_quote else end - 1
    observed = [int(row[0]) for row in q if row[0] <= deadline]
    observed.append(deadline)
    gap = any(b - a > 5 * SECOND for a, b in zip(observed, observed[1:], strict=False))
    result = {
        "status": "resolved" if exit_quote else "unresolved_exit_window_end",
        "entry_target_ts_ns": int(entry[0]),
        "entry_ts_ns": int(entry[0]),
        "entry_bid_nano": int(entry[1]),
        "entry_ask_nano": int(entry[2]),
        "exit_target_ts_ns": int(entry[0]) + 15 * SECOND,
        "exit_ts_ns": int(exit_quote[0]) if exit_quote else None,
        "exit_bid_nano": int(exit_quote[1]) if exit_quote else None,
        "exit_ask_nano": int(exit_quote[2]) if exit_quote else None,
        "inactivity_exposed": gap,
    }
    if exit_quote:
        result.update(
            exit_lateness_ns=int(exit_quote[0] - entry[0] - 15 * SECOND),
            late_exit=exit_quote[0] > entry[0] + 16 * SECOND,
            gross_crossed_quote_ticks=float((exit_quote[1] - entry[2]) / TICK),
        )
    return result


def test_same_entry_horizons_exact_deadline_spread_and_costs():
    q = quotes(
        [
            (0, 0, 1),
            (1, 1, 2),
            (5, 3, 4),
            (10, 2, 3),
            (15, 5, 7),
            (20, 4, 5),
            (25, 3, 4),
            (30, -3, -2),
            (60, 8, 9),
        ]
    )
    h = study.analyze_entry(q, original(q), 100 * SECOND)
    assert tuple(h) == ("1", "5", "15", "30", "60")
    assert h["1"]["gross_long_short_ticks"] == [0, -2]
    assert h["15"]["gross_long_short_ticks"] == [4, -7]  # Retain widened exit spread.
    assert h["30"]["directions"]["long"]["max_liquidation_ticks"] == 4
    assert h["30"]["directions"]["long"]["min_liquidation_ticks"] == -4
    assert h["5"]["directions"]["long"]["barriers"]["2"]["kind"] == "target"
    assert h["60"]["inactivity_exposed"]
    row = {"path_horizons": h}
    summary = study.horizon_summary([row])
    assert summary["5"]["extra_cost_ticks"]["1"]["mean_long_short_net_ticks"] == [1, -5]
    assert (
        summary["5"]["extra_cost_ticks"]["2"]["hindsight_either_direction_positive_fraction"] == 0
    )


def test_late_recovery_not_backdated_into_extrema_or_crossings():
    q = quotes([(0, 0, 1), (2.01, 10, 11), (5, 10, 11), (15, 0, 1), (60, 0, 1)])
    h = study.analyze_entry(q, original(q), 100 * SECOND)
    one = h["1"]
    assert one["late_exit"] and one["exit_lateness_ns"] == 1_010_000_000
    assert one["gross_long_short_ticks"] == [9, -11]
    assert one["directions"]["long"]["max_liquidation_ticks"] == -1
    assert one["directions"]["long"]["barriers"]["2"]["kind"] == "none_observed"
    assert h["5"]["directions"]["long"]["barriers"]["2"]["ts_ns"] == 2_010_000_000


def test_equal_timestamps_preserve_first_event_and_do_not_cross_after_exit():
    q = quotes([(0, 0, 1), (1, -2, -1), (1, 10, 11), (15, 0, 1), (60, 0, 1)])
    h = study.analyze_entry(q, original(q), 100 * SECOND)
    assert h["1"]["gross_long_short_ticks"] == [-3, 1]
    assert h["1"]["path_quote_count"] == 2
    crossing = h["5"]["directions"]["long"]["barriers"]["2"]
    assert crossing == {"kind": "stop", "ts_ns": SECOND, "gross_ticks": -3.0}
    assert h["5"]["directions"]["long"]["max_liquidation_ticks"] == 9


def test_no_quote_at_exit_is_not_a_loss_label_or_a_zero_return():
    q = quotes([(0, 0, 1), (1, 0, 1), (5, 0, 1), (15, 2, 3), (20, 3, 4)])
    h = study.analyze_entry(q, original(q, 30 * SECOND), 30 * SECOND)
    assert h["15"]["status"] == "resolved"
    for seconds in (30, 60):
        item = h[str(seconds)]
        assert item["status"] == "unresolved_exit_window_end"
        assert item["gross_long_short_ticks"] is None
        assert item["path_window_truncated"]
        assert item["path_observation_deadline_ns"] == 30 * SECOND - 1
    assert study.paired([{"path_horizons": h}]) == []


def test_unresolved_inactivity_runs_until_window_end_not_scheduled_exit():
    q = quotes([(0, 0, 1), (5, 0, 1), (10, 0, 1), (14, 0, 1)])
    h = study.analyze_entry(q, original(q, 21 * SECOND), 21 * SECOND)
    assert h["15"]["inactivity_exposed"]
    assert not h["15"]["path_inactivity_exposed"]
    assert h["15"]["directions"]["long"]["barriers"]["2"]["kind"] == "none_observed"


def test_gap_boundary_is_strict_and_gap_can_hide_crossings():
    q = quotes(
        [
            (0, 0, 1),
            (5, 0, 1),
            (10, 0, 1),
            (15, 0, 1),
            (20.000000001, 0, 1),
            (25, 0, 1),
            (30, 0, 1),
            (60, 0, 1),
        ]
    )
    h = study.analyze_entry(q, original(q), 100 * SECOND)
    assert not h["15"]["path_inactivity_exposed"]
    assert h["30"]["path_inactivity_exposed"]
    assert h["30"]["path_max_quote_gap_ns"] == 5 * SECOND + 1


@pytest.mark.parametrize(
    "status", ["not_eligible", "no_entry_quote_timeout", "no_entry_spread_widened"]
)
def test_entry_failures_have_no_path_labels(status):
    assert study.analyze_entry(np.empty((0, 3), dtype=np.int64), {"status": status}, 100) == {}


@pytest.mark.parametrize(
    "change", ["reverse", "crossed", "off_tick", "at_boundary", "float", "empty"]
)
def test_invalid_quote_arrays_are_refused(change):
    q = quotes([(0, 0, 1), (1, 0, 1)])
    if change == "reverse":
        q = q[::-1]
    elif change == "crossed":
        q[0, 2] = q[0, 1]
    elif change == "off_tick":
        q[0, 1] += 1
    elif change == "at_boundary":
        q[1, 0] = 100 * SECOND
    elif change == "float":
        q = q.astype(float)
    else:
        q = q[:0]
    with pytest.raises(ValueError):
        study.validate_quotes(q, 100 * SECOND)


def test_refuse_entry_or_15s_regression_and_bound(monkeypatch):
    q = quotes([(0, 0, 1), (15, 0, 1), (60, 0, 1)])
    for key in ("entry_bid_nano", "exit_bid_nano", "exit_lateness_ns"):
        o = original(q)
        o[key] += 1
        with pytest.raises(ValueError):
            study.analyze_entry(q, o, 100 * SECOND)
    monkeypatch.setattr(study, "MAX_QUOTES", 2)
    with pytest.raises(ValueError):
        study.validate_quotes(q, 100 * SECOND)


def test_builder_only_observes_complete_events_and_preserves_original():
    old, new = seeded(), seeded(study.PathBuilder)
    for second, millis, ticks in (
        (0, 0, 0),
        (0, 100, 0),
        (1, 100, 2),
        (5, 100, 1),
        (10, 100, 2),
        (15, 100, 3),
        (30, 100, 4),
        (60, 100, -2),
    ):
        for builder in (old, new):
            update(
                builder,
                ns(12, 0, second, millis) if second < 60 else ns(12, 1, 0, millis),
                ticks=ticks,
            )
    before = len(new.quote_buffer)
    new.consume(event("M", "B", BID, 20, 1, ns(12, 1, 1)))
    assert len(new.quote_buffer) == before
    new.consume(event("M", "A", ASK, 20, 2, ns(12, 1, 1), dbn.F_LAST))
    update(old, ns(12, 1, 1), bq=20, aq=20)
    for builder in (old, new):
        builder.finish_day()
    old_rows, _ = old.finish()
    new_rows, _ = new.finish()
    study.verify_original(new_rows, old_rows)
    assert new_rows[0]["path_horizons"]["60"]["gross_long_short_ticks"] == [-3, 1]
    changed = deepcopy(new_rows)
    changed[0]["features"]["queue_imbalance"] += 1
    with pytest.raises(ValueError, match="Original 15s"):
        study.verify_original(changed, old_rows)


def test_paired_clean_subset_is_separate_and_failures_are_counted():
    q = quotes([(0, 0, 1), *[(i, 0, 1) for i in range(1, 61)]])
    h = study.analyze_entry(q, original(q), 100 * SECOND)
    row = {
        "path_horizons": h,
        "source_session": "2025-07-07",
        "eligible": True,
        "decision_ts_ns": ns(12, 0, 0),
        "outcome": {"status": "resolved"},
    }
    failed = {
        **row,
        "decision_ts_ns": ns(12, 1, 1),
        "path_horizons": {},
        "outcome": {"status": "no_entry_quote_timeout"},
    }
    report = study.summarize([row, failed])
    assert report["decisions"] == report["eligible"] == 2
    assert report["paired_no_gap_no_late_count"] == report["paired_all_resolved_count"] == 1
    assert report["causally_thinned_decisions"] == 2  # No successful-outcome thinning.
    assert report["original_outcome_counts"]["no_entry_quote_timeout"] == 1
    row["path_horizons"]["1"]["late_exit"] = True
    assert len(study.paired([row])) == 1 and not study.paired([row], clean=True)


def test_registration_pins_protocol_source_and_refuses_overwrites(tmp_path, monkeypatch):
    registration = tmp_path / "registration.json"
    study.prepare(registration)
    frozen, _ = study.verify_registration(registration)
    assert not frozen["protocol"]["training_enabled"]
    with pytest.raises(FileExistsError):
        study.prepare(registration)
    monkeypatch.setattr(study, "HORIZONS", (15,))
    with pytest.raises(ValueError, match="Frozen"):
        study.verify_registration(registration)


def test_existing_output_refused_before_dataset_read(tmp_path):
    existing = tmp_path / "keep.json"
    existing.write_bytes(b"retained")
    with pytest.raises(ValueError, match="overwrite"):
        study.run(
            root=tmp_path,
            registration=tmp_path / "absent",
            rows_output=existing,
            summary_output=tmp_path / "new",
        )
    assert existing.read_bytes() == b"retained"


def test_empty_summary_does_not_invent_zero_performance():
    result = study.horizon_summary([])
    assert result["15"]["resolved"] == 0
    assert result["15"]["extra_cost_ticks"]["1"]["mean_long_short_net_ticks"] is None


def test_randomized_observed_extrema_and_crossings_match_event_order_oracle():
    rng = np.random.default_rng(83041)
    for _ in range(20):
        timestamps = np.sort(rng.integers(0, 70 * SECOND, size=80))
        timestamps[0] = 0
        bids = np.cumsum(rng.integers(-3, 4, size=80))
        bids[0] = 0
        q = np.column_stack((timestamps, BID + bids * TICK, BID + (bids + 1) * TICK)).astype(
            np.int64
        )
        study.validate_quotes(q, 100 * SECOND)
        results = study.analyze_entry(q, original(q), 100 * SECOND)
        for horizon in study.HORIZONS:
            deadline = horizon * SECOND
            selected = []
            exit_quote = None
            for timestamp, bid, ask in q:
                if timestamp <= deadline:
                    selected.append((timestamp, bid, ask))
                if timestamp >= deadline:
                    exit_quote = (timestamp, bid, ask)
                    break
            got = results[str(horizon)]
            assert got["exit_ts_ns"] == int(exit_quote[0])
            for side, index in (("long", 1), ("short", 2)):
                values = [
                    (r[index] - ASK) / TICK if side == "long" else (BID - r[index]) / TICK
                    for r in selected
                ]
                direction = got["directions"][side]
                assert direction["max_liquidation_ticks"] == max(values)
                assert direction["min_liquidation_ticks"] == min(values)
                for threshold in study.BARRIERS:
                    hit = next(
                        (
                            (r[0], v)
                            for r, v in zip(selected, values, strict=True)
                            if v >= threshold or v <= -threshold
                        ),
                        None,
                    )
                    crossing = direction["barriers"][str(threshold)]
                    assert crossing["ts_ns"] == (int(hit[0]) if hit else None)
                    assert crossing["gross_ticks"] == (float(hit[1]) if hit else None)


def test_changed_implementation_registration_refused(tmp_path, monkeypatch):
    path = tmp_path / "registration.json"
    study.prepare(path)
    monkeypatch.setattr(study, "fingerprints", lambda: {"changed": "implementation"})
    with pytest.raises(ValueError, match="Frozen"):
        study.verify_registration(path)


def test_builder_enforces_quote_bound_before_collecting(monkeypatch):
    builder = seeded(study.PathBuilder)
    monkeypatch.setattr(study, "MAX_QUOTES", 1)
    update(builder, ns(12, 0, 0))
    with pytest.raises(ValueError, match="bound"):
        update(builder, ns(12, 0, 1))
