"""Window receipt intake uses metadata only and cannot retune the frozen recipe."""

import copy
import json

import pytest
from test_capture_schedule import prepared, sha  # noqa: F401
from test_prospective_trial import guard_raw_opens
from test_windowed_capture import runtime as runtime_fixture  # noqa: F401

from ai_trader.models.local_checkpoint import canonical
from ai_trader.research import windowed_trial as module
from ai_trader.research.microstructure_trial import load_registration
from ai_trader.research.prospective_trial import load_completed_campaign


@pytest.fixture
def acquired(runtime_fixture):  # noqa: F811
    runtime = runtime_fixture
    runtime["run"]()
    pins = dict(
        schedule_path=runtime["path"],
        schedule_sha256=runtime["pin"],
        receipt_sha256=sha(runtime["output"] / "receipt.json"),
        audit_sha256=sha(runtime["output"] / "audit.jsonl"),
    )
    return runtime, pins


def repin_receipt(runtime, pins, change):
    path = runtime["output"] / "receipt.json"
    receipt = json.loads(path.read_bytes())
    change(receipt)
    path.write_text(canonical(receipt) + "\n")
    pins["receipt_sha256"] = sha(path)
    path = runtime["output"] / "audit.jsonl"
    audit = [json.loads(line) for line in path.read_text().splitlines()]
    for i, item in enumerate(receipt["sessions"]):
        audit[3 + 3 * i]["session"] = copy.deepcopy(item)
        evidence = item.get("window_evidence", {})
        audit[2 + 3 * i].update({k: v for k, v in evidence.items() if k != "intent_at_ns"})
    audit[-1]["receipt_sha256"] = pins["receipt_sha256"]
    path.write_text("".join(canonical(r) + "\n" for r in audit))
    pins["audit_sha256"] = sha(path)


def test_load_reads_only_declared_metadata_and_research_sidecars(acquired, monkeypatch):
    runtime, pins = acquired
    opened = guard_raw_opens(monkeypatch)
    result = module.load_completed_schedule(**pins)
    assert result.campaign.training_session_count == 1
    assert [s.role for s in result.campaign.sources] == ["research", "research", "reserved"]
    assert len(result.campaign.research_paths) == 2
    assert result.research_settings_json == runtime["schedule"]["research_settings_json"]
    assert result.research_settings_sha256 == runtime["schedule"]["research_settings_sha256"]
    assert len(opened) == 6
    assert all("reserved" not in name for name in opened)


def test_prepare_uses_embedded_settings_not_the_changed_external_file(
    acquired, tmp_path, monkeypatch
):
    runtime, pins = acquired
    raw_before = {p: p.read_bytes() for p in runtime["output"].iterdir()}
    runtime["args"]["settings_path"].write_text("settings no longer available")
    guard_raw_opens(monkeypatch)
    output = tmp_path / "research"
    report = module.prepare_windowed_trial(**pins, output_dir=output)
    assert report["raw_captures_opened"] == 0
    assert report["settings_sha256"] == runtime["schedule"]["research_settings_sha256"]
    assert report["kind"] == "windowed_research_preparation_v1"
    assert report["schedule_sha256"] == pins["schedule_sha256"]
    assert report["authority"] == module.AUTHORITY
    record = load_registration(output / "registration.json")
    assert str(record.gateway.costs.taker_fee_bps) == "10"
    assert str(record.gateway.costs.slippage_bps) == "2"
    assert record.policy.maximum_hold_ns == 10_000_000_000
    assert record.implementation_sha256 != report["acquisition_implementation_sha256"]
    assert record.sources == module.load_completed_schedule(**pins).campaign.sources
    manifest = json.loads((output / "split.json").read_text())["manifest"]
    assert manifest["train_sessions"] == [runtime["schedule"]["windows"][0]["source_session"]]
    assert manifest["reserved_sessions"] == [runtime["schedule"]["windows"][-1]["source_session"]]
    with pytest.raises(ValueError, match="research session"):
        record.research_source(record.sources[-1].source_session)
    with pytest.raises(FileExistsError):
        module.prepare_windowed_trial(**pins, output_dir=output)
    monkeypatch.undo()
    assert raw_before == {p: p.read_bytes() for p in runtime["output"].iterdir()}


