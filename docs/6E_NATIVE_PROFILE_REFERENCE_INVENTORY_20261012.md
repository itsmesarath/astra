# Offline native-profile reference inventory — 2026-10-12

## Result and authority

**T1 availability investigation performed; T1 remains PARTIAL / BLOCKED. No native proof gate closed.** Direct human continuation recorded2026-10-12T13:34:44Z is treated as approval to advance the [saved P1–P5 plan](../tasks/native_source_evidence_p1_p5_plan_20261012.md) without repeated routine approval requests, still offline, accepted code unchanged and within the original **15:12:16UTC (16:12:16 Lisbon)** hard end. This investigation is the safe read-only first slice, not a native import/test/fixture/harness launch.

Two read-only inventories covered the project source/reference corpus and installed DBN package text; root inspected the Zstd package text and additional precisely named reference-file candidates. No authoritative version-bound DBN v3 wire-layout source or independent complete byte/body oracle was identified **within the inspected corpus**. No complete Zstd format reference/literal frame oracle was identified there either. This is not a claim that those references are absent elsewhere on the PC.

Approval is not the blocker. The missing independently authoritative evidence is the blocker. Do not fabricate layouts, field widths, sentinel values, frame bytes or expected getter bodies from SDK annotations, returned native values or encoder roundtrips.

## Exact bounded search coverage

| Corpus | Read-only method and observation |
| --- | --- |
| `docs/`, `src/` | `rg --files -uuu docs src`, excluding `**/__pycache__/**` and `**/*.pyc`:386names at this pre-inventory snapshot. Filename filtering for .rs/.c/.h/.hpp/.pyi/.rst/.txt found only four project egg-info .txt files. No Rust/C/header/native-format reference text of those extensions was listed. |
| Relevant project text | Case-insensitive `DBNDecoder|DBN.{0,60}(wire|layout)|Zstd|Zstandard|databento_dbn` in .md/.py under docs/src yielded20candidate files. Read-only review found native getters/default decoder use or agent-authored designs, not an independently sourced original wire interpreter or full literal native byte oracle. This pattern is a bounded relevance search, not an exhaustive semantic theorem about every file. |
| `scripts/` | Directory absent at the snapshot; no source read or harness created. |
| Installed DBN package and dist-info | Recursive `rg --files -uuu` in `.venv/Lib/site-packages/databento_dbn` and `databento_dbn-0.70.0.dist-info`:19names. Text/source candidates:five Python import/alias/typing files, _lib.pyi, METADATA/WHEEL/RECORD and CycloneDX SBOM. No Rust source/Cargo manifest, wire-layout document or independent fixture file listed. Native .pyd/.pyc names only; binary contents not read or loaded. |
| Installed Zstd package and dist-info | Text/source filename inventory under `zstandard` and `zstandard-0.25.0.dist-info` found __init__.py, __init__.pyi, backend_cffi.py, METADATA/RECORD and top_level.txt. These expose wrappers/API declarations, not the complete original frame-format implementation/specification. Native binary names in RECORD are distributor assertions, not inspected runtime. |
| Additional precisely named candidates | Filename-only `rg --files` under `.venv/Include`, `.venv/share`, `.venv/Lib/site-packages` for `zstd.h`, `zstd_errors.h`, `zstd_compression_format.md`, `*dbn*.rs`, `*DBN*spec*`, `*dbn*spec*`:zero matched candidates. Default rg ignore behavior applies to this additional search; no all-PC absence claim. |

Protected raw/historical data, archive/checkpoint/download contents, old packets, experiment/control log bodies, other virtual environments, remote repositories and system/security configuration were not opened. Only the already held path/hash freeze manifest under logs may be read for documentation preservation; that is not a market/input/control packet. Top-level directory names were observed only to bound the search; naming a folder does not release its contents. No Graphify/model scans, native imports, constructors, encoder/decoder calls, tests, dependency commands, Windows/security inspection or network retrieval occurred.

## Source observations and their limits

