"""Registered offline price-level pilot on exposed 6E development data only."""

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

from ai_trader.research import six_e_auction_features as tape
from ai_trader.training import six_e_auction_playbooks as rules

old = rules.old
data, common, prior, census = old.data, old.common, old.prior, old.data.census
PURPOSE = "six_e_auction_development_pilot_v1"
DAYS = (
    "2025-04-07",
    "2025-04-08",
    "2025-04-09",
    "2025-07-07",
    "2025-07-08",
    "2025-07-09",
    "2025-10-06",
    "2025-10-07",
    "2025-10-08",
    "2025-12-08",
    "2025-12-09",
    "2025-12-10",
)
MAX_SECONDS = 2 * 3600
PROJECTION = (
    "source_session",
    "contract",
    "partition",
    "decision_ts_ns",
    "features",
    "execution_features",
)
POLICIES = (
    *rules.FAMILIES,
    *(f"{name}_{control}" for name in rules.FAMILIES for control in ("cvd", "queue")),
    "burst_follow",
    "no_trade",
)
FLAGS = {
    "independent_holdout": False,
    "promotion_allowed": False,
    "trading_enabled": False,
    "reserved_outcomes_opened": False,
    "model_training": False,
}


def protocol() -> dict:
    return {
        "purpose": PURPOSE,
        "days": list(DAYS),
        "selection": "Fixed calendar weekdays spanning April July October December; "
        "not performance-ranked; only 12 accepted sessions, not the full archive",
        "exposure": "All selected outcomes already exposed development; later roles are "
        "chronological development comparisons, NOT independent holdouts",
        "features": tape.protocol(),
        "rules": rules.protocol(),
        "calibration": "All original early train 60s cases, feature-only q90 initiation "
        "and q70 confirmation activity, including unknown-outcome cases",
        "price_replay": "Unchanged dated-contract strict MBO engine; T/F_LAST price-level "
        "sidecar; exact canonical parity with every original decision row is mandatory",
        "policy": old.protocol()["policy"],
        "costs": old.protocol()["costs"],
        "limits": {
            "seconds": MAX_SECONDS,
            "day_seconds": census.MAX_DAY_SECONDS,
            "day_bytes": census.MAX_DAY_BYTES,
            "rows_per_day": 14400,
        },
        "policies": list(POLICIES),
        "interpretation": "Quote-based 15s directional exits, not actual futures/CFD fills "
        "or account PnL; unknown attempts remain unknown; not a variable stop/target backtest",
        "next_gate": "No winner selection, retuning, retries or automatic corpus expansion; "
        "negative costs stop deployment; positive pilot alone cannot authorize promotion",
        **FLAGS,
    }


def fingerprints() -> dict:
    return {
        **old.fingerprints(),
        **{
            Path(m.__file__).name: common.hash_file(Path(m.__file__), 1024**2)
            for m in (tape, rules)
        },
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }


def sources(root: Path, manifest: dict) -> list[dict]:
    frozen = census.registration(
        root, root / data.diagnostic.REGISTRATION, data.diagnostic.REGISTRATION_PIN
    )
    entries = {e["utc_date"]: e for e in manifest["ledger"]}
    inventory = {e["utc_date"]: e for e in frozen["inventory"]["ledger"]}
    selected = []
    for day in DAYS:
        role, contract = data.role_for_day(day), census.dated_contract(day)
        entry, member = entries[day], inventory[day]
        if (
            entry["role"] != role
            or entry["contract"] != contract
            or entry["disposition"] != "decision_session"
            or member["condition"] != "available"
            or member["partition"] != "development"
            or member["contract"] != contract
            or member["sha256"] != entry["source_sha256"]
        ):
            raise ValueError("Auction pilot requires every declared accepted development source")
        selected.append({"entry": entry, "member": member})
    return selected


def prepare(root: Path, manifest_path: Path, manifest_pin: str, path: Path) -> dict:
    manifest = data.load(root, manifest_path, manifest_pin)
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "sources": sources(root, manifest),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def registration(root: Path, path: Path, pin: str) -> tuple[dict, dict]:
    frozen = data.review.pinned(path, pin)
    if frozen["protocol"] != protocol() or frozen["implementation_sha256"] != fingerprints():
        raise ValueError("Auction protocol or implementation changed")
    manifest = data.load(root, Path(frozen["manifest"]["path"]), frozen["manifest"]["sha256"])
    if frozen["sources"] != sources(root, manifest):
        raise ValueError("Auction source identities or roles changed")
    return frozen, manifest


