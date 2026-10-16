"""Independent complete-tree tests; no producer/native/P3 validator is imported.

The full audit is accounting evidence only.  Root owns every test launch.
Large successful B/M/support-width audit boundaries are not claimed here.
"""

import copy
import importlib.util
import json
from pathlib import Path

import local_member_intake_worker_recording_audit_oracles_20261016 as oracle
import pytest

_SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "local_member_intake_worker_recording_audit_20261016_1.py"
)
_TRACE = "worker_pre_emission_api_trace"
_APIS = (
    "GetProcAddress",
    "GetModuleHandleExW",
    "GetModuleFileNameW",
    "GetStdHandle",
    "GetFileType",
    "GetHandleInformation",
    "WriteFile",
    "PeekNamedPipe",
    "ReadFile",
    "GetCurrentProcessId",
    "CloseHandle",
    "VirtualAlloc",
    "VirtualFree",
    "CreatePipe",
    "SetHandleInformation",
)
_STORAGE_APIS = (
    "GetProcAddress",
    "GetModuleHandleExW",
    "GetModuleFileNameW",
    "GetHandleInformation",
    "WriteFile",
    "PeekNamedPipe",
    "ReadFile",
    "CreatePipe",
)
# Explicit independently selected parameter indexes/categories, not a suffix heuristic.
_ALLOCATED = {
    "GetProcAddress": ((1, "H"),),
    "GetModuleHandleExW": ((2, "B"),),
    "GetModuleFileNameW": ((1, "B"),),
    "GetStdHandle": (),
    "GetFileType": (),
    "GetHandleInformation": ((1, "B"),),
    "WriteFile": ((1, "H"), (3, "B")),
    "PeekNamedPipe": ((4, "B"), (5, "B")),
    "ReadFile": ((1, "B"), (3, "B")),
    "GetCurrentProcessId": (),
    "CloseHandle": (),
    "VirtualAlloc": (),
    "VirtualFree": (),
    "CreatePipe": ((0, "B"), (1, "B"), (2, "H")),
    "SetHandleInformation": (),
}
_HOOKS = []


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("independent_worker_audit", _SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exact(actual, expected):
    """Bounded mismatch text; the complete actual/expected bodies are captured separately."""
    if type(actual) is not type(expected):
        raise AssertionError("complete audit exact type mismatch")
    if type(expected) is dict:
        if actual.keys() != expected.keys():
            raise AssertionError("complete audit key roster mismatch")
        for key, value in expected.items():
            _exact(actual[key], value)
    elif type(expected) is list:
        if len(actual) != len(expected):
            raise AssertionError("complete audit list length mismatch")
        for index, value in enumerate(expected):
            _exact(actual[index], value)
    elif actual != expected:
        raise AssertionError("complete audit scalar value mismatch")


def _pack(value):
    if type(value) is bytes:
        return {"exact_type": "bytes", "complete_ascii": value.decode("ascii")}
    if type(value) is dict:
        return {key: _pack(item) for key, item in value.items()}
    if type(value) is list:
        return [_pack(item) for item in value]
    return value


def _capture(label, value):
    print(label + " " + json.dumps(_pack(value), ensure_ascii=True, sort_keys=True))


def _graph(value):
    """Lossless controlled input graph: all nodes/edges, aliases, cycles and state.

    No repr/str/iter/equality hook on a submitted object is invoked.  Strings are
    nodes too, so a large repeated immutable alias is emitted once, not sampled.
    Unsupported factories are defined completely in this file and have no hidden
    state; their exact base contents and complete instance dictionary are saved.
    """
    nodes = []
    seen = {}

    def visit(item):
        cls = type(item)
        if item is None or cls is bool or cls is int:
            return {"scalar": item}
        identity = id(item)
        if identity in seen:
            return {"ref": seen[identity]}
        index = len(nodes)
        seen[identity] = index
        node = {"id": index}
        nodes.append(node)
        if cls is str:
            node.update(kind="str", value=item)
        elif cls is bytes:
            node.update(kind="bytes", values=list(item))
        elif cls is list:
            node.update(kind="list", items=[visit(child) for child in item])
        elif cls is tuple:
            node.update(kind="tuple", items=[visit(child) for child in item])
        elif cls is dict:
            node.update(
                kind="dict", items=[[visit(key), visit(child)] for key, child in item.items()]
            )
        elif cls is float:
            # The constructed finite test value is exact, not native NaN/Infinity text.
            node.update(kind="float", hexadecimal=float.hex(item))
        else:
            name = type.__getattribute__(cls, "__qualname__")
            module = type.__getattribute__(cls, "__module__")
            node.update(kind="controlled_unsupported_factory", factory=module + "." + name)
            state = object.__getattribute__(item, "__dict__")
            node["complete_instance_state"] = visit(state)
            mro = type.__getattribute__(cls, "__mro__")
            if any(base is dict for base in mro):
                node["base_items"] = [[visit(k), visit(v)] for k, v in dict.items(item)]
            elif any(base is list for base in mro):
                node["base_items"] = [visit(v) for v in list.__iter__(item)]
            elif any(base is str for base in mro):
                node["base_string"] = str.__str__(item)
            elif any(base is int for base in mro):
                node["base_integer"] = int.__int__(item)
        return {"ref": index}

    root = visit(value)
    return {"root": root, "nodes": nodes}


def _invoke(module, container, body):
    try:
        return module.audit_worker_recording(container, body)
    except NotImplementedError as error:
        raise AssertionError(
            "complete Worker occurrence accounting behavior is unimplemented"
        ) from error


def _success(module, container, body, rows=None, expected=None):
    before = copy.deepcopy(body)
    before_graph = _graph([container, body])
    if expected is None:
        expected = oracle.expected_from_paths(container, body, rows)
    _capture("AUDIT_INPUT", {"container": container, "body": body})
    _capture("AUDIT_INPUT_GRAPH", before_graph)
    _capture("AUDIT_EXPECTED", expected)
    actual = _invoke(module, container, body)
    after_graph = _graph([container, body])
    _capture("AUDIT_POST_INPUT_GRAPH", after_graph)
    _capture("AUDIT_ACTUAL", actual)
    _exact(actual, expected)
    _exact(body, before)
    _exact(after_graph, before_graph)
    return actual


def _refusal(module, container, body, reason):
    before = _graph([container, body])
    _capture("AUDIT_INPUT_GRAPH", before)
    _capture("AUDIT_EXPECTED", {"exception": "WorkerRecordingRefusal", "reason": reason})
    with pytest.raises(module.WorkerRecordingRefusal) as caught:
        _invoke(module, container, body)
    actual = {"exception": type(caught.value).__name__, "reason": caught.value.reason}
    _capture("AUDIT_ACTUAL", actual)
    _exact(actual, {"exception": "WorkerRecordingRefusal", "reason": reason})
    _exact(_graph([container, body]), before)


def _row(path, category, body):
    value = body
    for part in path:
        value = value[part]
    return {"path": path, "category": category, "raw_byte_length": len(value) // 2}


def _trace_rows(body, index, prefix=None):
    prefix = [_TRACE] if prefix is None else prefix
    trace = body
    for part in prefix:
        trace = trace[part]
    trace = trace[index]
    rows = []
    for output_index, (argument_index, category) in enumerate(_ALLOCATED[trace["api"]]):
        rows.append(
            _row(
                prefix + [index, "arguments", argument_index, "value", "storage_before_hex"],
                category,
                body,
            )
        )
        rows.append(
            _row(
                prefix + [index, "output_buffers", output_index, "full_buffer_hex"], category, body
            )
        )
    return rows


def _worker_rows(body):
    rows = [_row(["nonce_hex"], "H", body), _row(["payload_hex"], "H", body)]
    for index in range(len(body[_TRACE])):
        rows.extend(_trace_rows(body, index))
    return rows


def _go_rows(body):
    rows = [_row(["go_observation", "packet_hex"], "H", body)]
    go = body["go_observation"]
    for index in range(len(go["data_reads"])):
        for output_index in range(2):
            rows.append(
                _row(
                    [
                        "go_observation",
                        "data_reads",
                        index,
                        "buffer_observations",
                        output_index,
                        "full_buffer_hex",
                    ],
                    "B",
                    body,
                )
            )
    for output_index in range(2):
        rows.append(
            _row(
                [
                    "go_observation",
                    "eof_probe",
                    "buffer_observations",
                    output_index,
                    "full_buffer_hex",
                ],
                "B",
                body,
            )
        )
    return rows


def _payload_rows(body):
    return [_row(["control_payload_hex"], "H", body)] + _go_rows(body)


def _marker_rows(body):
    rows = [_row(["nonce_hex"], "H", body)] + _go_rows(body)
    for index in range(len(body["completed_api_trace"])):
        rows.extend(_trace_rows(body, index, ["completed_api_trace"]))
    for index in range(2):
        rows.append(
            _row(
                ["pending_call", "arguments", 1 + 2 * index, "value", "storage_before_hex"],
                "B",
                body,
            )
        )
        rows.append(_row(["pending_call", "input_buffers", index, "full_buffer_hex"], "B", body))
    return rows


def _constructor_error(text="deadbeef"):
    return {
        "type_module": "builtins",
        "type_qualname": "OSError",
        "args": [
            {"kind": "str", "value": text},
            {"kind": "int", "value": -1},
            {"kind": "none", "value": None},
        ],
        "errno": {"kind": "int", "value": -1},
        "winerror": {"kind": "int", "value": 5},
        "strerror": {"kind": "str", "value": text},
        "filename": {"kind": "absent", "value": None},
        "filename2": {"kind": "none", "value": None},
        "hresult": {"kind": "int", "value": -2},
        "display_text": text,
    }


def _binding_error(text="deadbeef"):
    return {
        "type_module": "builtins",
        "type_qualname": "AttributeError",
        "args": [{"kind": "str", "value": text}],
        "display_text": text,
        "name": {"kind": "str", "value": text},
        "obj_state": "expected_library",
        "obj_constructor_ordinal": 0,
        "native_error_observed": False,
    }


def test_behavior_worker_complete_literal(audit_module):
    fixture = oracle.golden_cases()[0]
    assert fixture["id"] == "worker"
    _success(audit_module, fixture["container"], fixture["body"], expected=fixture["expected"])


def test_behavior_marker_complete_literal(audit_module):
    fixture = next(row for row in oracle.golden_cases() if row["id"] == "marker")
    _success(audit_module, fixture["container"], fixture["body"], expected=fixture["expected"])


@pytest.mark.parametrize(
    "case_id", ("worker", "payload", "marker"), ids=("worker", "payload", "marker")
)
def test_complete_literal_body_metadata_paths_and_totals(audit_module, case_id):
    fixture = next(row for row in oracle.golden_cases() if row["id"] == case_id)
    result = _success(
        audit_module, fixture["container"], fixture["body"], expected=fixture["expected"]
    )
    assert (
        result["totals"]["full"]
        == result["totals"]["M"] + 2 * result["totals"]["B"] + 2 * result["totals"]["H"]
    )
    assert result["totals"]["D"] == result["totals"]["R"] == 0


@pytest.mark.parametrize("api", _APIS, ids=_APIS)
def test_all_fifteen_api_signatures_and_independent_categories(audit_module, api):
    body = oracle.make_worker([oracle.make_trace(api)])
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


@pytest.mark.parametrize("api", _APIS, ids=_APIS)
def test_signature_selector_and_parameter_order_are_not_caller_supplied(audit_module, api):
    body = oracle.make_worker([oracle.make_trace(api)])
    body[_TRACE][0]["source_selector"] += ":invented"
    _refusal(audit_module, "BootstrapResult", body, "shape")


@pytest.mark.parametrize("api", _STORAGE_APIS, ids=_STORAGE_APIS)
def test_failed_storage_retains_every_complete_before_and_post(audit_module, api):
    body = oracle.make_worker([oracle.make_trace(api)])
    trace = body[_TRACE][0]
    trace["return"] = {
        "kind": trace["return"]["kind"],
        "raw_i64": 0,
        "raw_u64": None,
        "win32_error_u32": 5,
    }
    for output in trace["output_buffers"]:
        output.update(
            returned_bytes=None,
            output_validity="storage_only",
            valid_prefix_bytes=None,
            projection_kind="none",
        )
        output["full_buffer_hex"] = "ab" * output["capacity_bytes"]
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


def test_short_read_and_invalid_native_associations_do_not_shrink_storage(audit_module):
    trace = oracle.make_trace("ReadFile")
    pointer = trace["arguments"][1]["value"]
    pointer.update(storage_before_hex="a5" * 48, storage_bytes_u32=48)
    trace["arguments"][2]["value"] = 48
    trace["output_buffers"][0].update(
        capacity_bytes=48,
        full_buffer_hex="b6" * 48,
        returned_bytes=1,
        valid_prefix_bytes=1,
        output_validity="documented_valid",
        projection_kind="byte_prefix",
    )
    body = oracle.make_worker([trace])
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert result["totals"]["B"] == 104
    assert "clock_ordinal_return_GO_associations" in result["not_validated"]


@pytest.mark.parametrize("count", (1, 2, 48), ids=("one", "two", "forty_eight"))
def test_all_go_read_postcopies_are_physical_and_not_value_deduplicated(audit_module, count):
    go = oracle.make_go()
    go["data_reads"] = [go["data_reads"][0]] * count
    body = oracle.make_payload(go)
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    assert result["totals"]["B"] == 5 * (count + 1)
    assert len(result["occurrences"]) == 2 + 2 * (count + 1)


def test_atomic_worker_payload_is_not_recursively_decoded(audit_module):
    payload = oracle.make_payload()
    encoded = oracle.independent_canonical(payload).hex()
    body = oracle.make_worker([oracle.make_trace("GetCurrentProcessId")], payload_hex=encoded)
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert result["totals"]["B"] == 0
    assert result["totals"]["H"] == 16 + len(encoded) // 2


@pytest.mark.parametrize(
    "payload_hex",
    ("", "00", "ff", "7b7d", "6e6f742d6a736f6e"),
    ids=("empty", "nul", "invalid_utf8", "empty_object", "not_json"),
)
def test_numerically_fitting_semantically_invalid_payload_is_only_accounted(
    audit_module, payload_hex
):
    body = oracle.make_worker(payload_hex=payload_hex)
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert "payload_JSON" in result["not_validated"]
    assert result["metadata"]["payload_hex"] == ""


@pytest.mark.parametrize(
    "marker_hash", ("0" * 64, "f" * 64, "0123456789abcdef" * 4), ids=("zero", "eff", "pattern")
)
def test_marker_ownhash_is_complete_metadata_not_authenticated(audit_module, marker_hash):
    body = oracle.make_marker()
    body["marker_sha256"] = marker_hash
    result = _success(audit_module, "PendingReadMarker", body, _marker_rows(body))
    assert result["metadata"]["marker_sha256"] == marker_hash
    assert "ownhash_correctness" in result["not_validated"]


@pytest.mark.parametrize(
    "text",
    ("", "deadbeef", '"\\\b\t\n\f\r\x00\x1f\x7f', "éΩ中😀"),
    ids=("empty", "hex_lookalike", "ascii_escapes_DEL", "unicode_supplementary"),
)
def test_complete_diagnostics_lookalike_hex_and_ascii_escapes_stay_metadata(audit_module, text):
    body = oracle.make_payload()
    go = body["go_observation"]
    go["initialization"][0]["exception"] = _constructor_error(text)
    go["binding_initialization"][0]["exception"] = _binding_error(text)
    _success(audit_module, "ResultPayload", body, _payload_rows(body))


def test_all_thirty_three_binding_names_remain_metadata(audit_module):
    body = oracle.make_payload()
    template = body["go_observation"]["binding_initialization"][0]
    bindings = []
    for index, name in enumerate(oracle.BINDING_NAMES):
        binding = copy.deepcopy(template)
        binding.update(ordinal=index, api_name=name)
        bindings.append(binding)
    body["go_observation"]["binding_initialization"] = bindings
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    assert len(result["metadata"]["go_observation"]["binding_initialization"]) == 33


def test_acyclic_aliases_count_per_path_and_all_destinations_are_detached(audit_module):
    trace = oracle.make_trace("CreatePipe")
    body = oracle.make_worker()
    body[_TRACE] = [trace, trace]
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert len(result["occurrences"]) == 14
    result["body"][_TRACE][0]["ordinal"] = 999
    assert result["body"][_TRACE][1]["ordinal"] != 999
    assert body[_TRACE][0]["ordinal"] != 999
    assert result["metadata"][_TRACE][0]["ordinal"] != 999
    result["authority_flags"][0][1] = True
    assert body["authority_flags"][0][1] is False
    _capture("AUDIT_POST_MUTATION", result)


def test_reordered_input_keys_do_not_change_canonical_occurrence_order(audit_module):
    body = oracle.make_marker()

    def reverse_keys(value):
        if type(value) is dict:
            return {key: reverse_keys(value[key]) for key in reversed(tuple(value))}
        if type(value) is list:
            return [reverse_keys(item) for item in value]
        return value

    body = reverse_keys(body)
    _success(audit_module, "PendingReadMarker", body, _marker_rows(body))


def test_zero_length_raw_occurrence_is_not_omitted(audit_module):
    body = oracle.make_payload(control_payload_hex="")
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    assert {"path": ["control_payload_hex"], "category": "H", "raw_byte_length": 0} in result[
        "occurrences"
    ]


def _set(body, path, value):
    target = body
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


_WORKER_MUTATIONS = (
    ("case_empty", ["case_id"], "", "shape"),
    ("case_65", ["case_id"], "a" * 65, "shape"),
    ("case_upper", ["case_id"], "Wrong", "shape"),
    ("case_nonascii", ["case_id"], "é", "shape"),
    ("version", ["version"], "invented", "shape"),
    ("status", ["status"], "native_accepted", "shape"),
    ("pid_zero", ["worker_pid"], 0, "shape"),
    ("pid_bool", ["worker_pid"], True, "shape"),
    ("pid_over", ["worker_pid"], 2**32, "shape"),
    ("clock_negative", ["started_monotonic_ns"], -1, "shape"),
    ("clock_bool", ["ended_monotonic_ns"], False, "shape"),
    ("hash_upper", ["packet_sha256"], "A" * 64, "hex"),
    ("hash_short", ["packet_sha256"], "a" * 63, "hex"),
    ("nonce_short", ["nonce_hex"], "00" * 15, "hex"),
    ("nonce_odd", ["nonce_hex"], "0" * 31, "hex"),
    ("payload_odd", ["payload_hex"], "a", "hex"),
    ("payload_upper", ["payload_hex"], "AB", "hex"),
    ("payload_space", ["payload_hex"], "00 00", "hex"),
    ("trace_empty", [_TRACE], [], "shape"),
    ("phase", [_TRACE, 0, "phase"], "sealed", "shape"),
    ("ordinal_bool", [_TRACE, 0, "ordinal"], True, "shape"),
    ("return_kind", [_TRACE, 0, "return", "kind"], "void", "shape"),
    ("raw_i32_over", [_TRACE, 0, "return", "raw_i64"], 2**31, "shape"),
    ("raw_u64_negative", [_TRACE, 0, "return", "raw_u64"], -1, "shape"),
    ("error_over", [_TRACE, 0, "return", "win32_error_u32"], 2**32, "shape"),
    ("pointer_null", [_TRACE, 0, "arguments", 1, "value", "address_u64"], 0, "shape"),
    ("pointer_size_bool", [_TRACE, 0, "arguments", 1, "value", "storage_bytes_u32"], True, "shape"),
    ("pointer_short", [_TRACE, 0, "arguments", 1, "value", "storage_before_hex"], "00", "hex"),
    ("pointee", [_TRACE, 0, "arguments", 1, "value", "pointee_kind"], "opaque", "shape"),
    ("post_capacity", [_TRACE, 0, "output_buffers", 0, "capacity_bytes"], 1, "shape"),
    ("post_bad_extent", [_TRACE, 0, "output_buffers", 0, "full_buffer_hex"], "00", "hex"),
    ("post_validity", [_TRACE, 0, "output_buffers", 0, "output_validity"], "valid_enough", "shape"),
    ("post_prefix_over", [_TRACE, 0, "output_buffers", 0, "valid_prefix_bytes"], 65537, "shape"),
    (
        "post_projection",
        [_TRACE, 0, "output_buffers", 0, "projection_kind"],
        "native_guess",
        "shape",
    ),
    ("argument_name", [_TRACE, 0, "arguments", 0, "name"], "wrong", "shape"),
    ("argument_kind", [_TRACE, 0, "arguments", 0, "kind"], "int", "shape"),
    (
        "seed_disallowed",
        [_TRACE, 0, "saved_error_seed"],
        {"helper": "ctypes.set_last_error", "input_i32": 0, "returned_previous_i32": 0},
        "shape",
    ),
    ("authority_true", ["authority_flags", 0, 1], True, "shape"),
    ("authority_numeric", ["authority_flags", 0, 1], 0, "shape"),
)


@pytest.mark.parametrize(
    "case_id,path,value,reason", _WORKER_MUTATIONS, ids=[row[0] for row in _WORKER_MUTATIONS]
)
def test_worker_isolated_structural_hex_scalar_refusals(audit_module, case_id, path, value, reason):
    body = oracle.make_worker()
    _set(body, path, copy.deepcopy(value))
    _refusal(audit_module, "BootstrapResult", body, reason)


@pytest.mark.parametrize(
    "where",
    ("root", "trace", "return", "argument", "pointer", "post"),
    ids=("root", "trace", "return", "argument", "pointer", "post"),
)
@pytest.mark.parametrize("change", ("missing", "extra"), ids=("missing", "extra"))
def test_every_named_trace_roster_is_exact(audit_module, where, change):
    body = oracle.make_worker()
    targets = {
        "root": body,
        "trace": body[_TRACE][0],
        "return": body[_TRACE][0]["return"],
        "argument": body[_TRACE][0]["arguments"][1],
        "pointer": body[_TRACE][0]["arguments"][1]["value"],
        "post": body[_TRACE][0]["output_buffers"][0],
    }
    target = targets[where]
    if change == "missing":
        del target[next(iter(target))]
    else:
        target["extra"] = "00"
    _refusal(audit_module, "BootstrapResult", body, "shape")


@pytest.mark.parametrize(
    "where",
    (
        "go",
        "read",
        "init",
        "init_args",
        "binding",
        "close",
        "constructor_error",
        "optional",
        "binding_error",
        "scalar",
    ),
    ids=(
        "go",
        "read",
        "init",
        "init_args",
        "binding",
        "close",
        "constructor_error",
        "optional",
        "binding_error",
        "scalar",
    ),
)
@pytest.mark.parametrize("change", ("missing", "extra"), ids=("missing", "extra"))
def test_every_nested_go_and_diagnostic_roster_is_exact(audit_module, where, change):
    body = oracle.make_payload()
    go = body["go_observation"]
    go["initialization"][0]["exception"] = _constructor_error()
    go["binding_initialization"][0]["exception"] = _binding_error()
    targets = {
        "go": go,
        "read": go["data_reads"][0],
        "init": go["initialization"][0],
        "init_args": go["initialization"][0]["arguments"],
        "binding": go["binding_initialization"][0],
        "close": go["stdin_close"],
        "constructor_error": go["initialization"][0]["exception"],
        "optional": go["initialization"][0]["exception"]["errno"],
        "binding_error": go["binding_initialization"][0]["exception"],
        "scalar": go["initialization"][0]["exception"]["args"][0],
    }
    target = targets[where]
    if change == "missing":
        del target[next(iter(target))]
    else:
        target["extra"] = 0
    _refusal(audit_module, "ResultPayload", body, "shape")


@pytest.mark.parametrize(
    "api",
    ("LoadLibraryExW", "CreateProcessW", "FreeLibrary", "Invented"),
    ids=("LoadLibraryExW", "CreateProcessW", "FreeLibrary", "Invented"),
)
def test_unselected_direct_apis_refuse_even_if_a_name_is_bound(audit_module, api):
    body = oracle.make_worker()
    body[_TRACE][0]["api"] = api
    _refusal(audit_module, "BootstrapResult", body, "unsupported")


@pytest.mark.parametrize(
    "change",
    ("argument_order", "post_order", "extra_post", "missing_post", "flags_order"),
    ids=("argument_order", "post_order", "extra_post", "missing_post", "flags_order"),
)
def test_ordered_argument_post_and_authority_rosters(audit_module, change):
    body = oracle.make_worker([oracle.make_trace("CreatePipe")])
    trace = body[_TRACE][0]
    if change == "argument_order":
        trace["arguments"].reverse()
    elif change == "post_order":
        trace["output_buffers"].reverse()
    elif change == "extra_post":
        trace["output_buffers"].append(copy.deepcopy(trace["output_buffers"][0]))
    elif change == "missing_post":
        trace["output_buffers"].pop()
    else:
        body["authority_flags"].reverse()
    _refusal(audit_module, "BootstrapResult", body, "shape")


@pytest.mark.parametrize(
    "api,argument,bad",
    (
        ("GetModuleHandleExW", 0, 0),
        ("GetModuleFileNameW", 2, 511),
        ("GetStdHandle", 0, 0),
        ("PeekNamedPipe", 2, 1),
        ("VirtualAlloc", 1, 1),
        ("VirtualAlloc", 2, 0),
        ("VirtualAlloc", 3, 0),
        ("VirtualFree", 1, 1),
        ("VirtualFree", 2, 0),
        ("CreatePipe", 3, 0),
        ("SetHandleInformation", 1, 0),
        ("SetHandleInformation", 2, 1),
    ),
    ids=(
        "module_flags",
        "module_chars",
        "std_selector",
        "peek_zero",
        "allocation_size",
        "allocation_type",
        "allocation_protection",
        "free_size",
        "free_type",
        "pipe_size",
        "inherit_mask",
        "inherit_flags",
    ),
)
def test_selected_source_fixed_scalars_are_not_widened(audit_module, api, argument, bad):
    body = oracle.make_worker([oracle.make_trace(api)])
    body[_TRACE][0]["arguments"][argument]["value"] = bad
    _refusal(audit_module, "BootstrapResult", body, "shape")


@pytest.mark.parametrize("size", (2, 129), ids=("two", "one_twenty_nine"))
def test_getprocaddress_exact_capacity_token_endpoints(audit_module, size):
    body = oracle.make_worker()
    trace = body[_TRACE][0]
    trace["arguments"][1]["value"].update(storage_bytes_u32=size, storage_before_hex="ab" * size)
    trace["output_buffers"][0].update(
        capacity_bytes=size,
        full_buffer_hex="cd" * size,
        returned_bytes=None,
        valid_prefix_bytes=None,
        output_validity="storage_only",
        projection_kind="none",
    )
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


@pytest.mark.parametrize(
    "api,size",
    (("GetProcAddress", 1), ("GetProcAddress", 130), ("ReadFile", 49), ("WriteFile", 65537)),
    ids=("proc_one", "proc_one_thirty", "read_forty_nine", "write_sixty_five_k_plus_one"),
)
def test_selected_allocation_first_excess_refuses(audit_module, api, size):
    body = oracle.make_worker([oracle.make_trace(api)])
    trace = body[_TRACE][0]
    trace["arguments"][1]["value"].update(storage_bytes_u32=size, storage_before_hex="ab" * size)
    trace["output_buffers"][0].update(
        capacity_bytes=size,
        full_buffer_hex="cd" * size,
        returned_bytes=None,
        valid_prefix_bytes=None,
        output_validity="storage_only",
        projection_kind="none",
    )
    if api != "GetProcAddress":
        trace["arguments"][2]["value"] = size
    _refusal(audit_module, "BootstrapResult", body, "shape")


@pytest.mark.parametrize("size", (1, 48), ids=("one", "forty_eight"))
def test_selected_read_request_endpoints(audit_module, size):
    body = oracle.make_worker([oracle.make_trace("ReadFile")])
    trace = body[_TRACE][0]
    trace["arguments"][1]["value"].update(storage_bytes_u32=size, storage_before_hex="ab" * size)
    trace["arguments"][2]["value"] = size
    trace["output_buffers"][0].update(
        capacity_bytes=size,
        full_buffer_hex="cd" * size,
        returned_bytes=None,
        valid_prefix_bytes=None,
        output_validity="storage_only",
        projection_kind="none",
    )
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


@pytest.mark.parametrize("size", (1, 65536), ids=("one", "sixty_five_k"))
def test_selected_write_request_endpoints(audit_module, size):
    body = oracle.make_worker([oracle.make_trace("WriteFile")])
    trace = body[_TRACE][0]
    trace["arguments"][1]["value"].update(storage_bytes_u32=size, storage_before_hex="ab" * size)
    trace["arguments"][2]["value"] = size
    trace["output_buffers"][0].update(
        capacity_bytes=size,
        full_buffer_hex="cd" * size,
        returned_bytes=None,
        valid_prefix_bytes=None,
        output_validity="storage_only",
        projection_kind="none",
    )
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


class _DictSubclass(dict):
    pass


class _ListSubclass(list):
    pass


class _StringSubclass(str):
    pass


class _IntegerSubclass(int):
    pass


class _HostileMeta(type):
    def __eq__(cls, other):
        _HOOKS.append("metaclass_eq")
        raise AssertionError("submitted metaclass equality executed")

    def __hash__(cls):
        _HOOKS.append("metaclass_hash")
        raise AssertionError("submitted metaclass hash executed")


class _HostileObject(metaclass=_HostileMeta):
    def __repr__(self):
        _HOOKS.append("repr")
        raise AssertionError("submitted repr executed")

    def __str__(self):
        _HOOKS.append("str")
        raise AssertionError("submitted str executed")

    def __iter__(self):
        _HOOKS.append("iter")
        raise AssertionError("submitted iterator executed")


@pytest.mark.parametrize(
    "kind",
    (
        "dict_subclass",
        "list_subclass",
        "str_subclass",
        "int_subclass",
        "object",
        "tuple",
        "bytes",
        "float",
        "int_low",
        "int_high",
        "surrogate_low",
        "surrogate_high",
    ),
    ids=(
        "dict_subclass",
        "list_subclass",
        "str_subclass",
        "int_subclass",
        "object",
        "tuple",
        "bytes",
        "float",
        "int_low",
        "int_high",
        "surrogate_low",
        "surrogate_high",
    ),
)
def test_exact_snapshot_types_refuse_without_hostile_hooks(audit_module, kind):
    _HOOKS.clear()
    values = {
        "dict_subclass": _DictSubclass(a=1),
        "list_subclass": _ListSubclass([1]),
        "str_subclass": _StringSubclass("x"),
        "int_subclass": _IntegerSubclass(1),
        "object": _HostileObject(),
        "tuple": (1,),
        "bytes": b"x",
        "float": 1.25,
        "int_low": -(2**63) - 1,
        "int_high": 2**64,
        "surrogate_low": "\udc00",
        "surrogate_high": "\ud800",
    }
    body = oracle.make_worker()
    body["case_id"] = values[kind]
    _refusal(audit_module, "BootstrapResult", body, "input")
    assert _HOOKS == []


@pytest.mark.parametrize(
    "container,reason",
    ((None, "input"), (1, "input"), (True, "input"), ("Invented", "unsupported")),
    ids=("none", "integer", "bool", "unknown"),
)
def test_discriminator_precedes_body_snapshot(audit_module, container, reason):
    body = {"cycle": None}
    body["cycle"] = body
    _refusal(audit_module, container, body, reason)


@pytest.mark.parametrize(
    "kind",
    ("non_dict", "dict_subclass", "nonstring_key", "key_surrogate", "list_cycle", "dict_cycle"),
    ids=("non_dict", "dict_subclass", "nonstring_key", "key_surrogate", "list_cycle", "dict_cycle"),
)
def test_complete_snapshot_root_keys_and_cycles(audit_module, kind):
    if kind == "non_dict":
        body = []
    elif kind == "dict_subclass":
        body = _DictSubclass(oracle.make_worker())
    elif kind == "nonstring_key":
        body = {1: "x"}
    elif kind == "key_surrogate":
        body = {"\ud800": "x"}
    elif kind == "list_cycle":
        cycle = []
        cycle.append(cycle)
        body = {"cycle": cycle}
    else:
        body = {}
        body["cycle"] = body
    _refusal(audit_module, "BootstrapResult", body, "input")


@pytest.mark.parametrize(
    "depth,reason", ((64, "shape"), (65, "work")), ids=("equal", "first_excess")
)
def test_support_depth_equality_and_first_excess_before_shape(audit_module, depth, reason):
    value = None
    for _ in range(depth - 1):
        value = [value]
    _refusal(audit_module, "BootstrapResult", {"extra": value}, reason)


@pytest.mark.parametrize(
    "count,reason", ((65536, "shape"), (65537, "work")), ids=("equal", "first_excess")
)
def test_support_collection_equality_and_first_excess_before_shape(audit_module, count, reason):
    _refusal(audit_module, "BootstrapResult", {"extra": [None] * count}, reason)


@pytest.mark.parametrize(
    "padding,reason", ((13, "shape"), (14, "work")), ids=("equal", "first_excess")
)
def test_support_value_node_equality_and_first_excess_count_alias_per_path(
    audit_module, padding, reason
):
    shared = [None] * 65534
    body = {"extra": [shared] * 16, "pad": [None] * padding}
    # 1root+1extra+16*(1list+65534values)+1pad+13values =1048576.
    _capture(
        "AUDIT_LITERAL_ARITHMETIC",
        {
            "formula": "1+1+16*(1+65534)+1+padding",
            "padding": padding,
            "visited_value_nodes": 1048576 + padding - 13,
            "limit": 1048576,
            "outcome_is_shape_not_success": padding == 13,
        },
    )
    _refusal(audit_module, "BootstrapResult", body, reason)


@pytest.mark.parametrize(
    "last_length,reason", ((1048562, "shape"), (1048563, "work")), ids=("equal", "first_excess")
)
def test_support_ascii_width_equality_and_first_excess_without_giant_success_audit(
    audit_module, last_length, reason
):
    shared = "x" * 1048573
    body = {"extra": [shared] * 63 + ["y" * last_length]}
    # 64quoted strings+63commas+root/list/key punctuation:64*1048573+203-11.
    _capture(
        "AUDIT_LITERAL_ARITHMETIC",
        {
            "formula": "63*1048573+last_length+203",
            "last_length": last_length,
            "complete_ascii_width": 67108864 + last_length - 1048562,
            "limit": 67108864,
            "outcome_is_shape_not_success": last_length == 1048562,
        },
    )
    _refusal(audit_module, "BootstrapResult", body, reason)


def _adjust_diagnostic_to_width(body, target, selector):
    """ASCII-only independent width delta, not a production measurement."""
    selector["display_text"] = ""
    base = len(oracle.independent_canonical(body))
    assert base <= target
    selector["display_text"] = "x" * (target - base)


@pytest.mark.parametrize("delta", (0, 1), ids=("equal", "first_excess"))
def test_payload_complete_full_limit_equality_and_first_excess_returns_whole_audit(
    audit_module, delta
):
    body = oracle.make_payload()
    diagnostic = _constructor_error("")
    body["go_observation"]["initialization"][0]["exception"] = diagnostic
    _adjust_diagnostic_to_width(body, 262144 + delta, diagnostic)
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    row = result["measurements"][3]
    assert row == {
        "path": [],
        "quantity": "full",
        "actual": 262144 + delta,
        "limit": 262144,
        "within": delta == 0,
    }
    assert row in result["over_limits"] if delta else row not in result["over_limits"]


@pytest.mark.parametrize("delta", (0, 1), ids=("equal", "first_excess"))
def test_initialization_component_limit_equality_and_first_excess(audit_module, delta):
    body = oracle.make_payload()
    initialization = body["go_observation"]["initialization"][0]
    diagnostic = _constructor_error("")
    initialization["exception"] = diagnostic
    _adjust_diagnostic_to_width(initialization, 32768 + delta, diagnostic)
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    row = result["measurements"][4]
    assert row == {
        "path": ["go_observation", "initialization", 0],
        "quantity": "full",
        "actual": 32768 + delta,
        "limit": 32768,
        "within": delta == 0,
    }


@pytest.mark.parametrize("size", (262144, 262145), ids=("equal", "first_excess"))
def test_payload_decoded_extent_equality_and_first_excess_is_numerical(audit_module, size):
    body = oracle.make_worker(payload_hex="00" * size)
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert result["measurements"][4] == {
        "path": ["payload_hex"],
        "quantity": "decoded_bytes",
        "actual": size,
        "limit": 262144,
        "within": size == 262144,
    }
    if size > 262144:
        result["over_limits"][0]["actual"] = 0
        assert result["measurements"][4]["actual"] == size


@pytest.mark.parametrize("delta", (0, 1), ids=("equal", "first_excess"))
def test_H_category_limit_equality_and_first_excess_are_complete_numerical_rows(
    audit_module, delta
):
    body = oracle.make_worker(
        [oracle.make_trace("GetCurrentProcessId")], payload_hex="00" * (2097152 - 16 + delta)
    )
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert result["measurements"][1] == {
        "path": [],
        "quantity": "H",
        "actual": 2097152 + delta,
        "limit": 2097152,
        "within": delta == 0,
    }


@pytest.mark.parametrize("count", (1, 16), ids=("one", "sixteen"))
def test_initialization_measurements_have_literal_order_and_complete_actuals(audit_module, count):
    body = oracle.make_payload()
    base = body["go_observation"]["initialization"][0]
    body["go_observation"]["initialization"] = [base] * count
    result = _success(audit_module, "ResultPayload", body, _payload_rows(body))
    assert [row["path"] for row in result["measurements"][4:]] == [
        ["go_observation", "initialization", i] for i in range(count)
    ]


def test_over_limit_measurement_copies_do_not_alias_each_other(audit_module):
    body = oracle.make_worker(payload_hex="00" * 262145)
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    result["over_limits"][0]["path"].append("changed")
    assert result["measurements"][4]["path"] == ["payload_hex"]
    assert body["payload_hex"] == "00" * 262145
    _capture("AUDIT_POST_MUTATION", result)


@pytest.mark.parametrize("case_id", ("a", "a" * 64), ids=("one", "sixty_four"))
def test_worker_id_length_endpoints(audit_module, case_id):
    body = oracle.make_worker()
    body["case_id"] = case_id
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


@pytest.mark.parametrize("raw", (-(2**31), 2**31 - 1), ids=("i32_min", "i32_max"))
def test_return_i32_width_endpoints_are_not_native_success_claims(audit_module, raw):
    body = oracle.make_worker([oracle.make_trace("CloseHandle")])
    body[_TRACE][0]["return"]["raw_i64"] = raw
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert "owner_cleanup_state" in result["not_validated"]


@pytest.mark.parametrize("raw", (0, 2**64 - 1), ids=("u64_zero", "u64_max"))
def test_u64_return_and_clock_endpoints_do_not_validate_native_associations(audit_module, raw):
    body = oracle.make_worker([oracle.make_trace("GetCurrentProcessId")])
    body[_TRACE][0]["return"]["raw_u64"] = raw
    body["started_monotonic_ns"] = raw
    body["ended_monotonic_ns"] = 0
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert "clock_ordinal_return_GO_associations" in result["not_validated"]


@pytest.mark.parametrize("count", (0, 8), ids=("zero", "eight"))
def test_complete_error_argument_bound_endpoints(audit_module, count):
    body = oracle.make_payload()
    go = body["go_observation"]
    constructor = _constructor_error("")
    binding = _binding_error("")
    constructor["args"] = [{"kind": "str", "value": "deadbeef"}] * count
    binding["args"] = [{"kind": "int", "value": -(2**63)}] * count
    go["initialization"][0]["exception"] = constructor
    go["binding_initialization"][0]["exception"] = binding
    _success(audit_module, "ResultPayload", body, _payload_rows(body))


@pytest.mark.parametrize("which", ("constructor", "binding"), ids=("constructor", "binding"))
def test_complete_error_argument_first_excess_refuses(audit_module, which):
    body = oracle.make_payload()
    go = body["go_observation"]
    record = _constructor_error("") if which == "constructor" else _binding_error("")
    record["args"] = [{"kind": "none", "value": None}] * 9
    if which == "constructor":
        go["initialization"][0]["exception"] = record
    else:
        go["binding_initialization"][0]["exception"] = record
    _refusal(audit_module, "ResultPayload", body, "shape")


_GO_MUTATIONS = (
    ("packet_short", ["packet_hex"], "00" * 47, "hex"),
    ("initialization_empty", ["initialization"], [], "shape"),
    ("binding_empty", ["binding_initialization"], [], "shape"),
    ("reads_empty", ["data_reads"], [], "shape"),
    ("read_zero", ["data_reads", 0, "requested_count_u32"], 0, "shape"),
    ("read_49", ["data_reads", 0, "requested_count_u32"], 49, "shape"),
    ("read_bool", ["data_reads", 0, "returned_count_u32"], True, "shape"),
    ("eof_offset", ["eof_probe", "offset_u32"], 47, "shape"),
    ("eof_request", ["eof_probe", "requested_count_u32"], 2, "shape"),
    ("initializer_role", ["initialization", 0, "owner_role"], "host", "shape"),
    ("initializer_constructor", ["initialization", 0, "constructor"], "ctypes.CDLL", "shape"),
    ("initializer_path", ["initialization", 0, "arguments", "name"], "invented.dll", "shape"),
    ("initializer_errno", ["initialization", 0, "arguments", "use_errno"], True, "shape"),
    (
        "initializer_last_error",
        ["initialization", 0, "arguments", "use_last_error"],
        False,
        "shape",
    ),
    ("initializer_mode", ["initialization", 0, "arguments", "winmode"], 0, "shape"),
    ("initializer_completed", ["initialization", 0, "completed"], 1, "shape"),
    ("initializer_handle", ["initialization", 0, "exposed_handle_u64"], 0, "shape"),
    (
        "initializer_observation",
        ["initialization", 0, "native_call_observation"],
        "observed",
        "shape",
    ),
    (
        "initializer_disposition",
        ["initialization", 0, "reference_disposition"],
        "released",
        "shape",
    ),
    ("binding_name", ["binding_initialization", 0, "api_name"], "Invented", "shape"),
    ("binding_lookup", ["binding_initialization", 0, "lookup_kind"], "getattr", "shape"),
    ("binding_address", ["binding_initialization", 0, "exposed_address_u64"], 0, "shape"),
    ("close_role", ["stdin_close", "role"], "stdout", "shape"),
    ("close_handle", ["stdin_close", "handle_u64"], 0, "shape"),
    ("close_attempted", ["stdin_close", "close_attempted"], 1, "shape"),
    ("close_disposition", ["stdin_close", "disposition"], "assumed_closed", "shape"),
)


@pytest.mark.parametrize(
    "case_id,path,value,reason", _GO_MUTATIONS, ids=[row[0] for row in _GO_MUTATIONS]
)
def test_go_isolated_structural_domains(audit_module, case_id, path, value, reason):
    body = oracle.make_payload()
    _set(body["go_observation"], path, copy.deepcopy(value))
    _refusal(audit_module, "ResultPayload", body, reason)


@pytest.mark.parametrize(
    "where",
    ("root", "owned", "pending", "pending_argument", "pending_pointer", "pending_input"),
    ids=("root", "owned", "pending", "pending_argument", "pending_pointer", "pending_input"),
)
@pytest.mark.parametrize("change", ("missing", "extra"), ids=("missing", "extra"))
def test_every_marker_and_pending_record_roster(audit_module, where, change):
    body = oracle.make_marker()
    pending = body["pending_call"]
    targets = {
        "root": body,
        "owned": body["owned_handles"][0],
        "pending": pending,
        "pending_argument": pending["arguments"][1],
        "pending_pointer": pending["arguments"][1]["value"],
        "pending_input": pending["input_buffers"][0],
    }
    target = targets[where]
    if change == "missing":
        del target[next(iter(target))]
    else:
        target["extra"] = "00"
    _refusal(audit_module, "PendingReadMarker", body, "shape")


@pytest.mark.parametrize(
    "change",
    (
        "case",
        "ownhash",
        "owned_order",
        "owned_missing",
        "pending_request",
        "pending_api",
        "pending_return",
        "input_missing",
        "input_order",
    ),
    ids=(
        "case",
        "ownhash",
        "owned_order",
        "owned_missing",
        "pending_request",
        "pending_api",
        "pending_return",
        "input_missing",
        "input_order",
    ),
)
def test_marker_exact_domain_and_no_fabricated_pending_return(audit_module, change):
    body = oracle.make_marker()
    pending = body["pending_call"]
    reason = "shape"
    if change == "case":
        body["case_id"] = "audit_worker"
    elif change == "ownhash":
        body["marker_sha256"] = "F" * 64
        reason = "hex"
    elif change == "owned_order":
        body["owned_handles"].reverse()
    elif change == "owned_missing":
        body["owned_handles"].pop()
    elif change == "pending_request":
        pending["arguments"][2]["value"] = 2
    elif change == "pending_api":
        pending["api"] = "WriteFile"
    elif change == "pending_return":
        pending["return"] = {
            "kind": "bool32",
            "raw_i64": 0,
            "raw_u64": None,
            "win32_error_u32": 109,
        }
    elif change == "input_missing":
        pending["input_buffers"].pop()
    else:
        pending["input_buffers"].reverse()
    _refusal(audit_module, "PendingReadMarker", body, reason)


@pytest.mark.parametrize("count", (1, 4096), ids=("one", "four_k"))
def test_trace_public_count_endpoints_without_reachable_history_claim(audit_module, count):
    body = oracle.make_worker()
    shared = oracle.make_trace("GetCurrentProcessId")
    body[_TRACE] = [shared] * count
    result = _success(audit_module, "BootstrapResult", body, _worker_rows(body))
    assert len(result["body"][_TRACE]) == count
    assert result["totals"]["B"] == 0


@pytest.mark.parametrize(
    "which",
    ("trace", "cleanup", "initialization", "bindings", "reads"),
    ids=("trace", "cleanup", "initialization", "bindings", "reads"),
)
def test_public_collection_first_excess_is_shape_not_work(audit_module, which):
    if which == "trace":
        body = oracle.make_worker()
        body[_TRACE] = [body[_TRACE][0]] * 4097
        container = "BootstrapResult"
    elif which == "cleanup":
        body = oracle.make_worker()
        body["worker_cleanup"] = [body["worker_cleanup"][0]] * 17
        container = "BootstrapResult"
    else:
        body = oracle.make_payload()
        key, count = {
            "initialization": ("initialization", 17),
            "bindings": ("binding_initialization", 129),
            "reads": ("data_reads", 49),
        }[which]
        body["go_observation"][key] = [body["go_observation"][key][0]] * count
        container = "ResultPayload"
    _refusal(audit_module, container, body, "shape")


@pytest.mark.parametrize("count", (0, 16), ids=("zero", "sixteen"))
def test_cleanup_public_count_endpoints_are_metadata_only(audit_module, count):
    body = oracle.make_worker()
    body["worker_cleanup"] = [body["worker_cleanup"][0]] * count
    _success(audit_module, "BootstrapResult", body, _worker_rows(body))


@pytest.mark.parametrize("count", (1, 128), ids=("one", "one_twenty_eight"))
def test_binding_public_count_endpoints_are_not_runtime_sequence_proof(audit_module, count):
    body = oracle.make_payload()
    bindings = body["go_observation"]["binding_initialization"]
    body["go_observation"]["binding_initialization"] = [bindings[0]] * count
    _success(audit_module, "ResultPayload", body, _payload_rows(body))


# Exact prospectively declared IDs, derived only from the literal decorators above.
# This is collection metadata, not imported/executed outcome evidence.
EXPECTED_NODEIDS = (
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_behavior_worker_complete_literal",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_behavior_marker_complete_literal",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_literal_body_metadata_paths_and_totals[worker]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_literal_body_metadata_paths_and_totals[payload]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_literal_body_metadata_paths_and_totals[marker]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetProcAddress]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetModuleHandleExW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetModuleFileNameW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetStdHandle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetFileType]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetHandleInformation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[WriteFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[PeekNamedPipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[ReadFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[GetCurrentProcessId]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[CloseHandle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[VirtualAlloc]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[VirtualFree]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[CreatePipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_fifteen_api_signatures_and_independent_categories[SetHandleInformation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetProcAddress]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetModuleHandleExW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetModuleFileNameW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetStdHandle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetFileType]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetHandleInformation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[WriteFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[PeekNamedPipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[ReadFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[GetCurrentProcessId]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[CloseHandle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[VirtualAlloc]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[VirtualFree]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[CreatePipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_signature_selector_and_parameter_order_are_not_caller_supplied[SetHandleInformation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[GetProcAddress]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[GetModuleHandleExW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[GetModuleFileNameW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[GetHandleInformation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[WriteFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[PeekNamedPipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[ReadFile]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_failed_storage_retains_every_complete_before_and_post[CreatePipe]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_short_read_and_invalid_native_associations_do_not_shrink_storage",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_go_read_postcopies_are_physical_and_not_value_deduplicated[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_go_read_postcopies_are_physical_and_not_value_deduplicated[two]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_go_read_postcopies_are_physical_and_not_value_deduplicated[forty_eight]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_atomic_worker_payload_is_not_recursively_decoded",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_numerically_fitting_semantically_invalid_payload_is_only_accounted[empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_numerically_fitting_semantically_invalid_payload_is_only_accounted[nul]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_numerically_fitting_semantically_invalid_payload_is_only_accounted[invalid_utf8]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_numerically_fitting_semantically_invalid_payload_is_only_accounted[empty_object]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_numerically_fitting_semantically_invalid_payload_is_only_accounted[not_json]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_ownhash_is_complete_metadata_not_authenticated[zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_ownhash_is_complete_metadata_not_authenticated[eff]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_ownhash_is_complete_metadata_not_authenticated[pattern]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_diagnostics_lookalike_hex_and_ascii_escapes_stay_metadata[empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_diagnostics_lookalike_hex_and_ascii_escapes_stay_metadata[hex_lookalike]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_diagnostics_lookalike_hex_and_ascii_escapes_stay_metadata[ascii_escapes_DEL]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_diagnostics_lookalike_hex_and_ascii_escapes_stay_metadata[unicode_supplementary]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_all_thirty_three_binding_names_remain_metadata",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_acyclic_aliases_count_per_path_and_all_destinations_are_detached",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_reordered_input_keys_do_not_change_canonical_occurrence_order",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_zero_length_raw_occurrence_is_not_omitted",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[case_empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[case_65]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[case_upper]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[case_nonascii]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[version]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[status]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pid_zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pid_bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pid_over]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[clock_negative]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[clock_bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[hash_upper]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[hash_short]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[nonce_short]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[nonce_odd]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[payload_odd]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[payload_upper]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[payload_space]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[trace_empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[phase]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[ordinal_bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[return_kind]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[raw_i32_over]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[raw_u64_negative]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[error_over]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pointer_null]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pointer_size_bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pointer_short]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[pointee]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[post_capacity]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[post_bad_extent]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[post_validity]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[post_prefix_over]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[post_projection]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[argument_name]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[argument_kind]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[seed_disallowed]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[authority_true]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_isolated_structural_hex_scalar_refusals[authority_numeric]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-root]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-trace]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-return]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-argument]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-pointer]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[missing-post]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-root]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-trace]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-return]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-argument]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-pointer]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_named_trace_roster_is_exact[extra-post]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-go]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-read]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-init]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-init_args]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-binding]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-close]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-constructor_error]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-optional]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-binding_error]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[missing-scalar]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-go]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-read]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-init]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-init_args]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-binding]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-close]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-constructor_error]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-optional]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-binding_error]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_nested_go_and_diagnostic_roster_is_exact[extra-scalar]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_unselected_direct_apis_refuse_even_if_a_name_is_bound[LoadLibraryExW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_unselected_direct_apis_refuse_even_if_a_name_is_bound[CreateProcessW]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_unselected_direct_apis_refuse_even_if_a_name_is_bound[FreeLibrary]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_unselected_direct_apis_refuse_even_if_a_name_is_bound[Invented]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_ordered_argument_post_and_authority_rosters[argument_order]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_ordered_argument_post_and_authority_rosters[post_order]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_ordered_argument_post_and_authority_rosters[extra_post]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_ordered_argument_post_and_authority_rosters[missing_post]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_ordered_argument_post_and_authority_rosters[flags_order]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[module_flags]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[module_chars]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[std_selector]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[peek_zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[allocation_size]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[allocation_type]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[allocation_protection]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[free_size]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[free_type]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[pipe_size]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[inherit_mask]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_source_fixed_scalars_are_not_widened[inherit_flags]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_getprocaddress_exact_capacity_token_endpoints[two]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_getprocaddress_exact_capacity_token_endpoints[one_twenty_nine]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_allocation_first_excess_refuses[proc_one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_allocation_first_excess_refuses[proc_one_thirty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_allocation_first_excess_refuses[read_forty_nine]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_allocation_first_excess_refuses[write_sixty_five_k_plus_one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_read_request_endpoints[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_read_request_endpoints[forty_eight]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_write_request_endpoints[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_selected_write_request_endpoints[sixty_five_k]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[dict_subclass]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[list_subclass]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[str_subclass]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[int_subclass]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[object]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[tuple]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[bytes]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[float]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[int_low]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[int_high]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[surrogate_low]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_exact_snapshot_types_refuse_without_hostile_hooks[surrogate_high]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_discriminator_precedes_body_snapshot[none]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_discriminator_precedes_body_snapshot[integer]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_discriminator_precedes_body_snapshot[bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_discriminator_precedes_body_snapshot[unknown]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[non_dict]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[dict_subclass]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[nonstring_key]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[key_surrogate]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[list_cycle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_snapshot_root_keys_and_cycles[dict_cycle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_depth_equality_and_first_excess_before_shape[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_depth_equality_and_first_excess_before_shape[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_collection_equality_and_first_excess_before_shape[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_collection_equality_and_first_excess_before_shape[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_value_node_equality_and_first_excess_count_alias_per_path[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_value_node_equality_and_first_excess_count_alias_per_path[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_ascii_width_equality_and_first_excess_without_giant_success_audit[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_support_ascii_width_equality_and_first_excess_without_giant_success_audit[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_payload_complete_full_limit_equality_and_first_excess_returns_whole_audit[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_payload_complete_full_limit_equality_and_first_excess_returns_whole_audit[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_initialization_component_limit_equality_and_first_excess[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_initialization_component_limit_equality_and_first_excess[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_payload_decoded_extent_equality_and_first_excess_is_numerical[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_payload_decoded_extent_equality_and_first_excess_is_numerical[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_H_category_limit_equality_and_first_excess_are_complete_numerical_rows[equal]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_H_category_limit_equality_and_first_excess_are_complete_numerical_rows[first_excess]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_initialization_measurements_have_literal_order_and_complete_actuals[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_initialization_measurements_have_literal_order_and_complete_actuals[sixteen]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_over_limit_measurement_copies_do_not_alias_each_other",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_id_length_endpoints[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_worker_id_length_endpoints[sixty_four]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_return_i32_width_endpoints_are_not_native_success_claims[i32_min]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_return_i32_width_endpoints_are_not_native_success_claims[i32_max]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_u64_return_and_clock_endpoints_do_not_validate_native_associations[u64_zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_u64_return_and_clock_endpoints_do_not_validate_native_associations[u64_max]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_error_argument_bound_endpoints[zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_error_argument_bound_endpoints[eight]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_error_argument_first_excess_refuses[constructor]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_complete_error_argument_first_excess_refuses[binding]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[packet_short]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initialization_empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[binding_empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[reads_empty]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[read_zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[read_49]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[read_bool]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[eof_offset]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[eof_request]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_role]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_constructor]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_path]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_errno]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_last_error]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_mode]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_completed]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_handle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_observation]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[initializer_disposition]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[binding_name]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[binding_lookup]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[binding_address]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[close_role]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[close_handle]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[close_attempted]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_go_isolated_structural_domains[close_disposition]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-root]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-owned]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-pending]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-pending_argument]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-pending_pointer]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[missing-pending_input]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-root]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-owned]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-pending]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-pending_argument]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-pending_pointer]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_every_marker_and_pending_record_roster[extra-pending_input]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[case]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[ownhash]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[owned_order]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[owned_missing]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[pending_request]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[pending_api]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[pending_return]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[input_missing]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_marker_exact_domain_and_no_fabricated_pending_return[input_order]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_trace_public_count_endpoints_without_reachable_history_claim[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_trace_public_count_endpoints_without_reachable_history_claim[four_k]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_public_collection_first_excess_is_shape_not_work[trace]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_public_collection_first_excess_is_shape_not_work[cleanup]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_public_collection_first_excess_is_shape_not_work[initialization]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_public_collection_first_excess_is_shape_not_work[bindings]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_public_collection_first_excess_is_shape_not_work[reads]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_cleanup_public_count_endpoints_are_metadata_only[zero]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_cleanup_public_count_endpoints_are_metadata_only[sixteen]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_binding_public_count_endpoints_are_not_runtime_sequence_proof[one]",
    "tests/test_local_member_intake_worker_recording_audit_20261016.py::test_binding_public_count_endpoints_are_not_runtime_sequence_proof[one_twenty_eight]",
)

UNEXECUTED_SUCCESS_BOUNDARIES = (
    "B=12582912 and first-excess complete successful audits",
    "M=8388608 and first-excess complete successful audits",
    "full-support=67108864 successful audit (snapshot equality tested only)",
    "1048576-node successful audit (snapshot equality tested only)",
)
