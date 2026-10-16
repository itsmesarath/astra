"""Independent invented typed adapter contract oracles; no native/history calls."""

import copy
import hashlib
import importlib
import inspect
import json
import math
from dataclasses import FrozenInstanceError, replace

import pytest

from ai_trader.research import six_e_native_cursor_metadata as cursor
from ai_trader.research import six_e_record_payload_binding as binding

RAW_FIELDS = (
    "publisher_id",
    "instrument_id",
    "ts_event",
    "order_id",
    "price",
    "size",
    "action",
    "side",
    "ts_recv",
    "flags",
    "channel_id",
    "ts_in_delta",
    "sequence",
    "ts_out",
    "rtype",
    "record_size",
)
CURSOR_FLAGS = (
    "account_authenticated",
    "book_application_verified",
    "broker_economics_measured",
    "byte_offsets_verified",
    "calendar_authenticated",
    "decoded_source_authenticated",
    "event_closure_verified",
    "execution_allowed",
    "feature_derivation_verified",
    "funding_authenticated",
    "historical_access_allowed",
    "historical_validation_allowed",
    "mapping_authenticated",
    "model_call_allowed",
    "native_decoding_verified",
    "native_eof_verified",
    "native_target_ordinals_verified",
    "promotion_allowed",
    "publication_cursor_verified",
    "runtime_authenticated",
    "scoring_allowed",
    "source_authenticated",
    "storage_resume_allowed",
    "strategy_integration_allowed",
    "trading_enabled",
    "training_allowed",
)
BINDING_FLAGS = tuple(
    sorted(
        CURSOR_FLAGS
        + (
            "codec_context_authenticated",
            "native_header_verified",
            "native_payloads_verified",
            "native_record_semantics_verified",
            "original_bytes_verified",
        )
    )
)
ADAPTER_FLAGS = tuple(
    sorted(
        BINDING_FLAGS
        + (
            "original_feature_row_parity_verified",
            "complete_history_capacity_verified",
            "multi_session_continuity_verified",
        )
    )
)
SCHEMAS = {
    "AdapterContext": (
        "input_version",
        "upgrade_policy",
        "yielded_version",
        "stype_in",
        "stype_out",
        "partial",
        "limit",
        "ts_out",
    ),
    "AdapterFixture": ("context", "payload_bundle"),
    "OrderState": ("side", "price", "size"),
    "OrderEntry": ("order_id", "state"),
    "PriceLevel": ("price", "size"),
    "AdapterAudit": (
        "decoded_position",
        "disposition",
        "instrument_id",
        "target_candidate_ordinal",
        "target_transition_ordinal",
        "binding_prefix_sha256",
        "adapter_prefix_sha256",
    ),
    "TargetTransition": (
        "decoded_position",
        "target_transition_ordinal",
        "disposition",
        "snapshot",
        "exceptional_closed_clear",
        "order_id",
        "before",
        "after",
        "initialized_before",
        "initialized_after",
        "last_recv_before",
        "last_recv_after",
        "event_ordinal",
        "quote_ordinal",
        "publication_ordinal",
        "state_sha256",
    ),
    "EventWitness": (
        "event_ordinal",
        "closing_decoded_position",
        "closing_target_transition_ordinal",
        "ts_recv_ns",
        "target_positions",
        "trade_positions",
        "execution_capture_positions",
        "quote_ordinal",
        "adapter_prefix_sha256",
        "event_sha256",
    ),
    "QuoteWitness": (
        "quote_ordinal",
        "event_ordinal",
        "decoded_position",
        "ts_recv_ns",
        "bid",
        "ask",
        "bid_qty",
        "ask_qty",
        "prior_quote_gap_ns",
        "ofi_generation",
        "bid_depth5",
        "ask_depth5",
        "adapter_prefix_sha256",
        "quote_sha256",
    ),
    "InactivityInterval": (
        "start_ns",
        "timer_fired_ns",
        "end_ns",
        "recovered",
        "trigger_decoded_position",
    ),
    "FeaturePublication": (
        "publication_ordinal",
        "quote_ordinal",
        "event_ordinal",
        "decoded_position",
        "ts_recv_ns",
        "adapter_prefix_sha256",
        "features",
        "publication_sha256",
    ),
    "ClockSample": (
        "decoded_position",
        "ts_recv",
        "ts_event",
        "ts_in_delta",
        "flags",
        "sequence",
        "action",
        "protected",
        "event_ahead_ns",
        "sending_ns",
    ),
    "ClockQuality": (
        "target_records",
        "snapshot_records",
        "non_snapshot_records",
        "event_after_receive",
        "negative_send_delta",
        "event_after_sending",
        "clamped_delta",
        "clock_disagreement_records",
        "protected_disagreement_records",
        "outside_disagreement_records",
        "min_event_ahead_ns",
        "max_event_ahead_ns",
        "min_negative_delta_ns",
        "samples",
    ),
    "ReconstructedState": (
        "initialized",
        "orders",
        "bid_levels",
        "ask_levels",
        "last_recv_ns",
        "pending_target_positions",
        "pending_trade_positions",
        "execution_capture_positions",
        "last_quote_ordinal",
        "flow_events",
        "cvd",
        "known_trades",
        "unknown_trades",
        "ofi_generation",
        "ofi_previous_quote_ordinal",
        "ofi_first_ts_ns",
        "ofi_events",
        "ofi_total",
        "history_ofi_generation",
        "history_quote_ordinals",
        "bid_depletions",
        "ask_depletions",
        "history_reloads",
        "execution_last_ts_ns",
        "execution_events",
        "execution_totals",
        "bid_credits",
        "ask_credits",
        "execution_audit",
        "next_publication_ns",
        "watch_since_ns",
        "inactivity_start_ns",
        "window_closed",
    ),
    "AdapterAssessment": (
        "status",
        "protocol_sha256",
        "context_sha256",
        "binding_protocol_sha256",
        "cursor_protocol_sha256",
        "fixture_sha256",
        "fixture",
        "binding_assessment",
        "audits",
        "transitions",
        "events",
        "quotes",
        "publications",
        "inactivity_intervals",
        "clock_quality",
        "exceptional_clear_count",
        "terminal_state",
        "authority_flags",
        "assessment_sha256",
    ),
}
FEATURE_NAMES = (
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
DAY = 1_743_984_000_000_000_000
SECOND = 1_000_000_000
NOON = DAY + 43_200 * SECOND
END = DAY + 57_600 * SECOND
WARMUP = NOON - 10 * SECOND


def canonical(body):
    return json.dumps(
        body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(body):
    return hashlib.sha256(canonical(body)).hexdigest()


def expected_cursor_protocol():
    return {
        "version": "constructed_decoded_cursor_metadata_v1",
        "scope": "invented_header_mapping_and_decoded_item_assertions_only",
        "status": "constructed_decoded_cursor_metadata_not_native_verification",
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "dataset": "GLBX.MDP3",
        "schema": "mbo",
        "symbols": ["6E.FUT"],
        "not_found": [],
        "day_start_ns": DAY,
        "day_end_ns": DAY + 86_400 * SECOND,
        "max_items": 128,
        "max_mapping_groups": 8,
        "max_intervals_per_group": 16,
        "max_total_intervals": 32,
        "max_body_bytes": 65_536,
        "max_instrument_id": 4_294_967_295,
        "decoded_position_origin": 1,
        "target_candidate_ordinal_origin": 1,
        "header_included": True,
        "payload_pins": "opaque_caller_assertions",
        "prefix_complete_member_pin": "excluded",
        "authority_flags": dict.fromkeys(CURSOR_FLAGS, False),
    }


def expected_binding_protocol():
    signed = [-9_223_372_036_854_775_808, 9_223_372_036_854_775_807]
    unsigned = [0, 18_446_744_073_709_551_615]
    return {
        "version": "constructed_record_payload_binding_v1",
        "scope": "invented_complete_mbo_json_bodies_and_contextual_cursor_binding_only",
        "status": "constructed_record_payload_binding_not_native_verification",
        "codec_id": "constructed_mbo_json_v1",
        "schema_version": 1,
        "ts_out_modes": ["absent", "present"],
        "record_field_order": list(RAW_FIELDS),
        "integer_bounds": {
            "publisher_id": unsigned,
            "instrument_id": [0, 4_294_967_295],
            "ts_event": signed,
            "order_id": unsigned,
            "price": signed,
            "size": unsigned,
            "ts_recv": signed,
            "flags": unsigned,
            "channel_id": unsigned,
            "ts_in_delta": signed,
            "sequence": unsigned,
            "ts_out": signed,
            "rtype": unsigned,
            "record_size": [1, 65_536],
        },
        "action_side_length": 1,
        "action_side_codepoint_min": 0,
        "action_side_codepoint_max": 127,
        "min_items": 2,
        "max_items": 128,
        "max_payloads": 127,
        "max_body_bytes": 262_144,
        "max_cursor_body_bytes": 65_536,
        "metadata_payload": "literal_none",
        "context_pin_scheme": "sha256_canonical_context_body",
        "payload_pin_scheme": "sha256_canonical_complete_record_body",
        "contextual_prefix_scheme": "sha256_binding_protocol_context_cursor_prefix",
        "prefix_complete_member_pin": "excluded",
        "cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "cursor_source_sha256": "c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91",
        "dataclass_fields": {
            "PayloadContext": ["codec_id", "schema_version", "ts_out_mode"],
            "MboPayload": list(RAW_FIELDS),
            "PayloadBundle": ["context", "cursor_fixture", "payloads"],
            "PayloadAudit": [
                "decoded_position",
                "disposition",
                "instrument_id",
                "target_candidate_ordinal",
                "payload_sha256",
                "cursor_item_sha256",
                "cursor_prefix_sha256",
                "bound_prefix_sha256",
            ],
            "BindingAssessment": [
                "status",
                "protocol_sha256",
                "context_sha256",
                "cursor_protocol_sha256",
                "cursor_fixture_sha256",
                "bundle_sha256",
                "bundle",
                "cursor_assessment",
                "audits",
                "authority_flags",
                "assessment_sha256",
            ],
        },
        "authority_flags": dict.fromkeys(BINDING_FLAGS, False),
    }


def expected_protocol():
    return {
        "version": "constructed_typed_native_event_adapter_v1",
        "scope": "invented_native_shaped_target_event_and_feature_publication_reconstruction_only",
        "status": "constructed_typed_native_event_adapter_not_native_verification",
        "context_values": {
            "input_version": 3,
            "upgrade_policy": "AS_IS",
            "yielded_version": 3,
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "limit": None,
            "ts_out_modes": [False, True],
        },
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "day_start_ns": DAY,
        "day_end_ns": DAY + 86_400 * SECOND,
        "warmup_start_ns": WARMUP,
        "window_start_ns": NOON,
        "window_end_ns": END,
        "constants": {
            "second_ns": SECOND,
            "tick": 50_000,
            "decision_interval_ns": SECOND,
            "flow_ns": 5 * SECOND,
            "inactivity_ns": 5 * SECOND,
            "execution_window_ns": 5 * SECOND,
            "F_LAST": 128,
            "F_TOB": 64,
            "F_SNAPSHOT": 32,
            "F_MBP": 16,
            "F_BAD_TS_RECV": 8,
            "F_MAYBE_BAD_BOOK": 4,
            "UNDEF_PRICE": 9_223_372_036_854_775_807,
        },
        "limits": {
            "min_items": 2,
            "max_items": 128,
            "max_mapping_groups": 8,
            "max_intervals_per_group": 16,
            "max_total_intervals": 32,
            "max_cursor_body_bytes": 65_536,
            "max_binding_body_bytes": 262_144,
            "max_adapter_body_bytes": 1_048_576,
            "max_state_body_bytes": 1_048_576,
            "max_transitions": 127,
            "max_events": 127,
            "max_quotes": 127,
            "min_publications": 1,
            "max_publications": 32,
            "max_inactivity_intervals": 128,
            "max_orders": 127,
            "max_queue_entries": 127,
            "max_clock_samples": 8,
            "max_exceptional_clears": 32,
        },
        "dataclass_fields": {name: list(fields) for name, fields in SCHEMAS.items()},
        "feature_names": list(FEATURE_NAMES),
        "feature_scalar_rule": "original_float_values_except_single_quote_int_zero_travel",
        "prefix_scheme": "adapter_protocol_context_checked_binding_prefix",
        "prefix_complete_member_pin": "excluded",
        "binding_protocol_sha256": digest(expected_binding_protocol()),
        "cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "binding_source_sha256": "4c5ac736a268c350389c63f0c23577fdcdd4473ea19d16aa13313cb49187be94",
        "cursor_source_sha256": "c7bc0102073fa61f1d69411479331cf1e434616cb80faa6bbc266377745dcf91",
        "numerical_rule_sources": {
            "src/ai_trader/research/databento_6e_training_data.py": (
                "9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3"
            ),
            "src/ai_trader/research/databento_6e_scenario_replay.py": (
                "d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff"
            ),
            "src/ai_trader/research/databento_6e_seconds_pilot.py": (
                "7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b"
            ),
            "src/ai_trader/research/databento_6e_ofi_scalp.py": (
                "05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24"
            ),
            "src/ai_trader/research/databento_6e_event_scalp.py": (
                "48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e"
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
            "src/ai_trader/research/databento_6e_receive_clock.py": (
                "351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636"
            ),
        },
        "authority_flags": dict.fromkeys(ADAPTER_FLAGS, False),
    }


def adapter_module():
    try:
        return importlib.import_module("ai_trader.research.six_e_typed_native_event_adapter")
    except ModuleNotFoundError as exc:
        assert exc.name != "ai_trader.research.six_e_typed_native_event_adapter", (
            "Required typed adapter protocol behavior is not implemented"
        )
        raise


def test_required_protocol_matches_complete_literal_contract():
    adapter = adapter_module()
    assert callable(getattr(adapter, "protocol", None)), "Required protocol API is missing"
    actual = adapter.protocol()
    expected = expected_protocol()
    assert actual == expected
    assert canonical(actual) == canonical(expected)


class IntAlias(int):
    pass


class StrAlias(str):
    pass


class TupleAlias(tuple):
    pass


class NeverRead:
    def __getattribute__(self, name):
        raise AssertionError("Caller object traversed before expectation validation: " + name)


def context_body(mode=False):
    return {
        "input_version": 3,
        "upgrade_policy": "AS_IS",
        "yielded_version": 3,
        "stype_in": "parent",
        "stype_out": "instrument_id",
        "partial": [],
        "limit": None,
        "ts_out": mode,
    }


def make_context(adapter, mode=False):
    assert callable(getattr(adapter, "AdapterContext", None)), "Required context type is missing"
    return adapter.AdapterContext(3, "AS_IS", 3, "parent", "instrument_id", (), None, mode)


def test_required_context_identity_matches_independent_literal_body():
    adapter = adapter_module()
    assert callable(getattr(adapter, "context_sha256", None)), "Required context API is missing"
    context = make_context(adapter)
    assert adapter.context_sha256(
        context, expected_protocol_sha256=digest(expected_protocol())
    ) == (digest(context_body()))


@pytest.mark.parametrize("mode", [False, True])
def test_context_modes_are_explicit_exact_boolean_choices(mode):
    adapter = adapter_module()
    context = make_context(adapter, mode)
    assert adapter.context_sha256(
        context, expected_protocol_sha256=digest(expected_protocol())
    ) == (digest(context_body(mode)))


def test_protocol_pin_matches_complete_literal_protocol_not_returned_oracle():
    assert adapter_module().protocol_sha256() == digest(expected_protocol())


def test_returned_protocol_nested_mutation_cannot_change_literal_enforcement():
    adapter = adapter_module()
    returned = adapter.protocol()
    returned["version"] = "forged"
    returned["context_values"]["input_version"] = 2
    returned["limits"]["max_adapter_body_bytes"] = 100_000_000
    returned["constants"]["F_LAST"] = 0
    returned["authority_flags"]["execution_allowed"] = True
    returned["dataclass_fields"]["AdapterContext"].clear()
    returned["feature_names"].clear()
    returned["numerical_rule_sources"].clear()
    assert adapter.protocol() == expected_protocol()
    assert canonical(adapter.protocol()) == canonical(expected_protocol())
    assert adapter.protocol_sha256() == digest(expected_protocol())
    assert adapter.context_sha256(
        make_context(adapter), expected_protocol_sha256=digest(expected_protocol())
    ) == (digest(context_body()))


@pytest.mark.parametrize(
    "name",
    [
        "F_LAST",
        "TICK",
        "SECOND_NS",
        "MAX_BODY_BYTES",
        "MAX_ITEMS",
        "VERSION",
        "SCOPE",
        "STATUS",
        "FEATURE_NAMES",
    ],
)
def test_mutable_exported_aliases_do_not_govern_literal_protocol(monkeypatch, name):
    adapter = adapter_module()
    monkeypatch.setattr(adapter, name, "caller mutation", raising=False)
    assert adapter.protocol() == expected_protocol()
    assert canonical(adapter.protocol()) == canonical(expected_protocol())
    assert adapter.protocol_sha256() == digest(expected_protocol())


@pytest.mark.parametrize("name", tuple(SCHEMAS))
def test_exact_public_type_field_order_required_frozen_and_slotted(name):
    adapter = adapter_module()
    cls = getattr(adapter, name)
    signature = inspect.signature(cls)
    assert tuple(signature.parameters) == SCHEMAS[name]
    assert all(
        parameter.default is inspect.Parameter.empty for parameter in signature.parameters.values()
    )
    assert tuple(cls.__slots__) == SCHEMAS[name]
    marker = object()
    value = (
        make_context(adapter) if name == "AdapterContext" else cls(*(marker for _ in SCHEMAS[name]))
    )
    assert not hasattr(value, "__dict__")
    for field in SCHEMAS[name]:
        with pytest.raises(FrozenInstanceError):
            setattr(value, field, marker)
        if name != "AdapterContext":
            assert getattr(value, field) is marker
    with pytest.raises(TypeError):
        cls(*(marker for _ in SCHEMAS[name][:-1]))
    with pytest.raises(TypeError):
        cls(*(marker for _ in SCHEMAS[name]), unexpected=1)


CONTEXT_BAD = (
    ("input_version", 2),
    ("input_version", True),
    ("input_version", 3.0),
    ("input_version", IntAlias(3)),
    ("input_version", "3"),
    ("yielded_version", 2),
    ("yielded_version", True),
    ("yielded_version", 3.0),
    ("yielded_version", IntAlias(3)),
    ("yielded_version", "3"),
    ("upgrade_policy", "UPGRADE"),
    ("upgrade_policy", StrAlias("AS_IS")),
    ("upgrade_policy", None),
    ("stype_in", "instrument_id"),
    ("stype_in", StrAlias("parent")),
    ("stype_out", "parent"),
    ("stype_out", StrAlias("instrument_id")),
    ("partial", []),
    ("partial", TupleAlias()),
    ("partial", ("x",)),
    ("partial", None),
    ("limit", 0),
    ("limit", False),
    ("limit", -1),
    ("limit", 1),
    ("ts_out", 0),
    ("ts_out", 1),
    ("ts_out", None),
    ("ts_out", "absent"),
)


@pytest.mark.parametrize(
    "field,bad",
    CONTEXT_BAD,
    ids=[f"{field}-{index}" for index, (field, _) in enumerate(CONTEXT_BAD)],
)
def test_unsupported_context_representation_is_refused(field, bad):
    adapter = adapter_module()
    context = replace(make_context(adapter), **{field: bad})
    with pytest.raises(ValueError):
        adapter.context_sha256(context, expected_protocol_sha256=digest(expected_protocol()))


def test_context_dict_and_context_subclass_are_not_exact_context():
    adapter = adapter_module()

    class ContextAlias(adapter.AdapterContext):
        pass

    alias = ContextAlias(3, "AS_IS", 3, "parent", "instrument_id", (), None, False)
    for value in (context_body(), alias, object(), None):
        with pytest.raises(ValueError):
            adapter.context_sha256(value, expected_protocol_sha256=digest(expected_protocol()))


BAD_PINS = (
    None,
    True,
    1,
    "",
    "a" * 63,
    "a" * 65,
    "A" * 64,
    "g" * 64,
    "a" * 63 + "é",
    StrAlias("a" * 64),
    b"a" * 64,
    "a" * 64 + "\n",
)


@pytest.mark.parametrize("pin", BAD_PINS, ids=[f"pin-{i}" for i in range(len(BAD_PINS))])
def test_context_pin_syntax_precedes_any_caller_object_read(pin):
    with pytest.raises(ValueError):
        adapter_module().context_sha256(NeverRead(), expected_protocol_sha256=pin)


def test_context_known_protocol_mismatch_precedes_any_caller_object_read():
    with pytest.raises(ValueError):
        adapter_module().context_sha256(NeverRead(), expected_protocol_sha256="0" * 64)


PIN_FIELDS = (
    "expected_protocol_sha256",
    "expected_context_sha256",
    "expected_binding_protocol_sha256",
    "expected_cursor_protocol_sha256",
    "expected_cursor_fixture_sha256",
    "expected_binding_bundle_sha256",
    "expected_fixture_sha256",
    "expected_assessment_sha256",
)


@pytest.mark.parametrize(
    "api,positional,pins",
    [
        ("context_sha256", ("context",), PIN_FIELDS[:1]),
        ("fixture_sha256", ("fixture",), PIN_FIELDS[:6]),
        ("replay", ("fixture",), PIN_FIELDS[:7]),
        ("verify", ("assessment", "fixture"), PIN_FIELDS),
    ],
)
def test_public_pin_signatures_are_mandatory_keyword_only(api, positional, pins):
    signature = inspect.signature(getattr(adapter_module(), api))
    assert tuple(signature.parameters) == positional + pins
    for name in pins:
        parameter = signature.parameters[name]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty


@pytest.mark.parametrize("api", ["fixture_sha256", "replay", "verify"])
@pytest.mark.parametrize("field", PIN_FIELDS)
def test_all_pin_syntax_checks_precede_poisoned_fixture(monkeypatch, api, field):
    adapter = adapter_module()
    used = (
        PIN_FIELDS[:6]
        if api == "fixture_sha256"
        else (PIN_FIELDS[:7] if api == "replay" else PIN_FIELDS)
    )
    complete = {
        "expected_protocol_sha256": digest(expected_protocol()),
        "expected_context_sha256": digest(context_body()),
        "expected_binding_protocol_sha256": digest(expected_binding_protocol()),
        "expected_cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "expected_cursor_fixture_sha256": "0" * 64,
        "expected_binding_bundle_sha256": "0" * 64,
        "expected_fixture_sha256": "0" * 64,
        "expected_assessment_sha256": "0" * 64,
    }
    arguments = {key: complete[key] for key in used}
    fixture = adapter.AdapterFixture(make_context(adapter), None)
    assessment = adapter.AdapterAssessment(*(object() for _ in SCHEMAS["AdapterAssessment"]))

    def deferred_fixture_read(self, name):
        raise AssertionError("Exact fixture traversed before all pin syntax checks: " + name)

    def deferred_assessment_read(self, name):
        raise AssertionError("Exact result traversed before all pin syntax checks: " + name)

    monkeypatch.setattr(adapter.AdapterFixture, "__getattribute__", deferred_fixture_read)
    monkeypatch.setattr(adapter.AdapterAssessment, "__getattribute__", deferred_assessment_read)
    if field not in used:
        arguments[field] = "invalid"
        # Public malformed-call TypeError is normalized; constructor TypeError
        # above is separate from this guarded public boundary.
        with pytest.raises(ValueError):
            if api == "verify":
                getattr(adapter, api)(assessment, fixture, **arguments)
            else:
                getattr(adapter, api)(fixture, **arguments)
        return
    arguments[field] = "invalid"
    with pytest.raises(ValueError):
        if api == "verify":
            getattr(adapter, api)(assessment, fixture, **arguments)
        else:
            getattr(adapter, api)(fixture, **arguments)


def raw_record(
    action="N",
    side="N",
    *,
    recv=NOON,
    instrument=7,
    oid=0,
    price=0,
    size=0,
    flags=128,
    mode=False,
    sequence=1,
    **changes,
):
    body = {
        "publisher_id": 111,
        "instrument_id": instrument,
        "ts_event": recv - 1,
        "order_id": oid,
        "price": price,
        "size": size,
        "action": action,
        "side": side,
        "ts_recv": recv,
        "flags": flags,
        "channel_id": 2,
        "ts_in_delta": 0,
        "sequence": sequence,
        "ts_out": recv + 20 if mode else None,
        "rtype": 160,
        "record_size": 64,
    }
    return body | changes


def idle_records(mode=False, mapped=7):
    before = WARMUP - SECOND
    return [
        raw_record("R", recv=before, instrument=mapped, flags=0, mode=mode),
        raw_record(
            "A",
            "B",
            recv=before + 1,
            instrument=mapped,
            oid=11,
            price=1_000_001,
            size=10,
            flags=32,
            mode=mode,
            sequence=2,
        ),
        raw_record(
            "A",
            "A",
            recv=before + 2,
            instrument=mapped,
            oid=12,
            price=1_100_001,
            size=20,
            flags=32,
            mode=mode,
            sequence=3,
        ),
        raw_record(instrument=mapped, mode=mode, sequence=4),
    ]


def cursor_fixture_body(records, *, mapped=7, member="1" * 64, mappings=None):
    if mappings is None:
        mappings = [
            {
                "contract": "6EM5",
                "intervals": [
                    {
                        "start_date": "2025-04-07",
                        "end_date": "2025-04-08",
                        "instrument_symbol": str(mapped).zfill(4),
                    }
                ],
            }
        ]
    return {
        "fixture_id": "synthetic-typed-adapter",
        "source_session": "synthetic-complete-mbo",
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "header": {
            "dataset": "GLBX.MDP3",
            "schema": "mbo",
            "symbols": ["6E.FUT"],
            "not_found": [],
            "start_ns": DAY,
            "end_ns": DAY + 86_400 * SECOND,
            "mappings": mappings,
        },
        "asserted_member_sha256": member,
        "declared_item_count": len(records) + 1,
        "items": [
            {
                "decoded_position": 1,
                "kind": "metadata",
                "instrument_id": None,
                "payload_sha256": None,
            }
        ]
        + [
            {
                "decoded_position": position,
                "kind": "mbo",
                "instrument_id": raw["instrument_id"],
                "payload_sha256": digest(raw),
            }
            for position, raw in enumerate(records, 2)
        ],
    }


def cursor_object(body):
    header = body["header"]
    groups = tuple(
        cursor.MappingGroup(
            group["contract"],
            tuple(
                cursor.MappingInterval(
                    interval["start_date"], interval["end_date"], interval["instrument_symbol"]
                )
                for interval in group["intervals"]
            ),
        )
        for group in header["mappings"]
    )
    declared = cursor.DeclaredHeader(
        header["dataset"],
        header["schema"],
        tuple(header["symbols"]),
        tuple(header["not_found"]),
        header["start_ns"],
        header["end_ns"],
        groups,
    )
    items = tuple(
        cursor.DecodedItem(
            item["decoded_position"], item["kind"], item["instrument_id"], item["payload_sha256"]
        )
        for item in body["items"]
    )
    return cursor.CursorFixture(
        body["fixture_id"],
        body["source_session"],
        body["utc_date"],
        body["contract"],
        declared,
        body["asserted_member_sha256"],
        body["declared_item_count"],
        items,
    )


def expected_cursor_assessment(body, mapped=7):
    pin = digest(expected_cursor_protocol())
    prefix = digest(
        {
            "protocol_sha256": pin,
            "fixture_id": body["fixture_id"],
            "source_session": body["source_session"],
            "utc_date": body["utc_date"],
            "contract": body["contract"],
            "header": body["header"],
        }
    )
    target = foreign = 0
    audits = []
    for item in body["items"]:
        prefix = digest({"previous_prefix_sha256": prefix, "item": item})
        ordinal = None
        if item["kind"] == "metadata":
            disposition = "header"
        elif item["instrument_id"] == mapped:
            disposition = "target_candidate"
            target += 1
            ordinal = target
        else:
            disposition = "foreign"
            foreign += 1
        audits.append(
            {
                "decoded_position": item["decoded_position"],
                "disposition": disposition,
                "instrument_id": item["instrument_id"],
                "target_candidate_ordinal": ordinal,
                "item_sha256": digest(item),
                "prefix_sha256": prefix,
            }
        )
    result = {
        "status": "constructed_decoded_cursor_metadata_not_native_verification",
        "protocol_sha256": pin,
        "fixture_sha256": digest(body),
        "fixture": body,
        "mapped_instrument_id": mapped,
        "decoded_item_count": len(body["items"]),
        "target_candidate_count": target,
        "foreign_count": foreign,
        "audits": audits,
        "authority_flags": dict.fromkeys(CURSOR_FLAGS, False),
    }
    return result | {"assessment_sha256": digest(result)}


def expected_binding_assessment(body, mapped=7):
    old = expected_cursor_assessment(body["cursor_fixture"], mapped)
    pin, context_pin = digest(expected_binding_protocol()), digest(body["context"])
    audits = []
    for old_audit, item in zip(old["audits"], body["cursor_fixture"]["items"], strict=True):
        audits.append(
            {
                "decoded_position": old_audit["decoded_position"],
                "disposition": old_audit["disposition"],
                "instrument_id": old_audit["instrument_id"],
                "target_candidate_ordinal": old_audit["target_candidate_ordinal"],
                "payload_sha256": item["payload_sha256"],
                "cursor_item_sha256": old_audit["item_sha256"],
                "cursor_prefix_sha256": old_audit["prefix_sha256"],
                "bound_prefix_sha256": digest(
                    {
                        "binding_protocol_sha256": pin,
                        "context_sha256": context_pin,
                        "cursor_prefix_sha256": old_audit["prefix_sha256"],
                    }
                ),
            }
        )
    result = {
        "status": "constructed_record_payload_binding_not_native_verification",
        "protocol_sha256": pin,
        "context_sha256": context_pin,
        "cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "cursor_fixture_sha256": digest(body["cursor_fixture"]),
        "bundle_sha256": digest(body),
        "bundle": body,
        "cursor_assessment": old,
        "audits": audits,
        "authority_flags": dict.fromkeys(BINDING_FLAGS, False),
    }
    return result | {"assessment_sha256": digest(result)}


def binding_assessment_object(bundle, body):
    old = body["cursor_assessment"]
    old_result = cursor.CursorAssessment(
        old["status"],
        old["protocol_sha256"],
        old["fixture_sha256"],
        bundle.cursor_fixture,
        old["mapped_instrument_id"],
        old["decoded_item_count"],
        old["target_candidate_count"],
        old["foreign_count"],
        tuple(cursor.CursorAudit(**audit) for audit in old["audits"]),
        tuple((name, False) for name in CURSOR_FLAGS),
        old["assessment_sha256"],
    )
    return binding.BindingAssessment(
        body["status"],
        body["protocol_sha256"],
        body["context_sha256"],
        body["cursor_protocol_sha256"],
        body["cursor_fixture_sha256"],
        body["bundle_sha256"],
        bundle,
        old_result,
        tuple(binding.PayloadAudit(**audit) for audit in body["audits"]),
        tuple((name, False) for name in BINDING_FLAGS),
        body["assessment_sha256"],
    )


def make_case(mode=False, records=None, *, mapped=7, member="1" * 64, mappings=None):
    adapter = adapter_module()
    records = idle_records(mode, mapped) if records is None else records
    old_fixture = cursor_fixture_body(records, mapped=mapped, member=member, mappings=mappings)
    old_context = {
        "codec_id": "constructed_mbo_json_v1",
        "schema_version": 1,
        "ts_out_mode": "present" if mode else "absent",
    }
    bundle_body = {
        "context": old_context,
        "cursor_fixture": old_fixture,
        "payloads": [None, *records],
    }
    bundle = binding.PayloadBundle(
        binding.PayloadContext(**old_context),
        cursor_object(old_fixture),
        (None, *(binding.MboPayload(**raw) for raw in records)),
    )
    body = {"context": context_body(mode), "payload_bundle": bundle_body}
    fixture = adapter.AdapterFixture(make_context(adapter, mode), bundle)
    pins = {
        "expected_protocol_sha256": digest(expected_protocol()),
        "expected_context_sha256": digest(context_body(mode)),
        "expected_binding_protocol_sha256": digest(expected_binding_protocol()),
        "expected_cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "expected_cursor_fixture_sha256": digest(old_fixture),
        "expected_binding_bundle_sha256": digest(bundle_body),
        "expected_fixture_sha256": digest(body),
    }
    return adapter, fixture, pins, body


def call_fixture(adapter, api, fixture, pins):
    arguments = dict(pins)
    if api == "fixture_sha256":
        arguments.pop("expected_fixture_sha256")
    return getattr(adapter, api)(fixture, **arguments)


def empty_state():
    return {
        "initialized": False,
        "orders": [],
        "bid_levels": [],
        "ask_levels": [],
        "last_recv_ns": None,
        "pending_target_positions": [],
        "pending_trade_positions": [],
        "execution_capture_positions": [],
        "last_quote_ordinal": None,
        "flow_events": [],
        "cvd": 0,
        "known_trades": 0,
        "unknown_trades": 0,
        "ofi_generation": 0,
        "ofi_previous_quote_ordinal": None,
        "ofi_first_ts_ns": None,
        "ofi_events": [],
        "ofi_total": 0,
        "history_ofi_generation": None,
        "history_quote_ordinals": [],
        "bid_depletions": [],
        "ask_depletions": [],
        "history_reloads": [],
        "execution_last_ts_ns": None,
        "execution_events": [],
        "execution_totals": {},
        "bid_credits": [],
        "ask_credits": [],
        "execution_audit": {},
        "next_publication_ns": NOON,
        "watch_since_ns": WARMUP,
        "inactivity_start_ns": None,
        "window_closed": False,
    }


def idle_features():
    values = (
        math.log1p(10),
        math.log1p(20),
        -10 / 30,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        math.log1p(10),
        math.log1p(20),
        -10 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        math.log1p(1),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )
    return [[name, value] for name, value in zip(FEATURE_NAMES, values, strict=True)]


def expected_idle_assessment(fixture_body, mapped=7, *, bid_price=1_000_001, ask_price=1_100_001):
    """Literal R/snapshot-bid/snapshot-ask/noon-N oracle, foreign occurrences retained."""
    bound = expected_binding_assessment(fixture_body["payload_bundle"], mapped)
    protocol_pin, context_pin = digest(expected_protocol()), digest(fixture_body["context"])
    positions = [
        audit["decoded_position"]
        for audit in bound["audits"]
        if audit["disposition"] == "target_candidate"
    ]
    assert len(positions) == 4
    quote_position = positions[-1]
    prefixes = {
        audit["decoded_position"]: digest(
            {
                "adapter_protocol_sha256": protocol_pin,
                "context_sha256": context_pin,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
            }
        )
        for audit in bound["audits"]
    }
    bid = {"side": "B", "price": bid_price, "size": 10}
    ask = {"side": "A", "price": ask_price, "size": 20}
    state = empty_state()
    states = []
    state.update(initialized=True, last_recv_ns=WARMUP - SECOND)
    states.append(copy.deepcopy(state))
    state.update(
        orders=[{"order_id": 11, "state": bid}], bid_levels=[{"price": bid_price, "size": 10}]
    )
    states.append(copy.deepcopy(state))
    state.update(
        orders=[{"order_id": 11, "state": bid}, {"order_id": 12, "state": ask}],
        ask_levels=[{"price": ask_price, "size": 20}],
    )
    states.append(copy.deepcopy(state))
    state.update(
        last_recv_ns=NOON,
        last_quote_ordinal=1,
        ofi_generation=2,
        ofi_previous_quote_ordinal=1,
        ofi_first_ts_ns=NOON,
        history_ofi_generation=2,
        history_quote_ordinals=[1],
        history_reloads=[[NOON, 0, 0]],
        execution_last_ts_ns=NOON,
        execution_audit={"completed_events": 1, "temporal_resets": 1},
        next_publication_ns=NOON + SECOND,
        watch_since_ns=NOON,
    )
    states.append(copy.deepcopy(state))
    transitions = []
    for index, position in enumerate(positions):
        transition = {
            "decoded_position": position,
            "target_transition_ordinal": index + 1,
            "disposition": "target_reset"
            if index == 0
            else ("target_snapshot" if index in (1, 2) else "target_record"),
            "snapshot": index in (1, 2),
            "exceptional_closed_clear": False,
            "order_id": (0, 11, 12, 0)[index],
            "before": None,
            "after": (None, bid, ask, None)[index],
            "initialized_before": index != 0,
            "initialized_after": True,
            "last_recv_before": None if index == 0 else WARMUP - SECOND,
            "last_recv_after": NOON if index == 3 else WARMUP - SECOND,
            "event_ordinal": 1 if index == 3 else None,
            "quote_ordinal": 1 if index == 3 else None,
            "publication_ordinal": 1 if index == 3 else None,
            "state_sha256": digest(states[index]),
        }
        transitions.append(transition)
    audits = []
    for audit in bound["audits"]:
        ordinal = audit["target_candidate_ordinal"]
        audits.append(
            {
                "decoded_position": audit["decoded_position"],
                "disposition": audit["disposition"]
                if ordinal is None
                else transitions[ordinal - 1]["disposition"],
                "instrument_id": audit["instrument_id"],
                "target_candidate_ordinal": ordinal,
                "target_transition_ordinal": ordinal,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
                "adapter_prefix_sha256": prefixes[audit["decoded_position"]],
            }
        )
    event = {
        "event_ordinal": 1,
        "closing_decoded_position": quote_position,
        "closing_target_transition_ordinal": 4,
        "ts_recv_ns": NOON,
        "target_positions": [quote_position],
        "trade_positions": [],
        "execution_capture_positions": [quote_position],
        "quote_ordinal": 1,
        "adapter_prefix_sha256": prefixes[quote_position],
    }
    event["event_sha256"] = digest(event)
    quote = {
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": quote_position,
        "ts_recv_ns": NOON,
        "bid": bid_price,
        "ask": ask_price,
        "bid_qty": 10,
        "ask_qty": 20,
        "prior_quote_gap_ns": 0,
        "ofi_generation": 2,
        "bid_depth5": [{"price": bid_price, "size": 10}],
        "ask_depth5": [{"price": ask_price, "size": 20}],
        "adapter_prefix_sha256": prefixes[quote_position],
    }
    quote["quote_sha256"] = digest(quote)
    publication = {
        "publication_ordinal": 1,
        "quote_ordinal": 1,
        "event_ordinal": 1,
        "decoded_position": quote_position,
        "ts_recv_ns": NOON,
        "adapter_prefix_sha256": prefixes[quote_position],
        "features": idle_features(),
    }
    publication["publication_sha256"] = digest(publication)
    state.update(
        ofi_generation=3, ofi_previous_quote_ordinal=None, ofi_first_ts_ns=None, window_closed=True
    )
    intervals = [
        {
            "start_ns": WARMUP,
            "timer_fired_ns": WARMUP + 5 * SECOND + 1,
            "end_ns": NOON,
            "recovered": True,
            "trigger_decoded_position": quote_position,
        },
        {
            "start_ns": NOON,
            "timer_fired_ns": NOON + 5 * SECOND + 1,
            "end_ns": END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    quality = {
        "target_records": 4,
        "snapshot_records": 2,
        "non_snapshot_records": 2,
        "event_after_receive": 0,
        "negative_send_delta": 0,
        "event_after_sending": 0,
        "clamped_delta": 0,
        "clock_disagreement_records": 0,
        "protected_disagreement_records": 0,
        "outside_disagreement_records": 0,
        "min_event_ahead_ns": None,
        "max_event_ahead_ns": None,
        "min_negative_delta_ns": None,
        "samples": [],
    }
    result = {
        "status": "constructed_typed_native_event_adapter_not_native_verification",
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "binding_protocol_sha256": digest(expected_binding_protocol()),
        "cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "fixture_sha256": digest(fixture_body),
        "fixture": fixture_body,
        "binding_assessment": bound,
        "audits": audits,
        "transitions": transitions,
        "events": [event],
        "quotes": [quote],
        "publications": [publication],
        "inactivity_intervals": intervals,
        "clock_quality": quality,
        "exceptional_clear_count": 0,
        "terminal_state": state,
        "authority_flags": dict.fromkeys(ADAPTER_FLAGS, False),
    }
    return result | {"assessment_sha256": digest(result)}


def state_object(adapter, body):
    values = dict(body)
    values["orders"] = tuple(
        adapter.OrderEntry(entry["order_id"], adapter.OrderState(**entry["state"]))
        for entry in body["orders"]
    )
    for name in ("bid_levels", "ask_levels"):
        values[name] = tuple(adapter.PriceLevel(**level) for level in body[name])
    for name in (
        "pending_target_positions",
        "pending_trade_positions",
        "execution_capture_positions",
        "history_quote_ordinals",
    ):
        values[name] = tuple(body[name])
    for name in (
        "flow_events",
        "ofi_events",
        "bid_depletions",
        "ask_depletions",
        "history_reloads",
        "bid_credits",
        "ask_credits",
    ):
        values[name] = tuple(tuple(entry) for entry in body[name])
    values["execution_events"] = tuple(
        (time, tuple(sorted(metrics.items()))) for time, metrics in body["execution_events"]
    )
    for name in ("execution_totals", "execution_audit"):
        values[name] = tuple(sorted(body[name].items()))
    return adapter.ReconstructedState(**values)


def assessment_object(adapter, fixture, body):
    values = dict(body)
    values["fixture"] = fixture
    values["binding_assessment"] = binding_assessment_object(
        fixture.payload_bundle, body["binding_assessment"]
    )
    values["audits"] = tuple(adapter.AdapterAudit(**value) for value in body["audits"])
    transitions = []
    for value in body["transitions"]:
        converted = dict(value)
        converted["before"] = (
            None if value["before"] is None else adapter.OrderState(**value["before"])
        )
        converted["after"] = (
            None if value["after"] is None else adapter.OrderState(**value["after"])
        )
        transitions.append(adapter.TargetTransition(**converted))
    values["transitions"] = tuple(transitions)
    values["events"] = tuple(
        adapter.EventWitness(
            **(
                value
                | {
                    "target_positions": tuple(value["target_positions"]),
                    "trade_positions": tuple(value["trade_positions"]),
                    "execution_capture_positions": tuple(value["execution_capture_positions"]),
                }
            )
        )
        for value in body["events"]
    )
    values["quotes"] = tuple(
        adapter.QuoteWitness(
            **(
                value
                | {
                    "bid_depth5": tuple(
                        adapter.PriceLevel(**level) for level in value["bid_depth5"]
                    ),
                    "ask_depth5": tuple(
                        adapter.PriceLevel(**level) for level in value["ask_depth5"]
                    ),
                }
            )
        )
        for value in body["quotes"]
    )
    values["publications"] = tuple(
        adapter.FeaturePublication(
            **(value | {"features": tuple(tuple(pair) for pair in value["features"])})
        )
        for value in body["publications"]
    )
    values["inactivity_intervals"] = tuple(
        adapter.InactivityInterval(**value) for value in body["inactivity_intervals"]
    )
    values["clock_quality"] = adapter.ClockQuality(
        **(
            body["clock_quality"]
            | {
                "samples": tuple(
                    adapter.ClockSample(**sample) for sample in body["clock_quality"]["samples"]
                )
            }
        )
    )
    values["terminal_state"] = state_object(adapter, body["terminal_state"])
    values["authority_flags"] = tuple((name, False) for name in ADAPTER_FLAGS)
    return adapter.AdapterAssessment(**values)


def independent_submitted(mode=False):
    adapter, fixture, pins, body = make_case(mode)
    expected = expected_idle_assessment(body)
    return adapter, fixture, pins, body, assessment_object(adapter, fixture, expected), expected


def call_verify(adapter, result, fixture, pins, expected):
    return adapter.verify(
        result, fixture, **pins, expected_assessment_sha256=expected["assessment_sha256"]
    )


def poison_slot(monkeypatch, cls, objects, field):
    original = cls.__getattribute__
    identities = {id(value) for value in objects}

    def read(self, name):
        if id(self) in identities and name == field:
            raise AssertionError("Deferred exact slot was traversed: " + field)
        return original(self, name)

    monkeypatch.setattr(cls, "__getattribute__", read)


def test_valid_metadata_reaches_raw_boundary_after_public_cursor_verification(monkeypatch):
    adapter, fixture, pins, _ = make_case()
    calls = []
    original = cursor.verify

    def verified(*args, **kwargs):
        calls.append("cursor.verify")
        return original(*args, **kwargs)

    monkeypatch.setattr(cursor, "verify", verified)
    poison_slot(
        monkeypatch, binding.MboPayload, fixture.payload_bundle.payloads[1:], "publisher_id"
    )
    with pytest.raises(AssertionError, match="publisher_id"):
        call_fixture(adapter, "replay", fixture, pins)
    assert calls, "Complete cursor verification must precede any raw-body traversal"


@pytest.mark.parametrize("api", ["fixture_sha256", "replay"])
@pytest.mark.parametrize("field", RAW_FIELDS)
def test_final_original_foreign_metadata_fault_precedes_each_raw_slot(monkeypatch, api, field):
    records = idle_records() + [raw_record(instrument=99, recv=-123, flags=255, sequence=5)]
    adapter, fixture, pins, _ = make_case(records=records)
    old = fixture.payload_bundle.cursor_fixture
    bad_item = replace(old.items[-1], kind="unexpected")
    bad_old = replace(old, items=old.items[:-1] + (bad_item,))
    bad = replace(fixture, payload_bundle=replace(fixture.payload_bundle, cursor_fixture=bad_old))
    poison_slot(monkeypatch, binding.MboPayload, bad.payload_bundle.payloads[1:], field)
    with pytest.raises(ValueError):
        call_fixture(adapter, api, bad, pins)


@pytest.mark.parametrize("side", ["original", "submitted"])
@pytest.mark.parametrize("field", RAW_FIELDS)
def test_final_submitted_authority_fault_precedes_each_raw_slot(monkeypatch, side, field):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    _, separate, _, _ = make_case()
    result = replace(
        result,
        fixture=separate,
        binding_assessment=replace(result.binding_assessment, bundle=separate.payload_bundle),
    )
    bad = replace(
        result, authority_flags=result.authority_flags[:-1] + (("training_allowed", True),)
    )
    objects = (
        fixture.payload_bundle.payloads[1:]
        if side == "original"
        else separate.payload_bundle.payloads[1:]
    )
    poison_slot(monkeypatch, binding.MboPayload, objects, field)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


@pytest.mark.parametrize("field", RAW_FIELDS)
def test_valid_original_metadata_raw_sentinels_are_genuinely_uncaught(monkeypatch, field):
    adapter, fixture, pins, _ = make_case()
    poison_slot(monkeypatch, binding.MboPayload, fixture.payload_bundle.payloads[1:], field)
    with pytest.raises(AssertionError, match=field):
        call_fixture(adapter, "replay", fixture, pins)


NUMERIC_FAMILIES = tuple(
    (family, field)
    for family, fields in (
        (
            "transition",
            (
                "order_id",
                "last_recv_before",
                "last_recv_after",
                "snapshot",
                "exceptional_closed_clear",
                "initialized_before",
                "initialized_after",
            ),
        ),
        ("order", ("side", "price", "size")),
        ("entry", ("order_id",)),
        ("level", ("price", "size")),
        ("event", ("ts_recv_ns",)),
        (
            "quote",
            (
                "ts_recv_ns",
                "bid",
                "ask",
                "bid_qty",
                "ask_qty",
                "prior_quote_gap_ns",
                "ofi_generation",
            ),
        ),
        ("publication", ("ts_recv_ns",)),
        ("interval", ("start_ns", "timer_fired_ns", "end_ns", "recovered")),
        ("quality", SCHEMAS["ClockQuality"][:-1]),
        ("assessment", ("exceptional_clear_count",)),
        (
            "state",
            (
                "initialized",
                "last_recv_ns",
                "cvd",
                "known_trades",
                "unknown_trades",
                "ofi_generation",
                "ofi_first_ts_ns",
                "ofi_total",
                "history_ofi_generation",
                "execution_last_ts_ns",
                "next_publication_ns",
                "watch_since_ns",
                "inactivity_start_ns",
                "window_closed",
            ),
        ),
    )
    for field in fields
)


def numerical_object(result, family):
    return {
        "transition": result.transitions[-1],
        "order": result.terminal_state.orders[0].state,
        "entry": result.terminal_state.orders[0],
        "level": result.quotes[0].bid_depth5[0],
        "event": result.events[0],
        "quote": result.quotes[0],
        "publication": result.publications[0],
        "interval": result.inactivity_intervals[-1],
        "quality": result.clock_quality,
        "state": result.terminal_state,
        "assessment": result,
    }[family]


def numerical_objects(result, family):
    if family == "transition":
        return result.transitions
    if family == "order":
        return tuple(entry.state for entry in result.terminal_state.orders) + tuple(
            value
            for transition in result.transitions
            for value in (transition.before, transition.after)
            if value is not None
        )
    if family == "entry":
        return result.terminal_state.orders
    if family == "level":
        return (
            result.terminal_state.bid_levels
            + result.terminal_state.ask_levels
            + tuple(
                level for quote in result.quotes for level in quote.bid_depth5 + quote.ask_depth5
            )
        )
    return {
        "event": result.events,
        "quote": result.quotes,
        "publication": result.publications,
        "interval": result.inactivity_intervals,
        "quality": (result.clock_quality,),
        "state": (result.terminal_state,),
        "assessment": (result,),
    }[family]


@pytest.mark.parametrize("family,field", NUMERIC_FAMILIES)
def test_final_authority_refuses_before_each_submitted_numeric_boolean_generation_slot(
    monkeypatch, family, field
):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    # Status and every preceding authority are valid. The final flag is the
    # contradiction, so a status-only gate followed by eager numeric reads dies.
    bad = replace(
        result, authority_flags=result.authority_flags[:-1] + (("training_allowed", True),)
    )
    objects = numerical_objects(bad, family)
    poison_slot(monkeypatch, type(objects[0]), objects, field)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


@pytest.mark.parametrize("field", SCHEMAS["ClockSample"][1:])
def test_final_authority_precedes_every_valid_reference_clock_sample_value(monkeypatch, field):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    sample = adapter.ClockSample(5, NOON, NOON - 1, 0, 128, 5, "N", True, -1, NOON)
    bad = replace(
        result,
        clock_quality=replace(result.clock_quality, samples=(sample,)),
        authority_flags=result.authority_flags[:-1] + (("training_allowed", True),),
    )
    poison_slot(monkeypatch, adapter.ClockSample, [sample], field)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


@pytest.mark.parametrize("field", RAW_FIELDS)
def test_valid_submitted_metadata_reaches_raw_boundary_after_nested_cursor_verify(
    monkeypatch, field
):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    _, separate, _, _ = make_case()
    result = replace(
        result,
        fixture=separate,
        binding_assessment=replace(result.binding_assessment, bundle=separate.payload_bundle),
    )
    calls = []
    original = cursor.verify

    def verified(*args, **kwargs):
        calls.append(id(args[0]))
        return original(*args, **kwargs)

    monkeypatch.setattr(cursor, "verify", verified)
    poison_slot(monkeypatch, binding.MboPayload, separate.payload_bundle.payloads[1:], field)
    with pytest.raises(AssertionError, match=field):
        call_verify(adapter, result, fixture, pins, expected)
    assert id(result.binding_assessment.cursor_assessment) in calls


def expected_two_event_assessment(fixture_body):
    """Complete idle noon event followed by END singleton with no protected quote."""
    baseline = copy.deepcopy(fixture_body)
    baseline["payload_bundle"]["payloads"].pop()
    baseline_cursor = baseline["payload_bundle"]["cursor_fixture"]
    baseline_cursor["items"].pop()
    baseline_cursor["declared_item_count"] -= 1
    result = expected_idle_assessment(baseline)
    bound = expected_binding_assessment(fixture_body["payload_bundle"])
    result.update(
        fixture=fixture_body, fixture_sha256=digest(fixture_body), binding_assessment=bound
    )
    final_bound = bound["audits"][-1]
    prefix = digest(
        {
            "adapter_protocol_sha256": digest(expected_protocol()),
            "context_sha256": digest(fixture_body["context"]),
            "binding_prefix_sha256": final_bound["bound_prefix_sha256"],
        }
    )
    result["audits"].append(
        {
            "decoded_position": 6,
            "disposition": "target_record",
            "instrument_id": 7,
            "target_candidate_ordinal": 5,
            "target_transition_ordinal": 5,
            "binding_prefix_sha256": final_bound["bound_prefix_sha256"],
            "adapter_prefix_sha256": prefix,
        }
    )
    result["terminal_state"]["last_recv_ns"] = END
    result["transitions"].append(
        {
            "decoded_position": 6,
            "target_transition_ordinal": 5,
            "disposition": "target_record",
            "snapshot": False,
            "exceptional_closed_clear": False,
            "order_id": 0,
            "before": None,
            "after": None,
            "initialized_before": True,
            "initialized_after": True,
            "last_recv_before": NOON,
            "last_recv_after": END,
            "event_ordinal": 2,
            "quote_ordinal": None,
            "publication_ordinal": None,
            "state_sha256": digest(result["terminal_state"]),
        }
    )
    event = {
        "event_ordinal": 2,
        "closing_decoded_position": 6,
        "closing_target_transition_ordinal": 5,
        "ts_recv_ns": END,
        "target_positions": [6],
        "trade_positions": [],
        "execution_capture_positions": [],
        "quote_ordinal": None,
        "adapter_prefix_sha256": prefix,
    }
    result["events"].append(event | {"event_sha256": digest(event)})
    result["inactivity_intervals"][-1]["trigger_decoded_position"] = 6
    result["clock_quality"]["target_records"] = 5
    result["clock_quality"]["non_snapshot_records"] = 3
    result.pop("assessment_sha256")
    return result | {"assessment_sha256": digest(result)}


@pytest.mark.parametrize("owner", ["event", "transition_quote", "transition_publication"])
def test_cross_owner_artifact_reference_refuses_before_original_raw(monkeypatch, owner):
    records = idle_records() + [raw_record(recv=END, sequence=5)]
    adapter, fixture, pins, body = make_case(records=records)
    forged = expected_two_event_assessment(body)
    if owner == "event":
        event = forged["events"][-1]
        event["quote_ordinal"] = 1
        event.pop("event_sha256")
        event["event_sha256"] = digest(event)
    elif owner == "transition_quote":
        forged["transitions"][-1]["quote_ordinal"] = 1
    else:
        forged["transitions"][-1]["publication_ordinal"] = 1
    # All caller pins and whole submitted digest are coherently recomputed.
    # Existing quote/publication1 belongs to position5/event1, never event2.
    forged.pop("assessment_sha256")
    forged["assessment_sha256"] = digest(forged)
    result = assessment_object(adapter, fixture, forged)
    poison_slot(
        monkeypatch, binding.MboPayload, fixture.payload_bundle.payloads[1:], "publisher_id"
    )
    with pytest.raises(ValueError):
        call_verify(adapter, result, fixture, pins, forged)


@pytest.mark.parametrize(
    "layer,name",
    [
        (layer, name)
        for layer, names in (
            ("adapter", ADAPTER_FLAGS),
            ("binding", BINDING_FLAGS),
            ("cursor", CURSOR_FLAGS),
        )
        for name in names
    ],
)
@pytest.mark.parametrize(
    "false_alias", [0, 0.0, True, None], ids=["int0", "float0", "true", "none"]
)
def test_every_authority_is_literal_false_before_raw_traversal(
    monkeypatch, layer, name, false_alias
):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    if layer == "adapter":
        flags = tuple(
            (key, false_alias if key == name else value) for key, value in result.authority_flags
        )
        result = replace(result, authority_flags=flags)
    elif layer == "binding":
        flags = tuple(
            (key, false_alias if key == name else value)
            for key, value in result.binding_assessment.authority_flags
        )
        result = replace(
            result, binding_assessment=replace(result.binding_assessment, authority_flags=flags)
        )
    else:
        old = result.binding_assessment.cursor_assessment
        flags = tuple(
            (key, false_alias if key == name else value) for key, value in old.authority_flags
        )
        result = replace(
            result,
            binding_assessment=replace(
                result.binding_assessment, cursor_assessment=replace(old, authority_flags=flags)
            ),
        )
    poison_slot(
        monkeypatch, binding.MboPayload, fixture.payload_bundle.payloads[1:], "publisher_id"
    )
    with pytest.raises(ValueError):
        call_verify(adapter, result, fixture, pins, expected)


def book_apply(book, **raw):
    book.apply(binding.MboPayload(**raw_record(**raw)))


def test_required_strict_book_leaf_is_available_before_constructor_use():
    adapter = adapter_module()
    assert callable(getattr(adapter, "_Book", None)), "Required strict book behavior is missing"
    book = adapter._Book()
    assert book.initialized is False
    assert book.orders == {}
    assert book.levels == {"A": {}, "B": {}}
    assert book.best("A") is None and book.best("B") is None


def test_required_clock_audit_leaf_is_available_before_constructor_use():
    adapter = adapter_module()
    assert callable(getattr(adapter, "_ClockAudit", None)), (
        "Required clock-audit behavior is missing"
    )
    quality = adapter._ClockAudit().quality()
    assert quality == adapter.ClockQuality(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, None, None, None, ())


@pytest.mark.parametrize("action", ["T", "F", "N"])
def test_book_noops_do_not_manufacture_initialization_or_orders(action):
    adapter = adapter_module()
    book = adapter._Book()
    book_apply(book, action=action, side="?", size=0, price=9_223_372_036_854_775_807)
    assert book.initialized is False
    assert book.orders == {}
    assert book.levels == {"A": {}, "B": {}}


def initialized_book():
    book = adapter_module()._Book()
    book_apply(book, action="R", flags=0)
    return book


@pytest.mark.parametrize("snapshot", [0, 32, 160])
def test_order_updates_before_actual_reset_are_refused_even_snapshot(snapshot):
    book = adapter_module()._Book()
    with pytest.raises(ValueError):
        book_apply(book, action="A", side="B", oid=11, price=1_000_000, size=10, flags=snapshot)


def test_strict_book_complete_add_modify_partial_full_cancel_and_reset_states():
    adapter = adapter_module()
    book = initialized_book()
    assert book.initialized is True
    book_apply(book, action="A", side="B", oid=11, price=1_000_000, size=10)
    book_apply(book, action="A", side="B", oid=12, price=1_000_000, size=20)
    book_apply(book, action="A", side="A", oid=21, price=1_100_000, size=20)
    assert book.orders == {
        11: adapter.OrderState("B", 1_000_000, 10),
        12: adapter.OrderState("B", 1_000_000, 20),
        21: adapter.OrderState("A", 1_100_000, 20),
    }
    assert book.levels == {"B": {1_000_000: 30}, "A": {1_100_000: 20}}
    assert book.best("B") == 1_000_000 and book.best("A") == 1_100_000
    book_apply(book, action="M", side="B", oid=11, price=950_000, size=5)
    assert book.orders[11] == adapter.OrderState("B", 950_000, 5)
    assert book.levels["B"] == {1_000_000: 20, 950_000: 5}
    book_apply(book, action="C", side="B", oid=12, price=1_000_000, size=20)
    assert 12 not in book.orders
    assert book.best("B") == 950_000
    book_apply(book, action="C", side="B", oid=11, price=950_000, size=2)
    assert book.orders[11] == adapter.OrderState("B", 950_000, 3)
    assert book.levels["B"] == {950_000: 3}
    book_apply(book, action="R", side="?", oid=11, price=-123, size=0, flags=0)
    assert book.initialized is True
    assert book.orders == {} and book.levels == {"A": {}, "B": {}}
    assert book.best("A") is None and book.best("B") is None


@pytest.mark.parametrize("price", [-1_000_001, -1, 0, 1, 1_000_001])
def test_standing_order_price_has_no_invented_absolute_tick_grid_or_positive_rule(price):
    book = initialized_book()
    book_apply(book, action="A", side="B", oid=11, price=price, size=10)
    assert book.best("B") == price
    assert book.orders[11] == adapter_module().OrderState("B", price, 10)


def test_aggregate_level_quantity_is_not_bounded_as_one_raw_u64_field():
    book = initialized_book()
    for oid in (11, 12):
        book_apply(
            book, action="A", side="B", oid=oid, price=1_000_000, size=18_446_744_073_709_551_615
        )
    assert book.levels["B"][1_000_000] == 36_893_488_147_419_103_230


@pytest.mark.parametrize(
    "change",
    [
        {"action": "A", "oid": 11},
        {"action": "M", "oid": 99},
        {"action": "C", "oid": 99},
        {"action": "M", "side": "A"},
        {"action": "C", "side": "A"},
        {"action": "C", "price": 1_050_000},
        {"action": "C", "size": 11},
        {"action": "A", "oid": 99, "side": "N"},
        {"action": "A", "oid": 99, "price": 9_223_372_036_854_775_807},
        {"action": "M", "size": 0},
        {"action": "C", "size": 0},
        {"action": "A", "oid": 99, "size": 0},
        {"action": "X", "oid": 99},
        {"action": "A", "oid": 99, "flags": 64},
        {"action": "A", "oid": 99, "flags": 16},
    ],
)
def test_strict_book_faults_refuse_instead_of_repaired_or_unknown_order_adoption(change):
    book = initialized_book()
    book_apply(book, action="A", side="B", oid=11, price=1_000_000, size=10)
    arguments = {"action": "M", "side": "B", "oid": 11, "price": 1_000_000, "size": 10} | change
    with pytest.raises(ValueError):
        book_apply(book, **arguments)


@pytest.mark.parametrize("action", ["T", "F", "N"])
def test_book_noop_retains_existing_order_prestate(action):
    book = initialized_book()
    book_apply(book, action="A", side="B", oid=11, price=1_000_000, size=10)
    book_apply(book, action=action, side="A", oid=11, price=-5, size=0)
    assert book.orders[11] == adapter_module().OrderState("B", 1_000_000, 10)
    assert book.levels == {"A": {}, "B": {1_000_000: 10}}


@pytest.mark.parametrize("recv", [WARMUP, NOON, END - 1])
@pytest.mark.parametrize("change", [{"ts_event": "ahead"}, {"ts_in_delta": -1}])
def test_clock_audit_refuses_protected_ahead_or_negative_delta(recv, change):
    audit = adapter_module()._ClockAudit()
    changes = {key: recv + 1 if value == "ahead" else value for key, value in change.items()}
    with pytest.raises(ValueError):
        audit.observe(binding.MboPayload(**raw_record(recv=recv, **changes)), False, 2)


@pytest.mark.parametrize("recv", [DAY + 1, WARMUP - 1, END, DAY + 86_400 * SECOND - 1])
def test_clock_disagreement_outside_protected_interval_is_audited_not_corrected(recv):
    adapter = adapter_module()
    audit = adapter._ClockAudit()
    raw = raw_record(recv=recv, ts_event=recv + 3, ts_in_delta=-4, sequence=9)
    audit.observe(binding.MboPayload(**raw), False, 2)
    assert audit.quality() == adapter.ClockQuality(
        1,
        0,
        1,
        1,
        1,
        0,
        0,
        1,
        0,
        1,
        3,
        3,
        -4,
        (adapter.ClockSample(2, recv, recv + 3, -4, 128, 9, "N", False, 3, recv + 4),),
    )


def test_snapshot_reset_clock_is_counted_but_never_compared():
    adapter = adapter_module()
    audit = adapter._ClockAudit()
    audit.observe(
        binding.MboPayload(
            **raw_record(action="R", recv=NOON, flags=32, ts_event=NOON + 100, ts_in_delta=-10)
        ),
        True,
        2,
    )
    assert audit.quality() == adapter.ClockQuality(
        1, 1, 0, 0, 0, 0, 0, 0, 0, 0, None, None, None, ()
    )


def test_event_after_sending_and_positive_clamped_delta_are_audit_only():
    adapter = adapter_module()
    audit = adapter._ClockAudit()
    audit.observe(
        binding.MboPayload(**raw_record(recv=NOON, ts_event=NOON - 1, ts_in_delta=2)), False, 2
    )
    audit.observe(
        binding.MboPayload(**raw_record(recv=NOON, ts_event=NOON - 2**31, ts_in_delta=2**31 - 1)),
        False,
        3,
    )
    assert audit.quality() == adapter.ClockQuality(
        2, 0, 2, 0, 0, 1, 1, 0, 0, 0, None, None, None, ()
    )


def test_clock_full_counts_extrema_and_sending_arithmetic_preserve_unclamped_values():
    adapter = adapter_module()
    audit = adapter._ClockAudit()
    specifications = [
        (WARMUP - 1, WARMUP + 2, -4),
        (END, END + 2, 10),
        (END + 1, END, -(2**31)),
        (END + 2, END + 1, 2**31 - 1),
    ]
    samples = []
    for index, (recv, event, delta) in enumerate(specifications, 2):
        audit.observe(
            binding.MboPayload(
                **raw_record(recv=recv, ts_event=event, ts_in_delta=delta, sequence=index)
            ),
            False,
            index,
        )
        if index != 5:
            samples.append(
                adapter.ClockSample(
                    index, recv, event, delta, 128, index, "N", False, event - recv, recv - delta
                )
            )
    assert audit.quality() == adapter.ClockQuality(
        4, 0, 4, 2, 2, 2, 2, 3, 0, 3, 2, 3, -(2**31), tuple(samples)
    )


def test_clock_retains_first_eight_disagreements_and_all_later_counts():
    adapter = adapter_module()
    audit = adapter._ClockAudit()
    for index in range(12):
        recv = DAY + index + 1
        audit.observe(
            binding.MboPayload(**raw_record(recv=recv, ts_event=recv + 1, sequence=index)),
            False,
            index + 2,
        )
    samples = tuple(
        adapter.ClockSample(
            index + 2,
            DAY + index + 1,
            DAY + index + 2,
            0,
            128,
            index,
            "N",
            False,
            1,
            DAY + index + 1,
        )
        for index in range(8)
    )
    assert audit.quality() == adapter.ClockQuality(
        12, 0, 12, 12, 0, 12, 0, 12, 0, 12, 1, 1, None, samples
    )


def leaf_quote(time=NOON, *, bid=1_000_000, ask=1_100_000, bq=10, aq=20, ordinal=1):
    adapter = adapter_module()
    return adapter.QuoteWitness(
        ordinal,
        ordinal,
        ordinal + 1,
        time,
        bid,
        ask,
        bq,
        aq,
        0,
        1,
        (adapter.PriceLevel(bid, bq),),
        (adapter.PriceLevel(ask, aq),),
        "a" * 64,
        "b" * 64,
    )


@pytest.mark.parametrize("name", ["_Flow", "_Ofi", "_History", "_Captured", "_Execution"])
def test_required_numeric_leaf_callable_exists_before_construction(name):
    assert callable(getattr(adapter_module(), name, None)), (
        "Required numerical leaf is missing: " + name
    )


def test_flow_uses_completion_clock_known_unknown_counts_and_never_counts_fill_twice():
    flow = adapter_module()._Flow()
    for side, size in (("B", 5), ("A", 3), ("?", 7)):
        flow.add(NOON, binding.MboPayload(**raw_record("T", side, recv=WARMUP - SECOND, size=size)))
    flow.add(NOON, binding.MboPayload(**raw_record("F", "A", size=100)))
    assert list(flow.events) == [(NOON, 5, 1, 0), (NOON, -3, 1, 0), (NOON, 0, 0, 1)]
    assert (flow.cvd, flow.known, flow.unknown) == (2, 2, 1)
    flow.expire(NOON + 5 * SECOND)
    assert len(flow.events) == 3 and (flow.cvd, flow.known, flow.unknown) == (2, 2, 1)
    flow.expire(NOON + 5 * SECOND + 1)
    assert list(flow.events) == [] and (flow.cvd, flow.known, flow.unknown) == (0, 0, 0)


@pytest.mark.parametrize(
    "side,signed,known,unknown", [("B", 0, 1, 0), ("A", 0, 1, 0), ("N", 0, 0, 1)]
)
def test_flow_does_not_invent_execution_trade_price_or_positive_size_validation(
    side, signed, known, unknown
):
    flow = adapter_module()._Flow()
    flow.add(NOON, binding.MboPayload(**raw_record("T", side, price=-1, size=0)))
    assert list(flow.events) == [(NOON, signed, known, unknown)]


@pytest.mark.parametrize(
    "bid,ask,bq,aq,increment",
    [
        (1_000_000, 1_100_000, 10, 20, 0),
        (1_000_000, 1_100_000, 12, 18, 4),
        (1_050_000, 1_100_000, 5, 20, 5),
        (950_000, 1_100_000, 15, 20, -10),
        (1_000_000, 1_050_000, 10, 7, -7),
        (1_000_000, 1_150_000, 10, 7, 20),
    ],
)
def test_ofi_exact_bid_ask_comparison_arithmetic(bid, ask, bq, aq, increment):
    window = adapter_module()._Ofi()
    first = leaf_quote()
    second = leaf_quote(NOON + SECOND, bid=bid, ask=ask, bq=bq, aq=aq, ordinal=2)
    window.observe(first)
    window.observe(second)
    assert window.first_ts == NOON and window.previous is second
    assert list(window.events) == [(NOON + SECOND, increment)] and window.total == increment


def test_ofi_strict_expiry_preserves_previous_and_original_first_timestamp():
    window = adapter_module()._Ofi()
    first, second = leaf_quote(), leaf_quote(NOON + SECOND, bq=12, aq=18, ordinal=2)
    window.observe(first)
    window.observe(second)
    window.expire(NOON + 6 * SECOND)
    assert window.total == 4 and list(window.events) == [(NOON + SECOND, 4)]
    window.expire(NOON + 6 * SECOND + 1)
    assert window.total == 0 and list(window.events) == []
    assert window.previous is second and window.first_ts == NOON


def depth_book():
    book = initialized_book()
    for oid, side, price, size in (
        (11, "B", 1_000_000, 10),
        (12, "A", 1_100_000, 20),
        (14, "B", 950_000, 5),
        (15, "A", 1_150_000, 10),
    ):
        book_apply(book, action="A", oid=oid, side=side, price=price, size=size)
    return book


def assert_exact_feature_dict(actual, values, names):
    expected = dict(zip(names, values, strict=True))
    assert tuple(actual) == tuple(names)
    assert actual == expected
    assert canonical(actual) == canonical(expected)
    assert {name: type(value) for name, value in actual.items()} == {
        name: type(value) for name, value in expected.items()
    }


def test_history_exact_fifteen_features_depth_depletion_reload_and_int_float_travel():
    history, book = adapter_module()._History(), depth_book()
    history.observe(leaf_quote())
    single = (
        math.log1p(15),
        math.log1p(30),
        -15 / 45,
        10 / 15,
        20 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0,
        math.log1p(1),
        0.0,
        0.0,
        5 / 30,
        0.0,
    )
    assert_exact_feature_dict(history.features(book, 5), single, FEATURE_NAMES[8:23])
    book_apply(book, action="M", side="B", oid=11, price=1_000_000, size=8)
    book_apply(book, action="M", side="A", oid=12, price=1_100_000, size=18)
    history.observe(leaf_quote(NOON + SECOND, bq=8, aq=18, ordinal=2))
    assert list(history.depletions[0]) == [[NOON + SECOND, 2]]
    assert list(history.depletions[1]) == [[NOON + SECOND, 2]]
    second = (
        math.log1p(13),
        math.log1p(28),
        -15 / 41,
        8 / 13,
        18 / 28,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        math.log1p(2),
        0.0,
        0.0,
        5 / 26,
        0.0,
    )
    assert_exact_feature_dict(history.features(book, 5), second, FEATURE_NAMES[8:23])
    book_apply(book, action="M", side="B", oid=11, price=1_000_000, size=11)
    book_apply(book, action="M", side="A", oid=12, price=1_100_000, size=20)
    history.observe(leaf_quote(NOON + 2 * SECOND, bq=11, aq=20, ordinal=3))
    assert list(history.depletions[0]) == [] and list(history.depletions[1]) == []
    assert list(history.reloads) == [(NOON, 0, 0), (NOON + SECOND, 0, 0), (NOON + 2 * SECOND, 2, 2)]
    third = (
        math.log1p(16),
        math.log1p(30),
        -14 / 46,
        11 / 16,
        20 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        math.log1p(3),
        2 / 31,
        2 / 31,
        5 / 31,
        0.0,
    )
    assert_exact_feature_dict(history.features(book, 5), third, FEATURE_NAMES[8:23])


def test_history_changed_top_price_clears_that_side_depletion_without_authenticating_reload():
    history, book = adapter_module()._History(), depth_book()
    history.observe(leaf_quote())
    book_apply(book, action="M", side="B", oid=11, price=1_000_000, size=8)
    history.observe(leaf_quote(NOON + SECOND, bq=8, ordinal=2))
    book_apply(book, action="M", side="B", oid=11, price=1_050_000, size=8)
    history.observe(leaf_quote(NOON + 2 * SECOND, bid=1_050_000, bq=8, ordinal=3))
    assert list(history.depletions[0]) == []
    values = history.features(book, 5)
    assert values["mid_change_5s_ticks"] == 0.5
    assert values["mid_range_5s_ticks"] == 0.5
    assert values["mid_travel_5s_ticks"] == 0.5
    assert values["bid_span5_ticks"] == 2.0
    assert values["normalized_bid_reload_5s"] == 0.0
    assert values["buy_absorption_proxy_5s"] == 5 / (28 * 1.5)


def test_history_strict_five_second_quote_reload_cutoff_and_regression():
    history, book = adapter_module()._History(), depth_book()
    history.observe(leaf_quote())
    history.observe(leaf_quote(NOON + 5 * SECOND, ordinal=2))
    assert len(history.quotes) == 2 and len(history.reloads) == 2
    history.observe(leaf_quote(NOON + 5 * SECOND + 1, ordinal=3))
    assert [quote.quote_ordinal for quote in history.quotes] == [2, 3]
    assert list(history.reloads) == [(NOON + 5 * SECOND, 0, 0), (NOON + 5 * SECOND + 1, 0, 0)]
    assert type(history.features(book, 0)["mid_travel_5s_ticks"]) is float
    with pytest.raises(ValueError):
        history.observe(leaf_quote(NOON, ordinal=4))


def simple_book():
    book = initialized_book()
    book_apply(book, action="A", side="B", oid=11, price=1_000_000, size=10)
    book_apply(book, action="A", side="A", oid=12, price=1_100_000, size=20)
    return book


def captured(book, **kwargs):
    return adapter_module()._Captured.capture(binding.MboPayload(**raw_record(**kwargs)), book)


def prime_execution(observer, book, time=NOON - SECOND):
    quote = leaf_quote(time)
    observer.complete([captured(book, recv=time)], None, quote, book)
    return quote


def test_capture_retains_exact_preupdate_order_state_not_after_mutation():
    adapter, book = adapter_module(), simple_book()
    before = captured(book, action="C", side="A", oid=12, price=1_100_000, size=4)
    book_apply(book, action="C", side="A", oid=12, price=1_100_000, size=4)
    assert before == adapter._Captured(
        NOON, "C", "A", 1_100_000, 4, 12, adapter.OrderState("A", 1_100_000, 20)
    )
    assert book.orders[12] == adapter.OrderState("A", 1_100_000, 16)
    with pytest.raises(FrozenInstanceError):
        before.size = 100


def test_execution_exact_fourteen_features_linked_reload_net_refresh_overlap_and_touched_zero():
    adapter, book = adapter_module(), simple_book()
    observer = adapter._Execution()
    previous = prime_execution(observer, book)
    records = []
    for arguments in (
        {"action": "T", "side": "B", "oid": 900, "price": 1_100_000, "size": 4},
        {"action": "F", "side": "A", "oid": 12, "price": 1_100_000, "size": 4},
        {"action": "C", "side": "A", "oid": 12, "price": 1_100_000, "size": 4},
        {"action": "A", "side": "A", "oid": 13, "price": 1_100_000, "size": 2},
        {"action": "M", "side": "A", "oid": 12, "price": 1_100_000, "size": 18},
        {"action": "M", "side": "B", "oid": 11, "price": 1_000_000, "size": 8},
        {"action": "N"},
    ):
        records.append(captured(book, **arguments))
        book_apply(book, **arguments)
    quote = leaf_quote(bq=8, aq=20, ordinal=2)
    observer.complete(records, previous, quote, book)
    values = (
        0.0,
        0.0,
        0.0,
        2 / 28,
        0.0,
        0.0,
        0.0,
        4 / 28,
        4 / 28,
        4 / 28,
        0.0,
        2 / 28,
        2 / 28,
        2 / 28,
    )
    assert_exact_feature_dict(observer.features(quote), values, FEATURE_NAMES[23:])
    metrics = {
        ("A", "passive"): 4,
        ("A", "held_top_passive"): 4,
        ("A", "linked_decrease"): 4,
        ("A", "other_id_reload"): 2,
        ("A", "same_id_reload"): 2,
        ("A", "same_id_net_refresh"): 2,
        ("B", "unlinked_decrease"): 2,
    }
    assert dict(observer.totals) == metrics
    assert list(observer.events) == [(NOON, metrics)]
    assert list(observer.credits["A"]) == [] and list(observer.credits["B"]) == []
    assert dict(observer.audit) == {
        "temporal_resets": 1,
        "completed_events": 2,
        "trade_B_volume": 4,
        "fill_matched_passive_records": 1,
        "fill_matched_passive_volume": 4,
        "fill_above_displayed_volume": 0,
        "A_passive_volume": 4,
        "A_held_top_passive_volume": 4,
        "A_linked_decrease_volume": 4,
        "A_other_id_reload_volume": 2,
        "A_same_id_reload_volume": 2,
        "A_same_id_net_refresh_volume": 2,
        "B_unlinked_decrease_volume": 2,
    }


@pytest.mark.parametrize(
    "reason",
    [
        "without_trade",
        "unknown_aggressor",
        "aggressor",
        "unknown_side",
        "price_mismatch",
        "unmatched_book",
        "matched_passive",
    ],
)
def test_execution_fill_reason_precedence_is_exact_and_nonmatched_volume_is_not_inferred(reason):
    book, observer = simple_book(), adapter_module()._Execution()
    previous = prime_execution(observer, book)
    trade = {"action": "T", "side": "B", "oid": 900, "price": 1_100_000, "size": 4}
    fill = {"action": "F", "side": "A", "oid": 12, "price": 1_100_000, "size": 2}
    if reason == "unknown_aggressor":
        trade["side"] = "?"
    elif reason == "aggressor":
        trade["oid"] = 12
    elif reason == "unknown_side":
        fill["side"] = "N"
    elif reason == "price_mismatch":
        fill["price"] = 1_150_000
    elif reason == "unmatched_book":
        fill["oid"] = 99
    records = [] if reason == "without_trade" else [captured(book, **trade)]
    records.append(captured(book, **fill))
    observer.complete(records, previous, leaf_quote(ordinal=2), book)
    assert observer.audit[f"fill_{reason}_records"] == 1
    assert observer.audit[f"fill_{reason}_volume"] == 2
    expected = 2 if reason == "matched_passive" else 0
    assert observer.features(leaf_quote())["ask_passive_5s"] == expected / 30
    assert observer.features(leaf_quote())["ask_held_top_passive_5s"] == expected / 30


@pytest.mark.parametrize(
    "fault", ["zero_trade", "zero_price", "off_grid_trade", "zero_fill", "over_trade"]
)
def test_execution_trade_fill_validation_and_matched_summary_cap(fault):
    book, observer = simple_book(), adapter_module()._Execution()
    previous = prime_execution(observer, book)
    trade = {"action": "T", "side": "B", "oid": 900, "price": 1_100_000, "size": 4}
    fill = {"action": "F", "side": "A", "oid": 12, "price": 1_100_000, "size": 2}
    if fault == "zero_trade":
        trade["size"] = 0
    elif fault == "zero_price":
        trade["price"] = 0
    elif fault == "off_grid_trade":
        trade["price"] = 1_100_001
    elif fault == "zero_fill":
        fill["size"] = 0
    else:
        fill["size"] = 5
    with pytest.raises(ValueError):
        observer.complete(
            [captured(book, **trade), captured(book, **fill)], previous, leaf_quote(ordinal=2), book
        )


@pytest.mark.parametrize("gap,held,resets", [(5 * SECOND, 2 / 30, 1), (5 * SECOND + 1, 0.0, 2)])
def test_execution_temporal_gap_equality_vs_plus_one_nanosecond(gap, held, resets):
    book, observer = simple_book(), adapter_module()._Execution()
    previous = prime_execution(observer, book, NOON - gap)
    records = [
        captured(book, action="T", side="B", oid=900, price=1_100_000, size=2),
        captured(book, action="F", side="A", oid=12, price=1_100_000, size=2),
    ]
    quote = leaf_quote(ordinal=2)
    observer.complete(records, previous, quote, book)
    assert observer.features(quote)["ask_held_top_passive_5s"] == held
    assert observer.audit["temporal_resets"] == resets


@pytest.mark.parametrize("span,excluded", [(5 * SECOND, False), (5 * SECOND + 1, True)])
def test_stale_capture_span_equality_does_not_hide_invalid_trade_but_plus_one_excludes(
    span, excluded
):
    book, observer = simple_book(), adapter_module()._Execution()
    previous = prime_execution(observer, book, NOON - 6 * SECOND)
    records = [
        captured(book, action="T", side="B", recv=NOON - span, price=0, size=0),
        captured(book, recv=NOON),
    ]
    if excluded:
        observer.complete(records, previous, leaf_quote(ordinal=2), book)
        assert observer.audit["stale_spanning_events_excluded"] == 1
        assert observer.audit["completed_events"] == 1
    else:
        with pytest.raises(ValueError):
            observer.complete(records, previous, leaf_quote(ordinal=2), book)


def test_execution_expiry_retains_touched_zero_totals_without_temporal_reset():
    book, observer = simple_book(), adapter_module()._Execution()
    previous = prime_execution(observer, book)
    quote = leaf_quote(ordinal=2)
    records = [
        captured(book, action="T", side="B", oid=900, price=1_100_000, size=2),
        captured(book, action="F", side="A", oid=12, price=1_100_000, size=2),
    ]
    observer.complete(records, previous, quote, book)
    middle = leaf_quote(NOON + SECOND, ordinal=3)
    observer.complete([captured(book, recv=NOON + SECOND)], quote, middle, book)
    final = leaf_quote(NOON + 5 * SECOND + 1, ordinal=4)
    observer.complete([captured(book, recv=final.ts_recv_ns)], middle, final, book)
    assert dict(observer.totals) == {("A", "passive"): 0, ("A", "held_top_passive"): 0}
    assert list(observer.events) == []
    assert observer.audit["temporal_resets"] == 1 and observer.audit["completed_events"] == 4


OLD_SCHEMAS = {
    "MappingInterval": ("start_date", "end_date", "instrument_symbol"),
    "MappingGroup": ("contract", "intervals"),
    "DeclaredHeader": (
        "dataset",
        "schema",
        "symbols",
        "not_found",
        "start_ns",
        "end_ns",
        "mappings",
    ),
    "DecodedItem": ("decoded_position", "kind", "instrument_id", "payload_sha256"),
    "CursorFixture": (
        "fixture_id",
        "source_session",
        "utc_date",
        "contract",
        "header",
        "asserted_member_sha256",
        "declared_item_count",
        "items",
    ),
    "CursorAudit": (
        "decoded_position",
        "disposition",
        "instrument_id",
        "target_candidate_ordinal",
        "item_sha256",
        "prefix_sha256",
    ),
    "CursorAssessment": (
        "status",
        "protocol_sha256",
        "fixture_sha256",
        "fixture",
        "mapped_instrument_id",
        "decoded_item_count",
        "target_candidate_count",
        "foreign_count",
        "audits",
        "authority_flags",
        "assessment_sha256",
    ),
    "PayloadContext": ("codec_id", "schema_version", "ts_out_mode"),
    "MboPayload": RAW_FIELDS,
    "PayloadBundle": ("context", "cursor_fixture", "payloads"),
    "PayloadAudit": (
        "decoded_position",
        "disposition",
        "instrument_id",
        "target_candidate_ordinal",
        "payload_sha256",
        "cursor_item_sha256",
        "cursor_prefix_sha256",
        "bound_prefix_sha256",
    ),
    "BindingAssessment": (
        "status",
        "protocol_sha256",
        "context_sha256",
        "cursor_protocol_sha256",
        "cursor_fixture_sha256",
        "bundle_sha256",
        "bundle",
        "cursor_assessment",
        "audits",
        "authority_flags",
        "assessment_sha256",
    ),
}


def literal_actual_projection(value):
    """Read ACTUAL output using independently literal field lists, not reflected schemas.

    Expected bodies come from the separate scripted oracles; this function never
    produces expectations or invokes production serializers/protocol/replay.
    """
    if value is None or type(value) in (str, int, float, bool):
        return value
    if type(value) is tuple:
        return [literal_actual_projection(item) for item in value]
    adapter = adapter_module()
    for name, fields in (SCHEMAS | OLD_SCHEMAS).items():
        owner = adapter if name in SCHEMAS else cursor if hasattr(cursor, name) else binding
        if type(value) is not getattr(owner, name):
            continue
        body = {}
        for field in fields:
            observed = getattr(value, field)
            if field in ("authority_flags", "execution_totals", "execution_audit"):
                assert type(observed) is tuple
                assert all(type(pair) is tuple and len(pair) == 2 for pair in observed)
                assert [pair[0] for pair in observed] == sorted(pair[0] for pair in observed)
                body[field] = {key: literal_actual_projection(item) for key, item in observed}
            elif field == "execution_events":
                assert type(observed) is tuple
                body[field] = [
                    [time, {key: literal_actual_projection(item) for key, item in pairs}]
                    for time, pairs in observed
                ]
            else:
                body[field] = literal_actual_projection(observed)
        return body
    raise AssertionError("Unexpected output type rather than exact contracted primitive/record")


def assert_complete_assessment(adapter, result, fixture, expected):
    assert type(result) is adapter.AdapterAssessment
    assert result == assessment_object(adapter, fixture, expected)
    assert canonical(literal_actual_projection(result)) == canonical(expected)
    assert result.assessment_sha256 == expected["assessment_sha256"]
    assert result.authority_flags == tuple((name, False) for name in ADAPTER_FLAGS)


def test_required_complete_fixture_reconstruction_matches_independent_idle_body():
    adapter, fixture, pins, body = make_case()
    assert call_fixture(adapter, "fixture_sha256", fixture, pins) == digest(body)


def test_required_complete_replay_matches_full_independent_idle_assessment():
    adapter, fixture, pins, body = make_case()
    expected = expected_idle_assessment(body)
    assert_complete_assessment(
        adapter, call_fixture(adapter, "replay", fixture, pins), fixture, expected
    )


def test_required_complete_verification_accepts_independent_full_idle_assessment():
    adapter, fixture, pins, _, result, expected = independent_submitted()
    assert call_verify(adapter, result, fixture, pins, expected) is None


@pytest.mark.parametrize("mode", [False, True])
@pytest.mark.parametrize("mapped", [7, 101, 4_294_967_295])
def test_complete_idle_pipeline_has_exact_all_fields_hashes_modes_and_non_one_ids(mode, mapped):
    adapter, fixture, pins, body = make_case(mode, mapped=mapped)
    expected = expected_idle_assessment(body, mapped)
    assert call_fixture(adapter, "fixture_sha256", fixture, pins) == digest(body)
    result = call_fixture(adapter, "replay", fixture, pins)
    assert_complete_assessment(adapter, result, fixture, expected)
    submitted = assessment_object(adapter, fixture, expected)
    assert call_verify(adapter, submitted, fixture, pins, expected) is None
    assert type(dict(result.publications[0].features)["mid_travel_5s_ticks"]) is int


def nontrivial_records(mode=False):
    before = WARMUP - SECOND
    records = [raw_record("R", recv=before, flags=0, mode=mode)]
    for index, (oid, side, price, size) in enumerate(
        (
            (11, "B", 1_000_000, 10),
            (12, "A", 1_100_000, 20),
            (14, "B", 950_000, 5),
            (15, "A", 1_150_000, 10),
        ),
        1,
    ):
        records.append(
            raw_record(
                "A",
                side,
                recv=before + index,
                oid=oid,
                price=price,
                size=size,
                flags=32,
                mode=mode,
                sequence=index + 1,
            )
        )
    records.append(raw_record(recv=NOON - SECOND, mode=mode, sequence=6))
    specifications = (
        ("T", "B", 900, 1_100_000, 4),
        ("F", "A", 12, 1_100_000, 4),
        ("C", "A", 12, 1_100_000, 4),
        ("A", "A", 13, 1_100_000, 2),
        ("M", "A", 12, 1_100_000, 18),
        ("M", "B", 11, 1_000_000, 8),
        ("N", "N", 0, 0, 0),
    )
    for sequence, (action, side, oid, price, size) in enumerate(specifications, 7):
        records.append(
            raw_record(
                action,
                side,
                oid=oid,
                price=price,
                size=size,
                flags=128 if action == "N" else 0,
                mode=mode,
                sequence=sequence,
            )
        )
    return records


def nontrivial_features():
    values = (
        math.log1p(8),
        math.log1p(20),
        -12 / 28,
        -4 / 28,
        8 / 28,
        math.log1p(1),
        0.0,
        math.log1p(SECOND / 1_000_000),
        math.log1p(13),
        math.log1p(30),
        -17 / 43,
        8 / 13,
        20 / 30,
        1.0,
        1.0,
        0.0,
        0.0,
        0.0,
        math.log1p(2),
        0.0,
        0.0,
        4 / 28,
        0.0,
        0.0,
        0.0,
        0.0,
        2 / 28,
        0.0,
        0.0,
        0.0,
        4 / 28,
        4 / 28,
        4 / 28,
        0.0,
        2 / 28,
        2 / 28,
        2 / 28,
    )
    return [[name, value] for name, value in zip(FEATURE_NAMES, values, strict=True)]


def oracle_book_projection(orders):
    """Only the test's hand-scripted order dictionary, never production _Book."""
    entries = [{"order_id": oid, "state": copy.deepcopy(orders[oid])} for oid in sorted(orders)]
    levels = {"A": {}, "B": {}}
    for order in orders.values():
        levels[order["side"]][order["price"]] = (
            levels[order["side"]].get(order["price"], 0) + order["size"]
        )
    bids = [
        {"price": price, "size": levels["B"][price]} for price in sorted(levels["B"], reverse=True)
    ]
    asks = [{"price": price, "size": levels["A"][price]} for price in sorted(levels["A"])]
    return entries, bids, asks


def expected_nontrivial_assessment(fixture_body):
    """Complete literal thirteen-transition script; not a generic production replay."""
    bound = expected_binding_assessment(fixture_body["payload_bundle"])
    protocol_pin, context_pin = digest(expected_protocol()), digest(fixture_body["context"])
    prefixes = {
        audit["decoded_position"]: digest(
            {
                "adapter_protocol_sha256": protocol_pin,
                "context_sha256": context_pin,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
            }
        )
        for audit in bound["audits"]
    }
    state, orders, transitions, events, quotes, publications = empty_state(), {}, [], [], [], []
    metrics = {
        "A_passive": 4,
        "A_held_top_passive": 4,
        "A_linked_decrease": 4,
        "A_other_id_reload": 2,
        "A_same_id_reload": 2,
        "A_same_id_net_refresh": 2,
        "B_unlinked_decrease": 2,
    }
    execution_audit = {
        "temporal_resets": 1,
        "completed_events": 2,
        "trade_B_volume": 4,
        "fill_matched_passive_records": 1,
        "fill_matched_passive_volume": 4,
        "fill_above_displayed_volume": 0,
        "A_passive_volume": 4,
        "A_held_top_passive_volume": 4,
        "A_linked_decrease_volume": 4,
        "A_other_id_reload_volume": 2,
        "A_same_id_reload_volume": 2,
        "A_same_id_net_refresh_volume": 2,
        "B_unlinked_decrease_volume": 2,
    }
    records = fixture_body["payload_bundle"]["payloads"][1:]
    assert len(records) == 13
    for index, raw in enumerate(records):
        position = index + 2
        before = copy.deepcopy(orders.get(raw["order_id"]))
        last_before, initialized_before = state["last_recv_ns"], state["initialized"]
        if index == 0:
            state.update(initialized=True, last_recv_ns=WARMUP - SECOND)
        elif index < 5:
            orders[raw["order_id"]] = {
                "side": raw["side"],
                "price": raw["price"],
                "size": raw["size"],
            }
        else:
            state["last_recv_ns"] = raw["ts_recv"]
            if index >= 6:
                state["pending_target_positions"].append(position)
                state["execution_capture_positions"].append(position)
                if index == 6:
                    state["pending_trade_positions"] = [8]
                if index == 8:
                    orders[12]["size"] = 16
                elif index == 9:
                    orders[13] = {"side": "A", "price": 1_100_000, "size": 2}
                elif index == 10:
                    orders[12]["size"] = 18
                elif index == 11:
                    orders[11]["size"] = 8
        entries, bids, asks = oracle_book_projection(orders)
        state.update(orders=entries, bid_levels=bids, ask_levels=asks)
        event_ordinal = quote_ordinal = publication_ordinal = None
        if index in (5, 12):
            main = index == 12
            ordinal = 2 if main else 1
            time = NOON if main else NOON - SECOND
            members = list(range(8, 15)) if main else [7]
            event = {
                "event_ordinal": ordinal,
                "closing_decoded_position": position,
                "closing_target_transition_ordinal": index + 1,
                "ts_recv_ns": time,
                "target_positions": members,
                "trade_positions": [8] if main else [],
                "execution_capture_positions": members,
                "quote_ordinal": ordinal,
                "adapter_prefix_sha256": prefixes[position],
            }
            events.append(event | {"event_sha256": digest(event)})
            quote = {
                "quote_ordinal": ordinal,
                "event_ordinal": ordinal,
                "decoded_position": position,
                "ts_recv_ns": time,
                "bid": 1_000_000,
                "ask": 1_100_000,
                "bid_qty": 8 if main else 10,
                "ask_qty": 20,
                "prior_quote_gap_ns": SECOND if main else 0,
                "ofi_generation": 2,
                "bid_depth5": copy.deepcopy(bids),
                "ask_depth5": copy.deepcopy(asks),
                "adapter_prefix_sha256": prefixes[position],
            }
            quotes.append(quote | {"quote_sha256": digest(quote)})
            state.update(
                last_quote_ordinal=ordinal,
                ofi_generation=2,
                ofi_previous_quote_ordinal=ordinal,
                ofi_first_ts_ns=NOON - SECOND,
                ofi_events=[[NOON, -2]] if main else [],
                ofi_total=-2 if main else 0,
                history_ofi_generation=2,
                history_quote_ordinals=[1, 2] if main else [1],
                history_reloads=[[NOON - SECOND, 0, 0], [NOON, 0, 0]]
                if main
                else [[NOON - SECOND, 0, 0]],
                bid_depletions=[[NOON, 2]] if main else [],
                execution_last_ts_ns=time,
                execution_audit=copy.deepcopy(execution_audit)
                if main
                else {"completed_events": 1, "temporal_resets": 1},
                execution_events=[[NOON, metrics]] if main else [],
                execution_totals=metrics if main else {},
                next_publication_ns=NOON + SECOND if main else NOON,
                watch_since_ns=time,
                pending_target_positions=[],
                pending_trade_positions=[],
                execution_capture_positions=[],
                flow_events=[[NOON, 4, 1, 0]] if main else [],
                cvd=4 if main else 0,
                known_trades=1 if main else 0,
            )
            if main:
                publication = {
                    "publication_ordinal": 1,
                    "quote_ordinal": 2,
                    "event_ordinal": 2,
                    "decoded_position": 14,
                    "ts_recv_ns": NOON,
                    "adapter_prefix_sha256": prefixes[14],
                    "features": nontrivial_features(),
                }
                publications.append(publication | {"publication_sha256": digest(publication)})
            event_ordinal = quote_ordinal = ordinal
            publication_ordinal = 1 if main else None
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": index + 1,
                "disposition": "target_reset"
                if index == 0
                else "target_snapshot"
                if index < 5
                else "target_record",
                "snapshot": 1 <= index < 5,
                "exceptional_closed_clear": False,
                "order_id": raw["order_id"],
                "before": before,
                "after": copy.deepcopy(orders.get(raw["order_id"])),
                "initialized_before": initialized_before,
                "initialized_after": True,
                "last_recv_before": last_before,
                "last_recv_after": state["last_recv_ns"],
                "event_ordinal": event_ordinal,
                "quote_ordinal": quote_ordinal,
                "publication_ordinal": publication_ordinal,
                "state_sha256": digest(state),
            }
        )
    audits = [
        {
            "decoded_position": audit["decoded_position"],
            "disposition": "header"
            if audit["decoded_position"] == 1
            else transitions[audit["target_candidate_ordinal"] - 1]["disposition"],
            "instrument_id": audit["instrument_id"],
            "target_candidate_ordinal": audit["target_candidate_ordinal"],
            "target_transition_ordinal": audit["target_candidate_ordinal"],
            "binding_prefix_sha256": audit["bound_prefix_sha256"],
            "adapter_prefix_sha256": prefixes[audit["decoded_position"]],
        }
        for audit in bound["audits"]
    ]
    state.update(
        ofi_generation=3,
        ofi_previous_quote_ordinal=None,
        ofi_first_ts_ns=None,
        ofi_events=[],
        ofi_total=0,
        window_closed=True,
    )
    quality = {
        "target_records": 13,
        "snapshot_records": 4,
        "non_snapshot_records": 9,
        "event_after_receive": 0,
        "negative_send_delta": 0,
        "event_after_sending": 0,
        "clamped_delta": 0,
        "clock_disagreement_records": 0,
        "protected_disagreement_records": 0,
        "outside_disagreement_records": 0,
        "min_event_ahead_ns": None,
        "max_event_ahead_ns": None,
        "min_negative_delta_ns": None,
        "samples": [],
    }
    intervals = [
        {
            "start_ns": WARMUP,
            "timer_fired_ns": WARMUP + 5 * SECOND + 1,
            "end_ns": NOON - SECOND,
            "recovered": True,
            "trigger_decoded_position": 7,
        },
        {
            "start_ns": NOON,
            "timer_fired_ns": NOON + 5 * SECOND + 1,
            "end_ns": END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    result = {
        "status": "constructed_typed_native_event_adapter_not_native_verification",
        "protocol_sha256": protocol_pin,
        "context_sha256": context_pin,
        "binding_protocol_sha256": digest(expected_binding_protocol()),
        "cursor_protocol_sha256": digest(expected_cursor_protocol()),
        "fixture_sha256": digest(fixture_body),
        "fixture": fixture_body,
        "binding_assessment": bound,
        "audits": audits,
        "transitions": transitions,
        "events": events,
        "quotes": quotes,
        "publications": publications,
        "inactivity_intervals": intervals,
        "clock_quality": quality,
        "exceptional_clear_count": 0,
        "terminal_state": state,
        "authority_flags": dict.fromkeys(ADAPTER_FLAGS, False),
    }
    return result | {"assessment_sha256": digest(result)}


@pytest.mark.parametrize("mode", [False, True])
def test_nontrivial_full_37_feature_script_has_independent_complete_state_artifact_oracle(mode):
    adapter, fixture, pins, body = make_case(mode, nontrivial_records(mode))
    expected = expected_nontrivial_assessment(body)
    assert call_fixture(adapter, "fixture_sha256", fixture, pins) == digest(body)
    result = call_fixture(adapter, "replay", fixture, pins)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )
    assert type(dict(result.publications[0].features)["mid_travel_5s_ticks"]) is float


def test_complete_after_window_event_oracle_has_no_manufactured_quote_or_publication():
    adapter, fixture, pins, body = make_case(
        records=idle_records() + [raw_record(recv=END, sequence=5)]
    )
    expected = expected_two_event_assessment(body)
    result = call_fixture(adapter, "replay", fixture, pins)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )


def replay_records(records, mode=False, **kwargs):
    adapter, fixture, pins, body = make_case(mode, records, **kwargs)
    return adapter, fixture, pins, body, call_fixture(adapter, "replay", fixture, pins)


def refuses_records(records, mode=False):
    adapter, fixture, pins, _ = make_case(mode, records)
    for api in ("fixture_sha256", "replay"):
        with pytest.raises(ValueError):
            call_fixture(adapter, api, fixture, pins)


@pytest.mark.parametrize("mode", [False, True])
@pytest.mark.parametrize("location", ["before", "after"])
def test_foreign_semantic_poison_is_fully_bound_but_cannot_drive_target_rules(mode, location):
    foreign = raw_record(
        "X",
        "?",
        instrument=99,
        recv=-123,
        ts_event=9_223_372_036_854_775_807,
        ts_in_delta=-9_223_372_036_854_775_808,
        flags=255,
        sequence=77,
        mode=mode,
    )
    records = idle_records(mode)
    records.insert(3 if location == "before" else 4, foreign)
    adapter, fixture, pins, body, result = replay_records(records, mode)
    expected = expected_idle_assessment(body)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )
    assert result.clock_quality.target_records == 4
    assert len(result.events) == len(result.quotes) == len(result.publications) == 1
    assert result.terminal_state.last_recv_ns == NOON
    retained = fixture.payload_bundle.payloads[4 if location == "before" else 5]
    assert canonical({name: getattr(retained, name) for name in RAW_FIELDS}) == canonical(foreign)


def test_foreign_f_last_cannot_close_a_pending_target_event():
    records = idle_records()[:3] + [
        raw_record(recv=NOON, flags=0),
        raw_record(instrument=99, recv=END, flags=128),
        raw_record(recv=NOON, flags=128),
    ]
    _, _, _, _, result = replay_records(records)
    event = result.events[0]
    assert event.target_positions == (5, 7)
    assert event.execution_capture_positions == (5, 7)
    assert event.trade_positions == ()
    assert event.closing_decoded_position == 7
    assert result.clock_quality.target_records == 5
    refuses_records(records[:-1])


@pytest.mark.parametrize("mode", [False, True])
def test_future_foreign_suffix_and_member_change_complete_not_consumed_publication_identity(mode):
    future = raw_record(instrument=99, recv=END, flags=255, sequence=5, mode=mode)
    left = idle_records(mode) + [future]
    right = idle_records(mode) + [future | {"price": -991, "sequence": 777}]
    a, f1, _, b1, r1 = replay_records(left, mode, member="1" * 64)
    _, f2, _, b2, r2 = replay_records(right, mode, member="2" * 64)
    assert_complete_assessment(a, r1, f1, expected_idle_assessment(b1))
    assert_complete_assessment(a, r2, f2, expected_idle_assessment(b2))
    assert r1.publications == r2.publications
    assert r1.fixture_sha256 != r2.fixture_sha256
    assert r1.assessment_sha256 != r2.assessment_sha256
    assert r1.audits[4].adapter_prefix_sha256 == r2.audits[4].adapter_prefix_sha256
    assert r1.audits[-1].adapter_prefix_sha256 != r2.audits[-1].adapter_prefix_sha256


def test_consumed_foreign_body_preserves_features_not_causal_prefix_identity():
    foreign = raw_record(instrument=99, recv=-123, flags=255)
    a, f1, _, b1, r1 = replay_records(idle_records()[:3] + [foreign] + idle_records()[3:])
    _, f2, _, b2, r2 = replay_records(
        idle_records()[:3] + [foreign | {"price": -77}] + idle_records()[3:]
    )
    assert_complete_assessment(a, r1, f1, expected_idle_assessment(b1))
    assert_complete_assessment(a, r2, f2, expected_idle_assessment(b2))
    assert r1.publications[0].features == r2.publications[0].features
    assert r1.publications[0].adapter_prefix_sha256 != r2.publications[0].adapter_prefix_sha256
    assert r1.publications[0].publication_sha256 != r2.publications[0].publication_sha256


def test_full_trade_event_crosses_warmup_but_execution_capture_has_fill_without_trade():
    records = idle_records()[:3] + [
        raw_record("T", "B", recv=WARMUP - 1, price=1_100_001, size=3, oid=900, flags=0),
        raw_record("F", "A", recv=NOON, price=1_100_001, size=3, oid=12, flags=128),
    ]
    _, _, _, _, result = replay_records(records)
    event = result.events[0]
    assert event.target_positions == (5, 6)
    assert event.trade_positions == (5,)
    assert event.execution_capture_positions == (6,)
    assert result.terminal_state.flow_events == ((NOON, 3, 1, 0),)
    assert result.terminal_state.cvd == 3
    features = dict(result.publications[0].features)
    assert features["normalized_cvd_5s"] == 2 * 3 / 30
    assert features["log_known_trades_5s"] == math.log1p(1)
    assert features["buy_absorption_proxy_5s"] == 3 / 30
    assert all(features[name] == 0.0 for name in FEATURE_NAMES[23:])
    audit = dict(result.terminal_state.execution_audit)
    assert audit["fill_without_trade_records"] == 1
    assert audit["fill_without_trade_volume"] == 3
    assert "trade_B_volume" not in audit


@pytest.mark.parametrize("pending", ["N", "T"])
@pytest.mark.parametrize("incoming", ["R", "snapshot"])
def test_reset_or_snapshot_cannot_hide_any_incomplete_ordinary_event(pending, incoming):
    records = idle_records()[:3] + [
        raw_record(
            pending,
            "B" if pending == "T" else "N",
            recv=NOON - 2 * SECOND,
            price=1_100_000,
            size=1,
            flags=0,
        )
    ]
    records.append(
        raw_record("R", recv=NOON - SECOND, flags=0)
        if incoming == "R"
        else raw_record("A", "B", recv=NOON - SECOND, oid=88, price=900_001, size=1, flags=32)
    )
    refuses_records(records)


@pytest.mark.parametrize("action", ["N", "T"])
def test_incomplete_numeric_suffix_refuses_whole_witness_without_salvage(action):
    records = idle_records() + [
        raw_record(
            action,
            "B" if action == "T" else "N",
            recv=NOON + SECOND,
            price=1_100_000,
            size=1,
            flags=0,
        )
    ]
    refuses_records(records)


def test_no_reset_is_manufactured_for_preinitialization_updates():
    refuses_records(idle_records()[1:])


@pytest.mark.parametrize("flags", [0, 128, 32, 40])
def test_reset_returns_before_ordinary_event_even_with_f_last_or_snapshot(flags):
    records = idle_records()
    records[0] = records[0] | {"flags": flags}
    _, _, _, _, result = replay_records(records)
    transition = result.transitions[0]
    assert transition.disposition == "target_reset"
    assert transition.snapshot is bool(flags & 32)
    assert (
        transition.event_ordinal
        is transition.quote_ordinal
        is transition.publication_ordinal
        is None
    )
    assert len(result.events) == 1
    assert result.clock_quality.snapshot_records == 2 + bool(flags & 32)
    assert result.clock_quality.non_snapshot_records == 2 - bool(flags & 32)


@pytest.mark.parametrize("time", [DAY - 1, DAY + 86_400 * SECOND])
def test_mapped_target_day_is_end_exclusive(time):
    records = idle_records()
    records[0] = records[0] | {"ts_recv": time, "ts_event": time - 1}
    refuses_records(records)


@pytest.mark.parametrize("bad_bit", [8, 4, 64, 16])
def test_bad_quality_mask_is_not_silently_accepted_on_ordinary_target(bad_bit):
    records = idle_records()
    records[-1] = records[-1] | {"flags": 128 | bad_bit}
    refuses_records(records)


@pytest.mark.parametrize("bad_bit", [4, 64, 16])
def test_snapshot_exempts_bad_receive_only_not_other_quality_masks(bad_bit):
    records = idle_records()
    records[1] = records[1] | {"flags": 32 | bad_bit}
    refuses_records(records)


def test_snapshot_bad_receive_exemption_and_unknown_ordinary_flag_are_retained():
    records = idle_records()
    records[1] = records[1] | {
        "flags": 40,
        "ts_event": records[1]["ts_recv"] + 500,
        "ts_in_delta": -17,
    }
    records[-1] = records[-1] | {"flags": 128 | (1 << 40)}
    _, _, _, _, result = replay_records(records)
    assert result.clock_quality.clock_disagreement_records == 0
    assert result.clock_quality.snapshot_records == 2
    assert result.fixture.payload_bundle.payloads[-1].flags == 128 | (1 << 40)


@pytest.mark.parametrize("kind", ["snapshot", "reset", "ahead", "negative_delta", "regression"])
def test_selected_window_refusals_are_fail_closed(kind):
    extra = {
        "snapshot": raw_record(
            "A", "B", recv=NOON + SECOND, oid=55, price=900_001, size=1, flags=32
        ),
        "reset": raw_record("R", recv=NOON + SECOND, flags=0),
        "ahead": raw_record(recv=NOON + SECOND, ts_event=NOON + SECOND + 1),
        "negative_delta": raw_record(recv=NOON + SECOND, ts_in_delta=-1),
        "regression": raw_record(recv=NOON - 1),
    }[kind]
    refuses_records(idle_records() + [extra])


def test_outside_clock_disagreements_are_audited_without_timestamp_correction():
    before = WARMUP - SECOND
    records = idle_records()
    records[0] = records[0] | {"ts_event": before + 9, "ts_in_delta": -4}
    _, _, _, _, result = replay_records(records)
    quality = result.clock_quality
    assert (
        quality.event_after_receive,
        quality.negative_send_delta,
        quality.event_after_sending,
        quality.clock_disagreement_records,
        quality.protected_disagreement_records,
        quality.outside_disagreement_records,
    ) == (1, 1, 1, 1, 0, 1)
    sample = quality.samples[0]
    assert (
        sample.decoded_position,
        sample.ts_recv,
        sample.ts_event,
        sample.ts_in_delta,
        sample.protected,
        sample.event_ahead_ns,
        sample.sending_ns,
    ) == (2, before, before + 9, -4, False, 9, before + 4)
    assert quality.min_event_ahead_ns == quality.max_event_ahead_ns == 9
    assert quality.min_negative_delta_ns == -4


@pytest.mark.parametrize("count", [1, 32])
def test_closed_break_exceptional_clear_exact_bound_does_not_advance_ordinary_clock(count):
    time = DAY + 21 * 3_600 * SECOND
    records = idle_records() + [
        raw_record("R", recv=time + index, flags=8, sequence=5 + index) for index in range(count)
    ]
    _, _, _, _, result = replay_records(records)
    assert result.exceptional_clear_count == count
    assert result.terminal_state.orders == ()
    assert result.terminal_state.initialized is True
    assert result.terminal_state.last_recv_ns == NOON
    assert all(t.exceptional_closed_clear is True for t in result.transitions[-count:])
    assert all(t.event_ordinal is None for t in result.transitions[-count:])
    assert len(result.events) == 1


@pytest.mark.parametrize("case", ["33", "before", "end", "flags", "action", "side", "ahead"])
def test_exceptional_clear_requires_exact_closed_break_predicates(case):
    time = DAY + 21 * 3_600 * SECOND
    extra = raw_record("R", recv=time, flags=8)
    if case == "33":
        tail = [extra | {"sequence": index + 5} for index in range(33)]
    else:
        changes = {
            "before": {"ts_recv": time - 1, "ts_event": time - 2},
            "end": {"ts_recv": time + 3_600 * SECOND, "ts_event": time + 3_600 * SECOND - 1},
            "flags": {"flags": 136},
            "action": {"action": "N"},
            "side": {"side": "A"},
            "ahead": {"ts_event": time + 1},
        }[case]
        tail = [extra | changes]
    refuses_records(idle_records() + tail)


@pytest.mark.parametrize("gap", [5 * SECOND, 5 * SECOND + 1])
def test_inactivity_strict_equality_and_plus_one_preserve_actual_gap_and_prior_quote(gap):
    _, _, _, _, result = replay_records(idle_records() + [raw_record(recv=NOON + gap)])
    second = result.quotes[1]
    assert second.prior_quote_gap_ns == gap
    assert second.ofi_generation == (2 if gap == 5 * SECOND else 3)
    features = dict(result.publications[1].features)
    assert features["log_prior_quote_gap_ms"] == math.log1p(gap / 1_000_000)
    assert result.terminal_state.ofi_generation == (3 if gap == 5 * SECOND else 4)
    if gap > 5 * SECOND:
        recovered = result.inactivity_intervals[1]
        assert (
            recovered.start_ns,
            recovered.timer_fired_ns,
            recovered.end_ns,
            recovered.recovered,
            recovered.trigger_decoded_position,
        ) == (NOON, NOON + 5 * SECOND + 1, NOON + gap, True, 6)


def test_inactivity_advances_before_incoming_non_final_mutation_and_recovers_at_closure():
    time = NOON + 5 * SECOND + 1
    records = idle_records() + [
        raw_record("M", "B", recv=time, oid=11, price=1_000_001, size=12, flags=0),
        raw_record(recv=time, flags=128),
    ]
    _, _, _, _, result = replay_records(records)
    assert result.quotes[1].ofi_generation == 3
    assert result.quotes[1].bid_qty == 12
    assert result.events[1].target_positions == (6, 7)
    interval = result.inactivity_intervals[1]
    assert (interval.timer_fired_ns, interval.end_ns, interval.trigger_decoded_position) == (
        time,
        time,
        7,
    )


def test_first_due_equal_time_publication_is_not_rewritten_by_later_completed_quote():
    records = idle_records() + [
        raw_record("M", "B", recv=NOON, oid=11, price=1_000_001, size=12, flags=128),
        raw_record(recv=NOON + SECOND),
    ]
    _, _, _, _, result = replay_records(records)
    assert (len(result.quotes), len(result.publications)) == (3, 2)
    expected_first = expected_idle_assessment(make_case()[3])["publications"][0]
    assert canonical(literal_actual_projection(result.publications[0])) == canonical(expected_first)
    assert result.publications[0].quote_ordinal == 1
    assert result.publications[1].quote_ordinal == 3
    second = dict(result.publications[1].features)
    assert second["log_bid_qty"] == math.log1p(12)
    assert second["normalized_ofi_5s"] == 2 * 2 / 32
    assert result.terminal_state.next_publication_ns == NOON + 2 * SECOND


def test_end_minus_one_observation_then_end_event_has_no_future_quote():
    records = idle_records() + [raw_record(recv=END - 1), raw_record(recv=END)]
    _, _, _, _, result = replay_records(records)
    assert (len(result.events), len(result.quotes), len(result.publications)) == (3, 2, 2)
    assert result.publications[-1].ts_recv_ns == END - 1
    assert result.events[-1].quote_ordinal is None
    assert result.terminal_state.last_recv_ns == END
    assert result.terminal_state.window_closed is True
    interval = result.inactivity_intervals[-1]
    assert (interval.recovered, interval.end_ns, interval.trigger_decoded_position) == (
        True,
        END - 1,
        6,
    )


@pytest.mark.parametrize("case", ["none", "33", "one_sided", "crossed", "spread"])
def test_publication_completeness_and_quote_rules_refuse_without_partial_output(case):
    records = idle_records()
    if case == "none":
        records[-1] = raw_record(recv=NOON - 1)
    elif case == "33":
        records = records[:3] + [raw_record(recv=NOON + index * SECOND) for index in range(33)]
    elif case == "one_sided":
        records.pop(2)
    elif case == "crossed":
        records[2] = records[2] | {"price": 1_000_001}
    elif case == "spread":
        records[2] = records[2] | {"price": 1_100_002}
    refuses_records(records)


@pytest.mark.parametrize(
    "case", ["duplicate", "unknown_modify", "excess_cancel", "wrong_cancel_side"]
)
def test_strict_book_fault_is_not_salvaged_into_an_accepted_suffix(case):
    tail = {
        "duplicate": raw_record("A", "B", recv=NOON + SECOND, oid=11, price=1_000_001, size=1),
        "unknown_modify": raw_record(
            "M", "B", recv=NOON + SECOND, oid=999, price=1_000_001, size=1
        ),
        "excess_cancel": raw_record("C", "B", recv=NOON + SECOND, oid=11, price=1_000_001, size=11),
        "wrong_cancel_side": raw_record(
            "C", "A", recv=NOON + SECOND, oid=11, price=1_000_001, size=1
        ),
    }[case]
    refuses_records(idle_records() + [tail])


def distinct_value(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is float:
        return value + 0.25
    if type(value) is str:
        return "0" * 64 if len(value) == 64 else "forged"
    if type(value) is tuple:
        return value + (None,)
    return 1 if value is None else None


TAMPER_FAMILIES = {
    "assessment": "AdapterAssessment",
    "audit": "AdapterAudit",
    "transition": "TargetTransition",
    "event": "EventWitness",
    "quote": "QuoteWitness",
    "publication": "FeaturePublication",
    "interval": "InactivityInterval",
    "quality": "ClockQuality",
    "state": "ReconstructedState",
    "entry": "OrderEntry",
    "order": "OrderState",
    "level": "PriceLevel",
}
TAMPER_FIELDS = tuple(
    (family, field) for family, schema in TAMPER_FAMILIES.items() for field in SCHEMAS[schema]
)


def replace_artifact(result, family, replacement):
    if family == "assessment":
        return replacement
    if family == "entry":
        return replace(
            result,
            terminal_state=replace(
                result.terminal_state, orders=(replacement,) + result.terminal_state.orders[1:]
            ),
        )
    if family == "order":
        entry = replace(result.terminal_state.orders[0], state=replacement)
        return replace_artifact(result, "entry", entry)
    if family == "level":
        quote = replace(
            result.quotes[0], bid_depth5=(replacement,) + result.quotes[0].bid_depth5[1:]
        )
        return replace(result, quotes=(quote,) + result.quotes[1:])
    plural = {
        "audit": "audits",
        "transition": "transitions",
        "event": "events",
        "quote": "quotes",
        "publication": "publications",
        "interval": "inactivity_intervals",
    }
    if family in plural:
        name = plural[family]
        return replace(result, **{name: (replacement,) + getattr(result, name)[1:]})
    return replace(
        result, **{"clock_quality" if family == "quality" else "terminal_state": replacement}
    )


def tamper_object(result, family):
    if family == "audit":
        return result.audits[0]
    if family == "transition":
        return result.transitions[0]
    if family == "interval":
        return result.inactivity_intervals[0]
    return numerical_object(result, family)


@pytest.mark.parametrize("family,field", TAMPER_FIELDS)
def test_every_named_submitted_field_is_reconstructed_not_adopted(family, field):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    value = tamper_object(result, family)
    changed = replace(value, **{field: distinct_value(getattr(value, field))})
    bad = replace_artifact(result, family, changed)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


@pytest.mark.parametrize("family", tuple(TAMPER_FAMILIES))
def test_exact_nested_types_reject_json_equal_subclasses(family):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    value = tamper_object(result, family)
    schema = TAMPER_FAMILIES[family]
    alias = type("SubmittedAlias", (getattr(adapter, schema),), {})
    changed = alias(*(getattr(value, name) for name in SCHEMAS[schema]))
    bad = replace_artifact(result, family, changed)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


@pytest.mark.parametrize("family,field", NUMERIC_FAMILIES)
def test_valid_complete_metadata_genuinely_reaches_every_submitted_value_family(
    monkeypatch, family, field
):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    objects = numerical_objects(result, family)
    poison_slot(monkeypatch, type(objects[0]), objects, field)
    with pytest.raises(AssertionError, match=field):
        call_verify(adapter, result, fixture, pins, expected)


@pytest.mark.parametrize("feature", FEATURE_NAMES)
@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), IntAlias(0), 0.125])
def test_all_37_feature_scalar_representations_and_values_are_verified(feature, bad):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    publication = result.publications[0]
    changed = replace(
        publication,
        features=tuple(
            (name, bad if name == feature else value) for name, value in publication.features
        ),
    )
    with pytest.raises(ValueError):
        call_verify(
            adapter, replace_artifact(result, "publication", changed), fixture, pins, expected
        )


