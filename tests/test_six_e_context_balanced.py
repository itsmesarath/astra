"""Synthetic class-coverage selection/native receipt tests; never actual model calls."""

import copy
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import test_six_e_context_lora as natural_tests
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_context_lora import (
    balance_frozen as balance_frozen,
)
from test_six_e_context_lora import (
    candidate as candidate,
)
from test_six_e_context_lora import encoder
from test_six_e_context_lora import (
    evidence as evidence,
)
from test_six_e_context_lora import (
    gpu_request as gpu_request,
)
from test_six_e_context_lora import (
    original as original,
)
from test_six_e_context_lora import (
    prepared as prepared,
)
from test_six_e_context_lora import (
    samples as samples,
)
from test_six_e_context_lora import (
    trial_request as trial_request,
)
from test_six_e_lora_trial import FakeBackend, pin, write

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.training import _six_e_context_balanced_worker as w
from ai_trader.training import six_e_context_balanced as s

natural_frozen = natural_tests.frozen


@pytest.fixture
def frozen(natural_frozen, monkeypatch):
    path, prior_pin, _ = natural_frozen
    root = path.parent
    cpu, full, diagnostic = [
        root / name for name in ("linked-cpu.json", "linked-full.json", "fit-proof.json")
    ]
    dirs = [root / name for name in ("old-fit", "old-train", "old-cpu", "old-dev")]
    for directory in dirs:
        directory.mkdir()
    cpu_pin = write(cpu, {"training_registration": {"path": str(path), "sha256": prior_pin}})
    full_pin = write(
        full,
        {
            "controls_registration": {"path": str(cpu), "sha256": cpu_pin},
            "training_trial": {"directory": str(dirs[1])},
            "controls_trial": {"directory": str(dirs[2])},
        },
    )
    proof_pin = write(
        diagnostic,
        {
            "completed_comparison": {
                "registration": str(full),
                "registration_sha256": full_pin,
                "directory": str(dirs[3]),
            }
        },
    )
    report_pin = write(dirs[0] / "run.json", {"status": "fixture_completed_fit_recall"})

    def proof(check_path, check_pin, directory, result_pin):
        assert check_path == diagnostic and directory == dirs[0]
        s.tokens.metadata(check_path, check_pin)
        s.tokens.metadata(directory / "run.json", result_pin)
        return {
            "status": "verified_seen_fit_diagnostic_not_validation",
            "diagnostic_conclusion": "collapse_on_seen_fit",
            "files": {},
        }

    monkeypatch.setattr(s.diagnostic, "verify_run", proof)
    output = root / "balanced-context-plan.json"
    value = s.freeze(diagnostic, proof_pin, dirs[0], report_pin, output)
    return output, pin(output), value


@pytest.fixture
def packet(frozen):
    path, plan_pin, value = frozen
    _, rows = s.registration(path, plan_pin)
    return s.worker_packet(value, rows, plan_pin, path.parent / "balanced-native-run")


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


def test_import_has_no_gpu_tokenizer_decoder_or_exchange_load():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_context_balanced, "
            "_six_e_context_balanced_worker; assert not "
            "({'torch','transformers','peft','tokenizers','databento_dbn','databento'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_recipe_changes_sampling_and_four_updates_only():
    before, after = s.natural.profile(), s.profile()
    assert set(k for k in before if before[k] != after[k]) == {
        "purpose",
        "selection",
        "max_optimizer_steps",
    }
    assert s.STEPS == 196 and s.PER_STATE == 28 and s.TIMEOUT_MS == 1800000
    assert s.natural.STEPS == 192
    assert all(s.protocol()[key] is False for key in s.FLAGS)
    assert not s.protocol()["registration_authorizes_execution"]


@pytest.mark.parametrize("bad", [True, 27, -1, 28.0, "28"])
def test_insufficient_or_noninteger_support_has_no_fallback(bad):
    counts = dict.fromkeys(s.STATES, 100)
    counts["SSS"] = bad
    with pytest.raises(ValueError):
        s.quotas(counts)


def test_selection_native_boundary_and_completion_masks(frozen, packet):
    path, plan_pin, value = frozen
    assert s.registration(path, plan_pin)[0] == value
    assert Counter(i["spec"]["joint_state"] for i in packet["selection"]) == dict.fromkeys(
        s.STATES, 28
    )
    assert len({i["spec"]["case_id"] for i in packet["selection"]}) == 196
    assert all(i["example"]["inner_partition"] == "fit" for i in packet["selection"])
    assert not {"dataset", "adapter", "diagnostic", "comparison", "reservation"} & packet.keys()
    assert [s.natural.order_key(i["example"]) for i in packet["selection"]] == sorted(
        s.natural.order_key(i["example"]) for i in packet["selection"]
    )
    records = s.token_records(packet, encoder)
    assert records[0]["labels"][:2] == [-100, -100]
    assert records[0]["labels"][4] == 151643 and records[0]["labels"][5] == -100