class AuctionBuilder(census.DailyBuilder):
    def start_day(self, day) -> None:
        super().start_day(day)
        self.auction = tape.AuctionFeatures(day.isoformat(), self.contract)
        self.auction_ofi = None
        self.auction_rows = {}
        self.auction_resets = 0

    def _observe_completed_quote(self, quote) -> None:
        super()._observe_completed_quote(quote)
        if self.auction_ofi is not self.ofi:
            self.auction = tape.AuctionFeatures(self.day.isoformat(), self.contract)
            self.auction_ofi = self.ofi
            self.auction_resets += 1
        self.auction.observe(quote, self.event_records)

    def _event_decision(self, quote) -> None:
        super()._event_decision(quote)
        self.auction_rows[quote.ts_recv_ns] = self.auction.features(quote.ts_recv_ns)


def replay(member: dict) -> tuple[list[dict], list[dict], dict]:
    day = member["utc_date"]
    contract = census.dated_contract(day)  # Guard before accessing archive paths.
    if day not in DAYS or member["contract"] != contract or member["condition"] != "available":
        raise ValueError("Undeclared auction replay source")
    builder = AuctionBuilder(day, contract)
    builder.start_day(date.fromisoformat(day))
    path = Path(member["archive"])
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    if path.is_symlink() or stamp[0] != member["archive_bytes"]:
        raise ValueError("Auction archive identity changed")
    started = time.monotonic()
    with zipfile.ZipFile(path) as archive:
        for index, record in enumerate(census.source._member_records(archive, member)):
            if index % 65536 == 0 and time.monotonic() - started > census.MAX_DAY_SECONDS:
                raise TimeoutError("Auction daily native replay deadline exceeded")
            builder.consume(record)
        builder.finish_day()
    rows, _, quality = builder.finish()
    if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
        raise ValueError("Auction archive changed during complete member replay")
    if time.monotonic() - started > census.MAX_DAY_SECONDS:
        raise TimeoutError("Auction replay and original path analysis deadline exceeded")
    features = [
        {
            **{key: row[key] for key in PROJECTION},
            "auction_features": builder.auction_rows[row["decision_ts_ns"]],
        }
        for row in rows
    ]
    if len(features) != len(builder.auction_rows):
        raise ValueError("Auction sidecar has orphan or missing decisions")
    return (
        rows,
        features,
        {
            "quality": quality,
            "instrument_id": builder.instrument_id,
            "full_member_hash_verified": True,
            "auction_resets": builder.auction_resets,
            "elapsed_seconds": time.monotonic() - started,
        },
    )


def evaluate(rows: list[dict], features: list[dict], bundle: dict) -> dict:
    if len(rows) != len(features) or not rows:
        raise ValueError("Auction sidecar coverage differs")
    if any(
        {k: r[k] for k in PROJECTION} != {k: f[k] for k in PROJECTION}
        for r, f in zip(rows, features, strict=True)
    ):
        raise ValueError("Auction causal sidecar projection differs from original rows")
    # All decisions computed before any target/outcome scoring.
    detected, audit = rules.directions(features, bundle)
    cvd = np.array([rules.sign(r["features"]["normalized_cvd_5s"]) for r in features])
    queue = np.array([rules.sign(r["features"]["queue_imbalance"]) for r in features])
    controls = {
        f"{name}_{control}": np.where(signs != 0, values, 0)
        for name, signs in detected.items()
        for control, values in (("cvd", cvd), ("queue", queue))
    }
    old_signals, old_audit = old.directions(features, bundle)
    audit.update(old_audit)
    policies = {
        **detected,
        **controls,
        "burst_follow": old_signals["burst_follow"],
        "no_trade": np.zeros(len(rows), dtype=np.int8),
    }
    result = {
        "source_session": rows[0]["source_session"],
        "role": data.role_for_day(rows[0]["source_session"]),
        "rows": len(rows),
        "eligible": sum(r["eligible"] for r in rows),
        "statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "audit": audit,
        "policies": {},
    }
    for name in POLICIES:
        values = policies[name]
        result["policies"][name] = {
            "events": old.trigger_summary(rows, values, queue),
            "policy": prior.policy_summary(
                rows, np.column_stack((values > 0, values < 0)).astype(float)
            ),
        }
    return result


