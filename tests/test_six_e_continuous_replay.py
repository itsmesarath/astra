"""Bounded synthetic continuous replay: no historical data, models, feed or account."""

import hashlib
import json
import math
import sqlite3
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from ai_trader.research import six_e_continuous_replay as replay
from ai_trader.research import six_e_position_ledger as ledger
from ai_trader.training import six_e_liquidity as rules

DAY = "2025-04-07"
SECOND, TICK = ledger.target.SECOND, ledger.target.TICK
MS = SECOND // 1000


def original_row(day=DAY, offset_ns=0, direction=1):
    features = dict.fromkeys(rules.flow.data.FEATURES, 0.0)
    features.update(
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
        "source_session": day,
        "contract": rules.data.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": ledger.target.window(day)[0] + offset_ns,
        "eligible": True,
        "features": features,
        "execution_features": dict.fromkeys(rules.flow.FEATURES, 0.0),
        "outcome": object(),
        "outcomes": object(),
        "hindsight_states": object(),
        "net_ticks": object(),
    }


def session(quotes, decisions=((0, 0, 1),), day=DAY, source_pin="a" * 64):
    start = ledger.target.window(day)[0]
    native = np.asarray(
        [(start + offset, bid * TICK, ask * TICK) for offset, bid, ask in quotes],
        dtype=np.int64,
    ).reshape((-1, 3))
    rows = tuple(
        replay.decision_input(original_row(day, offset, direction), cursor)
        for offset, cursor, direction in decisions
    )
    return replay.ReplaySession(
        day, rules.data.census.dated_contract(day), source_pin, rows, native
    )


def config(inputs, **changes):
    return replace(
        ledger.ScenarioConfig(
            "synthetic-continuous-1",
            "cvd_follow",
            "bracket_exit",
            replay.manifest_pin(inputs),
            "synthetic-continuous-v1",
        ),
        **changes,
    )


def plan_for(source, **changes):
    inputs = (source,) if isinstance(source, replay.ReplaySession) else source
    return replay.build_plan(inputs, config(inputs, **changes))


def events(plan, kind):
    return [event for event in plan.events if isinstance(event, kind)]


def file_pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closed_session():
    return session(
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (300 * MS, 104, 105)]
    )


def unknown_session(day=DAY):
    return session([(0, 100, 101), (100 * MS, 100, 101)], day=day)


def written(tmp_path, source=None):
    plan = plan_for(closed_session() if source is None else source)
    output = tmp_path / "synthetic-replay"
    completion = replay.write_plan(plan, output)
    return plan, output, completion


def verify(plan, output):
    return replay.verify_plan(
        plan.inputs,
        plan.config,
        output,
        file_pin(output / "request.json"),
        file_pin(output / "completion.json"),
    )


def test_projection_ignores_future_poison_and_has_only_causal_fields():
    row = original_row()
    projected = replay.decision_input(row, 0)
    assert set(projected) == {
        "source_session",
        "contract",
        "partition",
        "decision_ts_ns",
        "eligible",
        "features",
        "execution_features",
        "published_cursor",
    }
    row.update(outcome=object(), outcomes=object(), hindsight_states=object(), net_ticks=object())
    assert replay.decision_input(row, 0) == projected
    assert projected["published_cursor"] == 0


def test_core_extra_future_field_is_refused_instead_of_silently_projected():
    source = closed_session()
    row = {**source.decisions[0], "future_return": 100}
    with pytest.raises(ValueError):
        bad = replace(source, decisions=(row,))
        replay.input_manifest((bad,))


def test_manifest_is_deterministic_and_binds_features_quotes_and_source_identity():
    source = closed_session()
    pin = replay.manifest_pin((source,))
    assert replay.manifest_pin((source,)) == pin
    assert isinstance(replay.input_manifest((source,)), dict)
    changed_quote = source.quotes.copy()
    changed_quote[-1, 1:] += TICK
    changed_row = deepcopy(source.decisions[0])
    changed_row["features"]["normalized_cvd_5s"] *= -1
    for changed in (
        replace(source, source_sha256="b" * 64),
        replace(source, quotes=changed_quote),
        replace(source, decisions=(changed_row,)),
    ):
        assert replay.manifest_pin((changed,)) != pin