def test_old_intake_cannot_downgrade_the_window_receipt(acquired):
    _, pins = acquired
    with pytest.raises(ValueError):
        load_completed_campaign(
            plan_path=pins["schedule_path"],
            plan_sha256=pins["schedule_sha256"],
            receipt_sha256=pins["receipt_sha256"],
            audit_sha256=pins["audit_sha256"],
        )


@pytest.mark.parametrize("key", ["schedule_sha256", "receipt_sha256", "audit_sha256"])
def test_wrong_external_pin_prevents_new_research_output(acquired, tmp_path, key):
    _, pins = acquired
    pins[key] = "b" * 64
    with pytest.raises(ValueError):
        module.prepare_windowed_trial(**pins, output_dir=tmp_path / "not-created")
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(status="failed"),
        lambda r: r.update(orders=1),
        lambda r: r.update(clock_origin_wall_ns=True),
        lambda r: r["authority"].update(training_allowed=True),
        lambda r: r["sessions"].pop(),
        lambda r: r["sessions"].reverse(),
        lambda r: r["sessions"][0].update(status="failed"),
        lambda r: r["sessions"][0].update(split="validation"),
        lambda r: r["sessions"][0]["source"].update(role="reserved"),
        lambda r: r["sessions"][0]["window_evidence"].update(dispatched_at_ns=1),
        lambda r: r["sessions"][0]["window_evidence"].update(dispatched_at_ns=True),
        lambda r: r["sessions"][0]["window_evidence"].update(dispatch_elapsed_ns=0),
        lambda r: r["sessions"][0]["window_evidence"].update(connected_elapsed_ns=999_999_999_999),
        lambda r: r["sessions"][0]["window_evidence"].update(started_at_ns=1),
        lambda r: r["sessions"][0].update(trade_events=999_998),
        lambda r: r["sessions"][0].update(bytes=True),
        lambda r: r["sessions"][0].update(snapshot_received_at_ns=1),
        lambda r: r["sessions"][-1].update(timing={}),
    ],
)
def test_self_rehashed_receipt_inconsistencies_fail(acquired, change):
    runtime, pins = acquired
    repin_receipt(runtime, pins, change)
    with pytest.raises(ValueError):
        module.load_completed_schedule(**pins)


@pytest.mark.parametrize(
    "change",
    [
        lambda a: a.pop(2),
        lambda a: a.insert(2, a[2]),
        lambda a: a[2].update(elapsed_ns=0),
        lambda a: a[1].update(elapsed_ns=0),
        lambda a: a[2].update(at_ns=0),
        lambda a: a[1].update(status="retry"),
        lambda a: a[-1].update(receipt_sha256="b" * 64),
        lambda a: a[0].update(extra="unknown"),
    ],
)
def test_rehashed_audit_cannot_omit_guard_or_add_retry(acquired, change):
    runtime, pins = acquired
    path = runtime["output"] / "audit.jsonl"
    audit = [json.loads(line) for line in path.read_text().splitlines()]
    change(audit)
    path.write_text("".join(canonical(r) + "\n" for r in audit))
    pins["audit_sha256"] = sha(path)
    with pytest.raises(ValueError):
        module.load_completed_schedule(**pins)


@pytest.mark.parametrize(
    "filename", ["failure.json", "receipt.json.partial", "schedule.json.partial", "plan.json"]
)
def test_failed_or_ambiguous_publication_is_not_a_successful_subset(acquired, filename):
    runtime, pins = acquired
    (runtime["output"] / filename).write_text("quarantined")
    with pytest.raises(ValueError, match="quarantined"):
        module.load_completed_schedule(**pins)


def test_reserved_sidecar_is_refused_without_opening_it(acquired, monkeypatch):
    runtime, pins = acquired
    name = runtime["schedule"]["windows"][-1]["filename"] + ".timing.json"
    (runtime["output"] / name).write_text("do not read")
    opened = guard_raw_opens(monkeypatch)
    with pytest.raises(ValueError, match="Reserved timing"):
        module.load_completed_schedule(**pins)
    assert name not in opened
