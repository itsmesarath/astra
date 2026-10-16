"""Read-only local constructed-packet check, never storage or account operation.

Threat model: trusted/cooperative local filesystem. Path and byte rechecks do
not establish adversarial race freedom or authenticate already executed code.
The eight source pins cover explicitly used helpers, NOT the entire import or
runtime graph and NOT the existing 47-wrapper/40-replay source identities.
No packet construction, advance, history, model, order, claim or file writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ai_trader.research import six_e_declared_admission_packet as packet

admission = packet.admission
budget = admission.budget
economics = budget.economics
replay = economics.replay
ledger = admission.ledger
target = ledger.target
VERSION = "six_e_declared_admission_operator_v1"
STATUS = "verified_local_constructed_packet_not_authenticated"
MANIFEST_VERSION = "six_e_declared_admission_operator_sources_v1"
MANIFEST_SCOPE = "local_source_bytes_not_executed_authentication"
MAX_MANIFEST_BYTES, MAX_SOURCE_BYTES = 8192, 512 * 1024
SOURCE_MODULES = {
    "src/ai_trader/research/six_e_declared_admission_operator.py": sys.modules[__name__],
    "src/ai_trader/research/six_e_declared_admission_packet.py": packet,
    "src/ai_trader/research/six_e_declared_admission.py": admission,
    "src/ai_trader/research/six_e_entry_budget.py": budget,
    "src/ai_trader/research/six_e_declared_economics.py": economics,
    "src/ai_trader/research/six_e_position_ledger.py": ledger,
    "src/ai_trader/research/six_e_bracket_targets.py": target,
    # budget.AUTHORITY_FLAGS calls this helper during module initialization.
    "src/ai_trader/research/six_e_continuous_replay.py": replay,
}
SOURCE_NAMES = frozenset(SOURCE_MODULES)
AUTHORITY_FLAGS = tuple(
    sorted(
        {
            **dict(packet.AUTHORITY_FLAGS),
            "operator_source_authentication": False,
            "runtime_code_authenticated": False,
        }.items()
    )
)


class OperatorError(ValueError):
    """Controlled refusal, never a partial verified state or automatic repair."""


@dataclass(frozen=True, slots=True)
class OperatorResult:
    version: str
    status: str
    packet_path: str
    source_manifest_path: str
    expected_packet_sha256: str
    expected_source_manifest_sha256: str
    expected_genesis_sha256: str
    expected_terminal: admission.DeclaredPrefix
    source_pins: tuple[tuple[str, str], ...]
    supplied_record_count: int
    matched_receipt_count: int
    decoded_packet: packet.DeclaredAdmissionPacket
    authority_flags: tuple[tuple[str, bool], ...]


def _require(condition, message):
    if not condition:
        raise OperatorError(message)


def _pin(value):
    _require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "Exact retained lowercase SHA256 required",
    )


def _literal(value):
    _require(type(value) is str or isinstance(value, Path), "Explicit local path required")
    raw = os.fspath(value)
    _require(bool(raw) and not raw.startswith(("\\\\", "//")), "UNC/empty paths unsupported")
    _require(not any(ord(char) < 32 or char in '<>"|?*' for char in raw), "Ambiguous path")
    text = raw.replace("\\", "/")
    _require("//" not in text, "Repeated path separators unsupported")
    path = Path(raw)
    _require(not path.drive or path.is_absolute(), "Drive-relative paths unsupported")
    for part in text.split("/"):
        if not part or part == path.drive:
            continue
        _require(part not in (".", "..") and not part.endswith((".", " ")), "Trailing/dot alias")
        _require(":" not in part, "Alternate data streams unsupported")
        base = part.split(".", 1)[0].upper()
        _require(
            re.fullmatch(r"CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³]", base) is None,
            "Windows device name unsupported",
        )
    return path


def _identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        getattr(info, "st_file_attributes", 0),
    )


def _opened_matches(info, path_identity):
    opened = _identity(info)
    # Python 3.12 Windows path ctime is creation time, while handle ctime can
    # be last-write time. Retain ctime in BOTH full same-view drift checks.
    if os.name == "nt":
        return opened[:6] + opened[7:] == path_identity[:6] + path_identity[7:]
    return opened == path_identity


def _all_false(flags):
    _require(type(flags) is tuple and bool(flags), "Nonempty immutable authority flags required")
    keys = set()
    for pair in flags:
        _require(
            type(pair) is tuple
            and len(pair) == 2
            and type(pair[0]) is str
            and pair[0] not in keys
            and pair[1] is False,
            "Every declared authority must be exact False",
        )
        keys.add(pair[0])


def _guard(path, *, directory=False):
    parts = tuple(reversed(path.parents)) + (path,)
    info = None
    for ancestor in parts:
        info = ancestor.lstat()
        _require(
            not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
            "Links/reparse ancestry unsupported",
        )
        if ancestor != path or directory:
            _require(stat.S_ISDIR(info.st_mode), "Existing ordinary directory required")
        else:
            _require(
                stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                "Ordinary unambiguous single-link file required",
            )
    return info


def _root(value):
    root = Path.cwd() if os.fspath(value) == "." else _literal(value).absolute()
    _guard(root, directory=True)
    installed_file = _literal(__file__).absolute()
    _guard(installed_file)
    _require(root == installed_file.parents[3], "Root must match this installed project")
    _guard(root / "logs", directory=True)
    return root


def _input(root, value):
    path = _literal(value)
    path = path if path.is_absolute() else root / path
    _require(
        path.is_relative_to(root / "logs") and path.suffix == ".json",
        "JSON input under logs required",
    )
    _guard(path)
    return path


def _aliases():
    _require(
        packet.admission is admission
        and admission.budget is budget
        and budget.economics is economics
        and economics.ledger is ledger
        and economics.replay is replay
        and replay.ledger is ledger
        and budget.ledger is ledger
        and admission.ledger is ledger
        and ledger.target is target
        and ledger.study.exits.target is target,
        "Actual used-helper module aliases differ",
    )


def _source_paths(root):
    _require(set(SOURCE_MODULES) == SOURCE_NAMES, "Exact eight used-helper source keys required")
    _aliases()
    result = {}
    for name in sorted(SOURCE_NAMES):
        expected = root / name
        actual = _literal(SOURCE_MODULES[name].__file__).absolute()
        _require(actual == expected, "Imported helper file identity/root differs")
        _guard(actual)
        result[name] = actual
    return result


def _read(path, cap, expected_sha256):
    """Metadata before read/hash; cap+1 detection and EOF, then identity checks."""
    before = _guard(path)
    _require(0 < before.st_size <= cap, "Input/source size exceeds bound")
    identity = _identity(before)
    # Revalidate immediately before opening; cooperative-local threat model only.
    _require(_identity(_guard(path)) == identity, "File drift before open")
    with path.open("rb") as handle:
        opened = os.fstat(handle.fileno())
        _require(_opened_matches(opened, identity), "Opened file identity differs")
        handle_identity = _identity(opened)
        raw = handle.read(cap + 1)
        _require(len(raw) <= cap, "Bounded read detected growth/oversize")
        _require(handle.read(1) == b"", "Complete EOF required")
        _require(len(raw) == before.st_size, "Complete file size differs")
        _require(
            _identity(os.fstat(handle.fileno())) == handle_identity, "File changed during read"
        )
    _require(_identity(_guard(path)) == identity, "File changed after read")
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256, "Retained raw byte pin differs")
    return raw, identity


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _manifest(raw):
    packet._scan(raw)
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=packet._pairs,
        parse_int=packet._parse_integer,
        parse_float=packet._forbidden_number,
        parse_constant=packet._forbidden_number,
    )
    _require(
        type(value) is dict and set(value) == {"version", "scope", "sources"},
        "Closed source manifest required",
    )
    _require(
        type(value["version"]) is str
        and value["version"] == MANIFEST_VERSION
        and type(value["scope"]) is str
        and value["scope"] == MANIFEST_SCOPE,
        "Fixed source manifest version/scope required",
    )
    sources = value["sources"]
    _require(
        type(sources) is dict and set(sources) == SOURCE_NAMES, "Exact used-helper closure required"
    )
    for pin in sources.values():
        _pin(pin)
    _require(_canonical(value) == raw, "Source manifest must be canonical ASCII JSON")
    return sources


def verify_packet(
    root,
    packet_path,
    source_manifest_path,
    *,
    expected_packet_sha256: str,
    expected_genesis_sha256: str,
    expected_terminal: admission.DeclaredPrefix,
    expected_source_manifest_sha256: str,
) -> OperatorResult:
    """Read-only complete check, no claims/writes/advance or source authentication."""
    try:
        for pin in (
            expected_packet_sha256,
            expected_genesis_sha256,
            expected_source_manifest_sha256,
        ):
            _pin(pin)
        _require(
            type(expected_terminal) is admission.DeclaredPrefix, "Exact external terminal required"
        )
        replace(expected_terminal)
        _all_false(AUTHORITY_FLAGS)
        root = _root(root)
        declared_path, manifest_path = _input(root, packet_path), _input(root, source_manifest_path)
        _require(declared_path != manifest_path, "Distinct packet and source manifest required")
        sources = _source_paths(root)
        manifest_raw, manifest_identity = _read(
            manifest_path, MAX_MANIFEST_BYTES, expected_source_manifest_sha256
        )
        pins = _manifest(manifest_raw)
        source_identities = {
            name: _read(path, MAX_SOURCE_BYTES, pins[name])[1] for name, path in sources.items()
        }
        raw, declared_identity = _read(
            declared_path, packet.MAX_PACKET_BYTES, expected_packet_sha256
        )
        decoded = packet.decode_packet(
            raw,
            expected_packet_sha256=expected_packet_sha256,
            expected_genesis_sha256=expected_genesis_sha256,
            expected_terminal=expected_terminal,
        )
        _all_false(decoded.authority_flags)
        _all_false(decoded.reconstructed_state.authority_flags)
        _require(_source_paths(root) == sources, "Used-helper path identity drift")
        _require(
            _read(manifest_path, MAX_MANIFEST_BYTES, expected_source_manifest_sha256)[1]
            == manifest_identity,
            "Source manifest metadata drift",
        )
        for name, path in sources.items():
            _require(
                _read(path, MAX_SOURCE_BYTES, pins[name])[1] == source_identities[name],
                "Source metadata drift",
            )
        _require(
            _read(declared_path, packet.MAX_PACKET_BYTES, expected_packet_sha256)[1]
            == declared_identity,
            "Packet metadata drift",
        )
        _all_false(AUTHORITY_FLAGS)
        return OperatorResult(
            VERSION,
            STATUS,
            declared_path.relative_to(root).as_posix(),
            manifest_path.relative_to(root).as_posix(),
            expected_packet_sha256,
            expected_source_manifest_sha256,
            expected_genesis_sha256,
            expected_terminal,
            tuple(sorted(pins.items())),
            len(decoded.records),
            len(decoded.reconstructed_state.receipt_content_sha256s),
            decoded,
            AUTHORITY_FLAGS,
        )
    except OperatorError:
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        AttributeError,
        RecursionError,
        OverflowError,
        MemoryError,
    ) as exc:
        raise OperatorError("Local constructed packet check refused") from exc


def _cli_integer(value):
    try:
        return packet._parse_integer(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Canonical bounded decimal integer required") from exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    check = command.add_parser("verify-packet")
    check.add_argument("--root", default=".")
    for name in (
        "packet",
        "source-manifest",
        "packet-sha256",
        "source-manifest-sha256",
        "genesis-sha256",
        "terminal-head-sha256",
    ):
        check.add_argument("--" + name, required=True)
    check.add_argument("--terminal-sequence", type=_cli_integer, required=True)
    check.add_argument("--terminal-complete-through-ns", type=_cli_integer, required=True)
    args = parser.parse_args(argv)
    try:
        result = verify_packet(
            args.root,
            args.packet,
            args.source_manifest,
            expected_packet_sha256=args.packet_sha256,
            expected_genesis_sha256=args.genesis_sha256,
            expected_terminal=admission.DeclaredPrefix(
                args.terminal_sequence, args.terminal_head_sha256, args.terminal_complete_through_ns
            ),
            expected_source_manifest_sha256=args.source_manifest_sha256,
        )
        print(_canonical(asdict(result)).decode("ascii"))
        return 0
    except (OperatorError, ValueError, TypeError) as exc:
        print(
            _canonical(
                {"status": "refused_local_constructed_packet", "error": type(exc).__name__}
            ).decode("ascii"),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
