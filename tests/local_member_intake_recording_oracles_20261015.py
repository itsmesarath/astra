"""Independent R1.1 mathematical literals; never producer or native observations.

The complete witness and widths below are hand-derived from the registered
six-expression contract. No serializer, evaluator, reflection, protocol table,
or actual output supplies an expected value.
"""


def six_variant_fixture():
    """Return fresh complete inputs and the independent upper35/actual32 oracle."""
    return {
        "expression": {
            "kind": "record",
            "fields": [
                [
                    "a",
                    {
                        "kind": "array",
                        "items": [
                            {"kind": "literal", "value": None},
                            {"kind": "integer", "lo": 9, "hi": 10},
                            {
                                "kind": "string",
                                "unit": "ascii_code_units",
                                "minimum": 2,
                                "maximum": 2,
                                "alphabet_ranges": [{"lo": 34, "hi": 34}],
                                "source_selector": "independent_quote_pair",
                            },
                            {
                                "kind": "one_of",
                                "items": [
                                    {"kind": "literal", "value": False},
                                    {"kind": "literal", "value": "x"},
                                ],
                            },
                        ],
                    },
                ],
                ["z", {"kind": "record", "fields": []}],
            ],
        },
        "source_rules": {
            "independent_quote_pair": {
                "unit": "ascii_code_units",
                "minimum": 2,
                "maximum": 2,
                "alphabet_ranges": [{"lo": 34, "hi": 34}],
            },
        },
        "expected_evaluation": {
            "upper_ascii_bytes": 35,
            "witness": {
                "kind": "record",
                "fields": [
                    [
                        "a",
                        {
                            "kind": "array",
                            "items": [
                                {"kind": "value", "value": None},
                                {"kind": "value", "value": 10},
                                {"kind": "string_runs", "runs": [[34, 2]]},
                                {
                                    "kind": "one_of",
                                    "selected_index": 0,
                                    "witness": {"kind": "value", "value": False},
                                },
                            ],
                        },
                    ],
                    ["z", {"kind": "record", "fields": []}],
                ],
            },
        },
        "actual": {"a": [None, 9, '""', "x"], "z": {}},
        "expected_actual": {"actual_ascii_bytes": 32, "upper_ascii_bytes": 35},
    }


def _copy(value):
    """Copy only these independently constructed, noncyclic literal fixtures."""
    if type(value) is dict:
        return {key: _copy(item) for key, item in value.items()}
    if type(value) is list:
        return [_copy(item) for item in value]
    return value


def _value(value, width):
    return {
        "expression": {"kind": "literal", "value": _copy(value)},
        "source_rules": {},
        "expected_evaluation": {
            "upper_ascii_bytes": width,
            "witness": {"kind": "value", "value": _copy(value)},
        },
        "actual": _copy(value),
        "expected_actual": {"actual_ascii_bytes": width, "upper_ascii_bytes": width},
    }


LITERAL_ROWS = (
    ("null", None, 4),
    ("false", False, 5),
    ("true", True, 4),
    ("zero", 0, 1),
    ("negative_one", -1, 2),
    ("i64_min", -9223372036854775808, 20),
    ("i64_max", 9223372036854775807, 19),
    ("u64_max", 18446744073709551615, 20),
    ("empty_string", "", 2),
    ("quote", '"', 4),
    ("backslash", "\\", 4),
    ("backspace", "\b", 4),
    ("tab", "\t", 4),
    ("newline", "\n", 4),
    ("formfeed", "\f", 4),
    ("carriage_return", "\r", 4),
    ("nul", "\0", 8),
    ("control_one", "\x01", 8),
    ("control_seven", "\x07", 8),
    ("vertical_tab", "\x0b", 8),
    ("control_fourteen", "\x0e", 8),
    ("control_thirty_one", "\x1f", 8),
    ("space", " ", 3),
    ("slash", "/", 3),
    ("tilde", "~", 3),
    ("del", "\x7f", 8),
    ("bmp_0080", "\x80", 8),
    ("bmp_00e9", "\u00e9", 8),
    ("bmp_ffff", "\uffff", 8),
    ("nonbmp_10000", "\U00010000", 14),
    ("nonbmp_max", "\U0010ffff", 14),
    ("empty_object", {}, 2),
    ("empty_array", [], 2),
    ("empty_key", {"": 0}, 6),
    ("nonbmp_key", {"\U00010000": 0}, 18),
    ("complete_object", {"a": 0, "b": False}, 17),
    ("complete_array", [None, False, -10], 16),
    ("digest_not_stripped", {"receipt_sha256": "0" * 64}, 85),
)