def aggregate(days: list[dict]) -> dict:
    statuses, audit = Counter(), Counter()
    for day in days:
        statuses.update(day["statuses"])
        audit.update(day["audit"])
    result = {
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "eligible": sum(d["eligible"] for d in days),
        "statuses": dict(statuses),
        "resolved": statuses["resolved"],
        "unknown": sum(statuses.values()) - statuses["resolved"],
        "audit": dict(audit),
        "policies": {},
    }
    for name in POLICIES:
        items = [d["policies"][name] for d in days]
        pooled = prior.pooled_policy([item["policy"] for item in items])
        result["policies"][name] = {
            "events": sum(item["events"]["detected"] for item in items),
            "policy": pooled,
            "positive_sessions": sum(i["policy"]["total_closed_net_ticks"] > 0 for i in items),
            "negative_sessions": sum(i["policy"]["total_closed_net_ticks"] < 0 for i in items),
            "zero_or_no_closed_sessions": sum(
                i["policy"]["total_closed_net_ticks"] == 0 for i in items
            ),
        }
    return result


def summaries(days: list[dict]) -> dict:
    return {
        "overall": aggregate(days),
        "by_role": {
            role: aggregate([d for d in days if d["role"] == role])
            for role in data.ROLES
            if any(d["role"] == role for d in days)
        },
        "by_month": {
            month: aggregate([d for d in days if d["source_session"].startswith(month)])
            for month in sorted({d["source_session"][:7] for d in days})
        },
    }


def _calibration(root: Path, manifest: dict, deadline=lambda: None) -> tuple[dict, dict]:
    samples, accounting = old.calibration_cases(root, manifest, deadline)
    return rules.calibrate(samples), accounting


def _feature_rows(path: Path, pin: str, count: int) -> list[dict]:
    if path.is_symlink() or not 0 < count <= 14400:
        raise ValueError("Invalid auction sidecar path or count")
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    result = []
    with path.open("rb") as stream:
        for line in stream:
            if len(line) > 65536 or not line.endswith(b"\n") or len(result) >= count:
                raise ValueError("Incomplete or excessive auction sidecar line")
            row = common.loads(line)
            if set(row) != {*PROJECTION, "auction_features"}:
                raise ValueError("Auction sidecar must contain features only")
            result.append(row)
    if len(result) != count:
        raise ValueError("Auction sidecar count differs")
    data.review.checked_hash(path, pin, census.MAX_DAY_BYTES)
    return result


