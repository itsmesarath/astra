"""Archive-free checks for the frozen OFI/queue experiment."""

from datetime import UTC, date, datetime
from pathlib import Path
from zipfile import ZipFile

import databento_dbn as dbn
import pytest

from ai_trader.research import databento_6e_ofi_scalp as study

clock = study.clock
SESSION = "2025-07-07"
BID = 1_000_000_000
ASK = BID + clock.TICK
CONFIG = Path(__file__).resolve().parents[1] / "configs/databento_6e_ofi_scalp_v1.json"


def ns(hour, minute, second, millis=0):
    return (
        int(datetime(2025, 7, 7, hour, minute, second, tzinfo=UTC).timestamp()) * clock.SECOND_NS
        + millis * 1_000_000
    )


def event(action, side, price, size, order_id, timestamp, *, flags=0):
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


def update(builder, timestamp, *, bid_qty=70, ask_qty=10, bid=BID, ask=ASK):
    builder.consume(event("M", "B", bid, bid_qty, 1, timestamp))
    builder.consume(event("M", "A", ask, ask_qty, 2, timestamp, flags=dbn.F_LAST))


def seeded(strategy="ofi_queue"):
    builder = study.OfiScalp(strategy, (SESSION,))
    builder.start_day(date.fromisoformat(SESSION))
    builder.metadata_seen = True
    builder.instrument_id = 42
    at = ns(11, 59, 50)
    builder.consume(event("R", "N", 0, 0, 0, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "B", BID, 10, 1, at, flags=dbn.F_SNAPSHOT))
    builder.consume(event("A", "A", ASK, 10, 2, at, flags=dbn.F_SNAPSHOT))
    update(builder, at, bid_qty=10)
    update(builder, ns(11, 59, 59, 800))
    return builder


def trigger(builder):
    update(builder, ns(12, 0, 0, 100))
    return builder.rows[0]


@pytest.mark.parametrize(
    "bid_step,ask_step,bq,aq,expected",
    [
        (0, 0, 25, 7, 8),  # bid adds +5, ask cancels +3
        (0, 0, 15, 13, -8),
        (1, 1, 25, 7, 35),  # new better bid +25, old ask removed +10
        (-1, -1, 25, 7, -27),  # old bid removed -20, new better ask -7
        (0, 0, 20, 10, 0),
    ],
)
def test_ofi_price_and_size_change_indicators(bid_step, ask_step, bq, aq, expected):
    previous = clock.Quote(1, BID, ASK, 20, 10)
    current = clock.Quote(2, BID + bid_step * clock.TICK, ASK + ask_step * clock.TICK, bq, aq)
    assert study.ofi_increment(previous, current) == expected


def test_window_expiration_retains_inclusive_lower_boundary():
    window = study.OfiWindow()
    window.observe(clock.Quote(0, BID, ASK, 10, 10))
    window.observe(clock.Quote(clock.SECOND_NS, BID, ASK, 20, 10))
    window.expire(6 * clock.SECOND_NS)
    assert window.total == 10
    window.expire(6 * clock.SECOND_NS + 1)
    assert window.total == 0


def test_ofi_uses_only_completed_event_and_excludes_equal_grid_timestamp():
    builder = seeded()
    # This partial event must not replace the earlier complete queue state.
    builder.consume(event("M", "B", BID, 1, 1, ns(11, 59, 59, 900)))
    builder.consume(event("M", "A", ASK, 70, 2, ns(12, 0, 0), flags=dbn.F_LAST))
    row = builder.rows[0]
    assert row["ofi_5s"] == 60
    assert row["normalized_ofi_5s"] == 1.5
    assert row["signal_direction"] == 1
    assert row["top_bid_qty"] == 70
    assert row["decision_quote_ts_ns"] == ns(11, 59, 59, 800)
    assert builder.ofi.total == -69


def test_trade_and_fill_do_not_double_count_ofi():
    builder = seeded()
    at = ns(11, 59, 59, 900)
    builder.consume(event("T", "B", ASK, 5, 0, at))
    builder.consume(event("F", "A", ASK, 5, 2, at, flags=dbn.F_LAST))
    assert builder.ofi.total == 60  # T/F do not change the MBO queue
    builder.consume(event("C", "A", ASK, 5, 2, at + 1, flags=dbn.F_LAST))
    assert builder.ofi.total == 65  # actual queue cancellation counted exactly once


