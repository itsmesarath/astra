"""Fixed invented proof modes; native modes require registered containment."""

import base64
import hashlib
import importlib
import io
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC_MANIFEST = ROOT / "logs/native_profile_20261012_1/artifacts_static.json"
STATIC_MANIFEST_SHA256 = "74b2044bba66e8c229669ac2dd2731ecd89205275a9d24ebaf54febbc9edd139"
ORACLE_PATH = ROOT / "tests/native_profile_oracles_20261012_1.py"
ORACLE_SHA256 = "4314a212d8e62047ab92b56028784b3914975391e2a2cbe78dee2bb7c7793ba4"
ENUM_ORACLE_SHA256 = "a27abb7efaece7797e22fd147f9dfbc2c29d5e79ee4c4058c440173ef91596ec"
COMPOSED_ORACLE_SHA256 = "fbb532130c6ac49ba05b1011baaf586e4f29939628d053cc47f450cff87159f8"
NEGATIVE_ORACLE_SHA256 = "d5db004581c115eb02194dd355b3a789024d670e038f8a01f05a6229b675cb3f"
CAPACITY_ORACLE_SHA256 = "739b81a4cca047d1f55c480bba4d0e6bf9597dd6ccc16b3e164c83f339459bcf"
ZSTD_CAPACITY_ORACLE_SHA256 = "17c91e7c6697df7f95b05fc5dbf25083fe486501afc06d008f793ac93b6193f4"


class _WireReader:
    """A bounded cursor whose nonempty reads cover one complete occurrence."""

    def __init__(self, data, start, end):
        self.data = data
        self.cursor = start
        self.end = end
        self.fields = []

    def take(self, name, size):
        start = self.cursor
        end = start + size
        if size <= 0 or end > self.end:
            raise ValueError("truncated or invalid field: " + name)
        self.cursor = end
        self.fields.append((name, start, end))
        return self.data[start:end]

    def integer(self, name, size, *, signed=False):
        return int.from_bytes(self.take(name, size), "little", signed=signed)

    def cstring(self, name, size):
        raw = self.take(name, size)
        stop = raw.find(b"\0")
        if stop < 0 or any(raw[stop:]):
            raise ValueError("missing terminator or nonzero string padding: " + name)
        try:
            return raw[:stop].decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid UTF-8: " + name) from exc

    def calendar_integer(self, name):
        raw = self.integer(name, 4)
        year, tail = divmod(raw, 10000)
        month, day = divmod(tail, 100)
        try:
            date(year, month, day)
        except ValueError as exc:
            raise ValueError("invalid mapping date: " + name) from exc
        return raw


def _metadata_wire(data, header_end):
    reader = _WireReader(data, 0, header_end)
    body = {
        "magic_hex": reader.take("magic", 3).hex(),
        "version": reader.integer("version", 1),
        "length_body": reader.integer("length_body", 4),
        "dataset": reader.cstring("dataset", 16),
        "dataset_cstr_bytes": 16,
        "schema": reader.integer("schema", 2),
        "start": reader.integer("start", 8),
        "end": reader.integer("end", 8),
        "limit": reader.integer("limit", 8),
        "stype_in": reader.integer("stype_in", 1),
        "stype_out": reader.integer("stype_out", 1),
        "ts_out": reader.integer("ts_out", 1),
        "symbol_cstr_len": reader.integer("symbol_cstr_len", 2),
        "reserved_bytes": tuple(reader.take("reserved", 53)),
        "schema_definition_length": reader.integer("schema_definition_length", 4),
    }
    if (
        body["magic_hex"] != "44424e"
        or body["version"] != 3
        or body["length_body"] + 8 != header_end
        or body["schema"] != 0
        or body["stype_in"] not in (*range(16), 255)
        or body["stype_out"] not in range(16)
        or body["ts_out"] not in (0, 1)
        or body["symbol_cstr_len"] != 71
        or any(body["reserved_bytes"])
        or body["schema_definition_length"] != 0
    ):
        raise ValueError("unsupported or noncanonical v3 MBO metadata")
    for name in ("symbols", "partial", "not_found"):
        count = reader.integer(name + "_count", 4)
        if count > 16:
            raise ValueError("metadata list exceeds registered bound")
        body[name + "_count"] = count
        body[name] = tuple(reader.cstring(f"{name}[{i}]", 71) for i in range(count))
    groups = reader.integer("mappings_count", 4)
    if groups > 16:
        raise ValueError("mapping groups exceed registered bound")
    body["mappings_count"] = groups
    mappings = []
    seen = set()
    intervals_seen = 0
    for i in range(groups):
        prefix = f"mappings[{i}]"
        raw_symbol = reader.cstring(prefix + ".raw_symbol", 71)
        if raw_symbol in seen:
            raise ValueError("duplicate original mapping group key")
        seen.add(raw_symbol)
        count = reader.integer(prefix + ".interval_count", 4)
        intervals_seen += count
        if intervals_seen > 32:
            raise ValueError("mapping intervals exceed registered bound")
        intervals = []
        for j in range(count):
            item = f"{prefix}.intervals[{j}]"
            intervals.append(
                {
                    "start_date": reader.calendar_integer(item + ".start_date"),
                    "end_date": reader.calendar_integer(item + ".end_date"),
                    "symbol": reader.cstring(item + ".symbol", 71),
                }
            )
        mappings.append(
            {"raw_symbol": raw_symbol, "interval_count": count, "intervals": tuple(intervals)}
        )
    body["mappings"] = tuple(mappings)
    padding = (-reader.cursor) % 8
    if reader.cursor + padding != header_end:
        raise ValueError("unexplained metadata tail or missing alignment")
    raw_padding = reader.take("alignment_padding", padding) if padding else b""
    if any(raw_padding):
        raise ValueError("nonzero metadata alignment padding")
    body["alignment_padding_bytes"] = tuple(raw_padding)
    return body, tuple(reader.fields)


