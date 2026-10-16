"""Independent, read-only qualification of a separately executed G4 cohort.

These tests do not execute a producer, import a producer, call a native API, or
adopt an observed result as an expected literal.  Missing mandatory artifacts are
failures.  The complete frozen declarations are the independent type/literal
oracle.  Actual native execution and pytest reader identities are separate facts.
"""

import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path

import pytest


WORKSPACE = Path("C:/Users/pabta/Projects/ai-trader")
RUN = WORKSPACE / "logs/local_member_intake_proof_20261015_1"
D_PATH = WORKSPACE / "tests/local_member_intake_bootstrap_declarations_20261015_2.json"
R_PATH = RUN / "bootstrap_registration_2.json"
D_RAW_SHA = "5a446768ca8f375c94e826df5e720804551a9653179f216cfbd05d5e614bbf62"
R_RAW_SHA = "9e9a63a06d6c0ca7e2bd80bf1d45eb0c4043fc49cc62bf95035dd8142d3383c0"
# Root will bind this exact independently reconciled identity before reader release.
R_CANONICAL_SHA = "e6d126783a620d70641e87a6cd1b5b1976de0730f3ead08da9de4647fb646eab"
P_CANONICAL_SHA = "24c955c1cb16cfd1058f79177078697d960bd4f2e3c3d323da77f76f4fbd5d7d"
HARD_END = "2026-10-15T14:59:08Z"
CASE_IDS = (
    "packet_first_excess", "packet_wrong_pin", "unknown_control", "success",
    "creation_refusal", "suspended_identity_refusal", "suspended_membership_refusal",
    "resume_refusal", "close_refusal", "invalid_utf8", "duplicate_key",
    "trailing_json", "unexpected_stderr", "crash", "result_exact_limit",
    "result_first_excess", "diagnostic_exact_limit", "diagnostic_first_excess",
    "initialization_stall", "wall_stall", "blocked_owned_pipe_read", "cpu_limit",
    "memory_positive_control", "memory_limit",
)
PURE = frozenset(CASE_IDS[:3])
NO_HANDOFF = PURE | {
    "creation_refusal", "suspended_identity_refusal", "suspended_membership_refusal",
}
NO_READY = PURE | {
    "creation_refusal", "suspended_identity_refusal", "suspended_membership_refusal",
    "resume_refusal", "initialization_stall",
}
NO_RESUME = PURE | {
    "creation_refusal", "suspended_identity_refusal", "suspended_membership_refusal",
    "resume_refusal",
}
READY = bytes.fromhex("4c4d494e4954310a")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pairs(items):
    value = {}
    for key, item in items:
        assert key not in value, ("duplicate JSON key", key)
        value[key] = item
    return value


def _constant(token):
    raise AssertionError(("non-finite JSON token", token))


def _json(raw):
    assert type(raw) is bytes
    value = json.loads(raw.decode("utf-8", errors="strict"),
                       object_pairs_hook=_pairs, parse_constant=_constant)
    _json_values(value)
    return value


def _json_values(value):
    if value is None or type(value) in (bool, int):
        return
    if type(value) is str:
        assert not any(0xD800 <= ord(char) <= 0xDFFF for char in value)
        return
    if type(value) is list:
        for item in value:
            _json_values(item)
        return
    assert type(value) is dict, ("unsupported JSON value", type(value).__name__)
    for key, item in value.items():
        assert type(key) is str
        _json_values(key)
        _json_values(item)