def verify(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen, manifest = registration(root, path, pin)
    if (output / "failure.json").exists():
        raise ValueError("Auction pilot has failure evidence; no subset verification")
    report = data.review.pinned(
        output / "completion.json", common.hash_file(output / "completion.json", 16 * 1024**2)
    )
    if (
        report["status"] != "completed_development_pilot_not_validation"
        or report["registration_sha256"] != pin
        or report["protocol"] != protocol()
        or report["implementation_sha256"] != fingerprints()
        or report["flags"] != FLAGS
        or len(report["days"]) != len(DAYS)
    ):
        raise ValueError("Auction completion authority, identity or coverage differs")
    bundle, accounting = _calibration(root, manifest)
    stored = data.review.pinned(output / "thresholds.json", report["thresholds_sha256"])
    if stored != {"bundle": bundle, "accounting": accounting}:
        raise ValueError("Auction feature-only training calibration changed")
    days = []
    for source, evidence in zip(frozen["sources"], report["days"], strict=True):
        day = source["entry"]["utc_date"]
        if evidence["utc_date"] != day:
            raise ValueError("Auction completed session order differs")
        rows = data.read_rows(root, source["entry"], "rows")
        features = _feature_rows(
            output / f"{day}.features.jsonl", evidence["features_sha256"], len(rows)
        )
        computed = evaluate(rows, features, bundle)
        saved = data.review.pinned(output / f"{day}.json", evidence["report_sha256"])
        if (
            saved["evaluation"] != computed
            or not saved["replay"]["full_member_hash_verified"]
            or (saved["parity_verified"] is not True)
        ):
            raise ValueError("Auction replay evidence or recomputed metrics differ")
        days.append(computed)
    if common.canonical(summaries(days)) != common.canonical(report["summaries"]):
        raise ValueError("Auction pooled metrics differ from every complete session")
    registration(root, path, pin)
    return {
        "status": "verified_development_pilot_not_validation",
        "sessions": len(days),
        "rows": sum(d["rows"] for d in days),
        "flags": FLAGS,
        "completion_sha256": common.hash_file(output / "completion.json", 16 * 1024**2),
    }


def run(root: Path, path: Path, pin: str, output: Path) -> dict:
    frozen, manifest = registration(root, path, pin)
    if output.is_symlink() or not output.resolve().is_relative_to(
        (root / "data" / "processed").resolve()
    ):
        raise ValueError("Auction output must be new project processed evidence")
    if shutil.disk_usage(root).free < 1024**3:
        raise ValueError("Insufficient free space for bounded auction pilot")
    output.mkdir(parents=False, exist_ok=False)  # Exclusive, no restarts or retries.
    started = time.monotonic()

    def deadline():
        if time.monotonic() - started > MAX_SECONDS:
            raise TimeoutError("Auction whole-pilot deadline exceeded")

    def event(value):
        with (output / "progress.jsonl").open("ab") as stream:
            stream.write(common.canonical({"utc": datetime.now(UTC).isoformat(), **value}) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())

    try:
        common._write_new(
            output / "request.json", {"registration_sha256": pin, "protocol": protocol()}
        )
        bundle, accounting = _calibration(root, manifest, deadline)
        common._write_new(output / "thresholds.json", {"bundle": bundle, "accounting": accounting})
        event({"event": "calibration_frozen", "cases": accounting["cases"]})
        days, evidence = [], []
        for source in frozen["sources"]:
            deadline()
            entry, member = source["entry"], source["member"]
            day = entry["utc_date"]
            event({"event": "session_started", "utc_date": day})
            original = data.read_rows(root, entry, "rows")
            rows, features, replay_evidence = replay(member)
            if common.canonical(rows) != common.canonical(original):
                raise ValueError("Auction replay differs from pinned original decision rows")
            evaluation = evaluate(original, features, bundle)
            with (output / f"{day}.features.jsonl").open("xb") as stream:
                stream.write(census.encode_rows(features))
                stream.flush()
                os.fsync(stream.fileno())
            common._write_new(
                output / f"{day}.json",
                {
                    "evaluation": evaluation,
                    "replay": replay_evidence,
                    "parity_verified": True,
                },
            )
            evidence.append(
                {
                    "utc_date": day,
                    "features_sha256": common.hash_file(
                        output / f"{day}.features.jsonl", census.MAX_DAY_BYTES
                    ),
                    "report_sha256": common.hash_file(output / f"{day}.json", 16 * 1024**2),
                }
            )
            days.append(evaluation)
            event(
                {
                    "event": "session_completed",
                    "utc_date": day,
                    "rows": len(rows),
                    "parity_verified": True,
                }
            )
            print(json.dumps({"completed_session": day, "rows": len(rows)}), flush=True)
        deadline()
        registration(root, path, pin)
        common._write_new(
            output / "completion.json",
            {
                "status": "completed_development_pilot_not_validation",
                "protocol": protocol(),
                "registration_sha256": pin,
                "implementation_sha256": fingerprints(),
                "thresholds_sha256": common.hash_file(output / "thresholds.json", 1024**2),
                "days": evidence,
                "summaries": summaries(days),
                "flags": FLAGS,
                "completed_utc": datetime.now(UTC).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
            },
        )
        verified = verify(root, path, pin, output)
        deadline()
        common._write_new(output / "verification.json", verified)
        event({"event": "verified_complete", "sessions": len(days)})
        return verified
    except Exception as exc:
        common._write_new(
            output / "failure.json",
            {
                "status": "failed_no_subset_scoring_or_retry",
                "registration_sha256": pin,
                "exception": type(exc).__name__,
                "message": str(exc)[:1000],
                "flags": FLAGS,
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--registration", type=Path, required=True)
    for action in ("run", "verify"):
        p = sub.add_parser(action)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    if args.action == "prepare":
        prepare(root, args.manifest, args.manifest_sha256, args.registration)
        print(json.dumps({"registration_sha256": common.hash_file(args.registration, 2 * 1024**2)}))
    else:
        result = (run if args.action == "run" else verify)(
            root, args.registration, args.registration_sha256, args.output
        )
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
