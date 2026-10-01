"""Passive execution identity, one-use replenishment and causal feature publication."""

from collections import Counter
from copy import deepcopy

import databento_dbn as dbn
import numpy as np
import pytest
from test_6e_cost_baseline import ASK, BID, DAY, event, ns, update
from test_6e_microdepth_tree import seeded

from ai_trader.research import databento_6e_execution_flow as flow
from ai_trader.research import historical_6e_execution_study as study


def builder():
    return seeded(flow.ExecutionBuilder)


def emit(b, at, messages):
    for i, (action, side, price, size, oid) in enumerate(messages):
        b.consume(
            event(action, side, price, size, oid, at, dbn.F_LAST if i == len(messages) - 1 else 0)
        )


def features(b):
    return b.execution.features(b.last_quote)


def execution(side="A", size=6, oid=2):
    price = ASK if side == "A" else BID
    return [
        ("T", "B" if side == "A" else "A", price, size, 99),
        ("F", side, price, size, oid),
        ("C", side, price, size, oid),
    ]


def test_trade_and_fill_not_double_counted_and_cross_order_reload_matched_once():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution(), ("A", "A", ASK, 6, 3)])
    f = features(b)
    assert f["ask_passive_5s"] == f["ask_linked_decrease_5s"] == 6 / 20
    assert f["ask_other_id_reload_5s"] == f["ask_held_top_passive_5s"] == 6 / 20
    assert f["ask_same_id_reload_5s"] == f["ask_same_id_net_refresh_5s"] == 0
    assert b.rows[0]["features"]["normalized_cvd_5s"] == 12 / 20  # T, not T+F.
    emit(b, ns(12, 0, 1), [("A", "A", ASK, 4, 4)])
    assert features(b)["ask_other_id_reload_5s"] == 6 / 24
    assert not b.execution.credits["A"]


def test_same_id_visible_reload_and_net_refresh_are_separate_overlapping_candidates():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution(), ("M", "A", ASK, 10, 2)])
    f = features(b)
    assert f["ask_same_id_reload_5s"] == f["ask_same_id_net_refresh_5s"] == 6 / 20
    assert f["ask_other_id_reload_5s"] == 0
    assert b.execution.audit["fill_matched_passive_volume"] == 6


def test_same_id_net_refresh_without_visible_intermediate_decrease_is_only_candidate():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution()[:2], ("M", "A", ASK, 10, 2)])
    f = features(b)
    assert f["ask_same_id_net_refresh_5s"] == 6 / 20
    assert f["ask_same_id_reload_5s"] == f["ask_linked_decrease_5s"] == 0


def test_cancel_then_increase_without_fill_does_not_create_execution_credit():
    b = builder()
    emit(b, ns(12, 0, 0), [("C", "A", ASK, 6, 2), ("M", "A", ASK, 10, 2)])
    f = features(b)
    assert f["ask_unlinked_decrease_5s"] == 6 / 20
    assert sum(f[k] for k in f if "unlinked" not in k) == 0


def test_same_price_modify_reduction_links_fill_and_residual_stays_unlinked():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution(size=3)[:2], ("M", "A", ASK, 4, 2)])
    f = features(b)
    assert f["ask_linked_decrease_5s"] == f["ask_unlinked_decrease_5s"] == 3 / 14
    assert f["ask_same_id_net_refresh_5s"] == 0


def test_aggressor_fill_is_not_passive_liquidity():
    b = builder()
    emit(
        b,
        ns(12, 0, 0),
        [
            ("T", "B", ASK, 6, 1),
            ("F", "B", ASK, 6, 1),
            ("F", "A", ASK, 6, 2),
            ("C", "A", ASK, 6, 2),
        ],
    )
    assert features(b)["bid_passive_5s"] == 0
    assert features(b)["ask_passive_5s"] == 6 / 14
    assert b.execution.audit["fill_aggressor_volume"] == 6


@pytest.mark.parametrize(
    "kind",
    ["without_trade", "unknown_aggressor", "unknown_side", "price_mismatch", "unmatched_book"],
)
def test_unclassifiable_fills_remain_unlinked(kind):
    before = ("A", ASK, 10)
    t = flow.Record(0, "T", "N" if kind == "unknown_aggressor" else "B", ASK, 6, 99, None)
    f = flow.Record(
        0,
        "F",
        "N" if kind == "unknown_side" else "A",
        ASK + flow.clock.TICK if kind == "price_mismatch" else ASK,
        6,
        2,
        None if kind == "unmatched_book" else before,
    )
    audit = Counter()
    assert flow.match_fills([f] if kind == "without_trade" else [t, f], audit) == {}
    assert audit[f"fill_{kind}_volume"] == 6


