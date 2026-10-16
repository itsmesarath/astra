"""Synthetic intake fixtures only; never actual protected data or custodian sign-offs."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2
from ai_trader.research import advisory_evaluation as evaluation
from ai_trader.research import protected_intake as intake
from ai_trader.training.advisory_holdout import audit_reservation, exposure_inventory

SUITE = Path(__file__).resolve().parents[1] / "configs/qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return evaluation.load_suite(SUITE, SUITE_SHA)


@pytest.fixture
def dataset():
    rows = []
    for number, expected in enumerate(("support", "veto", "preflight_refusal")):
        session = f"intake-fixture-session-{number}"
        metrics = {
            "estimated_gross_return_bps": "31" if number == 0 else "7",
            "estimated_round_trip_cost_bps": "7",
            "net_expectancy_bps": "24" if number == 0 else "0",
            "stressed_net_expectancy_bps": "9" if number == 0 else "-3",
        }
        evidence = [
            {
                "evidence_id": f"e{index}",
                "symbol": "BTCUSDT",
                "source_session": session,
                "metric": metric,
                "value": value,
                "event_time_ms": 1900,
                "available_time_ms": 2100 if number == 2 else 1950,
            }
            for index, (metric, value) in enumerate(metrics.items())
        ]
        rows.append(
            {
                "case_id": f"intake-fixture-case-{number}",
                "family": f"intake-fixture-family-{number}",
                "source_session": session,
                "split": intake.PROTECTED_SPLIT,
                "as_of_ms": 2000,
                "evidence": evidence,
                "expected": expected,
                "citation_groups": [] if number == 2 else [[e["evidence_id"]] for e in evidence],
                "reference_rationale": None
                if number == 2
                else "PRIVATE_FIXTURE_TARGET_NOT_A_LABEL_AUDIT",
            }
        )
    return {
        "schema_version": 1,
        "kind": intake.DATASET_KIND,
        "dataset_id": "intake-synthetic-fixture-only",
        "review_contract": SPOT_LONG_V2,
        "cases": rows,
    }


def inspect(suite, dataset):
    return intake._inspect_dataset(suite, dataset, digest(dataset))


def save(path, value):
    raw = value if type(value) is bytes else canonical(value).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_actual_payload_metadata_is_derived_but_remains_pending(suite, dataset, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No model, network, file search or child process belongs in intake checks")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    registry, receipt = inspect(suite, dataset)
    assert receipt["counts_by_expected"] == dict(support=1, veto=1, preflight_refusal=1)
    assert receipt["custodian_process_opened_contents"]
    assert receipt["declared_targets_match_mechanical_rubric"]
    assert registry["dataset_sha256"] == digest(dataset)
    assert registry["attestation"]["confirmed"] is False
    assert registry["attestation"]["reviewer_id"] is None
    assert registry["unexposed_attested"] is False
    assert audit_reservation(suite, registry)["blockers"] == [
        "custodian_unexposed_attestation_required"
    ]
    assert receipt["reservation_blockers"] == ["custodian_unexposed_attestation_required"]
    assert not receipt["reservation_complete"]
    assert not receipt["target_semantics_reviewed"]
    assert not receipt["independence_authenticated"]
    assert not receipt["near_duplicates_checked"]
    assert not receipt["training_process_opened_contents"]
    assert not receipt["training_allowed"]
    assert not receipt["execution_allowed"]
    assert not receipt["promotion_allowed"]
    assert receipt["model_calls"] == receipt["optimization_steps"] == receipt["orders"] == 0
    for case, row in zip(evaluation._parse_cases(dataset["cases"]), registry["cases"], strict=True):
        assert row["input_sha256"] == digest(evaluation.model_input(case, SPOT_LONG_V2))
        assert row["scenario_sha256"] == evaluation.scenario_fingerprint(case.snapshot)
        assert set(row) == set(exposure_inventory(suite)[0])
    assert "PRIVATE_FIXTURE_TARGET" not in canonical([registry, receipt])
    assert "net_expectancy_bps" not in canonical([registry, receipt])


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("kind", "advisory_sft_candidate_v1"),
        ("review_contract", "legacy_v1"),
        ("dataset_id", " "),
        ("cases", []),
        ("cases", {}),
        ("training_allowed", True),
        ("custodian", "automatic-approval"),
    ],
)
def test_bad_envelope_and_authority_fields_refused(suite, dataset, field, value):
    dataset[field] = value
    with pytest.raises(ValueError):
        inspect(suite, dataset)


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["cases"][0].update(split="curriculum_draft"),
        lambda d: d["cases"][0].update(split="development_eval"),
        lambda d: d["cases"][0].update(expected="veto"),
        lambda d: d["cases"][1].update(expected="support"),
        lambda d: d["cases"][0]["evidence"][2].update(value="23"),
        lambda d: d["cases"][0]["evidence"][3].update(value="0"),
        lambda d: d["cases"][0].update(citation_groups=[["made-up"]]),
        lambda d: d["cases"][0].update(citation_groups=[]),
        lambda d: d["cases"][0].update(reference_rationale=""),
        lambda d: d["cases"][0]["evidence"][0].update(value=31),
        lambda d: d["cases"][0]["evidence"][0].update(value="NaN"),
        lambda d: d["cases"][0]["evidence"][0].update(event_time_ms=True),
        lambda d: d["cases"][0]["evidence"][0].update(source_session="another-session"),
        lambda d: d["cases"][2].update(reference_rationale="Forbidden refusal target"),
        lambda d: d["cases"][2].update(citation_groups=[["e0"]]),
        lambda d: d["cases"][2].update(
            expected="veto", reference_rationale="x", citation_groups=[["e0"]]
        ),
        lambda d: d.update(cases=d["cases"][:2]),
        lambda d: d.update(cases=d["cases"][1:]),
        lambda d: d.update(cases=d["cases"] * 22),
    ],
)
def test_bad_targets_splits_numeric_boundaries_and_coverage(suite, dataset, change):
    change(dataset)
    with pytest.raises(ValueError):
        inspect(suite, dataset)


@pytest.mark.parametrize("field", ["case_id", "family", "source_session"])
def test_exposed_identity_overlap_refused(suite, dataset, field):
    dataset["cases"][0][field] = exposure_inventory(suite)[0][field]
    if field == "source_session":
        for e in dataset["cases"][0]["evidence"]:
            e[field] = dataset["cases"][0][field]
    with pytest.raises(ValueError, match="overlaps exposed"):
        inspect(suite, dataset)


def test_relabelling_exposed_payload_and_time_does_not_create_holdout(suite, dataset):
    original = json.loads(SUITE.read_text())["cases"][0]
    copied = copy.deepcopy(original)
    copied.update(
        case_id="renamed", family="renamed", source_session="renamed", split="protected_eval"
    )
    copied["as_of_ms"] += 90000
    for index, e in enumerate(reversed(copied["evidence"])):
        e.update(evidence_id=f"renamed-{index}", source_session="renamed")
        e["event_time_ms"] += 90000
        e["available_time_ms"] += 90000
        e["value"] += "0" if "." in e["value"] else ".0"
    copied["citation_groups"] = [[e["evidence_id"]] for e in copied["evidence"]]
    dataset["cases"][1] = copied
    with pytest.raises(ValueError, match="scenario_sha256"):
        inspect(suite, dataset)


def test_duplicate_protected_content_and_session_crossing_refused(suite, dataset):
    copied = copy.deepcopy(dataset["cases"][0])
    copied.update(case_id="renamed", family="renamed", source_session="renamed")
    for e in copied["evidence"]:
        e["source_session"] = "renamed"
    dataset["cases"].append(copied)
    with pytest.raises(ValueError, match="Duplicate scenario"):
        inspect(suite, dataset)
    dataset["cases"].pop()
    dataset["cases"][1]["source_session"] = dataset["cases"][0]["source_session"]
    with pytest.raises(ValueError, match="session reused"):
        inspect(suite, dataset)


@pytest.mark.parametrize(
    "which,key,value",
    [
        (0, "dataset_sha256", "a" * 64),
        (0, "unexposed_attested", True),
        (1, "training_allowed", True),
        (1, "target_semantics_reviewed", True),
        (1, "independence_authenticated", True),
        (1, "case_count", 99),
    ],
)
def test_reconstruction_rejects_provenance_or_authority_tampering(
    suite, dataset, which, key, value, tmp_path
):
    path = tmp_path / "private.json"
    pin = save(path, dataset)
    artifacts = inspect(suite, dataset)
    artifacts[which][key] = value
    with pytest.raises(ValueError, match="reconstruction"):
        intake.verify_intake(suite, path, pin, *artifacts)


def test_private_payload_drift_rejected_even_when_only_rationale_changed(suite, dataset, tmp_path):
    path = tmp_path / "private.json"
    pin = save(path, dataset)
    registry, receipt = intake.prepare_intake(suite, path, pin)
    intake.verify_intake(suite, path, pin, registry, receipt)
    dataset["cases"][0]["reference_rationale"] = "Changed private rationale"
    save(path, dataset)
    with pytest.raises(ValueError, match="SHA256"):
        intake.verify_intake(suite, path, pin, registry, receipt)


@pytest.mark.parametrize(
    "raw",
    [b'{"schema_version":1,"schema_version":1}', b" " * (1024 * 1024 + 1)],
    ids=("duplicate_keys", "oversized"),
)
def test_pinned_but_invalid_or_oversized_dataset_refused(suite, tmp_path, raw):
    path = tmp_path / "private.json"
    pin = save(path, raw)
    with pytest.raises(ValueError):
        intake.prepare_intake(suite, path, pin)


def test_protected_envelope_and_typed_suite_cannot_enter_training_loader(suite, dataset, tmp_path):
    path = tmp_path / "private.json"
    pin = save(path, dataset)
    with pytest.raises(ValueError):
        evaluation.load_suite(path, pin)
    protected = evaluation.AdvisorySuite("private", pin, evaluation._parse_cases(dataset["cases"]))
    with pytest.raises(ValueError, match="split"):
        evaluation.reference_responses(protected)
    with pytest.raises(ValueError, match="split"):
        exposure_inventory(protected)


def command(tmp_path, dataset):
    path = tmp_path / "private.json"
    pin = save(path, dataset)
    return [
        "intake",
        "prepare",
        "--suite",
        str(SUITE),
        "--suite-sha256",
        SUITE_SHA,
        "--dataset",
        str(path),
        "--dataset-sha256",
        pin,
        "--output-dir",
        str(tmp_path / "out"),
    ]


def test_cli_roundtrip_exclusive_metadata_output_and_no_targets(
    dataset, tmp_path, monkeypatch, capsys
):
    args = command(tmp_path, dataset)
    monkeypatch.setattr(sys, "argv", args)
    intake.main()
    output = tmp_path / "out"
    assert sorted(p.name for p in output.iterdir()) == ["receipt.json", "registry.json"]
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    with pytest.raises(SystemExit) as caught:
        intake.main()
    assert caught.value.code == 2
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    verify_args = ["intake", "verify", *args[2:-2]]
    for name in ("registry", "receipt"):
        path = output / (name + ".json")
        verify_args.extend(
            [
                "--" + name,
                str(path),
                "--" + name + "-sha256",
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    monkeypatch.setattr(sys, "argv", verify_args)
    intake.main()
    captured = capsys.readouterr()
    assert "PRIVATE_FIXTURE_TARGET" not in captured.out + captured.err
    assert "reconstructed" in captured.out
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize(
    "option,value",
    [
        ("--dataset-sha256", "0" * 64),
        ("--suite-sha256", "0" * 64),
        ("--output-dir", "MISSING_PARENT"),
    ],
)
def test_cli_failure_does_not_claim_output(dataset, tmp_path, monkeypatch, option, value):
    args = command(tmp_path, dataset)
    args[args.index(option) + 1] = (
        str(tmp_path / "absent" / "out") if value == "MISSING_PARENT" else value
    )
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as caught:
        intake.main()
    assert caught.value.code == 2
    assert not (tmp_path / "out").exists()


def test_cli_parser_errors_do_not_echo_protected_contents(dataset, tmp_path, monkeypatch, capsys):
    args = command(tmp_path, dataset)
    raw = b'{"PRIVATE_FIXTURE_TARGET_NOT_TO_PRINT":'
    args[args.index("--dataset-sha256") + 1] = save(tmp_path / "private.json", raw)
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as caught:
        intake.main()
    assert caught.value.code == 2
    captured = capsys.readouterr()
    assert "PRIVATE_FIXTURE_TARGET" not in captured.out + captured.err
    assert not (tmp_path / "out").exists()


def test_cli_preserves_partial_directory_on_write_failure(dataset, tmp_path, monkeypatch):
    args = command(tmp_path, dataset)
    monkeypatch.setattr(sys, "argv", args)
    real_write = intake._write_new

    def fail_receipt(path, value):
        if path.name == "receipt.json":
            raise OSError("Simulated disk failure")
        return real_write(path, value)

    monkeypatch.setattr(intake, "_write_new", fail_receipt)
    with pytest.raises(SystemExit) as caught:
        intake.main()
    assert caught.value.code == 2
    assert (tmp_path / "out" / "registry.json").is_file()
    assert not (tmp_path / "out" / "receipt.json").exists()


def test_cli_entrypoint_refuses_existing_exposed_suite(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_trader.research.protected_intake",
            "prepare",
            "--suite",
            str(SUITE),
            "--suite-sha256",
            SUITE_SHA,
            "--dataset",
            str(SUITE),
            "--dataset-sha256",
            SUITE_SHA,
            "--output-dir",
            str(tmp_path / "never"),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "never").exists()
