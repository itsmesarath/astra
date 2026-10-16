"""Independent invented numerical controls; no archives, fitting or orders."""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import io
import itertools
import json
import math
import os
import socket
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, asdict, fields
from datetime import UTC, datetime

import pytest

from ai_trader.research import six_e_synthetic_liquidity_point as selector

VERSION = "six_e_synthetic_liquidity_point_v1"
STATUS = "constructed_liquidity_directions_not_strategy_integration"
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
AUTHORITY_NAMES = (
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
FLAGS = tuple((name, False) for name in sorted(AUTHORITY_NAMES))
UNIT_FIELDS = ("unknown_trade_fraction_5s", "bid_top_share5", "ask_top_share5")
SIGNED_UNIT_FIELDS = ("queue_imbalance", "depth5_imbalance")
NONNEGATIVE_FIELDS = (
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
)
SOURCE_PINS = {
    "src/ai_trader/training/six_e_liquidity.py": (
        "0c3643695b50c0758b7ff73c8e4bb010bafa7ef492e25e5e8f408e28edc0a3ec"
    ),
    "src/ai_trader/research/databento_6e_cost_targets.py": (
        "ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b"
    ),
    "src/ai_trader/research/databento_6e_microdepth.py": (
        "8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4"
    ),
    "src/ai_trader/research/databento_6e_execution_flow.py": (
        "7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75"
    ),
}


def canonical(body):
    return json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def pin(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def protocol_body():
    """Literal prospective oracle, not a production protocol call."""
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
            "unit_interval": list(UNIT_FIELDS),
            "signed_unit_interval": list(SIGNED_UNIT_FIELDS),
            "nonnegative": list(NONNEGATIVE_FIELDS),
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
        "source_pins": dict(SOURCE_PINS),
        "max_canonical_bytes": 16384,
    }


def point_body(value):
    return {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": pin(protocol_body()),
        "point": {"point_id": value.point_id, "values": value.values},
    }


def point_pin(value):
    return pin(point_body(value))


def selection_body(value, directions):
    return {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": pin(protocol_body()),
        "point_sha256": point_pin(value),
        "directions": directions,
        "authority_flags": FLAGS,
    }


def vector(**changes):
    values = dict.fromkeys(FEATURES, 0)
    values.update(
        log_bid_qty=math.log1p(5),
        log_ask_qty=math.log1p(5),
        log_bid_depth5=math.log1p(20),
        log_ask_depth5=math.log1p(20),
        log_known_trades_5s=math.log1p(20),
        log_quote_events_5s=math.log1p(20),
        log_prior_quote_gap_ms=math.log1p(250),
        unknown_trade_fraction_5s=0.1,
        bid_span5_ticks=8,
        ask_span5_ticks=8,
        normalized_cvd_5s=0.5,
        normalized_ofi_5s=0.5,
        mid_change_5s_ticks=1,
        mid_range_5s_ticks=4,
        queue_imbalance=-0.5,
        ask_held_top_passive_5s=0.25,
        ask_other_id_reload_5s=0.1,
    )
    assert set(changes) <= set(FEATURES)
    values.update(changes)
    return tuple(values[name] for name in FEATURES)


def point(*, point_id="synthetic-independent-control", **changes):
    return selector.SyntheticLiquidityPoint(point_id, vector(**changes))


def changed(value, **changes):
    """Test-only poison reaches consuming guards, not eager constructors."""
    result = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(result, field.name, getattr(value, field.name))
    for name, item in changes.items():
        object.__setattr__(result, name, item)
    return result


def changed_feature(value, name, replacement):
    values = list(value.values)
    values[FEATURES.index(name)] = replacement
    return changed(value, values=tuple(values))


def manual_directions(value):
    """Independent scalar oracle, with four outputs never combined."""
    f = dict(zip(FEATURES, value.values, strict=True))
    cvd = (f["normalized_cvd_5s"] > 0) - (f["normalized_cvd_5s"] < 0)
    ofi = (f["normalized_ofi_5s"] > 0) - (f["normalized_ofi_5s"] < 0)
    move = (f["mid_change_5s_ticks"] > 0) - (f["mid_change_5s_ticks"] < 0)
    known = f["log_known_trades_5s"] > 0
    gate = all(
        (
            f["log_prior_quote_gap_ms"] <= math.log1p(250),
            known,
            f["unknown_trade_fraction_5s"] <= 0.1,
            f["log_bid_qty"] >= math.log1p(5),
            f["log_ask_qty"] >= math.log1p(5),
            f["log_bid_depth5"] >= math.log1p(20),
            f["log_ask_depth5"] >= math.log1p(20),
            f["bid_span5_ticks"] <= 8,
            f["ask_span5_ticks"] <= 8,
            f["log_quote_events_5s"] >= math.log1p(20),
            f["log_known_trades_5s"] >= math.log1p(20),
        )
    )
    follow = gate and all(
        (
            cvd != 0 and cvd == ofi == move,
            abs(f["normalized_cvd_5s"]) >= 0.5,
            abs(f["normalized_ofi_5s"]) >= 0.5,
            abs(f["mid_change_5s_ticks"]) >= 1,
            f["mid_range_5s_ticks"] >= 4,
        )
    )
    attacked = "ask" if cvd > 0 else "bid"
    queue = (f["queue_imbalance"] > 0) - (f["queue_imbalance"] < 0)
    fade = gate and all(
        (
            cvd != 0,
            abs(f["normalized_cvd_5s"]) >= 0.5,
            abs(f["mid_change_5s_ticks"]) <= 1,
            f[f"{attacked}_held_top_passive_5s"] >= 0.25,
            f[f"{attacked}_other_id_reload_5s"] >= 0.1,
            queue == -cvd,
        )
    )
    return tuple(
        zip(
            POLICIES,
            (cvd if known else 0, cvd if follow else 0, -cvd if fade else 0, 0),
            strict=True,
        )
    )


def assert_selection(value, expected=None, *, reference=False):
    expected = manual_directions(value) if expected is None else expected
    input_pin = point_pin(value)
    result = selector.select_point(value, expected_point_sha256=input_pin)
    body = selection_body(value, expected)
    assert selector.point_sha256(value) == input_pin
    assert result.directions == expected
    assert tuple(field.name for field in fields(result)) == (
        "version",
        "status",
        "protocol_sha256",
        "point_sha256",
        "directions",
        "selection_sha256",
        "authority_flags",
    )
    assert asdict(result) == {**body, "selection_sha256": pin(body)}
    assert all(type(item) is tuple and type(item[1]) is int for item in result.directions)
    assert result.authority_flags == FLAGS
    assert all(type(pair) is tuple and pair[1] is False for pair in result.authority_flags)
    assert (
        selector.verify_point_selection(
            value, expected_point_sha256=input_pin, expected_selection_sha256=pin(body)
        )
        == result
    )
    if reference:
        # These are invented feature values under an unchanged calendar-valid
        # one-row control. No archives, guard bypasses or fitting are involved.
        from ai_trader.training import six_e_liquidity as original

        row = {
            "source_session": "2025-04-07",
            "contract": "6EM5",
            "partition": "development",
            "decision_ts_ns": int(datetime(2025, 4, 7, 12, tzinfo=UTC).timestamp()) * 10**9,
            "features": dict(zip(FEATURES[:23], value.values[:23], strict=True)),
            "execution_features": dict(zip(FEATURES[23:], value.values[23:], strict=True)),
        }
        assert original.FEATURES == FEATURES
        assert original.POLICIES[:3] == POLICIES[:3]
        observed = original.rules([row])
        assert tuple((name, int(observed[name][0])) for name in POLICIES[:3]) == expected[:3]
    return result


UNSET = object()


def invoke(api, value, *, input_pin=UNSET, output_pin=UNSET):
    if api == "point_sha256":
        return selector.point_sha256(value)
    input_pin = point_pin(value) if input_pin is UNSET else input_pin
    if api == "select_point":
        return selector.select_point(value, expected_point_sha256=input_pin)
    if output_pin is UNSET:
        output_pin = pin(selection_body(value, manual_directions(value)))
    return selector.verify_point_selection(
        value, expected_point_sha256=input_pin, expected_selection_sha256=output_pin
    )


POINT_APIS = ("point_sha256", "select_point", "verify_point_selection")


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden numerical traversal or external side effect")


def test_literal_protocol_schema_and_closed_api():
    assert selector.VERSION == VERSION
    assert selector.STATUS == STATUS
    assert selector.MAX_CANONICAL_BYTES == 16384
    assert selector.FEATURES == FEATURES
    assert selector.POLICIES == POLICIES
    assert selector.AUTHORITY_FLAGS == FLAGS
    assert selector.protocol_sha256() == pin(protocol_body())
    assert len(FEATURES) == len(set(FEATURES)) == 37
    assert len(FLAGS) == 15
    assert tuple(field.name for field in fields(selector.SyntheticLiquidityPoint)) == (
        "point_id",
        "values",
    )
    assert issubclass(selector.SyntheticLiquidityPointError, ValueError)
    assert tuple(inspect.signature(selector.select_point).parameters) == (
        "point",
        "expected_point_sha256",
    )
    assert tuple(inspect.signature(selector.verify_point_selection).parameters) == (
        "point",
        "expected_point_sha256",
        "expected_selection_sha256",
    )


@pytest.mark.parametrize("sign", (-1, 1))
def test_simultaneous_opposing_rules_are_not_combined(sign):
    value = point(
        normalized_cvd_5s=sign * 0.5,
        normalized_ofi_5s=sign * 0.5,
        mid_change_5s_ticks=sign,
        queue_imbalance=-sign * 0.5,
        bid_held_top_passive_5s=0.25,
        bid_other_id_reload_5s=0.1,
    )
    expected = tuple(zip(POLICIES, (sign, sign, -sign, 0), strict=True))
    assert_selection(value, expected, reference=True)


@pytest.mark.parametrize("cvd,ofi,move", tuple(itertools.product((-2, 0, 2), repeat=3)))
def test_all_direction_triples(cvd, ofi, move):
    value = point(
        normalized_cvd_5s=cvd,
        normalized_ofi_5s=ofi,
        mid_change_5s_ticks=move,
        queue_imbalance=0,
    )
    assert_selection(value, reference=True)


GATE_EDGES = (
    ("log_prior_quote_gap_ms", math.log1p(250)),
    ("log_bid_qty", math.log1p(5)),
    ("log_ask_qty", math.log1p(5)),
    ("log_bid_depth5", math.log1p(20)),
    ("log_ask_depth5", math.log1p(20)),
    ("log_known_trades_5s", math.log1p(20)),
    ("log_quote_events_5s", math.log1p(20)),
    ("unknown_trade_fraction_5s", 0.1),
    ("bid_span5_ticks", 8.0),
    ("ask_span5_ticks", 8.0),
    ("normalized_cvd_5s", 0.5),
    ("normalized_ofi_5s", 0.5),
    ("mid_change_5s_ticks", 1.0),
    ("mid_range_5s_ticks", 4.0),
)


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("delta", (-1, 0, 1))
@pytest.mark.parametrize("name,threshold", GATE_EDGES)
def test_follow_and_shared_gate_equalities_and_adjacent_floats(name, threshold, delta, sign):
    replacement = threshold if delta == 0 else math.nextafter(threshold, delta * math.inf)
    if name in ("normalized_cvd_5s", "normalized_ofi_5s", "mid_change_5s_ticks"):
        replacement *= sign
    values = {
        "normalized_cvd_5s": sign * 0.5,
        "normalized_ofi_5s": sign * 0.5,
        "mid_change_5s_ticks": sign,
        "queue_imbalance": -sign * 0.5,
        "bid_held_top_passive_5s": 0.25,
        "bid_other_id_reload_5s": 0.1,
        name: replacement,
    }
    assert_selection(point(**values), reference=True)


@pytest.mark.parametrize("sign", (-1, 1))
@pytest.mark.parametrize("delta", (-1, 0, 1))
@pytest.mark.parametrize("kind,threshold", (("held_top_passive", 0.25), ("other_id_reload", 0.1)))
def test_fade_attacked_side_thresholds(kind, threshold, delta, sign):
    side = "ask" if sign > 0 else "bid"
    replacement = threshold if delta == 0 else math.nextafter(threshold, delta * math.inf)
    changes = {
        "normalized_cvd_5s": sign * 0.5,
        "normalized_ofi_5s": sign * 0.5,
        "mid_change_5s_ticks": 0,
        "queue_imbalance": -sign * 0.5,
        "bid_held_top_passive_5s": 0.25,
        "bid_other_id_reload_5s": 0.1,
    }
    changes[f"{side}_{kind}_5s"] = replacement
    value = point(**changes)
    assert_selection(value, reference=True)


@pytest.mark.parametrize("sign", (-1, 1))
def test_fade_does_not_borrow_unattacked_side(sign):
    attacked = "ask" if sign > 0 else "bid"
    other = "bid" if sign > 0 else "ask"
    value = point(
        normalized_cvd_5s=sign,
        mid_change_5s_ticks=0,
        queue_imbalance=-sign,
        **{
            f"{attacked}_held_top_passive_5s": 0,
            f"{attacked}_other_id_reload_5s": 0,
            f"{other}_held_top_passive_5s": 100,
            f"{other}_other_id_reload_5s": 100,
        },
    )
    assert_selection(value, tuple(zip(POLICIES, (sign, 0, 0, 0), strict=True)), reference=True)


@pytest.mark.parametrize("queue", (-1, -math.ulp(0.0), -0.0, 0, 0.0, math.ulp(0.0), 1))
@pytest.mark.parametrize("sign", (-1, 1))
def test_queue_sign_requires_exact_opposite_direction(queue, sign):
    value = point(
        normalized_cvd_5s=sign,
        mid_change_5s_ticks=0,
        queue_imbalance=queue,
        bid_held_top_passive_5s=0.25,
        bid_other_id_reload_5s=0.1,
    )
    assert_selection(value, reference=True)


@pytest.mark.parametrize("known", (0, -0.0, math.ulp(0.0), math.nextafter(math.log1p(20), 0)))
@pytest.mark.parametrize("cvd", (-100, -0.0, 0, 100))
def test_cvd_control_needs_known_aggressors_but_not_twenty_trades(known, cvd):
    value = point(log_known_trades_5s=known, normalized_cvd_5s=cvd)
    assert_selection(value, reference=True)


def test_nonliquid_cvd_and_idle_are_independent_controls():
    value = point(log_bid_qty=0, normalized_cvd_5s=-100)
    assert_selection(value, tuple(zip(POLICIES, (-1, 0, 0, 0), strict=True)), reference=True)


USED_FEATURES = {name for name, _ in GATE_EDGES} | {
    "queue_imbalance",
    "bid_held_top_passive_5s",
    "ask_held_top_passive_5s",
    "bid_other_id_reload_5s",
    "ask_other_id_reload_5s",
}


@pytest.mark.parametrize("name", tuple(name for name in FEATURES if name not in USED_FEATURES))
def test_unused_scalar_changes_identity_not_direction(name):
    baseline = point()
    value = point(**{name: 0.75})
    assert point_pin(value) != point_pin(baseline)
    assert_selection(value, manual_directions(baseline), reference=True)


@pytest.mark.parametrize("left,right", ((0, 0.0), (1, 1.0), (0.0, -0.0)))
def test_numeric_representation_is_not_silently_coerced(left, right):
    a = point(mid_travel_5s_ticks=left)
    b = point(mid_travel_5s_ticks=right)
    assert point_pin(a) != point_pin(b)
    assert_selection(a)
    assert_selection(b)
    assert selector.point_sha256(a) != selector.point_sha256(b)
    assert a.values[FEATURES.index("mid_travel_5s_ticks")] is left


class IntSubclass(int):
    pass


class FloatSubclass(float):
    pass


class StrSubclass(str):
    pass


class TupleSubclass(tuple):
    pass


@pytest.mark.parametrize("name", FEATURES)
@pytest.mark.parametrize(
    "bad", (True, False, math.nan, math.inf, -math.inf, IntSubclass(0), FloatSubclass(0))
)
def test_every_feature_rejects_wrong_type_and_nonfinite_even_for_idle(name, bad):
    value = changed_feature(point(log_known_trades_5s=0), name, bad)
    # NaN is intentionally not independently JSON serializable. A syntactically
    # valid retained expectation suffices because complete validation must refuse.
    expected = "0" * 64 if type(bad) is float and not math.isfinite(bad) else point_pin(value)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.select_point(value, expected_point_sha256=expected)


NONNEGATIVE_ALL = tuple(
    name
    for i, name in enumerate(FEATURES)
    if i >= 23 or name.startswith("log_") or name in NONNEGATIVE_FIELDS
)


@pytest.mark.parametrize("name", NONNEGATIVE_ALL)
def test_every_nonnegative_domain_refuses_negative_with_matching_complete_pin(name):
    value = changed_feature(point(), name, -math.ulp(0.0))
    expected = point_pin(value)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.select_point(value, expected_point_sha256=expected)


@pytest.mark.parametrize("name", UNIT_FIELDS)
@pytest.mark.parametrize("bad", (-math.ulp(0.0), math.nextafter(1.0, math.inf)))
def test_unit_interval_violations_have_matching_input_pin(name, bad):
    value = changed_feature(point(), name, bad)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.select_point(value, expected_point_sha256=point_pin(value))


@pytest.mark.parametrize("name", SIGNED_UNIT_FIELDS)
@pytest.mark.parametrize("bad", (math.nextafter(-1.0, -math.inf), math.nextafter(1.0, math.inf)))
def test_signed_unit_interval_violations_have_matching_input_pin(name, bad):
    value = changed_feature(point(), name, bad)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.select_point(value, expected_point_sha256=point_pin(value))


@pytest.mark.parametrize("name", UNIT_FIELDS + SIGNED_UNIT_FIELDS)
@pytest.mark.parametrize("edge", (0, 1))
def test_domain_endpoint_equalities_pass(name, edge):
    assert_selection(point(**{name: edge}), reference=True)


@pytest.mark.parametrize("name", SIGNED_UNIT_FIELDS)
def test_negative_signed_domain_endpoint_passes(name):
    assert_selection(point(**{name: -1}), reference=True)


@pytest.mark.parametrize("name", NONNEGATIVE_ALL)
def test_nonnegative_signed_zero_passes_without_coercion(name):
    value = point(**{name: -0.0})
    assert_selection(value, reference=True)
    assert math.copysign(1, value.values[FEATURES.index(name)]) == -1


@pytest.mark.parametrize("name", ("normalized_cvd_5s", "normalized_ofi_5s", "mid_change_5s_ticks"))
@pytest.mark.parametrize(
    "magnitude", (-sys.float_info.max, sys.float_info.max, -(10**308), 10**308)
)
def test_finite_only_signed_fields_have_no_added_normalization(name, magnitude):
    assert_selection(point(**{name: magnitude}), reference=True)


def test_complete_worst_shape_finite_integer_input_and_result_fit_declared_cap():
    maximum = int(sys.float_info.max)
    values = [maximum] * 37
    for name in UNIT_FIELDS + SIGNED_UNIT_FIELDS:
        values[FEATURES.index(name)] = 1
    for name in ("normalized_cvd_5s", "normalized_ofi_5s", "mid_change_5s_ticks"):
        values[FEATURES.index(name)] = -maximum
    value = selector.SyntheticLiquidityPoint("synthetic-" + "x" * 54, tuple(values))
    result = assert_selection(value)
    input_bytes = canonical(point_body(value))
    output_bytes = canonical(selection_body(value, result.directions))
    assert 9000 < len(input_bytes) < 16384
    assert len(output_bytes) < len(canonical(protocol_body())) < len(input_bytes)
    assert len(output_bytes) < 16384
    # This shape tests every unbounded scalar at the maximum finite integer;
    # it does not claim a mathematically universal maximum JSON byte shape.


@pytest.mark.parametrize("api", POINT_APIS)
def test_unrepresentably_huge_integer_is_declared_error_not_overflow(api):
    value = changed_feature(point(), "normalized_cvd_5s", 10**10000)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, value, input_pin="0" * 64, output_pin="0" * 64)


