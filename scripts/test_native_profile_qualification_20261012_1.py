"""Explicit native qualification tests; not ordinary tests/ discovery.

The initial test qualifies only fake-boundary wrapper behavior. It performs
no native import, constructor, parser, DLL inspection, child launch or artifact
inspection. Complete real native qualification will require root registration,
fresh mandatory deadline context and contained fixed child modes. No skip or
default future date can substitute for that evidence.
"""

import base64
import hashlib
import importlib.util
import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts/native_profile_probe_20261012_1.py"
PROBE_SPEC = importlib.util.spec_from_file_location(
    "native_profile_qualification_probe_20261012_1", PROBE_PATH
)
PROBE = importlib.util.module_from_spec(PROBE_SPEC)
sys.modules[PROBE_SPEC.name] = PROBE
PROBE_SPEC.loader.exec_module(PROBE)

CONTAINMENT_SPEC = importlib.util.spec_from_file_location(
    "native_profile_qualification_containment_20261012_1",
    ROOT / "scripts/native_profile_containment_20261012_1.py",
)
CONTAINMENT = importlib.util.module_from_spec(CONTAINMENT_SPEC)
sys.modules[CONTAINMENT_SPEC.name] = CONTAINMENT
CONTAINMENT_SPEC.loader.exec_module(CONTAINMENT)

