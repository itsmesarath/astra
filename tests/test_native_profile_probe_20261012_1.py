"""Independent control expectations for the registered native-proof harness."""

import hashlib
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "native_profile_containment_20261012_1",
    ROOT / "scripts/native_profile_containment_20261012_1.py",
)
CONTAINMENT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CONTAINMENT
SPEC.loader.exec_module(CONTAINMENT)
PYTHON = "C:/Users/pabta/AppData/Local/Programs/Python/Python312/python.exe"
PYTHON_SHA = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
PROBE = ROOT / "scripts/native_profile_probe_20261012_1.py"
PROBE_SPEC = importlib.util.spec_from_file_location("native_profile_probe_20261012_1", PROBE)
PROBE_MODULE = importlib.util.module_from_spec(PROBE_SPEC)
sys.modules[PROBE_SPEC.name] = PROBE_MODULE
PROBE_SPEC.loader.exec_module(PROBE_MODULE)
ORACLE_SPEC = importlib.util.spec_from_file_location(
    "native_profile_oracles_20261012_1",
    ROOT / "tests/native_profile_oracles_20261012_1.py",
)
ORACLES = importlib.util.module_from_spec(ORACLE_SPEC)
sys.modules[ORACLE_SPEC.name] = ORACLES
ORACLE_SPEC.loader.exec_module(ORACLES)
EXPECTED_LIMITS = {
    "limit_flags": 0x230E,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
}
OUTPUT_LIMIT = 4194304
DEADLINE_ENV = "AI_TRADER_NATIVE_PROOF_TEST_HARD_END_UTC"
FIXED_STUB_CONTROLS = (
    "stub_success",
    "stub_timeout",
    "stub_memory",
    "stub_crash",
    "stub_output",
)


