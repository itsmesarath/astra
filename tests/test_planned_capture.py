"""Prospective assignment, custody boundaries and failures; synthetic captures only."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_capture_replay import records

from ai_trader.ingestion import planned_capture as module
from ai_trader.ingestion.collect_combined import CaptureInterrupted

NS = module.NS


@pytest.fixture
def setup(tmp_path, monkeypatch):
    clock = [100 * NS]
    calls, pauses = [], []
    monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(module, "_environment", lambda: '{"test":"synthetic"}')
    monkeypatch.setattr(module.time, "time_ns", lambda: clock[0])

    def no_network(*args, **kwargs):
        pytest.fail("No actual network in prospective campaign tests.")

    monkeypatch.setattr(module, "collect", no_network)
    plan = module.prepare_plan(
        campaign_id="synthetic",
        output_dir=tmp_path / "campaign",
        seconds_per_session=30,
        pause_seconds=5,
    )
    plan_path = tmp_path / "plan.json"
    pin = module.write_new(plan_path, plan)
    clock[0] += NS

    async def collector(seconds, *, output_path, limits):
        assert limits is module.DEFAULT_LIMITS
        assert seconds == plan["seconds_per_session"]
        # The session intent is flushed BEFORE collector access.
        audit = [
            json.loads(line)
            for line in (output_path.parent / "audit.jsonl").read_text().splitlines()
        ]
        assert audit[-1]["status"] == "session_started"
        assert audit[-1]["filename"] == output_path.name
        calls.append(output_path)
        rows = records()
        offset = clock[0]
        rows[0]["started_at_ns"] += offset
        rows[1]["requested_at_ns"] += offset
        rows[1]["received_at_ns"] += offset
        for row in rows[2:-1]:
            row["received_at_ns"] += offset
            for key in ("E", "T"):
                if key in row["event"]:
                    row["event"][key] += offset // 1_000_000
        rows[-1]["ended_at_ns"] = rows[0]["started_at_ns"] + seconds * NS
        clock[0] = rows[-1]["ended_at_ns"] + NS
        output_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return output_path, 1, 2

    async def sleeper(seconds):
        pauses.append(seconds)
        clock[0] += seconds * NS

    def run(**kwargs):
        options = dict(
            enable_public_capture=True, collector=collector, sleeper=sleeper, clock=lambda: clock[0]
        )
        options.update(kwargs)
        return asyncio.run(module.run_plan(plan_path, pin, **options))

    return plan, plan_path, pin, clock, calls, pauses, collector, run


def test_plan_is_prospective_exclusive_and_offline(setup):
    plan, path, pin, _, calls, _, _, _ = setup
    assert not Path(plan["output_dir"]).exists()
    assert not calls
    assert [s["split"] for s in plan["sessions"]] == list(module.ROLES)
    assert len({s["source_session"] for s in plan["sessions"]}) == 3
    assert hashlib.sha256(path.read_bytes()).hexdigest() == pin
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        module.write_new(path, plan)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("seconds_per_session", True),
        ("seconds_per_session", 29),
        ("seconds_per_session", 301),
        ("seconds_per_session", 30.0),
        ("pause_seconds", -1),
        ("pause_seconds", 61),
        ("pause_seconds", False),
        ("prepared_at_ns", 0),
        ("prepared_at_ns", True),
        ("campaign_id", "../escape"),
        ("campaign_id", "bad/name"),
        ("campaign_id", "CON"),
        ("campaign_id", ""),
        ("schema_version", True),
        ("schema_version", 2),
        ("kind", "anything"),
        ("implementation_sha256", "b"),
        ("environment_json", None),
        ("output_dir", "relative"),
        ("output_dir", ""),
    ],
)
def test_plan_rejects_invalid_contract(setup, field, value):
    plan = copy.deepcopy(setup[0])
    plan[field] = value
    with pytest.raises(ValueError):
        module.validate_plan(plan)


@pytest.mark.parametrize(
    "mutation",
    [
        "overlap",
        "shuffle",
        "filename",
        "extra",
        "limits",
        "authority",
        "bool_count",
        "zero_count",
        "too_many",
        "total_duration",
    ],
)
def test_no_relabeling_traversal_or_budget_expansion(setup, mutation):
    plan = copy.deepcopy(setup[0])
    if mutation == "overlap":
        plan["sessions"][1]["source_session"] = plan["sessions"][0]["source_session"]
    elif mutation == "shuffle":
        plan["sessions"].reverse()
    elif mutation == "filename":
        plan["sessions"][0]["filename"] = "../outside.jsonl"
    elif mutation == "extra":
        plan["retry"] = True
    elif mutation == "limits":
        plan["limits"]["max_bytes"] += 1
    elif mutation == "authority":
        plan["authority"]["training_allowed"] = True
    elif mutation == "bool_count":
        plan["counts"]["train"] = True
    elif mutation == "zero_count":
        plan["counts"]["reserved"] = 0
    elif mutation == "too_many":
        plan["counts"] = dict.fromkeys(module.ROLES, 3)
    else:
        plan["counts"] = dict.fromkeys(module.ROLES, 2)
        plan["seconds_per_session"] = 300
    with pytest.raises(ValueError):
        module.validate_plan(plan)


@pytest.mark.parametrize("opt_in", [False, None, 1, "yes"])
def test_opt_in_required_before_any_plan_access(opt_in):
    with pytest.raises(ValueError, match="opt-in"):
        asyncio.run(module.run_plan(Path("does-not-exist"), "a" * 64, enable_public_capture=opt_in))


def test_success_retains_all_roles_and_exports_only_metadata(setup):
    plan, _, _, _, calls, pauses, _, run = setup
    receipt = run()
    assert receipt["status"] == "completed"
    assert pauses == [5, 5] and len(calls) == 3
    assert receipt["authority"] == module.AUTHORITY
    assert receipt["orders"] == receipt["model_calls"] == receipt["optimization_steps"] == 0
    assert not receipt["independence_authenticated"]
    assert [s["split"] for s in receipt["sessions"]] == list(module.ROLES)
    assert [s["source"]["role"] for s in receipt["sessions"]] == [
        "research",
        "research",
        "reserved",
    ]
    for before, after in zip(receipt["sessions"][:-1], receipt["sessions"][1:], strict=True):
        assert before["source"]["ended_at_ns"] + 5 * NS < after["source"]["started_at_ns"]
    for item, path in zip(receipt["sessions"], calls, strict=True):
        assert item["source"]["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert item["trade_events"] == 1 and item["depth_events"] == 2
    output = Path(plan["output_dir"])
    assert json.loads((output / "receipt.json").read_text()) == receipt
    audit = [json.loads(line) for line in (output / "audit.jsonl").read_text().splitlines()]
    assert (
        audit[-1]["receipt_sha256"]
        == hashlib.sha256((output / "receipt.json").read_bytes()).hexdigest()
    )
    # Only hashes, timings, counts and declared assignments leave the capture/custody process.
    exported = json.dumps(receipt) + (output / "audit.jsonl").read_text()
    for forbidden in (
        "best_bid",
        '"bids"',
        '"asks"',
        '"event"',
        '"session_cvd_base"',
        "target",
        "pnl",
    ):
        assert forbidden not in exported
    with pytest.raises(FileExistsError):
        run()
    assert len(calls) == 3


@pytest.mark.parametrize("failure_at", [0, 1, 2])
@pytest.mark.parametrize("error_class", [CaptureInterrupted, ValueError, asyncio.CancelledError])
def test_failures_and_cancellation_never_retry_replace_or_reassign(setup, failure_at, error_class):
    plan, _, _, _, calls, _, collector, run = setup

    async def fail(seconds, *, output_path, limits):
        if len(calls) == failure_at:
            calls.append(output_path)
            output_path.with_suffix(".jsonl.partial").write_bytes(b"retained partial")
            raise error_class("PRIVATE MARKET PAYLOAD")
        return await collector(seconds, output_path=output_path, limits=limits)

    with pytest.raises(error_class):
        run(collector=fail)
    assert len(calls) == failure_at + 1
    output = Path(plan["output_dir"])
    failure = json.loads((output / "failure.json").read_text())
    assert failure["status"] == "failed"
    assert [s["status"] for s in failure["sessions"]] == (
        ["completed"] * failure_at + ["failed"] + ["not_started"] * (2 - failure_at)
    )
    assert [s["split"] for s in failure["sessions"]] == list(module.ROLES)
    assert calls[-1].with_suffix(".jsonl.partial").read_bytes() == b"retained partial"
    assert not (output / "receipt.json").exists()
    assert "PRIVATE MARKET PAYLOAD" not in (output / "audit.jsonl").read_text()
    assert "PRIVATE MARKET PAYLOAD" not in (output / "failure.json").read_text()
    with pytest.raises(FileExistsError):
        run()


def test_wrong_pin_and_drift_fail_before_claim_or_network(setup, monkeypatch):
    plan, path, _, _, calls, _, _, run = setup
    original = path.read_bytes()
    path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="SHA256"):
        run()
    path.write_bytes(original)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "b" * 64)
    with pytest.raises(ValueError, match="changed"):
        run()
    assert not calls and not Path(plan["output_dir"]).exists()


@pytest.mark.parametrize("binding", ["_implementation_hash", "_environment"])
def test_mid_capture_drift_stops_remaining_sessions(setup, monkeypatch, binding):
    plan, _, _, _, calls, _, collector, run = setup

    async def change(*args, **kwargs):
        result = await collector(*args, **kwargs)
        monkeypatch.setattr(module, binding, lambda: "b" * 64)
        return result

    with pytest.raises(ValueError, match="changed"):
        run(collector=change)
    assert len(calls) == 1 and calls[0].exists()
    assert not (Path(plan["output_dir"]) / "receipt.json").exists()


@pytest.mark.parametrize(
    "fault",
    ["old", "short", "long", "future", "gap", "counts", "path", "partial", "freshness", "sequence"],
)
def test_bad_completed_captures_cannot_become_successful_subset(setup, fault):
    plan, _, _, clock, calls, _, collector, run = setup

    async def corrupt(*args, **kwargs):
        result = await collector(*args, **kwargs)
        path = result[0]
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if fault == "old":
            rows[0]["started_at_ns"] = plan["prepared_at_ns"] - 1
        elif fault in ("short", "long"):
            rows[-1]["ended_at_ns"] = (
                rows[0]["started_at_ns"] + (2 if fault == "short" else 36) * NS
            )
        elif fault == "future":
            clock[0] = rows[-1]["ended_at_ns"] - 1
        elif fault == "gap" and len(calls) == 1:
            clock[0] = rows[-1]["ended_at_ns"]
        elif fault == "counts":
            return path, 2, 2
        elif fault == "path":
            return path.with_name("unexpected.jsonl"), 1, 2
        elif fault == "partial":
            path.with_suffix(".jsonl.partial").write_bytes(b"partial")
        elif fault == "freshness":
            rows[2]["event"]["E"] -= 3000
        elif fault == "sequence":
            rows[-2]["event"].update(U=200, u=200)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return result

    async def no_gap(_):
        pass

    options = {"collector": corrupt}
    if fault == "gap":
        options["sleeper"] = no_gap
    with pytest.raises((ValueError, CaptureInterrupted)):
        run(**options)
    assert len(calls) <= 2
    assert not (Path(plan["output_dir"]) / "receipt.json").exists()


def test_existing_output_is_never_reused(setup):
    plan, _, _, _, calls, _, _, run = setup
    output = Path(plan["output_dir"])
    output.mkdir()
    marker = output / "user-data"
    marker.write_bytes(b"preserve me")
    with pytest.raises(FileExistsError):
        run()
    assert marker.read_bytes() == b"preserve me" and not calls


def test_clock_regression_before_start_has_no_effect(setup):
    plan, _, _, clock, calls, _, _, run = setup
    clock[0] = plan["prepared_at_ns"]
    with pytest.raises(ValueError, match="clock"):
        run()
    assert not calls and not Path(plan["output_dir"]).exists()


def test_audit_failure_before_intent_prevents_network(setup, monkeypatch):
    _, _, _, _, calls, _, _, run = setup

    def fail_fsync(_):
        raise OSError("disk full")

    monkeypatch.setattr(module.os, "fsync", fail_fsync)
    with pytest.raises(OSError):
        run()
    assert not calls


def test_metadata_fsync_failure_never_publishes_final(tmp_path, monkeypatch):
    path = tmp_path / "metadata.json"

    def fail(_):
        raise OSError("mock fsync failure")

    monkeypatch.setattr(module.os, "fsync", fail)
    with pytest.raises(OSError):
        module.write_new(path, {"status": "complete"})
    assert not path.exists()
    assert path.with_name("metadata.json.partial").exists()


def test_completion_publication_failure_retains_every_capture(setup, monkeypatch):
    plan, _, _, _, calls, _, _, run = setup
    original = module.write_new

    def fail(path, value):
        if path.name == "receipt.json":
            raise OSError("mock publication failure")
        return original(path, value)

    monkeypatch.setattr(module, "write_new", fail)
    with pytest.raises(OSError):
        run()
    assert len(calls) == 3 and all(path.exists() for path in calls)
    output = Path(plan["output_dir"])
    assert not (output / "receipt.json").exists()
    assert json.loads((output / "failure.json").read_text())["status"] == "failed"
    assert json.loads((output / "audit.jsonl").read_text().splitlines()[-1])["status"] == "failed"


def test_cancel_during_pause_leaves_later_assignments_not_started(setup):
    plan, _, _, _, calls, _, _, run = setup

    async def cancel(_):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        run(sleeper=cancel)
    assert len(calls) == 1
    failure = json.loads((Path(plan["output_dir"]) / "failure.json").read_text())
    assert [s["status"] for s in failure["sessions"]] == ["completed", "not_started", "not_started"]


def test_changes_during_pause_cannot_start_next_capture(setup, monkeypatch):
    _, _, _, _, calls, _, _, run = setup

    async def change(_):
        monkeypatch.setattr(module, "_environment", lambda: "changed")

    with pytest.raises(ValueError, match="changed"):
        run(sleeper=change)
    assert len(calls) == 1


def test_duplicate_keys_refused_even_with_matching_pin(setup):
    plan, path, _, _, calls, _, _, _ = setup
    raw = b'{"kind": "one", "kind": "two"}'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Duplicate"):
        asyncio.run(
            module.run_plan(path, hashlib.sha256(raw).hexdigest(), enable_public_capture=True)
        )
    assert not calls and not Path(plan["output_dir"]).exists()


def test_cli_prepare_is_offline_and_records_custom_counts(tmp_path, monkeypatch, capsys):
    path = tmp_path / "cli-plan.json"
    output = tmp_path / "new-output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "planned_capture",
            "prepare",
            "--plan",
            str(path),
            "--output-dir",
            str(output),
            "--campaign-id",
            "cli-test",
            "--train",
            "2",
            "--validation",
            "2",
            "--reserved",
            "1",
        ],
    )
    module.main()
    reported = json.loads(capsys.readouterr().out)
    assert reported["plan_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert [s["split"] for s in reported["sessions"]] == [
        "train",
        "train",
        "validation",
        "validation",
        "reserved",
    ]
    assert not output.exists()


def test_cli_run_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "planned_capture",
            "run",
            "--plan",
            "absent.json",
            "--plan-sha256",
            "a" * 64,
        ],
    )
    with pytest.raises(ValueError, match="opt-in"):
        module.main()
