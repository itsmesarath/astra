"""Independent known Action/Side source oracles; declarations only.

All byte strings are invented complete DBN v3 Metadata plus one MBO record.
They are manually assembled from the pinned layout and held literal packet,
not an SDK encoder, native observation, production serializer or reflection.
No imports, functions, native calls or historical inputs occur in this file.

Every source-defined Action and Side variant is represented separately with
both absent and present ts_out. Getter representation is a source expectation,
not a native measurement or CLOSED profile. Unknown-character cases remain
separate in the held original oracle; no known variant is relabeled unknown.
"""

DBN_COMMIT = "aa012adc6502e01b01d7b5c7836742dde21e93d8"
DBN_SOURCE_ROOT = "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/"
HELD_LITERAL_ORACLE_SHA256 = "48151a01cccf54df8815f934e160c2c75e848cbf82f6b04f4bdbcd54106b3c0a"
SOURCE_EXPECTATIONS_NOT_NATIVE_OBSERVATIONS = True
PROFILE_CLOSED = False
UNKNOWN_CHARACTER_CASES_REMAIN_SEPARATE = True

SOURCE_REFERENCES = (
    ("rust/dbn/src/enums.rs", "265-275", "complete three-variant Side domain"),
    ("rust/dbn/src/enums.rs", "308-330", "complete seven-variant Action domain"),
    ("rust/dbn/src/python/enums.rs", "130-160", "Side name, numeric index and text"),
    ("rust/dbn/src/python/enums.rs", "198-232", "Action name, numeric index and text"),
    (
        "rust/dbn/src/python/record.rs",
        "209-224",
        "recognized enum versus unknown-character getter paths",
    ),
    ("rust/dbn/src/record.rs", "37-122", "complete Header/MBO field layout"),
    ("rust/dbn/src/record/layout_tests.rs", "67-119", "MBO field offsets and lengths"),
    ("rust/dbn/src/python/record.rs", "289-313", "absent versus present ts_out conversion"),
)

# Entries retain the source enum order, not an inferred ordinal or sorting rule.
# Numeric code is the exact __index__ result; .value is TEXT for these classes.
ACTION_DOMAIN_FIELDS = (
    "name",
    "code",
    "text",
    "wire_byte_hex",
    "wire_source_lines",
    "name_source_line",
)
ACTION_DOMAIN = (
    ("MODIFY", 77, "M", "4d", "310-311", 214),
    ("TRADE", 84, "T", "54", "313-314", 215),
    ("FILL", 70, "F", "46", "316-317", 216),
    ("CANCEL", 67, "C", "43", "319-320", 217),
    ("ADD", 65, "A", "41", "322-323", 218),
    ("CLEAR", 82, "R", "52", "325-326", 219),
    ("NONE", 78, "N", "4e", "329-330", 220),
)
SIDE_DOMAIN_FIELDS = ACTION_DOMAIN_FIELDS
SIDE_DOMAIN = (
    ("ASK", 65, "A", "41", "267-268", 146),
    ("BID", 66, "B", "42", "270-271", 147),
    ("NONE", 78, "N", "4e", "274-275", 148),
)
ENUM_OBSERVATION_FIELDS = ("kind", "class_name", "name", "code", "text")

ACTION_MODIFY = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "MODIFY",
    "code": 77,
    "text": "M",
}
ACTION_TRADE = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "TRADE",
    "code": 84,
    "text": "T",
}
ACTION_FILL = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "FILL",
    "code": 70,
    "text": "F",
}
ACTION_CANCEL = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "CANCEL",
    "code": 67,
    "text": "C",
}
ACTION_ADD = {"kind": "native_enum", "class_name": "Action", "name": "ADD", "code": 65, "text": "A"}
ACTION_CLEAR = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "CLEAR",
    "code": 82,
    "text": "R",
}
ACTION_NONE = {
    "kind": "native_enum",
    "class_name": "Action",
    "name": "NONE",
    "code": 78,
    "text": "N",
}
SIDE_ASK = {"kind": "native_enum", "class_name": "Side", "name": "ASK", "code": 65, "text": "A"}
SIDE_BID = {"kind": "native_enum", "class_name": "Side", "name": "BID", "code": 66, "text": "B"}
SIDE_NONE = {"kind": "native_enum", "class_name": "Side", "name": "NONE", "code": 78, "text": "N"}

