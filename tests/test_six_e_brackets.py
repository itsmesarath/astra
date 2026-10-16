"""Native first-observation exits, costs, censoring and frozen whole-run verification."""

import json
from copy import deepcopy
from datetime import date

import numpy as np
import pytest
import test_six_e_crossings as fixture_source
from test_six_e_crossings import BASE, DAY, START, records_for, write_json
from test_six_e_crossings import census_root as census_root
from test_six_e_crossings import evidence as evidence
from test_six_e_crossings import manifest_evidence as manifest_evidence
from test_six_e_crossings import metadata_root as metadata_root
from test_six_e_crossings import protected_evidence as protected_evidence
from test_six_e_crossings import study as study

from ai_trader.research import six_e_bracket_study as s

t = s.target
original_pilot = fixture_source.pilot


def quotes(points):
    return np.asarray(
        [
            [START + int(sec * t.SECOND), BASE + bid * t.TICK, BASE + ask * t.TICK]
            for sec, bid, ask in points
        ],
        dtype=np.int64,
    )


def row(sec=0, **kwargs):
    return {
        "source_session": DAY,
        "contract": "6EM5",
        "partition": "development",
        "decision_ts_ns": START + int(sec * t.SECOND),
        "eligible": True,
        "eligibility_reason": None,
        **kwargs,
    }


def label(points):
    return t.targets([row()], quotes(points))[0]


@pytest.mark.parametrize("direction", [1, -1])
def test_target_is_a_trigger_not_a_fill_and_long_short_are_mirrored(direction):
    points = [
        (0, 0, 1),
        (0.1, 0, 1),
        (1, 5 * direction, 5 * direction + 1),
        (1.05, 10 * direction, 10 * direction + 1),
        (1.1, 6 * direction, 6 * direction + 1),
        (15.2, 0, 1),
    ]
    result = label(points)
    side = "long" if direction > 0 else "short"
    outcome = result["outcomes"]["bracket_exit"][side]
    assert outcome["trigger"] == "target" and outcome["trigger_net_ticks"] == 3
    assert outcome["exit_ts_ns"] == START + 1_100_000_000
    assert outcome["net_ticks"] == 4  # Arrival quote, not the trigger's +3 or pre-latency +8.
    assert outcome["hold_seconds"] == 1
    assert result["entry"]["ts_ns"] == START + 100_000_000
    assert result["outcomes"]["time_exit"][side]["net_ticks"] == -2


@pytest.mark.parametrize("direction", [1, -1])
def test_stop_overshoot_is_retained_not_clipped_to_stop(direction):
    result = label(
        [
            (0, 0, 1),
            (0.1, 0, 1),
            (1, -direction, 1 - direction),
            (1.1, -4 * direction, 1 - 4 * direction),
            (15.2, 0, 1),
        ]
    )
    outcome = result["outcomes"]["bracket_exit"]["long" if direction > 0 else "short"]
    assert outcome["trigger_net_ticks"] == -3 and outcome["trigger"] == "stop"
    assert outcome["net_ticks"] == -6 and outcome["gross_ticks"] == -5
    policy, selected = s.policy([result], np.array([direction]), "bracket_exit")
    assert selected == [(0, direction)] and policy["stop_overshoot_closed"] == 1
    assert policy["extra_cost_ticks"]["4"]["total_closed_net_ticks"] == -9


def test_widened_exit_is_kept_and_first_widened_entry_refuses_later_good_quote():
    result = label([(0, 0, 1), (0.1, 0, 1), (1, 5, 6), (1.1, 5, 8), (15.2, 0, 1)])
    outcome = result["outcomes"]["bracket_exit"]["long"]
    assert outcome["status"] == "resolved" and outcome["exit_spread_ticks"] == 3
    assert s.policy([result], np.array([1]), "bracket_exit")[0]["widened_exit_spreads"] == 1
    refused = label([(0, 0, 1), (0.1, 0, 2), (0.2, 0, 1), (15.3, 5, 6)])
    assert refused["entry"]["status"] == "no_entry_spread_widened"
    assert refused["entry"]["rejection_ts_ns"] == START + 100_000_000
    assert set(refused["hindsight_states"].values()) == {"unknown"}


def test_equal_time_native_order_and_no_fill_on_trigger_event():
    first = [(0, 0, 1), (0.1, 0, 1), (1, 5, 6), (1, -1, 0), (1.1, 0, 1), (15.2, 0, 1)]
    second = first[:2] + [first[3], first[2]] + first[4:]
    a = label(first)["outcomes"]["bracket_exit"]["long"]
    b = label(second)["outcomes"]["bracket_exit"]["long"]
    assert (a["trigger"], b["trigger"]) == ("target", "stop")
    assert a["net_ticks"] == b["net_ticks"] == -2
    assert a["exit_ts_ns"] > a["trigger_ts_ns"]


