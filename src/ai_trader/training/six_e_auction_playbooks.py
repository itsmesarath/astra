"""Frozen sequential auction hypotheses; feature-only decisions, never an order router."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ai_trader.research import six_e_auction_features as tape
from ai_trader.training import study_6e_triggers as old

FAMILIES = ("failed_auction", "accepted_breakout", "defended_hold", "defended_failure")
EPISODE_SECONDS = 30
COOLDOWN_SECONDS = 30


def protocol() -> dict:
    return {
        "version": "six_e_auction_playbooks_v1",
        "episode_seconds": EPISODE_SECONDS,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "range": "Prior completed-quote 60s range, width 2..12 ticks; 60s warmup",
        "initiation": "Training q90 activity and absolute 5s normalized CVD; nonzero actual "
        "5s delta aligned with that CVD; unknown count and quantity fractions <=0.1",
        "confirmation": "Training q70 activity; nonzero aligned actual and normalized 5s CVD",
        "failed_auction": "One-tick outside attack; later return >=0.5 tick inside; later "
        "retest within one tick inside; later >=1 tick inside with opposite flow and "
        "opposite 5s mid progress. Invalidate at >=3 ticks outside",
        "accepted_breakout": "One-tick outside attack; later >=2 ticks progress, at least "
        "two subsequent outside decisions spanning >=2s; later retest 0..1 tick outside "
        "with weaker opposite CVD (<=half initial magnitude, activity <=initial); later "
        ">=1.5 ticks outside with resumed CVD, aligned OFI and 15s delta. "
        "Invalidate on >=0.5 tick return inside",
        "defended": "Attack within one tick of prior range boundary, abs(5s progress)<=1; "
        "training q90 positive aggression-side held-top passive credit and other-id reload. "
        "Freeze current midpoint as defended level; NOT a confirmed iceberg",
        "defended_hold": "Later >=1 tick against attack with opposite flow/progress; "
        "invalidate on >=1.5 ticks through defended level",
        "defended_failure": "Later >=2 ticks through defended level with resumed flow/OFI; "
        "invalidate on >=1.5 ticks against attack",
        "sequence": "Distinct decisions only, frozen initial levels; max episode 30s; "
        "independent family cooldown 30s after confirmation, invalidation or expiry",
        "quality": "Fresh state per source session and dated contract; clear pending state "
        "on >5s decision/quote gap, missing range readiness or excess unknown count/quantity",
        "controls": "Same-event CVD and queue directions for each family plus original burst "
        "follow and idle; no best-rule selection or parameter search",
        "targets_used_for_calibration": False,
        "prediction_is_expected_profit": False,
        "promotion_allowed": False,
        "trading_enabled": False,
    }


def calibrate(samples: list[dict]) -> dict:
    bundle = old.calibrate(samples)  # Validates causal allowlist, early role and ordering.
    bundle["confirmation_activity"] = float(
        np.quantile([r["features"]["log_known_trades_5s"] for r in samples], 0.7, method="linear")
    )
    return bundle


def validate_bundle(bundle: dict) -> None:
    c = bundle["cutoffs"]
    if set(c) != set(old.CALIBRATION_KEYS) or bundle["targets_used"] is not False:
        raise ValueError("Auction thresholds require the frozen feature-only calibration")
    for key, value in {**c, "confirmation_activity": bundle["confirmation_activity"]}.items():
        if key == "held_passive" and value is None:
            continue
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid auction threshold")
    if bundle["confirmation_activity"] > c["activity"]:
        raise ValueError("Confirmation threshold exceeds initiation threshold")


def inputs(row: dict, session: str, contract: str) -> tuple[dict, dict, dict]:
    f, e = old.causal_inputs(row, session, contract)
    g = row["auction_features"]
    if set(g) != set(tape.FEATURES) or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in g.values()
    ):
        raise ValueError("Auction feature allowlist or finite values differ")
    integer_keys = (
        "bid_nano",
        "ask_nano",
        "prior_low_nano2",
        "prior_high_nano2",
        "range_ready",
        "prior_quote_count",
        "diagonal_pairs_5s",
        "segment_vwap_qty",
        "segment_vwap_start_ns",
        *(f"{key}_{w}s" for w in tape.WINDOWS for key in tape.TAPE_FIELDS[:-1]),
    )
    if any(type(g[k]) is not int for k in integer_keys):
        raise ValueError("Auction native counts and prices require integers")
    if (
        g["bid_nano"] <= 0
        or g["ask_nano"] <= g["bid_nano"]
        or g["bid_nano"] % tape.TICK
        or g["ask_nano"] % tape.TICK
        or g["prior_low_nano2"] <= 0
        or g["prior_high_nano2"] < g["prior_low_nano2"]
        or g["prior_range_ticks"]
        != (g["prior_high_nano2"] - g["prior_low_nano2"]) / (2 * tape.TICK)
        or g["range_ready"] not in (0, 1)
        or g["prior_quote_count"] < 0
        or not 0 <= g["range_age_seconds"] <= tape.RANGE_SECONDS
        or (g["range_ready"] and (g["range_age_seconds"] != 60 or g["prior_quote_count"] < 2))
        or g["segment_vwap_qty"] < 0
        or g["segment_vwap_start_ns"] < 0
        or g["segment_vwap_start_ns"] > row["decision_ts_ns"]
        or g["segment_vwap_nano"] < 0
        or g["executed_span_5s_ticks"] < 0
        or g["diagonal_pairs_5s"] < 0
        or any(not 0 <= g[k] <= 1 for k in ("diagonal_buy_max_5s", "diagonal_sell_max_5s"))
    ):
        raise ValueError("Invalid auction price, range, footprint or VWAP context")
    for window in tape.WINDOWS:
        b, s, u, delta, count, frac = (g[f"{k}_{window}s"] for k in tape.TAPE_FIELDS)
        if (
            min(b, s, u, count) < 0
            or delta != b - s
            or frac != (u / (b + s + u) if b + s + u else 0)
        ):
            raise ValueError("Auction tape accounting differs")
    return f, e, g


def sign(value: float) -> int:
    return int(value > 0) - int(value < 0)


@dataclass
class Episode:
    start: int
    direction: int
    level: int  # Twice native midpoint; no floating price comparisons.
    activity: float
    cvd: float
    stage: int = 0
    outside: int = 0


class State:
    def __init__(self, session: str, contract: str, bundle: dict):
        old.data.role_for_day(session)
        if contract != old.data.census.dated_contract(session):
            raise ValueError("Auction contract differs from dated session")
        validate_bundle(bundle)
        self.session, self.contract, self.bundle = session, contract, bundle
        self.pending: dict[str, Episode] = {}
        self.cooldown: dict[str, int] = {}
        self.last = None
        self.audit = Counter()

    def observe(self, row: dict) -> dict[str, int]:
        f, e, g = inputs(row, self.session, self.contract)
        now = row["decision_ts_ns"]
        if self.last is not None and now <= self.last:
            raise ValueError("Auction decisions must be unique and chronological")
        gap = (self.last is not None and now - self.last > 5 * tape.SECOND) or (
            f["log_prior_quote_gap_ms"] > math.log1p(5000)
        )
        self.last = now
        result = dict.fromkeys(FAMILIES, 0)
        quality = (
            g["range_ready"]
            and f["unknown_trade_fraction_5s"] <= 0.1
            and all(g[f"unknown_fraction_qty_{w}s"] <= 0.1 for w in tape.WINDOWS)
        )
        if gap or not quality:
            self.audit["quality_reset"] += 1
            self.pending.clear()
            self.cooldown.clear()
            return result
        direction = sign(f["normalized_cvd_5s"])
        flow = direction != 0 and direction == sign(g["delta_qty_5s"])
        active = f["log_known_trades_5s"] > 0
        burst = (
            flow
            and active
            and f["log_known_trades_5s"] >= self.bundle["cutoffs"]["activity"]
            and (abs(f["normalized_cvd_5s"]) >= self.bundle["cutoffs"]["absolute_cvd"])
        )
        confirm = (
            flow and active and (f["log_known_trades_5s"] >= self.bundle["confirmation_activity"])
        )
        mid2 = g["bid_nano"] + g["ask_nano"]
        for family in FAMILIES:
            episode = self.pending.get(family)
            if episode is not None:
                dist = episode.direction * (mid2 - episode.level) / (2 * tape.TICK)
                expired = now - episode.start > EPISODE_SECONDS * tape.SECOND
                invalid = (
                    dist >= 3
                    if family == "failed_auction"
                    else dist <= -0.5
                    if family == "accepted_breakout"
                    else dist >= 1.5
                    if family == "defended_hold"
                    else dist <= -1.5
                )
                if expired or invalid:
                    self._close(family, now, "expired" if expired else "invalidated")
                    continue
                emitted = 0
                if family == "failed_auction":
                    if episode.stage == 0 and dist <= -0.5:
                        episode.stage = 1
                    elif episode.stage == 1 and -1 <= dist <= 0:
                        episode.stage = 2
                    elif (
                        episode.stage == 2
                        and dist <= -1
                        and confirm
                        and (
                            direction == -episode.direction
                            and direction * f["mid_change_5s_ticks"] > 0
                        )
                    ):
                        emitted = -episode.direction
                elif family == "accepted_breakout":
                    episode.outside += int(dist > 0)
                    if (
                        episode.stage == 0
                        and dist >= 2
                        and episode.outside >= 2
                        and (now - episode.start >= 2 * tape.SECOND)
                    ):
                        episode.stage = 1
                    elif (
                        episode.stage == 1
                        and 0 <= dist <= 1
                        and flow
                        and (
                            direction == -episode.direction
                            and abs(f["normalized_cvd_5s"]) <= episode.cvd / 2
                            and f["log_known_trades_5s"] <= episode.activity
                        )
                    ):
                        episode.stage = 2
                    elif (
                        episode.stage == 2
                        and dist >= 1.5
                        and confirm
                        and (
                            direction == episode.direction
                            and direction * f["normalized_ofi_5s"] > 0
                            and direction * g["delta_qty_15s"] > 0
                        )
                    ):
                        emitted = episode.direction
                elif (
                    family == "defended_hold"
                    and dist <= -1
                    and confirm
                    and (
                        direction == -episode.direction and direction * f["mid_change_5s_ticks"] > 0
                    )
                ):
                    emitted = -episode.direction
                elif (
                    family == "defended_failure"
                    and dist >= 2
                    and confirm
                    and (direction == episode.direction and direction * f["normalized_ofi_5s"] > 0)
                ):
                    emitted = episode.direction
                if emitted:
                    result[family] = emitted
                    self._close(family, now, "confirmed")
                continue  # Never re-arm or confirm on the same decision.
            if (
                now < self.cooldown.get(family, 0)
                or not burst
                or not 2 <= g["prior_range_ticks"] <= 12
            ):
                continue
            edge = g["prior_high_nano2"] if direction > 0 else g["prior_low_nano2"]
            distance = direction * (mid2 - edge) / (2 * tape.TICK)
            if family in {"failed_auction", "accepted_breakout"}:
                arm = distance >= 1
                level = edge
            else:
                side = "ask" if direction > 0 else "bid"
                cutoff = self.bundle["cutoffs"]["held_passive"]
                arm = (
                    abs(distance) <= 1
                    and abs(f["mid_change_5s_ticks"]) <= 1
                    and (
                        cutoff is not None
                        and e[f"{side}_held_top_passive_5s"] > 0
                        and e[f"{side}_held_top_passive_5s"] >= cutoff
                        and e[f"{side}_other_id_reload_5s"] > 0
                    )
                )
                level = mid2
            if arm:
                self.pending[family] = Episode(
                    now, direction, level, f["log_known_trades_5s"], abs(f["normalized_cvd_5s"])
                )
                self.audit[f"{family}_armed"] += 1
        return result

    def _close(self, family: str, now: int, reason: str) -> None:
        del self.pending[family]
        self.cooldown[family] = now + COOLDOWN_SECONDS * tape.SECOND
        self.audit[f"{family}_{reason}"] += 1


def directions(rows: list[dict], bundle: dict) -> tuple[dict, dict]:
    if not rows:
        raise ValueError("Auction study requires a complete nonempty session")
    state = State(rows[0]["source_session"], rows[0]["contract"], bundle)
    result = {name: np.zeros(len(rows), dtype=np.int8) for name in FAMILIES}
    for index, row in enumerate(rows):
        for name, direction in state.observe(row).items():
            result[name][index] = direction
    for name in state.pending:
        state.audit[f"{name}_pending_at_end"] += 1
    return result, dict(state.audit)
