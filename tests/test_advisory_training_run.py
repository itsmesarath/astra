"""Synthetic approvals/backends only; no real Qwen fitting or operator attestations."""

import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.research.advisory_evaluation import load_suite
from ai_trader.training import _local_training_worker as worker
from ai_trader.training import advisory_curriculum as curriculum
from ai_trader.training import advisory_holdout as holdout
from ai_trader.training import advisory_training_run as run
from ai_trader.training import lora_backend as backend

SUITE_PATH = Path(__file__).resolve().parents[1] / "configs" / "qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


def write_fixture(path, value):
    raw = value.encode() if type(value) is str else canonical(value).encode()
    path.write_bytes(raw)
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest()}


@pytest.fixture
def launch(tmp_path, monkeypatch):
    suite = load_suite(SUITE_PATH, SUITE_SHA)
    review = curriculum.prepare_review(suite)
    review["attestation"].update(
        confirmed=True,
        reviewer_id="synthetic-test-operator",
        reviewed_at_utc="2026-09-24T12:00:00Z",
    )
    for row in review["cases"]:
        row.update(decision="approve", note="Synthetic test only.")
        row["checks"] = dict.fromkeys(curriculum.SEMANTIC_CHECKS, True)
    registry = holdout.reservation_template(suite)
    registry.update(dataset_sha256="b" * 64, unexposed_attested=True)
    registry["attestation"] = copy.deepcopy(review["attestation"])
    registry["cases"] = [
        {
            "case_id": "unseen",
            "family": "unseen",
            "source_session": "unseen",
            "input_sha256": "c" * 64,
            "scenario_sha256": "d" * 64,
        }
    ]
    runtime = {**run.runtime_manifest(), "packages": dict.fromkeys(run.PACKAGES, "1.0")}
    monkeypatch.setattr(run, "runtime_manifest", lambda: copy.deepcopy(runtime))
    monkeypatch.setattr(run, "version", lambda name: "1.0")
    inputs = {
        "suite": {"path": str(SUITE_PATH), "sha256": SUITE_SHA},
        "review": write_fixture(tmp_path / "review.json", review),
        "candidate": write_fixture(
            tmp_path / "candidate.json", curriculum.export_candidate(suite, review)
        ),
        "registry": write_fixture(tmp_path / "registry.json", registry),
        "runtime": write_fixture(tmp_path / "runtime.json", runtime),
        "dependency_lock": write_fixture(
            tmp_path / "lock.txt",
            "\n".join(name + "==1.0 --hash=sha256:" + "a" * 64 for name in run.PACKAGES),
        ),
    }
    checkpoint = tmp_path / "base"
    checkpoint.mkdir()
    return run.prepare_run(inputs, str(checkpoint), "e" * 64, "f" * 64, str(tmp_path / "output"))


class FakeBackend:
    def __init__(self, *args):
        self.steps = []

    def step(self, record):
        self.steps.append(record)
        return {"loss": 2.0, "gradient_norm": 0.1}

    def save_reload(self, directory, probe):
        directory.mkdir()
        (directory / "adapter_config.json").write_text("{}", encoding="utf-8")
        (directory / "adapter_model.safetensors").write_bytes(b"synthetic fixture, not tensors")
        return {
            "adapter_manifest": backend.adapter_manifest(directory),
            "adapter_updated": True,
            "reload_state_equal": True,
            "probe_loss_before": 2.0,
            "probe_loss_after": 2.0,
            "probe_loss_absolute_tolerance": 1e-5,
            "base_checkpoint_unchanged": True,
        }


def install_fake_worker(monkeypatch):
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    monkeypatch.setattr(run, "load_tokenizer", lambda *args: lambda text: [1, 2, 3])
    monkeypatch.setattr(backend, "PeftBackend", FakeBackend)


def test_launch_preparation_does_not_import_or_fit_and_binds_everything(launch):
    assert run.validate_launch(launch) is None
    assert not Path(launch["output_dir"]).exists()
    assert launch["recipe"]["max_optimizer_steps"] == 20
    assert launch["recipe"]["max_wall_time_seconds"] == 600
    assert launch["implementation_sha256"] == run.implementation_sha256()
    assert launch["worker_module"] == "ai_trader.training._local_training_worker"
    assert not launch["promotion_allowed"] and not launch["execution_allowed"]