INTEGER_ROWS = (
    ("decimal_transition", 9, 10, 2, 10, 9, 1),
    ("negative_transition", -10, -9, 3, -10, -9, 2),
    ("endpoint_tie", 0, 9, 1, 0, 9, 1),
    ("signed_tie", -99, 99, 3, -99, 99, 2),
    (
        "native_signed",
        -9223372036854775808,
        9223372036854775807,
        20,
        -9223372036854775808,
        9223372036854775807,
        19,
    ),
    ("native_unsigned", 0, 18446744073709551615, 20, 18446744073709551615, 0, 1),
)

# Unit/ranges/lengths, upper, exact RLE, actual, actual width are all fixed literals.
STRING_ROWS = (
    ("ascii_all", "ascii_code_units", 2, 2, [[0, 127]], 14, [[0, 2]], "\0\0", 14),
    ("ascii_quotes", "ascii_code_units", 2, 2, [[34, 34]], 6, [[34, 2]], '""', 6),
    ("ascii_short_escape", "ascii_code_units", 2, 2, [[8, 13]], 14, [[11, 2]], "\t\n", 6),
    ("ascii_printable_tie", "ascii_code_units", 3, 3, [[65, 90]], 5, [[65, 3]], "XYZ", 5),
    (
        "scalar_nonbmp",
        "unicode_scalar_values",
        3,
        3,
        [[65, 65], [65536, 65536]],
        38,
        [[65536, 3]],
        "A\U00010000A",
        16,
    ),
    (
        "utf16_mixed",
        "utf16_code_units",
        3,
        3,
        [[65, 65], [65536, 65536]],
        15,
        [[65536, 1], [65, 1]],
        "AAA",
        5,
    ),
    (
        "utf16_only_pair",
        "utf16_code_units",
        0,
        3,
        [[65536, 65536]],
        14,
        [[65536, 1]],
        "\U00010000",
        14,
    ),
    (
        "utf16_equal_ratio",
        "utf16_code_units",
        3,
        3,
        [[0, 0], [65536, 65536]],
        20,
        [[65536, 1], [0, 1]],
        "\0\0\0",
        20,
    ),
    ("empty_alphabet", "unicode_scalar_values", 0, 10, [], 2, [], "", 2),
    ("empty_length", "ascii_code_units", 0, 0, [[65, 65]], 2, [], "", 2),
    (
        "bmp_surrogate_gap",
        "unicode_scalar_values",
        1,
        1,
        [[55295, 55295], [57344, 57344]],
        8,
        [[55295, 1]],
        "\ue000",
        8,
    ),
    (
        "scalar_u64_compact",
        "unicode_scalar_values",
        0,
        18446744073709551615,
        [[65536, 65536]],
        221360928884514619382,
        [[65536, 18446744073709551615]],
        "",
        2,
    ),
    (
        "utf16_u64_compact",
        "utf16_code_units",
        0,
        18446744073709551615,
        [[65536, 65536]],
        110680464442257309686,
        [[65536, 9223372036854775807]],
        "",
        2,
    ),
)

EVALUATION_CASE_IDS = (
    tuple("literal_" + row[0] for row in LITERAL_ROWS)
    + tuple("integer_" + row[0] for row in INTEGER_ROWS)
    + tuple("string_" + row[0] for row in STRING_ROWS)
    + ("one_of_smaller_actual", "one_of_width_tie", "record_order", "array_alias")
)


def string_fixture(unit, minimum, maximum, ranges, upper, runs, actual, actual_width):
    rule = {
        "unit": unit,
        "minimum": minimum,
        "maximum": maximum,
        "alphabet_ranges": [{"lo": lo, "hi": hi} for lo, hi in ranges],
    }
    expression = {"kind": "string", **_copy(rule), "source_selector": "independent_string"}
    return {
        "expression": expression,
        "source_rules": {"independent_string": rule},
        "expected_evaluation": {
            "upper_ascii_bytes": upper,
            "witness": {"kind": "string_runs", "runs": _copy(runs)},
        },
        "actual": actual,
        "expected_actual": {"actual_ascii_bytes": actual_width, "upper_ascii_bytes": upper},
    }


