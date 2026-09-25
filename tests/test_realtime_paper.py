"""Synthetic public receipts only; no exchange connection or live order route."""

import asyncio
import hashlib
import json
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from test_capture_replay import cfg, records
from test_microstructure_paper import rows_with_exit
from test_microstructure_policy import capture_rows, gateway_config, policy, replay_config

from ai_trader.ingestion.collect_combined import DurableCaptureRecord
from ai_trader.research.microstructure_trial import _environment
from ai_trader.trading import realtime_paper as module
from ai_trader.trading.capture_replay import _implementation_hash
from ai_trader.trading.trade_journal import TradeJournal


def plan(*, settings=None, replay=None):
    return module.RealtimePaperPlan(
        "live-paper-test",
        "capture-one",
        800_000_000,
        settings or replace(policy(), rule="abstain"),
        replay or cfg(),
        gateway_config(),
        Decimal("1000"),
        1_000_000_000,
        500_000_000,
        _implementation_hash(),
        _environment(),
    )


def line(record):
    return (json.dumps(record, separators=(",", ":")) + "\n").encode()


def feed(session, rows, *, buffered=False, stop_before_footer=False):
    ordered = [
        rows[0],
        *(rows[2:4] if buffered else ()),
        rows[1],
        *(rows[4:-1] if buffered else rows[2:-1]),
        rows[-1],
    ]
    if stop_before_footer:
        ordered = ordered[:-1]
    metadata_end = stream_end = 0
    for row in ordered:
        encoded = line(row)
        event = row["record_type"] == "stream_event"
        if event:
            start = stream_end
            stream_end += len(encoded)
            end = stream_end
        else:
            start = metadata_end + (stream_end if row["record_type"] == "session_end" else 0)
            end = start + len(encoded)
            metadata_end = end
        session.accept(
            row,
            DurableCaptureRecord(
                "stream" if event else "metadata",
                start,
                end,
                hashlib.sha256(encoded).hexdigest(),
            ),
        )


@pytest.mark.parametrize("buffered", [False, True])
def test_realtime_paper_exact_final_capture_and_abstain(tmp_path, monkeypatch, buffered):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_300_000_000)
    rows = records()
    if buffered:
        rows[1]["received_at_ns"] = 1_075_000_000
    capture_path = tmp_path / "capture.jsonl"
    journal_path = tmp_path / "paper.sqlite"
    session = module.RealtimePaperSession(plan(), journal_path)
    try:
        feed(session, rows, buffered=buffered)
        capture_path.write_bytes(b"".join(map(line, rows)))
        report = session.complete(capture_path)
        assert report["mode"] == "realtime_paper"
        assert report["paper_orders"] == 0
        assert report["paper_frames"] == (3 if buffered else 5)
        assert report["live_trading_available"] is False
        assert (
            session.journal._db.execute("SELECT count(*) FROM paper_live_completion").fetchone()[0]
            == 1
        )
    finally:
        session.close()


def test_realtime_paper_retains_incomplete_journal_and_refuses_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_300_000_000)
    journal_path = tmp_path / "paper.sqlite"
    session = module.RealtimePaperSession(plan(), journal_path)
    try:
        feed(session, records(), stop_before_footer=True)
        with pytest.raises(RuntimeError, match="Incomplete"):
            session.complete(tmp_path / "missing.jsonl")
        assert (
            session.journal._db.execute("SELECT count(*) FROM paper_live_completion").fetchone()[0]
            == 0
        )
    finally:
        session.close()
    with pytest.raises(FileExistsError):
        module.RealtimePaperSession(plan(), journal_path)
    with TradeJournal(
        journal_path,
        run_id="realtime-paper-" + module._hash(plan().sha256),
        mode="paper",
        read_only=True,
    ) as journal:
        assert journal._db.execute("SELECT count(*) FROM paper_live_receipts").fetchone()[0] > 0


