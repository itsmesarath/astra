"""Qualify static close sizing data, never native cleanup or new source behavior.

Every expected width, tagged witness and complete synthetic body is independently
fixed in the oracle JSON. The source packet and calculator do not author them.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_PACKET = _ROOT / "scripts" / "local_member_intake_late_close_component_20261015_1.json"
_ORACLE = _ROOT / "tests" / "local_member_intake_late_close_oracles_20261015.json"
_CALCULATOR = _ROOT / "scripts" / "local_member_intake_recording_20261015_1.py"
_NAMES = (
    "close_return_success",
    "close_return_failure",
    "close_trace_success",
    "close_trace_failure",
    "parent_close_success",
    "parent_close_failure",
    "close_lifecycle",
    "close_component",
)
_ACTUAL_IDS = _NAMES + ("close_component_failure",)
_REFUSAL_IDS = (
    "handle_zero",
    "handle_above_u64",
    "return_zero_success",
    "return_below_i32",
    "error_above_u32",
    "close_ordinal_first_excess",
    "trace_ordinal_first_excess",
    "negative_clock",
    "attempted_bool_not_zero",
    "unknown_phase",
    "unknown_role",
    "extra_trace_field",
    "missing_close_return",
    "extra_lifecycle_link",
    "success_error_not_null",
    "failure_error_null",
)
_PACKET_KEYS = (
    "version",
    "basis",
    "source_sites",
    "domains",
    "source_rules",
    "expressions",
    "occurrences",
    "accounting",
    "association_obligations",
    "scope",
)
_ORACLE_KEYS = (
    "version",
    "expression_names",
    "evaluations",
    "actual_cases",
    "phase_rows",
    "role_rows",
    "refusal_cases",
    "association_cases",
    "accounting_cases",
)
_FLAG_NAMES = (
    "source_authenticated",
    "collection_receipt_authenticated",
    "native_runtime_authenticated",
    "native_abi_authenticated",
    "native_wire_authenticated",
    "native_header_authenticated",
    "native_eof_authenticated",
    "feed_authenticated",
    "calendar_authenticated",
    "historical_read_authorized",
    "historical_validation_authorized",
    "book_acceptance_authorized",
    "event_acceptance_authorized",
    "feature_acceptance_authorized",
    "account_authorized",
    "funding_authorized",
    "receipt_authorized",
    "cash_authorized",
    "margin_authorized",
    "risk_authorized",
    "storage_authorized",
    "resume_authorized",
    "execution_authorized",
    "trading_authorized",
    "training_authorized",
    "scoring_authorized",
    "independent_validation_authorized",
    "promotion_authorized",
)
_INTEGER_BOUNDS = {
    "handle": [1, 18446744073709551615],
    "api_ordinal": [0, 4095],
    "lifecycle_ordinal": [0, 4095],
    "close_ordinal": [0, 15],
    "clock": [0, 18446744073709551615],
    "negative_bool_success": [-2147483648, -1],
    "positive_bool_success": [1, 2147483647],
    "saved_error": [0, 4294967295],
}


def _exact(actual, expected):
    if type(actual) is not type(expected):
        raise AssertionError("Late-close complete literal type mismatch")
    if type(expected) is dict:
        if actual.keys() != expected.keys():
            raise AssertionError("Late-close complete literal key-set mismatch")
        for key, value in expected.items():
            _exact(actual[key], value)
    elif type(expected) is list:
        if len(actual) != len(expected):
            raise AssertionError("Late-close complete literal list-length mismatch")
        for index, value in enumerate(expected):
            _exact(actual[index], value)
    elif actual != expected:
        raise AssertionError("Late-close complete literal value mismatch")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AssertionError("Duplicate key in complete registered sizing data")
        result[key] = value
    return result


def _not_integer(_token):
    raise AssertionError("Noninteger number in registered sizing data")


def _read(path):
    with path.open("rb") as stream:
        raw = stream.read(262145)
        if len(raw) > 262144 or not raw:
            raise AssertionError("Registered sizing data exceeds its complete read bound")
        if stream.read(1) != b"":
            raise AssertionError("Registered sizing data lacks complete EOF")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise AssertionError("Registered sizing data has a UTF8 BOM")
    return json.loads(
        raw.decode("utf-8", errors="strict"),
        object_pairs_hook=_pairs,
        parse_float=_not_integer,
        parse_constant=_not_integer,
    )


@pytest.fixture(scope="module")
def packet():
    return _read(_PACKET)


@pytest.fixture(scope="module")
def oracle():
    return _read(_ORACLE)


@pytest.fixture(scope="module")
def calculator():
    spec = importlib.util.spec_from_file_location("late_close_frozen_pure_calculator", _CALCULATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(rows, case_id):
    matches = [row for row in rows if row["id"] == case_id]
    if len(matches) != 1:
        raise AssertionError("Independent oracle case is missing or duplicated")
    return matches[0]


def _actual(oracle, case_id):
    return copy.deepcopy(_row(oracle["actual_cases"], case_id))


def _mutate(value, path, replacement, delete=False):
    target = value
    for part in path[:-1]:
        target = target[part]
    if delete:
        del target[path[-1]]
    else:
        target[path[-1]] = copy.deepcopy(replacement)


def test_late_close_complete_source_and_oracle_rosters(packet, oracle):
    _exact(sorted(packet), sorted(_PACKET_KEYS))
    _exact(sorted(oracle), sorted(_ORACLE_KEYS))
    _exact(packet["version"], "local-member-intake-late-close-component-v1")
    _exact(oracle["version"], "local-member-intake-late-close-oracles-v1")
    _exact(
        packet["basis"],
        [
            {
                "role": "host_source",
                "path": "scripts/local_member_intake_bootstrap_host_20261015_1.py",
                "raw_byte_length": 96913,
                "raw_sha256": "518e75be61be5fdc5535d9619b790822a5bed8fa7f4607f1b5bfe936f2e69b7f",
            },
            {
                "role": "protocol",
                "path": "scripts/local_member_intake_bootstrap_protocol_20261015_3.json",
                "raw_byte_length": 171369,
                "raw_sha256": "2252ebefe2d38b14f5c915b3a1b9fbb2c8bc960a02477372bb1dd0ea7114c31f",
            },
            {
                "role": "calculator_contract",
                "path": "docs/6E_LOCAL_MEMBER_INTAKE_ENVELOPE_CALCULATOR_20261015.md",
                "raw_byte_length": 14433,
                "raw_sha256": "c29bfaf214dd8132d55484f2c2966b18bc6eefc64e461aa68eac2581cb37c186",
            },
            {
                "role": "official_closehandle",
                "path": (
                    "docs/reference_corpus/local_member_intake_20261014_1/"
                    "api_10_nf-handleapi-closehandle.md"
                ),
                "raw_byte_length": 7266,
                "raw_sha256": "c0cd1b25e7d35a8f4fb020cfba13b9ee5b3643a332e7c1f592b507746e1e794b",
            },
        ],
    )
    _exact(oracle["expression_names"], list(_NAMES))
    _exact(sorted(packet["expressions"]), sorted(_NAMES))
    _exact(sorted(oracle["evaluations"]), sorted(_NAMES))
    _exact([row["id"] for row in oracle["actual_cases"]], list(_ACTUAL_IDS))
    _exact([row["id"] for row in oracle["refusal_cases"]], list(_REFUSAL_IDS))
    _exact(
        [row["id"] for row in oracle["association_cases"]],
        ["reversed_clocks", "unequal_return_copies"],
    )
    _exact([row["id"] for row in oracle["accounting_cases"]], ["success", "failure"])
    _exact(packet["source_rules"], {})
    _exact(
        sorted(packet["domains"]),
        ["integer_bounds", "late_role_order", "phase_order", "role_order"],
    )
    _exact(packet["domains"]["phase_order"], [row[0] for row in oracle["phase_rows"]])
    _exact(packet["domains"]["role_order"], [row[0] for row in oracle["role_rows"]])
    _exact(
        packet["domains"]["late_role_order"],
        [
            "child_stdin_read",
            "child_stdin_write",
            "stdout_write",
            "stderr_write",
            "stdout_read",
            "stderr_read",
            "thread",
            "process",
            "job",
        ],
    )
    _exact(packet["domains"]["integer_bounds"], _INTEGER_BOUNDS)
    _exact(
        packet["source_sites"],
        {
            "host_line_ranges": {
                "native_call": [387, 453],
                "late_loop": [1371, 1373],
                "close": [834, 844],
                "event": [814, 818],
                "terminal_list_alias": [805, 805],
                "transport_snapshot": [1133, 1139],
            },
            "protocol_schema_names": [
                "ApiTrace",
                "ApiArgument",
                "ApiReturn",
                "ParentClose",
                "Lifecycle",
                "LifecycleToken",
                "ApiContracts",
            ],
            "native_api_selector": "R14/api_10_nf-handleapi-closehandle.md:CloseHandle",
        },
    )
    _exact(
        packet["occurrences"],
        [
            {
                "array_path": ["api_trace"],
                "index_parameter": "api_ordinal",
                "success_expression": "close_trace_success",
                "failure_expression": "close_trace_failure",
            },
            {
                "array_path": ["terminal", "parent_closes"],
                "index_parameter": "close_ordinal",
                "success_expression": "parent_close_success",
                "failure_expression": "parent_close_failure",
            },
            {
                "array_path": ["lifecycle"],
                "index_parameter": "lifecycle_ordinal",
                "success_expression": "close_lifecycle",
                "failure_expression": "close_lifecycle",
            },
        ],
    )
    _exact(
        packet["accounting"],
        {
            "category_deltas": {"B": 0, "H": 0, "D": 0, "R": 0},
            "source_selector_characters": 50,
            "synthetic_array_overhead_bytes": 4,
            "real_append_equation": (
                "C(array_of_three_rows)-4+I(api_trace_nonempty)"
                "+I(parent_closes_nonempty)+I(lifecycle_nonempty)"
            ),
            "comma_array_paths": [["api_trace"], ["terminal", "parent_closes"], ["lifecycle"]],
        },
    )
    _exact(
        sorted(packet["scope"]),
        [
            "authority_flags",
            "domain_reachability",
            "exclusions",
            "false_claims",
            "math_carrier",
            "status",
        ],
    )
    _exact(packet["scope"]["status"], "sizing-component-only")
    _exact(packet["scope"]["math_carrier"], "synthetic-array-of-three-rows-not-a-Host-field")
    _exact(
        packet["scope"]["domain_reachability"],
        "conservative-Cartesian-shape-domain-not-whole-continuation-reachability",
    )
    _exact(
        packet["scope"]["false_claims"],
        {
            "native_observation": False,
            "cleanup_success": False,
            "full_certificate": False,
            "governor": False,
            "runtime_integration": False,
            "association_validation_by_calculator": False,
        },
    )
    _exact(packet["scope"]["authority_flags"], [[name, False] for name in _FLAG_NAMES])
    # Full prose is preserved by the root's raw packet pin and complete review;
    # it is not executable evidence or a new oracle derived from the packet.
    for rows, length in (
        (packet["association_obligations"], 12),
        (packet["scope"]["exclusions"], 6),
    ):
        if type(rows) is not list or len(rows) != length:
            raise AssertionError("Missing complete registered limitation inventory")
        for item in rows:
            if type(item) is not str or not item:
                raise AssertionError("Invalid complete limitation prose")


@pytest.mark.parametrize("name", _NAMES)
def test_late_close_complete_evaluation(packet, oracle, calculator, name):
    actual = calculator.evaluate_envelope(packet["expressions"][name], source_rules={})
    _exact(actual, oracle["evaluations"][name])


@pytest.mark.parametrize("case_id", _ACTUAL_IDS)
def test_late_close_complete_actual(packet, oracle, calculator, case_id):
    row = _actual(oracle, case_id)
    actual = calculator.check_actual(
        packet["expressions"][row["expression"]], row["value"], source_rules={}
    )
    _exact(actual, row["expected"])


@pytest.mark.parametrize("case_id", _REFUSAL_IDS)
def test_late_close_domain_refusal(packet, oracle, calculator, case_id):
    recipe = _row(oracle["refusal_cases"], case_id)
    row = _actual(oracle, recipe["base"])
    _mutate(row["value"], recipe["path"], recipe["value"], recipe["operation"] == "delete")
    with pytest.raises(calculator.RecordingRefusal) as caught:
        calculator.check_actual(
            packet["expressions"][row["expression"]], row["value"], source_rules={}
        )
    _exact(caught.value.reason, "actual")


@pytest.mark.parametrize("case_id", ("reversed_clocks", "unequal_return_copies"))
def test_late_close_sizing_does_not_prove_association(packet, oracle, calculator, case_id):
    recipe = _row(oracle["association_cases"], case_id)
    row = _actual(oracle, recipe["base"])
    _mutate(row["value"], recipe["path"], recipe["value"])
    actual = calculator.check_actual(
        packet["expressions"][row["expression"]], row["value"], source_rules={}
    )
    _exact(actual, recipe["expected"])


@pytest.mark.parametrize("branch", ("success", "failure"))
def test_late_close_complete_copy_and_wrapper_arithmetic(packet, oracle, calculator, branch):
    row = _row(oracle["accounting_cases"], branch)
    trace = calculator.evaluate_envelope(packet["expressions"][row["trace"]], source_rules={})
    close = calculator.evaluate_envelope(packet["expressions"][row["close"]], source_rules={})
    event = calculator.evaluate_envelope(packet["expressions"]["close_lifecycle"], source_rules={})
    returned = calculator.evaluate_envelope(packet["expressions"][row["return"]], source_rules={})
    total = trace["upper_ascii_bytes"] + close["upper_ascii_bytes"] + event["upper_ascii_bytes"]
    _exact(
        {
            "return_width_each": returned["upper_ascii_bytes"],
            "return_occurrences": 2,
            "row_sum": total,
            "synthetic_array": total + 4,
            "all_nonfirst_appends": total + 3,
            "raw_category_deltas": {"B": 0, "H": 0, "D": 0, "R": 0},
        },
        row["expected"],
    )


def test_late_close_all_declared_phase_domains(packet, oracle, calculator):
    for phase, success_width, failure_width in oracle["phase_rows"]:
        for branch, width, upper in (
            ("success", success_width, 436),
            ("failure", failure_width, 432),
        ):
            row = _actual(oracle, "close_trace_" + branch)
            row["value"]["phase"] = phase
            _exact(
                calculator.check_actual(
                    packet["expressions"][row["expression"]], row["value"], source_rules={}
                ),
                {"actual_ascii_bytes": width, "upper_ascii_bytes": upper},
            )


def test_late_close_all_declared_role_domains(packet, oracle, calculator):
    for role, success_width, failure_width in oracle["role_rows"]:
        for branch, width, upper in (
            ("success", success_width, 239),
            ("failure", failure_width, 241),
        ):
            row = _actual(oracle, "parent_close_" + branch)
            row["value"]["role"] = role
            _exact(
                calculator.check_actual(
                    packet["expressions"][row["expression"]], row["value"], source_rules={}
                ),
                {"actual_ascii_bytes": width, "upper_ascii_bytes": upper},
            )
