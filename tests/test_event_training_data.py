"""Synthetic-only fold registration, source reproduction and protected-session checks."""

import hashlib
import json
import socket
import sys
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import pytest
from test_microstructure_campaign import shifted
from test_microstructure_data import rows_with_quote
from test_microstructure_policy import MS, capture_bytes, gateway_config, policy, replay_config

from ai_trader.research.microstructure_trial import SourceDeclaration, register_trial
from ai_trader.training import event_training_data as module
from ai_trader.training.microstructure_data import build_registered_event_dataset

D = Decimal


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Event fold attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def setup(tmp_path, *, captures=None, build=True, hold_ms=100, **overrides):
    captures = captures or [rows_with_quote(), shifted(rows_with_quote())]
    declarations, sources = [], []
    for i, rows in enumerate(captures):
        data = capture_bytes(rows)
        capture = tmp_path / f"capture-{i}.jsonl"
        capture.write_bytes(data)
        name = f"research-{i}"
        declarations.append(
            SourceDeclaration(
                name,
                hashlib.sha256(data).hexdigest(),
                rows[0]["started_at_ns"],
                rows[-1]["ended_at_ns"],
                "research",
            )
        )
        sources.append(module.EventDatasetInput(name, capture, tmp_path / f"dataset-{i}.json"))
    end = declarations[-1].ended_at_ns
    declarations.append(
        SourceDeclaration("reserved", "f" * 64, end + 1000 * MS, end + 2000 * MS, "reserved")
    )
    registration_path, manifest_path = tmp_path / "registration.json", tmp_path / "split.json"
    record = register_trial(
        registration_path,
        trial_id="synthetic-events",
        sources=tuple(declarations),
        policy=replace(policy(), entry_ttl_ns=200 * MS, maximum_hold_ns=hold_ms * MS),
        replay=replay_config(),
        gateway=gateway_config(),
        initial_cash_usdt=D("1000"),
    )
    settings = (
        dict(
            training_session_count=1,
            max_frames_per_session=100,
            embargo_ns=0,
            minimum_resolved_per_session=1,
            minimum_resolved_fraction=D("0.25"),
        )
        | overrides
    )
    manifest = module.register_event_split(
        registration_path=registration_path, output_path=manifest_path, **settings
    )
    if build:
        for source in sources:
            build_registered_event_dataset(
                registration_path=registration_path,
                capture_path=source.capture_path,
                source_session=source.source_session,
                max_frames=settings["max_frames_per_session"],
                output_path=source.dataset_path,
            )
    args = dict(
        registration_path=registration_path, manifest_path=manifest_path, sources=tuple(sources)
    )
    return args, record, manifest


def single_args(args, index=0):
    source = args["sources"][index]
    return dict(
        registration_path=args["registration_path"],
        source_session=source.source_session,
        capture_path=source.capture_path,
        dataset_path=source.dataset_path,
    )


def tamper(path, name, change, *, rehash=True):
    envelope = json.loads(path.read_bytes())
    change(envelope[name])
    if rehash:
        envelope[name + "_sha256"] = module._hash(module._json(envelope[name]))
    path.write_text(json.dumps(envelope), encoding="utf-8")