@pytest.mark.parametrize(
    "change", ["steps", "time", "rank", "seed", "opt-in", "worker", "python", "source"]
)
def test_tampered_launch_refused_before_output(launch, change, monkeypatch):
    if change in ("steps", "time", "rank", "seed"):
        key = {
            "steps": "max_optimizer_steps",
            "time": "max_wall_time_seconds",
            "rank": "lora_rank",
            "seed": "seed",
        }[change]
        launch["recipe"][key] += 1
    elif change == "opt-in":
        launch["execution_allowed"] = True
    elif change == "worker":
        launch["worker_module"] = "arbitrary.module"
    elif change == "python":
        launch["python_executable"] += "wrong"
    else:
        monkeypatch.setattr(run, "implementation_sha256", lambda: "a" * 64)
    with pytest.raises(ValueError):
        run.run(launch, enable_local_training=True)
    assert not Path(launch["output_dir"]).exists()


@pytest.mark.parametrize("value", [False, None, 1, "yes"])
def test_explicit_opt_in_cannot_be_faked(launch, value):
    with pytest.raises(ValueError, match="Explicit"):
        run.run(launch, enable_local_training=value)
    assert not Path(launch["output_dir"]).exists()


@pytest.mark.parametrize(
    "name", ["suite", "review", "candidate", "registry", "runtime", "dependency_lock"]
)
def test_changed_input_pin_refused_before_dispatch(launch, name):
    launch["inputs"][name]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        run.run(launch, enable_local_training=True)
    assert not Path(launch["output_dir"]).exists()


def test_missing_dependencies_pending_reviews_and_reservations_block(launch):
    inputs = copy.deepcopy(launch["inputs"])
    runtime = json.loads(Path(inputs["runtime"]["path"]).read_text())
    runtime["packages"]["peft"] = None
    inputs["runtime"] = write_fixture(Path(inputs["runtime"]["path"]), runtime)
    with pytest.raises(ValueError, match="dependency"):
        run.prepare_run(inputs, launch["checkpoint"], "e" * 64, "f" * 64, launch["output_dir"])
    runtime["packages"]["peft"] = "1.0"
    inputs["runtime"] = write_fixture(Path(inputs["runtime"]["path"]), runtime)
    registry = json.loads(Path(inputs["registry"]["path"]).read_text())
    registry["unexposed_attested"] = False
    inputs["registry"] = write_fixture(Path(inputs["registry"]["path"]), registry)
    with pytest.raises(ValueError, match="reservation"):
        run.prepare_run(inputs, launch["checkpoint"], "e" * 64, "f" * 64, launch["output_dir"])
    review = json.loads(Path(inputs["review"]["path"]).read_text())
    review["cases"][0]["decision"] = "pending"
    inputs["review"] = write_fixture(Path(inputs["review"]["path"]), review)
    with pytest.raises(ValueError, match="blocks candidate"):
        run.prepare_run(inputs, launch["checkpoint"], "e" * 64, "f" * 64, launch["output_dir"])


@pytest.mark.parametrize(
    "text",
    [
        "",
        "peft==1.0",
        "-r other.txt",
        "--extra-index-url https://invalid",
        "peft @ https://invalid/x.whl",
        "peft==1.0 --hash=sha256:" + "a" * 64,
    ],
)
def test_dependency_lock_must_be_self_contained_and_complete(tmp_path, text):
    item = write_fixture(tmp_path / "lock.txt", text)
    with pytest.raises(ValueError):
        run._lock_pin(Path(item["path"]), item["sha256"])


def test_version_mismatch_and_duplicate_lock_entries(launch):
    item = launch["inputs"]["dependency_lock"]
    path = Path(item["path"])
    original = path.read_text()
    launch["inputs"]["dependency_lock"] = write_fixture(
        path, original.replace("peft==1.0", "peft==2.0")
    )
    with pytest.raises(ValueError, match="differ"):
        run.validate_launch(launch)
    item = write_fixture(path, original + "\n" + original.splitlines()[0])
    with pytest.raises(ValueError, match="Duplicate"):
        run._lock_pin(path, item["sha256"])


@pytest.mark.parametrize("suffix", ["", "adapter"])
def test_output_cannot_overlap_base(launch, suffix):
    path = str(Path(launch["checkpoint"]) / suffix)
    with pytest.raises(ValueError, match="overlap"):
        run.prepare_run(launch["inputs"], launch["checkpoint"], "e" * 64, "f" * 64, path)