def _mbo_wire(data, start, end, has_ts_out):
    reader = _WireReader(data, start, end)
    fields = (
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
    body = {name: reader.integer(name, size, signed=signed) for name, size, signed in fields}
    body["ts_out"] = reader.integer("ts_out", 8) if has_ts_out else None
    if (
        body["length_words"] != (16 if has_ts_out else 14)
        or body["rtype"] != 160
        or reader.cursor != end
    ):
        raise ValueError("unsupported or incomplete MBO record")
    return body, tuple(reader.fields)


def inspect_dbn_wire(data):
    """Independently frame complete invented DBN bytes before native parsing."""
    if type(data) is not bytes or not 128 <= len(data) <= 1048576:
        raise ValueError("complete DBN must be exact bytes within registered bounds")
    if data[:4] != b"DBN\x03":
        raise ValueError("explicit DBN v3 header required")
    header_end = 8 + int.from_bytes(data[4:8], "little")
    if not 128 <= header_end <= min(65536, len(data)) or header_end % 8:
        raise ValueError("invalid complete metadata size")
    metadata, metadata_fields = _metadata_wire(data, header_end)
    record_size = 64 if metadata["ts_out"] else 56
    rest = len(data) - header_end
    if rest % record_size or not 1 <= rest // record_size <= 127:
        raise ValueError("complete positions must be 2..128 with no record tail")
    spans = [("Metadata", 0, header_end)]
    bodies = [metadata]
    field_spans = [metadata_fields]
    for start in range(header_end, len(data), record_size):
        end = start + record_size
        body, fields = _mbo_wire(data, start, end, metadata["ts_out"] == 1)
        spans.append(("MBO", start, end))
        bodies.append(body)
        field_spans.append(fields)
    return {
        "complete_bytes": len(data),
        "wire_spans": tuple(spans),
        "wire_bodies": tuple(bodies),
        "field_spans": tuple(field_spans),
    }


def inspect_zstd_frames(data):
    """Independently cover every physical frame span before native decoding."""
    if type(data) is not bytes or not 1 <= len(data) <= 262144:
        raise ValueError("complete compressed member must be bounded exact bytes")
    cursor = 0
    frames = []
    known_total = 0

    def take(count):
        nonlocal cursor
        if count < 0 or cursor + count > len(data):
            raise ValueError("incomplete physical frame")
        result = data[cursor : cursor + count]
        cursor += count
        return result

    while cursor < len(data):
        if len(frames) >= 16:
            raise ValueError("frame-count bound")
        start = cursor
        if take(4) != b"\x28\xb5\x2f\xfd":
            raise ValueError("standard frame magic required; no skippable or tail")
        descriptor = take(1)[0]
        size_flag = descriptor >> 6
        single = bool(descriptor & 32)
        checksum = bool(descriptor & 4)
        dictionary_flag = descriptor & 3
        if descriptor & 24 or dictionary_flag:
            raise ValueError("reserved/unused header bits or dictionary IDs forbidden")
        window_descriptor = None
        window = None
        if not single:
            window_descriptor = take(1)[0]
            base = 1 << (10 + (window_descriptor >> 3))
            window = base + (base >> 3) * (window_descriptor & 7)
            if window > 1048576:
                raise ValueError("window exceeds qualified bound")
        size_bytes = (1 if single else 0) if size_flag == 0 else (2, 4, 8)[size_flag - 1]
        content_size = None
        if size_bytes:
            content_size = int.from_bytes(take(size_bytes), "little")
            if size_flag == 1:
                content_size += 256
            known_total += content_size
            if content_size > 1048576 or known_total > 1048576:
                raise ValueError("known output exceeds qualified cumulative bound")
        if single:
            window = content_size
        header_end = cursor
        blocks = []
        last = False
        while not last:
            block_start = cursor
            block_header = int.from_bytes(take(3), "little")
            last = bool(block_header & 1)
            block_type = (block_header >> 1) & 3
            block_size = block_header >> 3
            if block_type == 3 or block_size > min(window, 131072):
                raise ValueError("reserved block or size exceeds frame block maximum")
            payload_start = cursor
            take(1 if block_type == 1 else block_size)
            blocks.append(
                (
                    len(blocks) + 1,
                    block_start,
                    payload_start,
                    last,
                    block_type,
                    block_size,
                    payload_start,
                    cursor,
                )
            )
        checksum_value = int.from_bytes(take(4), "little") if checksum else None
        frames.append(
            (
                len(frames) + 1,
                start,
                cursor,
                start,
                header_end,
                descriptor,
                window_descriptor,
                size_flag,
                single,
                dictionary_flag,
                checksum,
                content_size,
                window,
                None,
                checksum_value,
                tuple(blocks),
            )
        )
    return tuple(frames)


def inspect_loaded_native_identity():
    """Qualify fixed artifacts and observed loaded associations inside containment."""
    implementation = getattr(getattr(sys, "implementation", None), "name", None)
    if type(implementation) is not str or implementation != "cpython":
        raise ValueError("registered exact CPython implementation required")
    version = tuple(sys.version_info[:3])
    flags = (sys.flags.isolated, sys.flags.no_site, sys.flags.dont_write_bytecode)
    if version != (3, 12, 10) or any(type(flag) is not int or flag != 1 for flag in flags):
        raise ValueError("registered isolated/no-site/no-bytecode Python required")
    before = _static_artifact_snapshot()
    modules = _import_native_modules()
    loaded = _loaded_identity(modules)
    after = _static_artifact_snapshot()
    if before != after:
        raise ValueError("registered artifacts changed during native initialization")
    return {
        "status": "registered_loaded_identity_consistency_only",
        "python_version": version,
        "python_implementation": implementation,
        "isolated": flags[0],
        "no_site": flags[1],
        "dont_write_bytecode": flags[2],
        "artifact_manifest_sha256": STATIC_MANIFEST_SHA256,
        "artifacts_before": before,
        "modules_loaded": loaded["modules_loaded"],
        "artifacts_after": after,
        "backend": loaded["backend"],
        "dbn_version": loaded["dbn_version"],
        "zstd_package_version": loaded["zstd_package_version"],
        "zstd_library_version": loaded["zstd_library_version"],
        "constructor_calls": 0,
    }


def _static_artifact_snapshot():
    registry = _artifact_manifest()
    observed = []
    for entry in registry["artifacts"]:
        path = Path(entry["path"])
        with path.open("rb") as source:
            raw = source.read(67108865)
        if (
            len(raw) != entry["raw_bytes"]
            or len(raw) > 67108864
            or hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]
        ):
            raise ValueError("registered artifact bytes changed: " + entry["logical_id"])
        observed.append(
            {
                "logical_id": entry["logical_id"],
                "path": entry["path"],
                "raw_bytes": len(raw),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return tuple(observed)


def _artifact_manifest():
    with STATIC_MANIFEST.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != STATIC_MANIFEST_SHA256:
        raise ValueError("fixed artifact manifest raw identity mismatch")
    registry = json.loads(raw)
    if (
        registry["schema"] != "native_profile_provisional_artifacts_v1"
        or len(registry["artifacts"]) != 13
    ):
        raise ValueError("fixed artifact registration shape mismatch")
    return registry


def _package_version(logical_id, expected_name):
    from email.parser import BytesParser

    entry = next(
        item for item in _artifact_manifest()["artifacts"] if item["logical_id"] == logical_id
    )
    with Path(entry["path"]).open("rb") as source:
        raw = source.read(65537)
    if (
        len(raw) != entry["raw_bytes"]
        or len(raw) > 65536
        or hashlib.sha256(raw).hexdigest() != entry["raw_sha256"]
    ):
        raise ValueError("registered distribution metadata changed")
    metadata = BytesParser().parsebytes(raw)
    if metadata.get_all("Name") != [expected_name] or len(metadata.get_all("Version", [])) != 1:
        raise ValueError("registered distribution name/version mismatch")
    return metadata["Version"]


def _import_native_modules():
    if any(
        name == "databento_dbn"
        or name.startswith("databento_dbn.")
        or name == "zstandard"
        or name.startswith("zstandard.")
        for name in sys.modules
    ):
        raise ValueError("native modules must be freshly initialized in this child")
    site = str(ROOT / ".venv/Lib/site-packages")
    if site in sys.path:
        raise ValueError("registered native site unexpectedly present before explicit setup")
    sys.path.append(site)
    # Process-local only. Isolated startup does not process .pth/site initialization.
    os.environ["PYTHON_ZSTANDARD_IMPORT_POLICY"] = "cext"
    return {
        "dbn": importlib.import_module("databento_dbn"),
        "zstd": importlib.import_module("zstandard"),
    }


def _loaded_identity(modules):
    import ctypes as ctypes_module

    paths = {
        entry["logical_id"]: Path(entry["path"]).resolve(strict=True)
        for entry in _artifact_manifest()["artifacts"]
    }
    api = ctypes_module.WinDLL("kernel32", use_last_error=True, winmode=0x800)
    handle_type = ctypes_module.c_void_p
    api.GetModuleHandleExW.argtypes = [
        ctypes_module.c_uint32,
        ctypes_module.c_wchar_p,
        ctypes_module.POINTER(handle_type),
    ]
    api.GetModuleHandleExW.restype = ctypes_module.c_int32
    api.GetModuleFileNameW.argtypes = [handle_type, ctypes_module.c_wchar_p, ctypes_module.c_uint32]
    api.GetModuleFileNameW.restype = ctypes_module.c_uint32
    api.FreeLibrary.argtypes = [handle_type]
    api.FreeLibrary.restype = ctypes_module.c_int32

    def association(logical_id, module_name, module_file, spec_origin, *, native=False):
        expected = paths[logical_id]
        if Path(module_file).resolve(strict=True) != expected:
            raise ValueError("loaded module file mismatch: " + logical_id)
        if spec_origin is not None and Path(spec_origin).resolve(strict=True) != expected:
            raise ValueError("loaded module spec origin mismatch: " + logical_id)
        mapped = None
        handle_value = None
        if native:
            handle = handle_type()
            # Increment the refcount while querying this exact full-path module.
            if not api.GetModuleHandleExW(0, str(expected), ctypes_module.byref(handle)):
                raise ctypes_module.WinError(ctypes_module.get_last_error())
            try:
                buffer = ctypes_module.create_unicode_buffer(32768)
                count = api.GetModuleFileNameW(handle, buffer, len(buffer))
                if not 0 < count < len(buffer):
                    raise ValueError("loaded module path absent or truncated")
                mapped = str(Path(buffer.value).resolve(strict=True))
                if Path(mapped) != expected:
                    raise ValueError("mapped native module path mismatch")
                handle_value = handle.value
                if logical_id == "python312.dll" and handle_value != sys.dllhandle:
                    raise ValueError("Python DLL handle is not sys.dllhandle")
            finally:
                if not api.FreeLibrary(handle):
                    raise ctypes_module.WinError(ctypes_module.get_last_error())
        return {
            "logical_id": logical_id,
            "module_name": module_name,
            "module_file": str(expected),
            "spec_origin": spec_origin,
            "mapped_path": mapped,
            "module_handle": handle_value,
        }

    loaded = [
        association("python.exe", "sys.executable", sys.executable, None, native=True),
        association(
            "python312.dll", "sys.dllhandle", str(paths["python312.dll"]), None, native=True
        ),
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
            association(logical_id, name, module.__file__, module.__spec__.origin, native=native)
        )
    dbn = modules["dbn"]
    zstd = modules["zstd"]
    # DBN does not expose a package __version__ getter in this pinned module.
    # Distribution version is measured from its separately pinned METADATA.
    dbn_version = _package_version("dbn_package_metadata", "databento-dbn")
    zstd_version = _package_version("zstd_package_metadata", "zstandard")
    if (
        dbn is not sys.modules["databento_dbn"]
        or zstd is not sys.modules["zstandard"]
        or dbn_version != "0.70.0"
        or zstd_version != "0.25.0"
        or zstd.__version__ != zstd_version
        or type(dbn.DBN_VERSION) is not int
        or dbn.DBN_VERSION != 3
        or zstd.backend != "cext"
        or tuple(zstd.ZSTD_VERSION) != (1, 5, 7)
        or "zstandard.backend_cffi" in sys.modules
        or "zstandard.backend_rust" in sys.modules
    ):
        raise ValueError("registered native versions/backend/module association mismatch")
    return {
        "modules_loaded": tuple(loaded),
        "backend": zstd.backend,
        "dbn_version": dbn_version,
        "zstd_package_version": zstd_version,
        "zstd_library_version": tuple(zstd.ZSTD_VERSION),
    }


def _literal_packet(kind="primary"):
    # The reviewed declaration-only bytes are pinned before execution. No second read.
    if kind == "primary":
        path, expected = ORACLE_PATH, ORACLE_SHA256
    elif kind == "enum":
        path = ROOT / "tests/native_profile_enum_oracles_20261012_1.py"
        expected = ENUM_ORACLE_SHA256
    elif kind == "composed":
        path = ROOT / "tests/native_profile_composed_oracles_20261012_1.py"
        expected = COMPOSED_ORACLE_SHA256
    elif kind == "negative":
        path = ROOT / "tests/native_profile_native_negative_oracles_20261012_1.py"
        expected = NEGATIVE_ORACLE_SHA256
    elif kind == "capacity":
        path = ROOT / "tests/native_profile_capacity_oracles_20261012_1.py"
        expected = CAPACITY_ORACLE_SHA256
    elif kind == "zstd_capacity":
        path = ROOT / "tests/native_profile_zstd_capacity_oracles_20261012_1.py"
        expected = ZSTD_CAPACITY_ORACLE_SHA256
    else:
        raise ValueError("unregistered literal packet")
    with path.open("rb") as source:
        raw = source.read(1048577)
    if len(raw) > 1048576 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("independent literal packet changed")
    namespace = {"__file__": str(path)}
    exec(compile(raw, str(path), "exec"), namespace)
    return namespace


def _exact_integer(value, lower=0, upper=18446744073709551615):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError("unexpected raw native integer representation")
    return value


def _exact_text(value):
    if type(value) is not str:
        raise ValueError("unexpected native text representation")
    return value


def _native_enum(value, expected_class, *, nullable=False, unknown_char=False):
    if nullable and value is None:
        return None
    if unknown_char and type(value) is str:
        if len(value) != 1:
            raise ValueError("native unknown character is not one character")
        return {"kind": "str", "value": value}
    if type(value) is not expected_class:
        raise ValueError("unexpected native enum class")
    return {
        "kind": "native_enum",
        "class_name": expected_class.__name__,
        "name": _exact_text(value.name),
        "code": _exact_integer(int(value)),
        "text": _exact_text(str(value)),
    }


def _native_date(value):
    if type(value) is not date:
        raise ValueError("unexpected native mapping date")
    return {"kind": "python_date", "year": value.year, "month": value.month, "day": value.day}


def _native_text_list(value):
    if type(value) is not list or len(value) > 16:
        raise ValueError("unexpected native string-list shape")
    return tuple(_exact_text(item) for item in value)


def _native_metadata(value, dbn):
    if type(value) is not dbn.Metadata:
        raise ValueError("unexpected metadata object")
    mappings = value.mappings
    if type(mappings) is not dict or len(mappings) > 16:
        raise ValueError("unexpected native mapping projection")
    if any(type(key) is not str for key in mappings):
        raise ValueError("unexpected native mapping key")
    projected = []
    total = 0
    for key in sorted(mappings):
        intervals = mappings[key]
        if type(intervals) is not list:
            raise ValueError("unexpected native intervals")
        total += len(intervals)
        if total > 32:
            raise ValueError("native interval projection exceeds bound")
        rows = []
        for interval in intervals:
            if type(interval) is not dict or interval.keys() != {
                "start_date",
                "end_date",
                "symbol",
            }:
                raise ValueError("unexpected native interval fields")
            rows.append(
                {
                    "start_date": _native_date(interval["start_date"]),
                    "end_date": _native_date(interval["end_date"]),
                    "symbol": _exact_text(interval["symbol"]),
                }
            )
        projected.append({"raw_symbol": key, "intervals": tuple(rows)})
    end, limit, ts_out = value.end, value.limit, value.ts_out
    if type(ts_out) is not bool:
        raise ValueError("unexpected native ts_out representation")
    return {
        "kind": "Metadata",
        "version": _exact_integer(value.version, 0, 255),
        "dataset": _exact_text(value.dataset),
        "schema": _native_enum(value.schema, dbn.Schema, nullable=True),
        "start": _exact_integer(value.start),
        "end": None if end is None else _exact_integer(end),
        "limit": None if limit is None else _exact_integer(limit),
        "stype_in": _native_enum(value.stype_in, dbn.SType, nullable=True),
        "stype_out": _native_enum(value.stype_out, dbn.SType),
        "ts_out": ts_out,
        "symbol_cstr_len": _exact_integer(value.symbol_cstr_len, 0, 65535),
        "symbols": _native_text_list(value.symbols),
        "partial": _native_text_list(value.partial),
        "not_found": _native_text_list(value.not_found),
        "mappings": tuple(projected),
    }


def _native_mbo(value, dbn):
    if type(value) is not dbn.MBOMsg:
        raise ValueError("unexpected native record class")
    return {
        "kind": "MBO",
        "rtype": _native_enum(value.rtype, dbn.RType),
        "publisher_id": _exact_integer(value.publisher_id, 0, 65535),
        "instrument_id": _exact_integer(value.instrument_id, 0, 4294967295),
        "ts_event": _exact_integer(value.ts_event),
        "order_id": _exact_integer(value.order_id),
        "price": _exact_integer(value.price, -9223372036854775808, 9223372036854775807),
        "size": _exact_integer(value.size, 0, 4294967295),
        "flags": _exact_integer(value.flags, 0, 255),
        "channel_id": _exact_integer(value.channel_id, 0, 255),
        "action": _native_enum(value.action, dbn.Action, unknown_char=True),
        "side": _native_enum(value.side, dbn.Side, unknown_char=True),
        "ts_recv": _exact_integer(value.ts_recv),
        "ts_in_delta": _exact_integer(value.ts_in_delta, -2147483648, 2147483647),
        "sequence": _exact_integer(value.sequence, 0, 4294967295),
        "ts_out": _exact_integer(value.ts_out),
        "record_size": _exact_integer(value.record_size(), 0, 1020),
        "ts_index": _exact_integer(value.ts_index),
    }


def _decode_dbn_partition(dbn, raw, mode):
    # Fresh state for each (case, partition); no resets across its chunks.
    decoder = dbn.DBNDecoder(
        has_metadata=True,
        ts_out=False,
        input_version=None,
        upgrade_policy=dbn.VersionUpgradePolicy.AS_IS,
        compression=dbn.Compression.NONE,
    )
    chunk_size = {"complete": len(raw), "chunks7": 7, "bytewise": 1}[mode]
    lengths = []
    observations = []

    def append_batch(batch):
        if type(batch) is not list:
            raise ValueError("unexpected native decode batch")
        if len(observations) + len(batch) > 128:
            raise ValueError("native complete position bound")
        for value in batch:
            observations.append(
                _native_metadata(value, dbn)
                if type(value) is dbn.Metadata
                else _native_mbo(value, dbn)
            )

    for start in range(0, len(raw), chunk_size):
        chunk = raw[start : start + chunk_size]
        lengths.append(len(chunk))
        if mode == "bytewise":
            append_batch(decoder.write_and_decode(chunk))
        else:
            decoder.write(chunk)
            append_batch(decoder.decode())
    append_batch(decoder.decode())
    remaining = decoder.buffer()
    if type(remaining) is not bytes:
        raise ValueError("unexpected decoder buffer representation")
    if remaining:
        raise ValueError("framed complete DBN left native buffered bytes")
    return {
        "mode": mode,
        "chunk_lengths": tuple(lengths),
        "observations": tuple(observations),
        "buffer_hex": remaining.hex(),
    }


def _final_native_identity(initial, modules):
    artifacts = _static_artifact_snapshot()
    loaded = _loaded_identity(modules)
    if artifacts != initial["artifacts_before"] or any(
        loaded[name] != initial[name] for name in loaded
    ):
        raise ValueError("native artifacts or loaded associations changed during traversal")
    return artifacts, loaded


def inspect_native_dbn_members():
    """Observe the complete registered literal DBN cohort in a contained child."""
    packet = _literal_packet()
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    positives = (
        tuple(case for case in packet["DBN_CASES"] if not case["strict_profile_refusal"])
        + packet["DBN_STYPE_CASES"]
    )
    cases = []
    for case in positives:
        raw = bytes.fromhex(case["dbn_hex"])
        framing = inspect_dbn_wire(raw)
        partitions = tuple(
            _decode_dbn_partition(modules["dbn"], raw, mode)
            for mode in ("complete", "chunks7", "bytewise")
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "framing": framing,
                "partitions": partitions,
            }
        )
    negative = tuple(
        (case["case_id"], case["dbn_hex"])
        for case in packet["DBN_CASES"]
        if case["strict_profile_refusal"]
    )
    negative += packet["DBN_FRAMING_NEGATIVE_CASES"] + packet["DBN_STYPE_NEGATIVE_CASES"]
    refusals = []
    for name, input_hex in negative:
        try:
            inspect_dbn_wire(bytes.fromhex(input_hex))
        except ValueError:
            refusals.append(
                {
                    "case_id": name,
                    "input_hex": input_hex,
                    "phase": "independent_preflight",
                    "constructor_calls": 0,
                }
            )
        else:
            raise ValueError("strict candidate unexpectedly passed independent preflight")
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_dbn_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": ORACLE_SHA256,
        "identity": identity,
        "policy": {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
        "cases": tuple(cases),
        "strict_refusals": tuple(refusals),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


class OutputLimitExceeded(ValueError):
    """The single bounded excess byte was observed, never returned as success."""

    def __init__(self, observed_bytes):
        super().__init__("cumulative native output exceeded 1048576 bytes")
        self.observed_bytes = observed_bytes


def _zstd_policy():
    return {
        "backend": "cext",
        "read_across_frames": False,
        "read_size": 65536,
        "max_window_size_argument": 1048576,
        "independent_window_cap": 1048576,
        "cumulative_output_cap": 1048576,
        "compressed_input_cap": 262144,
        "frame_cap": 16,
    }


class _RecordingBytesIO(io.BytesIO):
    """Observe actual source read calls; this is not native-consumed position."""

    def __init__(self, raw, read_size):
        super().__init__(raw)
        self.read_size = read_size
        self.calls = []

    def read(self, size=-1):
        if type(size) is not int or size != self.read_size:
            raise ValueError("native source requested an unregistered read size")
        value = super().read(size)
        self.calls.append({"requested": size, "returned_hex": value.hex()})
        return value


def _read_zstd_frames(zstd, raw, framing, progress, *, source_read_size=65536, source_reads=None):
    if type(source_read_size) is not int or source_read_size not in (1, 7, 65536):
        raise ValueError("unregistered source partition")
    if source_reads is not None and type(source_reads) is not list:
        raise ValueError("source observation sink must be a list")
    chunks = []
    total = 0
    reads = []
    positions = []
    termination_checks = []
    for frame in framing:
        frame_raw = raw[frame[1] : frame[2]]
        before = total
        chunk_start = len(chunks)
        progress["constructor_calls"] += 1
        decoder = zstd.ZstdDecompressor(max_window_size=1048576)
        stream = (
            io.BytesIO(frame_raw)
            if source_reads is None
            else _RecordingBytesIO(frame_raw, source_read_size)
        )
        with stream as source:
            with decoder.stream_reader(
                source, read_across_frames=False, read_size=source_read_size
            ) as reader:
                while True:
                    request = min(65536, 1048576 - total + 1)
                    reads.append(request)
                    output = reader.read(request)
                    if type(output) is not bytes or len(output) > request:
                        raise ValueError("native reader violated bounded exact-byte interface")
                    if not output:
                        break
                    observed = total + len(output)
                    if observed > 1048576:
                        raise OutputLimitExceeded(observed)
                    chunks.append(output)
                    total = observed
                positions.append(source.tell())
                if positions[-1] != len(frame_raw):
                    raise ValueError("reader source did not read through the complete framed slice")
        if source_reads is not None:
            source_reads.append(tuple(stream.calls))
        if total == before:
            raise ValueError("every registered frame must produce nonempty output")
        if frame[11] is not None and total - before != frame[11]:
            raise ValueError("declared frame content size disagrees with complete output")
        frame_output = b"".join(chunks[chunk_start:])
        # Reader exhaustion and source read-through are not native EOF proof.
        # Exact positive allocation avoids the unknown-FCS resize branch that
        # otherwise bypasses the pinned implementation's extra-data check.
        terminal_output = decoder.decompress(
            frame_raw,
            max_output_size=len(frame_output),
            read_across_frames=False,
            allow_extra_data=False,
        )
        if type(terminal_output) is not bytes or terminal_output != frame_output:
            raise ValueError("native terminal output differs from complete bounded reader output")
        termination_checks.append(
            {
                "frame_ordinal": frame[0],
                "max_output_size": len(frame_output),
                "read_across_frames": False,
                "allow_extra_data": False,
                "output_bytes": len(terminal_output),
                "matches_stream_output": True,
            }
        )
    if total == 0:
        raise ValueError("registered complete member requires nonempty decompressed bytes")
    return b"".join(chunks), tuple(reads), tuple(positions), tuple(termination_checks)


def inspect_native_zstd_members():
    """Observe complete bounded frame outputs in a contained child."""
    packet = _literal_packet()
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    zstd = modules["zstd"]
    positives = packet["ZSTD_CASES"] + tuple(
        case for case in packet["ZSTD_RESOURCE_CASES"] if not case["strict_profile_refusal"]
    )
    cases = []
    for case in positives:
        raw = bytes.fromhex(case["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        output, reads, positions, terminal = _read_zstd_frames(
            zstd, raw, framing, {"constructor_calls": 0}
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "framing": framing,
                "output_base64": base64.b64encode(output).decode("ascii"),
                "output_bytes": len(output),
                "read_sizes": reads,
                "frame_input_positions": positions,
                "termination_checks": terminal,
            }
        )
    negatives = (
        packet["ZSTD_STRICT_FORMAT_NEGATIVE_CASES"]
        + tuple(case for case in packet["ZSTD_RESOURCE_CASES"] if case["strict_profile_refusal"])
        + packet["ZSTD_CHECKSUM_NEGATIVE_CASES"]
    )
    refusals = []
    for case in negatives:
        raw = bytes.fromhex(case["compressed_hex"])
        progress = {"constructor_calls": 0}
        observed = None
        try:
            framing = inspect_zstd_frames(raw)
        except ValueError as error:
            phase, error_type, message = "independent_preflight", "ValueError", str(error)
        else:
            try:
                _read_zstd_frames(zstd, raw, framing, progress)
            except OutputLimitExceeded as error:
                phase, error_type, message = (
                    "native_output_limit",
                    "OutputLimitExceeded",
                    str(error),
                )
                observed = error.observed_bytes
            except zstd.ZstdError as error:
                phase, error_type, message = "native_checksum", "ZstdError", str(error)
            else:
                raise ValueError("registered negative native member unexpectedly succeeded")
        refusals.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "phase": phase,
                "constructor_calls": progress["constructor_calls"],
                "error_type": error_type,
                "error_message": message,
                "observed_output_bytes": observed,
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_zstd_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": ORACLE_SHA256,
        "identity": identity,
        "policy": _zstd_policy(),
        "cases": tuple(cases),
        "refusals": tuple(refusals),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_enum_members():
    """Qualify all source-defined Action/Side observations using pinned literals."""
    packet = _literal_packet("enum")
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    cases = []
    for case in packet["DBN_ENUM_CASES"]:
        raw = bytes.fromhex(case["dbn_hex"])
        framing = inspect_dbn_wire(raw)
        partitions = tuple(
            _decode_dbn_partition(modules["dbn"], raw, mode)
            for mode in ("complete", "chunks7", "bytewise")
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "framing": framing,
                "partitions": partitions,
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_enum_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": ENUM_ORACLE_SHA256,
        "identity": identity,
        "policy": {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
        "cases": tuple(cases),
        "strict_refusals": (),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_composed_members():
    """Qualify bounded frame decoding followed by continuous DBN traversal."""
    packet = _literal_packet("composed")
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    cases = []
    for case in packet["COMPOSED_CASES"]:
        raw = bytes.fromhex(case["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        output, reads, positions, terminal = _read_zstd_frames(
            modules["zstd"], raw, framing, {"constructor_calls": 0}
        )
        dbn_framing = inspect_dbn_wire(output)
        # Reconfirm registered associations after decompression and before DBN.
        _final_native_identity(identity, modules)
        partitions = tuple(
            _decode_dbn_partition(modules["dbn"], output, mode)
            for mode in ("complete", "chunks7", "bytewise")
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "framing": framing,
                "output_hex": output.hex(),
                "dbn_framing": dbn_framing,
                "read_sizes": reads,
                "frame_input_positions": positions,
                "termination_checks": terminal,
                "partitions": partitions,
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_composed_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": COMPOSED_ORACLE_SHA256,
        "identity": identity,
        "policy": {
            "dbn": {
                "has_metadata": True,
                "input_version": None,
                "upgrade_policy": "AS_IS",
                "compression": "NONE",
                "ts_out_constructor": False,
            },
            "zstd": _zstd_policy(),
        },
        "cases": tuple(cases),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_capacity_members():
    """Observe the complete independently registered at-cap DBN candidates."""
    packet = _literal_packet("capacity")
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    cases = []
    for case in packet["DBN_CAPACITY_CASES"]:
        raw = bytes.fromhex(case["dbn_hex"])
        framing = inspect_dbn_wire(raw)
        partitions = tuple(
            _decode_dbn_partition(modules["dbn"], raw, mode)
            for mode in ("complete", "chunks7", "bytewise")
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "framing": framing,
                "partitions": partitions,
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_capacity_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": CAPACITY_ORACLE_SHA256,
        "identity": identity,
        "policy": {
            "has_metadata": True,
            "input_version": None,
            "upgrade_policy": "AS_IS",
            "compression": "NONE",
            "ts_out_constructor": False,
        },
        "cases": tuple(cases),
        "strict_refusals": (),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_zstd_partitions():
    """Measure identical physical frames under registered source read sizes."""
    packet = _literal_packet()
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    by_id = {case["case_id"]: case for case in packet["ZSTD_CASES"]}
    cases = []
    for name in (
        "raw_ab_known_single",
        "compressed_one_literal_and_repeat_one_match",
        "compressed_two_huffman_symbols_zero_sequences",
    ):
        raw = bytes.fromhex(by_id[name]["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        partitions = []
        for read_size in (1, 7, 65536):
            trace = []
            output, reads, positions, terminal = _read_zstd_frames(
                modules["zstd"],
                raw,
                framing,
                {"constructor_calls": 0},
                source_read_size=read_size,
                source_reads=trace,
            )
            partitions.append(
                {
                    "source_read_size": read_size,
                    "output_hex": output.hex(),
                    "read_sizes": reads,
                    "frame_input_positions": positions,
                    "termination_checks": terminal,
                    "source_reads": tuple(trace),
                }
            )
        cases.append(
            {
                "case_id": name,
                "input_hex": raw.hex(),
                "framing": framing,
                "partitions": tuple(partitions),
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_zstd_partitions_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": ORACLE_SHA256,
        "identity": identity,
        "policy": {"zstd": _zstd_policy(), "source_read_sizes": (1, 7, 65536)},
        "cases": tuple(cases),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_zstd_capacity():
    """Observe fixed complete input, frame-count and cumulative-output caps."""
    packet = _literal_packet("zstd_capacity")
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    cases = []
    for case in packet["ZSTD_CAPACITY_POSITIVE_CASES"]:
        raw = bytes.fromhex(case["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        output, reads, positions, terminal = _read_zstd_frames(
            modules["zstd"], raw, framing, {"constructor_calls": 0}
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "framing": framing,
                "output_base64": base64.b64encode(output).decode("ascii"),
                "output_bytes": len(output),
                "read_sizes": reads,
                "frame_input_positions": positions,
                "termination_checks": terminal,
            }
        )
    refusals = []
    for case in packet["ZSTD_CAPACITY_REFUSAL_CASES"]:
        raw = bytes.fromhex(case["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        progress = {"constructor_calls": 0}
        try:
            _read_zstd_frames(modules["zstd"], raw, framing, progress)
        except OutputLimitExceeded as error:
            refusals.append(
                {
                    "case_id": case["case_id"],
                    "input_hex": raw.hex(),
                    "phase": "native_output_limit",
                    "constructor_calls": progress["constructor_calls"],
                    "error_type": "OutputLimitExceeded",
                    "error_message": str(error),
                    "observed_output_bytes": error.observed_bytes,
                }
            )
        else:
            raise ValueError("registered cumulative output limit unexpectedly succeeded")
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_zstd_capacity_probe_v1",
        "status": "constructed_native_observation_only",
        "oracle_sha256": ZSTD_CAPACITY_ORACLE_SHA256,
        "identity": identity,
        "policy": _zstd_policy(),
        "cases": tuple(cases),
        "refusals": tuple(refusals),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def inspect_native_boundary_controls():
    """Fixed codec-direct negatives; never positive provider admission."""
    packet = _literal_packet("negative")
    identity = inspect_loaded_native_identity()
    modules = {"dbn": sys.modules["databento_dbn"], "zstd": sys.modules["zstandard"]}
    dbn, zstd = modules["dbn"], modules["zstd"]
    dbn_cases = []
    for case in packet["DBN_NATIVE_NEGATIVE_CASES"] + packet["DBN_COMPLETE_PREFIX_IDENTITY_CASES"]:
        raw = bytes.fromhex(case["complete_input_hex"])
        try:
            inspect_dbn_wire(raw)
        except ValueError:
            physical_complete = False
        else:
            physical_complete = True
        # This registered diagnostic deliberately measures the native response
        # after independent refusal. It never feeds a positive result pathway.
        decoder = dbn.DBNDecoder(
            has_metadata=True,
            ts_out=False,
            input_version=None,
            upgrade_policy=dbn.VersionUpgradePolicy.AS_IS,
            compression=dbn.Compression.NONE,
        )
        calls, visible = [], []
        for command in case["calls"]:
            operation = command["operation"]
            chunk = bytes.fromhex(command["input_chunk_hex"])
            observations = error_class = error_message = None
            try:
                if operation == "write_then_decode":
                    decoder.write(chunk)
                elif operation != "decode" or chunk:
                    raise ValueError("unregistered direct DBN operation")
                batch = decoder.decode()
            except dbn.DBNError as error:
                error_class, error_message = "DBNError", str(error)
            else:
                if type(batch) is not list or len(batch) > 128:
                    raise ValueError("unexpected direct DBN batch")
                observations = tuple(
                    _native_metadata(value, dbn)
                    if type(value) is dbn.Metadata
                    else _native_mbo(value, dbn)
                    for value in batch
                )
                visible.extend(observations)
            remaining = decoder.buffer()
            if type(remaining) is not bytes:
                raise ValueError("unexpected direct DBN buffer representation")
            calls.append(
                {
                    "operation": operation,
                    "input_chunk_hex": chunk.hex(),
                    "returned_observations": observations,
                    "error_class": error_class,
                    "error_message": error_message,
                    "buffer_hex": remaining.hex(),
                }
            )
        held = case.get("held_whole_input_hex")
        dbn_cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "input_sha256": hashlib.sha256(raw).hexdigest(),
                "held_whole_input_sha256": None
                if held is None
                else hashlib.sha256(bytes.fromhex(held)).hexdigest(),
                "physical_complete": physical_complete,
                "calls": tuple(calls),
                "visible_observations": tuple(visible),
                "constructor_calls": 1,
                "provider_complete_result_allowed": False,
            }
        )
    empty_cases = []
    for case in packet["ZSTD_EMPTY_FRAME_CASES"]:
        raw = bytes.fromhex(case["compressed_hex"])
        framing = inspect_zstd_frames(raw)
        direct = []
        for frame in framing:
            decoder = zstd.ZstdDecompressor(max_window_size=1048576)
            chunks, size = [], 0
            with io.BytesIO(raw[frame[1] : frame[2]]) as source:
                with decoder.stream_reader(
                    source, read_across_frames=False, read_size=65536
                ) as reader:
                    while True:
                        request = min(65536, 1048576 - size + 1)
                        value = reader.read(request)
                        if type(value) is not bytes or len(value) > request:
                            raise ValueError("unexpected direct Zstd reader result")
                        if not value:
                            break
                        size += len(value)
                        if size > 1048576:
                            raise OutputLimitExceeded(size)
                        chunks.append(value)
            direct.append(b"".join(chunks).hex())
        progress = {"constructor_calls": 0}
        error_class = error_message = None
        try:
            _read_zstd_frames(zstd, raw, framing, progress)
        except ValueError as error:
            error_class, error_message = type(error).__name__, str(error)
        empty_cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "framing": framing,
                "direct_frame_output_hex": tuple(direct),
                "profile_error_class": error_class,
                "profile_error_message": error_message,
                "profile_constructor_calls": progress["constructor_calls"],
                "provider_complete_result_allowed": False,
            }
        )
    terminal_cases = []
    for case in packet["ZSTD_TERMINAL_NEGATIVE_CASES"]:
        raw = bytes.fromhex(case["compressed_hex"])
        constructor = {"dict_data": None, "max_window_size": 1048576, "format": "FORMAT_ZSTD1"}
        decoder = zstd.ZstdDecompressor(
            dict_data=None, max_window_size=1048576, format=zstd.FORMAT_ZSTD1
        )
        kwargs = {
            "max_output_size": case["decompress_kwargs"]["max_output_size"],
            "read_across_frames": False,
            "allow_extra_data": False,
        }
        output = error_class = error_message = None
        try:
            value = decoder.decompress(raw, **kwargs)
        except zstd.ZstdError as error:
            error_class, error_message = "ZstdError", str(error)
        else:
            if type(value) is not bytes:
                raise ValueError("unexpected direct terminal output type")
            output = value.hex()
        terminal_cases.append(
            {
                "case_id": case["case_id"],
                "input_hex": raw.hex(),
                "constructor_kwargs": constructor,
                "decompress_kwargs": kwargs,
                "returned_output_hex": output,
                "error_class": error_class,
                "error_message": error_message,
                "constructor_calls": 1,
                "provider_complete_result_allowed": False,
            }
        )
    artifacts, loaded = _final_native_identity(identity, modules)
    return {
        "schema": "native_boundaries_probe_v1",
        "status": "constructed_native_negative_observation_only",
        "oracle_sha256": NEGATIVE_ORACLE_SHA256,
        "identity": identity,
        "policy": {
            "dbn": {
                "has_metadata": True,
                "input_version": None,
                "upgrade_policy": "AS_IS",
                "compression": "NONE",
                "ts_out_constructor": False,
                "fresh_decoder_per_case": True,
                "continuous_state_across_case_calls": True,
            },
            "zstd": _zstd_policy(),
            "direct_controls_only": True,
            "provider_admission": False,
        },
        "dbn_cases": tuple(dbn_cases),
        "zstd_empty_cases": tuple(empty_cases),
        "zstd_terminal_cases": tuple(terminal_cases),
        "artifacts_final": artifacts,
        "loaded_final": loaded,
    }


def main():
    if len(sys.argv) != 2:
        raise ValueError("one fixed control is required")
    mode = sys.argv[1]
    if mode == "stub_success":
        print('{"control":"success"}', flush=True)
    elif mode == "stub_timeout":
        time.sleep(60)
    elif mode == "stub_memory":
        try:
            allocation = bytearray(536870912)
        except MemoryError:
            print('{"control":"allocation_refused"}', flush=True)
        else:
            print('{"control":"allocation_not_refused"}', flush=True)
            del allocation
            raise SystemExit(23)
    elif mode == "stub_crash":
        os._exit(17)
    elif mode == "stub_output":
        chunk = b"x" * 65536
        for _ in range(80):
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
    elif mode == "native_identity":
        print(
            json.dumps(
                inspect_loaded_native_identity(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_dbn":
        print(
            json.dumps(
                inspect_native_dbn_members(), sort_keys=True, separators=(",", ":"), allow_nan=False
            ),
            flush=True,
        )
    elif mode == "native_zstd":
        print(
            json.dumps(
                inspect_native_zstd_members(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_enums":
        print(
            json.dumps(
                inspect_native_enum_members(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_composed":
        print(
            json.dumps(
                inspect_native_composed_members(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_boundaries":
        print(
            json.dumps(
                inspect_native_boundary_controls(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_capacity":
        print(
            json.dumps(
                inspect_native_capacity_members(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_zstd_partitions":
        print(
            json.dumps(
                inspect_native_zstd_partitions(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    elif mode == "native_zstd_capacity":
        print(
            json.dumps(
                inspect_native_zstd_capacity(),
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            flush=True,
        )
    else:
        raise ValueError("unregistered control")


if __name__ == "__main__":
    main()
