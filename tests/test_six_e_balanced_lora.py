"""Synthetic selected-only native batches; no actual model, reserved files or trades."""

import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import test_six_e_balance_plan as balance_tests
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_balance_plan import original as original
from test_six_e_balance_plan import samples as samples
from test_six_e_forecast_eval import candidate as candidate
from test_six_e_forecast_eval import trial_request as trial_request
from test_six_e_lora_trial import FakeBackend, encoder, pin, write
from test_six_e_lora_trial import gpu_request as gpu_request

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.training import _six_e_balanced_worker as w
from ai_trader.training import six_e_balanced_lora as s

balance_frozen = balance_tests.frozen


@pytest.fixture
def frozen(balance_frozen):
    path, plan_pin, _ = balance_frozen
    directory = path.parent / "controls"
    s.balance.run(path, plan_pin, directory, enable_cpu_controls=True)
    output = path.parent / "balanced-registration.json"
    value = s.freeze(
        path,
        plan_pin,
        directory,
        pin(directory / "run.json"),
        pin(directory / "models.json"),
        output,
    )
    return output, pin(output), value


@pytest.fixture
def packet(frozen):
    path, frozen_pin, value = frozen
    _, _, rows = s.registration(path, frozen_pin)
    return s.worker_packet(value, rows, frozen_pin, path.parent / "balanced-run")


def install(packet, monkeypatch, *, owned=False):
    directory = Path(packet["output_dir"])
    if not owned:
        directory.mkdir()
        write(directory / "request.json", packet)
    for key in (
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ):
        monkeypatch.setenv(key, "1")
    pins, runtime = s.validate_packet(packet)
    monkeypatch.setattr(w, "runtime_manifest", lambda: runtime)
    monkeypatch.setattr(w, "version", lambda name: pins[name])
    backend = FakeBackend()
    monkeypatch.setattr(w, "create_backend", lambda *args: backend)
    monkeypatch.setattr(w, "verify_frozen_parameters", lambda *args: None)
    monkeypatch.setattr(w, "resources", lambda *args: gpu_resources())
    monkeypatch.setattr(w, "trainable_adapters", lambda *args: [backend.parameter])
    return backend


def test_import_is_pure():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_balanced_lora; "
            "assert not ({'torch','peft','transformers','tokenizers','databento','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_recipe_does_not_modify_original_trials():
    assert s.profile()["max_optimizer_steps"] == 224
    assert s.profile()["max_wall_time_seconds"] == 1800
    assert s.profile()["limits_enforced_by_training_worker"] is True
    assert s.trial.profile()["max_optimizer_steps"] == 20
    assert (
        s.balance.protocol()["qwen_curriculum"]["recipe"]["limits_enforced_by_training_worker"]
        is False
    )
    assert s.protocol()["comparison"]["run_now"] is False
    assert all(s.protocol()[k] is False for k in s.FLAGS)


def test_frozen_balanced_fit_and_disjoint_even_check_selection(frozen):
    path, frozen_pin, value = frozen
    selected, check, split = value["selection"], value["comparison"], value["session_split"]
    assert len(selected) == len({r["case_id"] for r in selected}) == 224
    assert Counter(r["joint_state"] for r in selected) == dict.fromkeys(s.balance.STATES, 32)
    assert all(r["source_session"] in split["fit"] for r in selected)
    assert len(check) == len({r["case_id"] for r in check}) == 80
    assert [r["check_index"] for r in check] == s.balance.even_indices(112, 80)
    assert all(r["source_session"] in split["check"] for r in check)
    assert not ({r["case_id"] for r in check} & {r["case_id"] for r in selected})
    assert s.registration(path, frozen_pin)[0] == value


