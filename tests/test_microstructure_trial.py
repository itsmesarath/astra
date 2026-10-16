"""Synthetic metadata/capture bytes only; no downloads, held-out reads or orders."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from test_microstructure_policy import capture_bytes, gateway_config, policy, replay_config

from ai_trader.research import microstructure_trial as module
from ai_trader.research.microstructure_trial import SourceDeclaration
from ai_trader.trading.capture_replay import CaptureReplay
from ai_trader.trading.trade_journal import TradeJournal, _hash

D = Decimal
MS = 1_000_000


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Research case evaluation must not access the network.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def declarations():
    return (
        SourceDeclaration(
            "research-one",
            hashlib.sha256(capture_bytes()).hexdigest(),
            900 * MS,
            1400 * MS,
            "research",
        ),
        SourceDeclaration("reserved-one", "f" * 64, 2000 * MS, 3000 * MS, "reserved"),
    )


def register(path, **kwargs):
    args = dict(
        trial_id="synthetic-trial",
        sources=declarations(),
        policy=policy(),
        replay=replay_config(),
        gateway=gateway_config(),
        initial_cash_usdt=D("1000"),
    )
    return module.register_trial(path, **(args | kwargs))


@pytest.fixture
def run_args(tmp_path):
    registration = tmp_path / "registration.json"
    register(registration)
    capture = tmp_path / "research.jsonl"
    capture.write_bytes(capture_bytes())
    return dict(
        registration_path=registration,
        capture_path=capture,
        source_session="research-one",
        journal_path=tmp_path / "research.sqlite",
        max_frames=100,
    )


def open_journal(args):
    checksum = json.loads(args["registration_path"].read_text())["registration_sha256"]
    run_id = "micro-shadow-" + _hash(checksum + ":" + args["source_session"])
    return TradeJournal(args["journal_path"], run_id=run_id, mode="research_only")


def case_count(db):
    return db._db.execute("SELECT COUNT(*) FROM cases").fetchone()[0]


def test_registration_does_not_need_datasets_and_round_trips(tmp_path):
    path = tmp_path / "registration.json"
    record = register(path)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["registration.json"]
    assert module.load_registration(path) == record
    assert record.mode == "research_only" and record.promotion_allowed is False
    assert record.research_source("research-one") == declarations()[0]
    with pytest.raises(FileExistsError):
        register(path)
    assert module.load_registration(path) == record


def test_every_frame_retained_including_abstentions_no_execution(run_args):
    report = module.evaluate_registered_capture(**run_args)
    assert report["frames_evaluated"] == 12 and report["session_consumed"]
    assert report["case_counts"] == {"NO_ACTION:NOT_EVALUATED": 11, "ENTER_LONG:APPROVED": 1}
    assert report["orders"] == 0 and report["promotion_allowed"] is False
    with open_journal(run_args) as journal:
        assert case_count(journal) == 12
        assert journal._db.execute("SELECT COUNT(*) FROM paper_orders").fetchone()[0] == 0
        assert journal._db.execute("SELECT COUNT(*) FROM paper_events").fetchone()[0] == 0
        cases = [
            journal.get_case(row[0]) for row in journal._db.execute("SELECT case_id FROM cases")
        ]
        assert all(c.mode == "research_only" for c in cases)
        assert any(c.risk_reason == "book_unsynchronized" for c in cases)
    with pytest.raises(ValueError, match="identity"):
        TradeJournal(run_args["journal_path"], run_id="synthetic-trial", mode="paper")


@pytest.mark.parametrize("source", ["reserved-one", "unregistered"])
def test_refuses_reserved_and_unknown_before_capture_or_journal_open(run_args, monkeypatch, source):
    def forbidden(*args, **kwargs):
        pytest.fail("Forbidden session reached the capture loader.")

    monkeypatch.setattr(CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError, match="registered research"):
        module.evaluate_registered_capture(
            **{**run_args, "source_session": source, "capture_path": Path("must-never-be-opened")}
        )
    assert not run_args["journal_path"].exists()


def test_aliasing_reserved_bytes_into_research_is_rejected(tmp_path):
    sources = declarations()
    with pytest.raises(ValueError, match="aliased"):
        register(
            tmp_path / "registration.json",
            sources=(sources[0], replace(sources[1], source_sha256=sources[0].source_sha256)),
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "fault",
    ["overlap", "unordered", "duplicate_id", "no_reserved", "later_research", "mutable_sources"],
)
def test_bad_source_inventory_before_writes(tmp_path, fault):
    first, second = declarations()
    sources = (first, second)
    if fault == "overlap":
        sources = (first, replace(second, started_at_ns=first.ended_at_ns))
    elif fault == "unordered":
        sources = (second, first)
    elif fault == "duplicate_id":
        sources = (first, replace(second, source_session=first.source_session))
    elif fault == "no_reserved":
        sources = (first, replace(second, role="research"))
    elif fault == "later_research":
        sources = (replace(first, role="reserved"), replace(second, role="research"))
    elif fault == "mutable_sources":
        sources = list(sources)
    with pytest.raises(ValueError):
        register(tmp_path / "registration.json", sources=sources)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "code",
        "environment",
        "duplicate_json",
        "live",
        "boolean_schema",
        "boolean_duration",
        "bad_decimal",
        "extra_field",
    ],
)
def test_changed_or_malformed_registration_fails_before_source_access(run_args, monkeypatch, fault):
    path = run_args["registration_path"]
    document = json.loads(path.read_text())
    if fault == "code":
        monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    elif fault == "environment":
        monkeypatch.setattr(module, "_environment", lambda: "changed")
    else:
        if fault == "hash":
            document["registration_sha256"] = "b" * 64
        elif fault == "live":
            document["registration"]["mode"] = "spot_live"
        elif fault == "boolean_schema":
            document["registration"]["schema_version"] = True
        elif fault == "boolean_duration":
            document["registration"]["policy"]["entry_ttl_ns"] = True
        elif fault == "bad_decimal":
            document["registration"]["initial_cash_usdt"] = "NaN"
        elif fault == "extra_field":
            document["registration"]["future_outcome"] = "winner"
        raw = json.dumps(document)
        if fault == "duplicate_json":
            raw = '{"registration":null,' + raw[1:]
        path.write_text(raw)

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid registration reached capture access.")

    monkeypatch.setattr(CaptureReplay, "from_path", forbidden)
    with pytest.raises(ValueError):
        module.evaluate_registered_capture(**run_args)
    assert not run_args["journal_path"].exists()


def test_source_hash_and_declared_times_checked_before_journal(run_args):
    run_args["capture_path"].write_bytes(capture_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        module.evaluate_registered_capture(**run_args)
    assert not run_args["journal_path"].exists()
    run_args["capture_path"].write_bytes(capture_bytes())
    other = run_args["registration_path"].with_name("wrong-times.json")
    first, second = declarations()
    register(other, sources=(replace(first, started_at_ns=first.started_at_ns - 1), second))
    with pytest.raises(ValueError, match="times"):
        module.evaluate_registered_capture(**{**run_args, "registration_path": other})
    assert not run_args["journal_path"].exists()


def test_explicit_prefix_resume_and_exact_retries(run_args):
    report = module.evaluate_registered_capture(**{**run_args, "max_frames": 2})
    assert not report["session_consumed"]
    assert sum(report["case_counts"].values()) == 2
    with pytest.raises(FileExistsError):
        module.evaluate_registered_capture(**run_args)
    complete = module.evaluate_registered_capture(**run_args, resume=True)
    assert complete == module.evaluate_registered_capture(**run_args, resume=True)
    with open_journal(run_args) as journal:
        assert case_count(journal) == 12


def test_resume_different_registration_never_combines_trials(run_args):
    module.evaluate_registered_capture(**{**run_args, "max_frames": 2})
    other = run_args["registration_path"].with_name("other.json")
    register(other, policy=replace(policy(), rule="abstain"))
    with pytest.raises(ValueError, match="identity"):
        module.evaluate_registered_capture(**{**run_args, "registration_path": other}, resume=True)
    with open_journal(run_args) as journal:
        assert case_count(journal) == 2


def test_failure_rolls_back_new_invocation_preserving_prefix(run_args, monkeypatch):
    module.evaluate_registered_capture(**{**run_args, "max_frames": 2})
    original = module.assess_microstructure
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        if len(calls) == 5:
            raise RuntimeError("synthetic crash")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "assess_microstructure", fail)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        module.evaluate_registered_capture(**run_args, resume=True)
    with open_journal(run_args) as journal:
        assert case_count(journal) == 2


def test_source_change_during_evaluation_rolls_back(tmp_path, run_args, monkeypatch):
    original = module._implementation_hash
    calls = []

    def changing():
        calls.append(1)
        return original() if len(calls) == 1 else "f" * 64

    monkeypatch.setattr(module, "_implementation_hash", changing)
    with pytest.raises(ValueError, match="during evaluation"):
        module.evaluate_registered_capture(**run_args)
    with open_journal(run_args) as journal:
        assert case_count(journal) == 0


def test_no_trade_control_and_risk_rejected_signals_still_recorded(run_args):
    control = run_args["registration_path"].with_name("control.json")
    register(control, policy=replace(policy(), rule="abstain"))
    report = module.evaluate_registered_capture(**{**run_args, "registration_path": control})
    assert report["reason_counts"] == {"no_trade_control": 12}
    rejected = control.with_name("rejected.json")
    config = gateway_config()
    register(
        rejected, gateway=replace(config, limits=replace(config.limits, max_order_btc=D("0.01")))
    )
    report = module.evaluate_registered_capture(
        **{
            **run_args,
            "registration_path": rejected,
            "journal_path": run_args["journal_path"].with_name("rejected.sqlite"),
        }
    )
    assert report["case_counts"]["ENTER_LONG:REJECTED"] == 1


def test_bad_market_stream_records_abstention_through_footer(run_args):
    from test_microstructure_policy import capture_rows

    rows = capture_rows()
    rows[-2]["event"].update(U=200, u=200)
    data = capture_bytes(rows)
    first, second = declarations()
    source = replace(first, source_sha256=hashlib.sha256(data).hexdigest())
    path = run_args["registration_path"].with_name("gap.json")
    register(path, sources=(source, second))
    run_args["capture_path"].write_bytes(data)
    report = module.evaluate_registered_capture(**{**run_args, "registration_path": path})
    assert report["session_consumed"] and report["market_fault_frames"] == 2
    assert report["case_counts"] == {"NO_ACTION:NOT_EVALUATED": 12}


@pytest.mark.parametrize(
    "kwargs", [{"max_frames": True}, {"max_frames": 0}, {"max_frames": 10001}, {"resume": "yes"}]
)
def test_invalid_budget_before_any_source_access(run_args, monkeypatch, kwargs):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid settings accessed registration.")

    monkeypatch.setattr(module, "load_registration", forbidden)
    with pytest.raises(ValueError):
        module.evaluate_registered_capture(**(run_args | kwargs))


def test_cli_register_and_evaluate_synthetic_spec(run_args, monkeypatch, capsys):
    record = json.loads(run_args["registration_path"].read_text())["registration"]
    spec = {
        key: record[key]
        for key in ("trial_id", "sources", "policy", "replay", "gateway", "initial_cash_usdt")
    }
    spec_path = run_args["registration_path"].with_name("spec.json")
    spec_path.write_text(json.dumps(spec))
    output = spec_path.with_name("cli-registration.json")
    monkeypatch.setattr(
        sys, "argv", ["trial", "register", "--spec", str(spec_path), "--output", str(output)]
    )
    module.main()
    assert json.loads(capsys.readouterr().out)["mode"] == "research_only"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "trial",
            "evaluate",
            "--registration",
            str(output),
            "--capture",
            str(run_args["capture_path"]),
            "--source-session",
            "research-one",
            "--journal",
            str(run_args["journal_path"]),
            "--max-frames",
            "100",
        ],
    )
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["case_counts"]["ENTER_LONG:APPROVED"] == 1 and report["orders"] == 0


def test_oversized_registration_rejected_before_json_parsing(tmp_path):
    path = tmp_path / "oversized.json"
    path.write_bytes(b"x" * (module.MAX_REGISTRATION_BYTES + 1))
    with pytest.raises(ValueError, match="byte budget"):
        module.load_registration(path)


def test_another_research_session_requires_a_separate_journal(run_args):
    # Declare a second eligible session, not a reserved-session relabel inside this run.
    from test_microstructure_policy import capture_rows

    rows = capture_rows()
    for row in rows:
        for key in ("started_at_ns", "requested_at_ns", "received_at_ns", "ended_at_ns"):
            if key in row:
                row[key] += 1000 * MS
        if row["record_type"] == "stream_event":
            row["event"]["E"] += 1000
            if "T" in row["event"]:
                row["event"]["T"] += 1000
    data = capture_bytes(rows)
    first, reserved = declarations()
    second = SourceDeclaration(
        "research-two", hashlib.sha256(data).hexdigest(), 1900 * MS, 2400 * MS, "research"
    )
    reserved = replace(reserved, started_at_ns=3000 * MS, ended_at_ns=4000 * MS)
    registration = run_args["registration_path"].with_name("two-sources.json")
    register(registration, sources=(first, second, reserved))
    updated = {**run_args, "registration_path": registration}
    module.evaluate_registered_capture(**updated)
    second_path = run_args["capture_path"].with_name("second.jsonl")
    second_path.write_bytes(data)
    with pytest.raises(ValueError, match="identity"):
        module.evaluate_registered_capture(
            **{**updated, "capture_path": second_path, "source_session": "research-two"},
            resume=True,
        )


def test_bad_stream_cli_returns_nonzero_and_retains_cases(run_args, monkeypatch, capsys):
    from test_microstructure_policy import capture_rows

    rows = capture_rows()
    rows[-2]["event"].update(U=200, u=200)
    data = capture_bytes(rows)
    first, second = declarations()
    registration = run_args["registration_path"].with_name("bad-stream-cli.json")
    register(
        registration,
        sources=(replace(first, source_sha256=hashlib.sha256(data).hexdigest()), second),
    )
    run_args["capture_path"].write_bytes(data)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "trial",
            "evaluate",
            "--registration",
            str(registration),
            "--capture",
            str(run_args["capture_path"]),
            "--source-session",
            "research-one",
            "--journal",
            str(run_args["journal_path"]),
            "--max-frames",
            "100",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 2
    assert json.loads(capsys.readouterr().out)["market_fault_frames"] == 2
    with open_journal({**run_args, "registration_path": registration}) as journal:
        assert case_count(journal) == 12
