"""Metadata intake, original-role preservation and no raw/reserved access."""

import copy
import hashlib
import json
import socket
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from test_planned_capture import setup as acquisition_setup  # noqa: F401

from ai_trader.models.local_checkpoint import canonical
from ai_trader.research import prospective_trial as module
from ai_trader.research.microstructure_trial import load_registration

SETTINGS = Path(__file__).resolve().parents[1] / "configs/prospective_event_trial_v1.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def captured(acquisition_setup, tmp_path, monkeypatch):  # noqa: F811
    plan, plan_path, plan_pin, clock, _, _, _, run = acquisition_setup
    run()
    output = Path(plan["output_dir"])

    def forbid_network(*args, **kwargs):
        pytest.fail("Metadata preparation must be offline.")

    monkeypatch.setattr(socket, "create_connection", forbid_network)
    settings_path = tmp_path / "settings.json"
    settings_path.write_bytes(SETTINGS.read_bytes())
    pins = dict(
        plan_path=plan_path,
        plan_sha256=plan_pin,
        receipt_sha256=sha(output / "receipt.json"),
        audit_sha256=sha(output / "audit.jsonl"),
    )
    prepare = dict(
        **pins,
        settings_path=settings_path,
        settings_sha256=sha(settings_path),
        output_dir=tmp_path / "research",
    )
    return plan, pins, prepare, clock


def guard_raw_opens(monkeypatch):
    original = Path.open
    opened = []

    def guarded(self, *args, **kwargs):
        if self.suffix == ".jsonl" and self.name != "audit.jsonl":
            pytest.fail("Raw market capture opened during metadata-only preparation.")
        opened.append(self.name)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    return opened


def rewrite_receipt(plan, pins, change):
    """Re-pin a mutation, so validation cannot rely on checksums alone."""
    root = Path(plan["output_dir"])
    receipt_path = root / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    change(receipt)
    receipt_path.write_text(canonical(receipt) + "\n")
    pins["receipt_sha256"] = sha(receipt_path)
    # Update audit completion contents and receipt pin to match a self-consistent mutation.
    audit_path = root / "audit.jsonl"
    audit = [json.loads(line) for line in audit_path.read_text().splitlines()]
    for index, item in enumerate(receipt["sessions"]):
        if 2 + 2 * index < len(audit) - 1:
            audit[2 + 2 * index]["session"] = copy.deepcopy(item)
    audit[-1]["receipt_sha256"] = pins["receipt_sha256"]
    audit_path.write_text("".join(canonical(row) + "\n" for row in audit))
    pins["audit_sha256"] = sha(audit_path)


def test_metadata_load_preserves_original_assignments_without_raw_opens(captured, monkeypatch):
    plan, pins, _, _ = captured
    opened = guard_raw_opens(monkeypatch)
    result = module.load_completed_campaign(**pins)
    assert result.training_session_count == 1
    assert len(result.sources) == 3 and len(result.research_paths) == 2
    assert [s.role for s in result.sources] == ["research", "research", "reserved"]
    assert [s.source_session for s in result.sources] == [
        s["source_session"] for s in plan["sessions"]
    ]
    assert result.acquisition_implementation_sha256 == "a" * 64
    assert set(opened) == {"plan.json", "receipt.json", "audit.jsonl"}
    with pytest.raises(FrozenInstanceError):
        result.training_session_count = 2


def test_prepare_freezes_new_research_binding_and_original_metadata(captured, monkeypatch):
    plan, pins, args, _ = captured
    root = Path(plan["output_dir"])
    before = {
        p.name: p.read_bytes()
        for p in (root / "plan.json", root / "receipt.json", root / "audit.jsonl")
    }
    guard_raw_opens(monkeypatch)
    result = module.prepare_campaign_trial(**args)
    output = args["output_dir"]
    assert result["authority"] == module.AUTHORITY and result["raw_captures_opened"] == 0
    assert result["acquisition_implementation_sha256"] == "a" * 64
    assert result["research_implementation_sha256"] == module._implementation_hash()
    assert result["research_implementation_sha256"] != result["acquisition_implementation_sha256"]
    record = load_registration(output / "registration.json")
    assert record.sources == module.load_completed_campaign(**pins).sources
    manifest = json.loads((output / "split.json").read_text())["manifest"]
    assert manifest["train_sessions"] == [plan["sessions"][0]["source_session"]]
    assert manifest["validation_sessions"] == [plan["sessions"][1]["source_session"]]
    assert manifest["reserved_sessions"] == [plan["sessions"][2]["source_session"]]
    for name, pin in result["artifacts"].items():
        assert sha(output / name) == pin
    for name, raw in before.items():
        assert (root / name).read_bytes() == raw
    with pytest.raises(FileExistsError):
        module.prepare_campaign_trial(**args)
    with pytest.raises(ValueError, match="research"):
        record.research_source(record.sources[-1].source_session)


