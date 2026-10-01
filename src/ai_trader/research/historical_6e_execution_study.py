"""Frozen, historical-only execution feature audit on exposed 6EU5 sessions."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_execution_flow as flow
from ai_trader.research import historical_6e_paths as paths

data, diagnostics, common = paths.data, paths.diagnostics, paths.common
SESSIONS = paths.SESSIONS
SIGNALS = (
    "queue",
    "cvd",
    "depth",
    "momentum",
    "generic_reload",
    "passive_flow",
    "held_passive_support",
    "same_id_refresh_support",
    "other_id_reload_support",
)


def protocol() -> dict:
    return {
        "artifact_type": "6e_execution_linked_protocol_v1",
        "sessions": list(SESSIONS),
        "source_days": list(paths.SOURCE_DAYS),
        "exposure": "All three days previously exposed; descriptive pilot, no holdout claims",
        "original_rows_sha256": common.ROWS_SHA256,
        "original_config_sha256": data.CONFIG_SHA256,
        "features": list(flow.FEATURES),
        "lookback_seconds": 5,
        "normalization": "Divide rolling quantity by current best bid plus ask size",
        "matching": "Consecutive T/F groups; known opposite passive side, equal trade/fill/book "
        "price, known resting ID; exclude aggressor IDs; matched fills cannot exceed T size",
        "decrease": "C/same-price M decrease linked once to earlier same-event F by ID/side/price; "
        "all other decreases are unlinked, not asserted cancellations",
        "reload": "FIFO credit from linked displayed decreases; continuous completed best price, "
        "inclusive five-second expiry; credit consumed once by later A/M increases",
        "held": "Passive volume at unchanged pre/post completed-event best price",
        "net_refresh": "Same-ID M after fill, same price, uninterrupted identity; min(executed, "
        "max(0, final display - max(0, display before first fill - executed))). Separate "
        "overlapping candidate, not confirmed iceberg or additional traded volume",
        "reset": "Reset temporal state on day, clear/snapshot or completed-quote gap >5s; "
        "exclude events spanning >5s from new features",
        "limits": {
            "event_records": flow.MAX_EVENT_RECORDS,
            "rolling_events": flow.MAX_ROLLING_EVENTS,
            "credits": flow.MAX_CREDITS,
        },
        "comparison": "Nine fixed orientations; no sign flip, tuning, fit or threshold search",
        "signals": list(SIGNALS),
        "outcome": "Original 100ms-entry, 15s-hold quotes minus one tick",
        "activity_control": "Terciles of log quote count fit on eligible July 7 features only",
        "price_control": "Sign of prior five-second midpoint change; nine activity/price strata",
        "conditional_auc": "Long versus short among cost-positive outcomes; disclose support; "
        "within-stratum comparisons require both directions and >=20 observations",
        "quote_policy": "Sign only, one position, original entry gates, 15s hold, 10s cooldown",
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def fingerprints() -> dict:
    return {
        **paths.fingerprints(),
        **{
            p.name: common.hash_file(p, 1024 * 1024)
            for p in (Path(paths.__file__), Path(flow.__file__), Path(__file__))
        },
    }


def prepare(path: Path) -> None:
    common._write_new(
        path,
        {
            "protocol": protocol(),
            "implementation_sha256": fingerprints(),
            "prepared_utc": datetime.now(UTC).isoformat(),
        },
    )


def registration(path: Path) -> tuple[dict, str]:
    pin = common.hash_file(path, 64 * 1024)
    raw = path.read_bytes()
    record = common.loads(raw)
    if (
        hashlib.sha256(raw).hexdigest() != pin
        or record.get("protocol") != protocol()
        or record.get("implementation_sha256") != fingerprints()
    ):
        raise ValueError("Frozen execution study registration changed")
    return record, pin


def signal(row: dict, name: str) -> float:
    f, e = row["features"], row["execution_features"]
    controls = {
        "queue": "queue_imbalance",
        "cvd": "normalized_cvd_5s",
        "depth": "depth5_imbalance",
        "momentum": "mid_change_5s_ticks",
    }
    if name in controls:
        return f[controls[name]]
    if name == "generic_reload":
        return f["normalized_bid_reload_5s"] - f["normalized_ask_reload_5s"]
    kinds = {
        "passive_flow": "passive",
        "held_passive_support": "held_top_passive",
        "same_id_refresh_support": "same_id_net_refresh",
        "other_id_reload_support": "other_id_reload",
    }
    if name not in kinds:
        raise ValueError("Unregistered execution signal")
    kind = kinds[name]
    value = e[f"bid_{kind}_5s"] - e[f"ask_{kind}_5s"]
    return -value if name == "passive_flow" else value


def audit_conservation(quality: list[dict]) -> None:
    for day in quality:
        a = day["audit_including_warmup"]
        if sum(a.get(f"{side}_passive_volume", 0) for side in ("A", "B")) != a.get(
            "fill_matched_passive_volume", 0
        ):
            raise ValueError("Passive fill accounting differs")
        for side in ("A", "B"):
            passive = a.get(f"{side}_passive_volume", 0)
            linked = a.get(f"{side}_linked_decrease_volume", 0)
            reload = sum(
                a.get(f"{side}_{kind}_volume", 0) for kind in ("same_id_reload", "other_id_reload")
            )
            if not (0 <= reload <= linked <= passive):
                raise ValueError("Execution credit conservation failed")
            if any(
                not 0 <= a.get(f"{side}_{kind}_volume", 0) <= passive
                for kind in ("held_top_passive", "same_id_net_refresh")
            ):
                raise ValueError("Execution candidate volume exceeds passive volume")


def summarize(rows: list[dict], cuts: np.ndarray) -> dict:
    eligible = [r for r in rows if r["eligible"]]
    positive = [r for r in eligible if r["hindsight_action"] in {-1, 1}]
    target = [int(r["hindsight_action"] == 1) for r in positive]
    strata = {}
    for row in positive:
        activity = int(np.searchsorted(cuts, row["features"]["log_quote_events_5s"], side="right"))
        price = int(np.sign(row["features"]["mid_change_5s_ticks"]))
        strata.setdefault((activity, price), []).append(row)
    comparison = {}
    for name in SIGNALS:
        scores = np.array([signal(r, name) for r in rows])
        eligible_scores = np.array([signal(r, name) for r in eligible])
        cvd_scores = np.array([signal(r, "cvd") for r in eligible])
        overlap = (eligible_scores != 0) & (cvd_scores != 0)
        # Adapter scores select a direction; these are not predicted profits.
        direction = np.sign(scores)
        policy = diagnostics.baseline.policy(rows, np.column_stack((direction > 0, direction < 0)))
        policy.pop("selections")
        groups, weighted, pairs = [], 0.0, 0
        for (activity, price), selected in sorted(strata.items()):
            y = [int(r["hindsight_action"] == 1) for r in selected]
            auc = diagnostics.auc(y, [signal(r, name) for r in selected])
            weight = sum(y) * (len(y) - sum(y))
            supported = len(y) >= 20 and auc is not None
            groups.append(
                {
                    "activity_bin": activity,
                    "prior_price_sign": price,
                    "observations": len(y),
                    "long": sum(y),
                    "short": len(y) - sum(y),
                    "auc": auc,
                    "included_in_pair_weighted_auc": supported,
                }
            )
            if supported:
                weighted += weight * auc
                pairs += weight
        comparison[name] = {
            "nonzero_eligible": sum(signal(r, name) != 0 for r in eligible),
            "both_score_and_cvd_nonzero": int(overlap.sum()),
            "same_sign_as_cvd_when_both_nonzero": float(
                (np.sign(eligible_scores[overlap]) == np.sign(cvd_scores[overlap])).mean()
            )
            if overlap.any()
            else None,
            "conditional_direction_auc": diagnostics.auc(
                target, [signal(r, name) for r in positive]
            ),
            "activity_price_strata": groups,
            "within_stratum_pair_weighted_auc": weighted / pairs if pairs else None,
            "within_stratum_positive_negative_pairs": pairs,
            "quote_policy": policy,
        }
    return {
        **diagnostics.summarize(rows),
        "conditional_direction_rows": len(positive),
        "feature_distributions_eligible": {
            key: diagnostics.distribution([r["execution_features"][key] for r in eligible])
            for key in flow.FEATURES
        },
        "comparison": comparison,
    }


def run(*, root: Path, registration_path: Path, rows_output: Path, report_output: Path) -> dict:
    if (
        rows_output.exists()
        or report_output.exists()
        or rows_output.resolve() == report_output.resolve()
    ):
        raise ValueError("Refusing to overwrite execution study evidence")
    frozen, pin = registration(registration_path)
    config, _ = data.load_config(root / paths.CONFIG)
    original = diagnostics.load_rows(root / common.ROWS_PATH)
    rows, evidence = data.base.build_targets(
        {**config, "source_sessions": list(SESSIONS)},
        root,
        builder=flow.ExecutionBuilder(SESSIONS),
        source_days=paths.SOURCE_DAYS,
    )
    reduced = [{k: v for k, v in row.items() if k != "execution_features"} for row in rows]
    paths.verify_original(reduced, original)
    del original, reduced
    audit_conservation(evidence["quality"]["execution_flow"])
    reference = [
        r["features"]["log_quote_events_5s"]
        for r in rows
        if r["eligible"] and r["source_session"] == SESSIONS[0]
    ]
    cuts = np.unique(np.quantile(reference, [1 / 3, 2 / 3]))
    raw = b"".join(common.canonical(r) + b"\n" for r in rows)
    report = {
        "artifact_type": "6e_execution_linked_study_v1",
        "mode": "offline_research_only",
        "registration_sha256": pin,
        **frozen,
        **evidence,
        "rows": len(rows),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "original_regression": "all_original_features_and_15s_targets_exact",
        "activity_cuts_from_july7_eligible_features": cuts.tolist(),
        "summary": summarize(rows, cuts),
        "by_session": {
            s: summarize([r for r in rows if r["source_session"] == s], cuts) for s in SESSIONS
        },
        "later_exposed_days": summarize(
            [r for r in rows if r["source_session"] != SESSIONS[0]], cuts
        ),
        "decision": "mechanics_and_exploratory_comparisons_only_no_promotion",
        "limitations": [
            "Three exposed dates, nine predeclared comparisons; no independent evaluation or fit.",
            "Fills with unknown trade side, missing IDs or changed prices remain unclassified.",
            "Unlinked decreases are not proven cancellations. Replenishment is not proven iceberg.",
            "Same-ID net refresh and explicit reload overlap; do not sum as hidden volume.",
            "Held best price is contemporaneous resistance, not demonstrated future edge.",
            "AUC uses hindsight-positive outcomes and correlated samples, not a causal entry gate.",
            "Activity/price strata are coarse controls, not causal identification or proven lift.",
            "Quote policies omit fills, impact and broker EURUSD costs; no platform is connected.",
        ],
    }
    if registration(registration_path)[1] != pin:
        raise ValueError("Registration changed during replay")
    if common.hash_file(root / common.ROWS_PATH, common.MAX_BYTES) != common.ROWS_SHA256:
        raise ValueError("Original rows changed during replay")
    data.clock._publish(rows_output, report_output, raw, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--rows-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.registration)
        print("Execution feature protocol frozen without opening market files.")
    else:
        if args.rows_output is None or args.report_output is None:
            parser.error("New rows and report paths required")
        result = run(
            root=args.project_root,
            registration_path=args.registration,
            rows_output=args.rows_output,
            report_output=args.report_output,
        )
        print(
            common.canonical({k: result[k] for k in ("decision", "rows", "rows_sha256")}).decode()
        )


if __name__ == "__main__":
    main()