def test_packet_contains_only_fit_examples_and_no_dataset_adapter_or_check(packet):
    assert not ({"dataset", "balance_plan", "controls", "comparison", "adapter"} & set(packet))
    records = s.token_records(packet, encoder)
    assert len(records) == 224 and len(canonical(packet).encode()) < s.MAX_REQUEST_BYTES
    for record in records:
        assert record["labels"][:2] == [-100, -100]
        assert record["labels"][2:5] == [20, 21, 151643]
        assert record["labels"][5:] == [-100] * 2299
        assert sum(record["attention_mask"]) == 5


@pytest.mark.parametrize(
    "change",
    [
        "source",
        "profile",
        "bool_profile",
        "optin",
        "extra",
        "split",
        "calendar",
        "count",
        "order",
        "duplicate",
        "index",
        "target",
        "token",
        "base_pin",
        "runtime_pin",
        "output",
    ],
)
def test_packet_mutation_refused(packet, change):
    if change == "source":
        packet["source_sha256"] = "0" * 64
    elif change == "profile":
        packet["profile"]["max_optimizer_steps"] = 225
    elif change == "bool_profile":
        packet["profile"]["limits_enforced_by_training_worker"] = 1
    elif change == "optin":
        packet["enable_research_training"] = 1
    elif change == "extra":
        packet["adapter"] = "old-adapter"
    elif change == "split":
        packet["session_split"]["fit"].append(packet["session_split"]["check"][0])
    elif change == "calendar":
        packet["session_split"]["check"][-1] = "2026-01-01"
    elif change == "count":
        packet["selection"].pop()
    elif change == "order":
        packet["selection"][0], packet["selection"][1] = (
            packet["selection"][1],
            packet["selection"][0],
        )
    elif change == "duplicate":
        packet["selection"][7] = packet["selection"][0]
    elif change == "index":
        packet["selection"][0]["spec"]["example_index"] = True
    elif change == "target":
        packet["selection"][0]["example"]["target_sha256"] = "0" * 64
    elif change == "token":
        packet["selection"][0]["spec"]["prompt_tokens"] = 2049
    elif change == "base_pin":
        packet["checkpoint_sha256"] = "0" * 64
    elif change == "runtime_pin":
        packet["runtime_sha256"] = "0" * 64
    else:
        packet["output_dir"] = packet["checkpoint"]
    with pytest.raises(ValueError):
        s.validate_packet(packet)


@pytest.mark.parametrize("role", ["test_development", "validation_development", "train"])
def test_role_and_inner_check_gate_precedes_poison_prompt(packet, role):
    class Poison(dict):
        def __getitem__(self, key):
            if key == "role":
                return role
            if key == "source_session":
                return packet["session_split"]["check"][0]
            pytest.fail("Read poison example before role/session gate")

    packet["selection"][0]["example"] = Poison()
    with pytest.raises(ValueError, match="before prompt"):
        s.validate_packet(packet)


@pytest.mark.parametrize("change", ["record", "counts", "encoding"])
def test_native_tokens_bound_to_record_masks(packet, change):
    if change == "record":
        packet["selection"][0]["spec"]["record_sha256"] = "0" * 64
    elif change == "counts":
        packet["selection"][0]["spec"]["prompt_tokens"] += 1
    with pytest.raises(ValueError):
        s.token_records(packet, (lambda text: [99]) if change == "encoding" else encoder)


def test_native_all_224_steps_small_receipt_and_no_dataset_access(packet, monkeypatch):
    backend = install(packet, monkeypatch)
    old_open = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "train.jsonl",
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
            "models.json",
            "balance-plan.json",
        }
        assert path.suffix not in {".dbn", ".zip"}
        return old_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    monkeypatch.setattr(
        s, "load_balance", lambda *args: pytest.fail("Native worker loaded upstream dataset")
    )
    result = w.respond(canonical(packet).encode())
    assert len(backend.records) == result["steps"] == 224
    assert len(canonical(result).encode()) < 16 * 1024
    assert len(s.validate_result(result, packet, Path(packet["output_dir"]))) == 224
    assert result["journal"]["bytes"] < s.MAX_JOURNAL_BYTES


