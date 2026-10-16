"""Versioned campaign telemetry, failure retention and reserved boundaries; no network."""

import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from test_planned_capture import setup as acquisition_setup  # noqa: F401
from test_prospective_trial import guard_raw_opens, rewrite_receipt

from ai_trader.ingestion import planned_capture as module
from ai_trader.models.local_checkpoint import canonical
from ai_trader.research import prospective_trial
from ai_trader.training.microstructure_data import _json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def timed(acquisition_setup):  # noqa: F811
    plan, path, _, clock, calls, pauses, collector, _ = acquisition_setup
    plan.update(schema_version=2, kind=module.TIMED_PLAN_KIND, timing=dict(module.TIMING_CONTRACT))
    path.write_text(canonical(plan) + "\n")
    pin = sha(path)
    observers, invoked = [], []

    async def capture(seconds, *, output_path, limits, **kwargs):
        invoked.append(output_path)
        result = await collector(seconds, output_path=output_path, limits=limits)
        if "reserved" in output_path.name:
            assert not kwargs  # Never instantiate or export reserved telemetry.
        else:
            timing = kwargs["timing"]
            assert type(timing) is module.CaptureTiming
            observers.append(timing)
            timing.claim()
            rows = [json.loads(line) for line in output_path.read_text().splitlines()]
            wall = rows[1]["received_at_ns"]
            timing.snapshot_available(wall, wall)
            timing._observe("event_loop_lag", 0, wall, wall)
            for record in rows[2:-1]:
                wall = record["received_at_ns"]
                timing.receive(wall, wall)
                timing.queued(1)
                timing.consumed(record, wall, wall, wall + 1)
        return result

    async def sleep(seconds):
        pauses.append(seconds)
        clock[0] += seconds * module.NS

    def run(**kwargs):
        options = dict(
            enable_public_capture=True, collector=capture, sleeper=sleep, clock=lambda: clock[0]
        )
        return asyncio.run(module.run_plan(path, pin, **(options | kwargs)))

    def pins():
        output = Path(plan["output_dir"])
        return dict(
            plan_path=path,
            plan_sha256=pin,
            receipt_sha256=sha(output / "receipt.json"),
            audit_sha256=sha(output / "audit.jsonl"),
        )

    return plan, run, capture, pins, observers, invoked, calls


def test_timed_campaign_pins_reports_and_never_observes_reserved(timed, monkeypatch):
    plan, run, _, pins, observers, invoked, _ = timed
    receipt = run()
    assert receipt["schema_version"] == 2 and receipt["kind"] == module.TIMED_RECEIPT_KIND
    assert len(invoked) == 3 and len(observers) == 2 and observers[0] is not observers[1]
    output = Path(plan["output_dir"])
    for item in receipt["sessions"][:2]:
        ref = item["timing"]
        path = output / ref["filename"]
        assert sha(path) == ref["sha256"] and path.stat().st_size == ref["bytes"]
        report = json.loads(path.read_text())["report"]
        assert report["source_sha256"] == item["source"]["source_sha256"]
        assert report["diagnostics"]["processed_events"] == 3
        assert report["authority"] == module.AUTHORITY
    assert receipt["sessions"][-1]["timing"] is None
    assert not (output / module.timing_filename(plan["sessions"][-1])).exists()
    metadata_pins = pins()
    opened = guard_raw_opens(monkeypatch)
    campaign = prospective_trial.load_completed_campaign(**metadata_pins)
    assert len(campaign.research_paths) == 2 and len(campaign.sources) == 3
    assert campaign.sources[-1].role == "reserved"
    assert len(opened) == 6  # Four campaign metadata files plus two research sidecars.
    assert not any("reserved" in name for name in opened)


@pytest.mark.parametrize("value", [1, None, "true"])
def test_non_boolean_timing_refuses_before_output(tmp_path, value):
    with pytest.raises(ValueError, match="boolean"):
        module.prepare_plan(campaign_id="bad", output_dir=tmp_path / "out", research_timing=value)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("fault", ["scope", "period", "cap", "extra", "missing", "v1", "kind"])
def test_timing_contract_is_frozen(timed, fault):
    plan = copy.deepcopy(timed[0])
    if fault == "scope":
        plan["timing"]["scope"] = "all_sessions"
    elif fault == "period":
        plan["timing"]["timer_period_ns"] = 1
    elif fault == "cap":
        plan["timing"]["max_report_bytes"] += 1
    elif fault == "extra":
        plan["timing"]["retry"] = True
    elif fault == "missing":
        del plan["timing"]
    elif fault == "v1":
        plan.update(schema_version=1, kind=module.PLAN_KIND)
    else:
        plan["kind"] = module.PLAN_KIND
    with pytest.raises(ValueError):
        module.validate_plan(plan)


