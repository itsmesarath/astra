"""Independent invented native visibility fixtures; no feed, history or accounting."""

import ast
import builtins
import hashlib
import inspect
import json
import socket
import sqlite3
import subprocess
from dataclasses import FrozenInstanceError, asdict, fields
from pathlib import Path

import pytest

from ai_trader.research import six_e_native_prefix as native

SECOND = 1_000_000_000
TICK = 50_000
PRICE = 1_000_000_000
START = 10 * SECOND
END = 100 * SECOND
MAX_INT = 2**63 - 1
SOURCE = "a" * 64
VERSION = "six_e_native_prefix_v1"


def replace(value, **changes):
    """Poison an independent frozen copy to test APIs, not eager constructor guards."""
    copied = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(copied, field.name, getattr(value, field.name))
    for name, changed in changes.items():
        object.__setattr__(copied, name, changed)
    return copied


def fixture(**changes):
    value = native.NativeFixture(
        "synthetic-prefix-case",
        "6EU5",
        SOURCE,
        START,
        END,
        (
            native.NativeQuote(START + SECOND, PRICE, PRICE + TICK),
            native.NativeQuote(START + SECOND, PRICE - 5 * TICK, PRICE - 4 * TICK),
            native.NativeQuote(START + 2 * SECOND, PRICE + TICK, PRICE + 2 * TICK),
            native.NativeQuote(START + 5 * SECOND, PRICE, PRICE + 2 * TICK),
        ),
        (
            native.NativePublication("pub-a", 0, START + SECOND),
            native.NativePublication("pub-b", 2, START + 2 * SECOND),
        ),
    )
    return replace(value, **changes)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def metadata(value):
    """Independent closed schema, not a production serialization helper."""
    return {
        "version": VERSION,
        "source_session": value.source_session,
        "contract": value.contract,
        "source_sha256": value.source_sha256,
        "start_ns": value.start_ns,
        "end_ns": value.end_ns,
        "tick_nano": TICK,
    }


def fixture_body(value):
    return {
        "version": VERSION,
        "kind": "complete_constructed_native_fixture",
        "metadata": metadata(value),
        "quote_count": len(value.quotes),
        "publication_count": len(value.publications),
        "quotes": [
            [quote.received_at_ns, quote.bid_nano, quote.ask_nano] for quote in value.quotes
        ],
        "publications": [
            {
                "publication_id": publication.publication_id,
                "published_cursor": publication.published_cursor,
                "received_at_ns": publication.received_at_ns,
            }
            for publication in value.publications
        ],
    }


def fixture_pin(value):
    return digest(fixture_body(value))


def content_pin(value, count):
    previous = digest(
        {"version": VERSION, "kind": "consumed_metadata_seed", "metadata": metadata(value)}
    )
    for cursor, quote in enumerate(value.quotes[:count]):
        previous = digest(
            {
                "version": VERSION,
                "kind": "consumed_quote",
                "previous_sha256": previous,
                "native_cursor": cursor,
                "quote": [quote.received_at_ns, quote.bid_nano, quote.ask_nano],
            }
        )
    return previous


def prefix_at(value, count):
    pin = fixture_pin(value)
    prefix = native.initial_prefix(value, expected_fixture_sha256=pin)
    for cursor in range(count):
        result = native.consume_next(
            value,
            expected_fixture_sha256=pin,
            expected_prefix=prefix,
            expected_cursor=cursor,
        )
        assert result.native_cursor == cursor
        assert result.quote == value.quotes[cursor]
        prefix = result.prefix
    return prefix


def arguments(value, prefix=None):
    return {
        "expected_fixture_sha256": fixture_pin(value),
        "expected_prefix": prefix_at(value, 0) if prefix is None else prefix,
    }


class IntSubclass(int):
    def __int__(self):
        raise AssertionError("An integer subclass must be refused without conversion")


class StringSubclass(str):
    def encode(self, *args, **kwargs):
        raise AssertionError("A string subclass must be refused before encoding")


def safe_parameter_id(value):
    """Pytest must not call a deliberately poisoned subclass while making IDs."""
    if type(value) in (str, int, float, bool, type(None)):
        return repr(value)
    return type(value).__name__


class TupleSubclass(tuple):
    def __len__(self):
        raise AssertionError("A tuple subclass must be refused before length inspection")


class PoisonQuote(native.NativeQuote):
    def __getattribute__(self, name):
        raise AssertionError("Metadata or count refusal must precede quote-field access")


def poison_quote():
    return object.__new__(PoisonQuote)


