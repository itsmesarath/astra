"""Independent constructed oracles; no DBN decoding or historical input."""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from ai_trader.research import six_e_native_cursor_metadata as cursor

START = 1743984000000000000
END = 1744070400000000000
MAX_ID = 4294967295
FLAGS = (
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


class IntAlias(int):
    pass


class StrAlias(str):
    pass


class TupleAlias(tuple):
    pass


def _canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _pin(label):
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _protocol_body():
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
        "day_start_ns": START,
        "day_end_ns": END,
        "max_items": 128,
        "max_mapping_groups": 8,
        "max_intervals_per_group": 16,
        "max_total_intervals": 32,
        "max_body_bytes": 65536,
        "max_instrument_id": MAX_ID,
        "decoded_position_origin": 1,
        "target_candidate_ordinal_origin": 1,
        "header_included": True,
        "payload_pins": "opaque_caller_assertions",
        "prefix_complete_member_pin": "excluded",
        "authority_flags": {name: False for name in FLAGS},
    }


def _protocol_pin():
    return _digest(_protocol_body())


def _interval(start="2025-04-07", end="2025-04-08", symbol="731"):
    return cursor.MappingInterval(start, end, symbol)


def _header(*, target_symbol="731", mappings=None):
    if mappings is None:
        mappings = (cursor.MappingGroup("6EM5", (_interval(symbol=target_symbol),)),)
    return cursor.DeclaredHeader("GLBX.MDP3", "mbo", ("6E.FUT",), (), START, END, mappings)


def _fixture(*, ids=(731, 999, 731), target_symbol="731", mappings=None):
    items = (cursor.DecodedItem(1, "metadata", None, None),) + tuple(
        cursor.DecodedItem(position, "mbo", instrument, _pin(f"item-{position}"))
        for position, instrument in enumerate(ids, 2)
    )
    return cursor.CursorFixture(
        "synthetic-cursor-fixture",
        "synthetic-cursor-session",
        "2025-04-07",
        "6EM5",
        _header(target_symbol=target_symbol, mappings=mappings),
        _pin("asserted-complete-member"),
        len(items),
        items,
    )


def _interval_body(interval):
    return {
        "start_date": interval.start_date,
        "end_date": interval.end_date,
        "instrument_symbol": interval.instrument_symbol,
    }


def _group_body(group):
    return {
        "contract": group.contract,
        "intervals": [_interval_body(interval) for interval in group.intervals],
    }


def _header_body(header):
    return {
        "dataset": header.dataset,
        "schema": header.schema,
        "symbols": list(header.symbols),
        "not_found": list(header.not_found),
        "start_ns": header.start_ns,
        "end_ns": header.end_ns,
        "mappings": [_group_body(group) for group in header.mappings],
    }


def _item_body(item):
    return {
        "decoded_position": item.decoded_position,
        "kind": item.kind,
        "instrument_id": item.instrument_id,
        "payload_sha256": item.payload_sha256,
    }


def _fixture_body(fixture):
    return {
        "fixture_id": fixture.fixture_id,
        "source_session": fixture.source_session,
        "utc_date": fixture.utc_date,
        "contract": fixture.contract,
        "header": _header_body(fixture.header),
        "asserted_member_sha256": fixture.asserted_member_sha256,
        "declared_item_count": fixture.declared_item_count,
        "items": [_item_body(item) for item in fixture.items],
    }


def _oracle(fixture, mapped_id=731):
    """Manual complete body and chains, without production serializers."""
    protocol_pin = _protocol_pin()
    body = _fixture_body(fixture)
    fixture_pin = _digest(body)
    previous = _digest(
        {
            "protocol_sha256": protocol_pin,
            "fixture_id": fixture.fixture_id,
            "source_session": fixture.source_session,
            "utc_date": fixture.utc_date,
            "contract": fixture.contract,
            "header": _header_body(fixture.header),
        }
    )
    audits = []
    targets = 0
    foreign = 0
    for item in fixture.items:
        item_body = _item_body(item)
        if item.kind == "metadata":
            disposition, ordinal = "header", None
        elif item.instrument_id == mapped_id:
            targets += 1
            disposition, ordinal = "target_candidate", targets
        else:
            foreign += 1
            disposition, ordinal = "foreign", None
        previous = _digest({"previous_prefix_sha256": previous, "item": item_body})
        audits.append(
            {
                "decoded_position": item.decoded_position,
                "disposition": disposition,
                "instrument_id": item.instrument_id,
                "target_candidate_ordinal": ordinal,
                "item_sha256": _digest(item_body),
                "prefix_sha256": previous,
            }
        )
    result_body = {
        "status": "constructed_decoded_cursor_metadata_not_native_verification",
        "protocol_sha256": protocol_pin,
        "fixture_sha256": fixture_pin,
        "fixture": body,
        "mapped_instrument_id": mapped_id,
        "decoded_item_count": len(fixture.items),
        "target_candidate_count": targets,
        "foreign_count": foreign,
        "audits": audits,
        "authority_flags": {name: False for name in FLAGS},
    }
    return result_body, _digest(result_body)


def _assessment_body(result):
    return {
        "status": result.status,
        "protocol_sha256": result.protocol_sha256,
        "fixture_sha256": result.fixture_sha256,
        "fixture": _fixture_body(result.fixture),
        "mapped_instrument_id": result.mapped_instrument_id,
        "decoded_item_count": result.decoded_item_count,
        "target_candidate_count": result.target_candidate_count,
        "foreign_count": result.foreign_count,
        "audits": [
            {
                "decoded_position": audit.decoded_position,
                "disposition": audit.disposition,
                "instrument_id": audit.instrument_id,
                "target_candidate_ordinal": audit.target_candidate_ordinal,
                "item_sha256": audit.item_sha256,
                "prefix_sha256": audit.prefix_sha256,
            }
            for audit in result.audits
        ],
        "authority_flags": dict(result.authority_flags),
    }