@pytest.mark.parametrize("field", RAW_FIELDS)
def test_actual_raw_body_must_match_held_item_pin_not_an_adopted_bundle_summary(field):
    adapter, fixture, pins, _ = make_case()
    payloads = fixture.payload_bundle.payloads
    changed = replace(payloads[-1], **{field: distinct_value(getattr(payloads[-1], field))})
    bad = replace(
        fixture, payload_bundle=replace(fixture.payload_bundle, payloads=payloads[:-1] + (changed,))
    )
    for api in ("fixture_sha256", "replay"):
        with pytest.raises(ValueError):
            call_fixture(adapter, api, bad, pins)


@pytest.mark.parametrize("family", ["quote", "publication", "state"])
def test_coherently_rehashed_submitted_numeric_body_still_cannot_replace_reconstruction(family):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    submitted = copy.deepcopy(expected)
    if family == "quote":
        submitted["quotes"][0]["bid_qty"] = 11
        body = {
            name: value for name, value in submitted["quotes"][0].items() if name != "quote_sha256"
        }
        submitted["quotes"][0]["quote_sha256"] = digest(body)
    elif family == "publication":
        submitted["publications"][0]["features"][0][1] = math.log1p(11)
        body = {
            name: value
            for name, value in submitted["publications"][0].items()
            if name != "publication_sha256"
        }
        submitted["publications"][0]["publication_sha256"] = digest(body)
    else:
        submitted["terminal_state"]["cvd"] = 1
    body = {name: value for name, value in submitted.items() if name != "assessment_sha256"}
    submitted["assessment_sha256"] = digest(body)
    bad = assessment_object(adapter, fixture, submitted)
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, submitted)