def forbid_quote_traversal(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("The public API traversed quotes before its preflight refusal")

    monkeypatch.setattr(native, "_quote_fields", forbidden)


def assert_false_flags(value):
    flags = value.authority_flags
    assert type(flags) is tuple
    assert flags
    assert len({name for name, _ in flags}) == len(flags)
    assert all(type(pair) is tuple and len(pair) == 2 for pair in flags)
    assert all(type(name) is str and type(flag) is bool and flag is False for name, flag in flags)


def test_agreed_constants_and_independent_canonical_full_pin():
    value = fixture()
    assert native.VERSION == VERSION
    assert native.TICK_NANO == TICK
    assert native.SECOND_NS == SECOND
    assert native.MAX_QUOTES == 1024
    assert native.MAX_PUBLICATIONS == 64
    assert native.MAX_INPUT_BYTES == 256 * 1024
    pin = fixture_pin(value)
    assert native.fixture_sha256(value) == pin
    assert native.prepare_fixture(value, expected_fixture_sha256=pin) is value


def test_initial_prefix_is_empty_but_binds_the_complete_fixture():
    value = fixture()
    prefix = prefix_at(value, 0)
    assert type(prefix) is native.NativePrefix
    assert prefix.fixture_sha256 == fixture_pin(value)
    assert prefix.source_session == value.source_session
    assert prefix.contract == value.contract
    assert prefix.source_sha256 == value.source_sha256
    assert (prefix.start_ns, prefix.end_ns) == (START, END)
    assert (prefix.total_quotes, prefix.total_publications) == (4, 2)
    assert prefix.consumed_count == 0
    assert prefix.last_cursor is None
    assert prefix.last_received_at_ns is None
    assert prefix.current_timestamp_first_cursor is None
    assert prefix.consumed_content_sha256 == content_pin(value, 0)
    assert_false_flags(prefix)


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_every_consumed_prefix_matches_independent_chain_and_native_group(count):
    value = fixture()
    prefix = prefix_at(value, count)
    assert prefix.consumed_count == count
    assert prefix.last_cursor == count - 1
    assert prefix.last_received_at_ns == value.quotes[count - 1].received_at_ns
    assert prefix.current_timestamp_first_cursor == [0, 0, 2, 3][count - 1]
    assert prefix.consumed_content_sha256 == content_pin(value, count)
    assert_false_flags(prefix)
    assert native.verify_prefix(value, **arguments(value, prefix)) == prefix


def test_repeating_a_pure_consume_is_reproducible_not_persisted_progression():
    value = fixture()
    prefix = prefix_at(value, 0)
    call = arguments(value, prefix) | {"expected_cursor": 0}
    first = native.consume_next(value, **call)
    assert native.consume_next(value, **call) == first
    assert prefix.consumed_count == 0
    with pytest.raises(ValueError):
        native.consume_next(value, **arguments(value, first.prefix), expected_cursor=0)


@pytest.mark.parametrize("cursor", [-1, 1, 2, 1024, True, 0.0, "0", IntSubclass(0)])
def test_consumption_requires_the_exact_next_strict_cursor(cursor):
    value = fixture()
    with pytest.raises(ValueError):
        native.consume_next(value, **arguments(value), expected_cursor=cursor)


def test_consuming_past_eof_refuses_without_returning_a_successful_subset():
    value = fixture()
    with pytest.raises(ValueError):
        native.consume_next(value, **arguments(value, prefix_at(value, 4)), expected_cursor=4)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("source_session", "2025-07-07"),
        ("source_session", "reserved"),
        ("source_session", "train"),
        ("source_session", "synthetic-"),
        ("source_session", "Synthetic-example"),
        ("source_session", "synthetic-contains space"),
        ("source_session", "synthetic-path/name"),
        ("source_session", "synthetic-é"),
        ("source_session", "synthetic-" + "a" * 55),
        ("source_session", StringSubclass("synthetic-test")),
        ("source_session", None),
        ("contract", "6EU25"),
        ("contract", "6EZ"),
        ("contract", "6EA5"),
        ("contract", "6Eu5"),
        ("contract", "6EU5\n"),
        ("contract", StringSubclass("6EU5")),
        ("contract", None),
        ("source_sha256", "A" * 64),
        ("source_sha256", "a" * 63),
        ("source_sha256", "g" * 64),
        ("source_sha256", StringSubclass(SOURCE)),
        ("source_sha256", None),
        ("start_ns", True),
        ("start_ns", 0.0),
        ("start_ns", IntSubclass(START)),
        ("start_ns", -1),
        ("start_ns", END),
        ("start_ns", MAX_INT + 1),
        ("end_ns", False),
        ("end_ns", float(END)),
        ("end_ns", IntSubclass(END)),
        ("end_ns", START),
        ("end_ns", -1),
        ("end_ns", MAX_INT + 1),
    ],
    ids=safe_parameter_id,
)
def test_invalid_metadata_refuses_before_any_quote_field_access(field, changed, monkeypatch):
    value = fixture(quotes=(poison_quote(),), publications=(), **{field: changed})
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


@pytest.mark.parametrize(
    "pin",
    [None, True, "a" * 63, "A" * 64, "g" * 64, StringSubclass(SOURCE)],
    ids=safe_parameter_id,
)
def test_external_pin_syntax_refuses_before_quote_inspection(pin, monkeypatch):
    value = fixture(quotes=(poison_quote(),), publications=())
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256=pin)


@pytest.mark.parametrize("field", ["quotes", "publications"])
def test_exact_tuples_required_before_len_or_serialization(field, monkeypatch):
    value = fixture(**{field: TupleSubclass(())})
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


