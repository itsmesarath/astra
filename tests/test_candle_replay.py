"""Synthetic independent-execution checks; no historical or held-out data."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from ai_trader.backtesting.candle_replay import (
    CandleSession,
    ReplayConfig,
    SignalDistances,
    replay_candles,
    replay_report_payload,
    write_replay_report,
)
from ai_trader.backtesting.economic_metrics import EconomicConfig
from ai_trader.features import kline_dataset
from ai_trader.features.kline_dataset import Kline, TripleBarrierConfig

D = Decimal


def distance_session(candles, stop="1", target="2"):
    return replace(session(candles), signal_distances=(SignalDistances(999, D(stop), D(target)),))


@pytest.mark.parametrize("cost", ["2", "8", "14"])
def test_price_distances_do_not_move_with_costs(cost):
    candles = [bar(0), bar(1), bar(2, high="103", low="100")]
    config = ReplayConfig(
        barriers=TripleBarrierConfig(slippage_bps=D(cost)),
        holding_bars=2,
        barrier_mode="signal_distances",
        require_full_horizon=True,
    )
    report = replay_candles((distance_session(candles),), config)
    assert report.trades[0].exit.reference_price == D(102)
    assert report.trades[0].exit.reason == "target"
    assert report.trades[0].entry.price == D(100) * (1 + D(cost) / 10000)
    payload = replay_report_payload(report)
    assert payload["schema_version"] == 2
    assert payload["barriers"] == "signal_absolute_distances_from_entry_open_cost_independent"


def test_absolute_stop_adverse_gap_and_ambiguous_touch():
    config = ReplayConfig(barrier_mode="signal_distances", holding_bars=2)
    for candle, reason, price in (
        (bar(2, "98", "100", "97"), "gap_stop", D(98)),
        (bar(2, "100", "103", "98"), "ambiguous_stop", D(99)),
    ):
        report = replay_candles((distance_session([bar(0), bar(1), candle]),), config)
        assert report.trades[0].exit.reason == reason
        assert report.trades[0].exit.reference_price == price


def test_distances_reanchor_at_delayed_open_and_require_full_horizon():
    candles = [bar(0), bar(1), bar(2, "110"), bar(3, "110", high="113")]
    config = ReplayConfig(
        barrier_mode="signal_distances",
        holding_bars=2,
        entry_delay_bars=1,
        require_full_horizon=True,
    )
    report = replay_candles((distance_session(candles),), config)
    assert report.trades[0].entry.reference_price == D(110)
    assert report.trades[0].exit.reference_price == D(112)
    short = replay_candles((distance_session(candles[:-1]),), config)
    assert not short.fills
    assert short.decisions[0].reason == "insufficient_horizon"


def test_nonpositive_stop_rejected_without_spending_cash():
    report = replay_candles(
        (distance_session([bar(0), bar(1)], stop="100"),),
        ReplayConfig(barrier_mode="signal_distances"),
    )
    assert not report.fills
    assert report.decisions[0].reason == "invalid_stop_price"
    assert report.starting_balance == report.ending_balance


@pytest.mark.parametrize(
    "distances",
    [
        (),
        (SignalDistances(999, D(0), D(2)),),
        (SignalDistances(999, D(1), D("NaN")),),
        (SignalDistances(1999, D(1), D(2)),),
        (SignalDistances(999, D(1), D(2)),) * 2,
    ],
)
def test_distances_fail_closed_on_missing_invalid_or_duplicate_evidence(distances):
    with pytest.raises(ValueError):
        replay_candles(
            (replace(session([bar(0), bar(1)]), signal_distances=distances),),
            ReplayConfig(barrier_mode="signal_distances"),
        )


def test_distances_require_explicit_mode_and_affect_input_hash():
    candles = [bar(0), bar(1)]
    with pytest.raises(ValueError, match="explicit"):
        replay_candles((distance_session(candles),), ReplayConfig())
    config = ReplayConfig(barrier_mode="signal_distances")
    a = replay_candles((distance_session(candles),), config)
    b = replay_candles((distance_session(candles, target="3"),), config)
    assert a.input_sha256 != b.input_sha256


def bar(index: int, opening="100", high=None, low=None, close=None) -> Kline:
    opening, close = D(opening), D(close if close is not None else opening)
    return Kline(
        index * 1000,
        opening,
        D(high) if high is not None else max(opening, close),
        D(low) if low is not None else min(opening, close),
        close,
        D("10"),
        index * 1000 + 999,
        D("1000"),
        10,
        D("5"),
    )


def session(candles, signals=(0,), name="one") -> CandleSession:
    return CandleSession(
        name, tuple(candles), tuple(candles[index].close_time_ms for index in signals)
    )


def no_costs(**kwargs) -> ReplayConfig:
    return ReplayConfig(
        capital=EconomicConfig(starting_balance=1000),
        barriers=TripleBarrierConfig(
            take_profit_bps=D("100"),
            stop_loss_bps=D("100"),
            taker_fee_bps=D("0"),
            slippage_bps=D("0"),
        ),
        **kwargs,
    )


@pytest.mark.parametrize(
    "last,reason,reference,event_time",
    [
        (bar(2, "98", "102", "97"), "gap_stop", "98", 2000),
        (bar(2, "102", "103", "98"), "gap_target", "102", 2000),
        (bar(2, "99", "102", "98"), "gap_stop", "99", 2000),
        (bar(2, "101", "102", "98"), "gap_target", "101", 2000),
        (bar(2, "100", "102", "98"), "ambiguous_stop", "99", 2999),
        (bar(2, "100", "100", "98"), "stop", "99", 2999),
        (bar(2, "100", "102", "100"), "target", "101", 2999),
        (bar(2, "100", close="100.5"), "time", "100.5", 2999),
    ],
)
def test_independent_barriers_match_label_reference_semantics(last, reason, reference, event_time):
    candles = [bar(0), bar(1), last]
    config = no_costs(holding_bars=2)
    report = replay_candles((session(candles),), config)
    label = kline_dataset.calculate_triple_barrier_outcome(
        candles, 0, horizon_bars=2, config=config.barriers
    )
    trade = report.trades[0]
    assert trade.exit.reason == label.barrier_hit == reason
    assert trade.exit.reference_price == label.exit_price == D(reference)
    assert trade.exit.event_time_ms == label.future_event_time_ms == event_time
    assert trade.net_pnl == D("10") * (D(reference) - 100)
    assert report.ending_balance == 1000 + trade.net_pnl
    assert report.exposure_ms == event_time - 1000 + 1


def test_replay_never_calls_label_calculator(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Replay must execute candles independently")

    monkeypatch.setattr(kline_dataset, "calculate_triple_barrier_outcome", forbidden)
    report = replay_candles((session([bar(0), bar(1)]),), no_costs(holding_bars=1))
    assert report.trades[0].exit.reason == "time"


def test_fee_inclusive_sizing_cash_and_actual_turnover():
    config = ReplayConfig(
        capital=EconomicConfig(starting_balance=1000, position_fraction=0.5),
        quantity_step=D("1"),
        holding_bars=1,
        barriers=TripleBarrierConfig(
            take_profit_bps=D("1000"),
            stop_loss_bps=D("1000"),
            taker_fee_bps=D("100"),
            slippage_bps=D("100"),
        ),
    )
    report = replay_candles((session([bar(0), bar(1, close="102")]),), config)
    buy, sell = report.fills
    # 500 budget; 101 * 1.01 per unit => four units, never borrowed fee cash.
    assert buy.quantity == sell.quantity == 4
    assert buy.price == 101
    assert buy.fee_quote == D("4.04")
    assert sell.price == D("100.98")
    assert sell.fee_quote == D("4.0392")
    assert report.ending_balance == D("991.8408")
    assert report.fees_quote == D("8.0792")
    assert report.turnover_quote == D("807.92")  # 404 + 403.92, not twice 404
    assert report.net_pnl == report.trades[0].net_pnl == D("-8.1592")
    assert all(mark.cash >= 0 for mark in report.marks)


def test_costed_gap_loss_is_not_capped_and_risk_uses_only_settled_pnl():
    config = ReplayConfig(
        capital=EconomicConfig(starting_balance=1000, session_loss_limit=1),
        quantity_step=D("1"),
    )
    report = replay_candles(
        (session([bar(0), bar(1), bar(2, "99"), bar(3, "99")], signals=(0, 1, 2)),),
        config,
    )
    trade = report.trades[0]
    assert trade.exit.reason == "gap_stop"
    assert trade.entry.quantity == 9
    assert trade.entry.price == D("100.02")
    assert trade.exit.price == D("98.9802")
    assert trade.net_pnl == D("-11.1492018")
    assert report.ending_balance == D("988.8507982")
    assert [decision.reason for decision in report.decisions] == [
        "filled",
        "position_open",
        "session_limit",
    ]


def test_full_cash_allocation_reserves_entry_fee_without_negative_cash():
    report = replay_candles((session([bar(0), bar(1)]),), ReplayConfig())
    buy = report.fills[0]
    assert buy.notional_quote + buy.fee_quote <= report.starting_balance
    assert all(mark.cash >= 0 for mark in report.marks)
    assert report.ending_balance == pytest.approx(
        report.starting_balance + sum(trade.net_pnl for trade in report.trades)
    )


def test_marks_capture_unrealized_drawdown_missing_from_closed_trades():
    config = replace(
        no_costs(holding_bars=3),
        barriers=TripleBarrierConfig(
            take_profit_bps=D("2000"),
            stop_loss_bps=D("2000"),
            taker_fee_bps=D("0"),
            slippage_bps=D("0"),
        ),
    )
    report = replay_candles(
        (
            session(
                [
                    bar(0),
                    bar(1, close="105"),
                    bar(2, "105", low="90", close="90"),
                    bar(3, "90", high="100", close="100"),
                ]
            ),
        ),
        config,
    )
    assert [mark.equity for mark in report.marks] == [1000, 1050, 900, 1000]
    assert report.maximum_marked_drawdown_pct == D(150) / 1050 * 100
    assert report.maximum_closed_trade_drawdown_pct == 0
    assert report.ending_balance == 1000
    assert report.trades[0].exit.reason == "time"
    for mark in report.marks:
        assert mark.equity == mark.cash + mark.quantity * mark.close


def test_full_bar_delay_changes_entry_without_using_skipped_price_moves():
    candles = [bar(0), bar(1, close="110"), bar(2, "110")]
    immediate = replay_candles((session(candles),), no_costs(holding_bars=1))
    delayed = replay_candles((session(candles),), no_costs(holding_bars=1, entry_delay_bars=1))
    assert immediate.trades[0].entry.reference_price == 100
    assert delayed.trades[0].entry.reference_price == 110
    assert immediate.trades[0].entry.event_time_ms == 1000
    assert delayed.trades[0].entry.event_time_ms == 2000
    assert delayed.net_pnl == 0
    assert immediate.net_pnl == 10
    assert delayed.trades[0].exit.reason == "time"


def test_signals_while_waiting_or_holding_are_not_replayed_later():
    report = replay_candles(
        (session([bar(i) for i in range(5)], signals=(0, 1, 2, 4)),),
        no_costs(holding_bars=2, entry_delay_bars=1),
    )
    assert [decision.reason for decision in report.decisions] == [
        "filled",
        "pending_entry",
        "position_open",
        "session_end",
    ]
    assert len(report.trades) == 1


@pytest.mark.parametrize(
    "ending,limit_key", [("101", "session_profit_target"), ("99", "session_loss_limit")]
)
def test_session_limits_settle_before_new_entries_and_reset_next_session(ending, limit_key):
    config = replace(
        no_costs(holding_bars=1),
        capital=EconomicConfig(
            starting_balance=1000,
            **{limit_key: 5},
        ),
    )
    first = session([bar(0), bar(1, close=ending), bar(2)], signals=(0, 1))
    second = session([bar(5), bar(6)], name="two")
    report = replay_candles((first, second), config)
    assert [decision.reason for decision in report.decisions] == [
        "filled",
        "session_limit",
        "filled",
    ]
    assert report.sessions[1].starting_balance == report.sessions[0].ending_balance
    assert report.sessions[1].trades == 1
    assert report.net_pnl == sum(trade.net_pnl for trade in report.trades)


def test_session_boundary_liquidates_and_expires_delayed_entries():
    first = session([bar(0), bar(1)], signals=(0, 1))
    second = session([bar(10), bar(11)], name="two")
    report = replay_candles((first, second), no_costs())
    assert [trade.exit.reason for trade in report.trades] == ["session_end", "session_end"]
    assert [decision.reason for decision in report.decisions] == ["filled", "session_end", "filled"]
    assert report.observation_ms == 12000
    assert report.exposure_ms == 2000
    assert report.marks[-1].quantity == 0
    delayed = replay_candles((first, second), no_costs(entry_delay_bars=1))
    assert not delayed.fills
    assert all(decision.reason == "session_end" for decision in delayed.decisions)


def test_cooldown_carries_across_sessions_and_trade_count_resets():
    config = replace(
        no_costs(holding_bars=1),
        capital=EconomicConfig(
            starting_balance=1000,
            minimum_reentry_delay_ms=2000,
            maximum_trades_per_session=1,
        ),
    )
    first = session([bar(0), bar(1)])
    second = session([bar(2), bar(3), bar(4), bar(5)], signals=(0, 1, 2), name="two")
    report = replay_candles((first, second), config)
    assert [decision.reason for decision in report.decisions] == [
        "filled",
        "cooldown",
        "filled",
        "trade_limit",
    ]
    assert report.sessions[1].trades == 1
    assert report.trades[1].entry.event_time_ms == 4000


def test_no_trades_and_quantity_rounding_to_zero():
    candles = [bar(0), bar(1)]
    flat = replay_candles((session(candles, signals=()),), no_costs())
    tiny = replay_candles((session(candles),), replace(no_costs(), quantity_step=D("100")))
    assert flat.ending_balance == tiny.ending_balance == 1000
    assert flat.fees_quote == flat.turnover_quote == flat.exposure_ms == 0
    assert not flat.decisions
    assert tiny.decisions[0].reason == "insufficient_cash"


def test_future_suffix_cannot_change_earlier_fills_or_marks():
    initial = [bar(0), bar(1), bar(2), bar(3), bar(4)]
    changed = [*initial[:3], bar(3, "102"), bar(4, "102")]
    first = replay_candles((session(initial),), no_costs())
    second = replay_candles((session(changed),), no_costs())
    assert first.marks[:3] == second.marks[:3]
    assert first.fills[0] == second.fills[0]
    assert first.decisions == second.decisions
    assert first.input_sha256 != second.input_sha256


@pytest.mark.parametrize(
    "bad",
    [
        CandleSession("one", (bar(0), bar(2))),
        CandleSession("one", (bar(0), bar(1)), (1000,)),
        CandleSession("one", (bar(0), bar(1)), (999, 999)),
        CandleSession("one", (bar(0), bar(1)), (1999, 999)),
        CandleSession("one", (replace(bar(0), high=D("NaN")),)),
        CandleSession("one", (replace(bar(0), high=D("99")),)),
        CandleSession("one", (replace(bar(0), close_time_ms=-1),)),
        CandleSession("one", ()),
    ],
)
def test_invalid_candles_and_signals_fail_closed(bad):
    with pytest.raises(ValueError):
        replay_candles((bad,), no_costs())


@pytest.mark.parametrize(
    "sessions",
    [
        (),
        (session([bar(0), bar(1)]), session([bar(0), bar(1)], name="two")),
        (session([bar(0), bar(1)]), session([bar(2), bar(3)])),
    ],
)
def test_invalid_session_inventory_fails_closed(sessions):
    with pytest.raises(ValueError):
        replay_candles(sessions, no_costs())


@pytest.mark.parametrize(
    "updates",
    [
        {"holding_bars": 0},
        {"entry_delay_bars": -1},
        {"entry_delay_bars": True},
        {"quantity_step": D("NaN")},
        {"quantity_step": D("0")},
        {"barriers": TripleBarrierConfig(stop_loss_bps=D("20000"))},
    ],
)
def test_invalid_config_fails_closed(updates):
    with pytest.raises(ValueError):
        replay_candles((session([bar(0), bar(1)]),), replace(no_costs(), **updates))


def test_audit_report_contains_fills_marks_settings_and_refuses_overwrite(tmp_path):
    report = replay_candles((session([bar(0), bar(1)]),), no_costs())
    path = tmp_path / "reports" / "replay.json"
    write_replay_report(path, report)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["execution_mode"] == "paper"
    assert payload["fills"][0]["side"] == "BUY"
    assert payload["fills"][1]["side"] == "SELL"
    assert len(payload["marks"]) == 2
    assert payload["config"]["entry_delay_bars"] == 0
    assert D(payload["ending_balance"]) == report.ending_balance
    assert payload["input_sha256"] == report.input_sha256
    assert len(payload["input_sha256"]) == 64
    with pytest.raises(FileExistsError):
        write_replay_report(path, report)