EXPECTED_MANIFEST_SHA256 = "74b2044bba66e8c229669ac2dd2731ecd89205275a9d24ebaf54febbc9edd139"
# Deliberately fake named artifacts: no path is opened. These literal bodies
# test complete before/after retention rather than authenticating any file.
FAKE_ARTIFACTS = (
    {
        "logical_id": "fake_artifact_01",
        "path": "C:/native-proof-fake/artifact_01",
        "raw_bytes": 11,
        "raw_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    },
    {
        "logical_id": "fake_artifact_02",
        "path": "C:/native-proof-fake/artifact_02",
        "raw_bytes": 12,
        "raw_sha256": "2222222222222222222222222222222222222222222222222222222222222222",
    },
    {
        "logical_id": "fake_artifact_03",
        "path": "C:/native-proof-fake/artifact_03",
        "raw_bytes": 13,
        "raw_sha256": "3333333333333333333333333333333333333333333333333333333333333333",
    },
    {
        "logical_id": "fake_artifact_04",
        "path": "C:/native-proof-fake/artifact_04",
        "raw_bytes": 14,
        "raw_sha256": "4444444444444444444444444444444444444444444444444444444444444444",
    },
    {
        "logical_id": "fake_artifact_05",
        "path": "C:/native-proof-fake/artifact_05",
        "raw_bytes": 15,
        "raw_sha256": "5555555555555555555555555555555555555555555555555555555555555555",
    },
    {
        "logical_id": "fake_artifact_06",
        "path": "C:/native-proof-fake/artifact_06",
        "raw_bytes": 16,
        "raw_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
    },
    {
        "logical_id": "fake_artifact_07",
        "path": "C:/native-proof-fake/artifact_07",
        "raw_bytes": 17,
        "raw_sha256": "7777777777777777777777777777777777777777777777777777777777777777",
    },
    {
        "logical_id": "fake_artifact_08",
        "path": "C:/native-proof-fake/artifact_08",
        "raw_bytes": 18,
        "raw_sha256": "8888888888888888888888888888888888888888888888888888888888888888",
    },
    {
        "logical_id": "fake_artifact_09",
        "path": "C:/native-proof-fake/artifact_09",
        "raw_bytes": 19,
        "raw_sha256": "9999999999999999999999999999999999999999999999999999999999999999",
    },
    {
        "logical_id": "fake_artifact_10",
        "path": "C:/native-proof-fake/artifact_10",
        "raw_bytes": 20,
        "raw_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    },
    {
        "logical_id": "fake_artifact_11",
        "path": "C:/native-proof-fake/artifact_11",
        "raw_bytes": 21,
        "raw_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    },
    {
        "logical_id": "fake_artifact_12",
        "path": "C:/native-proof-fake/artifact_12",
        "raw_bytes": 22,
        "raw_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    },
    {
        "logical_id": "fake_artifact_13",
        "path": "C:/native-proof-fake/artifact_13",
        "raw_bytes": 23,
        "raw_sha256": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    },
)
FAKE_MODULE_ASSOCIATIONS = (
    {
        "logical_id": "python_executable",
        "module_name": "python",
        "module_file": "C:/native-proof-fake/python.exe",
        "spec_origin": "C:/native-proof-fake/python.exe",
        "mapped_path": "C:/native-proof-fake/python.exe",
        "module_handle": 101,
    },
    {
        "logical_id": "python_runtime_dll",
        "module_name": "python_runtime",
        "module_file": "C:/native-proof-fake/python312.dll",
        "spec_origin": "C:/native-proof-fake/python312.dll",
        "mapped_path": "C:/native-proof-fake/python312.dll",
        "module_handle": 102,
    },
    {
        "logical_id": "dbn_extension",
        "module_name": "databento_dbn._lib",
        "module_file": "C:/native-proof-fake/dbn.pyd",
        "spec_origin": "C:/native-proof-fake/dbn.pyd",
        "mapped_path": "C:/native-proof-fake/dbn.pyd",
        "module_handle": 103,
    },
    {
        "logical_id": "zstd_extension",
        "module_name": "zstandard.backend_c",
        "module_file": "C:/native-proof-fake/zstd.pyd",
        "spec_origin": "C:/native-proof-fake/zstd.pyd",
        "mapped_path": "C:/native-proof-fake/zstd.pyd",
        "module_handle": 104,
    },
    {
        "logical_id": "dbn_package",
        "module_name": "databento_dbn",
        "module_file": "C:/native-proof-fake/dbn_init.py",
        "spec_origin": "C:/native-proof-fake/dbn_init.py",
        "mapped_path": None,
        "module_handle": None,
    },
    {
        "logical_id": "dbn_metadata",
        "module_name": "databento_dbn.metadata",
        "module_file": "C:/native-proof-fake/dbn_metadata.py",
        "spec_origin": "C:/native-proof-fake/dbn_metadata.py",
        "mapped_path": None,
        "module_handle": None,
    },
    {
        "logical_id": "dbn_v3",
        "module_name": "databento_dbn.v3",
        "module_file": "C:/native-proof-fake/dbn_v3.py",
        "spec_origin": "C:/native-proof-fake/dbn_v3.py",
        "mapped_path": None,
        "module_handle": None,
    },
    {
        "logical_id": "zstd_package",
        "module_name": "zstandard",
        "module_file": "C:/native-proof-fake/zstd_init.py",
        "spec_origin": "C:/native-proof-fake/zstd_init.py",
        "mapped_path": None,
        "module_handle": None,
    },
    {
        "logical_id": "zstd_policy",
        "module_name": "zstandard.policy",
        "module_file": "C:/native-proof-fake/zstd_policy.py",
        "spec_origin": "C:/native-proof-fake/zstd_policy.py",
        "mapped_path": None,
        "module_handle": None,
    },
    {
        "logical_id": "proof_probe",
        "module_name": "native_profile_probe",
        "module_file": "C:/native-proof-fake/proof_probe.py",
        "spec_origin": "C:/native-proof-fake/proof_probe.py",
        "mapped_path": None,
        "module_handle": None,
    },
)


def test_identity_qualifies_complete_registered_context_without_native_calls(monkeypatch):
    """Missing identity behavior must fail here, not through a native call."""
    events = []
    dbn_token = object()
    zstd_token = object()
    fake_modules = {"dbn": dbn_token, "zstd": zstd_token}

    def static_snapshot():
        events.append("static")
        return FAKE_ARTIFACTS

    def fake_import():
        events.append("import")
        return fake_modules

    def fake_loaded_identity(modules):
        events.append("loaded")
        assert modules is fake_modules
        assert modules["dbn"] is dbn_token
        assert modules["zstd"] is zstd_token
        return {
            "modules_loaded": FAKE_MODULE_ASSOCIATIONS,
            "backend": "cext",
            "dbn_version": "0.70.0",
            "zstd_package_version": "0.25.0",
            "zstd_library_version": (1, 5, 7),
        }

    monkeypatch.setattr(
        PROBE,
        "sys",
        SimpleNamespace(
            version_info=(3, 12, 10, "final", 0),
            implementation=SimpleNamespace(name="cpython"),
            flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
            dont_write_bytecode=True,
            executable="C:/native-proof-fake/python.exe",
        ),
    )
    monkeypatch.setattr(PROBE, "_static_artifact_snapshot", static_snapshot)
    monkeypatch.setattr(PROBE, "_import_native_modules", fake_import)
    monkeypatch.setattr(PROBE, "_loaded_identity", fake_loaded_identity)

    actual = PROBE.inspect_loaded_native_identity()

    expected = {
        "status": "registered_loaded_identity_consistency_only",
        "python_version": (3, 12, 10),
        "python_implementation": "cpython",
        "isolated": 1,
        "no_site": 1,
        "dont_write_bytecode": 1,
        "artifact_manifest_sha256": EXPECTED_MANIFEST_SHA256,
        "artifacts_before": FAKE_ARTIFACTS,
        "modules_loaded": FAKE_MODULE_ASSOCIATIONS,
        "artifacts_after": FAKE_ARTIFACTS,
        "backend": "cext",
        "dbn_version": "0.70.0",
        "zstd_package_version": "0.25.0",
        "zstd_library_version": (1, 5, 7),
        # This concerns our explicit decoder/parser constructors only.
        # Native import initializer allocation/constructors are not counted.
        "constructor_calls": 0,
    }
    assert type(actual) is dict
    assert actual.keys() == expected.keys()
    assert actual == expected
    assert type(actual["python_implementation"]) is str
    assert events == ["static", "import", "loaded", "static"]
    assert all(
        type(actual[name]) is int and actual[name] == 1
        for name in ("isolated", "no_site", "dont_write_bytecode")
    )
    assert type(actual["constructor_calls"]) is int
    assert actual["constructor_calls"] == 0
    assert type(actual["artifacts_before"]) is tuple
    assert type(actual["artifacts_after"]) is tuple
    assert type(actual["modules_loaded"]) is tuple
    assert len(actual["artifacts_before"]) == 13
    assert len(actual["modules_loaded"]) == 10


# This is the explicit, currently registered qualification window, not a
# historical-date fallback. A later window requires a fresh registration.
CURRENT_HARD_END_UTC = "2026-10-15T14:59:08Z"
DEADLINE_ENV = "AI_TRADER_NATIVE_PROOF_TEST_HARD_END_UTC"
REGISTERED_PYTHON = "C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe"
REGISTERED_PYTHON_SHA256 = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
STATIC_MANIFEST_PATH = ROOT / "logs/native_profile_20261012_1/artifacts_static.json"
IDENTITY_KEYS = {
    "status",
    "python_version",
    "python_implementation",
    "isolated",
    "no_site",
    "dont_write_bytecode",
    "artifact_manifest_sha256",
    "artifacts_before",
    "modules_loaded",
    "artifacts_after",
    "backend",
    "dbn_version",
    "zstd_package_version",
    "zstd_library_version",
    "constructor_calls",
}
EXPECTED_JOB_LIMITS = {
    "limit_flags": 0x230E,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
}
EXPECTED_REAL_MODULE_ORDER = (
    ("python.exe", "sys.executable", True, False),
    ("python312.dll", "sys.dllhandle", True, False),
    ("dbn_init", "databento_dbn", False, True),
    ("dbn_metadata", "databento_dbn.metadata", False, True),
    ("dbn_v1", "databento_dbn.v1", False, True),
    ("dbn_v2", "databento_dbn.v2", False, True),
    ("dbn_v3", "databento_dbn.v3", False, True),
    ("dbn_extension", "databento_dbn._lib", True, True),
    ("zstd_init", "zstandard", False, True),
    ("zstd_extension", "zstandard.backend_c", True, True),
)


def _install_isolated_fake_sys(monkeypatch, *, version=(3, 12, 10), flags=(1, 1, 1)):
    monkeypatch.setattr(
        PROBE,
        "sys",
        SimpleNamespace(
            version_info=version + ("final", 0),
            implementation=SimpleNamespace(name="cpython"),
            flags=SimpleNamespace(
                isolated=flags[0], no_site=flags[1], dont_write_bytecode=flags[2]
            ),
            dont_write_bytecode=True,
            executable="C:/native-proof-fake/python.exe",
        ),
    )


def _fake_loaded_body():
    return {
        "modules_loaded": FAKE_MODULE_ASSOCIATIONS,
        "backend": "cext",
        "dbn_version": "0.70.0",
        "zstd_package_version": "0.25.0",
        "zstd_library_version": (1, 5, 7),
    }


@pytest.mark.parametrize("refusal_phase", ("static", "import", "loaded"))
def test_identity_phase_refusal_never_reaches_a_deferred_seam(monkeypatch, refusal_phase):
    _install_isolated_fake_sys(monkeypatch)
    events = []
    fake_modules = {"dbn": object(), "zstd": object()}
    prior = {
        "static": (),
        "import": ("static",),
        "loaded": ("static", "import"),
    }[refusal_phase]

    def static():
        if events:
            raise AssertionError("final static read occurred after an earlier refusal")
        events.append("static")
        if refusal_phase == "static":
            raise ValueError("registered static refusal")
        return FAKE_ARTIFACTS

    def native_import():
        if tuple(events) != ("static",):
            raise AssertionError("native import preceded the complete static gate")
        if refusal_phase == "static":
            raise AssertionError("native import reached after static refusal")
        events.append("import")
        if refusal_phase == "import":
            raise ValueError("registered import refusal")
        return fake_modules

    def loaded(modules):
        if refusal_phase != "loaded":
            raise AssertionError("loaded association reached after an earlier refusal")
        assert modules is fake_modules
        assert tuple(events) == ("static", "import")
        events.append("loaded")
        raise ValueError("registered loaded association refusal")

    monkeypatch.setattr(PROBE, "_static_artifact_snapshot", static)
    monkeypatch.setattr(PROBE, "_import_native_modules", native_import)
    monkeypatch.setattr(PROBE, "_loaded_identity", loaded)
    with pytest.raises(ValueError):
        PROBE.inspect_loaded_native_identity()
    assert tuple(events) == prior + (refusal_phase,)


def test_identity_rejects_artifact_mutation_after_loaded_association(monkeypatch):
    _install_isolated_fake_sys(monkeypatch)
    events = []
    changed = FAKE_ARTIFACTS[:-1] + (
        {
            **FAKE_ARTIFACTS[-1],
            "raw_sha256": "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        },
    )
    fake_modules = {"dbn": object(), "zstd": object()}

    def static():
        events.append("static")
        return FAKE_ARTIFACTS if len(events) == 1 else changed

    def native_import():
        assert events == ["static"]
        events.append("import")
        return fake_modules

    def loaded(modules):
        assert modules is fake_modules
        assert events == ["static", "import"]
        events.append("loaded")
        return _fake_loaded_body()

    monkeypatch.setattr(PROBE, "_static_artifact_snapshot", static)
    monkeypatch.setattr(PROBE, "_import_native_modules", native_import)
    monkeypatch.setattr(PROBE, "_loaded_identity", loaded)
    with pytest.raises(ValueError, match="changed"):
        PROBE.inspect_loaded_native_identity()
    assert events == ["static", "import", "loaded", "static"]


@pytest.mark.parametrize(
    ("version", "flags"),
    (
        ((3, 12, 10), (0, 1, 1)),
        ((3, 12, 10), (1, 0, 1)),
        ((3, 12, 10), (1, 1, 0)),
        ((3, 12, 10), (True, 1, 1)),
        ((3, 12, 9), (1, 1, 1)),
    ),
    ids=("not_isolated", "site_enabled", "bytecode_enabled", "bool_flag_alias", "wrong_python"),
)
def test_identity_runtime_preflight_refuses_before_any_artifact_or_native_seam(
    monkeypatch, version, flags
):
    _install_isolated_fake_sys(monkeypatch, version=version, flags=flags)

    def forbidden(*_args):
        raise AssertionError("deferred artifact/native seam was traversed")

    monkeypatch.setattr(PROBE, "_static_artifact_snapshot", forbidden)
    monkeypatch.setattr(PROBE, "_import_native_modules", forbidden)
    monkeypatch.setattr(PROBE, "_loaded_identity", forbidden)
    with pytest.raises(ValueError):
        PROBE.inspect_loaded_native_identity()


class _ImplementationStringSubclass(str):
    pass


@pytest.mark.parametrize(
    "invalid_implementation",
    (
        "missing_implementation",
        "missing_name",
        "pypy",
        True,
        _ImplementationStringSubclass("cpython"),
    ),
    ids=("missing_implementation", "missing_name", "wrong_value", "bool_alias", "str_subclass"),
)
def test_identity_implementation_refuses_before_artifacts_or_native_import(
    monkeypatch, invalid_implementation
):
    """The registered interpreter kind must be an observed exact str cpython."""
    _install_isolated_fake_sys(monkeypatch)
    if type(invalid_implementation) is str and invalid_implementation == "missing_implementation":
        del PROBE.sys.implementation
    elif type(invalid_implementation) is str and invalid_implementation == "missing_name":
        del PROBE.sys.implementation.name
    else:
        PROBE.sys.implementation.name = invalid_implementation

    def forbidden(*_args):
        raise AssertionError(
            "artifact/native seam reached before interpreter implementation refusal"
        )

    monkeypatch.setattr(PROBE, "_static_artifact_snapshot", forbidden)
    monkeypatch.setattr(PROBE, "_import_native_modules", forbidden)
    monkeypatch.setattr(PROBE, "_loaded_identity", forbidden)
    with pytest.raises(ValueError):
        PROBE.inspect_loaded_native_identity()


def _qualification_hard_end():
    value = os.environ.get(DEADLINE_ENV)
    if type(value) is not str or value != CURRENT_HARD_END_UTC:
        raise ValueError("explicit current registered native qualification deadline required")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("canonical native qualification deadline required") from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != value:
        raise ValueError("canonical native qualification deadline required")
    if (parsed - datetime.now(UTC)).total_seconds() < 15.0:
        raise ValueError("native qualification lacks the complete work/teardown reserve")
    return value


def _run_registered_native(mode):
    hard_end = _qualification_hard_end()
    if mode not in (
        "native_identity",
        "native_dbn",
        "native_zstd",
        "native_enums",
        "native_composed",
        "native_boundaries",
        "native_capacity",
        "native_zstd_partitions",
        "native_zstd_capacity",
    ):
        raise ValueError("fixed native qualification mode required")
    return CONTAINMENT.run_owned_case(
        python_exe=REGISTERED_PYTHON,
        expected_python_sha256=REGISTERED_PYTHON_SHA256,
        script_path=str(PROBE_PATH),
        expected_script_sha256=hashlib.sha256(PROBE_PATH.read_bytes()).hexdigest(),
        script_args=(mode,),
        case_id=mode,
        hard_end_utc=hard_end,
    )


@pytest.mark.parametrize("context", (None, "not-a-UTC-deadline", "2000-01-01T00:00:00Z"))
def test_explicit_native_deadline_refuses_before_containment_without_fallback(monkeypatch, context):
    if context is None:
        monkeypatch.delenv(DEADLINE_ENV, raising=False)
    else:
        monkeypatch.setenv(DEADLINE_ENV, context)

    def forbidden(**_kwargs):
        raise AssertionError("owned/native launch reached without its explicit valid deadline")

    monkeypatch.setattr(CONTAINMENT, "run_owned_case", forbidden)
    with pytest.raises(ValueError):
        _run_registered_native("native_identity")


def _strict_json_pairs(pairs):
    body = {}
    for name, value in pairs:
        if name in body:
            raise ValueError("duplicate child JSON key")
        body[name] = value
    return body


def _assert_successful_owned_native_receipt(receipt, output, *, mode):
    assert type(receipt) is dict
    assert type(output) is bytes
    assert receipt["case_id"] == mode
    assert receipt["hard_end_utc"] == CURRENT_HARD_END_UTC
    assert receipt["disposition"] == "completed"
    assert receipt["created"] is True
    assert receipt["resumed"] is True
    assert receipt["process_exited"] is True
    assert type(receipt["exit_code"]) is int and receipt["exit_code"] == 0
    assert receipt["in_job_before_resume"] is True
    assert type(receipt["resume_previous_count"]) is int
    assert receipt["resume_previous_count"] == 1
    assert receipt["configured_limits"] == EXPECTED_JOB_LIMITS
    assert receipt["queried_limits"] == EXPECTED_JOB_LIMITS
    for limits in (receipt["configured_limits"], receipt["queried_limits"]):
        assert all(type(value) is int for value in limits.values())
    assert type(receipt["parent_pid"]) is int and receipt["parent_pid"] == os.getpid()
    assert type(receipt["child_pid"]) is int and receipt["child_pid"] > 0
    assert receipt["child_pid"] != receipt["parent_pid"]
    assert receipt["child_parent_pid"] == receipt["parent_pid"]
    assert type(receipt["parent_creation_filetime"]) is int
    assert type(receipt["child_creation_filetime"]) is int
    assert 0 < receipt["parent_creation_filetime"] <= receipt["child_creation_filetime"]
    assert receipt["child_image"].replace("\\", "/").casefold() == REGISTERED_PYTHON.casefold()
    assert receipt["job_process_ids_initial"] == []
    assert receipt["job_process_ids_before_resume"] == [receipt["child_pid"]]
    assert receipt["job_process_ids_final"] == []
    assert receipt["final_active_processes"] == 0
    assert type(receipt["final_active_processes"]) is int
    assert receipt["job_accounting_initial"]["active_processes"] == 0
    assert receipt["job_accounting_before_resume"]["active_processes"] == 1
    assert receipt["job_accounting"]["active_processes"] == 0
    assert receipt["cleanup_errors"] == []
    assert receipt["error"] is None
    assert receipt["termination_requested"] is False
    assert receipt["termination_attempt"] is None
    assert receipt["output_complete"] is True
    assert receipt["output_hash_scope"] == "complete_stream"
    assert type(receipt["output_bytes"]) is int and receipt["output_bytes"] == len(output)
    assert 0 < len(output) <= 4194304
    assert receipt["output_sha256"] == hashlib.sha256(output).hexdigest()
    assert receipt["work_seconds"] == 12.0
    assert receipt["total_seconds"] == 15.0
    assert receipt["output_limit_bytes"] == 4194304
    assert receipt["read_chunk_bytes"] == 65536
    for key in ("peak_process_memory_bytes", "peak_job_memory_bytes"):
        assert type(receipt[key]) is int and 0 <= receipt[key] <= 268435456
    assert receipt["kill_on_job_close_queried"] is True
    assert receipt["parent_death_empirically_tested"] is False
    # Parent does not infer child imports from a mode name.
    assert receipt["native_codec_imported"] is None
    assert receipt["native_profile_closed"] is False
    assert receipt["argv"][1:4] == ["-I", "-S", "-B"]
    assert receipt["argv"][5:] == [mode]
    assert receipt["argv"][0].replace("\\", "/").casefold() == REGISTERED_PYTHON.casefold()
    assert (
        receipt["argv"][4].replace("\\", "/").casefold()
        == str(PROBE_PATH).replace("\\", "/").casefold()
    )


def test_registered_native_identity_child_complete_evidence():
    """Mandatory real child qualification: a missing dispatch is an executed RED."""
    receipt, output = _run_registered_native("native_identity")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_identity")
    assert output.endswith(b"\n")
    assert len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict and actual.keys() == IDENTITY_KEYS
    assert actual["status"] == "registered_loaded_identity_consistency_only"
    assert type(actual["python_implementation"]) is str
    assert actual["python_implementation"] == "cpython"
    assert actual["python_version"] == [3, 12, 10]
    assert all(type(value) is int for value in actual["python_version"])
    for key in ("isolated", "no_site", "dont_write_bytecode"):
        assert type(actual[key]) is int and actual[key] == 1
    assert actual["artifact_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
    assert actual["backend"] == "cext"
    assert actual["dbn_version"] == "0.70.0"
    assert actual["zstd_package_version"] == "0.25.0"
    assert actual["zstd_library_version"] == [1, 5, 7]
    assert all(type(value) is int for value in actual["zstd_library_version"])
    assert type(actual["constructor_calls"]) is int and actual["constructor_calls"] == 0

    # Read only the fixed bounded metadata registration, not arbitrary child paths.
    with STATIC_MANIFEST_PATH.open("rb") as stream:
        raw_registration = stream.read(65537)
    assert len(raw_registration) <= 65536
    assert hashlib.sha256(raw_registration).hexdigest() == EXPECTED_MANIFEST_SHA256
    registration = json.loads(raw_registration, object_pairs_hook=_strict_json_pairs)
    expected_artifacts = registration["artifacts"]
    assert type(expected_artifacts) is list and len(expected_artifacts) == 13
    assert len({entry["logical_id"] for entry in expected_artifacts}) == 13
    assert actual["artifacts_before"] == expected_artifacts
    assert actual["artifacts_after"] == expected_artifacts

    associations = actual["modules_loaded"]
    assert type(associations) is list and len(associations) == 10
    expected_paths = {entry["logical_id"]: entry["path"] for entry in expected_artifacts}
    for association, expected in zip(associations, EXPECTED_REAL_MODULE_ORDER, strict=True):
        logical_id, module_name, native, has_spec = expected
        assert type(association) is dict
        assert association.keys() == {
            "logical_id",
            "module_name",
            "module_file",
            "spec_origin",
            "mapped_path",
            "module_handle",
        }
        assert association["logical_id"] == logical_id
        assert association["module_name"] == module_name
        # Pure lexical normalization; never resolve/open an untrusted output path.
        expected_path = expected_paths[logical_id].replace("\\", "/").casefold()
        assert type(association["module_file"]) is str
        assert association["module_file"].replace("\\", "/").casefold() == expected_path
        if has_spec:
            assert type(association["spec_origin"]) is str
            assert association["spec_origin"].replace("\\", "/").casefold() == expected_path
        else:
            assert association["spec_origin"] is None
        if native:
            assert type(association["module_handle"]) is int and association["module_handle"] > 0
            assert type(association["mapped_path"]) is str
            assert association["mapped_path"].replace("\\", "/").casefold() == expected_path
        else:
            assert association["module_handle"] is None
            assert association["mapped_path"] is None


LITERAL_ORACLE_SHA256 = "4314a212d8e62047ab92b56028784b3914975391e2a2cbe78dee2bb7c7793ba4"
LITERAL_ORACLE_PATH = ROOT / "tests/native_profile_oracles_20261012_1.py"


def _load_registered_literal_oracles():
    # Execute the exact pinned declaration bytes, not a second path read.
    with LITERAL_ORACLE_PATH.open("rb") as source:
        raw = source.read(1048577)
    assert len(raw) <= 1048576
    assert hashlib.sha256(raw).hexdigest() == LITERAL_ORACLE_SHA256
    module = SimpleNamespace(__file__=str(LITERAL_ORACLE_PATH))
    exec(compile(raw, str(LITERAL_ORACLE_PATH), "exec"), vars(module))
    return module


def _assert_exact_json_literal(actual, expected):
    """Only explicit literal tuples become JSON lists; every scalar type is exact."""
    if type(expected) in (tuple, list):
        assert type(actual) is list
        assert len(actual) == len(expected)
        for value, literal in zip(actual, expected, strict=True):
            _assert_exact_json_literal(value, literal)
    elif type(expected) is dict:
        assert type(actual) is dict
        assert actual.keys() == expected.keys()
        for name, literal in expected.items():
            _assert_exact_json_literal(actual[name], literal)
    else:
        assert type(actual) is type(expected)
        assert actual == expected


def _registered_literal_artifacts():
    with STATIC_MANIFEST_PATH.open("rb") as source:
        raw = source.read(65537)
    assert len(raw) <= 65536
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_MANIFEST_SHA256
    registration = json.loads(raw, object_pairs_hook=_strict_json_pairs)
    assert registration["schema"] == "native_profile_provisional_artifacts_v1"
    assert registration["status"] == "STATIC_EXPECTATIONS_NOT_CLOSED_PROFILE"
    artifacts = registration["artifacts"]
    assert type(artifacts) is list and len(artifacts) == 13
    assert len({entry["logical_id"] for entry in artifacts}) == 13
    for entry in artifacts:
        assert type(entry) is dict
        assert entry.keys() == {"logical_id", "path", "raw_bytes", "raw_sha256"}
        assert type(entry["logical_id"]) is str and type(entry["path"]) is str
        assert type(entry["raw_bytes"]) is int and entry["raw_bytes"] >= 0
        assert type(entry["raw_sha256"]) is str and len(entry["raw_sha256"]) == 64
    return artifacts


def _assert_real_identity_complete(actual):
    assert type(actual) is dict and actual.keys() == IDENTITY_KEYS
    assert actual["status"] == "registered_loaded_identity_consistency_only"
    _assert_exact_json_literal(actual["python_implementation"], "cpython")
    _assert_exact_json_literal(actual["python_version"], (3, 12, 10))
    for name in ("isolated", "no_site", "dont_write_bytecode"):
        assert type(actual[name]) is int and actual[name] == 1
    assert actual["artifact_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
    assert type(actual["constructor_calls"]) is int and actual["constructor_calls"] == 0
    for name, literal in (
        ("backend", "cext"),
        ("dbn_version", "0.70.0"),
        ("zstd_package_version", "0.25.0"),
    ):
        assert type(actual[name]) is str and actual[name] == literal
    _assert_exact_json_literal(actual["zstd_library_version"], (1, 5, 7))
    artifacts = _registered_literal_artifacts()
    _assert_exact_json_literal(actual["artifacts_before"], artifacts)
    _assert_exact_json_literal(actual["artifacts_after"], artifacts)
    expected_paths = {entry["logical_id"]: entry["path"] for entry in artifacts}
    associations = actual["modules_loaded"]
    assert type(associations) is list and len(associations) == 10
    for association, expected in zip(associations, EXPECTED_REAL_MODULE_ORDER, strict=True):
        logical_id, module_name, native, has_spec = expected
        assert type(association) is dict
        assert association.keys() == {
            "logical_id",
            "module_name",
            "module_file",
            "spec_origin",
            "mapped_path",
            "module_handle",
        }
        assert type(association["logical_id"]) is str and association["logical_id"] == logical_id
        assert type(association["module_name"]) is str and association["module_name"] == module_name
        expected_path = expected_paths[logical_id].replace("\\", "/").casefold()
        assert type(association["module_file"]) is str
        assert association["module_file"].replace("\\", "/").casefold() == expected_path
        if has_spec:
            assert type(association["spec_origin"]) is str
            assert association["spec_origin"].replace("\\", "/").casefold() == expected_path
        else:
            assert association["spec_origin"] is None
        if native:
            assert type(association["module_handle"]) is int and association["module_handle"] > 0
            assert type(association["mapped_path"]) is str
            assert association["mapped_path"].replace("\\", "/").casefold() == expected_path
        else:
            assert association["module_handle"] is None and association["mapped_path"] is None


def _literal_dbn_framing(case, literals):
    header_end = case["wire_spans"][0][2]
    if header_end == 128:
        variable_spans = literals.MINIMAL_VARIABLE_SPANS
    elif header_end == 872:
        variable_spans = literals.RICH_VARIABLE_SPANS
    else:
        raise AssertionError("positive literal corpus contains an unregistered header size")
    fields = [literals.METADATA_FIXED_SPANS + variable_spans]
    record_fields = (
        literals.MBO_PRESENT_TS_OUT_FIELD_SPANS
        if case["wire_bodies"][0]["ts_out"] == 1
        else literals.MBO_BASE_FIELD_SPANS
    )
    for kind, start, _end in case["wire_spans"][1:]:
        assert kind == "MBO"
        fields.append(
            tuple((name, start + first, start + last) for name, first, last in record_fields)
        )
    return {
        "complete_bytes": case["complete_bytes"],
        "wire_spans": case["wire_spans"],
        "wire_bodies": case["wire_bodies"],
        "field_spans": tuple(fields),
    }


def _assert_final_identity_remeasurements(actual, initial):
    _assert_exact_json_literal(actual["artifacts_final"], initial["artifacts_before"])
    _assert_exact_json_literal(actual["artifacts_final"], initial["artifacts_after"])
    _assert_exact_json_literal(
        actual["loaded_final"],
        {
            "modules_loaded": initial["modules_loaded"],
            "backend": "cext",
            "dbn_version": "0.70.0",
            "zstd_package_version": "0.25.0",
            "zstd_library_version": [1, 5, 7],
        },
    )


def test_registered_native_dbn_child_complete_literal_cohort_and_partitions():
    """One real test body compares every registered case, partition and refusal."""
    literals = _load_registered_literal_oracles()
    positives = (
        tuple(case for case in literals.DBN_CASES if not case["strict_profile_refusal"])
        + literals.DBN_STYPE_CASES
    )
    assert len(positives) == 42
    assert len({case["case_id"] for case in positives}) == 42
    receipt, output = _run_registered_native("native_dbn")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_dbn")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "strict_refusals",
        "artifacts_final",
        "loaded_final",
    }
    assert actual["schema"] == "native_dbn_probe_v1"
    assert actual["status"] == "constructed_native_observation_only"
    assert actual["oracle_sha256"] == LITERAL_ORACLE_SHA256
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
    )
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 42
    assert len({case["case_id"] for case in cases}) == 42
    partition_count = 0
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {"case_id", "input_hex", "input_sha256", "framing", "partitions"}
        assert type(case["case_id"]) is str and case["case_id"] == literal["case_id"]
        assert type(case["input_hex"]) is str and case["input_hex"] == literal["dbn_hex"]
        raw_input = bytes.fromhex(literal["dbn_hex"])
        assert len(raw_input) == literal["complete_bytes"]
        assert case["input_sha256"] == hashlib.sha256(raw_input).hexdigest()
        _assert_exact_json_literal(case["framing"], _literal_dbn_framing(literal, literals))
        partitions = case["partitions"]
        assert type(partitions) is list and len(partitions) == 3
        quotient, remainder = divmod(literal["complete_bytes"], 7)
        expected_chunks = (7,) * quotient + ((remainder,) if remainder else ())
        for partition, mode, chunk_lengths in zip(
            partitions,
            ("complete", "chunks7", "bytewise"),
            ((literal["complete_bytes"],), expected_chunks, (1,) * literal["complete_bytes"]),
            strict=True,
        ):
            assert type(partition) is dict
            assert partition.keys() == {"mode", "chunk_lengths", "observations", "buffer_hex"}
            assert type(partition["mode"]) is str and partition["mode"] == mode
            _assert_exact_json_literal(partition["chunk_lengths"], chunk_lengths)
            assert sum(partition["chunk_lengths"]) == literal["complete_bytes"]
            _assert_exact_json_literal(partition["observations"], literal["native_observations"])
            assert type(partition["buffer_hex"]) is str and partition["buffer_hex"] == ""
            partition_count += 1
    assert partition_count == 126

    duplicate = tuple(
        (case["case_id"], case["dbn_hex"])
        for case in literals.DBN_CASES
        if case["strict_profile_refusal"]
    )
    expected_refusals = (
        duplicate + literals.DBN_FRAMING_NEGATIVE_CASES + literals.DBN_STYPE_NEGATIVE_CASES
    )
    assert len(expected_refusals) == 11
    assert len({name for name, _hex in expected_refusals}) == 11
    refusals = actual["strict_refusals"]
    assert type(refusals) is list and len(refusals) == 11
    assert len({case["case_id"] for case in refusals}) == 11
    for case, (case_id, input_hex) in zip(refusals, expected_refusals, strict=True):
        _assert_exact_json_literal(
            case,
            {
                "case_id": case_id,
                "input_hex": input_hex,
                "phase": "independent_preflight",
                "constructor_calls": 0,
            },
        )
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_zstd_child_complete_literal_outputs_and_refusals():
    """Per-frame tell positions are slice-relative, not global member offsets."""
    literals = _load_registered_literal_oracles()
    positives = literals.ZSTD_CASES + tuple(
        case for case in literals.ZSTD_RESOURCE_CASES if not case["strict_profile_refusal"]
    )
    assert len(positives) == 12
    assert len({case["case_id"] for case in positives}) == 12
    receipt, output = _run_registered_native("native_zstd")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_zstd")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "refusals",
        "artifacts_final",
        "loaded_final",
    }
    assert type(actual["schema"]) is str and actual["schema"] == "native_zstd_probe_v1"
    assert (
        type(actual["status"]) is str and actual["status"] == "constructed_native_observation_only"
    )
    assert type(actual["oracle_sha256"]) is str and actual["oracle_sha256"] == LITERAL_ORACLE_SHA256
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "backend": "cext",
            "read_across_frames": False,
            "read_size": 65536,
            "max_window_size_argument": 1048576,
            "independent_window_cap": 1048576,
            "cumulative_output_cap": 1048576,
            "compressed_input_cap": 262144,
            "frame_cap": 16,
        },
    )

    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 12
    assert len({case["case_id"] for case in cases}) == 12
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "framing",
            "output_base64",
            "output_bytes",
            "read_sizes",
            "frame_input_positions",
            "termination_checks",
        }
        assert type(case["case_id"]) is str and case["case_id"] == literal["case_id"]
        assert type(case["input_hex"]) is str and case["input_hex"] == literal["compressed_hex"]
        assert len(bytes.fromhex(literal["compressed_hex"])) == literal["compressed_bytes"]
        descriptors = literals.ZSTD_FRAME_EXPECTATIONS[literal["case_id"]]
        _assert_exact_json_literal(case["framing"], descriptors)
        if "decompressed_hex" in literal:
            expected_bytes = bytes.fromhex(literal["decompressed_hex"])
        else:
            assert type(literal["output_byte"]) is int and literal["output_byte"] == 65
            assert type(literal["output_repetitions"]) is int
            expected_bytes = b"A" * literal["output_repetitions"]
        assert 0 < len(expected_bytes) <= 1048576
        assert type(case["output_bytes"]) is int and case["output_bytes"] == len(expected_bytes)
        assert type(case["output_base64"]) is str
        encoded = case["output_base64"].encode("ascii", errors="strict")
        decoded = base64.b64decode(encoded, validate=True)
        assert decoded == expected_bytes
        # Reject noncanonical padding/alternate encodings, not merely equal hashes.
        assert base64.b64encode(expected_bytes) == encoded

        if len(expected_bytes) == 1048576:
            expected_reads = (65536,) * 16 + (1,)
        else:
            # Each complete small slice returns its output, then an EOF read.
            expected_reads = (65536,) * (2 * len(descriptors))
        _assert_exact_json_literal(case["read_sizes"], expected_reads)
        assert all(type(size) is int and 1 <= size <= 65536 for size in case["read_sizes"])
        # This is each BytesIO frame-slice tell(), not global compressed_end.
        expected_positions = tuple(frame[2] - frame[1] for frame in descriptors)
        _assert_exact_json_literal(case["frame_input_positions"], expected_positions)
        frame_outputs = tuple(last - first for _start, _end, first, last in literal["frame_spans"])
        assert len(frame_outputs) == len(descriptors)
        assert sum(frame_outputs) == len(expected_bytes)
        _assert_exact_json_literal(
            case["termination_checks"],
            tuple(
                {
                    "frame_ordinal": ordinal,
                    "max_output_size": length,
                    "read_across_frames": False,
                    "allow_extra_data": False,
                    "output_bytes": length,
                    "matches_stream_output": True,
                }
                for ordinal, length in enumerate(frame_outputs, 1)
            ),
        )

    over_cap = tuple(
        case for case in literals.ZSTD_RESOURCE_CASES if case["strict_profile_refusal"]
    )
    expected_refusals = (
        tuple(
            (
                case["case_id"],
                case["compressed_hex"],
                "independent_preflight",
                0,
                "ValueError",
                None,
            )
            for case in literals.ZSTD_STRICT_FORMAT_NEGATIVE_CASES
        )
        + (
            (
                over_cap[0]["case_id"],
                over_cap[0]["compressed_hex"],
                "independent_preflight",
                0,
                "ValueError",
                None,
            ),
            (
                over_cap[1]["case_id"],
                over_cap[1]["compressed_hex"],
                "native_output_limit",
                1,
                "OutputLimitExceeded",
                1048577,
            ),
        )
        + (
            (
                literals.ZSTD_CHECKSUM_NEGATIVE_CASES[0]["case_id"],
                literals.ZSTD_CHECKSUM_NEGATIVE_CASES[0]["compressed_hex"],
                "native_checksum",
                1,
                "ZstdError",
                None,
            ),
        )
    )
    assert len(over_cap) == 2
    assert len(expected_refusals) == 7
    assert len({entry[0] for entry in expected_refusals}) == 7
    refusals = actual["refusals"]
    assert type(refusals) is list and len(refusals) == 7
    assert len({case["case_id"] for case in refusals}) == 7
    for case, expected in zip(refusals, expected_refusals, strict=True):
        case_id, input_hex, phase, constructors, error_type, observed_bytes = expected
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "phase",
            "constructor_calls",
            "error_type",
            "error_message",
            "observed_output_bytes",
        }
        for name, literal in (
            ("case_id", case_id),
            ("input_hex", input_hex),
            ("phase", phase),
            ("constructor_calls", constructors),
            ("error_type", error_type),
            ("observed_output_bytes", observed_bytes),
        ):
            _assert_exact_json_literal(case[name], literal)
        # Diagnostic wording is a retained observation, not an invented oracle.
        assert type(case["error_message"]) is str and case["error_message"]
    _assert_final_identity_remeasurements(actual, actual["identity"])