@pytest.mark.parametrize("field", ["quotes", "publications"])
@pytest.mark.parametrize("changed", [[], None, {}])
def test_list_or_nonsequence_is_not_immutable_native_input(field, changed):
    with pytest.raises(ValueError):
        native.prepare_fixture(fixture(**{field: changed}), expected_fixture_sha256="0" * 64)


@pytest.mark.parametrize("field", ["quotes", "publications"])
def test_tuple_count_cap_refuses_before_inspecting_poison_quote(field, monkeypatch):
    changes = {"quotes": (poison_quote(),), "publications": ()}
    changes[field] = (poison_quote(),) * (1025 if field == "quotes" else 65)
    value = fixture(**changes)
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


def test_reduced_byte_cap_known_metadata_floor_precedes_poison_prices(monkeypatch):
    """Defensive reduced-cap probe, not a claim of a valid 256-KiB fixture."""
    value = fixture(quotes=(poison_quote(),), publications=())
    monkeypatch.setattr(native, "MAX_INPUT_BYTES", 1)
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


def test_reduced_final_byte_cap_accepts_equality_and_refuses_one_less(monkeypatch):
    """The fixed schema cannot manufacture arbitrary valid production-size inputs."""
    value = fixture()
    length = len(canonical(fixture_body(value)))
    pin = fixture_pin(value)
    monkeypatch.setattr(native, "MAX_INPUT_BYTES", length)
    assert native.prepare_fixture(value, expected_fixture_sha256=pin) is value
    monkeypatch.setattr(native, "MAX_INPUT_BYTES", length - 1)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256=pin)


def test_exact_maximum_quote_count_is_valid_complete_input():
    quote = native.NativeQuote(START, PRICE, PRICE + TICK)
    value = fixture(quotes=(quote,) * 1024, publications=())
    pin = fixture_pin(value)
    assert native.prepare_fixture(value, expected_fixture_sha256=pin) is value
    initial = prefix_at(value, 0)
    assert initial.total_quotes == 1024
    terminal = native.NativePrefix(
        **(
            asdict(initial)
            | {
                "consumed_count": 1024,
                "last_cursor": 1023,
                "last_received_at_ns": START,
                "current_timestamp_first_cursor": 0,
                "consumed_content_sha256": content_pin(value, 1024),
            }
        )
    )
    assert native.verify_prefix(value, **arguments(value, terminal)) == terminal
    closure = native.close_through(value, **arguments(value, terminal), through_ns=END)
    assert closure.closure_kind == "complete_eof"
    assert closure.prefix.consumed_count == closure.prefix.total_quotes == 1024


def test_exact_maximum_publication_count_and_one_second_spacing_are_valid():
    quotes = tuple(native.NativeQuote(START + i * SECOND, PRICE, PRICE + TICK) for i in range(64))
    publications = tuple(
        native.NativePublication(f"pub-{i}", i, q.received_at_ns) for i, q in enumerate(quotes)
    )
    value = fixture(quotes=quotes, publications=publications)
    assert native.prepare_fixture(value, expected_fixture_sha256=fixture_pin(value)) is value
    initial = prefix_at(value, 0)
    assert initial.total_publications == 64
    first = native.publication_witness(
        value, **arguments(value, prefix_at(value, 1)), publication_id="pub-0"
    )
    terminal = native.NativePrefix(
        **(
            asdict(initial)
            | {
                "consumed_count": 64,
                "last_cursor": 63,
                "last_received_at_ns": START + 63 * SECOND,
                "current_timestamp_first_cursor": 63,
                "consumed_content_sha256": content_pin(value, 64),
            }
        )
    )
    last = native.publication_witness(value, **arguments(value, terminal), publication_id="pub-63")
    assert (first.published_cursor, last.published_cursor) == (0, 63)
    assert first.boundary_state == last.boundary_state == "OPEN"


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("received_at_ns", True),
        ("received_at_ns", float(START + SECOND)),
        ("received_at_ns", IntSubclass(START + SECOND)),
        ("received_at_ns", START - 1),
        ("received_at_ns", END),
        ("received_at_ns", MAX_INT + 1),
        ("bid_nano", True),
        ("bid_nano", float(PRICE)),
        ("bid_nano", IntSubclass(PRICE)),
        ("bid_nano", 0),
        ("bid_nano", -TICK),
        ("bid_nano", PRICE + 1),
        ("bid_nano", PRICE + TICK),
        ("bid_nano", PRICE + 2 * TICK),
        ("bid_nano", MAX_INT + 1),
        ("ask_nano", False),
        ("ask_nano", float(PRICE + TICK)),
        ("ask_nano", IntSubclass(PRICE + TICK)),
        ("ask_nano", 0),
        ("ask_nano", PRICE - TICK),
        ("ask_nano", PRICE),
        ("ask_nano", PRICE + TICK + 1),
        ("ask_nano", MAX_INT + 1),
    ],
)
def test_quote_scalar_grid_spread_and_half_open_window_guards(field, changed):
    quote = replace(fixture().quotes[0], **{field: changed})
    value = fixture(quotes=(quote,), publications=())
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256=fixture_pin(value))