def test_realtime_paper_candidate_entry_and_protective_exit(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_700_000_000)
    rows = rows_with_exit()
    capture_path = tmp_path / "capture.jsonl"
    active = plan(settings=policy(), replay=replay_config())
    session = module.RealtimePaperSession(active, tmp_path / "paper.sqlite")
    try:
        feed(session, rows)
        capture_path.write_bytes(b"".join(map(line, rows)))
        report = session.complete(capture_path)
        assert report["paper_orders"] == 2
        assert report["position_btc"] == "0.000"
        assert session.journal.account_state().realized_pnl_usdt > 0
        assert (
            sum(
                session.journal.get_order(oid).reason == "take_profit"
                for oid in session.journal.order_ids()
                if hasattr(session.journal.get_order(oid), "reason")
            )
            == 1
        )
    finally:
        session.close()


def test_late_recorded_event_freezes_later_paper_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_700_000_000)
    rows = rows_with_exit()
    rows[2]["event"]["E"] = 800  # 200 ms old at receipt; within replay's 2 s budget.
    active = replace(
        plan(settings=policy(), replay=replay_config()),
        max_action_event_lag_ns=100_000_000,
    )
    capture_path = tmp_path / "capture.jsonl"
    session = module.RealtimePaperSession(active, tmp_path / "paper.sqlite")
    try:
        feed(session, rows)
        capture_path.write_bytes(b"".join(map(line, rows)))
        report = session.complete(capture_path)
        assert report["paper_frozen"] is True
        assert report["paper_orders"] == 0
        assert all(
            not json.loads(row[0])["book_synchronized"]
            for row in session.journal._db.execute("SELECT payload FROM paper_runner_ticks")
        )
    finally:
        session.close()


def test_completed_second_session_keeps_inventory_and_protects_it(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_900_000_000)
    active = replace(
        plan(settings=policy(), replay=replay_config()),
        source_session="series-s0001",
    )
    journal_path = tmp_path / "series.sqlite"
    first_rows = capture_rows()
    first_path = tmp_path / "series-s0001.jsonl"
    first = module.RealtimePaperSession(active, journal_path)
    try:
        feed(first, first_rows)
        first_path.write_bytes(b"".join(map(line, first_rows)))
        first_report = first.complete(first_path)
        assert Decimal(first_report["position_btc"]) > 0
    finally:
        first.close()

    wrong_path = tmp_path / "wrong-prior.jsonl"
    wrong_path.write_bytes(b"different capture\n")
    with pytest.raises(module.JournalConflict, match="Prior captures"):
        module.RealtimePaperSession(
            active,
            journal_path,
            source_session="series-s0002",
            prior_captures=(wrong_path,),
        )

    second_rows = records()
    second_rows[0]["started_at_ns"] += 600_000_000
    second_rows[1]["requested_at_ns"] += 600_000_000
    second_rows[1]["received_at_ns"] += 600_000_000
    second_rows[1]["event"]["bids"] = [["97", "2"], ["96", "3"]]
    second_rows[1]["event"]["asks"] = [["98", "2"], ["99", "3"]]
    for row in second_rows[2:-1]:
        row["received_at_ns"] += 600_000_000
        row["event"]["E"] += 600
        if row["stream"].endswith("aggTrade"):
            row["event"]["T"] += 600
    second_rows[-1]["ended_at_ns"] += 600_000_000
    second_path = tmp_path / "series-s0002.jsonl"
    second = module.RealtimePaperSession(
        active,
        journal_path,
        source_session="series-s0002",
        prior_captures=(first_path,),
    )
    try:
        feed(second, second_rows)
        second_path.write_bytes(b"".join(map(line, second_rows)))
        second_report = second.complete(second_path)
        assert second_report["position_btc"] == "0.000"
        assert second_report["paper_orders"] == 2
        assert any(
            getattr(second.journal.get_order(oid), "reason", None) == "stop_loss"
            for oid in second.journal.order_ids()
        )
        assert (
            second.journal._db.execute("SELECT count(*) FROM paper_live_completion").fetchone()[0]
            == 2
        )
    finally:
        second.close()


