"""Pure Qwen 6E outcome contract and CPU token preflight; never weights or orders."""

from __future__ import annotations

import argparse
import hashlib
import math
import time
from collections import Counter
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.training import advisory_training_plan as token_plan
from ai_trader.training.advisory_training_plan import (
    MAX_COMPLETION_TOKENS,
    MAX_PROMPT_TOKENS,
    MAX_SEQUENCE_TOKENS,
    completion_only_record,
    load_tokenizer,
)

TASK = "six_e_quote_opportunity_v1"
ROLES = ("train", "validation_development", "test_development")
TRAIN_END, VALIDATION_END = "2025-09-01", "2025-11-01"
EXTRA_COSTS = (1, 2, 4)
CLASSES = ("long_positive", "short_positive", "neither_positive")
SECOND = 1_000_000_000
MAX_CASES = 50_000
MAX_LINE = 16 * 1024
MAX_PROMPT_BYTES = 6144
MAX_DATA_BYTES = 256 * 1024**2
MAX_METADATA_BYTES = 2 * 1024**2
MAX_SECONDS = 600

# Versioned mirror of the pinned source schema. The builder checks exact parity
# with both source feature tuples before reading cases; no DBN/model imports here.
SNAPSHOT_FEATURES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
    "log_bid_depth5",
    "log_ask_depth5",
    "depth5_imbalance",
    "bid_top_share5",
    "ask_top_share5",
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_change_5s_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "log_quote_events_5s",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
)
EXECUTION_FEATURES = tuple(
    f"{side}_{metric}_5s"
    for side in ("bid", "ask")
    for metric in (
        "passive",
        "held_top_passive",
        "linked_decrease",
        "unlinked_decrease",
        "same_id_reload",
        "other_id_reload",
        "same_id_net_refresh",
    )
)
FEATURES = (*SNAPSHOT_FEATURES, *EXECUTION_FEATURES)
EXAMPLE_FIELDS = {
    "case_id",
    "source_session",
    "contract",
    "decision_ts_ns",
    "role",
    "source_row_sha256",
    "input_sha256",
    "target_sha256",
    "prompt",
    "completion",
}
PREFIX = (
    "Task: " + TASK + "\n"
    "Forecast a 6E Euro FX futures crossed-quote opportunity, not a trading order.\n"
    "Given only the current completed receive-time feature snapshot, predict which side "
    "has positive net ticks after a 100ms entry delay and a 15s hold. Entry and exit cross "
    "the quotes; additional total round-trip cost scenarios are 1, 2 and 4 ticks. "
    "Positive means strictly above zero; otherwise neither_positive.\n"
    "Return only JSON with keys extra_1_tick, extra_2_ticks, extra_4_ticks, each one of "
    "long_positive, short_positive, neither_positive. More cost cannot create an opportunity.\n"
    "Features ending _5s summarize observed past 5s data. log_ means log1p. "
    "Execution quantities are divided by current top-of-book total depth. CVD/OFI signs "
    "describe observed aggression/flow, not future prices. Reload and absorption are "
    "observable proxies, not confirmed icebergs or causal explanations. This snapshot "
    "has no longer-history encoding. Missing future outcomes are not negative labels. "
    "These are futures quote proxies, not EUR/USD CFD fills, broker costs or portfolio PnL.\n"
    "Features: "
)
SUFFIX = "\nForecast JSON:"


def role_for_session(session: str) -> str:
    if type(session) is not str or date.fromisoformat(session).isoformat() != session:
        raise ValueError("Canonical source session required")
    if not session.startswith("2025-"):
        raise ValueError("Reserved or nondevelopment date refused")
    return (
        "train"
        if session < TRAIN_END
        else ("validation_development" if session < VALIDATION_END else "test_development")
    )


def protocol() -> dict:
    return {
        "task": TASK,
        "features": list(FEATURES),
        "classes": list(CLASSES),
        "extra_round_trip_cost_ticks": list(EXTRA_COSTS),
        "entry_delay_ms": 100,
        "hold_seconds": 15,
        "inputs": "37 current causal feature values only; no paths, outcomes, eligibility, "
        "source date, exact contract, role or case ID in model input",
        "float_precision": "Eight significant decimal digits; finite numeric JSON only",
        "sampling": "All original causally eligible, sixty-second-spaced cases, no profit-sign "
        "selection, oversampling or session cherry-picking",
        "supervision": "Only resolved outcomes with no late exit or inactivity exposure; "
        "unavailable/uncertain outcomes retained separately, never labeled neither_positive",
        "exposure": "Every 2025 role is already exposed development, NOT an independent holdout",
        "split": {
            "train_before": TRAIN_END,
            "validation_before": VALIDATION_END,
            "unit": "Whole source_session",
            "roles": list(ROLES),
        },
        "limitations": "Snapshot forecast only; label-observability selection can bias results; "
        "not a causal reason, confirmed iceberg, portfolio policy or EURUSD broker backtest",
        "prompt_prefix": PREFIX,
        "prompt_suffix": SUFFIX,
        "bounds": {
            "cases": MAX_CASES,
            "line_bytes": MAX_LINE,
            "data_bytes": MAX_DATA_BYTES,
            "seconds": MAX_SECONDS,
        },
        "qwen_training": False,
        "promotion_enabled": False,
        "trading_enabled": False,
        "reserved_outcomes_opened": False,
    }


