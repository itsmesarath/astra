"""Causal event decisions and explicit clock/risk accounting without real archives."""

from copy import deepcopy
from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZipFile

import databento_dbn as dbn
import pytest

from ai_trader.research import databento_6e_event_scalp as study

clock = study.clock
SESSION = "2025-07-07"
DAY = date.fromisoformat(SESSION)
BID = 1_000_000_000
ASK = BID + clock.TICK
CONFIG = Path(__file__).resolve().parents[1] / "configs/databento_6e_event_scalp_v1.json"


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


def update(builder, timestamp, *, bq=70, aq=10, bid=BID, ask=ASK):
    builder.consume(event("M", "B", bid, bq, 1, timestamp))
    builder.consume(event("M", "A", ask, aq, 2, timestamp, dbn.F_LAST))


def seeded(strategy="ofi_queue"):
    builder = study.EventScalp(strategy, (SESSION,))
    builder.start_day(DAY)
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 59, 50)
    builder.consume(event("R", "N", 0, 0, 0, at, dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, 10, 1, at, dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, at, dbn.F_SNAPSHOT))
    update(builder, at, bq=10)
    update(builder, ns(11, 59, 55), bq=10)
    update(builder, ns(11, 59, 59, 800))
    return builder


def trigger(builder):
    update(builder, ns(12, 0, 0))
    return builder.rows[0]


def test_no_grid_decisions_and_current_completed_event_is_causal():
    builder = seeded()
    assert not builder.rows
    builder.consume(event("M", "B", BID, 1, 1, ns(12, 0, 0)))
    assert not builder.rows  # unfinished event cannot trigger even at a clock boundary
    builder.consume(event("M", "A", ASK, 70, 2, ns(12, 0, 0, 100), dbn.F_LAST))
    row = builder.rows[0]
    assert row["decision_ts_ns"] == ns(12, 0, 0, 100)
    assert row["decision_quote_age_ns"] == 0
    assert row["top_bid_qty"] == 1 and row["top_ask_qty"] == 70
    assert row["signal_direction"] == -1
    assert row["latency_variants"]["100"]["entry_target_ts_ns"] == ns(12, 0, 0, 200)
    assert row["latency_variants"]["100"]["entry_ts_ns"] is None
    update(builder, ns(12, 0, 0, 100), bq=70, aq=10)
    assert len(builder.rows) == 1 and row["top_bid_qty"] == 1


def test_decision_rate_is_elapsed_time_not_second_bucket():
    builder = seeded()
    update(builder, ns(12, 0, 0, 900))
    update(builder, ns(12, 0, 1))
    update(builder, ns(12, 0, 1, 899))
    assert len(builder.rows) == 1
    update(builder, ns(12, 0, 1, 900))
    assert len(builder.rows) == 2
    assert builder.rows[1]["decision_ts_ns"] - builder.rows[0]["decision_ts_ns"] == clock.SECOND_NS


def test_entry_latency_and_short_crossed_price_with_distinct_sensitivity_quotes():
    builder = seeded()
    update(builder, ns(11, 59, 59, 900), bq=10, aq=70)
    builder.consume(event("T", "N", ASK, 1, 0, ns(12, 0, 0), dbn.F_LAST))
    row = builder.rows[0]
    assert row["signal_direction"] == -1
    for millis, ticks in ((99, 0), (100, 0), (500, -1), (1000, -2)):
        update(
            builder,
            ns(12, 0, 0, millis),
            bid=BID + ticks * clock.TICK,
            ask=ASK + ticks * clock.TICK,
        )
        if millis == 99:
            assert row["latency_variants"]["100"]["entry_ts_ns"] is None
    for sec in (5, 9, 13):
        update(builder, ns(12, 0, sec))
    for sec, millis in ((15, 100), (15, 500), (16, 0)):
        update(builder, ns(12, 0, sec, millis), bid=BID - 3 * clock.TICK, ask=ASK - 3 * clock.TICK)
    assert [
        row["latency_variants"][str(m)]["gross_crossed_quote_ticks"] for m in clock.LATENCY_MS
    ] == [2, 1, 0]
    assert not any(v["inactivity_exposed"] for v in row["latency_variants"].values())


