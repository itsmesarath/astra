"""Bounded synthetic microstructure-health controller and durable protective exits."""

import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_durable_paper_gateway import config as gateway_config
from test_microstructure import baseline, depth, engine, trade
from test_paper_lifecycle import paper_case

from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.gateway import ExecutionStatus
from ai_trader.trading.paper_account import PaperAccountSeed
from ai_trader.trading.paper_lifecycle import PaperExitOrder
from ai_trader.trading.paper_runner import PaperMarketTick, PaperRunner, PaperRunnerConfig
from ai_trader.trading.trade_journal import JournalConflict, JournalError, TradeJournal

D = Decimal


def config():
    return PaperRunnerConfig(200, D("10"))


def tick(tick_id="tick-1", time=1200, **changes):
    return replace(
        PaperMarketTick(
            tick_id, "session-1", time, time, time, D("59990"), D("60000"), True, True, "a" * 64
        ),
        **changes,
    )


def reopen(path, **kwargs):
    return TradeJournal(path, run_id="run-1", mode="paper", **kwargs)


@pytest.fixture
def runner(tmp_path):
    with TradeJournal.create(tmp_path / "runner.sqlite", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("1000"), 1000))
        gateway = DurablePaperGateway.initialize(journal, gateway_config())
        yield PaperRunner.initialize(gateway, config())


def candidate(runner, value=None, **changes):
    current = tick() if value is None else value
    case = replace(
        paper_case(),
        case_id=current.tick_id + "-case",
        source_session=current.source_session,
        decision_at_ns=current.observed_at_ns,
        risk_config_sha256=runner.gateway.config.risk_config_sha256,
        market_state_sha256=current.observation_sha256,
        plan=replace(paper_case().plan, expires_at_ns=current.observed_at_ns + 1000),
        **changes,
    )
    runner.journal.append_case(case)
    return replace(current, candidate_case_id=case.case_id)


def buy(runner):
    value = candidate(runner)
    result = runner.process(value)
    assert result.entry_reason == "paper_fill_applied"
    return result.entry_order_id, value, result


def test_entry_reopen_retry_and_take_profit(runner, tmp_path):
    entry_id, value, result = buy(runner)
    assert runner.process(value) == result
    with reopen(tmp_path / "runner.sqlite") as journal:
        resumed = PaperRunner(DurablePaperGateway(journal, gateway_config()), config())
        assert resumed.process(value) == result
        exit_result = resumed.process(tick("tp", 2200, bid_usdt=D("61000"), ask_usdt=D("61010")))
        assert len(exit_result.exit_order_ids) == 1
        exit_order = journal.get_order(exit_result.exit_order_ids[0])
        assert exit_order.entry_order_id == entry_id
        assert exit_order.reason == "take_profit"
        assert journal.account_state().position_btc == 0
        assert journal.account_state().realized_pnl_usdt == D("0.879")
        assert (
            resumed.process(tick("tp", 2200, bid_usdt=D("61000"), ask_usdt=D("61010")))
            == exit_result
        )


@pytest.mark.parametrize(
    "time,bid,reason",
    [
        (1300, "59000", "stop_loss"),
        (1300, "58000", "stop_loss"),
        (1300, "61000", "take_profit"),
        (6200, "59990", "maximum_hold"),
    ],
)
def test_protection_boundaries_and_gap_fill_price(runner, time, bid, reason):
    buy(runner)
    value = tick("exit", time, bid_usdt=D(bid), ask_usdt=D(bid) + 10)
    result = runner.process(value)
    exit_id = result.exit_order_ids[0]
    assert runner.journal.get_order(exit_id).reason == reason
    assert runner.gateway.get_receipt(exit_id).average_fill_price_usdt == D(bid)
    assert runner.journal.account_state().position_btc == 0