BAD_IDS = (
    "",
    "synthetic-",
    "ordinary-point",
    "synthetic space",
    "synthetic-ä",
    "synthetic-\n",
    "synthetic-/path",
    "synthetic-" + "x" * 55,
    None,
    1,
    True,
    StrSubclass("synthetic-valid"),
)


@pytest.mark.parametrize("api", POINT_APIS)
@pytest.mark.parametrize(
    "bad",
    BAD_IDS,
    ids=lambda v: repr(v) if type(v) in (str, int, bool, type(None)) else type(v).__name__,
)
def test_identifier_metadata_refuses_before_any_numeric_traversal(api, bad, monkeypatch):
    baseline = point()
    assert_selection(baseline)
    value = changed(baseline, point_id=bad)
    monkeypatch.setattr(selector.math, "isfinite", forbidden)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, value, input_pin="0" * 64, output_pin="0" * 64)


@pytest.mark.parametrize("api", POINT_APIS)
@pytest.mark.parametrize(
    "kind",
    (
        "short",
        "long",
        "list",
        "tuple_subclass",
        "missing_id",
        "missing_values",
        "class_subclass",
        "foreign",
    ),
)
def test_complete_point_schema_precedes_scalar_traversal(api, kind, monkeypatch):
    baseline = point()
    assert_selection(baseline)
    if kind == "short":
        value = changed(baseline, values=baseline.values[:-1])
    elif kind == "long":
        value = changed(baseline, values=(*baseline.values, 0))
    elif kind == "list":
        value = changed(baseline, values=list(baseline.values))
    elif kind == "tuple_subclass":
        value = changed(baseline, values=TupleSubclass(baseline.values))
    elif kind.startswith("missing_"):
        value = changed(baseline)
        field = "point_id" if kind == "missing_id" else "values"
        object.__delattr__(value, field)
    elif kind == "class_subclass":
        subtype = type("ConstructedPointSubclass", (selector.SyntheticLiquidityPoint,), {})
        value = object.__new__(subtype)
        object.__setattr__(value, "point_id", baseline.point_id)
        object.__setattr__(value, "values", baseline.values)
    else:
        value = {"point_id": baseline.point_id, "values": baseline.values}
    monkeypatch.setattr(selector.math, "isfinite", forbidden)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, value, input_pin="0" * 64, output_pin="0" * 64)


