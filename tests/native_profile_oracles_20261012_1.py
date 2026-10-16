"""Independent literal codec-proof oracles; no native or production imports.

All inputs are invented. Hex was assembled from the immutable format/layout
references below, not SDK encode(), __bytes__(), a production serializer, a
returned native observation, dataclass reflection, or market/history fixtures.
This file contains declarations only; root owns collection and all launches.
No value here is a CLOSED profile, provider acceptance, or authentication fact.

The source-candidate native Metadata envelope includes symbol_cstr_len and
enum/None observations because v0.70.0 Rust differs from its Python stub and
the held 13-field proposed contract. Qualifying observations and a separately
reviewed exact-profile revision are required before provider implementation.

Native enums have explicit kind/class_name/name/code/text tags. Unknown MBO
action/side getters return a one-character string instead, per record.rs.
Dates use an explicit python_date tag and year/month/day integers; no pretty
datetime formatter defines an oracle. The observer must project these named
getters explicitly, not produce expected bodies by reflection.
"""

DBN_COMMIT = "aa012adc6502e01b01d7b5c7836742dde21e93d8"
DBN_SOURCE_ROOT = "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/"
DBN_REFERENCES = (
    ("rust/dbn/src/lib.rs", "132-158", "v3, widths and numeric sentinels"),
    ("rust/dbn/src/compat.rs", "5-10", "v3 fixed symbol length 71"),
    ("rust/dbn/src/encode/dbn/sync.rs", "145-249", "metadata ordering and padding"),
    ("rust/dbn/src/encode/dbn/sync.rs", "252-370", "range/list/mapping/date bytes"),
    ("rust/dbn/src/decode/dbn/fsm.rs", "685-821", "header and native translations"),
    ("rust/dbn/src/decode/dbn/fsm.rs", "839-961", "lists and mapping decoding"),
    ("rust/dbn/src/decode/dbn/fsm.rs", "1179-1202", "metadata overrides controls"),
    ("rust/dbn/src/metadata.rs", "30-78", "14 logical fields/getters"),
    ("rust/dbn/src/metadata.rs", "452-467", "inclusive/exclusive mapping dates"),
    ("rust/dbn/src/python/metadata.rs", "78-87", "mapping getter last-key wins"),
    ("rust/dbn/src/python/metadata.rs", "154-194", "mapping interval date objects"),
    ("rust/dbn/src/record.rs", "37-122", "ordered repr(C) Header/MBO layout"),
    ("rust/dbn/src/record/layout_tests.rs", "67-119", "source size assertions"),
    ("rust/dbn/src/record/methods.rs", "13-37", "length multiplier and size"),
    ("rust/dbn/src/record/with_ts_out_methods.rs", "60-66", "appended timestamp"),
    ("rust/dbn/src/python/record.rs", "101-150", "rtype/record_size/ts_index"),
    ("rust/dbn/src/python/record.rs", "206-239", "flags/action/side getters"),
    ("rust/dbn/src/python/record.rs", "307-334", "absent/present ts_out"),
    ("rust/dbn/src/python/enums.rs", "21-72", "RType name/text/index"),
    ("rust/dbn/src/python/enums.rs", "126-237", "Side/Action name/text/index"),
    ("rust/dbn/src/python/enums.rs", "620-714", "SType/Schema text/index"),
    ("rust/dbn/src/python.rs", "82-89", "FlagSet becomes Python integer"),
    ("rust/dbn/src/enums.rs", "273-340", "Side and Action codes"),
    ("rust/dbn/src/enums.rs", "580-599", "SType codes"),
    ("rust/dbn/src/enums.rs", "715-718", "Schema MBO code"),
    ("rust/dbn/src/enums.rs", "1434-1448", "upgrade-policy codes/default"),
    ("python/src/dbn_decoder.rs", "20-126", "constructor and output traversal"),
)
SOURCE_EXPECTATIONS_ARE_UNEXECUTED = True

DBN_NUMERIC_SOURCE_CONSTANTS = {
    "encoding_version": 3,
    "metadata_dataset_cstr_len": 16,
    "metadata_reserved_len": 53,
    "metadata_fixed_body_len": 100,
    "metadata_minimum_complete_bytes": 128,
    "symbol_cstr_len_v3": 71,
    "record_header_bytes": 16,
    "mbo_base_bytes": 56,
    "mbo_ts_out_bytes": 64,
    "record_length_multiplier": 4,
    "mbo_rtype": 160,
    "null_schema": 65535,
    "null_stype": 255,
    "null_limit": 0,
    "undef_timestamp": 18446744073709551615,
    "undef_price": 9223372036854775807,
    "undef_order_size": 4294967295,
    "fixed_price_scale": 1000000000,
}
DBN_DECODER_SOURCE_POLICY = {
    "has_metadata": True,
    "input_version": None,
    "upgrade_policy": "AS_IS",
    "upgrade_policy_code": 1,
    "compression": "NONE",
    "ts_out_constructor": False,
    "metadata_overrides_input_version_and_ts_out": True,
    "default_upgrade_policy": "UPGRADE_TO_V3",
    "default_upgrade_policy_code": 3,
    "empty_buffer_is_complete_eof_proof": False,
}

# Half-open offsets in the complete DECOMPRESSED DBN string only.
METADATA_FIXED_SPANS = (
    ("magic", 0, 3),
    ("version", 3, 4),
    ("length_body", 4, 8),
    ("dataset", 8, 24),
    ("schema", 24, 26),
    ("start", 26, 34),
    ("end", 34, 42),
    ("limit", 42, 50),
    ("stype_in", 50, 51),
    ("stype_out", 51, 52),
    ("ts_out", 52, 53),
    ("symbol_cstr_len", 53, 55),
    ("reserved", 55, 108),
    ("schema_definition_length", 108, 112),
)
MBO_BASE_FIELD_SPANS = (
    ("length_words", 0, 1),
    ("rtype", 1, 2),
    ("publisher_id", 2, 4),
    ("instrument_id", 4, 8),
    ("ts_event", 8, 16),
    ("order_id", 16, 24),
    ("price", 24, 32),
    ("size", 32, 36),
    ("flags", 36, 37),
    ("channel_id", 37, 38),
    ("action", 38, 39),
    ("side", 39, 40),
    ("ts_recv", 40, 48),
    ("ts_in_delta", 48, 52),
    ("sequence", 52, 56),
)
MBO_PRESENT_TS_OUT_FIELD_SPANS = MBO_BASE_FIELD_SPANS + (("ts_out", 56, 64),)

SCHEMA_MBO = {
    "kind": "native_enum",
    "class_name": "Schema",
    "name": "MBO",
    "code": 0,
    "text": "mbo",
}
STYPE_PARENT = {
    "kind": "native_enum",
    "class_name": "SType",
    "name": "PARENT",
    "code": 4,
    "text": "parent",
}
STYPE_INSTRUMENT_ID = {
    "kind": "native_enum",
    "class_name": "SType",
    "name": "INSTRUMENT_ID",
    "code": 0,
    "text": "instrument_id",
}
RTYPE_MBO = {
    "kind": "native_enum",
    "class_name": "RType",
    "name": "MBO",
    "code": 160,
    "text": "mbo",
}
ACTION_ADD = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "ADD",
    "code": 65,
    "text": "A",
}
ACTION_NONE = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "NONE",
    "code": 78,
    "text": "N",
}
SIDE_BID = {
    "kind": "native_enum",
    "class_name": "Side",
    "name": "BID",
    "code": 66,
    "text": "B",
}
SIDE_NONE = {
    "kind": "native_enum",
    "class_name": "Side",
    "name": "NONE",
    "code": 78,
    "text": "N",
}