def _canonical(value):
    _json_values(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _same(actual, expected, position="value"):
    assert type(actual) is type(expected), (position, "type", actual, expected)
    if type(expected) is dict:
        assert set(actual) == set(expected), (position, "keys", actual.keys(), expected.keys())
        for key in expected:
            _same(actual[key], expected[key], position + "." + key)
    elif type(expected) is list:
        assert len(actual) == len(expected), (position, "length")
        for index, item in enumerate(expected):
            _same(actual[index], item, f"{position}[{index}]")
    else:
        assert actual == expected, (position, actual, expected)


def _read(path, cap):
    path = Path(path)
    _admitted_read_path(path)
    assert path.is_file(), ("Missing mandatory qualification artifact", str(path))
    with path.open("rb") as stream:
        raw = stream.read(cap + 1)
        assert len(raw) <= cap, ("Artifact exceeds registered cap", str(path), len(raw), cap)
        assert stream.read(1) == b"", ("Artifact changed or missing exact EOF", str(path))
    return raw


def _admitted_read_path(path):
    """Scope guard only; not filesystem identity, ancestry, or authentication."""
    assert ".." not in path.parts
    literal = path.as_posix()
    fixed = {D_PATH.as_posix(), R_PATH.as_posix(),
             (WORKSPACE / "scripts/local_member_intake_bootstrap_protocol_20261015_2.json").as_posix(),
             (WORKSPACE / "docs/6E_LOCAL_MEMBER_INTAKE_STARTUP_POLICY_20261015.md").as_posix()}
    source_names = {"host_20261015_1.py", "worker_20261015_1.py", "contract_20261015_1.py",
                    "validation_20261015_1.py", "observer_20261015_1.ps1", "primitives_20261015_1.psm1",
                    "materialize_20261015_1.py"}
    fixed.update((WORKSPACE / "scripts" / ("local_member_intake_bootstrap_" + name)).as_posix()
                 for name in source_names)
    if literal in fixed:
        return
    prefix = RUN.as_posix() + "/"
    assert literal.startswith(prefix), ("Unregistered read target refused", literal)
    relative = literal[len(prefix):]
    if "/" not in relative:
        assert re.fullmatch(r"bootstrap_[A-Za-z0-9_]+\.(?:json|ps1|txt)", relative), relative
        return
    parts = relative.split("/")
    if parts[0] == "bootstrap_manifests":
        assert parts in (["bootstrap_manifests", "source_1.json"], ["bootstrap_manifests", "runtime_1.json"])
        return
    if parts[0] == "bootstrap_contexts":
        assert len(parts) == 2
        assert any(parts[1] == f"{index:02d}_{case}_{role}.json"
                   for index, case in enumerate(CASE_IDS) for role in ("CW", "CH"))
        return
    if parts[:2] == ["bootstrap_inputs", "literal_recipes"]:
        assert len(parts) == 3 and re.fullmatch(r"[a-z0-9_]+\.bin", parts[2])
        return
    assert parts[0] in {"bootstrap_inputs", "bootstrap_attempts"} and len(parts) == 3
    assert parts[1] in {f"{index:02d}_{case}" for index, case in enumerate(CASE_IDS)}
    if parts[0] == "bootstrap_inputs":
        assert parts[2] in {"expected_base.bin", "submitted.bin", "rejected_input.json"}
    else:
        assert parts[2] in {"root_receipt.json", "owned_capture.json", "tool_receipt.json",
                            "observer_entry.json", "host_stdout.bin", "host_stderr.bin",
                            "root_stdin_prepared.bin"} or re.fullmatch(r"read_buffer_[0-9]{4}\.bin", parts[2])


def _load(path, cap, expected_sha=None, expected_length=None):
    raw = _read(path, cap)
    if expected_sha is not None:
        assert _sha(raw) == expected_sha, ("Frozen raw identity changed", str(path))
    if expected_length is not None:
        assert len(raw) == expected_length, ("Frozen raw length changed", str(path))
    return raw, _json(raw)


def _own_hash(value, field):
    assert field in value
    body = {key: item for key, item in value.items() if key != field}
    assert value[field] == _sha(_canonical(body)), (field, "complete own body")


def _hex(value):
    assert type(value) is str and re.fullmatch(r"(?:[0-9a-f]{2})*", value)
    return bytes.fromhex(value)


def _at(value, position):
    for key in position.split("."):
        value = value[key]
    return value


class _Types:
    """Interpret the independent D grammar, never a producer's schema registry."""

    def __init__(self, declarations):
        expected = declarations["expected_template_registry"]
        self.registry = expected["types"] | expected["records"] | expected["observation_records"]

    def named(self, value, name, position=None):
        assert name in self.registry, ("Unresolved independent D type", name)
        if name == "InitializationObservation":
            assert len(_canonical(value)) <= 32768, "Complete initializer record cap"
        definition = self.registry[name]
        position = position or name
        if definition["kind"] == "primitive":
            self.expression(value, definition["domain"], position)
            return
        assert definition["kind"] == "record"
        assert type(value) is dict and set(value) == set(definition["keys"]), (
            position, "complete exact keys", type(value).__name__)
        assert set(definition["fields"]) == set(definition["keys"])
        for key in definition["keys"]:
            self.expression(value[key], definition["fields"][key], position + "." + key)

    def expression(self, value, expr, position):
        op = expr["op"]
        if op == "ref":
            self.named(value, expr["name"], position)
        elif op == "literal":
            _same(value, expr["value"], position)
        elif op == "integer":
            assert type(value) is int and expr["min"] <= value <= expr["max"], (position, value)
        elif op == "boolean":
            assert type(value) is bool, (position, value)
        elif op == "string":
            assert type(value) is str and expr["min"] <= len(value) <= expr["max"], position
            if expr["encoding"] == "ascii":
                assert value.isascii(), position
            if expr["pattern"] is not None:
                assert re.fullmatch(expr["pattern"], value), position
            _json_values(value)
        elif op == "enum":
            assert any(type(value) is type(item) and value == item for item in expr["values"]), (
                position, value)
        elif op == "nullable":
            if value is not None:
                self.expression(value, expr["item"], position)
        elif op == "array":
            assert type(value) is list and expr["min"] <= len(value) <= expr["max"], position
            for index, item in enumerate(value):
                self.expression(item, expr["item"], f"{position}[{index}]")
        elif op == "union":
            errors = []
            for alternative in expr["items"]:
                try:
                    self.expression(value, alternative, position)
                except AssertionError as error:
                    errors.append(str(error))
                else:
                    return
            raise AssertionError((position, "no independent D variant", errors))
        else:
            raise AssertionError((position, "unsupported independent D operation", op))


@pytest.fixture(scope="module")
def registration():
    _, declarations = _load(D_PATH, 4194304, D_RAW_SHA, 337273)
    _, registered = _load(R_PATH, 1048576, R_RAW_SHA, 258233)
    assert R_CANONICAL_SHA is not None, "Required R2 canonical identity not yet root-bound"
    assert _sha(_canonical(registered)) == R_CANONICAL_SHA
    assert registered["window"]["hard_end_utc"] == HARD_END
    assert tuple(row["case_id"] for row in registered["control_schedule"]) == CASE_IDS
    assert tuple(row["ordinal"] for row in registered["control_schedule"]) == tuple(range(24))
    assert registered["authority_flags"] == declarations["authority_flags"]
    assert len(declarations["authority_flags"]) == 28
    for name, flag in declarations["authority_flags"]:
        assert type(name) is str and flag is False
    return declarations, registered, _Types(declarations)


@pytest.fixture(scope="module", params=CASE_IDS)
def attempt(request, registration, cohort):
    declarations, registered, types = registration
    row = next(row for row in registered["control_schedule"] if row["case_id"] == request.param)
    control = next(row for row in declarations["controls"] if row["case_id"] == request.param)
    case = next(row for row in cohort["index"]["cases"] if row["case_id"] == request.param)
    expected = next(row for row in cohort["expectations"]["cases"] if row["case_id"] == request.param)
    for key in ("root_receipt", "owned_capture", "tool_receipt"):
        assert case[key]["path"] == row["outputs"][key]
    root_raw, root = _artifact_ref(case["root_receipt"], 335544320)
    host_slice = root["host_receipt"]
    assert host_slice is not None, "Mandatory complete actual LMF1, never a fabricated no-host substitute"
    physical_stdout = _read(row["outputs"]["host_stdout"], 67371024)
    assert host_slice["artifact_path"] == "host_stdout.bin"
    assert row["outputs"]["host_stdout"] == row["outputs"]["directory"] + "/host_stdout.bin"
    start, count = host_slice["byte_offset"], host_slice["byte_length"]
    assert 0 <= start <= len(physical_stdout) and 0 < count <= 67108864
    assert start + count <= len(physical_stdout)
    host_raw = physical_stdout[start:start + count]
    assert host_slice["sha256"] == _sha(host_raw)
    host = _json(host_raw)
    assert host_raw == _canonical(host)
    _same(host, host_slice["parsed_receipt"])
    assert not (Path(row["outputs"]["directory"]) / "host_receipt.json").exists(), (
        "Explicit absent alias; no second complete 64MiB receipt copy")
    _, owned = _artifact_ref(case["owned_capture"], 8388608)
    _, tool = _artifact_ref(case["tool_receipt"], 8388608)
    submitted = _read(row["inputs"]["submitted"], 8193)
    base_path = Path(row["inputs"]["expected_base"])
    if request.param == "packet_first_excess":
        assert not base_path.exists(), "No fabricated original for first-excess recipe"
        original = None
    else:
        original = _read(base_path, 8192)
    worker_raw, worker_context = _load(row["contexts"]["worker"], 3072)
    host_context_raw, host_context = _load(row["contexts"]["host"], 3072)
    return {"case_id": request.param, "declarations": declarations, "registered": registered,
            "types": types, "row": row, "control": control, "host": host, "host_raw": host_raw,
            "root": root, "root_raw": root_raw, "submitted": submitted, "original": original,
            "worker_context": worker_context, "worker_context_raw": worker_raw,
            "host_context": host_context, "host_context_raw": host_context_raw,
            "cohort": cohort, "cohort_case": case, "expected_case": expected,
            "physical_stdout": physical_stdout, "owned": owned, "tool": tool}


def _packet_literal(control, flags):
    return {"version": "local-member-intake-bootstrap-packet-v1", "operation": "bootstrap",
            "case_id": control["case_id"], "registration_sha256": R_CANONICAL_SHA,
            "protocol_sha256": P_CANONICAL_SHA, "oracle_sha256": D_RAW_SHA,
            "hard_end_utc": HARD_END, "nonce_hex": control["nonce_hex"],
            "control": control["control"], "authority_flags": flags}


def _recipe_bytes(recipe):
    op = recipe["op"]
    if op == "literal_hex":
        raw = _hex(recipe["hex"])
        assert len(raw) == recipe["raw_byte_length"]
        return raw
    if op == "ascii_padding_record":
        prefix, suffix = recipe["prefix"].encode("ascii"), recipe["suffix"].encode("ascii")
        count = recipe["raw_byte_length"] - len(prefix) - len(suffix)
        assert count >= 0
        return prefix + recipe["fill"].encode("ascii") * count + suffix
    if op == "repeat_ascii":
        return recipe["character"].encode("ascii") * recipe["count"]
    if op == "utf16le":
        assert recipe["include_nul"] is False
        return recipe["text"].encode("utf-16-le")
    if op == "zeroed_buffer_with_writes":
        raw = bytearray(recipe["raw_byte_length"])
        formats = {"u32-le": "<I", "u64-le": "<Q", "i64-le": "<q"}
        for write in recipe["writes"]:
            struct.pack_into(formats[write["encoding"]], raw, write["offset"], write["value"])
        return bytes(raw)
    raise AssertionError(("Not a fully fixed raw recipe", op))


def test_registered_literal_recipes_are_complete_and_independent(registration):
    declarations, registered, _ = registration
    for artifact in registered["artifact_contract"]["literal_recipe_artifacts"]:
        recipe = declarations["raw_byte_recipes"][artifact["recipe_name"]]
        _same(artifact["independent_complete_recipe"], recipe)
        expected = _recipe_bytes(recipe)
        assert _read(artifact["path"], len(expected)) == expected


def test_entire_submitted_and_original_packet_recipe(attempt):
    packet = _packet_literal(attempt["control"], attempt["declarations"]["authority_flags"])
    base = _canonical(packet)
    case = attempt["case_id"]
    if case == "packet_first_excess":
        packet["padding"] = ""
        count = 8193 - len(_canonical(packet))
        assert count >= 0
        packet["padding"] = "a" * count
        expected = _canonical(packet)
        assert len(expected) == 8193 and attempt["original"] is None
    elif case == "packet_wrong_pin":
        assert base == attempt["original"]
        packet["nonce_hex"] = "00000000000000000000000000000004"
        expected = _canonical(packet)
        assert len(expected) == len(base)
        differences = [(old, new) for old, new in zip(base, expected, strict=True) if old != new]
        assert differences == [(ord("3"), ord("4"))]
    else:
        expected = base
        assert attempt["original"] == base
    assert attempt["submitted"] == expected


def test_complete_host_and_root_schema_and_own_hashes(attempt):
    types = attempt["types"]
    types.named(attempt["host"], "BootstrapAttemptReceipt")
    types.named(attempt["root"], "RootObservationReceipt")
    for value in (attempt["host"], attempt["root"]):
        _own_hash(value, "receipt_sha256")
        assert value["registration_sha256"] == R_CANONICAL_SHA
        assert value["case_id"] == attempt["case_id"]
        _same(value["authority_flags"], attempt["declarations"]["authority_flags"])
    assert len(_canonical(attempt["host"])) <= 67108864
    assert len(attempt["root_raw"]) <= 335544320
    assert attempt["host"]["oracle_sha256"] == D_RAW_SHA
    assert attempt["host"]["packet_sha256"] == _sha(attempt["submitted"])
    assert attempt["host"]["terminal"]["acceptance"] == "accepted_control"
    assert attempt["root"]["terminal"]["acceptance"] == "accepted_control"
    assert attempt["root"]["wrapper_sha256"] == attempt["cohort"]["seal"]["observer"]["raw_sha256"]


def _artifact_ref(reference, cap):
    assert set(reference) == {"path", "raw_byte_length", "raw_sha256", "canonical_byte_length",
                              "canonical_sha256"}
    assert type(reference["path"]) is str
    for key in ("raw_byte_length", "canonical_byte_length"):
        assert type(reference[key]) is int and 0 < reference[key] <= cap
    for key in ("raw_sha256", "canonical_sha256"):
        assert type(reference[key]) is str and re.fullmatch(r"[0-9a-f]{64}", reference[key])
    raw, value = _load(reference["path"], cap, reference["raw_sha256"], reference["raw_byte_length"])
    canonical = _canonical(value)
    assert len(canonical) == reference["canonical_byte_length"]
    assert _sha(canonical) == reference["canonical_sha256"]
    return raw, value


def _keys(value, keys):
    assert type(value) is dict and set(value) == set(keys), ("closed record", keys, value)


def _raw_ref(reference, cap):
    _keys(reference, ("path", "raw_byte_length", "raw_sha256"))
    assert type(reference["path"]) is str
    assert type(reference["raw_byte_length"]) is int and 0 <= reference["raw_byte_length"] <= cap
    assert re.fullmatch(r"[0-9a-f]{64}", reference["raw_sha256"])
    raw = _read(reference["path"], cap)
    assert len(raw) == reference["raw_byte_length"] and _sha(raw) == reference["raw_sha256"]
    return raw


@pytest.fixture(scope="module")
def cohort(registration):
    declarations, registered, _ = registration
    _, index = _load(RUN / "bootstrap_cohort_1.json", 33554432)
    _keys(index, ("version", "expectations", "launch_seal", "cases", "authority_flags"))
    assert index["version"] == "local-member-intake-bootstrap-cohort-v1"
    assert [row["case_id"] for row in index["cases"]] == list(CASE_IDS)
    assert [row["ordinal"] for row in index["cases"]] == list(range(24))
    for row in index["cases"]:
        _keys(row, ("ordinal", "case_id", "root_receipt", "owned_capture", "tool_receipt", "physical_outputs"))
    _, expectations = _artifact_ref(index["expectations"], 4194304)
    _keys(expectations, ("version", "window_start_utc", "hard_end_utc", "registration", "protocol",
                         "declarations", "source_manifest", "runtime_manifest", "startup_policy",
                         "primitive_transfer", "materializer", "literal_artifacts", "cases", "authority_flags"))
    assert expectations["version"] == "local-member-intake-bootstrap-expectations-v1"
    assert expectations["window_start_utc"] == "2026-10-15T06:59:08Z"
    assert expectations["hard_end_utc"] == HARD_END
    assert [row["case_id"] for row in expectations["cases"]] == list(CASE_IDS)
    assert [row["ordinal"] for row in expectations["cases"]] == list(range(24))
    _, selected_registration = _artifact_ref(expectations["registration"], 1048576)
    _same(selected_registration, registered)
    _, selected_declarations = _artifact_ref(expectations["declarations"], 4194304)
    _same(selected_declarations, declarations)
    _artifact_ref(expectations["protocol"], 1048576)
    _artifact_ref(expectations["source_manifest"], 1048576)
    _artifact_ref(expectations["runtime_manifest"], 1048576)
    _artifact_ref(expectations["primitive_transfer"], 1048576)
    _raw_ref(expectations["materializer"], 262144)
    _raw_ref(expectations["startup_policy"], 262144)
    recipes = registered["artifact_contract"]["literal_recipe_artifacts"]
    assert len(expectations["literal_artifacts"]) == len(recipes) == 14
    for actual, registered_recipe in zip(expectations["literal_artifacts"], recipes, strict=True):
        _keys(actual, ("name", "artifact"))
        assert actual["name"] == registered_recipe["recipe_name"]
        assert actual["artifact"]["path"] == registered_recipe["path"]
        expected_bytes = _recipe_bytes(declarations["raw_byte_recipes"][actual["name"]])
        assert _raw_ref(actual["artifact"], len(expected_bytes)) == expected_bytes
    _, seal = _artifact_ref(index["launch_seal"], 1048576)
    _keys(seal, ("version", "expectations", "observer", "primitives", "invocations", "authority_flags"))
    assert seal["version"] == "local-member-intake-bootstrap-launch-seal-v1"
    _same(seal["expectations"], index["expectations"])
    _raw_ref(seal["observer"], 262144)
    _raw_ref(seal["primitives"], 262144)
    assert [row["case_id"] for row in seal["invocations"]] == list(CASE_IDS)
    assert [row["ordinal"] for row in seal["invocations"]] == list(range(24))
    for value in (index, expectations, seal):
        _same(value["authority_flags"], declarations["authority_flags"])
    return {"index": index, "expectations": expectations, "seal": seal}


def test_prelaunch_E_seal_full_ordered_cases_inputs_and_commands(attempt):
    expected = attempt["expected_case"]
    _keys(expected, ("ordinal", "case_id", "expected_base", "submitted", "rejected_evidence",
                     "worker_context", "host_context", "expected_packet_sha256", "expected_template",
                     "host_invocation", "outputs"))
    assert expected["ordinal"] == attempt["row"]["ordinal"]
    assert expected["case_id"] == attempt["case_id"]
    assert _raw_ref(expected["submitted"], 8193) == attempt["submitted"]
    if attempt["original"] is None:
        assert expected["expected_base"] is None
    else:
        assert _raw_ref(expected["expected_base"], 8192) == attempt["original"]
    assert _artifact_ref(expected["worker_context"], 3072)[0] == attempt["worker_context_raw"]
    assert _artifact_ref(expected["host_context"], 3072)[0] == attempt["host_context_raw"]
    assert expected["expected_packet_sha256"] == attempt["host_context"]["expected_packet_sha256"]
    if attempt["case_id"] in PURE:
        raw, _ = _artifact_ref(expected["rejected_evidence"], 32768)
        assert raw == _read(attempt["row"]["inputs"]["rejected_evidence"], 32768)
    else:
        assert expected["rejected_evidence"] is None
    template = expected["expected_template"]
    _keys(template, ("declarations", "case_selector", "registry_selector", "template_name"))
    _same(template["declarations"], attempt["cohort"]["expectations"]["declarations"])
    assert template["case_selector"] == attempt["case_id"]
    assert template["registry_selector"] == "expected_template_registry"
    assert template["template_name"] == attempt["control"]["expected_template"]
    _same(expected["outputs"], attempt["row"]["outputs"])
    invocation = expected["host_invocation"]
    _keys(invocation, ("file_name", "argument_list", "prepared_command_line", "working_directory", "environment"))
    process = attempt["registered"]["process_contract"]
    assert invocation["file_name"] == process["direct_interpreter"]
    assert invocation["working_directory"] == process["working_directory"]
    assert invocation["argument_list"] == ["-B", "-I",
        "C:/Users/pabta/Projects/ai-trader/scripts/local_member_intake_bootstrap_host_20261015_1.py",
        attempt["submitted"].hex(), _canonical(attempt["host_context"]).hex()]
    assert invocation["prepared_command_line"] == ('"' + invocation["file_name"] + '" '
        + " ".join(invocation["argument_list"]))
    _same(invocation["environment"], process["environment"])
    actual = attempt["root"]["host_creation"]["start_info"]
    assert actual["file_name"] == invocation["file_name"]
    assert actual["argument_list"] == invocation["argument_list"]
    assert actual["working_directory"] == invocation["working_directory"]
    _same(actual["environment"], invocation["environment"])
    assert actual["use_shell_execute"] is False and actual["create_no_window"] is True
    assert actual["redirect_stdin"] is actual["redirect_stdout"] is actual["redirect_stderr"] is True
    sealed = attempt["cohort"]["seal"]["invocations"][attempt["row"]["ordinal"]]
    _keys(sealed, ("ordinal", "case_id", "script_path", "parameters"))
    parameters = sealed["parameters"]
    _keys(parameters, ("CaseId", "LaunchSealPath", "ExpectedExpectationsSha256",
                       "ObserverSha256", "PrimitivesSha256"))
    assert parameters["CaseId"] == attempt["case_id"]
    assert parameters["LaunchSealPath"] == str(RUN / "bootstrap_launch_seal_1.json").replace("\\", "/")
    assert parameters["ExpectedExpectationsSha256"] == attempt["cohort"]["index"]["expectations"]["raw_sha256"]
    assert parameters["ObserverSha256"] == attempt["cohort"]["seal"]["observer"]["raw_sha256"]
    assert parameters["PrimitivesSha256"] == attempt["cohort"]["seal"]["primitives"]["raw_sha256"]


def test_complete_contexts_manifest_bodies_and_acyclic_associations(attempt):
    types = attempt["types"]
    worker, host = attempt["worker_context"], attempt["host_context"]
    for context in (worker, host):
        types.named(context, "BootstrapContext")
        assert context["hard_end_utc"] == HARD_END
        assert context["hard_end_unix_ns"] == 1792076348000000000
        assert context["working_directory"] == str(WORKSPACE).replace("\\", "/")
        assert context["registration"]["raw_sha256"] == R_RAW_SHA
        assert context["registration"]["canonical_sha256"] == R_CANONICAL_SHA
        assert context["protocol"]["canonical_sha256"] == P_CANONICAL_SHA
        assert context["declarations"]["raw_sha256"] == D_RAW_SHA
        for field, cap in (("registration", 1048576), ("protocol", 1048576),
                           ("declarations", 4194304), ("source_manifest", 1048576),
                           ("runtime_manifest", 1048576)):
            _artifact_ref(context[field], cap)
    assert worker["role"] == "worker" and worker["worker_context"] is None
    assert host["role"] == "host"
    raw, selected_worker = _artifact_ref(host["worker_context"], 3072)
    assert raw == attempt["worker_context_raw"]
    _same(selected_worker, worker)
    for key in worker:
        if key not in {"role", "worker_context"}:
            _same(host[key], worker[key], key)
    expected_pin = _sha(attempt["original"] if attempt["case_id"] == "packet_wrong_pin"
                        else attempt["submitted"])
    assert worker["expected_packet_sha256"] == host["expected_packet_sha256"] == expected_pin
    _, manifest = _artifact_ref(worker["source_manifest"], 1048576)
    types.named(manifest, "SourceManifest")
    assert manifest["registration_sha256"] == R_CANONICAL_SHA
    expected_sources = attempt["registered"]["binding_contract"]["source_manifest_schema"][
        "exact_ordered_runtime_role_path_set"]
    assert len(manifest["sources"]) == len(expected_sources) == 6
    for actual, expected in zip(manifest["sources"], expected_sources, strict=True):
        assert actual["role"] == expected["role"] and actual["path"] == expected["path"]
        _read_source = _read(actual["path"], 262144)
        assert len(_read_source) == actual["raw_byte_length"]
        assert _sha(_read_source) == actual["raw_sha256"]
    _, runtime = _artifact_ref(worker["runtime_manifest"], 1048576)
    types.named(runtime, "RuntimeManifest")
    assert runtime["registration_sha256"] == R_CANONICAL_SHA
    export_names = set(attempt["declarations"]["expected_template_registry"][
        "native_operation_contracts"])
    assert len(export_names) == 33
    for role in ("host", "worker"):
        rows = [row for row in runtime["exports"] if row["role"] == role]
        assert len(rows) == 33 and {row["export_name"] for row in rows} == export_names
        assert len({row["export_name"] for row in rows}) == len(rows)
    assert len(runtime["exports"]) == 66
    assert len({(row["role"], row["absolute_path_utf16le_hex"])
                for row in runtime["static_modules"]}) == len(runtime["static_modules"])


def test_exact_policy_packet_flags_and_pure_absence(attempt):
    host, case = attempt["host"], attempt["case_id"]
    expected = dict(attempt["declarations"]["expected_template_registry"]["fixed_values"]["default_policy"])
    if case == "memory_positive_control":
        expected["process_memory_bytes"] = 536870912
    _same(host["declared_policy"], expected)
    if case in PURE:
        assert host["packet"] is None
        _same(host["creation"], attempt["declarations"]["expected_template_registry"][
            "fixed_values"]["pure_absent_creation"])
        assert host["parent_identity"] is None
        for key in ("job_observations", "api_trace"):
            assert host[key] == []
        assert host["stdout"] is host["stderr"] is host["result"] is None
        lifecycle = host["lifecycle"]
        assert [row["event"] for row in lifecycle] == ["preflight", "failure_selected", "finished"]
        assert [row["ordinal"] for row in lifecycle] == [0, 1, 2]
        assert all(row["related_api_ordinals"] == [] for row in lifecycle)
        assert [row["monotonic_ns"] for row in lifecycle] == sorted(row["monotonic_ns"] for row in lifecycle)
    else:
        _same(host["packet"], _json(attempt["submitted"]))


def test_complete_rejected_input_only_for_three_pure_controls(attempt):
    path = Path(attempt["row"]["inputs"]["rejected_evidence"])
    if attempt["case_id"] not in PURE:
        assert not path.exists(), "No fabricated rejection evidence for a created-control recipe"
        return
    _, value = _load(path, 32768)
    attempt["types"].named(value, "RejectedInputEvidence")
    _own_hash(value, "rejection_sha256")
    assert value["case_id"] == attempt["case_id"]
    assert value["registration_sha256"] == R_CANONICAL_SHA
    assert value["oracle_sha256"] == D_RAW_SHA
    assert value["submitted_raw_hex"] == attempt["submitted"].hex()
    assert value["submitted_raw_byte_length"] == len(attempt["submitted"])
    assert value["submitted_raw_sha256"] == _sha(attempt["submitted"])
    expected_raw = attempt["original"]
    assert value["expected_raw_hex"] == (None if expected_raw is None else expected_raw.hex())
    expected_pin = _sha(expected_raw if attempt["case_id"] == "packet_wrong_pin"
                        else attempt["submitted"])
    assert value["expected_packet_sha256"] == expected_pin
    assert value["first_reason"] == attempt["control"]["expected_reason"]
    assert value["admitted_packet"] is None and value["native_setup_attempted"] is False


def _stream(raw):
    if raw is None:
        return None
    retained = _hex(raw["retained_hex"])
    assert raw["retained_byte_count"] == len(retained)
    assert raw["retained_sha256"] == _sha(retained)
    assert raw["observed_byte_count_lower_bound"] == len(retained)
    if raw["complete"]:
        assert raw["eof_observed"] is True and raw["excess_sentinel_observed"] is False
    return retained


def _semantic(attempt):
    physical = _stream(attempt["host"]["stdout"])
    if physical is None:
        return None
    if attempt["case_id"] in NO_READY:
        return physical
    assert physical[:8] == READY
    return physical[8:]


def _fixed_semantic(attempt, name):
    recipe = attempt["declarations"]["raw_byte_recipes"][name]
    if recipe["op"] in {"literal_hex", "ascii_padding_record", "repeat_ascii", "utf16le",
                         "zeroed_buffer_with_writes"}:
        return _recipe_bytes(recipe)
    return None


def test_complete_physical_streams_and_literal_semantics(attempt):
    host, case = attempt["host"], attempt["case_id"]
    semantic = _semantic(attempt)
    stderr = _stream(host["stderr"])
    if case in PURE or case == "creation_refusal":
        assert semantic is stderr is None
        return
    assert semantic is not None and stderr is not None
    assert len(_hex(host["stdout"]["retained_hex"])) <= 4194313
    assert len(stderr) <= 4194313
    recipe = attempt["control"]["stdout_semantic_recipe"]
    fixed = _fixed_semantic(attempt, recipe)
    if fixed is not None:
        assert semantic == fixed
    assert stderr == (b"x" if case == "unexpected_stderr" else b"")
    template = attempt["declarations"]["expected_template_registry"]["templates"][
        attempt["control"]["expected_template"]]
    for stream_name in ("stdout", "stderr"):
        expected = template.get("expect", {}).get(stream_name)
        if type(expected) is dict:
            for key in ("complete", "eof_observed", "excess_sentinel_observed"):
                if key in expected:
                    assert host[stream_name][key] is expected[key], (case, stream_name, key)


def test_selected_terminal_template_literals(attempt):
    host, case, control = attempt["host"], attempt["case_id"], attempt["control"]
    terminal = host["terminal"]
    assert terminal["outcome"] == control["expected_outcome"]
    assert terminal["failure_code"] == control["expected_reason"]
    template = attempt["declarations"]["expected_template_registry"]["templates"][
        control["expected_template"]]
    for position, expected in template.get("expect", {}).items():
        if type(expected) is not dict:
            _same(_at(host, position), expected, position)
    if case in PURE:
        assert terminal == {
            "outcome": "preflight_refusal", "failure_stage": "preflight",
            "failure_code": control["expected_reason"], "termination_requested": False,
            "termination_return": None, "wait_result_u32": None, "exit_code_u32": None,
            "exit_filetime_u64": None, "kernel_time_100ns_u64": None,
            "user_time_100ns_u64": None, "final_job_empty": None,
            "parent_closes": [], "cleanup_complete": None, "acceptance": "accepted_control"}
    elif case != "creation_refusal":
        assert terminal["wait_result_u32"] == 0
        assert terminal["final_job_empty"] is True and terminal["cleanup_complete"] is True
        assert terminal["exit_filetime_u64"] is not None
        if terminal["termination_requested"]:
            assert terminal["termination_return"]["raw_i64"] != 0
            assert terminal["exit_code_u32"] == 3758096455
        if case == "cpu_limit":
            assert terminal["termination_requested"] is False
            assert terminal["exit_code_u32"] != 0
            assert terminal["user_time_100ns_u64"] >= 50000000


def _return(value):
    kind = value["kind"]
    assert kind in {"bool32", "dword32", "handle64", "void"}
    if kind == "bool32":
        assert type(value["raw_i64"]) is int and -2147483648 <= value["raw_i64"] <= 2147483647
        assert value["raw_u64"] is None
    elif kind in {"dword32", "handle64"}:
        assert value["raw_i64"] is None and type(value["raw_u64"]) is int
        assert 0 <= value["raw_u64"] <= (4294967295 if kind == "dword32" else 18446744073709551615)
    else:
        assert value["raw_i64"] is value["raw_u64"] is value["win32_error_u32"] is None
    if value["win32_error_u32"] is not None:
        assert type(value["win32_error_u32"]) is int and 0 <= value["win32_error_u32"] <= 4294967295


def _pointer(value):
    address = value["address_u64"]
    if address == 0:
        assert value == {"address_u64": 0, "storage_before_hex": None,
                         "storage_bytes_u32": 0, "pointee_kind": "none"}
    elif value["pointee_kind"] in {"external_function_address", "allocation_base"}:
        assert value["storage_before_hex"] is None and value["storage_bytes_u32"] == 0
    else:
        assert len(_hex(value["storage_before_hex"])) == value["storage_bytes_u32"]


def _buffer(value):
    raw = _hex(value["full_buffer_hex"])
    assert len(raw) == value["capacity_bytes"]
    if value["output_validity"] == "storage_only":
        assert value["returned_bytes"] is value["valid_prefix_bytes"] is None
        assert value["projection_kind"] == "none"
    else:
        assert value["output_validity"] == "documented_valid"
        assert value["projection_kind"] in {"u32", "u64", "handle_u64", "filetime_u64",
            "process_information", "job_extended_limits", "job_accounting", "job_pid_list",
            "utf16_z", "module_array", "byte_prefix", "opaque_attribute_list"}
        assert type(value["valid_prefix_bytes"]) is int
        assert 0 <= value["valid_prefix_bytes"] <= len(raw)
        if value["returned_bytes"] is not None:
            assert 0 <= value["returned_bytes"] <= len(raw)


def _api_trace(rows, declarations):
    contracts = declarations["expected_template_registry"]["native_operation_contracts"]
    assert len(rows) <= 4096
    assert [row["ordinal"] for row in rows] == list(range(len(rows)))
    for row in rows:
        assert row["api"] in contracts
        contract = contracts[row["api"]]
        assert row["source_selector"] == contract["source_selector"]
        assert row["return"]["kind"] == contract["return"]
        _return(row["return"])
        assert row["started_monotonic_ns"] <= row["ended_monotonic_ns"]
        assert len(row["arguments"]) == len(contract["parameters"])
        for argument, parameter in zip(row["arguments"], contract["parameters"], strict=True):
            assert argument["name"] == parameter[0] and argument["kind"] == parameter[1]
            value, kind = argument["value"], argument["kind"]
            if kind == "pointer":
                _pointer(value)
                if parameter[2] not in {"selected-job-buffer", "opaque_attribute_list-or-none",
                                       "selected-handle-array"}:
                    assert value["pointee_kind"] == parameter[2]
            elif kind in {"u32", "u64", "handle64", "i64"}:
                assert type(value) is int
                low, high = ((-9223372036854775808, 9223372036854775807) if kind == "i64"
                             else (0, 4294967295 if kind == "u32" else 18446744073709551615))
                assert low <= value <= high
        for buffer in row["output_buffers"]:
            _buffer(buffer)
        expected_buffers = [argument["name"] for argument in row["arguments"]
                            if argument["kind"] == "pointer"
                            and argument["value"]["storage_before_hex"] is not None]
        assert [buffer["parameter"] for buffer in row["output_buffers"]] == expected_buffers
        for buffer in row["output_buffers"]:
            argument = next(value for value in row["arguments"] if value["name"] == buffer["parameter"])
            assert buffer["capacity_bytes"] == argument["value"]["storage_bytes_u32"]
            if _pointer_category(row["api"], buffer["parameter"]) == "H":
                assert buffer["output_validity"] == "storage_only"
            if row["api"] == "CreateProcessW" and buffer["parameter"] == "lpCommandLine":
                assert buffer["output_validity"] == "storage_only"
            if buffer["output_validity"] == "documented_valid":
                projection = {"dword_out": "u32", "dword_inout": "u32", "size_t_inout": "u64",
                    "filetime_out": "filetime_u64", "handle_out": "handle_u64",
                    "process_information": "process_information", "module_array_128": "module_array",
                    "utf16_mutable_z": "utf16_z", "opaque_attribute_list": "opaque_attribute_list",
                    "job_extended_limit": "job_extended_limits", "job_accounting": "job_accounting",
                    "job_pid_list": "job_pid_list", "byte_buffer": "byte_prefix"}
                assert buffer["projection_kind"] == projection[argument["value"]["pointee_kind"]]
        if row["return"]["kind"] == "bool32" and row["return"]["raw_i64"] == 0:
            sizing = (row["api"] == "InitializeProcThreadAttributeList"
                      and _args(row)["lpAttributeList"]["address_u64"] == 0)
            for buffer in row["output_buffers"]:
                if not (sizing and buffer["parameter"] == "lpSize"):
                    assert buffer["output_validity"] == "storage_only"
        seed = row["saved_error_seed"]
        if row["api"] == "GetFileType":
            assert seed is not None and seed["helper"] == "ctypes.set_last_error"
            assert seed["input_i32"] == 0
            assert type(seed["returned_previous_i32"]) is int
            assert -2147483648 <= seed["returned_previous_i32"] <= 2147483647
        else:
            assert seed is None
        if row["return"]["kind"] == "bool32" and row["return"]["raw_i64"] != 0:
            assert row["return"]["win32_error_u32"] is None


def test_all_retained_host_native_call_shapes_and_full_buffers(attempt):
    _api_trace(attempt["host"]["api_trace"], attempt["declarations"])
    lifecycle = attempt["host"]["lifecycle"]
    assert len(lifecycle) <= 4096
    assert [row["ordinal"] for row in lifecycle] == list(range(len(lifecycle)))
    assert [row["monotonic_ns"] for row in lifecycle] == sorted(row["monotonic_ns"] for row in lifecycle)
    for row in lifecycle:
        assert all(0 <= ordinal < len(attempt["host"]["api_trace"])
                   for ordinal in row["related_api_ordinals"])
    if attempt["case_id"] in NO_RESUME:
        assert not any(row["api"] == "ResumeThread" for row in attempt["host"]["api_trace"])
        assert not any(row["event"] == "resumed" for row in lifecycle)


def _go(value, host):
    assert _hex(value["packet_hex"]) == _hex(host["creation"]["identity_transport"]["go_hex"])
    packet = _hex(value["packet_hex"])
    assert len(packet) == 48 and packet[:8] == bytes.fromhex("4c4d474f3030310a")
    assert int.from_bytes(packet[8:12], "little") == host["creation"]["observed_parent_pid"]
    assert int.from_bytes(packet[12:16], "little") == host["creation"]["child_pid"]
    ack = host["creation"]["identity_transport"]["ack"]
    _own_hash(ack, "ack_sha256")
    assert packet[16:] == bytes.fromhex(ack["ack_sha256"])
    offset, actual = 0, bytearray()
    assert 1 <= len(value["data_reads"]) <= 48
    for ordinal, row in enumerate(value["data_reads"]):
        assert row["ordinal"] == ordinal and row["offset_u32"] == offset
        assert row["requested_count_u32"] == 48 - offset
        _return(row["return"])
        assert row["return"]["raw_i64"] != 0 and row["return"]["win32_error_u32"] is None
        count = row["returned_count_u32"]
        assert 1 <= count <= row["requested_count_u32"]
        assert len(row["buffer_observations"]) == 2
        for buffer in row["buffer_observations"]:
            _buffer(buffer)
        data = next(buffer for buffer in row["buffer_observations"] if buffer["parameter"] == "lpBuffer")
        counter = next(buffer for buffer in row["buffer_observations"] if buffer["parameter"] == "lpNumberOfBytesRead")
        assert data["capacity_bytes"] == row["requested_count_u32"]
        assert int.from_bytes(_hex(counter["full_buffer_hex"]), "little") == count
        actual.extend(_hex(data["full_buffer_hex"])[:count])
        offset += count
    assert bytes(actual) == packet and offset == 48
    eof = value["eof_probe"]
    assert eof["offset_u32"] == 48 and eof["requested_count_u32"] == 1
    assert eof["return"] == {"kind": "bool32", "raw_i64": 0, "raw_u64": None,
                             "win32_error_u32": 109}
    assert eof["returned_count_u32"] is None
    assert len(eof["buffer_observations"]) == 2
    for buffer in eof["buffer_observations"]:
        _buffer(buffer)
        assert buffer["output_validity"] == "storage_only"
    close = value["stdin_close"]
    assert close["role"] == "control_stdin_read" and close["close_attempted"] is True
    assert close["close_bool_i32"] != 0 and close["win32_error_u32"] is None
    assert close["disposition"] == "closed"


def test_normal_result_complete_raw_bundle_and_go_read_eof(attempt):
    result = attempt["host"]["result"]
    if result is None:
        return
    case, host = attempt["case_id"], attempt["host"]
    attempt["types"].named(result, "BootstrapResult")
    assert result["case_id"] == case
    assert result["packet_sha256"] == _sha(attempt["submitted"])
    assert result["nonce_hex"] == attempt["control"]["nonce_hex"]
    assert result["worker_pid"] == host["creation"]["child_pid"]
    assert result["observed_parent_pid"] == host["creation"]["observed_parent_pid"]
    assert result["started_monotonic_ns"] <= result["ended_monotonic_ns"]
    _same(result["authority_flags"], attempt["declarations"]["authority_flags"])
    assert _semantic(attempt) == _canonical(result)
    bundle_raw = _hex(result["payload_hex"])
    assert len(bundle_raw) <= 262144
    bundle = _json(bundle_raw)
    attempt["types"].named(bundle, "ResultBundle")
    assert bundle_raw == _canonical(bundle)
    _go(bundle["go_observation"], host)
    assert result["worker_cleanup"] == [bundle["go_observation"]["stdin_close"]]
    if case in {"memory_limit", "memory_positive_control"}:
        payload = _json(_hex(bundle["control_payload_hex"]))
        attempt["types"].named(payload, "MemoryControlObservation")
        assert _hex(bundle["control_payload_hex"]) == _canonical(payload)
        assert payload["allocation_type_u32"] == 12288
        assert payload["requested_bytes_u64"] == 268435456 and payload["protection_u32"] == 4
        if case == "memory_limit":
            assert result["status"] == "controlled_failure"
            assert payload["return_address_u64"] == 0 and payload["release"] is None
            assert type(payload["win32_error_u32"]) is int
        else:
            assert result["status"] == "completed" and payload["return_address_u64"] > 0
            assert payload["win32_error_u32"] is None
            release = payload["release"]
            assert release["attempted"] is True
            assert release["address_u64"] == payload["return_address_u64"]
            assert release["size_u64"] == 0 and release["free_type_u32"] == 32768
            assert release["return_bool_i32"] != 0 and release["win32_error_u32"] is None
    else:
        assert bundle["control_payload_hex"] == "626f6f7473747261702d6f6b"
        assert result["status"] == "completed"


def _args(row):
    return {argument["name"]: argument["value"] for argument in row["arguments"]}


def _outputs(row):
    values = row["output_buffers"]
    assert len({value["parameter"] for value in values}) == len(values)
    return {value["parameter"]: value for value in values}


def _output_bytes(row, parameter, capacity=None):
    value = _outputs(row)[parameter]
    raw = _hex(value["full_buffer_hex"])
    if capacity is not None:
        assert len(raw) == value["capacity_bytes"] == capacity
    return raw


def _u32(raw, offset=0):
    return int.from_bytes(raw[offset:offset + 4], "little")


def _u64(raw, offset=0):
    return int.from_bytes(raw[offset:offset + 8], "little")


def _i64(raw, offset=0):
    return int.from_bytes(raw[offset:offset + 8], "little", signed=True)


def _limits(raw):
    assert len(raw) == 144
    names = ("read_operation_count", "write_operation_count", "other_operation_count",
             "read_transfer_count", "write_transfer_count", "other_transfer_count")
    return {"per_process_user_time_i64": _i64(raw), "per_job_user_time_i64": _i64(raw, 8),
            "limit_flags_u32": _u32(raw, 16), "minimum_working_set_u64": _u64(raw, 24),
            "maximum_working_set_u64": _u64(raw, 32), "active_process_limit_u32": _u32(raw, 40),
            "affinity_u64": _u64(raw, 48), "priority_class_u32": _u32(raw, 56),
            "scheduling_class_u32": _u32(raw, 60),
            "io_counters": {name: _u64(raw, 64 + 8 * index) for index, name in enumerate(names)},
            "process_memory_limit_u64": _u64(raw, 112), "job_memory_limit_u64": _u64(raw, 120),
            "peak_process_memory_used_u64": _u64(raw, 128),
            "peak_job_memory_used_u64": _u64(raw, 136)}


def _accounting(raw):
    assert len(raw) == 48
    return {"total_user_time_i64": _i64(raw), "total_kernel_time_i64": _i64(raw, 8),
            "period_user_time_i64": _i64(raw, 16), "period_kernel_time_i64": _i64(raw, 24),
            "total_page_fault_count_u32": _u32(raw, 32), "total_processes_u32": _u32(raw, 36),
            "active_processes_u32": _u32(raw, 40), "total_terminated_processes_u32": _u32(raw, 44)}


def test_every_job_query_projection_from_complete_literal_abi(attempt):
    host = attempt["host"]
    rows = host["job_observations"]
    assert [row["ordinal"] for row in rows] == list(range(len(rows)))
    phases = []
    for observation in rows:
        phases.append(observation["phase"])
        for prefix, byte_key, projection, query_class, size in (
            ("limits", "extended_limit_bytes_hex", "extended_limits", 9, 144),
            ("accounting", "accounting_bytes_hex", "accounting", 1, 48),
            ("process_list", "pid_list_bytes_hex", "process_ids", 3, 16),
        ):
            state = observation[prefix + "_state"]
            ordinal = observation[prefix + "_api_ordinal"]
            returned = observation[prefix + "_return"]
            if state == "not_attempted":
                assert ordinal is returned is observation[byte_key] is observation[projection] is None
                continue
            assert state in {"attempted_invalid", "observed_valid"}
            row = host["api_trace"][ordinal]
            assert row["api"] == "QueryInformationJobObject"
            _same(returned, row["return"])
            arguments = _args(row)
            assert arguments["JobObjectInformationClass"] == query_class
            assert arguments["cbJobObjectInformationLength"] == size
            raw = _output_bytes(row, "lpJobObjectInformation", size)
            assert observation[byte_key] == raw.hex()
            returned_length = _u32(_output_bytes(row, "lpReturnLength", 4))
            if state == "attempted_invalid":
                assert observation[projection] is None
                continue
            assert row["return"]["raw_i64"] != 0
            if prefix == "limits":
                assert returned_length == 144
                _same(observation[projection], _limits(raw))
                limits = observation[projection]
                assert limits["limit_flags_u32"] == 8458
                assert limits["per_process_user_time_i64"] == 50000000
                assert limits["active_process_limit_u32"] == 1
                assert limits["process_memory_limit_u64"] == host["declared_policy"]["process_memory_bytes"]
            elif prefix == "accounting":
                assert returned_length == 48
                _same(observation[projection], _accounting(raw))
            else:
                assigned, listed = _u32(raw), _u32(raw, 4)
                assert assigned == listed and listed in {0, 1}
                assert returned_length in {8, 16} and returned_length >= 8 + listed * 8
                expected_pids = [] if listed == 0 else [_u64(raw, 8)]
                assert observation["assigned_process_count"] == assigned
                assert observation["listed_process_count"] == listed
                _same(observation["process_ids"], expected_pids)
                if observation["phase"] in {"before_create", "terminal"}:
                    assert expected_pids == []
                else:
                    assert expected_pids == [host["creation"]["child_pid"]]
    if attempt["case_id"] in PURE:
        assert phases == []
    else:
        assert "before_create" in phases
        assert rows[-1]["phase"] == "terminal"
        if attempt["case_id"] != "creation_refusal":
            assert "suspended" in phases
        if attempt["case_id"] not in NO_RESUME:
            assert "resumed" in phases


def test_native_fixed_arguments_initial_storage_and_return_relations(attempt):
    host = attempt["host"]
    memory = host["declared_policy"]["process_memory_bytes"]
    for row in host["api_trace"]:
        api, args = row["api"], _args(row)
        if api == "CreateJobObjectW":
            assert args["lpJobAttributes"]["address_u64"] == args["lpName"]["address_u64"] == 0
        elif api == "SetInformationJobObject":
            assert args["JobObjectInformationClass"] == 9 and args["cbJobObjectInformationLength"] == 144
            recipe = "set_limit_input_positive" if memory == 536870912 else "set_limit_input_default"
            expected = _recipe_bytes(attempt["declarations"]["raw_byte_recipes"][recipe])
            assert _hex(args["lpJobObjectInformation"]["storage_before_hex"]) == expected
        elif api == "InitializeProcThreadAttributeList":
            assert args["dwAttributeCount"] == 2 and args["dwFlags"] == 0
            assert args["lpSize"]["storage_bytes_u32"] == 8
            if args["lpAttributeList"]["address_u64"] == 0:
                assert args["lpSize"]["storage_before_hex"] == "00" * 8
                assert row["return"]["raw_i64"] == 0
                assert type(row["return"]["win32_error_u32"]) is int
                assert 1 <= _u64(_output_bytes(row, "lpSize", 8)) <= 65536
        elif api == "UpdateProcThreadAttribute":
            assert args["dwFlags"] == 0
            assert args["Attribute"] in {131074, 131085}
            assert args["cbSize"] == (24 if args["Attribute"] == 131074 else 8)
            assert args["lpPreviousValue"]["address_u64"] == args["lpReturnSize"]["address_u64"] == 0
        elif api == "CreateProcessW":
            assert args["bInheritHandles"] == 1 and args["dwCreationFlags"] == 134743044
            assert args["lpProcessAttributes"]["address_u64"] == args["lpThreadAttributes"]["address_u64"] == 0
            assert args["lpStartupInfo"]["storage_bytes_u32"] == 112
            startup = _hex(args["lpStartupInfo"]["storage_before_hex"])
            assert _u32(startup) == 112 and _u32(startup, 60) == 256
            assert args["lpProcessInformation"]["storage_before_hex"] == "00" * 24
            for parameter in ("lpApplicationName", "lpCommandLine", "lpCurrentDirectory"):
                assert _hex(args[parameter]["storage_before_hex"]).endswith(b"\0\0")
            environment = _hex(args["lpEnvironment"]["storage_before_hex"])
            assert environment.endswith(b"\0\0\0\0") and len(environment) // 2 <= 8192
        elif api == "ResumeThread":
            assert args["hThread"] == host["creation"]["thread_handle_u64"]
            assert row["return"]["raw_u64"] == 1
        elif api == "WaitForSingleObject":
            assert args["hHandle"] == host["creation"]["process_handle_u64"]
            assert 0 <= args["dwMilliseconds"] <= 20
            assert row["return"]["raw_u64"] in {0, 258}
        elif api == "TerminateJobObject":
            assert args["uExitCode"] == 3758096455
        elif api == "CreatePipe":
            assert args["nSize"] == 65536
            assert args["hReadPipe"]["storage_before_hex"] == "00" * 8
            assert args["hWritePipe"]["storage_before_hex"] == "00" * 8
            security = _hex(args["lpPipeAttributes"]["storage_before_hex"])
            assert len(security) == 24 and _u32(security) == 24
            assert _u64(security, 8) == 0 and _u32(security, 16) == 1
        elif api == "PeekNamedPipe":
            assert args["lpBuffer"]["address_u64"] == args["lpBytesRead"]["address_u64"] == 0
            assert args["nBufferSize"] == 0
        elif api in {"ReadFile", "WriteFile"}:
            count_name = "nNumberOfBytesToRead" if api == "ReadFile" else "nNumberOfBytesToWrite"
            output_name = "lpNumberOfBytesRead" if api == "ReadFile" else "lpNumberOfBytesWritten"
            requested = args[count_name]
            assert requested > 0 and args["lpBuffer"]["storage_bytes_u32"] == requested
            assert args["lpOverlapped"]["address_u64"] == 0
            assert args[output_name]["storage_before_hex"] == "00" * 4
            if api == "ReadFile":
                assert requested <= 65536
                assert args["lpBuffer"]["storage_before_hex"] == "00" * requested
            if row["return"]["raw_i64"] != 0:
                count = _u32(_output_bytes(row, output_name, 4))
                assert 0 <= count <= requested
                if api == "WriteFile":
                    assert count == requested
            else:
                for buffer in row["output_buffers"]:
                    assert buffer["output_validity"] == "storage_only"
        elif api == "GetStdHandle":
            assert args["nStdHandle"] in {4294967286, 4294967285, 4294967284}
        elif api == "GetFileType":
            assert row["return"]["raw_u64"] == 3
            assert row["return"]["win32_error_u32"] is None
        elif api == "SetHandleInformation":
            assert args["dwMask"] == 1 and args["dwFlags"] in {0, 1}
        elif api == "LoadLibraryExW":
            assert args["hFile"] == 0 and args["dwFlags"] == 2304
        elif api == "GetModuleHandleExW":
            assert args["dwFlags"] == 6
        elif api in {"GetModuleFileNameW", "K32GetModuleFileNameExW"}:
            assert args["nSize"] == 512
            assert args["lpFilename"]["storage_before_hex"] == "00" * 1024
            result = row["return"]["raw_u64"]
            assert 1 <= result <= (511 if api == "GetModuleFileNameW" else 510)
            after = _output_bytes(row, "lpFilename", 1024)
            assert after[2 * result:2 * result + 2] == b"\0\0"
        elif api == "K32EnumProcessModulesEx":
            assert args["cb"] == 1024 and args["dwFilterFlag"] == 3
            assert args["lphModule"]["storage_before_hex"] == "00" * 1024
        elif api == "VirtualAlloc":
            assert args["lpAddress"]["address_u64"] == 0
            assert args["dwSize"] == 268435456
            assert args["flAllocationType"] == 12288 and args["flProtect"] == 4
        elif api == "VirtualFree":
            assert args["dwSize"] == 0 and args["dwFreeType"] == 32768


def _initialization(initialization, bindings, role, runtime):
    assert [row["ordinal"] for row in initialization] == list(range(len(initialization)))
    assert initialization
    for row in initialization:
        assert row["owner_role"] == role
        assert row["completed"] is True and row["exception"] is None
        assert row["exposed_handle_u64"] > 0
        assert row["started_monotonic_ns"] <= row["ended_monotonic_ns"]
        assert row["native_call_observation"] == "not_exposed"
        assert row["reference_disposition"] == "process_lifetime_bootstrap"
        arguments = row["arguments"]
        assert arguments["mode"] == 0 and arguments["handle"] is None
        assert arguments["use_errno"] is False and arguments["use_last_error"] is True
        assert arguments["winmode"] == 2304
    selected = [row for row in runtime["exports"] if row["role"] == role]
    assert len(bindings) == len(selected) == 33
    for ordinal, (binding, expected) in enumerate(zip(bindings, selected, strict=True)):
        assert binding["ordinal"] == ordinal and binding["owner_role"] == role
        assert binding["api_name"] == expected["export_name"]
        assert binding["completed"] is True and binding["exception"] is None
        assert binding["exposed_address_u64"] > 0
        assert binding["started_monotonic_ns"] <= binding["ended_monotonic_ns"]
        constructor = initialization[binding["constructor_ordinal"]]
        assert constructor["arguments"]["name"] == expected["requested_module_path"]


def test_complete_host_initialization_binding_and_module_pairs(attempt):
    if attempt["case_id"] in PURE:
        return
    host = attempt["host"]
    _, runtime = _artifact_ref(attempt["worker_context"]["runtime_manifest"], 1048576)
    _initialization(host["creation"]["initialization"], host["creation"]["binding_initialization"],
                    "host", runtime)
    snapshots = host["creation"]["module_observations"]
    assert len(snapshots) <= 6 and len(snapshots) % 2 == 0
    host_rows = [row for row in snapshots if row["role"] == "host"]
    worker_rows = [row for row in snapshots if row["role"] == "worker"]
    assert len(host_rows) == 4
    if attempt["case_id"] not in NO_READY:
        assert len(worker_rows) == 2
    for first, second in zip(snapshots[::2], snapshots[1::2], strict=True):
        assert first["state"] == second["state"] == "complete"
        assert first["role"] == second["role"]
        assert first["process_id"] == second["process_id"]
        assert first["process_creation_filetime_u64"] == second["process_creation_filetime_u64"]
        assert first["needed_bytes"] == second["needed_bytes"]
        assert first["raw_module_buffer_hex"] == second["raw_module_buffer_hex"]
        assert [(entry["module_base_u64"], entry["path_utf16le_hex"], entry["registered_static_sha256"])
                for entry in first["entries"]] == [
                    (entry["module_base_u64"], entry["path_utf16le_hex"], entry["registered_static_sha256"])
                    for entry in second["entries"]]
    for snapshot in snapshots:
        assert snapshot["state"] == "complete"
        enum = host["api_trace"][snapshot["enum_api_ordinal"]]
        assert enum["api"] == "K32EnumProcessModulesEx" and enum["return"]["raw_i64"] != 0
        raw = _hex(snapshot["raw_module_buffer_hex"])
        assert raw == _output_bytes(enum, "lphModule", 1024)
        assert snapshot["needed_bytes"] == _u32(_output_bytes(enum, "lpcbNeeded", 4))
        assert 0 <= snapshot["needed_bytes"] <= 1024 and snapshot["needed_bytes"] % 8 == 0
        entries = snapshot["entries"]
        bases = [_u64(raw, offset) for offset in range(0, snapshot["needed_bytes"], 8)]
        assert len(entries) == len(bases) and all(bases) and len(set(bases)) == len(bases)
        assert [row["module_base_u64"] for row in entries] == bases
        assert [row["ordinal"] for row in entries] == list(range(len(entries)))
        allowed = {row["absolute_path_utf16le_hex"]: row["sha256"] for row in runtime["static_modules"]}
        observed_paths = []
        for entry in entries:
            path_row = host["api_trace"][entry["path_api_ordinal"]]
            assert path_row["api"] == ("GetModuleFileNameW" if snapshot["role"] == "host"
                                        else "K32GetModuleFileNameExW")
            count = path_row["return"]["raw_u64"]
            path = _output_bytes(path_row, "lpFilename", 1024)[:2 * count].hex()
            assert entry["path_utf16le_hex"] == path and path in allowed
            assert entry["registered_static_sha256"] == allowed[path]
            observed_paths.append(path)
        observed_literals = [_hex(path).decode("utf-16-le", errors="strict") for path in observed_paths]
        assert set(runtime[snapshot["role"] + "_required_paths"]).issubset(observed_literals)


def _managed_value(value):
    kind, item = value["kind"], value["value"]
    if kind == "void":
        assert item is None
    elif kind == "bool":
        assert type(item) is bool
    elif kind in {"i32", "u32", "u64"}:
        bounds = {"i32": (-2147483648, 2147483647), "u32": (0, 4294967295),
                  "u64": (0, 18446744073709551615)}
        assert type(item) is int and bounds[kind][0] <= item <= bounds[kind][1]
    elif kind == "utf16le_hex":
        assert len(_hex(item)) % 2 == 0
    elif kind == "local_ref":
        assert item["kind"] in {"process", "stream", "task", "buffer"}
        assert type(item["id"]) is int and 0 <= item["id"] <= 4294967295
    elif kind == "buffer_allocation":
        assert type(item["id"]) is int and type(item["capacity_bytes"]) is int
        assert item["id"] >= 0 and item["capacity_bytes"] > 0
    else:
        assert kind == "date_time"
        _date(item, 1)


def _date(value, quantum):
    assert value["managed_type"] == "System.DateTime"
    assert value["kind"] in {"Utc", "Local"} and value["conversion_state"] == "valid"
    assert value["quantum_100ns"] == quantum
    assert type(value["ticks_i64"]) is int and type(value["utc_ticks_i64"]) is int
    assert type(value["filetime_u64"]) is int
    assert value["utc_ticks_i64"] - 504911232000000000 == value["filetime_u64"]
    assert value["filetime_u64"] >= 0
    if quantum == 10:
        assert value["filetime_u64"] % 10 == value["utc_ticks_i64"] % 10 == 0
    match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})\.([0-9]{7})(Z|[+-][0-9]{2}:[0-9]{2})",
                         value["roundtrip_text"])
    assert match
    calendar = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S")
    days = (calendar - datetime(1, 1, 1)).days
    ticks = ((days * 86400 + calendar.hour * 3600 + calendar.minute * 60 + calendar.second)
             * 10000000 + int(match[2]))
    assert ticks == value["ticks_i64"]
    if value["kind"] == "Utc":
        assert match[3] == "Z" and value["utc_ticks_i64"] == ticks
    else:
        assert match[3] != "Z"
        offset_hours, offset_minutes = int(match[3][1:3]), int(match[3][4:6])
        assert offset_hours <= 14 and offset_minutes < 60
        offset = (offset_hours * 3600 + offset_minutes * 60) * 10000000
        if match[3][0] == "-":
            offset = -offset
        assert value["utc_ticks_i64"] == ticks - offset


