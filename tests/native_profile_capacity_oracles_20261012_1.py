"""Independent complete native-capacity candidates; declarations only.

All bytes are invented and assembled directly from the immutable official DBN
v3 layout/FSM/getter sources below. No native encoder, SDK import, production
serializer, reflection or measured observation defines any expected body.
Root alone owns collection, codec calls and complete evidence reconciliation.
These source expectations are UNEXECUTED when authored; they cannot close P2
or a profile without separately qualified observed equality.

Three complete members cover the distinct raw-end-zero translation, maximal
Metadata u64 integers, and the simultaneous 128-position/16-per-list/16-group/
32-interval boundaries. The latter retains UTF-8 U+00E9 and valid leap-day
2024-02-29 -> 2024-03-01; it is not a historical feed/session/mapping claim.
All declared framing spans use half-open DECOMPRESSED DBN coordinates.
"""

DBN_COMMIT = "aa012adc6502e01b01d7b5c7836742dde21e93d8"
DBN_SOURCE_ROOT = "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/"
SOURCE_REFERENCES = (
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::decode_metadata_impl",
        "raw u64 start/limit; end UNDEF_TIMESTAMP vs NonZeroU64::new(0); "
        "no start/end ordering coercion",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::decode_metadata_repeated_symbol_cstr; decode_metadata_symbol_mappings",
        "complete count/list order and every mapping occurrence",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::decode_metadata_symbol_mapping; decode_metadata_symbol",
        "fixed 71-byte UTF-8 C strings and complete little-endian dated intervals",
    ),
    (
        "rust/dbn/src/decode/dbn/sync.rs",
        "decode_iso8601",
        "YYYYMMDD decomposition followed by time::Date::from_calendar_date",
    ),
    (
        "rust/dbn/src/encode/dbn/sync.rs",
        "MetadataEncoder::encode; encode_symbol_mappings; encode_repeated_symbol_cstr",
        "source layout ordering/alignment only; no encoder is executed",
    ),
    (
        "rust/dbn/src/metadata.rs",
        "Metadata fields",
        "u64 start and Option<NonZeroU64> end/limit getters",
    ),
    (
        "rust/dbn/src/python/metadata.rs",
        "Metadata::get_mappings; IntoPyObject for &MappingInterval",
        "getter dictionary and explicit Python-date year/month/day projections",
    ),
    (
        "rust/dbn/src/record.rs",
        "RecordHeader; MboMsg",
        "complete v3 Header/MBO named raw fields and widths",
    ),
    (
        "rust/dbn/src/python/record.rs",
        "MboMsg getter implementations",
        "native enum/flags, absent ts_out, record_size and ts_index observations",
    ),
    (
        "python/src/dbn_decoder.rs",
        "DbnDecoder::new; decode; write_and_decode",
        "explicit metadata-present AS_IS/NONE fresh continuous decoder",
    ),
)
SOURCE_EXPECTATIONS_ARE_UNEXECUTED = True
PROFILE_CLOSED = False
SOURCE_AUTHENTICATION_ESTABLISHED = False
PROVIDER_IMPLEMENTATION_RELEASED = False

DBN_DECODER_SOURCE_POLICY = {
    "has_metadata": True,
    "input_version": None,
    "upgrade_policy": "AS_IS",
    "compression": "NONE",
    "ts_out_constructor": False,
    "fresh_decoder_per_case_and_partition": True,
    "continuous_state_across_partition_chunks": True,
}
DBN_CAPACITY_LIMITS = {
    "decoded_positions": 128,
    "symbols": 16,
    "partial": 16,
    "not_found": 16,
    "mapping_groups": 16,
    "mapping_intervals": 32,
}
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
SIDE_BID = {
    "kind": "native_enum",
    "class_name": "Side",
    "name": "BID",
    "code": 66,
    "text": "B",
}