@pytest.mark.parametrize(
    "empty_first", (True, False), ids=("empty_then_nonempty", "nonempty_then_empty")
)
def test_each_zstd_frame_must_have_nonempty_output_before_a_later_reader(empty_first):
    """Fake byte-only readers prove per-frame refusal, not native behavior."""
    empty = bytes.fromhex("28b52ffd2000010000")
    nonempty = bytes.fromhex("28b52ffd20021100004142")
    if empty_first:
        raw = empty + nonempty
        framing = (
            (
                1,
                0,
                9,
                0,
                6,
                32,
                None,
                0,
                True,
                0,
                False,
                0,
                0,
                None,
                None,
                ((1, 6, 9, True, 0, 0, 9, 9),),
            ),
            (
                2,
                9,
                20,
                9,
                15,
                32,
                None,
                0,
                True,
                0,
                False,
                2,
                2,
                None,
                None,
                ((1, 15, 18, True, 0, 2, 18, 20),),
            ),
        )
    else:
        raw = nonempty + empty
        framing = (
            (
                1,
                0,
                11,
                0,
                6,
                32,
                None,
                0,
                True,
                0,
                False,
                2,
                2,
                None,
                None,
                ((1, 6, 9, True, 0, 2, 9, 11),),
            ),
            (
                2,
                11,
                20,
                11,
                17,
                32,
                None,
                0,
                True,
                0,
                False,
                0,
                0,
                None,
                None,
                ((1, 17, 20, True, 0, 0, 20, 20),),
            ),
        )
    events = []

    class FakeReader:
        def __init__(self, source, output, owner):
            assert type(source) is io.BytesIO
            self.source = source
            self.output = output
            self.owner = owner
            self.finished = False

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            self.owner.closed = True
            return False

        def read(self, request):
            assert type(request) is int and request == 65536
            self.source.seek(0, 2)
            if self.finished:
                return b""
            self.finished = True
            return self.output

    class FakeDecoder:
        def __init__(self):
            self.closed = False

        def stream_reader(self, source, *, read_across_frames, read_size):
            assert read_across_frames is False and type(read_across_frames) is bool
            assert type(read_size) is int and read_size == 65536
            encoded = source.getvalue()
            if empty_first and encoded == nonempty:
                # An eager next-frame read is a real uncaught AssertionError.
                raise AssertionError("later reader was reached after an empty first frame")
            events.append("empty" if encoded == empty else "nonempty")
            assert encoded in (empty, nonempty)
            return FakeReader(source, b"" if encoded == empty else b"AB", self)

        def decompress(self, data, *, max_output_size, read_across_frames, allow_extra_data):
            assert self.closed is True
            assert data == nonempty
            assert type(data) is bytes
            assert type(max_output_size) is int and max_output_size == 2
            assert read_across_frames is False and type(read_across_frames) is bool
            assert allow_extra_data is False and type(allow_extra_data) is bool
            return b"AB"

    class FakeZstd:
        @staticmethod
        def ZstdDecompressor(*, max_window_size):
            assert type(max_window_size) is int and max_window_size == 1048576
            return FakeDecoder()

    progress = {"constructor_calls": 0}
    with pytest.raises(ValueError):
        PROBE._read_zstd_frames(FakeZstd, raw, framing, progress)
    assert events == (["empty"] if empty_first else ["nonempty", "empty"])
    assert progress == {"constructor_calls": 1 if empty_first else 2}