def test_managed_operations_full_closed_variants_and_task_provenance(attempt):
    rows = attempt["root"]["managed_calls"]
    contracts = attempt["declarations"]["expected_template_registry"]["managed_operation_contracts"]
    assert len(rows) <= 4352
    assert [row["ordinal"] for row in rows] == list(range(len(rows)))
    tasks, buffers = {}, {}
    for row in rows:
        operation = row["operation"]
        assert operation in contracts
        contract = contracts[operation]
        arguments = row["arguments"]
        receiver, values = arguments["receiver"], arguments["values"]
        if "receiver" in contract:
            _same(receiver, contract["receiver"])
        elif "receiver_one_of" in contract:
            assert receiver in contract["receiver_one_of"]
        else:
            assert contract["receiver_kind"] == "task" and receiver["kind"] == "task"
            assert receiver["id"] in tasks
        assert len(values) == len(contract["values"])
        for value, expected in zip(values, contract["values"], strict=True):
            _managed_value(value)
            assert value["kind"] == expected["kind"]
            if "value" in expected:
                _same(value["value"], expected["value"])
        if operation in {"Stream.ReadAsync", "Stream.WriteAsync"}:
            allocation, start, count = [value["value"] for value in values]
            assert start == 0 and allocation["capacity_bytes"] == count > 0
            assert allocation["id"] not in buffers
            buffers[allocation["id"]] = {"capacity": count, "stream": receiver["id"]}
            assert count <= (65536 if operation == "Stream.ReadAsync" else 524296)
        if operation == "Process.WaitForExit":
            assert 0 <= values[0]["value"] <= 20
        state = row["state"]
        assert state in {"pending", "completed", "faulted"}
        if state == "pending":
            assert row["ended_monotonic_ns"] is row["result"] is row["error"] is row["buffer_artifact"] is None
            continue
        assert row["started_monotonic_ns"] <= row["ended_monotonic_ns"]
        if state == "faulted":
            assert row["error"] is not None and row["result"] is None
            assert row["error"]["complete"] is True
            continue
        assert row["error"] is None and row["result"] is not None
        _managed_value(row["result"])
        if "completed_result" in contract:
            _same(row["result"], contract["completed_result"])
        if "completed_result_type" in contract:
            assert row["result"]["kind"] == contract["completed_result_type"]
        if "completed_result_value" in contract:
            _same(row["result"]["value"], contract["completed_result_value"])
        if "success_required_value" in contract:
            assert row["result"]["value"] is contract["success_required_value"]
        if operation in {"Stream.ReadAsync", "Stream.WriteAsync", "Stream.FlushAsync"}:
            ref = row["result"]["value"]
            assert ref["kind"] == "task" and ref["id"] not in tasks
            tasks[ref["id"]] = {"operation": operation, "arguments": arguments, "settled": False}
        if operation == "Task.GetResult":
            task = tasks[receiver["id"]]
            assert task["settled"] is False
            task["settled"] = True
            if task["operation"] == "Stream.ReadAsync":
                assert row["result"]["kind"] == "i32"
                allocation = task["arguments"]["values"][0]["value"]
                count = row["result"]["value"]
                assert 0 <= count <= allocation["capacity_bytes"]
                artifact = row["buffer_artifact"]
                assert artifact is not None
                assert artifact["allocation_id"] == allocation["id"]
                assert artifact["byte_length"] == allocation["capacity_bytes"]
                assert artifact["valid_prefix_bytes"] == count
            else:
                assert row["result"] == {"kind": "void", "value": None}
                assert row["buffer_artifact"] is None
    assert attempt["root"]["terminal"]["all_pending_tasks_completed"] is True
    assert all(task["settled"] for task in tasks.values())


