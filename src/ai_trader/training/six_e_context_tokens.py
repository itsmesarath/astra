"""Tokenizer-only preflight for pinned compact 6E context; no decoder or model weights."""

from __future__ import annotations

import argparse
import hashlib
import time
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.training import advisory_training_plan as token_plan
from ai_trader.training import six_e_context_forecast as task
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import _write

snapshot = task.snapshot
MAX_OUTPUT_BYTES = snapshot.MAX_DATA_BYTES
FLAGS = {
    "training_authorized": False,
    "qwen_trained": False,
    "independent_holdout": False,
    "reserved_outcomes_opened": False,
    "trading_enabled": False,
    "promotion_enabled": False,
    "automatic_retry": False,
}


def source_sha256() -> str:
    """Pin local token-pipeline code without importing the historical decoder."""
    folder = Path(__file__).parent
    paths = (
        Path(__file__),
        folder / "six_e_context_forecast.py",
        folder / "prepare_6e_context_data.py",
        folder / "causal_6e_context.py",
        folder / "six_e_forecast.py",
        folder / "advisory_training_plan.py",
        folder / "advisory_curriculum.py",
        folder / "advisory_training_run.py",
        folder.parent / "models/local_checkpoint.py",
    )
    return digest({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def deadline_guard(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise TimeoutError("Bounded context token preflight expired")


def metadata(path: Path, pin: str) -> dict:
    snapshot.checked_file(path, pin, snapshot.MAX_METADATA_BYTES)
    with path.open("rb") as stream:
        raw = stream.read(snapshot.MAX_METADATA_BYTES + 1)
    if len(raw) > snapshot.MAX_METADATA_BYTES or hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Pinned bounded context receipt changed")
    value = strict_json(raw)
    if type(value) is not dict:
        raise ValueError("Pinned context receipt must be an object")
    return value


def verified_receipt(directory: Path, pin: str) -> dict:
    value = metadata(directory / "completion.json", pin)
    _fields(
        value,
        (
            "status",
            "protocol",
            "source_sha256",
            "token_pipeline_sha256",
            "registration_sha256",
            "schema_sha256",
            "coverage",
            "session_split",
            "source_sessions",
            "sessions",
            "files",
            "source_bytes_read",
            "elapsed_seconds",
            "tokenization_verified",
            *FLAGS,
        ),
    )
    if (
        directory.is_symlink()
        or (directory / "failure.json").exists()
        or value["status"] != "prepared_train_only_6e_context_v2_not_training_approval"
        or value["protocol"]["kind"] != "prepare_6e_train_only_context_v2"
        or value["protocol"]["task"] != task.protocol()
        or value["protocol"]["permission"]
        != {
            "purpose": "prepare_6e_train_only_context_v2",
            "dataset_preparation": True,
            "model_training": False,
        }
        or any(value["protocol"][k] is not v for k, v in FLAGS.items())
        or value["token_pipeline_sha256"] != source_sha256()
        or value["schema_sha256"] != task.schema_sha256()
        or any(value[k] is not v for k, v in FLAGS.items())
        or set(value["files"]) != {"fit.jsonl", "check.jsonl", "unavailable.jsonl"}
        or sum(v["count"] for v in value["files"].values()) != value["coverage"]["cases"]
        or value["files"]["fit.jsonl"]["count"] + value["files"]["check.jsonl"]["count"]
        != value["coverage"]["supervised"]
    ):
        raise ValueError("Complete frozen train-only context receipt required")
    snapshot.check_digest(value["source_sha256"])
    snapshot.check_digest(value["registration_sha256"])
    _fields(
        value["coverage"],
        ("sessions", "dense_rows", "cases", "supervised", "supervised_by_partition"),
    )
    _fields(value["coverage"]["supervised_by_partition"], task.PARTITIONS)
    for key in ("sessions", "dense_rows", "cases", "supervised"):
        if type(value["coverage"][key]) is not int or value["coverage"][key] <= 0:
            raise ValueError("Positive integer complete coverage required")
    if value["coverage"]["cases"] > snapshot.MAX_CASES:
        raise ValueError("Context case budget exceeded")
    for info in value["files"].values():
        _fields(info, ("count", "bytes", "sha256"))
        snapshot.check_digest(info["sha256"])
        if (
            type(info["count"]) is not int
            or not 0 <= info["count"] <= snapshot.MAX_CASES
            or type(info["bytes"]) is not int
            or not 0 <= info["bytes"] <= MAX_OUTPUT_BYTES
        ):
            raise ValueError("Bounded integer context file accounting required")
    if sum(info["bytes"] for info in value["files"].values()) > MAX_OUTPUT_BYTES:
        raise ValueError("Combined context output byte budget exceeded")
    split = value["session_split"]
    _fields(split, task.PARTITIONS)
    sessions = split["fit"] + split["check"]
    if (
        not split["fit"]
        or not split["check"]
        or sessions != sorted(set(sessions))
        or any(snapshot.role_for_session(s) != "train" for s in sessions)
        or [s["source_session"] for s in value["source_sessions"]] != sessions
        or [s["source_session"] for s in value["sessions"]] != sessions
        or len(sessions) != value["coverage"]["sessions"]
        or sum(s["dense_rows"] for s in value["sessions"]) != value["coverage"]["dense_rows"]
        or sum(s["cases"] for s in value["sessions"]) != value["coverage"]["cases"]
        or value["tokenization_verified"] is not False
    ):
        raise ValueError("Complete isolated train-only session accounting required")
    for source, daily in zip(value["source_sessions"], value["sessions"], strict=True):
        day = source["source_session"]
        partition = "fit" if day in split["fit"] else "check"
        if (
            source["inner_partition"] != partition
            or daily["inner_partition"] != partition
            or daily["dense_rows"] != source["rows"]["count"]
            or daily["cases"] != source["cases"]["count"]
            or sum(daily["statuses"].values()) != daily["cases"]
        ):
            raise ValueError("Source and complete daily inner partition accounting differ")
        for kind in ("rows", "cases"):
            snapshot.check_digest(source[kind]["sha256"])
    for partition in task.PARTITIONS:
        expected = sum(
            s["statuses"].get("supervised", 0)
            for s in value["sessions"]
            if s["inner_partition"] == partition
        )
        if (
            expected != value["coverage"]["supervised_by_partition"][partition]
            or expected != value["files"][partition + ".jsonl"]["count"]
        ):
            raise ValueError("Original partition supervision counts differ")
    return value


def read_examples(directory: Path, partition: str, receipt: dict):
    if partition not in task.PARTITIONS:
        raise ValueError("Only explicit inner fit/check files permitted")
    info, count, size, checksum, previous = (
        receipt["files"][partition + ".jsonl"],
        0,
        0,
        hashlib.sha256(),
        None,
    )
    path = directory / (partition + ".jsonl")
    sources = {s["source_session"]: s for s in receipt["source_sessions"]}
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular explicit context example file required")
    with path.open("rb") as stream:
        while raw := stream.readline(task.MAX_LINE + 1):
            size += len(raw)
            checksum.update(raw)
            if (
                len(raw) > task.MAX_LINE
                or not raw.endswith(b"\n")
                or size > MAX_OUTPUT_BYTES
                or count >= info["count"]
            ):
                raise ValueError("Incomplete or oversized context examples")
            row = strict_json(raw)
            if (
                row["role"] != "train"
                or row["inner_partition"] != partition
                or row["source_session"] not in receipt["session_split"][partition]
            ):
                raise ValueError("Context role/session gate failed before prompt or target")
            source = sources[row["source_session"]]
            if (
                row["contract"] != source["contract"]
                or row["dense_rows_sha256"] != source["rows"]["sha256"]
            ):
                raise ValueError("Context example source contract or dense-file binding differs")
            text, answer = task.model_view(row, for_training=(partition == "fit"))
            if previous is not None and row["decision_ts_ns"] <= previous:
                raise ValueError("Unique chronological context examples required")
            previous = row["decision_ts_ns"]
            count += 1
            yield row, text, answer
    if count != info["count"] or size != info["bytes"] or checksum.hexdigest() != info["sha256"]:
        raise ValueError("Context example bytes, hash or count differ")


def audit_tokens(
    directory: Path,
    receipt_pin: str,
    output: Path,
    *,
    encode,
    tokenizer_pin: str,
    tokenizer_version: str,
    eos: int,
    pad: int,
) -> dict:
    snapshot.check_digest(tokenizer_pin)
    if (
        output.exists()
        or output.is_symlink()
        or output.resolve().is_relative_to(directory.resolve())
    ):
        raise ValueError("Exclusive token-preflight output outside dataset required")
    receipt, started = verified_receipt(directory, receipt_pin), time.monotonic()
    counts = {}
    for partition in task.PARTITIONS:
        stats = {
            "examples": 0,
            "max_prompt_tokens": 0,
            "max_completion_with_eos_tokens": 0,
            "max_active_tokens": 0,
        }
        for _, text, answer in read_examples(directory, partition, receipt):
            deadline_guard(started + snapshot.MAX_SECONDS)
            prompt_ids, answer_ids = encode(text), encode(answer)
            record = token_plan.completion_only_record(
                prompt_ids, answer_ids, eos_token_id=eos, pad_token_id=pad
            )
            stats["examples"] += 1
            stats["max_prompt_tokens"] = max(stats["max_prompt_tokens"], len(prompt_ids))
            stats["max_completion_with_eos_tokens"] = max(
                stats["max_completion_with_eos_tokens"], len(answer_ids) + 1
            )
            stats["max_active_tokens"] = max(
                stats["max_active_tokens"], sum(record["attention_mask"])
            )
        counts[partition] = stats
    for name, info in receipt["files"].items():
        size, _ = snapshot.checked_file(directory / name, info["sha256"], MAX_OUTPUT_BYTES)
        if size != info["bytes"]:
            raise ValueError("Token preflight dataset bytes changed")
    if verified_receipt(directory, receipt_pin) != receipt:
        raise ValueError("Context dataset changed during token preflight")
    deadline_guard(started + snapshot.MAX_SECONDS)
    result = {
        "status": "passed_context_v2_token_preflight_not_training_approval",
        "task": task.TASK,
        "dataset_completion_sha256": receipt_pin,
        "dataset_source_sha256": receipt["source_sha256"],
        "token_pipeline_sha256": source_sha256(),
        "schema_sha256": task.schema_sha256(),
        "tokenizer_sha256": tokenizer_pin,
        "tokenizer_version": tokenizer_version,
        "eos_token_id": eos,
        "pad_token_id": pad,
        "by_partition": counts,
        "unavailable_examples_not_tokenized": receipt["files"]["unavailable.jsonl"]["count"],
        "limits": {
            "prompt": token_plan.MAX_PROMPT_TOKENS,
            "completion_with_eos": token_plan.MAX_COMPLETION_TOKENS,
            "sequence": token_plan.MAX_SEQUENCE_TOKENS,
        },
        "prompt_loss_masked": True,
        "completion_and_eos_supervised": True,
        "truncation": False,
        "model_weights_loaded": False,
        **FLAGS,
    }
    _write(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--tokenizer-json", type=Path, required=True)
    parser.add_argument("--tokenizer-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_tokens(
        args.dataset,
        args.completion_sha256,
        args.output,
        encode=token_plan.load_tokenizer(args.tokenizer_json, args.tokenizer_sha256),
        tokenizer_pin=args.tokenizer_sha256,
        tokenizer_version=version("tokenizers"),
        eos=151643,
        pad=151643,
    )
    print(canonical({"status": result["status"], "by_partition": result["by_partition"]}))


if __name__ == "__main__":
    main()