@pytest.mark.parametrize("sign", [1, -1])
def test_exact_signal_boundaries_and_weighted_mid_identity(sign):
    builder = study.OfiScalp("ofi_queue")
    builder.ofi.first_ts = 0
    builder.ofi.total = 10 * sign  # normalized magnitude exactly one
    bq, aq = (13, 7) if sign == 1 else (7, 13)
    quote = clock.Quote(5 * clock.SECOND_NS - 1, BID, ASK, bq, aq)
    direction, reason, fields = builder._signal_at_grid(5 * clock.SECOND_NS, quote, 0.3 * sign)
    assert direction == sign and reason is None
    assert fields["weighted_mid_offset_ticks"] == pytest.approx(0.15 * sign)
    assert fields["weighted_mid_offset_ticks"] == (bq - aq) / (bq + aq) / 2
    builder.ofi.total = 9 * sign
    assert builder._signal_at_grid(5 * clock.SECOND_NS, quote, 0)[1] == "ofi_below_one_side_depth"


def test_queue_only_control_has_no_ofi_gate_but_same_warmup():
    primary, control = seeded(), seeded("queue_only")
    for builder in (primary, control):
        builder.ofi.total = 0
        builder.ofi.events.clear()
    assert trigger(primary)["policy_reason"] == "ofi_below_one_side_depth"
    row = trigger(control)
    assert row["selected_counterfactual"]
    assert row["known_side_trades_5s"] == 0  # no CVD gate inherited accidentally
    control.ofi.first_ts = ns(12, 0, 1)
    assert control._signal_at_grid(ns(12, 0, 5), control.last_quote, 0)[1] == (
        "insufficient_ofi_warmup"
    )


@pytest.mark.parametrize(
    "bq,aq,ofi,reason",
    [
        (12, 8, 60, "weighted_mid_offset_too_small"),
        (70, 10, -60, "ofi_queue_disagree"),
    ],
)
def test_magnitude_and_direction_vetoes(bq, aq, ofi, reason):
    builder = seeded()
    builder.ofi.total = ofi
    builder.ofi.events.clear()
    quote = clock.Quote(ns(11, 59, 59, 800), BID, ASK, bq, aq)
    assert builder._signal_at_grid(ns(12, 0, 0), quote, 0)[1] == reason


def test_reset_does_not_bridge_ofi_history():
    builder = seeded()
    assert builder.ofi.total == 60
    builder.consume(event("R", "N", 0, 0, 0, ns(11, 59, 59, 850)))
    builder.consume(event("A", "B", BID, 10, 1, ns(11, 59, 59, 900)))
    builder.consume(event("A", "A", ASK, 10, 2, ns(11, 59, 59, 900), flags=dbn.F_LAST))
    assert builder.ofi.total == 0
    assert builder.ofi.first_ts == ns(11, 59, 59, 900)
    builder._end_window()
    builder.start_day(date(2025, 7, 8))
    assert builder.ofi.first_ts is None
    assert builder.ofi.previous is None


def test_late_exit_remains_open_until_quote_then_records_loss_and_cooldown():
    builder = seeded()
    row = trigger(builder)
    update(builder, ns(12, 0, 14))
    assert builder.active_row is row
    assert row["latency_variants"]["100"]["status"] == "exit_pending"
    update(builder, ns(12, 0, 18), bid=BID - 2 * clock.TICK, ask=ASK)
    variant = row["latency_variants"]["100"]
    assert variant["late_exit"] is True
    assert variant["gross_crossed_quote_ticks"] == -3
    assert variant["net_after_extra_cost_ticks"]["1"] == -4
    assert variant["exit_lateness_ns"] == 2_900_000_000
    assert builder.active_row is None
    assert builder.cooldown_until_ns == ns(12, 0, 28)
    summary = study.summarize(builder.rows)["latency_ms"]["100"]
    assert summary["entered"] == summary["closed"] == summary["late_exits"] == 1
    assert summary["unresolved_entered"] == 0


def test_short_exit_arithmetic_and_independent_latency_prices():
    builder = seeded()
    update(builder, ns(11, 59, 59, 900), bid_qty=10, ask_qty=70)
    row = trigger(builder)
    assert row["signal_direction"] == -1
    update(builder, ns(12, 0, 0, 500), bid=BID - clock.TICK, ask=ASK - clock.TICK)
    update(builder, ns(12, 0, 1), bid=BID - 2 * clock.TICK, ask=ASK - 2 * clock.TICK)
    for second, millis in ((15, 100), (15, 500), (16, 0)):
        update(
            builder, ns(12, 0, second, millis), bid=BID - 3 * clock.TICK, ask=ASK - 3 * clock.TICK
        )
    assert [
        row["latency_variants"][str(m)]["gross_crossed_quote_ticks"] for m in clock.LATENCY_MS
    ] == [2, 1, 0]