MINIMAL_METADATA_FALSE_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
MINIMAL_METADATA_TRUE_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000147000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
TARGET_MBO_FALSE_HEX = (
    "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a000000"
)
FOREIGN_MBO_FALSE_HEX = (
    "0ea00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
    "edffffff14000000"
)
TARGET_MBO_TRUE_HEX = (
    "10a001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a0000001300000000000000"
)
FOREIGN_MBO_TRUE_HEX = (
    "10a00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
    "edffffff140000001d00000000000000"
)
BOUNDARY_MBO_FALSE_HEX = (
    "0ea0ffffffffffffffffffffffffffffffffffffffffffff0000000000000080ffffffffffff5859ffffffffffffffff"
    "00000080ffffffff"
)

MINIMAL_METADATA_WIRE_FALSE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 120,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 0,
    "end": 18446744073709551615,
    "limit": 0,
    "stype_in": 4,
    "stype_out": 0,
    "ts_out": 0,
    "symbol_cstr_len": 71,
    "reserved_bytes": (0,) * 53,
    "schema_definition_length": 0,
    "symbols_count": 0,
    "symbols": (),
    "partial_count": 0,
    "partial": (),
    "not_found_count": 0,
    "not_found": (),
    "mappings_count": 0,
    "mappings": (),
    "alignment_padding_bytes": (),
}
MINIMAL_METADATA_WIRE_TRUE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 120,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 0,
    "end": 18446744073709551615,
    "limit": 0,
    "stype_in": 4,
    "stype_out": 0,
    "ts_out": 1,
    "symbol_cstr_len": 71,
    "reserved_bytes": (0,) * 53,
    "schema_definition_length": 0,
    "symbols_count": 0,
    "symbols": (),
    "partial_count": 0,
    "partial": (),
    "not_found_count": 0,
    "not_found": (),
    "mappings_count": 0,
    "mappings": (),
    "alignment_padding_bytes": (),
}
MINIMAL_METADATA_NATIVE_FALSE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 0,
    "end": None,
    "limit": None,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": False,
    "symbol_cstr_len": 71,
    "symbols": (),
    "partial": (),
    "not_found": (),
    "mappings": (),
}
MINIMAL_METADATA_NATIVE_TRUE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 0,
    "end": None,
    "limit": None,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": True,
    "symbol_cstr_len": 71,
    "symbols": (),
    "partial": (),
    "not_found": (),
    "mappings": (),
}
TARGET_WIRE_FALSE = {
    "length_words": 14,
    "rtype": 160,
    "publisher_id": 1,
    "instrument_id": 2,
    "ts_event": 3,
    "order_id": 4,
    "price": -5,
    "size": 6,
    "flags": 128,
    "channel_id": 7,
    "action": 65,
    "side": 66,
    "ts_recv": 8,
    "ts_in_delta": -9,
    "sequence": 10,
    "ts_out": None,
}
FOREIGN_WIRE_FALSE = {
    "length_words": 14,
    "rtype": 160,
    "publisher_id": 1,
    "instrument_id": 3,
    "ts_event": 13,
    "order_id": 14,
    "price": -15,
    "size": 16,
    "flags": 0,
    "channel_id": 17,
    "action": 78,
    "side": 78,
    "ts_recv": 18,
    "ts_in_delta": -19,
    "sequence": 20,
    "ts_out": None,
}
TARGET_WIRE_TRUE = {
    "length_words": 16,
    "rtype": 160,
    "publisher_id": 1,
    "instrument_id": 2,
    "ts_event": 3,
    "order_id": 4,
    "price": -5,
    "size": 6,
    "flags": 128,
    "channel_id": 7,
    "action": 65,
    "side": 66,
    "ts_recv": 8,
    "ts_in_delta": -9,
    "sequence": 10,
    "ts_out": 19,
}
FOREIGN_WIRE_TRUE = {
    "length_words": 16,
    "rtype": 160,
    "publisher_id": 1,
    "instrument_id": 3,
    "ts_event": 13,
    "order_id": 14,
    "price": -15,
    "size": 16,
    "flags": 0,
    "channel_id": 17,
    "action": 78,
    "side": 78,
    "ts_recv": 18,
    "ts_in_delta": -19,
    "sequence": 20,
    "ts_out": 29,
}
TARGET_NATIVE_FALSE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 1,
    "instrument_id": 2,
    "ts_event": 3,
    "order_id": 4,
    "price": -5,
    "size": 6,
    "flags": 128,
    "channel_id": 7,
    "action": ACTION_ADD,
    "side": SIDE_BID,
    "ts_recv": 8,
    "ts_in_delta": -9,
    "sequence": 10,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 8,
}
FOREIGN_NATIVE_FALSE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 1,
    "instrument_id": 3,
    "ts_event": 13,
    "order_id": 14,
    "price": -15,
    "size": 16,
    "flags": 0,
    "channel_id": 17,
    "action": ACTION_NONE,
    "side": SIDE_NONE,
    "ts_recv": 18,
    "ts_in_delta": -19,
    "sequence": 20,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 18,
}
TARGET_NATIVE_TRUE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 1,
    "instrument_id": 2,
    "ts_event": 3,
    "order_id": 4,
    "price": -5,
    "size": 6,
    "flags": 128,
    "channel_id": 7,
    "action": ACTION_ADD,
    "side": SIDE_BID,
    "ts_recv": 8,
    "ts_in_delta": -9,
    "sequence": 10,
    "ts_out": 19,
    "record_size": 64,
    "ts_index": 8,
}
FOREIGN_NATIVE_TRUE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 1,
    "instrument_id": 3,
    "ts_event": 13,
    "order_id": 14,
    "price": -15,
    "size": 16,
    "flags": 0,
    "channel_id": 17,
    "action": ACTION_NONE,
    "side": SIDE_NONE,
    "ts_recv": 18,
    "ts_in_delta": -19,
    "sequence": 20,
    "ts_out": 29,
    "record_size": 64,
    "ts_index": 18,
}
BOUNDARY_WIRE_FALSE = {
    "length_words": 14,
    "rtype": 160,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": -9223372036854775808,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": 88,
    "side": 89,
    "ts_recv": 18446744073709551615,
    "ts_in_delta": -2147483648,
    "sequence": 4294967295,
    "ts_out": None,
}
BOUNDARY_NATIVE_FALSE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": -9223372036854775808,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": {"kind": "str", "value": "X"},
    "side": {"kind": "str", "value": "Y"},
    "ts_recv": 18446744073709551615,
    "ts_in_delta": -2147483648,
    "sequence": 4294967295,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 18446744073709551615,
}

