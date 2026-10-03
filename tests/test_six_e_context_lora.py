"""Natural-prior context-v2 registration and fake native workers; never real training."""

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from test_qwen_gpu_smoke import gpu_resources
from test_six_e_context_data import balance_frozen as balance_frozen
from test_six_e_context_data import candidate as candidate
from test_six_e_context_data import evidence as evidence
from test_six_e_context_data import gpu_request as gpu_request
from test_six_e_context_data import original as original
from test_six_e_context_data import prepared as prepared
from test_six_e_context_data import samples as samples
from test_six_e_context_data import trial_request as trial_request
from test_six_e_lora_trial import FakeBackend, pin, write

from ai_trader.models.local_checkpoint import canonical
from ai_trader.models.local_reviewer import LocalReviewError
from ai_trader.training import _six_e_context_worker as w
from ai_trader.training import six_e_context_lora as s


def encoder(text):
    return [10, 11] if text.startswith(s.task.PREFIX) else [20, 21]


@pytest.fixture
def frozen(prepared, gpu_request, trial_request, monkeypatch):
    root, dataset, receipt, receipt_pin, _ = prepared
    monkeypatch.setattr(s, "version", lambda name: "fixture")
    monkeypatch.setattr(s.tokens.token_plan, "load_tokenizer", lambda *args: encoder)
    assets = {k: gpu_request[k] for k in (*s.ASSET_PATHS, *s.ASSET_PINS) if k in gpu_request}
    assets.update(
        tokenizer_json=str(Path(gpu_request["checkpoint"]) / "tokenizer.json"),
        tokenizer_sha256=pin(Path(gpu_request["checkpoint"]) / "tokenizer.json"),
    )
    asset_file = root / "context-assets.json"
    asset_pin = write(
        asset_file,
        {
            "kind": s.legacy.KIND,
            "protocol": s.legacy.protocol(),
            "source_sha256": s.legacy.source_sha256(),
            "assets": assets,
            "balance_plan": {},
            "controls": {},
            "selection": [],
            "comparison": [],
            "session_split": receipt["session_split"],
            **s.legacy.FLAGS,
        },
    )
    preflight = root / "context-training-tokens.json"
    s.tokens.audit_tokens(
        dataset,
        receipt_pin,
        preflight,
        encode=encoder,
        tokenizer_pin=assets["tokenizer_sha256"],
        tokenizer_version="fixture",
        eos=151643,
        pad=151643,
    )
    reservation = Path(trial_request["reservation"])
    path = root / "context-training-registration.json"
    value = s.freeze(
        dataset,
        receipt_pin,
        preflight,
        pin(preflight),
        asset_file,
        asset_pin,
        reservation,
        pin(reservation),
        path,
    )
    return path, pin(path), value


@pytest.fixture
def packet(frozen):
    path, plan_pin, value = frozen
    _, rows = s.registration(path, plan_pin)
    return s.worker_packet(value, rows, plan_pin, path.parent / "context-native-run")


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


def test_import_has_no_decoder_gpu_or_tokenizer_loading():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_context_lora, _six_e_context_worker; "
            "assert not ({'torch','transformers','peft','tokenizers','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_fixed_recipe_has_context_task_natural_priors_and_no_old_adapter():
    assert s.profile()["task"] == s.task.TASK
    assert s.profile()["max_optimizer_steps"] == 192
    assert s.profile()["max_wall_time_seconds"] == 1800
    assert s.protocol()["comparison"]["scope"].startswith("ALL")
    assert s.protocol()["comparison"]["controls"] == [
        "no_opportunity",
        "inner_fit_joint_prior",
        "natural_context_joint_linear",
    ]
    assert s.legacy.STEPS == 224 and s.legacy.task.TASK != s.task.TASK
    assert all(s.protocol()[k] is False for k in s.FLAGS)