def evaluation_fixture(case_id):
    for name, value, width in LITERAL_ROWS:
        if case_id == "literal_" + name:
            return _value(value, width)
    for name, lo, hi, upper, selected, actual, width in INTEGER_ROWS:
        if case_id == "integer_" + name:
            return {
                "expression": {"kind": "integer", "lo": lo, "hi": hi},
                "source_rules": {},
                "expected_evaluation": {
                    "upper_ascii_bytes": upper,
                    "witness": {"kind": "value", "value": selected},
                },
                "actual": actual,
                "expected_actual": {"actual_ascii_bytes": width, "upper_ascii_bytes": upper},
            }
    for row in STRING_ROWS:
        if case_id == "string_" + row[0]:
            return string_fixture(*row[1:])
    if case_id in ("one_of_smaller_actual", "one_of_width_tie"):
        tie = case_id == "one_of_width_tie"
        first, second, upper, actual_width = (False, "abc", 5, 5) if tie else (None, "x", 4, 3)
        return {
            "expression": {
                "kind": "one_of",
                "items": [
                    {"kind": "literal", "value": first},
                    {"kind": "literal", "value": second},
                ],
            },
            "source_rules": {},
            "expected_evaluation": {
                "upper_ascii_bytes": upper,
                "witness": {
                    "kind": "one_of",
                    "selected_index": 0,
                    "witness": {"kind": "value", "value": first},
                },
            },
            "actual": second,
            "expected_actual": {"actual_ascii_bytes": actual_width, "upper_ascii_bytes": upper},
        }
    if case_id == "record_order":
        return {
            "expression": {
                "kind": "record",
                "fields": [
                    ["b", {"kind": "literal", "value": False}],
                    ["a", {"kind": "literal", "value": 0}],
                ],
            },
            "source_rules": {},
            "expected_evaluation": {
                "upper_ascii_bytes": 17,
                "witness": {
                    "kind": "record",
                    "fields": [
                        ["b", {"kind": "value", "value": False}],
                        ["a", {"kind": "value", "value": 0}],
                    ],
                },
            },
            "actual": {"a": 0, "b": False},
            "expected_actual": {"actual_ascii_bytes": 17, "upper_ascii_bytes": 17},
        }
    if case_id == "array_alias":
        child = {"kind": "literal", "value": {"x": 0}}
        actual = {"x": 0}
        return {
            "expression": {"kind": "array", "items": [child, child]},
            "source_rules": {},
            "expected_evaluation": {
                "upper_ascii_bytes": 17,
                "witness": {
                    "kind": "array",
                    "items": [
                        {"kind": "value", "value": {"x": 0}},
                        {"kind": "value", "value": {"x": 0}},
                    ],
                },
            },
            "actual": [actual, actual],
            "expected_actual": {"actual_ascii_bytes": 17, "upper_ascii_bytes": 17},
        }
    raise AssertionError("Unknown independent evaluation case")


BOUNDARY_CASE_IDS = (
    "input_eval_equal",
    "input_eval_excess",
    "input_actual_equal",
    "input_actual_excess",
    "depth_expression_equal",
    "depth_expression_excess",
    "depth_actual_equal",
    "depth_actual_excess",
    "collection_equal",
    "collection_excess",
    "match_equal",
    "match_excess",
    "match_first_branch_stops",
    "record_match_equal",
    "record_match_excess",
    "array_match_equal",
    "array_match_excess",
    "mutable_alias_equal",
    "mutable_alias_first_excess",
)


