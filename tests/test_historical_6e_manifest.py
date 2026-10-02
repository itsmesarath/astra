"""Complete-date lineage, exclusive session roles and limited training permission."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import write_json
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.training import historical_6e_manifest as data


@pytest.fixture
def protected_evidence(census_root, monkeypatch, request):
    original = data.census.inventory

    def inventory(root):
        value = original(root)
        value["ledger"].append(
            {
                "utc_date": "2026-01-01",
                "partition": "validation_reserved",
                "planned_action": "reserved_metadata_only",
                "contract": None,
            }
        )
        value["planned_actions"]["reserved_metadata_only"] = 1
        return value

    monkeypatch.setattr(data.census, "inventory", inventory)
    return request.getfixturevalue("evidence")


@pytest.fixture
def manifest_evidence(protected_evidence, monkeypatch):
    root, resource_registration, resource_pin, resource_output = protected_evidence
    resource = data.resource
    monkeypatch.setattr(data, "TRAIN_END", "2025-06-01")
    monkeypatch.setattr(data, "VALIDATION_END", "2025-09-01")
    resource.run(root, resource_registration, resource_pin, resource_output)
    monkeypatch.setattr(data, "RESOURCE_DIR", resource_output.relative_to(root).as_posix())
    monkeypatch.setattr(
        data,
        "RESOURCE_PIN",
        data.common.hash_file(resource_output / "completion.json", data.MAX_MANIFEST_BYTES),
    )
    diagnostic_registration = root / "diagnostic-registration.json"
    diagnostic_output = root / "data/processed/diagnostic"
    data.diagnostic.prepare(root, diagnostic_registration)
    diagnostic_pin = data.common.hash_file(diagnostic_registration, data.MAX_MANIFEST_BYTES)
    data.diagnostic.run(root, diagnostic_registration, diagnostic_pin, diagnostic_output)
    monkeypatch.setattr(data, "DIAGNOSTIC_DIR", diagnostic_output.relative_to(root).as_posix())
    monkeypatch.setattr(
        data,
        "DIAGNOSTIC_PIN",
        data.common.hash_file(diagnostic_output / "completion.json", data.MAX_MANIFEST_BYTES),
    )
    output = root / "data/processed/manifest.json"
    value = data.run(root, output)
    return root, output, data.common.hash_file(output, data.MAX_MANIFEST_BYTES), value


def test_manifest_has_exclusive_whole_sessions_complete_coverage_and_corrected_day(
    manifest_evidence,
):
    root, path, pin, value = manifest_evidence
    loaded = data.load(root, path, pin)
    assert loaded == value
    assert value["coverage"]["inventory_dates"] == 13
    assert value["coverage"]["decision_sessions"] == 9
    assert value["coverage"]["sessions_by_role"] == {
        "train": 3,
        "validation_development": 3,
        "test_development": 3,
    }
    assert value["coverage"]["dispositions"] == {
        "reconstruction_only": 3,
        "decision_session": 9,
        "reserved_metadata_only": 1,
    }
    corrected = next(e for e in value["ledger"] if e["utc_date"] == data.resource.RESOURCE_DAY)
    assert corrected["resource_correction"] is True
    assert corrected["original_status"] == "quality_refused"
    assert corrected["artifacts"]["rows"]["path"].startswith(data.RESOURCE_DIR)
    for entry in value["ledger"]:
        if entry["artifacts"]:
            rows = data.read_rows(root, entry, "cases")
            assert data.accounting(rows) == entry["case_accounting"]
            assert all(r["source_session"] == entry["utc_date"] for r in rows)
        else:
            assert entry["role"] in {"excluded", "validation_reserved"}
    for key in (
        "qwen_training",
        "trading_enabled",
        "promotion_enabled",
        "reserved_outcomes_opened",
    ):
        assert value["protocol"][key] is False
    assert value["protocol"]["training_permitted"] is True
    assert json.loads(path.read_bytes()) == value
    with pytest.raises(ValueError, match="new"):
        data.run(root, path)


@pytest.mark.parametrize(
    "day,role",
    [
        ("2025-08-31", "train"),
        ("2025-09-01", "validation_development"),
        ("2025-10-31", "validation_development"),
        ("2025-11-01", "test_development"),
    ],
)
def test_actual_split_boundaries_are_whole_calendar_sessions(day, role):
    assert data.role_for_day(day) == role


def test_reserved_case_refused_before_path_construction(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "artifact_path", lambda *a: pytest.fail("reserved path constructed"))
    with pytest.raises(ValueError):
        data.read_rows(tmp_path, {"utc_date": "2026-01-01", "role": "train"}, "cases")


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "drop",
        "role",
        "partition",
        "paths",
        "exclude",
        "counts",
        "qwen",
        "permission",
        "purpose",
    ],
)
def test_repinned_manifest_cannot_change_roles_lineage_permission_or_coverage(
    manifest_evidence, change
):
    root, path, _, original = manifest_evidence
    value = deepcopy(original)
    entry = next(e for e in value["ledger"] if e["artifacts"])
    if change == "duplicate":
        value["ledger"].append(deepcopy(entry))
    elif change == "drop":
        value["ledger"].pop(0)
    elif change == "role":
        entry["role"] = "test_development"
    elif change == "partition":
        entry["partition"] = "test_reserved"
    elif change == "paths":
        entry["artifacts"]["cases"]["path"] = "data/processed/other.jsonl"
    elif change == "exclude":
        entry.update(role="excluded", disposition="observed_empty_window", artifacts=None)
    elif change == "counts":
        value["coverage"]["cases"] += 1
    elif change in {"qwen", "permission", "purpose"}:
        key = {"qwen": "qwen_training", "permission": "training_permitted", "purpose": "purpose"}[
            change
        ]
        value["protocol"][key] = "another_purpose" if change == "purpose" else change == "qwen"
    pin = write_json(path, value)
    with pytest.raises(ValueError):
        data.load(root, path, pin)


def test_changed_row_file_is_rejected_without_altering_original_report(manifest_evidence):
    root, _, _, value = manifest_evidence
    entry = next(e for e in value["ledger"] if e["artifacts"])
    path = root / entry["artifacts"]["cases"]["path"]
    path.write_bytes(path.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="hash or count"):
        data.read_rows(root, entry, "cases")


def test_undeclared_path_and_incomplete_jsonl_refused(manifest_evidence):
    root, _, _, value = manifest_evidence
    original = next(e for e in value["ledger"] if e["artifacts"])
    entry = deepcopy(original)
    entry["artifacts"]["cases"]["path"] = "outside.jsonl"
    with pytest.raises(ValueError, match="processed"):
        data.read_rows(root, entry, "cases")
    path = root / original["artifacts"]["cases"]["path"]
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="incomplete"):
        data.read_rows(root, original, "cases")


def test_unknown_outcomes_remain_unknown_not_negative_or_no_trade():
    rows = [
        {"outcome": {"status": "resolved"}},
        {"outcome": {"status": "no_entry_quote_timeout"}},
        {"outcome": {"status": "unresolved_exit_window_end"}},
    ]
    a = data.accounting(rows)
    assert a["resolved"] == 1 and a["unknown"] == 2
    assert a["cases"] == 3
    assert "neither_positive" not in a["statuses"]


def test_raw_archives_never_opened_by_manifest_builder(manifest_evidence, monkeypatch):
    root, _, _, _ = manifest_evidence
    monkeypatch.setattr(
        data.census.zipfile, "ZipFile", lambda *a: pytest.fail("raw archive opened")
    )
    assert data.build(root)["coverage"]["decision_sessions"] == 9


def test_reserved_artifact_paths_are_never_opened(manifest_evidence, monkeypatch):
    root, path, pin, _ = manifest_evidence
    original = Path.open

    def guarded(path, *args, **kwargs):
        if "2026-01-01" in str(path):
            pytest.fail("reserved dataset path opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert data.build(root)["coverage"]["decision_sessions"] == 9
    assert data.load(root, path, pin)


def test_failure_receipt_cannot_be_used_as_manifest_source(manifest_evidence):
    root, _, _, _ = manifest_evidence
    write_json(root / data.RESOURCE_DIR / "failure.json", {"error": "interrupted"})
    output = root / "data/processed/another-manifest.json"
    with pytest.raises(ValueError, match="incomplete"):
        data.run(root, output)
    assert output.with_suffix(".attempt.json").exists()
    assert output.with_suffix(".failure.json").exists()
    assert not output.exists()


def test_manifest_loader_refuses_later_failure_evidence(manifest_evidence):
    root, path, pin, _ = manifest_evidence
    write_json(root / data.RESOURCE_DIR / "failure.json", {"error": "interrupted"})
    with pytest.raises(ValueError, match="failure evidence"):
        data.load(root, path, pin)


def test_reconstruction_only_day_cannot_become_a_fit_session(manifest_evidence, monkeypatch):
    root, path, _, original = manifest_evidence
    value = deepcopy(original)
    entry = next(e for e in value["ledger"] if e["disposition"] == "reconstruction_only")
    entry.update(role="train", disposition="decision_session", artifacts={"rows": {}})
    pin = write_json(path, value)
    monkeypatch.setattr(data, "decision_entry", lambda *a: pytest.fail("Sunday admitted"))
    with pytest.raises(ValueError, match="training access"):
        data.load(root, path, pin)