def test_largest_remainder_preserves_natural_counts_without_minority_bonus():
    counts = dict(zip(s.STATES, (11573, 691, 580, 245, 708, 580, 293), strict=True))
    result = s.quotas(counts)
    assert list(result.values()) == [151, 9, 8, 3, 9, 8, 4]
    assert sum(result.values()) == 192
    for state, value in result.items():
        assert abs(value - 192 * counts[state] / sum(counts.values())) < 1
    assert s.quotas(dict(zip(s.STATES, (10000, 1, 0, 0, 0, 0, 0), strict=True)))["LNN"] == 0


@pytest.mark.parametrize("bad", [True, -1, 0.5, "1"])
def test_prior_count_types_are_strict(bad):
    counts = dict.fromkeys(s.STATES, 100)
    counts["NNN"] = bad
    with pytest.raises(ValueError):
        s.quotas(counts)


def test_full_check_frozen_but_native_request_contains_selected_fit_only(frozen, packet):
    path, plan_pin, value = frozen
    assert s.registration(path, plan_pin)[0] == value
    assert value["comparison"]["cases"] == 112 and value["comparison"]["sessions"] == 2
    assert value["comparison"]["file"]["count"] == 112
    assert len(value["comparison"]["ordered_examples_sha256"]) == 64
    assert (
        len(packet["selection"]) == len({i["spec"]["case_id"] for i in packet["selection"]}) == 192
    )
    assert Counter(i["spec"]["joint_state"] for i in packet["selection"]) == s.quotas(
        packet["fit_joint_counts"]
    )
    assert all(
        i["example"]["inner_partition"] == "fit"
        and i["example"]["source_session"] in packet["session_split"]["fit"]
        for i in packet["selection"]
    )
    assert not (
        {"dataset", "comparison", "adapter", "reservation", "controls", "rows"} & set(packet)
    )
    assert len(canonical(packet).encode()) <= s.MAX_REQUEST_BYTES
    assert [s.order_key(i["example"]) for i in packet["selection"]] == sorted(
        s.order_key(i["example"]) for i in packet["selection"]
    )
    records = s.token_records(packet, encoder)
    assert records[0]["labels"][:2] == [-100, -100]
    assert records[0]["labels"][4] == 151643 and records[0]["labels"][5] == -100


def test_check_poison_refused_before_prompt_or_target(packet):
    class Poison(dict):
        def __getitem__(self, key):
            assert key not in {"prompt", "completion"}
            return super().__getitem__(key)

    item = packet["selection"][0]
    item["example"] = Poison(item["example"])
    item["example"]["inner_partition"] = "check"
    with pytest.raises(ValueError, match="before prompt"):
        s.validate_packet(packet)
    with pytest.raises(ValueError, match="inner-fit"):
        s.curriculum([item["example"]], packet["session_split"])


@pytest.mark.parametrize(
    "change",
    [
        "steps",
        "extra",
        "source",
        "duplicate",
        "order",
        "counts",
        "tokens",
        "example",
        "base",
        "tokenizer",
        "overlap",
    ],
)
def test_packet_mutations_refused_before_backend(packet, change):
    if change == "steps":
        packet["profile"]["max_optimizer_steps"] += 1
    elif change == "extra":
        packet["dataset"] = "forbidden"
    elif change == "source":
        packet["source_sha256"] = "0" * 64
    elif change == "duplicate":
        packet["selection"][0] = packet["selection"][1]
    elif change == "order":
        packet["selection"].reverse()
    elif change == "counts":
        packet["fit_joint_counts"]["NNN"] += 10000
    elif change == "tokens":
        packet["selection"][0]["spec"]["active_tokens"] += 1
    elif change == "example":
        packet["selection"][0]["example"]["causal_prefix_sha256"] = "0" * 64
    elif change == "base":
        packet["checkpoint_sha256"] = "0" * 64
    elif change == "tokenizer":
        packet["tokenizer_json"] = str(Path(packet["checkpoint"]).parent / "other.json")
    else:
        packet["output_dir"] = packet["checkpoint"]
    with pytest.raises(ValueError):
        s.validate_packet(packet)