@pytest.mark.parametrize(
    "name", ["F_LAST", "TICK", "SECOND_NS", "MAX_BODY_BYTES", "MAX_ITEMS", "STATUS"]
)
def test_mutable_exported_aliases_cannot_weaken_full_reconstruction(monkeypatch, name):
    adapter, fixture, pins, body = make_case()
    monkeypatch.setattr(adapter, name, False, raising=False)
    result = call_fixture(adapter, "replay", fixture, pins)
    assert_complete_assessment(adapter, result, fixture, expected_idle_assessment(body))


@pytest.mark.parametrize("module,limit", [(cursor, 65_536), (binding, 262_144)])
def test_inherited_arbitrary_guard_body_equality_and_overflow(module, limit):
    # An arbitrary guard input is not a legal native/cursor/binding fixture and
    # is not evidence of a universal maximum constructed fixture size.
    assert module._bounded_canonical("x" * (limit - 2)) == canonical("x" * (limit - 2))
    with pytest.raises(ValueError):
        module._bounded_canonical("x" * (limit - 1))


def test_shared_outer_arbitrary_guard_body_equality_and_overflow():
    adapter = adapter_module()
    limit = 1_048_576
    assert callable(getattr(adapter, "_bounded_canonical", None))
    assert adapter._bounded_canonical("x" * (limit - 2)) == canonical("x" * (limit - 2))
    with pytest.raises(ValueError):
        adapter._bounded_canonical("x" * (limit - 1))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_shared_outer_guard_refuses_nonfinite_canonical_body(bad):
    with pytest.raises(ValueError):
        adapter_module()._bounded_canonical({"value": bad})