@pytest.mark.parametrize(
    "failure",
    (None, "wrong_type", "wrong_complete_bytes", "native_exception"),
    ids=("complete_after_close", "wrong_type", "wrong_complete_bytes", "native_exception"),
)
def test_zstd_terminal_check_uses_closed_same_decoder_and_stops_before_next_frame(failure):
    """Exact bounded one-shot equality is a separate mandatory terminal fact."""
    first = bytes.fromhex("28b52ffd20021100004142")
    second = bytes.fromhex("28b52ffd200423000041")
    raw = first + second
    framing = (
        (
            1,
            0,
            11,
            0,
            6,
            32,
            None,
            0,
            True,
            0,
            False,
            2,
            2,
            None,
            None,
            ((1, 6, 9, True, 0, 2, 9, 11),),
        ),
        (
            2,
            11,
            21,
            11,
            17,
            32,
            None,
            0,
            True,
            0,
            False,
            4,
            4,
            None,
            None,
            ((1, 17, 20, True, 1, 4, 20, 21),),
        ),
    )
    events = []
    constructed = []

    class FakeCodecError(RuntimeError):
        pass

    class FakeReader:
        def __init__(self, source, decoder):
            assert type(source) is io.BytesIO
            self.source = source
            self.decoder = decoder
            self.finished = False

        def __enter__(self):
            events.append(("open", self.decoder.ordinal))
            return self

        def __exit__(self, *_exc):
            events.append(("closed", self.decoder.ordinal))
            self.decoder.closed = True
            return False

        def read(self, request):
            assert type(request) is int and request == 65536
            self.source.seek(0, 2)
            if self.finished:
                return b""
            self.finished = True
            return b"AB" if self.decoder.ordinal == 1 else b"AAAA"

    class FakeDecoder:
        def __init__(self, ordinal):
            self.ordinal = ordinal
            self.closed = False

        def stream_reader(self, source, *, read_across_frames, read_size):
            assert read_across_frames is False and type(read_across_frames) is bool
            assert type(read_size) is int and read_size == 65536
            assert source.getvalue() == (first if self.ordinal == 1 else second)
            return FakeReader(source, self)

        def decompress(self, data, *, max_output_size, read_across_frames, allow_extra_data):
            assert self.closed is True
            assert type(data) is bytes and data == (first if self.ordinal == 1 else second)
            length = 2 if self.ordinal == 1 else 4
            assert type(max_output_size) is int and max_output_size == length
            assert read_across_frames is False and type(read_across_frames) is bool
            assert allow_extra_data is False and type(allow_extra_data) is bool
            events.append(("terminal", self.ordinal))
            if failure == "wrong_type":
                return bytearray(b"AB")
            if failure == "wrong_complete_bytes":
                return b"BA"
            if failure == "native_exception":
                raise FakeCodecError("independent native terminal failure")
            return b"AB" if self.ordinal == 1 else b"AAAA"

    class FakeZstd:
        @staticmethod
        def ZstdDecompressor(*, max_window_size):
            assert type(max_window_size) is int and max_window_size == 1048576
            ordinal = len(constructed) + 1
            if failure is not None and ordinal == 2:
                raise AssertionError("next frame constructor reached after a failed terminal check")
            events.append(("constructed", ordinal))
            decoder = FakeDecoder(ordinal)
            constructed.append(decoder)
            return decoder

    progress = {"constructor_calls": 0}
    if failure is None:
        actual = PROBE._read_zstd_frames(FakeZstd, raw, framing, progress)
        assert type(actual) is tuple and actual[0] == b"ABAAAA"
        assert events == [
            ("constructed", 1),
            ("open", 1),
            ("closed", 1),
            ("terminal", 1),
            ("constructed", 2),
            ("open", 2),
            ("closed", 2),
            ("terminal", 2),
        ]
        # A missing four-field terminal result is an intended behavior failure,
        # not a tuple-unpacking accident or a collection error.
        assert len(actual) == 4
        assert actual == (
            b"ABAAAA",
            (65536, 65536, 65536, 65536),
            (11, 10),
            (
                {
                    "frame_ordinal": 1,
                    "max_output_size": 2,
                    "read_across_frames": False,
                    "allow_extra_data": False,
                    "output_bytes": 2,
                    "matches_stream_output": True,
                },
                {
                    "frame_ordinal": 2,
                    "max_output_size": 4,
                    "read_across_frames": False,
                    "allow_extra_data": False,
                    "output_bytes": 4,
                    "matches_stream_output": True,
                },
            ),
        )
        assert progress == {"constructor_calls": 2}
    else:
        expected_error = FakeCodecError if failure == "native_exception" else ValueError
        with pytest.raises(expected_error):
            PROBE._read_zstd_frames(FakeZstd, raw, framing, progress)
        assert progress == {"constructor_calls": 1}
        assert events == [("constructed", 1), ("open", 1), ("closed", 1), ("terminal", 1)]


