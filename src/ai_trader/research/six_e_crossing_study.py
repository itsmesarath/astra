"""Two-stage frozen offline crossing support and quote-cost development comparison."""

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

from ai_trader.research import six_e_auction_study as parent
from ai_trader.training import six_e_crossing_playbooks as rules

data, common, prior, census = parent.data, parent.common, parent.prior, parent.census
events = rules.events
PURPOSE = "six_e_crossing_development_comparison_v1"
MAX_SECONDS = parent.MAX_SECONDS
FLAGS = parent.FLAGS
SUPPORT_GATE = {
    "minimum_qualified_markers": 20,
    "minimum_supported_sessions": 4,
    "minimum_validation_supported_sessions": 1,
}


def protocol() -> dict:
    return {
        "purpose": PURPOSE,
        "days": list(parent.DAYS),
        "parent_scope": parent.protocol()["exposure"],
        "representations": rules.protocol(),
        "split": data.protocol()["split"],
        "calibration": "Exactly the original pilot's feature-only training quantiles; "
        "no threshold changes, fit or model calls",
        "two_stage": "Freeze before native replay; build ALL feature-only support first. "
        "Cost evaluation needs the pinned, independently verified whole build and support "
        "gate; no successful subset or profit-based selection",
        "support_gate": SUPPORT_GATE,
        "parity": "All original rows AND all original 33-field auction snapshots must match "
        "the first pilot before a completed feature build may be claimed",
        "policy": parent.protocol()["policy"],
        "costs": parent.protocol()["costs"],
        "bounds": {
            "seconds": MAX_SECONDS,
            "day_seconds": census.MAX_DAY_SECONDS,
            "day_bytes": census.MAX_DAY_BYTES,
            "line_bytes": 65536,
            "rows_per_day": 14400,
        },
        "selection": "Exactly 11 fixed policies, no winner choice, search, retries, "
        "reserved access, automatic expansion or model promotion",
        **FLAGS,
    }


def fingerprints() -> dict:
    return {
        **parent.fingerprints(),
        **{
            Path(m.__file__).name: common.hash_file(Path(m.__file__), 1024**2)
            for m in (events, rules)
        },
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def _inside(root: Path, output: Path) -> None:
    if output.is_symlink() or not output.resolve().is_relative_to(
        (root / "data/processed").resolve()
    ):
        raise ValueError("Crossing evidence must stay inside project processed data")


def parent_evidence(root: Path, path: Path, pin: str, output: Path, completion_pin: str) -> tuple:
    _inside(root, output)
    frozen, manifest = parent.registration(root, path, pin)
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        (output / "failure.json").exists()
        or report["registration_sha256"] != pin
        or report["status"] != "completed_development_pilot_not_validation"
        or report["protocol"] != parent.protocol()
        or report["flags"] != FLAGS
        or report["implementation_sha256"] != parent.fingerprints()
        or [e["utc_date"] for e in report["days"]] != list(parent.DAYS)
    ):
        raise ValueError("Original pilot is not a complete frozen development reference")
    thresholds = data.review.pinned(output / "thresholds.json", report["thresholds_sha256"])
    bundle, accounting = parent._calibration(root, manifest)
    if thresholds != {"bundle": bundle, "accounting": accounting}:
        raise ValueError("Original pilot training calibration changed")
    return frozen, manifest, report, thresholds


def prepare(
    root: Path,
    parent_path: Path,
    parent_pin: str,
    parent_output: Path,
    parent_completion_pin: str,
    path: Path,
) -> dict:
    frozen, _, report, thresholds = parent_evidence(
        root, parent_path, parent_pin, parent_output, parent_completion_pin
    )
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "parent": {
            "registration": str(parent_path.resolve()),
            "registration_sha256": parent_pin,
            "output": str(parent_output.resolve()),
            "completion_sha256": parent_completion_pin,
        },
        "sources": frozen["sources"],
        "parent_days": report["days"],
        "thresholds": thresholds,
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Crossing protocol or implementation changed")
    p = frozen["parent"]
    original, manifest, report, thresholds = parent_evidence(
        root,
        Path(p["registration"]),
        p["registration_sha256"],
        Path(p["output"]),
        p["completion_sha256"],
    )
    if (
        frozen["sources"] != original["sources"]
        or frozen["parent_days"] != report["days"]
        or (frozen["thresholds"] != thresholds)
    ):
        raise ValueError("Crossing original sources, snapshots or thresholds changed")
    return frozen, manifest


