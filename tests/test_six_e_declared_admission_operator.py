"""Read-only operator tests; only constructed temporary packets/source metadata."""

import io
import json
import os
import socket
import sqlite3
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_trader.research import six_e_declared_admission as admission
from ai_trader.research import six_e_declared_admission_operator as operator
from ai_trader.research import six_e_declared_admission_packet as packet
from ai_trader.research import six_e_declared_economics as economics
from ai_trader.research import six_e_entry_budget as budget
from ai_trader.research import six_e_liquidity_status as reader

START = 1_000_000_000_000
DELAY = 100_000_000
SECOND = 1_000_000_000
PRICE = 1_000_000_000
TICK = economics.ledger.target.TICK


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def pin(raw):
    return sha256(raw).hexdigest()


def constructed(kind="OPEN"):
    zero = kind == "ZERO_UNKNOWN"
    genesis = admission.DeclaredAdmissionGenesis(
        "synthetic-operator",
        economics.EconomicSeed(135, START),
        economics.DeclaredEconomics(
            "USD",
            125,
            0 if zero else 10,
            0 if zero else 20,
            economics.DeclaredMargin(0, 0) if zero else economics.DeclaredMargin(100, 80),
        ),
        budget.DeclaredBudgetLimits(0 if zero else 5, SECOND, None),
    )
    identity = admission.genesis_sha256(genesis)
    terminal = admission.DeclaredPrefix(0, identity, START)
    records = ()
    payloads = []
    if kind != "EMPTY":
        payloads.append((START, admission.AdmissionRequested("admission-1", "6EM5", "long", 1)))
    if kind == "UNFILLED":
        payloads.append((START + DELAY + SECOND, admission.EntryUnfilled("admission-1", "timeout")))
    elif kind not in ("EMPTY", "ENTRY_PENDING"):
        at = START + DELAY
        payloads.append(
            (at, admission.EntryReceipt("admission-1", "entry-1", "6EM5", "long", 1, PRICE, at))
        )
        if kind not in ("OPEN",):
            payloads.append((at, admission.ExitRequested("admission-1", "exit-1")))
            if kind in ("EXIT_UNKNOWN", "ZERO_UNKNOWN"):
                payloads.append((at + DELAY + SECOND, admission.ExitUnknown("exit-1")))
            elif kind != "EXIT_PENDING":
                at += DELAY
                payloads.append(
                    (
                        at,
                        admission.ExitReceipt(
                            "exit-1",
                            "close-1",
                            "6EM5",
                            1,
                            PRICE - 3 * TICK if kind == "NEGATIVE_CLOSED" else PRICE,
                            at,
                        ),
                    )
                )
    for at, payload in payloads:
        record = admission.DeclaredRecord(f"event-{len(records) + 1}", terminal, at, at, payload)
        result = admission.advance(
            genesis, records, record, expected_genesis_sha256=identity, expected_terminal=terminal
        )
        records, terminal = result.records, result.state.prefix
    state = admission.reconstruct(
        genesis, records, expected_genesis_sha256=identity, expected_terminal=terminal
    )
    raw = packet.encode_packet(
        genesis, records, expected_genesis_sha256=identity, expected_terminal=terminal
    )
    return SimpleNamespace(
        genesis=genesis,
        records=records,
        terminal=terminal,
        state=state,
        raw=raw,
        genesis_pin=identity,
    )