ENUM_ORACLE_PATH = ROOT / "tests/native_profile_enum_oracles_20261012_1.py"
ENUM_ORACLE_SHA256 = "a27abb7efaece7797e22fd147f9dfbc2c29d5e79ee4c4058c440173ef91596ec"
COMPOSED_ORACLE_PATH = ROOT / "tests/native_profile_composed_oracles_20261012_1.py"
COMPOSED_ORACLE_SHA256 = "fbb532130c6ac49ba05b1011baaf586e4f29939628d053cc47f450cff87159f8"
NEGATIVE_ORACLE_PATH = ROOT / "tests/native_profile_native_negative_oracles_20261012_1.py"
NEGATIVE_ORACLE_SHA256 = "d5db004581c115eb02194dd355b3a789024d670e038f8a01f05a6229b675cb3f"
CAPACITY_ORACLE_PATH = ROOT / "tests/native_profile_capacity_oracles_20261012_1.py"
CAPACITY_ORACLE_SHA256 = "739b81a4cca047d1f55c480bba4d0e6bf9597dd6ccc16b3e164c83f339459bcf"
ZSTD_CAPACITY_ORACLE_PATH = ROOT / "tests/native_profile_zstd_capacity_oracles_20261012_1.py"
ZSTD_CAPACITY_ORACLE_SHA256 = "17c91e7c6697df7f95b05fc5dbf25083fe486501afc06d008f793ac93b6193f4"