def test_manifest_freezes_metadata_before_any_dataset_exists_and_never_overwrites(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Metadata registration accessed an event dataset or capture.")

    monkeypatch.setattr(module, "_read_bytes", forbidden)
    args, record, manifest = setup(tmp_path, build=False)
    assert not any(s.dataset_path.exists() for s in args["sources"])
    assert manifest["train_sessions"] == ["research-0"]
    assert manifest["validation_sessions"] == ["research-1"]
    assert manifest["reserved_sessions"] == ["reserved"]
    before = args["manifest_path"].read_bytes()
    with pytest.raises(FileExistsError):
        module._publish(manifest, args["manifest_path"], payload_name="manifest")
    assert args["manifest_path"].read_bytes() == before
    assert manifest["registration_sha256"] == record.sha256


def test_source_verified_fold_has_only_allowlisted_features_and_separate_targets(tmp_path):
    args, _, _ = setup(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = module.load_event_split(**args)
    assert result.report["fold_available"] and result.report["reserved_sources_opened"] == 0
    assert result.report["train_rows"] == result.report["validation_rows"] == 1
    assert result.train.source_sessions == ("research-0",)
    assert result.validation.source_sessions == ("research-1",)
    assert len(result.train.X[0]) == len(result.train.feature_names) == 30
    assert result.train.direction == (-1,)  # Do not silently keep winners only.
    assert result.train.net_return_fraction[0] < 0
    assert not {"known_at_ns", "direction", "source_session", "net_return_fraction"} & set(
        result.train.feature_names
    )
    assert result.train.available_at_ns[0] < result.train.known_at_ns[0]
    assert result.train.known_at_ns[0] < result.validation.available_at_ns[0]
    assert set(result.train.example_ids).isdisjoint(result.validation.example_ids)
    assert all(
        s["outcome_counts"] == {"excluded": 9, "censored": 2, "resolved": 1}
        for s in result.report["sources"]
    )
    assert before == {p: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(FrozenInstanceError):
        result.train.direction = (1,)


def test_returned_manifest_cannot_mutate_the_shared_feature_schema(tmp_path):
    args, _, manifest = setup(tmp_path, build=False)
    manifest["feature_units"]["rolling_cvd_btc"] = "incorrect_unit"
    assert module.FEATURE_UNITS["rolling_cvd_btc"] == "BTC"
    stored = json.loads(args["manifest_path"].read_bytes())["manifest"]
    assert stored["feature_units"]["rolling_cvd_btc"] == "BTC"


def test_three_sessions_stay_exclusive_and_later_validation_is_not_shuffled(tmp_path):
    args, _, _ = setup(
        tmp_path,
        captures=[shifted(rows_with_quote(), ms=i * 1000) for i in range(3)],
        training_session_count=2,
    )
    result = module.load_event_split(**args)
    assert result.train.source_sessions == ("research-0", "research-1")
    assert result.validation.source_sessions == ("research-2",)
    assert set(result.train.source_sessions).isdisjoint(result.validation.source_sessions)


def test_variable_barrier_outcomes_need_not_mature_in_feature_order(tmp_path):
    rows = rows_with_quote()
    previous_bid, previous_ask = "100", "100.01"
    for row in rows:
        event = row.get("event", {})
        if event.get("e") == "depthUpdate" and event["E"] in (1200, 1300):
            bid, ask = ("100.2", "100.21") if event["E"] == 1200 else ("100.3", "100.31")
            event["b"] = [[previous_bid, "0"], [bid, "8"]]
            event["a"] = [[previous_ask, "0"], [ask, "3"]]
            previous_bid, previous_ask = bid, ask
        elif event.get("e") == "aggTrade" and event["E"] >= 1200:
            event["p"] = "100.2" if event["m"] else "100.21"
    footer = rows.pop()
    for timestamp, bid, ask, identifier in (
        (1400, "99.85", "99.86", 105),
        (1500, "99.6", "99.61", 106),
    ):
        rows.append(
            {
                "schema_version": 1,
                "record_type": "stream_event",
                "stream": "btcusdt@depth@100ms",
                "received_at_ns": timestamp * MS,
                "event": {
                    "e": "depthUpdate",
                    "E": timestamp,
                    "s": "BTCUSDT",
                    "U": identifier,
                    "u": identifier,
                    "b": [[previous_bid, "0"], [bid, "8"]],
                    "a": [[previous_ask, "0"], [ask, "3"]],
                },
            }
        )
        previous_bid, previous_ask = bid, ask
    footer.update(ended_at_ns=1600 * MS, depth_events=6)
    rows.append(footer)
    args, _, _ = setup(tmp_path, captures=[rows, shifted(rows)], hold_ms=1000)
    result = module.load_event_split(**args)
    assert result.report["fold_available"]
    maturity = dict(zip(result.train.available_at_ns, result.train.known_at_ns, strict=True))
    assert maturity[1100 * MS] == 1500 * MS
    assert maturity[1200 * MS] == 1400 * MS
    assert tuple(sorted(result.train.available_at_ns)) == result.train.available_at_ns


def test_each_market_input_is_read_once_and_actual_bytes_are_accounted(tmp_path, monkeypatch):
    args, _, _ = setup(tmp_path)
    original = module._read_bytes
    reads = []

    def tracked(path, limit):
        reads.append(path)
        return original(path, limit)

    monkeypatch.setattr(module, "_read_bytes", tracked)
    result = module.load_event_split(**args)
    paths = [p for s in args["sources"] for p in (s.dataset_path, s.capture_path)]
    assert reads == [args["manifest_path"], *paths]
    assert result.report["verified_input_bytes"] == sum(p.stat().st_size for p in paths)


@pytest.mark.parametrize(
    "fault", ["feature", "label", "unknown_label", "schema", "type", "row_order", "extra", "counts"]
)
def test_rehashed_tampering_is_rejected_by_source_reproduction(tmp_path, fault):
    args, _, _ = setup(tmp_path)

    def change(dataset):
        row = next(r for r in dataset["examples"] if r["outcome"]["status"] == "resolved")
        if fault == "feature":
            row["features"]["rolling_cvd_btc"] = "999"
            row["features_sha256"] = module._hash(module._json(row["features"]))
        elif fault == "label":
            row["outcome"]["direction"] = 1
        elif fault == "unknown_label":
            unknown = next(r for r in dataset["examples"] if r["outcome"]["status"] == "censored")
            unknown["outcome"].update(direction=0, net_return_fraction="0")
        elif fault == "schema":
            dataset["feature_schema_version"] = "future"
        elif fault == "type":
            dataset["schema_version"] = True  # True == 1 must not evade strict comparison.
        elif fault == "row_order":
            dataset["examples"].reverse()
        elif fault == "extra":
            row["features"]["future_return"] = "1"
        else:
            dataset["outcome_counts"]["resolved"] = 100

    tamper(args["sources"][0].dataset_path, "dataset", change)
    with pytest.raises(ValueError, match="source-reproduced"):
        module.load_event_split(**args)


def test_unrehashed_artifact_and_changed_capture_are_rejected(tmp_path):
    args, _, _ = setup(tmp_path)
    path = args["sources"][0].dataset_path
    before = path.read_bytes()
    tamper(path, "dataset", lambda d: d.update(training_started=True), rehash=False)
    with pytest.raises(ValueError, match="checksum"):
        module.load_verified_event_dataset(**single_args(args))
    path.write_bytes(before)
    args["sources"][0].capture_path.write_bytes(b"changed capture")
    with pytest.raises(ValueError, match="checksum"):
        module.load_verified_event_dataset(**single_args(args))


@pytest.mark.parametrize("source", ["reserved", "unknown"])
def test_protected_source_never_reaches_artifact_or_capture_io(tmp_path, monkeypatch, source):
    args, _, _ = setup(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("Protected source attempted IO.")

    monkeypatch.setattr(module, "_read_bytes", forbidden)
    with pytest.raises(ValueError, match="registered research"):
        module.load_verified_event_dataset(**(single_args(args) | {"source_session": source}))


@pytest.mark.parametrize(
    "fault", ["omitted", "reversed", "duplicate", "reserved", "unknown", "mutable"]
)
def test_entire_source_scope_is_checked_before_any_market_file_access(tmp_path, monkeypatch, fault):
    args, _, _ = setup(tmp_path)
    sources = args["sources"]
    if fault == "omitted":
        sources = sources[:1]
    elif fault == "reversed":
        sources = sources[::-1]
    elif fault == "duplicate":
        sources = (sources[0], sources[0])
    elif fault == "mutable":
        sources = list(sources)
    else:
        sources = (sources[0], replace(sources[1], source_session=fault))

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid scope attempted a source read.")

    monkeypatch.setattr(module, "_load_dataset", forbidden)
    with pytest.raises(ValueError, match="every research source"):
        module.load_event_split(**(args | {"sources": sources}))


@pytest.mark.parametrize(
    "settings",
    [
        {"training_session_count": 0},
        {"training_session_count": 2},
        {"training_session_count": True},
        {"max_frames_per_session": 5001},
        {"max_frames_per_session": True},
        {"embargo_ns": -1},
        {"embargo_ns": True},
        {"embargo_ns": 500 * MS},  # Equality is not separation at the training boundary.
        {"minimum_resolved_per_session": 0},
        {"minimum_resolved_per_session": True},
        {"minimum_resolved_per_session": 101},
        {"minimum_resolved_fraction": D("NaN")},
        {"minimum_resolved_fraction": D("1.1")},
        {"minimum_resolved_fraction": D("-0.1")},
        {"minimum_resolved_fraction": 0.25},
    ],
)
def test_invalid_split_or_quality_settings_cannot_publish_manifest(tmp_path, settings):
    with pytest.raises(ValueError):
        setup(tmp_path, build=False, **settings)
    assert not (tmp_path / "split.json").exists()


def test_one_nanosecond_inside_strict_embargo_is_valid(tmp_path):
    args, _, manifest = setup(tmp_path, embargo_ns=500 * MS - 1)
    assert manifest["embargo_ns"] == 500 * MS - 1
    assert module.load_event_split(**args).report["fold_available"]


def test_reserved_boundary_also_enforces_the_embargo(tmp_path):
    with pytest.raises(ValueError, match="embargo"):
        setup(
            tmp_path,
            captures=[rows_with_quote(), shifted(rows_with_quote(), ms=3000)],
            embargo_ns=1000 * MS,
        )
    assert not (tmp_path / "split.json").exists()


@pytest.mark.parametrize("fraction", ["not a number", "NaN", 0.25])
def test_manifest_fraction_requires_a_valid_decimal_string(tmp_path, fraction):
    args, _, _ = setup(tmp_path)
    tamper(
        args["manifest_path"], "manifest", lambda d: d.update(minimum_resolved_fraction=fraction)
    )
    with pytest.raises(ValueError):
        module.load_event_split(**args)


@pytest.mark.parametrize("fault", ["assignment", "columns", "registration", "type", "extra"])
def test_manifest_tampering_fails_before_market_io(tmp_path, monkeypatch, fault):
    args, _, _ = setup(tmp_path)

    def change(manifest):
        if fault == "assignment":
            manifest["train_sessions"] = manifest["validation_sessions"]
        elif fault == "columns":
            manifest["feature_names"].append("direction")
        elif fault == "registration":
            manifest["registration_sha256"] = "a" * 64
        elif fault == "type":
            manifest["training_session_count"] = True
        else:
            manifest["unexpected"] = 1

    tamper(args["manifest_path"], "manifest", change)
    monkeypatch.setattr(
        module, "_load_dataset", lambda *a, **k: pytest.fail("Unexpected source read")
    )
    with pytest.raises(ValueError):
        module.load_event_split(**args)


@pytest.mark.parametrize("fault", ["gap", "truncated", "count", "fraction", "no_eligible"])
def test_failed_source_quality_retains_accounting_and_blocks_both_partitions(tmp_path, fault):
    settings = {}
    captures = [rows_with_quote(), shifted(rows_with_quote(timestamp=1200, gap=fault == "gap"))]
    if fault == "truncated":
        settings["max_frames_per_session"] = 8
    elif fault == "count":
        settings["minimum_resolved_per_session"] = 2
    elif fault == "fraction":
        settings["minimum_resolved_fraction"] = D("0.5")
    elif fault == "no_eligible":
        from test_microstructure_campaign import recovery_rows

        captures[1] = recovery_rows()
    args, _, _ = setup(tmp_path, captures=captures, **settings)
    result = module.load_event_split(**args)
    assert result.train is result.validation is None and not result.report["fold_available"]
    assert len(result.report["sources"]) == 2
    assert result.report["sources"][1]["gate_failures"]
    assert result.report["train_rows"] == result.report["validation_rows"] == 0
    if fault in ("gap", "no_eligible"):
        assert not result.report["sources"][0]["gate_failures"]  # Even good training is withheld.
    if fault == "no_eligible":
        assert result.report["sources"][1]["resolved_fraction"] is None


def test_budget_mismatch_cannot_hide_a_truncated_artifact(tmp_path, monkeypatch):
    args, _, _ = setup(tmp_path)
    tamper(args["sources"][0].dataset_path, "dataset", lambda d: d.update(max_frames=5))
    original = module._read_bytes

    def checked(path, limit):
        assert path != args["sources"][0].capture_path
        return original(path, limit)

    monkeypatch.setattr(module, "_read_bytes", checked)
    with pytest.raises(ValueError, match="budget mismatch"):
        module.load_event_split(**args)


def test_known_at_cutoff_guard_is_not_only_dependent_on_label_rebuilder(tmp_path, monkeypatch):
    args, _, manifest = setup(tmp_path)
    original = module._load_dataset

    def changed(*a, **k):
        dataset, size = original(*a, **k)
        row = next(r for r in dataset["examples"] if r["outcome"]["status"] == "resolved")
        row["outcome"]["known_at_ns"] = manifest["train_outcome_cutoff_ns"]
        return dataset, size

    monkeypatch.setattr(module, "_load_dataset", changed)
    with pytest.raises(ValueError, match="source boundary"):
        module.load_event_split(**args)


@pytest.mark.parametrize("fault", ["duplicate_keys", "nan", "partial", "bytes", "aggregate"])
def test_strict_json_quarantine_and_read_budgets(tmp_path, monkeypatch, fault):
    args, _, _ = setup(tmp_path)
    path = args["sources"][0].dataset_path
    if fault == "duplicate_keys":
        path.write_bytes(b'{"dataset":{},"dataset":{},"dataset_sha256":"x"}')
    elif fault == "nan":
        path.write_bytes(b'{"dataset":{"x":NaN},"dataset_sha256":"x"}')
    elif fault == "partial":
        path = path.with_suffix(".json.partial")  # Not even opened; it does not exist.
    elif fault == "bytes":
        monkeypatch.setattr(module, "MAX_ARTIFACT_BYTES", 10)
    else:
        first_size = sum(p.stat().st_size for p in (path, args["sources"][0].capture_path))
        monkeypatch.setattr(module, "MAX_INPUT_BYTES", first_size + 1)
    with pytest.raises(ValueError):
        if fault == "aggregate":
            module.load_event_split(**args)
        else:
            module.load_verified_event_dataset(**(single_args(args) | {"dataset_path": path}))


def test_source_drift_during_fold_never_publishes_report(tmp_path, monkeypatch):
    args, _, _ = setup(tmp_path)
    monkeypatch.setattr(module, "_implementation_hash", lambda: "0" * 64)
    report = tmp_path / "verification.json"
    with pytest.raises(ValueError, match="changed"):
        module.load_event_split(**args, report_path=report)
    assert not report.exists()


def test_repeat_verification_is_deterministic_and_report_is_write_once(tmp_path):
    args, _, _ = setup(tmp_path)
    first = module.load_event_split(**args)
    report = tmp_path / "verification.json"
    with localcontext() as context:
        context.prec = 7
        assert module.load_event_split(**args, report_path=report) == first
    envelope = json.loads(report.read_bytes())
    assert envelope["report"] == first.report
    assert envelope["report_sha256"] == module._hash(module._json(first.report))
    before = report.read_bytes()
    with pytest.raises(FileExistsError):
        module.load_event_split(**args, report_path=report)
    assert report.read_bytes() == before


@pytest.mark.parametrize("passed", [True, False])
def test_cli_verification_never_fits_and_exits_two_when_fold_is_blocked(
    tmp_path, monkeypatch, capsys, passed
):
    args, _, _ = setup(tmp_path, minimum_resolved_per_session=1 if passed else 2)
    argv = [
        "event-fold",
        "verify",
        "--registration",
        str(args["registration_path"]),
        "--manifest",
        str(args["manifest_path"]),
        "--report",
        str(tmp_path / "report.json"),
    ]
    for source in args["sources"]:
        argv += [
            "--source",
            source.source_session,
            str(source.capture_path),
            str(source.dataset_path),
        ]
    monkeypatch.setattr(sys, "argv", argv)
    if passed:
        module.main()
    else:
        with pytest.raises(SystemExit) as error:
            module.main()
        assert error.value.code == 2
    report = json.loads(capsys.readouterr().out)
    assert report["fold_available"] is passed
    assert report["training_started"] is False and report["live_trading_available"] is False


def test_cli_registration_is_metadata_only(tmp_path, monkeypatch, capsys):
    args, _, _ = setup(tmp_path, build=False)
    output = tmp_path / "another-split.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "event-fold",
            "register",
            "--registration",
            str(args["registration_path"]),
            "--output",
            str(output),
            "--training-session-count",
            "1",
            "--max-frames-per-session",
            "100",
            "--embargo-ns",
            "0",
            "--minimum-resolved-per-session",
            "1",
            "--minimum-resolved-fraction",
            "0.25",
        ],
    )
    module.main()
    assert output.exists() and not any(s.dataset_path.exists() for s in args["sources"])
    assert json.loads(capsys.readouterr().out)["training_started"] is False
