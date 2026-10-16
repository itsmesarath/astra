"""Independent bounded codec-direct negative controls; declarations only.

These are source-derived expectations, not observed native results. A later
explicitly registered contained control may call the codec despite physical
preflight refusal, solely to measure error/ReadMore/buffer behavior. This is
NOT positive provider admission, historical access, parser recovery authority,
authentication or a CLOSED profile. No imports, functions or codec calls occur
here. No SDK encoder, production serializer or returned observation defined
these literals. Root must review, pin and register before any native attempt.

Python decode() returns an ordinary list on Rust ReadMore, not a public
ReadMore object. An exception means no returned list from THAT call; earlier
successful calls may already have exposed a prefix. Empty buffer() is never
used as native EOF or complete-input proof. Error text is deliberately not an
oracle; exact DBNError class and full per-call bodies/buffers are.
"""

DBN_COMMIT = "aa012adc6502e01b01d7b5c7836742dde21e93d8"
DBN_SOURCE_ROOT = "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/"
HELD_LITERAL_ORACLE_SHA256 = "48151a01cccf54df8815f934e160c2c75e848cbf82f6b04f4bdbcd54106b3c0a"
SOURCE_EXPECTATIONS_NOT_NATIVE_OBSERVATIONS = True
PROFILE_CLOSED = False
PROVIDER_ADMISSION_BYPASS_AUTHORIZED = False
ERROR_TEXT_IS_NOT_ORACLE = True
DBN_DIRECT_POLICY = {
    "has_metadata": True,
    "input_version": None,
    "upgrade_policy": "AS_IS",
    "compression": "NONE",
    "ts_out_constructor": False,
    "fresh_decoder_per_case": True,
    "continuous_state_across_case_calls": True,
}
DBN_SOURCE_REFERENCES = (
    ("python/src/dbn_decoder.rs", "DbnDecoder::new", "explicit constructor controls"),
    (
        "python/src/dbn_decoder.rs",
        "DbnDecoder::write; buffer; write_and_decode",
        "exact write and buffer API",
    ),
    (
        "python/src/dbn_decoder.rs",
        "DbnDecoder::decode",
        "ReadMore returns list; Err discards current Vec",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::METADATA_PRELUDE_LEN; HEADER_LEN",
        "eight-byte prelude and RecordHeader threshold",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::data",
        "ConsumeOne/ConsumeBatch view excludes read bytes",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::process; record_length",
        "record length, ReadMore and error state",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::advance_to_record; consume",
        "ConsumeOne advances bytes then returns to Record state",
    ),
    (
        "rust/dbn/src/decode/dbn/fsm.rs",
        "DbnFsm::decode_prelude; decode_metadata",
        "prelude consumes8; metadata body consumed only on success",
    ),
    (
        "rust/dbn/src/macros.rs",
        "rtype_dispatch_base!",
        "unrecognized rtype Err before typed handler",
    ),
    (
        "rust/dbn/src/record_ref.rs",
        "Record implementation for RecordRef::rtype",
        "self.header().rtype() conversion",
    ),
    ("rust/dbn/src/enums.rs", "RType enum", "complete variant domain excludes ff"),
    (
        "rust/dbn/src/python.rs",
        "DBNError declaration; to_py_err; From<Error> for PyErr",
        "Rust error conversion is Python DBNError",
    ),
)

METADATA_HEX = (
    "44424e0378000000494e56454e544544000000000000000000000000000000000000ffffffffffffffff000000000000"
    "000004000047000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
)
TARGET_MBO_HEX = (
    "0ea001000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a000000"
)
FOREIGN_MBO_HEX = (
    "0ea00100030000000d000000000000000e00000000000000f1ffffffffffffff1000000000114e4e1200000000000000"
    "edffffff14000000"
)
INVALID_ZERO_LENGTH_HEADER_HEX = "00a00100020000000300000000000000"
UNSUPPORTED_RTYPE_RECORD_HEX = (
    "0eff01000200000003000000000000000400000000000000fbffffffffffffff06000000800741420800000000000000"
    "f7ffffff0a000000"
)
PRELUDE_SEVEN_HEX = "44424e03780000"
PRELUDE_EIGHT_HEX = "44424e0378000000"
BAD_MAGIC_PRELUDE_HEX = "58424e0378000000"
METADATA_LAST_BYTE_MISSING_HEX = METADATA_HEX[:-2]
TARGET_LAST_BYTE_MISSING_HEX = TARGET_MBO_HEX[:-2]
METADATA_BODY_LAST_BYTE_MISSING_HEX = METADATA_HEX[16:-2]

