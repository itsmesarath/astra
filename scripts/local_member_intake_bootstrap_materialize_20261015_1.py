"""Root-owned, no-producer-import preparation of the registered invented cohort.

This support tool is not a runtime SourceManifest role or qualification result.
Its source and registration pins must be supplied by the retained root launch.
It refuses any existing output and does not open member/history/archive inputs.
"""

import hashlib
import json
import struct
import sys
import time
from pathlib import Path


ROOT = Path("C:/Users/pabta/Projects/ai-trader")
RUN = ROOT / "logs/local_member_intake_proof_20261015_1"
SELF = ROOT / "scripts/local_member_intake_bootstrap_materialize_20261015_1.py"
REGISTRATION = RUN / "bootstrap_registration_2.json"
HARD_END = "2026-10-15T14:59:08Z"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pairs(rows):
    result = {}
    for name, value in rows:
        require(name not in result, "duplicate JSON key")
        result[name] = value
    return result


def bad_number(token):
    raise ValueError("noninteger JSON token: " + token)


def parse(raw):
    return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_float=bad_number, parse_constant=bad_number)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def capture(path, cap, expected_sha=None, expected_length=None):
    require(type(cap) is int and cap > 0, "read cap")
    with Path(path).open("rb") as stream:
        raw = stream.read(cap + 1)
        require(len(raw) <= cap, "metadata first excess")
        require(expected_length is None or len(raw) == expected_length, "metadata length")
        require(stream.read(1) == b"", "metadata EOF")
    require(expected_sha is None or sha(raw) == expected_sha, "metadata raw pin")
    return raw


def raw_ref(path, raw):
    return {"path": str(path).replace("\\", "/"), "raw_byte_length": len(raw),
            "raw_sha256": sha(raw)}


def json_ref(path, raw):
    encoded = canonical(parse(raw))
    return {**raw_ref(path, raw), "canonical_byte_length": len(encoded),
            "canonical_sha256": sha(encoded)}


def read_json_ref(ref, cap):
    raw = capture(ref["path"], cap, ref["raw_sha256"], ref["raw_byte_length"])
    require(json_ref(ref["path"], raw) == ref, "entire JSON artifact reference")
    return parse(raw)


def literal(recipe):
    op = recipe["op"]
    if op == "literal_hex":
        raw = bytes.fromhex(recipe["hex"])
        require(len(raw) == recipe["raw_byte_length"], "literal exact length")
        return raw
    if op == "ascii_padding_record":
        prefix = recipe["prefix"].encode("ascii")
        suffix = recipe["suffix"].encode("ascii")
        count = recipe["raw_byte_length"] - len(prefix) - len(suffix)
        require(count >= 0 and recipe["fill"] == "a", "padding recipe")
        return prefix + b"a" * count + suffix
    if op == "repeat_ascii":
        unit = recipe["character"].encode("ascii")
        require(len(unit) == 1 and type(recipe["count"]) is int, "repeat recipe")
        return unit * recipe["count"]
    if op == "utf16le":
        return recipe["text"].encode("utf-16-le", "strict") + (
            b"\x00\x00" if recipe["include_nul"] else b""
        )
    require(op == "zeroed_buffer_with_writes", "unknown literal opcode")
    raw = bytearray(recipe["raw_byte_length"])
    occupied = set()
    for row in recipe["writes"]:
        encoding = {"i64-le": "<q", "u32-le": "<I", "u64-le": "<Q"}[row["encoding"]]
        encoded = struct.pack(encoding, row["value"])
        indexes = set(range(row["offset"], row["offset"] + len(encoded)))
        require(indexes and min(indexes) >= 0 and max(indexes) < len(raw), "write bounds")
        require(not occupied.intersection(indexes), "overlapping literal writes")
        occupied.update(indexes)
        raw[row["offset"]:row["offset"] + len(encoded)] = encoded
    return bytes(raw)