def test_max_hold_not_triggered_early(runner):
    buy(runner)
    assert runner.process(tick("before", 6199)).exit_order_ids == ()
    assert runner.journal.account_state().position_btc > 0


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"book_synchronized": False}, "book_unsynchronized"),
        ({"quote_received_at_ns": 1099}, "stale_quote"),
        ({"features_ready": False}, "microstructure_not_ready"),
        ({"last_trade_received_at_ns": None}, "stale_trades"),
        ({"last_trade_received_at_ns": 999}, "stale_trades"),
        ({"ask_usdt": D("60100")}, "entry_spread_limit"),
    ],
)
def test_entry_health_gates(runner, changes, reason):
    value = candidate(runner, tick(**changes))
    result = runner.process(value)
    assert result.entry_reason == reason
    assert result.entry_order_id is None
    assert runner.journal.order_ids() == ()


def test_health_inputs_do_not_block_healthy_protective_exit(runner):
    buy(runner)
    runner.gateway.set_kill_switch(True, observed_at_ns=2000)
    result = runner.process(
        tick(
            "stop",
            2200,
            bid_usdt=D("58000"),
            ask_usdt=D("59000"),
            features_ready=False,
            last_trade_received_at_ns=None,
        )
    )
    assert len(result.exit_order_ids) == 1  # No features, no trades, large spread, kill active.
    assert runner.journal.account_state().position_btc == 0


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"book_synchronized": False}, "book_unsynchronized"),
        ({"quote_received_at_ns": 1200}, "stale_quote"),
    ],
)
def test_bad_quote_defers_exits_without_fabricating_price(runner, changes, reason):
    entry_id, _, _ = buy(runner)
    before = runner.gateway.risk_checkpoint().peak_equity_usdt
    result = runner.process(
        tick("bad", 6200, bid_usdt=D("999999"), ask_usdt=D("1000000"), **changes)
    )
    assert result.quote_health == reason
    assert result.blocked_exit_entry_ids == (entry_id,)
    assert result.exit_order_ids == ()
    assert runner.journal.account_state().position_btc > 0
    assert runner.gateway.risk_checkpoint().peak_equity_usdt == before
    result = runner.process(tick("recovered", 6300))
    assert runner.journal.get_order(result.exit_order_ids[0]).reason == "maximum_hold"


def test_marks_every_healthy_tick_even_when_features_block_entries(runner):
    buy(runner)
    result = runner.process(
        tick("mark", 1300, bid_usdt=D("60900"), ask_usdt=D("60910"), features_ready=False)
    )
    assert result.exit_order_ids == ()
    assert runner.gateway.risk_checkpoint().peak_equity_usdt == D("1000.84")


def test_drawdown_exit_and_no_same_tick_reentry(runner):
    buy(runner)
    value = candidate(runner, tick("crash", 1300, bid_usdt=D("39000"), ask_usdt=D("39010")))
    result = runner.process(value)
    assert runner.journal.get_order(result.exit_order_ids[0]).reason == "drawdown_limit"
    assert result.entry_reason == "protective_exit_tick"
    assert result.entry_order_id is None


def test_reserved_exit_inventory_is_not_double_sold(runner):
    entry_id, _, _ = buy(runner)
    runner.journal.append_exit_order(PaperExitOrder("manual", entry_id, D("0.001"), 1300, "manual"))
    result = runner.process(tick("stop", 1400, bid_usdt=D("58000"), ask_usdt=D("58010")))
    assert result.exit_order_ids == ()
    assert result.blocked_exit_entry_ids == (entry_id,)
    assert runner.journal.account_state().position_btc == D("0.001")


def test_candidate_must_match_current_observation_and_session(runner):
    value = candidate(runner)
    result = runner.process(replace(value, source_session="reconnected"))
    assert result.entry_reason == "case_observation_mismatch"
    result = runner.process(replace(value, tick_id="different-hash", observation_sha256="b" * 64))
    assert result.entry_reason == "case_observation_mismatch"


def test_case_is_not_reentered_and_changed_tick_conflicts(runner):
    _, value, result = buy(runner)
    later = replace(value, tick_id="repeated-case", observed_at_ns=1250)
    assert runner.process(later).entry_reason == "case_already_ordered"
    with pytest.raises(JournalConflict):
        runner.process(replace(value, bid_usdt=D("59989")))
    assert runner.get_result(value.tick_id) == result