def test_complete_pipeline_calls_both_old_caps_and_shared_fixture_state_artifact_result_guard(
    monkeypatch,
):
    adapter, fixture, pins, body = make_case()
    observed = {"cursor": [], "binding": [], "adapter": []}
    for name, module in (("cursor", cursor), ("binding", binding), ("adapter", adapter)):
        original = module._bounded_canonical

        def bound(value, original=original, name=name):
            if type(value) is dict:
                observed[name].append(frozenset(value))
            return original(value)

        monkeypatch.setattr(module, "_bounded_canonical", bound)
    result = call_fixture(adapter, "replay", fixture, pins)
    assert_complete_assessment(adapter, result, fixture, expected_idle_assessment(body))
    assert frozenset(body) in observed["adapter"]
    assert frozenset(SCHEMAS["ReconstructedState"]) in observed["adapter"]
    assert frozenset(SCHEMAS["AdapterAssessment"]) - {"assessment_sha256"} in observed["adapter"]
    for schema, pin in (
        ("EventWitness", "event_sha256"),
        ("QuoteWitness", "quote_sha256"),
        ("FeaturePublication", "publication_sha256"),
    ):
        assert frozenset(SCHEMAS[schema]) - {pin} in observed["adapter"]
    assert frozenset(body["payload_bundle"]["cursor_fixture"]) in observed["cursor"]
    assert (
        frozenset(expected_cursor_assessment(body["payload_bundle"]["cursor_fixture"]))
        - {"assessment_sha256"}
        in observed["cursor"]
    )
    assert frozenset(body["payload_bundle"]) in observed["binding"]
    assert (
        frozenset(expected_binding_assessment(body["payload_bundle"])) - {"assessment_sha256"}
        in observed["binding"]
    )


