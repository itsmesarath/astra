"""Independent complete Zstd capacity candidates; declarations only.

Every byte is invented directly from the pinned official format. No SDK,
encoder, native parser, production framer/serializer or observed codec output
defines these expectations. Repetition expands fixed literal byte strings;
the original compressed and decompressed strings remain complete, not sampled.
Root alone owns qualification launches and complete reconciliation.

These are UNEXECUTED source expectations, not a CLOSED profile, provider
implementation release, historical-member capacity or authentication claim.
"""

ZSTD_COMMIT = "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
ZSTD_FORMAT_URL = (
    "https://github.com/facebook/zstd/blob/"
    "f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md"
)
ZSTD_FORMAT_VERSION = "0.4.3 (2024-10-07)"
SOURCE_RULES = (
    ("#frames", "each frame is independent; concatenated output preserves frame order"),
    ("#frame_header_descriptor", "descriptor00: no FCS, no single-segment, no dictionary/checksum"),
    ("#window_descriptor", "descriptor50: exponent10/mantissa0 => 1 << 20 bytes"),
    ("#blocks", "three-byte LE header = (Block_Size << 3) | (Block_Type << 1) | Last_Block"),
    ("#blocks", "RAW payload has Block_Size bytes; RLE payload has one repeated byte"),
    ("#blocks", "both physical and regenerated block sizes <= min(window, 131072)"),
)
SOURCE_EXPECTATIONS_ARE_UNEXECUTED = True
PROFILE_CLOSED = False
PROVIDER_IMPLEMENTATION_RELEASED = False
SOURCE_AUTHENTICATION_ESTABLISHED = False

EXPECTED_POLICY = {
    "backend": "cext",
    "read_across_frames": False,
    "read_size": 65536,
    "max_window_size_argument": 1048576,
    "independent_window_cap": 1048576,
    "cumulative_output_cap": 1048576,
    "compressed_input_cap": 262144,
    "frame_cap": 16,
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

# Header: magic28b52ffd, descriptor00, window50 => six bytes total.
# Last RLE65536: (65536 << 3) | 2 | 1 = 0x080003 => 03 00 08;
# last RLE65537: (65537 << 3) | 2 | 1 = 0x08000b => 0b 00 08.
# Each payload is one exact byte41 ('A'), so each complete frame is10bytes.
UNKNOWN_RLE_65536_FRAME_HEX = "28b52ffd005003000841"
UNKNOWN_RLE_65537_FRAME_HEX = "28b52ffd00500b000841"
FRAME_STARTS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150)
OUTPUT_STARTS = (
    0,
    65536,
    131072,
    196608,
    262144,
    327680,
    393216,
    458752,
    524288,
    589824,
    655360,
    720896,
    786432,
    851968,
    917504,
    983040,
)
SIXTEEN_FRAME_DESCRIPTORS = tuple(
    (
        ordinal,
        start,
        start + 10,
        start,
        start + 6,
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
        ((1, start + 6, start + 9, True, 1, 65536, start + 9, start + 10),),
    )
    for ordinal, start in enumerate(FRAME_STARTS, 1)
)
SIXTEEN_FRAME_OUTPUT_SPANS = tuple(
    (start, start + 10, first, first + 65536)
    for start, first in zip(FRAME_STARTS, OUTPUT_STARTS, strict=True)
)
OVER_CAP_FRAME_DESCRIPTORS = SIXTEEN_FRAME_DESCRIPTORS[:15] + (
    (
        16,
        150,
        160,
        150,
        156,
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
        ((1, 156, 159, True, 1, 65537, 159, 160),),
    ),
)
OVER_CAP_FRAME_OUTPUT_SPANS = SIXTEEN_FRAME_OUTPUT_SPANS[:15] + ((150, 160, 983040, 1048577),)

# Exact262144compressed bytes: header6 + RAW headers3+3 + payload131072+131060.
# First nonlast RAW131072 header: (131072 << 3) = 0x100000 => 00 00 10.
# Last RAW131060 header: (131060 << 3) | 1 = 0x0fffa1 => a1 ff 0f.
# Both blocks fit the source-defined128KiB maximum under the1MiB window.
EXACT_INPUT_CAP_HEX = "28b52ffd0050" + "000010" + "41" * 131072 + "a1ff0f" + "42" * 131060
EXACT_INPUT_CAP_DESCRIPTORS = (
    (
        1,
        0,
        262144,
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
            (1, 6, 9, False, 0, 131072, 9, 131081),
            (2, 131081, 131084, True, 0, 131060, 131084, 262144),
        ),
    ),
)

ZSTD_CAPACITY_POSITIVE_CASES = (
    {
        "case_id": "sixteen_unknown_frames_exact_cumulative_one_mib",
        "compressed_hex": UNKNOWN_RLE_65536_FRAME_HEX * 16,
        "compressed_bytes": 160,
        "decompressed_hex": "41" * 1048576,
        "decompressed_bytes": 1048576,
        "frame_count": 16,
        "framing": SIXTEEN_FRAME_DESCRIPTORS,
        "frame_spans": SIXTEEN_FRAME_OUTPUT_SPANS,
        "expected_read_sizes": (65536,) * 31 + (1,),
        "expected_frame_input_positions": (10,) * 16,
        "termination_checks": tuple(
            {
                "frame_ordinal": ordinal,
                "max_output_size": 65536,
                "read_across_frames": False,
                "allow_extra_data": False,
                "output_bytes": 65536,
                "matches_stream_output": True,
            }
            for ordinal in range(1, 17)
        ),
        "provider_complete_result_allowed": False,
    },
    {
        "case_id": "exact_compressed_input_cap_two_complete_raw_blocks",
        "compressed_hex": EXACT_INPUT_CAP_HEX,
        "compressed_bytes": 262144,
        "decompressed_hex": "41" * 131072 + "42" * 131060,
        "decompressed_bytes": 262132,
        "frame_count": 1,
        "framing": EXACT_INPUT_CAP_DESCRIPTORS,
        "frame_spans": ((0, 262144, 0, 262132),),
        "expected_read_sizes": (65536,) * 5,
        "expected_frame_input_positions": (262144,),
        "termination_checks": (
            {
                "frame_ordinal": 1,
                "max_output_size": 262132,
                "read_across_frames": False,
                "allow_extra_data": False,
                "output_bytes": 262132,
                "matches_stream_output": True,
            },
        ),
        "provider_complete_result_allowed": False,
    },
)
ZSTD_CAPACITY_REFUSAL_CASES = (
    {
        "case_id": "sixteen_unknown_frames_cumulative_one_mib_plus_one",
        "compressed_hex": UNKNOWN_RLE_65536_FRAME_HEX * 15 + UNKNOWN_RLE_65537_FRAME_HEX,
        "compressed_bytes": 160,
        "decompressed_hex": "41" * 1048577,
        "decompressed_bytes": 1048577,
        "frame_count": 16,
        "framing": OVER_CAP_FRAME_DESCRIPTORS,
        "frame_spans": OVER_CAP_FRAME_OUTPUT_SPANS,
        "phase": "native_output_limit",
        "constructor_calls": 16,
        "error_type": "OutputLimitExceeded",
        "observed_output_bytes": 1048577,
        "provider_complete_result_allowed": False,
    },
)
ZSTD_CAPACITY_CASES = ZSTD_CAPACITY_POSITIVE_CASES + ZSTD_CAPACITY_REFUSAL_CASES