def test_all_memberships_precede_any_prompt_target_or_serialization(packet):
    class Poison(dict):
        def __getitem__(self, key):
            assert key not in {"prompt", "completion"}
            return super().__getitem__(key)

    for item in packet["selection"]:
        item["example"] = Poison(item["example"])
    packet["selection"][-1]["example"]["inner_partition"] = "check"
    with pytest.raises(ValueError, match="before prompt"):
        s.validate_packet(packet)
    with pytest.raises(ValueError, match="before prompt"):
        s.curriculum([i["example"] for i in packet["selection"]], packet["session_split"])
    with pytest.raises(ValueError, match="before prompt"):
        s.token_records(packet, encoder)


def test_sampling_is_fit_only_deterministic_and_rejects_duplicate_pool(frozen):
    path, plan_pin, value = frozen
    _, rows = s.registration(path, plan_pin)
    expected = s.curriculum(rows, value["session_split"])
    check = Path(value["inputs"]["dataset"]["path"]) / "check.jsonl"
    check.write_bytes(b"never read by selection")
    assert s.curriculum(copy.deepcopy(rows), value["session_split"]) == expected
    rows[1] = copy.deepcopy(rows[0])
    with pytest.raises(ValueError, match="Unique chronological"):
        s.curriculum(rows, value["session_split"])


@pytest.mark.parametrize(
    "change",
    ["source", "step_count", "extra", "order", "duplicate", "tokens", "quota", "opt_in", "overlap"],
)
def test_packet_mutation_refused_before_native_backend(packet, change):
    if change == "source":
        packet["source_sha256"] = "0" * 64
    elif change == "step_count":
        packet["profile"]["max_optimizer_steps"] = 197
    elif change == "extra":
        packet["adapter"] = "old-adapter-forbidden"
    elif change == "order":
        packet["selection"].reverse()
    elif change == "duplicate":
        packet["selection"][0] = packet["selection"][1]
    elif change == "tokens":
        packet["selection"][0]["spec"]["prompt_tokens"] += 1
    elif change == "quota":
        packet["fit_joint_counts"]["SSS"] = 27
    elif change == "opt_in":
        packet["enable_research_training"] = False
    else:
        packet["output_dir"] = packet["checkpoint"]
    with pytest.raises(ValueError):
        s.validate_packet(packet)


@pytest.mark.parametrize(
    "change", ["selection", "source", "authority", "prior", "diagnostic", "comparison"]
)
def test_rehashed_registration_drift_refused(frozen, change):
    path, _, value = frozen
    if change == "selection":
        value["selection"][0] = value["selection"][1]
    elif change == "source":
        value["source_sha256"] = "0" * 64
    elif change == "authority":
        value["promotion_allowed"] = True
    elif change == "prior":
        value["natural_registration"]["sha256"] = "0" * 64
    elif change == "diagnostic":
        value["diagnostic"]["report_sha256"] = "0" * 64
    else:
        value["comparison"]["cases"] -= 1
    with pytest.raises(ValueError):
        s.registration(path, write(path, value))


def test_real_worker_loop_with_fake_backend_and_durable_receipt(packet, monkeypatch):
    backend = install(packet, monkeypatch)
    result = w.respond(canonical(packet).encode())
    out = Path(packet["output_dir"])
    assert (
        len(backend.records)
        == result["steps"]
        == len(s.validate_result(result, packet, out))
        == 196
    )
    assert json.loads((out / "native_result.json").read_text()) == result
    assert len((out / "steps.jsonl").read_text().splitlines()) == 396


@pytest.mark.parametrize("change", ["offline", "version", "request", "tokenization"])
def test_worker_preflight_refuses_before_backend(packet, monkeypatch, change):
    install(packet, monkeypatch)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "version":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "request":
        write(Path(packet["output_dir"]) / "request.json", {})
    else:
        monkeypatch.setattr(s.tokens.token_plan, "load_tokenizer", lambda *args: lambda _: [99])
    monkeypatch.setattr(w, "create_backend", lambda *args: pytest.fail("Native backend loaded"))
    with pytest.raises(ValueError):
        w.respond(canonical(packet).encode())