def test_window_end_retains_unresolved_exposure_and_blocks_conclusion():
    builder = seeded()
    row = trigger(builder)
    builder._end_window()
    variants = row["latency_variants"]
    assert variants["100"]["status"] == "unresolved_exit_window_end"
    assert variants["500"]["status"] == "no_entry_window_end"
    stats = {"ofi_queue": study.summarize(builder.rows)}
    assert stats["ofi_queue"]["latency_ms"]["100"]["entered"] == 1
    assert study.experiment_decision(stats) == "inconclusive_unresolved_positions"


def test_slow_or_control_unresolved_position_also_blocks_conclusion():
    primary = {"unresolved_entered": 0, "net_ticks_by_extra_cost": {"1": {"mean_closed": 10}}}
    stats = {
        "ofi_queue": {"latency_ms": {"100": primary}},
        "queue_only": {"latency_ms": {"1000": {"unresolved_entered": 1}}},
    }
    assert study.experiment_decision(stats) == "inconclusive_unresolved_positions"
    stats.pop("queue_only")
    assert (
        study.experiment_decision(stats) == "requires_independent_replication_and_broker_execution"
    )
    primary["net_ticks_by_extra_cost"]["1"]["mean_closed"] = 0
    assert study.experiment_decision(stats) == "reject_for_promotion"


def test_config_pin_fixed_cohort_and_mutation_refusal(tmp_path):
    config, digest = study.load_config(CONFIG)
    assert digest == study.CONFIG_SHA256
    assert config["source_sessions"] == list(study.SESSIONS)
    assert config["contract"] == study.OfiScalp("ofi_queue").contract == "6EU5"
    assert config["trading_enabled"] is config["training_enabled"] is False
    bad = tmp_path / "changed.json"
    bad.write_bytes(CONFIG.read_bytes() + b" ")
    with pytest.raises(ValueError, match="configuration changed"):
        study.load_config(bad)


def test_wrong_cohort_rejected_before_open_or_publish(tmp_path, monkeypatch):
    monkeypatch.setattr(
        study, "selected_sources", lambda *_: ({}, [{"day": date(2025, 7, 12)}], "unused")
    )
    with pytest.raises(ValueError, match="Unexpected source day"):
        study.run_experiment(
            project_root=tmp_path,
            config_path=CONFIG,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert not list(tmp_path.iterdir())


def test_existing_and_identical_outputs_rejected(tmp_path):
    output = tmp_path / "existing.json"
    output.write_text("preserve")
    for rows, summary in ((output, tmp_path / "new.json"), (tmp_path / "same", tmp_path / "same")):
        with pytest.raises(ValueError, match="overwrite"):
            study.run_experiment(
                project_root=tmp_path, config_path=CONFIG, rows_output=rows, summary_output=summary
            )
    assert output.read_text() == "preserve"
    assert len(list(tmp_path.iterdir())) == 1


def test_strategy_typo_is_not_silently_queue_only():
    with pytest.raises(ValueError, match="Unknown registered"):
        study.OfiScalp("ofi_typo")


def test_member_integrity_failure_does_not_publish_subset(tmp_path, monkeypatch):
    archive_path = tmp_path / "synthetic.zip"
    with ZipFile(archive_path, "x") as archive:
        archive.writestr("metadata-only", b"")
    sources = [
        {"day": date.fromisoformat(day), "archive": archive_path}
        for day in ("2025-07-06", *study.SESSIONS)
    ]
    monkeypatch.setattr(study, "selected_sources", lambda *_: ({}, sources, "unused"))

    def corrupt_member(*_):
        raise ValueError("Compressed member SHA256 mismatch")

    monkeypatch.setattr(study, "_member_records", corrupt_member)
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        study.run_experiment(
            project_root=tmp_path,
            config_path=CONFIG,
            rows_output=tmp_path / "rows.jsonl",
            summary_output=tmp_path / "summary.json",
        )
    assert list(tmp_path.iterdir()) == [archive_path]


@pytest.mark.parametrize(
    "millis,bid,ask,status",
    [
        (1100, BID, ASK, "exit_pending"),
        (1101, BID, ASK, "no_entry_quote_timeout"),
        (100, BID, ASK + clock.TICK, "no_entry_spread_widened"),
    ],
)
def test_entry_wait_boundary_and_widened_spread_veto(millis, bid, ask, status):
    builder = seeded()
    update(builder, ns(12, 0, 0, millis), bid=bid, ask=ask)
    variant = builder.rows[0]["latency_variants"]["100"]
    assert variant["status"] == status
    assert (variant["entry_ts_ns"] is not None) == (status == "exit_pending")