BAD_PINS = (None, True, 0, "", "0" * 63, "0" * 65, "G" * 64, "A" * 64, StrSubclass("0" * 64))


@pytest.mark.parametrize("api", ("select_point", "verify_point_selection"))
@pytest.mark.parametrize(
    "bad",
    BAD_PINS,
    ids=lambda v: repr(v) if type(v) in (str, int, bool, type(None)) else type(v).__name__,
)
def test_expected_input_pin_syntax_precedes_numeric_inspection(api, bad, monkeypatch):
    value = point()
    output_pin = pin(selection_body(value, manual_directions(value)))
    assert_selection(value)
    monkeypatch.setattr(selector.math, "isfinite", forbidden)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, value, input_pin=bad, output_pin=output_pin)


@pytest.mark.parametrize(
    "bad",
    BAD_PINS,
    ids=lambda v: repr(v) if type(v) in (str, int, bool, type(None)) else type(v).__name__,
)
def test_expected_output_pin_syntax_precedes_numeric_inspection(bad, monkeypatch):
    value = point()
    input_pin = point_pin(value)
    assert_selection(value)
    monkeypatch.setattr(selector.math, "isfinite", forbidden)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.verify_point_selection(
            value, expected_point_sha256=input_pin, expected_selection_sha256=bad
        )