METADATA_NATIVE = {
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
TARGET_NATIVE = {
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
    "action": {
        "kind": "native_enum",
        "class_name": "Action",
        "name": "ADD",
        "code": 65,
        "text": "A",
    },
    "side": {"kind": "native_enum", "class_name": "Side", "name": "BID", "code": 66, "text": "B"},
    "ts_recv": 8,
    "ts_in_delta": -9,
    "sequence": 10,
    "ts_out": 18446744073709551615,
    "record_size": 56,
    "ts_index": 8,
}

DBN_NATIVE_CALL_FIELDS = (
    "operation",
    "input_chunk_hex",
    "returned_observations",
    "error_class",
    "buffer_hex",
)
DBN_NATIVE_NEGATIVE_CASE_FIELDS = (
    "case_id",
    "complete_input_hex",
    "input_chunks_hex",
    "calls",
    "visible_observations",
    "interpretation",
    "provider_complete_result_allowed",
)

# A new decoder is used for each case; every call within that case reuses it.
# decode-only calls write no extra bytes. None means no list was returned,
# whereas () means an actual empty returned list. These are not interchangeable.
DBN_NATIVE_NEGATIVE_CASES = (
    {
        "case_id": "native_seven_byte_prelude_readmore",
        "complete_input_hex": PRELUDE_SEVEN_HEX,
        "input_chunks_hex": (PRELUDE_SEVEN_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": PRELUDE_SEVEN_HEX,
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": PRELUDE_SEVEN_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": PRELUDE_SEVEN_HEX,
            },
        ),
        "visible_observations": (),
        "interpretation": "incomplete_prelude_readmore_not_exception",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_eight_byte_prelude_empty_buffer_is_not_eof",
        "complete_input_hex": PRELUDE_EIGHT_HEX,
        "input_chunks_hex": (PRELUDE_EIGHT_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": PRELUDE_EIGHT_HEX,
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "",
            },
        ),
        "visible_observations": (),
        "interpretation": "prelude_consumed_but_all120_metadata_body_bytes_missing",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_metadata_last_byte_readmore",
        "complete_input_hex": METADATA_LAST_BYTE_MISSING_HEX,
        "input_chunks_hex": (METADATA_LAST_BYTE_MISSING_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_LAST_BYTE_MISSING_HEX,
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": METADATA_BODY_LAST_BYTE_MISSING_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": METADATA_BODY_LAST_BYTE_MISSING_HEX,
            },
        ),
        "visible_observations": (),
        "interpretation": "valid_prelude_consumed_119_metadata_body_bytes_retained",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_partial_mbo_returns_metadata_prefix",
        "complete_input_hex": METADATA_HEX + TARGET_LAST_BYTE_MISSING_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_LAST_BYTE_MISSING_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_LAST_BYTE_MISSING_HEX,
                "returned_observations": (METADATA_NATIVE,),
                "error_class": None,
                "buffer_hex": TARGET_LAST_BYTE_MISSING_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": TARGET_LAST_BYTE_MISSING_HEX,
            },
        ),
        "visible_observations": (METADATA_NATIVE,),
        "interpretation": "native_metadata_prefix_is_not_complete_member",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_trailing_byte_returns_metadata_mbo_prefix",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + "00",
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX + "00",),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX + "00",
                "returned_observations": (METADATA_NATIVE, TARGET_NATIVE),
                "error_class": None,
                "buffer_hex": "00",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "00",
            },
        ),
        "visible_observations": (METADATA_NATIVE, TARGET_NATIVE),
        "interpretation": "unexplained_one_byte_tail_is_readmore_not_eof",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_bad_magic_preconsume_error",
        "complete_input_hex": BAD_MAGIC_PRELUDE_HEX,
        "input_chunks_hex": (BAD_MAGIC_PRELUDE_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": BAD_MAGIC_PRELUDE_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": BAD_MAGIC_PRELUDE_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": BAD_MAGIC_PRELUDE_HEX,
            },
        ),
        "visible_observations": (),
        "interpretation": "invalid_prelude_not_consumed_error_repeats",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_zero_length_late_error_same_call_discards_current_list",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + INVALID_ZERO_LENGTH_HEADER_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX + INVALID_ZERO_LENGTH_HEADER_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX + INVALID_ZERO_LENGTH_HEADER_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": INVALID_ZERO_LENGTH_HEADER_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": INVALID_ZERO_LENGTH_HEADER_HEX,
            },
        ),
        "visible_observations": (),
        "interpretation": "late_error_discards_vec_from_this_call_not_native_atomicity",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_zero_length_late_error_split_calls_exposes_earlier_prefix",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + INVALID_ZERO_LENGTH_HEADER_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX, INVALID_ZERO_LENGTH_HEADER_HEX),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX,
                "returned_observations": (METADATA_NATIVE, TARGET_NATIVE),
                "error_class": None,
                "buffer_hex": "",
            },
            {
                "operation": "write_then_decode",
                "input_chunk_hex": INVALID_ZERO_LENGTH_HEADER_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": INVALID_ZERO_LENGTH_HEADER_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": INVALID_ZERO_LENGTH_HEADER_HEX,
            },
        ),
        "visible_observations": (METADATA_NATIVE, TARGET_NATIVE),
        "interpretation": "earlier_returned_prefix_cannot_be_adopted_as_complete",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_missing_header_direct_mbo_preconsume_error",
        "complete_input_hex": TARGET_MBO_HEX,
        "input_chunks_hex": (TARGET_MBO_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": TARGET_MBO_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": TARGET_MBO_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": TARGET_MBO_HEX,
            },
        ),
        "visible_observations": (),
        "interpretation": "metadata_present_decoder_rejects_record_bytes_as_invalid_prelude",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_missing_header_four_byte_mbo_prefix_readmore",
        "complete_input_hex": "0ea00100",
        "input_chunks_hex": ("0ea00100",),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": "0ea00100",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "0ea00100",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "0ea00100",
            },
        ),
        "visible_observations": (),
        "interpretation": "fewer_than8_bytes_delay_even_invalid_prelude_magic_validation",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_duplicate_header_is_buffered_as_incomplete_record",
        "complete_input_hex": METADATA_HEX + METADATA_HEX,
        "input_chunks_hex": (METADATA_HEX + METADATA_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + METADATA_HEX,
                "returned_observations": (METADATA_NATIVE,),
                "error_class": None,
                "buffer_hex": METADATA_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": METADATA_HEX,
            },
        ),
        "visible_observations": (METADATA_NATIVE,),
        "interpretation": "second_D_byte_claims_record_length272_with_only128_available",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_late_header_is_buffered_after_complete_record_prefix",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + METADATA_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX + METADATA_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX + METADATA_HEX,
                "returned_observations": (METADATA_NATIVE, TARGET_NATIVE),
                "error_class": None,
                "buffer_hex": METADATA_HEX,
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": METADATA_HEX,
            },
        ),
        "visible_observations": (METADATA_NATIVE, TARGET_NATIVE),
        "interpretation": "late_header_is_not_recognized_as_second_metadata_before_record_readmore",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_unknown_final_rtype_same_call_error_with_empty_data_view",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + UNSUPPORTED_RTYPE_RECORD_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX + UNSUPPORTED_RTYPE_RECORD_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX + UNSUPPORTED_RTYPE_RECORD_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": "",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "",
            },
        ),
        "visible_observations": (),
        "interpretation": "dispatch_error_after_ConsumeOne_data_view_is_not_recovery_or_eof",
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "native_unknown_final_rtype_split_calls_error_after_visible_prefix",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX + UNSUPPORTED_RTYPE_RECORD_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX, UNSUPPORTED_RTYPE_RECORD_HEX),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX,
                "returned_observations": (METADATA_NATIVE, TARGET_NATIVE),
                "error_class": None,
                "buffer_hex": "",
            },
            {
                "operation": "write_then_decode",
                "input_chunk_hex": UNSUPPORTED_RTYPE_RECORD_HEX,
                "returned_observations": None,
                "error_class": "DBNError",
                "buffer_hex": "",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "",
            },
        ),
        "visible_observations": (METADATA_NATIVE, TARGET_NATIVE),
        "interpretation": "empty_data_view_after_error_cannot_clear_invalid_member_or_adopt_prefix",
        "provider_complete_result_allowed": False,
    },
)