def test_strict_exact_native_quote_type_not_a_subclass_or_arbitrary_object():
    for quote in (poison_quote(), object(), (START, PRICE, PRICE + TICK)):
        with pytest.raises(ValueError):
            native.prepare_fixture(
                fixture(quotes=(quote,), publications=()), expected_fixture_sha256="0" * 64
            )


def test_exact_fixture_type_is_checked_before_any_metadata_access():
    class PoisonFixture(native.NativeFixture):
        def __getattribute__(self, name):
            raise AssertionError("Fixture subclasses must be refused before field access")

    with pytest.raises(ValueError):
        native.prepare_fixture(object.__new__(PoisonFixture), expected_fixture_sha256="0" * 64)


def test_nonmonotonic_native_rows_refuse_even_if_each_quote_is_individually_valid():
    value = fixture()
    changed = replace(value, quotes=(value.quotes[2], value.quotes[0]), publications=())
    with pytest.raises(ValueError):
        native.prepare_fixture(changed, expected_fixture_sha256=fixture_pin(changed))


def test_full_fixture_is_checked_before_any_initial_prefix_is_returned():
    value = fixture()
    changed = replace(value, quotes=(*value.quotes[:-1], replace(value.quotes[-1], ask_nano=0)))
    with pytest.raises(ValueError):
        native.initial_prefix(changed, expected_fixture_sha256=fixture_pin(changed))


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("publication_id", ""),
        ("publication_id", "bad space"),
        ("publication_id", "bad/path"),
        ("publication_id", "a" * 65),
        ("publication_id", "é"),
        ("publication_id", "-leading"),
        ("publication_id", StringSubclass("pub-a")),
        ("publication_id", None),
        ("published_cursor", True),
        ("published_cursor", 0.0),
        ("published_cursor", IntSubclass(0)),
        ("published_cursor", -1),
        ("published_cursor", 4),
        ("received_at_ns", True),
        ("received_at_ns", float(START + SECOND)),
        ("received_at_ns", IntSubclass(START + SECOND)),
        ("received_at_ns", -1),
        ("received_at_ns", MAX_INT + 1),
    ],
    ids=safe_parameter_id,
)
def test_invalid_publication_metadata_refuses_before_price_inspection(field, changed, monkeypatch):
    publication = replace(fixture().publications[0], **{field: changed})
    value = fixture(quotes=(poison_quote(),) * 4, publications=(publication,))
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


def test_publication_exact_type_precedes_its_field_access(monkeypatch):
    class PoisonPublication(native.NativePublication):
        def __getattribute__(self, name):
            raise AssertionError("Publication subclass must be refused before field access")

    value = fixture(quotes=(poison_quote(),), publications=(object.__new__(PoisonPublication),))
    forbid_quote_traversal(monkeypatch)
    with pytest.raises(ValueError):
        native.prepare_fixture(value, expected_fixture_sha256="0" * 64)


@pytest.mark.parametrize(
    "kind",
    ["suffix", "time_mismatch", "duplicate_id", "duplicate_cursor", "reverse", "short_spacing"],
)
def test_publication_first_cursor_identity_order_and_spacing(kind):
    value = fixture()
    a, b = value.publications
    if kind == "suffix":
        publications = (replace(a, published_cursor=1),)
    elif kind == "time_mismatch":
        publications = (replace(a, received_at_ns=a.received_at_ns + 1),)
    elif kind == "duplicate_id":
        publications = (a, replace(b, publication_id=a.publication_id))
    elif kind == "duplicate_cursor":
        publications = (a, replace(a, publication_id="different"))
    elif kind == "reverse":
        publications = (b, a)
    else:
        q2 = replace(value.quotes[2], received_at_ns=a.received_at_ns + SECOND - 1)
        value = replace(value, quotes=(*value.quotes[:2], q2, value.quotes[3]))
        publications = (a, replace(b, received_at_ns=q2.received_at_ns))
    changed = replace(value, publications=publications)
    with pytest.raises(ValueError):
        native.prepare_fixture(changed, expected_fixture_sha256=fixture_pin(changed))


def test_identifier_exact_maximum_length_and_declared_contract_labels_are_synthetic_only():
    for contract in ("6EH0", "6EM9", "6EU5", "6EZ8"):
        value = fixture(
            source_session="synthetic-" + "a" * 54,
            contract=contract,
            publications=(native.NativePublication("p" * 64, 0, START + SECOND),),
        )
        assert native.prepare_fixture(value, expected_fixture_sha256=fixture_pin(value)) is value