def test_market_gap_commits_fault_tick_then_stops_without_completion(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 1_300_000_000)
    rows = records()
    rows[4]["event"]["U"] = 104
    session = module.RealtimePaperSession(plan(), tmp_path / "fault.sqlite")
    try:
        with pytest.raises(RuntimeError, match="lost synchronization"):
            feed(session, rows)
        assert (
            session.journal._db.execute("SELECT count(*) FROM paper_live_completion").fetchone()[0]
            == 0
        )
        assert session.journal.order_ids() == ()
    finally:
        session.close()


def test_decision_lag_fails_before_paper_tick(tmp_path, monkeypatch):
    monkeypatch.setattr(module.time, "time_ns", lambda: 5_000_000_000)
    session = module.RealtimePaperSession(plan(), tmp_path / "lag.sqlite")
    try:
        with pytest.raises(RuntimeError, match="lag/skew"):
            feed(session, records())
        assert (
            session.journal._db.execute("SELECT count(*) FROM paper_runner_ticks").fetchone()[0]
            == 0
        )
    finally:
        session.close()


def test_run_requires_explicit_activation_before_any_artifact(tmp_path):
    with pytest.raises(ValueError, match="Explicit"):
        asyncio.run(
            module.run_realtime_paper(
                plan_path=tmp_path / "missing.json",
                capture_path=tmp_path / "capture.jsonl",
                journal_path=tmp_path / "paper.sqlite",
                seconds=1,
            )
        )
    assert list(tmp_path.iterdir()) == []


def test_registered_plan_runs_bounded_collector_and_refuses_reuse(tmp_path, monkeypatch):
    now = [800_000_000]
    monkeypatch.setattr(module.time, "time_ns", lambda: now[0])
    plan_path = tmp_path / "plan.json"
    capture_path = tmp_path / "capture.jsonl"
    journal_path = tmp_path / "paper.sqlite"
    registered = module.register_realtime_plan(
        plan_path,
        plan_id="live-paper-test",
        source_session="capture-one",
        policy=replace(policy(), rule="abstain"),
        replay=cfg(),
        gateway=gateway_config(),
        initial_cash_usdt=Decimal("1000"),
        max_decision_delay_ns=1_000_000_000,
        max_action_event_lag_ns=500_000_000,
    )
    assert module.load_realtime_plan(plan_path) == registered
    now[0] = 1_300_000_000

    async def fake_collector(seconds, *, output_path, limits, on_durable_record, validation_config):
        assert seconds == 1 and limits == module.REALTIME_LIMITS
        assert validation_config == registered.replay
        rows = records()
        feed(SimpleNamespace(accept=on_durable_record), rows)
        output_path.write_bytes(b"".join(map(line, rows)))
        return output_path, 1, 2

    kwargs = dict(
        plan_path=plan_path,
        capture_path=capture_path,
        journal_path=journal_path,
        seconds=1,
        enable_public_data=True,
        enable_paper_simulation=True,
        collector=fake_collector,
    )
    report = asyncio.run(module.run_realtime_paper(**kwargs))
    assert report["paper_frames"] == 5 and report["paper_orders"] == 0
    with pytest.raises(FileExistsError):
        asyncio.run(module.run_realtime_paper(**kwargs))


def test_registered_plan_rejects_source_change_before_capture(tmp_path, monkeypatch):
    path = tmp_path / "plan.json"
    module.register_realtime_plan(
        path,
        plan_id="source-pin-test",
        source_session="capture-one",
        policy=replace(policy(), rule="abstain"),
        replay=cfg(),
        gateway=gateway_config(),
        initial_cash_usdt=Decimal("1000"),
        max_action_event_lag_ns=500_000_000,
    )
    monkeypatch.setattr(module, "_implementation_hash", lambda: "0" * 64)
    with pytest.raises(ValueError, match="Source code changed"):
        module.load_realtime_plan(path)


