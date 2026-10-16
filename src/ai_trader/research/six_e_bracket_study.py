"""Frozen offline exit comparison and two-sided targets on exposed sessions only."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_bracket_targets as target

previous = target.previous
data, common, census = previous.data, previous.common, previous.census
FLAGS = previous.FLAGS
MAX_SECONDS = 2 * 3600
COOLDOWN = 10 * target.SECOND


def protocol() -> dict:
    return {
        "purpose": "six_e_cost_aware_exit_development_v1",
        "days": list(previous.parent.DAYS),
        "exposure": "Same exposed twelve-session development sample; no independent holdout",
        "targets": target.protocol(),
        "entries": "Exactly the previous eleven frozen feature-only direction rules; "
        "no threshold/entry/feature changes, fit, winner selection or parameter search",
        "policy": "One pending entry/position per policy and plan; 10s cooldown after "
        "close or entry refusal; unresolved entered exit blocks the rest of that session",
        "pairing": "Also compare both exit plans at ALL entries chosen by the time-exit "
        "schedule; expose unmatched outcomes, never choose only favorable pairs",
        "costs": "Base one extra tick sets bracket triggers; same closed selections "
        "recosted at 2/4 extra ticks without changing triggers or execution",
        "reference": "Original 15s exit has no new exit latency/wait cutoff; it remains "
        "an unchanged reference, not the matched time-exit comparator",
        "coverage": "ALL original rows, auction snapshots and crossing packets must match; "
        "consume original whole members to hash-verified EOF; no successful subsets",
        "proof": "Retain bounded native timestamp/bid/ask packed columns; all original "
        "decision and resolved 15s exit quotes must align; terminal verifier recomputes "
        "all targets and metrics from their pinned exact native sequence",
        "bounds": {
            "seconds": MAX_SECONDS,
            "day_seconds": census.MAX_DAY_SECONDS,
            "artifact_bytes": census.MAX_DAY_BYTES,
            "line_bytes": 65536,
            "rows_per_day": 14400,
        },
        "failure": "Exclusive output; retain failure evidence, no repair/retry or expansion",
        **FLAGS,
    }


def fingerprints() -> dict:
    return {
        **previous.fingerprints(),
        **{Path(m.__file__).name: common.hash_file(Path(m.__file__), 1024**2) for m in (target,)},
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def prepare(
    root: Path,
    path: Path,
    previous_path: Path,
    previous_pin: str,
    build_output: Path,
    build_pin: str,
    cost_output: Path,
    cost_pin: str,
) -> dict:
    previous.verify_evaluation(
        root, previous_path, previous_pin, build_output, build_pin, cost_output, cost_pin
    )
    frozen, _ = previous.registration(root, previous_path, previous_pin)
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "previous": {
            "registration": str(previous_path.resolve()),
            "registration_sha256": previous_pin,
            "build": str(build_output.resolve()),
            "build_sha256": build_pin,
            "cost": str(cost_output.resolve()),
            "cost_sha256": cost_pin,
        },
        "sources": frozen["sources"],
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Bracket protocol or implementation changed")
    p = frozen["previous"]
    original, _ = previous.registration(root, Path(p["registration"]), p["registration_sha256"])
    for kind, status in (
        ("build", "completed_feature_support_not_cost_validation"),
        ("cost", "completed_exposed_development_cost_comparison"),
    ):
        output = Path(p[kind])
        previous._inside(root, output)
        report = data.review.pinned(output / "completion.json", p[kind + "_sha256"])
        if (
            (output / "failure.json").exists()
            or report["status"] != status
            or report["registration_sha256"] != p["registration_sha256"]
            or report["flags"] != FLAGS
            or report["protocol"] != previous.protocol()
            or report["implementation_sha256"] != previous.fingerprints()
            or [d["utc_date"] for d in report["days"]] != list(previous.parent.DAYS)
        ):
            raise ValueError("Bracket original comparison is not complete and frozen")
        if kind == "build":
            build = report
            if not build["summary"]["gate"]["passed"]:
                raise ValueError("Original feature support gate refused")
        elif report["build_sha256"] != p["build_sha256"]:
            raise ValueError("Original feature/cost link differs")
    if frozen["sources"] != original["sources"]:
        raise ValueError("Bracket original sources changed")
    return frozen, original, build


def replay(member: dict) -> tuple[list[dict], list[dict], np.ndarray, dict]:
    day = member["utc_date"]
    contract = census.dated_contract(day)  # Reserved guard before archive construction.
    if (
        day not in previous.parent.DAYS
        or member["contract"] != contract
        or member["condition"] != "available"
    ):
        raise ValueError("Undeclared bracket replay source")
    builder = previous.CrossingBuilder(day, contract)
    builder.start_day(date.fromisoformat(day))
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Bracket archive identity differs")
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        for index, record in enumerate(census.source._member_records(archive, member)):
            if index % 65536 == 0 and time.monotonic() - started > census.MAX_DAY_SECONDS:
                raise TimeoutError("Bracket native replay deadline exceeded")
            builder.consume(record)
        builder.finish_day()
    rows, _, quality = builder.finish()
    if stamp != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError("Bracket archive changed during replay")
    features = [
        {
            **{k: r[k] for k in previous.parent.PROJECTION},
            "auction_features": builder.auction_rows[r["decision_ts_ns"]],
            "crossing_evidence": builder.crossing_rows[r["decision_ts_ns"]],
        }
        for r in rows
    ]
    if len(features) != len(builder.auction_rows) or len(features) != len(builder.crossing_rows):
        raise ValueError("Bracket feature coverage differs")
    quotes = np.frombuffer(builder.quote_buffer, dtype=np.int64).reshape(-1, 3)
    target.validate_quotes(quotes, day)
    quotes.setflags(write=False)
    return (
        rows,
        features,
        quotes,
        {
            "quality": quality,
            "full_member_hash_verified": True,
            "instrument_id": builder.instrument_id,
            "crossing_audit": builder.crossings.report(),
            "elapsed_seconds": time.monotonic() - started,
        },
    )


def policy(labels: list[dict], signs: np.ndarray, plan: str) -> tuple[dict, list]:
    if (
        not labels
        or not isinstance(signs, np.ndarray)
        or plan not in target.PLANS
        or signs.shape != (len(labels),)
        or signs.dtype.kind not in "iu"
        or not np.isin(signs, (-1, 0, 1)).all()
    ):
        raise ValueError("Fixed bracket policy directions required")
    session = labels[0]["source_session"]
    data.role_for_day(session)  # Metadata guard before any outcome access, even for idle.
    contract = census.dated_contract(session)
    if any(
        row["source_session"] != session
        or row["contract"] != contract
        or row["partition"] != "development"
        or type(row["eligible"]) is not bool
        for row in labels
    ) or any(
        b["decision_ts_ns"] - a["decision_ts_ns"] < target.SECOND
        for a, b in zip(labels, labels[1:], strict=False)
    ):
        raise ValueError("Bracket policy requires a single ordered development session")
    selected, closed, statuses, skips, triggers = [], [], Counter(), Counter(), Counter()
    free, blocked, unresolved, inactivity, widened, overshoot = 0, False, 0, 0, 0, 0
    holds = []
    for i, (row, direction) in enumerate(zip(labels, signs, strict=True)):
        now = row["decision_ts_ns"]
        if not row["eligible"]:
            skips["ineligible"] += 1
        elif blocked or now < free:
            skips["position_cooldown_or_unresolved"] += 1
        elif not direction:
            skips["no_signal"] += 1
        else:
            side = "long" if direction > 0 else "short"
            outcome, entry = row["outcomes"][plan][side], row["entry"]
            selected.append((i, int(direction)))
            statuses[outcome["status"]] += 1
            if outcome["trigger"] is not None:
                triggers[outcome["trigger"]] += 1
            if outcome["status"] == "resolved":
                closed.append(outcome["net_ticks"])
                holds.append(outcome["hold_seconds"])
                free = outcome["exit_ts_ns"] + COOLDOWN
                widened += outcome["exit_spread_ticks"] > 1
                overshoot += outcome["trigger"] == "stop" and outcome["net_ticks"] < target.STOP
            elif outcome["status"] == "unresolved_exit_quote_timeout":
                unresolved += 1
                blocked = True  # Never release an unobserved entered position as if closed.
            elif outcome["status"] == "no_entry_spread_widened":
                free = entry["rejection_ts_ns"] + COOLDOWN
            elif outcome["status"] == "no_entry_quote_timeout":
                free = entry["deadline_ts_ns"] + COOLDOWN
            else:
                raise ValueError("Unsupported selected bracket outcome")
            inactivity += outcome["inactivity_exposed"]
    return {
        "selected": len(selected),
        "closed": len(closed),
        "statuses": dict(statuses),
        "skips": dict(skips),
        "triggers": dict(triggers),
        "total_closed_net_ticks": sum(closed),
        "mean_net_ticks": sum(closed) / len(closed) if closed else None,
        "positive_closed": sum(x > 0 for x in closed),
        "unresolved_entered": unresolved,
        "inactivity_exposed_entered": inactivity,
        "widened_exit_spreads": widened,
        "stop_overshoot_closed": overshoot,
        "total_hold_seconds": sum(holds),
        "mean_hold_seconds": sum(holds) / len(holds) if holds else None,
        "extra_cost_ticks": {
            str(c): {
                "closed": len(closed),
                "total_closed_net_ticks": sum(x - c + 1 for x in closed),
                "positive_closed": sum(x - c + 1 > 0 for x in closed),
            }
            for c in (1, 2, 4)
        },
    }, selected


def paired(labels: list[dict], schedule: list) -> dict:
    counts = {p: Counter() for p in target.PLANS}
    differences = []
    for i, direction in schedule:
        sides = [
            labels[i]["outcomes"][p]["long" if direction > 0 else "short"] for p in target.PLANS
        ]
        for plan, outcome in zip(target.PLANS, sides, strict=True):
            counts[plan][outcome["status"]] += 1
        if all(o["status"] == "resolved" for o in sides):
            differences.append(sides[1]["net_ticks"] - sides[0]["net_ticks"])
    return {
        "common_time_exit_selected": len(schedule),
        "statuses": {k: dict(v) for k, v in counts.items()},
        "both_resolved": len(differences),
        "unmatched_or_unavailable": len(schedule) - len(differences),
        "bracket_minus_time_total_ticks": sum(differences),
        "mean_difference_ticks": sum(differences) / len(differences) if differences else None,
        "positive_difference": sum(x > 0 for x in differences),
        "negative_difference": sum(x < 0 for x in differences),
    }


def evaluate_day(labels: list[dict], features: list[dict], bundle: dict) -> dict:
    signs, audits = previous.rules.directions(features, bundle)  # Feature-only before targets.
    if len(labels) != len(features) or any(
        (label["source_session"], label["contract"], label["decision_ts_ns"])
        != (f["source_session"], f["contract"], f["decision_ts_ns"])
        for label, f in zip(labels, features, strict=True)
    ):
        raise ValueError("Bracket feature/target identity differs")
    policies = {}
    for name in previous.rules.POLICIES:
        timed, schedule = policy(labels, signs[name], "time_exit")
        bracket, _ = policy(labels, signs[name], "bracket_exit")
        policies[name] = {
            "signals": int(np.count_nonzero(signs[name])),
            "time_exit": timed,
            "bracket_exit": bracket,
            "paired": paired(labels, schedule),
        }
    return {
        "source_session": labels[0]["source_session"],
        "role": data.role_for_day(labels[0]["source_session"]),
        "rows": len(labels),
        "eligible": sum(r["eligible"] for r in labels),
        "entry_statuses": dict(Counter(r["entry"]["status"] for r in labels)),
        "hindsight_states": {
            p: dict(Counter(r["hindsight_states"][p] for r in labels)) for p in target.PLANS
        },
        "audits": audits,
        "policies": policies,
    }


def _sum(items: list[dict]) -> dict:
    if not items:
        raise ValueError("Cannot pool an empty bracket cohort")
    result = {}
    for key in sorted(set().union(*(d.keys() for d in items))):
        if key in ("mean_net_ticks", "mean_hold_seconds", "mean_difference_ticks"):
            continue
        values = [d[key] for d in items if key in d]
        result[key] = _sum(values) if isinstance(values[0], dict) else sum(values)
    if "closed" in result and "total_closed_net_ticks" in result:
        result["mean_net_ticks"] = (
            result["total_closed_net_ticks"] / result["closed"] if result["closed"] else None
        )
        if "total_hold_seconds" in result:
            result["mean_hold_seconds"] = (
                result["total_hold_seconds"] / result["closed"] if result["closed"] else None
            )
    if "both_resolved" in result:
        result["mean_difference_ticks"] = (
            result["bracket_minus_time_total_ticks"] / result["both_resolved"]
            if result["both_resolved"]
            else None
        )
    return result


def aggregate(days: list[dict]) -> dict:
    return {
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "eligible": sum(d["eligible"] for d in days),
        "entry_statuses": _sum([d["entry_statuses"] for d in days]),
        "hindsight_states": {
            p: _sum([d["hindsight_states"][p] for d in days]) for p in target.PLANS
        },
        "policies": {
            n: {
                "signals": sum(d["policies"][n]["signals"] for d in days),
                **{p: _sum([d["policies"][n][p] for d in days]) for p in (*target.PLANS, "paired")},
            }
            for n in previous.rules.POLICIES
        },
    }


def summaries(days: list[dict]) -> dict:
    return {
        "overall": aggregate(days),
        "by_role": {
            r: aggregate([d for d in days if d["role"] == r])
            for r in data.ROLES
            if any(d["role"] == r for d in days)
        },
    }


def _read_targets(path: Path, pin: str, count: int) -> list[dict]:
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    rows = []
    with path.open("rb") as stream:
        while line := stream.readline(65537):
            if len(line) > 65536 or not line.endswith(b"\n") or len(rows) >= count:
                raise ValueError("Incomplete or excessive bracket target sidecar")
            rows.append(common.loads(line))
    if not 0 < len(rows) == count <= 14400:
        raise ValueError("Bracket target row count differs")
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    return rows


def _entry_parity(rows: list[dict], labels: list[dict]) -> None:
    for row, label in zip(rows, labels, strict=True):
        if not label["eligible"]:
            continue
        entry, original = label["entry"], row["outcome"]
        if original.get("entry_ts_ns") is not None:
            if entry["status"] != "entered" or (
                entry["ts_ns"],
                entry["bid_nano"],
                entry["ask_nano"],
            ) != (original["entry_ts_ns"], original["entry_bid_nano"], original["entry_ask_nano"]):
                raise ValueError("Bracket shared entry differs from original first native quote")
        elif entry["status"] != original["status"] or (
            entry["status"] == "no_entry_spread_widened"
            and entry["rejection_ts_ns"] != original["entry_rejection_ts_ns"]
        ):
            raise ValueError("Bracket shared entry refusal differs from original")


def _quote_parity(rows: list[dict], features: list[dict], quotes: np.ndarray) -> None:
    target.validate_quotes(quotes, rows[0]["source_session"])
    times = quotes[:, 0]
    for row, feature in zip(rows, features, strict=True):
        i = int(np.searchsorted(times, row["decision_ts_ns"], side="left"))
        g = feature["auction_features"]
        if i >= len(quotes) or tuple(quotes[i]) != (
            row["decision_ts_ns"],
            g["bid_nano"],
            g["ask_nano"],
        ):
            raise ValueError("Bracket native decision quote differs from original snapshot")
        outcome = row["outcome"]
        if outcome["status"] == "resolved":
            j = int(np.searchsorted(times, outcome["exit_target_ts_ns"], side="left"))
            if j >= len(quotes) or tuple(quotes[j]) != (
                outcome["exit_ts_ns"],
                outcome["exit_bid_nano"],
                outcome["exit_ask_nano"],
            ):
                raise ValueError("Bracket native reference exit differs from original 15s quote")


def _features(
    root: Path, frozen: dict, original: dict, build: dict, index: int
) -> tuple[list, list]:
    entry = frozen["sources"][index]["entry"]
    features = previous._read_features(
        Path(frozen["previous"]["build"]) / f"{entry['utc_date']}.features.jsonl",
        build["days"][index]["features_sha256"],
        entry["artifacts"]["rows"]["count"],
    )
    rows = previous._check_parity(root, original, index, features)
    return rows, features


def verify(root: Path, path: Path, pin: str, output: Path, completion_pin: str) -> dict:
    previous._inside(root, output)
    frozen, original, build = registration(root, path, pin)
    if (output / "failure.json").exists():
        raise ValueError("Bracket experiment has retained failure evidence")
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        report["status"] != "completed_exposed_exit_comparison_not_validation"
        or report["protocol"] != protocol()
        or report["flags"] != FLAGS
        or report["registration_sha256"] != pin
        or report["implementation_sha256"] != fingerprints()
        or [d["utc_date"] for d in report["days"]] != list(previous.parent.DAYS)
    ):
        raise ValueError("Bracket completion identity, authority or coverage differs")
    request = data.review.pinned(output / "request.json", report["request_sha256"])
    if request != {"registration_sha256": pin, "protocol": protocol()}:
        raise ValueError("Bracket request identity differs")
    days = []
    for index, evidence in enumerate(report["days"]):
        rows, features = _features(root, frozen, original, build, index)
        day = evidence["utc_date"]
        qp = output / f"{day}.quotes.i64"
        size = data.review.checked_hash(qp, evidence["quotes_sha256"], census.MAX_DAY_BYTES)
        if size != evidence["quotes"] * 24 or not 0 < evidence["quotes"] <= census.paths.MAX_QUOTES:
            raise ValueError("Bracket native quote count or bytes differ")
        packed = np.memmap(qp, dtype="<i8", mode="r", shape=(evidence["quotes"], 3))
        try:
            _quote_parity(rows, features, packed)
            computed = target.targets(rows, packed)
            saved = _read_targets(
                output / f"{day}.targets.jsonl", evidence["targets_sha256"], len(rows)
            )
            if common.canonical(computed) != common.canonical(saved):
                raise ValueError("Bracket recomputed native targets differ")
            _entry_parity(rows, computed)
        finally:
            packed._mmap.close()
        data.review.checked_hash(qp, evidence["quotes_sha256"], census.MAX_DAY_BYTES)
        saved_day = data.review.pinned(output / f"{day}.json", evidence["report_sha256"])
        evaluated = evaluate_day(computed, features, original["thresholds"]["bundle"])
        if (
            saved_day["utc_date"] != day
            or saved_day["evaluation"] != evaluated
            or saved_day["parity_verified"] is not True
            or saved_day["replay"]["full_member_hash_verified"] is not True
        ):
            raise ValueError("Bracket metrics or original parity evidence differ")
        previous._audit_replay(saved_day["replay"], features)
        days.append(evaluated)
    if common.canonical(summaries(days)) != common.canonical(report["summaries"]):
        raise ValueError("Bracket pooled metrics differ")
    p = frozen["previous"]
    previous.verify_evaluation(
        root,
        Path(p["registration"]),
        p["registration_sha256"],
        Path(p["build"]),
        p["build_sha256"],
        Path(p["cost"]),
        p["cost_sha256"],
    )
    registration(root, path, pin)
    return {
        "status": "verified_exposed_exit_comparison_not_validation",
        "flags": FLAGS,
        "completion_sha256": completion_pin,
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
    }


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen, original, build = registration(root, path, pin)
    previous._inside(root, output)
    if shutil.disk_usage(root).free < 2 * 1024**3:
        raise ValueError("Insufficient space for bounded bracket evidence")
    output.mkdir(parents=False, exist_ok=False)
    started, days, evidence = time.monotonic(), [], []
    try:
        common._write_new(
            output / "request.json", {"registration_sha256": pin, "protocol": protocol()}
        )
        for index, source in enumerate(frozen["sources"]):
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Bracket whole experiment deadline exceeded")
            day, day_start = source["entry"]["utc_date"], time.monotonic()
            previous._journal(output, {"event": "native_session_started", "utc_date": day})
            rows, features, quotes, replay_evidence = replay(source["member"])
            expected_rows, expected_features = _features(root, frozen, original, build, index)
            if common.canonical(rows) != common.canonical(expected_rows) or common.canonical(
                features
            ) != common.canonical(expected_features):
                raise ValueError("Bracket original row or crossing feature parity differs")
            previous._audit_replay(replay_evidence, features)
            _quote_parity(rows, features, quotes)
            labels = target.targets(rows, quotes)
            _entry_parity(rows, labels)
            evaluated = evaluate_day(labels, features, original["thresholds"]["bundle"])
            saved = {
                "utc_date": day,
                "parity_verified": True,
                "replay": replay_evidence,
                "evaluation": evaluated,
            }
            for name, raw in (
                (f"{day}.quotes.i64", quotes.astype("<i8", copy=False).tobytes()),
                (f"{day}.targets.jsonl", census.encode_rows(labels)),
            ):
                if len(raw) > census.MAX_DAY_BYTES or (
                    name.endswith("jsonl")
                    and any(len(line) > 65536 for line in raw.splitlines(keepends=True))
                ):
                    raise ValueError("Bracket artifact bound exceeded")
                with (output / name).open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
            common._write_new(output / f"{day}.json", saved)
            evidence.append(
                {
                    "utc_date": day,
                    "quotes": len(quotes),
                    "quotes_sha256": common.hash_file(
                        output / f"{day}.quotes.i64", census.MAX_DAY_BYTES
                    ),
                    "targets_sha256": common.hash_file(
                        output / f"{day}.targets.jsonl", census.MAX_DAY_BYTES
                    ),
                    "report_sha256": common.hash_file(output / f"{day}.json", 2 * 1024**2),
                }
            )
            if time.monotonic() - day_start > census.MAX_DAY_SECONDS:
                raise TimeoutError("Bracket daily replay, targets and scoring deadline exceeded")
            days.append(evaluated)
            previous._journal(
                output, {"event": "session_completed", "utc_date": day, "rows": len(rows)}
            )
            print(json.dumps({"completed_exit_session": day, "rows": len(rows)}), flush=True)
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_exposed_exit_comparison_not_validation",
                "protocol": protocol(),
                "registration_sha256": pin,
                "implementation_sha256": fingerprints(),
                "days": evidence,
                "request_sha256": common.hash_file(output / "request.json", 2 * 1024**2),
                "summaries": summaries(days),
                "flags": FLAGS,
                "elapsed_seconds": time.monotonic() - started,
                "completed_utc": datetime.now(UTC).isoformat(),
            },
        )
        completion_pin = common.hash_file(output / "completion.json", 2 * 1024**2)
        result = verify(root, path, pin, output, completion_pin)
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Bracket final verification deadline exceeded")
        common._write_new(output / "verification.json", result)
        return result
    except Exception as exc:
        previous._failure(output, pin, exc)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare")
    for name in ("previous-registration", "build-output", "cost-output", "registration"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in ("previous-sha256", "build-sha256", "cost-sha256"):
        p.add_argument("--" + name, required=True)
    for action in ("run", "verify"):
        p = sub.add_parser(action)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        p.add_argument("--output", type=Path, required=True)
        if action == "verify":
            p.add_argument("--completion-sha256", required=True)
    args, root = parser.parse_args(), Path.cwd()
    if args.action == "prepare":
        prepare(
            root,
            args.registration,
            args.previous_registration,
            args.previous_sha256,
            args.build_output,
            args.build_sha256,
            args.cost_output,
            args.cost_sha256,
        )
        result = {"registration_sha256": common.hash_file(args.registration, 2 * 1024**2)}
    elif args.action == "run":
        result = run(root, args.registration, args.registration_sha256, args.output)
    else:
        result = verify(
            root, args.registration, args.registration_sha256, args.output, args.completion_sha256
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