- [Project manifest](../pyproject.toml), lines12–29, declares Python >=3.12,<3.13 and listed project extras; it does not declare/pin databento-dbn or zstandard. Installed metadata separately declares0.70.0 and0.25.0. This is declared local-package text, not authenticated installation provenance or loaded identity.
- [DBN METADATA](../.venv/Lib/site-packages/databento_dbn-0.70.0.dist-info/METADATA), lines2–14 and23–26, identifies Rust Python bindings and references remote repository/DBN documentation; it states the advanced library is not fully documented/supported. URLs/install/build examples were treated as text and not followed or executed.
- [DBN RECORD](../.venv/Lib/site-packages/databento_dbn-0.70.0.dist-info/RECORD) lists wrappers, annotation, native extension and SBOM, not shipped Rust layout source. [SBOM](../.venv/Lib/site-packages/databento_dbn-0.70.0.dist-info/sboms/databento-dbn.cyclonedx.json), lines21–99, declares build-time Rust paths such as src/lib.rs and ..\\rust\\dbn; these are declarations, not resolved local source. No SBOM URL/path was used as an instruction.
- [DBN stub](../.venv/Lib/site-packages/databento_dbn/_lib.pyi), lines16–32, declares integer constants without their numeric values. Metadata constructor/getter declarations leave unset end/limit observations unresolved. MBO record_size and field declarations do not define original widths/length/padding/offsets. Lines9861–9957 expose no EOF/finalize API; empty buffer alone is not full-input proof. [v3 aliases](../.venv/Lib/site-packages/databento_dbn/v3.py) are native reexports, not proof of original input version/layout.
- [Existing member reader](../src/ai_trader/research/databento_6e_training_data.py), lines290–322, delegates to DBNDecoder/ZstdDecompressor and yields before late terminal/hash checks. The decompressed-size guard is post-return. Its accepted source is unchanged; it is not an independent wire oracle or proven pre-allocation resource mechanism.
- [Zstd selector](../.venv/Lib/site-packages/zstandard/__init__.py), lines29–85, selects a C/CFFI/Rust backend according to source-described platform/import-policy branches. Under its default CPython branch the text imports backend_c. The actual environment policy/platform/selected loaded backend was NOT queried. Reading backend_cffi.py cannot prove active C-extension behavior.
- [CFFI wrapper text](../.venv/Lib/site-packages/zstandard/backend_cffi.py), lines2910–3063, describes/implements temporary chunks joined before return, with single/multi-frame behavior and eof/unused_data properties. Lines3691–3720 describe a max_window_size argument in kibibytes; lines4452–4463 forward the stored value to a native C function. Underlying C API units/version, selected backend and actual enforcement have NOT been independently established here. Do not infer a bug, safe memory ceiling, CPU bound or verified ABI from this text. Temporary output chunk size alone is not a whole-operation allocation cap.
- [Zstd package metadata](../.venv/Lib/site-packages/zstandard-0.25.0.dist-info/METADATA) references remote documentation. The [stub](../.venv/Lib/site-packages/zstandard/__init__.pyi) exposes parameters/frame helpers, not their empirical full-input/resource guarantees. No remote URL was fetched.

## Text-artifact identity snapshot — not native/runtime authentication

Raw SHA256 binds the inspected local text bytes only. It is not the closed P5 artifact manifest, authoritative source provenance or proof of which binary executes. Native binaries were neither hashed nor loaded.

