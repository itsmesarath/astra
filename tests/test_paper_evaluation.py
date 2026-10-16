"""Synthetic read-only evaluation; no feeds, hidden data or strategy execution."""

import hashlib
import json
import socket
import sqlite3
import sys
from dataclasses import replace
from decimal import Decimal, localcontext

import pytest
from test_microstructure_paper import MS, append_interval, open_journal, rows_with_exit, setup_run
from test_microstructure_policy import capture_rows, policy

from ai_trader.research import paper_evaluation as module
from ai_trader.trading import microstructure_paper as paper
from ai_trader.trading.capture_replay import CaptureReplay
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.microstructure_paper import simulate_registered_capture
from ai_trader.trading.paper_runner import PaperRunner
from ai_trader.trading.trade_journal import JournalError, TradeJournal

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Evaluation attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def prepared(tmp_path, *, max_frames=100, **kwargs):
    args, registration = setup_run(tmp_path, **kwargs)
    simulated = simulate_registered_capture(**{**args, "max_frames": max_frames})
    evaluation = {k: v for k, v in args.items() if k != "enable_paper_simulation"}
    return evaluation, simulated, registration


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_full_roundtrip_matches_hand_calculation_and_costs_are_counted_once(tmp_path):
    args, simulated, _ = prepared(tmp_path)
    report = module.evaluate_registered_paper(**args)
    qty = D("0.998")
    entry, exit_price = D("100.01") * D("1.0005"), D("101.2") * D("0.9995")
    entry_fee, exit_fee = qty * entry * D("0.001"), qty * exit_price * D("0.001")
    pnl = qty * (exit_price - entry) - entry_fee - exit_fee
    assert D(report["net_pnl_usdt"]) == D(simulated["realized_pnl_usdt"]) == pnl
    assert D(report["terminal_equity_usdt"]) == D("1000") + pnl
    assert D(report["fees_paid_usdt"]) == entry_fee + exit_fee
    assert D(report["slippage_embedded_usdt"]) == qty * (
        entry - D("100.01") + D("101.2") - exit_price
    )
    assert D(report["gross_filled_notional_usdt"]) == qty * (entry + exit_price)
    assert D(report["turnover_over_initial_cash"]) == qty * (entry + exit_price) / 1000
    assert D(report["net_return_fraction"]) == pnl / 1000
    assert report["filled_entries"] == report["closed_trades"] == 1
    assert report["winning_closed_trades"] == 1 and report["open_trades"] == 0
    assert report["closed_trade_win_fraction"] == "1"
    assert D(report["trades"][0]["net_realized_pnl_usdt"]) == pnl
    assert report["trades"][0]["closed_at_ns"] == 1500 * MS
    assert report["exposure_ns"] == 200 * MS
    assert report["full_session_flat_comparison_available"]
    assert report["excess_return_vs_cash_fraction"] == report["net_return_fraction"]
    assert report["cash_control"] == {"terminal_equity_usdt": "1000", "net_pnl_usdt": "0"}
    assert report["hypothetical_terminal_exit_equity_usdt"] == report["terminal_equity_usdt"]
    assert not report["promotion_allowed"] and not report["live_trading_available"]


def test_drawdown_samples_before_and_after_costs_including_pre_exit_peak(tmp_path):
    args, _, _ = prepared(tmp_path)
    report = module.evaluate_registered_paper(**args)
    curve = report["equity_curve"]
    assert len(curve) == 2 * report["frames_evaluated"] == 26
    peak, max_dd = D("1000"), D(0)
    for point in curve:
        equity = D(point["equity_usdt"])
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    assert max_dd == D(report["sampled_max_drawdown_usdt"])
    assert max_dd > 0  # Positive completed PnL does not erase initial spread/fee drawdown.
    exits = [p for p in curve if p["observed_at_ns"] == 1500 * MS]
    assert D(exits[0]["equity_usdt"]) > D(exits[1]["equity_usdt"])
    assert report["drawdown_path_fully_valued"]


@pytest.mark.parametrize("bid,ask", [("99.7", "99.71"), ("99", "99.01")])
def test_stop_and_gap_losses_remain_losses_after_fees(tmp_path, bid, ask):
    args, simulated, _ = prepared(tmp_path, rows=rows_with_exit(bid, ask))
    report = module.evaluate_registered_paper(**args)
    assert report["losing_closed_trades"] == 1 and report["winning_closed_trades"] == 0
    assert D(report["net_pnl_usdt"]) == D(simulated["realized_pnl_usdt"]) < 0
    assert report["closed_trade_win_fraction"] == "0"
    assert D(report["excess_return_vs_cash_fraction"]) < 0