@pytest.mark.parametrize(
    "changed_kind",
    [
        "omit_suffix",
        "reorder_equal",
        "quote_price",
        "publication",
        "omit_publication",
        "source",
        "session",
        "contract",
        "window",
    ],
)
def test_external_complete_pin_refuses_every_changed_or_incomplete_input(changed_kind):
    original = fixture()
    changed = original
    if changed_kind == "omit_suffix":
        changed = replace(
            original,
            quotes=(original.quotes[0], *original.quotes[2:]),
            publications=(original.publications[0],),
        )
    elif changed_kind == "reorder_equal":
        changed = replace(
            original, quotes=(original.quotes[1], original.quotes[0], *original.quotes[2:])
        )
    elif changed_kind == "quote_price":
        changed = replace(
            original,
            quotes=(*original.quotes[:3], replace(original.quotes[3], ask_nano=PRICE + 3 * TICK)),
        )
    elif changed_kind == "publication":
        changed = replace(
            original,
            publications=(
                original.publications[0],
                replace(original.publications[1], publication_id="other"),
            ),
        )
    elif changed_kind == "omit_publication":
        changed = replace(original, publications=original.publications[:1])
    elif changed_kind == "source":
        changed = replace(original, source_sha256="b" * 64)
    elif changed_kind == "session":
        changed = replace(original, source_session="synthetic-other")
    elif changed_kind == "contract":
        changed = replace(original, contract="6EZ5")
    else:
        changed = replace(original, end_ns=END + 1)
    assert fixture_pin(changed) != fixture_pin(original)
    with pytest.raises(ValueError):
        native.prepare_fixture(changed, expected_fixture_sha256=fixture_pin(original))
    with pytest.raises(ValueError):
        native.initial_prefix(changed, expected_fixture_sha256=fixture_pin(original))


PREFIX_CORRUPTIONS = [
    ("fixture_sha256", "b" * 64),
    ("fixture_sha256", StringSubclass("a" * 64)),
    ("source_session", "synthetic-other"),
    ("source_session", StringSubclass("synthetic-prefix-case")),
    ("contract", "6EZ5"),
    ("contract", StringSubclass("6EU5")),
    ("source_sha256", "b" * 64),
    ("source_sha256", StringSubclass(SOURCE)),
    ("start_ns", START + 1),
    ("end_ns", END + 1),
    ("total_quotes", 3),
    ("total_quotes", 4.0),
    ("total_publications", 1),
    ("total_publications", IntSubclass(2)),
    ("consumed_count", 0),
    ("consumed_count", True),
    ("consumed_count", 1.0),
    ("consumed_count", IntSubclass(1)),
    ("last_cursor", 1),
    ("last_cursor", False),
    ("last_cursor", None),
    ("last_received_at_ns", START + SECOND + 1),
    ("last_received_at_ns", None),
    ("current_timestamp_first_cursor", 1),
    ("current_timestamp_first_cursor", False),
    ("current_timestamp_first_cursor", None),
    ("consumed_content_sha256", "b" * 64),
    ("consumed_content_sha256", StringSubclass("a" * 64)),
    ("authority_flags", ()),
    ("authority_flags", (("trading_enabled", True),)),
]


@pytest.mark.parametrize(("field", "changed"), PREFIX_CORRUPTIONS, ids=safe_parameter_id)
@pytest.mark.parametrize("operation", ["verify", "consume", "publication", "closure"])
def test_each_consumer_reconstructs_every_retained_prefix_field(field, changed, operation):
    value = fixture()
    if operation == "closure":
        value = replace(
            value,
            quotes=(
                value.quotes[0],
                replace(value.quotes[1], received_at_ns=START + SECOND + 1),
                *value.quotes[2:],
            ),
        )
    original = prefix_at(value, 1)
    valid = arguments(value, original)
    if operation == "verify":
        assert native.verify_prefix(value, **valid) == original
    elif operation == "consume":
        assert native.consume_next(value, **valid, expected_cursor=1).native_cursor == 1
    elif operation == "publication":
        assert native.publication_witness(value, **valid, publication_id="pub-a").prefix == original
    else:
        assert native.close_through(value, **valid, through_ns=START + SECOND).prefix == original
    if type(changed) is StringSubclass:
        changed = StringSubclass(getattr(original, field))
    expected = replace(original, **{field: changed})
    kwargs = arguments(value, expected)
    with pytest.raises(ValueError):
        if operation == "verify":
            native.verify_prefix(value, **kwargs)
        elif operation == "consume":
            native.consume_next(value, **kwargs, expected_cursor=1)
        elif operation == "publication":
            native.publication_witness(value, **kwargs, publication_id="pub-a")
        else:
            native.close_through(value, **kwargs, through_ns=START + SECOND)


def test_prefix_subclass_is_not_reconstructed_by_reading_poison_fields():
    class PoisonPrefix(native.NativePrefix):
        def __getattribute__(self, name):
            raise AssertionError("Prefix subclass must refuse before field access")

    value = fixture()
    with pytest.raises(ValueError):
        native.verify_prefix(value, **arguments(value, object.__new__(PoisonPrefix)))


def test_constructed_frozen_prefix_flags_require_exact_boolean_false_types():
    value = fixture()
    prefix = prefix_at(value, 1)
    name, _ = prefix.authority_flags[0]
    for flag in (0, 0.0, None, True):
        changed = replace(prefix, authority_flags=((name, flag), *prefix.authority_flags[1:]))
        with pytest.raises(ValueError):
            native.verify_prefix(value, **arguments(value, changed))


