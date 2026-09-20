"""Bind selected research features to the actual candle inputs before fitting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

import numpy as np

from ai_trader.backtesting.candle_replay import CandleSession
from ai_trader.features import kline_dataset
from ai_trader.features.kline_dataset import FEATURE_WINDOWS, KLINE_FEATURE_COLUMNS
from ai_trader.training.model_data import row_to_kline_model_features
from ai_trader.training.session_data import SessionPartition


@dataclass(frozen=True, slots=True)
class VerifiedFeatureSession:
    source_session: str
    rows: int
    first_event_time_ms: int
    last_event_time_ms: int
    candles_sha256: str
    features_sha256: str


@dataclass(frozen=True, slots=True)
class ReplayFeatureProvenance:
    policy: str
    scope: str
    feature_names: tuple[str, ...]
    warmup_bars: int
    calculation_module_sha256: str
    sessions: tuple[VerifiedFeatureSession, ...]


def _content_hash(payload: object) -> str:
    def encode(value: object) -> str:
        if isinstance(value, Decimal):
            return str(value)
        raise TypeError(f"Unsupported provenance value: {type(value).__name__}")

    content = json.dumps(payload, sort_keys=True, allow_nan=False, default=encode)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def verify_replay_features(
    partitions: tuple[SessionPartition, ...],
    candles: tuple[CandleSession, ...],
    *,
    scope: Literal["evaluation", "research"] = "evaluation",
) -> ReplayFeatureProvenance:
    """Recompute every supplied row using only its causal in-session window.

    Compare float64 values after the generator's existing 12-significant-digit
    serialization. There is no tolerance or silent repair. This proves numeric
    consistency under the current calculation, not historical authenticity,
    outcome correctness, or provenance of sessions outside the supplied scope.
    Candle sessions must come from the validated raw-archive loader.
    """
    if scope not in {"evaluation", "research"}:
        raise ValueError("Feature provenance scope must be evaluation or research.")
    names = tuple(partition.name for partition in partitions)
    if not names or len(set(names)) != len(names) or names != tuple(item.name for item in candles):
        raise ValueError("Feature provenance requires exactly matching ordered source sessions.")
    warmup = max(FEATURE_WINDOWS)
    verified = []
    for partition, source in zip(partitions, candles, strict=True):
        model = partition.partition
        times = partition.event_times_ms
        if (
            model.feature_names != KLINE_FEATURE_COLUMNS
            or model.features.shape != (len(times), len(KLINE_FEATURE_COLUMNS))
            or not times
            or not np.isfinite(model.features).all()
        ):
            raise ValueError(f"{source.name}: invalid kline feature matrix for provenance.")
        closes = {candle.close_time_ms: index for index, candle in enumerate(source.candles)}
        if len(closes) != len(source.candles):
            raise ValueError(f"{source.name}: duplicate candle closes.")
        previous = -1
        for row_index, event_time in enumerate(times):
            if type(event_time) is not int or event_time <= previous or event_time not in closes:
                raise ValueError(
                    f"{source.name}: feature timestamps must align to unique candle closes."
                )
            previous = event_time
            index = closes[event_time]
            if index < warmup:
                raise ValueError(f"{source.name}: insufficient in-session feature warmup.")
            # Do not expose a future candle, or an earlier session, to the calculator.
            window = source.candles[index - warmup : index + 1]
            recomputed = row_to_kline_model_features(
                kline_dataset.calculate_kline_features(window, warmup)
            )
            different = np.flatnonzero(model.features[row_index] != recomputed)
            if len(different):
                column = KLINE_FEATURE_COLUMNS[int(different[0])]
                raise ValueError(
                    f"{source.name} at {event_time}: feature provenance mismatch in {column}."
                )
        verified.append(
            VerifiedFeatureSession(
                source.name,
                len(times),
                times[0],
                times[-1],
                _content_hash(
                    {
                        "source_session": source.name,
                        "candles": [asdict(candle) for candle in source.candles],
                    }
                ),
                _content_hash(
                    {
                        "source_session": source.name,
                        "event_times_ms": times,
                        "feature_names": model.feature_names,
                        "features": model.features.tolist(),
                    }
                ),
            )
        )
    return ReplayFeatureProvenance(
        policy="causal_kline_12sig_float64_exact_v1",
        scope=(
            "all_nonheldout_research_features_not_outcomes"
            if scope == "research"
            else "evaluation_features_only_not_fit_tune_or_outcomes"
        ),
        feature_names=KLINE_FEATURE_COLUMNS,
        warmup_bars=warmup,
        calculation_module_sha256=kline_dataset.file_sha256(Path(kline_dataset.__file__)),
        sessions=tuple(verified),
    )