def test_missing_candidate_does_not_prevent_protective_exit(runner):
    buy(runner)
    result = runner.process(
        tick("stop", 1300, bid_usdt=D("58000"), ask_usdt=D("58010"), candidate_case_id="missing")
    )
    assert len(result.exit_order_ids) == 1


def test_run_is_bounded_and_does_not_consume_extra_input(runner):
    consumed = []

    def source():
        for index in range(5):
            consumed.append(index)
            yield tick(f"tick-{index}", 1200 + index)

    assert len(runner.run(source(), max_ticks=2)) == 2
    assert consumed == [0, 1]
    with pytest.raises(ValueError):
        runner.run(source(), max_ticks=True)


def test_time_and_feed_receipts_cannot_regress(runner):
    runner.process(tick())
    with pytest.raises(JournalError, match="clock regressed"):
        runner.process(tick("backward", 1199))
    with pytest.raises(JournalError, match="receipt time regressed"):
        runner.process(tick("old-feed", 1250, quote_received_at_ns=1199))
    assert runner.get_result("old-feed") is None


def test_atomic_tick_failure_rolls_back_fill_and_mark(runner):
    value = candidate(runner)
    checkpoint = runner.gateway.risk_checkpoint()
    runner.journal._db.execute("""CREATE TRIGGER fail_tick BEFORE INSERT ON paper_runner_ticks
        BEGIN SELECT RAISE(ABORT, 'injected'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        runner.process(value)
    assert runner.journal.order_ids() == ()
    assert runner.gateway.risk_checkpoint() == checkpoint
    runner.journal._db.execute("DROP TRIGGER fail_tick")
    assert runner.process(value).entry_reason == "paper_fill_applied"


def test_concurrent_duplicate_ticks_create_one_entry(runner, tmp_path):
    value = candidate(runner)

    def execute(_):
        with reopen(tmp_path / "runner.sqlite") as journal:
            worker = PaperRunner(DurablePaperGateway(journal, gateway_config()), config())
            return worker.process(value)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, range(2)))
    assert results[0] == results[1]
    assert runner.journal.account_state().position_btc == D("0.001")


def test_read_only_result_and_no_network(runner, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network")

    monkeypatch.setattr("socket.socket", forbidden)
    _, value, result = buy(runner)
    with reopen(tmp_path / "runner.sqlite", read_only=True) as journal:
        reader = PaperRunner(DurablePaperGateway(journal, gateway_config()), config())
        assert reader.get_result(value.tick_id) == result
        with pytest.raises(JournalError, match="read-only"):
            reader.process(tick("next", 1300))


@pytest.mark.parametrize(
    "changes",
    [
        {"book_synchronized": 1},
        {"features_ready": "yes"},
        {"last_trade_received_at_ns": 1201},
        {"observation_sha256": "bad"},
        {"observed_at_ns": True},
        {"bid_usdt": D("NaN")},
    ],
)
def test_invalid_tick_contract(changes):
    with pytest.raises(ValueError):
        tick(**changes)


def test_microstructure_bridge_uses_causal_flags_and_fingerprint():
    subject = engine(rolling_window_ms=100)
    first = baseline(subject)
    cold = PaperMarketTick.from_observation(
        first,
        tick_id="warmup",
        observed_at_ns=1_000_000_000,
        last_trade_received_at_ns=None,
        book_synchronized=True,
    )
    assert not cold.features_ready
    subject.add_trade(trade(), received_at_ns=1_050_000_000)
    ready = subject.apply_depth(depth(102, 1100), received_at_ns=1_100_000_000)
    warm = PaperMarketTick.from_observation(
        ready,
        tick_id="ready",
        observed_at_ns=1_100_000_000,
        last_trade_received_at_ns=1_050_000_000,
        book_synchronized=True,
    )
    assert warm.features_ready
    assert warm.source_session == subject.source_session
    assert warm.bid_usdt == ready.book.best_bid_price
    assert warm.observation_sha256 != cold.observation_sha256


def test_runner_config_and_tick_corruption_fail_closed(runner):
    value = tick()
    runner.process(value)
    with pytest.raises(JournalConflict):
        PaperRunner(runner.gateway, replace(config(), max_trade_age_ns=999))
    runner.journal._db.execute("DROP TRIGGER paper_runner_ticks_no_update")
    runner.journal._db.execute("UPDATE paper_runner_ticks SET result='{}'")
    with pytest.raises(JournalError, match="checksum"):
        runner.process(value)


def test_decimal_context_does_not_change_decision(runner):
    value = candidate(runner)
    with localcontext() as context:
        context.prec = 2
        result = runner.process(value)
    assert runner.gateway.get_receipt(result.entry_order_id).status == ExecutionStatus.FILLED


@pytest.mark.parametrize("boundary", ["before_commit", "after_commit"])
def test_process_crash_does_not_duplicate_runner_entry(runner, tmp_path, boundary):
    value = candidate(runner)
    script = """
import os, sys
from ai_trader.trading.trade_journal import TradeJournal, _read
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.durable_paper_gateway import _decode_config as gateway_config
from ai_trader.trading.paper_runner import PaperRunner, _decode_config, _decode_tick
with TradeJournal(sys.argv[1], run_id='run-1', mode='paper') as journal:
    row = journal._db.execute('SELECT payload, sha256 FROM paper_gateway_config').fetchone()
    gw_cfg = _read(*row, gateway_config)
    row = journal._db.execute('SELECT payload, sha256 FROM paper_runner_config').fetchone()
    cfg = _read(*row, _decode_config)
    runner = PaperRunner(DurablePaperGateway(journal, gw_cfg), cfg)
    tick = _read(sys.argv[3], sys.argv[4], _decode_tick)
    if sys.argv[2] == 'before_commit':
        journal._db.create_function('crash_now', 0, lambda: os._exit(23))
        journal._db.execute('CREATE TEMP TRIGGER crash_tick BEFORE INSERT ON paper_runner_ticks '
                            'BEGIN SELECT crash_now(); END')
    runner.process(tick)
    os._exit(23)
"""
    from ai_trader.trading.trade_journal import _encode, _hash

    payload = _encode(value)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(tmp_path / "runner.sqlite"),
            boundary,
            payload,
            _hash(payload),
        ],
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 23, result.stderr
    with reopen(tmp_path / "runner.sqlite") as journal:
        resumed = PaperRunner(DurablePaperGateway(journal, gateway_config()), config())
        assert (resumed.get_result(value.tick_id) is None) == (boundary == "before_commit")
        recovered = resumed.process(value)
        assert recovered.entry_order_id is not None
        assert journal.account_state().position_btc == D("0.001")


def test_v4_runner_upgrade_and_failure_rollback(tmp_path):
    with TradeJournal.create(tmp_path / "old", run_id="run-1", mode="paper") as journal:
        journal._db.execute("DROP TABLE paper_replay_sources")
        journal.initialize_account(PaperAccountSeed(D("1000"), 1000))
        gateway = DurablePaperGateway.initialize(journal, gateway_config())
        journal._db.execute("DROP TABLE paper_runner_ticks")
        journal._db.execute("DROP TABLE paper_runner_config")
        journal._db.execute("PRAGMA user_version=4")
        with pytest.raises(JournalError, match="upgrade"):
            PaperRunner.initialize(gateway, config())
        journal._db.execute("CREATE TABLE paper_runner_ticks (sentinel TEXT)")
        with pytest.raises(sqlite3.OperationalError):
            journal.upgrade_schema()
        assert journal._db.execute("PRAGMA user_version").fetchone()[0] == 4
        assert (
            journal._db.execute(
                "SELECT name FROM sqlite_master WHERE name='paper_runner_config'"
            ).fetchone()
            is None
        )
        journal._db.execute("DROP TABLE paper_runner_ticks")
        assert journal.upgrade_schema()
        resumed = PaperRunner.initialize(gateway, config())
        assert resumed.process(tick()).entry_reason == "no_candidate"


def test_daily_loss_flattens_remaining_lots_independently_of_entry_features(tmp_path):
    with TradeJournal.create(tmp_path / "daily", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("1000"), 1000))
        cfg = gateway_config(max_daily_loss_usdt=D("1"), max_drawdown_usdt=D("100"))
        subject = PaperRunner.initialize(DurablePaperGateway.initialize(journal, cfg), config())
        buy(subject)
        subject.process(candidate(subject, tick("second", 1400)))
        result = subject.process(
            tick("loss", 1500, bid_usdt=D("59000"), ask_usdt=D("59010"), features_ready=False)
        )
        assert len(result.exit_order_ids) == 2
        assert {journal.get_order(i).reason for i in result.exit_order_ids} == {
            "stop_loss",
            "daily_loss_limit",
        }
        assert journal.account_state().position_btc == 0


def test_wide_peak_then_drawdown_between_trades_survives_restart(runner, tmp_path):
    # Widen the approved plan's target, so the high mark itself doesn't close the lot.
    value = candidate(runner)
    old_case = runner.journal.get_case(value.candidate_case_id)
    case = replace(
        old_case,
        case_id="wide-plan",
        plan=replace(old_case.plan, take_profit_price_usdt=D("100000")),
    )
    runner.journal.append_case(case)
    runner.process(replace(value, candidate_case_id=case.case_id))
    runner.process(tick("high-mark", 1300, bid_usdt=D("90000"), ask_usdt=D("90010")))
    assert runner.gateway.risk_checkpoint().peak_equity_usdt == D("1029.94")
    with reopen(tmp_path / "runner.sqlite") as journal:
        resumed = PaperRunner(DurablePaperGateway(journal, gateway_config()), config())
        result = resumed.process(tick("drawdown", 1400))
        assert journal.get_order(result.exit_order_ids[0]).reason == "drawdown_limit"


def test_no_entry_with_bid_already_at_stop(runner):
    value = candidate(runner)
    original = runner.journal.get_case(value.candidate_case_id)
    case = replace(
        original, case_id="tight-stop", plan=replace(original.plan, stop_price_usdt=D("59990"))
    )
    runner.journal.append_case(case)
    result = runner.process(replace(value, candidate_case_id=case.case_id))
    assert result.entry_reason == "entry_outside_plan"
    assert result.entry_order_id is None


def test_runner_tables_are_append_only(runner):
    runner.process(tick())
    for table in ("paper_runner_config", "paper_runner_ticks"):
        with pytest.raises(sqlite3.IntegrityError):
            runner.journal._db.execute(f"DELETE FROM {table}")
        with pytest.raises(sqlite3.IntegrityError):
            runner.journal._db.execute(f"UPDATE {table} SET payload='bad'")


def test_gateway_rejects_stale_mark_without_advancing_clock(runner):
    before = runner.gateway.risk_checkpoint()
    with pytest.raises(JournalError, match="stale"):
        runner.gateway.mark_quote(
            bid_usdt=D("59990"), ask_usdt=D("60000"), quote_at_ns=1000, observed_at_ns=1200
        )
    assert runner.gateway.risk_checkpoint() == before


def test_rejected_candidate_and_bad_decision_time_never_enter(runner):
    value = candidate(runner, risk_verdict="REJECTED", approved_quantity_btc=None)
    assert runner.process(value).entry_reason == "case_not_approved"
    new = candidate(runner, tick("new", 1300))
    future_quote = replace(new, quote_received_at_ns=1350, observed_at_ns=1350)
    assert runner.process(future_quote).entry_reason == "case_decision_time_mismatch"


def test_slippage_outside_target_prevents_entry(tmp_path):
    with TradeJournal.create(tmp_path / "slip", run_id="run-1", mode="paper") as journal:
        journal.initialize_account(PaperAccountSeed(D("1000"), 1000))
        cfg = gateway_config()
        cfg = replace(cfg, costs=replace(cfg.costs, slippage_bps=D("500")))
        subject = PaperRunner.initialize(DurablePaperGateway.initialize(journal, cfg), config())
        assert subject.process(candidate(subject)).entry_reason == "entry_outside_plan"
        assert journal.order_ids() == ()
