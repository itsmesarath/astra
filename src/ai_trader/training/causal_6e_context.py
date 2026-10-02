"""Bounded past-only context of observed feature snapshots, not raw volume totals."""

from __future__ import annotations

import math
from collections import deque
from datetime import UTC, datetime

import numpy as np

from ai_trader.training import train_6e_activity_direction as prior

data = prior.data
SECOND = 1_000_000_000
WINDOWS = (5, 15, 30)
RESET_GAP = 5 * SECOND
MAX_OBSERVATIONS = 64
DERIVED = ("passive_pressure", "held_support", "other_reload_support", "generic_reload_support")
HISTORY = (
    "queue_imbalance",
    "depth5_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "mid_change_5s_ticks",
    "log_quote_events_5s",
    *DERIVED,
)
FEATURES = (
    *prior.FEATURES,
    *DERIVED,
    "cvd_price_product",
    "cvd_held_support_product",
    *(
        name
        for window in WINDOWS
        for name in (
            *(f"past_mean_{key}_{window}s" for key in HISTORY),
            *(f"current_minus_past_mean_{key}_{window}s" for key in HISTORY),
            f"past_samples_{window}s",
            f"past_span_fraction_{window}s",
        )
    ),
)


def protocol() -> dict:
    return {
        "version": "causal_6e_context_v1",
        "features": list(FEATURES),
        "history_inputs": list(HISTORY),
        "lookback_seconds": list(WINDOWS),
        "interval": "Prior observed decisions in [now-window, now), inclusive lower boundary",
        "mean": "Observation-weighted feature-snapshot means, not time-weighted or volume sums",
        "change": "Current snapshot minus past snapshot mean; not a longer-window CVD",
        "padding": "Empty history mean is zero; sample count and span explicitly encode absence",
        "reset": "Fresh state per UTC source_session/contract; clear on decision gap >5s or "
        "current causal prior-quote-gap feature >5s; no cross-session history",
        "sampling": "Original receive-time decisions at least one second apart; no interpolation",
        "limits": {"observations_per_window": MAX_OBSERVATIONS},
        "forbidden_inputs": "Outcomes, future paths, targets, hindsight actions and eligibility",
        "proxy_semantics": "Reload/support are observable proxies, not confirmed iceberg labels",
    }


class CausalContext:
    def __init__(self, session: str, contract: str):
        data.role_for_day(session)  # Refuse reserved dates before any feature access.
        if contract != data.census.dated_contract(session):
            raise ValueError("Context contract differs from the dated source session")
        self.session, self.contract = session, contract
        self.last_ts = None
        self.history = {window: deque() for window in WINDOWS}
        self.totals = {window: np.zeros(len(HISTORY)) for window in WINDOWS}
        self.resets = 0

    def observe(self, row: dict) -> np.ndarray:
        if (
            row["source_session"] != self.session
            or row["contract"] != self.contract
            or row["partition"] != "development"
        ):
            raise ValueError("Context cannot mix source sessions, roles or contracts")
        now = row["decision_ts_ns"]
        if type(now) is not int:
            raise ValueError("Context timestamp must be integer nanoseconds")
        stamp = datetime.fromtimestamp(now // SECOND, UTC)
        if stamp.date().isoformat() != self.session or not 12 <= stamp.hour < 16:
            raise ValueError("Context decision is outside its declared window")
        if self.last_ts is not None and now - self.last_ts < SECOND:
            raise ValueError("Context decisions regress, duplicate or violate sampling interval")
        f, e = row["features"], row["execution_features"]
        if (
            set(f) != set(data.census.study.data.FEATURES)
            or set(e) != set(data.census.study.flow.FEATURES)
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in f.values())
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in e.values())
        ):
            raise ValueError("Context causal feature allowlist or values differ")
        derived = dict(
            zip(
                DERIVED,
                (
                    e["ask_passive_5s"] - e["bid_passive_5s"],
                    e["bid_held_top_passive_5s"] - e["ask_held_top_passive_5s"],
                    e["bid_other_id_reload_5s"] - e["ask_other_id_reload_5s"],
                    f["normalized_bid_reload_5s"] - f["normalized_ask_reload_5s"],
                ),
                strict=True,
            )
        )
        inputs = {**f, **e, **derived}
        current = np.array([inputs[key] for key in HISTORY], dtype=np.float64)
        values = [
            *(inputs[key] for key in (*prior.FEATURES, *DERIVED)),
            f["normalized_cvd_5s"] * f["mid_change_5s_ticks"],
            f["normalized_cvd_5s"] * derived["held_support"],
        ]
        reset = (self.last_ts is not None and now - self.last_ts > RESET_GAP) or f[
            "log_prior_quote_gap_ms"
        ] > math.log1p(RESET_GAP / 1_000_000)
        if reset:
            for window in WINDOWS:
                self.history[window].clear()
                self.totals[window].fill(0)
            self.resets += 1
        for window in WINDOWS:
            queue, total = self.history[window], self.totals[window]
            while queue and queue[0][0] < now - window * SECOND:
                _, old = queue.popleft()
                total -= old
            if len(queue) >= MAX_OBSERVATIONS:
                raise ValueError("Context observation bound exceeded")
            mean = total / len(queue) if queue else np.zeros(len(HISTORY))
            span = (now - queue[0][0]) / (window * SECOND) if queue else 0.0
            values.extend((*mean, *(current - mean), len(queue), span))
        result = np.asarray(values, dtype=np.float64)
        if result.shape != (len(FEATURES),) or not np.isfinite(result).all():
            raise ValueError("Nonfinite or misaligned causal context")
        # Publish the current vector only AFTER deriving all past-only windows.
        for window in WINDOWS:
            self.history[window].append((now, current))
            self.totals[window] += current
        self.last_ts = now
        return result


def transform(rows: list[dict]) -> tuple[np.ndarray, dict]:
    if not rows or len(rows) > 14_400:
        raise ValueError("Context requires a bounded complete source session")
    state = CausalContext(rows[0]["source_session"], rows[0]["contract"])
    matrix = np.stack([state.observe(row) for row in rows])
    return matrix, {
        "rows": len(rows),
        "causal_gap_resets": state.resets,
        "no_prior_30s_samples": int((matrix[:, FEATURES.index("past_samples_30s")] == 0).sum()),
        "incomplete_30s_span": int((matrix[:, FEATURES.index("past_span_fraction_30s")] < 1).sum()),
    }