# Exactly the held128-byte Metadata literals. One byte at52 declares ts_out.
METADATA_ABSENT_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
METADATA_PRESENT_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000147000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
METADATA_WIRE_ABSENT = {
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
METADATA_WIRE_PRESENT = {**METADATA_WIRE_ABSENT, "ts_out": 1}
METADATA_NATIVE_ABSENT = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": {
        "kind": "native_enum",
        "class_name": "Schema",
        "name": "MBO",
        "code": 0,
        "text": "mbo",
    },
    "start": 0,
    "end": None,
    "limit": None,
    "stype_in": {
        "kind": "native_enum",
        "class_name": "SType",
        "name": "PARENT",
        "code": 4,
        "text": "parent",
    },
    "stype_out": {
        "kind": "native_enum",
        "class_name": "SType",
        "name": "INSTRUMENT_ID",
        "code": 0,
        "text": "instrument_id",
    },
    "ts_out": False,
    "symbol_cstr_len": 71,
    "symbols": (),
    "partial": (),
    "not_found": (),
    "mappings": (),
}
METADATA_NATIVE_PRESENT = {**METADATA_NATIVE_ABSENT, "ts_out": True}

# Raw MBO prefix covers bytes0..38; the following two literal bytes are
# action38 and side39. Suffix starts at ts_recv40; present suffix appends19.
MBO_PREFIX_ABSENT_HEX = (
    "0ea001000200000003000000000000000400000000000000fbffffffffffffff060000008007"
)
MBO_PREFIX_PRESENT_HEX = (
    "10a001000200000003000000000000000400000000000000fbffffffffffffff060000008007"
)
MBO_SUFFIX_ABSENT_HEX = "0800000000000000f7ffffff0a000000"
MBO_SUFFIX_PRESENT_HEX = "0800000000000000f7ffffff0a0000001300000000000000"
MBO_WIRE_ABSENT = {
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
MBO_WIRE_PRESENT = {**MBO_WIRE_ABSENT, "length_words": 16, "ts_out": 19}
MBO_NATIVE_ABSENT = {
    "kind": "MBO",
    "rtype": {
        "kind": "native_enum",
        "class_name": "RType",
        "name": "MBO",
        "code": 160,
        "text": "mbo",
    },
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
MBO_NATIVE_PRESENT = {**MBO_NATIVE_ABSENT, "ts_out": 19, "record_size": 64}

DBN_ENUM_CASES = (
    {
        "case_id": "enum_action_modify_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4d42" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 77}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_MODIFY},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_modify_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4d42" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 77}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_MODIFY},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_trade_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "5442" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 84}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_TRADE},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_trade_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "5442" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 84}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_TRADE},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_fill_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4642" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 70}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_FILL},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_fill_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4642" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 70}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_FILL},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_cancel_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4342" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 67}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_CANCEL},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_cancel_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4342" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 67}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_CANCEL},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_add_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4142" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, MBO_WIRE_ABSENT),
        "native_observations": (METADATA_NATIVE_ABSENT, MBO_NATIVE_ABSENT),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_add_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4142" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, MBO_WIRE_PRESENT),
        "native_observations": (METADATA_NATIVE_PRESENT, MBO_NATIVE_PRESENT),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_clear_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "5242" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 82}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_CLEAR},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_clear_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "5242" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 82}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_CLEAR},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_none_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4e42" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "action": 78}),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            {**MBO_NATIVE_ABSENT, "action": ACTION_NONE},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_action_none_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4e42" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "action": 78}),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            {**MBO_NATIVE_PRESENT, "action": ACTION_NONE},
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_ask_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4141" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "side": 65}),
        "native_observations": (METADATA_NATIVE_ABSENT, {**MBO_NATIVE_ABSENT, "side": SIDE_ASK}),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_ask_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4141" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "side": 65}),
        "native_observations": (METADATA_NATIVE_PRESENT, {**MBO_NATIVE_PRESENT, "side": SIDE_ASK}),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_bid_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "4142" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, MBO_WIRE_ABSENT),
        "native_observations": (METADATA_NATIVE_ABSENT, MBO_NATIVE_ABSENT),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_bid_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "4142" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, MBO_WIRE_PRESENT),
        "native_observations": (METADATA_NATIVE_PRESENT, MBO_NATIVE_PRESENT),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_none_absent_ts_out",
        "dbn_hex": METADATA_ABSENT_HEX + MBO_PREFIX_ABSENT_HEX + "414e" + MBO_SUFFIX_ABSENT_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (METADATA_WIRE_ABSENT, {**MBO_WIRE_ABSENT, "side": 78}),
        "native_observations": (METADATA_NATIVE_ABSENT, {**MBO_NATIVE_ABSENT, "side": SIDE_NONE}),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "enum_side_none_present_ts_out",
        "dbn_hex": METADATA_PRESENT_HEX + MBO_PREFIX_PRESENT_HEX + "414e" + MBO_SUFFIX_PRESENT_HEX,
        "complete_bytes": 192,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192)),
        "wire_bodies": (METADATA_WIRE_PRESENT, {**MBO_WIRE_PRESENT, "side": 78}),
        "native_observations": (METADATA_NATIVE_PRESENT, {**MBO_NATIVE_PRESENT, "side": SIDE_NONE}),
        "strict_profile_refusal": False,
    },
)