# Rich headers use the v3 standard 71-byte C strings, duplicate list values,
# unsorted wire group order ZZ then AA, and repeated equal ZZ intervals.
# Body = 120 + 5*71 + 2*(71+4) + 3*(8+71) = 862, padded to 864.
RICH_METADATA_FALSE_HEX = (
    "44424e0360030000494e56454e5445440000000000000000000001000000000000000200000000000000030000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000200000041410000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000004141000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000010000004242000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000"
    "004343000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000434300000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002"
    "0000005a5a00000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000002000000942835019528350132000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000009428350195283501320000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000041410000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000100000094283501962835013300000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000"
)
RICH_METADATA_TRUE_HEX = (
    "44424e0360030000494e56454e5445440000000000000000000001000000000000000200000000000000030000000000"
    "000004000147000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000200000041410000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000004141000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000010000004242000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000020000"
    "004343000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000434300000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002"
    "0000005a5a00000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000002000000942835019528350132000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000009428350195283501320000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000041410000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000100000094283501962835013300000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000"
)
RICH_WIRE_MAPPINGS = (
    {
        "raw_symbol": "ZZ",
        "interval_count": 2,
        "intervals": (
            {"start_date": 20261012, "end_date": 20261013, "symbol": "2"},
            {"start_date": 20261012, "end_date": 20261013, "symbol": "2"},
        ),
    },
    {
        "raw_symbol": "AA",
        "interval_count": 1,
        "intervals": ({"start_date": 20261012, "end_date": 20261014, "symbol": "3"},),
    },
)
RICH_NATIVE_MAPPINGS = (
    {
        "raw_symbol": "AA",
        "intervals": (
            {
                "start_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 12},
                "end_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 14},
                "symbol": "3",
            },
        ),
    },
    {
        "raw_symbol": "ZZ",
        "intervals": (
            {
                "start_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 12},
                "end_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 13},
                "symbol": "2",
            },
            {
                "start_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 12},
                "end_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 13},
                "symbol": "2",
            },
        ),
    },
)
RICH_METADATA_WIRE_FALSE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 864,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": 4,
    "stype_out": 0,
    "ts_out": 0,
    "symbol_cstr_len": 71,
    "reserved_bytes": (0,) * 53,
    "schema_definition_length": 0,
    "symbols_count": 2,
    "symbols": ("AA", "AA"),
    "partial_count": 1,
    "partial": ("BB",),
    "not_found_count": 2,
    "not_found": ("CC", "CC"),
    "mappings_count": 2,
    "mappings": RICH_WIRE_MAPPINGS,
    "alignment_padding_bytes": (0, 0),
}
RICH_METADATA_WIRE_TRUE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 864,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": 4,
    "stype_out": 0,
    "ts_out": 1,
    "symbol_cstr_len": 71,
    "reserved_bytes": (0,) * 53,
    "schema_definition_length": 0,
    "symbols_count": 2,
    "symbols": ("AA", "AA"),
    "partial_count": 1,
    "partial": ("BB",),
    "not_found_count": 2,
    "not_found": ("CC", "CC"),
    "mappings_count": 2,
    "mappings": RICH_WIRE_MAPPINGS,
    "alignment_padding_bytes": (0, 0),
}
RICH_METADATA_NATIVE_FALSE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": False,
    "symbol_cstr_len": 71,
    "symbols": ("AA", "AA"),
    "partial": ("BB",),
    "not_found": ("CC", "CC"),
    "mappings": RICH_NATIVE_MAPPINGS,
}
RICH_METADATA_NATIVE_TRUE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": True,
    "symbol_cstr_len": 71,
    "symbols": ("AA", "AA"),
    "partial": ("BB",),
    "not_found": ("CC", "CC"),
    "mappings": RICH_NATIVE_MAPPINGS,
}
RICH_VARIABLE_SPANS = (
    ("symbols_count", 112, 116),
    ("symbols[0]", 116, 187),
    ("symbols[1]", 187, 258),
    ("partial_count", 258, 262),
    ("partial[0]", 262, 333),
    ("not_found_count", 333, 337),
    ("not_found[0]", 337, 408),
    ("not_found[1]", 408, 479),
    ("mappings_count", 479, 483),
    ("mappings[0].raw_symbol", 483, 554),
    ("mappings[0].interval_count", 554, 558),
    ("mappings[0].intervals[0].start_date", 558, 562),
    ("mappings[0].intervals[0].end_date", 562, 566),
    ("mappings[0].intervals[0].symbol", 566, 637),
    ("mappings[0].intervals[1].start_date", 637, 641),
    ("mappings[0].intervals[1].end_date", 641, 645),
    ("mappings[0].intervals[1].symbol", 645, 716),
    ("mappings[1].raw_symbol", 716, 787),
    ("mappings[1].interval_count", 787, 791),
    ("mappings[1].intervals[0].start_date", 791, 795),
    ("mappings[1].intervals[0].end_date", 795, 799),
    ("mappings[1].intervals[0].symbol", 799, 870),
    ("alignment_padding", 870, 872),
)

# Duplicate original wire keys are a strict profile-refusal candidate.
# The SDK getter's source shows last-group wins; that is NOT wire completeness.
DUPLICATE_GROUP_METADATA_HEX = (
    "44424e03b0010000494e56454e5445440000000000000000000001000000000000000200000000000000030000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000200000041410000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000100000094283501952835013200000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000414100000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000001000000942835019628350133000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000"
)
DUPLICATE_GROUP_WIRE_MAPPINGS = (
    {
        "raw_symbol": "AA",
        "interval_count": 1,
        "intervals": ({"start_date": 20261012, "end_date": 20261013, "symbol": "2"},),
    },
    {
        "raw_symbol": "AA",
        "interval_count": 1,
        "intervals": ({"start_date": 20261012, "end_date": 20261014, "symbol": "3"},),
    },
)
DUPLICATE_GROUP_METADATA_WIRE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 432,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": 4,
    "stype_out": 0,
    "ts_out": 0,
    "symbol_cstr_len": 71,
    "reserved_bytes": (0,) * 53,
    "schema_definition_length": 0,
    "symbols_count": 0,
    "symbols": (),
    "partial_count": 0,
    "partial": (),
    "not_found_count": 0,
    "not_found": (),
    "mappings_count": 2,
    "mappings": DUPLICATE_GROUP_WIRE_MAPPINGS,
    "alignment_padding_bytes": (0, 0, 0, 0),
}
DUPLICATE_GROUP_METADATA_NATIVE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 1,
    "end": 2,
    "limit": 3,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": False,
    "symbol_cstr_len": 71,
    "symbols": (),
    "partial": (),
    "not_found": (),
    "mappings": (
        {
            "raw_symbol": "AA",
            "intervals": (
                {
                    "start_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 12},
                    "end_date": {"kind": "python_date", "year": 2026, "month": 10, "day": 14},
                    "symbol": "3",
                },
            ),
        },
    ),
}