def _assert_exact_tree(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual) == set(expected)
        for key in expected:
            _assert_exact_tree(actual[key], expected[key])
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for left, right in zip(actual, expected, strict=True):
            _assert_exact_tree(left, right)
    else:
        assert actual == expected


def _assess(fixture=None, mapped_id=731):
    if fixture is None:
        fixture = _fixture()
    expected, expected_pin = _oracle(fixture, mapped_id)
    result = cursor.assess(
        fixture,
        expected_fixture_sha256=expected["fixture_sha256"],
        expected_protocol_sha256=_protocol_pin(),
    )
    assert type(result) is cursor.CursorAssessment
    assert type(result.audits) is tuple
    assert all(type(audit) is cursor.CursorAudit for audit in result.audits)
    assert type(result.authority_flags) is tuple
    assert result.authority_flags == tuple((name, False) for name in FLAGS)
    assert all(type(pair) is tuple and type(pair[1]) is bool for pair in result.authority_flags)
    _assert_exact_tree(_assessment_body(result), expected)
    assert result.assessment_sha256 == expected_pin
    assert (
        cursor.fixture_sha256(fixture, expected_protocol_sha256=_protocol_pin())
        == expected["fixture_sha256"]
    )
    assert (
        cursor.verify(
            result,
            fixture,
            expected_fixture_sha256=expected["fixture_sha256"],
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=expected_pin,
        )
        is None
    )
    return result


def _invalid(fixture):
    for api in ("fixture", "assess", "verify"):
        original = cursor._fixture_body
        seen = []

        def observe(value, _original=original, _seen=seen):
            _seen.append(value)
            return _original(value)

        with pytest.MonkeyPatch.context() as patcher:
            patcher.setattr(cursor, "_fixture_body", observe)
            with pytest.raises(ValueError):
                if api == "fixture":
                    cursor.fixture_sha256(fixture, expected_protocol_sha256=_protocol_pin())
                elif api == "assess":
                    cursor.assess(
                        fixture,
                        expected_fixture_sha256="0" * 64,
                        expected_protocol_sha256=_protocol_pin(),
                    )
                else:
                    cursor.verify(
                        None,
                        fixture,
                        expected_fixture_sha256="0" * 64,
                        expected_protocol_sha256=_protocol_pin(),
                        expected_assessment_sha256="0" * 64,
                    )
        assert len(seen) == 1
        assert seen[0] is fixture


def _forbid_fixture_traversal(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Fixture traversal preceded the expected-pin phase")

    monkeypatch.setattr(cursor, "_fixture_body", forbidden)


def _bad_params(mapping):
    return [
        pytest.param(field, value, id=f"{field}-{index}")
        for field, values in mapping.items()
        for index, value in enumerate(values)
    ]


BAD_PINS = (
    None,
    True,
    1,
    b"a" * 64,
    "",
    "a" * 63,
    "a" * 65,
    "A" * 64,
    "g" * 64,
    "a" * 63 + "\n",
    "ａ" * 64,
    StrAlias("a" * 64),
)
BAD_NAMES = (
    None,
    True,
    0,
    b"synthetic-a",
    "",
    "synthetic-",
    "not-synthetic-a",
    "synthetic-a b",
    "synthetic-a/b",
    "synthetic-a\\b",
    "synthetic-a\n",
    "synthetic-é",
    "synthetic-" + "a" * 55,
    StrAlias("synthetic-a"),
)
BAD_DATES = (
    None,
    20250407,
    "",
    "2025-4-07",
    "2025-04-7",
    "2025-02-30",
    "2025-04-07T00:00:00",
    "2025-04-07Z",
    "2025-04-07\n",
    "２０２５-０４-０７",
    "1999-12-31",
    "2101-01-01",
    StrAlias("2025-04-07"),
)


def test_protocol_matches_complete_independent_literal():
    _assert_exact_tree(cursor.protocol(), _protocol_body())
    assert cursor.protocol_sha256() == _protocol_pin()
    assert len(FLAGS) == 26
    assert FLAGS == tuple(sorted(FLAGS))


def test_protocol_returns_deep_fresh_bodies():
    body = cursor.protocol()
    body["symbols"].append("changed")
    body["not_found"].append("changed")
    body["authority_flags"]["training_allowed"] = True
    body["max_items"] = 1
    body["new"] = "changed"
    _assert_exact_tree(cursor.protocol(), _protocol_body())
    assert cursor.protocol_sha256() == _protocol_pin()


def test_mutable_exported_constants_do_not_replace_literal_contract(monkeypatch):
    for name in (
        "VERSION",
        "STATUS",
        "MAX_ITEMS",
        "MAX_MAPPING_GROUPS",
        "MAX_INTERVALS_PER_GROUP",
        "MAX_TOTAL_INTERVALS",
        "MAX_BODY_BYTES",
        "MAX_INSTRUMENT_ID",
        "DAY_START_NS",
        "DAY_END_NS",
    ):
        monkeypatch.setattr(cursor, name, None, raising=False)
    _assert_exact_tree(cursor.protocol(), _protocol_body())
    assert cursor.protocol_sha256() == _protocol_pin()
    _assess()
    _invalid(replace(_fixture(), declared_item_count=129))


def test_complete_oracle_other_than_instrument_one():
    result = _assess()
    assert [audit.disposition for audit in result.audits] == [
        "header",
        "target_candidate",
        "foreign",
        "target_candidate",
    ]
    assert [audit.target_candidate_ordinal for audit in result.audits] == [None, 1, None, 2]
    assert [audit.decoded_position for audit in result.audits] == [1, 2, 3, 4]
    assert result.decoded_item_count == 1 + result.target_candidate_count + result.foreign_count


@pytest.mark.parametrize("mapped_id", (0, 1, 731, MAX_ID))
def test_id_boundaries_and_exact_mapping(mapped_id):
    foreign_id = 17 if mapped_id != 17 else 18
    _assess(_fixture(ids=(foreign_id, mapped_id), target_symbol=str(mapped_id)), mapped_id)


def test_leading_zero_mapping_retained_but_classifies_same_integer():
    plain = _assess()
    leading = _assess(_fixture(target_symbol="000731"))
    assert leading.mapped_instrument_id == plain.mapped_instrument_id == 731
    assert leading.fixture_sha256 != plain.fixture_sha256
    assert leading.audits[0].prefix_sha256 != plain.audits[0].prefix_sha256
    assert leading.audits[0].item_sha256 == plain.audits[0].item_sha256


@pytest.mark.parametrize("count", (2, 3, 8, 64, 128))
def test_complete_item_count_boundaries(count):
    result = _assess(_fixture(ids=(731,) * (count - 1)))
    assert len(result.audits) == count
    assert result.target_candidate_count == count - 1


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "fixture_id": BAD_NAMES,
            "source_session": BAD_NAMES,
            "utc_date": BAD_DATES + ("2025-04-08",),
            "contract": (None, "6EU5", "6em5", "6EM5 ", StrAlias("6EM5")),
            "asserted_member_sha256": BAD_PINS,
            "declared_item_count": (None, True, False, 4.0, IntAlias(4), -1, 0, 1, 3, 5, 129),
            "items": (None, [], (), TupleAlias(()), {}, "items"),
            "header": (None, {}, "header"),
        }
    ),
)
def test_bad_fixture_fields_are_refused_completely(field, value):
    _invalid(replace(_fixture(), **{field: value}))