@pytest.mark.parametrize("module", [cursor, binding])
def test_inner_cap_refusal_is_propagated_not_overridden_by_outer_capacity(monkeypatch, module):
    adapter, fixture, pins, _ = make_case()

    def refused(value):
        raise ValueError("Independent inherited cap refusal")

    monkeypatch.setattr(module, "_bounded_canonical", refused)
    for api in ("fixture_sha256", "replay"):
        with pytest.raises(ValueError):
            call_fixture(adapter, api, fixture, pins)


@pytest.mark.parametrize("mode", [False, True])
def test_legal_maximum_position_and_publication_counts_have_complete_measured_envelopes(mode):
    records = idle_records(mode)[:3] + [
        raw_record(recv=NOON + min(index, 31) * SECOND, mode=mode, sequence=index + 4)
        for index in range(124)
    ]
    adapter, fixture, pins, body, result = replay_records(records, mode)
    expected = expected_many_noop_assessment(body)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert len(fixture.payload_bundle.cursor_fixture.items) == 128
    assert (
        len(result.transitions),
        len(result.events),
        len(result.quotes),
        len(result.publications),
    ) == (127, 124, 124, 32)
    assert result.quotes[-1].quote_ordinal == 124
    assert result.publications[-1].quote_ordinal == 32
    assert result.publications[-1].ts_recv_ns == NOON + 31 * SECOND
    assert (
        result.clock_quality.target_records,
        result.clock_quality.snapshot_records,
        result.clock_quality.non_snapshot_records,
    ) == (127, 2, 125)
    assert result.terminal_state.pending_target_positions == ()
    assert (
        result.terminal_state.pending_trade_positions
        == result.terminal_state.execution_capture_positions
        == ()
    )
    assert len(canonical(body["payload_bundle"]["cursor_fixture"])) <= 65_536
    assert len(canonical(body["payload_bundle"])) <= 262_144
    assert len(canonical(body)) <= 1_048_576
    projected = literal_actual_projection(result)
    result_body = {name: value for name, value in projected.items() if name != "assessment_sha256"}
    assert len(canonical(result_body)) <= 1_048_576
    print(
        json.dumps(
            {
                "measurement": "legal_invented_128_positions_32_publications_not_universal_maximum",
                "ts_out": mode,
                "cursor_fixture_body_bytes": len(
                    canonical(body["payload_bundle"]["cursor_fixture"])
                ),
                "binding_bundle_body_bytes": len(canonical(body["payload_bundle"])),
                "adapter_fixture_body_bytes": len(canonical(body)),
                "adapter_result_body_bytes": len(canonical(result_body)),
                "adapter_state_body_bytes": len(canonical(projected["terminal_state"])),
            },
            sort_keys=True,
        )
    )
    assert canonical(dict(result.authority_flags)) == canonical(dict.fromkeys(ADAPTER_FLAGS, False))
    assert all(
        tuple(name for name, _ in publication.features) == FEATURE_NAMES
        for publication in result.publications
    )
    assert all(
        dict(publication.features)["log_bid_qty"] == math.log1p(10)
        for publication in result.publications
    )
    assert all(
        dict(publication.features)["log_ask_qty"] == math.log1p(20)
        for publication in result.publications
    )
    assert all(
        dict(publication.features)[name] == 0.0
        for publication in result.publications
        for name in FEATURE_NAMES[23:]
    )
    assert call_fixture(adapter, "fixture_sha256", fixture, pins) == digest(body)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )


def test_more_than_128_complete_positions_refuses_without_thinning():
    records = idle_records()[:3] + [
        raw_record(recv=NOON + min(index, 31) * SECOND, sequence=index + 4) for index in range(125)
    ]
    refuses_records(records)


@pytest.mark.parametrize("mode", [False, True])
def test_complete_inactive_future_and_unrelated_mapping_declarations_are_retained(mode):
    mappings = [
        {
            "contract": "6EM5",
            "intervals": [
                {"start_date": "2025-04-06", "end_date": "2025-04-07", "instrument_symbol": "0009"},
                {"start_date": "2025-04-07", "end_date": "2025-04-08", "instrument_symbol": "0007"},
                {"start_date": "2025-04-08", "end_date": "2025-04-09", "instrument_symbol": "0011"},
            ],
        },
        {
            "contract": "6EU5",
            "intervals": [
                {"start_date": "2025-04-07", "end_date": "2025-04-08", "instrument_symbol": "0099"}
            ],
        },
    ]
    records = idle_records(mode) + [raw_record(instrument=99, recv=-123, flags=255, mode=mode)]
    adapter, fixture, pins, body, result = replay_records(records, mode, mappings=mappings)
    expected = expected_idle_assessment(body)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )
    assert (
        literal_actual_projection(fixture)["payload_bundle"]["cursor_fixture"]["header"]["mappings"]
        == mappings
    )
    assert result.binding_assessment.cursor_assessment.mapped_instrument_id == 7
    assert result.audits[-1].disposition == "foreign"