@pytest.mark.parametrize("change", ["offline", "version", "saved", "tokens", "stale"])
def test_native_preflight_refuses_before_loading(packet, monkeypatch, change):
    install(packet, monkeypatch)
    directory = Path(packet["output_dir"])
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "version":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "saved":
        write(directory / "request.json", {})
    elif change == "tokens":
        monkeypatch.setattr(s.trial.token_plan, "load_tokenizer", lambda *args: lambda text: [99])
    else:
        write(directory / "failure.json", {})
    monkeypatch.setattr(
        w, "create_backend", lambda *args: pytest.fail("Native loading on refused preflight")
    )
    with pytest.raises(ValueError):
        w.respond(canonical(packet).encode())


@pytest.mark.parametrize("change", ["step", "metric", "frozen", "reload", "timeout", "parameters"])
def test_native_failures_preserve_evidence_not_private_error(packet, monkeypatch, change):
    backend = install(packet, monkeypatch)

    def fail(*args):
        raise RuntimeError("private raw error never persisted")

    if change == "step":
        original_step = backend.step

        def fail_after_three(record):
            if len(backend.records) == 3:
                fail()
            return original_step(record)

        monkeypatch.setattr(backend, "step", fail_after_three)
    elif change == "metric":
        monkeypatch.setattr(
            backend, "step", lambda record: {"loss": float("inf"), "gradient_norm": 0.5}
        )
    elif change == "frozen":
        monkeypatch.setattr(w, "verify_frozen_parameters", fail)
    elif change == "reload":
        monkeypatch.setattr(backend, "save_reload", fail)
    elif change == "parameters":
        monkeypatch.setattr(backend.parameter, "numel", lambda: s.MAX_TRAINABLE_PARAMETERS + 1)
    else:
        calls = iter([0, 0, 1801])
        monkeypatch.setattr(w.time, "monotonic", lambda: next(calls))
    with pytest.raises((RuntimeError, ValueError, TimeoutError)):
        w.respond(canonical(packet).encode())
    raw = (Path(packet["output_dir"]) / "failure.json").read_text()
    assert "private raw" not in raw and json.loads(raw)["adapter_quarantined"]
    assert not (Path(packet["output_dir"]) / "run.json").exists()
    if change == "step":
        assert json.loads(raw)["completed_steps_unverified"] == 3


@pytest.mark.parametrize(
    "change",
    [
        "steps",
        "summary",
        "journal",
        "framing",
        "binding",
        "subset",
        "adapter",
        "reload",
        "authority",
        "resources",
    ],
)
def test_incomplete_or_changed_result_never_accepted(packet, monkeypatch, change):
    install(packet, monkeypatch)
    result = w.respond(canonical(packet).encode())
    directory = Path(packet["output_dir"])
    journal = directory / "steps.jsonl"
    if change == "steps":
        result["steps"] = 223
    elif change == "summary":
        result["summary"]["last_loss"] += 1
    elif change == "journal":
        result["journal"]["sha256"] = "0" * 64
    elif change in {"framing", "binding", "subset"}:
        raw = journal.read_bytes()
        if change == "framing":
            raw = raw[:-1]
        elif change == "binding":
            raw = raw.replace(packet["selection"][0]["spec"]["case_id"].encode(), b"changed")
        else:
            raw = b"\n".join(raw.splitlines()[:-3]) + b"\n"
        journal.write_bytes(raw)
        result["journal"] = s.journal_info(journal)
    elif change == "adapter":
        (directory / "adapter" / "adapter_model.safetensors").write_bytes(b"changed")
    elif change == "reload":
        result["reload"]["probe_loss_after"] += 0.1
    elif change == "authority":
        result["trading_enabled"] = True
    else:
        result["resources"]["peak_allocated_bytes"] = result["resources"]["total_bytes"] + 1
    with pytest.raises(ValueError):
        s.validate_result(result, packet, directory)