def _load_registered_supplementary_literals(kind):
    if kind == "enum":
        path, expected = ENUM_ORACLE_PATH, ENUM_ORACLE_SHA256
    elif kind == "composed":
        path, expected = COMPOSED_ORACLE_PATH, COMPOSED_ORACLE_SHA256
    elif kind == "negative":
        path, expected = NEGATIVE_ORACLE_PATH, NEGATIVE_ORACLE_SHA256
    elif kind == "capacity":
        path, expected = CAPACITY_ORACLE_PATH, CAPACITY_ORACLE_SHA256
    elif kind == "zstd_capacity":
        path, expected = ZSTD_CAPACITY_ORACLE_PATH, ZSTD_CAPACITY_ORACLE_SHA256
    else:
        raise AssertionError("supplementary packet must have a fixed registered identity")
    with path.open("rb") as source:
        raw = source.read(1048577)
    assert len(raw) <= 1048576
    assert hashlib.sha256(raw).hexdigest() == expected
    # Declaration-only reviewed packet bytes; no production/native imports.
    module = SimpleNamespace(__file__=str(path))
    exec(compile(raw, str(path), "exec"), vars(module))
    return module


def _assert_three_literal_dbn_partitions(actual, *, complete_bytes, native_observations):
    assert type(complete_bytes) is int and complete_bytes > 0
    quotient, remainder = divmod(complete_bytes, 7)
    expected_chunks = (7,) * quotient + ((remainder,) if remainder else ())
    assert type(actual) is list and len(actual) == 3
    for partition, mode, lengths in zip(
        actual,
        ("complete", "chunks7", "bytewise"),
        ((complete_bytes,), expected_chunks, (1,) * complete_bytes),
        strict=True,
    ):
        assert type(partition) is dict
        assert partition.keys() == {"mode", "chunk_lengths", "observations", "buffer_hex"}
        _assert_exact_json_literal(partition["mode"], mode)
        _assert_exact_json_literal(partition["chunk_lengths"], lengths)
        assert sum(partition["chunk_lengths"]) == complete_bytes
        _assert_exact_json_literal(partition["observations"], native_observations)
        _assert_exact_json_literal(partition["buffer_hex"], "")