def test_empty_native_session_requires_no_decisions_and_still_records_boundaries():
    source = session([], decisions=())
    plan = plan_for(source, policy_id="no_trade")
    assert len(events(plan, ledger.SessionBoundary)) == 2
    assert not events(plan, ledger.EntryFill)
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 0
    assert not plan.decisions
    with pytest.raises(ValueError):
        bad = replace(source, decisions=(replay.decision_input(original_row(), 0),))
        replay.input_manifest((bad,))


@pytest.mark.parametrize("direction", [1, -1])
def test_causal_cvd_side_and_integer_fill_accounting(direction):
    quotes = (
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (300 * MS, 104, 105)]
        if direction == 1
        else [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 95, 96), (300 * MS, 96, 97)]
    )
    plan = plan_for(session(quotes, decisions=((0, 0, direction),)))
    entry, exit_fill = events(plan, ledger.EntryFill), events(plan, ledger.ExitFill)
    assert len(entry) == len(exit_fill) == 1
    assert entry[0].side == ("long" if direction == 1 else "short")
    assert entry[0].quantity_contracts == exit_fill[0].quantity_contracts == 1
    assert plan.decisions[0]["direction"] == direction
    assert plan.terminal_state.closed_gross_contract_ticks == 3
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 2
    assert plan.terminal_state.closed_positions == 1


def test_equal_timestamp_native_quotes_are_not_coalesced_or_sorted_by_price():
    source = session(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (100 * MS, 110, 111),
            (200 * MS, 108, 109),
            (200 * MS, 95, 96),
        ]
    )
    plan = plan_for(source)
    assert events(plan, ledger.EntryFill)[0].price_nano == 101 * TICK
    assert (
        events(plan, ledger.ExitIntent)[0].observed_at_ns == ledger.target.window(DAY)[0] + 100 * MS
    )
    assert events(plan, ledger.ExitFill)[0].price_nano == 108 * TICK
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 6


def test_decision_cannot_claim_a_later_equal_time_publication_cursor():
    source = session([(0, 100, 101), (0, 110, 111), (100 * MS, 100, 101)])
    changed = {**source.decisions[0], "published_cursor": 1}
    with pytest.raises(ValueError):
        bad = replace(source, decisions=(changed,))
        replay.input_manifest((bad,))


def test_entry_and_exit_deadline_candidate_quotes_are_inclusive():
    plan = plan_for(
        session([(0, 100, 101), (1100 * MS, 100, 101), (17200 * MS, 104, 105)]),
        exit_plan="time_exit",
    )
    start = ledger.target.window(DAY)[0]
    assert events(plan, ledger.EntryFill)[0].executed_at_ns == start + 1100 * MS
    assert events(plan, ledger.ExitFill)[0].executed_at_ns == start + 17200 * MS
    assert not events(plan, ledger.UnresolvedExit)
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 2


def test_hold_timer_wins_bracket_quote_at_exact_holding_deadline():
    plan = plan_for(
        session(
            [(0, 100, 101), (100 * MS, 100, 101), (15100 * MS, 110, 111), (15200 * MS, 103, 104)]
        )
    )
    start = ledger.target.window(DAY)[0]
    assert events(plan, ledger.ExitIntent)[0].observed_at_ns == start + 15100 * MS
    assert events(plan, ledger.ExitFill)[0].executed_at_ns == start + 15200 * MS
    assert plan.sessions[0]["triggers"].get("timeout", 0) == 1
    assert plan.sessions[0]["triggers"].get("target", 0) == 0


def test_widened_first_entry_quote_refuses_without_searching_later_better_quote():
    plan = plan_for(session([(0, 100, 101), (100 * MS, 100, 102), (200 * MS, 100, 101)]))
    assert not events(plan, ledger.EntryFill)
    assert not events(plan, ledger.ExitIntent)
    assert plan.checkpoint["pending_entry"] is None
    assert plan.checkpoint["cooldown_until_ns"] == (
        ledger.target.window(DAY)[0] + 100 * MS + replay.COOLDOWN
    )
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 0