def test_loop_is_fixed_count_repeatable_and_records_intent_before_step(launch, tmp_path):
    orders = []
    for name in ("first", "second"):
        directory = tmp_path / name
        directory.mkdir()
        observed = FakeBackend()
        original_step = observed.step

        def step(record, directory=directory, original_step=original_step):
            events = [
                json.loads(line) for line in (directory / "steps.jsonl").read_text().splitlines()
            ]
            assert events[-1]["event"] == "step_started"
            return original_step(record)

        observed.step = step
        result = run.train_loop(
            observed, ["a", "b", "c"], directory, launch["recipe"], deadline=1, clock=lambda: 0
        )
        assert result["completed_steps"] == 20 and len(observed.steps) == 20
        events = [json.loads(line) for line in (directory / "steps.jsonl").read_text().splitlines()]
        assert len(events) == 42 and events[-1]["event"] == "save_reload_completed"
        orders.append(observed.steps)
    assert orders[0] == orders[1]


def test_deadline_before_step_and_after_slow_step_do_not_save(launch, tmp_path):
    observed = FakeBackend()
    with pytest.raises(TimeoutError):
        run.train_loop(observed, ["a"], tmp_path, launch["recipe"], deadline=1, clock=lambda: 1)
    assert observed.steps == [] and not (tmp_path / "adapter").exists()
    later = tmp_path / "later"
    later.mkdir()
    times = iter((0, 2))
    with pytest.raises(TimeoutError):
        run.train_loop(
            observed, ["a"], later, launch["recipe"], deadline=1, clock=lambda: next(times)
        )
    assert len(observed.steps) == 1 and not (later / "adapter").exists()
    assert (
        len((later / "steps.jsonl").read_text().splitlines()) == 1
    )  # Only durable intent is certain.


@pytest.mark.parametrize(
    "metric,value",
    [
        ("loss", math.nan),
        ("loss", math.inf),
        ("loss", -1),
        ("gradient_norm", math.nan),
        ("gradient_norm", -1),
        ("loss", True),
    ],
)
def test_nonfinite_or_invalid_metrics_do_not_save(launch, tmp_path, metric, value):
    observed = FakeBackend()
    observed.step = lambda record: {"loss": 1.0, "gradient_norm": 0.1, metric: value}
    with pytest.raises(ValueError, match="metrics"):
        run.train_loop(observed, ["a"], tmp_path, launch["recipe"], deadline=1, clock=lambda: 0)
    assert not (tmp_path / "adapter").exists()


def test_journal_failure_prevents_first_optimizer_call(launch, tmp_path, monkeypatch):
    observed = FakeBackend()

    def fail(*args):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(run, "_event", fail)
    with pytest.raises(OSError):
        run.train_loop(observed, ["a"], tmp_path, launch["recipe"], deadline=1, clock=lambda: 0)
    assert observed.steps == []


def test_private_worker_and_parent_complete_with_fake_backend_only(launch, monkeypatch):
    install_fake_worker(monkeypatch)
    invocations = []

    def exchange(command, request, timeout):
        invocations.append((command, timeout))
        return canonical(worker.respond(canonical(request).encode()))

    monkeypatch.setattr(run, "_exchange", exchange)
    result = run.run(launch, enable_local_training=True)
    assert result["status"] == "completed_adapter_smoke"
    assert result["completed_steps"] == 20 and not result["promotion_allowed"]
    assert invocations == [([launch["python_executable"], "-I", "-m", run.WORKER], 600000)]
    assert not result["heldout_evaluated"]
    before = (Path(launch["output_dir"]) / "run.json").read_bytes()
    with pytest.raises(FileExistsError):
        run.run(launch, enable_local_training=True)
    assert (Path(launch["output_dir"]) / "run.json").read_bytes() == before


@pytest.mark.parametrize("failure", ["deadline", "overflow", "interrupt", "bad_response"])
def test_parent_failure_retains_quarantine_and_never_retries(launch, monkeypatch, failure):
    calls = []

    def exchange(*args):
        calls.append(args)
        if failure == "bad_response":
            return "{}"
        if failure == "interrupt":
            raise KeyboardInterrupt()
        raise LocalReviewError(
            "worker_deadline" if failure == "deadline" else "worker_output_or_pipe_limit"
        )

    monkeypatch.setattr(run, "_exchange", exchange)
    with pytest.raises((ValueError, KeyboardInterrupt)):
        run.run(launch, enable_local_training=True)
    result = json.loads((Path(launch["output_dir"]) / "run.json").read_text())
    assert len(calls) == 1 and result["completed_steps"] is None
    assert result["status"] == "failed_or_interrupted" and not result["automatic_retry_allowed"]


