"""Native crossing retention, publication causality and two-stage offline evidence."""

import json
import math
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest
from test_causal_6e_context import DAY, START
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for, write_json
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence
from test_six_e_auction import BASE, bundle, record, row
from test_six_e_auction import pilot as pilot

from ai_trader.research import six_e_crossing_study as s

e, r, tape = s.events, s.rules, s.events.tape


def quote(second, bid_step=0, ask_step=None):
    return SimpleNamespace(
        ts_recv_ns=START + int(second * tape.SECOND),
        bid=BASE + bid_step * tape.TICK,
        ask=BASE + (ask_step if ask_step is not None else bid_step + 1) * tape.TICK,
        bid_qty=5,
        ask_qty=5,
    )


def buffer():
    producer, state = tape.AuctionFeatures(DAY, "6EM5"), e.CrossingBuffer(DAY, "6EM5")
    state.reset()
    return producer, state


def observe(producer, state, q, records=None):
    producer.observe(q, records or [])
    state.observe(producer, q)


@pytest.mark.parametrize("direction", [1, -1])
def test_two_half_tick_updates_survive_range_update_and_publication(direction):
    producer, state = buffer()
    for second, shift in ((0, 0), (10, 0), (30, 4), (60, 4 if direction > 0 else 0)):
        observe(producer, state, quote(second, shift))
    trades = [record(60, side="B" if direction > 0 else "A", size=1) for _ in range(20)]
    half = quote(60.25, 4, 6) if direction > 0 else quote(60.25, -1, 1)
    full = quote(60.5, 5) if direction > 0 else quote(60.5, -1)
    observe(producer, state, half, trades)
    assert not state.markers and direction in state.pending
    frozen = state.pending[direction].level
    observe(producer, state, full)
    assert len(state.markers) == 1 and state.markers[0]["level_nano2"] == frozen
    current = producer.features(full.ts_recv_ns)
    current_level = current["prior_high_nano2"] if direction > 0 else current["prior_low_nano2"]
    assert direction * (full.bid + full.ask - current_level) / (2 * tape.TICK) == 0.5
    later = quote(61, 5 if direction > 0 else -1)
    observe(producer, state, later)
    packet = state.publish(later.ts_recv_ns)
    e.validate_packet(packet, later.ts_recv_ns, DAY)
    assert packet["markers"][0]["ts_ns"] == full.ts_recv_ns < later.ts_recv_ns
    assert r.qualified(packet["markers"][0], bundle(), True)
    observe(producer, state, quote(62, 5 if direction > 0 else -1))
    assert state.publish(START + 62 * tape.SECOND)["markers"] == []
    assert state.report()["published_markers"] == 1


def test_equal_time_native_event_order_and_partial_attack_expiry():
    producer, state = buffer()
    for second, shift in ((0, 0), (10, 0), (30, 4), (60, 4)):
        observe(producer, state, quote(second, shift))
    observe(producer, state, quote(60.25, 4, 6))
    observe(producer, state, quote(60.25, 5))
    marker = state.markers[0]
    assert marker["start_ts_ns"] == marker["ts_ns"]
    assert marker["start_ordinal"] < marker["ordinal"]
    state.reset()
    assert state.report()["unpublished_discarded_on_reset"] == 1
    assert not state.markers and not state.pending
    assert state.marker_id == 1 and state.segment == 2
    producer, state = buffer()
    for second, shift in ((0, 0), (10, 0), (30, 4), (60, 4)):
        observe(producer, state, quote(second, shift))
    observe(producer, state, quote(60.25, 4, 6))
    observe(producer, state, quote(66, 5))
    assert not state.markers and not state.pending
    assert state.audit["partial_attack_invalidated_or_expired"] == 1


def test_return_inside_cancels_partial_attack_and_bounds_do_not_truncate(monkeypatch):
    producer, state = buffer()
    for second, shift in ((0, 0), (10, 0), (30, 4), (60, 4)):
        observe(producer, state, quote(second, shift))
    observe(producer, state, quote(60.25, 4, 6))
    observe(producer, state, quote(60.5, 4))
    assert not state.pending
    monkeypatch.setattr(e, "MAX_MARKERS", 0)
    observe(producer, state, quote(60.75, 5))
    with pytest.raises(ValueError, match="no truncation"):
        observe(producer, state, quote(61, 5, 7))