class CrossingBuilder(parent.AuctionBuilder):
    def start_day(self, day) -> None:
        super().start_day(day)
        self.crossings = events.CrossingBuffer(day.isoformat(), self.contract)
        self.crossing_ofi = None
        self.crossing_rows = {}

    def _observe_completed_quote(self, quote) -> None:
        super()._observe_completed_quote(quote)
        if self.crossing_ofi is not self.ofi:
            self.crossings.reset()
            self.crossing_ofi = self.ofi
        self.crossings.observe(self.auction, quote)

    def _event_decision(self, quote) -> None:
        super()._event_decision(quote)
        self.crossing_rows[quote.ts_recv_ns] = self.crossings.publish(quote.ts_recv_ns)


def replay(member: dict) -> tuple[list[dict], list[dict], dict]:
    day = member["utc_date"]
    contract = census.dated_contract(day)  # Reserved guard before archive path construction.
    if (
        day not in parent.DAYS
        or member["contract"] != contract
        or member["condition"] != "available"
    ):
        raise ValueError("Undeclared crossing replay source")
    builder = CrossingBuilder(day, contract)
    builder.start_day(date.fromisoformat(day))
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Crossing source archive identity differs")
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        for index, record in enumerate(census.source._member_records(archive, member)):
            if index % 65536 == 0 and time.monotonic() - started > census.MAX_DAY_SECONDS:
                raise TimeoutError("Crossing daily native replay deadline exceeded")
            builder.consume(record)
        builder.finish_day()
    rows, _, quality = builder.finish()
    if stamp != (path.stat().st_size, path.stat().st_mtime_ns):
        raise ValueError("Crossing archive changed during replay")
    if time.monotonic() - started > census.MAX_DAY_SECONDS:
        raise TimeoutError("Crossing replay and original path analysis deadline exceeded")
    features = [
        {
            **{k: row[k] for k in parent.PROJECTION},
            "auction_features": builder.auction_rows[row["decision_ts_ns"]],
            "crossing_evidence": builder.crossing_rows[row["decision_ts_ns"]],
        }
        for row in rows
    ]
    if len(features) != len(builder.crossing_rows) or len(features) != len(builder.auction_rows):
        raise ValueError("Crossing sidecar has missing or orphan decision evidence")
    return (
        rows,
        features,
        {
            "quality": quality,
            "instrument_id": builder.instrument_id,
            "full_member_hash_verified": True,
            "crossing_audit": builder.crossings.report(),
            "elapsed_seconds": time.monotonic() - started,
        },
    )


def _read_features(path: Path, pin: str, count: int) -> list[dict]:
    if not 0 < count <= 14400:
        raise ValueError("Crossing sidecar count bound differs")
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    rows = []
    with path.open("rb") as stream:
        while line := stream.readline(65537):
            if len(line) > 65536 or not line.endswith(b"\n") or len(rows) >= count:
                raise ValueError("Incomplete or excessive crossing sidecar line")
            row = common.loads(line)
            if set(row) != {*parent.PROJECTION, "auction_features", "crossing_evidence"}:
                raise ValueError("Crossing sidecar accepts causal features only")
            rows.append(row)
    if len(rows) != count:
        raise ValueError("Crossing sidecar count differs")
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    return rows