@pytest.fixture
def tree(tmp_path, monkeypatch):
    root = tmp_path / "installed"
    (root / "logs").mkdir(parents=True)
    modules, sources = {}, {}
    for index, relative in enumerate(sorted(operator.SOURCE_NAMES)):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = f"# constructed code-metadata {index}\n".encode("ascii")
        path.write_bytes(raw)
        modules[relative] = SimpleNamespace(__file__=str(path))
        sources[relative] = pin(raw)
    own = next(
        relative
        for relative in operator.SOURCE_NAMES
        if relative.endswith("six_e_declared_admission_operator.py")
    )
    monkeypatch.setattr(operator, "__file__", str(root / own))
    monkeypatch.setattr(operator, "SOURCE_MODULES", modules)
    value = constructed()
    packet_path = root / "logs" / "synthetic_packet.json"
    packet_path.write_bytes(value.raw)
    manifest_path = root / "logs" / "synthetic_sources.json"
    manifest = {
        "version": "six_e_declared_admission_operator_sources_v1",
        "scope": "local_source_bytes_not_executed_authentication",
        "sources": sources,
    }
    manifest_path.write_bytes(canonical(manifest))
    result = SimpleNamespace(
        root=root,
        packet_path=packet_path,
        manifest_path=manifest_path,
        manifest=manifest,
        value=value,
        modules=modules,
    )

    def verify(**changes):
        arguments = {
            "root": result.root,
            "packet_path": result.packet_path,
            "source_manifest_path": result.manifest_path,
            "expected_packet_sha256": pin(result.value.raw),
            "expected_genesis_sha256": result.value.genesis_pin,
            "expected_terminal": result.value.terminal,
            "expected_source_manifest_sha256": pin(canonical(result.manifest)),
        }
        arguments.update(changes)
        return operator.verify_packet(**arguments)

    result.verify = verify
    return result


def snapshot_tree(root):
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(
    "kind",
    [
        "EMPTY",
        "ENTRY_PENDING",
        "OPEN",
        "EXIT_PENDING",
        "EXIT_UNKNOWN",
        "ZERO_UNKNOWN",
        "UNFILLED",
        "CLOSED",
        "NEGATIVE_CLOSED",
    ],
)
def test_full_constructed_verification_is_repeatable_and_writes_nothing(tree, kind):
    tree.value = constructed(kind)
    tree.packet_path.write_bytes(tree.value.raw)
    before = snapshot_tree(tree.root)
    first, second = tree.verify(), tree.verify()
    assert first == second
    assert first.supplied_record_count == len(tree.value.records)
    assert first.matched_receipt_count == sum(
        type(record.payload) in (admission.EntryReceipt, admission.ExitReceipt)
        for record in tree.value.records
    )
    assert first.decoded_packet.reconstructed_state == tree.value.state
    assert first.decoded_packet.records == tree.value.records
    assert first.expected_genesis_sha256 == tree.value.genesis_pin
    assert first.expected_terminal == tree.value.terminal
    assert dict(first.source_pins) == tree.manifest["sources"]
    flags = dict(first.authority_flags)
    assert flags and all(value is False for value in flags.values())
    assert first.decoded_packet.reconstructed_state.phase == tree.value.state.phase
    assert snapshot_tree(tree.root) == before
    assert not any("attempt" in name or "failure" in name or "report" in name for name in before)


@pytest.mark.parametrize(
    "field",
    ["expected_packet_sha256", "expected_genesis_sha256", "expected_source_manifest_sha256"],
)
def test_independent_raw_genesis_and_manifest_pins_are_never_self_adopted(tree, field):
    with pytest.raises(operator.OperatorError):
        tree.verify(**{field: "a" * 64})


@pytest.mark.parametrize("field", ["sequence", "head_sha256", "complete_through_ns"])
def test_independent_exact_terminal_witness_is_not_replaced_by_packet(tree, field):
    changed = "a" * 64 if field == "head_sha256" else getattr(tree.value.terminal, field) + 1
    with pytest.raises(operator.OperatorError):
        tree.verify(expected_terminal=replace(tree.value.terminal, **{field: changed}))