def test_curriculum_is_invariant_to_check_labels(prepared):
    _, directory, receipt, _, _ = prepared
    fit = [r for r, _, _ in s.tokens.read_examples(directory, "fit", receipt)]
    before = s.curriculum(fit, receipt["session_split"])
    check = directory / "check.jsonl"
    check.write_bytes(b"not read by fit-only selection")
    assert s.curriculum(fit, receipt["session_split"]) == before


@pytest.mark.parametrize(
    "change",
    [
        "selection",
        "comparison",
        "authority",
        "source",
        "preflight",
        "reservation",
        "fit_file",
        "unknown_file",
    ],
)
def test_rehashed_registration_or_input_mutations_refused(frozen, change):
    path, plan_pin, value = frozen
    if change == "selection":
        value["selection"][0] = value["selection"][1]
    elif change == "comparison":
        value["comparison"]["cases"] -= 1
    elif change == "authority":
        value["execution_allowed"] = True
    elif change == "source":
        value["source_sha256"] = "0" * 64
    elif change in {"preflight", "reservation"}:
        file = Path(value["inputs"][change]["path"])
        contents = json.loads(file.read_text())
        contents["training_authorized"] = True
        value["inputs"][change]["sha256"] = write(file, contents)
    else:
        directory = Path(value["inputs"]["dataset"]["path"])
        file = directory / ("fit.jsonl" if change == "fit_file" else "unavailable.jsonl")
        file.write_bytes(file.read_bytes() + b"changed")
    if change in {"selection", "comparison", "authority", "source", "preflight", "reservation"}:
        plan_pin = write(path, value)
    with pytest.raises(ValueError):
        s.registration(path, plan_pin)


def test_real_worker_logic_runs_exact_steps_and_reload_with_fake_backend(packet, monkeypatch):
    backend = install(packet, monkeypatch)
    result = w.respond(canonical(packet).encode())
    assert len(backend.records) == result["steps"] == 192
    assert len(s.validate_result(result, packet, Path(packet["output_dir"]))) == 192
    assert result["reload"]["base_checkpoint_unchanged"]


@pytest.mark.parametrize("change", ["offline", "version", "request", "tokenization"])
def test_worker_refuses_bad_preflight_before_native_initialization(packet, monkeypatch, change):
    install(packet, monkeypatch)
    if change == "offline":
        monkeypatch.delenv("HF_HUB_OFFLINE")
    elif change == "version":
        monkeypatch.setattr(w, "version", lambda name: "wrong")
    elif change == "request":
        write(Path(packet["output_dir"]) / "request.json", {})
    else:
        monkeypatch.setattr(s.tokens.token_plan, "load_tokenizer", lambda *args: lambda _: [99])
    monkeypatch.setattr(w, "create_backend", lambda *args: pytest.fail("Native initialization"))
    with pytest.raises(ValueError):
        w.respond(canonical(packet).encode())


@pytest.mark.parametrize(
    "change",
    ["steps", "journal", "subset", "binding", "adapter", "authority", "reload", "resources"],
)
def test_result_needs_all_durable_updates_persistence_and_no_authority(packet, monkeypatch, change):
    install(packet, monkeypatch)
    result = w.respond(canonical(packet).encode())
    directory = Path(packet["output_dir"])
    if change == "steps":
        result["steps"] -= 1
    elif change == "journal":
        result["journal"]["sha256"] = "0" * 64
    elif change in {"subset", "binding"}:
        journal = directory / "steps.jsonl"
        raw = journal.read_bytes()
        raw = (
            b"\n".join(raw.splitlines()[:-3]) + b"\n"
            if change == "subset"
            else raw.replace(packet["selection"][0]["spec"]["case_id"].encode(), b"changed")
        )
        journal.write_bytes(raw)
        result["journal"] = s.journal_info(journal)
    elif change == "adapter":
        (directory / "adapter/adapter_model.safetensors").write_bytes(b"changed")
    elif change == "authority":
        result["trading_enabled"] = True
    elif change == "reload":
        result["reload"]["probe_loss_after"] += 1
    else:
        result["resources"]["peak_reserved_bytes"] = result["resources"]["total_bytes"] + 1
    with pytest.raises(ValueError):
        s.validate_result(result, packet, directory)