def test_entry_expiry_fires_without_complete_quote_and_cooldown_uses_deadline():
    builder = seeded()
    row = trigger(builder)
    builder.consume(event("M", "B", BID, 70, 1, ns(12, 0, 1, 100)))
    assert row["latency_variants"]["100"]["status"] == "entry_pending"
    deadline_plus_one = ns(12, 0, 1, 100) + 1
    builder.consume(event("M", "B", BID, 70, 1, deadline_plus_one))
    primary = row["latency_variants"]["100"]
    assert primary["status"] == "no_entry_quote_timeout"
    assert primary["entry_expiry_ts_ns"] == deadline_plus_one
    assert builder.cooldown_until_ns == deadline_plus_one + clock.COOLDOWN_NS
    assert builder.active_row is None
    assert len(builder.rows) == 1
    update(builder, ns(12, 0, 3))
    assert all(v["entry_ts_ns"] is None for v in row["latency_variants"].values())
    assert builder.cooldown_until_ns == deadline_plus_one + clock.COOLDOWN_NS


def test_gap_reset_requires_five_seconds_new_observation():
    builder = seeded()
    trigger(builder)
    update(builder, ns(12, 0, 6))
    assert builder.rows[-1]["policy_reason"] == "insufficient_ofi_warmup"
    assert builder.ofi.total == 0
    assert builder.inactivity_intervals[-1]["timer_fired_ns"] == ns(12, 0, 5) + 1
    update(builder, ns(12, 0, 10), bq=10)
    update(builder, ns(12, 0, 11))
    assert builder.rows[-1]["normalized_ofi_5s"] == 0
    assert builder.rows[-1]["policy_reason"] != "insufficient_ofi_warmup"


def test_exact_five_second_gap_does_not_reset():
    builder = seeded()
    trigger(builder)
    update(builder, ns(12, 0, 5))
    assert builder.ofi.first_ts == ns(11, 59, 50)
    assert not builder.inactivity_intervals


def test_open_position_survives_gap_and_late_widened_exit_is_not_discarded():
    builder = seeded()
    row = trigger(builder)
    update(builder, ns(12, 0, 0, 100))
    update(builder, ns(12, 0, 18), bid=BID - 2 * clock.TICK, ask=ASK)
    primary = row["latency_variants"]["100"]
    assert primary["status"] == "resolved"
    assert primary["inactivity_exposed"] and primary["late_exit"]
    assert primary["first_inactivity_ts_ns"] == ns(12, 0, 5, 100) + 1
    assert primary["gross_crossed_quote_ticks"] == -3
    assert primary["net_after_extra_cost_ticks"]["1"] == -4
    assert builder.cooldown_until_ns == ns(12, 0, 28)
    stats = study.summarize(builder.rows)
    assert "grid_rows" not in stats and "fresh_quotes" not in stats
    assert stats["latency_ms"]["100"]["inactivity_exposed_entered"] == 1
    assert stats["latency_ms"]["100"]["mean_hold_seconds"] == pytest.approx(17.9)


def test_window_end_marks_tail_gap_and_unresolved_without_fabricating_rows():
    builder = seeded()
    row = trigger(builder)
    update(builder, ns(12, 0, 0, 100))
    builder.finish_day()
    assert len(builder.rows) == 1
    assert row["latency_variants"]["100"]["status"] == "unresolved_exit_window_end"
    assert row["latency_variants"]["100"]["inactivity_exposed"]
    gap = builder.inactivity_intervals[-1]
    assert not gap["recovered_with_completed_quote"]
    assert gap["end_ts_ns"] == ns(16, 0, 0)
    rows, quality = builder.finish()
    assert len(rows) == quality["by_session"][0]["decision_events"] == 1


