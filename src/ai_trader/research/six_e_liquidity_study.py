"""Whole accepted-session liquidity research with a quarantined fixed CPU candidate."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_bracket_study as exits
from ai_trader.training import six_e_liquidity as rules

data, resource = rules.data, rules.data.resource
census, common = data.census, data.common
AUTH = {
    "independent_holdout": False,
    "promotion_allowed": False,
    "trading_enabled": False,
    "reserved_outcomes_opened": False,
    "qwen_training": False,
}
MAX_SECONDS = 3 * 3600
MAX_EVAL_SECONDS = 3600
MAX_TOTAL_BYTES = 16 * 1024**3
CHUNK_ROWS = 100
MIN_JOINT_TRAIN = 1000
MIN_UNKNOWN_TRAIN = 100


def protocol() -> dict:
    return {
        "version": "six_e_whole_liquidity_development_v1",
        "scope": "ALL and ONLY accepted source sessions from the original pinned "
        "development manifest; retain all excluded/reserved metadata, never their prices",
        "split": data.protocol()["split"],
        "exposure": "All later roles already exposed development; no independent holdout",
        "targets": exits.target.protocol(),
        "causal_rules_and_cpu": rules.protocol(),
        "replay": "Unchanged disk-backed original strict MBO/receive-clock/feature/target "
        "engine; whole-member EOF hash; original full rows AND sixty-second cases parity",
        "quote_batches": "Retain every native quote; resolve unchanged bracket engine in "
        "100-decision slices through last decision+18s, preserving same-time order; "
        "not downsampling or successful-subset processing",
        "phase_gate": "Complete source/quote/target verification BEFORE any fit or cost "
        "evaluation; then one fixed CPU fit on causal 60s TRAIN selections only",
        "minimum_joint_resolved_train": MIN_JOINT_TRAIN,
        "minimum_unknown_train": MIN_UNKNOWN_TRAIN,
        "policy": exits.protocol()["policy"],
        "costs": exits.protocol()["costs"],
        "evaluation": "All original decisions including missing entries/exits; both exits "
        "and matched time-entry diagnostic; CPU heads target bracket exits only",
        "support": "Report signals/session coverage per policy, including zero/weak "
        "support; no automatic threshold change, expansion, winner selection or retries",
        "limits": {
            "collection_seconds": MAX_SECONDS,
            "evaluation_seconds": MAX_EVAL_SECONDS,
            "day_seconds": census.MAX_DAY_SECONDS,
            "quote_count": resource.MAX_QUOTES,
            "day_target_bytes": census.MAX_DAY_BYTES,
            "total_bytes": MAX_TOTAL_BYTES,
            "chunk_rows": CHUNK_ROWS,
        },
        "cpu_training_allowed": True,
        **AUTH,
    }


def fingerprints() -> dict:
    return {
        **data.fingerprints(),
        **exits.fingerprints(),
        **{Path(m.__file__).name: common.hash_file(Path(m.__file__), 1024**2) for m in (rules,)},
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def sources(root: Path, manifest: dict) -> list[dict]:
    inventory = census.registration(
        root, root / data.diagnostic.REGISTRATION, data.diagnostic.REGISTRATION_PIN
    )["inventory"]["ledger"]
    members = {m["utc_date"]: m for m in inventory}
    result = []
    for entry in manifest["ledger"]:
        if not entry["artifacts"]:
            continue
        day = entry["utc_date"]
        role = data.role_for_day(day)  # Guard BEFORE constructing any archive path.
        member = members[day]
        if (
            entry["role"] != role
            or entry["contract"] != census.dated_contract(day)
            or member["partition"] != "development"
            or member["condition"] != "available"
            or member["planned_action"] != "decision_window_replay"
            or member["sha256"] != entry["source_sha256"]
            or member["contract"] != entry["contract"]
        ):
            raise ValueError(
                "Liquidity cohort requires every accepted undegraded development member"
            )
        result.append({"entry": entry, "member": member})
    if not result or [s["entry"]["utc_date"] for s in result] != sorted(
        {s["entry"]["utc_date"] for s in result}
    ):
        raise ValueError("Liquidity cohort must be complete, unique and chronological")
    return result


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path, enabled: bool) -> dict:
    if enabled is not True:
        raise ValueError("Explicit named CPU-development training permission required")
    if path.is_symlink() or not path.resolve().is_relative_to((root / "logs").resolve()):
        raise ValueError("Liquidity registration belongs inside project logs")
    manifest = data.load(root, manifest_path, manifest_pin)
    value = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "sources": sources(root, manifest),
        "coverage": manifest["coverage"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, value)
    return value


def registration(root: Path, path: Path, pin: str) -> dict:
    value = data.review.pinned(path, pin)
    if value["protocol"] != protocol() or value["implementation_sha256"] != fingerprints():
        raise ValueError("Liquidity frozen protocol or source changed")
    manifest = data.load(root, Path(value["manifest"]["path"]), value["manifest"]["sha256"])
    if value["sources"] != sources(root, manifest) or value["coverage"] != manifest["coverage"]:
        raise ValueError("Liquidity complete cohort or original coverage changed")
    return value


def _write_bytes(path: Path, raw: bytes, bound: int) -> str:
    if len(raw) > bound:
        raise ValueError("Liquidity artifact exceeds bound")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return common.hash_file(path, bound)


def _labels(path: Path, pin: str, count: int) -> list[dict]:
    return exits._read_targets(path, pin, count)


def _view(directory: Path, metadata: dict):
    count = metadata["count"]
    if type(count) is not int or not 0 < count <= resource.MAX_QUOTES:
        raise ValueError("Invalid liquidity native quote count")
    for name in resource.COLUMNS:
        pin = metadata["columns"][name]
        size = data.review.checked_hash(
            directory / f"{name}.i64", pin["sha256"], resource.MAX_QUOTES * 8
        )
        if size != pin["bytes"] or size != count * 8:
            raise ValueError("Liquidity native quote column size differs")
    return resource.QuoteView(directory, count)


def targets(rows: list[dict], view: resource.QuoteView) -> list[dict]:
    """Identical bounded per-decision paths without lowering whole-day quote limits."""
    if not rows:
        raise ValueError("Liquidity targets require a complete source session")
    session = rows[0]["source_session"]
    start, end = exits.target.window(session)
    # Check the ENTIRE native sequence in bounded pages, including cross-page order.
    last = None
    for first in range(0, len(view), resource.CHUNK_QUOTES):
        quotes = view[first : min(first + resource.CHUNK_QUOTES, len(view))]
        exits.target.validate_quotes(quotes, session)
        if last is not None and quotes[0, 0] < last:
            raise ValueError("Liquidity native order differs across quote pages")
        last = int(quotes[-1, 0])
    result = []
    times = view[:, 0]
    for first in range(0, len(rows), CHUNK_ROWS):
        part = rows[first : first + CHUNK_ROWS]
        a = int(np.searchsorted(times, part[0]["decision_ts_ns"], side="left"))
        b = int(
            np.searchsorted(
                times, min(end - 1, part[-1]["decision_ts_ns"] + exits.target.MARGIN), side="right"
            )
        )
        quotes = view[a:b]
        if not len(quotes) or quotes[0, 0] < start:
            raise ValueError("Liquidity decision lacks original native source quote")
        for row in part:
            original = row["outcome"]
            if original["status"] == "resolved":
                index = int(np.searchsorted(times, original["exit_target_ts_ns"], side="left"))
                if index >= len(view) or tuple(view[index]) != (
                    original["exit_ts_ns"],
                    original["exit_bid_nano"],
                    original["exit_ask_nano"],
                ):
                    raise ValueError("Liquidity reference exit differs from original source")
        result.extend(exits.target.targets(part, quotes))
    exits._entry_parity(rows, result)
    if any(
        b["decision_ts_ns"] - a["decision_ts_ns"] < exits.target.SECOND
        for a, b in zip(result, result[1:], strict=False)
    ):
        raise ValueError("Liquidity decision order differs across target batches")
    return result


def accounting(rows: list[dict], labels: list[dict]) -> dict:
    signs = rules.rules(rows)  # Causal features only; outcomes not inspected by directions.
    indices = rules.sample(rows, labels)
    joint = sum(
        all(
            labels[i]["outcomes"]["bracket_exit"][s]["status"] == "resolved"
            for s in ("long", "short")
        )
        for i in indices
    )
    return {
        "source_session": rows[0]["source_session"],
        "role": data.role_for_day(rows[0]["source_session"]),
        "rows": len(rows),
        "eligible": sum(y["eligible"] for y in labels),
        "entry_statuses": dict(Counter(y["entry"]["status"] for y in labels)),
        "hindsight_states": {
            p: dict(Counter(y["hindsight_states"][p] for y in labels)) for p in exits.target.PLANS
        },
        "signals": {n: int(np.count_nonzero(v)) for n, v in signs.items()},
        "fit_sampling": {
            "cases": len(indices),
            "joint_resolved": joint,
            "unknown": len(indices) - joint,
        },
    }


def _replay_check(root: Path, entry: dict, replay: dict, metadata: dict) -> None:
    original = data.review.pinned(root / entry["report"]["path"], entry["report"]["sha256"])
    if (
        replay["full_member_hash_verified"] is not True
        or replay["quality"] != original["quality"]
        or replay["completed_quotes"] != metadata["count"]
        or replay["quote_columns"] != metadata["columns"]
        or replay["instrument_id"] != original["instrument_id"]
    ):
        raise ValueError("Liquidity replay conservation, clock or quote storage differs")


def pooled(days: list[dict]) -> dict:
    def add(group):
        return {
            "sessions": len(group),
            "rows": sum(d["rows"] for d in group),
            "eligible": sum(d["eligible"] for d in group),
            **{
                k: exits._sum([d[k] for d in group])
                for k in ("entry_statuses", "hindsight_states", "signals", "fit_sampling")
            },
        }

    return {
        "overall": add(days),
        "by_role": {
            r: add([d for d in days if d["role"] == r])
            for r in data.ROLES
            if any(d["role"] == r for d in days)
        },
    }


def collect(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen = registration(root, path, pin)
    exits.previous._inside(root, output)
    if shutil.disk_usage(root).free < 32 * 1024**3:
        raise ValueError("Insufficient free space for complete liquidity evidence")
    output.mkdir(parents=False, exist_ok=False)
    started, evidence, days, total_bytes = time.monotonic(), [], [], 0
    try:
        common._write_new(
            output / "request.json", {"registration_sha256": pin, "protocol": protocol()}
        )
        for source in frozen["sources"]:
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Liquidity whole-cohort collection deadline exceeded")
            entry, member = source["entry"], source["member"]
            day, day_start = entry["utc_date"], time.monotonic()
            exits.previous._journal(output, {"event": "native_session_started", "utc_date": day})
            rows, cases, replay = resource.replay_day(member, output / f"{day}.quotes")
            expected_rows, expected_cases = (
                data.read_rows(root, entry, "rows"),
                data.read_rows(root, entry, "cases"),
            )
            if common.canonical(rows) != common.canonical(expected_rows) or common.canonical(
                cases
            ) != common.canonical(expected_cases):
                raise ValueError("Liquidity original full rows or sixty-second cases differ")
            if replay["full_member_hash_verified"] is not True:
                raise ValueError("Liquidity source member did not verify at EOF")
            columns = replay["quote_columns"]
            count = next(iter(columns.values()))["bytes"] // 8
            quote_meta = {"count": count, "columns": columns}
            _replay_check(root, entry, replay, quote_meta)
            with _view(output / f"{day}.quotes", quote_meta) as view:
                labels = targets(rows, view)
            summary = accounting(rows, labels)
            raw = census.encode_rows(labels)
            labels_pin = _write_bytes(output / f"{day}.targets.jsonl", raw, census.MAX_DAY_BYTES)
            report = {
                "utc_date": day,
                "role": entry["role"],
                "source_sha256": entry["source_sha256"],
                "parity_verified": True,
                "replay": replay,
                "quotes": quote_meta,
                "accounting": summary,
            }
            common._write_new(output / f"{day}.json", report)
            evidence.append(
                {
                    "utc_date": day,
                    "rows": len(rows),
                    "quotes": quote_meta,
                    "targets_sha256": labels_pin,
                    "report_sha256": common.hash_file(output / f"{day}.json", 2 * 1024**2),
                }
            )
            days.append(summary)
            total_bytes += len(raw) + sum(x["bytes"] for x in columns.values())
            if (
                total_bytes > MAX_TOTAL_BYTES
                or time.monotonic() - day_start > census.MAX_DAY_SECONDS
            ):
                raise TimeoutError("Liquidity daily deadline or complete artifact budget exceeded")
            exits.previous._journal(
                output, {"event": "session_completed", "utc_date": day, "rows": len(rows)}
            )
            print(
                json.dumps(
                    {
                        "completed_liquidity_session": day,
                        "rows": len(rows),
                        "sessions": len(days),
                        "total_sessions": len(frozen["sources"]),
                    }
                ),
                flush=True,
            )
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_whole_liquidity_targets_not_validation",
                "registration_sha256": pin,
                "protocol": protocol(),
                "implementation_sha256": fingerprints(),
                "request_sha256": common.hash_file(output / "request.json", 2 * 1024**2),
                "days": evidence,
                "summaries": pooled(days),
                "flags": {**AUTH, "cpu_training": False},
                "elapsed_seconds": time.monotonic() - started,
                "completed_utc": datetime.now(UTC).isoformat(),
            },
        )
        completion_pin = common.hash_file(output / "completion.json", 2 * 1024**2)
        verified = verify_collection(root, path, pin, output, completion_pin)
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Liquidity complete terminal verification deadline exceeded")
        common._write_new(output / "verification.json", verified)
        return verified
    except Exception as exc:
        exits.previous._failure(output, pin, exc)
        raise


def verify_collection(root: Path, path: Path, pin: str, output: Path, completion_pin: str) -> dict:
    frozen = registration(root, path, pin)
    exits.previous._inside(root, output)
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        (output / "failure.json").exists()
        or report["status"] != "completed_whole_liquidity_targets_not_validation"
        or report["registration_sha256"] != pin
        or report["protocol"] != protocol()
        or report["implementation_sha256"] != fingerprints()
        or report["flags"] != {**AUTH, "cpu_training": False}
        or [d["utc_date"] for d in report["days"]]
        != [s["entry"]["utc_date"] for s in frozen["sources"]]
    ):
        raise ValueError("Liquidity complete collection identity, authority or coverage differs")
    request = data.review.pinned(output / "request.json", report["request_sha256"])
    if request != {"registration_sha256": pin, "protocol": protocol()}:
        raise ValueError("Liquidity original collection request differs")
    days = []
    for source, evidence in zip(frozen["sources"], report["days"], strict=True):
        entry, day = source["entry"], source["entry"]["utc_date"]
        rows = data.read_rows(root, entry, "rows")
        saved = data.review.pinned(output / f"{day}.json", evidence["report_sha256"])
        _replay_check(root, entry, saved["replay"], evidence["quotes"])
        with _view(output / f"{day}.quotes", evidence["quotes"]) as view:
            computed = targets(rows, view)
        labels = _labels(output / f"{day}.targets.jsonl", evidence["targets_sha256"], len(rows))
        summary = accounting(rows, computed)
        if (
            evidence["rows"] != len(rows)
            or common.canonical(computed) != common.canonical(labels)
            or saved["accounting"] != summary
            or saved["quotes"] != evidence["quotes"]
            or saved["parity_verified"] is not True
            or saved["replay"]["full_member_hash_verified"] is not True
            or saved["source_sha256"] != entry["source_sha256"]
        ):
            raise ValueError("Liquidity recomputed source targets, parity or accounting differs")
        days.append(summary)
    if common.canonical(pooled(days)) != common.canonical(report["summaries"]):
        raise ValueError("Liquidity whole-cohort pooled accounting differs")
    registration(root, path, pin)
    return {
        "status": "verified_whole_liquidity_targets_not_validation",
        "completion_sha256": completion_pin,
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "flags": {**AUTH, "cpu_training": False},
    }


def _training(root: Path, frozen: dict, build: Path, report: dict) -> tuple[list, list]:
    rows, labels = [], []
    for source, evidence in zip(frozen["sources"], report["days"], strict=True):
        entry = source["entry"]
        if entry["role"] != "train":
            continue  # Never read later-role targets to construct the fit.
        daily = data.read_rows(root, entry, "rows")
        target_rows = _labels(
            build / f"{entry['utc_date']}.targets.jsonl", evidence["targets_sha256"], len(daily)
        )
        indices = rules.sample(daily, target_rows)
        rows.extend(daily[i] for i in indices)
        labels.extend(target_rows[i] for i in indices)
        if len(rows) > rules.MAX_TRAIN_CASES:
            raise ValueError("Liquidity train-case resource bound exceeded")
    available = sum(
        all(y["outcomes"]["bracket_exit"][s]["status"] == "resolved" for s in ("long", "short"))
        for y in labels
    )
    if available < MIN_JOINT_TRAIN or len(labels) - available < MIN_UNKNOWN_TRAIN:
        raise ValueError("Liquidity CPU train support gate refused; no fit or subset")
    return rows, labels


def evaluate_day(
    rows: list[dict], labels: list[dict], model: rules.Model
) -> tuple[dict, np.ndarray]:
    forecast = model.predict(rules.matrix(rows))
    signs = rules.rules(rows)
    signs["cpu_cost"] = rules.actions(forecast)
    signs["cpu_cost_liquidity"] = np.where(
        [rules.liquid(r["features"]) for r in rows], signs["cpu_cost"], 0
    ).astype(np.int8)
    signs["no_trade"] = np.zeros(len(rows), dtype=np.int8)
    if any(
        (r["source_session"], r["decision_ts_ns"]) != (y["source_session"], y["decision_ts_ns"])
        for r, y in zip(rows, labels, strict=True)
    ):
        raise ValueError("Liquidity evaluation features and targets differ")
    policies = {}
    for name in rules.POLICIES:
        timed, schedule = exits.policy(labels, signs[name], "time_exit")
        bracket, _ = exits.policy(labels, signs[name], "bracket_exit")
        policies[name] = {
            "signals": int(np.count_nonzero(signs[name])),
            "time_exit": timed,
            "bracket_exit": bracket,
            "paired": exits.paired(labels, schedule),
        }
    indices = rules.sample(rows, labels)
    available = np.array(
        [
            all(
                labels[i]["outcomes"]["bracket_exit"][s]["status"] == "resolved"
                for s in ("long", "short")
            )
            for i in indices
        ]
    )
    p = forecast[indices]
    known = np.flatnonzero(available)
    net = np.array(
        [
            [
                labels[indices[i]]["outcomes"]["bracket_exit"][s]["net_ticks"]
                for s in ("long", "short")
            ]
            for i in known
        ],
        dtype=float,
    ).reshape(-1, 2)
    return {
        "source_session": rows[0]["source_session"],
        "role": data.role_for_day(rows[0]["source_session"]),
        "rows": len(rows),
        "policies": policies,
        "forecast_diagnostics": {
            "sampled_cases": len(indices),
            "joint_resolved": int(available.sum()),
            "unknown": int((~available).sum()),
            "availability_squared_error_sum": float(np.square(p[:, 0] - available).sum()),
            "conditional_net_squared_error_sum": np.square(p[known, 1:] - net).sum(axis=0).tolist(),
        },
    }, forecast


def evaluation_summaries(days: list[dict]) -> dict:
    def add(group):
        return {
            "sessions": len(group),
            "rows": sum(d["rows"] for d in group),
            "policies": {
                n: {
                    "signals": sum(d["policies"][n]["signals"] for d in group),
                    "sessions_with_signals": sum(d["policies"][n]["signals"] > 0 for d in group),
                    **{
                        k: exits._sum([d["policies"][n][k] for d in group])
                        for k in (*exits.target.PLANS, "paired")
                    },
                }
                for n in rules.POLICIES
            },
            "forecast_diagnostics": {
                "sampled_cases": sum(d["forecast_diagnostics"]["sampled_cases"] for d in group),
                "joint_resolved": sum(d["forecast_diagnostics"]["joint_resolved"] for d in group),
                "unknown": sum(d["forecast_diagnostics"]["unknown"] for d in group),
                "availability_squared_error_sum": sum(
                    d["forecast_diagnostics"]["availability_squared_error_sum"] for d in group
                ),
                "conditional_net_squared_error_sum": np.sum(
                    [d["forecast_diagnostics"]["conditional_net_squared_error_sum"] for d in group],
                    axis=0,
                ).tolist(),
            },
        }

    return {
        "overall": add(days),
        "by_role": {
            r: add([d for d in days if d["role"] == r])
            for r in data.ROLES
            if any(d["role"] == r for d in days)
        },
        "by_month": {
            month: add([d for d in days if d["source_session"][:7] == month])
            for month in sorted({d["source_session"][:7] for d in days})
        },
    }


def evaluate(root: Path, path: Path, pin: str, build: Path, build_pin: str, output: Path) -> dict:
    exits.previous._inside(root, output)
    if output.exists():
        raise FileExistsError("Liquidity CPU output is already claimed; no retry or resume")
    verify_collection(root, path, pin, build, build_pin)  # Complete gate BEFORE fitting.
    frozen = registration(root, path, pin)
    report = data.review.pinned(build / "completion.json", build_pin)
    exits.previous._inside(root, output)
    output.mkdir(parents=False, exist_ok=False)
    started, evidence, days = time.monotonic(), [], []
    try:
        common._write_new(
            output / "request.json",
            {
                "registration_sha256": pin,
                "build": str(build.resolve()),
                "build_sha256": build_pin,
                "protocol": protocol(),
            },
        )
        train_rows, train_labels = _training(root, frozen, build, report)
        model, fit_accounting = rules.fit(train_rows, train_labels)
        del train_rows, train_labels
        common._write_new(
            output / "model.json",
            {
                "model": model.payload(),
                "fit_accounting": fit_accounting,
                "flags": {**AUTH, "cpu_training": True},
            },
        )
        for source, built in zip(frozen["sources"], report["days"], strict=True):
            if time.monotonic() - started > MAX_EVAL_SECONDS:
                raise TimeoutError("Liquidity CPU evaluation deadline exceeded")
            entry, day = source["entry"], source["entry"]["utc_date"]
            rows = data.read_rows(root, entry, "rows")
            labels = _labels(build / f"{day}.targets.jsonl", built["targets_sha256"], len(rows))
            evaluated, forecast = evaluate_day(rows, labels, model)
            pred_pin = _write_bytes(
                output / f"{day}.predictions.f64", forecast.astype("<f8").tobytes(), 14400 * 24
            )
            common._write_new(output / f"{day}.json", evaluated)
            evidence.append(
                {
                    "utc_date": day,
                    "rows": len(rows),
                    "predictions_sha256": pred_pin,
                    "report_sha256": common.hash_file(output / f"{day}.json", 2 * 1024**2),
                }
            )
            days.append(evaluated)
            exits.previous._journal(
                output, {"event": "cpu_session_completed", "utc_date": day, "rows": len(rows)}
            )
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_quarantined_liquidity_cpu_not_validation",
                "registration_sha256": pin,
                "build_sha256": build_pin,
                "protocol": protocol(),
                "implementation_sha256": fingerprints(),
                "request_sha256": common.hash_file(output / "request.json", 2 * 1024**2),
                "model_sha256": common.hash_file(output / "model.json", 1024**2),
                "days": evidence,
                "summaries": evaluation_summaries(days),
                "fit_accounting": fit_accounting,
                "flags": {**AUTH, "cpu_training": True},
                "completed_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        completion_pin = common.hash_file(output / "completion.json", 2 * 1024**2)
        verified = verify_evaluation(root, path, pin, build, build_pin, output, completion_pin)
        if time.monotonic() - started > MAX_EVAL_SECONDS:
            raise TimeoutError("Liquidity CPU terminal verification deadline exceeded")
        common._write_new(output / "verification.json", verified)
        return verified
    except Exception as exc:
        exits.previous._failure(output, pin, exc)
        raise


def verify_evaluation(
    root: Path, path: Path, pin: str, build: Path, build_pin: str, output: Path, completion_pin: str
) -> dict:
    frozen = registration(root, path, pin)
    exits.previous._inside(root, build)
    exits.previous._inside(root, output)
    built = data.review.pinned(build / "completion.json", build_pin)
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        (output / "failure.json").exists()
        or (build / "failure.json").exists()
        or report["status"] != "completed_quarantined_liquidity_cpu_not_validation"
        or report["registration_sha256"] != pin
        or report["build_sha256"] != build_pin
        or report["protocol"] != protocol()
        or report["implementation_sha256"] != fingerprints()
        or report["flags"] != {**AUTH, "cpu_training": True}
        or [d["utc_date"] for d in report["days"]]
        != [s["entry"]["utc_date"] for s in frozen["sources"]]
    ):
        raise ValueError("Liquidity CPU completion identity, authority or full coverage differs")
    request = data.review.pinned(output / "request.json", report["request_sha256"])
    if request != {
        "registration_sha256": pin,
        "build": str(build.resolve()),
        "build_sha256": build_pin,
        "protocol": protocol(),
    }:
        raise ValueError("Liquidity CPU request differs")
    # Read-only verification of source/model arithmetic, never a worker or model fit.
    saved_model = data.review.pinned(output / "model.json", report["model_sha256"])
    if (
        saved_model["flags"] != {**AUTH, "cpu_training": True}
        or saved_model["fit_accounting"] != report["fit_accounting"]
    ):
        raise ValueError("Liquidity CPU model authority or training accounting differs")
    model = rules.Model(**saved_model["model"])
    train_rows, train_labels = _training(root, frozen, build, built)
    rules.verify_fit(model, train_rows, train_labels, report["fit_accounting"])
    del train_rows, train_labels
    days = []
    for source, b, evidence in zip(frozen["sources"], built["days"], report["days"], strict=True):
        entry, day = source["entry"], source["entry"]["utc_date"]
        rows = data.read_rows(root, entry, "rows")
        labels = _labels(build / f"{day}.targets.jsonl", b["targets_sha256"], len(rows))
        computed, prediction = evaluate_day(rows, labels, model)
        pp = output / f"{day}.predictions.f64"
        data.review.checked_hash(pp, evidence["predictions_sha256"], 14400 * 24)
        if (
            evidence["rows"] != len(rows)
            or pp.stat().st_size != len(rows) * 24
            or pp.read_bytes() != prediction.astype("<f8").tobytes()
            or data.review.pinned(output / f"{day}.json", evidence["report_sha256"]) != computed
        ):
            raise ValueError("Liquidity CPU recomputed forecasts or complete metrics differ")
        days.append(computed)
    if common.canonical(evaluation_summaries(days)) != common.canonical(report["summaries"]):
        raise ValueError("Liquidity CPU pooled metrics differ")
    verify_collection(root, path, pin, build, build_pin)
    registration(root, path, pin)
    return {
        "status": "verified_quarantined_liquidity_cpu_not_validation",
        "completion_sha256": completion_pin,
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "flags": {**AUTH, "cpu_training": True},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--registration", type=Path, required=True)
    p.add_argument("--enable-cpu-development-training", action="store_true")
    for action in ("collect", "verify-collection", "evaluate", "verify-evaluation"):
        p = sub.add_parser(action)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        p.add_argument("--output", type=Path, required=True)
        if action in ("evaluate", "verify-evaluation"):
            p.add_argument("--build-output", type=Path, required=True)
            p.add_argument("--build-sha256", required=True)
        if action.startswith("verify"):
            p.add_argument("--completion-sha256", required=True)
    a, root = parser.parse_args(), Path.cwd()
    if a.action == "prepare":
        prepare(
            root, a.manifest, a.manifest_sha256, a.registration, a.enable_cpu_development_training
        )
        result = {"registration_sha256": common.hash_file(a.registration, 2 * 1024**2)}
    elif a.action == "collect":
        result = collect(root, a.registration, a.registration_sha256, a.output)
    elif a.action == "verify-collection":
        result = verify_collection(
            root, a.registration, a.registration_sha256, a.output, a.completion_sha256
        )
    elif a.action == "evaluate":
        result = evaluate(
            root, a.registration, a.registration_sha256, a.build_output, a.build_sha256, a.output
        )
    else:
        result = verify_evaluation(
            root,
            a.registration,
            a.registration_sha256,
            a.build_output,
            a.build_sha256,
            a.output,
            a.completion_sha256,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
