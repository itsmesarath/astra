"""Synthetic pinned-artifact audits; no market data, models, network or training."""

import hashlib
import json
import socket
import sys
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from test_event_training_data import setup as setup_fold
from test_event_training_data import tamper
from test_microstructure_campaign import shifted
from test_microstructure_data import rows_with_quote

from ai_trader.research import event_corpus_audit as module
from ai_trader.research import microstructure_trial
from ai_trader.training import event_training_data, microstructure_data, train_event_baseline

D = Decimal


def pin(path):
    return module.PinnedArtifact(path, hashlib.sha256(path.read_bytes()).hexdigest())


def setup(tmp_path, *, mixed=False, **settings):
    captures = None
    if mixed:
        captures = [
            rows_with_quote(),
            shifted(rows_with_quote(bid="101.2", ask="101.21")),
            shifted(rows_with_quote(), ms=2000),
        ]
        settings["training_session_count"] = 2
    args, record, split = setup_fold(tmp_path, captures=captures, **settings)
    audit = dict(
        registration=pin(args["registration_path"]),
        manifest=pin(args["manifest_path"]),
        training=tuple(
            module.TrainingArtifact(s.source_session, pin(s.dataset_path))
            for s in args["sources"][: split["training_session_count"]]
        ),
    )
    return audit, args, record


@pytest.fixture(autouse=True)
def no_side_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Audit attempted network/model fitting.")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(train_event_baseline, "_fit", forbidden)


