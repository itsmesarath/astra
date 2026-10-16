"""Deterministic read-only review on synthetic paper journals, not market data."""

import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal

import pytest
from test_microstructure_paper import open_journal, rows_with_exit, setup_run
from test_microstructure_policy import capture_rows, policy
from test_paper_evaluation import checksum, prepared

from ai_trader.research import paper_evaluation
from ai_trader.research import post_trade as module
from ai_trader.trading.durable_paper_gateway import DurablePaperGateway
from ai_trader.trading.microstructure_paper import simulate_registered_capture
from ai_trader.trading.trade_journal import JournalError, TradeJournal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("Network access"))


def review(tmp_path, **kwargs):
    args, simulated, record = prepared(tmp_path, **kwargs)
    output = tmp_path / "review.json"
    result = module.review_registered_paper(**args, output_path=output)
    return result, args, output, record


def test_reviews_retain_all_cases_and_match_verified_costed_outcome(tmp_path):
    result, args, output, record = review(tmp_path)
    evaluated = paper_evaluation.evaluate_registered_paper(**args)
    assert result["cases_reviewed"] == evaluated["frames_evaluated"] == 13
    assert result["process_failure_cases"] == 0
    assert result["status_counts"] == {"no_action": 12, "closed": 1}
    assert result["ledger_snapshot_sha256"] == evaluated["ledger_snapshot_sha256"]
    assert result["evaluation_sha256"] == module._hash(module._json(evaluated))
    assert not result["promotion_allowed"] and result["orders_created"] == 0
    closed = next(r for r in result["reviews"] if r["status"] == "closed")
    resolved = closed["resolved_review"]
    assert resolved["outcome"] == "WIN"
    assert resolved["net_pnl_usdt"] == evaluated["trades"][0]["net_realized_pnl_usdt"]
    assert resolved["decision_quality"] == "UNKNOWN"
    assert resolved["case"]["case_id"] == closed["process"]["case_id"]
    for row in result["reviews"]:
        assert row["available_at_ns"] == result["reviewed_at_ns"] >= record.registered_at_ns
        assert row["lesson_status"] == "ANECDOTE"
        assert (
            row["maximum_adverse_excursion_usdt"] is row["maximum_favorable_excursion_usdt"] is None
        )
        assert row["process"]["decision_quality"] == "UNKNOWN"
        if row["status"] != "closed":
            assert row["resolved_review"] is row["trade"] is None
    envelope = json.loads(output.read_bytes())
    assert envelope["report_sha256"] == module._hash(module._json(result))


@pytest.mark.parametrize("bid,expected", [("101.2", "WIN"), ("99.7", "LOSS"), ("99", "LOSS")])
def test_outcome_is_not_the_decision_quality_label(tmp_path, bid, expected):
    result, _, _, _ = review(
        tmp_path, rows=rows_with_exit(bid, str(Decimal(bid) + Decimal("0.01")))
    )
    closed = next(r for r in result["reviews"] if r["status"] == "closed")
    assert closed["resolved_review"]["outcome"] == expected
    assert closed["process"]["failed_checks"] == []
    assert closed["process"]["decision_quality"] == "UNKNOWN"


@pytest.mark.parametrize("frames", [None, 11])
def test_open_or_truncated_inventory_has_no_fabricated_closed_outcome(tmp_path, frames):
    kwargs = {"rows": capture_rows()} if frames is None else {"max_frames": frames}
    result, _, _, _ = review(tmp_path, **kwargs)
    assert result["open_trades"] == 1
    opened = next(r for r in result["reviews"] if r["status"] == "open")
    assert opened["resolved_review"] is None
    assert opened["trade"]["net_realized_pnl_usdt"] is None
    assert result["session_consumed"] is (frames is None)


def test_abstention_control_retains_every_case_without_trade_pnl(tmp_path):
    result, _, _, _ = review(tmp_path, settings=replace(policy(), rule="abstain"))
    assert result["status_counts"] == {"no_action": result["cases_reviewed"]}
    assert all(row["trade"] is row["resolved_review"] is None for row in result["reviews"])


def test_risk_rejected_cases_are_not_discarded(tmp_path):
    args, _ = setup_run(tmp_path)
    simulate_registered_capture(**(args | {"max_frames": 2}))
    with open_journal(args) as journal:
        gateway = DurablePaperGateway(journal, module_registration(args).gateway)
        gateway.set_kill_switch(True, observed_at_ns=gateway.risk_checkpoint().observed_at_ns)
    simulate_registered_capture(**args, resume=True)
    inputs = {k: v for k, v in args.items() if k != "enable_paper_simulation"}
    result = module.review_registered_paper(**inputs, output_path=tmp_path / "reviews.json")
    assert result["status_counts"]["risk_rejected"] == 1
    blocked = next(r for r in result["reviews"] if r["status"] == "risk_rejected")
    assert blocked["process"]["risk_reason"] == "risk_rejected:kill_switch_active"
    assert blocked["trade"] is blocked["resolved_review"] is None