@pytest.mark.parametrize("edge", ["ended", "future"])
def test_requested_mapping_end_is_exclusive_and_future_mapping_is_not_adopted(edge):
    interval = {"start_date": "2025-04-06", "end_date": "2025-04-07", "instrument_symbol": "0007"}
    if edge == "future":
        interval = interval | {"start_date": "2025-04-08", "end_date": "2025-04-09"}
    adapter, fixture, pins, _ = make_case(mappings=[{"contract": "6EM5", "intervals": [interval]}])
    for api in ("fixture_sha256", "replay"):
        with pytest.raises(ValueError):
            call_fixture(adapter, api, fixture, pins)


def test_snapshot_receive_regression_bypasses_ordinary_receive_advance_not_source_identity():
    records = idle_records()
    initial = records[0]["ts_recv"]
    for index in (1, 2):
        time = initial - index * SECOND
        records[index] = records[index] | {"ts_recv": time, "ts_event": time - 1}
    adapter, fixture, _, body, result = replay_records(records)
    assert_complete_assessment(adapter, result, fixture, expected_idle_assessment(body))
    assert all(
        transition.last_recv_before == transition.last_recv_after == initial
        for transition in result.transitions[1:3]
    )
    assert result.clock_quality.snapshot_records == 2


def test_multiple_known_and_unknown_trades_flush_at_completion_clock_and_f_is_not_a_second_trade():
    records = idle_records()[:3] + [
        raw_record("T", "B", recv=WARMUP - 3, price=1_100_000, size=2, oid=801, flags=0),
        raw_record("T", "A", recv=WARMUP - 2, price=1_000_000, size=1, oid=802, flags=0),
        raw_record("T", "N", recv=WARMUP - 1, price=1_100_000, size=3, oid=803, flags=0),
        raw_record("F", "A", recv=NOON, price=1_100_001, size=1, oid=12, flags=128),
    ]
    _, _, _, _, result = replay_records(records)
    event = result.events[0]
    assert event.target_positions == (5, 6, 7, 8)
    assert event.trade_positions == (5, 6, 7)
    assert event.execution_capture_positions == (8,)
    state = result.terminal_state
    assert state.flow_events == ((NOON, 2, 1, 0), (NOON, -1, 1, 0), (NOON, 0, 0, 1))
    assert (state.cvd, state.known_trades, state.unknown_trades) == (1, 2, 1)
    features = dict(result.publications[0].features)
    assert features["normalized_cvd_5s"] == 2 * 1 / 30
    assert features["log_known_trades_5s"] == math.log1p(2)
    assert features["unknown_trade_fraction_5s"] == 1 / 3
    assert dict(state.execution_audit)["fill_without_trade_records"] == 1