def test_open_footer_inventory_is_unknown_not_valued_at_an_old_quote(tmp_path):
    args, simulated, _ = prepared(tmp_path, rows=capture_rows())
    report = module.evaluate_registered_paper(**args)
    assert report["session_consumed"] and not report["truncated"]
    assert report["open_trades"] == 1 and report["closed_trades"] == 0
    assert report["position_btc"] == simulated["position_btc"]
    for key in (
        "terminal_equity_usdt",
        "net_pnl_usdt",
        "net_return_fraction",
        "hypothetical_terminal_exit_equity_usdt",
        "closed_trade_win_fraction",
        "excess_return_vs_cash_fraction",
    ):
        assert report[key] is None
    assert report["trades"][0]["net_realized_pnl_usdt"] is None
    assert report["unvalued_equity_samples"] == 2
    assert not report["drawdown_path_fully_valued"]
    assert report["last_valued_sample"]["observed_at_ns"] < report["ended_at_ns"]
    assert not report["full_session_flat_comparison_available"]


def test_healthy_open_prefix_has_mark_and_separate_exit_cost_scenario_without_a_fill(tmp_path):
    args, simulated, _ = prepared(tmp_path, max_frames=11)
    before = checksum(args["journal_path"])
    report = module.evaluate_registered_paper(**args)
    cash, qty = D(simulated["cash_usdt"]), D(simulated["position_btc"])
    assert report["truncated"] and not report["session_consumed"]
    assert D(report["terminal_equity_usdt"]) == cash + qty * 100
    assert D(report["unrealized_pnl_usdt"]) == qty * 100 - D(report["cost_basis_usdt"])
    assert D(report["net_pnl_usdt"]) == (
        D(report["realized_pnl_usdt"]) + D(report["unrealized_pnl_usdt"])
    )
    assert D(report["hypothetical_terminal_exit_equity_usdt"]) == (
        cash + qty * 100 * D("0.9995") * D("0.999")
    )
    assert report["closed_trades"] == 0 and report["excess_return_vs_cash_fraction"] is None
    assert checksum(args["journal_path"]) == before
    assert report["exposure_ns"] == 0  # Entry is at the last sampled instant.


def test_flat_incomplete_prefix_is_not_a_complete_comparison(tmp_path):
    args, _, _ = prepared(tmp_path, max_frames=2)
    report = module.evaluate_registered_paper(**args)
    assert report["terminal_equity_usdt"] == "1000"
    assert report["net_pnl_usdt"] == "0" and report["truncated"]
    assert report["closed_trade_win_fraction"] is None
    assert not report["full_session_flat_comparison_available"]


def test_single_tick_zero_duration_has_no_invented_exposure_fraction(tmp_path):
    args, _, _ = prepared(tmp_path, max_frames=1)
    report = module.evaluate_registered_paper(**args)
    assert report["observed_duration_ns"] == 0 and report["time_in_position_fraction"] is None


def test_stream_gap_retains_unvalued_inventory_and_exposure(tmp_path):
    args, _, _ = prepared(tmp_path, rows=rows_with_exit("99", "99.01", gap=True))
    report = module.evaluate_registered_paper(**args)
    assert report["market_fault_frames"] == 2
    assert report["terminal_equity_usdt"] is None and report["closed_trades"] == 0
    assert report["exposure_ns"] == 300 * MS
    assert report["unvalued_equity_samples"] == 4
    assert not report["full_session_flat_comparison_available"]


def test_closed_loss_and_new_open_lot_are_not_combined_into_a_fake_win(tmp_path):
    rows = rows_with_exit("99.7", "99.71")
    for i in range(3):
        append_interval(
            rows,
            timestamp=1600 + i * 100,
            bid="99.7",
            ask="99.71",
            before_bid=8 + i * 2,
            after_bid=10 + i * 2,
            after_ask=[10, 9, 1][i],
        )
    args, _, _ = prepared(tmp_path, rows=rows)
    report = module.evaluate_registered_paper(**args)
    assert report["filled_entries"] == 2
    assert report["closed_trades"] == report["open_trades"] == 1
    assert report["losing_closed_trades"] == 1 and report["winning_closed_trades"] == 0
    closed = next(t for t in report["trades"] if t["status"] == "closed")
    opened = next(t for t in report["trades"] if t["status"] == "open")
    assert D(closed["net_realized_pnl_usdt"]) == D(report["realized_pnl_usdt"]) < 0
    assert opened["net_realized_pnl_usdt"] is None and report["net_pnl_usdt"] is None
    assert D(report["fees_paid_usdt"]) == D(closed["fees_usdt"]) + D(opened["fees_usdt"])
    assert report["exposure_ns"] == 300 * MS


