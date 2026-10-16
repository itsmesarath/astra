"""Operator workflow tested against synthetic captures only, with networking forbidden."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal

import pytest
from test_capture_replay import cfg, records
from test_paper_lifecycle import paper_case

from ai_trader.trading import paper_smoke as module
from ai_trader.trading.paper_lifecycle import PaperEntryOrder
from ai_trader.trading.paper_runner import PaperRunner
from ai_trader.trading.trade_journal import JournalConflict, TradeJournal


@pytest.fixture
def args(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Smoke workflow must never connect to the network.")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    data = b"".join(json.dumps(r).encode() + b"\n" for r in records())
    path = tmp_path / "capture.jsonl"
    path.write_bytes(data)
    return dict(
        capture_path=path,
        expected_sha256=hashlib.sha256(data).hexdigest(),
        source_session="smoke-source",
        journal_path=tmp_path / "smoke.sqlite",
        run_id="smoke",
        initial_cash_usdt=Decimal("1000"),
        max_frames=100,
        replay_config=cfg(),
    )


def journal(args):
    return TradeJournal(args["journal_path"], run_id="smoke", mode="paper")


def test_smoke_completes_flat_killed_and_no_orders(args):
    report = module.run_smoke(**args)
    assert report["status"] == "session_complete" and report["session_consumed"]
    assert report["market_fault_frames"] == report["orders"] == 0
    assert report["frames_processed"] == 5
    assert report["cash_usdt"] == "1000" and report["position_btc"] == "0"
    assert report["quote_health_counts"]["healthy"] > 0
    with journal(args) as db:
        assert db.order_ids() == ()
        assert db._db.execute("SELECT COUNT(*) FROM paper_runner_ticks").fetchone()[0] == 5


def test_prefix_resume_is_idempotent_and_explicit(args):
    first = module.run_smoke(**{**args, "max_frames": 2})
    assert first["status"] == "frame_budget_reached"
    with pytest.raises(FileExistsError):
        module.run_smoke(**args)
    result = module.run_smoke(**args, resume=True)
    assert result == module.run_smoke(**args, resume=True)
    with journal(args) as db:
        assert db._db.execute("SELECT COUNT(*) FROM paper_runner_ticks").fetchone()[0] == 5


@pytest.mark.parametrize("change", ["cash", "source", "config", "run"])
def test_resume_rejects_changed_identity_or_configuration(args, change):
    module.run_smoke(**{**args, "max_frames": 2})
    updated = dict(args, resume=True)
    if change == "cash":
        updated["initial_cash_usdt"] = Decimal("900")
    elif change == "source":
        # Same session ID with different valid bytes is an immutable-binding conflict.
        data = args["capture_path"].read_bytes().replace(b'"q": "3"', b'"q": "4"')
        assert data != args["capture_path"].read_bytes()
        args["capture_path"].write_bytes(data)
        updated["expected_sha256"] = hashlib.sha256(data).hexdigest()
    elif change == "config":
        updated["replay_config"] = replace(cfg(), max_event_lag_ns=600_000_000)
    else:
        updated["run_id"] = "different"
    with pytest.raises((JournalConflict, ValueError)):
        module.run_smoke(**updated)
    with journal(args) as db:
        assert db._db.execute("SELECT COUNT(*) FROM paper_runner_ticks").fetchone()[0] == 2


def test_smoke_refuses_order_history_even_without_fills(args):
    module.run_smoke(**args)
    with journal(args) as db:
        case = paper_case()
        case = replace(
            case, decision_at_ns=1_300_000_000, plan=replace(case.plan, expires_at_ns=1_400_000_000)
        )
        db.append_case(case)
        db.append_order(
            PaperEntryOrder(
                "not-smoke",
                case.case_id,
                case.sha256,
                case.approved_quantity_btc,
                case.decision_at_ns,
            )
        )
    with pytest.raises(JournalConflict, match="no orders"):
        module.run_smoke(**args, resume=True)


def test_processing_failure_rolls_back_entire_invocation(args, monkeypatch):
    original = PaperRunner.process
    calls = []

    def fail(runner, tick):
        result = original(runner, tick)
        calls.append(tick)
        if len(calls) == 2:
            raise RuntimeError("synthetic crash after a tick")
        return result

    monkeypatch.setattr(PaperRunner, "process", fail)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        module.run_smoke(**args)
    with journal(args) as db:
        assert db.account_seed() is None
        assert db._db.execute("SELECT COUNT(*) FROM paper_runner_ticks").fetchone()[0] == 0
        assert db._db.execute("SELECT COUNT(*) FROM paper_replay_sources").fetchone()[0] == 0


def test_invalid_market_footer_not_reported_as_budget_exhaustion(args):
    rows = records()
    rows[-2]["event"].update(U=150, u=150)
    data = b"".join(json.dumps(r).encode() + b"\n" for r in rows)
    args["capture_path"].write_bytes(data)
    report = module.run_smoke(**{**args, "expected_sha256": hashlib.sha256(data).hexdigest()})
    assert report["status"] == "session_invalid" and report["session_consumed"]
    assert report["market_fault_frames"] > 0 and report["orders"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"expected_sha256": "0" * 64},
        {"max_frames": 0},
        {"max_frames": True},
        {"max_frames": 10001},
        {"initial_cash_usdt": Decimal("NaN")},
        {"resume": "yes"},
    ],
)
def test_invalid_inputs_before_journal_creation(args, kwargs):
    with pytest.raises(ValueError):
        module.run_smoke(**{**args, **kwargs})
    assert not args["journal_path"].exists()


def test_cli_uses_explicit_synthetic_capture(args, monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "paper_smoke",
            "--capture",
            str(args["capture_path"]),
            "--sha256",
            args["expected_sha256"],
            "--source-session",
            "smoke-source",
            "--journal",
            str(args["journal_path"]),
            "--run-id",
            "smoke",
            "--initial-cash-usdt",
            "1000",
            "--max-frames",
            "100",
            "--levels",
            "1",
            "--rolling-window-ms",
            "100",
        ],
    )
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "offline_paper_smoke" and report["orders"] == 0


def test_resume_crash_preserves_previously_committed_prefix(args, monkeypatch):
    module.run_smoke(**{**args, "max_frames": 2})
    original = PaperRunner.process
    calls = []

    def fail(runner, tick):
        result = original(runner, tick)
        calls.append(tick)
        if len(calls) == 4:
            raise RuntimeError("crash on resumed prefix")
        return result

    monkeypatch.setattr(PaperRunner, "process", fail)
    with pytest.raises(RuntimeError):
        module.run_smoke(**args, resume=True)
    with journal(args) as db:
        assert db.account_seed().initial_cash_usdt == Decimal("1000")
        assert db._db.execute("SELECT COUNT(*) FROM paper_runner_ticks").fetchone()[0] == 2


def test_full_unusable_capture_reports_failed_check(args):
    rows = records()
    rows[1]["received_at_ns"] = 1150_000_000  # All depth is buffered before availability.
    data = b"".join(json.dumps(r).encode() + b"\n" for r in rows)
    args["capture_path"].write_bytes(data)
    result = module.run_smoke(**{**args, "expected_sha256": hashlib.sha256(data).hexdigest()})
    assert result["session_consumed"]
    assert result["check_result"] == "failed"
    assert result["orders"] == 0
