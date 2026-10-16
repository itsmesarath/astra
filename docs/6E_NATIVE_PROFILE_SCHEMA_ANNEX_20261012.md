# Native profile exact schema annex — 2026-10-12

## Current status, scope and precedence

**CANDIDATE — pending complete C4 static review and profile/receipt assembly; NOT CLOSED.** This annex saves the exact T12 schema choices after root's terminal acceptance at **2026-10-12T17:37:30Z**. Complete regression is accepted: **12,414 passed + exactly three held skips**, 12,417 unique case-sensitive identities = every 12,206 old + 211 new, zero failures/errors. The [terminal receipt](../logs/native_profile_20261012_1/full_terminal_acceptance_1.json) records report/raw-pin/owned-exit reconciliation. It does not by itself close this new schema/profile or implement a provider.

The authorized window remains **2026-10-12T13:59:46Z–19:59:46Z (20:59:46 Lisbon)**. This document does not extend it. All 418 old Python files, approved contracts/plans, old source/target/input/result/control pins and UNKNOWN liabilities stay held. The ten new proof Python files and all independent oracles were frozen for the accepted full suite. No new native/runtime/code work is launched by this annex.

The [approved native/source-evidence contract](6E_NATIVE_SOURCE_EVIDENCE_CONTRACT_20261012.md), [P1–P5 proof plan](../tasks/native_source_evidence_p1_p5_plan_20261012.md), [proof window](6E_NATIVE_PROFILE_PROOF_WINDOW_20261012.md) and [candidate revision](6E_NATIVE_PROFILE_QUALIFICATION_REVISION_20261012.md) remain intact. This annex explicitly settles the previously blocked representations and normative interface choices; it does not silently rewrite the old approved contract. The notable explicit projection correction is **14 Metadata getters, including symbol_cstr_len**, not the earlier 13-field proposal. Candidate revision hashes/status rows are earlier snapshots; the current formatted declaration pins below and actual terminal receipt control T12 assembly.

Only a bounded invented-input codec/framing/runtime-identity consistency profile is being assembled. The public native-member witness's A1–A15 acceptance, native source/archive intake, causal publication, history/calendar/complete-session capacity, one-genesis multi-session account continuity and any training/scoring/promotion are separate **UNIMPLEMENTED** gates. Every authority remains literal False.

## Machine-readable registry grammar and hashing

Three JSON blocks below are normative, complete literals. Their block IDs are PUBLIC_PROTOCOL_JSON, PROOF_SCHEMA_JSON and PROFILE_CLOSURE_JSON; block IDs are extraction markers, not fields silently inserted into a hashed body. Parse each entire JSON object exactly once, reject duplicate keys and missing/extra schemas or fields. Do not reconstruct an object from headings, selectively copied field-name lists or returned native values.

The registry grammar is intentionally declarative, not an executable validator or installed native ABI service:

- A schema `kind=record` lists every ordered `[field_name,type_reference]`; the canonical body is an object with exactly those fields. A public `runtime_type=exact_registered_frozen_slotted_record` is the future explicit record boundary, not a claim that native SDK objects or JSON dictionaries already are those records. Proof objects are exact dictionaries/JSON records under their named schemas; native source classes are checked before explicit projection.
- `kind=tuple` is a complete ordered collection projected to a JSON array. `fixed_tuple` preserves every item and disallows extras. `literal` and `enum` require exact type and value/row. `union` selects one stated complete variant only. A reference beginning `public.` resolves into PUBLIC_PROTOCOL_JSON.schemas; an unqualified reference in PROOF_SCHEMA_JSON resolves into its own schemas.
- Integer data are exact Python ints, never bool, subclass, float, wrapped/clamped or decimal strings. Schema-descriptor endpoints named minimum_decimal/maximum_decimal are exact base-ten integer **strings in the descriptor** so an intermediate JSON consumer cannot round a u64/i64 endpoint. They do not change the actual data representation into strings or permit floating comparison. No arbitrary coercion, generic native-object str/int conversion, reflection, callback or inferred field omission is allowed.
- Text/hex/enum/date/count/padding rules and each cross-field rule are part of the literal protocol. A schema rule cannot be weakened by a later serializer. Literal allowed_rows are indivisible rows, not independently mixable columns. Unknown schema kinds, type references or fields refuse rather than default.
- H(body) = SHA256 of UTF-8 canonical JSON: sorted keys, separators comma/colon, ensure_ascii=True, allow_nan=False, tuples projected to complete ordered lists, no floats. Native date/enum observations use the exact tagged bodies in the registry. No pretty prices/timestamps/datetime formatter defines an oracle.
- RAW_SHA(bytes) is SHA256 of the exact entire immutable byte string or named original span, not of JSON hex/base64/hash text. Lossless CompleteOctets is a proof-only compression: expand its entire byte string before raw hashing/comparison. Its unique form is repeat_byte for every nonempty uniform string; otherwise hex, including empty strings. It is not truncation, sampling, thinning or a digest-only replacement.

Exact namespaces and exclusions:

| Identity | Complete body or bytes |
| --- | --- |
| protocol_sha256 | H of the **entire PUBLIC_PROTOCOL_JSON object**; no self-hash field |
| context_sha256 | H of all five Context fields |
| profile_sha256 | H of the entire 16-field profile_body assembled by PROFILE_CLOSURE_JSON; no own profile hash |
| runtime_manifest_sha256 | H of the entire four-field RuntimeManifest |
| member/compressed SHA | RAW_SHA of exact supplied Zstd member-content bytes, not ZIP/container/layer-compressed bytes |
| decompressed SHA | RAW_SHA of complete concatenated DBN bytes |
| projection/metadata SHA | H of complete logical projection; metadata SHA equals the first Metadata projection SHA, not original header-byte SHA |
| wire SHA | RAW_SHA of original decompressed-byte span |
| wire_fields SHA | H of complete independently interpreted original wire body |
| frame span SHA | RAW_SHA in its separately named compressed/decompressed coordinate space |
| framing report SHA | H of complete named report excluding ONLY its own report_sha256 |
| evidence SHA | H of complete MemberDecodeEvidence excluding ONLY evidence_sha256 |
| receipt identity | H of the complete nine-field receipt body, recorded externally with no receipt wrapper; never inserted into deterministic profile_body |

There is no own-digest cycle. The protocol body contains schema strings naming profile_sha256/evidence_sha256, not actual self-digests. The profile contains the complete protocol body and RuntimeManifest plus its digest; it does not contain its own profile digest. Full attempt/report/registration hashes can transitively contain machine paths, PIDs, times, error wording and ASLR observations: they belong only to the separate qualification receipt, not the deterministic core. This annex's own raw Markdown hash is a preservation receipt field, never a hidden profile input.

## Full public protocol body — PUBLIC_PROTOCOL_JSON

This is the full proposed public protocol registry, including exact native-dependent representations, fixed RuntimeManifest rows, decoder choices, limits and all-false authorities. It is an explicit interface decision backed by the qualified narrow proof, not a statement that these five public APIs exist.