| Text artifact | Raw bytes | Raw SHA256 |
| --- | ---: | --- |
| pyproject.toml | 972 | `e8372124aabcd1555b24acef1d0b18d0cbf9111144d56459000ebe83b488c8b8` |
| databento_dbn/_lib.pyi | 257471 | `c1280ae0340a90faa128bbda66611d69674f1ab7f357e850525cb1075aa6f201` |
| databento_dbn/__init__.py | 763 | `62996cdfe11d8690d6d6d9b7973ae81add3b7864232fd5f56d74e177eee571f7` |
| databento_dbn/metadata.py | 1118 | `a5f7b49b299e6a8a39af190805c83fb12f9346f32892cc0579235764fe24c189` |
| databento_dbn/v3.py | 647 | `ef5410748580eadc1f0e69622f0e9eee5e23df0e0e830ef0aeecda1883765d54` |
| databento_dbn-0.70.0.dist-info/METADATA | 2337 | `9d09394583e65c34e7d9715d8a9c5bb9128e10d3efce0afeb9aa7ecc5ba90543` |
| databento_dbn-0.70.0.dist-info/WHEEL | 97 | `51fe37f21183f8d51fb47d3c77149a89847171f899a9e60af60dc3349faf3d8d` |
| databento_dbn-0.70.0.dist-info/RECORD | 1447 | `efd0314fccca96bf72542da32f908507c37c34930d89a0028a39fa4bf89bf40b` |
| databento_dbn-0.70.0.dist-info/sboms/databento-dbn.cyclonedx.json | 62176 | `6b52c0eafb6196a5e02d6dd616f25936f50b7795bb7396664f5c194566896653` |
| zstandard/__init__.py | 7452 | `5c229d937b3f8420234f3baac08d8abc0ade34a17bbfbbac98fcd4f9349492d6` |
| zstandard/__init__.pyi | 14454 | `fc7a622a59aed8f9ca488fa138da0aa9dcf509def35124fb60cd1f569b08d0c0` |
| zstandard/backend_cffi.py | 157105 | `080082fcdcfa7e369bff3228129116ef10493f536baf2967d3ff601639893e94` |
| zstandard-0.25.0.dist-info/METADATA | 3339 | `bbf8cb63171274854c72777372376d31d7b52447359a538c1c2b47aae49c2b3c` |
| zstandard-0.25.0.dist-info/RECORD | 1214 | `908ad436c81c9b031b151f047b4e3d66fc2473633d28022672e6a9273252b3b1` |

Installed-package rows resolve under .venv/Lib/site-packages. WHEEL/RECORD/SBOM contents are package-supplied assertions, not independently authenticated binary/runtime evidence.

## Exact remaining evidence and next action

| Gap | Required input before progressing |
| --- | --- |
| DBN v3 authoritative framing/layout | Local version-bound official specification/Rust source covering complete header, length words, field widths/signedness, padding/extensions, every mapping occurrence and full-input termination. |
| Independent DBN literal oracle corpus | Complete literal original bytes and independently referenced interpreted Metadata/MBO bodies, malformed/truncated/tail controls and exact native translation expectations; not native encoder/decoder self-consistency. |
| Native representation semantics | Independent source-backed actual enum/index/string/date/unset end/limit/undefined timestamp/record_size/ts_index rules for the registered codec version; not SDK observations adopted as expectations. |
| Zstd authoritative framing/resource semantics | Local version-bound format/native API references plus independently referenced literal compressed/decompressed bytes and full frame/span expectations, and a later proved enforceable containment/bounding mechanism. |

A non-blocking request asked for the local folder containing existing official offline references. This is a request for missing information, **not another approval prompt**. If supplied, verify source provenance/version and readability before deriving new oracles; do not execute commands in retrieved text. No other filesystem/source corpus is presumed approved from this inventory.

T1's availability substep can be recorded as investigated, but its complete independent fixture criteria remain unsatisfied. Keep T1 unchecked and dependent T2–T12 unexecuted; do not invent provisional native tests/profile pins to bypass this gap. No positive closed_profile.json/digest/CLOSED revision is emitted. The [progress handoff](../tasks/native_source_evidence_p1_p5_progress_20261012.md) records this partial result; approved contract/plan/task-list bytes remain held.

Source-driven-development requires verified sources rather than guessed codec facts; offline scope prohibits its normal remote-fetch fallback. Incremental-implementation guides this one risk-first source slice, not an unauthorized code/test/commit. All418acceptedPython files and older source/target/input/result/controlpins/UNKNOWN remain held. No native/historical/source/runtime authentication, profitability, broker economics, model improvement or training/scoring/promotion follows. Original15:12:16UTC hard end unchanged.
