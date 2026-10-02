"""Cost labels, future-blind model inputs and full-session dataset/token preflights."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.training import prepare_6e_qwen_data as build
from ai_trader.training import six_e_forecast as t


def observation(day="2025-04-07", offset=0, move=5):
    now = int(datetime.fromisoformat(day).replace(hour=12, tzinfo=UTC).timestamp()) * t.SECOND
    tick = build.data.census.baseline.data.clock.TICK
    outcome = {
        "status": "resolved",
        "entry_ts_ns": now + offset * t.SECOND + 100_000_000,
        "exit_ts_ns": now + offset * t.SECOND + 15 * t.SECOND + 100_000_000,
        "entry_bid_nano": 1_100_000_000,
        "entry_ask_nano": 1_100_000_000 + tick,
        "exit_bid_nano": 1_100_000_000 + move * tick,
        "exit_ask_nano": 1_100_000_000 + (move + 1) * tick,
        "late_exit": False,
        "inactivity_exposed": False,
    }
    targets, label = build.data.census.baseline.data.observed_targets(outcome)
    return {
        "source_session": day,
        "contract": build.data.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": now + offset * t.SECOND,
        "features": dict.fromkeys(t.SNAPSHOT_FEATURES, 0.0),
        "execution_features": dict.fromkeys(t.EXECUTION_FEATURES, 0.0),
        "eligible": True,
        "eligibility_reason": None,
        "outcome": outcome,
        "net_targets_long_short_ticks": targets,
        "hindsight_action": label,
    }


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_bytes((t.canonical(value) + "\n").encode())
    return pin(path)


@pytest.mark.parametrize(
    "targets,labels",
    [
        ([3.0, -7.0], ["long_positive", "long_positive", "neither_positive"]),
        ([-7.0, 3.0], ["short_positive", "short_positive", "neither_positive"]),
        ([1.0, -5.0], ["long_positive", "neither_positive", "neither_positive"]),
        ([0.0, -4.0], ["neither_positive"] * 3),
        ([-2.0, -2.0], ["neither_positive"] * 3),
    ],
)
def test_strict_positive_and_cost_monotonicity(targets, labels):
    assert list(t.parse_completion(t.completion(targets)).values()) == labels


@pytest.mark.parametrize(
    "targets", [None, [1, 1], [float("nan"), -1], [True, -2], [1], [1, float("inf")]]
)
def test_invalid_targets_refused(targets):
    with pytest.raises(ValueError):
        t.completion(targets)


def test_future_fields_do_not_enter_input_and_label_changes_do_not_change_prompt():
    row = observation()
    original = t.features_only(row)
    for key in (
        "outcome",
        "net_targets_long_short_ticks",
        "hindsight_action",
        "path_horizons",
        "eligible",
    ):
        row[key] = object()  # Explodes if accidentally serialized or projected.
    assert t.features_only(row) == original
    a, _ = build.example(observation(move=5), "train")
    b, _ = build.example(observation(move=-5), "train")
    assert a["prompt"] == b["prompt"] and a["input_sha256"] == b["input_sha256"]
    assert a["completion"] != b["completion"]
    for forbidden in ("2025-04-07", "6EM5", "source_session", "hindsight_action", "exit_bid_nano"):
        assert forbidden not in a["prompt"]


def test_model_view_projects_only_text_and_train_gate_precedes_poison_access():
    record, _ = build.example(observation(), "train")
    assert t.model_view(record, for_training=True) == (record["prompt"], record["completion"])

    class Poison(dict):
        def __getitem__(self, key):
            if key != "role":
                pytest.fail("Later prompt/labels accessed before train gate")
            return "validation_development"

    with pytest.raises(ValueError, match="train-role"):
        t.model_view(Poison(), for_training=True)


@pytest.mark.parametrize(
    "day,role",
    [
        ("2025-08-31", "train"),
        ("2025-09-01", "validation_development"),
        ("2025-10-31", "validation_development"),
        ("2025-11-01", "test_development"),
    ],
)
def test_exact_calendar_role_boundaries(day, role):
    assert t.role_for_session(day) == role


def test_reserved_date_refuses_before_features_or_targets():
    with pytest.raises(ValueError, match="Reserved"):
        t.features_only({"source_session": "2026-01-01", "contract": None, "decision_ts_ns": None})


@pytest.mark.parametrize(
    "change",
    [
        "feature_key",
        "nan",
        "bool",
        "negative_execution",
        "fraction",
        "time",
        "contract",
        "role",
        "partition",
    ],
)
def test_bad_input_or_cross_role_refused(change):
    row = observation()
    role = "train"
    if change == "feature_key":
        row["features"]["future_return"] = 1.0
    elif change == "nan":
        row["features"]["queue_imbalance"] = float("nan")
    elif change == "bool":
        row["features"]["queue_imbalance"] = True
    elif change == "negative_execution":
        row["execution_features"][t.EXECUTION_FEATURES[0]] = -1
    elif change == "fraction":
        row["features"]["unknown_trade_fraction_5s"] = 1.01
    elif change == "time":
        row["decision_ts_ns"] -= t.SECOND
    elif change == "contract":
        row["contract"] = "6EU5"
    elif change == "partition":
        row["partition"] = "test_reserved"
    else:
        role = "validation_development"
    with pytest.raises(ValueError):
        build.example(row, role)


@pytest.mark.parametrize(
    "status", ["no_entry_quote_timeout", "no_entry_spread_widened", "unresolved_exit_window_end"]
)
def test_unavailable_outcomes_are_not_no_opportunity_labels(status):
    row = observation()
    row["outcome"] = {"status": status}
    row.update(net_targets_long_short_ticks=None, hindsight_action=None)
    record, result = build.example(row, "train")
    assert result == "unavailable:" + status
    assert record["completion"] is None and "prompt" not in record


@pytest.mark.parametrize("flag", ["late_exit", "inactivity_exposed"])
def test_uncertain_resolved_outcomes_excluded_not_negative(flag):
    row = observation()
    row["outcome"][flag] = True
    if flag == "late_exit":
        row["outcome"]["exit_ts_ns"] += 2 * t.SECOND
    record, status = build.example(row, "train")
    assert record["completion"] is None and status == "excluded:" + flag


@pytest.mark.parametrize(
    "change",
    ["target", "action", "missing_quality", "quality_bool", "late_flag", "entry", "exit_quote"],
)
def test_target_arithmetic_timing_and_explicit_quality_refused(change):
    row = observation()
    if change == "target":
        row["net_targets_long_short_ticks"][0] += 1
    elif change == "action":
        row["hindsight_action"] = 0
    elif change == "missing_quality":
        del row["outcome"]["inactivity_exposed"]
    elif change == "quality_bool":
        row["outcome"]["late_exit"] = 0
    elif change == "late_flag":
        row["outcome"]["exit_ts_ns"] += 2 * t.SECOND
    elif change == "entry":
        row["outcome"]["entry_ts_ns"] -= t.SECOND
    else:
        row["outcome"]["exit_ask_nano"] = row["outcome"]["exit_bid_nano"]
        row["net_targets_long_short_ticks"], row["hindsight_action"] = (
            build.data.census.baseline.data.observed_targets(row["outcome"])
        )
    with pytest.raises(ValueError):
        build.example(row, "train")


@pytest.mark.parametrize(
    "text",
    [
        '{"extra_1_tick":"neither_positive","extra_2_ticks":"long_positive","extra_4_ticks":"neither_positive"}',
        '{"extra_1_tick":"long_positive","extra_2_ticks":"short_positive","extra_4_ticks":"neither_positive"}',
        '{"extra_1_tick":"long_positive","extra_1_tick":"long_positive"}',
        '{"action":"buy"}',
        "[]",
        "not JSON",
    ],
)
def test_structured_response_refuses_unknown_fields_duplicates_and_nonmonotonicity(text):
    with pytest.raises(ValueError):
        t.parse_completion(text)


def test_no_model_or_dbn_imports_in_pure_forecast_contract():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import ai_trader.training.six_e_forecast; "
            "assert all(n not in sys.modules "
            "for n in ('torch','transformers','peft','databento_dbn'))",
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0


@pytest.fixture
def dataset_setup(manifest_evidence, monkeypatch):
    root, manifest, manifest_pin, _ = manifest_evidence
    monkeypatch.setattr(t, "TRAIN_END", build.data.TRAIN_END)
    monkeypatch.setattr(t, "VALIDATION_END", build.data.VALIDATION_END)
    reg = root / "registered-qwen-data.json"
    build.prepare(root, manifest, manifest_pin, reg)
    return root, reg, pin(reg), root / "data/processed/qwen-dataset"


@pytest.fixture
def dataset(dataset_setup):
    root, reg, reg_pin, output = dataset_setup
    result = build.run(root, reg, reg_pin, output)
    return root, output, result, pin(output / "completion.json")


def token_audit(output, receipt_pin, report, encode=lambda _: [10, 11]):
    return t.audit_tokens(
        output,
        receipt_pin,
        report,
        encode=encode,
        tokenizer_pin="a" * 64,
        eos=151643,
        pad=151643,
        tokenizer_version="fixture",
    )


def test_complete_dataset_roles_unknown_accounting_and_no_source_mutation(dataset):
    root, output, result, _ = dataset
    assert result["inspected_sessions"] == 9
    assert result["inspected_cases"] == result["source_coverage"]["cases"]
    assert set(result["files"]) == {*(f"{role}.jsonl" for role in t.ROLES), "unavailable.jsonl"}
    for role in t.ROLES:
        cases = [json.loads(raw) for raw in (output / f"{role}.jsonl").read_bytes().splitlines()]
        assert len(cases) == result["by_role"][role]["supervised"] > 0
        assert all(t.role_for_session(r["source_session"]) == role for r in cases)
        for row in cases:
            t.validate_example(row)
    assert result["independent_holdout"] is False and result["training_authorized"] is False
    assert result["source_coverage"]["dispositions"]["reserved_metadata_only"] == 1
    assert not result["qwen_trained"] and not result["trading_enabled"]
    for day in result["sessions"]:
        assert sum(day["target_statuses"].values()) == day["cases"]
    for meta in result["files"].values():
        assert type(meta["sha256"]) is str


def test_registration_refuses_rehashed_permission_change_before_case_read(
    dataset_setup, monkeypatch
):
    root, reg, _, output = dataset_setup
    frozen = json.loads(reg.read_bytes())
    frozen["protocol"]["permission"]["model_training"] = True
    changed_pin = write(reg, frozen)
    monkeypatch.setattr(build.data, "read_rows", lambda *args: pytest.fail("cases read"))
    with pytest.raises(ValueError, match="permission"):
        build.run(root, reg, changed_pin, output)
    assert not output.exists()


def test_raw_and_reserved_artifact_paths_never_opened(dataset_setup, monkeypatch):
    root, reg, reg_pin, output = dataset_setup
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert "2026-01-01" not in str(path) and path.suffix not in {".zip", ".dbn"}
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert build.run(root, reg, reg_pin, output)["inspected_sessions"] == 9


def test_failed_preparation_retains_incomplete_evidence_no_subset_or_retry(
    dataset_setup, monkeypatch
):
    root, reg, reg_pin, output = dataset_setup
    reads = []
    old = build.data.read_rows

    def fail_later(root, entry, kind):
        reads.append(entry["utc_date"])
        if len(reads) == 2:
            raise ValueError("fixture source changed")
        return old(root, entry, kind)

    monkeypatch.setattr(build.data, "read_rows", fail_later)
    with pytest.raises(ValueError):
        build.run(root, reg, reg_pin, output)
    assert len(reads) == 2 and (output / "failure.json").exists()
    assert (output / "attempt.json").exists() and not (output / "completion.json").exists()
    with pytest.raises(ValueError, match="New dataset"):
        build.run(root, reg, reg_pin, output)
    assert len(reads) == 2


def test_all_role_cpu_tokens_completion_only_and_no_training_authority(dataset):
    root, output, result, receipt_pin = dataset
    report = root / "token-report.json"
    checked = token_audit(output, receipt_pin, report)
    assert checked["supervised_examples"] == sum(
        v["supervised"] for v in result["by_role"].values()
    )
    assert all(
        v["max_prompt_tokens"] == 2 and v["max_completion_with_eos_tokens"] == 3
        for v in checked["by_role"].values()
    )
    assert checked["prompt_loss_masked"] and checked["completion_and_eos_supervised"]
    assert not checked["truncation"] and not checked["model_weights_loaded"]
    assert not checked["training_authorized"] and not checked["independent_holdout"]
    with pytest.raises(ValueError, match="exclusive"):
        token_audit(output, receipt_pin, report)


@pytest.mark.parametrize(
    "change",
    [
        "prompt_oversize",
        "completion_oversize",
        "embedded_eos",
        "tamper",
        "failure",
        "role",
        "duplicate",
        "approval",
        "extra_file",
    ],
)
def test_token_preflight_refuses_entire_result_without_truncation_or_subset(dataset, change):
    root, output, result, receipt_pin = dataset

    def encoder(_):
        return [10, 11]

    if change == "prompt_oversize":

        def encoder(text):
            return [10] * (t.MAX_PROMPT_TOKENS + 1) if text.startswith(t.PREFIX) else [10]
    elif change == "completion_oversize":

        def encoder(text):
            return [10] * t.MAX_COMPLETION_TOKENS if not text.startswith(t.PREFIX) else [10]
    elif change == "embedded_eos":

        def encoder(_):
            return [151643]
    elif change == "failure":
        write(output / "failure.json", {"error": "fixture"})
    elif change == "approval":
        result["training_authorized"] = True
        receipt_pin = write(output / "completion.json", result)
    elif change == "extra_file":
        result["files"]["reserved.jsonl"] = {}
        receipt_pin = write(output / "completion.json", result)
    else:
        path = output / "train.jsonl"
        if change == "tamper":
            path.write_bytes(path.read_bytes() + b"{}\n")
        else:
            rows = [json.loads(raw) for raw in path.read_bytes().splitlines()]
            if change == "role":
                rows[0]["role"] = "validation_development"
            else:
                rows.insert(1, deepcopy(rows[0]))
            path.write_bytes(b"".join((t.canonical(r) + "\n").encode() for r in rows))
            result["files"]["train.jsonl"].update(
                sha256=pin(path), bytes=path.stat().st_size, count=len(rows)
            )
            receipt_pin = write(output / "completion.json", result)
    report = root / "refused-token-report.json"
    with pytest.raises(ValueError):
        token_audit(output, receipt_pin, report, encoder)
    assert not report.exists()


def test_completion_mask_supervises_eos_even_when_eos_is_padding():
    record = t.completion_only_record([10, 11], [20, 21], eos_token_id=151643, pad_token_id=151643)
    assert record["labels"][:6] == [-100, -100, 20, 21, 151643, -100]
    assert record["attention_mask"][:6] == [1, 1, 1, 1, 1, 0]