def _cim(value, role, pid, declarations):
    assert value["role"] == role and value["state"] == "complete"
    assert value["error"] is None and value["excess_observed"] is False
    assert value["started_monotonic_ns"] <= value["ended_monotonic_ns"]
    expected = declarations["expected_template_registry"]["fixed_values"]["cim_query_template"]
    expected = expected.replace("$intakeObservedPid", str(pid))
    assert value["query_sha256"] == _sha(value["query_text"].encode("ascii"))
    # Query text is the full registered template; the decimal PID is fixed by
    # the independently retained Process object, not parsed from returned CIM.
    assert value["query_text"] == expected
    assert len(value["selected_instances"]) == 1
    selected = value["selected_instances"][0]
    assert selected["process_id"] == pid
    assert len(_hex(selected["executable_path_utf16le_hex"])) // 2 <= 512
    assert len(_hex(selected["command_line_utf16le_hex"])) // 2 <= (32768 if role == "observer" else 24576)
    _date(selected["creation"], 10)
    return selected


def test_root_protocol_query_count_and_complete_identity_joins(attempt):
    root, host, case = attempt["root"], attempt["host"], attempt["case_id"]
    observer, creation = root["observer"], root["host_creation"]
    assert observer is not None and all(observer[key] is not None for key in observer)
    assert creation is not None and creation["prepared"] is True
    assert creation["start_attempted"] is creation["start_return"] is True
    if case not in NO_HANDOFF:
        assert creation["process_id"] is not None and creation["process_handle_u64"] is not None
    _date(observer["start_time"], 1)
    observer_cim = _cim(observer["cim"], "observer", observer["pid"], attempt["declarations"])
    assert observer_cim["executable_path_utf16le_hex"] == observer["image_utf16le_hex"]
    assert observer_cim["command_line_utf16le_hex"] == observer["command_utf16le_hex"]
    assert observer_cim["creation"]["filetime_u64"] // 10 == observer["start_time"]["filetime_u64"] // 10
    if case in NO_HANDOFF:
        assert len(root["queries"]) == 1 and root["queries"][0] == observer["cim"]
        assert root["request"] is root["ack"] is None
        return
    assert [row["role"] for row in root["queries"]] == ["observer", "host", "worker"]
    assert root["queries"][0] == observer["cim"]
    host_cim = _cim(root["queries"][1], "host", creation["process_id"], attempt["declarations"])
    worker_pid = host["creation"]["child_pid"]
    worker_cim = _cim(root["queries"][2], "worker", worker_pid, attempt["declarations"])
    assert host_cim["parent_process_id"] == observer["pid"]
    assert worker_cim["parent_process_id"] == creation["process_id"]
    _date(creation["start_time"], 1)
    assert host_cim["creation"]["filetime_u64"] // 10 == creation["start_time"]["filetime_u64"] // 10
    assert host_cim["executable_path_utf16le_hex"] == creation["main_module_path_utf16le_hex"]
    assert worker_cim["creation"]["filetime_u64"] // 10 == host["creation"]["child_creation_filetime_u64"] // 10
    assert worker_cim["executable_path_utf16le_hex"] == host["creation"]["observed_image_utf16le_hex"]
    request, ack = root["request"], root["ack"]
    assert request is not None and ack is not None
    _own_hash(request, "request_sha256")
    _own_hash(ack, "ack_sha256")
    assert request["registration_sha256"] == ack["registration_sha256"] == R_CANONICAL_SHA
    assert request["case_id"] == ack["case_id"] == case
    assert request["nonce_hex"] == ack["nonce_hex"] == attempt["control"]["nonce_hex"]
    assert request["packet_sha256"] == _sha(attempt["submitted"])
    assert request["job_process_ids"] == [worker_pid]
    assert request["host"]["pid"] == creation["process_id"]
    assert request["worker"]["pid"] == worker_pid
    assert request["worker"]["creation_filetime_u64"] == host["creation"]["child_creation_filetime_u64"]
    assert ack["request_sha256"] == request["request_sha256"]
    _same(ack["observations"], root["queries"])
    assert ack["decision"] == "allow" and ack["failure_code"] is None
    assert host["creation"]["cim_observations"] == root["queries"]
    assert host["creation"]["identity_transport"]["request"] == request
    assert host["creation"]["identity_transport"]["ack"] == ack