def test_abstain_control_has_no_fees_trades_or_fake_win_rate(tmp_path):
    args, _, _ = prepared(tmp_path, settings=replace(policy(), rule="abstain"))
    report = module.evaluate_registered_paper(**args)
    assert report["full_session_flat_comparison_available"]
    assert D(report["net_pnl_usdt"]) == D(report["excess_return_vs_cash_fraction"]) == 0
    assert report["fees_paid_usdt"] == report["slippage_embedded_usdt"] == "0"
    assert report["trades"] == [] and report["closed_trade_win_fraction"] is None
    assert D(report["sampled_max_drawdown_usdt"]) == 0 and report["exposure_ns"] == 0


def test_no_write_no_reassessment_no_execution_and_repeat_is_identical(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    before = {
        key: checksum(args[key]) for key in ("journal_path", "capture_path", "registration_path")
    }

    def forbidden(*args, **kwargs):
        pytest.fail("Read-only evaluation attempted to write or execute.")

    monkeypatch.setattr(TradeJournal, "_write", forbidden)
    monkeypatch.setattr(PaperRunner, "process", forbidden)
    monkeypatch.setattr(PaperRunner, "process_with_case_builder", forbidden)
    first = module.evaluate_registered_paper(**args)
    assert module.evaluate_registered_paper(**args) == first
    for key, value in before.items():
        assert checksum(args[key]) == value
    assert len(first["ledger_snapshot_sha256"]) == len(first["protocol_sha256"]) == 64


def test_read_only_sqlite_connection_enforced(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    original = module._evaluate_snapshot

    def checked(journal, *remaining):
        assert journal.read_only
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            journal._db.execute("CREATE TABLE forbidden (value TEXT)")
        return original(journal, *remaining)

    monkeypatch.setattr(module, "_evaluate_snapshot", checked)
    assert module.evaluate_registered_paper(**args)["closed_trades"] == 1


def test_budget_cannot_cherry_pick_a_smaller_prefix_from_a_longer_journal(tmp_path):
    args, _, _ = prepared(tmp_path)
    with pytest.raises(JournalError, match="every committed tick"):
        module.evaluate_registered_paper(**{**args, "max_frames": 11})


@pytest.mark.parametrize("budget", [True, 0, -1, 10001, 1.0])
def test_invalid_budget_before_any_input_io(tmp_path, monkeypatch, budget):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid budget attempted IO.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError, match="budget"):
        module.evaluate_registered_paper(
            registration_path=tmp_path / "missing",
            capture_path=tmp_path / "missing",
            source_session="missing",
            journal_path=tmp_path / "missing",
            max_frames=budget,
        )


@pytest.mark.parametrize("source", ["reserved-one", "unknown"])
def test_reserved_unknown_source_rejected_before_capture_or_journal(tmp_path, monkeypatch, source):
    args, _, _ = prepared(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Protected source reached a capture loader.")

    monkeypatch.setattr(CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError, match="registered research"):
        module.evaluate_registered_paper(**{**args, "source_session": source})


def test_missing_journal_is_not_created(tmp_path):
    args, _, _ = prepared(tmp_path)
    missing = tmp_path / "absent.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        module.evaluate_registered_paper(**{**args, "journal_path": missing})
    assert not missing.exists()


def test_extra_case_outside_tick_prefix_fails_closed(tmp_path):
    args, _, _ = prepared(tmp_path)
    with open_journal(args) as journal:
        case_id = journal._db.execute("SELECT case_id FROM cases LIMIT 1").fetchone()[0]
        journal.append_case(replace(journal.get_case(case_id), case_id="outside-tick"))
    with pytest.raises(JournalError, match="outside"):
        module.evaluate_registered_paper(**args)


def test_altered_frame_evidence_is_rejected(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    original = CaptureReplay.frames

    def changed(replay):
        for frame in original(replay):
            yield replace(frame, status=frame.status + "-changed")

    monkeypatch.setattr(CaptureReplay, "frames", changed)
    with pytest.raises(JournalError, match="evidence"):
        module.evaluate_registered_paper(**args)


def test_wrong_fill_cost_model_is_not_accepted(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    original = module.simulate_market_fill

    def changed(**kwargs):
        expected = original(**kwargs)
        return replace(expected, fee_usdt=expected.fee_usdt + D("0.01"))

    monkeypatch.setattr(module, "simulate_market_fill", changed)
    with pytest.raises(JournalError, match="cost model"):
        module.evaluate_registered_paper(**args)


def test_source_environment_drift_during_read_has_no_success_report(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    before = checksum(args["journal_path"])
    monkeypatch.setattr(module, "_environment", lambda: "changed")
    with pytest.raises(ValueError, match="during evaluation"):
        module.evaluate_registered_paper(**args)
    assert checksum(args["journal_path"]) == before


def test_evaluation_decimal_context_independent_of_caller(tmp_path):
    args, _, _ = prepared(tmp_path)
    baseline = module.evaluate_registered_paper(**args)
    with localcontext() as context:
        context.prec = 7
        assert module.evaluate_registered_paper(**args) == baseline


def test_rejected_gateway_order_is_not_counted_as_a_trade(tmp_path, monkeypatch):
    args, record = setup_run(tmp_path)
    simulate_registered_capture(**{**args, "max_frames": 2})
    with open_journal(args) as journal:
        gateway = DurablePaperGateway(journal, record.gateway)
        gateway.set_kill_switch(True, observed_at_ns=gateway.risk_checkpoint().observed_at_ns)
    original = paper._build_case

    def policy_bypass(*values):
        case = original(*values)
        if case.action == "ENTER_LONG":
            return replace(
                case,
                risk_verdict="APPROVED",
                approved_quantity_btc=case.plan.quantity_btc,
                risk_reason="synthetic_policy_bypass",
            )
        return case

    monkeypatch.setattr(paper, "_build_case", policy_bypass)
    simulate_registered_capture(**args, resume=True)
    report = module.evaluate_registered_paper(
        **{k: v for k, v in args.items() if k != "enable_paper_simulation"}
    )
    assert report["rejected_orders"] == 1 and report["filled_entries"] == 0
    assert report["fees_paid_usdt"] == "0" and report["trades"] == []
    assert report["kill_switch_active"] and D(report["net_pnl_usdt"]) == 0


@pytest.mark.parametrize("mutation", ["tick_index", "tick_checksum", "request_quote"])
def test_corrupt_index_payload_or_quote_binding_fails_closed(tmp_path, mutation):
    args, _, _ = prepared(tmp_path)
    with open_journal(args) as journal:
        if mutation.startswith("tick"):
            journal._db.execute("DROP TRIGGER paper_runner_ticks_no_update")
            if mutation == "tick_index":
                journal._db.execute(
                    "UPDATE paper_runner_ticks SET tick_id='corrupt' WHERE sequence=1"
                )
            else:
                journal._db.execute("UPDATE paper_runner_ticks SET sha256='corrupt'")
        else:
            journal._db.execute("DROP TRIGGER paper_gateway_requests_no_update")
            order_id, payload = journal._db.execute(
                "SELECT order_id, payload FROM paper_gateway_requests LIMIT 1"
            ).fetchone()
            request = json.loads(payload)
            request["ask_usdt"] = str(D(request["ask_usdt"]) + 1)
            payload = json.dumps(request, sort_keys=True)
            journal._db.execute(
                "UPDATE paper_gateway_requests SET payload=?, sha256=? WHERE order_id=?",
                (payload, hashlib.sha256(payload.encode()).hexdigest(), order_id),
            )
    with pytest.raises(JournalError):
        module.evaluate_registered_paper(**args)


def test_capture_hash_mismatch_is_rejected(tmp_path):
    args, _, _ = prepared(tmp_path)
    args["capture_path"].write_bytes(args["capture_path"].read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        module.evaluate_registered_paper(**args)


def test_empty_metadata_only_journal_is_not_a_zero_return_experiment(tmp_path):
    args, record = setup_run(tmp_path)
    with TradeJournal.create(
        args["journal_path"],
        run_id=paper.paper_run_id(record, args["source_session"]),
        mode="paper",
    ):
        pass
    with pytest.raises(JournalError, match="empty journals"):
        module.evaluate_registered_paper(
            **{k: v for k, v in args.items() if k != "enable_paper_simulation"}
        )


def test_fixed_protocol_cannot_be_changed_through_a_report(tmp_path):
    args, _, _ = prepared(tmp_path)
    report = module.evaluate_registered_paper(**args)
    with pytest.raises(TypeError):
        module.PROTOCOL["terminal"] = "optimistic_liquidation"
    report["protocol"]["terminal"] = "optimistic_liquidation"
    reread = module.evaluate_registered_paper(**args)
    assert reread["protocol"]["terminal"] == "retain_inventory_no_forced_liquidation"
    assert reread["protocol_sha256"] == report["protocol_sha256"]


@pytest.mark.parametrize("frames,expected_code", [(100, 0), (11, 2)])
def test_cli_complete_vs_incomplete_without_execution_flag(
    tmp_path, monkeypatch, capsys, frames, expected_code
):
    args, _, _ = prepared(tmp_path, max_frames=frames)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluation",
            "--registration",
            str(args["registration_path"]),
            "--capture",
            str(args["capture_path"]),
            "--source-session",
            args["source_session"],
            "--journal",
            str(args["journal_path"]),
            "--max-frames",
            "100",
        ],
    )
    if expected_code:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == expected_code
    else:
        module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["full_session_flat_comparison_available"] is (expected_code == 0)