@pytest.mark.parametrize("field", ("fixture_id", "source_session"))
def test_name_exact_length_and_allowed_punctuation(field):
    value = "synthetic-" + "a" * 54
    assert len(value) == 64
    _assess(replace(_fixture(), **{field: value}))
    _assess(replace(_fixture(), **{field: "synthetic-a._:-0"}))


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "dataset": (None, "", "glbx.mdp3", "GLBX.MDP3 ", StrAlias("GLBX.MDP3")),
            "schema": (None, "MBO", "mbp", StrAlias("mbo")),
            "symbols": (
                None,
                [],
                ["6E.FUT"],
                (),
                ("6EM5",),
                ("6E.FUT", "6E.FUT"),
                TupleAlias(("6E.FUT",)),
                (StrAlias("6E.FUT"),),
            ),
            "not_found": (None, [], ("6E.FUT",), TupleAlias(())),
            "start_ns": (None, True, float(START), IntAlias(START), START - 1, START + 1),
            "end_ns": (None, True, float(END), IntAlias(END), END - 1, END + 1),
            "mappings": (None, [], (), TupleAlias(()), {}),
        }
    ),
)
def test_bad_header_fields_are_refused(field, value):
    fixture = _fixture()
    _invalid(replace(fixture, header=replace(fixture.header, **{field: value})))


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "contract": (None, True, "", "x" * 33, "has space", "a/b", "é", StrAlias("6EM5")),
            "intervals": (None, [], {}, TupleAlias(()), "intervals"),
        }
    ),
)
def test_bad_mapping_group_fields_are_refused(field, value):
    group = replace(cursor.MappingGroup("6EM5", (_interval(),)), **{field: value})
    _invalid(_fixture(mappings=(group,)))


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "start_date": BAD_DATES + ("2025-04-08", "2025-04-09"),
            "end_date": BAD_DATES + ("2025-04-07", "2025-04-06"),
            "instrument_symbol": (
                None,
                True,
                731,
                "",
                "x" * 33,
                "not decimal",
                "a/b",
                "é",
                StrAlias("731"),
                "+731",
                "-731",
                "731.0",
                "4294967296",
                "99999999999999999999999999999999",
            ),
        }
    ),
)
def test_bad_requested_active_intervals_refuse(field, value):
    interval = replace(_interval(), **{field: value})
    _invalid(_fixture(mappings=(cursor.MappingGroup("6EM5", (interval,)),)))


@pytest.mark.parametrize(
    "intervals",
    (
        (),
        (_interval("2025-04-06", "2025-04-07"),),
        (_interval("2025-04-08", "2025-04-09"),),
        (_interval(), _interval()),
        (_interval("2025-04-06", "2025-04-08"), _interval()),
    ),
)
def test_absent_or_multiple_requested_active_mapping_refuses(intervals):
    _invalid(_fixture(mappings=(cursor.MappingGroup("6EM5", intervals),)))


def test_missing_requested_group_and_duplicate_keys_refuse():
    _invalid(_fixture(mappings=(cursor.MappingGroup("OTHER", (_interval(),)),)))
    _invalid(
        _fixture(
            mappings=(
                cursor.MappingGroup("6EM5", (_interval(),)),
                cursor.MappingGroup("6EM5", ()),
            )
        )
    )


def test_unrelated_and_inactive_nonnumeric_overlaps_are_retained():
    target = cursor.MappingGroup(
        "6EM5",
        (
            _interval("2000-01-01", "2025-04-07", "inactive:left"),
            _interval(),
            _interval("2025-04-08", "2100-12-31", "inactive:right"),
        ),
    )
    repeated = _interval("2000-01-01", "2100-12-31", "not:numeric")
    unrelated = cursor.MappingGroup("OTHER", (repeated, repeated))
    fixture = _fixture(mappings=(unrelated, target, cursor.MappingGroup("EMPTY", ())))
    result = _assess(fixture)
    assert len(result.fixture.header.mappings) == 3
    assert result.fixture.header.mappings[0].intervals == (repeated, repeated)