@pytest.mark.parametrize(
    "kind", ["outer_subclass", "inner_subclass", "name_subclass", "reordered", "list"]
)
def test_authority_flag_equality_cannot_replace_exact_types_and_order(kind):
    value = fixture()
    prefix = prefix_at(value, 1)
    first = prefix.authority_flags[0]
    if kind == "outer_subclass":
        flags = TupleSubclass(prefix.authority_flags)
    elif kind == "inner_subclass":
        flags = (TupleSubclass(first), *prefix.authority_flags[1:])
    elif kind == "name_subclass":
        flags = ((StringSubclass(first[0]), False), *prefix.authority_flags[1:])
    elif kind == "reordered":
        flags = tuple(reversed(prefix.authority_flags))
    else:
        flags = list(prefix.authority_flags)
    with pytest.raises(ValueError):
        native.verify_prefix(value, **arguments(value, replace(prefix, authority_flags=flags)))


def test_source_pin_intentionally_changes_consumed_content_identity():
    original = fixture()
    other = replace(original, source_sha256="b" * 64)
    assert (
        prefix_at(original, 1).consumed_content_sha256
        != prefix_at(other, 1).consumed_content_sha256
    )


def test_unseen_prices_publications_and_counts_do_not_enter_consumed_content_digest():
    original = fixture()
    quote_changes = (
        original.quotes[0],
        replace(original.quotes[1], bid_nano=PRICE + 9 * TICK, ask_nano=PRICE + 10 * TICK),
        replace(original.quotes[2], bid_nano=PRICE - 8 * TICK, ask_nano=PRICE - 7 * TICK),
        original.quotes[3],
    )
    variants = [
        replace(original, quotes=quote_changes),
        replace(
            original,
            publications=(
                original.publications[0],
                replace(original.publications[1], publication_id="future-other"),
            ),
        ),
        replace(
            original,
            quotes=(*original.quotes, native.NativeQuote(START + 6 * SECOND, PRICE, PRICE + TICK)),
        ),
        replace(original, publications=original.publications[:1]),
    ]
    prefix = prefix_at(original, 1)
    for other in variants:
        another = prefix_at(other, 1)
        assert another.fixture_sha256 != prefix.fixture_sha256
        assert another.consumed_content_sha256 == prefix.consumed_content_sha256
        visible = [
            "source_session",
            "contract",
            "source_sha256",
            "start_ns",
            "end_ns",
            "consumed_count",
            "last_cursor",
            "last_received_at_ns",
            "current_timestamp_first_cursor",
            "consumed_content_sha256",
            "authority_flags",
        ]
        assert all(getattr(another, name) == getattr(prefix, name) for name in visible)
        with pytest.raises(ValueError):
            native.verify_prefix(other, **arguments(other, prefix))


def test_first_publication_is_open_and_exposes_only_its_observed_prefix():
    value = fixture()
    prefix = prefix_at(value, 1)
    witness = native.publication_witness(value, **arguments(value, prefix), publication_id="pub-a")
    assert type(witness) is native.PublicationWitness
    assert (witness.publication_id, witness.published_cursor, witness.received_at_ns) == (
        "pub-a",
        0,
        START + SECOND,
    )
    assert witness.prefix == prefix
    assert witness.boundary_state == "OPEN"
    assert_false_flags(witness)
    assert set(asdict(witness)) == {
        "publication_id",
        "published_cursor",
        "received_at_ns",
        "prefix",
        "boundary_state",
        "authority_flags",
    }
    assert not (
        {"quotes", "publications", "bid_nano", "ask_nano", "next_cursor"} & set(asdict(witness))
    )


@pytest.mark.parametrize("count", [0, 2, 3, 4])
def test_publication_cannot_be_recovered_before_its_quote_or_after_consuming_a_suffix(count):
    value = fixture()
    with pytest.raises(ValueError):
        native.publication_witness(
            value, **arguments(value, prefix_at(value, count)), publication_id="pub-a"
        )


@pytest.mark.parametrize(
    "publication_id", ["missing", "", None, True, StringSubclass("pub-a")], ids=safe_parameter_id
)
def test_publication_lookup_requires_exact_original_identifier(publication_id):
    value = fixture()
    with pytest.raises(ValueError):
        native.publication_witness(
            value, **arguments(value, prefix_at(value, 1)), publication_id=publication_id
        )


def test_later_publication_requires_its_first_cursor_not_all_equal_time_knowledge():
    value = fixture()
    witness = native.publication_witness(
        value, **arguments(value, prefix_at(value, 3)), publication_id="pub-b"
    )
    assert witness.published_cursor == 2
    assert witness.boundary_state == "OPEN"
    assert witness.prefix.current_timestamp_first_cursor == 2