# Inclusive wire-domain minimum/maximum corpus. These exercise getter
# representation, not book/action admission or transport representability.
MINIMUM_MBO_FALSE_HEX = (
    "0ea0000000000000000000000000000000000000000000000000000000000080"
    "000000000000000000000000000000000000008000000000"
)
MAXIMUM_MBO_FALSE_HEX = (
    "0ea0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"
    "ffffffffffffffffffffffffffffffffffffff7fffffffff"
)
MINIMUM_MBO_TRUE_HEX = (
    "10a0000000000000000000000000000000000000000000000000000000000080"
    "0000000000000000000000000000000000000080000000000000000000000000"
)
MAXIMUM_MBO_TRUE_HEX = (
    "10a0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f"
    "ffffffffffffffffffffffffffffffffffffff7fffffffffffffffffffffffff"
)
MINIMUM_WIRE_FALSE = {
    "length_words": 14,
    "rtype": 160,
    "publisher_id": 0,
    "instrument_id": 0,
    "ts_event": 0,
    "order_id": 0,
    "price": -9223372036854775808,
    "size": 0,
    "flags": 0,
    "channel_id": 0,
    "action": 0,
    "side": 0,
    "ts_recv": 0,
    "ts_in_delta": -2147483648,
    "sequence": 0,
    "ts_out": None,
}
MAXIMUM_WIRE_FALSE = {
    "length_words": 14,
    "rtype": 160,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": 9223372036854775807,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": 255,
    "side": 255,
    "ts_recv": 18446744073709551615,
    "ts_in_delta": 2147483647,
    "sequence": 4294967295,
    "ts_out": None,
}
MINIMUM_WIRE_TRUE = {
    "length_words": 16,
    "rtype": 160,
    "publisher_id": 0,
    "instrument_id": 0,
    "ts_event": 0,
    "order_id": 0,
    "price": -9223372036854775808,
    "size": 0,
    "flags": 0,
    "channel_id": 0,
    "action": 0,
    "side": 0,
    "ts_recv": 0,
    "ts_in_delta": -2147483648,
    "sequence": 0,
    "ts_out": 0,
}
MAXIMUM_WIRE_TRUE = {
    "length_words": 16,
    "rtype": 160,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": 9223372036854775807,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": 255,
    "side": 255,
    "ts_recv": 18446744073709551615,
    "ts_in_delta": 2147483647,
    "sequence": 4294967295,
    "ts_out": 18446744073709551615,
}
MINIMUM_NATIVE_FALSE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 0,
    "instrument_id": 0,
    "ts_event": 0,
    "order_id": 0,
    "price": -9223372036854775808,
    "size": 0,
    "flags": 0,
    "channel_id": 0,
    "action": {"kind": "str", "value": "\u0000"},
    "side": {"kind": "str", "value": "\u0000"},
    "ts_recv": 0,
    "ts_in_delta": -2147483648,
    "sequence": 0,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 0,
}
MAXIMUM_NATIVE_FALSE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": 9223372036854775807,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": {"kind": "str", "value": "\u00ff"},
    "side": {"kind": "str", "value": "\u00ff"},
    "ts_recv": 18446744073709551615,
    "ts_in_delta": 2147483647,
    "sequence": 4294967295,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 18446744073709551615,
}
MINIMUM_NATIVE_TRUE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 0,
    "instrument_id": 0,
    "ts_event": 0,
    "order_id": 0,
    "price": -9223372036854775808,
    "size": 0,
    "flags": 0,
    "channel_id": 0,
    "action": {"kind": "str", "value": "\u0000"},
    "side": {"kind": "str", "value": "\u0000"},
    "ts_recv": 0,
    "ts_in_delta": -2147483648,
    "sequence": 0,
    "ts_out": 0,
    "record_size": 64,
    "ts_index": 0,
}
MAXIMUM_NATIVE_TRUE = {
    "kind": "MBO",
    "rtype": RTYPE_MBO,
    "publisher_id": 65535,
    "instrument_id": 4294967295,
    "ts_event": 18446744073709551615,
    "order_id": 18446744073709551615,
    "price": 9223372036854775807,
    "size": 4294967295,
    "flags": 255,
    "channel_id": 255,
    "action": {"kind": "str", "value": "\u00ff"},
    "side": {"kind": "str", "value": "\u00ff"},
    "ts_recv": 18446744073709551615,
    "ts_in_delta": 2147483647,
    "sequence": 4294967295,
    "ts_out": 18446744073709551615,
    "record_size": 64,
    "ts_index": 18446744073709551615,
}
MINIMAL_VARIABLE_SPANS = (
    ("symbols_count", 112, 116),
    ("partial_count", 116, 120),
    ("not_found_count", 120, 124),
    ("mappings_count", 124, 128),
)
DUPLICATE_GROUP_VARIABLE_SPANS = (
    ("symbols_count", 112, 116),
    ("partial_count", 116, 120),
    ("not_found_count", 120, 124),
    ("mappings_count", 124, 128),
    ("mappings[0].raw_symbol", 128, 199),
    ("mappings[0].interval_count", 199, 203),
    ("mappings[0].intervals[0].start_date", 203, 207),
    ("mappings[0].intervals[0].end_date", 207, 211),
    ("mappings[0].intervals[0].symbol", 211, 282),
    ("mappings[1].raw_symbol", 282, 353),
    ("mappings[1].interval_count", 353, 357),
    ("mappings[1].intervals[0].start_date", 357, 361),
    ("mappings[1].intervals[0].end_date", 361, 365),
    ("mappings[1].intervals[0].symbol", 365, 436),
    ("alignment_padding", 436, 440),
)


DBN_CASES = (
    {
        "case_id": "wire_minimum_absent_ts_out",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX + MINIMUM_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_FALSE, MINIMUM_WIRE_FALSE),
        "native_observations": (MINIMAL_METADATA_NATIVE_FALSE, MINIMUM_NATIVE_FALSE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "wire_maximum_absent_ts_out",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX + MAXIMUM_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_FALSE, MAXIMUM_WIRE_FALSE),
        "native_observations": (MINIMAL_METADATA_NATIVE_FALSE, MAXIMUM_NATIVE_FALSE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "wire_minimum_present_ts_out",
        "dbn_hex": MINIMAL_METADATA_TRUE_HEX + MINIMUM_MBO_TRUE_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_TRUE, MINIMUM_WIRE_TRUE),
        "native_observations": (MINIMAL_METADATA_NATIVE_TRUE, MINIMUM_NATIVE_TRUE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "wire_maximum_present_ts_out",
        "dbn_hex": MINIMAL_METADATA_TRUE_HEX + MAXIMUM_MBO_TRUE_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_TRUE, MAXIMUM_WIRE_TRUE),
        "native_observations": (MINIMAL_METADATA_NATIVE_TRUE, MAXIMUM_NATIVE_TRUE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "minimal_absent_ts_out",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX + TARGET_MBO_FALSE_HEX + FOREIGN_MBO_FALSE_HEX,
        "complete_bytes": 240,
        "metadata_count": 1,
        "mbo_count": 2,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184), ("MBO", 184, 240)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_FALSE, TARGET_WIRE_FALSE, FOREIGN_WIRE_FALSE),
        "native_observations": (
            MINIMAL_METADATA_NATIVE_FALSE,
            TARGET_NATIVE_FALSE,
            FOREIGN_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "minimal_present_ts_out",
        "dbn_hex": MINIMAL_METADATA_TRUE_HEX + TARGET_MBO_TRUE_HEX + FOREIGN_MBO_TRUE_HEX,
        "complete_bytes": 256,
        "metadata_count": 1,
        "mbo_count": 2,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192), ("MBO", 192, 256)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_TRUE, TARGET_WIRE_TRUE, FOREIGN_WIRE_TRUE),
        "native_observations": (
            MINIMAL_METADATA_NATIVE_TRUE,
            TARGET_NATIVE_TRUE,
            FOREIGN_NATIVE_TRUE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "rich_absent_ts_out",
        "dbn_hex": RICH_METADATA_FALSE_HEX + TARGET_MBO_FALSE_HEX + FOREIGN_MBO_FALSE_HEX,
        "complete_bytes": 984,
        "metadata_count": 1,
        "mbo_count": 2,
        "wire_spans": (("Metadata", 0, 872), ("MBO", 872, 928), ("MBO", 928, 984)),
        "wire_bodies": (RICH_METADATA_WIRE_FALSE, TARGET_WIRE_FALSE, FOREIGN_WIRE_FALSE),
        "native_observations": (
            RICH_METADATA_NATIVE_FALSE,
            TARGET_NATIVE_FALSE,
            FOREIGN_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "rich_present_ts_out",
        "dbn_hex": RICH_METADATA_TRUE_HEX + TARGET_MBO_TRUE_HEX + FOREIGN_MBO_TRUE_HEX,
        "complete_bytes": 1000,
        "metadata_count": 1,
        "mbo_count": 2,
        "wire_spans": (("Metadata", 0, 872), ("MBO", 872, 936), ("MBO", 936, 1000)),
        "wire_bodies": (RICH_METADATA_WIRE_TRUE, TARGET_WIRE_TRUE, FOREIGN_WIRE_TRUE),
        "native_observations": (RICH_METADATA_NATIVE_TRUE, TARGET_NATIVE_TRUE, FOREIGN_NATIVE_TRUE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "raw_integer_extremes_and_unknown_chars",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX + BOUNDARY_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (MINIMAL_METADATA_WIRE_FALSE, BOUNDARY_WIRE_FALSE),
        "native_observations": (MINIMAL_METADATA_NATIVE_FALSE, BOUNDARY_NATIVE_FALSE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "duplicate_wire_mapping_groups",
        "dbn_hex": DUPLICATE_GROUP_METADATA_HEX + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 496,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 440), ("MBO", 440, 496)),
        "wire_bodies": (DUPLICATE_GROUP_METADATA_WIRE, TARGET_WIRE_FALSE),
        "native_observations": (DUPLICATE_GROUP_METADATA_NATIVE, TARGET_NATIVE_FALSE),
        "strict_profile_refusal": True,
    },
)

