"""Separate 196-update context-v2 class-coverage pilot; offline, never promotion."""

from __future__ import annotations

import argparse
import hashlib
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import _exchange
from ai_trader.research import six_e_fit_recall as diagnostic
from ai_trader.training import six_e_context_lora as natural
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _absolute
from ai_trader.training.lora_backend import MAX_TRAINABLE_PARAMETERS, adapter_manifest

KIND = "six_e_context_v2_balanced_196_update_lora"
WORKER = "ai_trader.training._six_e_context_balanced_worker"
PER_STATE, STEPS, TIMEOUT_MS = 28, 196, 1_800_000
MAX_REQUEST_BYTES, MAX_JOURNAL_BYTES = natural.MAX_REQUEST_BYTES, 256 * 1024
MAX_BYTES = diagnostic.MAX_BYTES
STATES, FLAGS = natural.STATES, dict(natural.FLAGS)
STATUS = "completed_196_update_context_v2_balanced_trial_not_validated"
tokens, task = natural.tokens, natural.task
ASSET_PATHS, ASSET_PINS = natural.ASSET_PATHS, natural.ASSET_PINS
PACKET_FIELDS = natural.PACKET_FIELDS
REG_FIELDS = (
    "kind",
    "protocol",
    "source_sha256",
    "diagnostic",
    "diagnostic_verification",
    "natural_registration",
    "inputs",
    "assets",
    "session_split",
    "fit_joint_counts",
    "fit_examples",
    "selection",
    "comparison",
    "protected_evidence",
    *FLAGS,
)
finite_nonnegative = natural.finite_nonnegative
binding, summarize = natural.binding, natural.summarize
write_artifact = diagnostic.write_artifact


def profile() -> dict:
    return {
        **natural.profile(),
        "purpose": KIND,
        "max_optimizer_steps": STEPS,
        "selection": "28 unique fit cases per each of seven joint states; same session spread "
        "and even within-session ranks; no duplication, reweighting or outcome search",
    }


def protocol() -> dict:
    return {
        "kind": KIND,
        "profile": profile(),
        "hypothesis": "Class-coverage sampling may reduce seen-fit idle collapse; "
        "not a promised fix",
        "change": "Sampling and consequent 196 updates versus 192; all optimizer, loss, "
        "causal prompt, target, initialization and decoding settings unchanged",
        "prerequisite": "Fully verified original 192-case seen-fit idle collapse; "
        "old evidence immutable",
        "packet": "Selected train/inner-fit examples and pinned assets only; no check examples, "
        "dataset paths, raw archives, old adapters or diagnostic predictions",
        "evaluation": "None during training. First-record reload probe proves persistence only; "
        "separate all-case seen-fit recall and natural full-development comparisons required",
        "prior_warning": "Uniform joint quotas alter class priors; more directional calls "
        "may be false signals",
        "bounds": {
            "updates": STEPS,
            "worker_seconds": TIMEOUT_MS // 1000,
            "request_bytes": MAX_REQUEST_BYTES,
            "artifact_bytes": MAX_BYTES,
        },
        "registration_authorizes_execution": False,
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "immutable_natural_pilot": natural.source_sha256(),
            "immutable_fit_diagnostic": diagnostic.source_sha256(),
            **{
                name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ("six_e_context_balanced.py", "_six_e_context_balanced_worker.py")
            },
        }
    )


def quotas(counts: dict) -> dict:
    _fields(counts, STATES)
    if (
        any(type(v) is not int or v < PER_STATE for v in counts.values())
        or sum(counts.values()) > task.snapshot.MAX_CASES
    ):
        raise ValueError("28 unique fit examples of every class required; no fallback")
    return dict.fromkeys(STATES, PER_STATE)


def gate(rows: list[dict], split: dict) -> None:
    natural.validate_split(split)
    if type(rows) is not list or not 1 <= len(rows) <= task.snapshot.MAX_CASES:
        raise ValueError("Bounded complete fit pool required")
    # Gate ALL memberships before reading ANY target, prompt or example digest.
    for row in rows:
        if (
            row["role"] != "train"
            or row["inner_partition"] != "fit"
            or row["source_session"] not in split["fit"]
        ):
            raise ValueError("Fit membership gate before prompt/target access")