def _check_parity(root: Path, frozen: dict, index: int, features: list[dict]) -> list[dict]:
    source, evidence = frozen["sources"][index], frozen["parent_days"][index]
    entry = source["entry"]
    day = entry["utc_date"]
    data.role_for_day(day)
    if day != parent.DAYS[index] or evidence["utc_date"] != day:
        raise ValueError("Crossing reference dates or roles differ")
    original = data.read_rows(root, entry, "rows")
    base_features = parent._feature_rows(
        Path(frozen["parent"]["output"]) / f"{day}.features.jsonl",
        evidence["features_sha256"],
        len(original),
    )
    projected = [{k: v for k, v in row.items() if k != "crossing_evidence"} for row in features]
    if common.canonical(projected) != common.canonical(base_features) or any(
        {k: r[k] for k in parent.PROJECTION} != {k: f[k] for k in parent.PROJECTION}
        for r, f in zip(original, features, strict=True)
    ):
        raise ValueError("Crossing original feature snapshot or row projection parity differs")
    return original


def _support_summary(days: list[dict]) -> dict:
    audits = {mode: Counter() for mode in (*rules.MODES, "snapshot")}
    signals, raw = Counter(), Counter()
    qualified, supported, later = 0, 0, 0
    for day in days:
        for mode in audits:
            audits[mode].update(day["support"]["audits"][mode])
        signals.update(day["support"]["signals"])
        raw.update(day["replay"]["crossing_audit"])
        n = day["support"]["audits"]["event"].get("qualified_markers", 0)
        qualified += n
        supported += int(n > 0)
        later += int(n > 0 and day["role"] == "validation_development")
    gate = {
        "qualified_markers": qualified,
        "supported_sessions": supported,
        "validation_supported_sessions": later,
    }
    passed = (
        qualified >= SUPPORT_GATE["minimum_qualified_markers"]
        and supported >= SUPPORT_GATE["minimum_supported_sessions"]
        and later >= SUPPORT_GATE["minimum_validation_supported_sessions"]
    )
    return {
        "sessions": len(days),
        "rows": sum(d["support"]["rows"] for d in days),
        "audits": {k: dict(v) for k, v in audits.items()},
        "signals": dict(signals),
        "crossing_audit": dict(raw),
        "gate": {**gate, "passed": passed},
    }


def _audit_replay(day: dict, features: list[dict]) -> None:
    if day["full_member_hash_verified"] is not True:
        raise ValueError("Crossing whole-member evidence is missing")
    audit = day["crossing_audit"]
    if audit.get("published_markers", 0) != sum(
        len(r["crossing_evidence"]["markers"]) for r in features
    ):
        raise ValueError("Crossing published marker audit differs from sidecar")
    if audit.get("completed_markers", 0) != sum(
        audit.get(k, 0)
        for k in ("published_markers", "unpublished_discarded_on_reset", "unpublished_tail_markers")
    ):
        raise ValueError("Crossing whole publication conservation differs")


def verify_build(root: Path, path: Path, pin: str, output: Path, completion_pin: str) -> dict:
    _inside(root, output)
    frozen, _ = registration(root, path, pin)
    if (output / "failure.json").exists():
        raise ValueError("Crossing feature build has failure evidence")
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        report["status"] != "completed_feature_support_not_cost_validation"
        or report["registration_sha256"] != pin
        or report["protocol"] != protocol()
        or report["implementation_sha256"] != fingerprints()
        or report["flags"] != FLAGS
        or [d["utc_date"] for d in report["days"]] != list(parent.DAYS)
    ):
        raise ValueError("Crossing build authority, protocol, pins or coverage differ")
    days = []
    for index, evidence in enumerate(report["days"]):
        entry = frozen["sources"][index]["entry"]
        day = entry["utc_date"]
        features = _read_features(
            output / f"{day}.features.jsonl",
            evidence["features_sha256"],
            entry["artifacts"]["rows"]["count"],
        )
        _check_parity(root, frozen, index, features)
        saved = data.review.pinned(output / f"{day}.json", evidence["report_sha256"])
        support = rules.support(features, frozen["thresholds"]["bundle"])
        if (
            saved["support"] != support
            or saved["utc_date"] != day
            or saved["role"] != entry["role"]
            or saved["parity_verified"] is not True
        ):
            raise ValueError("Crossing recomputed feature support or identity differs")
        _audit_replay(saved["replay"], features)
        days.append(saved)
    if common.canonical(_support_summary(days)) != common.canonical(report["summary"]):
        raise ValueError("Crossing complete feature support summary differs")
    registration(root, path, pin)
    return {
        "status": "verified_feature_support_not_cost_validation",
        "flags": FLAGS,
        "completion_sha256": completion_pin,
        "summary": report["summary"],
    }