def test_root_terminal_real_exit_cleanup_and_pending_completion(attempt):
    terminal = attempt["root"]["terminal"]
    assert terminal["host_signalled"] is True
    assert terminal["host_exit_code_i32"] == 0
    assert terminal["all_pending_tasks_completed"] is True
    assert terminal["process_disposed"] is True and terminal["cleanup_complete"] is True
    wait_observed = any(row["returned_bool"] is True for row in terminal["host_wait_calls"])
    retained_getter_observed = any(row["operation"] == "Process.HasExited"
        and row["state"] == "completed" and row["result"] == {"kind": "bool", "value": True}
        for row in attempt["root"]["managed_calls"])
    assert wait_observed or retained_getter_observed
    for ordinal, row in enumerate(terminal["host_wait_calls"]):
        assert row["ordinal"] == ordinal and 0 <= row["requested_ms"] <= 20
        assert row["started_monotonic_ns"] <= row["ended_monotonic_ns"]
        assert row["error"] is None
    assert len(terminal["poll_observations"]) <= 65536
    for ordinal, row in enumerate(terminal["poll_observations"]):
        assert row["ordinal"] == ordinal
    assert len(terminal["stream_closes"]) == 3
    assert len({row["role"] for row in terminal["stream_closes"]}) == 3
    for row in terminal["stream_closes"]:
        assert row["attempted"] is row["completed"] is True and row["error"] is None


def _utc_ns(value):
    assert type(value) is str
    match = re.fullmatch(r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,9}))?Z", value)
    assert match, ("strict complete UTC", value)
    stamp = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    seconds = (stamp - datetime(1970, 1, 1, tzinfo=timezone.utc)).days * 86400
    seconds += stamp.hour * 3600 + stamp.minute * 60 + stamp.second
    return seconds * 1000000000 + int((match[2] or "").ljust(9, "0"))


def test_external_entry_owned_capture_tool_result_and_complete_actor_joins(attempt):
    owned, tool, root = attempt["owned"], attempt["tool"], attempt["root"]
    _keys(owned, ("version", "case_id", "expectations", "launch_seal", "wrapper", "observer_entry",
                  "observer_initial", "observer_terminal", "host", "worker", "root_receipt",
                  "physical_outputs", "authority_flags"))
    _keys(tool, ("version", "case_id", "wrapper", "started_utc", "ended_utc", "tool_exit_code",
                 "observer_returned", "owned_capture", "root_receipt", "physical_outputs", "authority_flags"))
    assert owned["version"] == "local-member-intake-bootstrap-owned-capture-v1"
    assert tool["version"] == "local-member-intake-bootstrap-tool-receipt-v1"
    for value in (owned, tool):
        assert value["case_id"] == attempt["case_id"]
        _same(value["authority_flags"], attempt["declarations"]["authority_flags"])
        _same(value["root_receipt"], attempt["cohort_case"]["root_receipt"])
        _same(value["physical_outputs"], attempt["cohort_case"]["physical_outputs"])
    _same(owned["expectations"], attempt["cohort"]["index"]["expectations"])
    _same(owned["launch_seal"], attempt["cohort"]["index"]["launch_seal"])
    _same(tool["owned_capture"], attempt["cohort_case"]["owned_capture"])
    _same(tool["wrapper"], owned["wrapper"])
    _raw_ref(owned["wrapper"], 262144)
    entry_raw, entry = _artifact_ref(owned["observer_entry"], 1048576)
    assert entry_raw == _read(Path(attempt["row"]["outputs"]["directory"]) / "observer_entry.json", 1048576)
    _keys(entry, ("version", "case_id", "expectations", "launch_seal", "wrapper", "observer", "authority_flags"))
    assert entry["version"] == "local-member-intake-bootstrap-observer-entry-v1"
    assert entry["case_id"] == attempt["case_id"]
    for key in ("expectations", "launch_seal", "wrapper", "authority_flags"):
        _same(entry[key], owned[key])
    attempt["types"].named(entry["observer"], "RootObserver")
    _same(entry["observer"], owned["observer_initial"])
    terminal_observer = owned["observer_terminal"]
    _keys(terminal_observer, ("observer", "observed_utc", "root_terminal"))
    attempt["types"].named(terminal_observer["observer"], "RootObserver")
    _same(terminal_observer["root_terminal"], root["terminal"])
    for observer in (entry["observer"], terminal_observer["observer"]):
        assert observer["pid"] == root["observer"]["pid"]
        assert observer["image_utf16le_hex"] == root["observer"]["image_utf16le_hex"]
        assert observer["command_utf16le_hex"] == root["observer"]["command_utf16le_hex"]
        assert observer["start_time"]["filetime_u64"] == root["observer"]["start_time"]["filetime_u64"]
    _same(terminal_observer["observer"]["cim"], root["observer"]["cim"])
    initial_cim = entry["observer"]["cim"]
    assert initial_cim["ended_monotonic_ns"] <= root["observer"]["cim"]["started_monotonic_ns"]
    _same(initial_cim["selected_instances"], root["observer"]["cim"]["selected_instances"])
    actor_host = owned["host"]
    assert actor_host is not None
    _keys(actor_host, ("creation", "cim", "terminal"))
    _same(actor_host["creation"], root["host_creation"])
    _same(actor_host["terminal"], root["terminal"])
    if attempt["case_id"] in NO_HANDOFF:
        assert actor_host["cim"] is None
    else:
        _same(actor_host["cim"], root["queries"][1])
    actor_worker = owned["worker"]
    if attempt["case_id"] in PURE or attempt["case_id"] == "creation_refusal":
        assert actor_worker is None
    else:
        assert actor_worker is not None
        _keys(actor_worker, ("request", "ack", "creation", "terminal"))
        _same(actor_worker["creation"], attempt["host"]["creation"])
        _same(actor_worker["terminal"], attempt["host"]["terminal"])
        _same(actor_worker["request"], root["request"])
        _same(actor_worker["ack"], root["ack"])
    assert type(tool["tool_exit_code"]) is int and tool["tool_exit_code"] == 0
    assert tool["observer_returned"] is True
    start, ended = _utc_ns(tool["started_utc"]), _utc_ns(tool["ended_utc"])
    assert _utc_ns("2026-10-15T06:59:08Z") <= start <= ended <= _utc_ns(HARD_END)
    assert start <= _utc_ns(terminal_observer["observed_utc"]) <= ended