# Refusal is an INDEPENDENT FRAMER requirement, not guessed SDK behavior.
# Slicing literal hex constructs complete named candidate inputs only.
DBN_FRAMING_NEGATIVE_CASES = (
    ("metadata_last_byte_missing", MINIMAL_METADATA_FALSE_HEX[:-2]),
    ("final_mbo_last_byte_missing", MINIMAL_METADATA_FALSE_HEX + TARGET_MBO_FALSE_HEX[:-2]),
    ("unexplained_final_byte", MINIMAL_METADATA_FALSE_HEX + TARGET_MBO_FALSE_HEX + "00"),
    ("mbo_length_13_words", MINIMAL_METADATA_FALSE_HEX + "0d" + TARGET_MBO_FALSE_HEX[2:]),
    ("mbo_length_15_words", MINIMAL_METADATA_FALSE_HEX + "0f" + TARGET_MBO_FALSE_HEX[2:]),
    ("present_ts_out_extension_missing", MINIMAL_METADATA_TRUE_HEX + TARGET_MBO_FALSE_HEX),
    ("duplicate_metadata_header", MINIMAL_METADATA_FALSE_HEX + MINIMAL_METADATA_FALSE_HEX),
)

ZSTD_SPEC_COMMIT = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
ZSTD_SPEC_URL = (
    "https://github.com/facebook/zstd/blob/"
    "f8745da6ff1ad1e7bab384bd1f9d742439278e99/"
    "doc/zstd_compression_format.md"
)
ZSTD_SPEC_VERSION = "0.4.3, 2024-10-07"
ZSTD_SEQUENCE_RLE_SOURCE_URL = (
    "https://github.com/facebook/zstd/blob/"
    "f8745da6ff1ad1e7bab384bd1f9d742439278e99/"
    "lib/decompress/zstd_decompress_block.c"
)
ZSTD_SEQUENCE_RLE_SOURCE_ANCHORS = (
    ("463-476", "RLE tableLog/nbBits zero and literal base values"),
    ("657-666", "RLE code tables consume one symbol byte"),
    ("1192-1200", "zero-log tables consume zero initial-state bits"),
    ("1299-1304", "nonzero literal length/code0 resolves repeat offset1"),
)
# Match candidate: raw literal 08/41; one sequence 01; modes 54;
# LL/OF/ML symbols 01/00/00; RLE tables have zero state/extra bits;
# terminal bit 01. Copy one A, then three bytes at repeat offset1.
# Huffman candidate: 22c000 encodes type2/single-stream, regen2/comp3;
# 80/10 directly represents first weight1, final implied weight1;
# codes 0/1, stream05 has terminator bit2 then decoded bits0/1.
# Both are source-derived candidates, not native execution evidence.
PYTHON_ZSTD_COMMIT = "7a77a7510b8ce068e4a103d29aea1b5ec829d8b6"
PYTHON_ZSTD_SOURCE_ROOT = (
    "https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/"
)
ZSTD_REFERENCE_ANCHORS = (
    ("95-398", "frame/header/block-size rules"),
    ("431-563", "raw/RLE literal encoding"),
    ("613-661", "zero-sequence compressed block"),
    ("643-857", "RLE sequence modes/codes/bitstream"),
    ("898-982", "sequence execution and initial repeat offsets"),
    ("985-1023", "skippable frames"),
    ("1233-1471", "Huffman weights/direct tree/codes/reverse bitstream"),
)
# Packet independently authored by native_contract_scope_review, based on the
# immutable specification. No zstd encoder or native call produced these bytes.
# Block spans are compressed-string coordinates; outputs are literal hex.
ZSTD_CASES = (
    {
        "case_id": "raw_ab_known_single_checksum",
        "compressed_hex": "28b52ffd24021100004142e5b8cc3f",
        "decompressed_hex": "4142",
        "compressed_bytes": 15,
        "decompressed_bytes": 2,
        "content_size": 2,
        "window_bytes": 2,
        "dictionary_id": None,
        "checksum": True,
        "checksum_value": 1070381285,
        "checksum_span": (11, 15),
        "frame_spans": ((0, 15, 0, 2),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 11),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "compressed_one_literal_and_repeat_one_match",
        "compressed_hex": "28b52ffd00004500000841015401000001",
        "decompressed_hex": "41414141",
        "compressed_bytes": 17,
        "decompressed_bytes": 4,
        "content_size": None,
        "window_bytes": 1024,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 17, 0, 4),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 17),),
        "strict_profile_refusal": False,
        "literal_section": {"kind": "raw", "regenerated_size": 1, "literal_hex": "41"},
        "sequences": (
            {
                "literal_length_code": 1,
                "offset_code": 0,
                "match_length_code": 0,
                "literal_length": 1,
                "offset_value": 1,
                "match_length": 3,
                "resolved_offset": 1,
            },
        ),
        "sequence_modes": (1, 1, 1),
        "initial_repeat_offsets": (1, 4, 8),
        "sequence_bitstream_hex": "01",
        "useful_sequence_bits": 0,
    },
    {
        "case_id": "compressed_two_huffman_symbols_zero_sequences",
        "compressed_hex": "28b52ffd00003d000022c00080100500",
        "decompressed_hex": "0001",
        "compressed_bytes": 16,
        "decompressed_bytes": 2,
        "content_size": None,
        "window_bytes": 1024,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 16, 0, 2),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 16),),
        "strict_profile_refusal": False,
        "literal_section": {
            "kind": "huffman",
            "regenerated_size": 2,
            "compressed_size": 3,
            "tree_hex": "8010",
            "weights": ((0, 1), (1, 1)),
            "codes": ((0, 0, 1), (1, 1, 1)),
            "stream_hex": "05",
        },
        "sequences": (),
        "number_of_sequences": 0,
    },
    {
        "case_id": "raw_ab_known_single",
        "compressed_hex": "28b52ffd20021100004142",
        "decompressed_hex": "4142",
        "compressed_bytes": 11,
        "decompressed_bytes": 2,
        "content_size": 2,
        "window_bytes": 2,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 11, 0, 2),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 11),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "raw_ab_unknown",
        "compressed_hex": "28b52ffd00001100004142",
        "decompressed_hex": "4142",
        "compressed_bytes": 11,
        "decompressed_bytes": 2,
        "content_size": None,
        "window_bytes": 1024,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 11, 0, 2),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 11),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "rle_four_a_known_single",
        "compressed_hex": "28b52ffd200423000041",
        "decompressed_hex": "41414141",
        "compressed_bytes": 10,
        "decompressed_bytes": 4,
        "content_size": 4,
        "window_bytes": 4,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 10, 0, 4),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 10),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "compressed_raw_literals_abc_unknown",
        "compressed_hex": "28b52ffd00002d00001841424300",
        "decompressed_hex": "414243",
        "compressed_bytes": 14,
        "decompressed_bytes": 3,
        "content_size": None,
        "window_bytes": 1024,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 14, 0, 3),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 14),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "compressed_raw_literals_abc_known_non_single",
        "compressed_hex": "28b52ffd8000030000002d00001841424300",
        "decompressed_hex": "414243",
        "compressed_bytes": 18,
        "decompressed_bytes": 3,
        "content_size": 3,
        "window_bytes": 1024,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 18, 0, 3),),
        "header_spans": ((0, 10),),
        "block_header_spans": ((10, 13),),
        "block_payload_spans": ((13, 18),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "compressed_rle_literals_eight_a",
        "compressed_hex": "28b52ffd20081d0000414100",
        "decompressed_hex": "4141414141414141",
        "compressed_bytes": 12,
        "decompressed_bytes": 8,
        "content_size": 8,
        "window_bytes": 8,
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 12, 0, 8),),
        "header_spans": ((0, 6),),
        "block_header_spans": ((6, 9),),
        "block_payload_spans": ((9, 12),),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "concatenated_raw_ab_and_rle_four_a",
        "compressed_hex": "28b52ffd2002110000414228b52ffd200423000041",
        "decompressed_hex": "414241414141",
        "compressed_bytes": 21,
        "decompressed_bytes": 6,
        "content_sizes": (2, 4),
        "window_bytes": (2, 4),
        "dictionary_id": None,
        "checksum": False,
        "frame_spans": ((0, 11, 0, 2), (11, 21, 2, 6)),
        "header_spans": ((0, 6), (11, 17)),
        "block_header_spans": ((6, 9), (17, 20)),
        "block_payload_spans": ((9, 11), (20, 21)),
        "strict_profile_refusal": False,
    },
)
ZSTD_STRICT_FORMAT_NEGATIVE_CASES = (
    {
        "case_id": "compressed_block_size_exceeds_single_window",
        "compressed_hex": "28b52ffd20032d00001841424300",
        "claimed_content_size": 3,
        "claimed_window_bytes": 3,
        "compressed_block_size": 5,
        "reason": "Block_Size exceeds Window_Size",
        "native_rejection_is_not_assumed": True,
    },
    {
        "case_id": "truncated_final_frame",
        "compressed_hex": "28b52ffd200211000041",
        "reason": "last raw block requires two payload bytes, only one present",
        "native_rejection_is_not_assumed": True,
    },
    {
        "case_id": "unexplained_trailing_byte",
        "compressed_hex": "28b52ffd2002110000414200",
        "reason": "one complete frame followed by unexplained byte",
        "native_rejection_is_not_assumed": True,
    },
    {
        "case_id": "skippable_frame",
        "compressed_hex": "502a4d180100000041",
        "reason": "narrow profile forbids skippable frame, even if native accepts",
        "native_rejection_is_not_assumed": True,
    },
)