# This is a syntactically complete DIFFERENT member, not codec truncation.
# Holding the intended240-byte member makes the184-byte substitution refuse
# raw whole-input equality independently of native buffer or successful prefix.
DBN_COMPLETE_PREFIX_IDENTITY_FIELDS = (
    "case_id",
    "complete_input_hex",
    "held_whole_input_hex",
    "input_chunks_hex",
    "calls",
    "visible_observations",
    "physical_input_is_complete",
    "matches_held_whole_input",
    "source_authentication_established",
)
DBN_COMPLETE_PREFIX_IDENTITY_CASES = (
    {
        "case_id": "complete_record_boundary_is_different_from_held_whole_member",
        "complete_input_hex": METADATA_HEX + TARGET_MBO_HEX,
        "held_whole_input_hex": METADATA_HEX + TARGET_MBO_HEX + FOREIGN_MBO_HEX,
        "input_chunks_hex": (METADATA_HEX + TARGET_MBO_HEX,),
        "calls": (
            {
                "operation": "write_then_decode",
                "input_chunk_hex": METADATA_HEX + TARGET_MBO_HEX,
                "returned_observations": (METADATA_NATIVE, TARGET_NATIVE),
                "error_class": None,
                "buffer_hex": "",
            },
            {
                "operation": "decode",
                "input_chunk_hex": "",
                "returned_observations": (),
                "error_class": None,
                "buffer_hex": "",
            },
        ),
        "visible_observations": (METADATA_NATIVE, TARGET_NATIVE),
        "physical_input_is_complete": True,
        "matches_held_whole_input": False,
        "source_authentication_established": False,
    },
)