def test_timer_has_priority_over_price_at_exact_timeout():
    result = label([(0, 0, 1), (0.1, 0, 1), (15, 0, 1), (15.1, 5, 6), (15.2, 6, 7)])
    for plan in t.PLANS:
        outcome = result["outcomes"][plan]["long"]
        assert outcome["trigger"] == "timeout"
        assert outcome["trigger_ts_ns"] == START + 15_100_000_000
        assert outcome["exit_ts_ns"] == START + 15_200_000_000


@pytest.mark.parametrize("arrival,entered", [(1.1, True), (1.100000001, False)])
def test_entry_deadline_inclusive_and_one_nanosecond_later_is_unknown(arrival, entered):
    result = label([(0, 0, 1), (arrival, 0, 1), (16.3, 0, 1)])
    assert (result["entry"]["status"] == "entered") is entered
    if not entered:
        assert result["entry"]["status"] == "no_entry_quote_timeout"
        assert set(result["hindsight_states"].values()) == {"unknown"}


@pytest.mark.parametrize("arrival,resolved", [(2.1, True), (2.100000001, False)])
def test_exit_deadline_inclusive_and_no_late_recovery_fill(arrival, resolved):
    result = label([(0, 0, 1), (0.1, 0, 1), (1, -1, 0), (arrival, 0, 1), (15.2, 0, 1)])
    outcome = result["outcomes"]["bracket_exit"]["long"]
    assert (outcome["status"] == "resolved") is resolved
    if not resolved:
        assert outcome["status"] == "unresolved_exit_quote_timeout"
        assert outcome["net_ticks"] is None and outcome["exit_ts_ns"] is None
        assert result["hindsight_states"]["bracket_exit"] == "unknown"


def test_missing_exit_blocks_new_entries_and_is_not_zero_profit_or_no_trade():
    q = quotes([(0, 0, 1), (0.1, 0, 1), (1, -1, 0), (3, 0, 1), (3.1, 0, 1), (30, 0, 1)])
    rows = t.targets([row(), row(3)], q)
    report, selected = s.policy(rows, np.array([1, 1]), "bracket_exit")
    assert selected == [(0, 1)] and report["unresolved_entered"] == 1
    assert report["closed"] == 0 and report["mean_net_ticks"] is None
    assert report["skips"]["position_cooldown_or_unresolved"] == 1
    assert rows[0]["hindsight_states"]["bracket_exit"] == "unknown"


def test_both_directions_can_be_positive_at_different_exits_without_forced_winner():
    result = label([(0, 0, 1), (0.1, 0, 1), (1, -1, 0), (1.1, 5, 6), (1.2, -5, -4), (15.2, 0, 1)])
    sides = result["outcomes"]["bracket_exit"]
    assert sides["long"]["net_ticks"] == sides["short"]["net_ticks"] == 3
    assert sides["long"]["exit_ts_ns"] != sides["short"]["exit_ts_ns"]
    assert result["hindsight_states"]["bracket_exit"] == "both_positive"


@pytest.mark.parametrize("gap,exposed", [(5, False), (5.000000001, True)])
def test_inactivity_boundary_is_strict_and_diagnostics_are_retained(gap, exposed):
    result = label(
        [(0, 0, 1), (0.1, 0, 1), (0.1 + gap, 0, 1), (10.1, 0, 1), (15.1, 0, 1), (15.2, 0, 1)]
    )
    assert result["outcomes"]["time_exit"]["long"]["inactivity_exposed"] is exposed


def test_window_margin_eligibility_is_causal_and_original_outcomes_are_not_inputs():
    q = quotes([(0, 0, 1), (0.1, 0, 1), (15.2, 0, 1), (14382, 0, 1)])
    poisoned = row(
        outcome=object(), hindsight_action=object(), net_targets_long_short_ticks=object()
    )
    assert t.targets([poisoned], q) == t.targets([row()], q)
    end_row = row(14382)
    result = t.targets([end_row], q)[0]
    assert result["eligible"] is False
    assert result["eligibility_reason"] == "insufficient_window_for_exit_latency"
    assert set(result["hindsight_states"].values()) == {"unknown"}


def test_target_prefix_invariance_after_execution_deadlines():
    points = [(0, 0, 1), (0.1, 0, 1), (1, -1, 0), (1.1, 0, 1), (15.2, 0, 1)]
    assert label(points) == label(points + [(20, 100, 101)])


