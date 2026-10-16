"""Private complete-member framing; native codecs are not imported here."""

import hashlib
import importlib
import io
import os
import re
import sys
from datetime import date
from email.parser import BytesParser
from pathlib import Path

if __package__:
    from . import _native_member_types as _types
else:
    import _native_member_types as _types


_INITIAL_LOADED = None
_ROOT = Path(__file__).resolve().parents[3]
_BASE_PYTHON = Path("C:/Users/pabta/AppData/Local/Programs/Python/Python312")
_REQUEST_FIELDS = {
    "schema",
    "operation",
    "context",
    "member_hex",
    "expected_protocol_sha256",
    "expected_profile_sha256",
    "expected_runtime_manifest_sha256",
    "expected_member_sha256",
    "expected_metadata_sha256",
    "execution_manifest_sha256",
    "attempt_token",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class _OctetCursor:
    """Bound every original-byte read and retain its absolute field interval."""

    def __init__(self, source: bytes, start: int, stop: int):
        self.source = source
        self.position = start
        self.stop = stop
        self.fields: list[tuple[str, int, int]] = []

    def read(self, name: str, size: int) -> bytes:
        end = self.position + size
        _require(size > 0 and end <= self.stop, "incomplete original field")
        start = self.position
        self.position = end
        self.fields.append((name, start, end))
        return self.source[start:end]

    def number(self, name: str, size: int, *, signed: bool = False) -> int:
        return int.from_bytes(self.read(name, size), "little", signed=signed)

    def text(self, name: str, size: int) -> str:
        raw = self.read(name, size)
        terminator = raw.find(b"\x00")
        _require(terminator >= 0, "unterminated wire string")
        _require(not any(raw[terminator:]), "nonzero wire string padding")
        try:
            return raw[:terminator].decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid wire string encoding") from exc

    def day(self, name: str) -> int:
        value = self.number(name, 4)
        try:
            date(value // 10000, value // 100 % 100, value % 100)
        except (ValueError, OverflowError) as exc:
            raise ValueError("invalid wire mapping date") from exc
        return value


def _read_metadata(source: bytes, stop: int) -> tuple[dict, tuple]:
    reader = _OctetCursor(source, 0, stop)
    body = {
        "magic_hex": reader.read("magic", 3).hex(),
        "version": reader.number("version", 1),
        "length_body": reader.number("length_body", 4),
        "dataset": reader.text("dataset", 16),
        "dataset_cstr_bytes": 16,
        "schema": reader.number("schema", 2),
        "start": reader.number("start", 8),
        "end": reader.number("end", 8),
        "limit": reader.number("limit", 8),
        "stype_in": reader.number("stype_in", 1),
        "stype_out": reader.number("stype_out", 1),
        "ts_out": reader.number("ts_out", 1),
        "symbol_cstr_len": reader.number("symbol_cstr_len", 2),
        "reserved_bytes": tuple(reader.read("reserved", 53)),
        "schema_definition_length": reader.number("schema_definition_length", 4),
    }
    _require(
        body["magic_hex"] == "44424e"
        and body["version"] == 3
        and body["length_body"] + 8 == stop
        and body["schema"] == 0
        and body["stype_in"] in (*range(16), 255)
        and body["stype_out"] in range(16)
        and body["ts_out"] in (0, 1)
        and body["symbol_cstr_len"] == 71
        and not any(body["reserved_bytes"])
        and body["schema_definition_length"] == 0,
        "unsupported complete DBN metadata",
    )
    for field in ("symbols", "partial", "not_found"):
        count = reader.number(field + "_count", 4)
        _require(count <= 16, "wire symbol collection limit")
        body[field + "_count"] = count
        body[field] = tuple(reader.text(f"{field}[{index}]", 71) for index in range(count))

    count = reader.number("mappings_count", 4)
    _require(count <= 16, "wire mapping group limit")
    body["mappings_count"] = count
    groups = []
    symbols_seen = set()
    total_intervals = 0
    for group_index in range(count):
        label = f"mappings[{group_index}]"
        symbol = reader.text(label + ".raw_symbol", 71)
        _require(symbol not in symbols_seen, "duplicate original mapping group")
        symbols_seen.add(symbol)
        interval_count = reader.number(label + ".interval_count", 4)
        total_intervals += interval_count
        _require(total_intervals <= 32, "wire mapping interval limit")
        intervals = []
        for interval_index in range(interval_count):
            item = f"{label}.intervals[{interval_index}]"
            intervals.append(
                {
                    "start_date": reader.day(item + ".start_date"),
                    "end_date": reader.day(item + ".end_date"),
                    "symbol": reader.text(item + ".symbol", 71),
                }
            )
        groups.append(
            {"raw_symbol": symbol, "interval_count": interval_count, "intervals": tuple(intervals)}
        )
    body["mappings"] = tuple(groups)
    padding_length = (-reader.position) % 8
    _require(reader.position + padding_length == stop, "unexplained complete header tail")
    padding = reader.read("alignment_padding", padding_length) if padding_length else b""
    _require(not any(padding), "nonzero header alignment")
    body["alignment_padding_bytes"] = tuple(padding)
    return body, tuple(reader.fields)


def _read_mbo(source: bytes, start: int, stop: int, ts_out: bool) -> tuple[dict, tuple]:
    reader = _OctetCursor(source, start, stop)
    layout = (
        ("length_words", 1, False),
        ("rtype", 1, False),
        ("publisher_id", 2, False),
        ("instrument_id", 4, False),
        ("ts_event", 8, False),
        ("order_id", 8, False),
        ("price", 8, True),
        ("size", 4, False),
        ("flags", 1, False),
        ("channel_id", 1, False),
        ("action", 1, False),
        ("side", 1, False),
        ("ts_recv", 8, False),
        ("ts_in_delta", 4, True),
        ("sequence", 4, False),
    )
    body = {name: reader.number(name, width, signed=signed) for name, width, signed in layout}
    body["ts_out"] = reader.number("ts_out", 8) if ts_out else None
    _require(
        body["length_words"] == (16 if ts_out else 14)
        and body["rtype"] == 160
        and reader.position == stop,
        "unsupported or incomplete MBO wire record",
    )
    return body, tuple(reader.fields)


def inspect_dbn_wire(member_bytes: bytes) -> dict:
    """Retain all wire bodies and field spans without invoking a native parser."""
    _require(type(member_bytes) is bytes, "DBN member must be exact bytes")
    _require(128 <= len(member_bytes) <= 1048576, "complete DBN byte limit")
    _require(member_bytes[:4] == b"DBN\x03", "explicit complete DBN v3 header required")
    header_stop = int.from_bytes(member_bytes[4:8], "little") + 8
    _require(
        128 <= header_stop <= min(len(member_bytes), 65536) and header_stop % 8 == 0,
        "complete DBN header length/alignment",
    )
    metadata, fields = _read_metadata(member_bytes, header_stop)
    has_ts_out = metadata["ts_out"] == 1
    width = 64 if has_ts_out else 56
    remaining = len(member_bytes) - header_stop
    _require(
        remaining % width == 0 and 1 <= remaining // width <= 127,
        "complete DBN requires one header and 1..127 complete MBO records",
    )
    spans = [("Metadata", 0, header_stop)]
    bodies = [metadata]
    all_fields = [fields]
    for start in range(header_stop, len(member_bytes), width):
        stop = start + width
        body, fields = _read_mbo(member_bytes, start, stop, has_ts_out)
        spans.append(("MBO", start, stop))
        bodies.append(body)
        all_fields.append(fields)
    return {
        "complete_bytes": len(member_bytes),
        "wire_spans": tuple(spans),
        "wire_bodies": tuple(bodies),
        "field_spans": tuple(all_fields),
    }


def inspect_zstd_frames(member_bytes: bytes) -> tuple:
    """Cover every physical standard frame; terminal output remains a later check."""
    _require(type(member_bytes) is bytes, "compressed member must be exact bytes")
    _require(1 <= len(member_bytes) <= 262144, "complete compressed byte limit")
    reader = _OctetCursor(member_bytes, 0, len(member_bytes))
    frames = []
    known_output = 0
    while reader.position < reader.stop:
        _require(len(frames) < 16, "complete frame count limit")
        start = reader.position
        _require(reader.read("frame_magic", 4) == b"\x28\xb5\x2f\xfd", "standard frame required")
        descriptor = reader.number("frame_descriptor", 1)
        size_flag = descriptor >> 6
        single = bool(descriptor & 32)
        checksum = bool(descriptor & 4)
        dictionary_flag = descriptor & 3
        _require(not descriptor & 24 and dictionary_flag == 0, "forbidden frame header mode")
        window_descriptor = None
        window_size = None
        if not single:
            window_descriptor = reader.number("window_descriptor", 1)
            base = 1 << (10 + (window_descriptor >> 3))
            window_size = base + (base >> 3) * (window_descriptor & 7)
            _require(window_size <= 1048576, "frame window limit")
        size_width = (1 if single else 0) if size_flag == 0 else (2, 4, 8)[size_flag - 1]
        content_size = None
        if size_width:
            content_size = reader.number("frame_content_size", size_width)
            if size_flag == 1:
                content_size += 256
            known_output += content_size
            _require(
                1 <= content_size <= 1048576 and known_output <= 1048576,
                "known frame output must be nonempty and bounded cumulatively",
            )
        if single:
            window_size = content_size
        header_stop = reader.position
        blocks = []
        while True:
            block_start = reader.position
            bits = reader.number("block_header", 3)
            last = bool(bits & 1)
            block_kind = (bits >> 1) & 3
            block_size = bits >> 3
            _require(
                block_kind != 3 and block_size <= min(window_size, 131072),
                "unsupported block or frame block limit",
            )
            payload_start = reader.position
            payload_size = 1 if block_kind == 1 else block_size
            if payload_size:
                reader.read("block_payload", payload_size)
            blocks.append(
                (
                    len(blocks) + 1,
                    block_start,
                    payload_start,
                    last,
                    block_kind,
                    block_size,
                    payload_start,
                    reader.position,
                )
            )
            if last:
                break
        checksum_value = reader.number("frame_checksum", 4) if checksum else None
        frames.append(
            (
                len(frames) + 1,
                start,
                reader.position,
                start,
                header_stop,
                descriptor,
                window_descriptor,
                size_flag,
                single,
                dictionary_flag,
                checksum,
                content_size,
                window_size,
                None,
                checksum_value,
                tuple(blocks),
            )
        )
    return tuple(frames)


def _load_native_runtime() -> tuple:
    """Load the fixed native runtime only inside the registered worker."""
    global _INITIAL_LOADED
    _identity(_INITIAL_LOADED is None, "native runtime cannot be initialized twice")
    _identity(
        sys.platform == "win32" and sys.maxsize == (1 << 63) - 1, "registered platform required"
    )
    flags = (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode)
    _identity(
        sys.implementation.name == "cpython"
        and tuple(sys.version_info[:3]) == (3, 12, 10)
        and all(type(flag) is int and flag == 1 for flag in flags),
        "registered isolated Python required",
    )
    _identity(
        not any(
            name == "databento_dbn"
            or name.startswith("databento_dbn.")
            or name == "zstandard"
            or name.startswith("zstandard.")
            for name in sys.modules
        ),
        "native modules must be fresh",
    )
    try:
        expected = _types.profile_body()["runtime_manifest"]
        before = _static_runtime_manifest(expected)
        site = str(_ROOT / ".venv/Lib/site-packages")
        _identity(site not in sys.path, "native site must not precede controlled initialization")
        sys.path.append(site)
        os.environ["PYTHON_ZSTANDARD_IMPORT_POLICY"] = "cext"
        dbn = importlib.import_module("databento_dbn")
        zstd = importlib.import_module("zstandard")
        loaded = _loaded_associations(dbn, zstd)
        after = _static_runtime_manifest(expected)
        _identity(before == after, "native artifacts changed during initialization")
    except (OSError, ImportError, ValueError, KeyError, AttributeError) as exc:
        raise RuntimeError("registered native initialization identity failed") from exc
    _INITIAL_LOADED = loaded
    return dbn, zstd, before


def _check_native_identity(dbn, zstd, expected_manifest: dict) -> None:
    """Reconcile complete registered static and loaded native identities."""
    _identity(_INITIAL_LOADED is not None, "native runtime was not initialized")
    try:
        observed = _static_runtime_manifest(expected_manifest)
        loaded = _loaded_associations(dbn, zstd)
    except (OSError, ImportError, ValueError, KeyError, AttributeError) as exc:
        raise RuntimeError("registered native identity could not be reconciled") from exc
    _identity(
        observed == expected_manifest and loaded == _INITIAL_LOADED,
        "registered native identity changed",
    )


def _identity(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _native_paths() -> dict:
    site = _ROOT / ".venv/Lib/site-packages"
    dbn = site / "databento_dbn"
    zstd = site / "zstandard"
    return {
        "python.exe": _BASE_PYTHON / "python.exe",
        "python312.dll": _BASE_PYTHON / "python312.dll",
        "pyvenv.cfg": _ROOT / ".venv/pyvenv.cfg",
        "dbn_init": dbn / "__init__.py",
        "dbn_metadata": dbn / "metadata.py",
        "dbn_v1": dbn / "v1.py",
        "dbn_v2": dbn / "v2.py",
        "dbn_v3": dbn / "v3.py",
        "dbn_extension": dbn / "_lib.cp312-win_amd64.pyd",
        "dbn_package_metadata": site / "databento_dbn-0.70.0.dist-info/METADATA",
        "zstd_init": zstd / "__init__.py",
        "zstd_extension": zstd / "backend_c.cp312-win_amd64.pyd",
        "zstd_package_metadata": site / "zstandard-0.25.0.dist-info/METADATA",
    }


def _static_runtime_manifest(expected: dict) -> dict:
    _types.validate_body("RuntimeManifest", expected)
    _identity(_types.body_sha256(expected) == _types._RUNTIME_SHA, "unregistered native manifest")
    paths = _native_paths()
    artifacts = []
    metadata = {}
    for entry in expected["artifacts"]:
        path = paths[entry["logical_id"]]
        _identity(not path.is_symlink(), "linked native artifact")
        with path.open("rb") as source:
            raw = source.read(entry["raw_bytes"] + 1)
        observed = {
            "logical_id": entry["logical_id"],
            "kind": entry["kind"],
            "raw_bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
        }
        _identity(observed == entry, "native artifact raw identity mismatch")
        artifacts.append(observed)
        if entry["logical_id"] in ("dbn_package_metadata", "zstd_package_metadata"):
            metadata[entry["logical_id"]] = BytesParser().parsebytes(raw)
    packages = []
    for name, logical_id in (
        ("databento-dbn", "dbn_package_metadata"),
        ("zstandard", "zstd_package_metadata"),
    ):
        record = metadata[logical_id]
        _identity(
            record.get_all("Name") == [name] and len(record.get_all("Version", [])) == 1,
            "native distribution identity mismatch",
        )
        version = record["Version"]
        _identity(type(version) is str, "native distribution version type")
        packages.append(
            {
                "name": name,
                "version": version,
                "metadata_sha256": next(
                    row["raw_sha256"] for row in artifacts if row["logical_id"] == logical_id
                ),
            }
        )
    result = {
        "schema": "native_profile_runtime_manifest_v1",
        "interpreter": {
            "implementation": sys.implementation.name,
            "version": list(sys.version_info[:3]),
            "executable_sha256": next(
                row["raw_sha256"] for row in artifacts if row["logical_id"] == "python.exe"
            ),
        },
        "packages": packages,
        "artifacts": artifacts,
    }
    _identity(result == expected, "complete observed native manifest differs")
    return result


def _loaded_associations(dbn, zstd) -> tuple:
    import ctypes

    paths = {name: path.resolve(strict=True) for name, path in _native_paths().items()}
    kernel = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x800)
    handle_type = ctypes.c_void_p
    kernel.GetModuleHandleExW.argtypes = [
        ctypes.c_uint32,
        ctypes.c_wchar_p,
        ctypes.POINTER(handle_type),
    ]
    kernel.GetModuleHandleExW.restype = ctypes.c_int32
    kernel.GetModuleFileNameW.argtypes = [handle_type, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetModuleFileNameW.restype = ctypes.c_uint32
    kernel.FreeLibrary.argtypes = [handle_type]
    kernel.FreeLibrary.restype = ctypes.c_int32

    def association(logical_id, name, module_file, origin, native):
        _identity(type(module_file) is str, "native module path representation")
        expected = paths[logical_id]
        _identity(Path(module_file).resolve(strict=True) == expected, "native module path mismatch")
        if origin is not None:
            _identity(
                type(origin) is str and Path(origin).resolve(strict=True) == expected,
                "native module origin mismatch",
            )
        mapped = handle_value = None
        if native:
            handle = handle_type()
            if not kernel.GetModuleHandleExW(0, str(expected), ctypes.byref(handle)):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                buffer = ctypes.create_unicode_buffer(32768)
                count = kernel.GetModuleFileNameW(handle, buffer, len(buffer))
                _identity(0 < count < len(buffer), "native mapped path absent/truncated")
                mapped = str(Path(buffer.value).resolve(strict=True))
                _identity(Path(mapped) == expected, "native mapped path mismatch")
                handle_value = handle.value
                if logical_id == "python312.dll":
                    _identity(
                        handle_value == sys.dllhandle, "native Python DLL association mismatch"
                    )
            finally:
                if not kernel.FreeLibrary(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
        return (logical_id, name, str(expected), origin, mapped, handle_value)

    loaded = [
        association("python.exe", "sys.executable", sys.executable, None, True),
        association("python312.dll", "sys.dllhandle", str(paths["python312.dll"]), None, True),
    ]
    for logical_id, name, native in (
        ("dbn_init", "databento_dbn", False),
        ("dbn_metadata", "databento_dbn.metadata", False),
        ("dbn_v1", "databento_dbn.v1", False),
        ("dbn_v2", "databento_dbn.v2", False),
        ("dbn_v3", "databento_dbn.v3", False),
        ("dbn_extension", "databento_dbn._lib", True),
        ("zstd_init", "zstandard", False),
        ("zstd_extension", "zstandard.backend_c", True),
    ):
        module = sys.modules[name]
        loaded.append(
            association(logical_id, name, module.__file__, module.__spec__.origin, native)
        )
    _identity(
        dbn is sys.modules["databento_dbn"]
        and zstd is sys.modules["zstandard"]
        and type(dbn.DBN_VERSION) is int
        and dbn.DBN_VERSION == 3
        and type(zstd.__version__) is str
        and zstd.__version__ == "0.25.0"
        and type(zstd.backend) is str
        and zstd.backend == "cext"
        and type(zstd.ZSTD_VERSION) is tuple
        and all(type(item) is int for item in zstd.ZSTD_VERSION)
        and zstd.ZSTD_VERSION == (1, 5, 7)
        and "zstandard.backend_cffi" not in sys.modules
        and "zstandard.backend_rust" not in sys.modules,
        "native module version/backend association mismatch",
    )
    return tuple(loaded)


def _decompress_frames(member_bytes: bytes, physical_frames: tuple, zstd) -> tuple:
    """Return complete bounded output and every complete frame-span body."""
    chunks = []
    total = 0
    frames = []
    try:
        for physical in physical_frames:
            compressed = member_bytes[physical[1] : physical[2]]
            start = total
            frame_chunks = []
            decoder = zstd.ZstdDecompressor(max_window_size=1048576)
            with io.BytesIO(compressed) as source:
                with decoder.stream_reader(
                    source, read_across_frames=False, read_size=65536
                ) as reader:
                    while True:
                        count = min(65536, 1048576 - total + 1)
                        part = reader.read(count)
                        _require(
                            type(part) is bytes and len(part) <= count,
                            "native reader violated exact bounded-byte interface",
                        )
                        if not part:
                            break
                        total += len(part)
                        _require(total <= 1048576, "complete decompressed byte limit")
                        frame_chunks.append(part)
                    _require(
                        source.tell() == len(compressed), "incomplete frame source read-through"
                    )
            _require(total > start, "every frame must have nonempty complete output")
            _require(
                physical[11] is None or total - start == physical[11],
                "frame content size differs from actual complete output",
            )
            output = b"".join(frame_chunks)
            # Source exhaustion alone is not EOF proof. A positive exact bound
            # selects the qualified same-decoder strict terminal path.
            terminal = decoder.decompress(
                compressed,
                max_output_size=len(output),
                read_across_frames=False,
                allow_extra_data=False,
            )
            _require(
                type(terminal) is bytes and terminal == output, "frame terminal output differs"
            )
            chunks.append(output)
            frames.append(
                {
                    "frame_ordinal": physical[0],
                    "compressed_start": physical[1],
                    "compressed_end": physical[2],
                    "decompressed_start": start,
                    "decompressed_end": total,
                    "compressed_span_sha256": hashlib.sha256(compressed).hexdigest(),
                    "decompressed_span_sha256": hashlib.sha256(output).hexdigest(),
                }
            )
    except zstd.ZstdError as exc:
        raise ValueError("invalid complete compressed member") from exc
    _require(total > 0, "empty complete decompressed member")
    return b"".join(chunks), frames


def _native_integer(value, lower=0, upper=(1 << 64) - 1):
    _require(type(value) is int and lower <= value <= upper, "native integer representation/domain")
    return value


def _native_text(value):
    _require(type(value) is str, "native text representation")
    return value


def _native_enum(value, expected_class, class_name, *, nullable=False, character=False):
    if nullable and value is None:
        return None
    if character and type(value) is str:
        _require(len(value) == 1, "native character representation")
        return {"kind": "str", "value": value}
    _require(type(value) is expected_class, "native enum exact class")
    return {
        "kind": "native_enum",
        "class_name": class_name,
        "name": _native_text(value.name),
        "code": _native_integer(int(value), 0, 65535),
        "text": _native_text(str(value)),
    }


def _native_date(value):
    _require(type(value) is date, "native date exact class")
    return {"kind": "python_date", "year": value.year, "month": value.month, "day": value.day}


def _native_symbols(value):
    _require(type(value) is list and len(value) <= 16, "native symbol collection")
    return [_native_text(item) for item in value]


def _project_metadata(native, dbn) -> dict:
    """Project the exact complete registered native Metadata representation."""
    _require(type(native) is dbn.Metadata, "native Metadata exact class")
    original = native.mappings
    _require(type(original) is dict and len(original) <= 16, "native mapping groups")
    _require(all(type(key) is str for key in original), "native mapping key representation")
    mappings = []
    interval_total = 0
    for key in sorted(original):
        intervals = original[key]
        _require(type(intervals) is list, "native mapping interval collection")
        interval_total += len(intervals)
        _require(interval_total <= 32, "native complete interval limit")
        projected = []
        for item in intervals:
            _require(
                type(item) is dict and set(item) == {"start_date", "end_date", "symbol"},
                "native mapping interval shape",
            )
            _require(all(type(field) is str for field in item), "native mapping interval keys")
            projected.append(
                {
                    "start_date": _native_date(item["start_date"]),
                    "end_date": _native_date(item["end_date"]),
                    "symbol": _native_text(item["symbol"]),
                }
            )
        mappings.append({"raw_symbol": key, "intervals": projected})
    end, limit, mode = native.end, native.limit, native.ts_out
    _require(type(mode) is bool, "native ts_out exact bool")
    body = {
        "version": _native_integer(native.version, 0, 255),
        "dataset": _native_text(native.dataset),
        "schema": _native_enum(native.schema, dbn.Schema, "Schema"),
        "start": _native_integer(native.start),
        "end_observed": None if end is None else _native_integer(end),
        "limit_observed": None if limit is None else _native_integer(limit),
        "stype_in": _native_enum(native.stype_in, dbn.SType, "SType", nullable=True),
        "stype_out": _native_enum(native.stype_out, dbn.SType, "SType"),
        "ts_out": mode,
        "symbol_cstr_len": _native_integer(native.symbol_cstr_len, 0, 65535),
        "symbols": _native_symbols(native.symbols),
        "partial": _native_symbols(native.partial),
        "not_found": _native_symbols(native.not_found),
        "mappings": mappings,
    }
    _types.validate_body("MetadataProjection", body)
    return body


def _project_mbo(native, dbn) -> dict:
    """Project every exact registered MBO observation field."""
    _require(type(native) is dbn.MBOMsg, "native MBO exact class")
    body = {
        "rtype": _native_enum(native.rtype, dbn.RType, "RType"),
        "publisher_id": _native_integer(native.publisher_id, 0, 65535),
        "instrument_id": _native_integer(native.instrument_id, 0, (1 << 32) - 1),
        "ts_event": _native_integer(native.ts_event),
        "order_id": _native_integer(native.order_id),
        "price": _native_integer(native.price, -(1 << 63), (1 << 63) - 1),
        "size": _native_integer(native.size, 0, (1 << 32) - 1),
        "action": _native_enum(native.action, dbn.Action, "Action", character=True),
        "side": _native_enum(native.side, dbn.Side, "Side", character=True),
        "ts_recv": _native_integer(native.ts_recv),
        "flags": _native_integer(native.flags, 0, 255),
        "channel_id": _native_integer(native.channel_id, 0, 255),
        "ts_in_delta": _native_integer(native.ts_in_delta, -(1 << 31), (1 << 31) - 1),
        "sequence": _native_integer(native.sequence, 0, (1 << 32) - 1),
        "ts_out_observed": _native_integer(native.ts_out),
        "record_size_observed": _native_integer(native.record_size(), 0, 1020),
        "ts_index_observed": _native_integer(native.ts_index),
    }
    _types.validate_body("MboObservation", body)
    return body


def _request_preflight(request, execution_manifest):
    _require(
        type(request) is dict
        and all(type(key) is str for key in request)
        and set(request) == _REQUEST_FIELDS,
        "private request exact fields",
    )
    _require(
        type(request["schema"]) is str
        and request["schema"] == "native_member_worker_request_v1"
        and type(request["operation"]) is str
        and request["operation"] == "decode",
        "private request schema/operation",
    )
    for field in _REQUEST_FIELDS - {"schema", "operation", "context", "member_hex"}:
        value = request[field]
        _require(
            type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
            "private request digest/token syntax",
        )
    protocol = _types.protocol_body()
    profile = _types.profile_body()
    for field, expected in (
        ("expected_protocol_sha256", _types.body_sha256(protocol)),
        ("expected_profile_sha256", _types.body_sha256(profile)),
        ("expected_runtime_manifest_sha256", _types.body_sha256(profile["runtime_manifest"])),
    ):
        _require(request[field] == expected, "private request known identity mismatch")
    _types.validate_body("Context", request["context"])
    _require(len(_types.canonical_bytes(request["context"])) <= 65536, "private Context cap")
    _require(
        type(execution_manifest) is dict
        and len(_types.canonical_bytes(execution_manifest)) <= 65536,
        "private execution registration shape/cap",
    )
    _require(
        _types.body_sha256(execution_manifest) == request["execution_manifest_sha256"],
        "private execution registration identity mismatch",
    )
    _require(
        execution_manifest.get("schema") == "native_member_provider_execution_v1",
        "private execution registration schema",
    )
    for name in ("protocol_sha256", "profile_sha256", "runtime_manifest_sha256"):
        _require(
            execution_manifest.get(name) == request["expected_" + name],
            "private execution registration known identity mismatch",
        )
    encoded = request["member_hex"]
    _require(
        type(encoded) is str
        and 2 <= len(encoded) <= 524288
        and len(encoded) % 2 == 0
        and re.fullmatch("[0-9a-f]+", encoded) is not None,
        "private complete member hex",
    )
    member = bytes.fromhex(encoded)
    _require(
        hashlib.sha256(member).hexdigest() == request["expected_member_sha256"],
        "private complete member identity mismatch",
    )
    return member, protocol


def _wire_body(kind, original):
    body = dict(original)
    if kind == "Metadata":
        for name in (
            "reserved_bytes",
            "symbols",
            "partial",
            "not_found",
            "alignment_padding_bytes",
        ):
            body[name] = list(original[name])
        body["mappings"] = [
            {
                "raw_symbol": group["raw_symbol"],
                "interval_count": group["interval_count"],
                "intervals": [dict(interval) for interval in group["intervals"]],
            }
            for group in original["mappings"]
        ]
    return body


def _dbn_report(raw, wire):
    spans = []
    for index, ((kind, start, stop), original) in enumerate(
        zip(wire["wire_spans"], wire["wire_bodies"], strict=True), 1
    ):
        body = _wire_body(kind, original)
        spans.append(
            {
                "wire_span_ordinal": index,
                "kind": kind,
                "decompressed_start": start,
                "decompressed_end": stop,
                "wire_sha256": hashlib.sha256(raw[start:stop]).hexdigest(),
                "wire_fields": body,
                "wire_fields_sha256": _types.body_sha256(body),
            }
        )
    report = {
        "decompressed_bytes": len(raw),
        "decompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "spans": spans,
    }
    report["report_sha256"] = _types.body_sha256(report)
    _types.validate_body("DbnFramingReport", report)
    return report


def _decode_occurrences(raw, report, request, dbn):
    occurrences = []
    try:
        decoder = dbn.DBNDecoder(
            has_metadata=True,
            ts_out=False,
            input_version=None,
            upgrade_policy=dbn.VersionUpgradePolicy.AS_IS,
            compression=dbn.Compression.NONE,
        )

        def append(batch):
            _require(
                type(batch) is list and len(occurrences) + len(batch) <= 128,
                "native batch type/complete position cap",
            )
            for native in batch:
                index = len(occurrences)
                _require(
                    index < len(report["spans"]),
                    "native occurrence exceeds complete wire positions",
                )
                span = report["spans"][index]
                if index == 0:
                    projection = _project_metadata(native, dbn)
                    # Revalidate even if a controlled test replaced the projector.
                    _types.validate_body("MetadataProjection", projection)
                    _require(
                        projection["ts_out"] is request["context"]["expected_ts_out"],
                        "actual Metadata ts_out differs from Context",
                    )
                    _require(
                        _types.body_sha256(projection) == request["expected_metadata_sha256"],
                        "complete actual Metadata identity differs",
                    )
                else:
                    projection = _project_mbo(native, dbn)
                    _types.validate_body("MboObservation", projection)
                _require(
                    projection == _types.wire_projection(span["kind"], span["wire_fields"]),
                    "complete native projection differs from original wire body",
                )
                occurrences.append(
                    {
                        "decoded_position": index + 1,
                        "kind": span["kind"],
                        "wire_span_ordinal": index + 1,
                        "projection": projection,
                        "projection_sha256": _types.body_sha256(projection),
                    }
                )

        # One decoder receives the entire continuous DBN member. A native batch
        # may already parse records; only wrapper getter ordering is promised.
        decoder.write(raw)
        append(decoder.decode())
        append(decoder.decode())
        remaining = decoder.buffer()
        _require(type(remaining) is bytes and not remaining, "complete native buffer must be empty")
        _require(len(occurrences) == len(report["spans"]), "complete native/wire count mismatch")
    except dbn.DBNError as exc:
        raise ValueError("invalid complete DBN member") from exc
    return occurrences


def decode_request(request_body: dict, execution_manifest: dict) -> dict:
    """Reconstruct complete evidence inside the separately contained worker."""
    member, protocol = _request_preflight(request_body, execution_manifest)
    physical = inspect_zstd_frames(member)
    dbn, zstd, runtime = _load_native_runtime()
    _types.validate_body("RuntimeManifest", runtime)
    _identity(
        _types.body_sha256(runtime) == request_body["expected_runtime_manifest_sha256"],
        "actual native runtime manifest differs",
    )
    _check_native_identity(dbn, zstd, runtime)
    raw, frame_spans = _decompress_frames(member, physical, zstd)
    wire = inspect_dbn_wire(raw)
    dbn_report = _dbn_report(raw, wire)
    zstd_report = {
        "compressed_bytes": len(member),
        "compressed_sha256": hashlib.sha256(member).hexdigest(),
        "decompressed_bytes": len(raw),
        "decompressed_sha256": hashlib.sha256(raw).hexdigest(),
        "frames": frame_spans,
    }
    zstd_report["report_sha256"] = _types.body_sha256(zstd_report)
    _types.validate_body("ZstdFramingReport", zstd_report)
    _check_native_identity(dbn, zstd, runtime)
    occurrences = _decode_occurrences(raw, dbn_report, request_body, dbn)
    terminal = {
        "compressed_bytes": len(member),
        "compressed_sha256": zstd_report["compressed_sha256"],
        "decompressed_bytes": len(raw),
        "decompressed_sha256": zstd_report["decompressed_sha256"],
        "frame_count": len(frame_spans),
        "decoded_positions": len(occurrences),
        "metadata_count": 1,
        "mbo_count": len(occurrences) - 1,
        "dbn_remaining_buffer_bytes": 0,
        "zstd_framing_sha256": zstd_report["report_sha256"],
        "dbn_framing_sha256": dbn_report["report_sha256"],
        "framing_status": "complete_independent_v3_mbo_framing",
        "zstd_status": "complete_nonempty_frames_native_terminal_equality",
    }
    body = {
        "status": "complete_member_consistency_not_source_authentication",
        "protocol_sha256": request_body["expected_protocol_sha256"],
        "profile_sha256": request_body["expected_profile_sha256"],
        "runtime_manifest": runtime,
        "runtime_manifest_sha256": _types.body_sha256(runtime),
        "context_sha256": _types.body_sha256(request_body["context"]),
        "member_sha256": zstd_report["compressed_sha256"],
        "metadata_sha256": occurrences[0]["projection_sha256"],
        "occurrences": occurrences,
        "zstd_framing": zstd_report,
        "dbn_framing": dbn_report,
        "terminal": terminal,
        "authorities": [[name, False] for name in protocol["authority_names"]],
    }
    body["evidence_sha256"] = _types.body_sha256(body)
    _types.validate_body("MemberDecodeEvidence", body)
    _check_native_identity(dbn, zstd, runtime)
    return body