@pytest.mark.parametrize(
    "change",
    ["extra", "missing", "scope", "version", "pin", "wrong_shape", "noncanonical", "duplicate"],
)
def test_source_manifest_is_pinned_canonical_exact_closed_schema(tree, change):
    manifest = deepcopy(tree.manifest)
    if change == "extra":
        manifest["sources"]["src/ai_trader/research/unapproved.py"] = "a" * 64
    elif change == "missing":
        del manifest["sources"][next(iter(manifest["sources"]))]
    elif change in ("scope", "version"):
        manifest[change] = "different"
    elif change == "pin":
        manifest["sources"][next(iter(manifest["sources"]))] = "A" * 64
    elif change == "wrong_shape":
        manifest["sources"] = []
    raw = canonical(manifest)
    if change == "noncanonical":
        raw += b"\n"
    elif change == "duplicate":
        raw = raw[:1] + b'"version":"six_e_declared_admission_operator_sources_v1",' + raw[1:]
    tree.manifest_path.write_bytes(raw)
    with pytest.raises(operator.OperatorError):
        tree.verify(expected_source_manifest_sha256=pin(raw))


def test_source_pin_mismatch_refuses_before_packet_decoder(tree, monkeypatch):
    relative = next(iter(tree.manifest["sources"]))
    (tree.root / relative).write_bytes(b"# changed constructed bytes\n")

    def forbidden(*args, **kwargs):
        raise AssertionError("Unpinned source reached packet reconstruction")

    monkeypatch.setattr(packet, "decode_packet", forbidden)
    with pytest.raises(operator.OperatorError):
        tree.verify()


def test_imported_module_file_mapping_must_match_explicit_installed_root(tree):
    relative = next(iter(tree.modules))
    tree.modules[relative].__file__ = str(tree.root.parent / "elsewhere" / "unrelated.py")
    with pytest.raises(operator.OperatorError):
        tree.verify()


def test_root_cannot_be_changed_to_a_convenient_other_checkout(tree):
    with pytest.raises(operator.OperatorError):
        tree.verify(root=tree.root.parent)


@pytest.mark.parametrize(
    "path",
    [
        "../outside.json",
        "data/processed/packet.json",
        "logs/packet.json:stream",
        "logs/NUL.json",
        "logs/packet.json.",
        "logs/packet.json ",
        "//server/share/packet.json",
    ],
)
def test_packet_paths_cannot_escape_logs_or_use_windows_aliases(tree, path):
    with pytest.raises(operator.OperatorError):
        tree.verify(packet_path=path)


@pytest.mark.parametrize("role", ["packet", "manifest", "source"])
def test_oversized_regular_file_is_not_trimmed_to_the_bound(tree, role):
    path = (
        tree.packet_path
        if role == "packet"
        else tree.manifest_path
        if role == "manifest"
        else tree.root / next(iter(tree.manifest["sources"]))
    )
    bound = 4 * 1024**2 if role == "packet" else 8192 if role == "manifest" else 512 * 1024
    path.write_bytes(b"x" * (bound + 1))
    with pytest.raises(operator.OperatorError):
        tree.verify()


@pytest.mark.parametrize("role", ["packet", "manifest"])
def test_missing_or_directory_inputs_do_not_trigger_fallback_search(tree, role):
    key = "packet_path" if role == "packet" else "source_manifest_path"
    with pytest.raises(operator.OperatorError):
        tree.verify(**{key: tree.root / "logs" / "missing.json"})
    with pytest.raises(operator.OperatorError):
        tree.verify(**{key: tree.root / "logs"})


