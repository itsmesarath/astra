"""Synthetic bytes only: capture timing, gaps, restart identity and paper protection."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from decimal import Decimal

import pytest
from test_build_microstructure import capture_records
from test_durable_paper_gateway import config as gateway_config
from test_paper_lifecycle import paper_case

from ai_trader.features.microstructure import MicrostructureConfig
from ai_trader.trading import capture_replay as module
from ai_trader.trading.capture_replay import CaptureReplay, CaptureReplayConfig
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_runner import PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_case import CaseEvidence, EntryPlan
from ai_trader.trading.trade_journal import JournalConflict, JournalError, TradeJournal

D = Decimal
MS = 1_000_000


def records():
    rows = capture_records()
    for row in rows:
        row["schema_version"] = 1
    rows[0]["started_at_ns"] = 900 * MS
    rows[1].update(requested_at_ns=910 * MS, received_at_ns=950 * MS)
    rows[-1]["ended_at_ns"] = 1200 * MS
    return rows


def cfg():
    return CaptureReplayConfig(
        MicrostructureConfig(levels=1, rolling_window_ms=100), 500 * MS, 10 * MS
    )


def source(rows=None, *, session="capture-one", config=None):
    data = b"".join(
        json.dumps(row).encode() + b"\n" for row in (records() if rows is None else rows)
    )
    return CaptureReplay(
        data,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        source_session=session,
        config=config or cfg(),
    )


def costs():
    return replace(gateway_config(), max_quote_age_ns=200 * MS)


def settings():
    return PaperRunnerConfig(200 * MS, D("200"))


@pytest.fixture
def runner(tmp_path):
    with TradeJournal.create(tmp_path / "paper.sqlite", run_id="replay", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("1000"), 800 * MS))
        gateway = DurablePaperGateway.initialize(journal, costs())
        yield PaperRunner.initialize(gateway, settings())


def candidate(runner, replay):
    frame = next(f for f in replay.frames() if f.tick.features_ready)
    tick = frame.tick
    case = replace(
        paper_case(),
        case_id="entry-" + replay.source_session,
        source_session=tick.source_session,
        decision_at_ns=tick.observed_at_ns,
        market_state_sha256=tick.observation_sha256,
        evidence=(CaseEvidence("observation", tick.quote_received_at_ns, tick.observation_sha256),),
        risk_config_sha256=runner.gateway.config.risk_config_sha256,
        plan=EntryPlan(D("0.001"), D("100"), D("98"), D("101.5"), 10_000 * MS, 2100 * MS),
    )
    runner.journal.append_case(case)
    return {tick.tick_id: case.case_id}


def with_profit_tick():
    rows = records()
    update = {
        "schema_version": 1,
        "record_type": "stream_event",
        "stream": module.DEPTH_STREAM,
        "received_at_ns": 1200 * MS,
        "event": {
            "e": "depthUpdate",
            "s": "BTCUSDT",
            "E": 1200,
            "U": 103,
            "u": 103,
            "b": [["100", "0"], ["101.5", "2"]],
            "a": [["101", "0"]],
        },
    }
    rows.insert(-1, update)
    rows[-1].update(depth_events=3, ended_at_ns=1300 * MS)
    return rows


def test_capture_to_features_to_runner_round_trip(runner):
    replay = source(with_profit_tick())
    mapping = candidate(runner, replay)
    outcomes = replay.run(runner, max_frames=100, candidate_cases=mapping)
    entries = [o.result.entry_order_id for o in outcomes if o.result.entry_order_id]
    exits = [i for o in outcomes for i in o.result.exit_order_ids]
    assert len(entries) == len(exits) == 1
    assert runner.journal.get_order(exits[0]).reason == "take_profit"
    assert runner.journal.account_state().position_btc == 0
    assert runner.journal.account_state().realized_pnl_usdt == D("0.0002975")
    frames = list(replay.frames())
    assert frames[1].observation.session_cvd_base == 0
    assert next(f for f in frames if f.tick.features_ready).observation.session_cvd_base == 3
    assert outcomes[-1].status == "session_closed"
    assert not frames[-1].tick.book_synchronized
    assert replay.run(runner, max_frames=100, candidate_cases=mapping) == outcomes


def test_snapshot_availability_prevents_buffered_future_leakage():
    rows = records()
    rows[1]["received_at_ns"] = 1075 * MS
    frames = list(source(rows).frames())
    assert [f.line_number for f in frames] == [2, 5, 6]
    observation = frames[1].observation
    assert observation.received_at_ns == 1100 * MS
    assert observation.session_cvd_base == 0  # Buffered trade is not prewarmed CVD.
    assert not observation.rolling_window_complete
    assert not observation.evidence_interval_valid
    assert all(f.tick.observed_at_ns >= 1075 * MS for f in frames)


@pytest.mark.parametrize(
    "fault",
    [
        "depth_gap",
        "trade_gap",
        "trade_duplicate",
        "crossed",
        "stale_event",
        "future_event",
        "stale_trade_time",
        "bad_symbol",
        "bad_number",
        "bool_id",
        "duplicate_level",
    ],
)
def test_fault_invalidates_session_and_never_recovers_implicitly(fault):
    rows = with_profit_tick()
    broken = rows[-2]
    if fault in ("trade_gap", "trade_duplicate", "stale_trade_time"):
        broken["stream"] = module.TRADE_STREAM
        broken["event"] = dict(rows[3]["event"], E=1200, T=1200, a=3, f=3, l=3)
        rows[-1].update(depth_events=2, trade_events=2)
        if fault == "trade_duplicate":
            broken["event"]["a"] = 1
        if fault == "stale_trade_time":
            broken["event"].update(a=2, T=100)
    elif fault == "depth_gap":
        broken["event"].update(U=104, u=104)
    elif fault == "crossed":
        broken["event"]["b"] = [["105", "1"]]
    elif fault == "stale_event":
        broken["event"]["E"] = 600
    elif fault == "future_event":
        broken["event"]["E"] = 1300
    elif fault == "bad_symbol":
        broken["event"]["s"] = "ETHUSDT"
    elif fault == "bad_number":
        broken["event"]["b"] = [["101", "Infinity"]]
    elif fault == "bool_id":
        broken["event"]["U"] = True
    else:
        broken["event"]["b"] = [["100", "1"], ["100.0", "2"]]
    follow = dict(
        rows[2], received_at_ns=1250 * MS, event=dict(rows[2]["event"], E=1250, U=103, u=103)
    )
    rows.insert(-1, follow)
    rows[-1]["depth_events"] += 1
    frames = list(source(rows).frames())
    assert all(f.status.startswith("resync_required:") for f in frames[-3:])
    assert all(not f.tick.book_synchronized and not f.tick.features_ready for f in frames[-3:])
    assert frames[-3].tick.quote_received_at_ns == 1100 * MS


def test_new_capture_resets_cvd_warmup_and_restores_protective_exits(runner):
    first = with_profit_tick()
    first[-2]["event"].update(U=104, u=104)
    replay = source(first)
    replay.run(runner, max_frames=100, candidate_cases=candidate(runner, replay))
    assert runner.journal.account_state().position_btc == D("0.001")
    second = records()
    second[0]["started_at_ns"] += 500 * MS
    second[1]["requested_at_ns"] += 500 * MS
    second[1]["received_at_ns"] += 500 * MS
    second[1]["event"]["bids"] = [["97", "2"], ["96", "3"]]
    second[1]["event"]["asks"] = [["98", "2"], ["99", "3"]]
    for row in second[2:-1]:
        row["received_at_ns"] += 500 * MS
        row["event"]["E"] += 500
        if row["stream"] == module.TRADE_STREAM:
            row["event"].update(T=1550, p="98", q="2")
    second[-1]["ended_at_ns"] += 500 * MS
    recovered = source(second, session="capture-two")
    frames = list(recovered.frames())
    assert not frames[1].tick.features_ready
    assert frames[1].observation.session_cvd_base == 0
    assert frames[-2].observation.session_cvd_base == 2
    results = recovered.run(runner, max_frames=100)
    assert len(results[1].result.exit_order_ids) == 1
    exit_order = runner.journal.get_order(results[1].result.exit_order_ids[0])
    assert exit_order.reason == "stop_loss"
    assert runner.journal.account_state().position_btc == 0


def test_stale_depth_and_trade_frames_do_not_refresh_quote_time():
    rows = records()
    rows.insert(
        -1,
        dict(rows[2], received_at_ns=1150 * MS, event=dict(rows[2]["event"], E=1150, U=101, u=101)),
    )
    rows[-1]["depth_events"] += 1
    frames = list(source(rows).frames())
    assert frames[2].status == "no_new_depth"
    assert frames[2].tick.quote_received_at_ns == 1000 * MS
    assert frames[-2].status == "no_new_depth"
    assert frames[-2].tick.quote_received_at_ns == 1100 * MS
    assert not frames[-2].tick.features_ready


def test_prefix_frames_do_not_depend_on_future_prices():
    original = with_profit_tick()
    changed = with_profit_tick()
    changed[-2]["event"]["b"] = [["100", "1"]]
    assert list(source(original).frames())[:-2] == list(source(changed).frames())[:-2]


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_end",
        "count",
        "bool_schema",
        "bool_count",
        "receipt_regression",
        "missing_snapshot_time",
        "snapshot_future",
        "duplicate_snapshot",
        "trailing",
        "empty_event",
    ],
)
def test_malformed_framing_rejected_before_paper_actions(runner, mutation):
    rows = records()
    if mutation == "missing_end":
        rows.pop()
    elif mutation == "count":
        rows[-1]["depth_events"] = 100
    elif mutation == "bool_schema":
        rows[0]["schema_version"] = True
    elif mutation == "bool_count":
        rows[-1]["trade_events"] = True
    elif mutation == "receipt_regression":
        rows[4]["received_at_ns"] = 1000 * MS
    elif mutation == "missing_snapshot_time":
        rows[1].pop("received_at_ns")
    elif mutation == "snapshot_future":
        rows[1]["received_at_ns"] = 1300 * MS
    elif mutation == "duplicate_snapshot":
        rows[1]["event"]["bids"].append(["100.0", "9"])
    elif mutation == "trailing":
        rows.append(rows[-1])
    else:
        rows[3]["event"] = None
    with pytest.raises((ValueError, TypeError)):
        source(rows).run(runner, max_frames=100)
    assert runner.journal.order_ids() == ()
    assert runner.journal._db.execute("SELECT * FROM paper_replay_sources").fetchall() == []


def test_hash_budget_and_duplicate_json_rejection(tmp_path, monkeypatch):
    data = b'{"schema_version":1,"schema_version":1}\n'
    with pytest.raises(ValueError):
        CaptureReplay(
            data, expected_sha256=hashlib.sha256(data).hexdigest(), source_session="s", config=cfg()
        )
    good = source()
    path = tmp_path / "explicit.jsonl"
    path.write_bytes(good._data)
    with pytest.raises(ValueError, match="checksum"):
        CaptureReplay.from_path(path, expected_sha256="0" * 64, source_session="s", config=cfg())
    monkeypatch.setattr(module, "MAX_BYTES", 100)
    with pytest.raises(ValueError, match="budget"):
        CaptureReplay.from_path(
            path, expected_sha256=good.source_sha256, source_session="s", config=cfg()
        )


def test_explicit_file_bytes_are_pinned_not_reread(runner, tmp_path, monkeypatch):
    path = tmp_path / "chosen.jsonl"
    original = source()
    path.write_bytes(original._data)
    replay = CaptureReplay.from_path(
        path, expected_sha256=original.source_sha256, source_session="capture-one", config=cfg()
    )
    path.write_bytes(b"changed")

    def forbidden(*args, **kwargs):
        raise AssertionError("No network")

    monkeypatch.setattr("socket.socket", forbidden)
    assert replay.run(runner, max_frames=100)
    assert path.read_bytes() == b"changed"


def test_restart_reconstructs_prefix_without_duplicate_entry(runner, tmp_path):
    replay = source()
    mapping = candidate(runner, replay)
    prefix = replay.run(runner, max_frames=4, candidate_cases=mapping)
    assert prefix[-1].result.entry_order_id is not None
    with TradeJournal(tmp_path / "paper.sqlite", run_id="replay", mode="paper") as journal:
        resumed = PaperRunner(DurablePaperGateway(journal, costs()), settings())
        outcomes = replay.run(resumed, max_frames=100, candidate_cases=mapping)
        assert outcomes[:4] == prefix
        assert journal.account_state().position_btc == D("0.001")
        assert len(journal.order_ids()) == 1


@pytest.mark.parametrize("change", ["bytes", "config", "cases", "code"])
def test_source_binding_conflicts_block_changed_experiment(runner, monkeypatch, change):
    replay = source()
    mapping = candidate(runner, replay)
    replay.run(runner, max_frames=1, candidate_cases=mapping)
    kwargs = {"candidate_cases": mapping}
    if change == "bytes":
        rows = records()
        rows[-1]["ended_at_ns"] += 1
        replay = source(rows)
    elif change == "config":
        replay = source(config=replace(cfg(), max_event_lag_ns=600 * MS))
    elif change == "cases":
        kwargs = {}
    else:
        monkeypatch.setattr(module, "_implementation_hash", lambda: "f" * 64)
    with pytest.raises(JournalConflict):
        replay.run(runner, max_frames=100, **kwargs)
    assert runner.journal.order_ids() == ()


def test_replay_binding_corruption_and_append_only(runner):
    replay = source()
    replay.run(runner, max_frames=1)
    with pytest.raises(sqlite3.IntegrityError):
        runner.journal._db.execute("DELETE FROM paper_replay_sources")
    runner.journal._db.execute("DROP TRIGGER paper_replay_sources_no_update")
    runner.journal._db.execute("UPDATE paper_replay_sources SET payload='{}'")
    with pytest.raises(JournalError, match="checksum"):
        replay.run(runner, max_frames=100)


def test_v5_explicit_upgrade_preserves_runner(runner):
    journal = runner.journal
    journal._db.execute("DROP TABLE paper_replay_sources")
    journal._db.execute("PRAGMA user_version=5")
    with pytest.raises(JournalError, match="upgrade"):
        source().run(runner, max_frames=1)
    assert journal.upgrade_schema()
    assert source().run(runner, max_frames=1)[0].status == "awaiting_snapshot_bridge"


def test_failed_tick_retains_safe_prefix_and_retry_does_not_duplicate(runner):
    replay = source()
    mapping = candidate(runner, replay)
    runner.journal._db.execute("""CREATE TRIGGER fail_entry_tick
        BEFORE INSERT ON paper_runner_ticks
        WHEN json_extract(NEW.payload, '$.observed_at_ns') = 1100000000
        BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        replay.run(runner, max_frames=100, candidate_cases=mapping)
    assert runner.journal.order_ids() == ()
    assert runner.journal._db.execute("SELECT count(*) FROM paper_runner_ticks").fetchone()[0] == 3
    runner.journal._db.execute("DROP TRIGGER fail_entry_tick")
    outcomes = replay.run(runner, max_frames=100, candidate_cases=mapping)
    assert sum(o.result.entry_order_id is not None for o in outcomes) == 1
    assert runner.journal.account_state().position_btc == D("0.001")