def test_t_summary_stops_at_non_fill_and_overallocated_passive_group_is_rejected():
    t = flow.Record(0, "T", "B", ASK, 6, 99, None)
    f = flow.Record(0, "F", "A", ASK, 6, 2, ("A", ASK, 10))
    n = flow.Record(0, "N", "N", 0, 0, 0, None)
    audit = Counter()
    assert flow.match_fills([t, n, f], audit) == {}
    with pytest.raises(ValueError, match="exceed"):
        flow.match_fills([t, f, f], Counter())


def test_unknown_quantity_rejected_and_above_displayed_not_fabricated_as_extra_volume():
    t = flow.Record(0, "T", "B", ASK, 20, 99, None)
    f = flow.Record(0, "F", "A", ASK, 20, 2, ("A", ASK, 10))
    audit = Counter()
    assert len(flow.match_fills([t, f], audit)) == 1
    assert audit["fill_above_displayed_volume"] == 10
    with pytest.raises(ValueError, match="quantity"):
        flow.match_fills([flow.Record(0, "F", "A", ASK, 0, 2, None)], Counter())


def test_completed_event_only_publishes_features_and_past_rows_never_change():
    b = builder()
    update(b, ns(12, 0, 0))
    frozen = deepcopy(b.execution_rows)
    for action, side, price, size, oid in execution()[:2]:
        b.consume(event(action, side, price, size, oid, ns(12, 0, 1)))
    assert features(b)["ask_passive_5s"] == 0
    assert b.execution_rows == frozen
    b.consume(event("C", "A", ASK, 6, 2, ns(12, 0, 1), dbn.F_LAST))
    assert features(b)["ask_passive_5s"] > 0
    assert (
        b.execution_rows[(DAY.isoformat(), ns(12, 0, 0))] == frozen[(DAY.isoformat(), ns(12, 0, 0))]
    )


@pytest.mark.parametrize("seconds,expected", [(5, 6), (6, 0)])
def test_credit_expiry_inclusive_and_long_gap_resets(seconds, expected):
    b = builder()
    emit(b, ns(12, 0, 0), execution())
    emit(b, ns(12, 0, seconds), [("A", "A", ASK, 6, 3)])
    assert features(b)["ask_other_id_reload_5s"] == expected / 20


def test_best_price_change_discards_credit_even_when_original_price_returns():
    b = builder()
    emit(b, ns(12, 0, 0), execution())
    emit(b, ns(12, 0, 1), [("M", "A", ASK + flow.clock.TICK, 4, 2)])
    assert not b.execution.credits["A"]
    emit(b, ns(12, 0, 2), [("M", "A", ASK, 10, 2)])
    assert features(b)["ask_same_id_reload_5s"] == 0


def test_order_price_change_invalidates_same_id_net_refresh():
    b = builder()
    emit(b, ns(12, 0, 0), [("A", "A", ASK, 10, 3)])
    emit(
        b,
        ns(12, 0, 1),
        [*execution()[:2], ("M", "A", ASK + flow.clock.TICK, 10, 2), ("M", "A", ASK, 10, 2)],
    )
    assert features(b)["ask_same_id_net_refresh_5s"] == 0


def test_full_deletion_and_id_reuse_not_claimed_as_same_id_net_refresh():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution(size=10), ("A", "A", ASK, 10, 2), ("M", "A", ASK, 11, 2)])
    assert features(b)["ask_same_id_net_refresh_5s"] == 0


def test_credit_fifo_and_side_isolation():
    b = builder()
    emit(
        b,
        ns(12, 0, 0),
        [
            *execution(size=3),
            *execution(side="B", size=4, oid=1),
            ("A", "A", ASK, 8, 3),
            ("A", "B", BID, 1, 4),
        ],
    )
    f = features(b)
    assert f["ask_other_id_reload_5s"] == 3 / 22
    assert f["bid_other_id_reload_5s"] == 1 / 22
    assert sum(c[2] for c in b.execution.credits["B"]) == 3


def test_new_features_and_post_window_clear_preserve_all_original_rows_and_audit():
    old, new = seeded(), builder()
    for b in (old, new):
        emit(b, ns(12, 0, 0), [*execution(), ("M", "A", ASK, 10, 2)])
        for s, ms in ((0, 100), (4, 0), (8, 0), (12, 0), (15, 100)):
            update(b, ns(12, 0, s, ms))
        b.consume(event("R", "N", 0, 0, 0, ns(20, 0, 0)))
        b.finish_day()
    old_rows, _ = old.finish()
    new_rows, quality = new.finish()
    assert [{k: v for k, v in r.items() if k != "execution_features"} for r in new_rows] == old_rows
    audit = quality["execution_flow"][0]["audit_including_warmup"]
    assert audit["fill_matched_passive_volume"] == 6
    study.audit_conservation(quality["execution_flow"])
    assert set(new_rows[0]["execution_features"]) == set(flow.FEATURES)