END_ZERO_METADATA_HEX = (
    "44424e0378000000494e56454e5445440000000000000000000000000000000000000000000000000000000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)

MAX_U64_METADATA_HEX = (
    "44424e0378000000494e56454e54454400000000000000000000fffffffffffffffffeffffffffffffffffffffffffff"
    "ffff04000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)

# Source arithmetic: body 120 + 48*71 + 16*(71+4) + 32*(4+4+71)
# = 7256 bytes, already eight-aligned. Full Metadata = 7264 bytes.
# U+00E9 is exactly c3 a9 followed by 69 zero bytes in each 71-byte string.
# Each group G00..G15 occurs once and has two retained identical intervals.
AT_CAP_METADATA_HEX = (
    "44424e03581c0000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000010000000c3a90000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a9000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000c3a900000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a90000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000c3a9000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000c3a900000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000c3a90000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000c3a9000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000c3a900000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000c3a90000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000c3a9000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000c3a900000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000c3a90000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000c3a9000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000c3a900000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000c3a90000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000010000000c3a90000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000c3a9000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000c3a900000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000c3a90000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000c3a9000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000c3a900000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000c3a90000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000c3a9000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "c3a900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000c3a90000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a9"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000c3a900000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a90000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000c3a9000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a900000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000c3a90000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000000010000000c3a90000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000c3a9000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000c3a900000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000c3a90000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000c3a9000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000c3a900000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000c3a90000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000c3a9000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000c3a900000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000c3a90000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000c3a9000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000c3a900000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000c3a90000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000c3a9000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000c3a900000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000c3a90000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000001000000047303000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000200000065d73401add73401c3a9000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000065d73401add7"
    "3401c3a90000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000004730310000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0200000065d73401add73401c3a900000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000065d73401add73401c3a9000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000473032000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000000000000000000000200000065d734"
    "01add73401c3a90000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000065d73401add73401c3a900000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000047303300000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000200000065d73401add73401c3a9"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000065d73401add73401c3a90000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000004730340000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000200000065d73401add73401c3a900000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000065d73401add73401c3a9000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000473035"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000200000065d73401add73401c3a90000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000065d73401add73401c3a900000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000047303600000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000200000065d73401add73401c3a9000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "65d73401add73401c3a90000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000004730370000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000200000065d73401add73401c3a900000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000065d73401add734"
    "01c3a9000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000473038000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002"
    "00000065d73401add73401c3a90000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000065d73401add73401c3a900000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000047303900000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000200000065d73401"
    "add73401c3a9000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000065d73401add73401c3a90000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000004731300000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000200000065d73401add73401c3a900"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000065d73401add73401c3a9000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000473131000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000200000065d73401add73401c3a90000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000065d73401add73401c3a900000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000047313200"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000200000065d73401add73401c3a9000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000065d73401add73401c3a90000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000004731330000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000200000065d73401add73401c3a900000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000065"
    "d73401add73401c3a9000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000473134000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000200000065d73401add73401c3a90000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000000000000000000065d73401add73401"
    "c3a900000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000047313500000000000000000000000000000000000000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000200"
    "000065d73401add73401c3a9000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000000000000000000000000000000000000065d73401add73401c3a90000000000"
    "000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "00000000000000000000000000000000"
)

TARGET_MBO_HEX = (
    "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a000000"
)
TARGET_WIRE = {
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
TARGET_NATIVE = {
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

END_ZERO_METADATA_WIRE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 120,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 0,
    "end": 0,
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
END_ZERO_METADATA_NATIVE = {
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
MAX_U64_METADATA_WIRE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 120,
    "dataset": "INVENTED",
    "dataset_cstr_bytes": 16,
    "schema": 0,
    "start": 18446744073709551615,
    "end": 18446744073709551614,
    "limit": 18446744073709551615,
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
MAX_U64_METADATA_NATIVE = {
    "kind": "Metadata",
    "version": 3,
    "dataset": "INVENTED",
    "schema": SCHEMA_MBO,
    "start": 18446744073709551615,
    "end": 18446744073709551614,
    "limit": 18446744073709551615,
    "stype_in": STYPE_PARENT,
    "stype_out": STYPE_INSTRUMENT_ID,
    "ts_out": False,
    "symbol_cstr_len": 71,
    "symbols": (),
    "partial": (),
    "not_found": (),
    "mappings": (),
}
LEAP_WIRE_INTERVAL = {
    "start_date": 20240229,
    "end_date": 20240301,
    "symbol": "\u00e9",
}
LEAP_NATIVE_INTERVAL = {
    "start_date": {"kind": "python_date", "year": 2024, "month": 2, "day": 29},
    "end_date": {"kind": "python_date", "year": 2024, "month": 3, "day": 1},
    "symbol": "\u00e9",
}
AT_CAP_WIRE_MAPPINGS = (
    {"raw_symbol": "G00", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G01", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G02", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G03", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G04", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G05", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G06", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G07", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G08", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G09", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G10", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G11", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G12", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G13", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G14", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
    {"raw_symbol": "G15", "interval_count": 2, "intervals": (LEAP_WIRE_INTERVAL,) * 2},
)
AT_CAP_NATIVE_MAPPINGS = (
    {"raw_symbol": "G00", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G01", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G02", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G03", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G04", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G05", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G06", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G07", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G08", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G09", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G10", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G11", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G12", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G13", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G14", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
    {"raw_symbol": "G15", "intervals": (LEAP_NATIVE_INTERVAL,) * 2},
)

AT_CAP_METADATA_WIRE = {
    "magic_hex": "44424e",
    "version": 3,
    "length_body": 7256,
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
    "symbols_count": 16,
    "symbols": ("\u00e9",) * 16,
    "partial_count": 16,
    "partial": ("\u00e9",) * 16,
    "not_found_count": 16,
    "not_found": ("\u00e9",) * 16,
    "mappings_count": 16,
    "mappings": AT_CAP_WIRE_MAPPINGS,
    "alignment_padding_bytes": (),
}
AT_CAP_METADATA_NATIVE = {
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
    "symbols": ("\u00e9",) * 16,
    "partial": ("\u00e9",) * 16,
    "not_found": ("\u00e9",) * 16,
    "mappings": AT_CAP_NATIVE_MAPPINGS,
}

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

MINIMAL_VARIABLE_SPANS = (
    ("symbols_count", 112, 116),
    ("partial_count", 116, 120),
    ("not_found_count", 120, 124),
    ("mappings_count", 124, 128),
)
AT_CAP_VARIABLE_SPANS = (
    ("symbols_count", 112, 116),
    ("symbols[0]", 116, 187),
    ("symbols[1]", 187, 258),
    ("symbols[2]", 258, 329),
    ("symbols[3]", 329, 400),
    ("symbols[4]", 400, 471),
    ("symbols[5]", 471, 542),
    ("symbols[6]", 542, 613),
    ("symbols[7]", 613, 684),
    ("symbols[8]", 684, 755),
    ("symbols[9]", 755, 826),
    ("symbols[10]", 826, 897),
    ("symbols[11]", 897, 968),
    ("symbols[12]", 968, 1039),
    ("symbols[13]", 1039, 1110),
    ("symbols[14]", 1110, 1181),
    ("symbols[15]", 1181, 1252),
    ("partial_count", 1252, 1256),
    ("partial[0]", 1256, 1327),
    ("partial[1]", 1327, 1398),
    ("partial[2]", 1398, 1469),
    ("partial[3]", 1469, 1540),
    ("partial[4]", 1540, 1611),
    ("partial[5]", 1611, 1682),
    ("partial[6]", 1682, 1753),
    ("partial[7]", 1753, 1824),
    ("partial[8]", 1824, 1895),
    ("partial[9]", 1895, 1966),
    ("partial[10]", 1966, 2037),
    ("partial[11]", 2037, 2108),
    ("partial[12]", 2108, 2179),
    ("partial[13]", 2179, 2250),
    ("partial[14]", 2250, 2321),
    ("partial[15]", 2321, 2392),
    ("not_found_count", 2392, 2396),
    ("not_found[0]", 2396, 2467),
    ("not_found[1]", 2467, 2538),
    ("not_found[2]", 2538, 2609),
    ("not_found[3]", 2609, 2680),
    ("not_found[4]", 2680, 2751),
    ("not_found[5]", 2751, 2822),
    ("not_found[6]", 2822, 2893),
    ("not_found[7]", 2893, 2964),
    ("not_found[8]", 2964, 3035),
    ("not_found[9]", 3035, 3106),
    ("not_found[10]", 3106, 3177),
    ("not_found[11]", 3177, 3248),
    ("not_found[12]", 3248, 3319),
    ("not_found[13]", 3319, 3390),
    ("not_found[14]", 3390, 3461),
    ("not_found[15]", 3461, 3532),
    ("mappings_count", 3532, 3536),
    ("mappings[0].raw_symbol", 3536, 3607),
    ("mappings[0].interval_count", 3607, 3611),
    ("mappings[0].intervals[0].start_date", 3611, 3615),
    ("mappings[0].intervals[0].end_date", 3615, 3619),
    ("mappings[0].intervals[0].symbol", 3619, 3690),
    ("mappings[0].intervals[1].start_date", 3690, 3694),
    ("mappings[0].intervals[1].end_date", 3694, 3698),
    ("mappings[0].intervals[1].symbol", 3698, 3769),
    ("mappings[1].raw_symbol", 3769, 3840),
    ("mappings[1].interval_count", 3840, 3844),
    ("mappings[1].intervals[0].start_date", 3844, 3848),
    ("mappings[1].intervals[0].end_date", 3848, 3852),
    ("mappings[1].intervals[0].symbol", 3852, 3923),
    ("mappings[1].intervals[1].start_date", 3923, 3927),
    ("mappings[1].intervals[1].end_date", 3927, 3931),
    ("mappings[1].intervals[1].symbol", 3931, 4002),
    ("mappings[2].raw_symbol", 4002, 4073),
    ("mappings[2].interval_count", 4073, 4077),
    ("mappings[2].intervals[0].start_date", 4077, 4081),
    ("mappings[2].intervals[0].end_date", 4081, 4085),
    ("mappings[2].intervals[0].symbol", 4085, 4156),
    ("mappings[2].intervals[1].start_date", 4156, 4160),
    ("mappings[2].intervals[1].end_date", 4160, 4164),
    ("mappings[2].intervals[1].symbol", 4164, 4235),
    ("mappings[3].raw_symbol", 4235, 4306),
    ("mappings[3].interval_count", 4306, 4310),
    ("mappings[3].intervals[0].start_date", 4310, 4314),
    ("mappings[3].intervals[0].end_date", 4314, 4318),
    ("mappings[3].intervals[0].symbol", 4318, 4389),
    ("mappings[3].intervals[1].start_date", 4389, 4393),
    ("mappings[3].intervals[1].end_date", 4393, 4397),
    ("mappings[3].intervals[1].symbol", 4397, 4468),
    ("mappings[4].raw_symbol", 4468, 4539),
    ("mappings[4].interval_count", 4539, 4543),
    ("mappings[4].intervals[0].start_date", 4543, 4547),
    ("mappings[4].intervals[0].end_date", 4547, 4551),
    ("mappings[4].intervals[0].symbol", 4551, 4622),
    ("mappings[4].intervals[1].start_date", 4622, 4626),
    ("mappings[4].intervals[1].end_date", 4626, 4630),
    ("mappings[4].intervals[1].symbol", 4630, 4701),
    ("mappings[5].raw_symbol", 4701, 4772),
    ("mappings[5].interval_count", 4772, 4776),
    ("mappings[5].intervals[0].start_date", 4776, 4780),
    ("mappings[5].intervals[0].end_date", 4780, 4784),
    ("mappings[5].intervals[0].symbol", 4784, 4855),
    ("mappings[5].intervals[1].start_date", 4855, 4859),
    ("mappings[5].intervals[1].end_date", 4859, 4863),
    ("mappings[5].intervals[1].symbol", 4863, 4934),
    ("mappings[6].raw_symbol", 4934, 5005),
    ("mappings[6].interval_count", 5005, 5009),
    ("mappings[6].intervals[0].start_date", 5009, 5013),
    ("mappings[6].intervals[0].end_date", 5013, 5017),
    ("mappings[6].intervals[0].symbol", 5017, 5088),
    ("mappings[6].intervals[1].start_date", 5088, 5092),
    ("mappings[6].intervals[1].end_date", 5092, 5096),
    ("mappings[6].intervals[1].symbol", 5096, 5167),
    ("mappings[7].raw_symbol", 5167, 5238),
    ("mappings[7].interval_count", 5238, 5242),
    ("mappings[7].intervals[0].start_date", 5242, 5246),
    ("mappings[7].intervals[0].end_date", 5246, 5250),
    ("mappings[7].intervals[0].symbol", 5250, 5321),
    ("mappings[7].intervals[1].start_date", 5321, 5325),
    ("mappings[7].intervals[1].end_date", 5325, 5329),
    ("mappings[7].intervals[1].symbol", 5329, 5400),
    ("mappings[8].raw_symbol", 5400, 5471),
    ("mappings[8].interval_count", 5471, 5475),
    ("mappings[8].intervals[0].start_date", 5475, 5479),
    ("mappings[8].intervals[0].end_date", 5479, 5483),
    ("mappings[8].intervals[0].symbol", 5483, 5554),
    ("mappings[8].intervals[1].start_date", 5554, 5558),
    ("mappings[8].intervals[1].end_date", 5558, 5562),
    ("mappings[8].intervals[1].symbol", 5562, 5633),
    ("mappings[9].raw_symbol", 5633, 5704),
    ("mappings[9].interval_count", 5704, 5708),
    ("mappings[9].intervals[0].start_date", 5708, 5712),
    ("mappings[9].intervals[0].end_date", 5712, 5716),
    ("mappings[9].intervals[0].symbol", 5716, 5787),
    ("mappings[9].intervals[1].start_date", 5787, 5791),
    ("mappings[9].intervals[1].end_date", 5791, 5795),
    ("mappings[9].intervals[1].symbol", 5795, 5866),
    ("mappings[10].raw_symbol", 5866, 5937),
    ("mappings[10].interval_count", 5937, 5941),
    ("mappings[10].intervals[0].start_date", 5941, 5945),
    ("mappings[10].intervals[0].end_date", 5945, 5949),
    ("mappings[10].intervals[0].symbol", 5949, 6020),
    ("mappings[10].intervals[1].start_date", 6020, 6024),
    ("mappings[10].intervals[1].end_date", 6024, 6028),
    ("mappings[10].intervals[1].symbol", 6028, 6099),
    ("mappings[11].raw_symbol", 6099, 6170),
    ("mappings[11].interval_count", 6170, 6174),
    ("mappings[11].intervals[0].start_date", 6174, 6178),
    ("mappings[11].intervals[0].end_date", 6178, 6182),
    ("mappings[11].intervals[0].symbol", 6182, 6253),
    ("mappings[11].intervals[1].start_date", 6253, 6257),
    ("mappings[11].intervals[1].end_date", 6257, 6261),
    ("mappings[11].intervals[1].symbol", 6261, 6332),
    ("mappings[12].raw_symbol", 6332, 6403),
    ("mappings[12].interval_count", 6403, 6407),
    ("mappings[12].intervals[0].start_date", 6407, 6411),
    ("mappings[12].intervals[0].end_date", 6411, 6415),
    ("mappings[12].intervals[0].symbol", 6415, 6486),
    ("mappings[12].intervals[1].start_date", 6486, 6490),
    ("mappings[12].intervals[1].end_date", 6490, 6494),
    ("mappings[12].intervals[1].symbol", 6494, 6565),
    ("mappings[13].raw_symbol", 6565, 6636),
    ("mappings[13].interval_count", 6636, 6640),
    ("mappings[13].intervals[0].start_date", 6640, 6644),
    ("mappings[13].intervals[0].end_date", 6644, 6648),
    ("mappings[13].intervals[0].symbol", 6648, 6719),
    ("mappings[13].intervals[1].start_date", 6719, 6723),
    ("mappings[13].intervals[1].end_date", 6723, 6727),
    ("mappings[13].intervals[1].symbol", 6727, 6798),
    ("mappings[14].raw_symbol", 6798, 6869),
    ("mappings[14].interval_count", 6869, 6873),
    ("mappings[14].intervals[0].start_date", 6873, 6877),
    ("mappings[14].intervals[0].end_date", 6877, 6881),
    ("mappings[14].intervals[0].symbol", 6881, 6952),
    ("mappings[14].intervals[1].start_date", 6952, 6956),
    ("mappings[14].intervals[1].end_date", 6956, 6960),
    ("mappings[14].intervals[1].symbol", 6960, 7031),
    ("mappings[15].raw_symbol", 7031, 7102),
    ("mappings[15].interval_count", 7102, 7106),
    ("mappings[15].intervals[0].start_date", 7106, 7110),
    ("mappings[15].intervals[0].end_date", 7110, 7114),
    ("mappings[15].intervals[0].symbol", 7114, 7185),
    ("mappings[15].intervals[1].start_date", 7185, 7189),
    ("mappings[15].intervals[1].end_date", 7189, 7193),
    ("mappings[15].intervals[1].symbol", 7193, 7264),
)

# Literal independent record-start ledger; not native yields or feed chunks.
AT_CAP_RECORD_STARTS = (
    7264,
    7320,
    7376,
    7432,
    7488,
    7544,
    7600,
    7656,
    7712,
    7768,
    7824,
    7880,
    7936,
    7992,
    8048,
    8104,
    8160,
    8216,
    8272,
    8328,
    8384,
    8440,
    8496,
    8552,
    8608,
    8664,
    8720,
    8776,
    8832,
    8888,
    8944,
    9000,
    9056,
    9112,
    9168,
    9224,
    9280,
    9336,
    9392,
    9448,
    9504,
    9560,
    9616,
    9672,
    9728,
    9784,
    9840,
    9896,
    9952,
    10008,
    10064,
    10120,
    10176,
    10232,
    10288,
    10344,
    10400,
    10456,
    10512,
    10568,
    10624,
    10680,
    10736,
    10792,
    10848,
    10904,
    10960,
    11016,
    11072,
    11128,
    11184,
    11240,
    11296,
    11352,
    11408,
    11464,
    11520,
    11576,
    11632,
    11688,
    11744,
    11800,
    11856,
    11912,
    11968,
    12024,
    12080,
    12136,
    12192,
    12248,
    12304,
    12360,
    12416,
    12472,
    12528,
    12584,
    12640,
    12696,
    12752,
    12808,
    12864,
    12920,
    12976,
    13032,
    13088,
    13144,
    13200,
    13256,
    13312,
    13368,
    13424,
    13480,
    13536,
    13592,
    13648,
    13704,
    13760,
    13816,
    13872,
    13928,
    13984,
    14040,
    14096,
    14152,
    14208,
    14264,
    14320,
)

# Tuple arithmetic only shifts the explicitly source-derived fixed MBO spans
# into the literal coordinate ledger above. No parser/serializer/native oracle.
AT_CAP_WIRE_SPANS = (("Metadata", 0, 7264),) + tuple(
    ("MBO", start, start + 56) for start in AT_CAP_RECORD_STARTS
)
AT_CAP_FIELD_SPANS = (METADATA_FIXED_SPANS + AT_CAP_VARIABLE_SPANS,) + tuple(
    tuple((name, start + left, start + right) for name, left, right in MBO_BASE_FIELD_SPANS)
    for start in AT_CAP_RECORD_STARTS
)
MINIMAL_FIELD_SPANS = (
    METADATA_FIXED_SPANS + MINIMAL_VARIABLE_SPANS,
    tuple((name, 128 + left, 128 + right) for name, left, right in MBO_BASE_FIELD_SPANS),
)
DBN_CAPACITY_CASES = (
    {
        "case_id": "metadata_raw_end_zero_native_none",
        "dbn_hex": END_ZERO_METADATA_HEX + TARGET_MBO_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (END_ZERO_METADATA_WIRE, TARGET_WIRE),
        "native_observations": (END_ZERO_METADATA_NATIVE, TARGET_NATIVE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "metadata_u64_start_limit_max_end_max_minus_one",
        "dbn_hex": MAX_U64_METADATA_HEX + TARGET_MBO_HEX,
        "complete_bytes": 184,
        "metadata_count": 1,
        "mbo_count": 1,
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184)),
        "wire_bodies": (MAX_U64_METADATA_WIRE, TARGET_WIRE),
        "native_observations": (MAX_U64_METADATA_NATIVE, TARGET_NATIVE),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "complete_128_positions_16_lists_groups_32_intervals_utf8_leap_day",
        "dbn_hex": AT_CAP_METADATA_HEX + TARGET_MBO_HEX * 127,
        "complete_bytes": 14376,
        "metadata_count": 1,
        "mbo_count": 127,
        "wire_spans": AT_CAP_WIRE_SPANS,
        "wire_bodies": (AT_CAP_METADATA_WIRE,) + (TARGET_WIRE,) * 127,
        "native_observations": (AT_CAP_METADATA_NATIVE,) + (TARGET_NATIVE,) * 127,
        "strict_profile_refusal": False,
    },
)
DBN_CAPACITY_FIELD_SPANS = {
    "metadata_raw_end_zero_native_none": MINIMAL_FIELD_SPANS,
    "metadata_u64_start_limit_max_end_max_minus_one": MINIMAL_FIELD_SPANS,
    "complete_128_positions_16_lists_groups_32_intervals_utf8_leap_day": AT_CAP_FIELD_SPANS,
}
