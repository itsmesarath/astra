"""Verify a completed development census and describe its movement cases.

Reads published evidence only. Reserved dates are accounted for without opening
their artifacts. Associations and hindsight opportunity counts are not trades.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import historical_6e_archive as census

common, cohort = census.common, census.v1
FEATURES = (*census.study.data.FEATURES, *census.study.flow.FEATURES)
MAX_METADATA_BYTES = 2 * 1024**2
MAX_CASE_LINE = 64 * 1024
MAX_CASES_PER_DAY = 240
MIN_CLASS_SUPPORT = 5  # Descriptive AUC support, never a trading threshold.
STATUS = "census_completed_not_strategy_validated"


def pinned(path: Path, pin: str, limit: int = MAX_METADATA_BYTES) -> dict:
    return cohort.read_pinned(path, pin, limit)


def checked_hash(path: Path, pin: str, limit: int) -> int:
    if path.is_symlink() or not path.is_file() or common.hash_file(path, limit) != pin:
        raise ValueError("Missing, linked or changed census artifact")
    return path.stat().st_size


def read_cases(path: Path, report: dict) -> list[dict]:
    rows, digest, size = [], hashlib.sha256(), 0
    with path.open("rb") as handle:
        while raw := handle.readline(MAX_CASE_LINE + 1):
            size += len(raw)
            if (
                len(raw) > MAX_CASE_LINE
                or not raw.endswith(b"\n")
                or size > census.MAX_DAY_BYTES
                or len(rows) >= MAX_CASES_PER_DAY
            ):
                raise ValueError("Invalid bounded census case file")
            digest.update(raw)
            rows.append(common.loads(raw))
    if digest.hexdigest() != report["cases_sha256"] or len(rows) != report["cases"]:
        raise ValueError("Census case hash or count differs")
    day = report["utc_date"]
    if rows:
        census.baseline.validate_rows(
            rows, sessions=(day,), feature_names=census.study.data.FEATURES
        )
    for row in rows:
        execution = row["execution_features"]
        if (
            row["partition"] != "development"
            or row["contract"] != report["contract"]
            or row["eligible"] is not True
            or set(execution) != set(census.study.flow.FEATURES)
            or any(
                type(v) not in (int, float) or not math.isfinite(v) or v < 0
                for v in execution.values()
            )
        ):
            raise ValueError("Invalid case identity, eligibility or execution features")
    if census.study.diagnostics.thin_causally(rows) != rows:
        raise ValueError("Census cases violate causal sixty-second spacing")
    if census.case_associations(rows) != report["case_associations"]:
        raise ValueError("Case associations differ from published evidence")
    if census.paths.horizon_summary(rows) != report["thinned_paths"]:
        raise ValueError("Movement paths differ from published evidence")
    return rows


def refusal_category(error: str) -> str:
    return {
        "Daily completed quote bound exceeded": "resource_quote_bound",
        "Missing or excessive event decisions in source session": "decision_count_check",
        "Target MBO has a bad timestamp or quality flag": "source_quality_flag",
    }.get(error, "other_retained_refusal")


def verify_census(
    directory: Path, registration_path: Path, registration_sha256: str, receipt_sha256: str
) -> tuple[dict, list[dict], list[dict]]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Missing or linked census directory")
    receipt = pinned(directory / "completion.json", receipt_sha256)
    registration = pinned(registration_path, registration_sha256)
    if (
        receipt["status"] != STATUS
        or receipt["registration_sha256"] != registration_sha256
        or any(
            receipt[key] is not False
            for key in (
                "training_enabled",
                "promotion_enabled",
                "strategy_aggregate_permitted",
                "reserved_outcomes_opened",
            )
        )
        or (directory / "failure.json").exists()
        or registration["protocol"]["version"] != "6e_development_archive_census_v1"
        or registration["protocol"]["features"] != list(FEATURES)
    ):
        raise ValueError("Receipt is not a completed research-only development census")
    checked_hash(directory / "progress.jsonl", receipt["progress_sha256"], MAX_METADATA_BYTES)
    journal = [
        common.loads(raw) for raw in (directory / "progress.jsonl").read_bytes().splitlines()
    ]
    if journal != receipt["dates"]:
        raise ValueError("Receipt and progress date records differ")
    ledger = registration["inventory"]["ledger"]
    dates = [row["utc_date"] for row in ledger]
    if (
        not dates
        or len(dates) != len(set(dates))
        or dates != sorted(dates)
        or dates != [row["utc_date"] for row in journal]
        or dict(Counter(row["status"] for row in journal)) != receipt["counts"]
        or dict(Counter(row["planned_action"] for row in ledger))
        != registration["inventory"]["planned_actions"]
    ):
        raise ValueError("Incomplete, duplicate or inconsistent census date accounting")
    reports, cases, published = [], [], 0
    for member, item in zip(ledger, journal, strict=True):
        day, planned, status = member["utc_date"], member["planned_action"], item["status"]
        role = cohort.partition(day)
        if role != member["partition"]:
            raise ValueError("Census source-session partition differs from calendar")
        if role != "development":
            if planned != "reserved_metadata_only" or item != {
                "utc_date": day,
                "status": "reserved_metadata_only",
                "raw_opened": False,
            }:
                raise ValueError("Reserved census date has outcome access")
            continue  # Do not construct or open a reserved artifact path.
        if planned == "vendor_degraded_no_replay":
            if member["condition"] == "available" or item != {
                "utc_date": day,
                "status": planned,
                "raw_opened": False,
            }:
                raise ValueError("Degraded date accounting differs")
            continue
        expected_action = (
            "reconstruction_only"
            if cohort.iso_day(day).weekday() >= 5
            else ("decision_window_replay")
        )
        if (
            planned != expected_action
            or member["condition"] != "available"
            or member["contract"] != census.dated_contract(day)
        ):
            raise ValueError("Development date differs from declared replay scope")
        attempt_path = directory / "attempts" / f"{day}.json"
        attempt = pinned(attempt_path, common.hash_file(attempt_path, MAX_METADATA_BYTES))
        if any(
            attempt[key] != value
            for key, value in {
                "utc_date": day,
                "contract": member["contract"],
                "registration_sha256": registration_sha256,
                "source_sha256": member["sha256"],
                "exposure": "conservatively_exposed_before_raw_access",
            }.items()
        ):
            raise ValueError("Census attempt identity differs")
        if status == "quality_refused":
            failure_path = directory / "days" / f"{day}.failure.json"
            refusal = pinned(failure_path, common.hash_file(failure_path, MAX_METADATA_BYTES))
            if (
                refusal != item
                or item["source_sha256"] != member["sha256"]
                or item["automatic_retry"] is not False
                or item["raw_access_attempted"] is not True
            ):
                raise ValueError("Retained refusal evidence differs")
            continue
        if status != "replayed":
            raise ValueError("Unknown census terminal date status")
        report_path = directory / "days" / f"{day}.json"
        report = pinned(report_path, item["report_sha256"])
        if any(
            report[key] != value
            for key, value in {
                "status": "replayed",
                "utc_date": day,
                "contract": member["contract"],
                "registration_sha256": registration_sha256,
                "source_sha256": member["sha256"],
                "rows": item["rows"],
                "cases": item["cases"],
                "full_member_hash_verified": True,
                "training_eligible": False,
                "promotion_enabled": False,
            }.items()
        ):
            raise ValueError("Published report identity or counts differ")
        if (
            type(report["rows"]) is not int
            or not 0 <= report["rows"] <= 14_400
            or type(report["cases"]) is not int
            or not 0 <= report["cases"] <= MAX_CASES_PER_DAY
            or (planned == "reconstruction_only" and (report["rows"] or report["cases"]))
        ):
            raise ValueError("Invalid decision or reconstruction counts")
        published += report_path.stat().st_size
        for kind in ("rows", "cases"):
            published += checked_hash(
                directory / "days" / f"{day}.{kind}.jsonl",
                report[f"{kind}_sha256"],
                census.MAX_DAY_BYTES,
            )
        day_cases = read_cases(directory / "days" / f"{day}.cases.jsonl", report)
        if report["summary"]["rows"] != report["rows"]:
            raise ValueError("Daily summary row count differs")
        if report["quality"]["receive_clock_v2"]["counts"].get("protected_disagreements", 0):
            raise ValueError("Protected clock disagreements in accepted report")
        reports.append(report)
        cases.extend(day_cases)
    if published != receipt["total_published_bytes"]:
        raise ValueError("Published census byte accounting differs")
    # Recheck metadata after potentially lengthy artifact reads.
    pinned(directory / "completion.json", receipt_sha256)
    pinned(registration_path, registration_sha256)
    checked_hash(directory / "progress.jsonl", receipt["progress_sha256"], MAX_METADATA_BYTES)
    return receipt, reports, cases


def horizon_counts(cases: list[dict]) -> dict:
    result = {}
    for horizon in census.paths.HORIZONS:
        entered = [r["path_horizons"][str(horizon)] for r in cases if r["path_horizons"]]
        resolved = [h for h in entered if h["status"] == "resolved"]
        clean = [h for h in resolved if not h["late_exit"] and not h["inactivity_exposed"]]
        result[str(horizon)] = {
            "attempts": len(cases),
            "entered": len(entered),
            "resolved": len(resolved),
            "unavailable": len(cases) - len(resolved),
            "clean_resolved": len(clean),
            "late_resolved": sum(h["late_exit"] for h in resolved),
            "inactivity_exposed_entered": sum(h["inactivity_exposed"] for h in entered),
            "positive_direction_in_hindsight": {
                str(cost): {
                    "all_resolved": sum(max(h["gross_long_short_ticks"]) > cost for h in resolved),
                    "clean_resolved": sum(max(h["gross_long_short_ticks"]) > cost for h in clean),
                }
                for cost in census.study.diagnostics.EXTRA_COSTS
            },
        }
    return result


def daily_associations(cases: list[dict]) -> dict:
    resolved = [r for r in cases if r["outcome"]["status"] == "resolved"]
    directional = [
        r
        for r in resolved
        if r["net_targets_long_short_ticks"][0] != r["net_targets_long_short_ticks"][1]
    ]
    populations = {
        "any_positive_15s_direction": (
            resolved,
            [int(r["hindsight_action"] in (-1, 1)) for r in resolved],
        ),
        "long_better_than_short_15s": (
            directional,
            [
                int(r["net_targets_long_short_ticks"][0] > r["net_targets_long_short_ticks"][1])
                for r in directional
            ],
        ),
    }
    result = {}
    for name, (rows, target) in populations.items():
        positive, negative = sum(target), len(target) - sum(target)
        result[name] = {
            "observations": len(target),
            "positive_class": positive,
            "negative_class": negative,
            "excluded_resolved_ties": len(resolved) - len(rows),
            "meets_descriptive_support": min(positive, negative) >= MIN_CLASS_SUPPORT,
            "feature_auc": {
                key: census.study.diagnostics.auc(
                    target,
                    [({**r["features"], **r["execution_features"]})[key] for r in rows],
                )
                for key in FEATURES
            },
        }
    return result


def auc_distribution(values: list[float]) -> dict:
    return {
        "supported_dates": len(values),
        "p10_median_p90": np.quantile(values, [0.1, 0.5, 0.9]).tolist() if values else None,
        "dates_above_half": sum(v > 0.5 for v in values),
        "dates_below_half": sum(v < 0.5 for v in values),
    }


def describe(receipt: dict, reports: list[dict], cases: list[dict]) -> dict:
    by_day, by_month, by_hour = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in cases:
        by_day[row["source_session"]].append(row)
        by_month[row["source_session"][:7]].append(row)
        hour = datetime.fromtimestamp(row["decision_ts_ns"] // 10**9, UTC).hour
        by_hour[str(hour)].append(row)
    association_days = {day: daily_associations(rows) for day, rows in sorted(by_day.items())}
    feature_summary = {}
    for population in ("any_positive_15s_direction", "long_better_than_short_15s"):
        feature_summary[population] = {}
        for feature in FEATURES:
            supported = {
                day: a[population]["feature_auc"][feature]
                for day, a in association_days.items()
                if a[population]["meets_descriptive_support"]
            }
            feature_summary[population][feature] = {
                **auc_distribution(list(supported.values())),
                "by_month": {
                    month: auc_distribution(
                        [v for d, v in supported.items() if d.startswith(month)]
                    )
                    for month in sorted(by_month)
                },
            }
    refusals = [
        {
            **r,
            "category": refusal_category(r["error"]),
            "weekday": cohort.iso_day(r["utc_date"]).strftime("%A"),
        }
        for r in receipt["dates"]
        if r["status"] == "quality_refused"
    ]
    support = {}
    for feature in FEATURES:
        values = [({**r["features"], **r["execution_features"]})[feature] for r in cases]
        support[feature] = {
            "observations": len(values),
            "nonzero_observations": sum(v != 0 for v in values),
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
        }
    return {
        "coverage": {
            "all_inventory_dates": len(receipt["dates"]),
            "terminal_counts": receipt["counts"],
            "weekday_decision_dates": sum(r["rows"] > 0 for r in reports),
            "reconstruction_only_dates": sum(r["rows"] == 0 for r in reports),
            "decision_rows": sum(r["rows"] for r in reports),
            "sampled_cases": len(cases),
            "decision_window_utc": "12:00-16:00",
            "all_hours_analyzed": False,
            "by_month": {
                month: {
                    "terminal_counts": dict(
                        Counter(
                            r["status"] for r in receipt["dates"] if r["utc_date"].startswith(month)
                        )
                    ),
                    "decision_dates": sum(
                        r["rows"] > 0 for r in reports if r["utc_date"].startswith(month)
                    ),
                    "sampled_cases": len(by_month.get(month, [])),
                }
                for month in sorted({r["utc_date"][:7] for r in receipt["dates"]})
            },
        },
        "quality_refusals": refusals,
        "refusal_categories": dict(Counter(r["category"] for r in refusals)),
        "hindsight_horizons": horizon_counts(cases),
        "hindsight_horizons_by_month": {
            month: horizon_counts(rows) for month, rows in sorted(by_month.items())
        },
        "hindsight_horizons_by_utc_hour": {
            hour: horizon_counts(rows) for hour, rows in sorted(by_hour.items())
        },
        "daily_associations": association_days,
        "equal_date_weight_feature_associations": feature_summary,
        "feature_observation_support": support,
    }


def run(
    *,
    root: Path,
    directory: Path,
    registration_path: Path,
    registration_sha256: str,
    receipt_sha256: str,
    output: Path,
) -> dict:
    if output.exists() or not output.resolve().is_relative_to((root / "data/processed").resolve()):
        raise ValueError("Review output must be new and inside processed data")
    implementation = {
        **census.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }
    receipt, reports, cases = verify_census(
        directory, registration_path, registration_sha256, receipt_sha256
    )
    result = {
        "artifact_type": "6e_development_census_review_v1",
        "mode": "offline_research_only",
        "status": "verified_descriptive_review_not_strategy_validated",
        "registration_sha256": registration_sha256,
        "receipt_sha256": receipt_sha256,
        "progress_sha256": receipt["progress_sha256"],
        "review_source_sha256": common.hash_file(Path(__file__), 1024**2),
        "review_implementation_sha256": implementation,
        "minimum_per_class_daily_auc_support": MIN_CLASS_SUPPORT,
        "source_census_finished": receipt["finished_utc"],
        "reviewed_utc": datetime.now(UTC).isoformat(),
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "reserved_outcomes_opened": False,
        "raw_archives_opened": False,
        "strategy_aggregate_permitted": False,
        **describe(receipt, reports, cases),
        "limitations": [
            "Coverage includes every date, with refusals retained; successful dates are a subset.",
            "All inspected outcomes are exposed development evidence, not independent validation.",
            "Hindsight counts do not predict direction or achievable trade profit.",
            "Long-better-than-short includes losing entries and excludes exact direction ties.",
            "Clean path subsets use future availability; they are not causal entry filters.",
            "Daily AUCs keep feature orientation; no sign reversal or threshold fitting.",
            "Thirty-seven feature comparisons are exploratory and unadjusted for multiple testing.",
            "Futures quotes do not model cTrader spot spreads, basis, commissions or execution.",
            "Quality-flag messages do not identify the exact flag or prove its upstream cause.",
        ],
    }
    if implementation != {
        **census.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }:
        raise ValueError("Review implementation changed during verification")
    common._write_new(output, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--census-directory", type=Path, required=True)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--registration-sha256", required=True)
    parser.add_argument("--receipt-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        root=args.project_root,
        directory=args.census_directory,
        registration_path=args.registration,
        registration_sha256=args.registration_sha256,
        receipt_sha256=args.receipt_sha256,
        output=args.output,
    )
    print(common.canonical({"status": result["status"], **result["coverage"]}).decode())


if __name__ == "__main__":
    main()