def materialize(registration_sha, source_sha):
    require(time.time_ns() < 1792076348000000000, "expired registered window")
    require(len(registration_sha) == len(source_sha) == 64, "external pin width")
    own = capture(SELF, 262144, source_sha)
    r_raw = capture(REGISTRATION, 1048576, registration_sha)
    r = parse(r_raw)
    require(r["schema"] == "local-intake-bootstrap-registration-v2", "registration version")
    require(r["window"]["hard_end_utc"] == HARD_END, "registered deadline")
    r_ref = json_ref(REGISTRATION, r_raw)
    r_hash = r_ref["canonical_sha256"]
    resources = {row["role"]: row["artifact"] for row in r["existing_inputs"]["json_resources"]}
    require(set(resources) == {"protocol", "declarations"}, "exact resources")
    p_ref, d_ref = resources["protocol"], resources["declarations"]
    p = read_json_ref(p_ref, 1048576)
    d = read_json_ref(d_ref, 4194304)
    require(p["authority_flags"] == d["authority_flags"] == r["authority_flags"], "flags")
    require(len(r["authority_flags"]) == 28 and all(
        type(row) is list and len(row) == 2 and row[1] is False
        for row in r["authority_flags"]
    ), "ordered literal false flags")
    flags = r["authority_flags"]
    environment = r["process_contract"]["environment"]
    names = [row["name"] for row in environment]
    require(len(names) == 9 and len({name.casefold() for name in names}) == 9,
            "complete noncolliding process environment")
    require(all("\x00" not in row["name"] + row["value"] and "=" not in row["name"]
                for row in environment), "environment scalar values")
    environment_text = "\x00".join(row["name"] + "=" + row["value"] for row in environment) + "\x00\x00"
    require(len(environment_text.encode("utf-16-le")) // 2 <= 8192, "complete environment cap")
    source_rows = []
    for item in r["binding_contract"]["source_manifest_schema"]["exact_ordered_runtime_role_path_set"]:
        raw = capture(item["path"], 262144)
        require(raw, "empty runtime source")
        source_rows.append({"role": item["role"], **raw_ref(item["path"], raw)})
    require([row["role"] for row in source_rows] == [
        "host", "worker", "contract", "validation", "bootstrap_observer", "bootstrap_primitives"
    ], "exact six source roles")
    source_manifest = {"version": "local-member-intake-bootstrap-source-manifest-v1",
                       "registration_sha256": r_hash, "sources": source_rows}
    allowlists = r["runtime_contract"]["role_module_allowlists"]
    require([row["role"] for row in allowlists] == ["host_runtime", "worker_runtime"], "role order")
    host, worker = allowlists
    require(host["files"] == worker["files"] and host["required_paths"] == worker["required_paths"],
            "complete independent role equality")
    require(len(host["files"]) == 25, "fixed native candidate count")
    modules = [{"role": "host_runtime",
                "absolute_path_utf16le_hex": row["absolute_path"].encode("utf-16-le").hex(),
                "byte_length": row["byte_length"], "sha256": row["sha256"]}
               for row in host["files"]]
    exports = r["runtime_contract"]["export_registrations"]
    require(len(exports) == 66, "complete two-role export registration")
    runtime_manifest = {"version": "local-member-intake-bootstrap-runtime-manifest-v1",
                        "registration_sha256": r_hash,
                        "interpreter": r["runtime_contract"]["interpreter_static_candidate"],
                        "static_modules": modules, "host_required_paths": host["required_paths"],
                        "worker_required_paths": worker["required_paths"], "exports": exports}
    planned = {}
    absent = set()

    def require_absent(path):
        path = Path(path)
        require(path.is_absolute() and path.is_relative_to(RUN), "exact absent-artifact root")
        require(not path.exists() and not path.is_symlink(), "registered ABSENT path exists")
        absent.add(path)

    def prepare(path, raw, cap):
        path = Path(path)
        require(path.is_absolute() and path.is_relative_to(RUN), "exact generated root")
        require(not path.exists() and not path.is_symlink() and path not in planned, "no output replacement")
        require(type(raw) is bytes and len(raw) <= cap, "complete generated cap")
        planned[path] = raw
        return raw_ref(path, raw)

    def prepare_json(path, value, cap):
        raw = canonical(value)
        prepare(path, raw, cap)
        return json_ref(path, raw)

    source_ref = prepare_json(r["artifact_contract"]["source_manifest_path"], source_manifest, 1048576)
    runtime_ref = prepare_json(r["artifact_contract"]["runtime_manifest_path"], runtime_manifest, 1048576)
    literals = []
    for item in r["artifact_contract"]["literal_recipe_artifacts"]:
        recipe = item["independent_complete_recipe"]
        require(recipe == d["raw_byte_recipes"][item["recipe_name"]], "independent complete raw recipe")
        raw = literal(recipe)
        ref = prepare(item["path"], raw, 4194305)
        literals.append({"name": item["recipe_name"], "artifact": ref})
    require(len(literals) == 14, "all fixed raw recipes")
    controls = {row["case_id"]: row for row in d["controls"]}
    require(len(controls) == 24, "complete independent controls")
    cases = []
    for row in r["control_schedule"]:
        require(not Path(row["outputs"]["directory"]).exists(), "attempt directory already exists")
        case = row["case_id"]
        control = controls[case]
        require(row["expected_template"] == control["expected_template"], "case template")
        packet = {"version": "local-member-intake-bootstrap-packet-v1", "operation": "bootstrap",
                  "case_id": case, "registration_sha256": r_hash,
                  "protocol_sha256": p_ref["canonical_sha256"], "oracle_sha256": d_ref["raw_sha256"],
                  "hard_end_utc": HARD_END, "nonce_hex": control["nonce_hex"],
                  "control": control["control"], "authority_flags": flags}
        base = canonical(packet)
        require(len(base) <= 8192, "base packet cap")
        submitted = base
        original_ref = None
        if case == "packet_first_excess":
            require_absent(row["inputs"]["expected_base"])
            packet["padding"] = ""
            padding = 8193 - len(canonical(packet))
            require(padding >= 0, "first excess fixed padding")
            packet["padding"] = "a" * padding
            submitted = canonical(packet)
            require(len(submitted) == 8193, "actual first excess")
            expected_pin = sha(submitted)
        else:
            original_ref = prepare(row["inputs"]["expected_base"], base, 8192)
            expected_pin = sha(base)
            if case == "packet_wrong_pin":
                require(packet["nonce_hex"].endswith("3"), "wrong-pin original nonce")
                packet["nonce_hex"] = packet["nonce_hex"][:-1] + "4"
                submitted = canonical(packet)
                require(sum(a != b for a, b in zip(base, submitted, strict=True)) == 1,
                        "one exact submitted byte mutation")
        submitted_ref = prepare(row["inputs"]["submitted"], submitted, 8193)
        rejection_ref = None
        if case in ("packet_first_excess", "packet_wrong_pin", "unknown_control"):
            rejection = {"version": "local-member-intake-bootstrap-rejected-input-v1",
                         "case_id": case, "registration_sha256": r_hash,
                         "oracle_sha256": d_ref["raw_sha256"],
                         "expected_raw_hex": None if original_ref is None else base.hex(),
                         "expected_packet_sha256": expected_pin, "submitted_raw_hex": submitted.hex(),
                         "submitted_raw_byte_length": len(submitted), "submitted_raw_sha256": sha(submitted),
                         "first_reason": control["expected_reason"], "admitted_packet": None,
                         "native_setup_attempted": False}
            rejection["rejection_sha256"] = sha(canonical(rejection))
            rejection_ref = prepare_json(row["inputs"]["rejected_evidence"], rejection, 1048576)
        else:
            require_absent(row["inputs"]["rejected_evidence"])
        # Independently complete CW and CH literals; never relabel one context as the other.
        cw = {"version": "local-member-intake-bootstrap-context-v1", "role": "worker",
              "registration": r_ref, "protocol": p_ref, "declarations": d_ref,
              "source_manifest": source_ref, "runtime_manifest": runtime_ref,
              "expected_packet_sha256": expected_pin, "hard_end_utc": HARD_END,
              "hard_end_unix_ns": 1792076348000000000,
              "working_directory": str(ROOT).replace("\\", "/"), "worker_context": None}
        cw_ref = prepare_json(row["contexts"]["worker"], cw, 3072)
        ch = {"version": "local-member-intake-bootstrap-context-v1", "role": "host",
              "registration": r_ref, "protocol": p_ref, "declarations": d_ref,
              "source_manifest": source_ref, "runtime_manifest": runtime_ref,
              "expected_packet_sha256": expected_pin, "hard_end_utc": HARD_END,
              "hard_end_unix_ns": 1792076348000000000,
              "working_directory": str(ROOT).replace("\\", "/"), "worker_context": cw_ref}
        ch_ref = prepare_json(row["contexts"]["host"], ch, 3072)
        host_path = source_rows[0]["path"]
        arguments = ["-B", "-I", host_path, submitted.hex(), canonical(ch).hex()]
        require(all(value and not any(c in value for c in ' \t\r\n\0"') for value in arguments),
                "literal no-space host argument rendering")
        executable = r["process_contract"]["direct_interpreter"]
        command = '"' + executable + '" ' + " ".join(arguments)
        require(len(command.encode("utf-16-le")) // 2 + 1 <= 24576, "full command cap")
        cases.append({"ordinal": row["ordinal"], "case_id": case, "expected_base": original_ref,
                      "submitted": submitted_ref, "rejected_evidence": rejection_ref,
                      "worker_context": cw_ref, "host_context": ch_ref,
                      "expected_packet_sha256": expected_pin,
                      "expected_template": {"declarations": d_ref, "case_selector": case,
                                            "registry_selector": "expected_template_registry",
                                            "template_name": control["expected_template"]},
                      "host_invocation": {"file_name": executable, "argument_list": arguments,
                                          "prepared_command_line": command,
                                          "working_directory": str(ROOT).replace("\\", "/"),
                                          "environment": r["process_contract"]["environment"]},
                      "outputs": row["outputs"]})
    require([row["ordinal"] for row in cases] == list(range(24)), "case ordinal order")
    raw_inputs = {row["role"]: row for row in r["existing_inputs"]["raw_artifacts"]}
    startup_ref = raw_inputs["startup_policy"]
    startup_path = Path(startup_ref["path"])
    startup = capture(startup_path, 262144, startup_ref["raw_sha256"], startup_ref["raw_byte_length"])
    c3_ref = raw_inputs["primitive_C3_transfer"]
    c3_path = Path(c3_ref["path"])
    require(str(c3_path) == str(Path(r["artifact_contract"]["primitive_transfer_path"])), "fixed C3 path")
    c3_raw = capture(c3_path, 1048576, c3_ref["raw_sha256"], c3_ref["raw_byte_length"])
    c3 = parse(c3_raw)
    require(c3["module"]["sha256"] == source_rows[-1]["raw_sha256"], "exact C3 module pin")
    e = {"version": "local-member-intake-bootstrap-expectations-v1",
         "window_start_utc": "2026-10-15T06:59:08Z", "hard_end_utc": HARD_END,
         "registration": r_ref, "protocol": p_ref, "declarations": d_ref,
         "source_manifest": source_ref, "runtime_manifest": runtime_ref,
         "startup_policy": raw_ref(startup_path, startup), "primitive_transfer": json_ref(c3_path, c3_raw),
         "materializer": raw_ref(SELF, own), "literal_artifacts": literals, "cases": cases,
         "authority_flags": flags}
    e_ref = prepare_json(r["artifact_contract"]["expectations_E_path"], e, 4194304)
    seal_path = r["artifact_contract"]["external_launch_seal_path"]
    invocations = []
    for row in cases:
        parameters = {"CaseId": row["case_id"], "LaunchSealPath": seal_path,
                      "ExpectedExpectationsSha256": e_ref["raw_sha256"],
                      "ObserverSha256": source_rows[4]["raw_sha256"],
                      "PrimitivesSha256": source_rows[5]["raw_sha256"]}
        invocations.append({"ordinal": row["ordinal"], "case_id": row["case_id"],
                            "script_path": source_rows[4]["path"], "parameters": parameters})
    seal = {"version": "local-member-intake-bootstrap-launch-seal-v1", "expectations": e_ref,
            "observer": {key: source_rows[4][key] for key in ("path", "raw_byte_length", "raw_sha256")},
            "primitives": {key: source_rows[5][key] for key in ("path", "raw_byte_length", "raw_sha256")},
            "invocations": invocations, "authority_flags": flags}
    seal_ref = prepare_json(seal_path, seal, 1048576)
    # All literal complete bodies and all no-overwrite/cap constraints are checked before first publication.
    for path in planned:
        require(not path.exists() and not path.is_symlink(), "output appeared before publication")
    for path in absent:
        require(not path.exists() and not path.is_symlink(), "registered ABSENT path appeared")
    published = []
    for path, raw in planned.items():
        require(time.time_ns() < 1792076348000000000, "stop before next generated publication")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            require(stream.write(raw) == len(raw), "incomplete generated write")
        require(capture(path, max(len(raw), 1), sha(raw), len(raw)) == raw, "published raw equality")
        published.append(raw_ref(path, raw))
    for path in absent:
        require(not path.exists() and not path.is_symlink(), "registered ABSENT path appeared during publication")
    return {"schema": "local-intake-bootstrap-materialization-v1", "expectations": e_ref,
            "launch_seal": seal_ref, "complete_generated_artifacts": published,
            "all24_cases_and14_literal_bodies": True, "source_roles": 6,
            "native_execution_or_qualification": False}


def main():
    require(len(sys.argv) == 3, "two externally pinned SHA arguments")
    print(canonical(materialize(sys.argv[1], sys.argv[2])).decode("ascii"))


if __name__ == "__main__":
    main()