@pytest.mark.parametrize("change", ["steps", "reload", "loss", "tolerance", "authority", "adapter"])
def test_parent_rejects_wrong_results_even_with_correct_file_pin(launch, monkeypatch, change):
    install_fake_worker(monkeypatch)

    def exchange(command, request, timeout):
        reply = worker.respond(canonical(request).encode())
        directory = Path(launch["output_dir"])
        path = directory / "worker_result.json"
        result = json.loads(path.read_text())
        if change == "steps":
            result["completed_steps"] = 19
        elif change == "reload":
            result["reload"]["reload_state_equal"] = False
        elif change == "loss":
            result["reload"]["probe_loss_after"] = 7.0
        elif change == "tolerance":
            result["reload"]["probe_loss_absolute_tolerance"] = 10.0
        elif change == "authority":
            result["heldout_contents_opened"] = True
        else:
            (directory / "adapter" / "adapter_model.safetensors").write_bytes(b"tampered")
        reply["result_sha256"] = write_fixture(path, result)["sha256"]
        return canonical(reply)

    monkeypatch.setattr(run, "_exchange", exchange)
    with pytest.raises(ValueError):
        run.run(launch, enable_local_training=True)
    assert (
        json.loads((Path(launch["output_dir"]) / "run.json").read_text())["status"]
        == "failed_or_interrupted"
    )


def test_runtime_drift_refused_before_tokenization(launch, monkeypatch):
    directory = Path(launch["output_dir"])
    directory.mkdir()
    run._write(directory / "launch.json", launch)
    original = run.runtime_manifest()
    monkeypatch.setattr(run, "runtime_manifest", lambda: {**original, "machine": "different"})
    monkeypatch.setattr(run, "load_tokenizer", lambda *args: pytest.fail("Must not tokenize"))
    with pytest.raises(ValueError, match="runtime differs"):
        run.execute_worker(launch)


def test_private_worker_requires_strict_opt_in_and_budget(monkeypatch):
    monkeypatch.setattr(worker, "execute_worker", lambda plan: pytest.fail("Must not execute"))
    for raw in (
        b"{}",
        canonical({"enable_local_training": 1, "plan": {}}).encode(),
        b"x" * (run.MAX_REQUEST_BYTES + 1),
        b'{"plan":{},"plan":{}}',
    ):
        with pytest.raises(ValueError):
            worker.respond(raw)


def test_adapter_file_budgets_and_no_pickle(tmp_path, monkeypatch):
    observed = FakeBackend()
    path = tmp_path / "adapter"
    observed.save_reload(path, None)
    original = backend.adapter_manifest(path)
    assert len(original["files"]) == 2
    (path / "unsafe.bin").write_bytes(b"pickle is not allowed")
    with pytest.raises(ValueError, match="Unexpected"):
        backend.adapter_manifest(path)
    other = tmp_path / "bounded"
    observed.save_reload(other, None)
    monkeypatch.setattr(backend, "MAX_ADAPTER_BYTES", 1)
    with pytest.raises(ValueError, match="budget"):
        backend.adapter_manifest(other)


def test_only_bounded_lora_parameters_can_train():
    def model(entries):
        return SimpleNamespace(named_parameters=lambda: iter(entries))

    good = SimpleNamespace(requires_grad=True, numel=lambda: 10)
    frozen = SimpleNamespace(requires_grad=False, numel=lambda: 4_000_000_000)
    name = "base.model.layer.self_attn.q_proj.lora_A.default.weight"
    assert backend.trainable_adapters(model([(name, good), ("base.weight", frozen)])) == [good]
    with pytest.raises(ValueError, match="Non-adapter"):
        backend.trainable_adapters(model([("base.weight", good)]))
    with pytest.raises(ValueError, match="empty"):
        backend.trainable_adapters(model([("base.weight", frozen)]))
    huge = SimpleNamespace(requires_grad=True, numel=lambda: 4_000_001)
    with pytest.raises(ValueError, match="budget"):
        backend.trainable_adapters(model([(name, huge)]))


def test_cli_runtime_is_read_only_metadata_and_refuses_overwrite(tmp_path, monkeypatch):
    output = tmp_path / "runtime.json"
    monkeypatch.setattr(sys, "argv", ["training-run", "runtime", "--output", str(output)])
    assert run.main() == 0
    assert json.loads(output.read_text())["kind"] == "qwen_lora_runtime_versions_v1"
    with pytest.raises(FileExistsError):
        run.main()