ZSTD_SPEC_COMMIT = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
ZSTD_SPEC_URL = (
    "https://github.com/facebook/zstd/blob/"
    "f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md"
)
ZSTD_SOURCE_REFERENCES = (
    (
        "Frame_Header and Block_Header",
        "single-segment FCS, window and zero-sized last RAW block framing",
    ),
    ("Frames", "independent frames can be concatenated in original order"),
)
EMPTY_RAW_SINGLE_FRAME_HEX = "28b52ffd2000010000"
RAW_AB_SINGLE_FRAME_HEX = "28b52ffd20021100004142"
ZSTD_EMPTY_FRAME_FIELDS = (
    "case_id",
    "compressed_hex",
    "compressed_bytes",
    "framing",
    "frame_output_hex",
    "complete_output_hex",
    "empty_frame_ordinals",
    "positive_profile_refuses_empty_frame",
)
ZSTD_EMPTY_FRAME_CASES = (
    {
        "case_id": "native_empty_raw_single_frame",
        "compressed_hex": EMPTY_RAW_SINGLE_FRAME_HEX,
        "compressed_bytes": 9,
        "framing": (
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
        ),
        "frame_output_hex": ("",),
        "complete_output_hex": "",
        "empty_frame_ordinals": (1,),
        "positive_profile_refuses_empty_frame": True,
    },
    {
        "case_id": "native_empty_frame_before_raw_ab",
        "compressed_hex": EMPTY_RAW_SINGLE_FRAME_HEX + RAW_AB_SINGLE_FRAME_HEX,
        "compressed_bytes": 20,
        "framing": (
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
        ),
        "frame_output_hex": ("", "4142"),
        "complete_output_hex": "4142",
        "empty_frame_ordinals": (1,),
        "positive_profile_refuses_empty_frame": True,
    },
    {
        "case_id": "native_raw_ab_before_empty_frame",
        "compressed_hex": RAW_AB_SINGLE_FRAME_HEX + EMPTY_RAW_SINGLE_FRAME_HEX,
        "compressed_bytes": 20,
        "framing": (
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
        ),
        "frame_output_hex": ("4142", ""),
        "complete_output_hex": "4142",
        "empty_frame_ordinals": (2,),
        "positive_profile_refuses_empty_frame": True,
    },
)