def module_registration(args):
    return paper_evaluation.load_registration(args["registration_path"])


def test_first_pass_accepts_case_only_and_flags_wrong_versions(tmp_path):
    args, _, registration = prepared(tmp_path)
    with TradeJournal(
        args["journal_path"],
        run_id=paper_evaluation.paper_run_id(registration, args["source_session"]),
        mode="paper",
        read_only=True,
    ) as journal:
        case_id = journal._db.execute(
            "SELECT case_id FROM cases ORDER BY rowid LIMIT 1"
        ).fetchone()[0]
        case = journal.get_case(case_id)
    assert module.review_case_process(case, registration)["failed_checks"] == []
    modified = replace(
        case, policy_version="wrong", feature_version="wrong", risk_config_sha256="0" * 64
    )
    result = module.review_case_process(modified, registration)
    assert result["failed_checks"] == [
        "policy_version_matches",
        "feature_version_matches",
        "risk_configuration_matches",
    ]
    assert result["decision_quality"] == "UNKNOWN" and "net_pnl_usdt" not in result
    with pytest.raises(ValueError):
        module.review_case_process({}, registration)


def test_journal_is_unchanged_and_existing_report_not_overwritten(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    before = checksum(args["journal_path"])
    monkeypatch.setattr(TradeJournal, "append_review", lambda *a: pytest.fail("Journal mutation"))
    output = tmp_path / "review.json"
    module.review_registered_paper(**args, output_path=output)
    assert checksum(args["journal_path"]) == before
    previous = output.read_bytes()
    with pytest.raises(FileExistsError):
        module.review_registered_paper(**args, output_path=output)
    assert output.read_bytes() == previous


def test_evaluation_and_reviews_share_one_read_only_snapshot(tmp_path, monkeypatch):
    args, _, _ = prepared(tmp_path)
    original, snapshots = module._review_snapshot, []

    def traced(journal, registration, evaluation):
        assert journal._db.in_transaction
        assert journal._db.execute("PRAGMA query_only").fetchone()[0] == 1
        snapshots.append(evaluation["ledger_snapshot_sha256"])
        return original(journal, registration, evaluation)

    monkeypatch.setattr(module, "_review_snapshot", traced)
    result = module.review_registered_paper(**args, output_path=tmp_path / "review.json")
    assert snapshots == [result["ledger_snapshot_sha256"]]


@pytest.mark.parametrize("source", ["reserved-one", "unknown"])
def test_reserved_source_is_refused_before_data_or_journal_open(tmp_path, monkeypatch, source):
    args, _, _ = prepared(tmp_path)
    monkeypatch.setattr(
        paper_evaluation.CaptureReplay, "from_path", lambda *a, **k: pytest.fail("Capture opened")
    )
    with pytest.raises(ValueError, match="research session"):
        module.review_registered_paper(
            **(args | {"source_session": source}), output_path=tmp_path / "bad.json"
        )


def test_budget_cannot_hide_later_cases(tmp_path):
    args, _, _ = prepared(tmp_path)
    output = tmp_path / "short.json"
    with pytest.raises(JournalError, match="every committed tick"):
        module.review_registered_paper(**(args | {"max_frames": 2}), output_path=output)
    assert not output.exists()


@pytest.mark.parametrize("fault", ["timestamp", "bytes", "drift"])
def test_time_limits_or_drift_abort_without_publication(tmp_path, monkeypatch, fault):
    args, _, _ = prepared(tmp_path)
    if fault == "timestamp":
        monkeypatch.setattr(module.time, "time_ns", lambda: 0)
    elif fault == "bytes":
        monkeypatch.setattr(module, "MAX_REPORT_BYTES", 1)
    else:
        original = module.review_case_process

        def drift(*a):
            result = original(*a)
            monkeypatch.setattr(paper_evaluation, "_implementation_hash", lambda: "0" * 64)
            return result

        monkeypatch.setattr(module, "review_case_process", drift)
    before = checksum(args["journal_path"])
    output = tmp_path / "failed.json"
    with pytest.raises(ValueError):
        module.review_registered_paper(**args, output_path=output)
    assert not output.exists() and checksum(args["journal_path"]) == before


@pytest.mark.parametrize("closed", [False, True])
def test_cli_compact_report_and_incomplete_exit(tmp_path, monkeypatch, capsys, closed):
    args, _, _ = prepared(tmp_path, rows=rows_with_exit() if closed else capture_rows())
    argv = ["review", "--source-session", args["source_session"], "--max-frames", "100"]
    for name in ("registration", "capture", "journal"):
        argv += ["--" + name, str(args[name + "_path"])]
    argv += ["--output", str(tmp_path / "review.json")]
    monkeypatch.setattr(sys, "argv", argv)
    if closed:
        module.main()
    else:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["orders_created"] == 0 and report["process_failure_cases"] == 0
    assert "reviews" not in report