def test_no_bridge_never_declares_snapshot_executable():
    rows = records()
    for row in (rows[2], rows[4]):
        row["event"].update(U=99, u=100)
    frames = list(source(rows).frames())
    assert all(not frame.tick.book_synchronized for frame in frames)
    assert all(frame.observation is None for frame in frames)


def test_buffered_gap_is_not_repaired_by_later_good_record():
    rows = records()
    rows[1]["received_at_ns"] = 1075 * MS
    rows[2]["event"].update(U=103, u=103)
    frames = list(source(rows).frames())
    assert frames[1].status.startswith("resync_required:")
    assert frames[1].observation is None


def test_v5_failed_migration_rolls_back_without_resetting_risk(runner):
    journal = runner.journal
    before = runner.gateway.risk_checkpoint()
    # Mimic an unexpected conflicting extension; migration must not overwrite it.
    journal._db.execute("PRAGMA user_version=5")
    with pytest.raises(sqlite3.OperationalError):
        journal.upgrade_schema()
    assert journal._db.execute("PRAGMA user_version").fetchone()[0] == 5
    assert runner.gateway.risk_checkpoint() == before


def test_duplicate_json_key_in_complete_capture_is_rejected():
    data = source()._data.replace(
        b'"schema_version": 1', b'"schema_version": 1, "schema_version": 1', 1
    )
    with pytest.raises(JournalError, match="Duplicate"):
        CaptureReplay(
            data, expected_sha256=hashlib.sha256(data).hexdigest(), source_session="s", config=cfg()
        )
