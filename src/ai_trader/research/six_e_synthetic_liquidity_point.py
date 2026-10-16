"""Fixed invented feature-point directions, never historical strategy integration.

The numerical rules are isolated from calendars, loaders and models. Supplied
values have no authenticated causal provenance, eligibility or market context.
Declared original-source pins are literals, not runtime source-file checks.
There is no I/O, clock, account, fitting, network or execution hook.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, fields, replace

VERSION = "six_e_synthetic_liquidity_point_v1"
STATUS = "constructed_liquidity_directions_not_strategy_integration"
MAX_CANONICAL_BYTES = 16384
FEATURES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
    "log_bid_depth5",
    "log_ask_depth5",
    "depth5_imbalance",
    "bid_top_share5",
    "ask_top_share5",
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_change_5s_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "log_quote_events_5s",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
    "bid_passive_5s",
    "bid_held_top_passive_5s",
    "bid_linked_decrease_5s",
    "bid_unlinked_decrease_5s",
    "bid_same_id_reload_5s",
    "bid_other_id_reload_5s",
    "bid_same_id_net_refresh_5s",
    "ask_passive_5s",
    "ask_held_top_passive_5s",
    "ask_linked_decrease_5s",
    "ask_unlinked_decrease_5s",
    "ask_same_id_reload_5s",
    "ask_other_id_reload_5s",
    "ask_same_id_net_refresh_5s",
)
POLICIES = ("cvd_follow", "liquidity_follow", "absorption_fade", "no_trade")
_UNIT_INTERVAL = ("unknown_trade_fraction_5s", "bid_top_share5", "ask_top_share5")
_SIGNED_UNIT_INTERVAL = ("queue_imbalance", "depth5_imbalance")
_NONNEGATIVE = (
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
)
_SOURCE_PINS = (
    (
        "src/ai_trader/training/six_e_liquidity.py",
        "0c3643695b50c0758b7ff73c8e4bb010bafa7ef492e25e5e8f408e28edc0a3ec",
    ),
    (
        "src/ai_trader/research/databento_6e_cost_targets.py",
        "ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b",
    ),
    (
        "src/ai_trader/research/databento_6e_microdepth.py",
        "8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4",
    ),
    (
        "src/ai_trader/research/databento_6e_execution_flow.py",
        "7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75",
    ),
)
AUTHORITY_FLAGS = tuple(
    sorted(
        (name, False)
        for name in (
            "input_authenticated",
            "source_integrity_verified",
            "causal_features_verified",
            "calendar_verified",
            "eligibility_verified",
            "complete_session_verified",
            "original_strategy_integration_verified",
            "accounting_admission_authorized",
            "execution_authorized",
            "storage_resume_authorized",
            "trading_enabled",
            "training_enabled",
            "scoring_authorized",
            "independent_validation",
            "promotion_allowed",
        )
    )
)


class SyntheticLiquidityPointError(ValueError):
    """Malformed, conflicting or excessive complete invented point context."""


def _require(condition, message):
    if not condition:
        raise SyntheticLiquidityPointError(message)


def _pin(value):
    _require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "Exact lowercase SHA256 expectation required",
    )


def _canonical(value):
    raw = json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    _require(len(raw) <= MAX_CANONICAL_BYTES, "Complete canonical point body exceeds byte bound")
    return raw


def _hash(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class SyntheticLiquidityPoint:
    point_id: str
    values: tuple[int | float, ...]

    def __post_init__(self):
        try:
            _point_fields(self)
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise SyntheticLiquidityPointError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class PointSelection:
    version: str
    status: str
    protocol_sha256: str
    point_sha256: str
    directions: tuple[tuple[str, int], ...]
    selection_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


def _point_metadata(point):
    _require(type(point) is SyntheticLiquidityPoint, "Exact SyntheticLiquidityPoint required")
    _require(
        all(hasattr(point, field.name) for field in fields(SyntheticLiquidityPoint)),
        "Complete frozen point fields required",
    )
    _require(
        type(point.point_id) is str
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", point.point_id) is not None
        and point.point_id.startswith("synthetic-")
        and len(point.point_id) > 10,
        "Exact bounded nonempty ASCII synthetic point identifier required",
    )
    _require(
        type(point.values) is tuple and len(point.values) == 37,
        "Complete exact immutable 37-value tuple required",
    )


def _point_fields(point):
    _point_metadata(point)
    _require(
        all(type(value) in (int, float) and math.isfinite(value) for value in point.values),
        "Exact finite int/float values required, without bool or subclasses",
    )
    values = dict(zip(FEATURES, point.values, strict=True))
    _require(
        all(value >= 0 for value in point.values[23:])
        and all(value >= 0 for name, value in values.items() if name.startswith("log_"))
        and all(0 <= values[name] <= 1 for name in _UNIT_INTERVAL)
        and all(-1 <= values[name] <= 1 for name in _SIGNED_UNIT_INTERVAL)
        and all(values[name] >= 0 for name in _NONNEGATIVE),
        "Original numerical feature domains required",
    )
    return values


def _protocol():
    # Declared literals identify the reviewed formulas, not runtime source checks.
    return {
        "version": VERSION,
        "status": STATUS,
        "features": list(FEATURES),
        "policies": list(POLICIES),
        "numeric_domains": {
            "exact_types": ["int", "float"],
            "finite": True,
            "execution_nonnegative": True,
            "log_nonnegative": True,
            "unit_interval": list(_UNIT_INTERVAL),
            "signed_unit_interval": list(_SIGNED_UNIT_INTERVAL),
            "nonnegative": list(_NONNEGATIVE),
        },
        "thresholds": {
            "prior_quote_gap_ms": 250,
            "top_quantity": 5,
            "depth5_quantity": 20,
            "max_span_ticks": 8,
            "quote_events": 20,
            "known_trades": 20,
            "unknown_fraction": 0.1,
            "abs_cvd": 0.5,
            "abs_ofi": 0.5,
            "follow_abs_move_ticks": 1,
            "follow_range_ticks": 4,
            "fade_abs_move_ticks": 1,
            "held_top_passive": 0.25,
            "other_id_reload": 0.1,
        },
        "source_pins": dict(_SOURCE_PINS),
        "max_canonical_bytes": 16384,
    }


def protocol_sha256() -> str:
    """Hash fixed declared formula/schema provenance, without reading source files."""
    try:
        return _hash(_protocol())
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticLiquidityPointError(str(exc)) from exc


def _point_context(point):
    _point_metadata(point)
    protocol_pin = protocol_sha256()  # Known fixed envelope is bounded before numeric values.
    values = _point_fields(point)
    body = {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": protocol_pin,
        "point": asdict(point),
    }
    return protocol_pin, _hash(body), values


def point_sha256(point: SyntheticLiquidityPoint) -> str:
    """Generate a complete local input identity, never refresh retained expectations."""
    try:
        return _point_context(point)[1]
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticLiquidityPointError(str(exc)) from exc


def _sign(value):
    return int(value > 0) - int(value < 0)


def _directions(values):
    cvd, ofi, move = (
        _sign(values["normalized_cvd_5s"]),
        _sign(values["normalized_ofi_5s"]),
        _sign(values["mid_change_5s_ticks"]),
    )
    cvd_follow = cvd if values["log_known_trades_5s"] > 0 else 0
    follow, fade = 0, 0
    liquid = (
        values["log_prior_quote_gap_ms"] <= math.log1p(250)
        and values["log_known_trades_5s"] > 0
        and values["unknown_trade_fraction_5s"] <= 0.1
        and min(values["log_bid_qty"], values["log_ask_qty"]) >= math.log1p(5)
        and min(values["log_bid_depth5"], values["log_ask_depth5"]) >= math.log1p(20)
        and max(values["bid_span5_ticks"], values["ask_span5_ticks"]) <= 8
        and values["log_quote_events_5s"] >= math.log1p(20)
    )
    if liquid and values["log_known_trades_5s"] >= math.log1p(20):
        if (
            cvd == ofi == move != 0
            and abs(values["normalized_cvd_5s"]) >= 0.5
            and abs(values["normalized_ofi_5s"]) >= 0.5
            and abs(values["mid_change_5s_ticks"]) >= 1
            and values["mid_range_5s_ticks"] >= 4
        ):
            follow = cvd
        side = "ask" if cvd > 0 else "bid"
        if (
            cvd != 0
            and abs(values["normalized_cvd_5s"]) >= 0.5
            and abs(values["mid_change_5s_ticks"]) <= 1
            and values[f"{side}_held_top_passive_5s"] >= 0.25
            and values[f"{side}_other_id_reload_5s"] >= 0.1
            and _sign(values["queue_imbalance"]) == -cvd
        ):
            fade = -cvd
    return (
        ("cvd_follow", cvd_follow),
        ("liquidity_follow", follow),
        ("absorption_fade", fade),
        ("no_trade", 0),
    )


def select_point(point: SyntheticLiquidityPoint, *, expected_point_sha256: str) -> PointSelection:
    """Rebuild independent fixed directions from the complete retained invented point."""
    try:
        _pin(expected_point_sha256)  # Syntax before inspecting any numeric value.
        protocol_pin, point_pin, values = _point_context(point)
        _require(point_pin == expected_point_sha256, "Retained complete point pin differs")
        selection = PointSelection(
            VERSION, STATUS, protocol_pin, point_pin, _directions(values), "0" * 64, AUTHORITY_FLAGS
        )
        body = asdict(selection)
        del body["selection_sha256"]
        return replace(selection, selection_sha256=_hash(body))
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticLiquidityPointError(str(exc)) from exc


def verify_point_selection(
    point: SyntheticLiquidityPoint,
    *,
    expected_point_sha256: str,
    expected_selection_sha256: str,
) -> PointSelection:
    """Rebuild the complete result; no submitted selection or replacement pin is accepted."""
    try:
        _pin(expected_point_sha256)
        _pin(expected_selection_sha256)  # Both expectations precede deep numeric access.
        selection = select_point(point, expected_point_sha256=expected_point_sha256)
        _require(
            selection.selection_sha256 == expected_selection_sha256,
            "Retained complete selection pin differs",
        )
        return selection
    except (ValueError, TypeError, AttributeError, OverflowError) as exc:
        raise SyntheticLiquidityPointError(str(exc)) from exc