def test_mapping_names_and_active_symbol_exact_length_boundaries():
    leading_symbol = "0" * 29 + "731"
    assert len(leading_symbol) == 32
    mappings = (
        cursor.MappingGroup("6EM5", (_interval(symbol=leading_symbol),)),
        cursor.MappingGroup("x" * 32, (_interval("2000-01-01", "2000-01-02", "y" * 32),)),
    )
    _assess(_fixture(mappings=mappings))


def test_constructors_retain_without_normalization_and_public_calls_revalidate():
    item = cursor.DecodedItem(True, "mbo", 731.0, StrAlias("a" * 64))
    assert item.decoded_position is True
    assert type(item.instrument_id) is float
    assert type(item.payload_sha256) is StrAlias
    fixture = _fixture()
    _invalid(replace(fixture, items=(fixture.items[0], item) + fixture.items[2:]))


@pytest.mark.parametrize("groups", (1, 8))
def test_mapping_group_capacity_equality(groups):
    mappings = (cursor.MappingGroup("6EM5", (_interval(),)),) + tuple(
        cursor.MappingGroup(f"unrelated-{index}", ()) for index in range(groups - 1)
    )
    _assess(_fixture(mappings=mappings))


def test_mapping_group_overflow_refuses():
    mappings = (cursor.MappingGroup("6EM5", (_interval(),)),) + tuple(
        cursor.MappingGroup(f"unrelated-{index}", ()) for index in range(8)
    )
    _invalid(_fixture(mappings=mappings))


def test_interval_per_group_and_total_capacity_equality():
    target = cursor.MappingGroup("6EM5", (_interval(),))
    inactive = _interval("2000-01-01", "2000-01-02", "opaque")
    mappings = (
        target,
        cursor.MappingGroup("OTHER-A", (inactive,) * 16),
        cursor.MappingGroup("OTHER-B", (inactive,) * 15),
    )
    _assess(_fixture(mappings=mappings))


@pytest.mark.parametrize("overflow", ("group", "total"))
def test_interval_overflows_refuse(overflow):
    target = cursor.MappingGroup("6EM5", (_interval(),))
    inactive = _interval("2000-01-01", "2000-01-02", "opaque")
    if overflow == "group":
        mappings = (target, cursor.MappingGroup("OTHER", (inactive,) * 17))
    else:
        mappings = (
            target,
            cursor.MappingGroup("OTHER-A", (inactive,) * 16),
            cursor.MappingGroup("OTHER-B", (inactive,) * 16),
        )
    _invalid(_fixture(mappings=mappings))


def test_group_order_and_interval_order_change_complete_and_context_identity():
    target = cursor.MappingGroup("6EM5", (_interval(),))
    interval_a = _interval("2000-01-01", "2001-01-01", "opaque-a")
    interval_b = _interval("2001-01-01", "2002-01-01", "opaque-b")
    other = cursor.MappingGroup("OTHER", (interval_a, interval_b))
    first = _assess(_fixture(mappings=(target, other)))
    swapped_groups = _assess(_fixture(mappings=(other, target)))
    swapped_intervals = _assess(
        _fixture(mappings=(target, replace(other, intervals=(interval_b, interval_a))))
    )
    assert (
        len({first.fixture_sha256, swapped_groups.fixture_sha256, swapped_intervals.fixture_sha256})
        == 3
    )
    assert (
        len(
            {
                first.audits[0].prefix_sha256,
                swapped_groups.audits[0].prefix_sha256,
                swapped_intervals.audits[0].prefix_sha256,
            }
        )
        == 3
    )


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "decoded_position": (None, True, 2.0, IntAlias(2), -1, 0, 1, 3, 129),
            "kind": (None, "", "MBO", "metadata", "other", StrAlias("mbo")),
            "instrument_id": (None, True, False, 731.0, IntAlias(731), -1, MAX_ID + 1, "731"),
            "payload_sha256": BAD_PINS,
        }
    ),
)
def test_bad_mbo_item_fields_refuse(field, value):
    fixture = _fixture()
    changed = replace(fixture.items[1], **{field: value})
    _invalid(replace(fixture, items=(fixture.items[0], changed) + fixture.items[2:]))


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "decoded_position": (0, 2, True, 1.0, IntAlias(1)),
            "kind": (None, "mbo", "Metadata", StrAlias("metadata")),
            "instrument_id": (0, 731, False, "731"),
            "payload_sha256": ("0" * 64, "", False),
        }
    ),
)
def test_header_item_exact_none_and_position_semantics(field, value):
    fixture = _fixture()
    changed = replace(fixture.items[0], **{field: value})
    _invalid(replace(fixture, items=(changed,) + fixture.items[1:]))


def test_header_only_and_all_foreign_refuse():
    fixture = _fixture()
    _invalid(replace(fixture, declared_item_count=1, items=fixture.items[:1]))
    _invalid(_fixture(ids=(999, 999)))


def test_late_metadata_unexpected_type_and_bad_suffix_refuse():
    fixture = _fixture()
    _invalid(
        replace(
            fixture, items=fixture.items[:-1] + (cursor.DecodedItem(4, "metadata", None, None),)
        )
    )
    _invalid(replace(fixture, items=fixture.items[:-1] + (object(),)))
    _invalid(
        replace(
            fixture, items=fixture.items[:-1] + (replace(fixture.items[-1], payload_sha256="bad"),)
        )
    )


def test_no_sorting_reordering_gaps_or_repeated_positions():
    fixture = _fixture()
    _invalid(
        replace(
            fixture, items=(fixture.items[0], fixture.items[2], fixture.items[1], fixture.items[3])
        )
    )
    _invalid(
        replace(
            fixture, items=fixture.items[:-1] + (replace(fixture.items[-1], decoded_position=3),)
        )
    )
    _invalid(
        replace(
            fixture, items=fixture.items[:-1] + (replace(fixture.items[-1], decoded_position=5),)
        )
    )