def test_execution_and_rolling_bounds_fail_closed(monkeypatch):
    b = builder()
    monkeypatch.setattr(flow, "MAX_EVENT_RECORDS", 1)
    with pytest.raises(ValueError, match="bound"):
        emit(b, ns(12, 0, 0), execution())


@pytest.mark.parametrize("bound", ["MAX_CREDITS", "MAX_ROLLING_EVENTS"])
def test_credit_and_rolling_storage_bounds_are_enforced(bound, monkeypatch):
    b = builder()
    monkeypatch.setattr(flow, bound, 0)
    with pytest.raises(ValueError, match="bound"):
        emit(b, ns(12, 0, 0), execution())


def test_execution_support_is_not_algebraically_inverse_net_cvd():
    b = builder()
    emit(
        b,
        ns(12, 0, 0),
        [*execution(size=3), *execution(side="B", size=3, oid=1), ("M", "A", ASK, 10, 2)],
    )
    f = features(b)
    assert b.rows[0]["features"]["normalized_cvd_5s"] == 0
    assert f["ask_same_id_net_refresh_5s"] > 0
    assert f["bid_same_id_net_refresh_5s"] == 0


def test_price_changing_modify_cannot_link_a_fill_decrease_at_different_price():
    b = builder()
    emit(b, ns(12, 0, 0), [*execution()[:2], ("M", "A", ASK + flow.clock.TICK, 4, 2)])
    f = features(b)
    assert f["ask_passive_5s"] == 6 / 14
    assert f["ask_unlinked_decrease_5s"] == 10 / 14
    assert f["ask_linked_decrease_5s"] == f["ask_held_top_passive_5s"] == 0


def test_long_event_span_excluded_and_incomplete_event_refused_at_eof():
    b = builder()
    b.consume(event("T", "B", ASK, 6, 99, ns(12, 0, 0)))
    b.consume(event("F", "A", ASK, 6, 2, ns(12, 0, 0)))
    b.consume(event("C", "A", ASK, 6, 2, ns(12, 0, 6), dbn.F_LAST))
    assert sum(features(b).values()) == 0
    assert b.execution.audit["stale_spanning_events_excluded"] == 1
    b.consume(event("M", "B", BID, 10, 1, ns(12, 0, 7)))
    with pytest.raises(ValueError, match="Incomplete"):
        b.finish_day()


def test_non_target_and_bad_flag_records_cannot_publish_new_features():
    b = builder()
    foreign = dbn.MBOMsg(
        publisher_id=1,
        instrument_id=999,
        ts_event=ns(12, 0, 0),
        ts_recv=ns(12, 0, 0),
        action=dbn.Action.TRADE,
        side=dbn.Side.BID,
        price=ASK,
        size=6,
        order_id=99,
        flags=dbn.F_LAST,
    )
    b.consume(foreign)
    assert b.event_records == []
    assert b.execution_rows == {}
    with pytest.raises(ValueError, match="quality flag"):
        b.consume(event("T", "B", ASK, 6, 99, ns(12, 0, 0), dbn.F_LAST | dbn.F_MAYBE_BAD_BOOK))
    assert b.execution_rows == {}


def test_existing_output_refused_before_source_access(tmp_path):
    existing = tmp_path / "retained.json"
    existing.write_bytes(b"keep")
    with pytest.raises(ValueError, match="overwrite"):
        study.run(
            root=tmp_path,
            registration_path=tmp_path / "absent",
            rows_output=existing,
            report_output=tmp_path / "new.json",
        )
    assert existing.read_bytes() == b"keep"


def test_registration_source_protocol_and_overwrites(tmp_path, monkeypatch):
    path = tmp_path / "registration.json"
    study.prepare(path)
    assert not study.registration(path)[0]["protocol"]["training_enabled"]
    with pytest.raises(FileExistsError):
        study.prepare(path)
    monkeypatch.setattr(flow, "MAX_CREDITS", 1)
    with pytest.raises(ValueError, match="registration"):
        study.registration(path)


def test_conservation_rejects_double_used_credit():
    audit = {
        "fill_matched_passive_volume": 3,
        "A_passive_volume": 3,
        "A_linked_decrease_volume": 3,
        "A_other_id_reload_volume": 4,
    }
    with pytest.raises(ValueError, match="conservation"):
        study.audit_conservation([{"audit_including_warmup": audit}])


def test_empty_summary_and_unknown_signal_do_not_invent_performance():
    result = study.summarize([], np.array([1.0, 2.0]))
    assert result["conditional_direction_rows"] == 0
    for compared in result["comparison"].values():
        assert compared["conditional_direction_auc"] is None
        assert compared["within_stratum_pair_weighted_auc"] is None
        assert compared["quote_policy"]["mean_net_ticks"] is None
    with pytest.raises(ValueError, match="Unregistered"):
        study.signal({"features": {}, "execution_features": {}}, "not_registered")