def _frame(raw, magic, max_body):
    assert len(raw) >= 8 and raw[:4] == magic
    count = int.from_bytes(raw[4:8], "little")
    assert 0 < count <= max_body and len(raw) == count + 8
    value = _json(raw[8:])
    assert raw[8:] == _canonical(value)
    return value


def test_complete_root_physical_frames_ranges_and_no_second_receipt_copy(attempt):
    root = attempt["root"]
    stdout = attempt["physical_stdout"]
    stderr = _read(attempt["row"]["outputs"]["host_stderr"], 1048577)
    prepared = _read(attempt["row"]["outputs"]["root_stdin_prepared"], 524296)
    assert stderr == b""
    expected_roles = ["terminal"] if attempt["case_id"] in NO_HANDOFF else ["request", "ack", "terminal"]
    frames = root["terminal"]["frame_index"]
    assert [row["role"] for row in frames] == expected_roles
    assert [row["ordinal"] for row in frames] == list(range(len(frames)))
    stdout_offset = 0
    for row in frames:
        assert row["complete"] is True
        assert row["frame_bytes"] == 8 + row["body_bytes"]
        if row["role"] == "ack":
            assert row["artifact_path"] == "root_stdin_prepared.bin"
            assert attempt["row"]["outputs"]["root_stdin_prepared"] == (
                attempt["row"]["outputs"]["directory"] + "/root_stdin_prepared.bin")
            assert row["byte_offset"] == 0
            raw = prepared
            magic, maximum, expected = b"LMA1", 524288, root["ack"]
        else:
            assert row["artifact_path"] == "host_stdout.bin"
            assert attempt["row"]["outputs"]["host_stdout"] == (
                attempt["row"]["outputs"]["directory"] + "/host_stdout.bin")
            assert row["byte_offset"] == stdout_offset
            raw = stdout[stdout_offset:stdout_offset + row["frame_bytes"]]
            stdout_offset += row["frame_bytes"]
            if row["role"] == "request":
                magic, maximum, expected = b"LMR1", 262144, root["request"]
            else:
                magic, maximum, expected = b"LMF1", 67108864, attempt["host"]
                assert root["host_receipt"]["byte_offset"] == row["byte_offset"] + 8
                assert root["host_receipt"]["byte_length"] == row["body_bytes"]
        assert len(raw) == row["frame_bytes"] and _sha(raw) == row["frame_sha256"]
        assert _sha(raw[8:]) == row["body_sha256"]
        _same(_frame(raw, magic, maximum), expected)
    assert stdout_offset == len(stdout)
    if attempt["case_id"] in NO_HANDOFF:
        assert prepared == b""


def test_full_runtime_manifest_and_exact33_external_runtime_pins(attempt):
    _, runtime = _artifact_ref(attempt["worker_context"]["runtime_manifest"], 1048576)
    _, source = _artifact_ref(attempt["worker_context"]["source_manifest"], 1048576)
    expected_runtime = attempt["registered"]["runtime_contract"]
    host_candidates, worker_candidates = expected_runtime["role_module_allowlists"]
    assert host_candidates["role"] == "host_runtime" and worker_candidates["role"] == "worker_runtime"
    _same(host_candidates["files"], worker_candidates["files"])
    assert len(host_candidates["files"]) == 25
    expected_modules = [{"role": "host_runtime",
                         "absolute_path_utf16le_hex": row["absolute_path"].encode("utf-16-le").hex(),
                         "byte_length": row["byte_length"], "sha256": row["sha256"]}
                        for row in host_candidates["files"]]
    _same(runtime["static_modules"], expected_modules)
    _same(runtime["host_required_paths"], host_candidates["required_paths"])
    _same(runtime["worker_required_paths"], worker_candidates["required_paths"])
    _same(runtime["interpreter"], expected_runtime["interpreter_static_candidate"])
    _same(runtime["exports"], expected_runtime["export_registrations"])
    assert len(runtime["exports"]) == 66
    expected_pins = [dict(runtime["interpreter"])]
    for index in (0, 1):
        row = source["sources"][index]
        expected_pins.append({"role": row["role"], "path": row["path"],
                              "byte_length": row["raw_byte_length"], "sha256": row["raw_sha256"]})
    for role, field in (("protocol", "protocol"), ("oracle", "declarations")):
        row = attempt["cohort"]["expectations"][field]
        expected_pins.append({"role": role, "path": row["path"],
                              "byte_length": row["raw_byte_length"], "sha256": row["raw_sha256"]})
    for row in source["sources"][2:]:
        expected_pins.append({"role": "registered_dependency", "path": row["path"],
                              "byte_length": row["raw_byte_length"], "sha256": row["raw_sha256"]})
    special_roles = {"C:\\Windows\\System32\\kernel32.dll": "kernel32",
                     "C:\\Windows\\System32\\KernelBase.dll": "kernelbase",
                     "C:\\Windows\\System32\\ntdll.dll": "ntdll"}
    for row in host_candidates["files"]:
        if row["absolute_path"] == runtime["interpreter"]["path"]:
            continue
        expected_pins.append({"role": special_roles.get(row["absolute_path"], "registered_dependency"),
                              "path": row["absolute_path"], "byte_length": row["byte_length"],
                              "sha256": row["sha256"]})
    assert len(expected_pins) == 33
    assert len({row["path"] for row in expected_pins}) == 33
    _same(attempt["host"]["runtime_pins"], expected_pins)


def test_complete_fault_carrier_exactfive_controls_actual_vs_injected(attempt):
    host, case = attempt["host"], attempt["case_id"]
    assert host["version"] == "local-member-intake-bootstrap-attempt-v3"
    fault = host["fault_observation"]
    templates = attempt["declarations"]["expected_template_registry"]["fault_templates"]
    if case not in templates:
        assert fault is None
        return
    assert fault is not None
    attempt["types"].named(fault, "FaultObservation")
    _own_hash(fault, "fault_sha256")
    assert fault["case_id"] == case and fault["registration_sha256"] == R_CANONICAL_SHA
    assert fault["packet_sha256"] == _sha(attempt["submitted"])
    template = templates[case]
    for key in ("version", "case_id", "site", "trigger_stage", "original_call_count", "restoration_complete"):
        _same(fault[key], template[key], key)
    supplied = fault["supplied_observation"]
    if case == "suspended_identity_refusal":
        expected = _recipe_bytes(attempt["declarations"]["raw_byte_recipes"]["invalid_image_utf16le"])
        assert supplied == {"kind": "expected_image_override", "expected_image_utf16le_hex": expected.hex()}
    else:
        _same(supplied, template["supplied_observation"])
    if case == "close_refusal":
        ordinal = fault["actual_api_ordinal"]
        row = host["api_trace"][ordinal]
        assert row["api"] == "CloseHandle" and row["return"]["raw_i64"] != 0
        assert row["return"]["win32_error_u32"] is None
        _same(fault["actual_return"], row["return"])
        closes = [close for close in host["terminal"]["parent_closes"] if close["role"] == "stdout_read"]
        assert len(closes) == 1 and closes[0]["close_api_ordinal"] == ordinal
        assert closes[0]["disposition"] == "closed"
        assert _args(row)["hObject"] == closes[0]["handle_u64"]
        assert supplied == {"kind": "close_observation_override", "close_bool_i32": 0,
                            "win32_error_u32": 1234}
    else:
        assert fault["actual_api_ordinal"] is fault["actual_return"] is None
    if case == "creation_refusal":
        assert not any(row["api"] == "CreateProcessW" for row in host["api_trace"])
        assert host["creation"]["attempted"] is False
    if case in {"creation_refusal", "resume_refusal"}:
        assert fault["original_call_count"] == 0
    if case == "resume_refusal":
        assert host["creation"]["identity_transport"]["ack"]["decision"] == "allow"
        assert not any(row["api"] == "ResumeThread" for row in host["api_trace"])


def _worker_trace(attempt):
    result = attempt["host"]["result"]
    if result is not None:
        assert result["version"] == "local-member-intake-bootstrap-result-v3"
        trace = result["worker_pre_emission_api_trace"]
        assert 1 <= len(trace) <= 4096
        _api_trace(trace, attempt["declarations"])
        return trace
    if attempt["case_id"] == "blocked_owned_pipe_read":
        marker = _json(_semantic(attempt))
        attempt["types"].named(marker, "PendingReadMarker")
        trace = marker["completed_api_trace"]
        _api_trace(trace, attempt["declarations"])
        return trace
    return None


def test_entire_worker_pre_emission_trace_go_ordinals_and_memory_native_bodies(attempt):
    trace = _worker_trace(attempt)
    if trace is None:
        return
    if attempt["host"]["result"] is not None:
        bundle = _json(_hex(attempt["host"]["result"]["payload_hex"]))
        go = bundle["go_observation"]
    else:
        go = _json(_semantic(attempt))["go_observation"]
    for read in [*go["data_reads"], go["eof_probe"]]:
        row = trace[read["api_ordinal"]]
        assert row["api"] == "ReadFile"
        assert _args(row)["nNumberOfBytesToRead"] == read["requested_count_u32"]
        _same(row["return"], read["return"])
        _same(row["output_buffers"], read["buffer_observations"])
    close = go["stdin_close"]
    closes = [row for row in trace if row["api"] == "CloseHandle"
              and _args(row)["hObject"] == close["handle_u64"]]
    assert len(closes) == 1
    assert closes[0]["return"]["raw_i64"] == close["close_bool_i32"]
    assert closes[0]["return"]["win32_error_u32"] == close["win32_error_u32"]
    _, runtime = _artifact_ref(attempt["worker_context"]["runtime_manifest"], 1048576)
    _initialization(go["initialization"], go["binding_initialization"], "worker", runtime)
    allocation_rows = [row for row in trace if row["api"] == "VirtualAlloc"]
    release_rows = [row for row in trace if row["api"] == "VirtualFree"]
    if attempt["case_id"] in {"memory_positive_control", "memory_limit"}:
        assert len(allocation_rows) == 1
        allocation = allocation_rows[0]
        args = _args(allocation)
        assert args["lpAddress"]["address_u64"] == 0
        assert args["dwSize"] == 268435456 and args["flAllocationType"] == 12288 and args["flProtect"] == 4
        payload = _json(_hex(bundle["control_payload_hex"]))
        assert allocation["return"]["raw_u64"] == payload["return_address_u64"]
        assert allocation["return"]["win32_error_u32"] == payload["win32_error_u32"]
        if attempt["case_id"] == "memory_positive_control":
            assert len(release_rows) == 1
            release = release_rows[0]
            assert _args(release)["lpAddress"]["address_u64"] == payload["return_address_u64"]
            assert _args(release)["dwSize"] == 0 and _args(release)["dwFreeType"] == 32768
            assert release["return"]["raw_i64"] == payload["release"]["return_bool_i32"]
            assert release["ordinal"] > allocation["ordinal"]
        else:
            assert not release_rows and allocation["return"]["raw_u64"] == 0
    else:
        assert allocation_rows == release_rows == []


def _exports(trace, initialization, bindings, runtime, role):
    registrations = [row for row in runtime["exports"] if row["role"] == role]
    actual = [row for row in trace if row["api"] == "GetProcAddress"]
    assert len(actual) == len(registrations) == len(bindings) == 33
    allowed_static = {_hex(row["absolute_path_utf16le_hex"]).decode("utf-16-le"):
                      (row["byte_length"], row["sha256"]) for row in runtime["static_modules"]}
    used_owners, used_names = set(), set()
    for call, binding, registered in zip(actual, bindings, registrations, strict=True):
        assert binding["api_name"] == registered["export_name"]
        args = _args(call)
        constructor = initialization[binding["constructor_ordinal"]]
        assert args["hModule"] == constructor["exposed_handle_u64"]
        assert _hex(args["lpProcName"]["storage_before_hex"]) == registered["export_name"].encode("ascii") + b"\0"
        assert call["return"]["raw_u64"] == binding["exposed_address_u64"] > 0
        owners = [row for row in trace if row["api"] == "GetModuleHandleExW"
                  and row["ordinal"] > call["ordinal"] and row["ordinal"] not in used_owners
                  and _args(row)["lpModuleName"]["address_u64"] == call["return"]["raw_u64"]]
        assert owners, (role, registered["export_name"], "missing unused exact address-owner call")
        owner = owners[0]
        used_owners.add(owner["ordinal"])
        owner_args = _args(owner)
        assert owner_args["dwFlags"] == 6
        assert owner_args["lpModuleName"]["address_u64"] == call["return"]["raw_u64"]
        assert owner_args["lpModuleName"]["pointee_kind"] == "external_function_address"
        assert owner["return"]["raw_i64"] != 0
        module = _u64(_output_bytes(owner, "phModule", 8))
        assert module > 0
        names = [row for row in trace if row["api"] == "GetModuleFileNameW"
                 and row["ordinal"] > owner["ordinal"] and row["ordinal"] not in used_names
                 and _args(row)["hModule"] == module]
        assert names, (role, registered["export_name"], "missing unused exact owner-path call")
        name = names[0]
        used_names.add(name["ordinal"])
        count = name["return"]["raw_u64"]
        assert 1 <= count <= 511
        full = _output_bytes(name, "lpFilename", 1024)
        assert full[count * 2:count * 2 + 2] == b"\0\0"
        path = full[:count * 2].decode("utf-16-le", errors="strict")
        assert path in registered["allowed_owner_paths"] and path in allowed_static
    loads = [row for row in trace if row["api"] == "LoadLibraryExW"]
    frees = [row for row in trace if row["api"] == "FreeLibrary"]
    # The selected WinDLL reference lives until process exit.  Hidden loader
    # calls are not exposed ApiTrace rows; only actually retained direct calls
    # below are validated, without inventing a second load/free pair.
    acquired = []
    for row in loads:
        address = row["return"]["raw_u64"]
        assert address > 0 and row["return"]["win32_error_u32"] is None
        path = _hex(_args(row)["lpLibFileName"]["storage_before_hex"])
        assert path.endswith(b"\0\0")
        assert path[:-2].decode("utf-16-le", errors="strict") in allowed_static
        acquired.append((address, row["ordinal"]))
    for row in frees:
        matching = [item for item in acquired if item[0] == _args(row)["hLibModule"]
                    and item[1] < row["ordinal"]]
        assert matching, "Direct FreeLibrary must consume an actual prior direct load reference"
        acquired.remove(matching[0])
        assert row["return"]["raw_i64"] != 0 and row["return"]["win32_error_u32"] is None
        assert row["ordinal"] > max(call["ordinal"] for call in actual)


