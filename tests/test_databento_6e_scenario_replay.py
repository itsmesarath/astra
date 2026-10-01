"""Synthetic scenario-registry checks; no historical archive is opened."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import databento_dbn as dbn
import pytest

from ai_trader.research import databento_6e_scenario_replay as replay

SESSION = "2025-03-31"
DAY = date.fromisoformat(SESSION)
CONTRACT = "6EM5"
BID = 1_000_000_000
ASK = BID + 2 * replay.TICK


def ns(hour: int, minute: int, second: int = 1) -> int:
    stamp = datetime(2025, 3, 31, hour, minute, second, tzinfo=UTC)
    return int(stamp.timestamp()) * replay.SECOND_NS


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


def seeded_builder(*, skip_warmup_minute=None) -> replay.ScenarioBuilder:
    builder = replay.ScenarioBuilder((SESSION,), CONTRACT)
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 29)
    builder.consume(event("R", "N", 0, 0, 0, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, 10, 1, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, at, flags=dbn.F_SNAPSHOT))
    for minute in range(30, 60):
        if minute == skip_warmup_minute:
            continue
        builder.consume(event("T", "B", ASK, 1, 0, ns(11, minute), flags=dbn.F_LAST))
    return builder


def move_quote(builder, timestamp, bid, ask):
    builder.consume(event("M", "B", bid, 10, 1, timestamp))
    builder.consume(event("M", "A", ask, 10, 2, timestamp, flags=dbn.F_LAST))


def test_prior_range_excludes_current_and_future_quote() -> None:
    builder = seeded_builder()
    builder.consume(event("T", "N", ASK, 2, 0, ns(12, 0), flags=dbn.F_LAST))
    first = builder.rows[-1]
    assert first["prior_30m_observations"] == 30
    assert first["prior_30m_high_mid_twice_nano"] == BID + ASK
    assert first["candidate"] == "no_trade"
    assert first["cvd_5m_known_side"] == 5
    assert first["unknown_side_trades_5m"] == 1

    before = len(builder.rows)
    builder.consume(event("M", "B", BID + replay.TICK, 10, 1, ns(12, 1)))
    assert len(builder.rows) == before  # Incomplete event batch cannot become a decision.
    builder.consume(event("M", "A", ASK + replay.TICK, 10, 2, ns(12, 1), flags=dbn.F_LAST))
    breakout = builder.rows[-1]
    assert breakout["candidate"] == "initial_break_up"
    assert breakout["candidate_direction"] == 1
    assert breakout["prior_30m_high_mid_twice_nano"] == BID + ASK
    assert breakout["decision_bid_nano"] == BID + replay.TICK
    assert breakout["decision_ask_nano"] == ASK + replay.TICK
    frozen_signal = (
        breakout["candidate"],
        breakout["prior_30m_high_mid_twice_nano"],
        breakout["cvd_5m_known_side"],
    )

    move_quote(builder, ns(12, 2), BID + 3 * replay.TICK, ASK + 3 * replay.TICK)
    assert breakout["outcome_status"] == "resolved"
    assert breakout["signed_mid_move_ticks"] == 2
    assert breakout["gross_crossed_quote_ticks"] == 0
    assert frozen_signal == (
        breakout["candidate"],
        breakout["prior_30m_high_mid_twice_nano"],
        breakout["cvd_5m_known_side"],
    )


def test_reentry_uses_frozen_breakout_boundary_and_short_crossed_quote() -> None:
    builder = seeded_builder()
    move_quote(builder, ns(12, 0), BID + replay.TICK, ASK + replay.TICK)
    assert builder.rows[-1]["candidate"] == "initial_break_up"
    move_quote(builder, ns(12, 1), BID, ASK)
    failed = builder.rows[-1]
    assert failed["candidate"] == "failed_up_breakout"
    assert failed["candidate_direction"] == -1
    assert failed["frozen_breakout_boundary_mid_twice_nano"] == BID + ASK
    assert failed["breakout_age_minutes"] == 1
    move_quote(builder, ns(12, 2), BID - replay.TICK, ASK - replay.TICK)
    assert failed["outcome_status"] == "resolved"
    assert failed["signed_mid_move_ticks"] == 1
    # Selling at the decision bid and buying at the future ask still loses one tick.
    assert failed["gross_crossed_quote_ticks"] == -1


def test_live_clear_inside_observation_window_fails_entire_audit() -> None:
    builder = seeded_builder()
    builder.consume(event("T", "B", ASK, 3, 0, ns(12, 0), flags=dbn.F_LAST))
    with pytest.raises(ValueError, match="Unexpected live book clear"):
        builder.consume(event("R", "N", 0, 0, 0, ns(12, 0, 30)))


def test_clear_outside_observation_window_resets_causal_state() -> None:
    builder = replay.ScenarioBuilder((SESSION,), CONTRACT)
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 0)
    builder.consume(event("R", "N", 0, 0, 0, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, 10, 1, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("T", "B", ASK, 3, 0, ns(11, 1), flags=dbn.F_LAST))
    assert builder.flow.cvd == 3
    builder.consume(event("R", "N", 0, 0, 0, ns(11, 29)))
    assert builder.flow.cvd == 0
    assert not builder.history
    builder.consume(event("A", "B", BID, 10, 1, ns(11, 29, 30), flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, ns(11, 29, 30), flags=dbn.F_SNAPSHOT))
    builder.consume(event("T", "N", ASK, 2, 0, ns(12, 0), flags=dbn.F_LAST))
    fresh = builder.rows[-1]
    assert fresh["candidate"] == "no_trade"
    assert fresh["no_trade_reason"] == "insufficient_prior_minutes"
    assert fresh["prior_30m_observations"] == 0
    assert fresh["cvd_5m_known_side"] == 0
    assert fresh["unknown_side_trades_5m"] == 1


def test_five_minute_failed_break_boundary_is_inclusive() -> None:
    within = seeded_builder()
    move_quote(within, ns(12, 0), BID + replay.TICK, ASK + replay.TICK)
    for minute in range(1, 5):
        within.consume(event("T", "N", ASK + replay.TICK, 1, 0, ns(12, minute), flags=dbn.F_LAST))
    move_quote(within, ns(12, 5), BID, ASK)
    assert within.rows[-1]["candidate"] == "failed_up_breakout"
    assert within.rows[-1]["breakout_age_minutes"] == 5
    assert within.rows[-1]["frozen_breakout_boundary_mid_twice_nano"] == BID + ASK

    expired = seeded_builder()
    move_quote(expired, ns(12, 0), BID + replay.TICK, ASK + replay.TICK)
    for minute in range(1, 6):
        expired.consume(event("T", "N", ASK + replay.TICK, 1, 0, ns(12, minute), flags=dbn.F_LAST))
    move_quote(expired, ns(12, 6), BID, ASK)
    assert expired.rows[-1]["candidate"] != "failed_up_breakout"
    assert expired.rows[-1]["breakout_age_minutes"] is None


def test_unknown_modify_and_quality_flags_fail_closed() -> None:
    builder = seeded_builder()
    with pytest.raises(ValueError, match="Unknown target order modify"):
        builder.consume(event("M", "B", BID, 10, 999, ns(12, 0), flags=dbn.F_LAST))
    builder = seeded_builder()
    with pytest.raises(ValueError, match="quality flag"):
        builder.consume(event("T", "B", ASK, 1, 0, ns(12, 0), flags=dbn.F_LAST | dbn.F_BAD_TS_RECV))
    builder = seeded_builder()
    with pytest.raises(ValueError, match="Incomplete, locked, or crossed"):
        builder.consume(event("M", "B", ASK, 10, 1, ns(12, 0), flags=dbn.F_LAST))


def test_exact_closed_period_bad_timestamp_clear_exception() -> None:
    sunday = date(2025, 3, 30)
    builder = replay.ScenarioBuilder((SESSION,), CONTRACT)
    builder.start_day(sunday)
    builder.metadata_seen = True
    builder.instrument_id = 42
    closed = int(datetime(2025, 3, 30, 11, 7, 48, tzinfo=UTC).timestamp()) * replay.SECOND_NS
    builder.consume(event("R", "N", 0, 0, 0, closed, flags=dbn.F_BAD_TS_RECV))
    assert builder.counts["accepted_closed_period_bad_ts_clears"] == 1
    assert not builder.rows
    later = closed + int(timedelta(seconds=1).total_seconds()) * replay.SECOND_NS
    with pytest.raises(ValueError, match="quality flag"):
        builder.consume(event("T", "B", ASK, 1, 0, later, flags=dbn.F_BAD_TS_RECV))


def test_snapshot_bad_receive_time_is_allowed_but_completed_book_is_checked() -> None:
    builder = replay.ScenarioBuilder((SESSION,), CONTRACT)
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    flagged_snapshot = dbn.F_SNAPSHOT | dbn.F_BAD_TS_RECV
    builder.consume(event("R", "N", 0, 0, 0, ns(11, 30), flags=flagged_snapshot))
    builder.consume(event("A", "B", BID, 10, 1, ns(11, 30), flags=flagged_snapshot))
    builder.consume(event("A", "A", ASK, 10, 2, ns(11, 30), flags=flagged_snapshot | dbn.F_LAST))
    assert builder.counts["snapshot_records"] == 2
    assert not builder.rows

    incomplete = replay.ScenarioBuilder((SESSION,), CONTRACT)
    incomplete.start_day(DAY)
    incomplete.metadata_seen = True
    incomplete.instrument_id = 42
    incomplete.consume(event("R", "N", 0, 0, 0, ns(11, 30), flags=flagged_snapshot))
    with pytest.raises(ValueError, match="Incomplete, locked, or crossed"):
        incomplete.consume(
            event("A", "B", BID, 10, 1, ns(11, 30), flags=flagged_snapshot | dbn.F_LAST)
        )


def test_only_original_train_and_validation_source_days_are_selected(tmp_path, monkeypatch) -> None:
    config = (
        Path(__file__).resolve().parents[1] / "configs/databento_6e_first_training_20261001.json"
    )
    captured = {}

    def no_archives(restricted, project_root):
        captured["sessions"] = restricted["source_sessions"]
        captured["test"] = restricted["test_sessions"]
        raise RuntimeError("No raw archive access in this test")

    monkeypatch.setattr(replay, "selected_sources", no_archives)
    with pytest.raises(RuntimeError, match="No raw archive access"):
        replay.replay_scenarios(
            project_root=tmp_path,
            config_path=config,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert len(captured["sessions"]) == 10
    assert captured["sessions"][0] == "2025-03-27"
    assert captured["sessions"][-1] == "2025-04-09"
    assert not set(captured["sessions"]) & set(captured["test"])
    assert not list(tmp_path.iterdir())


def test_selected_source_day_cannot_reach_april_10(tmp_path, monkeypatch) -> None:
    config = (
        Path(__file__).resolve().parents[1] / "configs/databento_6e_first_training_20261001.json"
    )

    def unsafe_source(_restricted, _project_root):
        return {}, [{"day": date(2025, 4, 10)}], "unused"

    monkeypatch.setattr(replay, "selected_sources", unsafe_source)
    with pytest.raises(ValueError, match="source day reaches beyond"):
        replay.replay_scenarios(
            project_root=tmp_path,
            config_path=config,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert not list(tmp_path.iterdir())


def test_every_session_needs_all_warmup_and_decision_minutes() -> None:
    complete = seeded_builder()
    for hour in range(12, 16):
        for minute in range(60):
            complete.consume(event("T", "N", ASK, 1, 0, ns(hour, minute), flags=dbn.F_LAST))
    complete.finish_day()
    rows, quality = complete.finish()
    assert len(rows) == 240
    assert quality["warmup_minutes_per_session"][SESSION] == 30

    missing_decision = seeded_builder()
    for hour in range(12, 16):
        for minute in range(60):
            if hour == 15 and minute == 59:
                continue
            missing_decision.consume(event("T", "N", ASK, 1, 0, ns(hour, minute), flags=dbn.F_LAST))
    missing_decision.finish_day()
    with pytest.raises(ValueError, match="exactly 240 decision"):
        missing_decision.finish()

    missing_warmup = seeded_builder(skip_warmup_minute=45)
    for hour in range(12, 16):
        for minute in range(60):
            missing_warmup.consume(event("T", "N", ASK, 1, 0, ns(hour, minute), flags=dbn.F_LAST))
    missing_warmup.finish_day()
    with pytest.raises(ValueError, match="all 30 warmup"):
        missing_warmup.finish()


def test_failed_summary_publication_cleans_only_new_files(tmp_path, monkeypatch) -> None:
    rows = tmp_path / "rows.jsonl"
    summary = tmp_path / "summary.json"

    def fail_dump(*_args, **_kwargs):
        raise RuntimeError("summary write failed")

    monkeypatch.setattr(replay.json, "dump", fail_dump)
    with pytest.raises(RuntimeError, match="summary write failed"):
        replay._publish(rows, summary, b"{}\n", {"test": True})
    assert not rows.exists()
    assert not summary.exists()