```json
{
  "version": "native_member_decode_evidence_v1",
  "scope": "invented_complete_in_memory_native_member_consistency_only",
  "status": "complete_member_consistency_not_source_authentication",
  "context_fields": [
    "profile_id",
    "member_compression",
    "input_version",
    "upgrade_policy",
    "expected_ts_out"
  ],
  "metadata_fields": [
    "version",
    "dataset",
    "schema",
    "start",
    "end_observed",
    "limit_observed",
    "stype_in",
    "stype_out",
    "ts_out",
    "symbol_cstr_len",
    "symbols",
    "partial",
    "not_found",
    "mappings"
  ],
  "mbo_fields": [
    "rtype",
    "publisher_id",
    "instrument_id",
    "ts_event",
    "order_id",
    "price",
    "size",
    "action",
    "side",
    "ts_recv",
    "flags",
    "channel_id",
    "ts_in_delta",
    "sequence",
    "ts_out_observed",
    "record_size_observed",
    "ts_index_observed"
  ],
  "occurrence_fields": [
    "decoded_position",
    "kind",
    "wire_span_ordinal",
    "projection",
    "projection_sha256"
  ],
  "zstd_framing_fields": [
    "compressed_bytes",
    "compressed_sha256",
    "decompressed_bytes",
    "decompressed_sha256",
    "frames",
    "report_sha256"
  ],
  "dbn_framing_fields": [
    "decompressed_bytes",
    "decompressed_sha256",
    "spans",
    "report_sha256"
  ],
  "terminal_fields": [
    "compressed_bytes",
    "compressed_sha256",
    "decompressed_bytes",
    "decompressed_sha256",
    "frame_count",
    "decoded_positions",
    "metadata_count",
    "mbo_count",
    "dbn_remaining_buffer_bytes",
    "zstd_framing_sha256",
    "dbn_framing_sha256",
    "framing_status",
    "zstd_status"
  ],
  "evidence_fields": [
    "status",
    "protocol_sha256",
    "profile_sha256",
    "runtime_manifest",
    "runtime_manifest_sha256",
    "context_sha256",
    "member_sha256",
    "metadata_sha256",
    "occurrences",
    "zstd_framing",
    "dbn_framing",
    "terminal",
    "authorities",
    "evidence_sha256"
  ],
  "authority_names": [
    "source_authenticated",
    "collection_receipt_authenticated",
    "native_runtime_authenticated",
    "native_abi_authenticated",
    "native_wire_authenticated",
    "native_header_authenticated",
    "native_eof_authenticated",
    "feed_authenticated",
    "calendar_authenticated",
    "historical_read_authorized",
    "historical_validation_authorized",
    "book_acceptance_authorized",
    "event_acceptance_authorized",
    "feature_acceptance_authorized",
    "account_authorized",
    "funding_authorized",
    "receipt_authorized",
    "cash_authorized",
    "margin_authorized",
    "risk_authorized",
    "storage_authorized",
    "resume_authorized",
    "execution_authorized",
    "trading_authorized",
    "training_authorized",
    "scoring_authorized",
    "independent_validation_authorized",
    "promotion_authorized"
  ],
  "limits": {
    "compressed_bytes_min": 1,
    "compressed_bytes_max": 262144,
    "decompressed_bytes_max": 1048576,
    "frame_window_bytes_max": 1048576,
    "frame_count_min": 1,
    "frame_count_max": 16,
    "decoded_positions_min": 2,
    "decoded_positions_max": 128,
    "metadata_bytes_min": 128,
    "metadata_bytes_max": 65536,
    "symbols_max": 16,
    "partial_max": 16,
    "not_found_max": 16,
    "mapping_groups_max": 16,
    "mapping_intervals_max": 32,
    "metadata_text_utf8_bytes_max": 128,
    "context_canonical_bytes_max": 65536,
    "evidence_body_canonical_bytes_max": 1048576
  },
  "canonicalization": {
    "algorithm": "SHA256",
    "text_encoding": "UTF-8",
    "json_sorted_keys": true,
    "json_separators": [
      ",",
      ":"
    ],
    "ensure_ascii": true,
    "allow_nan": false,
    "tuple_projection": "ordered_lists",
    "extra_fields": "refuse",
    "exact_types": true,
    "floats_allowed": false,
    "own_digest_exclusion": "only_the_named_own_digest"
  },
  "decoder_options": {
    "dbn": {
      "has_metadata": true,
      "input_version": null,
      "upgrade_policy": "AS_IS",
      "compression": "NONE",
      "ts_out_constructor": false
    },
    "zstd": {
      "backend": "cext",
      "format": "FORMAT_ZSTD1",
      "dict_data": null,
      "max_window_size_argument": 1048576,
      "read_across_frames": false,
      "read_size": 65536,
      "output_read_quantum": 65536,
      "terminal_read_across_frames": false,
      "terminal_allow_extra_data": false,
      "terminal_allocation": "exact_positive_frame_output_length"
    }
  },
  "schemas": {
    "U8": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "255"
    },
    "U16": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "65535"
    },
    "U32": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "4294967295"
    },
    "U64": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "18446744073709551615"
    },
    "I32": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "-2147483648",
      "maximum_decimal": "2147483647"
    },
    "I64": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "-9223372036854775808",
      "maximum_decimal": "9223372036854775807"
    },
    "NonzeroEnd": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "18446744073709551614"
    },
    "NonzeroLimit": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "18446744073709551615"
    },
    "Offset": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "1048576"
    },
    "CompressedOffset": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "262144"
    },
    "FrameOrdinal": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "16"
    },
    "DecodedOrdinal": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "128"
    },
    "FrameCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "16"
    },
    "DecodedCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "2",
      "maximum_decimal": "128"
    },
    "MboCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "127"
    },
    "ListCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "16"
    },
    "IntervalCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "32"
    },
    "PaddingCount": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "7"
    },
    "CompressedBytes": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "262144"
    },
    "DecompressedBytes": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "1048576"
    },
    "MetadataBodyLength": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "120",
      "maximum_decimal": "65528"
    },
    "Year": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "9999"
    },
    "Month": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "12"
    },
    "Day": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "31"
    },
    "Bool": {
      "kind": "bool",
      "exact_type": true
    },
    "Null": {
      "kind": "literal",
      "exact_type": "NoneType",
      "value": null
    },
    "False": {
      "kind": "literal",
      "exact_type": "bool",
      "value": false
    },
    "Zero": {
      "kind": "literal",
      "exact_type": "int",
      "value": 0
    },
    "One": {
      "kind": "literal",
      "exact_type": "int",
      "value": 1
    },
    "Three": {
      "kind": "literal",
      "exact_type": "int",
      "value": 3
    },
    "Sixteen": {
      "kind": "literal",
      "exact_type": "int",
      "value": 16
    },
    "SeventyOne": {
      "kind": "literal",
      "exact_type": "int",
      "value": 71
    },
    "Sha256": {
      "kind": "str",
      "exact_type": true,
      "ascii": true,
      "pattern": "^[0-9a-f]{64}$"
    },
    "HexOctets": {
      "kind": "str",
      "exact_type": true,
      "ascii": true,
      "pattern": "^(?:[0-9a-f]{2})*$"
    },
    "HexMagic": {
      "kind": "literal",
      "exact_type": "str",
      "value": "44424e"
    },
    "MetadataText": {
      "kind": "str",
      "exact_type": true,
      "encoding": "UTF-8",
      "encoding_errors": "strict",
      "maximum_encoded_bytes": 128,
      "nul": "forbidden"
    },
    "DatasetText": {
      "kind": "str",
      "exact_type": true,
      "encoding": "UTF-8",
      "encoding_errors": "strict",
      "maximum_encoded_bytes": 15,
      "nul": "forbidden"
    },
    "SymbolText": {
      "kind": "str",
      "exact_type": true,
      "encoding": "UTF-8",
      "encoding_errors": "strict",
      "maximum_encoded_bytes": 70,
      "nul": "forbidden"
    },
    "ProfileId": {
      "kind": "literal",
      "exact_type": "str",
      "value": "dbn_v3_asis_zstd_cext_invented_20261012_v1"
    },
    "CompressionName": {
      "kind": "literal",
      "exact_type": "str",
      "value": "ZSTD_CONCAT"
    },
    "UpgradeName": {
      "kind": "literal",
      "exact_type": "str",
      "value": "AS_IS"
    },
    "EvidenceStatus": {
      "kind": "literal",
      "exact_type": "str",
      "value": "complete_member_consistency_not_source_authentication"
    },
    "FramingStatus": {
      "kind": "literal",
      "exact_type": "str",
      "value": "complete_independent_v3_mbo_framing"
    },
    "ZstdStatus": {
      "kind": "literal",
      "exact_type": "str",
      "value": "complete_nonempty_frames_native_terminal_equality"
    },
    "Kind": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "Metadata",
        "MBO"
      ]
    },
    "NullableEnd": {
      "kind": "union",
      "alternatives": [
        "Null",
        "NonzeroEnd"
      ],
      "extra_variants": "refuse"
    },
    "NullableLimit": {
      "kind": "union",
      "alternatives": [
        "Null",
        "NonzeroLimit"
      ],
      "extra_variants": "refuse"
    },
    "EnumKind": {
      "kind": "literal",
      "exact_type": "str",
      "value": "native_enum"
    },
    "EnumClass": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "Schema",
        "RType",
        "SType",
        "Action",
        "Side"
      ]
    },
    "EnumName": {
      "kind": "str",
      "exact_type": true,
      "ascii": true,
      "maximum_encoded_bytes": 32
    },
    "EnumText": {
      "kind": "str",
      "exact_type": true,
      "ascii": true,
      "maximum_encoded_bytes": 32
    },
    "SchemaMbo": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "EnumKind"
        ],
        [
          "class_name",
          "EnumClass"
        ],
        [
          "name",
          "EnumName"
        ],
        [
          "code",
          "U16"
        ],
        [
          "text",
          "EnumText"
        ]
      ],
      "extra_fields": "refuse",
      "fixed_values": {
        "kind": "native_enum",
        "class_name": "Schema"
      },
      "allowed_rows": [
        [
          "MBO",
          0,
          "mbo"
        ]
      ],
      "row_fields": [
        "name",
        "code",
        "text"
      ],
      "rules": [
        "name/code/text must match one complete allowed row; no independent mix-and-match",
        "native extraction validates the exact native class before reading name/index/text"
      ]
    },
    "RtypeMbo": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "EnumKind"
        ],
        [
          "class_name",
          "EnumClass"
        ],
        [
          "name",
          "EnumName"
        ],
        [
          "code",
          "U16"
        ],
        [
          "text",
          "EnumText"
        ]
      ],
      "extra_fields": "refuse",
      "fixed_values": {
        "kind": "native_enum",
        "class_name": "RType"
      },
      "allowed_rows": [
        [
          "MBO",
          160,
          "mbo"
        ]
      ],
      "row_fields": [
        "name",
        "code",
        "text"
      ],
      "rules": [
        "name/code/text must match one complete allowed row; no independent mix-and-match",
        "native extraction validates the exact native class before reading name/index/text"
      ]
    },
    "SType": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "EnumKind"
        ],
        [
          "class_name",
          "EnumClass"
        ],
        [
          "name",
          "EnumName"
        ],
        [
          "code",
          "U16"
        ],
        [
          "text",
          "EnumText"
        ]
      ],
      "extra_fields": "refuse",
      "fixed_values": {
        "kind": "native_enum",
        "class_name": "SType"
      },
      "allowed_rows": [
        [
          "INSTRUMENT_ID",
          0,
          "instrument_id"
        ],
        [
          "RAW_SYMBOL",
          1,
          "raw_symbol"
        ],
        [
          "SMART",
          2,
          "smart"
        ],
        [
          "CONTINUOUS",
          3,
          "continuous"
        ],
        [
          "PARENT",
          4,
          "parent"
        ],
        [
          "NASDAQ_SYMBOL",
          5,
          "nasdaq_symbol"
        ],
        [
          "CMS_SYMBOL",
          6,
          "cms_symbol"
        ],
        [
          "ISIN",
          7,
          "isin"
        ],
        [
          "US_CODE",
          8,
          "us_code"
        ],
        [
          "BBG_COMP_ID",
          9,
          "bbg_comp_id"
        ],
        [
          "BBG_COMP_TICKER",
          10,
          "bbg_comp_ticker"
        ],
        [
          "FIGI",
          11,
          "figi"
        ],
        [
          "FIGI_TICKER",
          12,
          "figi_ticker"
        ],
        [
          "LISTING_ID",
          13,
          "listing_id"
        ],
        [
          "ISSUER_ID",
          14,
          "issuer_id"
        ],
        [
          "SECURITY_ID",
          15,
          "security_id"
        ]
      ],
      "row_fields": [
        "name",
        "code",
        "text"
      ],
      "rules": [
        "name/code/text must match one complete allowed row; no independent mix-and-match",
        "native extraction validates the exact native class before reading name/index/text"
      ]
    },
    "Action": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "EnumKind"
        ],
        [
          "class_name",
          "EnumClass"
        ],
        [
          "name",
          "EnumName"
        ],
        [
          "code",
          "U16"
        ],
        [
          "text",
          "EnumText"
        ]
      ],
      "extra_fields": "refuse",
      "fixed_values": {
        "kind": "native_enum",
        "class_name": "Action"
      },
      "allowed_rows": [
        [
          "MODIFY",
          77,
          "M"
        ],
        [
          "TRADE",
          84,
          "T"
        ],
        [
          "FILL",
          70,
          "F"
        ],
        [
          "CANCEL",
          67,
          "C"
        ],
        [
          "ADD",
          65,
          "A"
        ],
        [
          "CLEAR",
          82,
          "R"
        ],
        [
          "NONE",
          78,
          "N"
        ]
      ],
      "row_fields": [
        "name",
        "code",
        "text"
      ],
      "rules": [
        "name/code/text must match one complete allowed row; no independent mix-and-match",
        "native extraction validates the exact native class before reading name/index/text"
      ]
    },
    "Side": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "EnumKind"
        ],
        [
          "class_name",
          "EnumClass"
        ],
        [
          "name",
          "EnumName"
        ],
        [
          "code",
          "U16"
        ],
        [
          "text",
          "EnumText"
        ]
      ],
      "extra_fields": "refuse",
      "fixed_values": {
        "kind": "native_enum",
        "class_name": "Side"
      },
      "allowed_rows": [
        [
          "ASK",
          65,
          "A"
        ],
        [
          "BID",
          66,
          "B"
        ],
        [
          "NONE",
          78,
          "N"
        ]
      ],
      "row_fields": [
        "name",
        "code",
        "text"
      ],
      "rules": [
        "name/code/text must match one complete allowed row; no independent mix-and-match",
        "native extraction validates the exact native class before reading name/index/text"
      ]
    },
    "StringKind": {
      "kind": "literal",
      "exact_type": "str",
      "value": "str"
    },
    "ByteCharacter": {
      "kind": "str",
      "exact_type": true,
      "minimum_characters": 1,
      "maximum_characters": 1,
      "minimum_codepoint": 0,
      "maximum_codepoint": 255
    },
    "UnknownChar": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "StringKind"
        ],
        [
          "value",
          "ByteCharacter"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "value code point equals original u8 for a byte not in the corresponding known Action or Side domain"
      ]
    },
    "ActionObservation": {
      "kind": "union",
      "alternatives": [
        "Action",
        "UnknownChar"
      ],
      "extra_variants": "refuse"
    },
    "SideObservation": {
      "kind": "union",
      "alternatives": [
        "Side",
        "UnknownChar"
      ],
      "extra_variants": "refuse"
    },
    "NullableSType": {
      "kind": "union",
      "alternatives": [
        "Null",
        "SType"
      ],
      "extra_variants": "refuse"
    },
    "DateKind": {
      "kind": "literal",
      "exact_type": "str",
      "value": "python_date"
    },
    "PythonDate": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "DateKind"
        ],
        [
          "year",
          "Year"
        ],
        [
          "month",
          "Month"
        ],
        [
          "day",
          "Day"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "the triple is a valid Gregorian date and the native source object is exact datetime.date, not datetime or a subclass"
      ]
    },
    "WireDate": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "10101",
      "maximum_decimal": "99991231"
    },
    "WireMappingInterval": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "start_date",
          "WireDate"
        ],
        [
          "end_date",
          "WireDate"
        ],
        [
          "symbol",
          "SymbolText"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "each raw YYYYMMDD decomposes to a valid PythonDate; retain original integer; no market/calendar or interval-order admission"
      ]
    },
    "MappingInterval": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "start_date",
          "PythonDate"
        ],
        [
          "end_date",
          "PythonDate"
        ],
        [
          "symbol",
          "SymbolText"
        ]
      ],
      "extra_fields": "refuse",
      "rules": []
    },
    "MappingIntervals": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "MappingInterval",
      "minimum_items": 0,
      "maximum_items": 32,
      "rules": []
    },
    "WireMappingIntervals": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "WireMappingInterval",
      "minimum_items": 0,
      "maximum_items": 32,
      "rules": []
    },
    "MappingGroup": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "raw_symbol",
          "SymbolText"
        ],
        [
          "intervals",
          "MappingIntervals"
        ]
      ],
      "extra_fields": "refuse",
      "rules": []
    },
    "WireMappingGroup": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "raw_symbol",
          "SymbolText"
        ],
        [
          "interval_count",
          "IntervalCount"
        ],
        [
          "intervals",
          "WireMappingIntervals"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "interval_count equals complete intervals length"
      ]
    },
    "MappingGroups": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "MappingGroup",
      "minimum_items": 0,
      "maximum_items": 16,
      "rules": [
        "groups sorted by exact raw_symbol; keys unique; total interval occurrences at most32"
      ]
    },
    "WireMappingGroups": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "WireMappingGroup",
      "minimum_items": 0,
      "maximum_items": 16,
      "rules": [
        "original order retained; duplicate raw_symbol keys refuse; total intervals at most32"
      ]
    },
    "Symbols": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "SymbolText",
      "minimum_items": 0,
      "maximum_items": 16,
      "rules": [
        "preserve every occurrence and duplicate in source order"
      ]
    },
    "STypeWireIn": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15,
        255
      ]
    },
    "STypeWireOut": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        0,
        1,
        2,
        3,
        4,
        5,
        6,
        7,
        8,
        9,
        10,
        11,
        12,
        13,
        14,
        15
      ]
    },
    "ModeByte": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        0,
        1
      ]
    },
    "ReservedZeros": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "Zero",
      "minimum_items": 53,
      "maximum_items": 53,
      "rules": []
    },
    "AlignmentZeros": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "Zero",
      "minimum_items": 0,
      "maximum_items": 7,
      "rules": []
    },
    "MetadataWireBody": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "magic_hex",
          "HexMagic"
        ],
        [
          "version",
          "Three"
        ],
        [
          "length_body",
          "MetadataBodyLength"
        ],
        [
          "dataset",
          "DatasetText"
        ],
        [
          "dataset_cstr_bytes",
          "Sixteen"
        ],
        [
          "schema",
          "Zero"
        ],
        [
          "start",
          "U64"
        ],
        [
          "end",
          "U64"
        ],
        [
          "limit",
          "U64"
        ],
        [
          "stype_in",
          "STypeWireIn"
        ],
        [
          "stype_out",
          "STypeWireOut"
        ],
        [
          "ts_out",
          "ModeByte"
        ],
        [
          "symbol_cstr_len",
          "SeventyOne"
        ],
        [
          "reserved_bytes",
          "ReservedZeros"
        ],
        [
          "schema_definition_length",
          "Zero"
        ],
        [
          "symbols_count",
          "ListCount"
        ],
        [
          "symbols",
          "Symbols"
        ],
        [
          "partial_count",
          "ListCount"
        ],
        [
          "partial",
          "Symbols"
        ],
        [
          "not_found_count",
          "ListCount"
        ],
        [
          "not_found",
          "Symbols"
        ],
        [
          "mappings_count",
          "ListCount"
        ],
        [
          "mappings",
          "WireMappingGroups"
        ],
        [
          "alignment_padding_bytes",
          "AlignmentZeros"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "magic_hex is hex text; all counts/lengths are integers; reserved and alignment are ordered integer-zero tuples, not hex substitutes",
        "each list/group count equals full tuple length",
        "length_body divisible by8 and plus8 equals exact complete header span",
        "C strings have the registered width, strict UTF-8, first NUL terminator and all-zero remainder",
        "alignment zeros have exactly the count needed for the next eight-byte boundary; no unexplained header tail"
      ]
    },
    "MetadataProjection": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "version",
          "Three"
        ],
        [
          "dataset",
          "DatasetText"
        ],
        [
          "schema",
          "SchemaMbo"
        ],
        [
          "start",
          "U64"
        ],
        [
          "end_observed",
          "NullableEnd"
        ],
        [
          "limit_observed",
          "NullableLimit"
        ],
        [
          "stype_in",
          "NullableSType"
        ],
        [
          "stype_out",
          "SType"
        ],
        [
          "ts_out",
          "Bool"
        ],
        [
          "symbol_cstr_len",
          "SeventyOne"
        ],
        [
          "symbols",
          "Symbols"
        ],
        [
          "partial",
          "Symbols"
        ],
        [
          "not_found",
          "Symbols"
        ],
        [
          "mappings",
          "MappingGroups"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "raw end0 or18446744073709551615 translates to None; other raw end retains exact positive value",
        "raw limit0 translates to None; other raw limit retains exact positive value",
        "raw stype_in255 translates to None; other codes use exact SType row",
        "raw ts_out0/1 translates to False/True; must equal Context expected_ts_out",
        "schema is exactly MBO; no native nullable-schema admission in this narrow profile",
        "getter mapping groups sorted only in logical body; original wire order remains in MetadataWireBody"
      ]
    },
    "MboLength": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        14,
        16
      ]
    },
    "MboRtypeWire": {
      "kind": "literal",
      "exact_type": "int",
      "value": 160
    },
    "NullableU64": {
      "kind": "union",
      "alternatives": [
        "Null",
        "U64"
      ],
      "extra_variants": "refuse"
    },
    "MboWireBody": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "length_words",
          "MboLength"
        ],
        [
          "rtype",
          "MboRtypeWire"
        ],
        [
          "publisher_id",
          "U16"
        ],
        [
          "instrument_id",
          "U32"
        ],
        [
          "ts_event",
          "U64"
        ],
        [
          "order_id",
          "U64"
        ],
        [
          "price",
          "I64"
        ],
        [
          "size",
          "U32"
        ],
        [
          "flags",
          "U8"
        ],
        [
          "channel_id",
          "U8"
        ],
        [
          "action",
          "U8"
        ],
        [
          "side",
          "U8"
        ],
        [
          "ts_recv",
          "U64"
        ],
        [
          "ts_in_delta",
          "I32"
        ],
        [
          "sequence",
          "U32"
        ],
        [
          "ts_out",
          "NullableU64"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "Metadata mode0 requires length_words14/56 original bytes and wire ts_outNone",
        "Metadata mode1 requires length_words16/64 original bytes and exact appended u64",
        "length multiplier4 is independently source-defined, never inferred from native record_size"
      ]
    },
    "RecordSize": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        56,
        64
      ]
    },
    "MboObservation": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "rtype",
          "RtypeMbo"
        ],
        [
          "publisher_id",
          "U16"
        ],
        [
          "instrument_id",
          "U32"
        ],
        [
          "ts_event",
          "U64"
        ],
        [
          "order_id",
          "U64"
        ],
        [
          "price",
          "I64"
        ],
        [
          "size",
          "U32"
        ],
        [
          "action",
          "ActionObservation"
        ],
        [
          "side",
          "SideObservation"
        ],
        [
          "ts_recv",
          "U64"
        ],
        [
          "flags",
          "U8"
        ],
        [
          "channel_id",
          "U8"
        ],
        [
          "ts_in_delta",
          "I32"
        ],
        [
          "sequence",
          "U32"
        ],
        [
          "ts_out_observed",
          "U64"
        ],
        [
          "record_size_observed",
          "RecordSize"
        ],
        [
          "ts_index_observed",
          "U64"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "wire absence maps to native ts_out_observed18446744073709551615, not None",
        "present ts_out is unchanged",
        "record_size_observed equals independently framed56/64 byte record; ts_index_observed equals ts_recv and never sorts or defines an offset",
        "known enum or unknown-character value must match the original raw u8"
      ]
    },
    "Context": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "profile_id",
          "ProfileId"
        ],
        [
          "member_compression",
          "CompressionName"
        ],
        [
          "input_version",
          "Three"
        ],
        [
          "upgrade_policy",
          "UpgradeName"
        ],
        [
          "expected_ts_out",
          "Bool"
        ]
      ],
      "extra_fields": "refuse",
      "rules": []
    },
    "Projection": {
      "kind": "union",
      "alternatives": [
        "MetadataProjection",
        "MboObservation"
      ],
      "extra_variants": "refuse"
    },
    "DecodedOccurrence": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "decoded_position",
          "DecodedOrdinal"
        ],
        [
          "kind",
          "Kind"
        ],
        [
          "wire_span_ordinal",
          "DecodedOrdinal"
        ],
        [
          "projection",
          "Projection"
        ],
        [
          "projection_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "kind chooses the corresponding exact projection schema",
        "projection_sha256 is H of the complete projection body"
      ]
    },
    "Occurrences": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "DecodedOccurrence",
      "minimum_items": 2,
      "maximum_items": 128,
      "rules": [
        "ordinal positions contiguous1..N; exactly one first Metadata and every subsequent MBO retained",
        "wire_span association is bijective, same kind/order; no successful-book ordinal or filtering"
      ]
    },
    "FrameSpan": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "frame_ordinal",
          "FrameOrdinal"
        ],
        [
          "compressed_start",
          "CompressedOffset"
        ],
        [
          "compressed_end",
          "CompressedOffset"
        ],
        [
          "decompressed_start",
          "Offset"
        ],
        [
          "decompressed_end",
          "Offset"
        ],
        [
          "compressed_span_sha256",
          "Sha256"
        ],
        [
          "decompressed_span_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "start<end in both spaces; per-frame decompressed output nonempty",
        "raw slice hashes cover exactly those separately named original coordinate spaces"
      ]
    },
    "Frames": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "FrameSpan",
      "minimum_items": 1,
      "maximum_items": 16,
      "rules": [
        "ordinal contiguous1..N and complete compressed/decompressed coverage from0toeachfull length, no gaps/overlap/tail"
      ]
    },
    "ZstdFramingReport": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "compressed_bytes",
          "CompressedBytes"
        ],
        [
          "compressed_sha256",
          "Sha256"
        ],
        [
          "decompressed_bytes",
          "DecompressedBytes"
        ],
        [
          "decompressed_sha256",
          "Sha256"
        ],
        [
          "frames",
          "Frames"
        ],
        [
          "report_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "raw complete hashes match original byte strings",
        "report_sha256 is H of this complete body excluding only report_sha256"
      ]
    },
    "WireBody": {
      "kind": "union",
      "alternatives": [
        "MetadataWireBody",
        "MboWireBody"
      ],
      "extra_variants": "refuse"
    },
    "WireSpan": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "wire_span_ordinal",
          "DecodedOrdinal"
        ],
        [
          "kind",
          "Kind"
        ],
        [
          "decompressed_start",
          "Offset"
        ],
        [
          "decompressed_end",
          "Offset"
        ],
        [
          "wire_sha256",
          "Sha256"
        ],
        [
          "wire_fields",
          "WireBody"
        ],
        [
          "wire_fields_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "kind selects matching complete wire body",
        "wire_sha256 is raw exact decompressed byte-span hash; wire_fields_sha256 is H of complete named wire_fields body",
        "span bounds are independently framed original bytes, not yield/chunk positions/native record_size"
      ]
    },
    "WireSpans": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "WireSpan",
      "minimum_items": 2,
      "maximum_items": 128,
      "rules": [
        "contiguous ordinal1..N, complete decompressed coverage, one first Metadata, remaining MBOs, no gaps/overlap/tail"
      ]
    },
    "DbnFramingReport": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "decompressed_bytes",
          "DecompressedBytes"
        ],
        [
          "decompressed_sha256",
          "Sha256"
        ],
        [
          "spans",
          "WireSpans"
        ],
        [
          "report_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "report_sha256 is H of complete body excluding only report_sha256",
        "all raw/logical translations and occurrence/span/count agreement reconcile"
      ]
    },
    "TerminalEvidence": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "compressed_bytes",
          "CompressedBytes"
        ],
        [
          "compressed_sha256",
          "Sha256"
        ],
        [
          "decompressed_bytes",
          "DecompressedBytes"
        ],
        [
          "decompressed_sha256",
          "Sha256"
        ],
        [
          "frame_count",
          "FrameCount"
        ],
        [
          "decoded_positions",
          "DecodedCount"
        ],
        [
          "metadata_count",
          "One"
        ],
        [
          "mbo_count",
          "MboCount"
        ],
        [
          "dbn_remaining_buffer_bytes",
          "Zero"
        ],
        [
          "zstd_framing_sha256",
          "Sha256"
        ],
        [
          "dbn_framing_sha256",
          "Sha256"
        ],
        [
          "framing_status",
          "FramingStatus"
        ],
        [
          "zstd_status",
          "ZstdStatus"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "counts/lengths/raw hashes equal complete reports; mbo_count=decoded_positions-1",
        "empty native buffer is necessary but not sufficient; complete independent framing and native terminal equality are also required",
        "all terminal/member/total facts remain outside any earlier causal publication identity"
      ]
    },
    "AuthorityName": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "source_authenticated",
        "collection_receipt_authenticated",
        "native_runtime_authenticated",
        "native_abi_authenticated",
        "native_wire_authenticated",
        "native_header_authenticated",
        "native_eof_authenticated",
        "feed_authenticated",
        "calendar_authenticated",
        "historical_read_authorized",
        "historical_validation_authorized",
        "book_acceptance_authorized",
        "event_acceptance_authorized",
        "feature_acceptance_authorized",
        "account_authorized",
        "funding_authorized",
        "receipt_authorized",
        "cash_authorized",
        "margin_authorized",
        "risk_authorized",
        "storage_authorized",
        "resume_authorized",
        "execution_authorized",
        "trading_authorized",
        "training_authorized",
        "scoring_authorized",
        "independent_validation_authorized",
        "promotion_authorized"
      ]
    },
    "AuthorityEntry": {
      "kind": "fixed_tuple",
      "exact_type": true,
      "canonical_type": "array",
      "items": [
        "AuthorityName",
        "False"
      ],
      "extra_items": "refuse"
    },
    "Authorities": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "AuthorityEntry",
      "minimum_items": 28,
      "maximum_items": 28,
      "rules": [
        "names occur once in the exact protocol authority_names order; every second value literalFalse"
      ]
    },
    "RuntimeSchema": {
      "kind": "literal",
      "exact_type": "str",
      "value": "native_profile_runtime_manifest_v1"
    },
    "Implementation": {
      "kind": "literal",
      "exact_type": "str",
      "value": "cpython"
    },
    "PythonVersion": {
      "kind": "fixed_tuple",
      "exact_type": true,
      "canonical_type": "array",
      "literal_items": [
        3,
        12,
        10
      ],
      "item_exact_type": "int",
      "extra_items": "refuse"
    },
    "Interpreter": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "implementation",
          "Implementation"
        ],
        [
          "version",
          "PythonVersion"
        ],
        [
          "executable_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "executable_sha256 equals the fixed registered python.exe artifact hash"
      ],
      "fixed_values": {
        "executable_sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
        "implementation": "cpython",
        "version": [
          3,
          12,
          10
        ]
      }
    },
    "PackageName": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "databento-dbn",
        "zstandard"
      ]
    },
    "PackageVersion": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "0.70.0",
        "0.25.0"
      ]
    },
    "Package": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "name",
          "PackageName"
        ],
        [
          "version",
          "PackageVersion"
        ],
        [
          "metadata_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "databento-dbn/0.70.0 and zstandard/0.25.0 pair exactly; metadata SHA equals their fixed complete registered METADATA artifact"
      ],
      "allowed_rows": [
        [
          "databento-dbn",
          "0.70.0",
          "9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543"
        ],
        [
          "zstandard",
          "0.25.0",
          "bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c"
        ]
      ],
      "row_fields": [
        "name",
        "version",
        "metadata_sha256"
      ]
    },
    "Packages": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "Package",
      "minimum_items": 2,
      "maximum_items": 2,
      "rules": [
        "sorted by exact name; required two entries once, no extras"
      ]
    },
    "ArtifactId": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "python.exe",
        "python312.dll",
        "pyvenv.cfg",
        "dbn_init",
        "dbn_metadata",
        "dbn_v1",
        "dbn_v2",
        "dbn_v3",
        "dbn_extension",
        "dbn_package_metadata",
        "zstd_init",
        "zstd_extension",
        "zstd_package_metadata"
      ]
    },
    "ArtifactKind": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "python_executable",
        "python_runtime_library",
        "venv_configuration",
        "python_module_source",
        "native_extension",
        "distribution_metadata"
      ]
    },
    "ArtifactBytes": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "67108864"
    },
    "Artifact": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "logical_id",
          "ArtifactId"
        ],
        [
          "kind",
          "ArtifactKind"
        ],
        [
          "raw_bytes",
          "ArtifactBytes"
        ],
        [
          "raw_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "id/kind/byte-count/hash equal the one complete fixed recognized artifact row; no path field"
      ],
      "allowed_rows": [
        [
          "dbn_extension",
          "native_extension",
          3709952,
          "c48c57974ca83d68ae67522e6e191e3ae7fe9ae353fe78a59ab020a49cbef64a"
        ],
        [
          "dbn_init",
          "python_module_source",
          763,
          "62996cdfe11d8690d6d6d9b7973ae81add3b7864232fd5f56d74e177eee571f7"
        ],
        [
          "dbn_metadata",
          "python_module_source",
          1118,
          "a5f7b49b299e6a8a39af190805c83fb12f9346f32892cc0579235764fe24c189"
        ],
        [
          "dbn_package_metadata",
          "distribution_metadata",
          2337,
          "9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543"
        ],
        [
          "dbn_v1",
          "python_module_source",
          733,
          "71503b977417b9fb7771e32aa1af4422c22db4f3223dafa730bd000974769e30"
        ],
        [
          "dbn_v2",
          "python_module_source",
          682,
          "2cc50301be2d0043ebe80dce98baa38ea665b61302ac723db8761cae8d48cc24"
        ],
        [
          "dbn_v3",
          "python_module_source",
          647,
          "ef5410748580eadc1f0e69622f0e9eee5e23df0e0e830ef0aeecda1883765d54"
        ],
        [
          "python.exe",
          "python_executable",
          104952,
          "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
        ],
        [
          "python312.dll",
          "python_runtime_library",
          6945272,
          "9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120"
        ],
        [
          "pyvenv.cfg",
          "venv_configuration",
          325,
          "b1a1e44d494a290b40de7b4030ab3852f66b8c31ad89f4851806127f10d2c493"
        ],
        [
          "zstd_extension",
          "native_extension",
          525312,
          "2ce792041f2bf7d8a8f514f0fb5adfc7778e56e988491e6ac7f3438c2e8cb3d3"
        ],
        [
          "zstd_init",
          "python_module_source",
          7452,
          "5c229d937b3f8420234f3baac08d8abc0ade34a17bbfbbac98fcd4f9349492d6"
        ],
        [
          "zstd_package_metadata",
          "distribution_metadata",
          3339,
          "bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c"
        ]
      ],
      "row_fields": [
        "logical_id",
        "kind",
        "raw_bytes",
        "raw_sha256"
      ]
    },
    "Artifacts": {
      "kind": "tuple",
      "exact_type": true,
      "canonical_type": "array",
      "item": "Artifact",
      "minimum_items": 13,
      "maximum_items": 13,
      "rules": [
        "sorted ordinally by exact logical_id; each required row exactly once, no missing/extra"
      ]
    },
    "RuntimeManifest": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "schema",
          "RuntimeSchema"
        ],
        [
          "interpreter",
          "Interpreter"
        ],
        [
          "packages",
          "Packages"
        ],
        [
          "artifacts",
          "Artifacts"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "13 artifact identities/2 package identities are the fixed recognized set, not full DLL/import-graph/build/source authentication",
        "no PID/time/path/address/attempt diagnostic field"
      ]
    },
    "MemberDecodeEvidence": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "status",
          "EvidenceStatus"
        ],
        [
          "protocol_sha256",
          "Sha256"
        ],
        [
          "profile_sha256",
          "Sha256"
        ],
        [
          "runtime_manifest",
          "RuntimeManifest"
        ],
        [
          "runtime_manifest_sha256",
          "Sha256"
        ],
        [
          "context_sha256",
          "Sha256"
        ],
        [
          "member_sha256",
          "Sha256"
        ],
        [
          "metadata_sha256",
          "Sha256"
        ],
        [
          "occurrences",
          "Occurrences"
        ],
        [
          "zstd_framing",
          "ZstdFramingReport"
        ],
        [
          "dbn_framing",
          "DbnFramingReport"
        ],
        [
          "terminal",
          "TerminalEvidence"
        ],
        [
          "authorities",
          "Authorities"
        ],
        [
          "evidence_sha256",
          "Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "protocol/profile/runtime/context/member expected pins must all reconcile",
        "metadata_sha256 equals first occurrence complete MetadataProjection hash, not raw-header hash",
        "evidence_sha256 is H of complete body excluding only evidence_sha256",
        "no partial positive schema; all complete guards before return; submitted verification reconstructs complete fresh state"
      ]
    }
  }
}
```

