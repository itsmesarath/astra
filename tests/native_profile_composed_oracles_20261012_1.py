"""Independent literal Zstd/DBN composition candidates, not observed native facts.

Declaration-only; no imports, encoder, native codec, serializer or reflection.
All DBN bytes and complete expected bodies are invented source-derived literals
from the held independent packet below. Standard RAW-block bytes are assembled
directly from the pinned Zstd format: single-segment FCS, then one last RAW block.
The concatenated case splits at DBN byte5, INSIDE the metadata length integer.
One DBN decoder must continue across that physical Zstd frame boundary.

These UNEXECUTED expectations are not a CLOSED profile, provider acceptance,
native initialization/decoding proof, historical input or authentication claim.
Root owns all launches and complete-body comparison. No SDK-returned result
defines an expected body, and original foreign occurrences are not filtered.
"""

SOURCE_EXPECTATIONS_ARE_UNEXECUTED = True
DBN_PACKET_PATH = "tests/native_profile_oracles_20261012_1.py"
DBN_PACKET_SHA256 = "48151a01cccf54df8815f934e160c2c75e848cbf82f6b04f4bdbcd54106b3c0a"
DBN_SOURCE_COMMIT = "aa012adc6502e01b01d7b5c7836742dde21e93d8"
ZSTD_SOURCE_COMMIT = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
ZSTD_FORMAT_URL = (
    "https://github.com/facebook/zstd/blob/"
    "f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md"
)
SOURCE_DERIVATION = (
    "Zstd magic 28b52ffd; descriptor20 gives single segment and one-byte FCS.",
    "Descriptor60 gives single segment and two-byte FCS with the format's +256 offset.",
    "Last RAW block header is (raw payload bytes << 3) | 1, three little-endian bytes.",
    "240: FCSf0/header810700; 256: stored FCS0000/header010800.",
    "Split5/235: FCS05/eb; RAW headers290000/590700; two complete standard frames.",
    "Complete DBN source cases minimal_absent_ts_out and minimal_present_ts_out.",
)
DBN_DECODER_EXPECTED_POLICY = {
    "has_metadata": True,
    "input_version": None,
    "upgrade_policy": "AS_IS",
    "upgrade_policy_code": 1,
    "compression": "NONE",
    "ts_out_constructor": False,
    "metadata_overrides_input_version_and_ts_out": True,
    "empty_buffer_is_complete_eof_proof": False,
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

ABSENT_DBN_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a000000"
    "0ea00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
    "edffffff14000000"
)
PRESENT_DBN_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000147000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "10a001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a0000001300000000000000"
    "10a00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
    "edffffff140000001d00000000000000"
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
METADATA_WIRE_PRESENT = {
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
METADATA_NATIVE_ABSENT = {
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
METADATA_NATIVE_PRESENT = {
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
TARGET_WIRE_ABSENT = {
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
FOREIGN_WIRE_ABSENT = {
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
TARGET_WIRE_PRESENT = {
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
FOREIGN_WIRE_PRESENT = {
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
TARGET_NATIVE_ABSENT = {
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
FOREIGN_NATIVE_ABSENT = {
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
TARGET_NATIVE_PRESENT = {
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
FOREIGN_NATIVE_PRESENT = {
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

COMPOSED_CASES = (
    {
        "case_id": "raw_minimal_absent_ts_out",
        "dbn_case_id": "minimal_absent_ts_out",
        "compressed_hex": (
            "28b52ffd20f0810700"
            "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
            "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
            "f7ffffff0a000000"
            "0ea00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
            "edffffff14000000"
        ),
        "decompressed_hex": ABSENT_DBN_HEX,
        "compressed_bytes": 249,
        "decompressed_bytes": 240,
        "metadata_count": 1,
        "mbo_count": 2,
        "frame_count": 1,
        "frame_spans": ((0, 249, 0, 240),),
        "frame_descriptors": (
            (
                1,
                0,
                249,
                0,
                6,
                32,
                None,
                0,
                True,
                0,
                False,
                240,
                240,
                None,
                None,
                ((1, 6, 9, True, 0, 240, 9, 249),),
            ),
        ),
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184), ("MBO", 184, 240)),
        "wire_bodies": (METADATA_WIRE_ABSENT, TARGET_WIRE_ABSENT, FOREIGN_WIRE_ABSENT),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            TARGET_NATIVE_ABSENT,
            FOREIGN_NATIVE_ABSENT,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "raw_minimal_present_ts_out",
        "dbn_case_id": "minimal_present_ts_out",
        "compressed_hex": (
            "28b52ffd600000010800"
            "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
            "000004000147000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "10a001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
            "f7ffffff0a0000001300000000000000"
            "10a00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
            "edffffff140000001d00000000000000"
        ),
        "decompressed_hex": PRESENT_DBN_HEX,
        "compressed_bytes": 266,
        "decompressed_bytes": 256,
        "metadata_count": 1,
        "mbo_count": 2,
        "frame_count": 1,
        "frame_spans": ((0, 266, 0, 256),),
        "frame_descriptors": (
            (
                1,
                0,
                266,
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
                ((1, 7, 10, True, 0, 256, 10, 266),),
            ),
        ),
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 192), ("MBO", 192, 256)),
        "wire_bodies": (METADATA_WIRE_PRESENT, TARGET_WIRE_PRESENT, FOREIGN_WIRE_PRESENT),
        "native_observations": (
            METADATA_NATIVE_PRESENT,
            TARGET_NATIVE_PRESENT,
            FOREIGN_NATIVE_PRESENT,
        ),
        "strict_profile_refusal": False,
    },
    {
        "case_id": "concatenated_raw_absent_split_metadata_length",
        "dbn_case_id": "minimal_absent_ts_out",
        "compressed_hex": (
            "28b52ffd200529000044424e0378"
            "28b52ffd20eb590700"
            "000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
            "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
            "f7ffffff0a000000"
            "0ea00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
            "edffffff14000000"
        ),
        "decompressed_hex": ABSENT_DBN_HEX,
        "compressed_bytes": 258,
        "decompressed_bytes": 240,
        "metadata_count": 1,
        "mbo_count": 2,
        "frame_count": 2,
        "frame_boundary_dbn_offset": 5,
        "frame_spans": ((0, 14, 0, 5), (14, 258, 5, 240)),
        "frame_descriptors": (
            (
                1,
                0,
                14,
                0,
                6,
                32,
                None,
                0,
                True,
                0,
                False,
                5,
                5,
                None,
                None,
                ((1, 6, 9, True, 0, 5, 9, 14),),
            ),
            (
                2,
                14,
                258,
                14,
                20,
                32,
                None,
                0,
                True,
                0,
                False,
                235,
                235,
                None,
                None,
                ((1, 20, 23, True, 0, 235, 23, 258),),
            ),
        ),
        "wire_spans": (("Metadata", 0, 128), ("MBO", 128, 184), ("MBO", 184, 240)),
        "wire_bodies": (METADATA_WIRE_ABSENT, TARGET_WIRE_ABSENT, FOREIGN_WIRE_ABSENT),
        "native_observations": (
            METADATA_NATIVE_ABSENT,
            TARGET_NATIVE_ABSENT,
            FOREIGN_NATIVE_ABSENT,
        ),
        "strict_profile_refusal": False,
    },
)