def test_repeated_payload_pins_are_not_deduplicated():
    fixture = _fixture(ids=(731, 731, 731))
    shared = _pin("asserted-repeated-body")
    fixture = replace(
        fixture,
        items=(fixture.items[0],)
        + tuple(replace(item, payload_sha256=shared) for item in fixture.items[1:]),
    )
    result = _assess(fixture)
    assert result.target_candidate_count == 3
    assert len({audit.item_sha256 for audit in result.audits}) == 4
    assert [audit.target_candidate_ordinal for audit in result.audits[1:]] == [1, 2, 3]


@pytest.mark.parametrize("changed_index", (1, 2, 3))
def test_each_item_pin_binds_complete_identity_and_only_following_prefix(changed_index):
    fixture = _fixture()
    original = _assess(fixture)
    items = list(fixture.items)
    items[changed_index] = replace(items[changed_index], payload_sha256=_pin("changed assertion"))
    changed = _assess(replace(fixture, items=tuple(items)))
    assert changed.fixture_sha256 != original.fixture_sha256
    assert changed.assessment_sha256 != original.assessment_sha256
    assert changed.audits[:changed_index] == original.audits[:changed_index]
    assert changed.audits[changed_index].item_sha256 != original.audits[changed_index].item_sha256
    assert all(
        left.prefix_sha256 != right.prefix_sha256
        for left, right in zip(
            changed.audits[changed_index:], original.audits[changed_index:], strict=True
        )
    )


def test_foreign_pin_change_preserves_classification_not_decoded_prefix():
    fixture = _fixture()
    original = _assess(fixture)
    foreign = replace(
        fixture.items[2], instrument_id=1234, payload_sha256=_pin("foreign poison assertion")
    )
    changed = _assess(replace(fixture, items=fixture.items[:2] + (foreign,) + fixture.items[3:]))
    assert changed.target_candidate_count == original.target_candidate_count
    assert changed.foreign_count == original.foreign_count
    assert [audit.target_candidate_ordinal for audit in changed.audits] == [None, 1, None, 2]
    assert changed.audits[:2] == original.audits[:2]
    assert changed.audits[2].prefix_sha256 != original.audits[2].prefix_sha256
    assert changed.audits[3].prefix_sha256 != original.audits[3].prefix_sha256


def test_suffix_append_changes_whole_identity_but_preserves_every_consumed_audit():
    fixture = _fixture(ids=(731, 999))
    original = _assess(fixture)
    extended = replace(
        fixture,
        declared_item_count=5,
        items=fixture.items
        + (
            cursor.DecodedItem(4, "mbo", 731, _pin("new-target")),
            cursor.DecodedItem(5, "mbo", 999, _pin("new-foreign")),
        ),
        asserted_member_sha256=_pin("new-whole-member"),
    )
    changed = _assess(extended)
    assert changed.fixture_sha256 != original.fixture_sha256
    assert changed.assessment_sha256 != original.assessment_sha256
    assert changed.audits[:3] == original.audits


def test_complete_member_assertion_is_excluded_from_all_prefixes():
    fixture = _fixture()
    original = _assess(fixture)
    changed = _assess(replace(fixture, asserted_member_sha256=_pin("different complete member")))
    assert changed.fixture_sha256 != original.fixture_sha256
    assert changed.assessment_sha256 != original.assessment_sha256
    assert changed.audits == original.audits


@pytest.mark.parametrize("field", ("fixture_id", "source_session"))
def test_known_declared_context_binds_prefix_seed(field):
    fixture = _fixture()
    original = _assess(fixture)
    changed = _assess(replace(fixture, **{field: "synthetic-replacement"}))
    assert [audit.item_sha256 for audit in original.audits] == [
        audit.item_sha256 for audit in changed.audits
    ]
    assert all(
        left.prefix_sha256 != right.prefix_sha256
        for left, right in zip(original.audits, changed.audits, strict=True)
    )


def test_insertion_advances_decoded_positions_separately_from_candidate_ordinals():
    fixture = _fixture(ids=(731, 731))
    original = _assess(fixture)
    inserted = replace(
        fixture,
        declared_item_count=4,
        items=(fixture.items[0], cursor.DecodedItem(2, "mbo", 999, _pin("inserted")))
        + tuple(
            replace(item, decoded_position=item.decoded_position + 1) for item in fixture.items[1:]
        ),
    )
    changed = _assess(inserted)
    assert [audit.target_candidate_ordinal for audit in changed.audits] == [None, None, 1, 2]
    assert changed.audits[0] == original.audits[0]
    assert changed.audits[2].prefix_sha256 != original.audits[1].prefix_sha256


@pytest.mark.parametrize("pin", BAD_PINS)
@pytest.mark.parametrize("api", ("fixture", "assess", "verify"))
def test_expected_protocol_pin_syntax_before_fixture_traversal(monkeypatch, pin, api):
    _forbid_fixture_traversal(monkeypatch)
    fixture = object()
    with pytest.raises(ValueError):
        if api == "fixture":
            cursor.fixture_sha256(fixture, expected_protocol_sha256=pin)
        elif api == "assess":
            cursor.assess(fixture, expected_fixture_sha256="0" * 64, expected_protocol_sha256=pin)
        else:
            cursor.verify(
                object(),
                fixture,
                expected_fixture_sha256="0" * 64,
                expected_protocol_sha256=pin,
                expected_assessment_sha256="0" * 64,
            )


@pytest.mark.parametrize("pin", BAD_PINS)
@pytest.mark.parametrize("api", ("assess", "verify"))
def test_expected_fixture_pin_syntax_before_fixture_traversal(monkeypatch, pin, api):
    _forbid_fixture_traversal(monkeypatch)
    with pytest.raises(ValueError):
        if api == "assess":
            cursor.assess(
                object(), expected_fixture_sha256=pin, expected_protocol_sha256=_protocol_pin()
            )
        else:
            cursor.verify(
                object(),
                object(),
                expected_fixture_sha256=pin,
                expected_protocol_sha256=_protocol_pin(),
                expected_assessment_sha256="0" * 64,
            )