def test_every_host_and_retained_worker_export_owner_full_path_and_load_reference(attempt):
    if attempt["case_id"] in PURE:
        return
    _, runtime = _artifact_ref(attempt["worker_context"]["runtime_manifest"], 1048576)
    _exports(attempt["host"]["api_trace"], attempt["host"]["creation"]["initialization"],
             attempt["host"]["creation"]["binding_initialization"],
             runtime, "host")
    worker = _worker_trace(attempt)
    if worker is not None:
        if attempt["host"]["result"] is not None:
            go = _json(_hex(attempt["host"]["result"]["payload_hex"]))["go_observation"]
        else:
            go = _json(_semantic(attempt))["go_observation"]
        _exports(worker, go["initialization"], go["binding_initialization"], runtime, "worker")


def _read_data(row):
    assert row["api"] == "ReadFile"
    if row["return"]["raw_i64"] == 0:
        assert row["return"]["win32_error_u32"] == 109
        return None
    count = _u32(_output_bytes(row, "lpNumberOfBytesRead", 4))
    requested = _args(row)["nNumberOfBytesToRead"]
    assert 0 <= count <= requested
    return _output_bytes(row, "lpBuffer", requested)[:count]


def test_worker_stream_partition_links_exact_host_ReadFile_bodies_and_EOF(attempt):
    host = attempt["host"]
    for stream_name in ("stdout", "stderr"):
        stream = host[stream_name]
        if stream is None:
            continue
        actual, ended = bytearray(), False
        ordinals = stream["read_api_ordinals"]
        owners = [row for row in host["terminal"]["parent_closes"] if row["role"] == stream_name + "_read"]
        assert len(owners) == 1
        assert len(set(ordinals)) == len(ordinals) and ordinals == sorted(ordinals)
        for ordinal in ordinals:
            row = host["api_trace"][ordinal]
            assert _args(row)["hFile"] == owners[0]["handle_u64"]
            part = _read_data(row)
            if part is None:
                assert ordinal == ordinals[-1] and not ended
                ended = True
            else:
                assert not ended
                actual.extend(part)
        assert bytes(actual) == _hex(stream["retained_hex"])
        if not ended:
            last_read = ordinals[-1] if ordinals else -1
            close_ordinal = owners[0]["close_api_ordinal"]
            peeks = [row for row in host["api_trace"] if row["api"] == "PeekNamedPipe"
                     and last_read < row["ordinal"] < close_ordinal
                     and _args(row)["hNamedPipe"] == owners[0]["handle_u64"]
                     and row["return"]["raw_i64"] == 0
                     and row["return"]["win32_error_u32"] == 109]
            ended = bool(peeks)
        assert ended is stream["eof_observed"]
        if stream["complete"]:
            assert ended
        if stream["excess_sentinel_observed"]:
            assert not ended and stream["complete"] is False
    if attempt["case_id"] not in NO_READY:
        transport = host["creation"]["identity_transport"]
        assert transport["ready_hex"] == READY.hex()
        ready_reads = [host["api_trace"][index] for index in transport["ready_read_api_ordinals"]]
        ready_bytes = b"".join(part for row in ready_reads if (part := _read_data(row)) is not None)
        assert ready_bytes == READY
        go = _hex(transport["go_hex"])
        assert len(go) == 48
        writes = [host["api_trace"][index] for index in transport["go_write_api_ordinals"]]
        assert len(writes) == 1 and writes[0]["api"] == "WriteFile"
        assert _hex(_args(writes[0])["lpBuffer"]["storage_before_hex"]) == go
        assert _u32(_output_bytes(writes[0], "lpNumberOfBytesWritten", 4)) == 48


def test_pending_owned_read_full_marker_prepared_lower_bound_and_real_timeout(attempt):
    if attempt["case_id"] != "blocked_owned_pipe_read":
        return
    host = attempt["host"]
    raw = _semantic(attempt)
    assert len(raw) <= 262144
    marker = _json(raw)
    assert raw == _canonical(marker)
    attempt["types"].named(marker, "PendingReadMarker")
    _own_hash(marker, "marker_sha256")
    assert marker["case_id"] == "blocked_owned_pipe_read"
    assert marker["packet_sha256"] == _sha(attempt["submitted"])
    assert marker["nonce_hex"] == attempt["control"]["nonce_hex"]
    assert marker["worker_pid"] == host["creation"]["child_pid"]
    assert marker["observed_parent_pid"] == host["creation"]["observed_parent_pid"]
    _same(marker["authority_flags"], attempt["declarations"]["authority_flags"])
    _go(marker["go_observation"], host)
    owned = marker["owned_handles"]
    assert len(owned) == 2 and len({row["role"] for row in owned}) == 2
    assert len({row["handle_u64"] for row in owned}) == 2
    assert all(row["handle_u64"] > 0 for row in owned)
    pending = marker["pending_call"]
    assert pending["api"] == "ReadFile"
    arguments = {row["name"]: row["value"] for row in pending["arguments"]}
    assert arguments["nNumberOfBytesToRead"] == 1
    assert arguments["lpBuffer"]["storage_before_hex"] == "00"
    assert arguments["lpNumberOfBytesRead"]["storage_before_hex"] == "00" * 4
    assert arguments["lpOverlapped"]["address_u64"] == 0
    assert arguments["hFile"] in {row["handle_u64"] for row in owned}
    eof_row = marker["completed_api_trace"][marker["go_observation"]["eof_probe"]["api_ordinal"]]
    assert eof_row["ended_monotonic_ns"] <= pending["started_monotonic_ns"]
    private_pipes = [row for row in marker["completed_api_trace"] if row["api"] == "CreatePipe"]
    assert len(private_pipes) == 1
    private = private_pipes[0]
    assert private["return"]["raw_i64"] != 0
    acquired = {"control_pipe_read": _u64(_output_bytes(private, "hReadPipe", 8)),
                "control_pipe_write": _u64(_output_bytes(private, "hWritePipe", 8))}
    assert {row["role"]: row["handle_u64"] for row in owned} == acquired
    assert arguments["hFile"] == acquired["control_pipe_read"]
    assert not any(row["api"] == "ReadFile" and row["ordinal"] > private["ordinal"]
                   and _args(row)["hFile"] == arguments["hFile"]
                   for row in marker["completed_api_trace"])
    for buffer in pending["input_buffers"]:
        assert buffer["output_validity"] == "storage_only"
        _buffer(buffer)
    assert len(pending["input_buffers"]) == 2
    assert host["result"] is None and host["terminal"]["termination_requested"] is True


def test_full_root_artifact_inventory_buffers_provenance_and_exact_paths(attempt):
    root = attempt["root"]
    artifacts = root["artifacts"]
    assert 3 <= len(artifacts) <= 2051
    assert [row["ordinal"] for row in artifacts] == list(range(len(artifacts)))
    directory = attempt["row"]["outputs"]["directory"]
    physical = attempt["cohort_case"]["physical_outputs"]
    assert len(physical) == len(artifacts)
    assert len({row["artifact"]["path"] for row in physical}) == len(physical)
    assert len({row["relative_path"] for row in artifacts}) == len(artifacts)
    buffer_sum, stream_sum, prepared_sum = 0, 0, 0
    for ordinal, (artifact, external) in enumerate(zip(artifacts, physical, strict=True)):
        _keys(external, ("role", "artifact"))
        if ordinal < 3:
            filename = ("host_stdout.bin", "host_stderr.bin", "root_stdin_prepared.bin")[ordinal]
            role = ("host_stdout", "host_stderr", "root_stdin")[ordinal]
        else:
            filename = f"read_buffer_{ordinal - 3:04d}.bin"
            role = "read_buffer"
        assert artifact["relative_path"] == filename
        assert artifact["role"] == external["role"] == role
        assert external["artifact"]["path"] == directory + "/" + filename
        maximum = (67371024 if ordinal == 0 else 1048577 if ordinal == 1 else 524296
                   if ordinal == 2 else 65536)
        raw = _raw_ref(external["artifact"], maximum)
        assert artifact["byte_length"] == len(raw) and artifact["sha256"] == _sha(raw)
        assert artifact["complete"] is True
        if ordinal < 2:
            assert artifact["provenance"] == "observed_stream_bytes"
            assert artifact["transferred_byte_count"] == len(raw)
            stream_sum += len(raw)
        elif ordinal == 2:
            assert artifact["provenance"] == "prepared_write_input"
            assert artifact["transferred_byte_count"] is None
            prepared_sum += len(raw)
        else:
            assert artifact["provenance"] == "allocated_buffer_storage"
            assert artifact["transferred_byte_count"] is None
            buffer_sum += len(raw)
    assert buffer_sum <= 134217728 and stream_sum <= 71303168 and prepared_sum <= 1048576
    read_starts = [row for row in root["managed_calls"] if row["operation"] == "Stream.ReadAsync"]
    assert len(read_starts) <= 2048
    assert len(artifacts) == 3 + len(read_starts)
    for row in root["managed_calls"]:
        reference = row["buffer_artifact"]
        if reference is None:
            continue
        ordinal = reference["artifact_ordinal"]
        assert 3 <= ordinal < len(artifacts)
        artifact = artifacts[ordinal]
        assert reference["relative_path"] == artifact["relative_path"]
        assert reference["byte_length"] == artifact["byte_length"]
        assert reference["sha256"] == artifact["sha256"]
        count = reference["valid_prefix_bytes"]
        assert count is None or 0 <= count <= reference["byte_length"]
    for stream_id, role, expected in ((1, "host_stdout", attempt["physical_stdout"]),
                                      (2, "host_stderr", _read(attempt["row"]["outputs"]["host_stderr"], 1048577))):
        pieces = []
        starts = [row for row in read_starts if row["arguments"]["receiver"]["id"] == stream_id]
        ended = False
        for start in starts:
            task = start["result"]["value"]
            settled = [row for row in root["managed_calls"] if row["operation"] == "Task.GetResult"
                       and row["arguments"]["receiver"] == task]
            assert len(settled) == 1
            completion = settled[0]
            assert completion["state"] == "completed" and completion["result"]["kind"] == "i32"
            count = completion["result"]["value"]
            reference = completion["buffer_artifact"]
            assert reference is not None
            raw = _read(directory + "/" + reference["relative_path"], 65536)
            assert not ended
            pieces.append(raw[:count])
            if count == 0:
                ended = True
        assert ended, (role, "missing actual successful zero-byte async EOF")
        assert b"".join(pieces) == expected
    assert len(attempt["root_raw"]) + buffer_sum + stream_sum + prepared_sum <= 335544320


def test_full_enabled_limits_before_resume_final_accounting_and_owned_closes(attempt):
    host, case = attempt["host"], attempt["case_id"]
    if case in PURE:
        return
    traces = host["api_trace"]
    create_rows = [row for row in traces if row["api"] == "CreateProcessW"]
    if case == "creation_refusal":
        assert create_rows == []
    else:
        assert len(create_rows) == 1
        creation = create_rows[0]
        assert creation["return"]["raw_i64"] != 0
        native = _output_bytes(creation, "lpProcessInformation", 24)
        assert _u64(native) == host["creation"]["process_handle_u64"] > 0
        assert _u64(native, 8) == host["creation"]["thread_handle_u64"] > 0
        assert _u32(native, 16) == host["creation"]["child_pid"] > 0
        assert _u32(native, 20) == host["creation"]["child_tid"] > 0
        assert host["creation"]["creation_flags_u32"] == 134743044
        assert host["creation"]["job_attribute_u64"] == 131085
        assert host["creation"]["handle_attribute_u64"] == 131074
        before = [row for row in host["job_observations"] if row["phase"] == "before_create"]
        assert before and max(row["process_list_api_ordinal"] for row in before) < creation["ordinal"]
        resumes = [row for row in traces if row["api"] == "ResumeThread"]
        assert len(resumes) == (0 if case in NO_RESUME else 1)
        if resumes:
            suspended = [row for row in host["job_observations"] if row["phase"] == "suspended"]
            assert suspended
            assert max(row["process_list_api_ordinal"] for row in suspended) < resumes[0]["ordinal"]
            assert host["creation"]["resume_count_u32"] == 1
        if case in {"initialization_stall", "wall_stall", "blocked_owned_pipe_read"}:
            selected = next(row for row in host["lifecycle"] if row["event"] == "failure_selected")
            assert selected["monotonic_ns"] >= creation["started_monotonic_ns"] + 12000000000
    final = [row for row in host["job_observations"] if row["phase"] == "terminal"]
    assert final
    assert final[-1]["process_ids"] == [] and final[-1]["accounting"]["active_processes_u32"] == 0
    closes = host["terminal"]["parent_closes"]
    assert len(closes) <= 16
    assert [row["ordinal"] for row in closes] == list(range(len(closes)))
    closed = []
    for close in closes:
        assert close["close_attempted"] is True and close["disposition"] == "closed"
        row = traces[close["close_api_ordinal"]]
        assert row["api"] == "CloseHandle"
        assert _args(row)["hObject"] == close["handle_u64"]
        _same(close["close_return"], row["return"])
        assert row["return"]["raw_i64"] != 0 and row["return"]["win32_error_u32"] is None
        closed.append(close["handle_u64"])
    assert len(set(closed)) == len(closed)
    assert host["terminal"]["cleanup_complete"] is True
    assert not {"root_stdin", "root_stdout", "root_stderr"}.intersection(row["role"] for row in closes)


def _pointer_category(api, parameter):
    pure_inputs = {
        "CreateProcessW": {"lpApplicationName", "lpEnvironment", "lpCurrentDirectory", "lpStartupInfo"},
        "CreatePipe": {"lpPipeAttributes"}, "SetInformationJobObject": {"lpJobObjectInformation"},
        "UpdateProcThreadAttribute": {"lpValue"}, "WriteFile": {"lpBuffer"},
        "LoadLibraryExW": {"lpLibFileName"}, "GetProcAddress": {"lpProcName"},
    }
    return "H" if parameter in pure_inputs.get(api, set()) else "B"


def _api_occurrence_view(value, counters):
    view = {key: item for key, item in value.items()}
    arguments = []
    for argument in value["arguments"]:
        copy = dict(argument)
        if argument["kind"] == "pointer":
            pointer = dict(argument["value"])
            if pointer["storage_before_hex"] is not None:
                counters[_pointer_category(value["api"], argument["name"])] += len(_hex(pointer["storage_before_hex"]))
                pointer["storage_before_hex"] = ""
            copy["value"] = pointer
        arguments.append(copy)
    outputs = []
    for buffer in value["output_buffers"]:
        counters[_pointer_category(value["api"], buffer["parameter"])] += len(_hex(buffer["full_buffer_hex"]))
        outputs.append({**buffer, "full_buffer_hex": ""})
    view["arguments"], view["output_buffers"] = arguments, outputs
    return view


