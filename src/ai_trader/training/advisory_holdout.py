"""Metadata-only protected evaluation reservation; never reads held-out examples or targets."""

from ai_trader.models.local_checkpoint import canonical, check_digest, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2
from ai_trader.research.advisory_evaluation import (
    _identifier,
    _validate_suite,
    model_input,
    scenario_fingerprint,
)
from ai_trader.training.advisory_curriculum import _attestation, _bounded_artifact, _fields

REGISTRY_KIND = "advisory_protected_eval_reservation_v1"
INDEX_FIELDS = ("case_id", "family", "source_session", "input_sha256", "scenario_sha256")


def exposure_inventory(suite):
    """All known cases are exposed, including rejected curriculum and visible development."""
    _validate_suite(suite)
    return [
        {
            "case_id": c.case_id,
            "family": c.family,
            "source_session": c.source_session,
            "input_sha256": digest(model_input(c, SPOT_LONG_V2)),
            "scenario_sha256": scenario_fingerprint(c.snapshot),
        }
        for c in suite.cases
    ]


def reservation_template(suite):
    return {
        "schema_version": 1,
        "kind": REGISTRY_KIND,
        "review_contract": SPOT_LONG_V2,
        "exposed_suite_sha256": suite.sha256,
        "exposure_inventory_sha256": digest(exposure_inventory(suite)),
        "fingerprint_version": "normalized_numeric_evidence_v1",
        "dataset_sha256": None,
        "unexposed_attested": False,
        "attestation": {
            "reviewer_type": "operator",
            "reviewer_id": None,
            "reviewed_at_utc": None,
            "confirmed": False,
        },
        "cases": [],
    }


def audit_reservation(suite, registry):
    """Check declared disjointness; a custodian remains responsible for truthful metadata."""
    _bounded_artifact(registry)
    template = reservation_template(suite)
    _fields(registry, template)
    for key in template.keys() - {"dataset_sha256", "unexposed_attested", "attestation", "cases"}:
        if canonical(registry[key]) != canonical(template[key]):
            raise ValueError("Protected-evaluation binding mismatch: " + key)
    operator = _attestation(registry["attestation"])
    if type(registry["unexposed_attested"]) is not bool:
        raise ValueError("Unexposed attestation must be a boolean.")
    if registry["dataset_sha256"] is not None:
        check_digest(registry["dataset_sha256"])
        if registry["dataset_sha256"] == suite.sha256:
            raise ValueError("The exposed suite cannot become final evaluation.")
    cases = registry["cases"]
    if type(cases) is not list or len(cases) > 64:
        raise ValueError("Protected index must contain at most 64 entries.")
    exposed = exposure_inventory(suite)
    known = {key: {c[key] for c in exposed} for key in INDEX_FIELDS}
    seen = {key: set() for key in INDEX_FIELDS}
    sessions = {}
    for row in cases:
        # No payload, label or filesystem path is permitted in this metadata-only interface.
        _fields(row, INDEX_FIELDS)
        for key in INDEX_FIELDS:
            (_identifier if key in ("case_id", "family", "source_session") else check_digest)(
                row[key]
            )
            if row[key] in known[key]:
                raise ValueError("Protected index overlaps exposed " + key)
            if key in ("case_id", "input_sha256", "scenario_sha256") and row[key] in seen[key]:
                raise ValueError("Duplicate protected " + key)
            seen[key].add(row[key])
        if sessions.setdefault(row["source_session"], row["family"]) != row["family"]:
            raise ValueError("Protected source session crosses families.")
    blockers = []
    if not cases:
        blockers.append("protected_index_missing")
    if registry["dataset_sha256"] is None:
        blockers.append("protected_dataset_pin_missing")
    if not operator or not registry["unexposed_attested"]:
        blockers.append("custodian_unexposed_attestation_required")
    return {
        "kind": "advisory_protected_eval_reservation_audit_v1",
        "registry_sha256": digest(registry),
        "exposed_case_count": len(exposed),
        "protected_case_count": len(cases),
        "declared_metadata_disjoint": True,
        "reservation_complete": not blockers,
        "blockers": blockers,
        "heldout_contents_opened": False,
        "heldout_contents_verified": False,
        "independence_authenticated": False,
        "near_duplicates_checked": False,
        "training_allowed": False,
        "promotion_allowed": False,
    }