@pytest.mark.parametrize("pin", BAD_PINS)
def test_expected_assessment_pin_syntax_before_any_reconstruction(monkeypatch, pin):
    _forbid_fixture_traversal(monkeypatch)
    with pytest.raises(ValueError):
        cursor.verify(
            object(),
            object(),
            expected_fixture_sha256="0" * 64,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=pin,
        )


@pytest.mark.parametrize("api", ("fixture", "assess", "verify"))
def test_wrong_but_wellformed_protocol_expectation_refuses_before_fixture(monkeypatch, api):
    _forbid_fixture_traversal(monkeypatch)
    wrong = "0" * 64
    with pytest.raises(ValueError):
        if api == "fixture":
            cursor.fixture_sha256(object(), expected_protocol_sha256=wrong)
        elif api == "assess":
            cursor.assess(object(), expected_fixture_sha256=wrong, expected_protocol_sha256=wrong)
        else:
            cursor.verify(
                object(),
                object(),
                expected_fixture_sha256=wrong,
                expected_protocol_sha256=wrong,
                expected_assessment_sha256=wrong,
            )


@pytest.mark.parametrize("which", ("fixture", "assessment"))
def test_wrong_retained_expectation_is_never_adopted(which):
    fixture = _fixture()
    result = _assess(fixture)
    with pytest.raises(ValueError):
        if which == "fixture":
            cursor.assess(
                fixture, expected_fixture_sha256="0" * 64, expected_protocol_sha256=_protocol_pin()
            )
        else:
            cursor.verify(
                result,
                fixture,
                expected_fixture_sha256=result.fixture_sha256,
                expected_protocol_sha256=_protocol_pin(),
                expected_assessment_sha256="0" * 64,
            )


@pytest.mark.parametrize("length", (0, 1, 65533, 65534))
def test_private_complete_json_guard_literal_boundary(length):
    # A JSON string adds two quotes. This is not a valid CursorFixture capacity claim.
    value = "a" * length
    expected = _canonical(value)
    assert len(expected) == length + 2
    assert cursor._bounded_canonical(value) == expected


@pytest.mark.parametrize("length", (65535, 65536, 65537))
def test_private_complete_json_guard_excess_refuses(length):
    with pytest.raises(ValueError):
        cursor._bounded_canonical("a" * length)


@pytest.mark.parametrize(
    "value", (float("nan"), float("inf"), float("-inf"), object(), {"bad": object()})
)
def test_private_canonical_guard_normalizes_encoding_failures(value):
    with pytest.raises(ValueError):
        cursor._bounded_canonical(value)


def test_private_guard_uses_canonical_ascii_sorted_compact_bytes():
    value = {"z": [1, False, None], "a": "é\n"}
    assert cursor._bounded_canonical(value) == b'{"a":"\\u00e9\\n","z":[1,false,null]}'


def test_both_public_complete_bodies_use_required_shared_guard(monkeypatch):
    original = cursor._bounded_canonical
    seen = []

    def observe(value):
        seen.append(value)
        return original(value)

    monkeypatch.setattr(cursor, "_bounded_canonical", observe)
    fixture = _fixture()
    result = _assess(fixture)
    assert _fixture_body(fixture) in seen
    assert _assessment_body(result) in seen


@pytest.mark.parametrize("body_kind", ("fixture", "assessment"))
def test_shared_guard_failure_blocks_whole_public_result(monkeypatch, body_kind):
    original = cursor._bounded_canonical

    def refuse(value):
        if type(value) is dict and (
            (body_kind == "fixture" and set(value) == set(_fixture_body(_fixture())))
            or (body_kind == "assessment" and "audits" in value and "fixture" in value)
        ):
            raise ValueError("constructed complete-body refusal")
        return original(value)

    monkeypatch.setattr(cursor, "_bounded_canonical", refuse)
    fixture = _fixture()
    with pytest.raises(ValueError):
        cursor.assess(
            fixture,
            expected_fixture_sha256=_digest(_fixture_body(fixture)),
            expected_protocol_sha256=_protocol_pin(),
        )


@pytest.mark.parametrize(
    "field", ("dataset", "schema", "symbols", "not_found", "start_ns", "end_ns", "mappings")
)
def test_missing_header_field_normalizes_to_value_error(field):
    fixture = _fixture()
    object.__delattr__(fixture.header, field)
    _invalid(fixture)


@pytest.mark.parametrize(
    "field",
    (
        "fixture_id",
        "source_session",
        "utc_date",
        "contract",
        "header",
        "asserted_member_sha256",
        "declared_item_count",
        "items",
    ),
)
def test_missing_fixture_field_normalizes_to_value_error(field):
    fixture = _fixture()
    object.__delattr__(fixture, field)
    _invalid(fixture)


@pytest.mark.parametrize("field", ("decoded_position", "kind", "instrument_id", "payload_sha256"))
def test_missing_late_item_field_refuses_without_partial_acceptance(field):
    fixture = _fixture()
    object.__delattr__(fixture.items[-1], field)
    _invalid(fixture)


@pytest.mark.parametrize("field", ("start_date", "end_date", "instrument_symbol"))
def test_missing_interval_field_refuses(field):
    fixture = _fixture()
    object.__delattr__(fixture.header.mappings[0].intervals[0], field)
    _invalid(fixture)


@pytest.mark.parametrize("field", ("contract", "intervals"))
def test_missing_group_field_refuses(field):
    fixture = _fixture()
    object.__delattr__(fixture.header.mappings[0], field)
    _invalid(fixture)