@pytest.mark.parametrize(
    "change",
    [
        "steps",
        "journal",
        "subset",
        "binding",
        "summary",
        "adapter",
        "authority",
        "reload",
        "resources",
        "receipt_missing",
        "receipt_changed",
    ],
)
def test_full_result_guards_and_no_subset(packet, monkeypatch, change):
    install(packet, monkeypatch)
    result = w.respond(canonical(packet).encode())
    out = Path(packet["output_dir"])
    if change == "steps":
        result["steps"] -= 1
    elif change in {"journal", "subset", "binding"}:
        journal = out / "steps.jsonl"
        raw = journal.read_bytes()
        raw = (
            raw + b"extra\n"
            if change == "journal"
            else b"\n".join(raw.splitlines()[:-3]) + b"\n"
            if change == "subset"
            else raw.replace(packet["selection"][0]["spec"]["case_id"].encode(), b"changed")
        )
        journal.write_bytes(raw)
        result["journal"] = s.journal_info(journal)
    elif change == "summary":
        result["summary"]["last_loss"] += 1
    elif change == "adapter":
        (out / "adapter/adapter_model.safetensors").write_bytes(b"changed")
    elif change == "authority":
        result["trading_enabled"] = True
    elif change == "reload":
        result["reload"]["probe_loss_after"] += 1
    elif change == "resources":
        result["resources"]["peak_reserved_bytes"] = result["resources"]["total_bytes"] + 1
    if change == "receipt_missing":
        (out / "native_result.json").unlink()
    else:
        write(out / "native_result.json", {} if change == "receipt_changed" else result)
    with pytest.raises((ValueError, OSError)):
        s.validate_result(result, packet, out)


@pytest.mark.parametrize("failure", [None, "timeout", "drift"])
def test_parent_one_dispatch_and_readonly_full_verification(frozen, monkeypatch, failure):
    path, plan_pin, _ = frozen
    output = path.parent / "new-balanced-parent-run"
    calls, original = [], s.registration

    def registration(*args):
        if calls and failure == "drift":
            raise ValueError("Frozen input changed")
        return original(*args)

    monkeypatch.setattr(s, "registration", registration)

    def dispatch(command, packet, timeout):
        calls.append((command, timeout))
        if failure == "timeout":
            raise LocalReviewError("worker_deadline")
        install(packet, monkeypatch, owned=True)
        return canonical(w.respond(canonical(packet).encode()))

    monkeypatch.setattr(s, "_exchange", dispatch)
    if failure:
        with pytest.raises((ValueError, LocalReviewError)):
            s.run(path, plan_pin, output, enable_research_training=True)
        assert (
            json.loads((output / "run.json").read_text())["status"]
            == "failed_or_interrupted_no_partial_success"
        )
    else:
        report = s.run(path, plan_pin, output, enable_research_training=True)
        assert report["metric_count"] == 196 and report["adapter_quarantined"]
        assert report["selected_joint_counts"] == dict.fromkeys(s.STATES, 28)
        assert not report["evaluation_performed"] and not report["full_training_epoch"]
        before = {p: pin(p) for p in output.iterdir() if p.is_file()}
        monkeypatch.setattr(s, "_exchange", lambda *args: pytest.fail("Verifier launched model"))
        verified = s.verify_run(path, plan_pin, output, pin(output / "run.json"))
        assert verified["updates"] == 196 and verified["journal_events"] == 396
        assert before == {p: pin(p) for p in output.iterdir() if p.is_file()}
        report["metric_count"] = 195
        with pytest.raises(ValueError):
            s.verify_run(path, plan_pin, output, write(output / "run.json", report))
    monkeypatch.setattr(s, "registration", original)
    with pytest.raises(ValueError, match="exclusive"):
        s.run(path, plan_pin, output, enable_research_training=True)
    assert len(calls) == 1 and calls[0][1] == 1800000 and calls[0][0][-1] == s.WORKER


def test_opt_in_before_all_inputs(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        s.run(tmp_path / "missing", "bad", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_all_old_outputs_and_inputs_are_protected(frozen):
    _, _, value = frozen
    for name in (
        *value["protected_evidence"],
        value["diagnostic"]["directory"],
        value["assets"]["checkpoint"],
        value["inputs"]["dataset"]["path"],
    ):
        with pytest.raises(ValueError):
            s.disjoint(Path(name) / "must-not-create", value)


def test_worker_failure_is_retained_and_never_retried(packet, monkeypatch):
    backend = install(packet, monkeypatch)
    step = backend.step

    def failed(record):
        if len(backend.records) == 6:
            raise RuntimeError("Synthetic optimizer failure")
        return step(record)

    monkeypatch.setattr(backend, "step", failed)
    with pytest.raises(RuntimeError):
        w.respond(canonical(packet).encode())
    out = Path(packet["output_dir"])
    assert json.loads((out / "failure.json").read_text())["completed_steps_unverified"] == 6
    assert not (out / "native_result.json").exists() and not (out / "adapter").exists()
    with pytest.raises(ValueError, match="supervisor-owned"):
        w.respond(canonical(packet).encode())


def test_deadline_prevents_native_initialization(packet, monkeypatch):
    install(packet, monkeypatch)
    ticks = iter((0.0, 1801.0))
    monkeypatch.setattr(w.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(w, "create_backend", lambda *args: pytest.fail("Native load after limit"))
    with pytest.raises(TimeoutError):
        w.respond(canonical(packet).encode())
    failure = json.loads((Path(packet["output_dir"]) / "failure.json").read_text())
    assert failure["completed_steps_unverified"] == 0 and failure["error_type"] == "TimeoutError"