@pytest.mark.parametrize("boundary", [START + SECOND, START + SECOND + 1, START + SECOND // 2])
def test_equality_suffix_and_consumed_later_quote_prevent_premature_closure(boundary):
    value = fixture()
    with pytest.raises(ValueError):
        native.close_through(value, **arguments(value, prefix_at(value, 1)), through_ns=boundary)


@pytest.mark.parametrize("boundary", [START + SECOND, START + SECOND + 1, START + 2 * SECOND - 1])
def test_complete_equality_group_or_gap_closes_with_next_timestamp_not_price(boundary):
    value = fixture()
    prefix = prefix_at(value, 2)
    closure = native.close_through(value, **arguments(value, prefix), through_ns=boundary)
    assert type(closure) is native.ClosedNativeBoundary
    assert closure.prefix == prefix
    assert closure.through_ns == boundary
    assert closure.closure_kind == "next_timestamp"
    assert closure.next_cursor == 2
    assert closure.next_received_at_ns == START + 2 * SECOND
    assert closure.boundary_state == "CLOSED"
    assert prefix.consumed_count == 2
    assert_false_flags(closure)
    assert set(asdict(closure)) == {
        "prefix",
        "through_ns",
        "closure_kind",
        "next_cursor",
        "next_received_at_ns",
        "boundary_state",
        "authority_flags",
    }
    assert not ({"quote", "quotes", "bid_nano", "ask_nano"} & set(asdict(closure)))


def test_next_row_at_the_deadline_does_not_prove_strictly_later_closure():
    value = fixture()
    with pytest.raises(ValueError):
        native.close_through(
            value, **arguments(value, prefix_at(value, 2)), through_ns=START + 2 * SECOND
        )


def test_initial_gap_can_close_without_claiming_a_consumed_quote():
    value = fixture()
    prefix = prefix_at(value, 0)
    closure = native.close_through(value, **arguments(value, prefix), through_ns=START)
    assert closure.closure_kind == "next_timestamp"
    assert closure.next_cursor == 0
    assert closure.next_received_at_ns == START + SECOND
    assert closure.prefix.consumed_count == 0
    assert closure.prefix.last_received_at_ns is None
    assert_false_flags(closure)


def test_exact_int64_clock_and_highest_valid_tick_grid_prices_are_supported():
    high_price = MAX_INT // TICK * TICK
    quote = native.NativeQuote(MAX_INT - 1, high_price - TICK, high_price)
    value = fixture(start_ns=MAX_INT - 1, end_ns=MAX_INT, quotes=(quote,), publications=())
    pin = fixture_pin(value)
    assert native.prepare_fixture(value, expected_fixture_sha256=pin) is value
    closure = native.close_through(
        value, **arguments(value, prefix_at(value, 1)), through_ns=MAX_INT
    )
    assert closure.closure_kind == "complete_eof"


def test_closure_does_not_consume_later_quote_or_rewrite_open_publication():
    value = fixture()
    original = native.publication_witness(
        value, **arguments(value, prefix_at(value, 1)), publication_id="pub-a"
    )
    prefix = prefix_at(value, 2)
    closure = native.close_through(value, **arguments(value, prefix), through_ns=START + SECOND)
    assert original.boundary_state == "OPEN"
    assert original.prefix.consumed_count == 1
    assert closure.prefix.consumed_count == 2
    following = native.consume_next(value, **arguments(value, prefix), expected_cursor=2)
    assert following.quote == value.quotes[2]
    assert following.prefix.consumed_count == 3


def test_pure_closure_regeneration_is_not_persisted_frontier_advancement():
    value = fixture()
    prefix = prefix_at(value, 2)
    kwargs = arguments(value, prefix)
    first = native.close_through(value, **kwargs, through_ns=START + SECOND)
    gap = native.close_through(value, **kwargs, through_ns=START + SECOND + 1)
    assert native.close_through(value, **kwargs, through_ns=START + SECOND) == first
    assert gap.prefix == first.prefix


@pytest.mark.parametrize(
    "boundary", [START - 1, END + 1, True, float(START), IntSubclass(START), None, MAX_INT + 1]
)
def test_closure_boundary_is_an_exact_bounded_declared_time(boundary):
    value = fixture()
    with pytest.raises(ValueError):
        native.close_through(value, **arguments(value, prefix_at(value, 0)), through_ns=boundary)


@pytest.mark.parametrize("boundary", [START, START + 5 * SECOND - 1])
def test_full_eof_cannot_close_a_boundary_before_an_already_consumed_later_quote(boundary):
    value = fixture()
    with pytest.raises(ValueError):
        native.close_through(value, **arguments(value, prefix_at(value, 4)), through_ns=boundary)


@pytest.mark.parametrize("boundary", [START + 5 * SECOND, START + 5 * SECOND + 1, END])
def test_complete_pinned_eof_closes_supplied_coverage_not_a_clock_or_execution(boundary):
    value = fixture()
    prefix = prefix_at(value, 4)
    closure = native.close_through(value, **arguments(value, prefix), through_ns=boundary)
    assert closure.closure_kind == "complete_eof"
    assert closure.next_cursor is None
    assert closure.next_received_at_ns is None
    assert closure.prefix.total_quotes == closure.prefix.consumed_count == 4
    assert_false_flags(closure)


def test_empty_fixture_has_declared_eof_without_publications_or_observed_prices():
    value = fixture(quotes=(), publications=())
    prefix = prefix_at(value, 0)
    closure = native.close_through(value, **arguments(value, prefix), through_ns=END)
    assert closure.closure_kind == "complete_eof"
    assert closure.prefix.last_received_at_ns is None
    assert closure.prefix.current_timestamp_first_cursor is None
    assert closure.prefix.consumed_count == 0
    with pytest.raises(ValueError):
        native.consume_next(value, **arguments(value, prefix), expected_cursor=0)
    with pytest.raises(ValueError):
        native.publication_witness(value, **arguments(value, prefix), publication_id="pub-a")
    with pytest.raises(ValueError):
        native.prepare_fixture(fixture(quotes=()), expected_fixture_sha256="0" * 64)


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_deadline_group_completion_preserves_every_equality_row(offset):
    """No fill or timer is generated: only native visibility around a declared ns."""
    deadline = START + SECOND
    quotes = (
        native.NativeQuote(deadline - 1, PRICE, PRICE + TICK),
        native.NativeQuote(deadline, PRICE + TICK, PRICE + 2 * TICK),
        native.NativeQuote(deadline, PRICE - TICK, PRICE),
        native.NativeQuote(deadline + 1, PRICE, PRICE + 2 * TICK),
    )
    value = fixture(quotes=quotes, publications=())
    boundary = deadline + offset
    count = sum(quote.received_at_ns <= boundary for quote in quotes)
    closure = native.close_through(
        value, **arguments(value, prefix_at(value, count)), through_ns=boundary
    )
    assert closure.prefix.consumed_count == count
    if count < len(quotes):
        assert closure.next_received_at_ns > boundary
    if count:
        with pytest.raises(ValueError):
            native.close_through(
                value, **arguments(value, prefix_at(value, count - 1)), through_ns=boundary
            )


def test_missing_publications_do_not_create_unauthenticated_decision_coverage_claims():
    value = fixture(publications=())
    prefix = prefix_at(value, 4)
    assert prefix.total_publications == 0
    assert prefix.total_quotes == 4
    closure = native.close_through(value, **arguments(value, prefix), through_ns=END)
    assert closure.prefix.total_publications == 0
    assert_false_flags(closure)


def test_frozen_fixture_objects_are_revalidated_not_trusted_as_caches():
    value = fixture()
    pin = fixture_pin(value)
    prefix = prefix_at(value, 1)
    object.__setattr__(value.quotes[-1], "ask_nano", 0)
    with pytest.raises(ValueError):
        native.verify_prefix(value, expected_fixture_sha256=pin, expected_prefix=prefix)


def test_outputs_and_input_dataclasses_are_frozen_and_flags_are_exactly_false():
    value = fixture()
    initial = prefix_at(value, 0)
    observed = native.consume_next(value, **arguments(value, initial), expected_cursor=0)
    publication = native.publication_witness(
        value, **arguments(value, observed.prefix), publication_id="pub-a"
    )
    closure = native.close_through(
        value, **arguments(value, prefix_at(value, 2)), through_ns=START + SECOND
    )
    for item in (
        value,
        value.quotes[0],
        value.publications[0],
        initial,
        observed,
        publication,
        closure,
    ):
        field = fields(item)[0]
        with pytest.raises(FrozenInstanceError):
            setattr(item, field.name, getattr(item, field.name))
        assert not hasattr(item, "__dict__")
    for item in (initial, observed.prefix, publication, closure):
        assert_false_flags(item)
    assert type(value.quotes) is tuple
    assert type(value.publications) is tuple


def test_only_standard_library_imports_and_no_cli_or_foreign_integration():
    tree = ast.parse(inspect.getsource(native))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert roots <= {"__future__", "dataclasses", "hashlib", "json", "re"}
    assert not hasattr(native, "main")
    assert not hasattr(native, "verify_publication")
    assert not hasattr(native, "verify_closure")


def test_pure_full_workflow_with_io_network_and_process_hooks_disabled(monkeypatch):
    value = fixture()
    pin = fixture_pin(value)

    def forbidden(*args, **kwargs):
        raise AssertionError("Synthetic visibility must not use I/O, network or processes")

    with monkeypatch.context() as context:
        context.setattr(builtins, "open", forbidden)
        context.setattr(Path, "open", forbidden)
        context.setattr(socket, "socket", forbidden)
        context.setattr(socket, "create_connection", forbidden)
        context.setattr(sqlite3, "connect", forbidden)
        context.setattr(subprocess, "Popen", forbidden)
        context.setattr(subprocess, "run", forbidden)
        assert native.fixture_sha256(value) == pin
        assert native.prepare_fixture(value, expected_fixture_sha256=pin) is value
        prefix = native.initial_prefix(value, expected_fixture_sha256=pin)
        first = native.consume_next(
            value, expected_fixture_sha256=pin, expected_prefix=prefix, expected_cursor=0
        )
        publication = native.publication_witness(
            value, expected_fixture_sha256=pin, expected_prefix=first.prefix, publication_id="pub-a"
        )
        second = native.consume_next(
            value, expected_fixture_sha256=pin, expected_prefix=first.prefix, expected_cursor=1
        )
        closure = native.close_through(
            value,
            expected_fixture_sha256=pin,
            expected_prefix=second.prefix,
            through_ns=START + SECOND,
        )
        assert publication.boundary_state == "OPEN"
        assert closure.boundary_state == "CLOSED"
        assert (
            native.verify_prefix(value, expected_fixture_sha256=pin, expected_prefix=second.prefix)
            == second.prefix
        )
