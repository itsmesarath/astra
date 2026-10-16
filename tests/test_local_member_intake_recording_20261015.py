"""Independent direct R1.1 behavior assertions, not interface-presence evidence."""

import copy
import importlib.util
from pathlib import Path

import local_member_intake_recording_oracles_20261015 as oracle
import pytest

_SOURCE = (
    Path(__file__).resolve().parents[1] / "scripts" / "local_member_intake_recording_20261015_1.py"
)


@pytest.fixture(scope="module")
def calculator():
    spec = importlib.util.spec_from_file_location("independent_r11_calculator", _SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exact(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key, value in expected.items():
            _exact(actual[key], value)
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for index, value in enumerate(expected):
            _exact(actual[index], value)
    else:
        assert actual == expected


def test_r11_evaluate_complete_six_variant_literal(calculator):
    fixture = oracle.six_variant_fixture()
    try:
        actual = calculator.evaluate_envelope(
            fixture["expression"], source_rules=fixture["source_rules"]
        )
    except NotImplementedError as error:
        raise AssertionError(
            "R1.1 complete six-variant envelope evaluation is unimplemented"
        ) from error
    _exact(actual, fixture["expected_evaluation"])


def test_r11_check_actual_preserves_whole_upper_width(calculator):
    fixture = oracle.six_variant_fixture()
    try:
        actual = calculator.check_actual(
            fixture["expression"], fixture["actual"], source_rules=fixture["source_rules"]
        )
    except NotImplementedError as error:
        raise AssertionError("R1.1 complete actual-fit width checking is unimplemented") from error
    _exact(actual, fixture["expected_actual"])


def _bounded_exact(actual, expected):
    """Complete equality with bounded failure messages, even for large fixtures."""
    if type(actual) is not type(expected):
        raise AssertionError("R1.1 complete result has an incorrect exact type")
    if type(expected) is dict:
        if actual.keys() != expected.keys():
            raise AssertionError("R1.1 complete result has an incorrect key set")
        for key, value in expected.items():
            _bounded_exact(actual[key], value)
    elif type(expected) is list:
        if len(actual) != len(expected):
            raise AssertionError("R1.1 complete result has an incorrect list length")
        for index, value in enumerate(expected):
            _bounded_exact(actual[index], value)
    elif actual != expected:
        raise AssertionError("R1.1 complete result differs from the independent literal")


def _refusal(calculator, api, expression, rules, reason, actual=None):
    with pytest.raises(calculator.RecordingRefusal) as caught:
        if api == "evaluate":
            calculator.evaluate_envelope(expression, source_rules=rules)
        else:
            calculator.check_actual(expression, actual, source_rules=rules)
    _bounded_exact(caught.value.reason, reason)


@pytest.mark.parametrize("case_id", oracle.EVALUATION_CASE_IDS)
def test_r11_all_literal_widths_and_complete_witnesses(calculator, case_id):
    fixture = oracle.evaluation_fixture(case_id)
    before = copy.deepcopy((fixture["expression"], fixture["source_rules"]))
    result = calculator.evaluate_envelope(
        fixture["expression"], source_rules=fixture["source_rules"]
    )
    _bounded_exact(result, fixture["expected_evaluation"])
    _bounded_exact(fixture["expression"], before[0])
    _bounded_exact(fixture["source_rules"], before[1])


@pytest.mark.parametrize("case_id", oracle.EVALUATION_CASE_IDS)
def test_r11_all_actual_domains_and_complete_widths(calculator, case_id):
    fixture = oracle.evaluation_fixture(case_id)
    before = copy.deepcopy(fixture)
    result = calculator.check_actual(
        fixture["expression"], fixture["actual"], source_rules=fixture["source_rules"]
    )
    _bounded_exact(result, fixture["expected_actual"])
    _bounded_exact(fixture, before)


@pytest.mark.parametrize("case_id", oracle.BOUNDARY_CASE_IDS)
def test_r11_exact_independent_input_depth_collection_and_matching_boundaries(calculator, case_id):
    fixture = oracle.boundary_fixture(case_id)
    if fixture["reason"] is not None:
        _refusal(
            calculator,
            fixture["api"],
            fixture["expression"],
            fixture["source_rules"],
            fixture["reason"],
            fixture.get("actual"),
        )
    elif fixture["api"] == "evaluate":
        result = calculator.evaluate_envelope(
            fixture["expression"], source_rules=fixture["source_rules"]
        )
        _bounded_exact(result, fixture["expected_evaluation"])
    else:
        result = calculator.check_actual(
            fixture["expression"], fixture["actual"], source_rules=fixture["source_rules"]
        )
        _bounded_exact(result, fixture["expected_actual"])


_KINDS = ("literal", "integer", "string", "one_of", "record", "array")
_FIELDS = {
    "literal": ("kind", "value"),
    "integer": ("kind", "lo", "hi"),
    "string": ("kind", "unit", "minimum", "maximum", "alphabet_ranges", "source_selector"),
    "one_of": ("kind", "items"),
    "record": ("kind", "fields"),
    "array": ("kind", "items"),
}
_MISSING_FIELD_IDS = tuple(kind + ":" + field for kind in _KINDS for field in _FIELDS[kind])


def _valid(kind):
    if kind == "literal":
        return {"kind": kind, "value": None}, {}
    if kind == "integer":
        return {"kind": kind, "lo": 0, "hi": 10}, {}
    if kind == "string":
        fixture = oracle.string_fixture("ascii_code_units", 0, 2, [[65, 65]], 4, [[65, 2]], "", 2)
        return fixture["expression"], fixture["source_rules"]
    if kind == "one_of":
        return {"kind": kind, "items": [{"kind": "literal", "value": None}]}, {}
    if kind == "record":
        return {"kind": kind, "fields": [["x", {"kind": "literal", "value": None}]]}, {}
    return {"kind": "array", "items": [{"kind": "literal", "value": None}]}, {}


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("case_id", _MISSING_FIELD_IDS)
def test_r11_every_expression_field_is_required(calculator, api, case_id):
    kind, field = case_id.split(":")
    expression, rules = _valid(kind)
    del expression[field]
    _refusal(calculator, api, expression, rules, "expression")


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("kind", _KINDS)
def test_r11_every_expression_rejects_extra_fields(calculator, api, kind):
    expression, rules = _valid(kind)
    expression["extra"] = None
    _refusal(calculator, api, expression, rules, "expression")


_INVALID_EXPRESSION_IDS = (
    "unknown_kind",
    "kind_bool",
    "kind_list",
    "root_none",
    "root_list",
    "integer_lo_bool",
    "integer_hi_bool",
    "integer_reverse",
    "integer_below_i64",
    "integer_above_u64",
    "integer_float",
    "one_of_empty",
    "one_of_tuple",
    "one_of_bad_last_branch",
    "array_tuple",
    "array_bad_child",
    "record_tuple",
    "record_pair_tuple",
    "record_pair_short",
    "record_pair_extra",
    "record_key_bool",
    "record_key_surrogate",
    "record_duplicate_key",
    "record_bad_child",
    "literal_float",
    "literal_nan",
    "literal_inf",
    "literal_tuple",
    "literal_bytes",
    "literal_set",
    "literal_key_int",
    "literal_key_surrogate",
    "literal_surrogate",
    "literal_low_surrogate",
    "literal_below_i64",
    "literal_above_u64",
    "string_unit",
    "string_min_bool",
    "string_max_bool",
    "string_reverse",
    "string_negative",
    "string_above_u64",
    "string_ranges_tuple",
    "string_range_extra",
    "string_range_missing",
    "string_range_bool",
    "string_range_reverse",
    "string_range_overlap",
    "string_range_unsorted",
    "string_surrogate_crossing",
    "string_surrogate_only",
    "string_ascii_nonascii",
    "string_above_unicode",
    "string_source_unknown",
    "string_source_unit_mismatch",
    "string_source_min_mismatch",
    "string_source_max_mismatch",
    "string_source_ranges_mismatch",
    "string_nonrealizable",
    "string_empty_nonrealizable",
)


def _invalid_expression(case_id):
    prefix = case_id.split("_", 1)[0]
    expression, rules = _valid(prefix if prefix in _KINDS else "literal")
    if case_id == "unknown_kind":
        expression["kind"] = "not_registered"
    elif case_id.startswith("kind_"):
        expression["kind"] = False if case_id == "kind_bool" else []
    elif case_id.startswith("root_"):
        expression = None if case_id == "root_none" else []
    elif case_id.startswith("integer_"):
        key, value = {
            "integer_lo_bool": ("lo", False),
            "integer_hi_bool": ("hi", True),
            "integer_reverse": ("lo", 11),
            "integer_below_i64": ("lo", -9223372036854775809),
            "integer_above_u64": ("hi", 18446744073709551616),
            "integer_float": ("hi", 1.0),
        }[case_id]
        expression[key] = value
    elif case_id.startswith("one_of_"):
        expression, rules = _valid("one_of")
        expression["items"] = (
            []
            if case_id == "one_of_empty"
            else (
                ()
                if case_id == "one_of_tuple"
                else [{"kind": "literal", "value": None}, {"kind": "unknown"}]
            )
        )
    elif case_id.startswith("array_"):
        expression["items"] = () if case_id == "array_tuple" else [None]
    elif case_id.startswith("record_"):
        expression["fields"] = {
            "record_tuple": (),
            "record_pair_tuple": [("x", {"kind": "literal", "value": None})],
            "record_pair_short": [["x"]],
            "record_pair_extra": [["x", {}, None]],
            "record_key_bool": [[False, {"kind": "literal", "value": None}]],
            "record_key_surrogate": [["\ud800", {"kind": "literal", "value": None}]],
            "record_duplicate_key": [
                ["x", {"kind": "literal", "value": None}],
                ["x", {"kind": "literal", "value": 0}],
            ],
            "record_bad_child": [["x", None]],
        }[case_id]
    elif case_id.startswith("literal_"):
        expression["value"] = {
            "literal_float": 1.0,
            "literal_nan": float("nan"),
            "literal_inf": float("inf"),
            "literal_tuple": (),
            "literal_bytes": b"x",
            "literal_set": set(),
            "literal_key_int": {0: None},
            "literal_key_surrogate": {"\ud800": None},
            "literal_surrogate": "\ud800",
            "literal_low_surrogate": "\udfff",
            "literal_below_i64": -9223372036854775809,
            "literal_above_u64": 18446744073709551616,
        }[case_id]
    else:
        changes = {
            "string_unit": ("unit", "utf8_bytes"),
            "string_min_bool": ("minimum", False),
            "string_max_bool": ("maximum", True),
            "string_reverse": ("minimum", 3),
            "string_negative": ("minimum", -1),
            "string_above_u64": ("maximum", 18446744073709551616),
            "string_ranges_tuple": ("alphabet_ranges", ()),
            "string_range_extra": ("alphabet_ranges", [{"lo": 65, "hi": 65, "x": 0}]),
            "string_range_missing": ("alphabet_ranges", [{"lo": 65}]),
            "string_range_bool": ("alphabet_ranges", [{"lo": False, "hi": 65}]),
            "string_range_reverse": ("alphabet_ranges", [{"lo": 66, "hi": 65}]),
            "string_range_overlap": (
                "alphabet_ranges",
                [{"lo": 65, "hi": 67}, {"lo": 67, "hi": 68}],
            ),
            "string_range_unsorted": (
                "alphabet_ranges",
                [{"lo": 67, "hi": 68}, {"lo": 65, "hi": 66}],
            ),
            "string_surrogate_crossing": ("alphabet_ranges", [{"lo": 55295, "hi": 57344}]),
            "string_surrogate_only": ("alphabet_ranges", [{"lo": 55296, "hi": 55296}]),
            "string_ascii_nonascii": ("alphabet_ranges", [{"lo": 128, "hi": 128}]),
            "string_above_unicode": ("alphabet_ranges", [{"lo": 1114112, "hi": 1114112}]),
            "string_source_unknown": ("source_selector", "unknown"),
            "string_source_unit_mismatch": ("unit", "unicode_scalar_values"),
            "string_source_min_mismatch": ("minimum", 1),
            "string_source_max_mismatch": ("maximum", 3),
            "string_source_ranges_mismatch": ("alphabet_ranges", [{"lo": 66, "hi": 66}]),
        }
        if case_id in ("string_nonrealizable", "string_empty_nonrealizable"):
            nonempty = case_id == "string_nonrealizable"
            fixture = oracle.string_fixture(
                "utf16_code_units",
                3 if nonempty else 1,
                3 if nonempty else 1,
                [[65536, 65536]] if nonempty else [],
                0,
                [],
                "",
                0,
            )
            expression, rules = fixture["expression"], fixture["source_rules"]
        else:
            key, value = changes[case_id]
            expression[key] = value
    return expression, rules


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("case_id", _INVALID_EXPRESSION_IDS)
def test_r11_complete_malformed_expression_refusals(calculator, api, case_id):
    expression, rules = _invalid_expression(case_id)
    _refusal(calculator, api, expression, rules, "expression")


_RULE_FIELDS = ("unit", "minimum", "maximum", "alphabet_ranges")
_BAD_RULE_IDS = (
    "root_none",
    "root_list",
    "selector_empty",
    "selector_nonascii",
    "selector_long",
    "selector_int",
    "row_none",
    "row_extra",
    "unit_unknown",
    "minimum_bool",
    "maximum_bool",
    "negative",
    "reverse",
    "above_u64",
    "ranges_tuple",
    "range_missing",
    "range_extra",
    "range_lo_bool",
    "range_hi_bool",
    "range_reverse",
    "range_overlap",
    "range_unsorted",
    "range_surrogate",
    "range_crosses_surrogate",
    "range_above_unicode",
    "ascii_nonascii",
)


def _unused_rule():
    return {"unit": "ascii_code_units", "minimum": 0, "maximum": 0, "alphabet_ranges": []}


def _bad_rules(case_id):
    row = _unused_rule()
    rules = {"unused": row}
    selectors = {
        "selector_empty": "",
        "selector_nonascii": "\u00e9",
        "selector_long": "x" * 257,
        "selector_int": 0,
    }
    if case_id in selectors:
        return {selectors[case_id]: row}
    if case_id.startswith("root_"):
        return None if case_id == "root_none" else []
    if case_id == "row_none":
        return {"unused": None}
    if case_id == "row_extra":
        row["extra"] = None
        return rules
    changes = {
        "unit_unknown": ("unit", "utf8_bytes"),
        "minimum_bool": ("minimum", False),
        "maximum_bool": ("maximum", True),
        "negative": ("minimum", -1),
        "reverse": ("minimum", 1),
        "above_u64": ("maximum", 18446744073709551616),
        "ranges_tuple": ("alphabet_ranges", ()),
        "range_missing": ("alphabet_ranges", [{"lo": 65}]),
        "range_extra": ("alphabet_ranges", [{"lo": 65, "hi": 65, "extra": None}]),
        "range_lo_bool": ("alphabet_ranges", [{"lo": False, "hi": 65}]),
        "range_hi_bool": ("alphabet_ranges", [{"lo": 0, "hi": True}]),
        "range_reverse": ("alphabet_ranges", [{"lo": 66, "hi": 65}]),
        "range_overlap": ("alphabet_ranges", [{"lo": 65, "hi": 67}, {"lo": 67, "hi": 68}]),
        "range_unsorted": ("alphabet_ranges", [{"lo": 67, "hi": 68}, {"lo": 65, "hi": 66}]),
        "range_surrogate": ("alphabet_ranges", [{"lo": 55296, "hi": 55296}]),
        "range_crosses_surrogate": ("alphabet_ranges", [{"lo": 55295, "hi": 57344}]),
        "range_above_unicode": ("alphabet_ranges", [{"lo": 1114112, "hi": 1114112}]),
        "ascii_nonascii": ("alphabet_ranges", [{"lo": 128, "hi": 128}]),
    }
    key, value = changes[case_id]
    row[key] = value
    return rules


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("case_id", _BAD_RULE_IDS)
def test_r11_all_unused_source_rules_are_validated_first(calculator, api, case_id):
    # Both later phases are wrong; the complete independent source phase wins.
    _refusal(
        calculator, api, {"kind": "unknown"}, _bad_rules(case_id), "source_rules", actual=object()
    )


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("field", _RULE_FIELDS)
def test_r11_each_unused_source_rule_field_is_required(calculator, api, field):
    rules = {"unused": _unused_rule()}
    del rules["unused"][field]
    _refusal(calculator, api, {"kind": "literal", "value": None}, rules, "source_rules")


@pytest.mark.parametrize("selector_id", ("max_ascii", "nul_ascii", "del_ascii"))
def test_r11_selector_is_declared_ascii_not_an_invented_path_policy(calculator, selector_id):
    selector = {"max_ascii": "x" * 256, "nul_ascii": "x\0", "del_ascii": "x\x7f"}[selector_id]
    expression, rules = _valid("string")
    rule = rules["independent_string"]
    expression["source_selector"] = selector
    actual = calculator.evaluate_envelope(expression, source_rules={selector: rule})
    _bounded_exact(
        actual, {"upper_ascii_bytes": 4, "witness": {"kind": "string_runs", "runs": [[65, 2]]}}
    )


def test_r11_unused_structurally_valid_nonrealizable_rule_is_not_an_expression(calculator):
    rules = {
        "unused": {
            "unit": "utf16_code_units",
            "minimum": 1,
            "maximum": 1,
            "alphabet_ranges": [{"lo": 65536, "hi": 65536}],
        }
    }
    result = calculator.evaluate_envelope({"kind": "literal", "value": None}, source_rules=rules)
    _bounded_exact(result, {"upper_ascii_bytes": 4, "witness": {"kind": "value", "value": None}})


_ACTUAL_IDS = (
    "literal_true_is_not_one",
    "literal_false_is_not_zero",
    "literal_nested_bool",
    "literal_extra_key",
    "literal_missing_key",
    "literal_array_length",
    "integer_bool",
    "integer_below",
    "integer_above",
    "string_alphabet",
    "string_units",
    "string_type",
    "record_extra",
    "record_missing",
    "record_type",
    "array_extra",
    "array_type",
    "one_of_none_match",
    "surrogate_value",
    "surrogate_key",
    "integer_above_u64",
    "integer_below_i64",
    "float",
    "nan",
    "bytes",
    "tuple",
    "nonstring_key",
)


def _bad_actual(case_id):
    expression, rules = _valid("literal")
    actual = None
    if case_id in ("literal_true_is_not_one", "literal_false_is_not_zero"):
        expression["value"] = case_id == "literal_true_is_not_one"
        actual = 1 if expression["value"] else 0
    elif case_id == "literal_nested_bool":
        expression["value"], actual = {"x": [True]}, {"x": [1]}
    elif case_id in ("literal_extra_key", "literal_missing_key"):
        expression["value"] = {"x": None}
        actual = {"x": None, "y": None} if case_id == "literal_extra_key" else {}
    elif case_id == "literal_array_length":
        expression["value"], actual = [None], []
    elif case_id.startswith("integer_") and case_id in (
        "integer_bool",
        "integer_below",
        "integer_above",
    ):
        expression, rules = _valid("integer")
        actual = {"integer_bool": True, "integer_below": -1, "integer_above": 11}[case_id]
    elif case_id.startswith("string_"):
        expression, rules = _valid("string")
        actual = {"string_alphabet": "B", "string_units": "AAA", "string_type": 0}[case_id]
    elif case_id.startswith("record_"):
        expression, rules = _valid("record")
        actual = {"record_extra": {"x": None, "y": None}, "record_missing": {}, "record_type": []}[
            case_id
        ]
    elif case_id.startswith("array_"):
        expression, rules = _valid("array")
        actual = [None, None] if case_id == "array_extra" else {}
    elif case_id == "one_of_none_match":
        expression, rules = _valid("one_of")
        actual = 0
    else:
        actual = {
            "surrogate_value": "\ud800",
            "surrogate_key": {"\udfff": None},
            "integer_above_u64": 18446744073709551616,
            "integer_below_i64": -9223372036854775809,
            "float": 0.0,
            "nan": float("nan"),
            "bytes": b"x",
            "tuple": (),
            "nonstring_key": {0: None},
        }[case_id]
    return expression, rules, actual


@pytest.mark.parametrize("case_id", _ACTUAL_IDS)
def test_r11_actual_complete_membership_is_not_just_width(calculator, case_id):
    expression, rules, actual = _bad_actual(case_id)
    _refusal(calculator, "actual", expression, rules, "actual", actual)


def test_r11_complete_expression_precedes_actual_even_after_first_matching_branch(calculator):
    expression = {
        "kind": "one_of",
        "items": [{"kind": "literal", "value": None}, {"kind": "integer", "lo": False, "hi": 1}],
    }
    _refusal(calculator, "actual", expression, {}, "expression", actual=object())


@pytest.mark.parametrize("api", ("evaluate", "actual"))
@pytest.mark.parametrize("cycle_id", ("array_expression", "literal_value"))
def test_r11_expression_active_cycles_refuse_without_repr_or_recursion(calculator, api, cycle_id):
    if cycle_id == "array_expression":
        expression = {"kind": "array", "items": []}
        expression["items"].append(expression)
    else:
        value = []
        value.append(value)
        expression = {"kind": "literal", "value": value}
    _refusal(calculator, api, expression, {}, "expression")


def test_r11_actual_active_cycle_is_not_a_noncyclic_alias(calculator):
    actual = []
    actual.append(actual)
    _refusal(calculator, "actual", {"kind": "literal", "value": None}, {}, "actual", actual)


def test_r11_source_rule_cycle_stays_in_source_phase(calculator):
    ranges = []
    ranges.append(ranges)
    rules = {
        "unused": {
            "unit": "ascii_code_units",
            "minimum": 0,
            "maximum": 0,
            "alphabet_ranges": ranges,
        }
    }
    _refusal(calculator, "evaluate", {"kind": "unknown"}, rules, "source_rules")


class _NotExactInt(int):
    pass


class _NotExactString(str):
    pass


class _NotExactList(list):
    pass


class _NotExactDict(dict):
    pass


class _ExplosiveObject:
    def __init__(self):
        self.touched_methods = []

    def __eq__(self, _other):
        self.touched_methods.append("__eq__")
        raise AssertionError("R1.1 hostile object equality must not be entered")

    def __len__(self):
        self.touched_methods.append("__len__")
        raise AssertionError("R1.1 hostile object length must not be entered")

    def __iter__(self):
        self.touched_methods.append("__iter__")
        raise AssertionError("R1.1 hostile object iteration must not be entered")


_METACLASS_TOUCHES = []


class _ExplosiveMetaclass(type):
    def __eq__(cls, _other):
        _METACLASS_TOUCHES.append("metaclass.__eq__")
        raise AssertionError("R1.1 hostile metaclass equality must not be entered")


_BAD_BUILTIN_IDS = (
    "int_subclass",
    "string_subclass",
    "list_subclass",
    "dict_subclass",
    "hostile",
    "metaclass",
)


def _bad_builtin(case_id):
    if case_id == "metaclass":
        _METACLASS_TOUCHES.clear()

        class _MetaclassObject(metaclass=_ExplosiveMetaclass):
            pass

        return _MetaclassObject()
    return {
        "int_subclass": _NotExactInt(0),
        "string_subclass": _NotExactString("x"),
        "list_subclass": _NotExactList(),
        "dict_subclass": _NotExactDict(),
        "hostile": _ExplosiveObject(),
    }[case_id]


@pytest.mark.parametrize("case_id", _BAD_BUILTIN_IDS)
@pytest.mark.parametrize("phase", ("literal", "actual"))
def test_r11_exact_builtin_domains_do_not_invoke_hostile_methods(calculator, case_id, phase):
    value = _bad_builtin(case_id)
    expression = {"kind": "literal", "value": value if phase == "literal" else None}
    _refusal(
        calculator,
        "evaluate" if phase == "literal" else "actual",
        expression,
        {},
        "expression" if phase == "literal" else "actual",
        actual=value,
    )
    if case_id == "hostile":
        _bounded_exact(value.touched_methods, [])
    elif case_id == "metaclass":
        _bounded_exact(_METACLASS_TOUCHES, [])


def test_r11_source_rule_and_record_keys_are_exact_strings(calculator):
    rules = {_NotExactString("unused"): _unused_rule()}
    _refusal(calculator, "evaluate", {"kind": "literal", "value": None}, rules, "source_rules")
    expression = {
        "kind": "record",
        "fields": [[_NotExactString("x"), {"kind": "literal", "value": None}]],
    }
    _refusal(calculator, "evaluate", expression, {}, "expression")


def test_r11_returned_mutable_witness_is_fresh_and_not_an_input_alias(calculator):
    expression = {"kind": "literal", "value": {"a": [0]}}
    first = calculator.evaluate_envelope(expression, source_rules={})
    _bounded_exact(
        first, {"upper_ascii_bytes": 9, "witness": {"kind": "value", "value": {"a": [0]}}}
    )
    first["witness"]["value"]["a"].append(1)
    _bounded_exact(expression, {"kind": "literal", "value": {"a": [0]}})
    second = calculator.evaluate_envelope(expression, source_rules={})
    _bounded_exact(
        second, {"upper_ascii_bytes": 9, "witness": {"kind": "value", "value": {"a": [0]}}}
    )


def test_r11_unicode_is_not_normalized_before_width_or_membership(calculator):
    fixture = oracle.string_fixture(
        "unicode_scalar_values", 0, 3, [[101, 101], [233, 233], [769, 769]], 20, [[233, 3]], "", 2
    )
    expression, rules = fixture["expression"], fixture["source_rules"]
    _bounded_exact(
        calculator.check_actual(expression, "\u00e9", source_rules=rules),
        {"actual_ascii_bytes": 8, "upper_ascii_bytes": 20},
    )
    _bounded_exact(
        calculator.check_actual(expression, "e\u0301", source_rules=rules),
        {"actual_ascii_bytes": 9, "upper_ascii_bytes": 20},
    )
    _refusal(
        calculator, "actual", {"kind": "literal", "value": "\u00e9"}, {}, "actual", actual="e\u0301"
    )


def test_r11_refusal_reason_is_read_only(calculator):
    error = calculator.RecordingRefusal("expression")
    _bounded_exact(error.reason, "expression")
    with pytest.raises(AttributeError):
        error.reason = "capacity"