def test_registered_native_enum_child_complete_source_domains_and_ts_out_modes():
    """Every known Action/Side branch is literal, in both ts_out modes."""
    literals = _load_registered_literal_oracles()
    enum_literals = _load_registered_supplementary_literals("enum")
    positives = enum_literals.DBN_ENUM_CASES
    assert type(positives) is tuple and len(positives) == 20
    assert len({case["case_id"] for case in positives}) == 20
    assert all(case["strict_profile_refusal"] is False for case in positives)
    receipt, output = _run_registered_native("native_enums")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_enums")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "strict_refusals",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_enum_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], ENUM_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
    )
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 20
    assert len({case["case_id"] for case in cases}) == 20
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {"case_id", "input_hex", "input_sha256", "framing", "partitions"}
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["dbn_hex"])
        raw = bytes.fromhex(literal["dbn_hex"])
        assert len(raw) == literal["complete_bytes"]
        _assert_exact_json_literal(case["input_sha256"], hashlib.sha256(raw).hexdigest())
        _assert_exact_json_literal(case["framing"], _literal_dbn_framing(literal, literals))
        _assert_three_literal_dbn_partitions(
            case["partitions"],
            complete_bytes=literal["complete_bytes"],
            native_observations=literal["native_observations"],
        )
    _assert_exact_json_literal(actual["strict_refusals"], ())
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_composed_child_complete_frames_and_continuous_dbn():
    """Physical compressed coordinates and per-slice tell positions stay separate."""
    literals = _load_registered_literal_oracles()
    composed_literals = _load_registered_supplementary_literals("composed")
    positives = composed_literals.COMPOSED_CASES
    assert type(positives) is tuple and len(positives) == 3
    assert len({case["case_id"] for case in positives}) == 3
    receipt, output = _run_registered_native("native_composed")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_composed")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_composed_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], COMPOSED_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "dbn": {
                "has_metadata": True,
                "input_version": None,
                "upgrade_policy": "AS_IS",
                "compression": "NONE",
                "ts_out_constructor": False,
            },
            "zstd": {
                "backend": "cext",
                "read_across_frames": False,
                "read_size": 65536,
                "max_window_size_argument": 1048576,
                "independent_window_cap": 1048576,
                "cumulative_output_cap": 1048576,
                "compressed_input_cap": 262144,
                "frame_cap": 16,
            },
        },
    )
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 3
    assert len({case["case_id"] for case in cases}) == 3
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "input_sha256",
            "framing",
            "output_hex",
            "dbn_framing",
            "read_sizes",
            "frame_input_positions",
            "partitions",
            "termination_checks",
        }
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["compressed_hex"])
        compressed = bytes.fromhex(literal["compressed_hex"])
        assert len(compressed) == literal["compressed_bytes"]
        _assert_exact_json_literal(case["input_sha256"], hashlib.sha256(compressed).hexdigest())
        _assert_exact_json_literal(case["framing"], literal["frame_descriptors"])
        _assert_exact_json_literal(case["output_hex"], literal["decompressed_hex"])
        decompressed = bytes.fromhex(literal["decompressed_hex"])
        assert len(decompressed) == literal["decompressed_bytes"]
        expected_dbn = {
            "complete_bytes": literal["decompressed_bytes"],
            "wire_spans": literal["wire_spans"],
            "wire_bodies": literal["wire_bodies"],
        }
        _assert_exact_json_literal(
            case["dbn_framing"], _literal_dbn_framing(expected_dbn, literals)
        )
        _assert_exact_json_literal(case["read_sizes"], (65536,) * (2 * literal["frame_count"]))
        # Each tell() is source read-through within its exact frame slice;
        # original compressed_start/end remain global only in frame_descriptors.
        _assert_exact_json_literal(
            case["frame_input_positions"],
            tuple(last - first for first, last, _start, _end in literal["frame_spans"]),
        )
        _assert_exact_json_literal(
            case["termination_checks"],
            tuple(
                {
                    "frame_ordinal": ordinal,
                    "max_output_size": last - first,
                    "read_across_frames": False,
                    "allow_extra_data": False,
                    "output_bytes": last - first,
                    "matches_stream_output": True,
                }
                for ordinal, (_start, _end, first, last) in enumerate(literal["frame_spans"], 1)
            ),
        )
        _assert_three_literal_dbn_partitions(
            case["partitions"],
            complete_bytes=literal["decompressed_bytes"],
            native_observations=literal["native_observations"],
        )
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_boundaries_child_complete_negative_controls_not_admission():
    """Codec-direct observations never admit a partial or substituted member."""
    literals = _load_registered_supplementary_literals("negative")
    negative_dbn = literals.DBN_NATIVE_NEGATIVE_CASES
    complete_prefix = literals.DBN_COMPLETE_PREFIX_IDENTITY_CASES
    assert type(negative_dbn) is tuple and len(negative_dbn) == 14
    assert type(complete_prefix) is tuple and len(complete_prefix) == 1
    expected_dbn = negative_dbn + complete_prefix
    assert len({case["case_id"] for case in expected_dbn}) == 15
    receipt, output = _run_registered_native("native_boundaries")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_boundaries")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "dbn_cases",
        "zstd_empty_cases",
        "zstd_terminal_cases",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_boundaries_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_negative_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], NEGATIVE_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "dbn": literals.DBN_DIRECT_POLICY,
            "zstd": {
                "backend": "cext",
                "read_across_frames": False,
                "read_size": 65536,
                "max_window_size_argument": 1048576,
                "independent_window_cap": 1048576,
                "cumulative_output_cap": 1048576,
                "compressed_input_cap": 262144,
                "frame_cap": 16,
            },
            "direct_controls_only": True,
            "provider_admission": False,
        },
    )
    dbn_cases = actual["dbn_cases"]
    assert type(dbn_cases) is list and len(dbn_cases) == 15
    assert len({case["case_id"] for case in dbn_cases}) == 15
    for index, (case, literal) in enumerate(zip(dbn_cases, expected_dbn, strict=True)):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "input_sha256",
            "held_whole_input_sha256",
            "physical_complete",
            "calls",
            "visible_observations",
            "constructor_calls",
            "provider_complete_result_allowed",
        }
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["complete_input_hex"])
        raw = bytes.fromhex(literal["complete_input_hex"])
        _assert_exact_json_literal(case["input_sha256"], hashlib.sha256(raw).hexdigest())
        assert "".join(literal["input_chunks_hex"]) == literal["complete_input_hex"]
        if index < 14:
            _assert_exact_json_literal(case["held_whole_input_sha256"], None)
            _assert_exact_json_literal(case["physical_complete"], False)
        else:
            held = bytes.fromhex(literal["held_whole_input_hex"])
            assert len(raw) == 184 and len(held) == 240 and raw != held
            assert literal["physical_input_is_complete"] is True
            assert literal["matches_held_whole_input"] is False
            assert literal["source_authentication_established"] is False
            _assert_exact_json_literal(
                case["held_whole_input_sha256"], hashlib.sha256(held).hexdigest()
            )
            assert case["input_sha256"] != case["held_whole_input_sha256"]
            _assert_exact_json_literal(case["physical_complete"], True)
        _assert_exact_json_literal(case["constructor_calls"], 1)
        _assert_exact_json_literal(case["provider_complete_result_allowed"], False)
        _assert_exact_json_literal(case["visible_observations"], literal["visible_observations"])
        calls = case["calls"]
        assert type(calls) is list and len(calls) == len(literal["calls"])
        for call, expected_call in zip(calls, literal["calls"], strict=True):
            assert type(call) is dict
            assert call.keys() == {
                "operation",
                "input_chunk_hex",
                "returned_observations",
                "error_class",
                "buffer_hex",
                "error_message",
            }
            assert expected_call.keys() == {
                "operation",
                "input_chunk_hex",
                "returned_observations",
                "error_class",
                "buffer_hex",
            }
            for name in (
                "operation",
                "input_chunk_hex",
                "returned_observations",
                "error_class",
                "buffer_hex",
            ):
                _assert_exact_json_literal(call[name], expected_call[name])
            if expected_call["error_class"] is None:
                _assert_exact_json_literal(call["error_message"], None)
            else:
                assert type(call["error_message"]) is str and call["error_message"]

    empty_cases = actual["zstd_empty_cases"]
    assert type(empty_cases) is list and len(empty_cases) == 3
    assert len({case["case_id"] for case in empty_cases}) == 3
    for case, literal, constructors in zip(
        empty_cases,
        literals.ZSTD_EMPTY_FRAME_CASES,
        (1, 1, 2),
        strict=True,
    ):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "framing",
            "direct_frame_output_hex",
            "profile_error_class",
            "profile_error_message",
            "profile_constructor_calls",
            "provider_complete_result_allowed",
        }
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["compressed_hex"])
        assert len(bytes.fromhex(literal["compressed_hex"])) == literal["compressed_bytes"]
        _assert_exact_json_literal(case["framing"], literal["framing"])
        _assert_exact_json_literal(case["direct_frame_output_hex"], literal["frame_output_hex"])
        assert "".join(case["direct_frame_output_hex"]) == literal["complete_output_hex"]
        _assert_exact_json_literal(case["profile_error_class"], "ValueError")
        assert type(case["profile_error_message"]) is str and case["profile_error_message"]
        _assert_exact_json_literal(case["profile_constructor_calls"], constructors)
        _assert_exact_json_literal(case["provider_complete_result_allowed"], False)

    terminal_cases = actual["zstd_terminal_cases"]
    assert type(terminal_cases) is list and len(terminal_cases) == 3
    assert len({case["case_id"] for case in terminal_cases}) == 3
    for case, literal in zip(terminal_cases, literals.ZSTD_TERMINAL_NEGATIVE_CASES, strict=True):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "constructor_kwargs",
            "decompress_kwargs",
            "returned_output_hex",
            "error_class",
            "error_message",
            "constructor_calls",
            "provider_complete_result_allowed",
        }
        for name, expected in (
            ("case_id", literal["case_id"]),
            ("input_hex", literal["compressed_hex"]),
            ("constructor_kwargs", literal["constructor_kwargs"]),
            ("decompress_kwargs", literal["decompress_kwargs"]),
            ("returned_output_hex", literal["returned_output_hex"]),
            ("error_class", literal["error_class"]),
            ("constructor_calls", 1),
            ("provider_complete_result_allowed", False),
        ):
            _assert_exact_json_literal(case[name], expected)
        # FORMAT_ZSTD1 is a fixed registered constant declaration, not a
        # caller-provided string passed as the native format integer.
        assert case["constructor_kwargs"]["format"] == "FORMAT_ZSTD1"
        assert type(case["error_message"]) is str and case["error_message"]
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_capacity_child_complete_metadata_and_position_boundaries():
    """Compare every at-cap body/span and native getter, not selected totals."""
    literals = _load_registered_supplementary_literals("capacity")
    positives = literals.DBN_CAPACITY_CASES
    assert type(positives) is tuple and len(positives) == 3
    assert len({case["case_id"] for case in positives}) == 3
    assert all(case["strict_profile_refusal"] is False for case in positives)
    receipt, output = _run_registered_native("native_capacity")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_capacity")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "strict_refusals",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_capacity_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], CAPACITY_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
    )
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 3
    assert len({case["case_id"] for case in cases}) == 3
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {"case_id", "input_hex", "input_sha256", "framing", "partitions"}
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["dbn_hex"])
        raw = bytes.fromhex(literal["dbn_hex"])
        assert len(raw) == literal["complete_bytes"]
        _assert_exact_json_literal(case["input_sha256"], hashlib.sha256(raw).hexdigest())
        _assert_exact_json_literal(
            case["framing"],
            {
                "complete_bytes": literal["complete_bytes"],
                "wire_spans": literal["wire_spans"],
                "wire_bodies": literal["wire_bodies"],
                "field_spans": literals.DBN_CAPACITY_FIELD_SPANS[literal["case_id"]],
            },
        )
        _assert_three_literal_dbn_partitions(
            case["partitions"],
            complete_bytes=literal["complete_bytes"],
            native_observations=literal["native_observations"],
        )
    _assert_exact_json_literal(actual["strict_refusals"], ())
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_zstd_partitions_child_full_source_reads_and_outputs():
    """Identical literal frame bytes retain identical complete outputs under partitioning."""
    literals = _load_registered_literal_oracles()
    requested_ids = (
        "raw_ab_known_single",
        "compressed_one_literal_and_repeat_one_match",
        "compressed_two_huffman_symbols_zero_sequences",
    )
    by_id = {case["case_id"]: case for case in literals.ZSTD_CASES}
    assert len(by_id) == len(literals.ZSTD_CASES)
    positives = tuple(by_id[case_id] for case_id in requested_ids)
    assert len(positives) == 3
    receipt, output = _run_registered_native("native_zstd_partitions")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_zstd_partitions")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_zstd_partitions_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], LITERAL_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(
        actual["policy"],
        {
            "zstd": {
                "backend": "cext",
                "read_across_frames": False,
                "read_size": 65536,
                "max_window_size_argument": 1048576,
                "independent_window_cap": 1048576,
                "cumulative_output_cap": 1048576,
                "compressed_input_cap": 262144,
                "frame_cap": 16,
            },
            "source_read_sizes": (1, 7, 65536),
        },
    )
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 3
    assert len({case["case_id"] for case in cases}) == 3
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {"case_id", "input_hex", "framing", "partitions"}
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["compressed_hex"])
        compressed = bytes.fromhex(literal["compressed_hex"])
        assert len(compressed) == literal["compressed_bytes"]
        descriptors = literals.ZSTD_FRAME_EXPECTATIONS[literal["case_id"]]
        _assert_exact_json_literal(case["framing"], descriptors)
        partitions = case["partitions"]
        assert type(partitions) is list and len(partitions) == 3
        for partition, read_size in zip(partitions, (1, 7, 65536), strict=True):
            assert type(partition) is dict
            assert partition.keys() == {
                "source_read_size",
                "output_hex",
                "read_sizes",
                "frame_input_positions",
                "termination_checks",
                "source_reads",
            }
            _assert_exact_json_literal(partition["source_read_size"], read_size)
            _assert_exact_json_literal(partition["output_hex"], literal["decompressed_hex"])
            _assert_exact_json_literal(partition["read_sizes"], (65536,) * (2 * len(descriptors)))
            _assert_exact_json_literal(
                partition["frame_input_positions"],
                tuple(frame[2] - frame[1] for frame in descriptors),
            )
            _assert_exact_json_literal(
                partition["termination_checks"],
                tuple(
                    {
                        "frame_ordinal": ordinal,
                        "max_output_size": last - first,
                        "read_across_frames": False,
                        "allow_extra_data": False,
                        "output_bytes": last - first,
                        "matches_stream_output": True,
                    }
                    for ordinal, (_start, _end, first, last) in enumerate(literal["frame_spans"], 1)
                ),
            )
            sources = partition["source_reads"]
            assert type(sources) is list and len(sources) == len(descriptors)
            for calls, descriptor in zip(sources, descriptors, strict=True):
                assert type(calls) is list and calls
                frame_bytes = compressed[descriptor[1] : descriptor[2]]
                offset = 0
                saw_empty = False
                for call in calls:
                    assert type(call) is dict and call.keys() == {"requested", "returned_hex"}
                    _assert_exact_json_literal(call["requested"], read_size)
                    expected_chunk = frame_bytes[offset : offset + read_size]
                    _assert_exact_json_literal(call["returned_hex"], expected_chunk.hex())
                    if expected_chunk:
                        assert saw_empty is False
                        offset += len(expected_chunk)
                    else:
                        # Only optional final empty reads are valid; their
                        # presence/count is an observed batching fact, not guessed.
                        assert offset == len(frame_bytes)
                        saw_empty = True
                assert offset == len(frame_bytes)
                assert "".join(call["returned_hex"] for call in calls) == frame_bytes.hex()
    _assert_final_identity_remeasurements(actual, actual["identity"])