## Provider interfaces and representation boundaries

The unchanged five proposed signatures remain: protocol(), protocol_sha256(), context_sha256(context, *, expected_protocol_sha256), decode_member(member_bytes, context, *, expected_protocol_sha256, expected_profile_sha256, expected_runtime_manifest_sha256, expected_member_sha256, expected_metadata_sha256), and verify(evidence, member_bytes, context, *, those same five expected pins, expected_evidence_sha256). Every expected pin is mandatory exact lowercase 64-ASCII-hex; bytes are exact immutable bytes, not paths, bytearrays, iterators, archives or supplied native objects. Context is exactly the registry's five-field body.

All five APIs are **UNIMPLEMENTED**. Full native proof does not imply that public Context/pin/shape preflight, wrapper Metadata-before-MBO read ordering, all-or-nothing positive return, complete canonical output caps or submitted fresh reconstruction are already implemented/tested. The approved phase contract remains necessary. Controlled mocks prove only wrapper seam behavior. Native import/load is itself execution; static identities before import plus contained loaded-association checks before constructors are not code-free preflight or universal authentication.

The exact native observation→public projection rename is recorded in PROFILE_CLOSURE_JSON.logical_schema. Metadata's kind discriminator is not a getter; end and limit become explicitly named end_observed/limit_observed. MBO ts_out/record_size/ts_index become ts_out_observed/record_size_observed/ts_index_observed. No raw value is normalized during this rename.

Metadata raw end=0 and U64_MAX both yield native None through distinct source branches; raw bytes retain the distinction. Raw limit0 yields None, otherwise the exact u64. Native absent MBO ts_out is U64_MAX, not None; original absent wire extension is separately None. Present native/wire ts_out remains unchanged. No widening/downcast into held signed64 payload transport occurs. UTF-8 decoder admissibility is not ASCII encoder admissibility or authentic symbol/calendar admission.

Wire Metadata dictionaries cannot erase original occurrences: complete wire group/interval order is retained; duplicate raw-symbol group keys refuse in this narrow profile even if the SDK coalesces them. Logical getter groups sort only by raw-symbol key; interval multiplicity/order remains. Complete field-span ledgers retain reserved/count/padding bytes. Native decoded_position, physical compressed member offsets, decompressed wire offsets, feed/emission batches and ZIP coordinates remain distinct; no yield position or record_size manufactures an offset.

Physical Zstd frames alone do not establish checksum/FCS/content consistency. The qualified mechanism first frames complete bytes and caps declarations/window, then bounded-read each exact frame, refuses empty frame output, and after closing the reader uses the **same decoder** one-shot with exact positive observed output allocation, read_across_frames=False and allow_extra_data=False. Full output equality and terminal behavior are required; an empty reader or native DBN buffer is not EOF. Complete final eight-byte DBN prelude can leave empty native buffer while Metadata is absent. Complete record/frame boundary prefixes can be valid different members; only held full-input identity detects substitution.

The public constructed caps remain 262,144 compressed bytes; 1,048,576 decompressed bytes and window; 1–16 frames; 2–128 complete positions; 0–16 entries per complete list/group; 32 total intervals; 65,536 Context bytes and 1,048,576 complete canonical evidence-body bytes. Equality is allowed; excess refuses all output. Public-envelope byte capacity is a normative unimplemented interface cap, not a measured full provider envelope. Existing cursor/payload/typed-adapter limits and APIs are not overridden or called.

## Complete proof schema and family registry — PROOF_SCHEMA_JSON

This registry gives exact native-free framing, full harness observations, semantic-core reductions, all 53 registered JUnit base-name families (211 full identities), all byte-input mode families and harmless predicates. Case families are evidence organization, not provider admission. A missing or extra family/node/input case blocks C4; no catch-all default silently drops it.