# Complete v0.70.0 SType domain, independently read from enums.rs580-632,
# enums.rs670-688 and python/enums.rs635-653. Byte50 is stype_in, byte51
# is stype_out. stype_in255 means None; no stype_out255 variant exists.
# SMART is still source-exposed despite deprecation; no PARENT-only narrowing.
# Explicit literal overrides below expand the complete independent minimal
# bodies, not a production serializer or returned SDK values.
DBN_STYPE_REFERENCES = (
    ("rust/dbn/src/enums.rs", "580-632", "complete u8 enum domain"),
    ("rust/dbn/src/enums.rs", "670-688", "complete as_str mapping"),
    ("rust/dbn/src/python/enums.rs", "635-653", "native uppercase name getter"),
    ("rust/dbn/src/decode/dbn/fsm.rs", "760-772", "input-null/output-enum checks"),
)
DBN_STYPE_DOMAIN_FIELDS = ("code", "name", "text", "wire_byte_hex")
DBN_STYPE_DOMAIN = (
    (0, "INSTRUMENT_ID", "instrument_id", "00"),
    (1, "RAW_SYMBOL", "raw_symbol", "01"),
    (2, "SMART", "smart", "02"),
    (3, "CONTINUOUS", "continuous", "03"),
    (4, "PARENT", "parent", "04"),
    (5, "NASDAQ_SYMBOL", "nasdaq_symbol", "05"),
    (6, "CMS_SYMBOL", "cms_symbol", "06"),
    (7, "ISIN", "isin", "07"),
    (8, "US_CODE", "us_code", "08"),
    (9, "BBG_COMP_ID", "bbg_comp_id", "09"),
    (10, "BBG_COMP_TICKER", "bbg_comp_ticker", "0a"),
    (11, "FIGI", "figi", "0b"),
    (12, "FIGI_TICKER", "figi_ticker", "0c"),
    (13, "LISTING_ID", "listing_id", "0d"),
    (14, "ISSUER_ID", "issuer_id", "0e"),
    (15, "SECURITY_ID", "security_id", "0f"),
)
DBN_STYPE_CASES = (
    {
        "case_id": "stype_in_00_instrument_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "00"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 0},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "INSTRUMENT_ID",
                    "code": 0,
                    "text": "instrument_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_01_raw_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "01"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 1},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "RAW_SYMBOL",
                    "code": 1,
                    "text": "raw_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_02_smart",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "02"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 2},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "SMART",
                    "code": 2,
                    "text": "smart",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_03_continuous",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "03"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 3},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "CONTINUOUS",
                    "code": 3,
                    "text": "continuous",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_04_parent",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "04"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 4},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "PARENT",
                    "code": 4,
                    "text": "parent",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_05_nasdaq_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "05"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 5},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "NASDAQ_SYMBOL",
                    "code": 5,
                    "text": "nasdaq_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_06_cms_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "06"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 6},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "CMS_SYMBOL",
                    "code": 6,
                    "text": "cms_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_07_isin",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "07"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 7},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "ISIN",
                    "code": 7,
                    "text": "isin",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_08_us_code",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "08"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 8},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "US_CODE",
                    "code": 8,
                    "text": "us_code",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_09_bbg_comp_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "09"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 9},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "BBG_COMP_ID",
                    "code": 9,
                    "text": "bbg_comp_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_10_bbg_comp_ticker",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0a"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 10},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "BBG_COMP_TICKER",
                    "code": 10,
                    "text": "bbg_comp_ticker",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_11_figi",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0b"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 11},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "FIGI",
                    "code": 11,
                    "text": "figi",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_12_figi_ticker",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0c"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 12},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "FIGI_TICKER",
                    "code": 12,
                    "text": "figi_ticker",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_13_listing_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0d"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 13},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "LISTING_ID",
                    "code": 13,
                    "text": "listing_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_14_issuer_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0e"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 14},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "ISSUER_ID",
                    "code": 14,
                    "text": "issuer_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_15_security_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "0f"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 15},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_in": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "SECURITY_ID",
                    "code": 15,
                    "text": "security_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_00_instrument_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "00"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 0},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "INSTRUMENT_ID",
                    "code": 0,
                    "text": "instrument_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_01_raw_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "01"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 1},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "RAW_SYMBOL",
                    "code": 1,
                    "text": "raw_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_02_smart",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "02"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 2},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "SMART",
                    "code": 2,
                    "text": "smart",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_03_continuous",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "03"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 3},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "CONTINUOUS",
                    "code": 3,
                    "text": "continuous",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_04_parent",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "04"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 4},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "PARENT",
                    "code": 4,
                    "text": "parent",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_05_nasdaq_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "05"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 5},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "NASDAQ_SYMBOL",
                    "code": 5,
                    "text": "nasdaq_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_06_cms_symbol",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "06"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 6},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "CMS_SYMBOL",
                    "code": 6,
                    "text": "cms_symbol",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_07_isin",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "07"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 7},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "ISIN",
                    "code": 7,
                    "text": "isin",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_08_us_code",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "08"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 8},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "US_CODE",
                    "code": 8,
                    "text": "us_code",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_09_bbg_comp_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "09"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 9},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "BBG_COMP_ID",
                    "code": 9,
                    "text": "bbg_comp_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_10_bbg_comp_ticker",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0a"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 10},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "BBG_COMP_TICKER",
                    "code": 10,
                    "text": "bbg_comp_ticker",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_11_figi",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0b"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 11},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "FIGI",
                    "code": 11,
                    "text": "figi",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_12_figi_ticker",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0c"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 12},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "FIGI_TICKER",
                    "code": 12,
                    "text": "figi_ticker",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_13_listing_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0d"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 13},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "LISTING_ID",
                    "code": 13,
                    "text": "listing_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_14_issuer_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0e"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 14},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "ISSUER_ID",
                    "code": 14,
                    "text": "issuer_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_out_15_security_id",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:102]
        + "0f"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_out": 15},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {
                **MINIMAL_METADATA_NATIVE_FALSE,
                "stype_out": {
                    "kind": "native_enum",
                    "class_name": "SType",
                    "name": "SECURITY_ID",
                    "code": 15,
                    "text": "security_id",
                },
            },
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "stype_in_255_none",
        "dbn_hex": MINIMAL_METADATA_FALSE_HEX[:100]
        + "ff"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (
            {**MINIMAL_METADATA_WIRE_FALSE, "stype_in": 255},
            TARGET_WIRE_FALSE,
        ),
        "native_observations": (
            {**MINIMAL_METADATA_NATIVE_FALSE, "stype_in": None},
            TARGET_NATIVE_FALSE,
        ),
        "strict_profile_refusal": False,
    },
)
DBN_STYPE_NEGATIVE_CASES = (
    (
        "stype_in_unknown_16",
        MINIMAL_METADATA_FALSE_HEX[:100]
        + "10"
        + MINIMAL_METADATA_FALSE_HEX[102:]
        + TARGET_MBO_FALSE_HEX,
    ),
    (
        "stype_out_unknown_16",
        MINIMAL_METADATA_FALSE_HEX[:102]
        + "10"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
    ),
    (
        "stype_out_null_255",
        MINIMAL_METADATA_FALSE_HEX[:102]
        + "ff"
        + MINIMAL_METADATA_FALSE_HEX[104:]
        + TARGET_MBO_FALSE_HEX,
    ),
)

