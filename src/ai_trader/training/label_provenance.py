"""Check declared kline labels against their verified research candle sessions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ai_trader.backtesting.candle_replay import CandleSession
from ai_trader.features import kline_dataset
from ai_trader.features.kline_dataset import LABEL_SCHEMA_VERSION, TripleBarrierConfig
from ai_trader.training.feature_provenance import _content_hash
from ai_trader.training.session_data import KLINE_LABEL_COLUMNS, SessionPartition

CONFIG_COLUMNS = (
    "take_profit_bps",
    "stop_loss_bps",
    "neutral_threshold_bps",
    "taker_fee_bps",
    "slippage_bps",
)


@dataclass(frozen=True, slots=True)
class VerifiedLabelSession:
    source_session: str
    rows: int
    label_records_sha256: str
    candles_sha256: str


@dataclass(frozen=True, slots=True)
class ResearchLabelProvenance:
    policy: str
    scope: str
    settings: dict[str, str | int]
    calculation_module_sha256: str
    sessions: tuple[VerifiedLabelSession, ...]


def verify_research_labels(
    partitions: tuple[SessionPartition, ...],
    candles: tuple[CandleSession, ...],
) -> ResearchLabelProvenance:
    """Recompute every supplied label with one consistent declared labeling-v2 spec.

    Call after feature verification on the same validated research candles. This
    checks consistency with the current generator, not independent correctness
    of its algorithm or historical authenticity. Replay stress settings are not
    used: labels retain their declared base horizon and cost assumptions.
    """
    names = tuple(item.name for item in partitions)
    if not names or len(set(names)) != len(names) or names != tuple(item.name for item in candles):
        raise ValueError("Label provenance requires exactly matching research sessions.")
    specification = None
    settings = {}
    verified = []
    for partition, source in zip(partitions, candles, strict=True):
        records = partition.label_records
        if (
            records is None
            or not records
            or len(records) != len(partition.event_times_ms)
            or partition.outcomes is None
            or len(partition.outcomes) != len(records)
            or len(partition.partition.targets) != len(records)
        ):
            raise ValueError(f"{source.name}: complete label evidence and outcomes are required.")
        closes = {bar.close_time_ms: index for index, bar in enumerate(source.candles)}
        interval_ms = source.candles[0].close_time_ms - source.candles[0].open_time_ms + 1
        for row_index, values in enumerate(records):
            if len(values) != len(KLINE_LABEL_COLUMNS):
                raise ValueError(f"{source.name}: invalid label evidence width.")
            row = dict(zip(KLINE_LABEL_COLUMNS, values, strict=True))
            if row["schema_version"] != "1" or row["labeling_version"] != str(LABEL_SCHEMA_VERSION):
                raise ValueError(
                    "Label verification requires labeling version 2; regenerate legacy data."
                )
            try:
                horizon_ms = int(row["label_horizon_ms"])
                if (
                    str(horizon_ms) != row["label_horizon_ms"]
                    or horizon_ms <= 0
                    or horizon_ms % interval_ms
                ):
                    raise ValueError("Invalid label horizon.")
                config = TripleBarrierConfig(
                    **{name: Decimal(row[name]) for name in CONFIG_COLUMNS}
                )
                config.validate()
            except (ValueError, InvalidOperation) as error:
                raise ValueError(f"{source.name}: invalid declared label settings.") from error
            current_specification = (horizon_ms, config)
            if specification is None:
                specification = current_specification
                settings = {
                    "labeling_version": LABEL_SCHEMA_VERSION,
                    "label_horizon_ms": horizon_ms,
                    **{name: str(getattr(config, name)) for name in CONFIG_COLUMNS},
                }
            elif current_specification != specification:
                raise ValueError(
                    "Research rows must use one consistent declared label specification."
                )
            event_time = partition.event_times_ms[row_index]
            if event_time not in closes:
                raise ValueError(f"{source.name}: label feature timestamp is not a candle close.")
            index = closes[event_time]
            session_day = datetime.fromtimestamp(
                source.candles[0].open_time_ms / 1000, tz=UTC
            ).date()
            if source.name != f"binance_spot_{row['symbol']}_{session_day.isoformat()}":
                raise ValueError(f"{source.name}: label symbol/session identity mismatch.")
            outcome = kline_dataset.calculate_triple_barrier_outcome(
                source.candles,
                index,
                horizon_bars=horizon_ms // interval_ms,
                config=config,
            )
            if outcome is None:
                raise ValueError(f"{source.name}: label horizon extends beyond its source session.")
            expected = kline_dataset._build_output_row(
                symbol=row["symbol"],
                session_name=source.name,
                klines=source.candles,
                feature_index=index,
                horizon_ms=horizon_ms,
                config=config,
                outcome=outcome,
            )
            for column in KLINE_LABEL_COLUMNS:
                actual, required = row[column], expected[column]
                if column in {"symbol", "source_session", "barrier_hit"} or isinstance(
                    required, int
                ):
                    matches = actual == str(required)
                else:
                    try:
                        number = Decimal(actual)
                        matches = number.is_finite() and number == Decimal(str(required))
                    except InvalidOperation:
                        matches = False
                if not matches:
                    raise ValueError(
                        f"{source.name} at {event_time}: label provenance mismatch in {column}."
                    )
            used = partition.outcomes[row_index]
            if (
                partition.partition.targets[row_index] != outcome.direction
                or used.entry_time_ms != outcome.entry_time_ms
                or used.exit_time_ms != outcome.future_event_time_ms
                or used.net_return_bps != float(outcome.net_return_bps)
            ):
                raise ValueError(
                    f"{source.name}: parsed model targets/outcomes differ from label evidence."
                )
        verified.append(
            VerifiedLabelSession(
                source.name,
                len(records),
                _content_hash({"columns": KLINE_LABEL_COLUMNS, "records": records}),
                _content_hash(
                    {
                        "source_session": source.name,
                        "candles": [asdict(candle) for candle in source.candles],
                    }
                ),
            )
        )
    return ResearchLabelProvenance(
        policy="declared_label_v2_recomputation_exact_v1",
        scope="all_nonheldout_research_labels",
        settings=settings,
        calculation_module_sha256=kline_dataset.file_sha256(Path(kline_dataset.__file__)),
        sessions=tuple(verified),
    )