def test_missing_entry_timeout_is_fired_without_another_native_quote():
    plan = plan_for(session([(0, 100, 101)]))
    assert not events(plan, ledger.EntryFill)
    assert plan.checkpoint["pending_entry"] is None
    assert plan.checkpoint["cooldown_until_ns"] == (
        ledger.target.window(DAY)[0] + 1100 * MS + replay.COOLDOWN
    )


def test_quote_one_nanosecond_after_entry_deadline_cannot_fill():
    plan = plan_for(session([(0, 100, 101), (1100 * MS + 1, 100, 101)]))
    assert not events(plan, ledger.EntryFill)


def test_missing_exit_timeout_fires_without_quote_and_preserves_unknown_inventory():
    plan = plan_for(unknown_session())
    start = ledger.target.window(DAY)[0]
    assert events(plan, ledger.ExitIntent)[0].observed_at_ns == start + 15100 * MS
    assert events(plan, ledger.UnresolvedExit)[0].observed_at_ns == start + 16200 * MS
    assert not events(plan, ledger.ExitFill)
    assert plan.terminal_state.position.remaining_contracts == 1
    assert plan.terminal_state.reservation.status == "UNKNOWN"
    assert plan.terminal_state.complete_simulated_net_contract_ticks is None


def test_quote_after_exit_deadline_is_reference_only_and_never_retries_exit():
    plan = plan_for(session([(0, 100, 101), (100 * MS, 100, 101), (16200 * MS + 1, 120, 121)]))
    assert len(events(plan, ledger.ExitIntent)) == 1
    assert len(events(plan, ledger.UnresolvedExit)) == 1
    assert not events(plan, ledger.ExitFill)
    assert events(plan, ledger.QuoteReference)[-1].bid_nano == 120 * TICK
    assert plan.terminal_state.closed_contracts == 0
    assert plan.terminal_state.complete_simulated_net_contract_ticks is None


def test_stop_overshoot_and_widened_exit_are_retained_in_receipt_price():
    plan = plan_for(
        session([(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 96, 97), (300 * MS, 94, 97)])
    )
    assert plan.sessions[0]["triggers"].get("stop", 0) == 1
    assert events(plan, ledger.ExitFill)[0].price_nano == 94 * TICK
    assert plan.terminal_state.complete_simulated_net_contract_ticks == -8


def test_cooldown_blocks_signal_then_releases_at_later_causal_decision():
    source = session(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (SECOND, 100, 101),
            (1100 * MS, 100, 101),
            (11 * SECOND, 100, 101),
            (11100 * MS, 100, 101),
            (11200 * MS, 105, 106),
            (11300 * MS, 104, 105),
        ],
        decisions=((0, 0, 1), (SECOND, 4, 1), (11 * SECOND, 6, 1)),
    )
    plan = plan_for(source)
    start = ledger.target.window(DAY)[0]
    assert [event.executed_at_ns for event in events(plan, ledger.EntryFill)] == [
        start + 100 * MS,
        start + 11100 * MS,
    ]
    assert len(plan.decisions) == 3
    assert [audit["direction"] for audit in plan.decisions] == [1, 1, 1]
    assert plan.decisions[1]["disposition"] != plan.decisions[0]["disposition"]
    assert plan.terminal_state.closed_positions == 2


def test_cooldown_deadline_is_inclusive_for_new_entry_selection():
    source = session(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (10300 * MS, 100, 101),
            (10400 * MS, 100, 101),
        ],
        decisions=((0, 0, 1), (10300 * MS, 4, 1)),
    )
    assert len(events(plan_for(source), ledger.EntryFill)) == 2


def test_one_position_blocks_later_signals_and_closed_subset_stays_incomplete():
    source = session(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (11 * SECOND, 100, 101),
            (11100 * MS, 100, 101),
            (30 * SECOND, 120, 121),
        ],
        decisions=((0, 0, 1), (11 * SECOND, 4, 1), (30 * SECOND, 6, 1)),
    )
    plan = plan_for(source)
    assert len(events(plan, ledger.EntryFill)) == 2
    assert len(events(plan, ledger.ExitFill)) == 1
    assert plan.terminal_state.closed_net_contract_ticks == 2
    assert plan.terminal_state.closed_positions == 1
    assert plan.terminal_state.complete_simulated_net_contract_ticks is None
    assert len(plan.decisions) == 3


