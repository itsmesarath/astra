"""Replay frozen evaluation predictions without model fitting or label access."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace

from ai_trader.backtesting.candle_replay import (
    CandleSession,
    ReplayConfig,
    ReplayReport,
    replay_candles,
    replay_report_payload,
)
from ai_trader.trading.decision_policy import DecisionPolicy, decide_position


@dataclass(frozen=True, slots=True)
class FrozenPredictions:
    source_session: str
    event_times_ms: tuple[int, ...]
    probabilities: tuple[tuple[float, ...], ...]


@dataclass(frozen=True, slots=True)
class ReplayComparison:
    predictions_sha256: str
    next_open: ReplayReport
    delayed_one_bar: ReplayReport


def replay_frozen_predictions(
    predictions: tuple[FrozenPredictions, ...],
    candles: tuple[CandleSession, ...],
    policy: DecisionPolicy,
    config: ReplayConfig,
    *,
    evaluated_sessions: tuple[str, ...],
    held_out_sessions: tuple[str, ...],
) -> ReplayComparison:
    """Require exact evaluation-session coverage, and replay identical long signals twice.

    All feature timestamps, including flat predictions, must align with unique
    candle closes. This does not establish feature-to-candle derivation lineage.
    """
    config.validate()
    if policy.allow_short:
        raise ValueError("Candle replay requires a long/flat-only policy.")
    if config.entry_delay_bars != 0:
        raise ValueError(
            "Comparison config must use zero entry delay; one-bar stress is automatic."
        )
    if (
        not evaluated_sessions
        or len(set(evaluated_sessions)) != len(evaluated_sessions)
        or set(evaluated_sessions) & set(held_out_sessions)
        or tuple(item.source_session for item in predictions) != evaluated_sessions
        or tuple(item.name for item in candles) != evaluated_sessions
    ):
        raise ValueError(
            "Replay inputs must cover exactly the ordered evaluation sessions, not holdouts."
        )
    signal_sessions = []
    for frozen, source in zip(predictions, candles, strict=True):
        if source.long_signal_times_ms:
            raise ValueError("Candle inputs must not supply signals; use frozen predictions only.")
        if not frozen.event_times_ms or len(frozen.event_times_ms) != len(frozen.probabilities):
            raise ValueError("Frozen timestamps and probabilities must be nonempty and aligned.")
        closes = {candle.close_time_ms for candle in source.candles}
        previous_time = -1
        signals = []
        for event_time, probabilities in zip(
            frozen.event_times_ms, frozen.probabilities, strict=True
        ):
            if (
                type(event_time) is not int
                or event_time <= previous_time
                or event_time not in closes
            ):
                raise ValueError(
                    "Every prediction must align with a unique chronological candle close."
                )
            previous_time = event_time
            if decide_position(probabilities, policy).intent == "LONG":
                signals.append(event_time)
        signal_sessions.append(replace(source, long_signal_times_ms=tuple(signals)))
    encoded = json.dumps(
        {"predictions": [asdict(item) for item in predictions], "policy": asdict(policy)},
        sort_keys=True,
        allow_nan=False,
    )
    inputs = tuple(signal_sessions)
    return ReplayComparison(
        hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        replay_candles(inputs, config),
        replay_candles(inputs, replace(config, entry_delay_bars=1)),
    )


def replay_comparison_payload(report: ReplayComparison) -> dict[str, object]:
    return {
        "predictions_sha256": report.predictions_sha256,
        "selection_policy": "fixed_scenarios_no_winner_selection_or_promotion",
        "next_open": replay_report_payload(report.next_open),
        "delayed_one_bar": replay_report_payload(report.delayed_one_bar),
    }