@pytest.mark.parametrize("api", ("select_point", "verify_point_selection"))
def test_valid_but_replaced_input_pin_is_not_refreshed(api):
    original = point()
    modified = point(mid_travel_5s_ticks=1)
    assert_selection(original)
    assert_selection(modified)
    original_output = pin(selection_body(original, manual_directions(original)))
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, modified, input_pin=point_pin(original), output_pin=original_output)


def test_valid_but_replaced_complete_output_pin_is_not_refreshed():
    value = point()
    body = selection_body(value, manual_directions(value))
    input_pin = point_pin(value)
    assert_selection(value)
    body["authority_flags"] = (("trading_enabled", True),)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.verify_point_selection(
            value, expected_point_sha256=input_pin, expected_selection_sha256=pin(body)
        )


def test_otherwise_valid_reordered_vector_requires_original_complete_pin():
    original = point(mid_change_5s_ticks=2, mid_range_5s_ticks=4)
    values = list(original.values)
    a, b = FEATURES.index("mid_change_5s_ticks"), FEATURES.index("mid_range_5s_ticks")
    values[a], values[b] = values[b], values[a]
    reordered = selector.SyntheticLiquidityPoint(original.point_id, tuple(values))
    assert point_pin(reordered) != point_pin(original)
    assert_selection(original)
    # Semantics of a coherently replaced vector cannot be authenticated. Both
    # invented vectors are valid; only the independently retained pin detects
    # replacement of the original complete ordered numerical input.
    assert_selection(reordered)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.select_point(reordered, expected_point_sha256=point_pin(original))