def boundary_fixture(case_id):
    """Complete fixed recipes; expected arithmetic is literal, never measured."""
    if case_id in ("mutable_alias_equal", "mutable_alias_first_excess"):
        # Shared LIST: W(shared)=2+524275; Wtotal=26+2*524275=1048576.
        # Prefixing null makes Wtotal=1048577, reached inside the second alias.
        text = "a" * 524275
        shared = [text]
        excess = case_id == "mutable_alias_first_excess"
        value = [None, shared, shared] if excess else [shared, shared]
        result = {
            "expression": {"kind": "literal", "value": value},
            "source_rules": {},
            "api": "evaluate",
            "reason": "capacity" if excess else None,
        }
        if not excess:
            result["expected_evaluation"] = {
                "upper_ascii_bytes": 1048561,
                "witness": {"kind": "value", "value": [[text], [text]]},
            }
        return result
    if case_id in ("input_eval_equal", "input_eval_excess"):
        count = 1048554 if case_id == "input_eval_equal" else 1048555
        value = "a" * count
        result = _value(value, 1048556)
        result["api"] = "evaluate"
        result["reason"] = None if case_id == "input_eval_equal" else "capacity"
        return result
    if case_id in ("input_actual_equal", "input_actual_excess"):
        result = _value("a" * 524246, 524248)
        result["source_rules"] = {
            "xx": {"unit": "ascii_code_units", "minimum": 0, "maximum": 0, "alphabet_ranges": []}
        }
        if case_id == "input_actual_excess":
            result["actual"] += "a"
        result["api"] = "actual"
        result["reason"] = None if case_id == "input_actual_equal" else "capacity"
        return result
    if case_id in ("depth_expression_equal", "depth_expression_excess"):
        value = None
        count = 62 if case_id == "depth_expression_equal" else 63
        for _ in range(count):
            value = [value]
        result = _value(value, 128)
        result["api"] = "evaluate"
        result["reason"] = None if case_id == "depth_expression_equal" else "capacity"
        return result
    if case_id in ("depth_actual_equal", "depth_actual_excess"):
        result = _value(None, 4)
        count = 63 if case_id == "depth_actual_equal" else 64
        for _ in range(count):
            result["actual"] = [result["actual"]]
        result["api"] = "actual"
        result["reason"] = "actual" if case_id == "depth_actual_equal" else "capacity"
        return result
    if case_id in ("collection_equal", "collection_excess"):
        count = 65536 if case_id == "collection_equal" else 65537
        result = _value([None] * count, 327681)
        result["api"] = "evaluate"
        result["reason"] = None if case_id == "collection_equal" else "capacity"
        return result
    if case_id in ("match_equal", "match_excess", "match_first_branch_stops"):
        value = "a" * 349523
        first = "bbb" if case_id in ("match_excess", "match_first_branch_stops") else "bb"
        branches = [{"kind": "literal", "value": first}, {"kind": "literal", "value": value}]
        if case_id == "match_first_branch_stops":
            branches.reverse()
        return {
            "expression": {"kind": "one_of", "items": branches},
            "source_rules": {},
            "actual": value,
            "expected_actual": {"actual_ascii_bytes": 349525, "upper_ascii_bytes": 349525},
            "api": "actual",
            "reason": "capacity" if case_id == "match_excess" else None,
        }
    if case_id in (
        "record_match_equal",
        "record_match_excess",
        "array_match_equal",
        "array_match_excess",
    ):
        # T = 8 + len(mismatching literal) + 4*262142. Registered order matters.
        fixture = string_fixture(
            "ascii_code_units", 262142, 262142, [[97, 97]], 262144, [[97, 262142]], "", 2
        )
        string_expression = fixture["expression"]
        excess = case_id.endswith("excess")
        wrong = {"kind": "literal", "value": "b" if excess else ""}
        value = "a" * 262142
        if case_id.startswith("record"):
            first = {"kind": "record", "fields": [["b", _copy(string_expression)], ["a", wrong]]}
            second = {
                "kind": "record",
                "fields": [["b", _copy(string_expression)], ["a", _copy(string_expression)]],
            }
            actual, width = {"a": value, "b": value}, 524299
        else:
            first = {"kind": "array", "items": [_copy(string_expression), wrong]}
            second = {
                "kind": "array",
                "items": [_copy(string_expression), _copy(string_expression)],
            }
            actual, width = [value, value], 524291
        return {
            "expression": {"kind": "one_of", "items": [first, second]},
            "source_rules": fixture["source_rules"],
            "actual": actual,
            "expected_actual": {"actual_ascii_bytes": width, "upper_ascii_bytes": width},
            "api": "actual",
            "reason": "capacity" if excess else None,
        }
    raise AssertionError("Unknown independent boundary case")