def test_one_class_report_is_not_training_authority_and_preserves_inputs(tmp_path):
    args, _, record = setup(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    report = module.audit_event_corpus(**args, output_path=tmp_path / "audit.json")
    assert all(p.read_bytes() == raw for p, raw in before.items())
    summary = report["training_summary"]
    assert summary["observed_classes"] == 1
    assert summary["class_counts_loss_breakeven_profit"] == [summary["resolved_rows"], 0, 0]
    assert report["observed_training_blockers"] == ["insufficient_training_classes"]
    assert report["historical_implementation_sha256"] == record.implementation_sha256
    assert report["raw_captures_opened"] == report["validation_datasets_opened"] == 0
    assert report["reserved_datasets_opened"] == 0
    assert report["training_allowed"] is report["training_started"] is False
    assert report["promotion_allowed"] is report["live_trading_available"] is False
    saved = json.loads((tmp_path / "audit.json").read_bytes())
    assert saved == {"report": report, "report_sha256": module._hash(module._json(report))}
    assert "examples" not in module._json(report)


def test_only_explicit_training_and_metadata_files_are_opened(tmp_path, monkeypatch):
    args, fold, record = setup(tmp_path, mixed=True)
    allowed = {
        args["registration"].path,
        args["manifest"].path,
        *(t.artifact.path for t in args["training"]),
    }
    for source in fold["sources"]:
        source.capture_path.unlink()
    fold["sources"][-1].dataset_path.unlink()
    original_open, opened = Path.open, []

    def guarded(path, *a, **kw):
        assert path in allowed, f"Unexpected artifact read: {path}"
        opened.append(path)
        return original_open(path, *a, **kw)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(module, "_environment", lambda: record.environment_json)
    report = module.audit_event_corpus(**args)
    assert opened == [
        args["registration"].path,
        args["manifest"].path,
        *(t.artifact.path for t in args["training"]),
    ]
    assert report["training_summary"]["observed_classes"] == 2
    assert report["observed_training_blockers"] == []
    assert report["readiness"] == "not_established_by_descriptive_audit"
    assert not report["training_allowed"]


@pytest.mark.parametrize(
    "bad", ["reserved", "research-1", "unknown", "duplicate", "missing", "reordered"]
)
def test_scope_rejection_precedes_any_dataset_read(tmp_path, monkeypatch, bad):
    args, _, _ = setup(tmp_path, mixed=True)
    items = args["training"]
    if bad == "duplicate":
        items = (items[0], items[0])
    elif bad == "missing":
        items = items[:1]
    elif bad == "reordered":
        items = tuple(reversed(items))
    else:
        items = (replace(items[0], source_session=bad), items[1])
    original = module._read

    def guarded(pinned, name, limit):
        assert name != "dataset", "Out-of-scope dataset was opened"
        return original(pinned, name, limit)

    monkeypatch.setattr(module, "_read", guarded)
    with pytest.raises(ValueError, match="exactly every training"):
        module.audit_event_corpus(**(args | {"training": items}))


def test_historical_audit_does_not_relax_existing_training_code_guard(tmp_path, monkeypatch):
    args, fold, record = setup(tmp_path)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(microstructure_trial, "_implementation_hash", lambda: "a" * 64)
    monkeypatch.setattr(module, "_environment", lambda: "audit-environment")
    report = module.audit_event_corpus(**args)
    assert report["historical_implementation_sha256"] == record.implementation_sha256
    assert report["audit_implementation_sha256"] == "a" * 64
    assert report["historical_environment_json"] == record.environment_json
    assert report["audit_environment_json"] == "audit-environment"
    with pytest.raises(ValueError, match="changed after registration"):
        event_training_data.load_event_split(**fold)
    with pytest.raises(ValueError, match="changed after registration"):
        microstructure_data.build_registered_event_dataset(
            registration_path=fold["registration_path"],
            source_session="research-0",
            capture_path=fold["sources"][0].capture_path,
            max_frames=100,
        )


def test_fixed_costs_and_training_only_return_math(tmp_path):
    args, _, record = setup(tmp_path, mixed=True)
    report = module.audit_event_corpus(**args)
    with localcontext(module.DECIMAL_CONTEXT):
        fee, slip = (
            record.gateway.costs.taker_fee_bps / 10000,
            record.gateway.costs.slippage_bps / 10000,
        )
        expected = (((1 + slip) * (1 + fee)) / ((1 - slip) * (1 - fee)) - 1) * 10000
        assert D(report["break_even_exit_bid_over_entry_ask_return_bps"]) == expected
        net, pre_fee, quote = [], [], []
        for selected in args["training"]:
            dataset = json.loads(selected.artifact.path.read_bytes())["dataset"]
            for row in dataset["examples"]:
                outcome = row["outcome"]
                if outcome["status"] == "resolved":
                    entry, exit_price = (
                        D(outcome["entry_price_usdt"]),
                        D(outcome["exit_price_usdt"]),
                    )
                    net.append(
                        (exit_price * (1 - fee) - entry * (1 + fee)) / (entry * (1 + fee)) * 10000
                    )
                    pre_fee.append((exit_price / entry - 1) * 10000)
                    quote.append((exit_price / entry * (1 + slip) / (1 - slip) - 1) * 10000)
        summary = report["training_summary"]
        assert summary["net_return_bps"] == module._stats(net)
        assert summary["slipped_exit_over_entry_return_bps_before_fees"] == module._stats(pre_fee)
        assert summary["inferred_exit_bid_over_entry_ask_return_bps_before_costs"] == module._stats(
            quote
        )
    with localcontext() as context:
        context.prec = 6
        assert module.audit_event_corpus(**args) == report


def test_nonoverlapping_intervals_are_a_count_not_a_row_selector():
    rows = [
        dict(
            feature_available_at_ns=start,
            outcome=dict(
                entry_price_usdt="100",
                exit_price_usdt="100",
                net_return_fraction="0",
                direction=0,
                known_at_ns=end,
                reason="horizon",
            ),
        )
        for start, end in [(0, 10), (1, 5), (5, 7), (6, 8), (9, 12)]
    ]
    description = module._describe(rows, D(0))
    assert description["resolved_rows"] == 5
    assert description["maximum_nonoverlapping_label_intervals"] == 3
    assert description["class_counts_loss_breakeven_profit"] == [0, 5, 0]


def test_quality_failure_report_retains_all_rows_and_reason_counts(tmp_path):
    args, _, _ = setup(tmp_path, minimum_resolved_per_session=99)
    report = module.audit_event_corpus(**args)
    assert "training_artifact_quality_failure" in report["observed_training_blockers"]
    assert report["training_summary"]["resolved_rows"] > 0
    quality = report["training_sources"][0]["quality_from_artifact_not_replay"]
    assert sum(quality["outcome_counts"].values()) == quality["frames_processed"]
    assert "insufficient_resolved_count" in quality["gate_failures"]


def test_no_resolved_outcomes_does_not_invent_neutral_labels(tmp_path):
    args, _, _ = setup(tmp_path, hold_ms=10_000)
    report = module.audit_event_corpus(**args)
    summary = report["training_summary"]
    assert summary["class_counts_loss_breakeven_profit"] == [0, 0, 0]
    assert summary["observed_classes"] == summary["maximum_nonoverlapping_label_intervals"] == 0
    assert summary["net_return_bps"] is None
    assert report["observed_training_blockers"] == [
        "training_artifact_quality_failure",
        "insufficient_training_classes",
    ]


def test_validation_outcomes_do_not_change_report(tmp_path):
    args, fold, _ = setup(tmp_path)
    before = module.audit_event_corpus(**args)
    fold["sources"][-1].dataset_path.write_text("invalid and unavailable")
    assert module.audit_event_corpus(**args) == before


def test_metadata_coverage_durations_and_days(tmp_path):
    args, _, record = setup(tmp_path, mixed=True)
    report = module.audit_event_corpus(**args)
    coverage = report["declared_coverage_metadata_only"]
    assert {k: v["sessions"] for k, v in coverage.items()} == {
        "train": 2,
        "validation": 1,
        "reserved": 1,
    }
    training = record.sources[:2]
    assert coverage["train"]["declared_duration_ns"] == sum(
        s.ended_at_ns - s.started_at_ns for s in training
    )
    assert coverage["train"]["elapsed_span_ns"] == (
        training[-1].ended_at_ns - training[0].started_at_ns
    )
    assert coverage["train"]["distinct_utc_start_dates"] == 1
    assert coverage["train"]["regime_coverage"] == "not_established_from_declarations"


@pytest.mark.parametrize(
    "field,value",
    [
        ("rolling_window_complete", 1),
        ("rolling_trade_count", True),
        ("rolling_trade_count", -1),
        ("spread_bps", "NaN"),
        ("rolling_cvd_btc", 0.25),
    ],
)
def test_rehashed_invalid_feature_types_are_rejected(tmp_path, field, value):
    args, _, _ = setup(tmp_path)
    selected = args["training"][0]

    def change(dataset):
        row = resolved(dataset)
        row["features"][field] = value
        row["features_sha256"] = module._hash(module._json(row["features"]))

    tamper(selected.artifact.path, "dataset", change)
    args["training"] = (replace(selected, artifact=pin(selected.artifact.path)),)
    with pytest.raises(ValueError):
        module.audit_event_corpus(**args)


def test_checksum_is_required_in_addition_to_external_pin(tmp_path):
    args, _, _ = setup(tmp_path)
    selected = args["training"][0]
    tamper(selected.artifact.path, "dataset", lambda d: d.update(frames_processed=1), rehash=False)
    args["training"] = (replace(selected, artifact=pin(selected.artifact.path)),)
    with pytest.raises(ValueError, match="envelope or checksum"):
        module.audit_event_corpus(**args)


@pytest.mark.parametrize("field", ["registration", "manifest", "training"])
def test_pins_are_checked_even_when_envelope_is_unchanged(tmp_path, field):
    args, _, _ = setup(tmp_path)
    path = args[field].path if field != "training" else args["training"][0].artifact.path
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="raw-file pin"):
        module.audit_event_corpus(**args)