@pytest.mark.parametrize("api", POINT_APIS)
def test_defensive_tiny_envelope_cap_precedes_numeric_inspection(api, monkeypatch):
    value = point()
    input_pin = point_pin(value)
    output_pin = pin(selection_body(value, manual_directions(value)))
    assert_selection(value)
    monkeypatch.setattr(selector, "MAX_CANONICAL_BYTES", 1)
    monkeypatch.setattr(selector.math, "isfinite", forbidden)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        invoke(api, value, input_pin=input_pin, output_pin=output_pin)


def test_runtime_protocol_cap_refuses_without_changing_fixed_identity(monkeypatch):
    expected = pin(protocol_body())
    original_size = len(canonical(protocol_body()))
    assert selector.protocol_sha256() == expected
    monkeypatch.setattr(selector, "MAX_CANONICAL_BYTES", original_size)
    assert selector.protocol_sha256() == expected
    monkeypatch.setattr(selector, "MAX_CANONICAL_BYTES", original_size - 1)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        selector.protocol_sha256()


def test_runtime_point_cap_guards_complete_body_not_partial_input(monkeypatch):
    maximum = int(sys.float_info.max)
    values = [maximum] * 37
    for name in UNIT_FIELDS + SIGNED_UNIT_FIELDS:
        values[FEATURES.index(name)] = 1
    value = selector.SyntheticLiquidityPoint("synthetic-large-cap-control", tuple(values))
    input_pin = point_pin(value)
    output_pin = pin(selection_body(value, manual_directions(value)))
    size = len(canonical(point_body(value)))
    assert size > len(canonical(protocol_body()))
    assert_selection(value)
    monkeypatch.setattr(selector, "MAX_CANONICAL_BYTES", size)
    for api in POINT_APIS:
        result = invoke(api, value, input_pin=input_pin, output_pin=output_pin)
        if api == "point_sha256":
            assert result == input_pin
        else:
            assert result.selection_sha256 == output_pin
    monkeypatch.setattr(selector, "MAX_CANONICAL_BYTES", size - 1)
    for api in POINT_APIS:
        with pytest.raises(selector.SyntheticLiquidityPointError):
            invoke(api, value, input_pin=input_pin, output_pin=output_pin)