@pytest.mark.parametrize(
    "change", ["selection", "comparison", "authority", "control_pin", "source"]
)
def test_rehashed_registration_changes_refused(frozen, change):
    path, _, value = frozen
    value = copy.deepcopy(value)
    if change == "selection":
        value["selection"][0] = value["selection"][1]
    elif change == "comparison":
        value["comparison"][0]["check_index"] += 1
    elif change == "authority":
        value["promotion_eligible"] = True
    elif change == "control_pin":
        value["controls"]["models_sha256"] = "0" * 64
    else:
        value["source_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        s.registration(path, write(path, value))


def test_distinct_cpu_provenance_exe_allowed_but_other_runtime_drift_refused(
    balance_frozen, tmp_path
):
    path, _, plan = balance_frozen
    fake_exe = tmp_path / "cpu-venv" / "Scripts" / "python.exe"
    fake_exe.parent.mkdir(parents=True)
    fake_exe.write_bytes(b"known fixture")
    dist = fake_exe.parent.parent / "Lib" / "site-packages" / "numpy-99.0.dist-info"
    dist.mkdir(parents=True)
    (dist / "METADATA").write_text("Name: numpy\nVersion: 99.0\n", encoding="utf-8")
    plan["cpu_runtime"]["python_executable"] = str(fake_exe)
    plan["cpu_runtime"]["numpy"] = "99.0"
    assert s.load_balance(path, write(path, plan))[0] == plan
    plan["cpu_runtime"]["numpy"] = "different"
    with pytest.raises(ValueError, match="provenance"):
        s.load_balance(path, write(path, plan))


def test_opt_in_before_reads(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        s.run(tmp_path / "missing", "bad", tmp_path / "output")
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("failure", [None, "timeout", "drift"])
def test_parent_one_dispatch_no_retry_and_final_revalidation(frozen, monkeypatch, failure):
    path, frozen_pin, _ = frozen
    output = path.parent / "new-parent-run"
    calls = []
    registration = s.registration

    def drift(*args):
        if calls:
            raise ValueError("Pinned input changed")
        return registration(*args)

    if failure == "drift":
        monkeypatch.setattr(s, "registration", drift)

    def dispatch(command, packet, timeout):
        calls.append((command, timeout))
        if failure == "timeout":
            raise LocalReviewError("worker_deadline")
        install(packet, monkeypatch, owned=True)
        return canonical(w.respond(canonical(packet).encode()))

    monkeypatch.setattr(s, "_exchange", dispatch)
    if failure:
        with pytest.raises((LocalReviewError, ValueError)):
            s.run(path, frozen_pin, output, enable_research_training=True)
        assert (
            json.loads((output / "run.json").read_text())["status"]
            == "failed_or_interrupted_no_partial_success"
        )
    else:
        report = s.run(path, frozen_pin, output, enable_research_training=True)
        assert report["metric_count"] == 224 and report["selected_training_sessions"] == 6
        assert report["adapter_quarantined"] and not report["evaluation_performed"]
        assert all(report[k] is False for k in s.FLAGS)
        with pytest.raises(FileExistsError):
            s.run(path, frozen_pin, output, enable_research_training=True)
    assert len(calls) == 1 and calls[0][1] == 1_800_000 and calls[0][0][-1] == s.WORKER


def test_freeze_and_run_cannot_overlap_protected_inputs(frozen):
    path, frozen_pin, value = frozen
    _, request, _ = s.registration(path, frozen_pin)
    for output in (
        Path(request["dataset"]) / "bad",
        Path(request["checkpoint"]) / "bad",
        Path(request["output_dir"]) / "bad",
        Path(value["controls"]["directory"]) / "bad",
        path.parent,
    ):
        with pytest.raises(ValueError):
            s.disjoint(output, request, value)