def test_unknown_and_inventory_survive_next_session_without_daily_reset():
    first = unknown_session()
    second = session([(0, 110, 111), (100 * MS, 112, 113), (SECOND, 114, 115)], day="2025-04-08")
    plan = plan_for((first, second))
    assert len(events(plan, ledger.SessionBoundary)) == 4
    assert len(events(plan, ledger.EntryFill)) == 1
    assert len(events(plan, ledger.ExitIntent)) == 1
    assert not events(plan, ledger.ExitFill)
    assert plan.terminal_state.position.entry_source_session == DAY
    assert plan.terminal_state.reservation.status == "UNKNOWN"
    assert plan.terminal_state.last_reference.source_session == "2025-04-08"
    assert plan.terminal_state.complete_simulated_net_contract_ticks is None
    assert len(plan.decisions) == 2


def test_roll_keeps_original_contract_and_does_not_mark_with_new_contract_quotes():
    first = unknown_session("2025-06-06")
    second = session([(0, 120, 121), (100 * MS, 120, 121)], day="2025-06-09")
    plan = plan_for((first, second))
    assert first.contract == "6EM5" and second.contract == "6EU5"
    assert plan.terminal_state.position.contract == "6EM5"
    assert plan.terminal_state.reservation.status == "UNKNOWN"
    assert not events(plan, ledger.ExitFill)
    assert all(reference.contract == "6EM5" for reference in events(plan, ledger.QuoteReference))
    assert plan.terminal_state.last_reference.source_session == "2025-06-06"
    assert plan.terminal_state.reference_age_ns > 2 * 86400 * SECOND


def test_no_trade_keeps_all_decision_audits_but_never_fills():
    plan = plan_for(closed_session(), policy_id="no_trade")
    assert len(plan.decisions) == 1 and plan.decisions[0]["direction"] == 0
    assert not events(plan, ledger.EntryFill)
    assert not events(plan, ledger.ExitIntent)
    assert plan.terminal_state.complete_simulated_net_contract_ticks == 0


@pytest.mark.parametrize("policy", ["cpu_cost", "cpu_cost_liquidity", "unknown-policy"])
def test_model_or_unregistered_policy_is_refused(policy):
    source = closed_session()
    with pytest.raises(ValueError):
        replay.build_plan((source,), config((source,), policy_id=policy))


@pytest.mark.parametrize(
    "changes",
    [{"max_position_contracts": 2}, {"extra_round_trip_ticks_per_contract": 2}],
)
def test_unregistered_quantity_and_cost_changes_are_refused(changes):
    source = closed_session()
    with pytest.raises(ValueError):
        replay.build_plan((source,), config((source,), **changes))


def test_config_manifest_pin_must_equal_actual_complete_inputs():
    source = closed_session()
    with pytest.raises(ValueError):
        replay.build_plan((source,), config((source,), source_manifest_sha256="b" * 64))


class UnreadableQuotes:
    def __getattribute__(self, name):
        raise AssertionError("Rejected metadata attempted quote access")


@pytest.mark.parametrize("day", ["2026-01-01", "2025-4-7", "not-a-date"])
def test_reserved_or_invalid_session_rejected_before_quote_access(day):
    with pytest.raises(ValueError):
        source = replay.ReplaySession(day, "6EM5", "a" * 64, (), UnreadableQuotes())
        replay.input_manifest((source,))


@pytest.mark.parametrize("pin", ["not-a-hash", "A" * 64, "a" * 63])
def test_invalid_source_pin_is_rejected_before_quote_access(pin):
    with pytest.raises(ValueError):
        source = replay.ReplaySession(DAY, "6EM5", pin, (), UnreadableQuotes())
        replay.input_manifest((source,))


@pytest.mark.parametrize(
    "change",
    ["float", "shape", "order", "before_window", "after_window", "crossed", "grid", "zero"],
)
def test_native_quote_schema_order_window_and_tick_guards(change):
    source = closed_session()
    quotes = source.quotes.copy()
    if change == "float":
        quotes = quotes.astype(np.float64)
    elif change == "shape":
        quotes = quotes[:, :2]
    elif change == "order":
        quotes[[1, 2]] = quotes[[2, 1]]
    elif change == "before_window":
        quotes[0, 0] -= 1
    elif change == "after_window":
        quotes[-1, 0] = ledger.target.window(DAY)[1]
    elif change == "crossed":
        quotes[1, 2] = quotes[1, 1]
    elif change == "grid":
        quotes[1, 1] += 1
    else:
        quotes[1, 1] = 0
    with pytest.raises(ValueError):
        bad = replace(source, quotes=quotes)
        replay.input_manifest((bad,))