def identity(row: dict) -> dict:
    session, contract, now = row["source_session"], row["contract"], row["decision_ts_ns"]
    role_for_session(session)  # Refuse reserved dates before reading features or targets.
    expected = next(
        symbol
        for end, symbol in (
            ("2025-06-09", "6EM5"),
            ("2025-09-08", "6EU5"),
            ("2025-12-08", "6EZ5"),
            ("2026-01-01", "6EH6"),
        )
        if session < end
    )
    if contract != expected:
        raise ValueError("Dated 6E contract required")
    if type(now) is not int:
        raise ValueError("Integer decision nanoseconds required")
    stamp = datetime.fromtimestamp(now // SECOND, UTC)
    if stamp.date().isoformat() != session or not 12 <= stamp.hour < 16:
        raise ValueError("Decision outside source session window")
    return {"source_session": session, "contract": contract, "decision_ts_ns": now}


def features_only(row: dict) -> dict:
    identity(row)
    if row["partition"] != "development":
        raise ValueError("Only development feature snapshots allowed")
    f, e = row["features"], row["execution_features"]
    if set(f) != set(SNAPSHOT_FEATURES) or set(e) != set(EXECUTION_FEATURES):
        raise ValueError("Causal feature allowlist differs")
    values = {**f, **e}
    validate_features(values)
    return {key: float(format(values[key], ".8g")) for key in FEATURES}


def validate_features(values: dict) -> None:
    if (
        type(values) is not dict
        or set(values) != set(FEATURES)
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values())
    ):
        raise ValueError("Finite numeric causal features required")
    if any(values[k] < 0 for k in EXECUTION_FEATURES) or not (
        0 <= values["unknown_trade_fraction_5s"] <= 1
    ):
        raise ValueError("Invalid execution/unknown-fraction features")


def prompt(values: dict) -> str:
    validate_features(values)
    result = PREFIX + canonical(values) + SUFFIX
    if len(result.encode()) > MAX_PROMPT_BYTES:
        raise ValueError("Prompt byte ceiling exceeded; no truncation")
    return result


def completion(targets: list) -> str:
    if (
        type(targets) is not list
        or len(targets) != 2
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in targets)
        or sum(targets) >= 0
    ):
        raise ValueError("Finite mutually exclusive crossed-quote targets required")
    labels = {}
    for cost in EXTRA_COSTS:
        long, short = (v - (cost - 1) for v in targets)
        labels[f"extra_{cost}_{'tick' if cost == 1 else 'ticks'}"] = (
            "long_positive" if long > 0 else "short_positive" if short > 0 else "neither_positive"
        )
    return canonical(labels)


def parse_completion(text: str) -> dict:
    if type(text) is not str or not 1 <= len(text.encode()) <= 512:
        raise ValueError("Bounded structured forecast required")
    value = strict_json(text)
    keys = tuple(f"extra_{cost}_{'tick' if cost == 1 else 'ticks'}" for cost in EXTRA_COSTS)
    if (
        type(value) is not dict
        or set(value) != set(keys)
        or any(value[k] not in CLASSES for k in keys)
    ):
        raise ValueError("Forecast fields/classes differ")
    labels = [value[k] for k in keys]
    if any(b not in (a, "neither_positive") for a, b in zip(labels, labels[1:], strict=False)):
        raise ValueError("More cost cannot create or reverse an opportunity")
    return value