@pytest.mark.parametrize("pin", ["plan_sha256", "receipt_sha256", "audit_sha256"])
def test_wrong_pin_refuses_before_preparation(captured, pin):
    _, _, args, _ = captured
    args[pin] = "b" * 64
    with pytest.raises(ValueError, match="SHA256"):
        module.prepare_campaign_trial(**args)
    assert not args["output_dir"].exists()


@pytest.mark.parametrize(
    "fault",
    [
        "status",
        "schema_bool",
        "authority",
        "orders_bool",
        "trained",
        "extra",
        "missing",
        "reorder",
        "source_role",
        "source_alias",
        "split",
        "filename",
        "snapshot",
        "old",
        "duration",
        "counts_bool",
        "counts_overflow",
        "bytes",
        "source_id",
        "extra_source",
    ],
)
def test_self_consistent_but_invalid_receipts_fail(captured, fault):
    plan, pins, args, _ = captured

    def change(receipt):
        item = receipt["sessions"][0]
        if fault == "status":
            receipt["status"] = "failed"
        elif fault == "schema_bool":
            receipt["schema_version"] = True
        elif fault == "authority":
            receipt["authority"]["training_allowed"] = True
        elif fault == "orders_bool":
            receipt["orders"] = False
        elif fault == "trained":
            receipt["optimization_steps"] = 1
        elif fault == "extra":
            receipt["retry_allowed"] = True
        elif fault == "missing":
            receipt["sessions"].pop()
        elif fault == "reorder":
            receipt["sessions"].reverse()
        elif fault == "source_role":
            receipt["sessions"][-1]["source"]["role"] = "research"
        elif fault == "source_alias":
            receipt["sessions"][-1]["source"]["source_sha256"] = item["source"]["source_sha256"]
        elif fault == "split":
            item["split"] = "validation"
        elif fault == "filename":
            item["filename"] = "../unexpected.jsonl"
        elif fault == "snapshot":
            item["snapshot_received_at_ns"] = item["source"]["ended_at_ns"] + 1
        elif fault == "old":
            item["source"]["started_at_ns"] = plan["prepared_at_ns"]
        elif fault == "duration":
            item["source"]["ended_at_ns"] = item["source"]["started_at_ns"] + module.NS
        elif fault == "counts_bool":
            item["trade_events"] = True
        elif fault == "counts_overflow":
            item["trade_events"] = module.DEFAULT_LIMITS.max_events
        elif fault == "bytes":
            item["bytes"] = 0
        elif fault == "source_id":
            item["source"]["source_session"] = "renamed"
        else:
            item["source"]["extra"] = "bad"

    rewrite_receipt(plan, pins, change)
    with pytest.raises(ValueError):
        module.prepare_campaign_trial(**(args | pins))
    assert not args["output_dir"].exists()


@pytest.mark.parametrize(
    "fault",
    ["intent", "completion", "regression", "future", "missing", "duplicate", "terminal", "payload"],
)
def test_audit_tampering_refused_even_when_repinned(captured, fault):
    plan, pins, _, clock = captured
    path = Path(plan["output_dir"]) / "audit.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if fault == "intent":
        rows[1]["at_ns"] = rows[2]["session"]["source"]["started_at_ns"]
    elif fault == "completion":
        rows[2]["at_ns"] = rows[1]["at_ns"]
    elif fault == "regression":
        rows[3]["at_ns"] = rows[1]["at_ns"]
    elif fault == "future":
        rows[-1]["at_ns"] = clock[0] + 1
    elif fault == "missing":
        rows.pop(2)
    elif fault == "duplicate":
        rows.insert(2, rows[1])
    elif fault == "terminal":
        rows[-1]["receipt_sha256"] = "b" * 64
    else:
        rows[2]["session"]["trade_events"] += 1
    path.write_text("".join(canonical(row) + "\n" for row in rows))
    pins["audit_sha256"] = sha(path)
    with pytest.raises(ValueError):
        module.load_completed_campaign(**pins)


