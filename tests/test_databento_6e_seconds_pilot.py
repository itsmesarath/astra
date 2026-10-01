"""Synthetic, archive-free checks of the bounded seconds quote pilot."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import databento_dbn as dbn
import pytest

from ai_trader.research import databento_6e_seconds_pilot as pilot

SESSION = "2025-03-31"
DAY = date.fromisoformat(SESSION)
BID = 1_000_000_000
ASK = BID + pilot.TICK


def ns(hour: int, minute: int, second: int, millis: int = 0) -> int:
    value = datetime(2025, 3, 31, hour, minute, second, tzinfo=UTC)
    return int(value.timestamp()) * pilot.SECOND_NS + millis * 1_000_000


def event(action, side, price, size, order_id, timestamp, *, flags=0, ts_event=None):
    return dbn.MBOMsg(
        publisher_id=1,
        instrument_id=42,
        ts_event=timestamp if ts_event is None else ts_event,
        order_id=order_id,
        price=price,
        size=size,
        action=dbn.Action.from_str(action),
        side=dbn.Side.from_str(side),
        ts_recv=timestamp,
        flags=flags,
    )


def seeded(*, trade_side="B", bid_qty=20, ask_qty=10) -> pilot.SecondsPilot:
    builder = pilot.SecondsPilot((SESSION,))
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 59, 59)
    builder.consume(event("R", "N", 0, 0, 0, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, bid_qty, 1, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, ask_qty, 2, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("T", trade_side, ASK, 2, 0, ns(11, 59, 59, 800), flags=dbn.F_LAST))
    return builder


def quote(builder: pilot.SecondsPilot, timestamp: int, *, bid=BID, ask=ASK) -> None:
    builder.consume(event("M", "B", bid, 20, 1, timestamp))
    builder.consume(event("M", "A", ask, 10, 2, timestamp, flags=dbn.F_LAST))


def trigger(builder: pilot.SecondsPilot, timestamp: int | None = None) -> dict:
    timestamp = ns(12, 0, 0, 100) if timestamp is None else timestamp
    builder.consume(event("T", "N", ASK, 1, 0, timestamp, flags=dbn.F_LAST))
    return builder.rows[0]


def test_grid_uses_only_completed_records_strictly_before_grid() -> None:
    builder = seeded()
    builder.consume(event("T", "A", BID, 20, 0, ns(12, 0, 0), flags=dbn.F_LAST))
    decision = builder.rows[0]
    assert decision["cvd_known_side_5s"] == 2
    assert decision["signal_direction"] == 1
    assert decision["decision_quote_ts_ns"] == ns(11, 59, 59, 800)
    assert decision["decision_quote_age_ns"] == 200_000_000
    assert decision["latency_variants"]["100"]["status"] == "entry_pending"
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 0, 100), flags=dbn.F_LAST))
    assert decision["latency_variants"]["100"]["entry_ts_ns"] == ns(12, 0, 0, 100)
    assert decision["cvd_known_side_5s"] == 2


def test_trade_spanning_grid_enters_flow_only_at_f_last_completion() -> None:
    builder = seeded(trade_side="N")
    builder.consume(event("T", "B", ASK, 3, 0, ns(11, 59, 59, 900)))
    assert len(builder.pending_trade_records) == 1
    builder.consume(event("F", "N", ASK, 3, 0, ns(12, 0, 0, 100), flags=dbn.F_LAST))
    first = builder.rows[0]
    assert first["known_side_trades_5s"] == 0
    assert first["cvd_known_side_5s"] == 0
    assert first["signal_direction"] == 0
    assert builder.flow.cvd == 3
    assert not builder.pending_trade_records
    assert builder.trade_counts[(SESSION, "known")] == 1
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 4, 900), flags=dbn.F_LAST))
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 5, 100), flags=dbn.F_LAST))
    second = builder.rows[1]
    assert second["cvd_known_side_5s"] == 3
    assert second["signal_direction"] == 1


def test_long_crossed_quote_latency_cost_and_missing_slow_entries() -> None:
    builder = seeded()
    decision = trigger(builder)
    assert decision["selected_counterfactual"]
    quote(builder, ns(12, 0, 15, 100), bid=BID + 2 * pilot.TICK, ask=ASK + 2 * pilot.TICK)
    primary = decision["latency_variants"]["100"]
    assert primary["status"] == "resolved"
    assert primary["gross_crossed_quote_ticks"] == 1
    assert primary["net_after_extra_cost_ticks"]["2"] == -1
    assert decision["latency_variants"]["500"]["status"] == "censored_entry_quote_timeout"
    assert decision["latency_variants"]["1000"]["status"] == "censored_entry_quote_timeout"
    summary = pilot._summary(builder.rows)
    assert summary["completed_primary_long"] == 1
    assert summary["latency_ms"]["100"]["median_gross_crossed_quote_ticks"] == 1
    assert summary["latency_ms"]["100"]["positive_gross_share"] == 1


def test_latency_variants_use_their_own_later_entry_and_exit_quotes() -> None:
    builder = seeded()
    decision = trigger(builder)
    quote(builder, ns(12, 0, 0, 500), bid=BID + pilot.TICK, ask=ASK + pilot.TICK)
    quote(builder, ns(12, 0, 1), bid=BID + 2 * pilot.TICK, ask=ASK + 2 * pilot.TICK)
    quote(builder, ns(12, 0, 15, 100), bid=BID + 3 * pilot.TICK, ask=ASK + 3 * pilot.TICK)
    quote(builder, ns(12, 0, 15, 500), bid=BID + 3 * pilot.TICK, ask=ASK + 3 * pilot.TICK)
    quote(builder, ns(12, 0, 16), bid=BID + 3 * pilot.TICK, ask=ASK + 3 * pilot.TICK)
    assert [decision["latency_variants"][str(ms)]["entry_ts_ns"] for ms in pilot.LATENCY_MS] == [
        ns(12, 0, 0, 100),
        ns(12, 0, 0, 500),
        ns(12, 0, 1),
    ]
    assert [
        decision["latency_variants"][str(ms)]["gross_crossed_quote_ticks"]
        for ms in pilot.LATENCY_MS
    ] == [2, 1, 0]


def test_short_crossed_quote_and_unknown_trade_not_inferred() -> None:
    unknown = seeded(trade_side="N")
    row = trigger(unknown)
    assert row["signal_direction"] == 0
    assert row["known_side_trades_5s"] == 0
    assert row["unknown_side_trades_5s"] == 1
    assert row["policy_reason"] == "no_known_side_trades_5s"

    short = seeded(trade_side="A", bid_qty=10, ask_qty=20)
    decision = trigger(short)
    assert decision["signal_direction"] == -1
    quote(short, ns(12, 0, 15, 100), bid=BID - 2 * pilot.TICK, ask=ASK - 2 * pilot.TICK)
    assert decision["latency_variants"]["100"]["gross_crossed_quote_ticks"] == 1
    assert pilot._summary(short.rows)["completed_primary_short"] == 1


def test_pending_position_cooldown_and_new_episode() -> None:
    builder = seeded()
    first = trigger(builder)
    builder.consume(event("T", "B", ASK, 2, 0, ns(12, 0, 4, 900), flags=dbn.F_LAST))
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 5, 100), flags=dbn.F_LAST))
    assert builder.rows[1]["policy_reason"] == "entry_or_position_pending"
    quote(builder, ns(12, 0, 15, 100), bid=BID + pilot.TICK, ask=ASK + pilot.TICK)
    assert first["latency_variants"]["100"]["status"] == "resolved"
    builder.consume(event("T", "B", ASK, 2, 0, ns(12, 0, 19, 900), flags=dbn.F_LAST))
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 20, 100), flags=dbn.F_LAST))
    assert builder.rows[4]["policy_reason"] == "cooldown"
    builder.consume(event("T", "B", ASK, 2, 0, ns(12, 0, 29, 900), flags=dbn.F_LAST))
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 30, 100), flags=dbn.F_LAST))
    assert builder.rows[6]["selected_counterfactual"]
    assert sum(row["selected_counterfactual"] for row in builder.rows) == 2


def test_continuous_signal_episode_cannot_reenter_after_cooldown() -> None:
    builder = seeded()
    trigger(builder)
    for second in (5, 10, 15):
        builder.consume(event("T", "B", ASK, 2, 0, ns(12, 0, second - 1, 900), flags=dbn.F_LAST))
        builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, second, 100), flags=dbn.F_LAST))
    quote(builder, ns(12, 0, 15, 200), bid=BID + pilot.TICK, ask=ASK + pilot.TICK)
    for second in (20, 25, 30):
        builder.consume(event("T", "B", ASK, 2, 0, ns(12, 0, second - 1, 900), flags=dbn.F_LAST))
        builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, second, 100), flags=dbn.F_LAST))
    assert builder.rows[6]["policy_reason"] == "same_episode"
    assert sum(row["selected_counterfactual"] for row in builder.rows) == 1


def test_fail_closed_on_quality_crossed_book_and_midwindow_snapshot() -> None:
    bad = seeded()
    with pytest.raises(ValueError, match="quality flag"):
        bad.consume(event("T", "B", ASK, 1, 0, ns(12, 0, 0, 100), flags=dbn.F_BAD_TS_RECV))

    crossed = seeded()
    with pytest.raises(ValueError, match="locked, or crossed"):
        crossed.consume(event("M", "B", ASK, 20, 1, ns(12, 0, 0, 100), flags=dbn.F_LAST))

    snapshot = seeded()
    before = dict(snapshot.book.orders)
    with pytest.raises(ValueError, match="Unexpected target snapshot"):
        snapshot.consume(event("R", "N", 0, 0, 0, ns(12, 0, 0, 100), flags=dbn.F_SNAPSHOT))
    assert snapshot.book.orders == before


def test_closed_period_clear_exception_does_not_relax_later_quality() -> None:
    builder = seeded()
    closed = ns(21, 30, 0)
    builder.consume(event("R", "N", 0, 0, 0, closed, flags=dbn.F_BAD_TS_RECV))
    assert builder.counts["accepted_closed_period_bad_ts_clears"] == 1
    assert not builder.book.orders
    with pytest.raises(ValueError, match="quality flag"):
        builder.consume(
            event("T", "B", ASK, 1, 0, closed + pilot.SECOND_NS, flags=dbn.F_BAD_TS_RECV)
        )


def test_incomplete_trade_before_clear_snapshot_or_member_end_fails() -> None:
    clear = seeded()
    clear.consume(event("T", "B", ASK, 1, 0, ns(12, 0, 0, 100)))
    with pytest.raises(ValueError, match="Incomplete target event before"):
        clear.consume(event("R", "N", 0, 0, 0, ns(21, 30, 0), flags=dbn.F_BAD_TS_RECV))

    snapshot = seeded()
    snapshot.consume(event("T", "B", ASK, 1, 0, ns(12, 0, 0, 100)))
    with pytest.raises(ValueError, match="Incomplete target event before"):
        snapshot.consume(event("A", "B", BID, 1, 3, ns(16, 30, 0), flags=dbn.F_SNAPSHOT))

    member_end = seeded()
    member_end.consume(event("T", "B", ASK, 1, 0, ns(12, 0, 0, 100)))
    with pytest.raises(ValueError, match="Incomplete target trade event at UTC member end"):
        member_end.finish_day()


def test_window_end_censors_and_no_late_decision() -> None:
    builder = seeded()
    first = trigger(builder)
    builder._end_window()
    assert len(builder.rows) == pilot.GRIDS_PER_DAY
    assert first["latency_variants"]["100"]["status"] == "censored_window_end"
    assert builder.rows[-1]["grid_ts_ns"] == ns(15, 59, 55)
    assert builder.rows[-1]["selected_counterfactual"] is False


def test_per_session_fresh_quote_coverage_gate_fails_closed() -> None:
    builder = seeded()
    trigger(builder)
    with pytest.raises(ValueError, match="quote coverage below frozen"):
        builder.finish_day()
    assert len(builder.rows) == pilot.GRIDS_PER_DAY
    assert pilot._summary(builder.rows)["fresh_quote_grid_fraction"] < 0.95


def test_v2_quality_gate_accepts_observed_coverage_without_signal_minimum() -> None:
    def synthetic_day(minimum: int, fresh: int) -> pilot.SecondsPilot:
        builder = pilot.SecondsPilot((SESSION,), minimum_fresh_grids_per_day=minimum)
        builder.start_day(DAY)
        builder.metadata_seen = True
        builder.day_target_records = 1
        builder.window_closed = True
        builder.rows = [
            {"source_session": SESSION, "decision_quote_age_ns": 1 if i < fresh else None}
            for i in range(pilot.GRIDS_PER_DAY)
        ]
        return builder

    observed = 2293
    with pytest.raises(ValueError, match="required=2736"):
        synthetic_day(pilot.MIN_FRESH_GRIDS_PER_DAY, observed).finish_day()
    synthetic_day(pilot.MIN_FRESH_GRIDS_PER_DAY_V2, observed).finish_day()
    synthetic_day(pilot.MIN_FRESH_GRIDS_PER_DAY_V2, 2016).finish_day()
    with pytest.raises(ValueError, match="required=2016"):
        synthetic_day(pilot.MIN_FRESH_GRIDS_PER_DAY_V2, 2015).finish_day()


def test_config_pinned_and_unsafe_source_rejected_without_archive_open(
    tmp_path, monkeypatch
) -> None:
    config_path = Path(__file__).resolve().parents[1] / "configs/databento_6e_seconds_pilot_v1.json"
    config, digest = pilot.load_config(config_path)
    assert digest == pilot.CONFIG_SHA256
    assert config["source_sessions"] == list(pilot.SESSIONS)

    def wrong_sources(_config, _project_root):
        return {}, [{"day": date(2025, 4, 3)}], "unused"

    monkeypatch.setattr(pilot, "selected_sources", wrong_sources)
    with pytest.raises(ValueError, match="Unexpected UTC source days"):
        pilot.run_pilot(
            project_root=tmp_path,
            config_path=config_path,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert not list(tmp_path.iterdir())


def test_v1_v2_pins_and_separate_output_paths(tmp_path, monkeypatch) -> None:
    configs = Path(__file__).resolve().parents[1] / "configs"
    v1, v1_sha = pilot.load_config(configs / "databento_6e_seconds_pilot_v1.json")
    v2, v2_sha = pilot.load_config(configs / "databento_6e_seconds_pilot_v2.json")
    assert v1_sha == pilot.CONFIG_SHA256
    assert v2_sha == pilot.CONFIG_V2_SHA256
    assert v1_sha != v2_sha
    assert pilot.PROFILES[v1_sha]["minimum_grids"] == 2736
    assert pilot.PROFILES[v2_sha]["minimum_grids"] == 2016
    shared_fields = set(v1) - {
        "artifact_type",
        "experiment_id",
        "minimum_fresh_quote_grid_fraction_per_session",
    }
    assert all(v1[key] == v2[key] for key in shared_fields)
    assert set(v2) - set(v1) == {"revision_basis"}

    def wrong_sources(_config, _project_root):
        return {}, [{"day": date(2025, 4, 3)}], "unused"

    monkeypatch.setattr(pilot, "selected_sources", wrong_sources)
    with pytest.raises(ValueError, match="require separate v2-named paths"):
        pilot.run_pilot(
            project_root=tmp_path,
            config_path=configs / "databento_6e_seconds_pilot_v2.json",
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    with pytest.raises(ValueError, match="Unexpected UTC source days"):
        pilot.run_pilot(
            project_root=tmp_path,
            config_path=configs / "databento_6e_seconds_pilot_v2.json",
            rows_output=tmp_path / "seconds_pilot_v2_rows.jsonl",
            summary_output=tmp_path / "seconds_pilot_v2_summary.json",
        )
    assert not list(tmp_path.iterdir())