# RLE block header 0x100002: nonlast RLE 131072 bytes; last sets bit0.
# Each hex is a COMPLETE compressed string with literal repeat blocks; output
# is the independent byte 0x41 repeated the stated exact count, not SDK output.
ZSTD_RESOURCE_CASES = (
    {
        "case_id": "known_exact_one_mib",
        "compressed_hex": "28b52ffda000001000"
        "0200104102001041020010410200104102001041020010410200104103001041",
        "compressed_bytes": 41,
        "output_byte": 65,
        "output_repetitions": 1048576,
        "content_size": 1048576,
        "window_bytes": 1048576,
        "frame_spans": ((0, 41, 0, 1048576),),
        "header_span": (0, 9),
        "block_count": 8,
        "strict_profile_refusal": False,
    },
    {
        "case_id": "unknown_exact_one_mib",
        "compressed_hex": "28b52ffd0050"
        "0200104102001041020010410200104102001041020010410200104103001041",
        "compressed_bytes": 38,
        "output_byte": 65,
        "output_repetitions": 1048576,
        "content_size": None,
        "window_bytes": 1048576,
        "frame_spans": ((0, 38, 0, 1048576),),
        "header_span": (0, 6),
        "block_count": 8,
        "strict_profile_refusal": False,
    },
    {
        "case_id": "known_one_mib_plus_one",
        "compressed_hex": "28b52ffda001001000"
        "02001041020010410200104102001041020010410200104102001041020010410b000041",
        "compressed_bytes": 45,
        "output_byte": 65,
        "output_repetitions": 1048577,
        "content_size": 1048577,
        "window_bytes": 1048577,
        "frame_spans": ((0, 45, 0, 1048577),),
        "header_span": (0, 9),
        "block_count": 9,
        "strict_profile_refusal": True,
        "reason": "complete decompressed cap exceeded",
    },
    {
        "case_id": "unknown_one_mib_plus_one",
        "compressed_hex": "28b52ffd0050"
        "02001041020010410200104102001041020010410200104102001041020010410b000041",
        "compressed_bytes": 42,
        "output_byte": 65,
        "output_repetitions": 1048577,
        "content_size": None,
        "window_bytes": 1048576,
        "frame_spans": ((0, 42, 0, 1048577),),
        "header_span": (0, 6),
        "block_count": 9,
        "strict_profile_refusal": True,
        "reason": "complete decompressed cap exceeded",
    },
)