def resolved(dataset):
    return next(r for r in dataset["examples"] if r["outcome"]["status"] == "resolved")


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(registration_sha256="a" * 64),
        lambda d: d.update(implementation_sha256="a" * 64),
        lambda d: d.update(source_session="reserved"),
        lambda d: d.update(source_sha256="a" * 64),
        lambda d: d.update(max_frames=99),
        lambda d: d.update(frames_processed=True),
        lambda d: d.update(session_consumed=1),
        lambda d: d.update(market_fault_frames=False),
        lambda d: d.update(training_started=True),
        lambda d: d.update(protocol={}),
        lambda d: d.update(outcome_counts={}),
        lambda d: d.update(outcome_reason_counts={}),
        lambda d: d.update(extra="unsupported"),
        lambda d: resolved(d).update(source_session="reserved"),
        lambda d: resolved(d).update(example_id="a" * 64),
        lambda d: resolved(d).update(source_line=True),
        lambda d: resolved(d).update(feature_available_at_ns=-1),
        lambda d: resolved(d).update(features={}),
        lambda d: resolved(d).update(features_sha256="a" * 64),
        lambda d: resolved(d)["outcome"].update(direction=True),
        lambda d: resolved(d)["outcome"].update(direction=1),
        lambda d: resolved(d)["outcome"].update(net_return_fraction="0"),
        lambda d: resolved(d)["outcome"].update(net_return_fraction="NaN"),
        lambda d: resolved(d)["outcome"].update(net_return_fraction="1e99999"),
        lambda d: resolved(d)["outcome"].update(exit_price_usdt="0"),
        lambda d: resolved(d)["outcome"].update(exit_at_ns=True),
        lambda d: resolved(d)["outcome"].update(known_at_ns=d["source_ended_at_ns"] + 1),
        lambda d: resolved(d)["outcome"].update(horizon_at_ns=0),
        lambda d: resolved(d)["outcome"].update(reason="unrecognized"),
        lambda d: resolved(d)["outcome"].update(status="censored"),
        lambda d: resolved(d)["outcome"].update(status="pending"),
        lambda d: d["examples"][0]["outcome"].update(direction=0),
    ],
)
def test_rehashed_and_repinned_internal_inconsistencies_fail(tmp_path, change):
    args, _, _ = setup(tmp_path)
    selected = args["training"][0]
    tamper(selected.artifact.path, "dataset", change)
    args["training"] = (replace(selected, artifact=pin(selected.artifact.path)),)
    with pytest.raises(ValueError):
        module.audit_event_corpus(**args)


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(train_sessions=["research-1"]),
        lambda m: m.update(train_outcome_cutoff_ns=999),
        lambda m: m.update(embargo_ns=True),
        lambda m: m.update(minimum_resolved_fraction=0.5),
        lambda m: m.update(reserved_sessions=[]),
        lambda m: m.update(registration_sha256="a" * 64),
    ],
)
def test_rehashed_split_reassignment_is_refused(tmp_path, change):
    args, _, _ = setup(tmp_path)
    path = args["manifest"].path
    tamper(path, "manifest", change)
    args["manifest"] = pin(path)
    with pytest.raises(ValueError):
        module.audit_event_corpus(**args)