@pytest.mark.parametrize(
    "change", ["float", "order", "off_tick", "crossed", "shape", "end", "start"]
)
def test_native_quote_schema_and_session_bounds_refuse(change):
    q = quotes([(0, 0, 1), (0.1, 0, 1), (15.2, 0, 1)])
    if change == "float":
        q = q.astype(float)
    elif change == "order":
        q = q[::-1]
    elif change == "off_tick":
        q[1, 1] += 1
    elif change == "crossed":
        q[1, 2] = q[1, 1]
    elif change == "shape":
        q = q[:, :2]
    else:
        q[-1, 0] = START + 14400 * t.SECOND if change == "end" else START - 1
    with pytest.raises(ValueError):
        t.targets([row()], q)


def test_reserved_refusal_precedes_prices_and_raw_paths(monkeypatch):
    monkeypatch.setattr(s.zipfile, "ZipFile", lambda *a: pytest.fail("raw opened"))
    with pytest.raises(ValueError):
        s.replay({"utc_date": "2026-01-01"})
    with pytest.raises(ValueError):
        t.targets([row(source_session="2026-01-01")], object())
    with pytest.raises(ValueError):
        s.policy([row(source_session="2026-01-01", outcomes=object())], np.array([0]), "time_exit")


@pytest.mark.parametrize("change", ["contract", "session", "order", "eligible", "direction"])
def test_policy_identity_and_direction_guards(change):
    labels = t.targets(
        [row(), row(2)], quotes([(0, 0, 1), (0.1, 0, 1), (2, 0, 1), (2.1, 0, 1), (18, 0, 1)])
    )
    signs = np.array([1, 0])
    if change == "contract":
        labels[1]["contract"] = "6EU5"
    elif change == "session":
        labels[1]["source_session"] = "2025-04-08"
    elif change == "order":
        labels.reverse()
    elif change == "eligible":
        labels[1]["eligible"] = 1
    else:
        signs[0] = 2
    with pytest.raises(ValueError):
        s.policy(labels, signs, "bracket_exit")


def test_path_overflow_refuses_not_truncates(monkeypatch):
    monkeypatch.setattr(t, "MAX_PATH_QUOTES", 1)
    with pytest.raises(ValueError, match="path bound"):
        label([(0, 0, 1), (0.1, 0, 1), (1, 0, 1), (15.2, 0, 1)])


def test_idle_never_reads_outcomes_and_matched_diagnostics_keep_unavailable():
    result = label([(0, 0, 1), (0.1, 0, 1), (1, -1, 0), (3, 0, 1), (15.2, 0, 1)])
    poison = deepcopy(result)
    poison["outcomes"] = object()
    report, selected = s.policy([poison], np.array([0]), "time_exit")
    assert selected == [] and report["closed"] == 0
    matched = s.paired([result], [(0, 1)])
    assert matched["common_time_exit_selected"] == 1
    assert matched["both_resolved"] == 0 and matched["unmatched_or_unavailable"] == 1
    assert matched["mean_difference_ticks"] is None


def test_pool_preserves_later_only_statuses_and_weighted_means():
    items = [
        {
            "closed": 2,
            "total_closed_net_ticks": 6,
            "total_hold_seconds": 2,
            "mean_net_ticks": 3,
            "mean_hold_seconds": 1,
            "statuses": {"resolved": 2},
        },
        {
            "closed": 0,
            "total_closed_net_ticks": 0,
            "total_hold_seconds": 0,
            "mean_net_ticks": None,
            "mean_hold_seconds": None,
            "statuses": {"unresolved": 1},
        },
    ]
    merged = s._sum(items)
    assert merged["statuses"] == {"resolved": 2, "unresolved": 1}
    assert merged["mean_net_ticks"] == 3 and merged["mean_hold_seconds"] == 1


@pytest.mark.parametrize("index", [0, 2])
def test_semantically_valid_quote_change_cannot_break_original_snapshot_or_exit(index):
    q = quotes([(0, 0, 1), (0.1, 0, 1), (15.1, 0, 1), (15.2, 0, 1)])
    original = row(
        outcome={
            "status": "resolved",
            "exit_target_ts_ns": START + 15_100_000_000,
            "exit_ts_ns": START + 15_100_000_000,
            "exit_bid_nano": BASE,
            "exit_ask_nano": BASE + t.TICK,
        }
    )
    features = [{"auction_features": {"bid_nano": BASE, "ask_nano": BASE + t.TICK}}]
    s._quote_parity([original], features, q)
    q[index, 1:] += t.TICK  # Still ordered and tick-native, but not the original source price.
    with pytest.raises(ValueError, match="differs"):
        s._quote_parity([original], features, q)


