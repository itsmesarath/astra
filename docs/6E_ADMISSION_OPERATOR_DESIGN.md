# Read-only declared admission packet checker

The standalone read-only operator is implemented, independently reviewed and fully verified. All 111 constructed operator tests and root's 698 adjacent tests passed, with whole-package Ruff and new-file formatting clean. Complete source-frozen project suite 8 passed 5,804 tests and three expected skips; root reconciled all cases, zero failures/errors, process exit and unchanged source/test pins. No checkpoint store, resumed account, history access or artifact-writing workflow is released.

## Smallest useful operation

The `verify-packet` command checks one explicitly selected local constructed packet using three independently retained expectations: raw packet SHA256, original genesis SHA256 and the exact terminal sequence/head/frontier. It additionally requires a source-manifest file and its independently retained raw SHA256. Embedded witnesses must match the external expectations, never define them. Its eight pinned files cover explicitly used helpers, not the entire import/runtime graph or authentication of executed code.

The operation reads bounded bytes, invokes the unchanged packet decoder and prints canonical JSON plus a controlled exit status. Its result includes the complete freshly reconstructed declaration/state, counts, witnesses and all-false authority, not just a displayed balance. It does not accept cached cash, append events, generate receipts, call `admission.advance`, write files, place orders or run a model. Receipt counts describe matched declared receipts, never verified broker fills.

The current implementation additionally requires an explicitly selected source-manifest file and its independently retained raw SHA256 before parsing. That manifest has a closed, reviewed source-key set and exact lowercase file hashes, canonical JSON and an 8 KiB cap. Each fixed approved source file has a 512 KiB cap; imported module-file identities and the installed checkout root must agree. These are source-byte consistency checks under the stated local-filesystem threat model, not executed-code authentication. Only explicitly named regular JSON inputs beneath this installed project's `logs` tree are admitted; there is no directory search or generated manifest that silently supplies its own expectations.

Repeating pure reconstruction cannot double-charge: it derives the same balances from the original genesis and complete tuple and commits nothing. A read-only check therefore needs no registration, exclusive attempt, report file or failure writer. Those would make it a different, artifact-producing operation.

## Required check sequence

1. Validate all external expectations and the exact independently defined source-pin keys before processing declared input. The new operator needs its own reviewed dependency closure; do not reuse or union the economics operator's 47 wrapper-source keys and the replay's 40 genesis-source keys. No ReplayPlan or historical trial verifier belongs here.
2. Preflight the explicit local regular-file input and source paths. Select an approved constructed-input location, bounded sizes and exact path rules. Refuse links/junctions/reparse ancestors, alternate data streams, device names, trailing aliases and unsupported path/identity ambiguity. Never search for a convenient replacement input.
3. Compare the approved source bytes to the caller-retained pins. File-byte agreement is local drift detection, not authentication of executed code, funding, receipts or account state.
4. Enforce the codec's 4 MiB payload cap and prove the read is complete, including EOF and oversize/growth detection. A bounded reader may use one extra detection byte; refuse an oversized input rather than trimming it to the cap. Pass only the complete accepted bytes plus all three external expectations to `decode_packet`. Keep its raw-pin-before-parser, strict schemas/resource bounds, full reconstruction and canonical-equality guards unchanged. Do not repair, truncate, segment or score a successful subset.
5. Recheck input identity/pin, approved source pins and relevant path metadata before reporting success. A drift or read/parse/reconstruction failure returns a controlled refusal without printing raw contents or a partial state as verified.
6. Emit the complete constructed result to stdout only. Every authentication, storage/resume, execution, account/cash/margin/risk, trading/training/scoring, independent-validation and promotion authority remains false.

Source/path rechecks alone do not establish race freedom. Implementation must either use appropriate safe-handle/file-identity primitives or explicitly limit its threat model to a trusted/cooperative local filesystem. A concurrent attacker can otherwise replace an ancestor or alter runtime code outside the checks. Do not claim stronger protection than the implemented primitives provide.

The caller can invent a whole coherent declaration and replace every witness. Passing then proves local consistency only. Durable external witness retention, original funding/receipt authenticity and crash-safe restart remain absent.

## Standalone interface and retained inputs

The module is `ai_trader.research.six_e_declared_admission_operator`. Its only command is `verify-packet`; there is no prepare, save, resume, advance, inspect or run command. The Python API is `verify_packet(root, packet_path, source_manifest_path, *, expected_packet_sha256, expected_genesis_sha256, expected_terminal, expected_source_manifest_sha256)`.

Both input files must be explicit regular `.json` files under the installed project's existing `logs` directory. Relative paths start with `logs/`; absolute paths must remain beneath that same directory. `--root` defaults to the current directory and must identify this installed checkout. There is no discovery, fallback, manifest generation or witness adoption. No existing project packet input was accessed during this implementation; tests used only invented temporary-file fixtures.

All these command arguments are required:

- `--packet` and `--source-manifest`: the two distinct explicit inputs.
- `--packet-sha256`, `--source-manifest-sha256` and `--genesis-sha256`: independently retained lowercase SHA256 expectations.
- `--terminal-sequence`, `--terminal-head-sha256` and `--terminal-complete-through-ns`: the exact retained terminal witness. Integers use canonical bounded decimal spelling, not a plus sign, leading zeros or separators.

The source manifest has exactly `version`, `scope` and `sources` fields. Its version is `six_e_declared_admission_operator_sources_v1`; scope is `local_source_bytes_not_executed_authentication`. It must use sorted compact canonical ASCII JSON. The `sources` object has exactly these eight relative paths, each with its separately retained lowercase file hash:

