"""Invented metadata only; independent complete canonical assessment oracles.

No historical ledger, source events, quotes, features, outcomes or account is
loaded. Expected identities are literal/manual bodies, not private helpers or
an assessment returned by the new implementation.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import io
import json
import pathlib
import socket
import subprocess
import sys
import time
from dataclasses import FrozenInstanceError, asdict, fields
from datetime import date, timedelta

import pytest

from ai_trader.research import six_e_metadata_cohort as metadata

VERSION = "six_e_metadata_cohort_v1"
STATUS = "constructed_metadata_consistency_not_provenance"
SECOND = 1_000_000_000
DAY = 86_400_000_000_000
MAX_INT = 2**63 - 1
PIN = "a" * 64
ROLES = ("train", "validation", "test", "reserved")
DISPOSITIONS = ("decision_session", "degraded", "empty", "reconstruction_only", "reserved_metadata")
CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")
SCHEMAS = {
    "InventorySession": (
        "source_session",
        "utc_date",
        "role",
        "partition",
        "disposition",
        "contract",
        "source_sha256",
        "start_ns",
        "end_ns",
        "quote_count",
        "publication_count",
        "completed_event_count",
    ),
    "PublicationMetadata": (
        "publication_id",
        "source_session",
        "original_row_ordinal",
        "received_at_ns",
        "original_first_quote_cursor",
        "first_quote_received_at_ns",
        "preceding_quote_received_at_ns",
        "completed_event_cursor",
        "completed_event_received_at_ns",
        "completed_event_prefix_sha256",
        "completion_marker",
        "feature_publication_ref_sha256",
    ),
    "SessionPublications": ("source_session", "publications"),
    "MetadataCohort": (
        "cohort_id",
        "collection_registration_sha256",
        "collection_receipt_sha256",
        "source_schema_sha256",
        "feature_schema_sha256",
        "feature_derivation_sha256",
        "declared_feature_count",
        "declared_inventory_count",
        "declared_selected_count",
        "declared_publication_count",
        "inventory",
        "selected_session_ids",
        "selected_publications",
    ),
    "MetadataAssessment": (
        "version",
        "status",
        "protocol_sha256",
        "cohort_sha256",
        "cohort",
        "inventory_count",
        "selected_count",
        "publication_count",
        "role_counts",
        "disposition_counts",
        "assessment_sha256",
        "authority_flags",
    ),
}
AUTHORITY_NAMES = (
    "accounting_admission_authorized",
    "calendar_verified",
    "cohort_externally_complete",
    "collection_receipt_authenticated",
    "event_prefix_verified",
    "execution_authorized",
    "feature_derivation_verified",
    "feature_publication_verified",
    "feed_authenticated",
    "first_cursor_verified",
    "historical_access_authorized",
    "independent_validation",
    "input_authenticated",
    "metadata_assertions_authenticated",
    "promotion_allowed",
    "source_integrity_verified",
    "source_runtime_verified",
    "storage_resume_authorized",
    "trading_enabled",
    "training_enabled",
)
FLAGS = tuple((name, False) for name in sorted(AUTHORITY_NAMES))


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def protocol_body():
    return {
        "version": VERSION,
        "status": STATUS,
        "bounds": {
            "max_inventory_sessions": 16,
            "max_selected_sessions": 3,
            "max_selected_publications": 64,
            "max_session_publications": 14400,
            "max_session_quotes": 2000000,
            "max_session_events": 4000000,
            "max_int": MAX_INT,
            "max_canonical_bytes": 262144,
        },
        "scope": {
            "identifier_pattern": "[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
            "synthetic_prefix": "synthetic-",
            "roles": ROLES,
            "dispositions": DISPOSITIONS,
            "partitions": ("development", "reserved"),
            "contracts": CONTRACTS,
            "selected_role": "train",
            "selection": "first_accepted_decision_session_prefix",
            "window_start_seconds": 43200,
            "window_end_seconds": 57600,
            "min_publication_cadence_ns": SECOND,
            "declared_feature_count": 37,
            "completion_marker": "asserted_F_LAST",
            "reference_scope": "opaque_assertions_not_source_or_feature_verification",
        },
        "schemas": SCHEMAS,
        "authority_flags": FLAGS,
    }


def input_body(cohort):
    return {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": digest(protocol_body()),
        "cohort": asdict(cohort),
    }


def result_oracle(cohort):
    body = {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": digest(protocol_body()),
        "cohort_sha256": digest(input_body(cohort)),
        "cohort": asdict(cohort),
        "inventory_count": len(cohort.inventory),
        "selected_count": len(cohort.selected_session_ids),
        "publication_count": sum(
            len(bundle.publications) for bundle in cohort.selected_publications
        ),
        "role_counts": tuple(
            (role, sum(entry.role == role for entry in cohort.inventory)) for role in ROLES
        ),
        "disposition_counts": tuple(
            (kind, sum(entry.disposition == kind for entry in cohort.inventory))
            for kind in DISPOSITIONS
        ),
        "authority_flags": FLAGS,
    }
    return body | {"assessment_sha256": digest(body)}


def expectations(cohort):
    return {
        "expected_protocol_sha256": digest(protocol_body()),
        "expected_cohort_sha256": digest(input_body(cohort)),
    }


def window(day):
    # Integer civil-day arithmetic is independent of host timezone and floats.
    midnight = (date.fromisoformat(day) - date(1970, 1, 1)).days * DAY
    return midnight + 43200 * SECOND, midnight + 57600 * SECOND


def inventory(
    index,
    day=None,
    *,
    role="train",
    disposition="decision_session",
    publications=2,
    quotes=10,
    events=20,
    large=False,
):
    day = day or (date(2025, 4, 7) + timedelta(days=index)).isoformat()
    start, end = window(day)
    label = "synthetic-" + "s" * 52 + f"{index:02d}" if large else f"synthetic-session-{index}"
    if disposition == "reserved_metadata":
        role, publications, quotes, events = "reserved", None, None, None
    elif disposition == "empty":
        publications = quotes = events = 0
    elif disposition in ("degraded", "reconstruction_only"):
        publications = 0
    return metadata.InventorySession(
        label,
        day,
        role,
        "reserved" if role == "reserved" else "development",
        disposition,
        CONTRACTS[index % len(CONTRACTS)],
        PIN,
        start,
        end,
        quotes,
        publications,
        events,
    )


def publication(session, ordinal, *, global_index=None, large=False):
    if large:
        now = session.end_ns - (session.publication_count - ordinal) * SECOND
        quote_cursor = session.quote_count - session.publication_count + ordinal
        event_cursor = session.completed_event_count - session.publication_count + ordinal
        preceding = now - SECOND
        name = "p" * 62 + f"{global_index:02d}"
    else:
        now = session.start_ns + ordinal * SECOND
        quote_cursor, event_cursor = ordinal * 2, ordinal * 3
        preceding = None if ordinal == 0 else now - SECOND // 2
        name = f"publication-{session.source_session}-{ordinal}"
    return metadata.PublicationMetadata(
        name,
        session.source_session,
        ordinal,
        now,
        quote_cursor,
        now,
        preceding,
        event_cursor,
        now,
        PIN,
        "asserted_F_LAST",
        "b" * 64,
    )


def bundle(session, *, large=False, global_start=0):
    return metadata.SessionPublications(
        session.source_session,
        tuple(
            publication(session, ordinal, global_index=global_start + ordinal, large=large)
            for ordinal in range(session.publication_count)
        ),
    )


def cohort_from(entries, selected=2, *, bundles=None, label="synthetic-metadata-cohort"):
    accepted = tuple(entry for entry in entries if entry.disposition == "decision_session")
    chosen = accepted[:selected]
    bundles = tuple(bundle(entry) for entry in chosen) if bundles is None else tuple(bundles)
    return metadata.MetadataCohort(
        label,
        "1" * 64,
        "2" * 64,
        "3" * 64,
        "4" * 64,
        "5" * 64,
        37,
        len(entries),
        len(chosen),
        sum(len(value.publications) for value in bundles),
        tuple(entries),
        tuple(entry.source_session for entry in chosen),
        bundles,
    )


def fixture(selected=2):
    return cohort_from(
        (
            inventory(0),
            inventory(1, disposition="degraded", quotes=5, events=10),
            inventory(2),
            inventory(3),
            inventory(4, role="validation", disposition="empty"),
            inventory(5, role="test", disposition="reconstruction_only", quotes=2, events=4),
            inventory(6, disposition="reserved_metadata"),
            inventory(7, role="validation", publications=14400, quotes=2000000, events=4000000),
        ),
        selected,
    )


def capacity_fixture():
    # Sixteen civil days ending at the last date with a valid declared 16 UTC end.
    entries = []
    for index in range(16):
        day = (date(2262, 3, 27) + timedelta(days=index)).isoformat()
        if index < 3:
            entry = inventory(
                index,
                day,
                publications=(22, 21, 21)[index],
                quotes=2000000,
                events=4000000,
                large=True,
            )
        else:
            kind = DISPOSITIONS[(index - 3) % len(DISPOSITIONS)]
            role = ROLES[(index - 3) % 3]
            entry = inventory(
                index,
                day,
                role=role,
                disposition=kind,
                publications=14400,
                quotes=2000000,
                events=4000000,
                large=True,
            )
        entries.append(entry)
    bundles, offset = [], 0
    for entry in entries[:3]:
        bundles.append(bundle(entry, large=True, global_start=offset))
        offset += entry.publication_count
    return cohort_from(entries, 3, bundles=bundles, label="synthetic-" + "c" * 54)


def changed(value, **updates):
    """Bypass eager constructors only to test consuming revalidation."""
    poisoned = object.__new__(type(value))
    for field in fields(value):
        object.__setattr__(poisoned, field.name, getattr(value, field.name))
    for name, replacement in updates.items():
        object.__setattr__(poisoned, name, replacement)
    return poisoned


def remove(value, name):
    poisoned = changed(value)
    object.__delattr__(poisoned, name)
    return poisoned


def subclass(value):
    cls = type("InventedSubclass", (type(value),), {})
    poisoned = object.__new__(cls)
    for field in fields(value):
        object.__setattr__(poisoned, field.name, getattr(value, field.name))
    return poisoned


class IntSubclass(int):
    pass


class StrSubclass(str):
    pass


class TupleSubclass(tuple):
    pass


def forbidden(*unused_args, **unused_kwargs):
    raise AssertionError("Forbidden publication field traversal or external operation")


def assess(cohort, args=None, *, output=None):
    args = expectations(cohort) if args is None else args
    if output is None:
        return metadata.assess_cohort(cohort, **args)
    return metadata.verify_cohort(cohort, **args, expected_assessment_sha256=output)


def assert_complete(cohort):
    expected = result_oracle(cohort)
    result = assess(cohort)
    assert type(result) is metadata.MetadataAssessment
    assert type(result.cohort) is metadata.MetadataCohort
    assert type(result.role_counts) is tuple and type(result.disposition_counts) is tuple
    assert all(
        type(value) is tuple and type(value[1]) is int
        for value in (*result.role_counts, *result.disposition_counts)
    )
    assert canonical(asdict(result)) == canonical(expected)
    assert metadata.cohort_sha256(cohort) == expected["cohort_sha256"]
    assert (
        metadata.verify_cohort(
            cohort, **expectations(cohort), expected_assessment_sha256=expected["assessment_sha256"]
        )
        == result
    )
    assert result.authority_flags == FLAGS and all(
        flag is False for _, flag in result.authority_flags
    )
    return result


def replace_publication(cohort, publication_index=0, bundle_index=0, **updates):
    bundles = list(cohort.selected_publications)
    items = list(bundles[bundle_index].publications)
    items[publication_index] = changed(items[publication_index], **updates)
    bundles[bundle_index] = changed(bundles[bundle_index], publications=tuple(items))
    return changed(cohort, selected_publications=tuple(bundles))


def replace_inventory(cohort, index=0, **updates):
    entries = list(cohort.inventory)
    entries[index] = changed(entries[index], **updates)
    return changed(cohort, inventory=tuple(entries))


def publication_sentinel(monkeypatch, cohort):
    target = cohort.selected_publications[0].publications[0]
    original = metadata.PublicationMetadata.__getattribute__

    def blocked(self, name):
        if self is target and name in SCHEMAS["PublicationMetadata"]:
            forbidden()
        return original(self, name)

    monkeypatch.setattr(metadata.PublicationMetadata, "__getattribute__", blocked)


def test_literal_protocol_constants_exact_schemas_signatures_and_twenty_false_flags():
    assert metadata.protocol_sha256() == digest(protocol_body())
    constants = {
        "VERSION": VERSION,
        "STATUS": STATUS,
        "MAX_INVENTORY_SESSIONS": 16,
        "MAX_SELECTED_SESSIONS": 3,
        "MAX_SELECTED_PUBLICATIONS": 64,
        "MAX_SESSION_PUBLICATIONS": 14400,
        "MAX_SESSION_QUOTES": 2000000,
        "MAX_SESSION_EVENTS": 4000000,
        "MAX_CANONICAL_BYTES": 262144,
        "MAX_INT": MAX_INT,
        "SECOND_NS": SECOND,
        "DAY_NS": DAY,
        "WINDOW_START_SECONDS": 43200,
        "WINDOW_END_SECONDS": 57600,
        "MIN_PUBLICATION_CADENCE_NS": SECOND,
        "DECLARED_FEATURE_COUNT": 37,
        "SUPPORTED_CONTRACTS": CONTRACTS,
        "ROLES": ROLES,
        "DISPOSITIONS": DISPOSITIONS,
    }
    for name, value in constants.items():
        assert getattr(metadata, name) == value
    assert metadata.AUTHORITY_FLAGS == FLAGS and len(FLAGS) == 20
    for name, expected in SCHEMAS.items():
        cls = getattr(metadata, name)
        assert tuple(field.name for field in fields(cls)) == expected
        assert cls.__dataclass_params__.frozen and cls.__slots__ == expected
    api_parameters = {
        "protocol_sha256": (),
        "cohort_sha256": ("cohort",),
        "assess_cohort": ("cohort", "expected_protocol_sha256", "expected_cohort_sha256"),
        "verify_cohort": (
            "cohort",
            "expected_protocol_sha256",
            "expected_cohort_sha256",
            "expected_assessment_sha256",
        ),
    }
    for name, expected in api_parameters.items():
        signature = inspect.signature(getattr(metadata, name))
        assert tuple(signature.parameters) == expected
        assert all(
            parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        )
        assert all(
            parameter.kind
            is (
                inspect.Parameter.POSITIONAL_OR_KEYWORD
                if position == 0
                else inspect.Parameter.KEYWORD_ONLY
            )
            for position, parameter in enumerate(signature.parameters.values())
        )


@pytest.mark.parametrize("selected", (1, 2, 3))
def test_full_literal_ledger_exact_accepted_train_prefix_and_retained_disposition_counts(selected):
    cohort = fixture(selected)
    result = assert_complete(cohort)
    assert result.role_counts == (("train", 4), ("validation", 2), ("test", 1), ("reserved", 1))
    assert result.disposition_counts == (
        ("decision_session", 4),
        ("degraded", 1),
        ("empty", 1),
        ("reconstruction_only", 1),
        ("reserved_metadata", 1),
    )
    assert result.publication_count == 2 * selected
    assert result.cohort.inventory[6].quote_count is None
    assert result.cohort.inventory[4].quote_count == 0
    assert result.cohort.inventory[-1].publication_count == 14400


def test_sparse_ledger_includes_every_zero_role_and_disposition_count():
    cohort = cohort_from((inventory(0),), 1)
    result = assert_complete(cohort)
    assert result.role_counts == (("train", 1), ("validation", 0), ("test", 0), ("reserved", 0))
    assert result.disposition_counts == (
        ("decision_session", 1),
        ("degraded", 0),
        ("empty", 0),
        ("reconstruction_only", 0),
        ("reserved_metadata", 0),
    )


def test_complete_maximum_16_3_64_constructed_bodies_remain_bounded_without_universal_size_claim():
    cohort = capacity_fixture()
    result = assert_complete(cohort)
    assert (result.inventory_count, result.selected_count, result.publication_count) == (16, 3, 64)
    assert max(len(entry.source_session) for entry in cohort.inventory) == 64
    assert all(
        len(item.publication_id) == 64
        for value in cohort.selected_publications
        for item in value.publications
    )
    expected = result_oracle(cohort)
    del expected["assessment_sha256"]
    input_size, output_size = len(canonical(input_body(cohort))), len(canonical(expected))
    assert input_size < output_size <= 262144
    print(f"constructed metadata16/3/64: input={input_size} result={output_size} bytes <=262144")
    # Exact constructed measurement, not a proof of the universal maximum size.


@pytest.mark.parametrize("contract", CONTRACTS)
def test_dated_contract_is_membership_assertion_not_calendar_or_expiry_inference(contract):
    cohort = fixture(1)
    cohort = replace_inventory(cohort, contract=contract)
    result = assert_complete(cohort)
    assert result.cohort.inventory[0].contract == contract
    assert dict(result.authority_flags)["calendar_verified"] is False


BAD_PINS = (None, True, "", "a" * 63, "A" * 64, "g" * 64, StrSubclass(PIN))


@pytest.mark.parametrize(
    "name", ("expected_protocol_sha256", "expected_cohort_sha256", "expected_assessment_sha256")
)
@pytest.mark.parametrize(
    "bad", BAD_PINS, ids=lambda value: type(value).__name__ + "-" + str(value)[:8]
)
def test_all_independent_expectation_syntax_precedes_any_cohort_field(monkeypatch, name, bad):
    cohort = fixture()
    args = expectations(cohort)
    args["expected_assessment_sha256"] = result_oracle(cohort)["assessment_sha256"]
    args[name] = bad
    original = metadata.MetadataCohort.__getattribute__

    def blocked(self, field):
        if self is cohort and field in SCHEMAS["MetadataCohort"]:
            forbidden()
        return original(self, field)

    monkeypatch.setattr(metadata.MetadataCohort, "__getattribute__", blocked)
    with pytest.raises(metadata.MetadataCohortError):
        metadata.verify_cohort(cohort, **args)


def test_well_formed_wrong_protocol_refuses_before_any_cohort_access(monkeypatch):
    cohort = fixture()
    args = expectations(cohort) | {"expected_protocol_sha256": "0" * 64}
    original = metadata.MetadataCohort.__getattribute__

    def blocked(self, field):
        if self is cohort and field in SCHEMAS["MetadataCohort"]:
            forbidden()
        return original(self, field)

    monkeypatch.setattr(metadata.MetadataCohort, "__getattribute__", blocked)
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, args)


@pytest.mark.parametrize(
    "name", ("expected_protocol_sha256", "expected_cohort_sha256", "expected_assessment_sha256")
)
def test_valid_but_wrong_expectation_is_never_adopted_or_refreshed(name):
    cohort = fixture()
    args = expectations(cohort) | {
        "expected_assessment_sha256": result_oracle(cohort)["assessment_sha256"]
    }
    args[name] = "0" * 64
    with pytest.raises(metadata.MetadataCohortError):
        metadata.verify_cohort(cohort, **args)


def nested_value(cohort, name):
    return {
        "MetadataCohort": cohort,
        "InventorySession": cohort.inventory[0],
        "SessionPublications": cohort.selected_publications[0],
        "PublicationMetadata": cohort.selected_publications[0].publications[0],
    }[name]


def poison_nested(cohort, name, value):
    if name == "MetadataCohort":
        return value
    if name == "InventorySession":
        return changed(cohort, inventory=(value, *cohort.inventory[1:]))
    if name == "SessionPublications":
        return changed(cohort, selected_publications=(value, *cohort.selected_publications[1:]))
    first = cohort.selected_publications[0]
    first = changed(first, publications=(value, *first.publications[1:]))
    return changed(cohort, selected_publications=(first, *cohort.selected_publications[1:]))


MISSING_FIELDS = tuple(
    (name, field)
    for name in ("MetadataCohort", "InventorySession", "SessionPublications", "PublicationMetadata")
    for field in SCHEMAS[name]
)


@pytest.mark.parametrize("name,field", MISSING_FIELDS)
def test_every_removed_nested_field_becomes_declared_error_not_attribute_error(name, field):
    cohort = fixture()
    args = expectations(cohort)
    poisoned = remove(nested_value(cohort, name), field)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poison_nested(cohort, name, poisoned), args)


@pytest.mark.parametrize(
    "name", ("MetadataCohort", "InventorySession", "SessionPublications", "PublicationMetadata")
)
@pytest.mark.parametrize("kind", ("subclass", "mapping", "none"))
def test_every_complete_nested_type_is_exact_not_duck_typed(name, kind):
    cohort = fixture()
    args = expectations(cohort)
    value = nested_value(cohort, name)
    poisoned = (
        subclass(value) if kind == "subclass" else asdict(value) if kind == "mapping" else None
    )
    with pytest.raises(metadata.MetadataCohortError):
        assess(poison_nested(cohort, name, poisoned), args)


@pytest.mark.parametrize(
    "where", ("inventory", "selected_session_ids", "selected_publications", "publications")
)
@pytest.mark.parametrize("kind", ("list", "subclass"))
def test_all_tuple_containers_are_exact_and_never_normalized(where, kind):
    cohort = fixture()
    args = expectations(cohort)
    value = (
        cohort.selected_publications[0].publications
        if where == "publications"
        else getattr(cohort, where)
    )
    poisoned = list(value) if kind == "list" else TupleSubclass(value)
    if where == "publications":
        first = changed(cohort.selected_publications[0], publications=poisoned)
        cohort = changed(cohort, selected_publications=(first, *cohort.selected_publications[1:]))
    else:
        cohort = changed(cohort, **{where: poisoned})
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, args)


@pytest.mark.parametrize("bad", (StrSubclass("synthetic-session-0"), True))
def test_selected_identity_scalar_is_exact_before_publication_access(monkeypatch, bad):
    cohort = fixture()
    poisoned = changed(cohort, selected_session_ids=(bad, *cohort.selected_session_ids[1:]))
    args = expectations(poisoned)
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


@pytest.mark.parametrize("bad", (StrSubclass("synthetic-session-0"), True))
def test_bundle_identity_scalar_is_exact_before_publication_access(monkeypatch, bad):
    cohort = fixture()
    first = changed(cohort.selected_publications[0], source_session=bad)
    poisoned = changed(cohort, selected_publications=(first, *cohort.selected_publications[1:]))
    args = expectations(poisoned)
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


COHORT_BAD_SCALARS = (
    ("cohort_id", "ordinary"),
    ("cohort_id", "synthetic-"),
    ("cohort_id", "synthetic-é"),
    ("cohort_id", "synthetic-" + "x" * 55),
    ("cohort_id", StrSubclass("synthetic-cohort")),
    *(
        (name, "A" * 64)
        for name in (
            "collection_registration_sha256",
            "collection_receipt_sha256",
            "source_schema_sha256",
            "feature_schema_sha256",
            "feature_derivation_sha256",
        )
    ),
    ("declared_feature_count", 36),
    ("declared_feature_count", True),
    ("declared_inventory_count", 7),
    ("declared_inventory_count", IntSubclass(8)),
    ("declared_selected_count", 1),
    ("declared_selected_count", True),
    ("declared_publication_count", 3),
    ("declared_publication_count", IntSubclass(4)),
)


@pytest.mark.parametrize("field,bad", COHORT_BAD_SCALARS)
def test_every_top_scalar_metadata_guard_before_publication_fields(monkeypatch, field, bad):
    cohort = fixture()
    poisoned = changed(cohort, **{field: bad})
    args = expectations(poisoned)
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


INVENTORY_BAD_SCALARS = (
    ("source_session", "real-session"),
    ("source_session", "synthetic-"),
    ("source_session", StrSubclass("synthetic-session-0")),
    ("utc_date", "2025-4-7"),
    ("utc_date", "2025-02-30"),
    ("utc_date", StrSubclass("2025-04-07")),
    ("role", "validation_development"),
    ("role", True),
    ("partition", "reserved"),
    ("partition", StrSubclass("development")),
    ("disposition", "ignore"),
    ("disposition", StrSubclass("decision_session")),
    ("contract", "EURUSD"),
    ("contract", StrSubclass("6EM5")),
    ("source_sha256", "A" * 64),
    ("source_sha256", True),
    ("start_ns", True),
    ("start_ns", -1),
    ("end_ns", MAX_INT + 1),
    ("quote_count", True),
    ("publication_count", IntSubclass(2)),
    ("completed_event_count", None),
)


@pytest.mark.parametrize("field,bad", INVENTORY_BAD_SCALARS)
def test_every_inventory_scalar_consumption_guard_before_publication_fields(
    monkeypatch, field, bad
):
    cohort = fixture()
    poisoned = replace_inventory(cohort, **{field: bad})
    args = expectations(poisoned)
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


@pytest.mark.parametrize(
    "kind",
    (
        "last_role",
        "last_pin",
        "last_missing",
        "last_bundle_id",
        "last_bundle_count",
        "last_bundle_missing",
    ),
)
def test_invalid_last_inventory_or_bundle_refuses_before_earlier_publication_payload(
    monkeypatch, kind
):
    cohort = fixture()
    args = expectations(cohort)
    if kind.startswith("last_bundle"):
        last = cohort.selected_publications[-1]
        if kind == "last_bundle_id":
            last = changed(last, source_session="synthetic-unselected")
        elif kind == "last_bundle_count":
            last = changed(last, publications=last.publications[:-1])
        else:
            last = remove(last, "source_session")
        poisoned = changed(cohort, selected_publications=(*cohort.selected_publications[:-1], last))
    else:
        last = cohort.inventory[-1]
        if kind == "last_role":
            last = changed(last, role="ordinary")
        elif kind == "last_pin":
            last = changed(last, source_sha256="A" * 64)
        else:
            last = remove(last, "completed_event_count")
        poisoned = changed(cohort, inventory=(*cohort.inventory[:-1], last))
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


@pytest.mark.parametrize(
    "kind",
    (
        "omit_inventory",
        "reorder_inventory",
        "duplicate_session",
        "duplicate_date",
        "skip_accepted",
        "duplicate_selected",
        "reorder_selected",
        "unaccepted_selected",
        "selected_validation",
        "selected_test",
        "no_accepted",
        "reserved_bundle",
    ),
)
def test_complete_ordered_ledger_and_exact_first_train_prefix_before_publication_fields(
    monkeypatch, kind
):
    cohort = fixture()
    if kind == "omit_inventory":
        poisoned = changed(cohort, inventory=cohort.inventory[:-1])
    elif kind == "reorder_inventory":
        poisoned = changed(
            cohort, inventory=(cohort.inventory[1], cohort.inventory[0], *cohort.inventory[2:])
        )
    elif kind == "duplicate_session":
        poisoned = replace_inventory(
            cohort, index=1, source_session=cohort.inventory[0].source_session
        )
    elif kind == "duplicate_date":
        first = cohort.inventory[0]
        poisoned = replace_inventory(
            cohort, index=1, utc_date=first.utc_date, start_ns=first.start_ns, end_ns=first.end_ns
        )
    elif kind == "skip_accepted":
        poisoned = changed(
            cohort,
            selected_session_ids=(
                cohort.inventory[2].source_session,
                cohort.inventory[3].source_session,
            ),
        )
    elif kind == "duplicate_selected":
        poisoned = changed(cohort, selected_session_ids=(cohort.selected_session_ids[0],) * 2)
    elif kind == "reorder_selected":
        poisoned = changed(
            cohort, selected_session_ids=tuple(reversed(cohort.selected_session_ids))
        )
    elif kind == "unaccepted_selected":
        poisoned = changed(
            cohort,
            selected_session_ids=(
                cohort.inventory[1].source_session,
                cohort.selected_session_ids[1],
            ),
        )
    elif kind in ("selected_validation", "selected_test"):
        poisoned = replace_inventory(cohort, role=kind.removeprefix("selected_"))
    elif kind == "no_accepted":
        entries = tuple(
            changed(
                entry,
                disposition="empty",
                quote_count=0,
                publication_count=0,
                completed_event_count=0,
            )
            if entry.disposition == "decision_session"
            else entry
            for entry in cohort.inventory
        )
        poisoned = changed(cohort, inventory=entries)
    else:
        last = changed(
            cohort.selected_publications[-1], source_session=cohort.inventory[6].source_session
        )
        poisoned = changed(cohort, selected_publications=(cohort.selected_publications[0], last))
    args = expectations(poisoned)
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


DISPOSITION_FAILURES = (
    ("decision_session", "publication_count", 0),
    ("decision_session", "quote_count", 1),
    ("decision_session", "completed_event_count", 9),
    ("degraded", "publication_count", 1),
    ("degraded", "completed_event_count", 0),
    ("reconstruction_only", "publication_count", None),
    ("reconstruction_only", "quote_count", None),
    ("empty", "quote_count", 1),
    ("empty", "publication_count", None),
    ("empty", "completed_event_count", 1),
    ("reserved_metadata", "quote_count", 0),
    ("reserved_metadata", "publication_count", 0),
    ("reserved_metadata", "completed_event_count", 0),
)


@pytest.mark.parametrize("kind,field,bad", DISPOSITION_FAILURES)
def test_complete_disposition_specific_zero_null_and_count_relationships(kind, field, bad):
    cohort = fixture()
    index = next(i for i, entry in enumerate(cohort.inventory) if entry.disposition == kind)
    poisoned = replace_inventory(cohort, index=index, **{field: bad})
    args = expectations(poisoned)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


@pytest.mark.parametrize(
    "kind",
    (
        "reserved_as_train",
        "train_as_reserved",
        "reserved_degraded",
        "nonreserved_reserved",
        "development_reserved",
    ),
)
def test_role_partition_reserved_disposition_equivalence_never_invents_zero_measurements(kind):
    cohort = fixture()
    if kind == "reserved_as_train":
        poisoned = replace_inventory(cohort, index=6, role="train")
    elif kind == "train_as_reserved":
        poisoned = replace_inventory(cohort, role="reserved")
    elif kind == "reserved_degraded":
        poisoned = replace_inventory(
            cohort,
            index=6,
            disposition="degraded",
            quote_count=0,
            publication_count=0,
            completed_event_count=1,
        )
    elif kind == "nonreserved_reserved":
        poisoned = replace_inventory(
            cohort,
            disposition="reserved_metadata",
            quote_count=None,
            publication_count=None,
            completed_event_count=None,
        )
    else:
        poisoned = replace_inventory(cohort, index=6, partition="development")
    args = expectations(poisoned)
    with pytest.raises(metadata.MetadataCohortError):
        assess(poisoned, args)


PUBLICATION_BAD_SCALARS = (
    ("publication_id", "bad/id"),
    ("publication_id", StrSubclass("publication-0")),
    ("source_session", "synthetic-other"),
    ("source_session", StrSubclass("synthetic-session-0")),
    ("original_row_ordinal", True),
    ("original_row_ordinal", 1),
    ("received_at_ns", True),
    ("received_at_ns", 0),
    ("original_first_quote_cursor", True),
    ("original_first_quote_cursor", -1),
    ("original_first_quote_cursor", 10),
    ("first_quote_received_at_ns", None),
    ("first_quote_received_at_ns", 0),
    ("preceding_quote_received_at_ns", 0),
    ("preceding_quote_received_at_ns", False),
    ("completed_event_cursor", True),
    ("completed_event_cursor", -1),
    ("completed_event_cursor", 20),
    ("completed_event_received_at_ns", None),
    ("completed_event_received_at_ns", 0),
    ("completed_event_prefix_sha256", "A" * 64),
    ("completion_marker", "F_LAST"),
    ("completion_marker", StrSubclass("asserted_F_LAST")),
    ("feature_publication_ref_sha256", "a" * 63),
)


@pytest.mark.parametrize("field,bad", PUBLICATION_BAD_SCALARS)
def test_every_publication_scalar_with_matching_manual_malformed_input_pin(field, bad):
    cohort = replace_publication(fixture(), **{field: bad})
    # Retaining this malformed body's own independent pin rules out a stale-pin
    # mismatch as the reason the complete consuming metadata guard refuses.
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort))


def linked_publications():
    cohort = cohort_from((inventory(0, quotes=100, events=200),), 1)
    start = cohort.inventory[0].start_ns
    first = changed(
        cohort.selected_publications[0].publications[0],
        received_at_ns=start + SECOND,
        first_quote_received_at_ns=start + SECOND,
        completed_event_received_at_ns=start + SECOND,
        original_first_quote_cursor=10,
        completed_event_cursor=20,
        preceding_quote_received_at_ns=start,
    )
    second = changed(
        cohort.selected_publications[0].publications[1],
        received_at_ns=start + 2 * SECOND,
        first_quote_received_at_ns=start + 2 * SECOND,
        completed_event_received_at_ns=start + 2 * SECOND,
        original_first_quote_cursor=12,
        completed_event_cursor=23,
        preceding_quote_received_at_ns=start + SECOND + SECOND // 2,
    )
    value = changed(cohort.selected_publications[0], publications=(first, second))
    return changed(cohort, selected_publications=(value,))


@pytest.mark.parametrize("adjacent", (False, True))
def test_nonzero_first_cursor_consistent_predecessor_event_delta_and_suffix_equalities(adjacent):
    cohort = linked_publications()
    first = cohort.selected_publications[0].publications[0]
    if adjacent:
        cohort = replace_publication(
            cohort,
            1,
            original_first_quote_cursor=11,
            completed_event_cursor=21,
            preceding_quote_received_at_ns=first.received_at_ns,
        )
    result = assert_complete(cohort)
    assert result.cohort.selected_publications[0].publications[0].original_first_quote_cursor == 10
    assert dict(result.authority_flags)["first_cursor_verified"] is False
    assert dict(result.authority_flags)["event_prefix_verified"] is False


@pytest.mark.parametrize(
    "kind",
    (
        "earlier_predecessor",
        "adjacent_wrong_predecessor",
        "equal_time_predecessor",
        "too_small_event_delta",
        "too_small_event_suffix",
        "event_before_quote",
        "duplicate_quote_cursor",
        "decreasing_quote_cursor",
        "duplicate_event_cursor",
        "decreasing_event_cursor",
        "positive_no_predecessor",
        "positive_predecessor_before_window",
        "short_cadence",
        "duplicate_publication_id",
        "skipped_ordinal",
    ),
)
def test_inferable_cross_publication_consistency_not_authenticated_source_truth(kind):
    cohort = linked_publications()
    first, second = cohort.selected_publications[0].publications
    changes = {
        "earlier_predecessor": {"preceding_quote_received_at_ns": first.received_at_ns - 1},
        "adjacent_wrong_predecessor": {
            "original_first_quote_cursor": 11,
            "completed_event_cursor": 21,
        },
        "equal_time_predecessor": {"preceding_quote_received_at_ns": second.received_at_ns},
        "too_small_event_delta": {"original_first_quote_cursor": 20, "completed_event_cursor": 25},
        "too_small_event_suffix": {"completed_event_cursor": 190},
        "duplicate_quote_cursor": {"original_first_quote_cursor": 10},
        "decreasing_quote_cursor": {"original_first_quote_cursor": 9},
        "duplicate_event_cursor": {"completed_event_cursor": 20},
        "decreasing_event_cursor": {"completed_event_cursor": 19},
        "positive_no_predecessor": {"preceding_quote_received_at_ns": None},
        "positive_predecessor_before_window": {
            "preceding_quote_received_at_ns": cohort.inventory[0].start_ns - 1
        },
        "short_cadence": {
            "received_at_ns": second.received_at_ns - 1,
            "first_quote_received_at_ns": second.received_at_ns - 1,
            "completed_event_received_at_ns": second.received_at_ns - 1,
        },
        "duplicate_publication_id": {"publication_id": first.publication_id},
        "skipped_ordinal": {"original_row_ordinal": 2},
    }
    if kind == "event_before_quote":
        cohort = replace_publication(cohort, completed_event_cursor=9)
    else:
        cohort = replace_publication(cohort, 1, **changes[kind])
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort))


def test_publication_identifiers_are_unique_across_bundles_not_only_inside_one_session():
    cohort = fixture()
    first = cohort.selected_publications[0].publications[0]
    cohort = replace_publication(cohort, bundle_index=1, publication_id=first.publication_id)
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort))


@pytest.mark.parametrize(
    "kind", ("before_start", "at_end", "wrong_day_window", "negative_day", "overflow_day")
)
def test_civil_day_window_and_publication_exact_interval_boundaries(kind):
    cohort = fixture()
    entry = cohort.inventory[0]
    if kind == "before_start":
        now = entry.start_ns - 1
        cohort = replace_publication(
            cohort,
            received_at_ns=now,
            first_quote_received_at_ns=now,
            completed_event_received_at_ns=now,
        )
    elif kind == "at_end":
        now = entry.end_ns
        cohort = replace_publication(
            cohort,
            received_at_ns=now,
            first_quote_received_at_ns=now,
            completed_event_received_at_ns=now,
        )
    elif kind == "wrong_day_window":
        cohort = replace_inventory(cohort, start_ns=entry.start_ns + 1)
    else:
        day = "1969-12-31" if kind == "negative_day" else "2262-04-12"
        start, end = window(day)
        cohort = replace_inventory(cohort, utc_date=day, start_ns=start, end_ns=end)
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort))


@pytest.mark.parametrize("day", ("1970-01-01", "2262-04-11"))
def test_integer_utc_window_endpoints_are_valid_without_host_timezone_or_calendar_claim(day):
    cohort = cohort_from((inventory(0, day),), 1)
    result = assert_complete(cohort)
    assert result.cohort.inventory[0].start_ns == window(day)[0]
    assert result.cohort.inventory[0].end_ns <= MAX_INT
    assert dict(result.authority_flags)["calendar_verified"] is False


@pytest.mark.parametrize(
    "kind",
    (
        "zero_inventory",
        "seventeen_inventory",
        "zero_selected",
        "four_selected",
        "zero_publications",
        "sixtyfive_publications",
        "session_publications_excess",
        "session_quotes_excess",
        "session_events_excess",
    ),
)
def test_every_declared_input_bound_refuses_whole_without_truncation(kind):
    cohort = capacity_fixture()
    if kind == "zero_inventory":
        cohort = changed(cohort, inventory=(), declared_inventory_count=0)
    elif kind == "seventeen_inventory":
        cohort = changed(
            cohort, inventory=(*cohort.inventory, cohort.inventory[-1]), declared_inventory_count=17
        )
    elif kind == "zero_selected":
        cohort = changed(
            cohort,
            selected_session_ids=(),
            selected_publications=(),
            declared_selected_count=0,
            declared_publication_count=0,
        )
    elif kind == "four_selected":
        cohort = changed(
            cohort,
            selected_session_ids=(*cohort.selected_session_ids, cohort.inventory[3].source_session),
            declared_selected_count=4,
        )
    elif kind == "zero_publications":
        first = changed(cohort.selected_publications[0], publications=())
        cohort = changed(cohort, selected_publications=(first, *cohort.selected_publications[1:]))
    elif kind == "sixtyfive_publications":
        first = cohort.selected_publications[0]
        first = changed(first, publications=(*first.publications, first.publications[-1]))
        cohort = changed(
            cohort,
            selected_publications=(first, *cohort.selected_publications[1:]),
            declared_publication_count=65,
        )
        cohort = replace_inventory(cohort, publication_count=23)
    else:
        field, value = {
            "session_publications_excess": ("publication_count", 14401),
            "session_quotes_excess": ("quote_count", 2000001),
            "session_events_excess": ("completed_event_count", 4000001),
        }[kind]
        cohort = replace_inventory(cohort, index=3, **{field: value})
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort))


@pytest.mark.parametrize(
    "name,value",
    (("MAX_INVENTORY_SESSIONS", 7), ("MAX_SELECTED_SESSIONS", 1), ("MAX_SELECTED_PUBLICATIONS", 3)),
)
def test_lowered_outer_runtime_bounds_are_defensive_not_a_new_protocol(monkeypatch, name, value):
    cohort = fixture()
    args = expectations(cohort)
    monkeypatch.setattr(metadata, name, value)
    assert metadata.protocol_sha256() == args["expected_protocol_sha256"]
    publication_sentinel(monkeypatch, cohort)
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, args)


def test_complete_protocol_exact_and_excess_canonical_body_cap(monkeypatch):
    expected, size = digest(protocol_body()), len(canonical(protocol_body()))
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size)
    assert metadata.protocol_sha256() == expected
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size - 1)
    with pytest.raises(metadata.MetadataCohortError):
        metadata.protocol_sha256()


def test_complete_input_hash_exact_cap_stops_before_larger_result_body(monkeypatch):
    cohort = capacity_fixture()
    args = expectations(cohort)
    size = len(canonical(input_body(cohort)))
    assert size > len(canonical(protocol_body()))
    result = result_oracle(cohort)
    del result["assessment_sha256"]
    assert len(canonical(result)) > size
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size)
    assert metadata.protocol_sha256() == args["expected_protocol_sha256"]
    assert metadata.cohort_sha256(cohort) == args["expected_cohort_sha256"]
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, args)
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size - 1)
    with pytest.raises(metadata.MetadataCohortError):
        metadata.cohort_sha256(cohort)


def test_full_assessment_exact_cap_and_excess_for_both_assessment_and_verification(monkeypatch):
    cohort = capacity_fixture()
    expected = result_oracle(cohort)
    body = dict(expected)
    del body["assessment_sha256"]
    size, args = len(canonical(body)), expectations(cohort)
    assert len(canonical(input_body(cohort))) < size - 1
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size)
    assert canonical(asdict(assess(cohort, args))) == canonical(expected)
    assert canonical(
        asdict(assess(cohort, args, output=expected["assessment_sha256"]))
    ) == canonical(expected)
    monkeypatch.setattr(metadata, "MAX_CANONICAL_BYTES", size - 1)
    assert metadata.cohort_sha256(cohort) == args["expected_cohort_sha256"]
    for verify in (False, True):
        with pytest.raises(metadata.MetadataCohortError):
            assess(cohort, args, output=expected["assessment_sha256"] if verify else None)


@pytest.mark.parametrize(
    "api", ("protocol_sha256", "cohort_sha256", "assess_cohort", "verify_cohort")
)
@pytest.mark.parametrize("exception", (ValueError, TypeError, AttributeError, OverflowError))
def test_canonical_failures_are_normalized_as_declared_errors(api, exception, monkeypatch):
    cohort = fixture()
    args, result = expectations(cohort), result_oracle(cohort)

    def failed(*unused_args, **unused_kwargs):
        raise exception("Invented encoder failure")

    monkeypatch.setattr(metadata.json, "dumps", failed)
    with pytest.raises(metadata.MetadataCohortError):
        if api == "protocol_sha256":
            metadata.protocol_sha256()
        elif api == "cohort_sha256":
            metadata.cohort_sha256(cohort)
        else:
            assess(
                cohort, args, output=result["assessment_sha256"] if api == "verify_cohort" else None
            )


@pytest.mark.parametrize(
    "component",
    ("excluded_count", "later_publication_ref", "opaque_derivation_ref", "reserved_source_ref"),
)
def test_complete_opaque_identity_changes_not_earlier_assertions_or_external_proof(component):
    original = fixture()
    expected = result_oracle(original)
    if component == "excluded_count":
        altered = replace_inventory(original, index=1, completed_event_count=11)
    elif component == "later_publication_ref":
        altered = replace_publication(
            original, 1, bundle_index=1, feature_publication_ref_sha256="c" * 64
        )
    elif component == "opaque_derivation_ref":
        altered = changed(original, feature_derivation_sha256="d" * 64)
    else:
        altered = replace_inventory(original, index=6, source_sha256="e" * 64)
    with pytest.raises(metadata.MetadataCohortError):
        assess(altered, expectations(original), output=expected["assessment_sha256"])
    result = assert_complete(altered)
    assert result.cohort_sha256 != expected["cohort_sha256"]
    assert result.assessment_sha256 != expected["assessment_sha256"]
    assert result.cohort.selected_publications[0] == original.selected_publications[0]
    assert result.inventory_count == expected["inventory_count"]
    assert result.publication_count == expected["publication_count"]
    assert all(flag is False for _, flag in result.authority_flags)


@pytest.mark.parametrize(
    "field",
    (
        "cohort",
        "role_counts",
        "disposition_counts",
        "publication_count",
        "authority_flags",
        "protocol_sha256",
    ),
)
def test_full_result_verifier_rebuilds_every_body_field_not_just_headline_counts(field):
    cohort = fixture()
    altered = json.loads(canonical(result_oracle(cohort)))
    del altered["assessment_sha256"]
    if field == "cohort":
        altered[field]["feature_derivation_sha256"] = "e" * 64
    elif field in ("role_counts", "disposition_counts"):
        altered[field][-1][1] += 1
    elif field == "publication_count":
        altered[field] += 1
    elif field == "authority_flags":
        altered[field][0][1] = True
    else:
        altered[field] = "0" * 64
    with pytest.raises(metadata.MetadataCohortError):
        assess(cohort, expectations(cohort), output=digest(altered))


def test_repeatable_frozen_slotted_input_output_and_no_hidden_external_hooks(monkeypatch):
    cohort = fixture()
    args, expected = expectations(cohort), result_oracle(cohort)
    before = canonical(asdict(cohort))
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(io, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "open", forbidden)
    monkeypatch.setattr(pathlib.Path, "read_bytes", forbidden)
    monkeypatch.setattr(pathlib.Path, "read_text", forbidden)
    monkeypatch.setattr(hashlib, "file_digest", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(time, "time", forbidden)
    monkeypatch.setattr(time, "monotonic", forbidden)
    monkeypatch.setattr(time, "perf_counter", forbidden)
    assert metadata.protocol_sha256() == args["expected_protocol_sha256"]
    assert metadata.cohort_sha256(cohort) == args["expected_cohort_sha256"]
    first = assess(cohort, args)
    second = assess(cohort, args, output=expected["assessment_sha256"])
    assert canonical(asdict(first)) == canonical(expected)
    assert second == first and second is not first
    assert canonical(asdict(cohort)) == before
    for value in (
        cohort,
        cohort.inventory[0],
        cohort.selected_publications[0],
        cohort.selected_publications[0].publications[0],
        first,
    ):
        assert not hasattr(value, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(value, fields(value)[0].name, None)


def test_source_is_stdlib_only_and_has_no_loader_rich_data_or_dynamic_import_hook():
    tree = ast.parse(inspect.getsource(metadata))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] in sys.stdlib_module_names for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.module.split(".")[0] in sys.stdlib_module_names
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"open", "eval", "exec", "compile", "__import__"}
    assert not {"load", "run", "main", "train", "predict", "trade", "advance", "read_rows"} & set(
        vars(metadata)
    )


def test_outer_input_constructors_validate_only_their_own_metadata_not_publication_children(
    monkeypatch,
):
    cohort = fixture()
    bundle_value = cohort.selected_publications[0]
    context = {field: getattr(cohort, field) for field in SCHEMAS["MetadataCohort"]}
    publication_sentinel(monkeypatch, cohort)
    rebuilt_bundle = metadata.SessionPublications(
        bundle_value.source_session, bundle_value.publications
    )
    rebuilt_cohort = metadata.MetadataCohort(**context)
    assert rebuilt_bundle.publications is bundle_value.publications
    assert rebuilt_cohort.selected_publications is cohort.selected_publications
    assert rebuilt_cohort.inventory is cohort.inventory


@pytest.mark.parametrize(
    "name,field,bad",
    (
        ("InventorySession", "source_sha256", "A" * 64),
        ("PublicationMetadata", "completion_marker", "F_LAST"),
        ("SessionPublications", "source_session", "ordinary"),
        ("MetadataCohort", "declared_feature_count", True),
    ),
)
def test_input_constructors_refuse_their_own_invalid_scalar_metadata(name, field, bad):
    cohort = fixture()
    original = nested_value(cohort, name)
    context = {key: getattr(original, key) for key in SCHEMAS[name]}
    context[field] = bad
    with pytest.raises(metadata.MetadataCohortError):
        getattr(metadata, name)(**context)