@pytest.fixture
def pilot(original_pilot, monkeypatch):
    # The old no-trade fixture intentionally invents auction snapshots. Keep its
    # inactive signals, but bind prices to native quotes for this stronger proof.
    original_replay = s.previous.parent.replay

    def replay(member):
        rows, features, quality = original_replay(member)
        day = date.fromisoformat(member["utc_date"])
        builder = s.census.DailyBuilder(member["utc_date"], member["contract"])
        builder.start_day(day)
        for item in records_for(day, member["contract"]):
            builder.consume(item)
        builder.finish_day()
        assert builder.finish()[0] == rows
        packed = np.frombuffer(builder.quote_buffer, dtype=np.int64).reshape(-1, 3)
        for source, feature in zip(rows, features, strict=True):
            index = np.searchsorted(packed[:, 0], source["decision_ts_ns"], side="left")
            feature["auction_features"].update(
                bid_nano=int(packed[index, 1]), ask_nano=int(packed[index, 2])
            )
        return rows, features, quality

    monkeypatch.setattr(s.previous.parent, "replay", replay)
    return original_pilot


@pytest.fixture
def exit_study(study, monkeypatch):
    root, previous_path, previous_pin = study
    build_output, cost_output = (
        root / "data/processed/cross-features",
        root / "data/processed/cross-cost",
    )
    built = s.previous.build(root, previous_path, previous_pin, build_output)
    cost = s.previous.evaluate(
        root, previous_path, previous_pin, build_output, built["completion_sha256"], cost_output
    )
    path = root / "bracket-registration.json"
    s.prepare(
        root,
        path,
        previous_path,
        previous_pin,
        build_output,
        built["completion_sha256"],
        cost_output,
        cost["completion_sha256"],
    )
    pin = s.common.hash_file(path, 2 * 1024**2)
    frozen, original, build = s.registration(root, path, pin)

    def replay(member):
        day = member["utc_date"]
        index = s.previous.parent.DAYS.index(day)
        rows, features = s._features(root, frozen, original, build, index)
        builder = s.census.DailyBuilder(day, member["contract"])
        builder.start_day(date.fromisoformat(day))
        for item in records_for(date.fromisoformat(day), member["contract"]):
            builder.consume(item)
        builder.finish_day()
        assert builder.finish()[0] == rows
        packed = np.frombuffer(builder.quote_buffer, dtype=np.int64).reshape(-1, 3)
        return (
            rows,
            features,
            packed,
            {
                "full_member_hash_verified": True,
                "crossing_audit": {
                    "published_markers": 0,
                    "completed_markers": 0,
                    "unpublished_discarded_on_reset": 0,
                    "unpublished_tail_markers": 0,
                },
            },
        )

    monkeypatch.setattr(s, "replay", replay)
    return root, path, pin


def test_full_run_native_target_and_cost_verifier_no_rerun(exit_study):
    root, path, pin = exit_study
    output = root / "data/processed/exits"
    result = s.run(root, path, pin, output)
    assert result["sessions"] == len(s.previous.parent.DAYS) and not any(result["flags"].values())
    assert s.verify(root, path, pin, output, result["completion_sha256"]) == result
    with pytest.raises(FileExistsError):
        s.run(root, path, pin, output)


@pytest.mark.parametrize("kind", ["targets", "quotes", "pooled", "flags"])
def test_repinned_mutations_still_fail_recomputation_or_authority(exit_study, kind):
    root, path, pin = exit_study
    output = root / "data/processed/exits"
    s.run(root, path, pin, output)
    report = json.loads((output / "completion.json").read_bytes())
    if kind in ("targets", "quotes"):
        evidence = report["days"][0]
        day = evidence["utc_date"]
        if kind == "targets":
            file = output / f"{day}.targets.jsonl"
            rows = [json.loads(line) for line in file.read_bytes().splitlines()]
            rows[0]["hindsight_states"]["bracket_exit"] = "long_only"
            file.write_bytes(s.census.encode_rows(rows))
        else:
            file = output / f"{day}.quotes.i64"
            q = np.frombuffer(file.read_bytes(), dtype="<i8").copy().reshape(-1, 3)
            q[0, 1] += 1
            file.write_bytes(q.tobytes())
        evidence[kind + "_sha256"] = s.common.hash_file(file, s.census.MAX_DAY_BYTES)
    elif kind == "pooled":
        report["summaries"]["overall"]["rows"] += 1
    else:
        report["flags"]["promotion_allowed"] = True
    new_pin = write_json(output / "completion.json", report)
    with pytest.raises(ValueError):
        s.verify(root, path, pin, output, new_pin)


def test_protocol_drift_and_source_failure_do_not_publish_subset(exit_study, monkeypatch):
    root, path, pin = exit_study
    monkeypatch.setattr(s, "replay", lambda *a: (_ for _ in ()).throw(ValueError("source failed")))
    output = root / "data/processed/failed-exits"
    with pytest.raises(ValueError, match="source failed"):
        s.run(root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    monkeypatch.setattr(t, "TARGET", 4)
    with pytest.raises(ValueError, match="protocol"):
        s.registration(root, path, pin)