@pytest.mark.parametrize("failure", ["exception", "cancel", "counters", "integrity", "drift"])
def test_failed_slot_keeps_diagnostics_and_never_retries(timed, monkeypatch, failure):
    plan, run, capture, _, observers, invoked, _ = timed

    async def broken(seconds, **kwargs):
        if failure == "exception":
            invoked.append(kwargs["output_path"])
            raise OSError("private packet must not leak")
        if failure == "cancel":
            invoked.append(kwargs["output_path"])
            raise asyncio.CancelledError("private packet must not leak")
        result = await capture(seconds, **kwargs)
        if failure == "counters":
            observers[-1].received += 1
        elif failure == "integrity":
            result[0].write_text("private packet must not leak")
        else:
            monkeypatch.setattr(module, "_environment", lambda: "changed")
        return result

    with pytest.raises((Exception, asyncio.CancelledError)):
        run(collector=broken)
    output = Path(plan["output_dir"])
    assert len(invoked) == 1 and not (output / "receipt.json").exists()
    report = json.loads((output / module.timing_filename(plan["sessions"][0])).read_text())[
        "report"
    ]
    assert report["status"] == "failed" and report["source_sha256"] is None
    assert report["error_type"] and "private packet" not in canonical(report)
    failure_record = json.loads((output / "failure.json").read_text())
    assert [s["status"] for s in failure_record["sessions"]] == [
        "failed",
        "not_started",
        "not_started",
    ]
    assert "private packet" not in canonical(failure_record)


@pytest.mark.parametrize("failure", ["publication", "partial"])
def test_diagnostic_publication_failure_quarantines_whole_campaign(timed, monkeypatch, failure):
    plan, run, _, _, _, invoked, _ = timed
    original = module._publish

    def publish(report, path, **kwargs):
        if failure == "publication":
            raise OSError("mock disk failure")
        original(report, path, **kwargs)
        path.with_name(path.name + ".partial").write_bytes(b"retained")

    monkeypatch.setattr(module, "_publish", publish)
    with pytest.raises((OSError, ValueError)):
        run()
    output = Path(plan["output_dir"])
    assert len(invoked) == 1 and invoked[0].exists()
    assert (output / "failure.json").exists() and not (output / "receipt.json").exists()
    with pytest.raises(FileExistsError):
        run()


def rewrite_report(plan, pins, mutation):
    output = Path(plan["output_dir"])
    path = output / module.timing_filename(plan["sessions"][0])
    envelope = json.loads(path.read_text())
    mutation(envelope["report"])
    envelope["report_sha256"] = hashlib.sha256(_json(envelope["report"]).encode()).hexdigest()
    path.write_text(_json(envelope) + "\n")
    rewrite_receipt(
        plan,
        pins,
        lambda r: r["sessions"][0]["timing"].update(sha256=sha(path), bytes=path.stat().st_size),
    )


@pytest.mark.parametrize(
    "fault", ["role", "source", "plan", "status", "error", "authority", "count", "bool", "probe"]
)
def test_self_consistently_repinned_bad_report_refused(timed, monkeypatch, fault):
    plan, run, _, pins, _, _, _ = timed
    run()
    metadata_pins = pins()

    def mutate(report):
        if fault == "role":
            report["split"] = "reserved"
        elif fault == "source":
            report["source_sha256"] = "b" * 64
        elif fault == "plan":
            report["plan_sha256"] = "b" * 64
        elif fault == "status":
            report["status"] = "failed"
        elif fault == "error":
            report["error_type"] = "ValueError"
        elif fault == "authority":
            report["authority"]["training_allowed"] = True
        elif fault == "count":
            report["diagnostics"]["processed_events"] += 1
        elif fault == "bool":
            report["diagnostics"]["queue_high_water"] = True
        else:
            report["diagnostics"]["metrics"]["event_loop_lag"]["count"] = 0

    rewrite_report(plan, metadata_pins, mutate)
    guard_raw_opens(monkeypatch)
    with pytest.raises(ValueError):
        prospective_trial.load_completed_campaign(**metadata_pins)