def test_incomplete_nontrade_event_fails_at_end_or_reset():
    for finish in (True, False):
        builder = seeded()
        builder.consume(event("M", "B", BID, 20, 1, ns(12, 0, 0)))
        with pytest.raises(ValueError, match="Incomplete target event"):
            if finish:
                builder.finish_day()
            else:
                builder.consume(event("R", "N", 0, 0, 0, ns(16, 30, 0), dbn.F_SNAPSHOT))


@pytest.mark.parametrize("flags", [dbn.F_BAD_TS_RECV, dbn.F_MAYBE_BAD_BOOK, dbn.F_TOB, dbn.F_MBP])
def test_inherited_quality_flags_remain_fail_closed(flags):
    builder = seeded()
    with pytest.raises(ValueError, match="quality flag"):
        builder.consume(event("M", "B", BID, 20, 1, ns(12, 0, 0), flags))


def test_midwindow_snapshot_and_missing_event_session_rejected():
    builder = seeded()
    with pytest.raises(ValueError, match="Unexpected target snapshot"):
        builder.consume(event("R", "N", 0, 0, 0, ns(12, 0, 0), dbn.F_SNAPSHOT))
    with pytest.raises(ValueError, match="Missing or excessive"):
        builder.finish_day()


def test_no_cross_session_feature_or_position_reuse():
    builder = seeded()
    trigger(builder)
    builder.finish_day()
    builder.start_day(date(2025, 7, 8))
    assert builder.ofi.first_ts is None and builder.active_row is None
    assert builder.next_decision_ns == builder.window_start_ns
    assert builder.cooldown_until_ns == 0 and not builder.incomplete_event


def test_no_signal_inside_last_seventeen_seconds():
    builder = seeded()
    update(builder, ns(15, 59, 37), bq=10)
    update(builder, ns(15, 59, 41), bq=10)
    update(builder, ns(15, 59, 43))
    assert builder.rows[-1]["signal_direction"] == 1
    assert builder.rows[-1]["policy_reason"] == "insufficient_window_for_hold"


def test_active_position_cooldown_and_episode_reentry_are_independent_gates():
    builder = seeded("queue_only")
    first = trigger(builder)
    update(builder, ns(12, 0, 0, 100))
    for second in range(1, 27):
        update(builder, ns(12, 0, second))
        if second == 1:
            assert builder.rows[-1]["policy_reason"] == "entry_or_position_pending"
        if second == 17:
            assert builder.rows[-1]["policy_reason"] == "cooldown"
    assert first["latency_variants"]["100"]["status"] == "resolved"
    assert builder.rows[-1]["policy_reason"] == "same_episode"
    update(builder, ns(12, 0, 27), bq=10, aq=10)
    update(builder, ns(12, 0, 28))
    assert builder.rows[-1]["selected_counterfactual"]
    assert sum(r["selected_counterfactual"] for r in builder.rows) == 2


def test_event_at_window_end_cannot_close_or_create_a_trade():
    builder = seeded()
    first = trigger(builder)
    update(builder, ns(12, 0, 0, 100))
    update(builder, ns(16, 0, 0))
    assert len(builder.rows) == 1
    assert first["latency_variants"]["100"]["status"] == "unresolved_exit_window_end"
    assert first["latency_variants"]["100"]["exit_ts_ns"] is None


def positive_stats():
    primary = {
        "closed": 120,
        "unresolved_entered": 0,
        "inactivity_exposed_entered": 0,
        "net_ticks_by_extra_cost": {"1": {"mean_closed": 1}},
    }
    strategies = {"ofi_queue": {"latency_ms": {"100": primary}}}
    days = [{"source_session": s, "strategies": deepcopy(strategies)} for s in study.EVALUATION]
    return strategies, days


def test_evaluation_requires_positive_cost_adjusted_result_on_every_day():
    stats, days = positive_stats()
    assert (
        study.evaluate(stats, days)["decision"]
        == "requires_independent_replication_and_broker_execution"
    )
    days[0]["strategies"]["ofi_queue"]["latency_ms"]["100"]["net_ticks_by_extra_cost"]["1"][
        "mean_closed"
    ] = -1
    result = study.evaluate(stats, days)
    assert result["decision"] == "reject_for_promotion"
    assert result["promotion_enabled"] is False