```json
{
  "schema": "native_profile_proof_schema_v1",
  "public_schema_registry": "native_member_decode_evidence_v1",
  "schemas": {
    "ProofText": {
      "kind": "str",
      "exact_type": true
    },
    "NullableU8": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "public.U8"
      ]
    },
    "NullableU32": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "public.U32"
      ]
    },
    "NullableU64": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "public.U64"
      ]
    },
    "Nonnegative": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "0",
      "maximum_decimal": "18446744073709551615"
    },
    "Positive": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "18446744073709551615"
    },
    "PhysicalBlockType": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        0,
        1,
        2
      ]
    },
    "ContentSizeFlag": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        0,
        1,
        2,
        3
      ]
    },
    "DictionaryIdFlag": {
      "kind": "literal",
      "exact_type": "int",
      "value": 0
    },
    "PhysicalBlock": {
      "kind": "fixed_tuple",
      "items": [
        "BlockOrdinal",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.Bool",
        "PhysicalBlockType",
        "Nonnegative",
        "public.CompressedOffset",
        "public.CompressedOffset"
      ],
      "extra_items": "refuse",
      "canonical_type": "array",
      "field_names": [
        "block_ordinal",
        "header_start",
        "header_end",
        "last",
        "block_type",
        "block_size",
        "payload_start",
        "payload_end"
      ],
      "rules": [
        "header_end-header_start=3",
        "raw/compressed payload length=block_size; RLE payload length=1",
        "block_size<=min(window_bytes,131072)",
        "the named last field (fourth tuple item) is an exact bool, not int; no reserved block type"
      ]
    },
    "PhysicalBlocks": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "PhysicalBlock",
      "minimum_items": 1,
      "maximum_items": 87380
    },
    "PhysicalFrame": {
      "kind": "fixed_tuple",
      "items": [
        "public.FrameOrdinal",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.U8",
        "NullableU8",
        "ContentSizeFlag",
        "public.Bool",
        "DictionaryIdFlag",
        "public.Bool",
        "NullableU64",
        "Nonnegative",
        "public.Null",
        "NullableU32",
        "PhysicalBlocks"
      ],
      "extra_items": "refuse",
      "canonical_type": "array",
      "field_names": [
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
        "blocks"
      ],
      "rules": [
        "physical standard magic28b52ffd only; descriptor unused/reserved bits zero",
        "single_segment True implies absent window_descriptor; otherwise exact u8 descriptor",
        "dictionary flag0; dictionary_id=None means no ID field; a flag carrying an ID field refuses even when its value is zero",
        "checksum flag chooses exact u32 checksum_value versus None",
        "physical source bytes fully covered by magic/header/blocks/optional checksum without tail",
        "content_size/window values follow pinned Zstd format; known size/window cap checks are preflight",
        "a physically complete wrong checksum or wrong FCS is not certified consistent output"
      ]
    },
    "PhysicalFrames": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "PhysicalFrame",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "Kind": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "Metadata",
        "MBO"
      ]
    },
    "WireSpanTriple": {
      "kind": "fixed_tuple",
      "items": [
        "Kind",
        "Nonnegative",
        "Nonnegative"
      ],
      "extra_items": "refuse",
      "canonical_type": "array"
    },
    "FieldSpanTriple": {
      "kind": "fixed_tuple",
      "items": [
        "ProofText",
        "Nonnegative",
        "Nonnegative"
      ],
      "extra_items": "refuse",
      "canonical_type": "array"
    },
    "FieldSpanSet": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "FieldSpanTriple",
      "minimum_items": 1,
      "maximum_items": 65536
    },
    "FieldSpanSets": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "FieldSpanSet",
      "minimum_items": 2,
      "maximum_items": 128
    },
    "DbnFramingResult": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "complete_bytes",
          "Positive"
        ],
        [
          "wire_spans",
          "WireSpanTriples"
        ],
        [
          "wire_bodies",
          "WireBodies"
        ],
        [
          "field_spans",
          "FieldSpanSets"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "wire_spans,wire_bodies,field_spans have equal complete lengths",
        "all source fields, including count/reserved/padding bytes, covered exactly once in original order; absolute offsets, no overlap/tail",
        "native-free framer shapes match the held independent literal packet, not production output copied as expected"
      ]
    },
    "WireSpanTriples": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "WireSpanTriple",
      "minimum_items": 2,
      "maximum_items": 128
    },
    "WireBodies": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "public.WireBody",
      "minimum_items": 2,
      "maximum_items": 128
    },
    "MetadataNative": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "MetadataKind"
        ],
        [
          "version",
          "public.Three"
        ],
        [
          "dataset",
          "public.DatasetText"
        ],
        [
          "schema",
          "public.SchemaMbo"
        ],
        [
          "start",
          "public.U64"
        ],
        [
          "end",
          "public.NullableEnd"
        ],
        [
          "limit",
          "public.NullableLimit"
        ],
        [
          "stype_in",
          "public.NullableSType"
        ],
        [
          "stype_out",
          "public.SType"
        ],
        [
          "ts_out",
          "public.Bool"
        ],
        [
          "symbol_cstr_len",
          "public.SeventyOne"
        ],
        [
          "symbols",
          "public.Symbols"
        ],
        [
          "partial",
          "public.Symbols"
        ],
        [
          "not_found",
          "public.Symbols"
        ],
        [
          "mappings",
          "public.MappingGroups"
        ]
      ],
      "extra_fields": "refuse"
    },
    "MetadataKind": {
      "kind": "literal",
      "value": "Metadata"
    },
    "MboKind": {
      "kind": "literal",
      "value": "MBO"
    },
    "MboNative": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "MboKind"
        ],
        [
          "rtype",
          "public.RtypeMbo"
        ],
        [
          "publisher_id",
          "public.U16"
        ],
        [
          "instrument_id",
          "public.U32"
        ],
        [
          "ts_event",
          "public.U64"
        ],
        [
          "order_id",
          "public.U64"
        ],
        [
          "price",
          "public.I64"
        ],
        [
          "size",
          "public.U32"
        ],
        [
          "action",
          "public.ActionObservation"
        ],
        [
          "side",
          "public.SideObservation"
        ],
        [
          "ts_recv",
          "public.U64"
        ],
        [
          "flags",
          "public.U8"
        ],
        [
          "channel_id",
          "public.U8"
        ],
        [
          "ts_in_delta",
          "public.I32"
        ],
        [
          "sequence",
          "public.U32"
        ],
        [
          "ts_out",
          "public.U64"
        ],
        [
          "record_size",
          "public.RecordSize"
        ],
        [
          "ts_index",
          "public.U64"
        ]
      ],
      "extra_fields": "refuse"
    },
    "NativeObservation": {
      "kind": "union",
      "alternatives": [
        "MetadataNative",
        "MboNative"
      ]
    },
    "NativeObservations": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "NativeObservation",
      "minimum_items": 0,
      "maximum_items": 128
    },
    "NullableNativeObservations": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "NativeObservations"
      ]
    },
    "FeedMode": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "complete",
        "chunks7",
        "bytewise"
      ]
    },
    "DbnPreflightCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "phase",
          "PreflightPhase"
        ],
        [
          "constructor_calls",
          "public.Zero"
        ]
      ],
      "extra_fields": "refuse"
    },
    "PreflightPhase": {
      "kind": "literal",
      "value": "independent_preflight"
    },
    "DbCallOperation": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "write_then_decode",
        "decode"
      ]
    },
    "DbnDirectCallCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "operation",
          "DbCallOperation"
        ],
        [
          "input_chunk_hex",
          "public.HexOctets"
        ],
        [
          "returned_observations",
          "NullableNativeObservations"
        ],
        [
          "error_class",
          "DbnErrorClass"
        ],
        [
          "buffer_hex",
          "public.HexOctets"
        ]
      ],
      "extra_fields": "refuse"
    },
    "DbnErrorClass": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "DbnError"
      ]
    },
    "DbnError": {
      "kind": "literal",
      "value": "DBNError"
    },
    "DbnDirectCalls": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "DbnDirectCallCore",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "DbnDirectCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "input_sha256",
          "public.Sha256"
        ],
        [
          "held_whole_input_sha256",
          "NullableSha"
        ],
        [
          "physical_complete",
          "public.Bool"
        ],
        [
          "calls",
          "DbnDirectCalls"
        ],
        [
          "visible_observations",
          "NativeObservations"
        ],
        [
          "constructor_calls",
          "public.One"
        ],
        [
          "provider_complete_result_allowed",
          "public.False"
        ]
      ],
      "extra_fields": "refuse"
    },
    "NullableSha": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "public.Sha256"
      ]
    },
    "TerminalCheck": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "frame_ordinal",
          "public.FrameOrdinal"
        ],
        [
          "max_output_size",
          "Positive"
        ],
        [
          "read_across_frames",
          "public.False"
        ],
        [
          "allow_extra_data",
          "public.False"
        ],
        [
          "output_bytes",
          "Positive"
        ],
        [
          "matches_stream_output",
          "True"
        ]
      ],
      "extra_fields": "refuse"
    },
    "True": {
      "kind": "literal",
      "value": true
    },
    "TerminalChecks": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "TerminalCheck",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "ZstdRefusalPhase": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "independent_preflight",
        "native_output_limit",
        "native_checksum"
      ]
    },
    "RefusalError": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "ValueError",
        "OutputLimitExceeded",
        "ZstdError"
      ]
    },
    "ZstdRefusalCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "phase",
          "ZstdRefusalPhase"
        ],
        [
          "constructor_calls",
          "Nonnegative"
        ],
        [
          "error_class",
          "RefusalError"
        ],
        [
          "observed_output_bytes",
          "NullableNonnegative"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ZstdEmptyCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "physical_framing",
          "PhysicalFrames"
        ],
        [
          "direct_frame_output_hex",
          "FrameOutputHexes"
        ],
        [
          "profile_error_class",
          "ValueError"
        ],
        [
          "profile_constructor_calls",
          "Positive"
        ],
        [
          "provider_complete_result_allowed",
          "public.False"
        ]
      ],
      "extra_fields": "refuse"
    },
    "FrameOutputHexes": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "public.HexOctets",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "ValueError": {
      "kind": "literal",
      "value": "ValueError"
    },
    "ZstdConstructorKwargs": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "format",
          "FormatName"
        ],
        [
          "dict_data",
          "public.Null"
        ],
        [
          "max_window_size",
          "WindowCap"
        ]
      ],
      "extra_fields": "refuse"
    },
    "FormatName": {
      "kind": "literal",
      "value": "FORMAT_ZSTD1"
    },
    "WindowCap": {
      "kind": "literal",
      "value": 1048576
    },
    "ZstdDecompressKwargs": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "max_output_size",
          "Positive"
        ],
        [
          "read_across_frames",
          "public.False"
        ],
        [
          "allow_extra_data",
          "public.False"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ZstdError": {
      "kind": "literal",
      "value": "ZstdError"
    },
    "ZstdTerminalDirectCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "constructor_kwargs",
          "ZstdConstructorKwargs"
        ],
        [
          "decompress_kwargs",
          "ZstdDecompressKwargs"
        ],
        [
          "returned_output_hex",
          "public.Null"
        ],
        [
          "error_class",
          "ZstdError"
        ],
        [
          "constructor_calls",
          "public.One"
        ],
        [
          "provider_complete_result_allowed",
          "public.False"
        ]
      ],
      "extra_fields": "refuse"
    },
    "SourceReadSize": {
      "kind": "enum",
      "exact_type": "int",
      "values": [
        1,
        7,
        65536
      ]
    },
    "SourcePartitionCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "source_read_size",
          "SourceReadSize"
        ],
        [
          "output",
          "CompleteOctets"
        ],
        [
          "termination_checks",
          "TerminalChecks"
        ]
      ],
      "extra_fields": "refuse"
    },
    "SourcePartitions": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "SourcePartitionCore",
      "minimum_items": 3,
      "maximum_items": 3,
      "rules": [
        "exact registered control order1,7,65536; identical complete output and physical framing"
      ]
    },
    "ComposedCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "input_sha256",
          "public.Sha256"
        ],
        [
          "physical_framing",
          "PhysicalFrames"
        ],
        [
          "output",
          "CompleteOctets"
        ],
        [
          "dbn_framing",
          "DbnFramingResult"
        ],
        [
          "observations",
          "NativeObservations"
        ],
        [
          "buffer_hex",
          "public.HexOctets"
        ],
        [
          "termination_checks",
          "TerminalChecks"
        ]
      ],
      "extra_fields": "refuse"
    },
    "LoadedAssociation": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "logical_id",
          "public.ArtifactId"
        ],
        [
          "module_name",
          "ProofText"
        ],
        [
          "native",
          "public.Bool"
        ]
      ],
      "extra_fields": "refuse",
      "allowed_rows": [
        [
          "python.exe",
          "sys.executable",
          true
        ],
        [
          "python312.dll",
          "sys.dllhandle",
          true
        ],
        [
          "dbn_init",
          "databento_dbn",
          false
        ],
        [
          "dbn_metadata",
          "databento_dbn.metadata",
          false
        ],
        [
          "dbn_v1",
          "databento_dbn.v1",
          false
        ],
        [
          "dbn_v2",
          "databento_dbn.v2",
          false
        ],
        [
          "dbn_v3",
          "databento_dbn.v3",
          false
        ],
        [
          "dbn_extension",
          "databento_dbn._lib",
          true
        ],
        [
          "zstd_init",
          "zstandard",
          false
        ],
        [
          "zstd_extension",
          "zstandard.backend_c",
          true
        ]
      ],
      "row_fields": [
        "logical_id",
        "module_name",
        "native"
      ]
    },
    "LoadedAssociations": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "LoadedAssociation",
      "minimum_items": 10,
      "maximum_items": 10,
      "rules": [
        "all ten rows once in listed fixed registration order; actual machine paths and handles remain only in attempt receipt"
      ]
    },
    "IdentityCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "status",
          "IdentityStatus"
        ],
        [
          "runtime_manifest",
          "public.RuntimeManifest"
        ],
        [
          "backend",
          "BackendName"
        ],
        [
          "dbn_version",
          "DbnVersion"
        ],
        [
          "zstd_package_version",
          "ZstdVersion"
        ],
        [
          "zstd_library_version",
          "LibraryVersion"
        ],
        [
          "isolated",
          "public.One"
        ],
        [
          "no_site",
          "public.One"
        ],
        [
          "dont_write_bytecode",
          "public.One"
        ],
        [
          "constructor_calls",
          "public.Zero"
        ],
        [
          "loaded_associations",
          "LoadedAssociations"
        ]
      ],
      "extra_fields": "refuse"
    },
    "IdentityStatus": {
      "kind": "literal",
      "value": "registered_loaded_identity_consistency_only"
    },
    "BackendName": {
      "kind": "literal",
      "value": "cext"
    },
    "DbnVersion": {
      "kind": "literal",
      "value": "0.70.0"
    },
    "ZstdVersion": {
      "kind": "literal",
      "value": "0.25.0"
    },
    "LibraryVersion": {
      "kind": "fixed_tuple",
      "literal_items": [
        1,
        5,
        7
      ],
      "item_exact_type": "int",
      "canonical_type": "array",
      "extra_items": "refuse"
    },
    "JunitAssertion": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "collected_identity",
          "ProofText"
        ],
        [
          "junit_identity",
          "JunitIdentity"
        ],
        [
          "evidence_kind",
          "AssertionEvidenceKind"
        ],
        [
          "expected_outcome",
          "Passed"
        ],
        [
          "observed_outcome",
          "Passed"
        ]
      ],
      "extra_fields": "refuse"
    },
    "Passed": {
      "kind": "literal",
      "value": "passed"
    },
    "JunitAssertions": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "schema",
          "AssertionIndexSchema"
        ],
        [
          "cases",
          "JunitAssertionList"
        ],
        [
          "unemitted_bodies_not_fabricated",
          "True"
        ]
      ],
      "extra_fields": "refuse"
    },
    "SemanticFamily": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "dbn_member",
        "dbn_preflight_refusal",
        "dbn_direct_boundary",
        "zstd_member",
        "zstd_refusal",
        "zstd_empty_boundary",
        "zstd_oneshot_boundary",
        "zstd_source_partitions",
        "composed_member"
      ]
    },
    "SemanticCore": {
      "kind": "union",
      "alternatives": [
        "DbnCore",
        "DbnPreflightCore",
        "DbnDirectCore",
        "ZstdCore",
        "ZstdRefusalCore",
        "ZstdEmptyCore",
        "ZstdTerminalDirectCore",
        "ComposedCore"
      ]
    },
    "SemanticCase": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "case_id",
          "ProofText"
        ],
        [
          "family",
          "SemanticFamily"
        ],
        [
          "source_packet",
          "SourcePacket"
        ],
        [
          "input",
          "NullableOctets"
        ],
        [
          "expected",
          "SemanticCore"
        ],
        [
          "observed",
          "SemanticCore"
        ],
        [
          "partition_controls",
          "PartitionControls"
        ],
        [
          "comparison",
          "Comparison"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "family chooses EXACT corresponding core schema; no generic arbitrary body",
        "case_id is exact mode/case-id identifier; preserve registered order and uniqueness",
        "no provider_complete_result_allowed addition unless the actual native output emitted it"
      ]
    },
    "SemanticCases": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "SemanticCase",
      "minimum_items": 125,
      "maximum_items": 125
    },
    "SemanticProofCases": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "schema",
          "ProofCasesSchema"
        ],
        [
          "junit_cases",
          "JunitAssertions"
        ],
        [
          "identity_context",
          "IdentityCore"
        ],
        [
          "native_cases",
          "SemanticCases"
        ],
        [
          "harmless_controls",
          "HarmlessControls"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ProofCasesSchema": {
      "kind": "literal",
      "value": "native_profile_semantic_proof_cases_v1"
    },
    "Empty": {
      "kind": "fixed_tuple",
      "items": [],
      "canonical_type": "array",
      "extra_items": "refuse"
    },
    "HexEncoding": {
      "kind": "literal",
      "value": "hex"
    },
    "RepeatEncoding": {
      "kind": "literal",
      "value": "repeat_byte"
    },
    "HexBody": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "encoding",
          "HexEncoding"
        ],
        [
          "hex",
          "public.HexOctets"
        ]
      ],
      "extra_fields": "refuse"
    },
    "RepeatBody": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "encoding",
          "RepeatEncoding"
        ],
        [
          "byte",
          "public.U8"
        ],
        [
          "count",
          "Positive"
        ]
      ],
      "extra_fields": "refuse"
    },
    "CompleteOctets": {
      "kind": "union",
      "alternatives": [
        "HexBody",
        "RepeatBody"
      ],
      "rules": [
        "expand the ENTIRE lossless byte string before comparison/hashing",
        "unique normalization: nonempty uniform string is repeat_byte; every empty/mixed string is hex; no arbitrary compression/subset/digest substitution"
      ]
    },
    "NullableOctets": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "CompleteOctets"
      ]
    },
    "SourcePacket": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "logical_id",
          "ProofText"
        ],
        [
          "raw_sha256",
          "public.Sha256"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "logical source identifier, not a machine path; exact formatted held declaration source hash",
        "runtime identity source may be the deterministic runtime-manifest literal; no attempt/report hash as semantic source"
      ]
    },
    "Comparison": {
      "kind": "literal",
      "value": "complete_equal"
    },
    "DbnCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "input_sha256",
          "public.Sha256"
        ],
        [
          "dbn_framing",
          "DbnFramingResult"
        ],
        [
          "observations",
          "NativeObservations"
        ],
        [
          "buffer_hex",
          "public.HexOctets"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ZstdCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "physical_framing",
          "PhysicalFrames"
        ],
        [
          "output",
          "CompleteOctets"
        ],
        [
          "termination_checks",
          "TerminalChecks"
        ]
      ],
      "extra_fields": "refuse"
    },
    "CompleteFrameOutputs": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "CompleteOctets",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "ZstdSourceCore": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "physical_framing",
          "PhysicalFrames"
        ],
        [
          "output",
          "CompleteOctets"
        ],
        [
          "termination_checks",
          "TerminalChecks"
        ]
      ],
      "extra_fields": "refuse"
    },
    "DbnPartitionControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "mode",
          "FeedMode"
        ],
        [
          "chunk_lengths",
          "ChunkLengths"
        ],
        [
          "buffer_hex",
          "public.HexOctets"
        ],
        [
          "comparison",
          "Comparison"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ChunkLengths": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "Positive",
      "minimum_items": 1,
      "maximum_items": 1048576
    },
    "OutputRequests": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "Positive",
      "minimum_items": 1,
      "maximum_items": 1048576
    },
    "FrameInputPositions": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "Positive",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "ReadThroughInterpretation": {
      "kind": "literal",
      "value": "source_read_through_not_native_eof"
    },
    "SourceReadControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "source_read_size",
          "SourceReadSize"
        ],
        [
          "output_read_requests",
          "OutputRequests"
        ],
        [
          "frame_input_positions",
          "FrameInputPositions"
        ],
        [
          "interpretation",
          "ReadThroughInterpretation"
        ]
      ],
      "extra_fields": "refuse"
    },
    "PartitionControl": {
      "kind": "union",
      "alternatives": [
        "DbnPartitionControl",
        "SourceReadControl",
        "DbnBoundaryControl",
        "DiagnosticErrorControl",
        "SourceTraceControl"
      ]
    },
    "PartitionControls": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "PartitionControl",
      "minimum_items": 0,
      "maximum_items": 16
    },
    "NullableNonnegative": {
      "kind": "union",
      "alternatives": [
        "public.Null",
        "Nonnegative"
      ]
    },
    "ErrorMessageRule": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "none",
        "nonempty_exact_string"
      ]
    },
    "ErrorMessageCheck": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "rule",
          "ErrorMessageRule"
        ],
        [
          "matched",
          "True"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ErrorMessageChecks": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "ErrorMessageCheck",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "DbnBoundaryControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "input_chunks_hex",
          "InputChunks"
        ],
        [
          "error_message_checks",
          "ErrorMessageChecks"
        ]
      ],
      "extra_fields": "refuse"
    },
    "InputChunks": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "public.HexOctets",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "DiagnosticErrorControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "error_message_rule",
          "ErrorMessageRule"
        ],
        [
          "matched",
          "True"
        ]
      ],
      "extra_fields": "refuse"
    },
    "SourceReadCall": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "requested",
          "SourceReadSize"
        ],
        [
          "returned_hex",
          "public.HexOctets"
        ]
      ],
      "extra_fields": "refuse"
    },
    "SourceReadCalls": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "SourceReadCall",
      "minimum_items": 1,
      "maximum_items": 1048576
    },
    "SourceReadFrameCalls": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "SourceReadCalls",
      "minimum_items": 1,
      "maximum_items": 16
    },
    "PermittedSuffix": {
      "kind": "literal",
      "value": "zero_or_more_empty_reads_after_complete_frame"
    },
    "SourceTraceControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "source_read_size",
          "SourceReadSize"
        ],
        [
          "expected_nonempty_source_reads",
          "SourceReadFrameCalls"
        ],
        [
          "observed_source_reads",
          "SourceReadFrameCalls"
        ],
        [
          "output_read_requests",
          "OutputRequests"
        ],
        [
          "frame_input_positions",
          "FrameInputPositions"
        ],
        [
          "interpretation",
          "ReadThroughInterpretation"
        ],
        [
          "permitted_suffix",
          "PermittedSuffix"
        ],
        [
          "comparison",
          "Comparison"
        ]
      ],
      "extra_fields": "refuse"
    },
    "ExpectedLimits": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "limit_flags",
          "LimitFlags"
        ],
        [
          "active_process_limit",
          "public.One"
        ],
        [
          "process_memory_bytes",
          "MemoryLimit"
        ],
        [
          "job_memory_bytes",
          "MemoryLimit"
        ],
        [
          "process_user_time_100ns",
          "CpuLimit"
        ],
        [
          "job_user_time_100ns",
          "CpuLimit"
        ]
      ],
      "extra_fields": "refuse"
    },
    "LimitFlags": {
      "kind": "literal",
      "value": 8974
    },
    "MemoryLimit": {
      "kind": "literal",
      "value": 268435456
    },
    "CpuLimit": {
      "kind": "literal",
      "value": 50000000
    },
    "ControlDisposition": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "completed",
        "timeout",
        "nonzero_exit",
        "output_limit"
      ]
    },
    "ExitCondition": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "zero",
        "nonzero_retained_exit",
        "exact_17",
        "retained_exit"
      ]
    },
    "OutputCondition": {
      "kind": "enum",
      "exact_type": "str",
      "values": [
        "complete_success_json_one_lf_or_crlf",
        "incomplete_empty_prefix",
        "complete_allocation_refused_json_one_lf_or_crlf",
        "complete_empty_stream",
        "incomplete_all_x_prefix_1_to_4194304"
      ]
    },
    "HarmlessControl": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "identity",
          "JunitIdentity"
        ],
        [
          "case_id",
          "ProofText"
        ],
        [
          "disposition",
          "ControlDisposition"
        ],
        [
          "exit_condition",
          "ExitCondition"
        ],
        [
          "output_condition",
          "OutputCondition"
        ],
        [
          "configured_limits",
          "ExpectedLimits"
        ],
        [
          "queried_limits_equal",
          "True"
        ],
        [
          "in_job_before_resume",
          "True"
        ],
        [
          "process_exited",
          "True"
        ],
        [
          "final_active_processes",
          "public.Zero"
        ],
        [
          "final_job_process_ids",
          "Empty"
        ],
        [
          "cleanup_errors",
          "Empty"
        ],
        [
          "assertion_outcome",
          "Passed"
        ]
      ],
      "extra_fields": "refuse",
      "allowed_rows": [
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_missing_process_birth_containment_behavior"
          ],
          "stub_success",
          "completed",
          "zero",
          "complete_success_json_one_lf_or_crlf"
        ],
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_sleeping_owned_control_is_terminated_and_waited"
          ],
          "stub_timeout",
          "timeout",
          "nonzero_retained_exit",
          "incomplete_empty_prefix"
        ],
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_attempted_512_mib_allocation_is_refused_under_256_mib_job"
          ],
          "stub_memory",
          "completed",
          "zero",
          "complete_allocation_refused_json_one_lf_or_crlf"
        ],
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_real_exit_17_is_retained_not_reported_as_success"
          ],
          "stub_crash",
          "nonzero_exit",
          "exact_17",
          "complete_empty_stream"
        ],
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_excess_output_is_retained_only_as_bounded_incomplete_prefix"
          ],
          "stub_output",
          "output_limit",
          "retained_exit",
          "incomplete_all_x_prefix_1_to_4194304"
        ],
        [
          [
            "tests.test_native_profile_probe_20261012_1",
            "test_generic_future_utc_deadline_allows_the_fixed_owned_unit_control"
          ],
          "stub_success",
          "completed",
          "zero",
          "complete_success_json_one_lf_or_crlf"
        ]
      ],
      "row_fields": [
        "identity",
        "case_id",
        "disposition",
        "exit_condition",
        "output_condition"
      ],
      "rules": [
        "identity tuple equals exactly one complete allowed row, including case-sensitive class and name; no undefined derived-field alias"
      ]
    },
    "HarmlessControls": {
      "kind": "tuple",
      "canonical_type": "array",
      "exact_type": true,
      "item": "HarmlessControl",
      "minimum_items": 6,
      "maximum_items": 6,
      "rules": [
        "all six complete identity tuples match the listed allowed rows exactly once; no filename/base-name coercion",
        "predicate claims come from executed independent assertions; do not encode unobserved fixed output lengths, peaks, PIDs/times or sampled successful subsets",
        "output bytes are preserved in complete machine receipt; large x output is a retained prefix, not intended stream"
      ]
    },
    "JunitIdentity": {
      "kind": "fixed_tuple",
      "items": [
        "ProofText",
        "ProofText"
      ],
      "canonical_type": "array",
      "extra_items": "refuse"
    },
    "AssertionEvidenceKind": {
      "kind": "literal",
      "value": "executed_test_assertions_not_unemitted_body_capture"
    },
    "JunitAssertionList": {
      "kind": "tuple",
      "canonical_type": "array",
      "item": "JunitAssertion",
      "minimum_items": 211,
      "maximum_items": 211,
      "rules": [
        "complete case-sensitive set/order from final_new_expected_1.json,178ordinary+33qualification; every node once",
        "full collected string and full class/name tuple retain parameter distinctions; no lowercasing or GZIP/gzip normalization",
        "assertion-only evidence never synthesizes expected/observed body; full native body families are retained separately"
      ]
    },
    "AssertionIndexSchema": {
      "kind": "literal",
      "value": "native_profile_complete_assertion_index_v1"
    },
    "BlockOrdinal": {
      "kind": "int",
      "exact_type": true,
      "minimum_decimal": "1",
      "maximum_decimal": "87380"
    }
  },
  "junit_family_mapping": {
    "scripts/test_native_profile_qualification_20261012_1.py::test_each_zstd_frame_must_have_nonempty_output_before_a_later_reader": {
      "family": "codec_phase_guard_assertion",
      "registered_instances": 2
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_explicit_native_deadline_refuses_before_containment_without_fallback": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 3
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_identity_implementation_refuses_before_artifacts_or_native_import": {
      "family": "identity_guard_assertion",
      "registered_instances": 5
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_identity_phase_refusal_never_reaches_a_deferred_seam": {
      "family": "identity_guard_assertion",
      "registered_instances": 3
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_identity_qualifies_complete_registered_context_without_native_calls": {
      "family": "identity_guard_assertion",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_identity_rejects_artifact_mutation_after_loaded_association": {
      "family": "identity_guard_assertion",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_identity_runtime_preflight_refuses_before_any_artifact_or_native_seam": {
      "family": "identity_guard_assertion",
      "registered_instances": 5
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_boundaries_child_complete_negative_controls_not_admission": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_capacity_child_complete_metadata_and_position_boundaries": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_composed_child_complete_frames_and_continuous_dbn": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_dbn_child_complete_literal_cohort_and_partitions": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_enum_child_complete_source_domains_and_ts_out_modes": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_identity_child_complete_evidence": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_zstd_capacity_child_complete_input_frame_and_cumulative_caps": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_zstd_child_complete_literal_outputs_and_refusals": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_registered_native_zstd_partitions_child_full_source_reads_and_outputs": {
      "family": "native_capture_controller",
      "registered_instances": 1
    },
    "scripts/test_native_profile_qualification_20261012_1.py::test_zstd_terminal_check_uses_closed_same_decoder_and_stops_before_next_frame": {
      "family": "codec_phase_guard_assertion",
      "registered_instances": 4
    },
    "tests/test_native_profile_probe_20261012_1.py::test_attempted_512_mib_allocation_is_refused_under_256_mib_job": {
      "family": "containment_control_capture",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_all_shorter_prefixes_distinguish_complete_records_from_incomplete_bytes": {
      "family": "dbn_prefix_sweep_assertion",
      "registered_instances": 9
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_complete_distinct_mapping_groups_at_limit_and_first_excess": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 2
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_complete_mapping_intervals_at_limit_and_first_excess": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 2
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_complete_symbol_list_at_limit_and_first_excess": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 2
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_exact_position_capacity_and_first_excess_preserve_every_record": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_preserves_all_source_defined_stype_wire_codes": {
      "family": "dbn_literal_framing_assertion",
      "registered_instances": 33
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_preserves_complete_literal_wire_bodies_and_spans": {
      "family": "dbn_literal_framing_assertion",
      "registered_instances": 9
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_refuses_complete_named_malformed_candidates": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 7
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_refuses_duplicate_original_wire_mapping_keys": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_refuses_noncanonical_complete_field_candidates": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 25
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_framing_refuses_undefined_stype_wire_codes": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 3
    },
    "tests/test_native_profile_probe_20261012_1.py::test_dbn_outer_byte_and_header_caps_refuse_before_metadata_traversal": {
      "family": "dbn_framing_boundary_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_deadline_jump_is_rechecked_immediately_before_process_creation": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_excess_output_is_retained_only_as_bounded_incomplete_prefix": {
      "family": "containment_control_capture",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_framing_requires_exact_nonempty_bytes_without_input_coercion": {
      "family": "framing_exact_type_assertion",
      "registered_instances": 18
    },
    "tests/test_native_profile_probe_20261012_1.py::test_generic_future_utc_deadline_allows_the_fixed_owned_unit_control": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_insufficient_deadline_reserve_refuses_before_api_setup": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_missing_process_birth_containment_behavior": {
      "family": "containment_control_capture",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_only_fixed_stub_unit_controls_have_a_local_future_deadline": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_present_invalid_or_expired_deadline_never_falls_back_or_creates": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 5
    },
    "tests/test_native_profile_probe_20261012_1.py::test_real_exit_17_is_retained_not_reported_as_success": {
      "family": "containment_control_capture",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_sleeping_owned_control_is_terminated_and_waited": {
      "family": "containment_control_capture",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_successful_verified_job_termination_does_not_race_process_fallback": {
      "family": "job_termination_guard_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_wrong_executable_or_script_pin_refuses_before_process_creation": {
      "family": "precreation_or_deadline_assertion",
      "registered_instances": 2
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_all_shorter_prefixes_distinguish_complete_frames_from_incomplete_bytes": {
      "family": "zstd_prefix_sweep_assertion",
      "registered_instances": 10
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_complete_compressed_member_exact_byte_cap_and_first_excess": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 2
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_cumulative_known_output_cap_is_not_confused_with_unknown_output_claims": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_each_block_type_first_excess_block_size_refuses": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 3
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_exact_frame_capacity_and_first_excess_keep_all_physical_frames": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_framing_preserves_complete_literal_physical_frame_descriptors": {
      "family": "zstd_literal_framing_assertion",
      "registered_instances": 10
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_framing_refuses_strict_format_truncation_tail_and_skippable_candidates": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 4
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_physical_framing_does_not_claim_checksum_or_declared_output_consistency": {
      "family": "zstd_literal_framing_assertion",
      "registered_instances": 1
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_physical_framing_refuses_forbidden_complete_structural_candidates": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 11
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_physical_framing_separates_known_size_refusal_from_unknown_output_capacity": {
      "family": "zstd_framing_boundary_assertion",
      "registered_instances": 4
    },
    "tests/test_native_profile_probe_20261012_1.py::test_zstd_two_byte_size_bias_and_eight_byte_size_have_independent_literal_descriptors": {
      "family": "zstd_literal_framing_assertion",
      "registered_instances": 1
    }
  },
  "native_mode_mapping": {
    "native_identity": {
      "identity_context": "IdentityCore",
      "case_count": 1,
      "native_input_row_count": 0
    },
    "native_dbn": {
      "cases_family": "dbn_member",
      "case_count": 42,
      "partitions_each": 3,
      "strict_refusals_family": "dbn_preflight_refusal",
      "strict_refusal_count": 11
    },
    "native_enums": {
      "cases_family": "dbn_member",
      "case_count": 20,
      "partitions_each": 3,
      "strict_refusal_count": 0
    },
    "native_capacity": {
      "cases_family": "dbn_member",
      "case_count": 3,
      "partitions_each": 3,
      "strict_refusal_count": 0
    },
    "native_zstd": {
      "cases_family": "zstd_member",
      "case_count": 12,
      "refusals_family": "zstd_refusal",
      "refusal_count": 7
    },
    "native_zstd_capacity": {
      "cases_family": "zstd_member",
      "case_count": 2,
      "refusals_family": "zstd_refusal",
      "refusal_count": 1
    },
    "native_boundaries": {
      "dbn_cases_family": "dbn_direct_boundary",
      "dbn_case_count": 15,
      "zstd_empty_cases_family": "zstd_empty_boundary",
      "zstd_empty_case_count": 3,
      "zstd_terminal_cases_family": "zstd_oneshot_boundary",
      "zstd_terminal_case_count": 3
    },
    "native_zstd_partitions": {
      "cases_family": "zstd_source_partitions",
      "case_count": 3,
      "partitions_each": 3
    },
    "native_composed": {
      "cases_family": "composed_member",
      "case_count": 3,
      "partitions_each": 3
    }
  },
  "family_schema_mapping": {
    "dbn_member": "DbnCore",
    "dbn_preflight_refusal": "DbnPreflightCore",
    "dbn_direct_boundary": "DbnDirectCore",
    "zstd_member": "ZstdCore",
    "zstd_refusal": "ZstdRefusalCore",
    "zstd_empty_boundary": "ZstdEmptyCore",
    "zstd_oneshot_boundary": "ZstdTerminalDirectCore",
    "zstd_source_partitions": "ZstdCore",
    "composed_member": "ComposedCore"
  },
  "semantic_normalization": {
    "schema": "native_profile_semantic_normalization_v1",
    "case_fields": [
      "case_id",
      "family",
      "source_packet",
      "input",
      "expected",
      "observed",
      "partition_controls",
      "comparison"
    ],
    "case_order": [
      {
        "mode": "native_dbn",
        "category": "positive",
        "rows": 42,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_enums",
        "category": "positive",
        "rows": 20,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_capacity",
        "category": "positive",
        "rows": 3,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_zstd",
        "category": "positive",
        "rows": 12,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_zstd_capacity",
        "category": "positive",
        "rows": 2,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_zstd",
        "category": "refusal",
        "rows": 7,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_zstd_capacity",
        "category": "refusal",
        "rows": 1,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_dbn",
        "category": "preflight_refusal",
        "rows": 11,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_composed",
        "category": "positive",
        "rows": 3,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_boundaries",
        "category": "dbn_direct",
        "rows": 15,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_boundaries",
        "category": "zstd_empty",
        "rows": 3,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_boundaries",
        "category": "zstd_oneshot",
        "rows": 3,
        "within": "independent_literal_order"
      },
      {
        "mode": "native_zstd_partitions",
        "category": "source_partition",
        "rows": 3,
        "within": "independent_literal_order"
      }
    ],
    "junit_case_order": "registered_complete_collected_identity_order",
    "family_selection": "exact_family_schema_mapping_no_default",
    "comparison": "complete_equal",
    "octets": {
      "nonempty_uniform": "repeat_byte",
      "empty_or_mixed": "hex",
      "compare": "expand_entire_bytes_before_equality_and_raw_sha256",
      "subset_allowed": false
    },
    "dbn_partitions": {
      "modes": [
        "complete",
        "chunks7",
        "bytewise"
      ],
      "require": "compare_every_complete_observation_framing_and_final_buffer_before_shared_body_reduction",
      "retained_controls": [
        "mode",
        "chunk_lengths",
        "buffer_hex",
        "comparison"
      ],
      "unreduced_captures": "complete_receipt_only"
    },
    "zstd_output": {
      "input_capture": "strict_canonical_base64_or_full_hex",
      "core_output": "lossless_CompleteOctets",
      "physical_frames": "unchanged_complete16_field_tuples",
      "terminal_checks": "every_full_same_decoder_check"
    },
    "source_reads": {
      "controls": [
        1,
        7,
        65536
      ],
      "framing": "unchanged_original_member_coordinates",
      "expected_nonempty": "complete_exact_frame_chunks_from_registered_source_read_size",
      "observed_core": "strip_only_final_empty_read_suffix_after_exact_nonempty_chunk_equality",
      "permitted_suffix": "zero_or_more_empty_reads_after_complete_frame",
      "complete_unstripped_trace": "complete_receipt_only",
      "input_positions_interpretation": "source_read_through_not_native_eof"
    },
    "error_messages": {
      "core": "exclude_literal_wording_only",
      "retained_rule_values": [
        "none",
        "nonempty_exact_string"
      ],
      "require_matched": true,
      "complete_wording": "complete_receipt_only",
      "retain": [
        "exact_error_class",
        "per_call_None_vs_empty_return",
        "full_buffer",
        "visible_prefix",
        "constructor_count",
        "actual_phase"
      ]
    },
    "provider_complete_result_allowed": {
      "rule": "retain_only_when_the_actual_case_emitted_it",
      "invent_missing_field": false
    },
    "harmless_controls": {
      "core": "exact_six_13field_predicate_rows",
      "full_actual_output_and_variable_prefix_length": "complete_receipt_only",
      "output_prefix_scope": "retained_prefix_not_intended_full_stream"
    },
    "excluded_from_profile_body": [
      "attempt_receipts",
      "raw_report_hashes",
      "registration_hashes",
      "machine_execution_paths",
      "PIDs",
      "creation_or_elapsed_times",
      "ASLR_handles",
      "variable_peaks",
      "literal_error_wording",
      "permitted_final_empty_read_suffixes"
    ],
    "source_identifier_exception": "fixed_source_test_identifiers_and_official_immutable_reference_URLs_are_source_identity_not_machine_execution_paths",
    "body_oracle": "independent_held_literal_declarations_not_returned_native_or_production_serializers",
    "unemitted_unit_bodies": "assertion_outcomes_only_never_fabricate_expected_or_observed_data"
  }
}
```