@pytest.mark.parametrize(
    "fault", ["absent", "partial", "tampered", "oversize", "filename", "bytes", "envelope", "pin"]
)
def test_missing_or_misbound_research_report_refused(timed, monkeypatch, fault):
    plan, run, _, pins, _, _, _ = timed
    run()
    metadata_pins = pins()
    output = Path(plan["output_dir"])
    path = output / module.timing_filename(plan["sessions"][0])
    if fault == "absent":
        path.rename(path.with_name("retained-report.json"))
    elif fault == "partial":
        path.with_name(path.name + ".partial").write_bytes(b"retained")
    elif fault == "tampered":
        path.write_bytes(path.read_bytes() + b" ")
    elif fault == "oversize":
        path.write_bytes(b" " * (module.MAX_REPORT_BYTES + 1))
    elif fault in ("filename", "bytes", "pin"):

        def change(receipt):
            receipt["sessions"][0]["timing"].update(
                {"filename": "../elsewhere.json", "bytes": 1, "sha256": "b" * 64}
                if fault == "filename"
                else {
                    "bytes" if fault == "bytes" else "sha256": 1 if fault == "bytes" else "b" * 64
                }
            )

        rewrite_receipt(plan, metadata_pins, change)
    else:
        envelope = json.loads(path.read_text())
        envelope["report_sha256"] = "b" * 64
        path.write_text(_json(envelope))
        rewrite_receipt(
            plan,
            metadata_pins,
            lambda r: r["sessions"][0]["timing"].update(
                sha256=sha(path), bytes=path.stat().st_size
            ),
        )
    guard_raw_opens(monkeypatch)
    with pytest.raises(ValueError):
        prospective_trial.load_completed_campaign(**metadata_pins)


@pytest.mark.parametrize("fault", ["file", "reference", "partial"])
def test_reserved_timing_refused_without_opening_it(timed, monkeypatch, fault):
    plan, run, _, pins, _, _, _ = timed
    run()
    metadata_pins = pins()
    path = Path(plan["output_dir"]) / module.timing_filename(plan["sessions"][-1])
    if fault == "reference":
        rewrite_receipt(plan, metadata_pins, lambda r: r["sessions"][-1].update(timing={}))
    else:
        if fault == "partial":
            path = path.with_name(path.name + ".partial")
        path.write_text("must not open")
    original = Path.open

    def guard(self, *args, **kwargs):
        assert "reserved" not in self.name
        assert self.suffix != ".jsonl" or self.name == "audit.jsonl"
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    with pytest.raises(ValueError):
        prospective_trial.load_completed_campaign(**metadata_pins)


def test_cli_freezes_research_timing_before_any_capture(tmp_path, monkeypatch, capsys):
    path, output = tmp_path / "plan.json", tmp_path / "new"
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
            "cli-timed",
            "--research-timing",
            "--seconds-per-session",
            "120",
        ],
    )
    module.main()
    result = json.loads(capsys.readouterr().out)
    plan = json.loads(path.read_text())
    assert sha(path) == result["plan_sha256"] and not output.exists()
    assert plan["schema_version"] == 2 and plan["timing"] == module.TIMING_CONTRACT
    assert plan["seconds_per_session"] == 120


def test_longer_trial_changes_only_frame_budget_and_identity():
    configs = Path(__file__).resolve().parents[1] / "configs"
    old = json.loads((configs / "prospective_event_trial_v1.json").read_text())
    new = json.loads((configs / "prospective_event_trial_120s_v1.json").read_text())
    assert new["fold"]["max_frames_per_session"] == 5000
    assert new["trial_id"] == "btcusdt-prospective-events-120s-v1"
    new["trial_id"] = old["trial_id"]
    new["fold"]["max_frames_per_session"] = old["fold"]["max_frames_per_session"]
    assert new == old


def test_timed_campaign_prepares_unchanged_training_gates(timed, tmp_path, monkeypatch):
    plan, run, _, pins, _, _, _ = timed
    run()
    metadata_pins = pins()
    settings = Path(__file__).resolve().parents[1] / "configs/prospective_event_trial_120s_v1.json"
    settings_pin = sha(settings)
    guard_raw_opens(monkeypatch)
    prepared = prospective_trial.prepare_campaign_trial(
        **metadata_pins,
        settings_path=settings,
        settings_sha256=settings_pin,
        output_dir=tmp_path / "research",
    )
    assert prepared["raw_captures_opened"] == 0 and prepared["authority"] == module.AUTHORITY
    manifest = json.loads((tmp_path / "research/split.json").read_text())["manifest"]
    assert manifest["train_sessions"] == [plan["sessions"][0]["source_session"]]
    assert manifest["validation_sessions"] == [plan["sessions"][1]["source_session"]]
    assert manifest["reserved_sessions"] == [plan["sessions"][2]["source_session"]]
    assert manifest["max_frames_per_session"] == 5000