@pytest.mark.parametrize(
    "filename",
    [
        "failure.json",
        "failure.json.partial",
        "receipt.json.partial",
        "plan.json.partial",
        "raw_partial",
    ],
)
def test_incomplete_publication_not_accepted(captured, filename):
    plan, pins, _, _ = captured
    if filename == "raw_partial":
        filename = plan["sessions"][-1]["filename"] + ".partial"
    (Path(plan["output_dir"]) / filename).write_bytes(b"retained")
    with pytest.raises(ValueError, match="quarantined"):
        module.load_completed_campaign(**pins)


@pytest.mark.parametrize(
    "fault", ["split_override", "embargo", "frames", "epochs", "lr", "fee", "missing_field"]
)
def test_invalid_settings_fail_before_output_or_capture_access(captured, monkeypatch, fault):
    _, _, args, _ = captured
    path = args["settings_path"]
    settings = json.loads(path.read_text())
    if fault == "split_override":
        settings["fold"]["training_session_count"] = 2
    elif fault == "embargo":
        settings["fold"]["embargo_ns"] = 100 * module.NS
    elif fault == "frames":
        settings["fold"]["max_frames_per_session"] = 6000
    elif fault == "epochs":
        settings["baseline"]["epochs"] = 1000
    elif fault == "lr":
        settings["baseline"]["learning_rate"] = "NaN"
    elif fault == "fee":
        settings["gateway"]["costs"]["taker_fee_bps"] = "-1"
    else:
        del settings["policy"]["rule"]
    path.write_text(canonical(settings) + "\n")
    args["settings_sha256"] = sha(path)
    guard_raw_opens(monkeypatch)
    with pytest.raises(ValueError):
        module.prepare_campaign_trial(**args)
    assert not args["output_dir"].exists()


def test_metadata_size_and_duplicate_keys_refused(tmp_path):
    path = tmp_path / "metadata.json"
    path.write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(ValueError, match="budget"):
        module._pinned_bytes(path, sha(path))
    path.write_bytes(b'{"schema_version":1,"schema_version":1}')
    with pytest.raises(ValueError, match="Duplicate"):
        module.load_completed_campaign(
            plan_path=path, plan_sha256=sha(path), receipt_sha256="a" * 64, audit_sha256="a" * 64
        )


def test_prepare_failure_has_no_success_marker_and_does_not_resume(captured, monkeypatch):
    _, _, args, _ = captured

    def fail(**kwargs):
        raise OSError("mock publication failure")

    monkeypatch.setattr(module, "register_event_split", fail)
    with pytest.raises(OSError):
        module.prepare_campaign_trial(**args)
    assert (args["output_dir"] / "preparation_intent.json").exists()
    assert not (args["output_dir"] / "prepared.json").exists()
    with pytest.raises(FileExistsError):
        module.prepare_campaign_trial(**args)


def test_training_and_model_calls_are_not_part_of_preparation(captured, monkeypatch):
    from ai_trader.training import train_event_baseline

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata preparation attempted fitting.")

    monkeypatch.setattr(train_event_baseline, "_fit", forbidden)
    result = module.prepare_campaign_trial(**captured[2])
    assert result["authority"]["training_allowed"] is False


@pytest.mark.parametrize("binding", ["_implementation_hash", "_environment"])
def test_final_preparation_check_refuses_drift(captured, monkeypatch, binding):
    original = module.register_event_baseline

    def change(**kwargs):
        result = original(**kwargs)
        monkeypatch.setattr(module, binding, lambda: "b" * 64)
        return result

    monkeypatch.setattr(module, "register_event_baseline", change)
    args = captured[2]
    with pytest.raises(ValueError, match="changed"):
        module.prepare_campaign_trial(**args)
    assert not (args["output_dir"] / "prepared.json").exists()


def test_plan_copy_must_match_original_even_if_repinned(captured):
    plan, pins, _, _ = captured
    path = Path(plan["output_dir"]) / "plan.json"
    copy_plan = json.loads(path.read_text())
    copy_plan["campaign_id"] = "different"
    path.write_text(canonical(copy_plan) + "\n")
    rewrite_receipt(plan, pins, lambda r: r.update(plan_copy_sha256=sha(path)))
    with pytest.raises(ValueError, match="copy"):
        module.load_completed_campaign(**pins)


def test_cli_prepares_only_metadata(captured, monkeypatch, capsys):
    _, _, args, _ = captured
    argv = ["prospective_trial"]
    for name, value in args.items():
        option = {"plan_path": "plan", "settings_path": "settings"}.get(name, name)
        argv.extend(["--" + option.replace("_", "-"), str(value)])
    monkeypatch.setattr("sys.argv", argv)
    guard_raw_opens(monkeypatch)
    module.main()
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"
