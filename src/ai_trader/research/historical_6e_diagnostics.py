"""Descriptive historical-only diagnostics on already-exposed 6E research rows.

No fitting, archive replay, download, platform access or strategy promotion.
All comparisons are exploratory, including later dates; none is a fresh test.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_microdepth as data
from ai_trader.training import train_6e_cost_baseline as baseline
from ai_trader.training import train_6e_opportunity as common

INTAKE = "data/processed/databento_6e_18_month_intake_20261001_2.json"
INTAKE_PIN = "de12f9833b951781f27b5ea46d2c6dc2302c422e1080bfc48914b2dc8a82b27a"
CLASSIFIER = "data/processed/6e_opportunity_development_20261001_1_report.json"
CLASSIFIER_PIN = "465be3e1146086016aa82d8ab9d4b91046aaf803b25b0769a2cd354fff3b53ac"
EARLY = common.TRAIN
LATER = tuple(s for s in data.SESSIONS if s not in EARLY)
RULE_FEATURES = (
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "depth5_imbalance",
    "mid_change_5s_ticks",
    "reload_difference",
    "absorption_difference",
)
EXTRA_COSTS = (0, 1, 2, 4)


def pinned_json(path: Path, expected: str) -> dict:
    if common.hash_file(path, 1024 * 1024) != expected:
        raise ValueError("Pinned report differs")
    return common.loads(path.read_bytes())


def load_rows(path: Path) -> list[dict]:
    if common.hash_file(path, common.MAX_BYTES) != common.ROWS_SHA256:
        raise ValueError("Pinned rows differ")
    rows, pin = [], hashlib.sha256()
    with path.open("rb") as source:
        while raw := source.readline(common.MAX_LINE + 1):
            if len(raw) > common.MAX_LINE or not raw.endswith(b"\n"):
                raise ValueError("Invalid bounded JSONL line")
            rows.append(common.loads(raw))
            pin.update(raw)
            if len(rows) > common.MAX_ROWS:
                raise ValueError("Too many rows")
    if pin.hexdigest() != common.ROWS_SHA256:
        raise ValueError("Rows changed during intake")
    baseline.validate_rows(rows, sessions=data.SESSIONS, feature_names=data.FEATURES)
    return rows


def distribution(values) -> dict | None:
    a = np.asarray(values, dtype=float)
    if not len(a):
        return None
    if not np.isfinite(a).all():
        raise ValueError("Nonfinite diagnostic values")
    return {
        "count": len(a),
        "mean": float(a.mean()),
        "quantiles_min_p01_p10_p50_p90_p99_max": np.quantile(
            a, [0, 0.01, 0.1, 0.5, 0.9, 0.99, 1]
        ).tolist(),
        "positive_fraction": float((a > 0).mean()),
    }


def decomposition(row: dict) -> tuple[float, float]:
    o = row["outcome"]
    mid = (o["exit_bid_nano"] + o["exit_ask_nano"] - o["entry_bid_nano"] - o["entry_ask_nano"]) / (
        2 * data.clock.TICK
    )
    burden = (
        o["exit_ask_nano"] - o["exit_bid_nano"] + o["entry_ask_nano"] - o["entry_bid_nano"]
    ) / (2 * data.clock.TICK)
    if any(
        abs(a - b) > 1e-12
        for a, b in zip(
            [mid - burden - 1, -mid - burden - 1], row["net_targets_long_short_ticks"], strict=True
        )
    ):
        raise ValueError("Cost decomposition differs from targets")
    return mid, burden


def summarize(rows: list[dict]) -> dict:
    resolved = [r for r in rows if r["outcome"]["status"] == "resolved"]
    eligible = sum(r["eligible"] for r in rows)
    result = {
        "rows": len(rows),
        "eligible": eligible,
        "resolved": len(resolved),
        "unavailable_among_eligible": eligible - len(resolved),
        "statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "opportunity_fraction_resolved": None,
    }
    if not resolved:
        return result
    mid, burden = np.asarray([decomposition(r) for r in resolved]).T
    result.update(
        opportunity_fraction_resolved=float((abs(mid) - burden - 1 > 0).mean()),
        midpoint_change_ticks=distribution(mid),
        absolute_midpoint_change_ticks=distribution(abs(mid)),
        crossed_spread_burden_ticks=distribution(burden),
        holding_seconds=distribution(
            [(r["outcome"]["exit_ts_ns"] - r["outcome"]["entry_ts_ns"]) / 1e9 for r in resolved]
        ),
        inactivity_exposed=sum(r["outcome"].get("inactivity_exposed", False) for r in resolved),
        cost_sensitivity={
            str(cost): {
                "long_mean_ticks": float((mid - burden - cost).mean()),
                "short_mean_ticks": float((-mid - burden - cost).mean()),
                "hindsight_either_positive_fraction": float((abs(mid) - burden - cost > 0).mean()),
            }
            for cost in EXTRA_COSTS
        },
    )
    return result


def thin_causally(rows: list[dict], seconds: int = 60) -> list[dict]:
    """Eligible decision-time thinning only, before observing outcome availability."""
    if type(seconds) is not int or seconds <= 0:
        raise ValueError("Positive thinning interval required")
    selected, last = [], {}
    for row in rows:
        day, now = row["source_session"], row["decision_ts_ns"]
        if row["eligible"] and now >= last.get(day, 0) + seconds * 1_000_000_000:
            selected.append(row)
            last[day] = now
    return selected


def rule_directions(rows: list[dict], feature: str, sign: int) -> np.ndarray:
    if feature not in RULE_FEATURES or sign not in (-1, 1):
        raise ValueError("Unknown diagnostic rule")
    values = []
    for r in rows:
        f = r["features"]
        if feature == "reload_difference":
            value = f["normalized_bid_reload_5s"] - f["normalized_ask_reload_5s"]
        elif feature == "absorption_difference":
            value = f["sell_absorption_proxy_5s"] - f["buy_absorption_proxy_5s"]
        else:
            value = f[feature]
        values.append(value)
    return (np.sign(values) * sign).astype(int)


def summarize_rule(rows: list[dict], directions: np.ndarray) -> dict:
    if directions.shape != (len(rows),) or not np.isin(directions, [-1, 0, 1]).all():
        raise ValueError("Invalid causal directions")
    # These scores only adapt fixed directions to existing one-position/cooldown accounting.
    # They are not forecasts of net profit. Do not publish predicted_net_ticks from that adapter.
    scores = np.column_stack((directions == 1, directions == -1)).astype(float)
    result = baseline.policy(rows, scores)
    selections = result.pop("selections")
    resolved = [s for s in selections if s["status"] == "resolved"]
    index = {(r["source_session"], r["decision_ts_ns"]): r for r in rows}
    mids, burdens = [], []
    for selected in resolved:
        row = index[selected["source_session"], selected["decision_ts_ns"]]
        mid, burden = decomposition(row)
        mids.append(mid * selected["direction"])
        burdens.append(burden)
    days = []
    for session in dict.fromkeys(r["source_session"] for r in rows):
        closed = [s["net_ticks"] for s in resolved if s["source_session"] == session]
        days.append(
            {
                "source_session": session,
                "closed": len(closed),
                "mean_net_ticks": float(np.mean(closed)) if closed else None,
            }
        )
    daily_means = [d["mean_net_ticks"] for d in days if d["mean_net_ticks"] is not None]
    # Descriptive session-block uncertainty, not adjusted for these many comparisons.
    ci = None
    if len(daily_means) >= 3:
        rng = np.random.default_rng(20261001)
        draws = rng.choice(daily_means, (2000, len(daily_means))).mean(axis=1)
        ci = np.quantile(draws, [0.025, 0.975]).tolist()
    return {
        **result,
        "by_session": days,
        "closed_net_tick_distribution": distribution([s["net_ticks"] for s in resolved]),
        "mean_signed_midpoint_ticks": float(np.mean(mids)) if mids else None,
        "mean_spread_burden_ticks": float(np.mean(burdens)) if burdens else None,
        "daily_equal_weight_mean_ticks": float(np.mean(daily_means)) if daily_means else None,
        "descriptive_daily_bootstrap_95_interval": ci,
        "positive_net_days": sum(v > 0 for v in daily_means),
        "cost_sensitivity_mean_ticks": {
            str(c): float(np.mean([s["net_ticks"] + 1 - c for s in resolved])) if resolved else None
            for c in EXTRA_COSTS
        },
    }


def feature_bins(rows: list[dict]) -> dict:
    matrix = baseline.feature_matrix(rows, data.FEATURES)
    fit_mask = np.array([r["source_session"] in EARLY and r["eligible"] for r in rows])
    if not fit_mask.any():
        raise ValueError("No early eligible feature reference rows")
    result = {}
    for column, name in enumerate(data.FEATURES):
        cuts = np.unique(np.quantile(matrix[fit_mask, column], [0.2, 0.4, 0.6, 0.8]))
        bins = np.searchsorted(cuts, matrix[:, column], side="right")
        result[name] = {
            "cuts_from_early_eligible_features_only": cuts.tolist(),
            "partitions": {
                label: [
                    {
                        "bin": b,
                        **summarize(
                            [
                                row
                                for row, bucket in zip(rows, bins, strict=True)
                                if bucket == b and row["source_session"] in sessions
                            ]
                        ),
                    }
                    for b in range(len(cuts) + 1)
                ]
                for label, sessions in (("early_exposed", EARLY), ("later_exposed", LATER))
            },
        }
    return result


def auc(target, score) -> float | None:
    """Mann-Whitney binary AUC, average ranks for ties; no fitted threshold."""
    y, s = np.asarray(target), np.asarray(score, dtype=float)
    if (
        y.ndim != 1
        or s.shape != y.shape
        or not np.isin(y, [0, 1]).all()
        or not np.isfinite(s).all()
    ):
        raise ValueError("Invalid binary AUC input")
    positives = int(y.sum())
    negatives = len(y) - positives
    if not positives or not negatives:
        return None
    order = np.argsort(s, kind="stable")
    sorted_s = s[order]
    starts = np.r_[0, np.flatnonzero(np.diff(sorted_s)) + 1]
    ends = np.r_[starts[1:], len(y)]
    ranks = np.empty(len(y))
    for start, end in zip(starts, ends, strict=True):
        ranks[order[start:end]] = (start + 1 + end) / 2
    return float((ranks[y == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))


def classifier_diagnostic(rows: list[dict], report: dict) -> dict:
    model = common.OpportunityModel(**report["model"])
    if common.digest(report["model"]) != report["model_sha256"]:
        raise ValueError("Frozen model pin differs")
    # Exactly the original three development dates, not a new classifier evaluation cohort.
    chosen = [
        r
        for r in rows
        if r["source_session"] in common.DEVELOPMENT and r["outcome"]["status"] == "resolved"
    ]
    x = baseline.feature_matrix(chosen, data.FEATURES)
    p = model.predict(x)
    labels = np.array([r["hindsight_action"] for r in chosen])
    p_any = p[:, 0] + p[:, 2]
    any_positive = labels != 0
    p_long = p[any_positive, 2] / p_any[any_positive]
    long_label = labels[any_positive] == 1
    prior = report["training"]["prior_short_neither_long"]
    prior_any = prior[0] + prior[2]
    prior_long = prior[2] / prior_any

    def binary_loss(y, probability):
        return float(
            -np.mean(
                y * np.log(np.clip(probability, 1e-15, 1))
                + (1 - y) * np.log(np.clip(1 - probability, 1e-15, 1))
            )
        )

    return {
        "sessions": list(common.DEVELOPMENT),
        "resolved": len(chosen),
        "any_opportunity": {
            "prevalence": float(any_positive.mean()),
            "auc": auc(any_positive, p_any),
            "model_log_loss": binary_loss(any_positive, p_any),
            "prior_log_loss": binary_loss(any_positive, prior_any),
        },
        "direction_given_hindsight_opportunity": {
            "rows": int(any_positive.sum()),
            "long_fraction": float(long_label.mean()),
            "auc": auc(long_label, p_long),
            "model_log_loss": binary_loss(long_label, p_long),
            "prior_log_loss": binary_loss(long_label, prior_long),
            "accuracy_at_fixed_half": float(((p_long > 0.5) == long_label).mean()),
            "prior_accuracy_at_fixed_half": float(((prior_long > 0.5) == long_label).mean()),
            "warning": "Hindsight-conditioned diagnostic, not a deployable opportunity filter",
        },
    }


def inventory_summary(intake: dict) -> dict:
    daily = [f for batch in intake["batches"] for f in batch["files"] if "date" in f]
    if len({f["date"] for f in daily}) != len(daily):
        raise ValueError("Duplicate daily inventory date")
    return {
        "daily_files": len(daily),
        "archive_bytes": sum(b["archive_bytes"] for b in intake["batches"]),
        "months": {
            m: {
                "files": sum(f["date"].startswith(m) for f in daily),
                "degraded": [
                    f["date"]
                    for f in daily
                    if f["date"].startswith(m) and f["condition"] != "available"
                ],
            }
            for m in sorted({f["date"][:7] for f in daily})
        },
        "partial_symbol_headers": sum(bool(f["dbn_header"]["partial"]) for f in daily),
        "full_corpus_event_replay_performed": False,
        "scope": "Previously pinned inventory metadata only, not a new full archive verification",
    }


def analyze(rows: list[dict], classifier: dict) -> dict:
    partitions = {"all_exposed": data.SESSIONS, "early_exposed": EARLY, "later_exposed": LATER}
    rule_results = {}
    for feature in RULE_FEATURES:
        for sign, label in ((1, "follow"), (-1, "fade")):
            rule_results[f"{feature}_{label}"] = {}
            for name, sessions in partitions.items():
                selected = [r for r in rows if r["source_session"] in sessions]
                rule_results[f"{feature}_{label}"][name] = summarize_rule(
                    selected, rule_directions(selected, feature, sign)
                )
    for direction, label in ((1, "always_long"), (-1, "always_short")):
        rule_results[label] = {}
        for name, sessions in partitions.items():
            selected = [r for r in rows if r["source_session"] in sessions]
            rule_results[label][name] = summarize_rule(selected, np.full(len(selected), direction))
    return {
        "partitions": {
            n: summarize([r for r in rows if r["source_session"] in s])
            for n, s in partitions.items()
        },
        "by_session": [
            {"session": s, **summarize([r for r in rows if r["source_session"] == s])}
            for s in data.SESSIONS
        ],
        "by_utc_hour": {
            str(h): summarize([r for r in rows if r["decision_ts_ns"] // int(3.6e12) % 24 == h])
            for h in range(12, 16)
        },
        "causal_60s_thinning": summarize(thin_causally(rows)),
        "feature_quintile_diagnostics": feature_bins(rows),
        "fixed_rule_quote_counterfactuals": rule_results,
        "classifier_opportunity_vs_direction": classifier_diagnostic(rows, classifier),
        "comparison_disclosure": {
            "fixed_direction_rules": 16,
            "feature_families": len(data.FEATURES),
            "maximum_bins_per_feature": 5,
            "extra_cost_assumptions_ticks": list(EXTRA_COSTS),
            "all_dates_previously_exposed": True,
            "no_independent_test": True,
            "uncertainty": "2000 resamples of whole-day mean returns; descriptive, unadjusted",
            "no_new_model_fit_or_chosen_winner": True,
        },
        "promotion_enabled": False,
        "new_training": False,
        "trading_enabled": False,
    }


def run(root: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(output)
    paths = {
        INTAKE: INTAKE_PIN,
        CLASSIFIER: CLASSIFIER_PIN,
        common.ROWS_PATH: common.ROWS_SHA256,
        common.REPORT_PATH: common.REPORT_SHA256,
    }
    code_pins = {
        **common.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }
    intake = pinned_json(root / INTAKE, INTAKE_PIN)
    classifier = pinned_json(root / CLASSIFIER, CLASSIFIER_PIN)
    pinned_json(root / common.REPORT_PATH, common.REPORT_SHA256)
    rows = load_rows(root / common.ROWS_PATH)
    result = {
        "artifact_type": "historical_6e_exploratory_diagnostics_v1",
        "input_sha256": paths,
        "implementation_sha256": code_pins,
        "inventory": inventory_summary(intake),
        **analyze(rows, classifier),
    }
    if any(common.hash_file(root / p, common.MAX_BYTES) != pin for p, pin in paths.items()):
        raise ValueError("Input evidence changed during diagnostics")
    if code_pins != {
        **common.fingerprints(),
        Path(__file__).name: common.hash_file(Path(__file__), 1024**2),
    }:
        raise ValueError("Implementation changed during diagnostics")
    common._write_new(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.project_root, args.output)
    print(
        common.canonical(
            {
                k: result[k]
                for k in (
                    "partitions",
                    "classifier_opportunity_vs_direction",
                    "comparison_disclosure",
                )
            }
        ).decode()
    )