def _occurrences(value, counters, key=None):
    if type(value) is dict:
        if set(value) == {"ordinal", "phase", "api", "source_selector", "arguments", "return",
                          "saved_error_seed", "output_buffers", "started_monotonic_ns", "ended_monotonic_ns"}:
            return _api_occurrence_view(value, counters)
        if set(value) == {"retained_hex", "retained_byte_count", "retained_sha256",
                          "observed_byte_count_lower_bound", "complete", "eof_observed",
                          "excess_sentinel_observed", "read_api_ordinals"}:
            counters["D"] += len(_hex(value["retained_hex"]))
            return {field: "" if field == "retained_hex" else item for field, item in value.items()}
        output = {}
        for field, item in value.items():
            if field == "result" and type(item) is dict and "worker_pre_emission_api_trace" in item:
                counters["R"] += len(_canonical(item))
                output[field] = None
            else:
                output[field] = _occurrences(item, counters, field)
        return output
    if type(value) is list:
        return [_occurrences(item, counters, key) for item in value]
    if type(value) is str and value and key is not None and key.endswith("_hex"):
        raw = _hex(value)
        category = "B" if key in {"storage_before_hex", "full_buffer_hex", "raw_module_buffer_hex"} else "H"
        counters[category] += len(raw)
        return ""
    return value


def test_complete_occurrence_body_and_root_container_caps(attempt):
    host = attempt["host"]
    counters = {"D": 0, "B": 0, "H": 0, "R": 0}
    metadata = _occurrences(host, counters)
    amount_m = len(_canonical(metadata))
    assert counters["D"] <= 4194313
    assert counters["B"] <= 12582912 and counters["H"] <= 2097152
    assert counters["R"] <= 1048576 and amount_m <= 8388608
    assert 2 * counters["D"] + 2 * counters["B"] + 2 * counters["H"] + counters["R"] + amount_m <= 47185938
    assert len(attempt["host_raw"]) <= 67108864
    assert len(_canonical(host)) <= 67108864
    worker = _worker_trace(attempt)
    if worker is not None:
        worker_counters = {"D": 0, "B": 0, "H": 0, "R": 0}
        worker_metadata = _occurrences(worker, worker_counters)
        assert worker_counters["B"] <= 12582912 and worker_counters["H"] <= 2097152
        assert len(_canonical(worker_metadata)) <= 8388608
    assert len(attempt["root"]["managed_calls"]) <= 4352
    assert len(attempt["root"]["terminal"]["poll_observations"]) <= 65536
    assert len(attempt["root"]["artifacts"]) <= 2051
    full_artifacts = attempt["cohort_case"]["physical_outputs"]
    artifacts_raw = sum(row["artifact"]["raw_byte_length"] for row in full_artifacts)
    assert artifacts_raw + len(attempt["root_raw"]) <= 335544320
    assert len(_canonical(attempt["root"]["host_receipt"]["parsed_receipt"])) <= 67108864


def test_registered_memory_pair_order_and_both_complete_actual_attempts(cohort):
    cases = cohort["index"]["cases"]
    positive_index = next(index for index, row in enumerate(cases) if row["case_id"] == "memory_positive_control")
    negative_index = next(index for index, row in enumerate(cases) if row["case_id"] == "memory_limit")
    assert positive_index == 22 and negative_index == 23
    prior_end = None
    for index, memory, expected_outcome in ((positive_index, 536870912, "memory_positive_observed"),
                                             (negative_index, 268435456, "memory_control_observed")):
        _, root = _artifact_ref(cases[index]["root_receipt"], 335544320)
        _, tool = _artifact_ref(cases[index]["tool_receipt"], 8388608)
        body = root["host_receipt"]["parsed_receipt"]
        assert body["declared_policy"]["process_memory_bytes"] == memory
        assert body["terminal"]["outcome"] == expected_outcome
        assert body["terminal"]["acceptance"] == root["terminal"]["acceptance"] == "accepted_control"
        assert body["terminal"]["cleanup_complete"] is root["terminal"]["cleanup_complete"] is True
        assert tool["tool_exit_code"] == 0 and tool["observer_returned"] is True
        started, ended = _utc_ns(tool["started_utc"]), _utc_ns(tool["ended_utc"])
        if prior_end is not None:
            assert prior_end <= started
        prior_end = ended


def test_child_native_image_filetime_exit_and_attribute_projections(attempt):
    host, case = attempt["host"], attempt["case_id"]
    if case in PURE or case == "creation_refusal":
        return
    creation, trace = host["creation"], host["api_trace"]
    process = creation["process_handle_u64"]
    times = [row for row in trace if row["api"] == "GetProcessTimes" and _args(row)["hProcess"] == process]
    images = [row for row in trace if row["api"] == "QueryFullProcessImageNameW"
              and _args(row)["hProcess"] == process]
    assert times and images
    for row in times:
        assert row["return"]["raw_i64"] != 0
        for name in ("lpCreationTime", "lpExitTime", "lpKernelTime", "lpUserTime"):
            assert _args(row)[name]["storage_before_hex"] == "00" * 8
            _output_bytes(row, name, 8)
        assert _u64(_output_bytes(row, "lpCreationTime", 8)) == creation["child_creation_filetime_u64"]
        signalled_before = any(wait["api"] == "WaitForSingleObject"
            and wait["ordinal"] < row["ordinal"] and _args(wait)["hHandle"] == process
            and wait["return"]["raw_u64"] == 0 for wait in trace)
        exit_buffer = _outputs(row)["lpExitTime"]
        assert exit_buffer["output_validity"] == ("documented_valid" if signalled_before else "storage_only")
    final_times = times[-1]
    assert _u64(_output_bytes(final_times, "lpExitTime", 8)) == host["terminal"]["exit_filetime_u64"]
    assert _u64(_output_bytes(final_times, "lpKernelTime", 8)) == host["terminal"]["kernel_time_100ns_u64"]
    assert _u64(_output_bytes(final_times, "lpUserTime", 8)) == host["terminal"]["user_time_100ns_u64"]
    exits = [row for row in trace if row["api"] == "GetExitCodeProcess" and _args(row)["hProcess"] == process]
    assert exits and exits[-1]["return"]["raw_i64"] != 0
    assert _u32(_output_bytes(exits[-1], "lpExitCode", 4)) == host["terminal"]["exit_code_u32"]
    _, runtime = _artifact_ref(attempt["worker_context"]["runtime_manifest"], 1048576)
    expected_image = runtime["interpreter"]["path"].encode("utf-16-le")
    for row in images:
        args = _args(row)
        assert args["dwFlags"] == 0
        assert args["lpExeName"]["storage_before_hex"] == "00" * 1024
        assert _u32(_hex(args["lpdwSize"]["storage_before_hex"])) == 512
        count = _u32(_output_bytes(row, "lpdwSize", 4))
        assert row["return"]["raw_i64"] != 0 and 1 <= count <= 511
        full = _output_bytes(row, "lpExeName", 1024)
        assert full[2 * count:2 * count + 2] == b"\0\0"
        assert full[:2 * count] == expected_image
        assert creation["observed_image_utf16le_hex"] == expected_image.hex()
    job = [row for row in trace if row["api"] == "CreateJobObjectW"]
    assert len(job) == 1 and job[0]["return"]["raw_u64"] > 0
    attributes = [row for row in trace if row["api"] == "UpdateProcThreadAttribute"]
    assert [_args(row)["Attribute"] for row in attributes] == [131074, 131085]
    handles = _hex(_args(attributes[0])["lpValue"]["storage_before_hex"])
    assert [_u64(handles, offset) for offset in (0, 8, 16)] == creation["inherited_handles_u64"]
    assert _u64(_hex(_args(attributes[1])["lpValue"]["storage_before_hex"])) == job[0]["return"]["raw_u64"]


def test_all_acquired_parent_kernel_handles_closed_once_not_pid_only(attempt):
    host, case = attempt["host"], attempt["case_id"]
    if case in PURE:
        return
    acquired = []
    for row in host["api_trace"]:
        if row["api"] == "CreateJobObjectW":
            assert row["return"]["raw_u64"] > 0
            acquired.append(row["return"]["raw_u64"])
        elif row["api"] == "CreatePipe":
            assert row["return"]["raw_i64"] != 0
            acquired.extend((_u64(_output_bytes(row, "hReadPipe", 8)),
                             _u64(_output_bytes(row, "hWritePipe", 8))))
        elif row["api"] == "CreateProcessW":
            assert row["return"]["raw_i64"] != 0
            raw = _output_bytes(row, "lpProcessInformation", 24)
            acquired.extend((_u64(raw), _u64(raw, 8)))
    assert all(acquired) and len(set(acquired)) == len(acquired)
    actual = [row["handle_u64"] for row in host["terminal"]["parent_closes"]]
    assert sorted(actual) == sorted(acquired)
    calls = [row for row in host["api_trace"] if row["api"] == "CloseHandle"]
    assert len(calls) == len(acquired)
    assert sorted(_args(row)["hObject"] for row in calls) == sorted(acquired)
    for close in host["terminal"]["parent_closes"]:
        target = close["handle_u64"]
        acquisition = next(row for row in host["api_trace"] if row["api"] in
            {"CreateJobObjectW", "CreatePipe", "CreateProcessW"} and (
                row["api"] == "CreateJobObjectW" and row["return"]["raw_u64"] == target
                or row["api"] == "CreatePipe" and target in {
                    _u64(_output_bytes(row, "hReadPipe", 8)), _u64(_output_bytes(row, "hWritePipe", 8))}
                or row["api"] == "CreateProcessW" and target in {
                    _u64(_output_bytes(row, "lpProcessInformation", 24)),
                    _u64(_output_bytes(row, "lpProcessInformation", 24), 8)}))
        assert acquisition["ordinal"] < close["close_api_ordinal"]


def test_complete_worker_command_environment_and_no_terminator_relabel(attempt):
    host, case = attempt["host"], attempt["case_id"]
    if case in PURE:
        return
    if case == "creation_refusal":
        assert host["creation"]["command_utf16le_hex"] is None
        assert host["creation"]["environment_utf16le_hex"] is None
        assert not any(row["api"] == "CreateProcessW" for row in host["api_trace"])
        return
    process = attempt["registered"]["process_contract"]
    arguments = ["-B", "-I",
                 "C:/Users/pabta/Projects/ai-trader/scripts/local_member_intake_bootstrap_worker_20261015_1.py",
                 attempt["submitted"].hex(), _canonical(attempt["worker_context"]).hex()]
    command = '"' + process["direct_interpreter"] + '" ' + " ".join(arguments)
    command_raw = (command + "\0").encode("utf-16-le")
    environment_text = "\0".join(pair["name"] + "=" + pair["value"] for pair in process["environment"]) + "\0\0"
    environment_raw = environment_text.encode("utf-16-le")
    assert len(command_raw) // 2 <= 24576 and len(environment_raw) // 2 <= 8192
    assert host["creation"]["command_utf16le_hex"] == command_raw.hex()
    assert host["creation"]["environment_utf16le_hex"] == environment_raw.hex()
    actual_create = [row for row in host["api_trace"] if row["api"] == "CreateProcessW"]
    if actual_create:
        args = _args(actual_create[0])
        assert _hex(args["lpCommandLine"]["storage_before_hex"]) == command_raw
        assert _hex(args["lpEnvironment"]["storage_before_hex"]) == environment_raw
        assert _hex(args["lpApplicationName"]["storage_before_hex"]) == (process["direct_interpreter"] + "\0").encode("utf-16-le")
        assert _hex(args["lpCurrentDirectory"]["storage_before_hex"]) == (process["working_directory"] + "\0").encode("utf-16-le")
    if attempt["root"]["request"] is not None:
        assert attempt["root"]["request"]["worker"]["command_utf16le_hex"] == command.encode("utf-16-le").hex()
        assert attempt["root"]["queries"][2]["selected_instances"][0]["command_line_utf16le_hex"] == command.encode("utf-16-le").hex()


def test_host_parent_identity_provenance_is_root_CIM_ACK_not_guessed(attempt):
    parent, root = attempt["host"]["parent_identity"], attempt["root"]
    if attempt["case_id"] in NO_HANDOFF:
        if parent is not None:
            assert parent["observation_state"] == "incomplete"
            assert parent["observation_method"] == "root_cim_ack_v1"
        return
    assert parent is not None and parent["observation_state"] == "complete"
    assert parent["observation_method"] == "root_cim_ack_v1"
    own = root["queries"][1]["selected_instances"][0]
    observer = root["queries"][0]["selected_instances"][0]
    assert parent["pid"] == own["process_id"] == root["host_creation"]["process_id"]
    assert parent["creator_pid"] == own["parent_process_id"] == observer["process_id"]
    assert parent["creation_filetime_u64"] // 10 == own["creation"]["filetime_u64"] // 10
    assert parent["creator_creation_filetime_u64"] // 10 == observer["creation"]["filetime_u64"] // 10
    assert parent["image_utf16le_hex"] == own["executable_path_utf16le_hex"]
    assert parent["command_utf16le_hex"] == own["command_line_utf16le_hex"]
    assert parent["creation_filetime_u64"] >= parent["creator_creation_filetime_u64"]


def test_all_handle_flags_full_values_and_final_inheritance_before_create(attempt):
    host, case = attempt["host"], attempt["case_id"]
    if case in PURE:
        return
    rows = host["api_trace"]
    observations = [row for row in rows if row["api"] == "GetHandleInformation"]
    assert observations
    for row in observations:
        assert row["return"]["raw_i64"] != 0
        flags = _u32(_output_bytes(row, "lpdwFlags", 4))
        assert flags in {0, 1}, "No dropped unknown bits/protect-from-close bit"
    create = [row for row in rows if row["api"] == "CreateProcessW"]
    if create:
        inherited = host["creation"]["inherited_handles_u64"]
        assert len(inherited) == len(set(inherited)) == 3
        for handle in inherited:
            queried = [row for row in observations if row["ordinal"] < create[0]["ordinal"]
                       and _args(row)["hObject"] == handle]
            assert queried and _u32(_output_bytes(queried[-1], "lpdwFlags", 4)) == 1


def test_root_supervision_uses_selected_successful_Start_lower_bound(attempt):
    starts = [row for row in attempt["root"]["managed_calls"] if row["operation"] == "Process.Start"]
    assert len(starts) == 1 and starts[0]["state"] == "completed"
    assert starts[0]["result"] == {"kind": "bool", "value": True}
    deadline = attempt["root"]["terminal"]["work_deadline_monotonic_ns"]
    assert deadline is not None
    assert starts[0]["started_monotonic_ns"] < deadline <= starts[0]["started_monotonic_ns"] + 30000000000
    if attempt["root"]["request"] is not None:
        ack_deadline = attempt["root"]["terminal"]["ack_deadline_monotonic_ns"]
        assert ack_deadline is not None and ack_deadline <= deadline
        assert attempt["root"]["request"]["host"]["pid"] == attempt["root"]["host_creation"]["process_id"]


def test_registered_bootstrap_producer_interfaces_are_present():
    """Keep this identity when later independent actual-cohort readers are added."""
    registered_paths = (
        Path(
            "C:/Users/pabta/Projects/ai-trader/scripts/"
            "local_member_intake_bootstrap_host_20261015_1.py"
        ),
        Path(
            "C:/Users/pabta/Projects/ai-trader/scripts/"
            "local_member_intake_bootstrap_worker_20261015_1.py"
        ),
        Path(
            "C:/Users/pabta/Projects/ai-trader/scripts/"
            "local_member_intake_bootstrap_observer_20261015_1.ps1"
        ),
        Path(
            "C:/Users/pabta/Projects/ai-trader/scripts/"
            "local_member_intake_bootstrap_primitives_20261015_1.psm1"
        ),
    )
    missing = [str(path) for path in registered_paths if not path.is_file()]
    assert not missing, ("Missing registered bootstrap producer interfaces", missing)


def test_registered_bootstrap_materializer_interface_is_present():
    path = WORKSPACE / "scripts/local_member_intake_bootstrap_materialize_20261015_1.py"
    assert path.is_file(), ("Missing registered bootstrap materializer interface", str(path))
