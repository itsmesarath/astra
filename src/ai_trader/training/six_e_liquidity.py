"""Fixed causal liquidity rules and one CPU cost/availability candidate, never orders."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

import numpy as np

from ai_trader.research import databento_6e_execution_flow as flow
from ai_trader.training import historical_6e_manifest as data
from ai_trader.training.standardize import fit_standardizer, validate_feature_matrix

FEATURES = (*flow.data.FEATURES, *flow.FEATURES)
POLICIES = (
    "cvd_follow",
    "liquidity_follow",
    "absorption_fade",
    "cpu_cost",
    "cpu_cost_liquidity",
    "no_trade",
)
RIDGE, CLIP, AVAILABILITY, EDGE = 1.0, 10.0, 0.90, 0.5
SAMPLE_NS = 60_000_000_000
MAX_TRAIN_CASES = 30_000


def protocol() -> dict:
    return {
        "version": "six_e_liquidity_cost_cpu_v1",
        "features": list(FEATURES),
        "inputs": "Only the 23 original causal flow/depth fields and 14 execution proxies; "
        "no timestamps, contracts, source-session IDs, prices, future outcomes or labels",
        "liquidity": "Prior quote gap <=250ms; known aggressors exist; unknown count <=0.1; "
        "both top queues >=5 and visible five-level depths >=20; five-level spans <=8 "
        "ticks; >=20 completed quote events in preceding 5s",
        "follow": "Liquidity gate, >=20 known trades, preceding 5s midpoint range >=4 "
        "ticks, absolute midpoint change >=1 tick, OFI and CVD magnitudes >=0.5 "
        "aligned with midpoint change; no feature/threshold search",
        "fade": "Liquidity gate; >=20 known trades; absolute CVD >=0.5; midpoint "
        "change magnitude <=1 tick; passive held-top execution >=0.25 and other-ID "
        "reload >=0.1 on attacked side; fade aggressor direction only if visible "
        "queue imbalance also agrees with fade; proxies are not proof of icebergs",
        "controls": "Sign of known-trade CVD and idle; all policies separately scheduled",
        "cpu": {
            "algorithm": "One fixed ridge fit with unpenalized intercept; no Qwen, "
            "hyperparameter search, winner selection, class balancing or promotion",
            "ridge": RIDGE,
            "standardized_clip": CLIP,
            "sampling_seconds": SAMPLE_NS // 1_000_000_000,
            "max_train_cases": MAX_TRAIN_CASES,
            "standardization": "All causally sampled eligible train cases including unknowns",
            "availability_head": "Fit on every sampled train case; target is both directional "
            "bracket exits resolved; unknowns are zero availability, never zero returns",
            "economic_heads": "Two conditional net-tick heads on joint-resolved sampled "
            "train only, including losses and no-positive cases; missing-not-at-random "
            "coverage and conditional limitations must remain visible",
            "selection": "Both-resolved availability prediction >=0.90 and strictly "
            "unique maximum conditional net prediction >0.5 tick; unknown entered "
            "exits still block session; no future validity filter during evaluation",
            "availability_threshold": AVAILABILITY,
            "net_edge_threshold": EDGE,
        },
        "policies": list(POLICIES),
        "training_scope": "Named quarantined CPU research candidate only",
        "qwen_training": False,
        "promotion_allowed": False,
        "trading_enabled": False,
    }


def inputs(row: dict) -> tuple[dict, dict]:
    session = row["source_session"]
    data.role_for_day(session)  # Reserved guard before reading any feature.
    if row["partition"] != "development" or row["contract"] != data.census.dated_contract(session):
        raise ValueError("Liquidity input is not the declared dated development contract")
    now = row["decision_ts_ns"]
    start = int(datetime.fromisoformat(session).replace(tzinfo=UTC).timestamp()) * 1_000_000_000
    if (
        type(now) is not int
        or not start + 12 * 3600 * 1_000_000_000 <= now < start + 16 * 3600 * 1_000_000_000
    ):
        raise ValueError("Liquidity decision timestamp does not belong to its source session")
    f, e = row["features"], row["execution_features"]
    if set(f) != set(flow.data.FEATURES) or set(e) != set(flow.FEATURES):
        raise ValueError("Liquidity feature allowlist differs")
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in (*f.values(), *e.values())):
        raise ValueError("Liquidity inputs must be finite numerical causal features")
    if any(v < 0 for v in e.values()) or not 0 <= f["unknown_trade_fraction_5s"] <= 1:
        raise ValueError("Invalid execution proxy or aggressor fraction")
    if (
        any(v < 0 for k, v in f.items() if k.startswith("log_"))
        or any(not 0 <= f[k] <= 1 for k in ("bid_top_share5", "ask_top_share5"))
        or any(not -1 <= f[k] <= 1 for k in ("queue_imbalance", "depth5_imbalance"))
    ):
        raise ValueError("Invalid liquidity log, share or imbalance feature")
    nonnegative = (
        "bid_span5_ticks",
        "ask_span5_ticks",
        "mid_range_5s_ticks",
        "mid_travel_5s_ticks",
        "normalized_bid_reload_5s",
        "normalized_ask_reload_5s",
        "buy_absorption_proxy_5s",
        "sell_absorption_proxy_5s",
    )
    if any(f[k] < 0 for k in nonnegative):
        raise ValueError("Negative range, travel, span or replenishment proxy")
    return f, e


def matrix(rows: list[dict]) -> np.ndarray:
    values = []
    for row in rows:
        f, e = inputs(row)
        values.append([*(f[k] for k in flow.data.FEATURES), *(e[k] for k in flow.FEATURES)])
    return validate_feature_matrix(values)


def liquid(f: dict) -> bool:
    return (
        f["log_prior_quote_gap_ms"] <= math.log1p(250)
        and f["log_known_trades_5s"] > 0
        and f["unknown_trade_fraction_5s"] <= 0.1
        and min(f["log_bid_qty"], f["log_ask_qty"]) >= math.log1p(5)
        and min(f["log_bid_depth5"], f["log_ask_depth5"]) >= math.log1p(20)
        and max(f["bid_span5_ticks"], f["ask_span5_ticks"]) <= 8
        and f["log_quote_events_5s"] >= math.log1p(20)
    )


def sign(value: float) -> int:
    return int(value > 0) - int(value < 0)


def rules(rows: list[dict]) -> dict[str, np.ndarray]:
    if not rows:
        raise ValueError("Liquidity rules require a nonempty complete session")
    session, last = rows[0]["source_session"], None
    result = {n: np.zeros(len(rows), dtype=np.int8) for n in POLICIES[:3]}
    for i, row in enumerate(rows):
        f, e = inputs(row)
        now = row["decision_ts_ns"]
        if (
            row["source_session"] != session
            or type(now) is not int
            or (last is not None and now - last < 1_000_000_000)
        ):
            raise ValueError("Liquidity rules cannot mix or reorder decision sessions")
        last = now
        cvd, ofi, move = (
            sign(f["normalized_cvd_5s"]),
            sign(f["normalized_ofi_5s"]),
            sign(f["mid_change_5s_ticks"]),
        )
        result["cvd_follow"][i] = cvd if f["log_known_trades_5s"] > 0 else 0
        if not liquid(f) or f["log_known_trades_5s"] < math.log1p(20):
            continue
        if (
            cvd == ofi == move != 0
            and abs(f["normalized_cvd_5s"]) >= 0.5
            and abs(f["normalized_ofi_5s"]) >= 0.5
            and abs(f["mid_change_5s_ticks"]) >= 1
            and f["mid_range_5s_ticks"] >= 4
        ):
            result["liquidity_follow"][i] = cvd
        side = "ask" if cvd > 0 else "bid"
        if (
            cvd != 0
            and abs(f["normalized_cvd_5s"]) >= 0.5
            and abs(f["mid_change_5s_ticks"]) <= 1
            and e[f"{side}_held_top_passive_5s"] >= 0.25
            and e[f"{side}_other_id_reload_5s"] >= 0.1
            and sign(f["queue_imbalance"]) == -cvd
        ):
            result["absorption_fade"][i] = -cvd
    return result


def sample(rows: list[dict], labels: list[dict]) -> list[int]:
    if len(rows) != len(labels):
        raise ValueError("Liquidity sampling targets differ in length")
    if not rows or any(r["source_session"] != rows[0]["source_session"] for r in rows):
        raise ValueError("Sampling requires a single complete source session")
    indices, last = [], None
    for i, (row, label) in enumerate(zip(rows, labels, strict=True)):
        inputs(row)
        if (row["source_session"], row["decision_ts_ns"]) != (
            label["source_session"],
            label["decision_ts_ns"],
        ) or type(label["eligible"]) is not bool:
            raise ValueError("Liquidity sampling identity or eligibility differs")
        if label["eligible"] and (last is None or row["decision_ts_ns"] - last >= SAMPLE_NS):
            indices.append(i)
            last = row["decision_ts_ns"]
    return indices


@dataclass(frozen=True)
class Model:
    features: list[str]
    means: list[float]
    scales: list[float]
    weights: list[list[float]]
    bias: list[float]

    def predict(self, x: np.ndarray) -> np.ndarray:
        x = validate_feature_matrix(x)
        means, scales, weights, bias = map(
            np.asarray, (self.means, self.scales, self.weights, self.bias)
        )
        if (
            self.features != list(FEATURES)
            or x.shape[1] != len(FEATURES)
            or means.shape != (len(FEATURES),)
            or scales.shape != means.shape
            or weights.shape != (len(FEATURES), 3)
            or bias.shape != (3,)
            or not all(np.isfinite(a).all() for a in (means, scales, weights, bias))
            or np.any(scales <= 0)
        ):
            raise ValueError("Invalid frozen liquidity model feature/parameter shapes")
        prediction = np.clip((x - means) / scales, -CLIP, CLIP) @ weights + bias
        prediction[:, 0] = np.clip(prediction[:, 0], 0, 1)
        if not np.isfinite(prediction).all():
            raise ValueError("Nonfinite liquidity forecast")
        return prediction

    def payload(self) -> dict:
        return asdict(self)


def fit(rows: list[dict], labels: list[dict]) -> tuple[Model, dict]:
    if not rows or len(rows) != len(labels) or len(rows) > MAX_TRAIN_CASES:
        raise ValueError("Liquidity CPU fit requires bounded aligned training cases")
    if any(data.role_for_day(r["source_session"]) != "train" for r in rows):
        raise ValueError("Only complete train-session selected cases may fit the CPU candidate")
    if any(
        a["decision_ts_ns"] >= b["decision_ts_ns"] for a, b in zip(rows, rows[1:], strict=False)
    ) or any(
        a["source_session"] == b["source_session"]
        and b["decision_ts_ns"] - a["decision_ts_ns"] < SAMPLE_NS
        for a, b in zip(rows, rows[1:], strict=False)
    ):
        raise ValueError("CPU train cases must be unique and chronological")
    if any(
        (r["source_session"], r["contract"], r["partition"], r["decision_ts_ns"])
        != (y["source_session"], y["contract"], y["partition"], y["decision_ts_ns"])
        or y["eligible"] is not True
        for r, y in zip(rows, labels, strict=True)
    ):
        raise ValueError("CPU train-case target identity or causal eligibility differs")
    x = matrix(rows)
    scaler = fit_standardizer(x)
    design = np.column_stack((np.ones(len(x)), np.clip(scaler.transform(x), -CLIP, CLIP)))
    available = np.array(
        [
            all(y["outcomes"]["bracket_exit"][s]["status"] == "resolved" for s in ("long", "short"))
            for y in labels
        ]
    )
    if available.sum() < 10 or not np.any(~available):
        raise ValueError("CPU fit needs at least ten joint-resolved and one unknown train case")
    y = np.array(
        [
            [labels[i]["outcomes"]["bracket_exit"][s]["net_ticks"] for s in ("long", "short")]
            for i in np.flatnonzero(available)
        ],
        dtype=float,
    )
    if not np.isfinite(y).all():
        raise ValueError("Resolved CPU training targets must be finite")
    penalty = np.eye(design.shape[1]) * RIDGE
    penalty[0, 0] = 0
    availability = np.linalg.solve(
        design.T @ design / len(x) + penalty, design.T @ available / len(x)
    )
    known = design[available]
    economic = np.linalg.solve(known.T @ known / len(known) + penalty, known.T @ y / len(known))
    parameters = np.column_stack((availability, economic))
    model = Model(
        list(FEATURES),
        scaler.means.tolist(),
        scaler.scales.tolist(),
        parameters[1:].tolist(),
        parameters[0].tolist(),
    )
    model.predict(x)
    return model, {
        "train_cases": len(x),
        "joint_resolved": int(available.sum()),
        "unknown": int((~available).sum()),
        "sessions": len({r["source_session"] for r in rows}),
        "feature_count": len(FEATURES),
        "conditional_target_means": y.mean(axis=0).tolist(),
    }


def verify_fit(model: Model, rows: list[dict], labels: list[dict], accounting: dict) -> None:
    """Read-only normal-equation check: no solve, optimizer, refit or model worker."""
    if (
        not rows
        or len(rows) != len(labels)
        or len(rows) > MAX_TRAIN_CASES
        or any(data.role_for_day(r["source_session"]) != "train" for r in rows)
    ):
        raise ValueError("Model proof requires bounded train-only cases")
    x = matrix(rows)
    scaler = fit_standardizer(x)
    model.predict(x)
    if not np.array_equal(model.means, scaler.means) or not np.array_equal(
        model.scales, scaler.scales
    ):
        raise ValueError("CPU scaler does not match all causal train cases")
    design = np.column_stack((np.ones(len(x)), np.clip(scaler.transform(x), -CLIP, CLIP)))
    available = np.array(
        [
            all(y["outcomes"]["bracket_exit"][s]["status"] == "resolved" for s in ("long", "short"))
            for y in labels
        ]
    )
    y = np.array(
        [
            [labels[i]["outcomes"]["bracket_exit"][s]["net_ticks"] for s in ("long", "short")]
            for i in np.flatnonzero(available)
        ],
        dtype=float,
    )
    expected = {
        "train_cases": len(x),
        "joint_resolved": int(available.sum()),
        "unknown": int((~available).sum()),
        "sessions": len({r["source_session"] for r in rows}),
        "feature_count": len(FEATURES),
        "conditional_target_means": y.mean(axis=0).tolist(),
    }
    if accounting != expected:
        raise ValueError("CPU fit accounting differs from complete sampled train cases")
    penalty = np.eye(design.shape[1]) * RIDGE
    penalty[0, 0] = 0
    parameters = np.vstack((model.bias, model.weights))
    known = design[available]
    equations = ((design, available.astype(float), parameters[:, 0]), (known, y, parameters[:, 1:]))
    for a, b, parameters_head in equations:
        left = (a.T @ a / len(a) + penalty) @ parameters_head
        right = a.T @ b / len(a)
        if not np.allclose(left, right, rtol=1e-11, atol=1e-11):
            raise ValueError("CPU weights fail frozen train-only ridge normal equations")


def actions(prediction: np.ndarray) -> np.ndarray:
    if (
        prediction.ndim != 2
        or prediction.shape[1] != 3
        or not np.isfinite(prediction).all()
        or np.any((prediction[:, 0] < 0) | (prediction[:, 0] > 1))
    ):
        raise ValueError("Expected bounded availability and two conditional net predictions")
    available, long, short = prediction.T
    return np.where(
        (available >= AVAILABILITY) & (np.maximum(long, short) > EDGE) & (long != short),
        np.where(long > short, 1, -1),
        0,
    ).astype(np.int8)