def _journal(output: Path, value: dict) -> None:
    with (output / "progress.jsonl").open("ab") as stream:
        stream.write(common.canonical({"utc": datetime.now(UTC).isoformat(), **value}) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _failure(output: Path, pin: str, exc: Exception) -> None:
    common._write_new(
        output / "failure.json",
        {
            "status": "failed_no_subset_or_retry",
            "registration_sha256": pin,
            "exception": type(exc).__name__,
            "message": str(exc)[:1000],
            "flags": FLAGS,
        },
    )


def build(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen, _ = registration(root, path, pin)
    _inside(root, output)
    if shutil.disk_usage(root).free < 1024**3:
        raise ValueError("Insufficient space for bounded crossing evidence")
    output.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    try:
        common._write_new(
            output / "request.json", {"registration_sha256": pin, "protocol": protocol()}
        )
        days, evidence = [], []
        for index, source in enumerate(frozen["sources"]):
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Crossing whole feature build deadline exceeded")
            entry = source["entry"]
            day = entry["utc_date"]
            _journal(output, {"event": "session_started", "utc_date": day})
            rows, features, replay_evidence = replay(source["member"])
            original = _check_parity(root, frozen, index, features)
            if common.canonical(rows) != common.canonical(original):
                raise ValueError("Crossing replay differs from every original decision row")
            support = rules.support(features, frozen["thresholds"]["bundle"])
            _audit_replay(replay_evidence, features)
            saved = {
                "utc_date": day,
                "role": entry["role"],
                "support": support,
                "replay": replay_evidence,
                "parity_verified": True,
            }
            encoded = census.encode_rows(features)
            if any(len(line) > 65536 for line in encoded.splitlines(keepends=True)):
                raise ValueError("Crossing sidecar line bound exceeded")
            with (output / f"{day}.features.jsonl").open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            common._write_new(output / f"{day}.json", saved)
            evidence.append(
                {
                    "utc_date": day,
                    "features_sha256": common.hash_file(
                        output / f"{day}.features.jsonl", census.MAX_DAY_BYTES
                    ),
                    "report_sha256": common.hash_file(output / f"{day}.json", 2 * 1024**2),
                }
            )
            days.append(saved)
            _journal(
                output,
                {
                    "event": "session_completed_features_only",
                    "utc_date": day,
                    "rows": len(rows),
                    "parity_verified": True,
                },
            )
            print(json.dumps({"completed_feature_session": day, "rows": len(rows)}), flush=True)
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_feature_support_not_cost_validation",
                "registration_sha256": pin,
                "protocol": protocol(),
                "implementation_sha256": fingerprints(),
                "days": evidence,
                "summary": _support_summary(days),
                "flags": FLAGS,
                "completed_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        completion_pin = common.hash_file(output / "completion.json", 2 * 1024**2)
        result = verify_build(root, path, pin, output, completion_pin)
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Crossing complete build and verification deadline exceeded")
        common._write_new(output / "verification.json", result)
        _journal(output, {"event": "verified_complete_features_only", "sessions": len(days)})
        return result
    except Exception as exc:
        _failure(output, pin, exc)
        raise


def evaluate_day(rows: list[dict], features: list[dict], bundle: dict) -> dict:
    if (
        len(rows) != len(features)
        or not rows
        or any(
            {k: r[k] for k in parent.PROJECTION} != {k: f[k] for k in parent.PROJECTION}
            for r, f in zip(rows, features, strict=True)
        )
    ):
        raise ValueError("Crossing cost input projection or coverage differs")
    signs, audits = rules.directions(features, bundle)  # Before any outcome access.
    queue = np.array([rules.v1.sign(f["features"]["queue_imbalance"]) for f in features])
    return {
        "source_session": rows[0]["source_session"],
        "role": data.role_for_day(rows[0]["source_session"]),
        "rows": len(rows),
        "eligible": sum(r["eligible"] for r in rows),
        "statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "audits": audits,
        "policies": {
            name: {
                "events": parent.old.trigger_summary(rows, signs[name], queue),
                "policy": prior.policy_summary(
                    rows, np.column_stack((signs[name] > 0, signs[name] < 0)).astype(float)
                ),
            }
            for name in rules.POLICIES
        },
    }


def _aggregate(days: list[dict]) -> dict:
    result = {
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "eligible": sum(d["eligible"] for d in days),
        "policies": {},
    }
    statuses = Counter()
    for day in days:
        statuses.update(day["statuses"])
    result["statuses"] = dict(statuses)
    for name in rules.POLICIES:
        items = [d["policies"][name] for d in days]
        result["policies"][name] = {
            "events": sum(i["events"]["detected"] for i in items),
            "policy": prior.pooled_policy([i["policy"] for i in items]),
            "positive_sessions": sum(i["policy"]["total_closed_net_ticks"] > 0 for i in items),
            "negative_sessions": sum(i["policy"]["total_closed_net_ticks"] < 0 for i in items),
        }
    return result


def _summaries(days: list[dict]) -> dict:
    return {
        "overall": _aggregate(days),
        "by_role": {
            role: _aggregate([d for d in days if d["role"] == role])
            for role in data.ROLES
            if any(d["role"] == role for d in days)
        },
        "by_month": {
            month: _aggregate([d for d in days if d["source_session"].startswith(month)])
            for month in sorted({d["source_session"][:7] for d in days})
        },
    }


def _check_controls(frozen: dict, index: int, evaluated: dict) -> None:
    day = frozen["sources"][index]["entry"]["utc_date"]
    original = data.review.pinned(
        Path(frozen["parent"]["output"]) / f"{day}.json",
        frozen["parent_days"][index]["report_sha256"],
    )["evaluation"]
    for name in (*rules.FAMILIES, "burst_follow"):
        new_name = f"snapshot_{name}" if name in rules.FAMILIES else name
        if evaluated["policies"][new_name] != original["policies"][name]:
            raise ValueError(
                "Crossing unchanged snapshot/burst control differs from original pilot"
            )


def verify_evaluation(
    root: Path,
    path: Path,
    pin: str,
    build_output: Path,
    build_pin: str,
    output: Path,
    completion_pin: str,
) -> dict:
    _inside(root, output)
    verified = verify_build(root, path, pin, build_output, build_pin)
    if not verified["summary"]["gate"]["passed"] or (output / "failure.json").exists():
        raise ValueError("Crossing evaluation support gate or failure guard refused")
    frozen, _ = registration(root, path, pin)
    report = data.review.pinned(output / "completion.json", completion_pin)
    if (
        report["status"] != "completed_exposed_development_cost_comparison"
        or report["registration_sha256"] != pin
        or report["build_sha256"] != build_pin
        or report["protocol"] != protocol()
        or report["implementation_sha256"] != fingerprints()
        or report["flags"] != FLAGS
        or [d["utc_date"] for d in report["days"]] != list(parent.DAYS)
    ):
        raise ValueError("Crossing cost completion identity, authority or coverage differs")
    build_report = data.review.pinned(build_output / "completion.json", build_pin)
    days = []
    for index, evidence in enumerate(report["days"]):
        entry = frozen["sources"][index]["entry"]
        day = entry["utc_date"]
        features = _read_features(
            build_output / f"{day}.features.jsonl",
            build_report["days"][index]["features_sha256"],
            entry["artifacts"]["rows"]["count"],
        )
        rows = data.read_rows(root, entry, "rows")
        computed = evaluate_day(rows, features, frozen["thresholds"]["bundle"])
        saved = data.review.pinned(output / f"{day}.json", evidence["report_sha256"])
        if saved != computed:
            raise ValueError("Crossing recomputed complete session cost metrics differ")
        _check_controls(frozen, index, computed)
        days.append(computed)
    if common.canonical(_summaries(days)) != common.canonical(report["summaries"]):
        raise ValueError("Crossing all-session pooled cost metrics differ")
    registration(root, path, pin)
    return {
        "status": "verified_exposed_development_not_validation",
        "completion_sha256": completion_pin,
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "flags": FLAGS,
    }


def evaluate(
    root: Path, path: Path, pin: str, build_output: Path, build_pin: str, output: Path
) -> dict:
    verified = verify_build(root, path, pin, build_output, build_pin)
    if not verified["summary"]["gate"]["passed"]:
        raise ValueError("Crossing feature-only support gate refused; no cost subset scoring")
    frozen, _ = registration(root, path, pin)
    _inside(root, output)
    output.mkdir(parents=False, exist_ok=False)
    started = time.monotonic()
    try:
        build_report = data.review.pinned(build_output / "completion.json", build_pin)
        common._write_new(
            output / "request.json",
            {"registration_sha256": pin, "build_sha256": build_pin, "protocol": protocol()},
        )
        days, evidence = [], []
        for index, source in enumerate(frozen["sources"]):
            if time.monotonic() - started > MAX_SECONDS:
                raise TimeoutError("Crossing complete cost comparison deadline exceeded")
            entry = source["entry"]
            day = entry["utc_date"]
            features = _read_features(
                build_output / f"{day}.features.jsonl",
                build_report["days"][index]["features_sha256"],
                entry["artifacts"]["rows"]["count"],
            )
            rows = data.read_rows(root, entry, "rows")
            result = evaluate_day(rows, features, frozen["thresholds"]["bundle"])
            _check_controls(frozen, index, result)
            common._write_new(output / f"{day}.json", result)
            evidence.append(
                {
                    "utc_date": day,
                    "report_sha256": common.hash_file(output / f"{day}.json", 2 * 1024**2),
                }
            )
            days.append(result)
            _journal(
                output, {"event": "session_cost_completed", "utc_date": day, "rows": len(rows)}
            )
            print(json.dumps({"completed_cost_session": day, "rows": len(rows)}), flush=True)
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_exposed_development_cost_comparison",
                "protocol": protocol(),
                "registration_sha256": pin,
                "build_sha256": build_pin,
                "implementation_sha256": fingerprints(),
                "days": evidence,
                "summaries": _summaries(days),
                "flags": FLAGS,
                "completed_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        completion_pin = common.hash_file(output / "completion.json", 2 * 1024**2)
        verified = verify_evaluation(
            root, path, pin, build_output, build_pin, output, completion_pin
        )
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Crossing complete evaluation verification deadline exceeded")
        common._write_new(output / "verification.json", verified)
        return verified
    except Exception as exc:
        _failure(output, pin, exc)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--parent-registration", type=Path, required=True)
    p.add_argument("--parent-sha256", required=True)
    p.add_argument("--parent-output", type=Path, required=True)
    p.add_argument("--parent-completion-sha256", required=True)
    p.add_argument("--registration", type=Path, required=True)
    for action in ("build", "verify-build", "evaluate", "verify-evaluation"):
        p = sub.add_parser(action)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        p.add_argument("--output", type=Path, required=True)
        if action in ("evaluate", "verify-evaluation"):
            p.add_argument("--build-output", type=Path, required=True)
            p.add_argument("--build-sha256", required=True)
        if action in ("verify-build", "verify-evaluation"):
            p.add_argument("--completion-sha256", required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.action == "prepare":
        prepare(
            root,
            args.parent_registration,
            args.parent_sha256,
            args.parent_output,
            args.parent_completion_sha256,
            args.registration,
        )
        result = {"registration_sha256": common.hash_file(args.registration, 2 * 1024**2)}
    elif args.action == "build":
        result = build(root, args.registration, args.registration_sha256, args.output)
    elif args.action == "verify-build":
        result = verify_build(
            root, args.registration, args.registration_sha256, args.output, args.completion_sha256
        )
    elif args.action == "evaluate":
        result = evaluate(
            root,
            args.registration,
            args.registration_sha256,
            args.build_output,
            args.build_sha256,
            args.output,
        )
    else:
        result = verify_evaluation(
            root,
            args.registration,
            args.registration_sha256,
            args.build_output,
            args.build_sha256,
            args.output,
            args.completion_sha256,
        )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
