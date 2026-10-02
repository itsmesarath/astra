"""Prepare all pinned exposed 6E cases for a future Qwen forecast experiment; no fit."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

from ai_trader.training import advisory_training_plan as token_plan
from ai_trader.training import historical_6e_manifest as data
from ai_trader.training import six_e_forecast as task

common = data.common
PURPOSE = "prepare_6e_qwen_development_v1"


def protocol() -> dict:
    return {
        **task.protocol(),
        "permission": {"purpose": PURPOSE, "dataset_preparation": True, "model_training": False},
        "lineage": "Original named-baseline manifest used for verified sources and session roles "
        "only; source permissions and reports remain unchanged",
    }


def fingerprints() -> dict:
    return {
        **data.fingerprints(),
        **{
            Path(module.__file__).name: common.hash_file(Path(module.__file__), 1024**2)
            for module in (task, token_plan)
        },
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    value = data.review.pinned(path, pin)
    if value["protocol"] != protocol() or value["implementation_sha256"] != fingerprints():
        raise ValueError("Dataset registration task, permission or source changed")
    manifest = data.load(root, Path(value["manifest"]["path"]), value["manifest"]["sha256"])
    if value["coverage"] != manifest["coverage"]:
        raise ValueError("Dataset registered coverage differs")
    if (
        task.SNAPSHOT_FEATURES != data.census.study.data.FEATURES
        or (task.EXECUTION_FEATURES != data.census.study.flow.FEATURES)
        or task.ROLES != data.ROLES
    ):
        raise ValueError("Forecast/source feature or role schema differs")
    if any(
        task.role_for_session(e["utc_date"]) != e["role"]
        for e in manifest["ledger"]
        if e["artifacts"]
    ):
        raise ValueError("Forecast/source calendar roles differ")
    return value, manifest


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path) -> dict:
    manifest = data.load(root, manifest_path, manifest_pin)
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "coverage": manifest["coverage"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def target_status(row: dict) -> str:
    outcome = row["outcome"]
    if row["eligible"] is not True or outcome["status"] not in {
        "resolved",
        "no_entry_quote_timeout",
        "no_entry_spread_widened",
        "no_entry_window_end",
        "unresolved_exit_window_end",
    }:
        raise ValueError("Only original causally eligible cases with finished outcomes allowed")
    targets, action = data.census.baseline.data.observed_targets(outcome)
    if targets != row["net_targets_long_short_ticks"] or action != row["hindsight_action"]:
        raise ValueError("Target arithmetic or missingness differs")
    if outcome["status"] != "resolved":
        return "unavailable:" + outcome["status"]
    if type(row["hindsight_action"]) is not int:
        raise ValueError("Explicit integer hindsight target required")
    if any(type(outcome.get(k)) is not bool for k in ("late_exit", "inactivity_exposed")):
        raise ValueError("Explicit resolved outcome quality flags required")
    decision, entry, exit_ts = (
        row["decision_ts_ns"],
        outcome["entry_ts_ns"],
        outcome["exit_ts_ns"],
    )
    prices = [
        outcome[k] for k in ("entry_bid_nano", "entry_ask_nano", "exit_bid_nano", "exit_ask_nano")
    ]
    tick, clock = data.census.baseline.data.clock.TICK, data.census.baseline.data.clock
    if (
        any(type(v) is not int or v <= 0 or v % tick for v in prices)
        or any(type(v) is not int for v in (decision, entry, exit_ts))
        or not decision + 100_000_000 <= entry <= decision + 1_100_000_000
        or (prices[1] - prices[0] != tick or prices[3] <= prices[2])
        or exit_ts < entry + clock.HOLD_NS
        or outcome["late_exit"] != (exit_ts > entry + clock.HOLD_NS + clock.QUOTE_WAIT_NS)
    ):
        raise ValueError("Resolved target quote, timing or quality flags differ")
    if outcome["late_exit"]:
        return "excluded:late_exit"
    if outcome["inactivity_exposed"]:
        return "excluded:inactivity_exposed"
    return "supervised"


def example(row: dict, role: str) -> tuple[dict, str]:
    provenance = task.identity(row)
    if role != task.role_for_session(provenance["source_session"]):
        raise ValueError("Source session cannot cross dataset roles")
    values = task.features_only(row)
    status = target_status(row)
    record = {
        **provenance,
        "role": role,
        "case_id": task.digest(provenance),
        "source_row_sha256": common.digest(row),
        "input_sha256": task.digest(values),
    }
    if status != "supervised":
        return {
            **record,
            "outcome_status": row["outcome"]["status"],
            "target_status": status,
            "completion": None,
        }, status
    answer = task.completion(row["net_targets_long_short_ticks"])
    record.update(
        prompt=task.prompt(values),
        completion=answer,
        target_sha256=task.digest(task.parse_completion(answer)),
    )
    task.validate_example(record)
    return record, status


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen, manifest = registration(root, path, pin)
    root = root.resolve()
    if (
        output.exists()
        or output.is_symlink()
        or not output.resolve().is_relative_to((root / "data/processed").resolve())
        or not output.parent.is_dir()
    ):
        raise ValueError("New dataset directory required inside processed data")
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    common._write_new(
        output / "attempt.json",
        {
            "registration_sha256": pin,
            "started_utc": datetime.now(UTC).isoformat(),
            "automatic_retry": False,
        },
    )
    try:
        names = [*(f"{role}.jsonl" for role in task.ROLES), "unavailable.jsonl"]
        file_stats = {name: {"count": 0, "bytes": 0, "sha256": hashlib.sha256()} for name in names}
        counters = {role: Counter() for role in task.ROLES}
        labels = {role: {str(cost): Counter() for cost in task.EXTRA_COSTS} for role in task.ROLES}
        daily, total_bytes, total_cases, last = [], 0, 0, None
        with ExitStack() as stack:
            handles = {name: stack.enter_context((output / name).open("xb")) for name in names}
            for entry in manifest["ledger"]:
                if entry["role"] not in task.ROLES:
                    continue  # Never construct a raw/reserved artifact path.
                if time.monotonic() - started > task.MAX_SECONDS:
                    raise ValueError("Dataset wall-time ceiling exceeded")
                print(f"Preparing Qwen cases {entry['utc_date']}", flush=True)
                rows = data.read_rows(root, entry, "cases")
                if data.accounting(rows) != entry["case_accounting"]:
                    raise ValueError("Source case accounting differs")
                statuses = Counter()
                for row in rows:
                    if last is not None and row["decision_ts_ns"] <= last:
                        raise ValueError("Duplicate or nonchronological dataset case")
                    last = row["decision_ts_ns"]
                    record, status = example(row, entry["role"])
                    name = (
                        f"{entry['role']}.jsonl" if status == "supervised" else "unavailable.jsonl"
                    )
                    raw = common.canonical(record) + b"\n"
                    total_cases += 1
                    total_bytes += len(raw)
                    if (
                        len(raw) > task.MAX_LINE
                        or total_bytes > task.MAX_DATA_BYTES
                        or total_cases > task.MAX_CASES
                    ):
                        raise ValueError("Dataset case or byte ceiling exceeded")
                    handles[name].write(raw)
                    stats = file_stats[name]
                    stats["count"] += 1
                    stats["bytes"] += len(raw)
                    stats["sha256"].update(raw)
                    counters[entry["role"]][status] += 1
                    statuses[status] += 1
                    if status == "supervised":
                        parsed = task.parse_completion(record["completion"])
                        for cost in task.EXTRA_COSTS:
                            key = f"extra_{cost}_{'tick' if cost == 1 else 'ticks'}"
                            labels[entry["role"]][str(cost)][parsed[key]] += 1
                daily.append(
                    {
                        "source_session": entry["utc_date"],
                        "role": entry["role"],
                        "cases": len(rows),
                        "target_statuses": dict(statuses),
                        "source_case_sha256": entry["artifacts"]["cases"]["sha256"],
                    }
                )
        expected_sessions = [e["utc_date"] for e in manifest["ledger"] if e["role"] in task.ROLES]
        if [d["source_session"] for d in daily] != expected_sessions or total_cases != manifest[
            "coverage"
        ]["cases"]:
            raise ValueError("All source cases/sessions required; no successful subset")
        registration(root, path, pin)
        for entry in manifest["ledger"]:
            if entry["role"] not in task.ROLES:
                continue
            artifact = entry["artifacts"]["cases"]
            data.review.checked_hash(
                data.artifact_path(root, artifact["path"]),
                artifact["sha256"],
                data.census.MAX_DAY_BYTES,
            )
        files = {}
        for name, stats in file_stats.items():
            checksum = stats["sha256"].hexdigest()
            task.checked_file(output / name, checksum, task.MAX_DATA_BYTES)
            files[name] = {**stats, "sha256": checksum}
        by_role = {}
        for role in task.ROLES:
            counts = counters[role]
            supervised = counts["supervised"]
            if not supervised:
                raise ValueError("Every role requires supervised support")
            by_role[role] = {
                "sessions": sum(d["role"] == role for d in daily),
                "cases": counts.total(),
                "supervised": supervised,
                "unavailable_or_uncertain": counts.total() - supervised,
                "target_statuses": dict(counts),
                "classes_by_extra_cost": {k: dict(v) for k, v in labels[role].items()},
            }
        if time.monotonic() - started > task.MAX_SECONDS:
            raise ValueError("Dataset completion wall-time ceiling exceeded")
        result = {
            "status": "prepared_6e_qwen_development_only",
            "protocol": task.protocol(),
            "preparation_protocol": frozen["protocol"],
            "registration_sha256": pin,
            "manifest_sha256": frozen["manifest"]["sha256"],
            "implementation_sha256": frozen["implementation_sha256"],
            "source_coverage": frozen["coverage"],
            "inspected_sessions": len(daily),
            "inspected_cases": total_cases,
            "files": files,
            "by_role": by_role,
            "sessions": daily,
            "elapsed_seconds": time.monotonic() - started,
            "tokenization_verified": False,
            "independent_holdout": False,
            "qwen_trained": False,
            "training_authorized": False,
            "trading_enabled": False,
            "promotion_enabled": False,
            "reserved_outcomes_opened": False,
            "automatic_retry": False,
            "completed_utc": datetime.now(UTC).isoformat(),
        }
        if len(common.canonical(result)) > task.MAX_METADATA_BYTES:
            raise ValueError("Dataset receipt byte ceiling exceeded")
        common._write_new(output / "completion.json", result)
        return result
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {
                "error_type": type(exc).__name__,
                "automatic_retry": False,
                "incomplete_artifacts_not_training_data": True,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--registration-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.manifest is None or args.manifest_sha256 is None:
            parser.error("Pinned source manifest required")
        prepare(args.project_root, args.manifest, args.manifest_sha256, args.registration)
        print("Dataset preparation frozen; no training permission")
    else:
        if args.registration_sha256 is None or args.output is None:
            parser.error("Pinned registration and exclusive output required")
        result = run(args.project_root, args.registration, args.registration_sha256, args.output)
        print(task.canonical({"status": result["status"], "by_role": result["by_role"]}))


if __name__ == "__main__":
    main()