def marker(direction=1):
    low, high = 2 * BASE + tape.TICK, 2 * BASE + 9 * tape.TICK
    level = high if direction > 0 else low
    mid = level + direction * 2 * tape.TICK
    return {
        "id": 1,
        "segment": 1,
        "direction": direction,
        "start_ts_ns": START + 59_250_000_000,
        "start_ordinal": 998,
        "ts_ns": START + 59_500_000_000,
        "ordinal": 999,
        "prior_low_nano2": low,
        "prior_high_nano2": high,
        "level_nano2": level,
        "start_mid_nano2": level + direction * tape.TICK,
        "bid_nano": (mid - tape.TICK) // 2,
        "ask_nano": (mid + tape.TICK) // 2,
        "activity": math.log1p(20),
        "known_trades": 20,
        "unknown_trades": 0,
        "delta_qty": 20 * direction,
        "top_depth_qty": 10,
        "normalized_cvd": 4.0 * direction,
        **{f"unknown_fraction_qty_{w}s": 0.0 for w in tape.WINDOWS},
    }


def packet_row(second, dist=1, direction=1, attack=1, *, previous=None, markers=None, segment=1):
    result = row(second, dist, direction, attack)
    prior_ordinal = previous["crossing_evidence"]["ordinal"] if previous else 0
    ordinal = prior_ordinal + 10 if previous else 1000
    result["crossing_evidence"] = {
        "segment": segment,
        "ordinal": ordinal,
        "previous_publication_ordinal": prior_ordinal,
        "previous_publication_ts_ns": previous["decision_ts_ns"] if previous else 0,
        "markers": markers or [],
    }
    return result


@pytest.mark.parametrize("direction", [1, -1])
def test_event_failed_auction_arms_from_delivered_level_not_current_extrema(direction):
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    first = packet_row(60, 1, direction, direction, markers=[marker(direction)])
    # The pre-publication rolling range already absorbed the price: V1 cannot arm here.
    g = first["auction_features"]
    if direction > 0:
        g["prior_high_nano2"] += 2 * tape.TICK
    else:
        g["prior_low_nano2"] -= 2 * tape.TICK
    g["prior_range_ticks"] = 5.0
    assert state.observe(first)["failed_auction"] == 0
    assert state.pending["failed_auction"].level == marker(direction)["level_nano2"]
    previous = first
    for second, dist, expected in ((61, -1, 0), (62, 0, 0), (63, -1, -direction)):
        current = packet_row(second, dist, -direction, direction, previous=previous)
        assert state.observe(current)["failed_auction"] == expected
        previous = current


@pytest.mark.parametrize("direction", [1, -1])
def test_accepted_breakout_preserves_sequence_and_never_confirms_at_publication(direction):
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    first = packet_row(60, 2, direction, direction, markers=[marker(direction)])
    assert state.observe(first)["accepted_breakout"] == 0
    previous = first
    for second, dist, flow, expected in (
        (61, 2, direction, 0),
        (62, 2, direction, 0),
        (63, 1, -direction, 0),
        (64, 2, direction, direction),
    ):
        current = packet_row(second, dist, flow, direction, previous=previous)
        if second == 63:
            current["features"]["normalized_cvd_5s"] = -0.5 * direction
        assert state.observe(current)["accepted_breakout"] == expected
        previous = current


def test_price_ablation_removes_only_initiation_burst_and_unknown_is_never_guessed():
    m = marker()
    m.update(known_trades=1, activity=math.log1p(1), delta_qty=1, normalized_cvd=0.2)
    initial = packet_row(60, markers=[m])
    for burst, expected in ((True, False), (False, True)):
        state = r.State(DAY, "6EM5", bundle(), burst=burst)
        state.observe(initial)
        assert bool(state.pending) == expected
    m["unknown_fraction_qty_30s"] = 0.11
    assert not r.qualified(m, bundle(), False)


def test_first_native_qualifying_marker_is_used_without_retroactive_or_stale_entry():
    first, second = marker(), marker(-1)
    second.update(id=2, ordinal=1000, ts_ns=START + 59_600_000_000)
    initial = packet_row(60, markers=[first, second])
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    result = state.observe(initial)
    assert result["crossing_follow"] == 1
    assert result["failed_auction"] == result["accepted_breakout"] == 0
    assert state.pending["failed_auction"].direction == 1
    stale = marker()
    stale.update(start_ts_ns=START + 54_250_000_000, ts_ns=START + 54_500_000_000)
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    assert not any(state.observe(packet_row(60, markers=[stale])).values())
    assert not state.pending and state.audit["stale_markers"] == 1