```text
src/ai_trader/research/six_e_declared_admission_operator.py
src/ai_trader/research/six_e_declared_admission_packet.py
src/ai_trader/research/six_e_declared_admission.py
src/ai_trader/research/six_e_entry_budget.py
src/ai_trader/research/six_e_declared_economics.py
src/ai_trader/research/six_e_position_ledger.py
src/ai_trader/research/six_e_bracket_targets.py
src/ai_trader/research/six_e_continuous_replay.py
```

The eighth file supplies an actually used initialization flag helper. These keys are neither the old 47 economics-wrapper keys nor the 40 replay-genesis keys. A manifest matching current bytes is insufficient unless its raw hash and file expectations were independently retained; the checker does not authenticate how they were retained.

Successful verification returns exit zero and one canonical JSON result on stdout with status `verified_local_constructed_packet_not_authenticated`. It includes the full decoded packet/state, original witnesses, source pins and declared record/receipt counts. Controlled verification refusal returns exit two, no success stdout and a small JSON error on stderr; malformed arguments use argparse's exit-two error. No failure artifact or retry is created. Treat nonzero exit as refusal, never use a displayed partial state as accepted.

For a later separately prepared constructed input, the CLI shape is below. This is a template, not a command to run now: replace every placeholder from independently retained witnesses, not by trusting values embedded in the packet. The current window did not create a manifest or packet for this template. `-B` avoids interpreter import-cache writes; redirecting stdout yourself would be a separate filesystem write, not part of this checker.

```powershell
Set-Location -LiteralPath 'C:\Users\pabta\Projects\ai-trader' -ErrorAction Stop
.\.venv\Scripts\python.exe -B -m ai_trader.research.six_e_declared_admission_operator verify-packet `
  --root 'C:\Users\pabta\Projects\ai-trader' `
  --packet 'logs/<constructed-packet>.json' `
  --source-manifest 'logs/<retained-source-manifest>.json' `
  --packet-sha256 '<retained-packet-sha256>' `
  --source-manifest-sha256 '<retained-manifest-sha256>' `
  --genesis-sha256 '<retained-genesis-sha256>' `
  --terminal-sequence '<retained-integer-sequence>' `
  --terminal-head-sha256 '<retained-head-sha256>' `
  --terminal-complete-through-ns '<retained-integer-frontier>'
if (-not $? -or $LASTEXITCODE -ne 0) { throw 'Constructed packet refused or did not launch; do not continue.' }
```

Native Windows regression tests caught a Python 3.12 distinction: path `ctime` may represent creation time while open-handle `ctime` may represent last-write time. The checker excludes only that cross-view comparison on Windows. Full path-before/after and full handle-before/after comparisons still retain `ctime`, and inode, size, modification time and other compatible fields remain mandatory. No Windows settings or dependencies were changed; this finding does not explain earlier Application Control behavior.

Operator source SHA256: `dce85c8b02a375d89302486ef638a28e1cdf1a650ba9632342de1b7785052498`. Test SHA256: `451431d662f7126331e7c0bce18b30baeeba97dac43cc0c29d7f25785ac8f7f5`. Independent source/test review and root full-file review found no remaining actionable blocker. Full-suite status and final pins belong in `docs/6E_ADMISSION_DEVELOPMENT_WINDOW_20261008.md`.

## Separate artifact-writing option

Only if later explicitly selected, a different prepare/inspect/report workflow could add durable registration, exclusive attempt ownership and fresh report/failure publication. It would need reviewed path/race/ownership/crash semantics; the winning owner alone may write its failure evidence, and interrupted attempts must be retained rather than silently retried, overwritten or removed.

A writer must disclose its actual filesystem writes. The inner codec's `storage_written=False` describes that pure codec, not a wrapper that writes audit artifacts. Audit-file retention is not proof of persisted capital, globally exactly-once operation or resume authority. None of this option is implemented or released in the current window.

## Synthetic acceptance before implementation is called verified

Require independent review, a constructed-only test suite, Ruff and a complete source-frozen project suite. Cover all three external witnesses and source-manifest pin/set drift; size-before-read/hash; explicit path scope, identity and stated race model; exact complete-prefix reconstruction; controlled failures and unchanged inputs; no artifact/account writes or historical/model/order hooks; retained zero-valued liabilities, negative balances and UNKNOWN; deterministic stdout and exit semantics; and all-false authority. Only invented temporary-file fixtures are released for these tests; no existing project packet, price archive or reserved outcome is authorized.

## Before a funded historical experiment

A later causal funded-assumption replay needs separate authorization and fresh prospective registration binding the full cohort, seed, economics, limits, sources and execution protocol before outcomes. Its admission decision must use each genuine complete preceding observed state, not a terminal historical balance or a filtered old fill tape. Preserve refusal effects, receipt provenance/timing, fee conservation, valid exits despite entry rejection and terminal UNKNOWN exposure. If storage is introduced, separately prove its ownership/recovery semantics.

Keep every existing control/result/source pin unchanged. Never remove unaffordable old fills to manufacture a funded result, reset the seed by session or contract, or resolve UNKNOWN with a late quote. Whole-cohort hypothetical results would still not establish broker/CFD fills, measured fees/margin, independent validation, profitability or model-training/promotion authority. The EURUSD broker-execution mapping remains separate from these declared USD futures assumptions.