def validate_example(row: dict) -> None:
    if type(row) is not dict or set(row) != EXAMPLE_FIELDS:
        raise ValueError("Forecast example allowlist differs")
    provenance = identity(row)
    if row["role"] != role_for_session(row["source_session"]) or row["case_id"] != digest(
        provenance
    ):
        raise ValueError("Case/session/role identity differs")
    for key in ("source_row_sha256", "input_sha256", "target_sha256"):
        check_digest(row[key])
    text = row["prompt"]
    if type(text) is not str or not text.startswith(PREFIX) or not text.endswith(SUFFIX):
        raise ValueError("Fixed prompt contract differs")
    values = strict_json(text[len(PREFIX) : -len(SUFFIX)])
    if text != prompt(values) or digest(values) != row["input_sha256"]:
        raise ValueError("Noncanonical or changed causal input")
    target = parse_completion(row["completion"])
    if canonical(target) != row["completion"] or digest(target) != row["target_sha256"]:
        raise ValueError("Changed or noncanonical target")


def model_view(row: dict, *, for_training: bool) -> tuple[str, str]:
    # Gate before accessing either prompt or completion, including poison payloads.
    if type(for_training) is not bool or (for_training and row["role"] != "train"):
        raise ValueError("Only train-role examples may enter a fit")
    validate_example(row)
    return row["prompt"], row["completion"]


def write_new(path: Path, value: dict) -> None:
    with path.open("xb") as handle:
        handle.write((canonical(value) + "\n").encode())


def checked_file(path: Path, pin: str, limit: int) -> tuple[int, str]:
    check_digest(pin)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular pinned file required")
    size, checksum = 0, hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024**2), b""):
            size += len(block)
            if size > limit:
                raise ValueError("Pinned file byte ceiling exceeded")
            checksum.update(block)
    actual = checksum.hexdigest()
    if actual != pin:
        raise ValueError("Pinned file changed")
    return size, actual