## Complete semantic extraction rules

Root assembles the profile from held declaration text and reconciled complete captures, not from freshly imported native code. Declaration extraction is limited to the held assignment/expression grammar and admitted literal builtins in the source receipt; future arbitrary code execution is not an oracle. Independent expectations must come from those declarations and immutable format sources. Observed data must come from actual retained outputs; never synthesize observed=expected for an un-emitted unit body.

The complete semantic object has schema, junit_cases, identity_context, native_cases and harmless_controls. junit_cases is the entire exact assertion-index wrapper: schema=native_profile_complete_assertion_index_v1, all 211 five-field records, and unemitted_bodies_not_fabricated=True. Each record retains collected_identity, the complete JUnit [class,name] identity tuple, evidence_kind, expected_outcome and observed_outcome. Both outcomes are passed in this accepted cohort; this is assertion-outcome evidence, not native body capture. PROOF_SCHEMA_JSON's exact base-name mapping removes only the parameter suffix for family selection; full identities retain every case-sensitive parameter. No case is omitted or merged.

identity_context is the explicit IdentityCore body, not a fake native input. It contains the full observed/expected-equal RuntimeManifest and versions/backend/flags/constructor0 plus the complete 10-entry logical loaded-association policy. Actual file/spec/mapped-address association checks survive intact in machine receipts. Runtime identity expectations are held before import; loaded associations are checked after controlled import and before constructors, then artifacts/associations rechecked at completion. A failed/unavailable association refuses; there is no runtime-identity bootstrap where already-called native output supplies its own expectation.

native_cases contains **125 complete eight-field rows**:
case_id,family,source_packet,input,expected,observed,partition_controls,comparison.
Their order is the explicit semantic_normalization.case_order list, with original independent literal order inside each category: DBN42 + enums20 + capacity3; Zstd12 + capacity2 positives, Zstd7 + capacity1 refusals, DBN11 preflight refusals; composed3; boundaries15 DBN + 3 empty + 3 one-shot; source partitions3. There is no hidden sort or dictionary iteration order. All125 byte inputs plus identity_context and all211 assertion identities are retained, not a selected successful subset.

| Family | Rows | Complete expected/observed core |
| --- | ---: | --- |
| dbn_member | 65 | input_sha256, complete dbn_framing, every Metadata/MBO observation, buffer_hex |
| dbn_preflight_refusal | 11 | phase=independent_preflight and actual constructor_calls0; no fabricated error/authority/body |
| zstd_member | 14 | complete physical_framing, lossless complete output, every same-decoder termination_check |
| zstd_refusal | 8 | actual phase, constructor_calls, error_class, observed_output_bytes (None where not emitted) |
| composed_member | 3 | input_sha256, physical_framing, complete output, full dbn_framing/observations/buffer, termination_checks |
| dbn_direct_boundary | 15 | all per-call inputs/returns/error classes/full buffers, visible prefix, held full-input identity/physical status/call count and actual emitted provider False |
| zstd_empty_boundary | 3 | every physical frame and full per-frame output, actual profile refusal/call count and emitted provider False |
| zstd_oneshot_boundary | 3 | exact constructor/decompress kwargs, actual no returned output, error class/call count and emitted provider False |
| zstd_source_partitions | 3 | same complete physical_framing/output/termination core; all three explicit source controls |
| TOTAL | 125 | No omitted direct/empty/terminal/refusal/partition family |

Reduction is explicit and exhaustive:

1. DBN/main/enum/capacity/composed complete, chunks7 and bytewise partitions are each compared against the independent full expected observations/framing/final buffer. Only AFTER exact complete equality may identical bodies be represented once in the semantic core; all three mode/chunk-length/final-buffer/comparison controls remain. The full repeated actual bodies stay in complete child outputs. No adoption of the first partition replaces checking another partition.
2. Zstd base64 output is strictly decoded and checked for canonical base64 against the entire independent expected bytes, then losslessly normalized to CompleteOctets. No hash-only/length-only adoption. Physical 16-field frames and eight-field blocks are unchanged. Public seven-field FrameSpan is a separate future projection, not silently replaced by these probe tuples.
3. Source partition controls retain 1/7/65536, requested output read sizes and frame_input_positions labelled source_read_through_not_native_eof. The independent nonempty source chunks are the complete exact frame split by that control. Strip ONLY each permitted final empty-read suffix for deterministic observed_source_reads after full nonempty sequence equality; no internal empty, duplicate/drop/reordering or premature stop is accepted. Preserve the entire unstripped observed trace in machine receipts. Optional EOF-read batching cannot change the semantic profile hash.
4. Error message wording is retained verbatim in machine captures. Semantic cores exclude only literal diagnostic wording; partition_controls retain exact rule none/nonempty_exact_string and matched=True for each relevant error. Native class, per-call return None versus empty list, complete remaining buffer, constructor count, visible prefix and actual phase remain in the core. A codec-direct negative result is not public provider admission; False is retained ONLY where actually emitted.
5. Harmless controls are the six exact 13-field predicate records, not copied output data. Success/generic-deadline controls require the complete success JSON with one LF or CRLF. Memory requires completed/exit0 and the complete allocation_refused JSON, not an invented nonzero exit. Timeout has nonzero retained exit and incomplete empty prefix; crash preserves exact17/complete empty stream; excess output retains the predicate full actual prefix is all x with length1..4194304, never claims intended stream completion. Complete output hashes/bytes (or exact lossless repeated-x prefix), queried limits, actual peaks/accounting/ownership/cleanup remain in the separate receipt. Variable prefix partition length does not enter deterministic policy semantics.
6. Full attempt diagnostics, parent/child PIDs/creation times/commands/paths, elapsed/peak values, ASLR handles, optional empty-read suffixes and literal error strings are excluded from deterministic profile_body, but NEVER discarded from qualification receipt. Stable source/test identifiers and official immutable repository URLs are source identifiers, not machine execution paths.
7. Every family and case is checked before a complete profile positive status. Shape/canonical/refusal aliases and exact ordinal/count equality remain mandatory; no successful-prefix or historical/source-authentication claim is created by normalization.

## Exact profile body/closure registry — PROFILE_CLOSURE_JSON

This literal supplies the fixed 16-field profile shape, exact official source file/selectors (including independent XXH64 spec/vector and Windows API references), RuntimeManifest, loaded-policy rows, complete wire/logical schemas, budgets and canonical exclusions. public_schemas.source_block_id instructs assembly to insert the **entire parsed PUBLIC_PROTOCOL_JSON object**, not that reference record. wire_schema.proof_registry.source_block_id likewise inserts the **entire parsed PROOF_SCHEMA_JSON object**, including every schema, all 53 family mappings, exact family_schema_mapping and complete semantic_normalization rules. semantic_proof_cases inserts the complete reconciled five-field semantic object. All other fixed fields shown are inserted literally. runtime_manifest_sha256 is H of the full literal RuntimeManifest. No unspecified status/kind/implementation, omitted outside-registry dependency or arbitrary caller registry is admitted.