def test_registered_native_zstd_capacity_child_complete_input_frame_and_cumulative_caps():
    """Exact complete capacities are literal, including cumulative cap-plus-one."""
    literals = _load_registered_supplementary_literals("zstd_capacity")
    positives = literals.ZSTD_CAPACITY_POSITIVE_CASES
    negatives = literals.ZSTD_CAPACITY_REFUSAL_CASES
    assert type(positives) is tuple and len(positives) == 2
    assert type(negatives) is tuple and len(negatives) == 1
    assert len({case["case_id"] for case in positives + negatives}) == 3
    receipt, output = _run_registered_native("native_zstd_capacity")
    print(
        json.dumps(
            {"receipt": receipt, "complete_output_utf8": output.decode("utf-8", errors="strict")},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    _assert_successful_owned_native_receipt(receipt, output, mode="native_zstd_capacity")
    assert output.endswith(b"\n") and len(output.splitlines()) == 1
    actual = json.loads(output, object_pairs_hook=_strict_json_pairs)
    assert type(actual) is dict
    assert actual.keys() == {
        "schema",
        "status",
        "oracle_sha256",
        "identity",
        "policy",
        "cases",
        "refusals",
        "artifacts_final",
        "loaded_final",
    }
    _assert_exact_json_literal(actual["schema"], "native_zstd_capacity_probe_v1")
    _assert_exact_json_literal(actual["status"], "constructed_native_observation_only")
    _assert_exact_json_literal(actual["oracle_sha256"], ZSTD_CAPACITY_ORACLE_SHA256)
    _assert_real_identity_complete(actual["identity"])
    _assert_exact_json_literal(actual["policy"], literals.EXPECTED_POLICY)
    cases = actual["cases"]
    assert type(cases) is list and len(cases) == 2
    assert len({case["case_id"] for case in cases}) == 2
    for case, literal in zip(cases, positives, strict=True):
        assert type(case) is dict
        assert case.keys() == {
            "case_id",
            "input_hex",
            "framing",
            "output_base64",
            "output_bytes",
            "read_sizes",
            "frame_input_positions",
            "termination_checks",
        }
        _assert_exact_json_literal(case["case_id"], literal["case_id"])
        _assert_exact_json_literal(case["input_hex"], literal["compressed_hex"])
        compressed = bytes.fromhex(literal["compressed_hex"])
        expected_output = bytes.fromhex(literal["decompressed_hex"])
        assert len(compressed) == literal["compressed_bytes"] <= 262144
        assert len(expected_output) == literal["decompressed_bytes"] <= 1048576
        assert len(literal["framing"]) == literal["frame_count"] <= 16
        _assert_exact_json_literal(case["framing"], literal["framing"])
        _assert_exact_json_literal(case["output_bytes"], literal["decompressed_bytes"])
        assert type(case["output_base64"]) is str
        encoded = case["output_base64"].encode("ascii", errors="strict")
        assert base64.b64decode(encoded, validate=True) == expected_output
        assert base64.b64encode(expected_output) == encoded
        # Derive exact requests solely from literal per-frame output lengths
        # and the public min(65536, remaining+1) request policy.
        expected_requests = []
        cumulative = 0
        for _start, _end, first, last in literal["frame_spans"]:
            frame_remaining = last - first
            assert type(frame_remaining) is int and frame_remaining > 0
            while frame_remaining:
                request = min(65536, 1048576 - cumulative + 1)
                expected_requests.append(request)
                produced = min(request, frame_remaining)
                cumulative += produced
                frame_remaining -= produced
            expected_requests.append(min(65536, 1048576 - cumulative + 1))
        assert cumulative == len(expected_output)
        assert tuple(expected_requests) == literal["expected_read_sizes"]
        _assert_exact_json_literal(case["read_sizes"], literal["expected_read_sizes"])
        _assert_exact_json_literal(
            case["frame_input_positions"],
            literal["expected_frame_input_positions"],
        )
        _assert_exact_json_literal(case["termination_checks"], literal["termination_checks"])

    refusals = actual["refusals"]
    assert type(refusals) is list and len(refusals) == 1
    literal = negatives[0]
    case = refusals[0]
    assert type(case) is dict
    assert case.keys() == {
        "case_id",
        "input_hex",
        "phase",
        "constructor_calls",
        "error_type",
        "error_message",
        "observed_output_bytes",
    }
    assert len(bytes.fromhex(literal["compressed_hex"])) == literal["compressed_bytes"] == 160
    assert (
        len(bytes.fromhex(literal["decompressed_hex"])) == literal["decompressed_bytes"] == 1048577
    )
    assert literal["frame_count"] == 16
    assert literal["provider_complete_result_allowed"] is False
    for name, expected in (
        ("case_id", literal["case_id"]),
        ("input_hex", literal["compressed_hex"]),
        ("phase", "native_output_limit"),
        ("constructor_calls", 16),
        ("error_type", "OutputLimitExceeded"),
        ("observed_output_bytes", 1048577),
    ):
        _assert_exact_json_literal(case[name], expected)
    assert type(case["error_message"]) is str and case["error_message"]
    _assert_final_identity_remeasurements(actual, actual["identity"])