@pytest.mark.parametrize("raw", [b"{}", b'{"report":{},"report":{}}', b'{"report":NaN}', b"[]"])
def test_invalid_envelope_and_json(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        module._read(pin(path), "report", 1024)


def test_limits_partial_and_no_overwrite(tmp_path, monkeypatch):
    args, _, _ = setup(tmp_path)
    with pytest.raises(ValueError, match="byte budget"):
        module._read(args["registration"], "registration", 1)
    partial = tmp_path / "input.partial"
    partial.write_bytes(b"{}")
    with pytest.raises(ValueError, match="partial"):
        module._read(pin(partial), "dataset", 1024)
    monkeypatch.setattr(module, "MAX_INPUT_BYTES", 1)
    with pytest.raises(ValueError, match="byte budget"):
        module.audit_event_corpus(**args)
    output = tmp_path / "out.json"
    output.write_text("keep")
    with pytest.raises(FileExistsError):
        module.audit_event_corpus(**args, output_path=output)
    assert output.read_text() == "keep"


def test_audit_code_drift_withholds_publication(tmp_path, monkeypatch):
    args, _, _ = setup(tmp_path)
    hashes = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(module, "_implementation_hash", lambda: next(hashes))
    with pytest.raises(ValueError, match="changed; nothing published"):
        module.audit_event_corpus(**args, output_path=tmp_path / "out.json")
    assert not (tmp_path / "out.json").exists()


def test_cli_writes_only_a_descriptive_report(tmp_path, monkeypatch, capsys):
    args, _, _ = setup(tmp_path)
    selected = args["training"][0]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "event_corpus_audit",
            "--registration",
            str(args["registration"].path),
            args["registration"].raw_sha256,
            "--manifest",
            str(args["manifest"].path),
            args["manifest"].raw_sha256,
            "--training",
            selected.source_session,
            str(selected.artifact.path),
            selected.artifact.raw_sha256,
            "--output",
            str(tmp_path / "audit.json"),
        ],
    )
    module.main()
    report = json.loads(capsys.readouterr().out)
    assert report["artifact_type"] == "historical_event_corpus_audit"
    assert not report["training_allowed"]