def _deadline_for_control(mode):
    if DEADLINE_ENV in os.environ:
        return os.environ[DEADLINE_ENV], "registered_environment"
    if mode not in FIXED_STUB_CONTROLS:
        raise ValueError("only fixed harmless unit controls may use a local deadline")
    return (
        (datetime.now(UTC) + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fixed_stub_unit_utc_plus_60s",
    )


def _run(mode, *, python_sha=PYTHON_SHA, script_sha=None):
    hard_end_utc, deadline_origin = _deadline_for_control(mode)
    receipt, output = CONTAINMENT.run_owned_case(
        python_exe=PYTHON,
        expected_python_sha256=python_sha,
        script_path=str(PROBE),
        expected_script_sha256=(
            hashlib.sha256(PROBE.read_bytes()).hexdigest() if script_sha is None else script_sha
        ),
        script_args=(mode,),
        case_id=mode,
        hard_end_utc=hard_end_utc,
    )
    print(
        json.dumps(
            {
                "receipt": receipt,
                "deadline_origin": deadline_origin,
                "output_hex": output.hex() if len(output) <= 4096 else None,
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    )
    return receipt, output


def _assert_output_receipt(receipt, output, *, complete):
    assert type(output) is bytes
    assert type(receipt["output_bytes"]) is int
    assert receipt["output_bytes"] == len(output)
    assert receipt["output_sha256"] == hashlib.sha256(output).hexdigest()
    assert receipt["output_complete"] is complete
    assert receipt["output_hash_scope"] == ("complete_stream" if complete else "retained_prefix")


def _assert_owned_exit(receipt):
    assert receipt["created"] is True
    assert receipt["resumed"] is True
    assert receipt["in_job_before_resume"] is True
    assert type(receipt["resume_previous_count"]) is int
    assert receipt["resume_previous_count"] == 1
    assert receipt["configured_limits"] == EXPECTED_LIMITS
    assert receipt["queried_limits"] == EXPECTED_LIMITS
    for limits in (receipt["configured_limits"], receipt["queried_limits"]):
        assert all(type(value) is int for value in limits.values())
    assert type(receipt["child_pid"]) is int
    assert receipt["child_pid"] > 0
    assert receipt["child_pid"] != os.getpid()
    assert receipt["job_process_ids_initial"] == []
    assert receipt["job_process_ids_before_resume"] == [receipt["child_pid"]]
    assert receipt["job_process_ids_final"] == []
    assert receipt["parent_pid"] == os.getpid()
    assert receipt["child_parent_pid"] == os.getpid()
    assert receipt["child_image"].replace("\\", "/").casefold() == PYTHON.casefold()
    assert type(receipt["parent_creation_filetime"]) is int
    assert type(receipt["child_creation_filetime"]) is int
    assert 0 < receipt["parent_creation_filetime"] <= receipt["child_creation_filetime"]
    assert receipt["process_exited"] is True
    assert type(receipt["exit_code"]) is int
    assert type(receipt["final_active_processes"]) is int
    assert receipt["final_active_processes"] == 0
    assert receipt["cleanup_errors"] == []
    assert type(receipt["job_accounting"]) is dict
    assert receipt["job_accounting_initial"]["active_processes"] == 0
    assert receipt["job_accounting_before_resume"]["active_processes"] == 1
    assert receipt["job_accounting"]["active_processes"] == 0
    for key in ("peak_process_memory_bytes", "peak_job_memory_bytes"):
        assert type(receipt[key]) is int
        assert 0 <= receipt[key] <= 268435456
    assert receipt["work_seconds"] == 12.0
    assert receipt["total_seconds"] == 15.0
    assert receipt["output_limit_bytes"] == OUTPUT_LIMIT
    assert receipt["read_chunk_bytes"] == 65536
    assert receipt["kill_on_job_close_queried"] is True
    assert receipt["parent_death_empirically_tested"] is False
    assert receipt["native_codec_imported"] is False
    assert receipt["native_profile_closed"] is False


def _assert_one_print_line(output, literal):
    assert output in (literal + b"\n", literal + b"\r\n")


def test_missing_process_birth_containment_behavior():
    receipt, output = _run("stub_success")
    assert receipt["disposition"] == "completed"
    assert receipt["exit_code"] == 0
    assert receipt["in_job_before_resume"] is True
    assert receipt["resume_previous_count"] == 1
    assert output.rstrip(b"\r\n") == b'{"control":"success"}'
    _assert_one_print_line(output, b'{"control":"success"}')
    _assert_output_receipt(receipt, output, complete=True)
    _assert_owned_exit(receipt)


def test_sleeping_owned_control_is_terminated_and_waited():
    receipt, output = _run("stub_timeout")
    assert receipt["disposition"] == "timeout"
    assert receipt["exit_code"] != 0
    assert type(receipt["termination_reason"]) is str
    assert receipt["termination_reason"]
    assert output == b""
    _assert_output_receipt(receipt, output, complete=False)
    _assert_owned_exit(receipt)


def test_attempted_512_mib_allocation_is_refused_under_256_mib_job():
    receipt, output = _run("stub_memory")
    assert receipt["disposition"] == "completed"
    assert receipt["exit_code"] == 0
    _assert_one_print_line(output, b'{"control":"allocation_refused"}')
    _assert_output_receipt(receipt, output, complete=True)
    _assert_owned_exit(receipt)


def test_real_exit_17_is_retained_not_reported_as_success():
    receipt, output = _run("stub_crash")
    assert receipt["disposition"] == "nonzero_exit"
    assert receipt["exit_code"] == 17
    assert output == b""
    _assert_output_receipt(receipt, output, complete=True)
    _assert_owned_exit(receipt)


def test_excess_output_is_retained_only_as_bounded_incomplete_prefix():
    receipt, output = _run("stub_output")
    assert receipt["disposition"] == "output_limit"
    assert 0 < len(output) <= OUTPUT_LIMIT
    assert output == b"x" * len(output)
    assert type(receipt["termination_reason"]) is str
    assert receipt["termination_reason"]
    _assert_output_receipt(receipt, output, complete=False)
    _assert_owned_exit(receipt)


@pytest.mark.parametrize("pin", ("python", "script"))
def test_wrong_executable_or_script_pin_refuses_before_process_creation(monkeypatch, pin):
    def forbidden_create(*args, **kwargs):
        raise AssertionError("process creation reached after incorrect held pin")

    monkeypatch.setattr(CONTAINMENT, "_create_process", forbidden_create)
    overrides = {"python_sha": "0" * 64} if pin == "python" else {"script_sha": "0" * 64}
    receipt, output = _run("stub_success", **overrides)
    assert receipt["disposition"] == "setup_refused"
    assert receipt["created"] is False
    assert receipt["resumed"] is False
    assert receipt["child_pid"] is None
    assert receipt["exit_code"] is None
    assert output == b""
    assert receipt["output_bytes"] == 0
    assert receipt["output_sha256"] == hashlib.sha256(b"").hexdigest()


def test_successful_verified_job_termination_does_not_race_process_fallback():
    calls = []

    class FakeApi:
        @staticmethod
        def TerminateJobObject(job, code):
            calls.append(("job", job, code))
            return True

        @staticmethod
        def WaitForSingleObject(process, timeout):
            return 258

        @staticmethod
        def TerminateProcess(process, code):
            raise AssertionError("redundant process termination raced successful job termination")

    result = CONTAINMENT._terminate_owned(FakeApi(), 101, 202, in_job=True)
    print(json.dumps({"termination_regression": result}, sort_keys=True, allow_nan=False))
    assert len(calls) == 1
    assert calls[0][0:2] == ("job", 101)
    assert result == {
        "job_succeeded": True,
        "job_error": None,
        "process_fallback_requested": False,
        "process_succeeded": None,
        "process_error": None,
    }


DBN_POSITIVE_CASES = tuple(case for case in ORACLES.DBN_CASES if not case["strict_profile_refusal"])


def _assert_exact_literal_tree(actual, expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual) == set(expected)
        for key in expected:
            _assert_exact_literal_tree(actual[key], expected[key])
    elif type(expected) is tuple:
        assert len(actual) == len(expected)
        for value, literal in zip(actual, expected, strict=True):
            _assert_exact_literal_tree(value, literal)
    else:
        assert actual == expected


def _expected_dbn_field_spans(case):
    metadata_end = case["wire_spans"][0][2]
    if metadata_end == 128:
        variable = ORACLES.MINIMAL_VARIABLE_SPANS
    elif metadata_end == 872:
        variable = ORACLES.RICH_VARIABLE_SPANS
    else:
        raise AssertionError("unregistered independent metadata field span oracle")
    fields = [ORACLES.METADATA_FIXED_SPANS + variable]
    for (_, start, _), body in zip(case["wire_spans"][1:], case["wire_bodies"][1:], strict=True):
        relative = (
            ORACLES.MBO_BASE_FIELD_SPANS
            if body["ts_out"] is None
            else ORACLES.MBO_PRESENT_TS_OUT_FIELD_SPANS
        )
        fields.append(tuple((name, start + first, start + last) for name, first, last in relative))
    return tuple(fields)


@pytest.mark.parametrize("case", DBN_POSITIVE_CASES, ids=lambda case: case["case_id"])
def test_dbn_framing_preserves_complete_literal_wire_bodies_and_spans(case):
    member = bytes.fromhex(case["dbn_hex"])
    result = PROBE_MODULE.inspect_dbn_wire(member)
    assert type(result) is dict
    assert set(result) == {"complete_bytes", "wire_spans", "wire_bodies", "field_spans"}
    assert result["complete_bytes"] == case["complete_bytes"] == len(member)
    assert type(result["complete_bytes"]) is int
    assert result["wire_spans"] == case["wire_spans"]
    assert result["wire_bodies"] == case["wire_bodies"]
    _assert_exact_literal_tree(result["wire_bodies"], case["wire_bodies"])
    assert result["field_spans"] == _expected_dbn_field_spans(case)
    assert type(result["wire_spans"]) is tuple
    assert type(result["wire_bodies"]) is tuple
    assert type(result["field_spans"]) is tuple
    for (kind, start, end), fields, expected_body, actual_body in zip(
        result["wire_spans"],
        result["field_spans"],
        case["wire_bodies"],
        result["wire_bodies"],
        strict=True,
    ):
        assert kind in ("Metadata", "MBO")
        assert set(actual_body) == set(expected_body)
        assert type(fields) is tuple
        cursor = start
        for name, first, last in fields:
            assert type(name) is str
            assert type(first) is type(last) is int
            assert first == cursor
            assert first < last <= end
            cursor = last
        assert cursor == end


@pytest.mark.parametrize(
    "case_id,literal_hex",
    ORACLES.DBN_FRAMING_NEGATIVE_CASES,
    ids=[case[0] for case in ORACLES.DBN_FRAMING_NEGATIVE_CASES],
)
def test_dbn_framing_refuses_complete_named_malformed_candidates(case_id, literal_hex):
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(bytes.fromhex(literal_hex))


def test_dbn_framing_refuses_duplicate_original_wire_mapping_keys():
    case = next(
        case for case in ORACLES.DBN_CASES if case["case_id"] == "duplicate_wire_mapping_groups"
    )
    assert case["strict_profile_refusal"] is True
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(bytes.fromhex(case["dbn_hex"]))


@pytest.mark.parametrize("case", ORACLES.DBN_STYPE_CASES, ids=lambda case: case["case_id"])
def test_dbn_framing_preserves_all_source_defined_stype_wire_codes(case):
    member = bytes.fromhex(case["dbn_hex"])
    result = PROBE_MODULE.inspect_dbn_wire(member)
    _assert_exact_literal_tree(
        result,
        {
            "complete_bytes": case["complete_bytes"],
            "wire_spans": case["wire_spans"],
            "wire_bodies": case["wire_bodies"],
            "field_spans": _expected_dbn_field_spans(case),
        },
    )


@pytest.mark.parametrize(
    "case_id,literal_hex",
    ORACLES.DBN_STYPE_NEGATIVE_CASES,
    ids=[case[0] for case in ORACLES.DBN_STYPE_NEGATIVE_CASES],
)
def test_dbn_framing_refuses_undefined_stype_wire_codes(case_id, literal_hex):
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(bytes.fromhex(literal_hex))


@pytest.mark.parametrize("case", ORACLES.ZSTD_CASES, ids=lambda case: case["case_id"])
def test_zstd_framing_preserves_complete_literal_physical_frame_descriptors(case):
    member = bytes.fromhex(case["compressed_hex"])
    frames = PROBE_MODULE.inspect_zstd_frames(member)
    _assert_exact_literal_tree(frames, ORACLES.ZSTD_FRAME_EXPECTATIONS[case["case_id"]])
    cursor = 0
    for ordinal, frame in enumerate(frames, 1):
        assert len(frame) == 16 == len(ORACLES.ZSTD_FRAME_FIELDS)
        assert frame[0] == ordinal
        assert frame[1] == frame[3] == cursor
        assert frame[3] < frame[4] <= frame[2]
        block_cursor = frame[4]
        for block_ordinal, block in enumerate(frame[15], 1):
            assert len(block) == 8 == len(ORACLES.ZSTD_BLOCK_FIELDS)
            assert block[0] == block_ordinal
            assert block[1] == block_cursor
            assert block[2] == block[1] + 3 == block[6]
            assert block[6] <= block[7] <= frame[2]
            block_cursor = block[7]
        assert frame[15][-1][3] is True
        assert all(block[3] is False for block in frame[15][:-1])
        assert block_cursor + (4 if frame[10] else 0) == frame[2]
        cursor = frame[2]
    assert cursor == len(member) == case["compressed_bytes"]


@pytest.mark.parametrize(
    "case",
    ORACLES.ZSTD_STRICT_FORMAT_NEGATIVE_CASES,
    ids=lambda case: case["case_id"],
)
def test_zstd_framing_refuses_strict_format_truncation_tail_and_skippable_candidates(case):
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_zstd_frames(bytes.fromhex(case["compressed_hex"]))


@pytest.mark.parametrize("case", ORACLES.ZSTD_RESOURCE_CASES, ids=lambda case: case["case_id"])
def test_zstd_physical_framing_separates_known_size_refusal_from_unknown_output_capacity(case):
    member = bytes.fromhex(case["compressed_hex"])
    if case["case_id"] == "known_one_mib_plus_one":
        with pytest.raises(ValueError):
            PROBE_MODULE.inspect_zstd_frames(member)
    else:
        _assert_exact_literal_tree(
            PROBE_MODULE.inspect_zstd_frames(member),
            ORACLES.ZSTD_FRAME_EXPECTATIONS[case["case_id"]],
        )
    # Unknown+1 is physically complete. Its cumulative decoded-output refusal
    # is a later contained native reader obligation, not invented framing EOF.


def test_generic_future_utc_deadline_allows_the_fixed_owned_unit_control(monkeypatch):
    future = (datetime.now(UTC) + timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    monkeypatch.setenv(DEADLINE_ENV, future)
    receipt, output = _run("stub_success")
    assert receipt["hard_end_utc"] == future
    assert receipt["disposition"] == "completed"
    _assert_one_print_line(output, b'{"control":"success"}')
    _assert_output_receipt(receipt, output, complete=True)
    _assert_owned_exit(receipt)


@pytest.mark.parametrize(
    "deadline",
    (
        "",
        "not-a-utc-deadline",
        "2026-01-01T00:00:00Z",
        "2026-10-12T19:59:46+00:00",
        "2026-10-12T19:59:46.000Z",
    ),
)
def test_present_invalid_or_expired_deadline_never_falls_back_or_creates(monkeypatch, deadline):
    def forbidden_create(*args, **kwargs):
        raise AssertionError("invalid or expired deadline reached process creation")

    monkeypatch.setenv(DEADLINE_ENV, deadline)
    monkeypatch.setattr(CONTAINMENT, "_create_process", forbidden_create)
    assert _deadline_for_control("stub_success") == (deadline, "registered_environment")
    receipt, output = _run("stub_success")
    assert receipt["hard_end_utc"] == deadline
    assert receipt["disposition"] == "setup_refused"
    assert receipt["created"] is False
    assert receipt["resumed"] is False
    assert receipt["child_pid"] is None
    assert output == b""


def test_only_fixed_stub_unit_controls_have_a_local_future_deadline(monkeypatch):
    monkeypatch.delenv(DEADLINE_ENV, raising=False)
    before = datetime.now(UTC)
    deadline, origin = _deadline_for_control("stub_success")
    after = datetime.now(UTC)
    parsed = datetime.strptime(deadline, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert before + timedelta(seconds=59) <= parsed <= after + timedelta(seconds=60)
    assert origin == "fixed_stub_unit_utc_plus_60s"
    with pytest.raises(ValueError):
        _deadline_for_control("native_decode")


class _BytesAlias(bytes):
    pass


@pytest.mark.parametrize("parser_name", ("inspect_dbn_wire", "inspect_zstd_frames"))
@pytest.mark.parametrize(
    "value",
    (
        None,
        False,
        1,
        "literal bytes",
        bytearray(b"literal"),
        memoryview(b"literal"),
        _BytesAlias(b"literal"),
        [1, 2],
        b"",
    ),
    ids=(
        "none",
        "bool",
        "int",
        "text",
        "bytearray",
        "memoryview",
        "bytes_subclass",
        "list",
        "empty",
    ),
)
def test_framing_requires_exact_nonempty_bytes_without_input_coercion(parser_name, value):
    with pytest.raises(ValueError):
        getattr(PROBE_MODULE, parser_name)(value)


@pytest.mark.parametrize("case", DBN_POSITIVE_CASES, ids=lambda case: case["case_id"])
def test_dbn_all_shorter_prefixes_distinguish_complete_records_from_incomplete_bytes(case):
    member = bytes.fromhex(case["dbn_hex"])
    complete_ends = {
        span[2]: index + 1 for index, span in enumerate(case["wire_spans"]) if index > 0
    }
    field_spans = _expected_dbn_field_spans(case)
    for cut in range(len(member)):
        if cut in complete_ends:
            count = complete_ends[cut]
            _assert_exact_literal_tree(
                PROBE_MODULE.inspect_dbn_wire(member[:cut]),
                {
                    "complete_bytes": cut,
                    "wire_spans": case["wire_spans"][:count],
                    "wire_bodies": case["wire_bodies"][:count],
                    "field_spans": field_spans[:count],
                },
            )
            assert hashlib.sha256(member[:cut]).digest() != hashlib.sha256(member).digest()
        else:
            with pytest.raises(ValueError):
                PROBE_MODULE.inspect_dbn_wire(member[:cut])
    # An exact complete record prefix is a different valid member; only an
    # independently held whole-member pin/count can detect that substitution.


@pytest.mark.parametrize("case", ORACLES.ZSTD_CASES, ids=lambda case: case["case_id"])
def test_zstd_all_shorter_prefixes_distinguish_complete_frames_from_incomplete_bytes(case):
    member = bytes.fromhex(case["compressed_hex"])
    expected = ORACLES.ZSTD_FRAME_EXPECTATIONS[case["case_id"]]
    complete_ends = {frame[2]: index + 1 for index, frame in enumerate(expected)}
    for cut in range(len(member)):
        if cut in complete_ends:
            _assert_exact_literal_tree(
                PROBE_MODULE.inspect_zstd_frames(member[:cut]),
                expected[: complete_ends[cut]],
            )
            assert hashlib.sha256(member[:cut]).digest() != hashlib.sha256(member).digest()
        else:
            with pytest.raises(ValueError):
                PROBE_MODULE.inspect_zstd_frames(member[:cut])


def _replace_literal_bytes(member, offset, replacement):
    return member[:offset] + replacement + member[offset + len(replacement) :]


DBN_BAD_FIELD_CASES = (
    ("magic", False, 0, b"DBX"),
    ("version", False, 3, b"\x02"),
    ("short_header_length", False, 4, b"\x77\x00\x00\x00"),
    ("misaligned_header_length", False, 4, b"\x79\x00\x00\x00"),
    ("dataset_without_terminator", False, 8, b"A" * 16),
    ("dataset_non_utf8", False, 8, b"\xff"),
    ("dataset_nonzero_cstring_padding", False, 23, b"\x01"),
    ("schema_not_mbo", False, 24, b"\x01\x00"),
    ("schema_null_not_mbo", False, 24, b"\xff\xff"),
    ("ts_out_not_bool_wire_byte", False, 52, b"\x02"),
    ("symbol_width_not_v3_71", False, 53, b"\x46\x00"),
    ("nonzero_reserved", False, 55, b"\x01"),
    ("unsupported_schema_definition", False, 108, b"\x01\x00\x00\x00"),
    ("symbol_count_excess", False, 112, b"\x11\x00\x00\x00"),
    ("partial_count_excess", False, 116, b"\x11\x00\x00\x00"),
    ("not_found_count_excess", False, 120, b"\x11\x00\x00\x00"),
    ("mapping_count_excess", False, 124, b"\x11\x00\x00\x00"),
    ("rich_symbol_non_utf8", True, 116, b"\xff"),
    ("rich_symbol_nonzero_cstring_padding", True, 119, b"\x01"),
    ("mapping_start_date_zero", True, 558, b"\x00" * 4),
    ("mapping_end_date_invalid_month", True, 562, (20261301).to_bytes(4, "little")),
    ("mapping_symbol_no_terminator", True, 566, b"A" * 71),
    ("alignment_padding_nonzero", True, 871, b"\x01"),
    ("final_record_rtype_unsupported", False, 185, b"\x00"),
    ("final_record_length_zero", False, 184, b"\x00"),
)


@pytest.mark.parametrize(
    "case_id,rich,offset,replacement",
    DBN_BAD_FIELD_CASES,
    ids=[case[0] for case in DBN_BAD_FIELD_CASES],
)
def test_dbn_framing_refuses_noncanonical_complete_field_candidates(
    case_id, rich, offset, replacement
):
    header = ORACLES.RICH_METADATA_FALSE_HEX if rich else ORACLES.MINIMAL_METADATA_FALSE_HEX
    member = bytes.fromhex(header + ORACLES.TARGET_MBO_FALSE_HEX + ORACLES.FOREIGN_MBO_FALSE_HEX)
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(_replace_literal_bytes(member, offset, replacement))


def test_dbn_exact_position_capacity_and_first_excess_preserve_every_record():
    header = bytes.fromhex(ORACLES.MINIMAL_METADATA_FALSE_HEX)
    record = bytes.fromhex(ORACLES.TARGET_MBO_FALSE_HEX)
    member = header + record * 127
    result = PROBE_MODULE.inspect_dbn_wire(member)
    expected_spans = (("Metadata", 0, 128),) + tuple(
        ("MBO", 128 + index * 56, 128 + (index + 1) * 56) for index in range(127)
    )
    expected_fields = (ORACLES.METADATA_FIXED_SPANS + ORACLES.MINIMAL_VARIABLE_SPANS,) + tuple(
        tuple(
            (name, 128 + index * 56 + first, 128 + index * 56 + last)
            for name, first, last in ORACLES.MBO_BASE_FIELD_SPANS
        )
        for index in range(127)
    )
    _assert_exact_literal_tree(
        result,
        {
            "complete_bytes": 7240,
            "wire_spans": expected_spans,
            "wire_bodies": (ORACLES.MINIMAL_METADATA_WIRE_FALSE,)
            + (ORACLES.TARGET_WIRE_FALSE,) * 127,
            "field_spans": expected_fields,
        },
    )
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(member + record)


def test_dbn_outer_byte_and_header_caps_refuse_before_metadata_traversal(monkeypatch):
    def forbidden_metadata(*args, **kwargs):
        raise AssertionError("oversized complete input or header traversed metadata")

    monkeypatch.setattr(PROBE_MODULE, "_metadata_wire", forbidden_metadata)
    header = bytes.fromhex(ORACLES.MINIMAL_METADATA_FALSE_HEX)
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(header + b"\x00" * (1048577 - len(header)))
    # Declared header bytes65544, body65536, fully supplied: one step beyond
    # the separate65536 complete-header cap, not a short-input surrogate.
    oversized_header = _replace_literal_bytes(header, 4, b"\x00\x00\x01\x00")
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_dbn_wire(oversized_header + b"\x00" * (65544 + 56 - len(header)))


def _complete_metadata_fixture(variable_bytes):
    # Independent layout assembly: the held112-byte fixed prefix, then the
    # explicit literal count/C-string/mapping bytes below, then zero alignment.
    prefix = bytes.fromhex(ORACLES.MINIMAL_METADATA_FALSE_HEX)[:112]
    complete = prefix + variable_bytes
    complete += b"\x00" * (-len(complete) % 8)
    return _replace_literal_bytes(complete, 4, (len(complete) - 8).to_bytes(4, "little"))


@pytest.mark.parametrize("count", (16, 17))
def test_dbn_complete_symbol_list_at_limit_and_first_excess(count):
    symbol = b"AA\x00" + b"\x00" * 68
    variable = count.to_bytes(4, "little") + symbol * count + b"\x00" * 12
    header = _complete_metadata_fixture(variable)
    member = header + bytes.fromhex(ORACLES.TARGET_MBO_FALSE_HEX)
    if count == 17:
        with pytest.raises(ValueError):
            PROBE_MODULE.inspect_dbn_wire(member)
    else:
        result = PROBE_MODULE.inspect_dbn_wire(member)
        _assert_exact_literal_tree(
            result["wire_bodies"],
            (
                {
                    **ORACLES.MINIMAL_METADATA_WIRE_FALSE,
                    "length_body": 1256,
                    "symbols_count": 16,
                    "symbols": ("AA",) * 16,
                },
                ORACLES.TARGET_WIRE_FALSE,
            ),
        )
        assert result["wire_spans"] == (("Metadata", 0, 1264), ("MBO", 1264, 1320))


@pytest.mark.parametrize("count", (16, 17))
def test_dbn_complete_distinct_mapping_groups_at_limit_and_first_excess(count):
    groups = tuple(
        (f"{index:02d}".encode("ascii") + b"\x00" * 69 + b"\x00" * 4) for index in range(count)
    )
    header = _complete_metadata_fixture(
        b"\x00" * 12 + count.to_bytes(4, "little") + b"".join(groups)
    )
    member = header + bytes.fromhex(ORACLES.TARGET_MBO_FALSE_HEX)
    if count == 17:
        with pytest.raises(ValueError):
            PROBE_MODULE.inspect_dbn_wire(member)
    else:
        mappings = tuple(
            {"raw_symbol": f"{index:02d}", "interval_count": 0, "intervals": ()}
            for index in range(16)
        )
        result = PROBE_MODULE.inspect_dbn_wire(member)
        _assert_exact_literal_tree(
            result["wire_bodies"],
            (
                {
                    **ORACLES.MINIMAL_METADATA_WIRE_FALSE,
                    "length_body": 1320,
                    "mappings_count": 16,
                    "mappings": mappings,
                },
                ORACLES.TARGET_WIRE_FALSE,
            ),
        )
        assert result["wire_spans"] == (("Metadata", 0, 1328), ("MBO", 1328, 1384))


@pytest.mark.parametrize("count", (32, 33))
def test_dbn_complete_mapping_intervals_at_limit_and_first_excess(count):
    interval = bytes.fromhex("9428350195283501") + b"2\x00" + b"\x00" * 69
    group = b"AA\x00" + b"\x00" * 68 + count.to_bytes(4, "little") + interval * count
    header = _complete_metadata_fixture(b"\x00" * 12 + b"\x01\x00\x00\x00" + group)
    member = header + bytes.fromhex(ORACLES.TARGET_MBO_FALSE_HEX)
    if count == 33:
        with pytest.raises(ValueError):
            PROBE_MODULE.inspect_dbn_wire(member)
    else:
        result = PROBE_MODULE.inspect_dbn_wire(member)
        mappings = (
            {
                "raw_symbol": "AA",
                "interval_count": 32,
                "intervals": ({"start_date": 20261012, "end_date": 20261013, "symbol": "2"},) * 32,
            },
        )
        _assert_exact_literal_tree(
            result["wire_bodies"],
            (
                {
                    **ORACLES.MINIMAL_METADATA_WIRE_FALSE,
                    "length_body": 2728,
                    "mappings_count": 1,
                    "mappings": mappings,
                    "alignment_padding_bytes": (0,) * 5,
                },
                ORACLES.TARGET_WIRE_FALSE,
            ),
        )
        assert result["wire_spans"] == (("Metadata", 0, 2736), ("MBO", 2736, 2792))


ZSTD_BAD_STRUCTURE_CASES = (
    ("wrong_magic", "28b52ffc20021100004142"),
    ("reserved_descriptor_bit", "28b52ffd28021100004142"),
    ("unused_descriptor_bit", "28b52ffd30021100004142"),
    ("one_byte_dictionary_zero", "28b52ffd2100021100004142"),
    ("two_byte_dictionary_zero", "28b52ffd220000021100004142"),
    ("four_byte_dictionary_zero", "28b52ffd2300000000021100004142"),
    ("one_byte_dictionary_nonzero", "28b52ffd2101021100004142"),
    ("window_first_excess", "28b52ffd00511100004142"),
    ("reserved_block_type", "28b52ffd20021700004142"),
    ("missing_last_block", "28b52ffd20021000004142"),
    ("raw_block_exceeds_single_window", "28b52ffd2002190000414243"),
)


@pytest.mark.parametrize(
    "case_id,literal_hex",
    ZSTD_BAD_STRUCTURE_CASES,
    ids=[case[0] for case in ZSTD_BAD_STRUCTURE_CASES],
)
def test_zstd_physical_framing_refuses_forbidden_complete_structural_candidates(
    case_id, literal_hex
):
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_zstd_frames(bytes.fromhex(literal_hex))


def _shift_physical_frame(frame, ordinal, offset):
    blocks = tuple(
        (
            block[0],
            block[1] + offset,
            block[2] + offset,
            *block[3:6],
            block[6] + offset,
            block[7] + offset,
        )
        for block in frame[15]
    )
    return (
        ordinal,
        frame[1] + offset,
        frame[2] + offset,
        frame[3] + offset,
        frame[4] + offset,
        *frame[5:15],
        blocks,
    )


def test_zstd_exact_frame_capacity_and_first_excess_keep_all_physical_frames():
    frame_bytes = bytes.fromhex("28b52ffd20021100004142")
    literal = ORACLES.ZSTD_FRAME_EXPECTATIONS["raw_ab_known_single"][0]
    expected = tuple(_shift_physical_frame(literal, index + 1, index * 11) for index in range(16))
    _assert_exact_literal_tree(PROBE_MODULE.inspect_zstd_frames(frame_bytes * 16), expected)
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_zstd_frames(frame_bytes * 17)


@pytest.mark.parametrize("excess", (False, True))
def test_zstd_complete_compressed_member_exact_byte_cap_and_first_excess(excess):
    # Two RAW blocks, independently assembled from the frame/block format.
    # At the cap:9header +3+131072 +3+131057 =262144bytes.
    header = bytes.fromhex("28b52ffda0f2ff0300" if excess else "28b52ffda0f1ff0300")
    final_block_header = bytes.fromhex("91ff0f" if excess else "89ff0f")
    member = (
        header
        + bytes.fromhex("000010")
        + b"A" * 131072
        + final_block_header
        + b"B" * (131058 if excess else 131057)
    )
    assert len(member) == (262145 if excess else 262144)
    if excess:
        with pytest.raises(ValueError):
            PROBE_MODULE.inspect_zstd_frames(member)
    else:
        expected = (
            (
                1,
                0,
                262144,
                0,
                9,
                160,
                None,
                2,
                True,
                0,
                False,
                262129,
                262129,
                None,
                None,
                (
                    (1, 9, 12, False, 0, 131072, 12, 131084),
                    (2, 131084, 131087, True, 0, 131057, 131087, 262144),
                ),
            ),
        )
        _assert_exact_literal_tree(PROBE_MODULE.inspect_zstd_frames(member), expected)


@pytest.mark.parametrize(
    "block_type,block_header,payload",
    (
        (0, "090010", b"A" * 131073),
        (1, "0b0010", b"A"),
        (2, "0d0010", b"\x00" * 131073),
    ),
    ids=("raw", "rle", "compressed"),
)
def test_zstd_each_block_type_first_excess_block_size_refuses(block_type, block_header, payload):
    member = bytes.fromhex("28b52ffd0050" + block_header) + payload
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_zstd_frames(member)


def test_zstd_two_byte_size_bias_and_eight_byte_size_have_independent_literal_descriptors():
    candidates = (
        (
            "28b52ffd60000003080041",
            (
                (
                    1,
                    0,
                    11,
                    0,
                    7,
                    96,
                    None,
                    1,
                    True,
                    0,
                    False,
                    256,
                    256,
                    None,
                    None,
                    ((1, 7, 10, True, 1, 256, 10, 11),),
                ),
            ),
        ),
        (
            "28b52ffde002000000000000001100004142",
            (
                (
                    1,
                    0,
                    18,
                    0,
                    13,
                    224,
                    None,
                    3,
                    True,
                    0,
                    False,
                    2,
                    2,
                    None,
                    None,
                    ((1, 13, 16, True, 0, 2, 16, 18),),
                ),
            ),
        ),
    )
    for literal_hex, expected in candidates:
        _assert_exact_literal_tree(
            PROBE_MODULE.inspect_zstd_frames(bytes.fromhex(literal_hex)), expected
        )


def test_zstd_cumulative_known_output_cap_is_not_confused_with_unknown_output_claims():
    known = next(
        case for case in ORACLES.ZSTD_RESOURCE_CASES if case["case_id"] == "known_exact_one_mib"
    )
    member = bytes.fromhex(known["compressed_hex"])
    with pytest.raises(ValueError):
        PROBE_MODULE.inspect_zstd_frames(member + bytes.fromhex("28b52ffd200109000041"))
    unknown = bytes.fromhex("28b52ffd00001100004142")
    expected = ORACLES.ZSTD_FRAME_EXPECTATIONS["known_exact_one_mib"] + (
        _shift_physical_frame(ORACLES.ZSTD_FRAME_EXPECTATIONS["raw_ab_unknown"][0], 2, 41),
    )
    _assert_exact_literal_tree(PROBE_MODULE.inspect_zstd_frames(member + unknown), expected)
    # Actual combined output would exceed1MiB. Physical acceptance is NOT
    # decoded-output acceptance; the later bounded native reader must refuse.


def test_zstd_physical_framing_does_not_claim_checksum_or_declared_output_consistency():
    wrong_checksum = ORACLES.ZSTD_CHECKSUM_NEGATIVE_CASES[0]
    expected = (
        (
            1,
            0,
            15,
            0,
            6,
            36,
            None,
            0,
            True,
            0,
            True,
            2,
            2,
            None,
            wrong_checksum["stored_checksum"],
            ((1, 6, 9, True, 0, 2, 9, 11),),
        ),
    )
    _assert_exact_literal_tree(
        PROBE_MODULE.inspect_zstd_frames(bytes.fromhex(wrong_checksum["compressed_hex"])),
        expected,
    )
    mismatched_size = (
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
            3,
            3,
            None,
            None,
            ((1, 6, 9, True, 0, 2, 9, 11),),
        ),
    )
    _assert_exact_literal_tree(
        PROBE_MODULE.inspect_zstd_frames(bytes.fromhex("28b52ffd20031100004142")),
        mismatched_size,
    )


def test_insufficient_deadline_reserve_refuses_before_api_setup(monkeypatch):
    base = datetime.now(UTC).replace(microsecond=0)
    deadline = (base + timedelta(seconds=14)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def forbidden_api():
        raise AssertionError("insufficient deadline reserve reached native API setup")

    monkeypatch.setenv(DEADLINE_ENV, deadline)
    monkeypatch.setattr(CONTAINMENT, "_utc", lambda: base)
    monkeypatch.setattr(CONTAINMENT, "_api", forbidden_api)
    receipt, output = _run("stub_success")
    assert receipt["disposition"] == "setup_refused"
    assert receipt["created"] is False
    assert output == b""


def test_deadline_jump_is_rechecked_immediately_before_process_creation(monkeypatch):
    base = datetime.now(UTC).replace(microsecond=0)
    hard_end = base + timedelta(seconds=60)
    clock_calls = []

    def clock():
        clock_calls.append(len(clock_calls) + 1)
        return base if len(clock_calls) == 1 else hard_end + timedelta(seconds=1)

    def forbidden_create(*args, **kwargs):
        raise AssertionError("expired pre-create deadline reached process creation")

    monkeypatch.setenv(DEADLINE_ENV, hard_end.strftime("%Y-%m-%dT%H:%M:%SZ"))
    monkeypatch.setattr(CONTAINMENT, "_stamp", lambda: base.strftime("%Y-%m-%dT%H:%M:%SZ"))
    monkeypatch.setattr(CONTAINMENT, "_utc", clock)
    monkeypatch.setattr(CONTAINMENT, "_create_process", forbidden_create)
    receipt, output = _run("stub_success")
    assert len(clock_calls) >= 2
    assert receipt["disposition"] == "setup_refused"
    assert receipt["created"] is False
    assert receipt["child_pid"] is None
    assert output == b""