@pytest.mark.parametrize("kind", ("fixture", "header", "group", "interval", "item"))
def test_exact_input_dataclass_types_reject_subclasses(kind):
    fixture = _fixture()
    if kind == "fixture":
        base = fixture
    elif kind == "header":
        base = fixture.header
    elif kind == "group":
        base = fixture.header.mappings[0]
    elif kind == "interval":
        base = fixture.header.mappings[0].intervals[0]
    else:
        base = fixture.items[-1]
    subclass = type(f"Forged{kind.title()}", (type(base),), {})
    changed = subclass(*(getattr(base, field.name) for field in fields(base)))
    if kind == "fixture":
        fixture = changed
    elif kind == "header":
        fixture = replace(fixture, header=changed)
    elif kind == "group":
        fixture = replace(fixture, header=replace(fixture.header, mappings=(changed,)))
    elif kind == "interval":
        group = replace(fixture.header.mappings[0], intervals=(changed,))
        fixture = replace(fixture, header=replace(fixture.header, mappings=(group,)))
    else:
        fixture = replace(fixture, items=fixture.items[:-1] + (changed,))
    _invalid(fixture)


@pytest.mark.parametrize(
    "class_name,names",
    (
        ("MappingInterval", ("start_date", "end_date", "instrument_symbol")),
        ("MappingGroup", ("contract", "intervals")),
        (
            "DeclaredHeader",
            ("dataset", "schema", "symbols", "not_found", "start_ns", "end_ns", "mappings"),
        ),
        ("DecodedItem", ("decoded_position", "kind", "instrument_id", "payload_sha256")),
        (
            "CursorFixture",
            (
                "fixture_id",
                "source_session",
                "utc_date",
                "contract",
                "header",
                "asserted_member_sha256",
                "declared_item_count",
                "items",
            ),
        ),
        (
            "CursorAudit",
            (
                "decoded_position",
                "disposition",
                "instrument_id",
                "target_candidate_ordinal",
                "item_sha256",
                "prefix_sha256",
            ),
        ),
        (
            "CursorAssessment",
            (
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
        ),
    ),
)
def test_exact_frozen_slotted_schemas(class_name, names):
    cls = getattr(cursor, class_name)
    assert tuple(field.name for field in fields(cls)) == names
    assert cls.__dataclass_params__.frozen
    assert set(cls.__slots__) == set(names)
    fixture = _fixture()
    result = _assess(fixture)
    instances = (
        fixture.header.mappings[0].intervals[0],
        fixture.header.mappings[0],
        fixture.header,
        fixture.items[0],
        fixture,
        result.audits[0],
        result,
    )
    instance = next(value for value in instances if type(value) is cls)
    assert not hasattr(instance, "__dict__")
    with pytest.raises(FrozenInstanceError):
        setattr(instance, names[0], None)


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "status": (
                None,
                "accepted",
                StrAlias("constructed_decoded_cursor_metadata_not_native_verification"),
            ),
            "protocol_sha256": ("0" * 64, None, StrAlias(_protocol_pin())),
            "fixture_sha256": ("0" * 64, None),
            "fixture": (None, {}, object()),
            "mapped_instrument_id": (True, 1, 731.0, IntAlias(731), None),
            "decoded_item_count": (True, 4.0, IntAlias(4), 3, 5, None),
            "target_candidate_count": (True, 2.0, IntAlias(2), 1, 3, None),
            "foreign_count": (False, 1.0, IntAlias(1), 0, 2, None),
            "audits": (None, [], (), TupleAlias(())),
            "authority_flags": (None, [], (), TupleAlias(()), {}),
            "assessment_sha256": (None, "0" * 64, StrAlias("0" * 64)),
        }
    ),
)
def test_every_result_field_tamper_refuses(field, value):
    fixture = _fixture()
    result = _assess(fixture)
    changed = replace(result, **{field: value})
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


