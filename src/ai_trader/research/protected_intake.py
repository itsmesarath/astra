"""Custodian-side protected dataset intake. Reads targets, never trains or claims independence."""

import argparse
import hashlib
import os
from decimal import InvalidOperation
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2
from ai_trader.research.advisory_evaluation import (
    AdvisorySuite,
    _parse_cases,
    _validate_suite,
    load_suite,
    model_input,
    read_pinned,
    scenario_fingerprint,
)
from ai_trader.research.spot_long_checks import CHECK_VERSION, assess_spot_long
from ai_trader.training.advisory_curriculum import _bounded_artifact, _fields
from ai_trader.training.advisory_holdout import audit_reservation, reservation_template

DATASET_KIND = "advisory_protected_dataset_v1"
RECEIPT_KIND = "advisory_protected_intake_v1"
PROTECTED_SPLIT = "protected_eval"


def _inspect_dataset(exposed_suite, dataset, dataset_sha256):
    """Derive metadata from actual payloads, without certifying their unseen origin/semantics.

    This belongs on the evaluation custodian side, NOT in training launch preparation.
    Only the pending registry may be passed to that metadata-only training interface.
    """
    _bounded_artifact(dataset)
    _fields(dataset, ("schema_version", "kind", "dataset_id", "review_contract", "cases"))
    if (
        type(dataset["schema_version"]) is not int
        or dataset["schema_version"] != 1
        or dataset["kind"] != DATASET_KIND
        or dataset["review_contract"] != SPOT_LONG_V2
    ):
        raise ValueError("Unsupported protected dataset contract.")
    protected = AdvisorySuite(dataset["dataset_id"], dataset_sha256, _parse_cases(dataset["cases"]))
    _validate_suite(protected, allowed_splits=(PROTECTED_SPLIT,))
    registry = reservation_template(exposed_suite)
    registry["dataset_sha256"] = dataset_sha256
    counts = dict.fromkeys(("support", "veto", "preflight_refusal"), 0)
    for case in protected.cases:
        # Negative preflight examples may be stale/future, but cannot disguise another session.
        if any(e.source_session != case.source_session for e in case.snapshot.evidence):
            raise ValueError("Protected evidence must belong to its declared source session.")
        assessment = assess_spot_long(case.snapshot, case.source_session)
        if case.expected != "preflight_refusal":
            expected = {"conditional_support": "support", "veto": "veto"}.get(assessment["status"])
            if expected != case.expected:
                raise ValueError("Protected target disagrees with the numeric rubric.")
        # _validate_suite already requires refusals to match the real local input preflight,
        # and forbids rationale/citation targets on refused inputs.
        counts[case.expected] += 1
        registry["cases"].append(
            {
                "case_id": case.case_id,
                "family": case.family,
                "source_session": case.source_session,
                "input_sha256": digest(model_input(case, SPOT_LONG_V2)),
                "scenario_sha256": scenario_fingerprint(case.snapshot),
            }
        )
    audit = audit_reservation(exposed_suite, registry)
    if not all(counts.values()):
        raise ValueError("Protected intake requires support, veto and input-refusal coverage.")
    # This is deliberately still pending. No caller-provided identity or switch can complete it.
    receipt = {
        "schema_version": 1,
        "kind": RECEIPT_KIND,
        "dataset_sha256": dataset_sha256,
        "exposed_suite_sha256": exposed_suite.sha256,
        "registry_sha256": digest(registry),
        "check_version": CHECK_VERSION,
        "case_count": len(protected.cases),
        "counts_by_expected": counts,
        "payload_structure_checked": True,
        "declared_targets_match_mechanical_rubric": True,
        "declared_metadata_disjoint": audit["declared_metadata_disjoint"],
        "custodian_process_opened_contents": True,
        "training_process_opened_contents": False,
        "target_semantics_reviewed": False,
        "independence_authenticated": False,
        "near_duplicates_checked": False,
        "reservation_complete": False,
        "reservation_blockers": audit["blockers"],
        "model_calls": 0,
        "optimization_steps": 0,
        "orders": 0,
        "training_allowed": False,
        "promotion_allowed": False,
        "execution_allowed": False,
    }
    _bounded_artifact(registry)
    _bounded_artifact(receipt)
    return registry, receipt


def prepare_intake(exposed_suite, dataset_path, dataset_sha256):
    """Read one bounded, byte-pinned private dataset; emit only metadata and a receipt."""
    return _inspect_dataset(
        exposed_suite, read_pinned(dataset_path, dataset_sha256), dataset_sha256
    )


def verify_intake(exposed_suite, dataset_path, dataset_sha256, registry, receipt):
    """Custodian-side reconstruction; never infer real provenance from self-consistent hashes."""
    _bounded_artifact(registry)
    _bounded_artifact(receipt)
    rebuilt_registry, rebuilt_receipt = prepare_intake(exposed_suite, dataset_path, dataset_sha256)
    if canonical(registry) != canonical(rebuilt_registry) or canonical(receipt) != canonical(
        rebuilt_receipt
    ):
        raise ValueError("Protected intake reconstruction mismatch.")


def _write_new(path, value):
    encoded = (_bounded_artifact(value) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(encoded).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--suite-sha256", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--dataset-sha256", required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--registry-sha256")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--receipt-sha256")
    args = parser.parse_args()
    verification = (args.registry, args.registry_sha256, args.receipt, args.receipt_sha256)
    if args.action == "prepare":
        if args.output_dir is None or any(v is not None for v in verification):
            parser.error("prepare requires only --output-dir besides the pinned inputs.")
    elif args.output_dir is not None or any(v is None for v in verification):
        parser.error("verify requires --registry/--receipt with both raw hashes, no output.")
    try:
        # Refuse obvious collisions before opening protected content. mkdir remains exclusive.
        if args.output_dir is not None and (
            args.output_dir.exists()
            or args.output_dir.is_symlink()
            or not args.output_dir.parent.is_dir()
        ):
            raise ValueError("New output directory with an existing parent required.")
        suite = load_suite(args.suite, args.suite_sha256)
        if args.action == "verify":
            verify_intake(
                suite,
                args.dataset,
                args.dataset_sha256,
                read_pinned(args.registry, args.registry_sha256),
                read_pinned(args.receipt, args.receipt_sha256),
            )
            print("Protected intake reconstructed; no training or independence authorization.")
            return
        registry, receipt = prepare_intake(suite, args.dataset, args.dataset_sha256)
        # All checks complete before claiming output. Preserve partials after any I/O failure;
        # a receipt is written last and must independently verify before it is trusted.
        args.output_dir.mkdir()
        _write_new(args.output_dir / "registry.json", registry)
        _write_new(args.output_dir / "receipt.json", receipt)
        print("Protected intake prepared; reservation remains pending. No targets printed.")
    except (ValueError, TypeError, OSError, InvalidOperation, RecursionError):
        # Do not print payload/label/decimal/parser details to a training-side transcript.
        parser.exit(2, "Protected intake refused or incomplete; no verified result is claimed.\n")


if __name__ == "__main__":
    main()