@pytest.mark.parametrize(
    "change",
    [
        "cursor_bool",
        "cursor_range",
        "time",
        "partition",
        "contract",
        "eligible",
        "nan",
        "extra_feature",
    ],
)
def test_strict_decision_identity_cursor_and_causal_feature_guards(change):
    source = closed_session()
    row = deepcopy(source.decisions[0])
    if change == "cursor_bool":
        row["published_cursor"] = True
    elif change == "cursor_range":
        row["published_cursor"] = len(source.quotes)
    elif change == "time":
        row["decision_ts_ns"] += 1
    elif change == "partition":
        row["partition"] = "reserved"
    elif change == "contract":
        row["contract"] = "6EU5"
    elif change == "eligible":
        row["eligible"] = 1
    elif change == "nan":
        row["features"]["normalized_cvd_5s"] = float("nan")
    else:
        row["features"]["future_profit"] = 1.0
    with pytest.raises(ValueError):
        bad = replace(source, decisions=(row,))
        replay.input_manifest((bad,))


def test_decision_spacing_cannot_be_relaxed_to_manufacture_pending_entry_cases():
    with pytest.raises(ValueError):
        source = session(
            [(0, 100, 101), (500 * MS, 100, 101)],
            decisions=((0, 0, 1), (500 * MS, 1, 1)),
        )
        replay.input_manifest((source,))


@pytest.mark.parametrize("kind", ["duplicate", "reverse"])
def test_complete_session_sequence_must_be_unique_and_chronological(kind):
    first, second = unknown_session(), unknown_session("2025-04-08")
    inputs = (first, first) if kind == "duplicate" else (second, first)
    with pytest.raises(ValueError):
        replay.input_manifest(inputs)


@pytest.mark.parametrize("bound", ["MAX_SESSIONS", "MAX_DECISIONS", "MAX_QUOTES", "MAX_EVENTS"])
def test_input_and_event_resource_bounds_refuse_instead_of_truncating(bound, monkeypatch):
    source = closed_session()
    inputs = (source, unknown_session("2025-04-08"))
    cfg = config(inputs)
    monkeypatch.setattr(replay, bound, 1)
    with pytest.raises(ValueError):
        replay.build_plan(inputs, cfg)


def test_plan_copies_inputs_and_pins_generated_receipts():
    source = closed_session()
    plan = plan_for(source)
    assert plan.inputs[0].quotes is not source.quotes
    assert not plan.inputs[0].quotes.flags.writeable
    assert len(plan.receipts) == 2
    assert all(
        len(event.paper_receipt_sha256) == 64
        for event in plan.events
        if hasattr(event, "paper_receipt_sha256")
    )


def test_original_execution_constants_remain_controls():
    assert replay.COOLDOWN == 10 * SECOND
    assert ledger.target.ENTRY_DELAY == ledger.target.EXIT_DELAY == 100 * MS
    assert ledger.target.WAIT == SECOND
    assert ledger.target.HOLD == 15 * SECOND
    assert (ledger.target.TARGET, ledger.target.STOP, ledger.target.COST) == (3, -3, 1)