The assembled profile is self-contained: public type names resolve within profile_body.public_schemas.schemas; proof type names resolve within profile_body.wire_schema.proof_registry.schemas. The explicit schema_owners/schema_owner fields identify the origins of duplicated wire/logical schema descriptors. A public.-prefixed proof reference resolves to the attached public registry, not this Markdown or an untracked file. Both complete registries, every family-selection rule and every normalization rule are therefore part of H(profile_body). No proof definition may remain merely outside the hashed body.

Before C4, a review artifact is permitted **only** in the exact four-field pending wrapper declared below: schema,status,proposed_profile_body,proposed_receipt. It retains the actual COMPLETE assembled proposed body and COMPLETE proposed receipt for inspection, labelled PENDING_C4_NO_POSITIVE_PROFILE_SHA256. The proposed receipt retains the final nine-field shape/schema but profile_sha256 is null and its status is pending. No positive digest, closed_profile or positive closure receipt is published. The proposed body's conditional qualified-status literal is a reviewable proposed value, not current qualification acceptance. This wrapper resolves the inspection bootstrap without a premature positive claim.

Its qualified status is conditional: **do not publish a qualified profile envelope, positive profile_sha256 or CLOSED artifact until C4 independently accepts the complete exact assembled body, receipts/pins and limitations.** Before that acceptance, the explicitly PENDING_C4 review wrapper may contain the complete proposed body and pending proposed receipt with profile_sha256=null. This saved annex remains CANDIDATE. Passing full regression alone does not override C4.

