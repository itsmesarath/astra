"""Frozen sequential range rules using completed-event evidence, never past fills."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from ai_trader.research import six_e_crossing_events as events
from ai_trader.training import six_e_auction_playbooks as v1

FAMILIES = ("failed_auction", "accepted_breakout")
MODES = ("event", "price_only")
POLICIES = (
    *(f"{mode}_{family}" for mode in MODES for family in FAMILIES),
    *(f"event_{family}_queue" for family in FAMILIES),
    *(f"snapshot_{family}" for family in FAMILIES),
    "crossing_follow",
    "burst_follow",
    "no_trade",
)


def protocol() -> dict:
    return {
        "version": "six_e_crossing_playbooks_v1",
        "parent_sequences": v1.protocol(),
        "evidence": events.protocol(),
        "scope": "Only the two range families; defended-level rules remain unchanged in V1",
        "arming": "First native-order delivered marker matching initiation gates per idle "
        "family; frozen event level/activity/CVD; episode expiry starts at event completion, "
        "not delayed publication; confirmation only on a later decision",
        "initiation": "Unchanged early q90 activity/CVD; direction aligned at completed attack; "
        "unknown count/quantity <=0.1 at attack and current decision",
        "price_only": "Same marker-quality, sequence and confirmation gates but remove ONLY "
        "initiation q90 activity/CVD gates; first native-order eligible marker, no winner choice",
        "state": "Original 30s expiry/cooldown and confirmation thresholds; resets on "
        "current quality/gap/segment loss; stale markers >5s cannot arm; no reusing marker IDs",
        "controls": "Unchanged current-snapshot V1 branches; same-confirmation-time queue; "
        "first qualifying crossing follow at PUBLICATION, not attack time; original burst/idle",
        "causal_interpretation": "Ablations are descriptive; different entry times/support "
        "do not establish price-context causation or a profitable effect",
        "policy_names": list(POLICIES),
        "calibration_changed": False,
        "model_training": False,
        "promotion_allowed": False,
        "trading_enabled": False,
    }


def qualified(marker: dict, bundle: dict, burst: bool) -> bool:
    known, unknown = marker["known_trades"], marker["unknown_trades"]
    total = known + unknown
    quality = (unknown / total if total else 0.0) <= 0.1 and all(
        marker[f"unknown_fraction_qty_{w}s"] <= 0.1 for w in events.tape.WINDOWS
    )
    if not quality or not burst:
        return quality
    return (
        known > 0
        and marker["activity"] >= bundle["cutoffs"]["activity"]
        and abs(marker["normalized_cvd"]) >= bundle["cutoffs"]["absolute_cvd"]
        and v1.sign(marker["normalized_cvd"]) == marker["direction"]
        and v1.sign(marker["delta_qty"]) == marker["direction"]
    )


class State:
    def __init__(self, session: str, contract: str, bundle: dict, *, burst: bool):
        v1.old.data.role_for_day(session)
        if contract != v1.old.data.census.dated_contract(session):
            raise ValueError("Crossing policy cannot mix dated contracts")
        v1.validate_bundle(bundle)
        self.session, self.contract, self.bundle, self.burst = session, contract, bundle, burst
        self.pending: dict[str, v1.Episode] = {}
        self.cooldown: dict[str, int] = {}
        self.last = None
        self.ordinal = self.segment = self.marker_id = 0
        self.audit = Counter()

    def observe(self, row: dict) -> dict:
        f, _, g = v1.inputs(row, self.session, self.contract)
        now, packet = row["decision_ts_ns"], row["crossing_evidence"]
        events.validate_packet(packet, now, self.session)
        if (
            packet["previous_publication_ts_ns"] != (self.last or 0)
            or packet["previous_publication_ordinal"] != self.ordinal
            or packet["segment"] < self.segment
            or (self.last is not None and now <= self.last)
        ):
            raise ValueError("Crossing publication chain or decision order differs")
        for marker in packet["markers"]:
            if marker["id"] <= self.marker_id:
                raise ValueError("Crossing marker cannot be delivered twice")
            self.marker_id = marker["id"]
        gap = (self.last is not None and now - self.last > 5 * events.tape.SECOND) or (
            f["log_prior_quote_gap_ms"] > math.log1p(5000)
        )
        reset = self.segment not in (0, packet["segment"])
        self.last, self.ordinal, self.segment = now, packet["ordinal"], packet["segment"]
        if reset:
            self._reset("segment_reset")
        result = dict.fromkeys((*FAMILIES, "crossing_follow"), 0)
        current_quality = (
            bool(g["range_ready"])
            and f["unknown_trade_fraction_5s"] <= 0.1
            and all(g[f"unknown_fraction_qty_{w}s"] <= 0.1 for w in events.tape.WINDOWS)
        )
        if gap or not current_quality:
            self._reset("quality_or_gap_reset")
            return result
        direction = v1.sign(f["normalized_cvd_5s"])
        flow = direction != 0 and direction == v1.sign(g["delta_qty_5s"])
        confirm = (
            flow
            and f["log_known_trades_5s"] > 0
            and (f["log_known_trades_5s"] >= self.bundle["confirmation_activity"])
        )
        eligible = []
        for marker in packet["markers"]:
            self.audit["delivered_markers"] += 1
            if now - marker["ts_ns"] > events.DELIVERY_SECONDS * events.tape.SECOND:
                self.audit["stale_markers"] += 1
            elif qualified(marker, self.bundle, self.burst):
                eligible.append(marker)
                self.audit["qualified_markers"] += 1
        if eligible:
            result["crossing_follow"] = eligible[0]["direction"]
        for family in FAMILIES:
            episode = self.pending.get(family)
            if episode is not None:
                dist = (
                    episode.direction
                    * (g["bid_nano"] + g["ask_nano"] - episode.level)
                    / (2 * events.tape.TICK)
                )
                expired = now - episode.start > v1.EPISODE_SECONDS * events.tape.SECOND
                invalid = dist >= 3 if family == "failed_auction" else dist <= -0.5
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
                else:
                    episode.outside += int(dist > 0)
                    if (
                        episode.stage == 0
                        and dist >= 2
                        and episode.outside >= 2
                        and (now - episode.start >= 2 * events.tape.SECOND)
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
                if emitted:
                    result[family] = emitted
                    self._close(family, now, "confirmed")
                continue  # No replacement or re-arming on this publication.
            if eligible and now >= self.cooldown.get(family, 0):
                marker = eligible[0]
                self.pending[family] = v1.Episode(
                    marker["ts_ns"],
                    marker["direction"],
                    marker["level_nano2"],
                    marker["activity"],
                    abs(marker["normalized_cvd"]),
                )
                self.audit[f"{family}_armed"] += 1
        return result

    def _reset(self, reason: str) -> None:
        for family in self.pending:
            self.audit[f"{family}_reset_cancelled"] += 1
        self.pending.clear()
        self.cooldown.clear()
        self.audit[reason] += 1

    def _close(self, family: str, now: int, reason: str) -> None:
        del self.pending[family]
        self.cooldown[family] = now + v1.COOLDOWN_SECONDS * events.tape.SECOND
        self.audit[f"{family}_{reason}"] += 1


def directions(rows: list[dict], bundle: dict) -> tuple[dict, dict]:
    if not rows:
        raise ValueError("Crossing study requires a complete source session")
    result, audits = {}, {}
    for mode in MODES:
        state = State(rows[0]["source_session"], rows[0]["contract"], bundle, burst=mode == "event")
        values = [state.observe(row) for row in rows]
        for family in FAMILIES:
            result[f"{mode}_{family}"] = np.array([v[family] for v in values], dtype=np.int8)
            if family in state.pending:
                state.audit[f"{family}_pending_at_end"] += 1
        audits[mode] = dict(state.audit)
        if mode == "event":
            result["crossing_follow"] = np.array(
                [v["crossing_follow"] for v in values], dtype=np.int8
            )
    original, original_audit = v1.directions(rows, bundle)
    for family in FAMILIES:
        result[f"snapshot_{family}"] = original[family]
        queue = np.array([v1.sign(row["features"]["queue_imbalance"]) for row in rows])
        result[f"event_{family}_queue"] = np.where(result[f"event_{family}"] != 0, queue, 0)
    burst_signals, _ = v1.old.directions(rows, bundle)
    result["burst_follow"] = burst_signals["burst_follow"]
    result["no_trade"] = np.zeros(len(rows), dtype=np.int8)
    audits["snapshot"] = original_audit
    return result, audits


def support(rows: list[dict], bundle: dict) -> dict:
    """Feature-only initiation/confirmation coverage; no outcomes or eligibility."""
    signs, audits = directions(rows, bundle)
    return {
        "rows": len(rows),
        "audits": audits,
        "signals": {name: int(np.count_nonzero(values)) for name, values in signs.items()},
    }