def test_generated_receipt_hash_and_crossing_price_are_independently_reproducible():
    plan = plan_for(closed_session())
    fills = {
        event.evidence_id: event
        for event in (*events(plan, ledger.EntryFill), *events(plan, ledger.ExitFill))
    }
    for document in plan.receipts:
        receipt = document["receipt"]
        canonical = json.dumps(
            receipt, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        assert document["sha256"] == hashlib.sha256(canonical).hexdigest()
        fill = fills[document["evidence_id"]]
        assert fill.paper_receipt_sha256 == document["sha256"]
        quote = plan.inputs[0].quotes[receipt["native_cursor"]]
        assert fill.executed_at_ns == int(quote[0]) == receipt["executed_at_ns"]
        assert fill.price_nano == int(quote[2] if receipt["phase"] == "entry" else quote[1])
        assert receipt["source_manifest_sha256"] == plan.config.source_manifest_sha256
        assert receipt["contract"] == plan.inputs[0].contract
        assert receipt["quantity_contracts"] == 1
        assert receipt["execution_confirmed"] is False


def test_planning_never_calls_model_fitting_prediction_or_future_target_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Continuous replay called fitting, prediction or future targets")

    monkeypatch.setattr(rules, "fit", forbidden)
    monkeypatch.setattr(rules.Model, "predict", forbidden)
    monkeypatch.setattr(ledger.target, "targets", forbidden)
    monkeypatch.setattr(replay.study.resource, "replay_day", forbidden)
    assert plan_for(closed_session()).terminal_state.closed_positions == 1


@pytest.mark.parametrize("policy", ["cvd_follow", "liquidity_follow", "absorption_fade"])
def test_fixed_feature_rules_produce_their_own_causal_direction(policy):
    source = closed_session()
    expected = 1
    if policy == "absorption_fade":
        row = deepcopy(source.decisions[0])
        row["features"]["mid_change_5s_ticks"] = 0.0
        row["features"]["queue_imbalance"] = -0.5
        row["execution_features"].update(ask_held_top_passive_5s=0.25, ask_other_id_reload_5s=0.1)
        source = replace(source, decisions=(row,))
        expected = -1
    plan = plan_for(source, policy_id=policy)
    assert plan.decisions[0]["direction"] == expected
    assert events(plan, ledger.EntryFill)[0].side == ("long" if expected > 0 else "short")


def test_exit_latency_window_margin_is_strict_at_session_end():
    start, end = ledger.target.window(DAY)
    offset = end - start - ledger.target.MARGIN
    source = session(
        [(offset, 100, 101), (offset + 100 * MS, 100, 101)],
        decisions=((offset, 0, 1),),
    )
    plan = plan_for(source)
    assert plan.decisions[0]["disposition"] == "ineligible"
    assert not events(plan, ledger.EntryFill)


def test_planning_deadline_refuses_a_successful_prefix(monkeypatch):
    source = closed_session()
    cfg = config((source,))
    ticks = 0

    def advancing_clock():
        nonlocal ticks
        ticks += 1
        return float(ticks)

    monkeypatch.setattr(replay, "MAX_SECONDS", 0)
    monkeypatch.setattr(replay.time, "monotonic", advancing_clock)
    with pytest.raises(TimeoutError):
        replay.build_plan((source,), cfg)


def test_sidecar_byte_bound_refuses_before_output_creation(tmp_path, monkeypatch):
    plan = plan_for(closed_session())
    monkeypatch.setattr(replay, "MAX_OUTPUT_BYTES", 1)
    output = tmp_path / "oversized"
    with pytest.raises(ValueError):
        replay.write_plan(plan, output)
    assert not output.exists()


def test_written_plan_reconstructs_full_account_read_only(tmp_path):
    plan, output, completion = written(tmp_path)
    assert isinstance(completion, dict)
    for name in (
        "request.json",
        "events.jsonl",
        "receipts.jsonl",
        "decisions.jsonl",
        "scenario.sqlite",
        "completion.json",
    ):
        assert (output / name).is_file()
    before = {path.name: file_pin(path) for path in output.iterdir() if path.is_file()}
    assert isinstance(verify(plan, output), dict)
    after = {path.name: file_pin(path) for path in output.iterdir() if path.is_file()}
    assert after == before
    with ledger.ScenarioLedger(output / "scenario.sqlite", plan.config) as account:
        state = account.snapshot(expected_tip_sha256=plan.terminal_state.tip_sha256)
    assert state == plan.terminal_state
    assert state.sequence == len(plan.events)


def test_exclusive_output_is_never_overwritten_or_adopted(tmp_path):
    plan, output, _ = written(tmp_path)
    before = {path.name: file_pin(path) for path in output.iterdir() if path.is_file()}
    with pytest.raises((ValueError, FileExistsError)):
        replay.write_plan(plan, output)
    assert {path.name: file_pin(path) for path in output.iterdir() if path.is_file()} == before


@pytest.mark.parametrize("field", ["terminal_state", "events", "receipts", "decisions"])
def test_forged_plan_is_rejected_before_output_creation(field, tmp_path):
    plan = plan_for(closed_session())
    if field == "terminal_state":
        value = replace(plan.terminal_state, closed_net_contract_ticks=1000)
    elif field == "events":
        value = plan.events[:-1]
    elif field == "receipts":
        value = ({"forged": True}, *plan.receipts[1:])
    else:
        value = ({**plan.decisions[0], "direction": -1},)
    output = tmp_path / "forged"
    with pytest.raises(ValueError):
        replay.write_plan(replace(plan, **{field: value}), output)
    assert not output.exists()


def test_adapter_source_drift_rejects_a_prepared_plan_before_creation(tmp_path, monkeypatch):
    plan = plan_for(closed_session())
    pins = replay.fingerprints()
    monkeypatch.setattr(
        replay, "fingerprints", lambda: {**pins, "six_e_continuous_replay.py": "f" * 64}
    )
    output = tmp_path / "source-drift"
    with pytest.raises(ValueError):
        replay.write_plan(plan, output)
    assert not output.exists()


def test_verification_refuses_different_fixture_even_when_account_totals_match(tmp_path):
    plan, output, _ = written(tmp_path)
    source = replace(plan.inputs[0], source_sha256="b" * 64)
    changed_inputs = (source,)
    with pytest.raises(ValueError):
        replay.verify_plan(
            changed_inputs,
            config(changed_inputs),
            output,
            file_pin(output / "request.json"),
            file_pin(output / "completion.json"),
        )


@pytest.mark.parametrize(
    "name", ["request.json", "completion.json", "events.jsonl", "receipts.jsonl", "decisions.jsonl"]
)
def test_changed_sidecar_is_not_verified(name, tmp_path):
    plan, output, _ = written(tmp_path)
    request_pin, completion_pin = (
        file_pin(output / "request.json"),
        file_pin(output / "completion.json"),
    )
    path = output / name
    path.write_bytes(path.read_bytes() + b"\n{}\n")
    with pytest.raises(ValueError):
        replay.verify_plan(plan.inputs, plan.config, output, request_pin, completion_pin)


def test_repinning_a_forged_receipt_and_request_cannot_establish_causal_provenance(tmp_path):
    plan, output, _ = written(tmp_path)
    path = output / "receipts.jsonl"
    documents = [json.loads(line) for line in path.read_bytes().splitlines()]
    documents[0]["receipt"]["price_nano"] += TICK
    receipt_raw = json.dumps(
        documents[0]["receipt"], sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    documents[0]["sha256"] = hashlib.sha256(receipt_raw).hexdigest()
    raw = b"".join(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for document in documents
    )
    path.write_bytes(raw)
    request_path = output / "request.json"
    request = json.loads(request_path.read_bytes())
    request["sidecars"]["receipts.jsonl"] = {"bytes": len(raw), "sha256": file_pin(path)}
    request_path.write_bytes(json.dumps(request, sort_keys=True, separators=(",", ":")).encode())
    completion_path = output / "completion.json"
    completion = json.loads(completion_path.read_bytes())
    completion["request_sha256"] = file_pin(request_path)
    completion_path.write_bytes(
        json.dumps(completion, sort_keys=True, separators=(",", ":")).encode()
    )
    with pytest.raises(ValueError):
        verify(plan, output)


def test_failed_durable_append_retains_evidence_and_forbids_retry(tmp_path, monkeypatch):
    plan = plan_for(closed_session())
    output = tmp_path / "failed-write"
    append = ledger.ScenarioLedger.append
    calls = 0

    def interrupted(account, event, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic durable-write interruption")
        return append(account, event, **kwargs)

    monkeypatch.setattr(ledger.ScenarioLedger, "append", interrupted)
    with pytest.raises(RuntimeError, match="Synthetic"):
        replay.write_plan(plan, output)
    assert (output / "request.json").exists()
    assert (output / "scenario.sqlite").exists()
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()
    with pytest.raises(FileExistsError):
        replay.write_plan(plan, output)


def test_valid_extra_reference_suffix_cannot_be_adopted_as_the_registered_plan(tmp_path):
    plan, output, _ = written(tmp_path, unknown_session())
    last = plan.terminal_state.last_reference
    assert last is not None
    extra = ledger.QuoteReference(
        "unregistered-extra-reference",
        DAY,
        ledger.target.window(DAY)[1] + SECOND,
        last.contract,
        last.quote_at_ns,
        last.native_cursor + 1,
        last.bid_nano,
        last.ask_nano,
    )
    with ledger.ScenarioLedger(output / "scenario.sqlite", plan.config, read_only=False) as account:
        account.append(extra, expected_tip_sha256=account.snapshot().tip_sha256)
        assert account.snapshot().sequence == len(plan.events) + 1
    with pytest.raises(ValueError):
        verify(plan, output)


def test_valid_prefix_truncation_is_refused_even_when_remaining_chain_is_valid(tmp_path):
    plan, output, _ = written(tmp_path)
    with sqlite3.connect(output / "scenario.sqlite") as connection:
        connection.execute("DROP TRIGGER events_no_delete")
        connection.execute("DELETE FROM events WHERE sequence = ?", (len(plan.events),))
        for kind, name, _, sql in ledger._schema_rows():
            if kind == "trigger" and name == "events_no_delete":
                connection.execute(sql)
    with ledger.ScenarioLedger(output / "scenario.sqlite", plan.config) as account:
        assert account.snapshot().sequence == len(plan.events) - 1
    with pytest.raises(ValueError):
        verify(plan, output)


def test_valid_rewritten_account_with_same_totals_still_fails_expected_event_head(tmp_path):
    plan, output, _ = written(tmp_path)
    altered = []
    for event in plan.events:
        if isinstance(event, (ledger.EntryFill, ledger.ExitFill)):
            event = replace(
                event,
                price_nano=event.price_nano + TICK,
                paper_receipt_sha256=hashlib.sha256(
                    f"forged-{event.event_id}".encode()
                ).hexdigest(),
            )
        altered.append(event)
    with sqlite3.connect(output / "scenario.sqlite") as connection:
        connection.execute("DROP TRIGGER events_no_update")
        previous = connection.execute("SELECT sha256 FROM config").fetchone()[0]
        for sequence, event in enumerate(altered, 1):
            raw = ledger._record(event)
            tip = hashlib.sha256(previous.encode() + b"\n" + raw).hexdigest()
            connection.execute(
                "UPDATE events SET payload = ?, previous_sha256 = ?, sha256 = ? WHERE sequence = ?",
                (raw, previous, tip, sequence),
            )
            previous = tip
        for kind, name, _, sql in ledger._schema_rows():
            if kind == "trigger" and name == "events_no_update":
                connection.execute(sql)
    with ledger.ScenarioLedger(output / "scenario.sqlite", plan.config) as account:
        state = account.snapshot()
    assert state.closed_net_contract_ticks == plan.terminal_state.closed_net_contract_ticks
    assert state.closed_positions == plan.terminal_state.closed_positions
    assert state.sequence == plan.terminal_state.sequence
    assert state.tip_sha256 != plan.terminal_state.tip_sha256
    with pytest.raises(ValueError):
        verify(plan, output)


def test_mutating_returned_flags_cannot_grant_authority_to_later_results(tmp_path):
    plan, output, completion = written(tmp_path)
    completion["flags"]["trading_enabled"] = True
    assert replay.FLAGS["trading_enabled"] is False
    verified = verify(plan, output)
    assert verified["flags"]["trading_enabled"] is False
    verified["flags"]["promotion_allowed"] = True
    assert replay.FLAGS["promotion_allowed"] is False


def test_completed_synthetic_artifacts_never_grant_training_trading_or_promotion(tmp_path):
    plan, output, completion = written(tmp_path)
    verified = verify(plan, output)
    documents = [completion, verified, json.loads((output / "request.json").read_text())]

    def inspect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {
                    "training_eligible",
                    "strategy_scoring_allowed",
                    "promotion_allowed",
                    "trading_enabled",
                    "broker_execution_confirmed",
                    "receipt_provenance_verified",
                }:
                    assert child is False
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for document in documents:
        inspect(document)
