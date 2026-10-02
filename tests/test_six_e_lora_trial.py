"""Synthetic fixtures/backends only: fixed training ranks, metadata protection and quarantine."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_qwen_gpu_smoke import gpu_request as gpu_request
from test_qwen_gpu_smoke import gpu_resources, reload_result
from test_six_e_forecast import observation

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.training import _six_e_lora_worker as w
from ai_trader.training import prepare_6e_qwen_data as builder
from ai_trader.training import six_e_lora_trial as s


def write(path, value):
    path.write_text(canonical(value) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encoder(text):
    return [10, 11] if text.startswith(s.task.PREFIX) else [20, 21]


def reservation(dataset_pin, manifest_pin):
    rows = [
        {
            "source_session": day,
            "partition": name,
            "member_sha256": "d" * 64,
            "member_bytes": 200,
            "prior_access": "no_replay_documented",
            "condition": "available",
        }
        for name, day in (
            ("validation_reserved", "2026-01-15"),
            ("test_reserved", "2026-04-15"),
            ("lockbox_reserved", "2026-07-15"),
        )
    ]
    return {
        "kind": s.RESERVATION_KIND,
        "task": s.task.TASK,
        "status": "reserved_metadata_only_not_evaluated",
        "dataset_completion_sha256": dataset_pin,
        "source_manifest_sha256": manifest_pin,
        "source_census_registration_sha256": "c" * 64,
        "calendar": [list(item) for item in s.CALENDAR],
        "sessions": rows,
        "counts": {name: 1 for name, _, _ in s.CALENDAR},
        "outcomes_opened": False,
        "evaluation_authorized": False,
        "external_nonexposure_proven": False,
        "training_authorized": False,
    }


@pytest.fixture
def trial_request(gpu_request, monkeypatch):
    dataset = Path(gpu_request["output_dir"]).parent / "dataset"
    dataset.mkdir()
    rows = [
        builder.example(observation(day=day, offset=i * 60, move=5 if i % 2 else -5), "train")[0]
        for day in ("2025-04-07", "2025-04-08", "2025-04-09")
        for i in range(12)
    ]
    train = dataset / "train.jsonl"
    train.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    receipt = {
        "status": "prepared_6e_qwen_development_only",
        "protocol": s.task.protocol(),
        "manifest_sha256": "b" * 64,
        "registration_sha256": "f" * 64,
        "implementation_sha256": {
            Path(module.__file__).name: pin(Path(module.__file__))
            for module in (s.task, s.token_plan)
        },
        "files": {
            name: {}
            for name in (
                "train.jsonl",
                "validation_development.jsonl",
                "test_development.jsonl",
                "unavailable.jsonl",
            )
        },
        "by_role": {"train": {"supervised": len(rows)}},
    }
    receipt.update(
        dict.fromkeys(
            (
                "training_authorized",
                "qwen_trained",
                "independent_holdout",
                "reserved_outcomes_opened",
                "trading_enabled",
                "promotion_enabled",
                "automatic_retry",
            ),
            False,
        )
    )
    receipt["files"]["train.jsonl"] = {
        "count": len(rows),
        "bytes": train.stat().st_size,
        "sha256": pin(train),
    }
    dataset_pin = write(dataset / "completion.json", receipt)
    token_path = dataset.parent / "tokens.json"
    tokenizer = Path(gpu_request["checkpoint"]) / "tokenizer.json"
    token_pin = write(
        token_path,
        {
            "status": "passed_all_supervised_token_preflight_not_training_approval",
            "dataset_completion_sha256": dataset_pin,
            "task": s.task.TASK,
            "tokenizer_sha256": pin(tokenizer),
            "tokenizer_version": s._lock_pin(
                Path(gpu_request["dependency_lock"]), gpu_request["dependency_lock_sha256"]
            )["tokenizers"],
            "eos_token_id": 151643,
            "pad_token_id": 151643,
            "by_role": {"train": {"examples": len(rows)}},
            "prompt_loss_masked": True,
            "completion_and_eos_supervised": True,
            "truncation": False,
            "training_authorized": False,
            "model_weights_loaded": False,
            "qwen_trained": False,
            "independent_holdout": False,
            "trading_enabled": False,
            "promotion_enabled": False,
        },
    )
    reserved_path = dataset.parent / "reserved.json"
    reserved_pin = write(reserved_path, reservation(dataset_pin, receipt["manifest_sha256"]))
    request = {key: value for key, value in gpu_request.items() if key in s.BASE_FIELDS}
    request.update(
        dataset=str(dataset),
        dataset_sha256=dataset_pin,
        token_preflight=str(token_path),
        token_preflight_sha256=token_pin,
        tokenizer_json=str(tokenizer),
        tokenizer_sha256=pin(tokenizer),
        reservation=str(reserved_path),
        reservation_sha256=reserved_pin,
        enable_research_training=True,
        profile=s.profile(),
        source_sha256=s.source_sha256(),
    )
    monkeypatch.setattr(s.token_plan, "load_tokenizer", lambda *args: encoder)
    receipt, _, _ = s.validate_inputs(request, verify_assets=True)
    selected = s.selected_examples(request, receipt)
    request["selection"], _ = s.encode_selection(request, selected, encoder)
    return request


def launch(request):
    return s.run({key: value for key, value in request.items() if key in s.BASE_FIELDS})


def fake_result(request):
    directory = Path(request["output_dir"])
    metrics = [{"loss": 2.0, "gradient_norm": 0.5} for _ in range(s.STEPS)]
    events = [
        {"event": "native_initialization_started"},
        {"event": "native_initialization_completed"},
    ]
    for step, (spec, metric) in enumerate(zip(request["selection"], metrics, strict=True), 1):
        binding = {"step": step, "case_id": spec["case_id"], "record_sha256": spec["record_sha256"]}
        events.extend(
            [{"event": "step_intent", **binding}, {"event": "step_completed", **binding, **metric}]
        )
    events.extend([{"event": "save_reload_started"}, {"event": "save_reload_completed"}])
    (directory / "steps.jsonl").write_text(
        "".join(canonical(row) + "\n" for row in events), encoding="utf-8"
    )
    return {
        "kind": s.KIND,
        "request_sha256": digest(request),
        "steps": s.STEPS,
        "metrics": metrics,
        "runtime": json.loads(Path(request["runtime_manifest"]).read_text()),
        "resources": gpu_resources(),
        "trainable_parameters": 200,
        "frozen_parameter_guards_passed": True,
        "reload": reload_result(directory),
        **s.NO_AUTHORITY,
    }


def dispatched_result(request):
    directory = Path(request["output_dir"])
    directory.mkdir()
    write(directory / "request.json", request)
    return fake_result(request)


def test_fixed_rank_indices_no_repetition_or_label_argument():
    assert s.indices(20) == list(range(20))
    values = s.indices(19678)
    assert values[0] == 0 and values[-1] == 19677 and len(set(values)) == 20
    assert values == [step * 19677 // 19 for step in range(20)]
    assert s.profile()["max_optimizer_steps"] == 20
    assert s.profile()["max_retries"] == 0 and s.TIMEOUT_MS == 600_000


@pytest.mark.parametrize("count", [19, True, 50001, None])
def test_invalid_training_support_refused(count):
    with pytest.raises(ValueError):
        s.indices(count)


def test_no_optional_model_or_dbn_imports_for_trial_or_worker():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; import ai_trader.training._six_e_lora_worker; "
            "assert not {'torch','transformers','peft','databento_dbn'} & sys.modules.keys()",
        ],
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


def test_selection_reads_only_train_and_is_invariant_to_later_metadata_paths(
    trial_request, monkeypatch
):
    request = trial_request
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
        }
        assert "2026" not in path.name
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    rows, _, _ = s.validate_request(request, verify_assets=True)
    assert [i for i, _ in rows] == s.indices(36)
    assert len(rows) == 20 and all(row["role"] == "train" for _, row in rows)
    assert len({row["source_session"] for _, row in rows}) == 3


@pytest.mark.parametrize("value", [False, None, 1, "yes"])
def test_opt_in_strict_and_before_input_read(trial_request, monkeypatch, value):
    request = copy.deepcopy(trial_request)
    request["enable_research_training"] = value
    request["checkpoint"] = "invalid"
    monkeypatch.setattr(s, "metadata", lambda *args: pytest.fail("metadata read"))
    with pytest.raises(ValueError, match="opt-in"):
        launch(request)


@pytest.mark.parametrize(
    "change",
    [
        "steps",
        "cost",
        "source",
        "extra_field",
        "tokenizer",
        "token_authority",
        "reservation_authority",
        "dataset_authority",
        "selection",
        "overlap",
    ],
)
def test_drift_and_extra_authority_refused_before_dispatch(trial_request, monkeypatch, change):
    request = copy.deepcopy(trial_request)
    if change == "steps":
        request["profile"]["max_optimizer_steps"] = 21
    elif change == "cost":
        request["profile"]["task"] = "live-trading"
    elif change == "source":
        request["source_sha256"] = "0" * 64
    elif change == "extra_field":
        request["live_api_key"] = "not-a-key-fixture"
    elif change == "tokenizer":
        Path(request["tokenizer_json"]).write_text("changed", encoding="utf-8")
    elif change == "selection":
        request["selection"][0]["example_index"] += 1
    elif change == "overlap":
        request["output_dir"] = request["dataset"]
    else:
        key = {
            "token_authority": "token_preflight",
            "reservation_authority": "reservation",
            "dataset_authority": "dataset",
        }[change]
        path = Path(request[key]) / "completion.json" if key == "dataset" else Path(request[key])
        value = json.loads(path.read_text())
        value["training_authorized"] = True
        request[key + "_sha256"] = write(path, value)
    monkeypatch.setattr(s, "_exchange", lambda *args: pytest.fail("worker dispatched"))
    with pytest.raises(ValueError):
        s.validate_request(request, verify_assets=True)


def test_rehashed_later_role_row_refused_even_if_train_filename(trial_request):
    request = copy.deepcopy(trial_request)
    dataset = Path(request["dataset"])
    train = dataset / "train.jsonl"
    rows = [json.loads(raw) for raw in train.read_text().splitlines()]
    rows[0]["role"] = "validation_development"
    train.write_text("".join(canonical(row) + "\n" for row in rows), encoding="utf-8")
    receipt = json.loads((dataset / "completion.json").read_text())
    receipt["files"]["train.jsonl"].update(sha256=pin(train), bytes=train.stat().st_size)
    request["dataset_sha256"] = write(dataset / "completion.json", receipt)
    with pytest.raises(ValueError, match="train-role"):
        s.selected_examples(request, receipt)


def test_rehashed_tokenizer_version_drift_refused_before_dispatch(trial_request, monkeypatch):
    request = copy.deepcopy(trial_request)
    path = Path(request["token_preflight"])
    value = json.loads(path.read_text())
    value["tokenizer_version"] = "wrong"
    request["token_preflight_sha256"] = write(path, value)
    monkeypatch.setattr(s, "_exchange", lambda *args: pytest.fail("worker dispatched"))
    with pytest.raises(ValueError, match="tokenizer preflight"):
        s.validate_request(request, verify_assets=True)


def test_one_dispatch_persisted_selection_timeout_and_quarantine(trial_request, monkeypatch):
    calls = []

    def dispatch(command, request, timeout):
        calls.append((command, timeout))
        assert json.loads((Path(request["output_dir"]) / "request.json").read_text()) == request
        assert request["selection"] == trial_request["selection"]
        return canonical(fake_result(request))

    monkeypatch.setattr(s, "_exchange", dispatch)
    report = launch(trial_request)
    assert len(calls) == 1 and calls[0][1] == 600_000
    assert calls[0][0][-1] == s.WORKER
    assert report["selected_training_examples"] == 20 and report["selected_training_sessions"] == 3
    assert report["full_training_epoch"] is False and report["adapter_quarantined"]
    assert all(report[key] is False for key in s.NO_AUTHORITY)
    with pytest.raises(FileExistsError):
        launch(trial_request)
    assert len(calls) == 1


def test_timeout_keeps_unknown_completion_and_no_retry(trial_request, monkeypatch):
    calls = []

    def timeout(*args):
        calls.append(1)
        raise LocalReviewError("worker_deadline")

    monkeypatch.setattr(s, "_exchange", timeout)
    with pytest.raises(LocalReviewError):
        launch(trial_request)
    report = json.loads((Path(trial_request["output_dir"]) / "run.json").read_text())
    assert report["status"] == "failed_or_interrupted" and report["completed_steps"] is None
    assert report["adapter_quarantined"] and len(calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        "partial",
        "nan",
        "authority",
        "reload",
        "adapter",
        "journal",
        "framing",
        "oversized_journal",
        "memory",
        "checkpoint",
    ],
)
def test_bad_native_evidence_refused_not_promoted(trial_request, change):
    result = dispatched_result(trial_request)
    directory = Path(trial_request["output_dir"])
    if change == "partial":
        result["steps"] = 19
    elif change == "nan":
        result["metrics"][0]["loss"] = float("nan")
    elif change == "authority":
        result["adapter_approved_for_inference"] = True
    elif change == "reload":
        result["reload"]["reload_state_equal"] = False
    elif change == "adapter":
        (directory / "adapter/adapter_model.safetensors").write_bytes(b"changed")
    elif change == "memory":
        result["resources"]["peak_reserved_bytes"] = result["resources"]["total_bytes"] + 1
    elif change == "checkpoint":
        (Path(trial_request["checkpoint"]) / "model.safetensors").write_bytes(b"changed")
    else:
        journal = directory / "steps.jsonl"
        if change == "oversized_journal":
            journal.write_bytes(b" " * (s.MAX_EVENTS_BYTES + 1))
        elif change == "framing":
            journal.write_bytes(journal.read_bytes()[:-1])
        else:
            journal.write_text(
                journal.read_text().replace(trial_request["selection"][0]["case_id"], "bad-case"),
                encoding="utf-8",
            )
    with pytest.raises(ValueError):
        s.validate_result(result, trial_request, directory)


def test_metadata_reservation_cannot_be_forged_into_eval_or_training_authority():
    value = reservation("a" * 64, "b" * 64)
    s.validate_reservation(value, "a" * 64, "b" * 64)
    assert value["external_nonexposure_proven"] is False
    for key in ("outcomes_opened", "training_authorized", "evaluation_authorized"):
        bad = copy.deepcopy(value)
        bad[key] = True
        with pytest.raises(ValueError):
            s.validate_reservation(bad, "a" * 64, "b" * 64)


@pytest.mark.parametrize("change", ["exposed", "partial", "duplicate", "development", "calendar"])
def test_reservation_rejects_exposure_overlap_omissions_and_reordering(change):
    value = reservation("a" * 64, "b" * 64)
    if change == "exposed":
        value["sessions"][0]["prior_access"] = "outcomes_exposed"
    elif change == "partial":
        value["sessions"].pop()
    elif change == "duplicate":
        value["sessions"][1] = copy.deepcopy(value["sessions"][0])
    elif change == "development":
        value["sessions"][0]["source_session"] = "2025-12-31"
    else:
        value["calendar"][0][1] = "2025-01-01"
    with pytest.raises(ValueError):
        s.validate_reservation(value, "a" * 64, "b" * 64)


def test_reservation_producer_metadata_only_complete_and_exclusive(trial_request, monkeypatch):
    request = trial_request
    expected = json.loads(Path(request["reservation"]).read_text())
    ledger = [
        {
            "utc_date": item["source_session"],
            "partition": item["partition"],
            "planned_action": "reserved_metadata_only",
            "sha256": item["member_sha256"],
            "bytes": item["member_bytes"],
            "prior_access": item["prior_access"],
            "condition": item["condition"],
        }
        for item in expected["sessions"]
    ]
    manifest = {
        "ledger": [
            {
                "utc_date": item["utc_date"],
                "role": item["partition"],
                "disposition": "reserved_metadata_only",
                "artifacts": None,
            }
            for item in ledger
        ],
        "coverage": {"dispositions": {"reserved_metadata_only": 3}},
    }
    monkeypatch.setattr(
        builder, "registration", lambda *args: ({"manifest": {"sha256": "b" * 64}}, manifest)
    )
    monkeypatch.setattr(
        builder.data.census, "registration", lambda *args: {"inventory": {"ledger": ledger}}
    )
    monkeypatch.setattr(builder.data.diagnostic, "REGISTRATION_PIN", "c" * 64)
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert path.suffix not in {".zip", ".dbn"} and "2026" not in path.name
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    output = Path(request["dataset"]).parent / "new-reservation.json"
    value = s.reserve(
        output.parent,
        Path(request["dataset"]),
        request["dataset_sha256"],
        output.parent / "registration.json",
        "f" * 64,
        output,
    )
    assert value == expected and all(
        not value[k] for k in ("training_authorized", "outcomes_opened")
    )
    with pytest.raises(FileExistsError):
        s.reserve(
            output.parent,
            Path(request["dataset"]),
            request["dataset_sha256"],
            output.parent / "registration.json",
            "f" * 64,
            output,
        )


class FakeBackend:
    def __init__(self):
        self.records = []
        self.parameter = SimpleNamespace(
            requires_grad=True, grad=None, device=SimpleNamespace(type="cuda"), numel=lambda: 200
        )
        self.model = SimpleNamespace(parameters=lambda: [self.parameter])

    def step(self, record):
        self.records.append(record)
        assert record["labels"][:2] == [-100, -100]
        return {"loss": 2.0, "gradient_norm": 0.5}

    def save_reload(self, directory, probe):
        self.parameter.requires_grad = False
        assert probe == self.records[0]
        return reload_result(directory.parent)


def install_worker(request, monkeypatch):
    directory = Path(request["output_dir"])
    directory.mkdir()
    write(directory / "request.json", request)
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    runtime = json.loads(Path(request["runtime_manifest"]).read_text())
    pins = s._lock_pin(Path(request["dependency_lock"]), request["dependency_lock_sha256"])
    monkeypatch.setattr(w, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    backend = FakeBackend()
    monkeypatch.setattr(w, "create_backend", lambda *args: backend)
    monkeypatch.setattr(w, "verify_frozen_parameters", lambda *args: None)
    monkeypatch.setattr(w, "resources", lambda *args: gpu_resources())
    monkeypatch.setattr(w, "trainable_adapters", lambda *args: [backend.parameter])
    return backend


def test_worker_twenty_bound_steps_save_reload_and_exact_durable_bindings(
    trial_request, monkeypatch
):
    backend = install_worker(trial_request, monkeypatch)
    result = w.respond(canonical(trial_request).encode())
    assert len(backend.records) == 20 and result["steps"] == 20
    assert result["reload"]["reload_state_equal"]
    s.validate_result(result, trial_request, Path(trial_request["output_dir"]))


@pytest.mark.parametrize("change", ["offline", "version", "saved_request", "tokens"])
def test_worker_preflight_fails_before_native_loading(trial_request, monkeypatch, change):
    install_worker(trial_request, monkeypatch)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "version":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "saved_request":
        write(Path(trial_request["output_dir"]) / "request.json", {})
    else:
        monkeypatch.setattr(s.token_plan, "load_tokenizer", lambda *args: lambda text: [99])
    monkeypatch.setattr(w, "create_backend", lambda *args: pytest.fail("native model loaded"))
    with pytest.raises(ValueError):
        w.respond(canonical(trial_request).encode())


def test_worker_failed_step_retains_stage_not_private_error_or_success(trial_request, monkeypatch):
    backend = install_worker(trial_request, monkeypatch)

    def fail(record):
        raise RuntimeError("private contents must not enter failure artifacts")

    monkeypatch.setattr(backend, "step", fail)
    with pytest.raises(RuntimeError):
        w.respond(canonical(trial_request).encode())
    raw = (Path(trial_request["output_dir"]) / "failure.json").read_text()
    failure = json.loads(raw)
    assert failure["stage"] == "optimizer_step_1" and failure["completed_steps_unverified"] == 0
    assert "private contents" not in raw and failure["adapter_quarantined"]


def test_worker_metric_fields_refused_before_completed_journal(trial_request, monkeypatch):
    backend = install_worker(trial_request, monkeypatch)
    monkeypatch.setattr(
        backend, "step", lambda record: {"loss": 1.0, "gradient_norm": 1.0, "extra": 1.0}
    )
    with pytest.raises(ValueError):
        w.respond(canonical(trial_request).encode())
    directory = Path(trial_request["output_dir"])
    assert "step_completed" not in (directory / "steps.jsonl").read_text()
    assert json.loads((directory / "failure.json").read_text())["completed_steps_unverified"] == 0