@pytest.mark.parametrize("field", ["ts_recv", "price"])
def test_undefined_native_shaped_target_value_is_not_coerced_to_a_usable_value(field):
    records = idle_records()
    index = 0 if field == "ts_recv" else 1
    undefined = 18_446_744_073_709_551_615 if field == "ts_recv" else 9_223_372_036_854_775_807
    records[index] = records[index] | {field: undefined}
    refuses_records(records)


class FloatAlias(float):
    pass


SCALAR_ALIAS_FIELDS = tuple(
    (family, field)
    for family, fields in (
        (
            "assessment",
            (
                "status",
                "protocol_sha256",
                "context_sha256",
                "binding_protocol_sha256",
                "cursor_protocol_sha256",
                "fixture_sha256",
                "exceptional_clear_count",
                "assessment_sha256",
            ),
        ),
        (
            "audit",
            ("decoded_position", "disposition", "binding_prefix_sha256", "adapter_prefix_sha256"),
        ),
        (
            "transition",
            (
                "decoded_position",
                "target_transition_ordinal",
                "disposition",
                "snapshot",
                "exceptional_closed_clear",
                "order_id",
                "initialized_before",
                "initialized_after",
                "last_recv_after",
                "state_sha256",
            ),
        ),
        (
            "event",
            (
                "event_ordinal",
                "closing_decoded_position",
                "closing_target_transition_ordinal",
                "ts_recv_ns",
                "quote_ordinal",
                "adapter_prefix_sha256",
                "event_sha256",
            ),
        ),
        (
            "quote",
            (
                "quote_ordinal",
                "event_ordinal",
                "decoded_position",
                "ts_recv_ns",
                "bid",
                "ask",
                "bid_qty",
                "ask_qty",
                "prior_quote_gap_ns",
                "ofi_generation",
                "adapter_prefix_sha256",
                "quote_sha256",
            ),
        ),
        (
            "publication",
            (
                "publication_ordinal",
                "quote_ordinal",
                "event_ordinal",
                "decoded_position",
                "ts_recv_ns",
                "adapter_prefix_sha256",
                "publication_sha256",
            ),
        ),
        (
            "interval",
            ("start_ns", "timer_fired_ns", "end_ns", "recovered", "trigger_decoded_position"),
        ),
        ("quality", SCHEMAS["ClockQuality"][:10]),
        (
            "state",
            (
                "initialized",
                "last_recv_ns",
                "last_quote_ordinal",
                "cvd",
                "known_trades",
                "unknown_trades",
                "ofi_generation",
                "ofi_total",
                "history_ofi_generation",
                "execution_last_ts_ns",
                "next_publication_ns",
                "watch_since_ns",
                "window_closed",
            ),
        ),
        ("entry", ("order_id",)),
        ("order", ("side", "price", "size")),
        ("level", ("price", "size")),
    )
    for field in fields
)


def independent_scalar_body(expected, family):
    if family == "assessment":
        return expected
    if family == "entry":
        return expected["terminal_state"]["orders"][0]
    if family == "order":
        return expected["terminal_state"]["orders"][0]["state"]
    if family == "level":
        return expected["quotes"][0]["bid_depth5"][0]
    plural = {
        "audit": "audits",
        "transition": "transitions",
        "event": "events",
        "quote": "quotes",
        "publication": "publications",
        "interval": "inactivity_intervals",
    }
    if family in plural:
        return expected[plural[family]][0]
    return expected["clock_quality" if family == "quality" else "terminal_state"]


@pytest.mark.parametrize("family,field", SCALAR_ALIAS_FIELDS)
def test_exact_submitted_scalar_type_is_not_hidden_by_equal_canonical_value(family, field):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    literal = independent_scalar_body(expected, family)[field]
    assert type(literal) in (int, str, bool)
    if type(literal) is bool:
        # Observed bool-as-int aliases have different JSON; this is an exact
        # boolean check, not a same-canonical-byte integer-subclass claim.
        alias = int(literal)
        assert canonical(alias) != canonical(literal)
    else:
        alias = IntAlias(literal) if type(literal) is int else StrAlias(literal)
        assert type(alias) is not type(literal)
        assert canonical(alias) == canonical(literal)
    original = tamper_object(result, family)
    assert getattr(original, field) == literal
    bad = replace_artifact(result, family, replace(original, **{field: alias}))
    # Original independently literal pins stay correct for every byte-equal
    # alias. No production serializer, returned protocol or result supplies an
    # expected body or an expected digest.
    with pytest.raises(ValueError):
        call_verify(adapter, bad, fixture, pins, expected)


def expected_many_noop_assessment(fixture_body):
    """Independent R/two-snapshot/124-N script, never a production-engine oracle.

    First32 clocks are one second apart; following92 equal clock32. Exact
    five-second equality retains six dated quotes and every equal-time quote.
    No standing quantity changes, so no flow, fills, reloads or OFI quantity.
    """
    assert len(fixture_body["payload_bundle"]["payloads"]) == 128
    first = copy.deepcopy(fixture_body)
    first["payload_bundle"]["payloads"] = first["payload_bundle"]["payloads"][:5]
    first["payload_bundle"]["cursor_fixture"]["items"] = first["payload_bundle"]["cursor_fixture"][
        "items"
    ][:5]
    first["payload_bundle"]["cursor_fixture"]["declared_item_count"] = 5
    result = expected_idle_assessment(first)
    bound = expected_binding_assessment(fixture_body["payload_bundle"])
    protocol_pin, context_pin = digest(expected_protocol()), digest(fixture_body["context"])
    prefixes = {
        audit["decoded_position"]: digest(
            {
                "adapter_protocol_sha256": protocol_pin,
                "context_sha256": context_pin,
                "binding_prefix_sha256": audit["bound_prefix_sha256"],
            }
        )
        for audit in bound["audits"]
    }
    transitions = copy.deepcopy(result["transitions"][:3])
    state = empty_state()
    state.update(
        initialized=True,
        last_recv_ns=WARMUP - SECOND,
        orders=[
            {"order_id": 11, "state": {"side": "B", "price": 1_000_001, "size": 10}},
            {"order_id": 12, "state": {"side": "A", "price": 1_100_001, "size": 20}},
        ],
        bid_levels=[{"price": 1_000_001, "size": 10}],
        ask_levels=[{"price": 1_100_001, "size": 20}],
    )
    events, quotes, publications = [], [], []
    times = [NOON + min(index, 31) * SECOND for index in range(124)]
    for index, time in enumerate(times):
        ordinal, position = index + 1, index + 5
        last_receive = state["last_recv_ns"]
        gap = 0 if index == 0 else time - times[index - 1]
        history = [
            previous + 1 for previous in range(index + 1) if times[previous] >= time - 5 * SECOND
        ]
        ofi = [
            [times[previous], 0]
            for previous in range(1, index + 1)
            if times[previous] >= time - 5 * SECOND
        ]
        event = {
            "event_ordinal": ordinal,
            "closing_decoded_position": position,
            "closing_target_transition_ordinal": ordinal + 3,
            "ts_recv_ns": time,
            "target_positions": [position],
            "trade_positions": [],
            "execution_capture_positions": [position],
            "quote_ordinal": ordinal,
            "adapter_prefix_sha256": prefixes[position],
        }
        events.append(event | {"event_sha256": digest(event)})
        quote = {
            "quote_ordinal": ordinal,
            "event_ordinal": ordinal,
            "decoded_position": position,
            "ts_recv_ns": time,
            "bid": 1_000_001,
            "ask": 1_100_001,
            "bid_qty": 10,
            "ask_qty": 20,
            "prior_quote_gap_ns": gap,
            "ofi_generation": 2,
            "bid_depth5": [{"price": 1_000_001, "size": 10}],
            "ask_depth5": [{"price": 1_100_001, "size": 20}],
            "adapter_prefix_sha256": prefixes[position],
        }
        quotes.append(quote | {"quote_sha256": digest(quote)})
        if index < 32:
            features = idle_features()
            features[7][1] = math.log1p(gap / 1_000_000)
            features[17][1] = 0 if len(history) == 1 else 0.0
            features[18][1] = math.log1p(len(history))
            publication = {
                "publication_ordinal": ordinal,
                "quote_ordinal": ordinal,
                "event_ordinal": ordinal,
                "decoded_position": position,
                "ts_recv_ns": time,
                "adapter_prefix_sha256": prefixes[position],
                "features": features,
            }
            publications.append(publication | {"publication_sha256": digest(publication)})
        state.update(
            last_recv_ns=time,
            last_quote_ordinal=ordinal,
            ofi_generation=2,
            ofi_previous_quote_ordinal=ordinal,
            ofi_first_ts_ns=NOON,
            ofi_events=ofi,
            ofi_total=0,
            history_ofi_generation=2,
            history_quote_ordinals=history,
            history_reloads=[[times[previous - 1], 0, 0] for previous in history],
            execution_last_ts_ns=time,
            execution_audit={"completed_events": ordinal, "temporal_resets": 1},
            next_publication_ns=NOON + min(ordinal, 32) * SECOND,
            watch_since_ns=time,
        )
        transitions.append(
            {
                "decoded_position": position,
                "target_transition_ordinal": ordinal + 3,
                "disposition": "target_record",
                "snapshot": False,
                "exceptional_closed_clear": False,
                "order_id": 0,
                "before": None,
                "after": None,
                "initialized_before": True,
                "initialized_after": True,
                "last_recv_before": last_receive,
                "last_recv_after": time,
                "event_ordinal": ordinal,
                "quote_ordinal": ordinal,
                "publication_ordinal": ordinal if index < 32 else None,
                "state_sha256": digest(state),
            }
        )
    audits = [
        {
            "decoded_position": audit["decoded_position"],
            "disposition": "header"
            if audit["decoded_position"] == 1
            else transitions[audit["target_candidate_ordinal"] - 1]["disposition"],
            "instrument_id": audit["instrument_id"],
            "target_candidate_ordinal": audit["target_candidate_ordinal"],
            "target_transition_ordinal": audit["target_candidate_ordinal"],
            "binding_prefix_sha256": audit["bound_prefix_sha256"],
            "adapter_prefix_sha256": prefixes[audit["decoded_position"]],
        }
        for audit in bound["audits"]
    ]
    # Target-free end changes inactivity only, not history/execution. No event
    # or publication is manufactured; earlier states contain no future total.
    state.update(
        ofi_generation=3,
        ofi_previous_quote_ordinal=None,
        ofi_first_ts_ns=None,
        ofi_events=[],
        ofi_total=0,
        window_closed=True,
    )
    quality = copy.deepcopy(result["clock_quality"])
    quality.update(target_records=127, snapshot_records=2, non_snapshot_records=125)
    intervals = [
        copy.deepcopy(result["inactivity_intervals"][0]),
        {
            "start_ns": times[-1],
            "timer_fired_ns": times[-1] + 5 * SECOND + 1,
            "end_ns": END,
            "recovered": False,
            "trigger_decoded_position": None,
        },
    ]
    result.update(
        fixture_sha256=digest(fixture_body),
        fixture=fixture_body,
        binding_assessment=bound,
        audits=audits,
        transitions=transitions,
        events=events,
        quotes=quotes,
        publications=publications,
        inactivity_intervals=intervals,
        clock_quality=quality,
        terminal_state=state,
    )
    result.pop("assessment_sha256")
    return result | {"assessment_sha256": digest(result)}


@pytest.mark.parametrize("mode", [False, True])
def test_negative_standing_quote_prices_have_full_independent_complete_idle_oracle(mode):
    records = idle_records(mode)
    records[1] = records[1] | {"price": -1_000_001}
    records[2] = records[2] | {"price": -900_001}
    adapter, fixture, pins, body, result = replay_records(records, mode)
    expected = expected_idle_assessment(body, bid_price=-1_000_001, ask_price=-900_001)
    assert_complete_assessment(adapter, result, fixture, expected)
    assert call_fixture(adapter, "fixture_sha256", fixture, pins) == digest(body)
    assert (
        call_verify(adapter, assessment_object(adapter, fixture, expected), fixture, pins, expected)
        is None
    )


@pytest.mark.parametrize("feature", FEATURE_NAMES)
def test_all_37_feature_scalar_subclasses_are_refused_even_with_identical_json(feature):
    adapter, fixture, pins, _, result, expected = independent_submitted()
    literal = dict(expected["publications"][0]["features"])[feature]
    alias = FloatAlias(literal) if type(literal) is float else IntAlias(literal)
    assert type(alias) is not type(literal)
    assert canonical(alias) == canonical(literal)
    publication = replace(
        result.publications[0],
        features=tuple(
            (name, alias if name == feature else value)
            for name, value in result.publications[0].features
        ),
    )
    with pytest.raises(ValueError):
        call_verify(
            adapter, replace_artifact(result, "publication", publication), fixture, pins, expected
        )