# Complete source-derived physical framing expectations. Fields have explicit
# fixed order; original compressed coordinates are half-open and zero-based.
# Output-coordinate assertions remain in each case's separate frame_spans.
ZSTD_FRAME_FIELDS = (
    "frame_ordinal",
    "compressed_start",
    "compressed_end",
    "header_start",
    "header_end",
    "descriptor",
    "window_descriptor",
    "content_size_flag",
    "single_segment",
    "dictionary_id_flag",
    "checksum_flag",
    "content_size",
    "window_bytes",
    "dictionary_id",
    "checksum_value",
    "blocks",
)
ZSTD_BLOCK_FIELDS = (
    "block_ordinal",
    "header_start",
    "header_end",
    "last",
    "block_type",
    "block_size",
    "payload_start",
    "payload_end",
)
# descriptor retains every header bit; all current unused/reserved bits are0.
# No dictionary ID field exists in these literals. A checksum, when present,
# occupies [compressed_end-4, compressed_end) independently of block limits.
ZSTD_FRAME_EXPECTATIONS = {
    "raw_ab_known_single_checksum": (
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
            1070381285,
            ((1, 6, 9, True, 0, 2, 9, 11),),
        ),
    ),
    "compressed_one_literal_and_repeat_one_match": (
        (
            1,
            0,
            17,
            0,
            6,
            0,
            0,
            0,
            False,
            0,
            False,
            None,
            1024,
            None,
            None,
            ((1, 6, 9, True, 2, 8, 9, 17),),
        ),
    ),
    "compressed_two_huffman_symbols_zero_sequences": (
        (
            1,
            0,
            16,
            0,
            6,
            0,
            0,
            0,
            False,
            0,
            False,
            None,
            1024,
            None,
            None,
            ((1, 6, 9, True, 2, 7, 9, 16),),
        ),
    ),
    "raw_ab_known_single": (
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
    ),
    "raw_ab_unknown": (
        (
            1,
            0,
            11,
            0,
            6,
            0,
            0,
            0,
            False,
            0,
            False,
            None,
            1024,
            None,
            None,
            ((1, 6, 9, True, 0, 2, 9, 11),),
        ),
    ),
    "rle_four_a_known_single": (
        (
            1,
            0,
            10,
            0,
            6,
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
            ((1, 6, 9, True, 1, 4, 9, 10),),
        ),
    ),
    "compressed_raw_literals_abc_unknown": (
        (
            1,
            0,
            14,
            0,
            6,
            0,
            0,
            0,
            False,
            0,
            False,
            None,
            1024,
            None,
            None,
            ((1, 6, 9, True, 2, 5, 9, 14),),
        ),
    ),
    "compressed_raw_literals_abc_known_non_single": (
        (
            1,
            0,
            18,
            0,
            10,
            128,
            0,
            2,
            False,
            0,
            False,
            3,
            1024,
            None,
            None,
            ((1, 10, 13, True, 2, 5, 13, 18),),
        ),
    ),
    "compressed_rle_literals_eight_a": (
        (
            1,
            0,
            12,
            0,
            6,
            32,
            None,
            0,
            True,
            0,
            False,
            8,
            8,
            None,
            None,
            ((1, 6, 9, True, 2, 3, 9, 12),),
        ),
    ),
    "concatenated_raw_ab_and_rle_four_a": (
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
    ),
    "known_exact_one_mib": (
        (
            1,
            0,
            41,
            0,
            9,
            160,
            None,
            2,
            True,
            0,
            False,
            1048576,
            1048576,
            None,
            None,
            (
                (1, 9, 12, False, 1, 131072, 12, 13),
                (2, 13, 16, False, 1, 131072, 16, 17),
                (3, 17, 20, False, 1, 131072, 20, 21),
                (4, 21, 24, False, 1, 131072, 24, 25),
                (5, 25, 28, False, 1, 131072, 28, 29),
                (6, 29, 32, False, 1, 131072, 32, 33),
                (7, 33, 36, False, 1, 131072, 36, 37),
                (8, 37, 40, True, 1, 131072, 40, 41),
            ),
        ),
    ),
    "unknown_exact_one_mib": (
        (
            1,
            0,
            38,
            0,
            6,
            0,
            80,
            0,
            False,
            0,
            False,
            None,
            1048576,
            None,
            None,
            (
                (1, 6, 9, False, 1, 131072, 9, 10),
                (2, 10, 13, False, 1, 131072, 13, 14),
                (3, 14, 17, False, 1, 131072, 17, 18),
                (4, 18, 21, False, 1, 131072, 21, 22),
                (5, 22, 25, False, 1, 131072, 25, 26),
                (6, 26, 29, False, 1, 131072, 29, 30),
                (7, 30, 33, False, 1, 131072, 33, 34),
                (8, 34, 37, True, 1, 131072, 37, 38),
            ),
        ),
    ),
    # Over-cap frames remain complete physical oracles, not positive admission.
    "known_one_mib_plus_one": (
        (
            1,
            0,
            45,
            0,
            9,
            160,
            None,
            2,
            True,
            0,
            False,
            1048577,
            1048577,
            None,
            None,
            (
                (1, 9, 12, False, 1, 131072, 12, 13),
                (2, 13, 16, False, 1, 131072, 16, 17),
                (3, 17, 20, False, 1, 131072, 20, 21),
                (4, 21, 24, False, 1, 131072, 24, 25),
                (5, 25, 28, False, 1, 131072, 28, 29),
                (6, 29, 32, False, 1, 131072, 32, 33),
                (7, 33, 36, False, 1, 131072, 36, 37),
                (8, 37, 40, False, 1, 131072, 40, 41),
                (9, 41, 44, True, 1, 1, 44, 45),
            ),
        ),
    ),
    "unknown_one_mib_plus_one": (
        (
            1,
            0,
            42,
            0,
            6,
            0,
            80,
            0,
            False,
            0,
            False,
            None,
            1048576,
            None,
            None,
            (
                (1, 6, 9, False, 1, 131072, 9, 10),
                (2, 10, 13, False, 1, 131072, 13, 14),
                (3, 14, 17, False, 1, 131072, 17, 18),
                (4, 18, 21, False, 1, 131072, 21, 22),
                (5, 22, 25, False, 1, 131072, 25, 26),
                (6, 26, 29, False, 1, 131072, 29, 30),
                (7, 30, 33, False, 1, 131072, 33, 34),
                (8, 34, 37, False, 1, 131072, 37, 38),
                (9, 38, 41, True, 1, 1, 41, 42),
            ),
        ),
    ),
}

XXH64_SPEC_COMMIT = "e626a72bc2321cd320e953a0ccf1584cad60f363"
XXH64_SPEC_URL = (
    "https://github.com/Cyan4973/xxHash/blob/"
    "e626a72bc2321cd320e953a0ccf1584cad60f363/doc/xxhash_spec.md"
)
XXH64_SPEC_ANCHORS = (
    ("191-233", "constants and short-input initialization"),
    ("280-330", "length, tail bytes, rotations and avalanche"),
)
XXH64_VECTOR_SOURCE_URL = (
    "https://github.com/Cyan4973/xxHash/blob/173e50be0509c6fb6c1bb74d95049ef61d7fdced/xxhsum.c"
)
XXH64_VECTOR_SOURCE_ANCHORS = (
    ("580-590", "first sanity input byte is00"),
    ("1213-1215", "empty and one-byte00 independent seed0 vector literals"),
)
# Independent unsigned modulo2**64 arithmetic from the official algorithm,
# not native XXH64 or encoder output; checked against both source vectors.
# All values below are fixed literals. No hash algorithm runs in this module.
XXH64_CHECKSUM_ORACLES = (
    {"input_hex": "", "seed": 0, "xxh64": 0xEF46DB3751D8E999},
    {"input_hex": "00", "seed": 0, "xxh64": 0xE934A84ADB052768},
    {
        "input_hex": "4142",
        "seed": 0,
        "xxh64": 0x7E0D83C83FCCB8E5,
        "low32": 1070381285,
        "low32_little_endian_hex": "e5b8cc3f",
    },
)
ZSTD_CHECKSUM_NEGATIVE_CASES = (
    {
        "case_id": "raw_ab_wrong_checksum",
        "compressed_hex": "28b52ffd24021100004142e5b8cc3e",
        "decompressed_hex": "4142",
        "stored_checksum": 1053604069,
        "expected_checksum": 1070381285,
        "framing_is_complete": True,
        "checksum_consistency_refuses": True,
        "native_rejection_is_not_assumed": True,
    },
)