# These few codec-direct controls qualify the exact terminal method separately
# from physical framing and positive provider admission. The terminal policy
# uses a nonzero exact destination, not a guessed/universal allocation cap.
PYTHON_ZSTD_COMMIT = "7a77a7510b8ce068e4a103d29aea1b5ec829d8b6"
PYTHON_ZSTD_SOURCE_ROOT = (
    "https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/"
)
ZSTD_TERMINAL_SOURCE_REFERENCES = (
    (
        "c-ext/decompressor.c",
        "Decompressor_init; ensure_dctx",
        "explicit standard-format/no-dictionary context",
    ),
    (
        "c-ext/decompressor.c",
        "Decompressor_decompress argument and frameHeader branches",
        "method kwargs and complete frame-header check",
    ),
    (
        "c-ext/decompressor.c",
        "Decompressor_decompress decompressedSize branches",
        "known FCS versus unknown-FCS destination allocation",
    ),
    (
        "c-ext/decompressor.c",
        "Decompressor_decompress ZSTD_isError/zresult branches",
        "codec error or unfinished frame becomes ZstdError",
    ),
    (
        "c-ext/decompressor.c",
        "Decompressor_decompress outBuffer.pos/allowExtraData branches",
        "length/resize/no-extra-data ordering",
    ),
)
ZSTD_TERMINAL_CONSTRUCTOR_KWARGS = {
    "dict_data": None,
    "max_window_size": 1048576,
    "format": "FORMAT_ZSTD1",
}
# The format string above names a fixed, registered module constant; it is not
# passed to a native integer argument or resolved from arbitrary caller text.
ZSTD_TERMINAL_NEGATIVE_CASE_FIELDS = (
    "case_id",
    "compressed_hex",
    "constructor_kwargs",
    "decompress_kwargs",
    "returned_output_hex",
    "error_class",
    "positive_profile_result_allowed",
    "source_rule",
)
ZSTD_TERMINAL_NEGATIVE_CASES = (
    {
        "case_id": "native_terminal_truncated_raw_ab_final_byte",
        "compressed_hex": "28b52ffd200211000041",
        "constructor_kwargs": ZSTD_TERMINAL_CONSTRUCTOR_KWARGS,
        "decompress_kwargs": {
            "max_output_size": 2,
            "read_across_frames": False,
            "allow_extra_data": False,
        },
        "returned_output_hex": None,
        "error_class": "ZstdError",
        "positive_profile_result_allowed": False,
        "source_rule": "unfinished_or_invalid_frame_has_no_successful_returned_bytes",
    },
    {
        "case_id": "native_terminal_complete_raw_ab_plus_forbidden_tail",
        "compressed_hex": "28b52ffd2002110000414200",
        "constructor_kwargs": ZSTD_TERMINAL_CONSTRUCTOR_KWARGS,
        "decompress_kwargs": {
            "max_output_size": 2,
            "read_across_frames": False,
            "allow_extra_data": False,
        },
        "returned_output_hex": None,
        "error_class": "ZstdError",
        "positive_profile_result_allowed": False,
        "source_rule": "exact_two_byte_destination_reaches_explicit_unused_input_refusal",
    },
    {
        "case_id": "native_terminal_unknown_raw_ab_destination_one_is_insufficient",
        "compressed_hex": "28b52ffd00001100004142",
        "constructor_kwargs": ZSTD_TERMINAL_CONSTRUCTOR_KWARGS,
        "decompress_kwargs": {
            "max_output_size": 1,
            "read_across_frames": False,
            "allow_extra_data": False,
        },
        "returned_output_hex": None,
        "error_class": "ZstdError",
        "positive_profile_result_allowed": False,
        "source_rule": "unknown_fcs_destination_cannot_finish_frame_requiring_two_output_bytes",
    },
)