@pytest.mark.parametrize(
    "field",
    (
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
)
def test_missing_result_field_refuses(field):
    fixture = _fixture()
    result = _assess(fixture)
    expected_pin = result.assessment_sha256
    object.__delattr__(result, field)
    with pytest.raises(ValueError):
        cursor.verify(
            result,
            fixture,
            expected_fixture_sha256=_digest(_fixture_body(fixture)),
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=expected_pin,
        )


@pytest.mark.parametrize("flag", FLAGS)
@pytest.mark.parametrize("value", (True, 0, None))
def test_every_authority_flag_tamper_refuses_even_false_int_alias(flag, value):
    fixture = _fixture()
    result = _assess(fixture)
    flags = tuple(
        (name, value if name == flag else state) for name, state in result.authority_flags
    )
    changed = replace(result, authority_flags=flags)
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


@pytest.mark.parametrize(
    "mutation",
    ("missing", "extra", "duplicate", "reordered", "pair-list", "name-alias", "pair-length"),
)
def test_complete_exact_authority_flag_container_refuses(mutation):
    fixture = _fixture()
    result = _assess(fixture)
    flags = result.authority_flags
    if mutation == "missing":
        flags = flags[:-1]
    elif mutation == "extra":
        flags = flags + (("new_authority", False),)
    elif mutation == "duplicate":
        flags = flags + (flags[-1],)
    elif mutation == "reordered":
        flags = tuple(reversed(flags))
    elif mutation == "pair-list":
        flags = (list(flags[0]),) + flags[1:]
    elif mutation == "name-alias":
        flags = ((StrAlias(flags[0][0]), False),) + flags[1:]
    else:
        flags = ((flags[0][0], False, False),) + flags[1:]
    changed = replace(result, authority_flags=flags)
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


@pytest.mark.parametrize(
    "field,value",
    _bad_params(
        {
            "decoded_position": (True, 2.0, IntAlias(2), 0, 3, None),
            "disposition": (None, "foreign", "target", StrAlias("target_candidate")),
            "instrument_id": (None, True, 731.0, IntAlias(731), 999),
            "target_candidate_ordinal": (None, True, 1.0, IntAlias(1), 0, 2),
            "item_sha256": (None, "0" * 64, StrAlias("0" * 64)),
            "prefix_sha256": (None, "0" * 64, StrAlias("0" * 64)),
        }
    ),
)
def test_every_audit_field_tamper_refuses(field, value):
    fixture = _fixture()
    result = _assess(fixture)
    audits = (result.audits[0], replace(result.audits[1], **{field: value})) + result.audits[2:]
    changed = replace(result, audits=audits)
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


@pytest.mark.parametrize(
    "field",
    (
        "decoded_position",
        "disposition",
        "instrument_id",
        "target_candidate_ordinal",
        "item_sha256",
        "prefix_sha256",
    ),
)
def test_missing_audit_field_refuses(field):
    fixture = _fixture()
    result = _assess(fixture)
    object.__delattr__(result.audits[-1], field)
    with pytest.raises(ValueError):
        cursor.verify(
            result,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


def test_header_position_one_bool_alias_refuses_even_json_alias():
    fixture = _fixture(ids=(1,), target_symbol="1")
    result = _assess(fixture, 1)
    for changed in (
        replace(result, mapped_instrument_id=True),
        replace(result, target_candidate_count=True),
        replace(result, foreign_count=False),
        replace(
            result, audits=(replace(result.audits[0], decoded_position=True),) + result.audits[1:]
        ),
        replace(result, audits=(result.audits[0], replace(result.audits[1], instrument_id=True))),
    ):
        with pytest.raises(ValueError):
            cursor.verify(
                changed,
                fixture,
                expected_fixture_sha256=result.fixture_sha256,
                expected_protocol_sha256=_protocol_pin(),
                expected_assessment_sha256=result.assessment_sha256,
            )


@pytest.mark.parametrize(
    "mutation", ("missing", "extra", "duplicate", "reordered", "dict", "subclass")
)
def test_audit_coverage_and_exact_nested_type_refuse(mutation):
    fixture = _fixture()
    result = _assess(fixture)
    audits = result.audits
    if mutation == "missing":
        audits = audits[:-1]
    elif mutation == "extra":
        audits = audits + (audits[-1],)
    elif mutation == "duplicate":
        audits = audits[:-1] + (audits[1],)
    elif mutation == "reordered":
        audits = tuple(reversed(audits))
    elif mutation == "dict":
        audits = (_assessment_body(result)["audits"][0],) + audits[1:]
    else:
        base = audits[0]
        subclass = type("ForgedAudit", (cursor.CursorAudit,), {})
        changed = subclass(*(getattr(base, field.name) for field in fields(base)))
        audits = (changed,) + audits[1:]
    changed_result = replace(result, audits=audits)
    with pytest.raises(ValueError):
        cursor.verify(
            changed_result,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


def test_exact_result_type_rejects_subclass():
    fixture = _fixture()
    result = _assess(fixture)
    subclass = type("ForgedAssessment", (cursor.CursorAssessment,), {})
    changed = subclass(*(getattr(result, field.name) for field in fields(result)))
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


def test_submitted_fixture_is_checked_completely_not_ignored():
    fixture = _fixture()
    result = _assess(fixture)
    equivalent = replace(fixture)
    cursor.verify(
        replace(result, fixture=equivalent),
        fixture,
        expected_fixture_sha256=result.fixture_sha256,
        expected_protocol_sha256=_protocol_pin(),
        expected_assessment_sha256=result.assessment_sha256,
    )
    changed = replace(
        result, fixture=replace(fixture, asserted_member_sha256=_pin("replacement member"))
    )
    with pytest.raises(ValueError):
        cursor.verify(
            changed,
            fixture,
            expected_fixture_sha256=result.fixture_sha256,
            expected_protocol_sha256=_protocol_pin(),
            expected_assessment_sha256=result.assessment_sha256,
        )


def test_rebuilding_determinism_and_coherent_replacement_are_not_authentication():
    fixture = _fixture()
    first = _assess(fixture)
    second = _assess(fixture)
    assert first == second
    replacement = replace(fixture, asserted_member_sha256=_pin("coherent replacement"))
    replaced = _assess(replacement)
    assert replaced.assessment_sha256 != first.assessment_sha256
    assert dict(replaced.authority_flags) == {name: False for name in FLAGS}


def test_no_native_body_fields_or_unreleased_operations_are_exposed():
    names = set(field.name for field in fields(cursor.DecodedItem))
    assert names == {"decoded_position", "kind", "instrument_id", "payload_sha256"}
    for name in (
        "ts_recv",
        "ts_event",
        "flags",
        "action",
        "side",
        "price",
        "size",
        "order_id",
        "byte_offset",
    ):
        assert name not in names
    for name in ("run", "main", "decode", "train", "send_order", "resume", "replay"):
        assert not hasattr(cursor, name)


def test_module_imports_are_stdlib_only_and_has_no_project_helper_import():
    tree = ast.parse(Path(cursor.__file__).read_text(encoding="utf-8"))
    forbidden = {
        "ai_trader",
        "databento",
        "databento_dbn",
        "torch",
        "numpy",
        "requests",
        "subprocess",
        "socket",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module is not None
            assert node.module.split(".")[0] not in forbidden


@pytest.mark.parametrize(
    "api,expected",
    (
        ("fixture_sha256", ("fixture", "expected_protocol_sha256")),
        ("assess", ("fixture", "expected_fixture_sha256", "expected_protocol_sha256")),
        (
            "verify",
            (
                "assessment",
                "fixture",
                "expected_fixture_sha256",
                "expected_protocol_sha256",
                "expected_assessment_sha256",
            ),
        ),
    ),
)
def test_exact_public_expected_pin_signatures(api, expected):
    signature = inspect.signature(getattr(cursor, api))
    assert tuple(signature.parameters) == expected
    for name in expected:
        if name.startswith("expected_"):
            assert signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert signature.parameters[name].default is inspect.Parameter.empty