def test_quality_and_segment_changes_clear_old_level_and_reused_delivery_is_refused():
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    initial = packet_row(60, markers=[marker()])
    state.observe(initial)
    next_row = packet_row(61, previous=initial, segment=2)
    state.observe(next_row)
    assert not state.pending and state.audit["segment_reset"] == 1
    repeated = deepcopy(marker())
    repeated.update(
        segment=2,
        ts_ns=next_row["decision_ts_ns"],
        start_ts_ns=next_row["decision_ts_ns"],
        start_ordinal=1011,
        ordinal=1012,
    )
    with pytest.raises(ValueError, match="twice"):
        state.observe(packet_row(62, previous=next_row, segment=2, markers=[repeated]))
    state = r.State(DAY, "6EM5", bundle(), burst=True)
    state.observe(initial)
    bad = packet_row(61, previous=initial)
    bad["features"]["unknown_trade_fraction_5s"] = 0.11
    state.observe(bad)
    assert not state.pending


@pytest.mark.parametrize(
    "change",
    [
        "future",
        "too_old_start",
        "off_tick",
        "extra",
        "negative",
        "count",
        "cvd",
        "direction",
        "wrong_level",
        "segment",
        "order",
    ],
)
def test_marker_strict_causal_metadata_guards(change):
    m = marker()
    if change == "future":
        m["ts_ns"] = START + 61 * tape.SECOND
    elif change == "too_old_start":
        m["start_ts_ns"] -= 5 * tape.SECOND
    elif change == "off_tick":
        m["bid_nano"] += 1
    elif change == "extra":
        m["future_exit"] = 100
    elif change == "negative":
        m["unknown_fraction_qty_15s"] = -1.0
    elif change == "count":
        m["known_trades"] += 1
    elif change == "cvd":
        m["normalized_cvd"] = 5.0
    elif change == "direction":
        m["direction"] = 0
    elif change == "wrong_level":
        m["level_nano2"] += tape.TICK
    elif change == "segment":
        m["segment"] = 2
    else:
        m["ordinal"] = 0
    with pytest.raises(ValueError):
        r.support([packet_row(60, markers=[m])], bundle())


def test_prefix_invariance_and_no_labels_eligibility_or_outcome_access():
    rows = [packet_row(60, markers=[marker()])]
    for second, dist in ((61, -1), (62, 0), (63, -1), (64, 1)):
        rows.append(packet_row(second, dist, -1, previous=rows[-1]))
    expected, _ = r.directions(rows, bundle())
    poisoned = deepcopy(rows)
    for item in poisoned:
        item.update(
            eligible=object(),
            outcome=object(),
            hindsight_action=object(),
            net_targets_long_short_ticks=object(),
            path_horizons=object(),
        )
    actual, _ = r.directions(poisoned, bundle())
    prefix, _ = r.directions(poisoned[:3], bundle())
    for name in r.POLICIES:
        np.testing.assert_array_equal(actual[name], expected[name])
        np.testing.assert_array_equal(prefix[name], expected[name][:3])


def test_native_builder_exact_original_rows_and_all_auction_fields_match():
    original = s.parent.AuctionBuilder(DAY, "6EM5")
    new = s.CrossingBuilder(DAY, "6EM5")
    for builder in (original, new):
        builder.start_day(date.fromisoformat(DAY))
        for item in records_for(date.fromisoformat(DAY), "6EM5"):
            builder.consume(item)
        builder.finish_day()
    assert new.finish() == original.finish()
    assert new.auction_rows == original.auction_rows
    assert len(new.crossing_rows) == len(new.finish()[0])
    for ts, packet in new.crossing_rows.items():
        e.validate_packet(packet, ts, DAY)
    assert new.crossings.report()["published_markers"] == 0


