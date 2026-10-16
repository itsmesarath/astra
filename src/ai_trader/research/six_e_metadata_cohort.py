"""Pure consistency checks for complete invented metadata cohorts.

Retained source, event-prefix and feature references are opaque assertions.
This module neither opens their referents nor authenticates provenance.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from functools import wraps

VERSION = "six_e_metadata_cohort_v1"
STATUS = "constructed_metadata_consistency_not_provenance"
MAX_INVENTORY_SESSIONS = 16
MAX_SELECTED_SESSIONS = 3
MAX_SELECTED_PUBLICATIONS = 64
MAX_SESSION_PUBLICATIONS = 14400
MAX_SESSION_QUOTES = 2000000
MAX_SESSION_EVENTS = 4000000
MAX_CANONICAL_BYTES = 262144
MAX_INT = 9223372036854775807
SECOND_NS = 1000000000
DAY_NS = 86400000000000
WINDOW_START_SECONDS = 43200
WINDOW_END_SECONDS = 57600
MIN_PUBLICATION_CADENCE_NS = 1000000000
DECLARED_FEATURE_COUNT = 37
SUPPORTED_CONTRACTS = ("6EM5", "6EU5", "6EZ5", "6EH6")
ROLES = ("train", "validation", "test", "reserved")
DISPOSITIONS = (
    "decision_session",
    "degraded",
    "empty",
    "reconstruction_only",
    "reserved_metadata",
)

AUTHORITY_FLAGS = tuple(
    (name, False)
    for name in (
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
)

_INVENTORY_FIELDS = (
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
)
_PUBLICATION_FIELDS = (
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
)
_BUNDLE_FIELDS = ("source_session", "publications")
_COHORT_FIELDS = (
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
)
_ASSESSMENT_FIELDS = (
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
)


class MetadataCohortError(ValueError):
    """The complete declared metadata is malformed or inconsistent."""


def _guard(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except MetadataCohortError:
            raise
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise MetadataCohortError("Malformed complete metadata or canonical body") from exc

    return checked


def _require(condition, message):
    if not condition:
        raise MetadataCohortError(message)


def _integer(value, minimum=0, maximum=MAX_INT):
    _require(type(value) is int and minimum <= value <= maximum, "Exact bounded integer required")


def _identifier(value, *, synthetic=False):
    _require(
        type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value) is not None,
        "Exact bounded ASCII identifier required",
    )
    if synthetic:
        _require(
            value.startswith("synthetic-") and len(value) > len("synthetic-"),
            "Invented synthetic identifier required",
        )


def _pin(value):
    _require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "Exact lowercase SHA256 required",
    )


def _read(value, cls, names):
    _require(type(value) is cls, "Exact complete metadata class required")
    return {name: getattr(value, name) for name in names}


def _encoded(body):
    raw = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    encoded = raw.encode("utf-8")
    _require(len(encoded) <= MAX_CANONICAL_BYTES, "Complete canonical body exceeds fixed bound")
    return encoded


def _digest(body):
    return hashlib.sha256(_encoded(body)).hexdigest()


@dataclass(frozen=True, slots=True)
class InventorySession:
    source_session: str
    utc_date: str
    role: str
    partition: str
    disposition: str
    contract: str
    source_sha256: str
    start_ns: int
    end_ns: int
    quote_count: int | None
    publication_count: int | None
    completed_event_count: int | None

    def __post_init__(self):
        _inventory_metadata(self)


@dataclass(frozen=True, slots=True)
class PublicationMetadata:
    publication_id: str
    source_session: str
    original_row_ordinal: int
    received_at_ns: int
    original_first_quote_cursor: int
    first_quote_received_at_ns: int
    preceding_quote_received_at_ns: int | None
    completed_event_cursor: int
    completed_event_received_at_ns: int
    completed_event_prefix_sha256: str
    completion_marker: str
    feature_publication_ref_sha256: str

    def __post_init__(self):
        _publication_metadata(self)


@dataclass(frozen=True, slots=True)
class SessionPublications:
    source_session: str
    publications: tuple[PublicationMetadata, ...]

    def __post_init__(self):
        _bundle_metadata(self)


@dataclass(frozen=True, slots=True)
class MetadataCohort:
    cohort_id: str
    collection_registration_sha256: str
    collection_receipt_sha256: str
    source_schema_sha256: str
    feature_schema_sha256: str
    feature_derivation_sha256: str
    declared_feature_count: int
    declared_inventory_count: int
    declared_selected_count: int
    declared_publication_count: int
    inventory: tuple[InventorySession, ...]
    selected_session_ids: tuple[str, ...]
    selected_publications: tuple[SessionPublications, ...]

    def __post_init__(self):
        _outer_metadata(self)


@dataclass(frozen=True, slots=True)
class MetadataAssessment:
    version: str
    status: str
    protocol_sha256: str
    cohort_sha256: str
    cohort: MetadataCohort
    inventory_count: int
    selected_count: int
    publication_count: int
    role_counts: tuple[tuple[str, int], ...]
    disposition_counts: tuple[tuple[str, int], ...]
    assessment_sha256: str
    authority_flags: tuple[tuple[str, bool], ...]


@_guard
def _inventory_metadata(value):
    item = _read(value, InventorySession, _INVENTORY_FIELDS)
    _identifier(item["source_session"], synthetic=True)
    _pin(item["source_sha256"])
    _require(type(item["utc_date"]) is str, "Canonical ISO UTC date required")
    day = date.fromisoformat(item["utc_date"])
    _require(day.isoformat() == item["utc_date"], "Canonical ISO UTC date required")
    _integer(item["start_ns"])
    _integer(item["end_ns"])
    day_start = (day - date(1970, 1, 1)).days * DAY_NS
    _require(
        item["start_ns"] == day_start + WINDOW_START_SECONDS * SECOND_NS
        and item["end_ns"] == day_start + WINDOW_END_SECONDS * SECOND_NS
        and item["start_ns"] < item["end_ns"],
        "Exact declared UTC research window required",
    )
    for name, choices in (
        ("role", ROLES),
        ("partition", ("development", "reserved")),
        ("disposition", DISPOSITIONS),
        ("contract", SUPPORTED_CONTRACTS),
    ):
        _require(
            type(item[name]) is str and item[name] in choices, "Closed session metadata required"
        )
    reserved = item["role"] == "reserved"
    _require(
        item["partition"] == ("reserved" if reserved else "development")
        and (item["disposition"] == "reserved_metadata") == reserved,
        "Original role, partition and disposition must agree",
    )
    if reserved:
        _require(
            all(
                item[name] is None
                for name in ("quote_count", "publication_count", "completed_event_count")
            ),
            "Reserved metadata counts must remain null",
        )
        return item
    _integer(item["quote_count"], maximum=MAX_SESSION_QUOTES)
    _integer(item["publication_count"], maximum=MAX_SESSION_PUBLICATIONS)
    _integer(item["completed_event_count"], maximum=MAX_SESSION_EVENTS)
    if item["disposition"] == "decision_session":
        _require(
            1 <= item["publication_count"] <= item["quote_count"] <= item["completed_event_count"],
            "Complete positive decision, quote and event counts required",
        )
    elif item["disposition"] in ("degraded", "reconstruction_only"):
        _require(
            item["publication_count"] == 0
            and 1 <= item["completed_event_count"]
            and item["quote_count"] <= item["completed_event_count"],
            "Excluded reconstruction/degraded counts must remain complete",
        )
    else:
        _require(
            item["quote_count"] == item["publication_count"] == item["completed_event_count"] == 0,
            "Empty session must retain zero complete counts",
        )
    return item


@_guard
def _publication_metadata(value):
    item = _read(value, PublicationMetadata, _PUBLICATION_FIELDS)
    _identifier(item["publication_id"])
    _identifier(item["source_session"], synthetic=True)
    _pin(item["completed_event_prefix_sha256"])
    _pin(item["feature_publication_ref_sha256"])
    for name in (
        "original_row_ordinal",
        "received_at_ns",
        "original_first_quote_cursor",
        "first_quote_received_at_ns",
        "completed_event_cursor",
        "completed_event_received_at_ns",
    ):
        _integer(item[name])
    _require(
        item["first_quote_received_at_ns"] == item["received_at_ns"]
        and item["completed_event_received_at_ns"] == item["received_at_ns"],
        "Declared first quote and source completion must have the publication receive time",
    )
    if item["original_first_quote_cursor"] == 0:
        _require(item["preceding_quote_received_at_ns"] is None, "Cursor zero has no predecessor")
    else:
        _integer(item["preceding_quote_received_at_ns"])
        _require(
            item["preceding_quote_received_at_ns"] < item["received_at_ns"],
            "Declared immediate predecessor must be strictly earlier",
        )
    _require(
        type(item["completion_marker"]) is str and item["completion_marker"] == "asserted_F_LAST",
        "Only an asserted completion marker is admitted",
    )
    return item


@_guard
def _bundle_metadata(value):
    item = _read(value, SessionPublications, _BUNDLE_FIELDS)
    _identifier(item["source_session"], synthetic=True)
    _require(type(item["publications"]) is tuple, "Exact publication tuple required")
    _require(
        1 <= len(item["publications"]) <= MAX_SELECTED_PUBLICATIONS,
        "Complete bounded publication tuple required",
    )
    return item


@_guard
def _outer_metadata(value):
    item = _read(value, MetadataCohort, _COHORT_FIELDS)
    _identifier(item["cohort_id"], synthetic=True)
    for name in (
        "collection_registration_sha256",
        "collection_receipt_sha256",
        "source_schema_sha256",
        "feature_schema_sha256",
        "feature_derivation_sha256",
    ):
        _pin(item[name])
    _integer(item["declared_feature_count"], DECLARED_FEATURE_COUNT, DECLARED_FEATURE_COUNT)
    for count, values, maximum in (
        ("declared_inventory_count", "inventory", MAX_INVENTORY_SESSIONS),
        ("declared_selected_count", "selected_session_ids", MAX_SELECTED_SESSIONS),
    ):
        _integer(item[count], 1, maximum)
        _require(
            type(item[values]) is tuple and len(item[values]) == item[count],
            "Complete exact tuple count required",
        )
    _integer(item["declared_publication_count"], 1, MAX_SELECTED_PUBLICATIONS)
    _require(
        type(item["selected_publications"]) is tuple
        and len(item["selected_publications"]) == item["declared_selected_count"],
        "Complete selected bundle tuple count required",
    )
    return item


def _protocol_body():
    # Literal protocol bounds never resize when a defensive runtime cap is lowered.
    return {
        "version": "six_e_metadata_cohort_v1",
        "status": "constructed_metadata_consistency_not_provenance",
        "bounds": {
            "max_inventory_sessions": 16,
            "max_selected_sessions": 3,
            "max_selected_publications": 64,
            "max_session_publications": 14400,
            "max_session_quotes": 2000000,
            "max_session_events": 4000000,
            "max_int": 9223372036854775807,
            "max_canonical_bytes": 262144,
        },
        "scope": {
            "identifier_pattern": "[A-Za-z0-9][A-Za-z0-9_-]{0,63}",
            "synthetic_prefix": "synthetic-",
            "roles": ("train", "validation", "test", "reserved"),
            "dispositions": (
                "decision_session",
                "degraded",
                "empty",
                "reconstruction_only",
                "reserved_metadata",
            ),
            "partitions": ("development", "reserved"),
            "contracts": ("6EM5", "6EU5", "6EZ5", "6EH6"),
            "selected_role": "train",
            "selection": "first_accepted_decision_session_prefix",
            "window_start_seconds": 43200,
            "window_end_seconds": 57600,
            "min_publication_cadence_ns": 1000000000,
            "declared_feature_count": 37,
            "completion_marker": "asserted_F_LAST",
            "reference_scope": "opaque_assertions_not_source_or_feature_verification",
        },
        "schemas": {
            "InventorySession": _INVENTORY_FIELDS,
            "PublicationMetadata": _PUBLICATION_FIELDS,
            "SessionPublications": _BUNDLE_FIELDS,
            "MetadataCohort": _COHORT_FIELDS,
            "MetadataAssessment": _ASSESSMENT_FIELDS,
        },
        "authority_flags": AUTHORITY_FLAGS,
    }


def _prepare(cohort):
    outer = _outer_metadata(cohort)
    inventory = tuple(_inventory_metadata(value) for value in outer["inventory"])
    session_ids = tuple(item["source_session"] for item in inventory)
    dates = tuple(item["utc_date"] for item in inventory)
    _require(
        len(set(session_ids)) == len(session_ids), "Complete inventory session IDs must be unique"
    )
    _require(
        tuple(sorted(set(dates))) == dates,
        "Complete inventory dates must be unique and chronological",
    )
    selected_ids = outer["selected_session_ids"]
    for session_id in selected_ids:
        _identifier(session_id, synthetic=True)
    accepted = tuple(item for item in inventory if item["disposition"] == "decision_session")
    selected = accepted[: outer["declared_selected_count"]]
    _require(
        selected_ids == tuple(item["source_session"] for item in selected)
        and len(selected) == outer["declared_selected_count"],
        "Only the original first accepted decision-session prefix is admitted",
    )
    _require(
        all(item["role"] == "train" and item["partition"] == "development" for item in selected),
        "Every selected session must retain train/development scope",
    )

    # Finish every bundle's metadata before reading any publication assertion.
    bundles = tuple(_bundle_metadata(value) for value in outer["selected_publications"])
    _require(
        tuple(item["source_session"] for item in bundles) == selected_ids,
        "Complete original selected bundle order required",
    )
    for bundle, session in zip(bundles, selected, strict=True):
        _require(
            len(bundle["publications"]) == session["publication_count"],
            "Every selected publication assertion must be retained",
        )
    publication_count = sum(len(item["publications"]) for item in bundles)
    _require(
        publication_count == outer["declared_publication_count"]
        and 1 <= publication_count <= MAX_SELECTED_PUBLICATIONS,
        "Complete selected publication total exceeds or differs from declaration",
    )

    publication_ids = set()
    for bundle, session in zip(bundles, selected, strict=True):
        prior = None
        for ordinal, value in enumerate(bundle["publications"]):
            item = _publication_metadata(value)
            _require(
                item["publication_id"] not in publication_ids,
                "Publication IDs must be globally unique",
            )
            publication_ids.add(item["publication_id"])
            _require(
                item["source_session"] == session["source_session"]
                and item["original_row_ordinal"] == ordinal,
                "Complete original session and contiguous row identity required",
            )
            now, cursor, event_cursor = (
                item["received_at_ns"],
                item["original_first_quote_cursor"],
                item["completed_event_cursor"],
            )
            _require(
                session["start_ns"] <= now < session["end_ns"],
                "Publication is outside declared window",
            )
            _require(
                cursor < session["quote_count"] and event_cursor < session["completed_event_count"],
                "Original cursor exceeds its complete declared count",
            )
            if cursor:
                _require(
                    session["start_ns"] <= item["preceding_quote_received_at_ns"],
                    "Declared predecessor is outside session",
                )
            _require(
                cursor <= event_cursor
                and session["completed_event_count"] - event_cursor - 1
                >= session["quote_count"] - cursor - 1,
                "Declared event/quote mapping or remaining suffix is inconsistent",
            )
            if prior is not None:
                cursor_delta = cursor - prior["original_first_quote_cursor"]
                event_delta = event_cursor - prior["completed_event_cursor"]
                _require(
                    now - prior["received_at_ns"] >= MIN_PUBLICATION_CADENCE_NS
                    and cursor_delta > 0
                    and event_delta >= cursor_delta,
                    "Original publication cadence and cursor deltas must be complete "
                    "and increasing",
                )
                _require(
                    item["preceding_quote_received_at_ns"] >= prior["received_at_ns"]
                    and (
                        cursor_delta != 1
                        or item["preceding_quote_received_at_ns"] == prior["received_at_ns"]
                    ),
                    "Declared predecessor contradicts an earlier publication quote",
                )
            prior = item
    return outer, inventory, publication_count


def _input_body(cohort, protocol_pin):
    return {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": protocol_pin,
        "cohort": asdict(cohort),
    }


@_guard
def protocol_sha256() -> str:
    """Hash only the complete literal protocol; access no cohort."""
    return _digest(_protocol_body())


@_guard
def cohort_sha256(cohort: MetadataCohort) -> str:
    """Validate and hash the complete bounded input, without constructing a result."""
    protocol_pin = protocol_sha256()
    _prepare(cohort)
    return _digest(_input_body(cohort, protocol_pin))


def _assess(cohort, expected_protocol_sha256, expected_cohort_sha256):
    _pin(expected_protocol_sha256)
    _pin(expected_cohort_sha256)
    protocol_pin = protocol_sha256()
    _require(protocol_pin == expected_protocol_sha256, "Original complete protocol pin differs")
    outer, inventory, publication_count = _prepare(cohort)
    cohort_pin = _digest(_input_body(cohort, protocol_pin))
    _require(cohort_pin == expected_cohort_sha256, "Original complete metadata cohort pin differs")
    roles = tuple((role, sum(item["role"] == role for item in inventory)) for role in ROLES)
    dispositions = tuple(
        (kind, sum(item["disposition"] == kind for item in inventory)) for kind in DISPOSITIONS
    )
    body = {
        "version": VERSION,
        "status": STATUS,
        "protocol_sha256": protocol_pin,
        "cohort_sha256": cohort_pin,
        "cohort": asdict(cohort),
        "inventory_count": len(inventory),
        "selected_count": len(outer["selected_session_ids"]),
        "publication_count": publication_count,
        "role_counts": roles,
        "disposition_counts": dispositions,
        "authority_flags": AUTHORITY_FLAGS,
    }
    assessment_pin = _digest(body)
    return MetadataAssessment(
        VERSION,
        STATUS,
        protocol_pin,
        cohort_pin,
        cohort,
        len(inventory),
        len(outer["selected_session_ids"]),
        publication_count,
        roles,
        dispositions,
        assessment_pin,
        AUTHORITY_FLAGS,
    )


@_guard
def assess_cohort(
    cohort: MetadataCohort,
    *,
    expected_protocol_sha256: str,
    expected_cohort_sha256: str,
) -> MetadataAssessment:
    """Assess all invented metadata assertions without opening their referents."""
    return _assess(cohort, expected_protocol_sha256, expected_cohort_sha256)


@_guard
def verify_cohort(
    cohort: MetadataCohort,
    *,
    expected_protocol_sha256: str,
    expected_cohort_sha256: str,
    expected_assessment_sha256: str,
) -> MetadataAssessment:
    """Rebuild the complete original input/result; accept no submitted assessment."""
    # All independent expectation syntax precedes even the protocol comparison.
    _pin(expected_protocol_sha256)
    _pin(expected_cohort_sha256)
    _pin(expected_assessment_sha256)
    result = _assess(cohort, expected_protocol_sha256, expected_cohort_sha256)
    _require(
        result.assessment_sha256 == expected_assessment_sha256,
        "Original complete assessment pin differs",
    )
    return result