@pytest.mark.parametrize("fail_second", [False, True])
def test_finite_realtime_service_keeps_one_journal_and_stops_after_two(
    tmp_path, monkeypatch, fail_second
):
    now = [800_000_000]
    monkeypatch.setattr(module.time, "time_ns", lambda: now[0])
    plan_path = tmp_path / "plan.json"
    output = tmp_path / "captures"
    journal_path = tmp_path / "paper.sqlite"
    manifest_path = tmp_path / "manifest.jsonl"
    module.register_realtime_plan(
        plan_path,
        plan_id="service-test",
        source_session="service-s0001",
        policy=replace(policy(), rule="abstain"),
        replay=cfg(),
        gateway=gateway_config(),
        initial_cash_usdt=Decimal("1000"),
        max_decision_delay_ns=2_000_000_000,
        max_action_event_lag_ns=500_000_000,
    )
    now[0] = 2_000_000_000

    async def fake_collector(seconds, *, output_path, limits, on_durable_record, validation_config):
        assert seconds == 1 and limits == module.REALTIME_LIMITS
        assert validation_config == cfg()
        if fail_second and output_path.stem.endswith("s0002"):
            raise RuntimeError("synthetic second-session disconnect")
        rows = records()
        if output_path.stem.endswith("s0002"):
            rows[0]["started_at_ns"] += 500_000_000
            rows[1]["requested_at_ns"] += 500_000_000
            rows[1]["received_at_ns"] += 500_000_000
            for row in rows[2:-1]:
                row["received_at_ns"] += 500_000_000
                row["event"]["E"] += 500
                if row["stream"].endswith("aggTrade"):
                    row["event"]["T"] += 500
            rows[-1]["ended_at_ns"] += 500_000_000
        feed(SimpleNamespace(accept=on_durable_record), rows)
        output_path.write_bytes(b"".join(map(line, rows)))
        return output_path, 1, 2

    invocation = module.run_realtime_paper_service(
        plan_path=plan_path,
        output_directory=output,
        journal_path=journal_path,
        manifest_path=manifest_path,
        sessions=2,
        seconds_per_session=1,
        enable_public_data=True,
        enable_paper_simulation=True,
        collector=fake_collector,
    )
    if fail_second:
        with pytest.raises(RuntimeError, match="second-session disconnect"):
            asyncio.run(invocation)
    else:
        report = asyncio.run(invocation)
        assert report["completed_sessions"] == 2
        assert len(report["capture_paths"]) == 2
    assert not (output / ".realtime-paper.lock").exists()
    manifest = [json.loads(row) for row in manifest_path.read_text().splitlines()]
    assert [row["record_type"] for row in manifest] == (
        ["service_start", "session_start", "session_completed", "session_start", "session_failed"]
        if fail_second
        else [
            "service_start",
            "session_start",
            "session_completed",
            "session_start",
            "session_completed",
            "service_completed",
        ]
    )
    if not fail_second:
        assert manifest[-1]["live_orders_submitted"] is False
    assert (output / "service-s0001.jsonl").exists()
    assert (output / "service-s0002.jsonl").exists() is not fail_second
    inspection = module.inspect_realtime_paper_service(
        journal_path=journal_path, output_directory=output, manifest_path=manifest_path
    )
    assert inspection["status"] == ("failed_incomplete" if fail_second else "recorded_complete")
    assert inspection["capture_hashes_match"] is True
    with TradeJournal(
        journal_path,
        run_id="realtime-paper-" + module._hash(module.load_realtime_plan(plan_path).sha256),
        mode="paper",
        read_only=True,
    ) as journal:
        assert journal._db.execute("SELECT count(*) FROM paper_live_completion").fetchone()[0] == (
            1 if fail_second else 2
        )
        assert journal.account_state().cash_usdt == Decimal("1000")
    if not fail_second:
        (output / "service-s0001.jsonl").write_bytes(b"changed evidence\n")
        inspection = module.inspect_realtime_paper_service(
            journal_path=journal_path, output_directory=output, manifest_path=manifest_path
        )
        assert inspection["status"] == "integrity_failed"