@pytest.fixture
def study(pilot, monkeypatch):
    root, parent_path, parent_pin = pilot
    original_output = root / "data/processed/original-auction"
    s.parent.run(root, parent_path, parent_pin, original_output)
    completion_pin = s.common.hash_file(original_output / "completion.json", 2 * 1024**2)
    # Tiny fixture has no trades; production gate remains 20 / 4 / 1.
    monkeypatch.setattr(s, "SUPPORT_GATE", {k: 0 for k in s.SUPPORT_GATE})
    path = root / "crossing-registration.json"
    s.prepare(root, parent_path, parent_pin, original_output, completion_pin, path)
    pin = s.common.hash_file(path, 2 * 1024**2)
    frozen, _ = s.registration(root, path, pin)

    def replay(member):
        day = member["utc_date"]
        index = s.parent.DAYS.index(day)
        entry = frozen["sources"][index]["entry"]
        rows = s.data.read_rows(root, entry, "rows")
        baseline = s.parent._feature_rows(
            original_output / f"{day}.features.jsonl",
            frozen["parent_days"][index]["features_sha256"],
            len(rows),
        )
        features, previous, ordinal = [], 0, 0
        for base in baseline:
            features.append(
                {
                    **base,
                    "crossing_evidence": {
                        "segment": 1,
                        "ordinal": ordinal + 1,
                        "previous_publication_ordinal": ordinal,
                        "previous_publication_ts_ns": previous,
                        "markers": [],
                    },
                }
            )
            previous, ordinal = base["decision_ts_ns"], ordinal + 1
        return (
            rows,
            features,
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


def test_complete_two_stage_support_and_cost_verifiers_preserve_all_sources(study):
    root, path, pin = study
    build_output, cost_output = root / "data/processed/features", root / "data/processed/costs"
    built = s.build(root, path, pin, build_output)
    assert built["summary"]["sessions"] == len(s.parent.DAYS) and built["summary"]["gate"]["passed"]
    assert not (build_output / "costs.json").exists()
    assert s.verify_build(root, path, pin, build_output, built["completion_sha256"]) == built
    evaluated = s.evaluate(root, path, pin, build_output, built["completion_sha256"], cost_output)
    assert evaluated["sessions"] == len(s.parent.DAYS) and not any(evaluated["flags"].values())
    assert (
        s.verify_evaluation(
            root,
            path,
            pin,
            build_output,
            built["completion_sha256"],
            cost_output,
            evaluated["completion_sha256"],
        )
        == evaluated
    )
    with pytest.raises(FileExistsError):
        s.build(root, path, pin, build_output)
    with pytest.raises(FileExistsError):
        s.evaluate(root, path, pin, build_output, built["completion_sha256"], cost_output)


def test_real_support_gate_refuses_scoring_before_output_creation(study, monkeypatch):
    root, path, pin = study
    monkeypatch.setattr(
        s,
        "SUPPORT_GATE",
        {
            "minimum_qualified_markers": 20,
            "minimum_supported_sessions": 4,
            "minimum_validation_supported_sessions": 1,
        },
    )
    # A new registration freezes the real gate; no repinning an old protocol silently.
    old = s.data.review.pinned(path, pin)
    old["protocol"] = s.protocol()
    pin = write_json(path, old)
    output = root / "data/processed/features"
    built = s.build(root, path, pin, output)
    assert built["summary"]["gate"]["passed"] is False
    monkeypatch.setattr(s, "evaluate_day", lambda *a: pytest.fail("costs scored"))
    costs = root / "data/processed/costs"
    with pytest.raises(ValueError, match="support gate"):
        s.evaluate(root, path, pin, output, built["completion_sha256"], costs)
    assert not costs.exists()


def test_snapshot_drift_and_failed_source_quarantine_whole_feature_build(study, monkeypatch):
    root, path, pin = study
    original = s.replay

    def changed(member):
        rows, features, replay = original(member)
        features[0]["auction_features"]["bid_nano"] += tape.TICK
        return rows, features, replay

    monkeypatch.setattr(s, "replay", changed)
    output = root / "data/processed/failure"
    with pytest.raises(ValueError, match="parity"):
        s.build(root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()


def test_changed_event_source_and_repinned_cost_metrics_are_refused(study, monkeypatch):
    root, path, pin = study
    feature_output, cost_output = root / "data/processed/features", root / "data/processed/costs"
    built = s.build(root, path, pin, feature_output)
    s.evaluate(root, path, pin, feature_output, built["completion_sha256"], cost_output)
    completion = cost_output / "completion.json"
    report = json.loads(completion.read_bytes())
    report["summaries"]["overall"]["rows"] += 1
    new_pin = write_json(completion, report)
    with pytest.raises(ValueError, match="pooled"):
        s.verify_evaluation(
            root, path, pin, feature_output, built["completion_sha256"], cost_output, new_pin
        )
    monkeypatch.setattr(e, "ATTACK_SECONDS", 6)
    with pytest.raises(ValueError, match="protocol"):
        s.registration(root, path, pin)


def test_reserved_sources_refused_before_any_archive_or_marker_access(monkeypatch):
    monkeypatch.setattr(s.zipfile, "ZipFile", lambda *a: pytest.fail("reserved raw opened"))
    with pytest.raises(ValueError):
        s.replay({"utc_date": "2026-01-01"})
    with pytest.raises(ValueError):
        e.CrossingBuffer("2026-01-01", "6EH6")
    with pytest.raises(ValueError):
        e.validate_packet({}, START, "2026-01-01")