@pytest.mark.parametrize("location", ["outside", "data"])
def test_existing_valid_packet_outside_approved_logs_is_refused(tree, location):
    path = (
        tree.root.parent / "outside.json"
        if location == "outside"
        else tree.root / "data" / "synthetic.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tree.value.raw)
    with pytest.raises(operator.OperatorError):
        tree.verify(packet_path=path)


def test_packet_and_source_manifest_cannot_alias_the_same_input(tree):
    with pytest.raises(operator.OperatorError):
        tree.verify(
            source_manifest_path=tree.packet_path,
            expected_source_manifest_sha256=pin(tree.value.raw),
        )


def test_two_hardlinked_packet_names_are_not_an_unambiguous_regular_input(tree):
    alias = tree.root / "logs" / "hardlinked_packet.json"
    os.link(tree.packet_path, alias)
    with pytest.raises(operator.OperatorError):
        tree.verify()


@pytest.mark.parametrize("changed", ["packet", "manifest", "source", "metadata"])
def test_terminal_drift_after_decode_refuses_success_without_retry_or_repair(
    tree, monkeypatch, changed
):
    original = packet.decode_packet
    calls = []

    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(result)
        if changed == "packet":
            tree.packet_path.write_bytes(tree.value.raw + b"\n")
        elif changed == "manifest":
            tree.manifest_path.write_bytes(canonical(tree.manifest) + b"\n")
        elif changed == "source":
            (tree.root / next(iter(tree.manifest["sources"]))).write_bytes(
                b"# terminal source drift\n"
            )
        else:
            initial = tree.packet_path.stat()
            os.utime(tree.packet_path, ns=(initial.st_atime_ns, initial.st_mtime_ns + SECOND))
        return result

    monkeypatch.setattr(packet, "decode_packet", mutate)
    with pytest.raises(operator.OperatorError):
        tree.verify()
    assert len(calls) == 1
    assert not any(
        "attempt" in str(path) or "failure" in str(path) or "report" in str(path)
        for path in tree.root.rglob("*")
    )


@pytest.mark.parametrize("failure", ["short", "extra", "oversized"])
def test_reader_requires_complete_eof_and_detects_growth_before_decode(tree, monkeypatch, failure):
    original_open = Path.open
    raw = (
        tree.value.raw[:-1]
        if failure == "short"
        else tree.value.raw + b"x"
        if failure == "extra"
        else b"x" * (4 * 1024**2 + 1)
    )
    reads = []

    class ChangedStream:
        def __init__(self, actual):
            self.actual = actual
            self.memory = io.BytesIO(raw)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.actual.close()
            self.memory.close()

        def fileno(self):
            return self.actual.fileno()

        def read(self, count=-1):
            reads.append(count)
            return self.memory.read(count)

    def changed_open(path, *args, **kwargs):
        actual = original_open(path, *args, **kwargs)
        return ChangedStream(actual) if path == tree.packet_path else actual

    def forbidden(*args, **kwargs):
        raise AssertionError("Incomplete or grown packet reached decode")

    monkeypatch.setattr(Path, "open", changed_open)
    monkeypatch.setattr(packet, "decode_packet", forbidden)
    with pytest.raises(operator.OperatorError):
        tree.verify()
    assert reads
    assert all(0 <= count <= 4 * 1024**2 + 1 for count in reads)


def test_operator_never_opens_files_for_writing_or_invokes_history_policy_model_or_advance(
    tree, monkeypatch
):
    before = snapshot_tree(tree.root)
    original_open = Path.open

    def readonly_open(path, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Read-only operator attempted a write mode"
        return original_open(path, mode, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Read-only packet operator attempted mutation or historical integration"
        )

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", readonly_open)
        for name in ("write_bytes", "write_text", "touch", "mkdir", "unlink", "rename", "replace"):
            patch.setattr(Path, name, forbidden)
        patch.setattr(admission, "advance", forbidden)
        patch.setattr(reader, "snapshot", forbidden)
        patch.setattr(economics.replay, "build_plan", forbidden)
        patch.setattr(economics.replay, "_freeze", forbidden)
        patch.setattr(economics, "project", forbidden)
        patch.setattr(economics.ledger, "ScenarioLedger", forbidden)
        patch.setattr(economics.replay.rules, "rules", forbidden)
        patch.setattr(economics.replay.rules.Model, "predict", forbidden)
        patch.setattr(sqlite3, "connect", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        first, second = tree.verify(), tree.verify()
        assert first == second
    assert snapshot_tree(tree.root) == before


def cli_arguments(tree):
    return [
        "verify-packet",
        "--root",
        str(tree.root),
        "--packet",
        str(tree.packet_path),
        "--source-manifest",
        str(tree.manifest_path),
        "--packet-sha256",
        pin(tree.value.raw),
        "--source-manifest-sha256",
        pin(canonical(tree.manifest)),
        "--genesis-sha256",
        tree.value.genesis_pin,
        "--terminal-sequence",
        str(tree.value.terminal.sequence),
        "--terminal-head-sha256",
        tree.value.terminal.head_sha256,
        "--terminal-complete-through-ns",
        str(tree.value.terminal.complete_through_ns),
    ]


def test_cli_stdout_is_canonical_complete_deterministic_and_exit_zero(tree, capsys):
    arguments = cli_arguments(tree)
    before = snapshot_tree(tree.root)
    assert operator.main(arguments) == 0
    first = capsys.readouterr()
    assert first.err == ""
    result = json.loads(first.out)
    assert first.out == canonical(result).decode("ascii") + "\n"
    assert result["supplied_record_count"] == len(tree.value.records)
    assert result["decoded_packet"]["records"] == [asdict(record) for record in tree.value.records]
    assert result["decoded_packet"]["reconstructed_state"] == json.loads(
        canonical(asdict(tree.value.state))
    )
    assert all(flag is False for _, flag in result["authority_flags"])
    assert operator.main(arguments) == 0
    second = capsys.readouterr()
    assert second == first
    assert snapshot_tree(tree.root) == before


def test_cli_refusal_exits_two_and_does_not_print_raw_bytes_or_partial_verified_state(tree, capsys):
    arguments = cli_arguments(tree)
    arguments[arguments.index("--packet-sha256") + 1] = "a" * 64
    assert operator.main(arguments) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    error = json.loads(captured.err)
    assert error == {"status": "refused_local_constructed_packet", "error": "OperatorError"}
    assert "synthetic-operator" not in captured.err
    assert "declared_realization_balance" not in captured.err


@pytest.mark.parametrize(
    "missing",
    [
        "--packet-sha256",
        "--source-manifest-sha256",
        "--genesis-sha256",
        "--terminal-sequence",
        "--terminal-head-sha256",
        "--terminal-complete-through-ns",
    ],
)
def test_cli_external_witnesses_are_required_not_adopted_from_inputs(tree, capsys, missing):
    arguments = cli_arguments(tree)
    position = arguments.index(missing)
    del arguments[position : position + 2]
    with pytest.raises(SystemExit) as error:
        operator.main(arguments)
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("command", ["prepare", "inspect", "resume", "save", "advance", "run"])
def test_cli_has_no_artifact_writer_resume_account_or_execution_commands(tree, capsys, command):
    arguments = cli_arguments(tree)
    arguments[0] = command
    with pytest.raises(SystemExit) as error:
        operator.main(arguments)
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


def test_source_keyset_is_fixed_eight_used_helpers_not_the_old_forty_or_forty_seven(tree):
    names = {
        "six_e_declared_admission_operator.py",
        "six_e_declared_admission_packet.py",
        "six_e_declared_admission.py",
        "six_e_entry_budget.py",
        "six_e_declared_economics.py",
        "six_e_position_ledger.py",
        "six_e_bracket_targets.py",
        "six_e_continuous_replay.py",
    }
    assert operator.SOURCE_NAMES == {"src/ai_trader/research/" + name for name in names}
    assert set(tree.manifest["sources"]) == operator.SOURCE_NAMES
    assert operator.MAX_MANIFEST_BYTES == 8192
    assert operator.MAX_SOURCE_BYTES == 512 * 1024


@pytest.mark.parametrize("change", ["missing", "extra"])
def test_imported_helper_registry_cannot_add_or_drop_keys(tree, change):
    if change == "missing":
        del tree.modules[next(iter(tree.modules))]
    else:
        tree.modules["src/ai_trader/research/other.py"] = SimpleNamespace(
            __file__=str(tree.packet_path)
        )
    with pytest.raises(operator.OperatorError):
        tree.verify()


@pytest.mark.parametrize("role", ["logs", "source_ancestor", "packet"])
def test_reparse_attributes_on_input_or_ancestors_are_refused_without_link_privileges(
    tree, monkeypatch, role
):
    bad = (
        tree.root / "logs"
        if role == "logs"
        else tree.root / "src"
        if role == "source_ancestor"
        else tree.packet_path
    )
    original = Path.lstat

    class ReparseInfo:
        def __init__(self, actual):
            self.actual = actual

        def __getattr__(self, field):
            if field == "st_file_attributes":
                return getattr(self.actual, field, 0) | 0x400
            return getattr(self.actual, field)

    def metadata(path, *args, **kwargs):
        actual = original(path, *args, **kwargs)
        return ReparseInfo(actual) if path == bad else actual

    monkeypatch.setattr(Path, "lstat", metadata)
    with pytest.raises(operator.OperatorError, match="reparse|Links"):
        tree.verify()


@pytest.mark.parametrize(
    "literal",
    [
        "logs/x.json:stream",
        "logs/NUL.json",
        "logs/COM1.json",
        "logs/COM¹.json",
        "logs/CONOUT$.json",
        "logs/x.json.",
        "logs/x.json ",
        "logs//x.json",
        "logs/../x.json",
        "C:relative.json",
        "\\\\server\\share\\x.json",
        "\\\\?\\C:\\x.json",
    ],
)
def test_windows_ambiguous_literals_fail_before_any_filesystem_fallback(literal):
    with pytest.raises(operator.OperatorError):
        operator._literal(literal)


@pytest.mark.parametrize(
    "bound", [8192, 512 * 1024, 4 * 1024**2], ids=["manifest", "source", "packet"]
)
def test_private_reader_accepts_exact_size_bound_and_rejects_one_more_without_public_schema_claim(
    tree, bound
):
    # This guard-only fixture is not asserted to be a valid manifest or packet.
    path = tree.root / "logs" / "raw_boundary.json"
    raw = b"x" * bound
    path.write_bytes(raw)
    accepted, identity = operator._read(path, bound, pin(raw))
    assert accepted == raw
    assert identity[4] == bound
    path.write_bytes(raw + b"x")
    with pytest.raises(operator.OperatorError, match="size|bound"):
        operator._read(path, bound, pin(raw + b"x"))


@pytest.mark.parametrize("pin_value", [None, True, "A" * 64, "a" * 63])
def test_malformed_external_pins_are_refused_before_any_path_reads(tree, monkeypatch, pin_value):
    def forbidden(*args, **kwargs):
        raise AssertionError("Malformed caller expectation reached path reads")

    monkeypatch.setattr(Path, "lstat", forbidden)
    with pytest.raises(operator.OperatorError):
        tree.verify(expected_packet_sha256=pin_value)


def test_economics_ledger_alias_drift_is_refused_before_packet_decoding(tree, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Changed money-validation ledger alias reached decoder")

    monkeypatch.setattr(economics, "ledger", SimpleNamespace())
    monkeypatch.setattr(packet, "decode_packet", forbidden)
    with pytest.raises(operator.OperatorError):
        tree.verify()


@pytest.mark.parametrize("spelling", ["+2", "02", "2_0", "-0", "9223372036854775808"])
def test_cli_terminal_numeric_spelling_is_canonical_bounded_before_file_reads(
    tree, monkeypatch, capsys, spelling
):
    arguments = cli_arguments(tree)
    arguments[arguments.index("--terminal-sequence") + 1] = spelling

    def forbidden(*args, **kwargs):
        raise AssertionError("Noncanonical CLI integer reached file verification")

    monkeypatch.setattr(operator, "verify_packet", forbidden)
    with pytest.raises(SystemExit) as error:
        operator.main(arguments)
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("target", ["operator", "decoded", "state"])
@pytest.mark.parametrize("flags", [(), (("poisoned", True),), (("poisoned", 0),)])
def test_output_authority_is_nonempty_and_exact_false_at_every_layer(
    tree, monkeypatch, target, flags
):
    if target == "operator":
        monkeypatch.setattr(operator, "AUTHORITY_FLAGS", flags)
    else:
        original = packet.decode_packet

        def changed(*args, **kwargs):
            decoded = original(*args, **kwargs)
            if target == "decoded":
                return replace(decoded, authority_flags=flags)
            return replace(
                decoded,
                reconstructed_state=replace(decoded.reconstructed_state, authority_flags=flags),
            )

        monkeypatch.setattr(packet, "decode_packet", changed)
    with pytest.raises(operator.OperatorError):
        tree.verify()


def test_source_pin_failure_precedes_source_or_packet_body_hashing(tree, monkeypatch):
    tree.manifest_path.write_bytes(b"x" * 8193)

    def forbidden(*args, **kwargs):
        raise AssertionError("Oversized manifest reached byte hashing")

    monkeypatch.setattr(operator.hashlib, "sha256", forbidden)
    with pytest.raises(operator.OperatorError):
        tree.verify(expected_source_manifest_sha256="a" * 64)


class MetadataView:
    def __init__(self, actual, **changes):
        self.actual = actual
        self.changes = changes

    def __getattr__(self, field):
        return self.changes[field] if field in self.changes else getattr(self.actual, field)


def test_native_reader_preserves_windows_cross_view_ctime_difference_but_not_drift(
    tree, monkeypatch
):
    original = os.fstat

    def handle_view(descriptor):
        info = original(descriptor)
        return MetadataView(info, st_ctime_ns=info.st_ctime_ns + SECOND)

    monkeypatch.setattr(os, "fstat", handle_view)
    if os.name == "nt":
        accepted, identity = operator._read(tree.packet_path, 4 * 1024**2, pin(tree.value.raw))
        assert accepted == tree.value.raw
        assert identity[6] == tree.packet_path.lstat().st_ctime_ns
    else:
        with pytest.raises(operator.OperatorError):
            operator._read(tree.packet_path, 4 * 1024**2, pin(tree.value.raw))


def test_handle_ctime_change_during_read_is_still_refused(tree, monkeypatch):
    original = os.fstat
    observations = []

    def changed(descriptor):
        info = original(descriptor)
        observations.append(info)
        return MetadataView(
            info, st_ctime_ns=info.st_ctime_ns + (SECOND if len(observations) > 1 else 0)
        )

    monkeypatch.setattr(os, "fstat", changed)
    with pytest.raises(operator.OperatorError, match="during read"):
        operator._read(tree.packet_path, 4 * 1024**2, pin(tree.value.raw))
    assert len(observations) == 2


def test_path_ctime_change_after_read_is_still_refused(tree, monkeypatch):
    original = Path.lstat
    observations = []

    def changed(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == tree.packet_path:
            observations.append(info)
            if len(observations) > 2:
                return MetadataView(info, st_ctime_ns=info.st_ctime_ns + SECOND)
        return info

    monkeypatch.setattr(Path, "lstat", changed)
    with pytest.raises(operator.OperatorError, match="after read"):
        operator._read(tree.packet_path, 4 * 1024**2, pin(tree.value.raw))
    assert len(observations) == 3


@pytest.mark.parametrize("field", ["st_ino", "st_size", "st_mtime_ns"])
def test_compatible_cross_view_inode_size_and_mtime_fields_cannot_drift(tree, monkeypatch, field):
    original = os.fstat

    def changed(descriptor):
        info = original(descriptor)
        return MetadataView(info, **{field: getattr(info, field) + 1})

    monkeypatch.setattr(os, "fstat", changed)
    with pytest.raises(operator.OperatorError, match="Opened file identity"):
        operator._read(tree.packet_path, 4 * 1024**2, pin(tree.value.raw))