@pytest.mark.parametrize("api", ("protocol_sha256", *POINT_APIS))
@pytest.mark.parametrize("exception", (TypeError, ValueError, OverflowError))
def test_serialization_failures_become_declared_error(api, exception, monkeypatch):
    value = point()
    input_pin = point_pin(value)
    output_pin = pin(selection_body(value, manual_directions(value)))
    assert_selection(value)

    def fail(*args, **kwargs):
        raise exception("Invented encoder failure")

    monkeypatch.setattr(selector.json, "dumps", fail)
    with pytest.raises(selector.SyntheticLiquidityPointError):
        if api == "protocol_sha256":
            selector.protocol_sha256()
        else:
            invoke(api, value, input_pin=input_pin, output_pin=output_pin)


def test_point_and_selection_are_frozen_slotted_and_pure_repeatable():
    value = point()
    retained = (value.point_id, value.values)
    result = assert_selection(value)
    assert not hasattr(value, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.values = ()
    with pytest.raises(FrozenInstanceError):
        result.directions = ()
    assert assert_selection(value) == result
    assert (value.point_id, value.values) == retained
    assert all(flag is False for _, flag in result.authority_flags)


def test_production_stdlib_only_imports_and_no_integration_hooks():
    tree = ast.parse(inspect.getsource(selector))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.append(node.module.split(".")[0])
    assert set(imported) <= sys.stdlib_module_names | {"__future__"}
    banned_roots = {
        "os",
        "pathlib",
        "socket",
        "subprocess",
        "time",
        "datetime",
        "importlib",
        "requests",
    }
    assert not set(imported) & banned_roots
    banned_names = {"open", "eval", "exec", "compile", "__import__", "input"}
    banned_attrs = {
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "system",
        "Popen",
        "sleep",
        "now",
        "utcnow",
        "fit",
        "train",
        "place_order",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in banned_names
            elif isinstance(node.func, ast.Attribute):
                assert node.func.attr not in banned_attrs


def test_selection_calls_need_no_files_clock_process_or_network(monkeypatch):
    value = point()
    input_pin = point_pin(value)
    output_pin = pin(selection_body(value, manual_directions(value)))
    assert_selection(value)
    for owner, attribute in (
        (builtins, "open"),
        (io, "open"),
        (os, "open"),
        (socket, "socket"),
        (subprocess, "run"),
        (subprocess, "Popen"),
        (time, "time"),
        (time, "sleep"),
    ):
        monkeypatch.setattr(owner, attribute, forbidden)
    assert selector.protocol_sha256() == pin(protocol_body())
    assert selector.point_sha256(value) == input_pin
    result = selector.select_point(value, expected_point_sha256=input_pin)
    assert result.selection_sha256 == output_pin
    assert (
        selector.verify_point_selection(
            value, expected_point_sha256=input_pin, expected_selection_sha256=output_pin
        )
        == result
    )