def curriculum(rows: list[dict], split: dict) -> tuple[list[dict], dict]:
    gate(rows, split)
    pools = {state: defaultdict(list) for state in STATES}
    ids, previous = set(), None
    for index, row in enumerate(rows):
        task.model_view(row, for_training=True)
        if row["case_id"] in ids or (previous is not None and row["decision_ts_ns"] <= previous):
            raise ValueError("Unique chronological fit pool required")
        ids.add(row["case_id"])
        previous = row["decision_ts_ns"]
        pools[natural.legacy.balance.state_of(row)][row["source_session"]].append(index)
    counts = {state: sum(map(len, groups.values())) for state, groups in pools.items()}
    quotas(counts)
    selected = []
    for groups in pools.values():
        sessions = sorted(groups)
        allocation = dict.fromkeys(sessions, 0)
        if len(sessions) >= PER_STATE:
            for i in natural.legacy.balance.even_indices(len(sessions), PER_STATE):
                allocation[sessions[i]] = 1
        else:
            remaining = PER_STATE
            while remaining:
                for day in sessions:
                    if remaining and allocation[day] < len(groups[day]):
                        allocation[day] += 1
                        remaining -= 1
        for day, number in allocation.items():
            if number:
                selected.extend(
                    groups[day][i]
                    for i in natural.legacy.balance.even_indices(len(groups[day]), number)
                )
    selected.sort(key=lambda i: natural.order_key(rows[i]))
    if len(selected) != STEPS or len({rows[i]["case_id"] for i in selected}) != STEPS:
        raise ValueError("Exactly 196 unique selected fit cases required")
    return [
        {
            "example_index": i,
            "joint_state": natural.legacy.balance.state_of(rows[i]),
            **{
                k: rows[i][k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            },
            "example_sha256": digest(rows[i]),
        }
        for i in selected
    ], counts


def validate_packet(packet: dict, *, verify_assets=True):
    _fields(packet, PACKET_FIELDS)
    if (
        packet["kind"] != KIND
        or packet["profile"] != profile()
        or packet["source_sha256"] != source_sha256()
        or packet["enable_research_training"] is not True
    ):
        raise ValueError("Fixed balanced profile/source and explicit opt-in required")
    for key in (
        "source_sha256",
        "registration_sha256",
        "dataset_completion_sha256",
        "token_preflight_sha256",
    ):
        check_digest(packet[key])
    selection = packet["selection"]
    if type(selection) is not list or len(selection) != STEPS:
        raise ValueError("All 196 selected cases required")
    for item in selection:
        _fields(item, ("spec", "example"))
    gate([item["example"] for item in selection], packet["session_split"])
    if len(canonical(packet).encode()) > MAX_REQUEST_BYTES:
        raise ValueError("Bounded selected-fit packet required")
    expected = quotas(packet["fit_joint_counts"])
    seen, indices, counts, order = set(), set(), Counter(), []
    for item in selection:
        spec, row = item["spec"], item["example"]
        _fields(spec, natural.SPEC_FIELDS)
        task.model_view(row, for_training=True)
        if (
            natural.legacy.balance.state_of(row) != spec["joint_state"]
            or digest(row) != spec["example_sha256"]
            or any(
                spec[k] != row[k]
                for k in ("case_id", "source_session", "input_sha256", "target_sha256")
            )
            or row["case_id"] in seen
            or type(spec["example_index"]) is not int
            or not 0 <= spec["example_index"] < sum(packet["fit_joint_counts"].values())
            or spec["example_index"] in indices
            or any(
                type(spec[k]) is not int or spec[k] <= 0
                for k in ("prompt_tokens", "completion_with_eos_tokens", "active_tokens")
            )
            or spec["prompt_tokens"] > tokens.token_plan.MAX_PROMPT_TOKENS
            or spec["completion_with_eos_tokens"] > tokens.token_plan.MAX_COMPLETION_TOKENS
            or spec["active_tokens"] != spec["prompt_tokens"] + spec["completion_with_eos_tokens"]
            or spec["active_tokens"] > tokens.token_plan.MAX_SEQUENCE_TOKENS
        ):
            raise ValueError("Balanced selection/token identity differs")
        check_digest(spec["record_sha256"])
        check_digest(spec["example_sha256"])
        seen.add(row["case_id"])
        indices.add(spec["example_index"])
        counts[spec["joint_state"]] += 1
        order.append(natural.order_key(row))
    if dict(counts) != expected or order != sorted(order):
        raise ValueError("Exact uniform quotas and label-blind hash order required")
    return natural.validate_assets(packet, verify_assets=verify_assets)


def token_records(packet: dict, encode) -> list[dict]:
    gate([i["example"] for i in packet["selection"]], packet["session_split"])
    records = []
    for item in packet["selection"]:
        info, record = natural.encoded(item["example"], encode)
        if any(item["spec"][k] != v for k, v in info.items()):
            raise ValueError("Exact native tokenization/completion-only mask required")
        records.append(record)
    return records


def make_registration(path: Path, pin: str, directory: Path, report_pin: str):
    proof = diagnostic.verify_run(path, pin, directory, report_pin)
    if proof["diagnostic_conclusion"] != "collapse_on_seen_fit":
        raise ValueError("This hypothesis requires verified original seen-fit idle collapse")
    prior = tokens.metadata(path, pin)["completed_comparison"]
    full = tokens.metadata(_absolute(prior["registration"]), prior["registration_sha256"])
    reference = full["controls_registration"]
    cpu = tokens.metadata(_absolute(reference["path"]), reference["sha256"])
    reference = cpu["training_registration"]
    _fields(reference, ("path", "sha256"))
    value, rows = natural.registration(_absolute(reference["path"]), reference["sha256"])
    selected, counts = curriculum(rows, value["session_split"])
    if counts != value["fit_joint_counts"] or len(rows) != value["fit_examples"]:
        raise ValueError("Complete original fit distribution required")
    encode = tokens.token_plan.load_tokenizer(
        Path(value["assets"]["tokenizer_json"]), value["assets"]["tokenizer_sha256"]
    )
    selection = [
        {**spec, **natural.encoded(rows[spec["example_index"]], encode)[0]} for spec in selected
    ]
    registered = {
        "kind": KIND,
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "diagnostic": {
            "path": str(path.resolve()),
            "sha256": pin,
            "directory": str(directory.resolve()),
            "report_sha256": report_pin,
        },
        "diagnostic_verification": proof,
        "natural_registration": reference,
        "protected_evidence": [
            prior["registration"],
            prior["directory"],
            full["training_trial"]["directory"],
            full["controls_trial"]["directory"],
            full["controls_registration"]["path"],
        ],
        **{
            key: value[key]
            for key in (
                "inputs",
                "assets",
                "session_split",
                "fit_joint_counts",
                "fit_examples",
                "comparison",
            )
        },
        "selection": selection,
        **FLAGS,
    }
    return registered, rows


def disjoint(output: Path, value: dict, extra=()) -> None:
    natural.disjoint(output, value)
    protected = [value["diagnostic"][k] for k in ("path", "directory")]
    protected += [value["natural_registration"]["path"], *value["protected_evidence"], *extra]
    for name in protected:
        path = _absolute(str(name))
        if output.resolve().is_relative_to(path) or path.is_relative_to(output.resolve()):
            raise ValueError("Output overlaps immutable prior evidence")


def worker_packet(value: dict, rows: list[dict], pin: str, output: Path) -> dict:
    packet = {
        "kind": KIND,
        "profile": profile(),
        "source_sha256": source_sha256(),
        "registration_sha256": pin,
        "dataset_completion_sha256": value["inputs"]["dataset"]["sha256"],
        "token_preflight_sha256": value["inputs"]["preflight"]["sha256"],
        "enable_research_training": True,
        **value["assets"],
        "output_dir": str(output.resolve()),
        "session_split": value["session_split"],
        "fit_joint_counts": value["fit_joint_counts"],
        "selection": [
            {"spec": spec, "example": rows[spec["example_index"]]} for spec in value["selection"]
        ],
    }
    validate_packet(packet)
    return packet


def freeze(path: Path, pin: str, directory: Path, report_pin: str, output: Path) -> dict:
    value, rows = make_registration(path, pin, directory, report_pin)
    disjoint(output, value)
    worker_packet(value, rows, "0" * 64, output.with_name(output.stem + "_preview_never_created"))
    write_artifact(output, value)
    return value


def registration(path: Path, pin: str):
    value = tokens.metadata(path, pin)
    _fields(value, REG_FIELDS)
    if (
        value["kind"] != KIND
        or value["protocol"] != protocol()
        or value["source_sha256"] != source_sha256()
    ):
        raise ValueError("Frozen balanced source/protocol required")
    item = value["diagnostic"]
    _fields(item, ("path", "sha256", "directory", "report_sha256"))
    rebuilt, rows = make_registration(
        _absolute(item["path"]), item["sha256"], _absolute(item["directory"]), item["report_sha256"]
    )
    if canonical(value) != canonical(rebuilt):
        raise ValueError("Balanced selection, evidence, inputs or authority drifted")
    return value, rows


def journal_info(path: Path) -> dict:
    return diagnostic.controls.file_info(path, MAX_JOURNAL_BYTES)


def validate_result(result: dict, packet: dict, directory: Path) -> list[dict]:
    _fields(
        result,
        (
            "kind",
            "request_sha256",
            "steps",
            "summary",
            "journal",
            "runtime",
            "resources",
            "trainable_parameters",
            "frozen_parameter_guards_passed",
            "reload",
            *FLAGS,
        ),
    )
    if (
        result["kind"] != KIND
        or result["request_sha256"] != digest(packet)
        or type(result["steps"]) is not int
        or result["steps"] != STEPS
        or result["frozen_parameter_guards_passed"] is not True
        or any(result[k] is not v for k, v in FLAGS.items())
        or type(result["trainable_parameters"]) is not int
        or not 1 <= result["trainable_parameters"] <= MAX_TRAINABLE_PARAMETERS
        or directory.is_symlink()
        or (directory / "failure.json").exists()
    ):
        raise ValueError("Complete quarantined training result required")
    _, runtime = validate_packet(packet)
    if canonical(result["runtime"]) != canonical(runtime):
        raise ValueError("Native runtime differs")
    native_pin = diagnostic.controls.file_info(directory / "native_result.json", MAX_BYTES)[
        "sha256"
    ]
    if canonical(tokens.metadata(directory / "native_result.json", native_pin)) != canonical(
        result
    ):
        raise ValueError("Durable native receipt required before transport/reporting")
    _fields(result["journal"], ("bytes", "sha256"))
    if journal_info(directory / "steps.jsonl") != result["journal"]:
        raise ValueError("Complete durable journal pin required")
    events = diagnostic.controls.lines(directory / "steps.jsonl", result["journal"])
    if (
        len(events) != 2 * STEPS + 4
        or events[:2]
        != [
            {"event": "native_initialization_started"},
            {"event": "native_initialization_completed"},
        ]
        or events[-2:] != [{"event": "save_reload_started"}, {"event": "save_reload_completed"}]
    ):
        raise ValueError("Every update and initialization/save stage required")
    metrics = []
    for step, item in enumerate(packet["selection"], 1):
        intent, completed = events[2 * step : 2 * step + 2]
        expected = binding(step, item)
        _fields(completed, ("event", *expected, "loss", "gradient_norm"))
        metric = {k: completed[k] for k in ("loss", "gradient_norm")}
        finite_nonnegative(metric.values())
        if canonical(intent) != canonical({"event": "step_intent", **expected}) or canonical(
            completed
        ) != canonical({"event": "step_completed", **expected, **metric}):
            raise ValueError("Ordered update identity or metrics differ")
        metrics.append(metric)
    if canonical(result["summary"]) != canonical(summarize(metrics)):
        raise ValueError("All-update loss/gradient summary differs")
    reload = result["reload"]
    _fields(
        reload,
        (
            "adapter_manifest",
            "adapter_updated",
            "reload_state_equal",
            "probe_loss_before",
            "probe_loss_after",
            "probe_loss_absolute_tolerance",
            "base_checkpoint_unchanged",
        ),
    )
    finite_nonnegative([reload["probe_loss_before"], reload["probe_loss_after"]])
    if (
        any(
            reload[k] is not True
            for k in ("adapter_updated", "reload_state_equal", "base_checkpoint_unchanged")
        )
        or reload["probe_loss_absolute_tolerance"] != 1e-5
        or not math.isclose(
            reload["probe_loss_before"], reload["probe_loss_after"], rel_tol=0, abs_tol=1e-5
        )
        or canonical(adapter_manifest(directory / "adapter"))
        != canonical(reload["adapter_manifest"])
    ):
        raise ValueError("Saved adapter/fresh reload must match")
    diagnostic.previous.validate_resources(result["resources"])
    return metrics


def report_fields(packet: dict, metrics: list[dict]) -> dict:
    return {
        "selected_training_examples": STEPS,
        "selected_training_sessions": len(
            {i["spec"]["source_session"] for i in packet["selection"]}
        ),
        "selected_joint_counts": dict(
            Counter(i["spec"]["joint_state"] for i in packet["selection"])
        ),
        "metric_count": len(metrics),
        "full_training_epoch": False,
        "adapter_quarantined": True,
        "qwen_training_performed": True,
        "evaluation_performed": False,
        **FLAGS,
    }


def run(path: Path, pin: str, output: Path, *, enable_research_training=False) -> dict:
    if enable_research_training is not True:
        raise ValueError("Explicit one-pilot research-training opt-in required")
    value, rows = registration(path, pin)
    disjoint(output, value, [path])
    packet = worker_packet(value, rows, pin, output)
    output.mkdir(exist_ok=False)
    started, stage = time.monotonic(), "native_training"
    try:
        write_artifact(output / "request.json", packet)
        result = strict_json(
            _exchange([packet["python_executable"], "-I", "-m", WORKER], packet, TIMEOUT_MS)
        )
        metrics = validate_result(result, packet, output)
        stage = "post_training_pins"
        if canonical(registration(path, pin)) != canonical((value, rows)):
            raise ValueError("Frozen training inputs/evidence drifted")
        report = {
            "status": STATUS,
            "registration_sha256": pin,
            "result": result,
            "elapsed_seconds": time.monotonic() - started,
            **report_fields(packet, metrics),
        }
        write_artifact(output / "run.json", report)
        return report
    except BaseException as exc:
        if not (output / "run.json").exists():
            write_artifact(
                output / "run.json",
                {
                    "status": "failed_or_interrupted_no_partial_success",
                    "stage": stage,
                    "error_type": type(exc).__name__,
                    "adapter_quarantined": True,
                    **FLAGS,
                },
            )
        raise


def verify_run(path: Path, pin: str, directory: Path, report_pin: str) -> dict:
    value, rows = registration(path, pin)
    report = tokens.metadata(directory / "run.json", report_pin)
    _fields(
        report,
        (
            "status",
            "registration_sha256",
            "result",
            "elapsed_seconds",
            *report_fields({"selection": []}, []),
        ),
    )
    if report["status"] != STATUS or report["registration_sha256"] != pin:
        raise ValueError("Complete balanced training report required")
    finite_nonnegative([report["elapsed_seconds"]])
    names = ("run.json", "request.json", "steps.jsonl", "native_result.json")
    before = {name: diagnostic.controls.file_info(directory / name, MAX_BYTES) for name in names}
    packet = worker_packet(value, rows, pin, directory)
    if canonical(
        tokens.metadata(directory / "request.json", before["request.json"]["sha256"])
    ) != canonical(packet):
        raise ValueError("Persisted selected-example request differs")
    metrics = validate_result(report["result"], packet, directory)
    for k, expected in report_fields(packet, metrics).items():
        if canonical(report[k]) != canonical(expected):
            raise ValueError("Full training report accounting/authority differs")
    after = {name: diagnostic.controls.file_info(directory / name, MAX_BYTES) for name in names}
    if before != after or after["run.json"]["sha256"] != report_pin:
        raise ValueError("Training evidence drifted during verification")
    return {
        "status": "verified_balanced_training_not_validation",
        "files": after,
        "adapter_manifest": report["result"]["reload"]["adapter_manifest"],
        "updates": STEPS,
        "journal_events": 2 * STEPS + 4,
        **report_fields(packet, metrics),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "verify"))
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--diagnostic-directory", type=Path)
    parser.add_argument("--report-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--enable-research-training", action="store_true")
    args = parser.parse_args()
    if args.action == "freeze":
        if args.diagnostic_directory is None or args.report_sha256 is None:
            parser.error("Pinned completed diagnostic directory/report required")
        result = freeze(
            args.registration,
            args.registration_sha256,
            args.diagnostic_directory,
            args.report_sha256,
            args.output,
        )
    elif args.action == "verify":
        if args.report_sha256 is None:
            parser.error("Pinned completed training report required")
        result = verify_run(
            args.registration, args.registration_sha256, args.output, args.report_sha256
        )
    else:
        result = run(
            args.registration,
            args.registration_sha256,
            args.output,
            enable_research_training=args.enable_research_training,
        )
    print(canonical({"kind": KIND, "status": result.get("status", "registered_not_run")}))


if __name__ == "__main__":
    main()