@pytest.mark.parametrize("failure", [None, "timeout", "drift"])
def test_parent_one_dispatch_final_binding_and_no_retry(frozen, monkeypatch, failure):
    path, plan_pin, _ = frozen
    output = path.parent / "new-context-parent-run"
    calls = []
    original = s.registration

    def registration(*args):
        if calls and failure == "drift":
            raise ValueError("Final input changed")
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
        assert report["metric_count"] == 192 and report["adapter_quarantined"]
        assert not report["full_training_epoch"] and not report["evaluation_performed"]
        assert all(report[k] is False for k in s.FLAGS)
    monkeypatch.setattr(s, "registration", original)
    with pytest.raises(ValueError, match="exclusive"):
        s.run(path, plan_pin, output, enable_research_training=True)
    assert len(calls) == 1 and calls[0][1] == 1800000 and calls[0][0][-1] == s.WORKER


def test_opt_in_precedes_all_input_access(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        s.run(tmp_path / "absent", "bad", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_output_is_disjoint_from_each_protected_input(frozen):
    path, _, value = frozen
    for output in (
        Path(value["inputs"]["dataset"]["path"]) / "bad",
        Path(value["assets"]["checkpoint"]) / "bad",
        path.parent,
    ):
        with pytest.raises(ValueError):
            s.disjoint(output, value)


def test_worker_failure_retains_incomplete_steps_and_no_adapter(packet, monkeypatch):
    backend = install(packet, monkeypatch)
    step = backend.step

    def failed(record):
        if len(backend.records) == 6:
            raise RuntimeError("Fixture optimizer failure")
        return step(record)

    monkeypatch.setattr(backend, "step", failed)
    with pytest.raises(RuntimeError):
        w.respond(canonical(packet).encode())
    directory = Path(packet["output_dir"])
    failure = json.loads((directory / "failure.json").read_text())
    assert failure["completed_steps_unverified"] == 6
    assert failure["adapter_quarantined"]
    assert not (directory / "adapter").exists() and not (directory / "run.json").exists()
    with pytest.raises(ValueError, match="supervisor-owned"):
        w.respond(canonical(packet).encode())


def test_worker_deadline_fails_before_backend_with_retained_failure(packet, monkeypatch):
    install(packet, monkeypatch)
    calls = iter((0.0, 1801.0))
    monkeypatch.setattr(w.time, "monotonic", lambda: next(calls))
    monkeypatch.setattr(
        w, "create_backend", lambda *args: pytest.fail("Native load after deadline")
    )
    with pytest.raises(TimeoutError):
        w.respond(canonical(packet).encode())
    failure = json.loads((Path(packet["output_dir"]) / "failure.json").read_text())
    assert failure["completed_steps_unverified"] == 0 and failure["error_type"] == "TimeoutError"


def test_preflight_cannot_hide_an_extra_partition(frozen):
    path, _, value = frozen
    preflight = Path(value["inputs"]["preflight"]["path"])
    metadata = json.loads(preflight.read_text())
    metadata["by_partition"]["reserved"] = {}
    value["inputs"]["preflight"]["sha256"] = write(preflight, metadata)
    with pytest.raises(ValueError):
        s.registration(path, write(path, value))


def test_relative_cli_dataset_path_normalizes_before_native_asset_checks(frozen, monkeypatch):
    path, _, value = frozen
    monkeypatch.chdir(path.parent)
    args = []
    for name in ("dataset", "preflight", "asset_registration", "reservation"):
        item = value["inputs"][name]
        input_path = Path(item["path"])
        args.extend(
            (
                input_path.relative_to(path.parent) if name == "dataset" else input_path,
                item["sha256"],
            )
        )
    assert s.make_registration(*args)[0] == value