def audit_tokens(
    directory: Path,
    receipt_pin: str,
    output: Path,
    *,
    encode,
    tokenizer_pin: str,
    eos: int,
    pad: int,
    tokenizer_version: str,
) -> dict:
    """Stream every supervised role, mask prompts, count tokens; never persist token arrays."""
    if directory.is_symlink() or not directory.is_dir() or output.exists() or output.is_symlink():
        raise ValueError("Regular dataset and exclusive token audit output required")
    if output.resolve().is_relative_to(directory.resolve()):
        raise ValueError("Token audit cannot modify the prepared dataset")
    check_digest(tokenizer_pin)
    started = time.monotonic()
    receipt_path = directory / "completion.json"
    checked_file(receipt_path, receipt_pin, MAX_METADATA_BYTES)
    receipt = strict_json(receipt_path.read_bytes())
    if (
        receipt["status"] != "prepared_6e_qwen_development_only"
        or receipt["protocol"] != protocol()
        or (directory / "failure.json").exists()
        or receipt["implementation_sha256"][Path(__file__).name]
        != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or receipt["implementation_sha256"][Path(token_plan.__file__).name]
        != hashlib.sha256(Path(token_plan.__file__).read_bytes()).hexdigest()
        or any(
            receipt[key] is not False
            for key in (
                "training_authorized",
                "independent_holdout",
                "qwen_trained",
                "trading_enabled",
                "promotion_enabled",
                "reserved_outcomes_opened",
                "automatic_retry",
            )
        )
    ):
        raise ValueError("Dataset completion, source or task changed")
    if (
        type(receipt["inspected_cases"]) is not int
        or not 1 <= receipt["inspected_cases"] <= MAX_CASES
        or (receipt["inspected_cases"] != receipt["source_coverage"]["cases"])
    ):
        raise ValueError("Complete bounded source case accounting required")
    expected_names = {f"{role}.jsonl" for role in ROLES} | {"unavailable.jsonl"}
    if set(receipt["files"]) != expected_names:
        raise ValueError("Dataset artifact allowlist differs")
    token_counts, total_bytes, total_cases, previous = {}, 0, 0, None
    for role in ROLES:
        path = directory / f"{role}.jsonl"
        item = receipt["files"][path.name]
        size, _ = checked_file(path, item["sha256"], MAX_DATA_BYTES)
        if (
            type(item["count"]) is not int
            or not 1 <= item["count"] <= MAX_CASES
            or size != item["bytes"]
        ):
            raise ValueError("Declared token audit file accounting differs")
        total_bytes += size
        if total_bytes > MAX_DATA_BYTES:
            raise ValueError("Dataset byte ceiling exceeded")
        counts = {
            "examples": 0,
            "max_prompt_tokens": 0,
            "max_completion_with_eos_tokens": 0,
            "max_active_tokens": 0,
        }
        labels = {str(cost): Counter() for cost in EXTRA_COSTS}
        stream_pin, stream_bytes = hashlib.sha256(), 0
        with path.open("rb") as handle:
            while raw := handle.readline(MAX_LINE + 1):
                stream_pin.update(raw)
                stream_bytes += len(raw)
                if len(raw) > MAX_LINE or not raw.endswith(b"\n"):
                    raise ValueError("Incomplete or oversized example line")
                row = strict_json(raw)
                if row["role"] != role or (
                    previous is not None and row["decision_ts_ns"] <= previous
                ):
                    raise ValueError("Mixed roles or duplicate/nonchronological token examples")
                previous = row["decision_ts_ns"]
                text, answer = model_view(row, for_training=(role == "train"))
                p, c = encode(text), encode(answer)
                record = completion_only_record(p, c, eos_token_id=eos, pad_token_id=pad)
                counts["examples"] += 1
                counts["max_prompt_tokens"] = max(counts["max_prompt_tokens"], len(p))
                counts["max_completion_with_eos_tokens"] = max(
                    counts["max_completion_with_eos_tokens"], len(c) + 1
                )
                counts["max_active_tokens"] = max(
                    counts["max_active_tokens"], sum(record["attention_mask"])
                )
                parsed = parse_completion(answer)
                for cost in EXTRA_COSTS:
                    key = f"extra_{cost}_{'tick' if cost == 1 else 'ticks'}"
                    labels[str(cost)][parsed[key]] += 1
                total_cases += 1
                if total_cases > MAX_CASES or time.monotonic() - started > MAX_SECONDS:
                    raise ValueError("Token preflight resource ceiling exceeded")
        if (
            counts["examples"] != item["count"]
            or counts["examples"] != receipt["by_role"][role]["supervised"]
        ):
            raise ValueError("Token preflight count differs")
        if stream_pin.hexdigest() != item["sha256"] or stream_bytes != item["bytes"]:
            raise ValueError("Tokenized bytes differ from pinned file")
        if {k: dict(v) for k, v in labels.items()} != receipt["by_role"][role][
            "classes_by_extra_cost"
        ]:
            raise ValueError("Token preflight label distribution differs")
        checked_file(path, item["sha256"], MAX_DATA_BYTES)
        token_counts[role] = counts
    unknown = receipt["files"]["unavailable.jsonl"]
    size, _ = checked_file(directory / "unavailable.jsonl", unknown["sha256"], MAX_DATA_BYTES)
    if (
        type(unknown["count"]) is not int
        or not 0 <= unknown["count"] <= MAX_CASES
        or (
            size != unknown["bytes"]
            or total_bytes + size > MAX_DATA_BYTES
            or total_cases + unknown["count"] != receipt["inspected_cases"]
        )
    ):
        raise ValueError("Unavailable accounting differs")
    checked_file(receipt_path, receipt_pin, MAX_METADATA_BYTES)
    if (
        hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        != receipt["implementation_sha256"][Path(__file__).name]
        or (
            hashlib.sha256(Path(token_plan.__file__).read_bytes()).hexdigest()
            != receipt["implementation_sha256"][Path(token_plan.__file__).name]
        )
        or (directory / "failure.json").exists()
    ):
        raise ValueError("Token preflight source or completion changed during audit")
    result = {
        "status": "passed_all_supervised_token_preflight_not_training_approval",
        "dataset_completion_sha256": receipt_pin,
        "task": TASK,
        "tokenizer_sha256": tokenizer_pin,
        "tokenizer_version": tokenizer_version,
        "eos_token_id": eos,
        "pad_token_id": pad,
        "by_role": token_counts,
        "supervised_examples": total_cases,
        "unavailable_examples_not_tokenized": unknown["count"],
        "limits": {
            "prompt": MAX_PROMPT_TOKENS,
            "completion_including_eos": MAX_COMPLETION_TOKENS,
            "sequence": MAX_SEQUENCE_TOKENS,
        },
        "prompt_loss_masked": True,
        "completion_and_eos_supervised": True,
        "truncation": False,
        "model_weights_loaded": False,
        "qwen_trained": False,
        "training_authorized": False,
        "independent_holdout": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "automatic_retry": False,
    }
    write_new(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--tokenizer-json", type=Path, required=True)
    parser.add_argument("--tokenizer-sha256", required=True)
    parser.add_argument("--eos-token-id", type=int, required=True)
    parser.add_argument("--pad-token-id", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    encode = load_tokenizer(args.tokenizer_json, args.tokenizer_sha256)
    result = audit_tokens(
        args.dataset,
        args.completion_sha256,
        args.output,
        encode=encode,
        tokenizer_pin=args.tokenizer_sha256,
        eos=args.eos_token_id,
        pad=args.pad_token_id,
        tokenizer_version=version("tokenizers"),
    )
    print(canonical({"status": result["status"], "by_role": result["by_role"]}))


if __name__ == "__main__":
    main()