```json
{
  "schema": "native_profile_closure_schema_v1",
  "profile_body_fields": [
    "schema",
    "profile_id",
    "status",
    "scope",
    "references",
    "runtime_manifest",
    "runtime_manifest_sha256",
    "loaded_associations",
    "wire_schema",
    "logical_schema",
    "public_schemas",
    "decoder_options",
    "limits",
    "containment_policy",
    "semantic_proof_cases",
    "authorities"
  ],
  "profile_body_fixed_values": {
    "schema": "native_profile_qualification_v1",
    "profile_id": "dbn_v3_asis_zstd_cext_invented_20261012_v1",
    "status": "qualified_invented_native_proof_not_provider_acceptance",
    "scope": "invented_complete_in_memory_native_member_consistency_only"
  },
  "references": {
    "schema": "native_profile_reference_identity_v1",
    "immutable_repository_identities": [
      {
        "reference_id": "dbn_v0.70.0",
        "repository": "https://github.com/databento/dbn",
        "commit": "aa012adc6502e01b01d7b5c7836742dde21e93d8"
      },
      {
        "reference_id": "python_zstandard_0.25.0",
        "repository": "https://github.com/indygreg/python-zstandard",
        "commit": "7a77a7510b8ce068e4a103d29aea1b5ec829d8b6"
      },
      {
        "reference_id": "zstd_v1.5.7",
        "repository": "https://github.com/facebook/zstd",
        "commit": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
      },
      {
        "reference_id": "xxh64_spec",
        "repository": "https://github.com/Cyan4973/xxHash",
        "commit": "e626a72bc2321cd320e953a0ccf1584cad60f363"
      },
      {
        "reference_id": "xxh64_independent_vectors",
        "repository": "https://github.com/Cyan4973/xxHash",
        "commit": "173e50be0509c6fb6c1bb74d95049ef61d7fdced"
      }
    ],
    "held_declaration_file_selectors": {
      "native_profile_capacity_oracles_20261012_1.py": {
        "DBN_COMMIT": "aa012adc6502e01b01d7b5c7836742dde21e93d8",
        "DBN_SOURCE_ROOT": "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/",
        "SOURCE_REFERENCES": [
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::decode_metadata_impl",
            "raw u64 start/limit; end UNDEF_TIMESTAMP vs NonZeroU64::new(0); no start/end ordering coercion"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::decode_metadata_repeated_symbol_cstr; decode_metadata_symbol_mappings",
            "complete count/list order and every mapping occurrence"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::decode_metadata_symbol_mapping; decode_metadata_symbol",
            "fixed 71-byte UTF-8 C strings and complete little-endian dated intervals"
          ],
          [
            "rust/dbn/src/decode/dbn/sync.rs",
            "decode_iso8601",
            "YYYYMMDD decomposition followed by time::Date::from_calendar_date"
          ],
          [
            "rust/dbn/src/encode/dbn/sync.rs",
            "MetadataEncoder::encode; encode_symbol_mappings; encode_repeated_symbol_cstr",
            "source layout ordering/alignment only; no encoder is executed"
          ],
          [
            "rust/dbn/src/metadata.rs",
            "Metadata fields",
            "u64 start and Option<NonZeroU64> end/limit getters"
          ],
          [
            "rust/dbn/src/python/metadata.rs",
            "Metadata::get_mappings; IntoPyObject for &MappingInterval",
            "getter dictionary and explicit Python-date year/month/day projections"
          ],
          [
            "rust/dbn/src/record.rs",
            "RecordHeader; MboMsg",
            "complete v3 Header/MBO named raw fields and widths"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "MboMsg getter implementations",
            "native enum/flags, absent ts_out, record_size and ts_index observations"
          ],
          [
            "python/src/dbn_decoder.rs",
            "DbnDecoder::new; decode; write_and_decode",
            "explicit metadata-present AS_IS/NONE fresh continuous decoder"
          ]
        ]
      },
      "native_profile_composed_oracles_20261012_1.py": {
        "DBN_SOURCE_COMMIT": "aa012adc6502e01b01d7b5c7836742dde21e93d8",
        "SOURCE_DERIVATION": [
          "Zstd magic 28b52ffd; descriptor20 gives single segment and one-byte FCS.",
          "Descriptor60 gives single segment and two-byte FCS with the format's +256 offset.",
          "Last RAW block header is (raw payload bytes << 3) | 1, three little-endian bytes.",
          "240: FCSf0/header810700; 256: stored FCS0000/header010800.",
          "Split5/235: FCS05/eb; RAW headers290000/590700; two complete standard frames.",
          "Complete DBN source cases minimal_absent_ts_out and minimal_present_ts_out."
        ],
        "ZSTD_FORMAT_URL": "https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md",
        "ZSTD_SOURCE_COMMIT": "f8745da6ff1ad1e7bab384bd1f9d742439278e99"
      },
      "native_profile_enum_oracles_20261012_1.py": {
        "DBN_COMMIT": "aa012adc6502e01b01d7b5c7836742dde21e93d8",
        "DBN_SOURCE_ROOT": "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/",
        "SOURCE_REFERENCES": [
          [
            "rust/dbn/src/enums.rs",
            "265-275",
            "complete three-variant Side domain"
          ],
          [
            "rust/dbn/src/enums.rs",
            "308-330",
            "complete seven-variant Action domain"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "130-160",
            "Side name, numeric index and text"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "198-232",
            "Action name, numeric index and text"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "209-224",
            "recognized enum versus unknown-character getter paths"
          ],
          [
            "rust/dbn/src/record.rs",
            "37-122",
            "complete Header/MBO field layout"
          ],
          [
            "rust/dbn/src/record/layout_tests.rs",
            "67-119",
            "MBO field offsets and lengths"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "289-313",
            "absent versus present ts_out conversion"
          ]
        ]
      },
      "native_profile_native_negative_oracles_20261012_1.py": {
        "DBN_COMMIT": "aa012adc6502e01b01d7b5c7836742dde21e93d8",
        "DBN_SOURCE_REFERENCES": [
          [
            "python/src/dbn_decoder.rs",
            "DbnDecoder::new",
            "explicit constructor controls"
          ],
          [
            "python/src/dbn_decoder.rs",
            "DbnDecoder::write; buffer; write_and_decode",
            "exact write and buffer API"
          ],
          [
            "python/src/dbn_decoder.rs",
            "DbnDecoder::decode",
            "ReadMore returns list; Err discards current Vec"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::METADATA_PRELUDE_LEN; HEADER_LEN",
            "eight-byte prelude and RecordHeader threshold"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::data",
            "ConsumeOne/ConsumeBatch view excludes read bytes"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::process; record_length",
            "record length, ReadMore and error state"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::advance_to_record; consume",
            "ConsumeOne advances bytes then returns to Record state"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "DbnFsm::decode_prelude; decode_metadata",
            "prelude consumes8; metadata body consumed only on success"
          ],
          [
            "rust/dbn/src/macros.rs",
            "rtype_dispatch_base!",
            "unrecognized rtype Err before typed handler"
          ],
          [
            "rust/dbn/src/record_ref.rs",
            "Record implementation for RecordRef::rtype",
            "self.header().rtype() conversion"
          ],
          [
            "rust/dbn/src/enums.rs",
            "RType enum",
            "complete variant domain excludes ff"
          ],
          [
            "rust/dbn/src/python.rs",
            "DBNError declaration; to_py_err; From<Error> for PyErr",
            "Rust error conversion is Python DBNError"
          ]
        ],
        "DBN_SOURCE_ROOT": "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/",
        "PYTHON_ZSTD_COMMIT": "7a77a7510b8ce068e4a103d29aea1b5ec829d8b6",
        "PYTHON_ZSTD_SOURCE_ROOT": "https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/",
        "ZSTD_SOURCE_REFERENCES": [
          [
            "Frame_Header and Block_Header",
            "single-segment FCS, window and zero-sized last RAW block framing"
          ],
          [
            "Frames",
            "independent frames can be concatenated in original order"
          ]
        ],
        "ZSTD_SPEC_COMMIT": "f8745da6ff1ad1e7bab384bd1f9d742439278e99",
        "ZSTD_SPEC_URL": "https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md",
        "ZSTD_TERMINAL_SOURCE_REFERENCES": [
          [
            "c-ext/decompressor.c",
            "Decompressor_init; ensure_dctx",
            "explicit standard-format/no-dictionary context"
          ],
          [
            "c-ext/decompressor.c",
            "Decompressor_decompress argument and frameHeader branches",
            "method kwargs and complete frame-header check"
          ],
          [
            "c-ext/decompressor.c",
            "Decompressor_decompress decompressedSize branches",
            "known FCS versus unknown-FCS destination allocation"
          ],
          [
            "c-ext/decompressor.c",
            "Decompressor_decompress ZSTD_isError/zresult branches",
            "codec error or unfinished frame becomes ZstdError"
          ],
          [
            "c-ext/decompressor.c",
            "Decompressor_decompress outBuffer.pos/allowExtraData branches",
            "length/resize/no-extra-data ordering"
          ]
        ]
      },
      "native_profile_oracles_20261012_1.py": {
        "DBN_COMMIT": "aa012adc6502e01b01d7b5c7836742dde21e93d8",
        "DBN_REFERENCES": [
          [
            "rust/dbn/src/lib.rs",
            "132-158",
            "v3, widths and numeric sentinels"
          ],
          [
            "rust/dbn/src/compat.rs",
            "5-10",
            "v3 fixed symbol length 71"
          ],
          [
            "rust/dbn/src/encode/dbn/sync.rs",
            "145-249",
            "metadata ordering and padding"
          ],
          [
            "rust/dbn/src/encode/dbn/sync.rs",
            "252-370",
            "range/list/mapping/date bytes"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "685-821",
            "header and native translations"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "839-961",
            "lists and mapping decoding"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "1179-1202",
            "metadata overrides controls"
          ],
          [
            "rust/dbn/src/metadata.rs",
            "30-78",
            "14 logical fields/getters"
          ],
          [
            "rust/dbn/src/metadata.rs",
            "452-467",
            "inclusive/exclusive mapping dates"
          ],
          [
            "rust/dbn/src/python/metadata.rs",
            "78-87",
            "mapping getter last-key wins"
          ],
          [
            "rust/dbn/src/python/metadata.rs",
            "154-194",
            "mapping interval date objects"
          ],
          [
            "rust/dbn/src/record.rs",
            "37-122",
            "ordered repr(C) Header/MBO layout"
          ],
          [
            "rust/dbn/src/record/layout_tests.rs",
            "67-119",
            "source size assertions"
          ],
          [
            "rust/dbn/src/record/methods.rs",
            "13-37",
            "length multiplier and size"
          ],
          [
            "rust/dbn/src/record/with_ts_out_methods.rs",
            "60-66",
            "appended timestamp"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "101-150",
            "rtype/record_size/ts_index"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "206-239",
            "flags/action/side getters"
          ],
          [
            "rust/dbn/src/python/record.rs",
            "307-334",
            "absent/present ts_out"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "21-72",
            "RType name/text/index"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "126-237",
            "Side/Action name/text/index"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "620-714",
            "SType/Schema text/index"
          ],
          [
            "rust/dbn/src/python.rs",
            "82-89",
            "FlagSet becomes Python integer"
          ],
          [
            "rust/dbn/src/enums.rs",
            "273-340",
            "Side and Action codes"
          ],
          [
            "rust/dbn/src/enums.rs",
            "580-599",
            "SType codes"
          ],
          [
            "rust/dbn/src/enums.rs",
            "715-718",
            "Schema MBO code"
          ],
          [
            "rust/dbn/src/enums.rs",
            "1434-1448",
            "upgrade-policy codes/default"
          ],
          [
            "python/src/dbn_decoder.rs",
            "20-126",
            "constructor and output traversal"
          ]
        ],
        "DBN_SOURCE_ROOT": "https://github.com/databento/dbn/blob/aa012adc6502e01b01d7b5c7836742dde21e93d8/",
        "DBN_STYPE_REFERENCES": [
          [
            "rust/dbn/src/enums.rs",
            "580-632",
            "complete u8 enum domain"
          ],
          [
            "rust/dbn/src/enums.rs",
            "670-688",
            "complete as_str mapping"
          ],
          [
            "rust/dbn/src/python/enums.rs",
            "635-653",
            "native uppercase name getter"
          ],
          [
            "rust/dbn/src/decode/dbn/fsm.rs",
            "760-772",
            "input-null/output-enum checks"
          ]
        ],
        "PYTHON_ZSTD_COMMIT": "7a77a7510b8ce068e4a103d29aea1b5ec829d8b6",
        "PYTHON_ZSTD_SOURCE_ROOT": "https://github.com/indygreg/python-zstandard/blob/7a77a7510b8ce068e4a103d29aea1b5ec829d8b6/",
        "XXH64_SPEC_ANCHORS": [
          [
            "191-233",
            "constants and short-input initialization"
          ],
          [
            "280-330",
            "length, tail bytes, rotations and avalanche"
          ]
        ],
        "XXH64_SPEC_COMMIT": "e626a72bc2321cd320e953a0ccf1584cad60f363",
        "XXH64_SPEC_URL": "https://github.com/Cyan4973/xxHash/blob/e626a72bc2321cd320e953a0ccf1584cad60f363/doc/xxhash_spec.md",
        "XXH64_VECTOR_SOURCE_ANCHORS": [
          [
            "580-590",
            "first sanity input byte is00"
          ],
          [
            "1213-1215",
            "empty and one-byte00 independent seed0 vector literals"
          ]
        ],
        "XXH64_VECTOR_SOURCE_URL": "https://github.com/Cyan4973/xxHash/blob/173e50be0509c6fb6c1bb74d95049ef61d7fdced/xxhsum.c",
        "ZSTD_REFERENCE_ANCHORS": [
          [
            "95-398",
            "frame/header/block-size rules"
          ],
          [
            "431-563",
            "raw/RLE literal encoding"
          ],
          [
            "613-661",
            "zero-sequence compressed block"
          ],
          [
            "643-857",
            "RLE sequence modes/codes/bitstream"
          ],
          [
            "898-982",
            "sequence execution and initial repeat offsets"
          ],
          [
            "985-1023",
            "skippable frames"
          ],
          [
            "1233-1471",
            "Huffman weights/direct tree/codes/reverse bitstream"
          ]
        ],
        "ZSTD_SEQUENCE_RLE_SOURCE_ANCHORS": [
          [
            "463-476",
            "RLE tableLog/nbBits zero and literal base values"
          ],
          [
            "657-666",
            "RLE code tables consume one symbol byte"
          ],
          [
            "1192-1200",
            "zero-log tables consume zero initial-state bits"
          ],
          [
            "1299-1304",
            "nonzero literal length/code0 resolves repeat offset1"
          ]
        ],
        "ZSTD_SEQUENCE_RLE_SOURCE_URL": "https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/lib/decompress/zstd_decompress_block.c",
        "ZSTD_SPEC_COMMIT": "f8745da6ff1ad1e7bab384bd1f9d742439278e99",
        "ZSTD_SPEC_URL": "https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md"
      },
      "native_profile_zstd_capacity_oracles_20261012_1.py": {
        "SOURCE_RULES": [
          [
            "#frames",
            "each frame is independent; concatenated output preserves frame order"
          ],
          [
            "#frame_header_descriptor",
            "descriptor00: no FCS, no single-segment, no dictionary/checksum"
          ],
          [
            "#window_descriptor",
            "descriptor50: exponent10/mantissa0 => 1 << 20 bytes"
          ],
          [
            "#blocks",
            "three-byte LE header = (Block_Size << 3) | (Block_Type << 1) | Last_Block"
          ],
          [
            "#blocks",
            "RAW payload has Block_Size bytes; RLE payload has one repeated byte"
          ],
          [
            "#blocks",
            "both physical and regenerated block sizes <= min(window, 131072)"
          ]
        ],
        "ZSTD_COMMIT": "f8745da6ff1ad1e7bab384bd1f9d742439278e99",
        "ZSTD_FORMAT_URL": "https://github.com/facebook/zstd/blob/f8745da6ff1ad1e7bab384bd1f9d742439278e99/doc/zstd_compression_format.md"
      }
    },
    "platform_document_selectors": [
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw",
        "CreateProcessW; CREATE_SUSPENDED; EXTENDED_STARTUPINFO_PRESENT",
        "direct retained process creation"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute",
        "UpdateProcThreadAttribute; PROC_THREAD_ATTRIBUTE_JOB_LIST; PROC_THREAD_ATTRIBUTE_HANDLE_LIST",
        "process-birth job assignment and explicit inherited handles"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information",
        "JOBOBJECT_EXTENDED_LIMIT_INFORMATION; ProcessMemoryLimit; JobMemoryLimit; PeakProcessMemoryUsed; PeakJobMemoryUsed",
        "committed-memory limits versus observations"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information",
        "JOBOBJECT_BASIC_LIMIT_INFORMATION; PerProcessUserTimeLimit; PerJobUserTimeLimit; ActiveProcessLimit; LimitFlags",
        "user CPU and process-count limits"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_process_id_list",
        "JOBOBJECT_BASIC_PROCESS_ID_LIST; NumberOfAssignedProcesses; NumberOfProcessIdsInList; ProcessIdList",
        "complete fresh/pre-resume/final own-job PID observations"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-terminateprocess",
        "TerminateProcess; retained process handle",
        "owned fallback termination; no PID-only target"
      ],
      [
        "https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-peeknamedpipe",
        "PeekNamedPipe; lpTotalBytesAvail",
        "bounded output reads and cap-triggered retained prefix"
      ],
      [
        "https://learn.microsoft.com/en-us/cpp/build/x64-software-conventions",
        "x64 type/storage/alignment conventions",
        "explicit ctypes layout reference, not universal loaded ABI authentication"
      ]
    ],
    "platform_reference_policy": "unversioned_official_document_identifiers_from_held_source_snapshot_not_immutable_or_content_authenticated",
    "source_lookup_policy": "exact_named_path_selector_in_the_stated_commit_or_official_document; no_repository_root_only_layout_claim",
    "historical_declaration_expectation_flags": "authorship_metadata_not_current_runtime_status"
  },
  "runtime_manifest": {
    "artifacts": [
      {
        "kind": "native_extension",
        "logical_id": "dbn_extension",
        "raw_bytes": 3709952,
        "raw_sha256": "c48c57974ca83d68ae67522e6e191e3ae7fe9ae353fe78a59ab020a49cbef64a"
      },
      {
        "kind": "python_module_source",
        "logical_id": "dbn_init",
        "raw_bytes": 763,
        "raw_sha256": "62996cdfe11d8690d6d6d9b7973ae81add3b7864232fd5f56d74e177eee571f7"
      },
      {
        "kind": "python_module_source",
        "logical_id": "dbn_metadata",
        "raw_bytes": 1118,
        "raw_sha256": "a5f7b49b299e6a8a39af190805c83fb12f9346f32892cc0579235764fe24c189"
      },
      {
        "kind": "distribution_metadata",
        "logical_id": "dbn_package_metadata",
        "raw_bytes": 2337,
        "raw_sha256": "9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543"
      },
      {
        "kind": "python_module_source",
        "logical_id": "dbn_v1",
        "raw_bytes": 733,
        "raw_sha256": "71503b977417b9fb7771e32aa1af4422c22db4f3223dafa730bd000974769e30"
      },
      {
        "kind": "python_module_source",
        "logical_id": "dbn_v2",
        "raw_bytes": 682,
        "raw_sha256": "2cc50301be2d0043ebe80dce98baa38ea665b61302ac723db8761cae8d48cc24"
      },
      {
        "kind": "python_module_source",
        "logical_id": "dbn_v3",
        "raw_bytes": 647,
        "raw_sha256": "ef5410748580eadc1f0e69622f0e9eee5e23df0e0e830ef0aeecda1883765d54"
      },
      {
        "kind": "python_executable",
        "logical_id": "python.exe",
        "raw_bytes": 104952,
        "raw_sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
      },
      {
        "kind": "python_runtime_library",
        "logical_id": "python312.dll",
        "raw_bytes": 6945272,
        "raw_sha256": "9a0e3435aaa680d868150f87ab3e388ad2eebc22f87e036155c7b4eda8cd2120"
      },
      {
        "kind": "venv_configuration",
        "logical_id": "pyvenv.cfg",
        "raw_bytes": 325,
        "raw_sha256": "b1a1e44d494a290b40de7b4030ab3852f66b8c31ad89f4851806127f10d2c493"
      },
      {
        "kind": "native_extension",
        "logical_id": "zstd_extension",
        "raw_bytes": 525312,
        "raw_sha256": "2ce792041f2bf7d8a8f514f0fb5adfc7778e56e988491e6ac7f3438c2e8cb3d3"
      },
      {
        "kind": "python_module_source",
        "logical_id": "zstd_init",
        "raw_bytes": 7452,
        "raw_sha256": "5c229d937b3f8420234f3baac08d8abc0ade34a17bbfbbac98fcd4f9349492d6"
      },
      {
        "kind": "distribution_metadata",
        "logical_id": "zstd_package_metadata",
        "raw_bytes": 3339,
        "raw_sha256": "bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c"
      }
    ],
    "interpreter": {
      "executable_sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
      "implementation": "cpython",
      "version": [
        3,
        12,
        10
      ]
    },
    "packages": [
      {
        "metadata_sha256": "9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543",
        "name": "databento-dbn",
        "version": "0.70.0"
      },
      {
        "metadata_sha256": "bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c",
        "name": "zstandard",
        "version": "0.25.0"
      }
    ],
    "schema": "native_profile_runtime_manifest_v1"
  },
  "loaded_associations": [
    {
      "logical_id": "python.exe",
      "module_name": "sys.executable",
      "native": true
    },
    {
      "logical_id": "python312.dll",
      "module_name": "sys.dllhandle",
      "native": true
    },
    {
      "logical_id": "dbn_init",
      "module_name": "databento_dbn",
      "native": false
    },
    {
      "logical_id": "dbn_metadata",
      "module_name": "databento_dbn.metadata",
      "native": false
    },
    {
      "logical_id": "dbn_v1",
      "module_name": "databento_dbn.v1",
      "native": false
    },
    {
      "logical_id": "dbn_v2",
      "module_name": "databento_dbn.v2",
      "native": false
    },
    {
      "logical_id": "dbn_v3",
      "module_name": "databento_dbn.v3",
      "native": false
    },
    {
      "logical_id": "dbn_extension",
      "module_name": "databento_dbn._lib",
      "native": true
    },
    {
      "logical_id": "zstd_init",
      "module_name": "zstandard",
      "native": false
    },
    {
      "logical_id": "zstd_extension",
      "module_name": "zstandard.backend_c",
      "native": true
    }
  ],
  "wire_schema": {
    "schema": "dbn_v3_mbo_complete_wire_schema_v1",
    "byte_order": "little_endian",
    "metadata_fixed_fields": [
      [
        "magic",
        0,
        3,
        "44424e"
      ],
      [
        "version",
        3,
        4,
        "u8=3"
      ],
      [
        "length_body",
        4,
        8,
        "u32"
      ],
      [
        "dataset",
        8,
        24,
        "utf8_cstr16"
      ],
      [
        "schema",
        24,
        26,
        "u16=0"
      ],
      [
        "start",
        26,
        34,
        "u64"
      ],
      [
        "end",
        34,
        42,
        "u64"
      ],
      [
        "limit",
        42,
        50,
        "u64"
      ],
      [
        "stype_in",
        50,
        51,
        "u8"
      ],
      [
        "stype_out",
        51,
        52,
        "u8"
      ],
      [
        "ts_out",
        52,
        53,
        "u8=0_or_1"
      ],
      [
        "symbol_cstr_len",
        53,
        55,
        "u16=71"
      ],
      [
        "reserved",
        55,
        108,
        "53_zero_bytes"
      ],
      [
        "schema_definition_length",
        108,
        112,
        "u32=0"
      ]
    ],
    "metadata_variable_order": [
      "symbols_count",
      "symbols",
      "partial_count",
      "partial",
      "not_found_count",
      "not_found",
      "mappings_count",
      "mappings",
      "alignment_padding"
    ],
    "metadata_variable_rules": {
      "list_count_encoding": "u32",
      "symbol_encoding": "utf8_cstr71",
      "mapping_group_fields": [
        [
          "raw_symbol",
          "utf8_cstr71"
        ],
        [
          "interval_count",
          "u32"
        ],
        [
          "intervals",
          "ordered_complete_intervals"
        ]
      ],
      "mapping_interval_fields": [
        [
          "start_date",
          "u32_yyyymmdd"
        ],
        [
          "end_date",
          "u32_yyyymmdd"
        ],
        [
          "symbol",
          "utf8_cstr71"
        ]
      ],
      "padding": "zero_bytes_until_complete_body_length_is_multiple_of_8",
      "cstring": "strict_utf8_before_first_nul_all_remaining_bytes_zero",
      "duplicate_wire_group_keys": "refuse",
      "interval_multiplicity": "retain"
    },
    "mbo_fields": [
      [
        "length_words",
        0,
        1,
        "u8"
      ],
      [
        "rtype",
        1,
        2,
        "u8=160"
      ],
      [
        "publisher_id",
        2,
        4,
        "u16"
      ],
      [
        "instrument_id",
        4,
        8,
        "u32"
      ],
      [
        "ts_event",
        8,
        16,
        "u64"
      ],
      [
        "order_id",
        16,
        24,
        "u64"
      ],
      [
        "price",
        24,
        32,
        "i64"
      ],
      [
        "size",
        32,
        36,
        "u32"
      ],
      [
        "flags",
        36,
        37,
        "u8"
      ],
      [
        "channel_id",
        37,
        38,
        "u8"
      ],
      [
        "action",
        38,
        39,
        "u8"
      ],
      [
        "side",
        39,
        40,
        "u8"
      ],
      [
        "ts_recv",
        40,
        48,
        "u64"
      ],
      [
        "ts_in_delta",
        48,
        52,
        "i32"
      ],
      [
        "sequence",
        52,
        56,
        "u32"
      ],
      [
        "ts_out",
        56,
        64,
        "u64_only_when_metadata_mode1"
      ]
    ],
    "mbo_length_rules": {
      "mode0": {
        "length_words": 14,
        "complete_bytes": 56,
        "wire_ts_out": null
      },
      "mode1": {
        "length_words": 16,
        "complete_bytes": 64
      },
      "word_bytes": 4
    },
    "metadata_wire_body_schema": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "magic_hex",
          "HexMagic"
        ],
        [
          "version",
          "Three"
        ],
        [
          "length_body",
          "MetadataBodyLength"
        ],
        [
          "dataset",
          "DatasetText"
        ],
        [
          "dataset_cstr_bytes",
          "Sixteen"
        ],
        [
          "schema",
          "Zero"
        ],
        [
          "start",
          "U64"
        ],
        [
          "end",
          "U64"
        ],
        [
          "limit",
          "U64"
        ],
        [
          "stype_in",
          "STypeWireIn"
        ],
        [
          "stype_out",
          "STypeWireOut"
        ],
        [
          "ts_out",
          "ModeByte"
        ],
        [
          "symbol_cstr_len",
          "SeventyOne"
        ],
        [
          "reserved_bytes",
          "ReservedZeros"
        ],
        [
          "schema_definition_length",
          "Zero"
        ],
        [
          "symbols_count",
          "ListCount"
        ],
        [
          "symbols",
          "Symbols"
        ],
        [
          "partial_count",
          "ListCount"
        ],
        [
          "partial",
          "Symbols"
        ],
        [
          "not_found_count",
          "ListCount"
        ],
        [
          "not_found",
          "Symbols"
        ],
        [
          "mappings_count",
          "ListCount"
        ],
        [
          "mappings",
          "WireMappingGroups"
        ],
        [
          "alignment_padding_bytes",
          "AlignmentZeros"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "magic_hex is hex text; all counts/lengths are integers; reserved and alignment are ordered integer-zero tuples, not hex substitutes",
        "each list/group count equals full tuple length",
        "length_body divisible by8 and plus8 equals exact complete header span",
        "C strings have the registered width, strict UTF-8, first NUL terminator and all-zero remainder",
        "alignment zeros have exactly the count needed for the next eight-byte boundary; no unexplained header tail"
      ]
    },
    "mbo_wire_body_schema": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "length_words",
          "MboLength"
        ],
        [
          "rtype",
          "MboRtypeWire"
        ],
        [
          "publisher_id",
          "U16"
        ],
        [
          "instrument_id",
          "U32"
        ],
        [
          "ts_event",
          "U64"
        ],
        [
          "order_id",
          "U64"
        ],
        [
          "price",
          "I64"
        ],
        [
          "size",
          "U32"
        ],
        [
          "flags",
          "U8"
        ],
        [
          "channel_id",
          "U8"
        ],
        [
          "action",
          "U8"
        ],
        [
          "side",
          "U8"
        ],
        [
          "ts_recv",
          "U64"
        ],
        [
          "ts_in_delta",
          "I32"
        ],
        [
          "sequence",
          "U32"
        ],
        [
          "ts_out",
          "NullableU64"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "Metadata mode0 requires length_words14/56 original bytes and wire ts_outNone",
        "Metadata mode1 requires length_words16/64 original bytes and exact appended u64",
        "length multiplier4 is independently source-defined, never inferred from native record_size"
      ]
    },
    "dbn_framing_result_schema": {
      "kind": "record",
      "canonical_type": "object",
      "fields": [
        [
          "complete_bytes",
          "Positive"
        ],
        [
          "wire_spans",
          "WireSpanTriples"
        ],
        [
          "wire_bodies",
          "WireBodies"
        ],
        [
          "field_spans",
          "FieldSpanSets"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "wire_spans,wire_bodies,field_spans have equal complete lengths",
        "all source fields, including count/reserved/padding bytes, covered exactly once in original order; absolute offsets, no overlap/tail",
        "native-free framer shapes match the held independent literal packet, not production output copied as expected"
      ]
    },
    "physical_frame_schema": {
      "kind": "fixed_tuple",
      "items": [
        "public.FrameOrdinal",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.U8",
        "NullableU8",
        "ContentSizeFlag",
        "public.Bool",
        "DictionaryIdFlag",
        "public.Bool",
        "NullableU64",
        "Nonnegative",
        "public.Null",
        "NullableU32",
        "PhysicalBlocks"
      ],
      "extra_items": "refuse",
      "canonical_type": "array",
      "field_names": [
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
        "blocks"
      ],
      "rules": [
        "physical standard magic28b52ffd only; descriptor unused/reserved bits zero",
        "single_segment True implies absent window_descriptor; otherwise exact u8 descriptor",
        "dictionary flag0; dictionary_id=None means no ID field; a flag carrying an ID field refuses even when its value is zero",
        "checksum flag chooses exact u32 checksum_value versus None",
        "physical source bytes fully covered by magic/header/blocks/optional checksum without tail",
        "content_size/window values follow pinned Zstd format; known size/window cap checks are preflight",
        "a physically complete wrong checksum or wrong FCS is not certified consistent output"
      ]
    },
    "physical_block_schema": {
      "kind": "fixed_tuple",
      "items": [
        "BlockOrdinal",
        "public.CompressedOffset",
        "public.CompressedOffset",
        "public.Bool",
        "PhysicalBlockType",
        "Nonnegative",
        "public.CompressedOffset",
        "public.CompressedOffset"
      ],
      "extra_items": "refuse",
      "canonical_type": "array",
      "field_names": [
        "block_ordinal",
        "header_start",
        "header_end",
        "last",
        "block_type",
        "block_size",
        "payload_start",
        "payload_end"
      ],
      "rules": [
        "header_end-header_start=3",
        "raw/compressed payload length=block_size; RLE payload length=1",
        "block_size<=min(window_bytes,131072)",
        "the named last field (fourth tuple item) is an exact bool, not int; no reserved block type"
      ]
    },
    "proof_registry": {
      "source_block_id": "PROOF_SCHEMA_JSON",
      "operation": "parse_entire_json_literal_without_omission"
    },
    "schema_owners": {
      "metadata_wire_body_schema": "profile_body.public_schemas.schemas",
      "mbo_wire_body_schema": "profile_body.public_schemas.schemas",
      "dbn_framing_result_schema": "profile_body.wire_schema.proof_registry.schemas",
      "physical_frame_schema": "profile_body.wire_schema.proof_registry.schemas",
      "physical_block_schema": "profile_body.wire_schema.proof_registry.schemas"
    }
  },
  "logical_schema": {
    "schema": "dbn_v3_complete_logical_schema_v1",
    "metadata_projection": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "version",
          "Three"
        ],
        [
          "dataset",
          "DatasetText"
        ],
        [
          "schema",
          "SchemaMbo"
        ],
        [
          "start",
          "U64"
        ],
        [
          "end_observed",
          "NullableEnd"
        ],
        [
          "limit_observed",
          "NullableLimit"
        ],
        [
          "stype_in",
          "NullableSType"
        ],
        [
          "stype_out",
          "SType"
        ],
        [
          "ts_out",
          "Bool"
        ],
        [
          "symbol_cstr_len",
          "SeventyOne"
        ],
        [
          "symbols",
          "Symbols"
        ],
        [
          "partial",
          "Symbols"
        ],
        [
          "not_found",
          "Symbols"
        ],
        [
          "mappings",
          "MappingGroups"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "raw end0 or18446744073709551615 translates to None; other raw end retains exact positive value",
        "raw limit0 translates to None; other raw limit retains exact positive value",
        "raw stype_in255 translates to None; other codes use exact SType row",
        "raw ts_out0/1 translates to False/True; must equal Context expected_ts_out",
        "schema is exactly MBO; no native nullable-schema admission in this narrow profile",
        "getter mapping groups sorted only in logical body; original wire order remains in MetadataWireBody"
      ]
    },
    "mbo_observation": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "rtype",
          "RtypeMbo"
        ],
        [
          "publisher_id",
          "U16"
        ],
        [
          "instrument_id",
          "U32"
        ],
        [
          "ts_event",
          "U64"
        ],
        [
          "order_id",
          "U64"
        ],
        [
          "price",
          "I64"
        ],
        [
          "size",
          "U32"
        ],
        [
          "action",
          "ActionObservation"
        ],
        [
          "side",
          "SideObservation"
        ],
        [
          "ts_recv",
          "U64"
        ],
        [
          "flags",
          "U8"
        ],
        [
          "channel_id",
          "U8"
        ],
        [
          "ts_in_delta",
          "I32"
        ],
        [
          "sequence",
          "U32"
        ],
        [
          "ts_out_observed",
          "U64"
        ],
        [
          "record_size_observed",
          "RecordSize"
        ],
        [
          "ts_index_observed",
          "U64"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "wire absence maps to native ts_out_observed18446744073709551615, not None",
        "present ts_out is unchanged",
        "record_size_observed equals independently framed56/64 byte record; ts_index_observed equals ts_recv and never sorts or defines an offset",
        "known enum or unknown-character value must match the original raw u8"
      ]
    },
    "metadata_getter_to_projection": [
      [
        "version",
        "version"
      ],
      [
        "dataset",
        "dataset"
      ],
      [
        "schema",
        "schema"
      ],
      [
        "start",
        "start"
      ],
      [
        "end",
        "end_observed"
      ],
      [
        "limit",
        "limit_observed"
      ],
      [
        "stype_in",
        "stype_in"
      ],
      [
        "stype_out",
        "stype_out"
      ],
      [
        "ts_out",
        "ts_out"
      ],
      [
        "symbol_cstr_len",
        "symbol_cstr_len"
      ],
      [
        "symbols",
        "symbols"
      ],
      [
        "partial",
        "partial"
      ],
      [
        "not_found",
        "not_found"
      ],
      [
        "mappings",
        "mappings"
      ]
    ],
    "mbo_getter_to_projection": [
      [
        "rtype",
        "rtype"
      ],
      [
        "publisher_id",
        "publisher_id"
      ],
      [
        "instrument_id",
        "instrument_id"
      ],
      [
        "ts_event",
        "ts_event"
      ],
      [
        "order_id",
        "order_id"
      ],
      [
        "price",
        "price"
      ],
      [
        "size",
        "size"
      ],
      [
        "action",
        "action"
      ],
      [
        "side",
        "side"
      ],
      [
        "ts_recv",
        "ts_recv"
      ],
      [
        "flags",
        "flags"
      ],
      [
        "channel_id",
        "channel_id"
      ],
      [
        "ts_in_delta",
        "ts_in_delta"
      ],
      [
        "sequence",
        "sequence"
      ],
      [
        "ts_out",
        "ts_out_observed"
      ],
      [
        "record_size",
        "record_size_observed"
      ],
      [
        "ts_index",
        "ts_index_observed"
      ]
    ],
    "metadata_kind_discriminator": "Metadata",
    "mbo_kind_discriminator": "MBO",
    "getter_lists": "exact_list_preserved_as_complete_ordered_tuple",
    "getter_mappings": "exact_dict_with_exact_string_keys_and_exact_interval_lists_projected_sorted_by_raw_symbol",
    "native_enum_schemas": {
      "Schema": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "EnumKind"
          ],
          [
            "class_name",
            "EnumClass"
          ],
          [
            "name",
            "EnumName"
          ],
          [
            "code",
            "U16"
          ],
          [
            "text",
            "EnumText"
          ]
        ],
        "extra_fields": "refuse",
        "fixed_values": {
          "kind": "native_enum",
          "class_name": "Schema"
        },
        "allowed_rows": [
          [
            "MBO",
            0,
            "mbo"
          ]
        ],
        "row_fields": [
          "name",
          "code",
          "text"
        ],
        "rules": [
          "name/code/text must match one complete allowed row; no independent mix-and-match",
          "native extraction validates the exact native class before reading name/index/text"
        ]
      },
      "RType": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "EnumKind"
          ],
          [
            "class_name",
            "EnumClass"
          ],
          [
            "name",
            "EnumName"
          ],
          [
            "code",
            "U16"
          ],
          [
            "text",
            "EnumText"
          ]
        ],
        "extra_fields": "refuse",
        "fixed_values": {
          "kind": "native_enum",
          "class_name": "RType"
        },
        "allowed_rows": [
          [
            "MBO",
            160,
            "mbo"
          ]
        ],
        "row_fields": [
          "name",
          "code",
          "text"
        ],
        "rules": [
          "name/code/text must match one complete allowed row; no independent mix-and-match",
          "native extraction validates the exact native class before reading name/index/text"
        ]
      },
      "SType": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "EnumKind"
          ],
          [
            "class_name",
            "EnumClass"
          ],
          [
            "name",
            "EnumName"
          ],
          [
            "code",
            "U16"
          ],
          [
            "text",
            "EnumText"
          ]
        ],
        "extra_fields": "refuse",
        "fixed_values": {
          "kind": "native_enum",
          "class_name": "SType"
        },
        "allowed_rows": [
          [
            "INSTRUMENT_ID",
            0,
            "instrument_id"
          ],
          [
            "RAW_SYMBOL",
            1,
            "raw_symbol"
          ],
          [
            "SMART",
            2,
            "smart"
          ],
          [
            "CONTINUOUS",
            3,
            "continuous"
          ],
          [
            "PARENT",
            4,
            "parent"
          ],
          [
            "NASDAQ_SYMBOL",
            5,
            "nasdaq_symbol"
          ],
          [
            "CMS_SYMBOL",
            6,
            "cms_symbol"
          ],
          [
            "ISIN",
            7,
            "isin"
          ],
          [
            "US_CODE",
            8,
            "us_code"
          ],
          [
            "BBG_COMP_ID",
            9,
            "bbg_comp_id"
          ],
          [
            "BBG_COMP_TICKER",
            10,
            "bbg_comp_ticker"
          ],
          [
            "FIGI",
            11,
            "figi"
          ],
          [
            "FIGI_TICKER",
            12,
            "figi_ticker"
          ],
          [
            "LISTING_ID",
            13,
            "listing_id"
          ],
          [
            "ISSUER_ID",
            14,
            "issuer_id"
          ],
          [
            "SECURITY_ID",
            15,
            "security_id"
          ]
        ],
        "row_fields": [
          "name",
          "code",
          "text"
        ],
        "rules": [
          "name/code/text must match one complete allowed row; no independent mix-and-match",
          "native extraction validates the exact native class before reading name/index/text"
        ]
      },
      "Action": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "EnumKind"
          ],
          [
            "class_name",
            "EnumClass"
          ],
          [
            "name",
            "EnumName"
          ],
          [
            "code",
            "U16"
          ],
          [
            "text",
            "EnumText"
          ]
        ],
        "extra_fields": "refuse",
        "fixed_values": {
          "kind": "native_enum",
          "class_name": "Action"
        },
        "allowed_rows": [
          [
            "MODIFY",
            77,
            "M"
          ],
          [
            "TRADE",
            84,
            "T"
          ],
          [
            "FILL",
            70,
            "F"
          ],
          [
            "CANCEL",
            67,
            "C"
          ],
          [
            "ADD",
            65,
            "A"
          ],
          [
            "CLEAR",
            82,
            "R"
          ],
          [
            "NONE",
            78,
            "N"
          ]
        ],
        "row_fields": [
          "name",
          "code",
          "text"
        ],
        "rules": [
          "name/code/text must match one complete allowed row; no independent mix-and-match",
          "native extraction validates the exact native class before reading name/index/text"
        ]
      },
      "Side": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "EnumKind"
          ],
          [
            "class_name",
            "EnumClass"
          ],
          [
            "name",
            "EnumName"
          ],
          [
            "code",
            "U16"
          ],
          [
            "text",
            "EnumText"
          ]
        ],
        "extra_fields": "refuse",
        "fixed_values": {
          "kind": "native_enum",
          "class_name": "Side"
        },
        "allowed_rows": [
          [
            "ASK",
            65,
            "A"
          ],
          [
            "BID",
            66,
            "B"
          ],
          [
            "NONE",
            78,
            "N"
          ]
        ],
        "row_fields": [
          "name",
          "code",
          "text"
        ],
        "rules": [
          "name/code/text must match one complete allowed row; no independent mix-and-match",
          "native extraction validates the exact native class before reading name/index/text"
        ]
      },
      "UnknownChar": {
        "kind": "record",
        "runtime_type": "exact_registered_frozen_slotted_record",
        "canonical_type": "object",
        "fields": [
          [
            "kind",
            "StringKind"
          ],
          [
            "value",
            "ByteCharacter"
          ]
        ],
        "extra_fields": "refuse",
        "rules": [
          "value code point equals original u8 for a byte not in the corresponding known Action or Side domain"
        ]
      }
    },
    "native_date_schema": {
      "kind": "record",
      "runtime_type": "exact_registered_frozen_slotted_record",
      "canonical_type": "object",
      "fields": [
        [
          "kind",
          "DateKind"
        ],
        [
          "year",
          "Year"
        ],
        [
          "month",
          "Month"
        ],
        [
          "day",
          "Day"
        ]
      ],
      "extra_fields": "refuse",
      "rules": [
        "the triple is a valid Gregorian date and the native source object is exact datetime.date, not datetime or a subclass"
      ]
    },
    "integer_width_schemas": {
      "u8": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "0",
        "maximum_decimal": "255"
      },
      "u16": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "0",
        "maximum_decimal": "65535"
      },
      "u32": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "0",
        "maximum_decimal": "4294967295"
      },
      "u64": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "0",
        "maximum_decimal": "18446744073709551615"
      },
      "i32": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "-2147483648",
        "maximum_decimal": "2147483647"
      },
      "i64": {
        "kind": "int",
        "exact_type": true,
        "minimum_decimal": "-9223372036854775808",
        "maximum_decimal": "9223372036854775807"
      }
    },
    "schema_owner": "profile_body.public_schemas.schemas"
  },
  "public_schemas": {
    "source_block_id": "PUBLIC_PROTOCOL_JSON",
    "operation": "parse_entire_json_literal_without_omission"
  },
  "decoder_options": {
    "dbn": {
      "has_metadata": true,
      "input_version": null,
      "upgrade_policy": "AS_IS",
      "compression": "NONE",
      "ts_out_constructor": false
    },
    "zstd": {
      "backend": "cext",
      "format": "FORMAT_ZSTD1",
      "dict_data": null,
      "max_window_size_argument": 1048576,
      "read_across_frames": false,
      "read_size": 65536,
      "output_read_quantum": 65536,
      "terminal_read_across_frames": false,
      "terminal_allow_extra_data": false,
      "terminal_allocation": "exact_positive_frame_output_length"
    }
  },
  "limits": {
    "compressed_bytes_min": 1,
    "compressed_bytes_max": 262144,
    "decompressed_bytes_max": 1048576,
    "frame_window_bytes_max": 1048576,
    "frame_count_min": 1,
    "frame_count_max": 16,
    "decoded_positions_min": 2,
    "decoded_positions_max": 128,
    "metadata_bytes_min": 128,
    "metadata_bytes_max": 65536,
    "symbols_max": 16,
    "partial_max": 16,
    "not_found_max": 16,
    "mapping_groups_max": 16,
    "mapping_intervals_max": 32,
    "metadata_text_utf8_bytes_max": 128,
    "context_canonical_bytes_max": 65536,
    "evidence_body_canonical_bytes_max": 1048576
  },
  "containment_policy": {
    "schema": "windows_owned_native_proof_containment_v1",
    "limit_flags": 8974,
    "active_process_limit": 1,
    "process_memory_bytes": 268435456,
    "job_memory_bytes": 268435456,
    "process_user_time_100ns": 50000000,
    "job_user_time_100ns": 50000000,
    "work_seconds": 12,
    "total_seconds": 15,
    "teardown_reserve_seconds": 3,
    "output_limit_bytes": 4194304,
    "read_chunk_bytes": 65536,
    "process_birth_job_list": true,
    "create_suspended": true,
    "pre_resume_queried_limits_match": true,
    "pre_resume_exact_job_pid_list": true,
    "pre_resume_identity_match": true,
    "immediate_pre_resume_deadline_reserve": true,
    "retained_handle_exit_required": true,
    "final_job_pid_list_empty": true,
    "final_active_processes_zero": true,
    "cleanup_errors_empty": true,
    "kill_on_job_close_queried": true,
    "parent_death_empirically_tested": false,
    "cpu_limit_exhaustion_empirically_tested": false,
    "successful_job_termination_avoids_immediate_process_fallback": true,
    "filesystem_sandbox": false,
    "network_sandbox": false,
    "total_ram_bound": false,
    "provider_inprocess_containment_inherited": false
  },
  "semantic_proof_cases": {
    "schema_ref": "PROOF_SCHEMA_JSON.schemas.SemanticProofCases",
    "required_junit_count": 211,
    "required_native_input_rows": 125,
    "required_harmless_controls": 6,
    "identity_context_schema_ref": "PROOF_SCHEMA_JSON.schemas.IdentityCore"
  },
  "authorities": [
    [
      "source_authenticated",
      false
    ],
    [
      "collection_receipt_authenticated",
      false
    ],
    [
      "native_runtime_authenticated",
      false
    ],
    [
      "native_abi_authenticated",
      false
    ],
    [
      "native_wire_authenticated",
      false
    ],
    [
      "native_header_authenticated",
      false
    ],
    [
      "native_eof_authenticated",
      false
    ],
    [
      "feed_authenticated",
      false
    ],
    [
      "calendar_authenticated",
      false
    ],
    [
      "historical_read_authorized",
      false
    ],
    [
      "historical_validation_authorized",
      false
    ],
    [
      "book_acceptance_authorized",
      false
    ],
    [
      "event_acceptance_authorized",
      false
    ],
    [
      "feature_acceptance_authorized",
      false
    ],
    [
      "account_authorized",
      false
    ],
    [
      "funding_authorized",
      false
    ],
    [
      "receipt_authorized",
      false
    ],
    [
      "cash_authorized",
      false
    ],
    [
      "margin_authorized",
      false
    ],
    [
      "risk_authorized",
      false
    ],
    [
      "storage_authorized",
      false
    ],
    [
      "resume_authorized",
      false
    ],
    [
      "execution_authorized",
      false
    ],
    [
      "trading_authorized",
      false
    ],
    [
      "training_authorized",
      false
    ],
    [
      "scoring_authorized",
      false
    ],
    [
      "independent_validation_authorized",
      false
    ],
    [
      "promotion_authorized",
      false
    ]
  ],
  "profile_envelope_fields": [
    "profile_body",
    "profile_sha256"
  ],
  "profile_sha256_rule": "H_complete_profile_body_no_self_digest",
  "qualification_receipt_fields": [
    "schema",
    "status",
    "profile_sha256",
    "registration",
    "attempts",
    "complete_regression",
    "preservation",
    "review",
    "limitations"
  ],
  "qualification_receipt_schema": "native_profile_qualification_receipt_v1",
  "qualification_receipt_status": "fully_reconciled_invented_native_proof_not_provider_or_history_acceptance",
  "receipt_semantic_exclusion": "entire_receipt_body",
  "c4_closure_preconditions": [
    "all_P1_P5_required_finite_case_and_resource_evidence_complete",
    "all211_new_assertions_and12206_old_identities_reconciled",
    "exact3_old_full_skip_XML_representations",
    "whole_old_new_package_contract_oracle_native_registration_raw_pins_unchanged",
    "every_owned_attempt_exited_and_failed_attempts_retained",
    "independent_complete_static_C4_review_passed",
    "canonical_profile_and_all_nested_bodies_reconciled_without_cycles"
  ],
  "pending_review_wrapper_fields": [
    "schema",
    "status",
    "proposed_profile_body",
    "proposed_receipt"
  ],
  "pending_review_wrapper_fixed_values": {
    "schema": "native_profile_pending_c4_review_v1",
    "status": "PENDING_C4_NO_POSITIVE_PROFILE_SHA256"
  },
  "pending_review_wrapper_rules": [
    "proposed_profile_body is the COMPLETE assembled16field proposed body for static inspection",
    "conditional qualified status inside proposed_profile_body is a proposed literal, not current qualification acceptance",
    "proposed_receipt has the EXACT final nine-field qualification receipt shape and schema, but status PENDING_C4_NO_POSITIVE_PROFILE_SHA256 and profile_sha256 null",
    "no top-level profile_sha256,closed_profile,positive_closure_receipt or own_digest; no positive nonnull profile digest anywhere in this wrapper",
    "only after C4 accepts exact complete proposedbody and full receipts may qualified profile envelope and final positive receipt be published"
  ],
  "pending_receipt_status": "PENDING_C4_NO_POSITIVE_PROFILE_SHA256",
  "pending_receipt_profile_sha256": null
}
```