@pytest.mark.parametrize(
    "field,expected",
    [
        ("unresolved_entered", "inconclusive_unresolved_positions"),
        ("inactivity_exposed_entered", "inconclusive_quality_or_sample"),
    ],
)
def test_control_sensitivity_risk_blocks_positive_conclusion(field, expected):
    stats, days = positive_stats()
    stats["queue_only"] = {
        "latency_ms": {"1000": {"unresolved_entered": 0, "inactivity_exposed_entered": 0}}
    }
    stats["queue_only"]["latency_ms"]["1000"][field] = 1
    assert study.evaluate(stats, days)["decision"] == expected


def test_small_sample_and_missing_evaluation_day_block_conclusion():
    stats, days = positive_stats()
    stats["ofi_queue"]["latency_ms"]["100"]["closed"] = 99
    assert "insufficient_evaluation_sample" in study.evaluate(stats, days)["blockers"]
    stats, days = positive_stats()
    assert "insufficient_evaluation_sample" in study.evaluate(stats, days[1:])["blockers"]


def test_development_outcomes_do_not_change_evaluation_decision():
    stats, days = positive_stats()
    development = deepcopy(days[0])
    development["source_session"] = study.DEVELOPMENT[0]
    development["strategies"]["ofi_queue"]["latency_ms"]["100"]["net_ticks_by_extra_cost"]["1"][
        "mean_closed"
    ] = -999
    assert study.evaluate(stats, days) == study.evaluate(stats, [development, *days])


def test_config_pin_cohort_and_mutation_refusal(tmp_path):
    config, pin = study.load_config(CONFIG)
    assert pin == study.CONFIG_SHA256
    assert config["development_sessions"] + config["evaluation_sessions"] == list(study.SESSIONS)
    assert not set(config["development_sessions"]) & set(config["evaluation_sessions"])
    assert config["minimum_decision_interval_ms"] * 1_000_000 == study.DECISION_INTERVAL_NS
    assert config["trading_enabled"] is config["training_enabled"] is False
    altered = tmp_path / "changed.json"
    altered.write_bytes(CONFIG.read_bytes() + b" ")
    with pytest.raises(ValueError, match="configuration changed"):
        study.load_config(altered)


def test_wrong_source_days_fail_before_archives_are_opened(tmp_path, monkeypatch):
    monkeypatch.setattr(study, "selected_sources", lambda *_: ({}, [{"day": DAY}], "unused"))
    with pytest.raises(ValueError, match="Unexpected source day"):
        study.run_experiment(
            project_root=tmp_path,
            config_path=CONFIG,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert not list(tmp_path.iterdir())


def test_source_integrity_failure_publishes_nothing(tmp_path, monkeypatch):
    archive_path = tmp_path / "synthetic.zip"
    with ZipFile(archive_path, "x") as archive:
        archive.writestr("metadata-only", b"")
    sources = [
        {"day": date.fromisoformat(day), "archive": archive_path}
        for day in ("2025-07-06", *study.SESSIONS)
    ]
    monkeypatch.setattr(study, "selected_sources", lambda *_: ({}, sources, "unused"))

    def corrupt(*_):
        raise ValueError("Compressed member SHA256 mismatch")

    monkeypatch.setattr(study, "_member_records", corrupt)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        study.run_experiment(
            project_root=tmp_path,
            config_path=CONFIG,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert list(tmp_path.iterdir()) == [archive_path]


def test_output_paths_are_exclusive(tmp_path):
    output = tmp_path / "keep.json"
    output.write_text("keep")
    for rows, summary in ((output, tmp_path / "new.json"), (tmp_path / "same", tmp_path / "same")):
        with pytest.raises(ValueError, match="overwrite"):
            study.run_experiment(
                project_root=tmp_path, config_path=CONFIG, rows_output=rows, summary_output=summary
            )
    assert output.read_text() == "keep" and len(list(tmp_path.iterdir())) == 1