## Receipt separation, proof limits and remaining gates

The profile envelope is exactly {profile_body,profile_sha256}; only the complete profile_body is H's input. A separate qualification receipt uses the nine stated fields and schema native_profile_qualification_receipt_v1; its registration/attempts/regression/preservation/review records retain the COMPLETE root-owned receipt objects and raw report identities, not reduced summaries. Its expected status is conditional on actual full reconciliation/static acceptance, never guessed from dots or process presence/absence.

The receipt must link the complete actual native/harmless child outputs, complete owned attempt receipts, all source/oracle/static/registration/whole-old-new-package-contract pins, all31 retained new-window JUnit attempt reports and every failure/error/skip XML, tool exits and all exact owned process/resource/cleanup observations. The historical63 failures include intended RED and the first retained containment defects; they are not current failures. Neither successful subset scoring nor deleting failed attempts is allowed. Current full regression is independently accepted; receipt assembly/static closure is the remaining T12 work.

The fixed containment policy is scoped to this harness's fresh suspended process assigned to a new Job Object at birth, with explicit pre-resume membership/identity/queried limits/deadline reserve and retained-handle teardown. Flags0x230E govern one active child, 256MiB process/job committed memory and five seconds process/job user CPU; work12s/total15s with three-second teardown reserve and 4MiB captured output. Queried kill-on-close is not a measured parent-death guarantee; CPU-limit exhaustion was not separately measured. There is no filesystem/network sandbox, total-RAM claim, parent allocator proof or universal real-time guarantee. **A future in-process byte-only provider does not inherit this process-birth containment.** Its resource architecture remains an implementation blocker; unsafe allocation claims cannot be manufactured from post-checks.

P1–P5 closure is finite for the explicit source versions, narrow schemas, constructed limits, declared policies and complete registered case corpus. It is not all-format/native-ABI equivalence, complete import/DLL/memory/build authentication, adversarial parser universality or a security health audit. Fixed package/binary/source-reference equality does not prove the binaries were built from those upstream commits. Coherent caller whole-context/expectation replacement is unauthenticated and not detected.

Public A1–A15 provider phase/preflight/atomicity/canonical-cap/submitted-verification acceptance remains **UNIMPLEMENTED**. Causal publication needs actually consumed-prefix/header/context binding while excluding future terminal/member/runtime/total state. Native/source/archive intake needs separately registered full-member/full-cohort/source receipts; historical row parity/calendar/full capacity and one-genesis multi-session continuity remain later gates. No adapter coercion into held instrument/genesis/window/signed transport, thinning/truncating/splitting/resampling/relabeling history synthetic, future-terminal stitching or successful subset adoption is allowed.

All 28 top authority names in PUBLIC_PROTOCOL_JSON remain ordered literal-False pairs in the profile; no authentication/account/funding/receipt/cash/margin/risk/storage/resume/execution/trading/training/scoring/independent-validation/promotion authority changes. No late fill, UNKNOWN cancellation/reconciliation, reseed/daily reset, old-fill filtering, broker economics, profitable strategy or model improvement follows. BTC/cloud collectors and Windows/security settings remain untouched; no App Security causation is claimed.

## Current declaration pins and evidence navigation

Use the **formatted frozen** source declarations, not the candidate's earlier raw source hashes:

| Packet | Raw bytes | Raw SHA256 |
| --- | ---: | --- |
| [Primary](../tests/native_profile_oracles_20261012_1.py) | 90,741 | 4314a212d8e62047ab92b56028784b3914975391e2a2cbe78dee2bb7c7793ba4 |
| [Enums](../tests/native_profile_enum_oracles_20261012_1.py) | 18,668 | a27abb7efaece7797e22fd147f9dfbc2c29d5e79ee4c4058c440173ef91596ec |
| [Composed](../tests/native_profile_composed_oracles_20261012_1.py) | 15,746 | fbb532130c6ac49ba05b1011baaf586e4f29939628d053cc47f450cff87159f8 |
| [Native direct/empty/terminal](../tests/native_profile_native_negative_oracles_20261012_1.py) | 29,618 | d5db004581c115eb02194dd355b3a789024d670e038f8a01f05a6229b675cb3f |
| [DBN capacity](../tests/native_profile_capacity_oracles_20261012_1.py) | 41,001 | 739b81a4cca047d1f55c480bba4d0e6bf9597dd6ccc16b3e164c83f339459bcf |
| [Zstd cumulative/input capacity](../tests/native_profile_zstd_capacity_oracles_20261012_1.py) | 7,329 | 17c91e7c6697df7f95b05fc5dbf25083fe486501afc06d008f793ac93b6193f4 |

The [source decision packet](6E_NATIVE_PROFILE_REFERENCES_20261012_1.md) gives pinned official Rust/C/format URLs; the [slice ledger](../logs/native_profile_20261012_1/native_slice_design.md) retains actual intended RED/GREEN and limitations; the [current execution board](../tasks/native_profile_execution_20261012.md) governs current T12. No completed native/test/control example is rerun for documentation status.

This single annex uses the installed documentation and API/interface skills to make hashes, shapes, refusal semantics and resource boundaries explicit. It creates no execution plan or source release. Save/static review/profile assembly must finish honestly within the unchanged19:59:46Z hard end; at/after it launch nothing, retain verified work/gaps and stop.

