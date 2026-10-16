"""Offline synthetic advisory curriculum and recorded-response checks; never calls a model."""

import argparse
import hashlib
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.models.local_reviewer import (
    LocalReviewerConfig,
    LocalReviewError,
    build_request,
    prompt_for_contract,
)
from ai_trader.models.review_contracts import (
    LEGACY_V1,
    REVIEW_CONTRACTS,
    SPOT_LONG_V2,
    review_task,
    validate_contract,
)
from ai_trader.research.council import Evidence, ResearchSnapshot, parse_role_report

MAX_FILE_BYTES = 1024 * 1024
SPLITS = ("curriculum_draft", "development_eval")
REVIEW_STATUS = "agent_draft_requires_operator_review"


@dataclass(frozen=True, slots=True)
class AdvisoryCase:
    case_id: str
    family: str
    split: str
    source_session: str
    snapshot: ResearchSnapshot
    expected: str
    citation_groups: tuple[tuple[str, ...], ...]
    reference_rationale: str | None


@dataclass(frozen=True, slots=True)
class AdvisorySuite:
    suite_id: str
    sha256: str
    cases: tuple[AdvisoryCase, ...]


def _object(value, fields):
    if type(value) is not dict or set(value) != set(fields.split()):
        raise ValueError("Unexpected artifact fields.")


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", value):
        raise ValueError("Invalid bounded identifier.")


def read_pinned(path, expected_sha256):
    check_digest(expected_sha256)
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise ValueError("Explicit regular artifact file required.")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Artifact size or SHA256 mismatch.")
    return strict_json(raw)


def model_input(case, review_contract=LEGACY_V1):
    """Only model-visible data; never expected labels, split, family or reference rationale."""
    payload = {
        "role": "analyst",
        "symbol": case.snapshot.symbol,
        "as_of_ms": case.snapshot.as_of_ms,
        "evidence": [{**asdict(e), "value": str(e.value)} for e in case.snapshot.evidence],
        "prior": [],
    }
    task = review_task(review_contract)
    if task is not None:
        payload["review_task"] = task
    return payload


def artifact_contract_fields(review_contract):
    """Legacy artifacts stay byte-compatible; V2 input bindings are never inferred as V1."""
    validate_contract(review_contract)
    return (
        {"schema_version": 1}
        if review_contract == LEGACY_V1
        else {"schema_version": 2, "review_contract": review_contract}
    )


def _response_contract(data):
    if (
        type(data) is not dict
        or type(data.get("schema_version")) is not int
        or data["schema_version"] not in (1, 2)
    ):
        raise ValueError("Unsupported response version.")
    fields = "schema_version suite_sha256 producer responses"
    if data["schema_version"] == 1:
        _object(data, fields)
        return LEGACY_V1
    _object(data, fields + " review_contract")
    if data["review_contract"] != SPOT_LONG_V2:
        raise ValueError("V2 responses require the explicit Spot-long contract.")
    return SPOT_LONG_V2


def reference_response(case):
    if case.expected == "preflight_refusal":
        return None
    ids = tuple(dict.fromkeys(group[0] for group in case.citation_groups))
    return canonical(
        {"verdict": case.expected, "evidence_ids": ids, "rationale": case.reference_rationale}
    )


def _decimal_key(value):
    # Decimal.normalize() uses the ambient precision and can round distinct long values.
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return (0, (0,), 0)
    while digits[-1] == 0:
        digits, exponent = digits[:-1], exponent + 1
    return (sign, digits, exponent)


def scenario_fingerprint(snapshot):
    """Exact normalized evidence identity, not semantic/near-duplicate detection."""
    return digest(
        sorted(
            (
                e.symbol,
                e.metric,
                _decimal_key(e.value),
                e.event_time_ms - snapshot.as_of_ms,
                e.available_time_ms - snapshot.as_of_ms,
            )
            for e in snapshot.evidence
        )
    )


def _validate_suite(suite, *, allowed_splits=SPLITS):
    if type(suite) is not AdvisorySuite or type(suite.cases) is not tuple:
        raise ValueError("Typed immutable suite required.")
    _identifier(suite.suite_id)
    check_digest(suite.sha256)
    if not 1 <= len(suite.cases) <= 64:
        raise ValueError("Supply 1-64 cases.")
    ids, family_splits, session_families, contents = set(), {}, {}, set()
    for case in suite.cases:
        if type(case) is not AdvisoryCase or type(case.snapshot) is not ResearchSnapshot:
            raise ValueError("Typed case and snapshot required.")
        for value in (case.case_id, case.family, case.source_session):
            _identifier(value)
        if case.case_id in ids or case.split not in allowed_splits:
            raise ValueError("Duplicate case or invalid development split.")
        ids.add(case.case_id)
        if family_splits.setdefault(case.family, case.split) != case.split:
            raise ValueError("Scenario family crosses splits.")
        if session_families.setdefault(case.source_session, case.family) != case.family:
            raise ValueError("Source session reused across scenario families.")
        if case.expected not in ("support", "veto", "preflight_refusal"):
            raise ValueError("Unknown expected behavior.")
        if type(case.citation_groups) is not tuple or len(case.citation_groups) > 16:
            raise ValueError("Invalid citation requirement groups.")
        evidence_ids = {e.evidence_id for e in case.snapshot.evidence}
        for group in case.citation_groups:
            if (
                type(group) is not tuple
                or not 1 <= len(group) <= 16
                or any(type(i) is not str for i in group)
                or len(set(group)) != len(group)
                or not set(group) <= evidence_ids
            ):
                raise ValueError("Invalid required citation group.")
        # Disallow exact normalized duplicates, even if IDs/session names have been relabeled.
        content_hash = scenario_fingerprint(case.snapshot)
        if content_hash in contents:
            raise ValueError("Duplicate scenario content after removing identifiers.")
        contents.add(content_hash)
        refused = False
        try:
            build_request(LocalReviewerConfig(case.source_session), "analyst", case.snapshot, ())
        except LocalReviewError:
            refused = True
        if refused != (case.expected == "preflight_refusal"):
            raise ValueError(
                "Expected input boundary disagrees with the actual reviewer preflight."
            )
        if refused:
            if case.reference_rationale is not None or case.citation_groups:
                raise ValueError("Preflight refusals cannot become model-training targets.")
        else:
            if not case.citation_groups:
                raise ValueError("Review cases require decisive citation groups.")
            parse_role_report(reference_response(case), "analyst", case.snapshot)


def _parse_cases(items):
    """Shared strict evidence parser; each caller must validate its own envelope and split."""
    if type(items) is not list or not 1 <= len(items) <= 64:
        raise ValueError("Case budget exceeded.")
    cases = []
    for item in items:
        _object(
            item,
            "case_id family split source_session as_of_ms evidence expected "
            "citation_groups reference_rationale",
        )
        if type(item["evidence"]) is not list or not 1 <= len(item["evidence"]) <= 32:
            raise ValueError("Invalid evidence budget.")
        evidence = []
        for e in item["evidence"]:
            _object(
                e, "evidence_id symbol source_session metric value event_time_ms available_time_ms"
            )
            if type(e["value"]) is not str or len(e["value"]) > 128:
                raise ValueError("Bounded decimal string required.")
            evidence.append(Evidence(**{**e, "value": Decimal(e["value"])}))
        if type(item["citation_groups"]) is not list or any(
            type(g) is not list for g in item["citation_groups"]
        ):
            raise ValueError("Citation groups must be lists.")
        cases.append(
            AdvisoryCase(
                item["case_id"],
                item["family"],
                item["split"],
                item["source_session"],
                ResearchSnapshot("BTCUSDT", item["as_of_ms"], tuple(evidence)),
                item["expected"],
                tuple(tuple(g) for g in item["citation_groups"]),
                item["reference_rationale"],
            )
        )
    return tuple(cases)


def load_suite(path, expected_sha256):
    data = read_pinned(path, expected_sha256)
    _object(data, "schema_version suite_id review_status cases")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported suite version.")
    if data["review_status"] != REVIEW_STATUS or type(data["cases"]) is not list:
        raise ValueError("Only explicitly unapproved synthetic development cases are supported.")
    suite = AdvisorySuite(data["suite_id"], expected_sha256, _parse_cases(data["cases"]))
    _validate_suite(suite)
    return suite


def reference_responses(suite, review_contract=LEGACY_V1):
    """Harness demonstration only: repeats authored targets, not an independent evaluation."""
    _validate_suite(suite)
    return {
        **artifact_contract_fields(review_contract),
        "suite_sha256": suite.sha256,
        "producer": {
            "kind": "synthetic_reference",
            "model_id": "authored-reference",
            "checkpoint_sha256": None,
            "prompt_sha256": None,
        },
        "responses": [
            {
                "case_id": c.case_id,
                "input_sha256": digest(model_input(c, review_contract)),
                "status": "preflight_refused" if c.expected == "preflight_refusal" else "completed",
                "raw_response": reference_response(c),
            }
            for c in suite.cases
        ],
    }


def _validate_responses(suite, data):
    contract = _response_contract(data)
    if data["suite_sha256"] != suite.sha256:
        raise ValueError("Response suite binding mismatch.")
    producer = data["producer"]
    _object(producer, "kind model_id checkpoint_sha256 prompt_sha256")
    _identifier(producer["model_id"])
    if producer["kind"] == "recorded":
        check_digest(producer["checkpoint_sha256"])
        check_digest(producer["prompt_sha256"])
        if contract == SPOT_LONG_V2 and producer["prompt_sha256"] != digest(
            prompt_for_contract(contract)
        ):
            raise ValueError("V2 response prompt binding mismatch.")
    elif producer != {
        "kind": "synthetic_reference",
        "model_id": "authored-reference",
        "checkpoint_sha256": None,
        "prompt_sha256": None,
    }:
        raise ValueError("Invalid producer identity.")
    if type(data["responses"]) is not list or len(data["responses"]) > len(suite.cases):
        raise ValueError("Invalid response budget.")
    known, responses = {c.case_id for c in suite.cases}, {}
    for row in data["responses"]:
        _object(row, "case_id input_sha256 status raw_response")
        if (
            type(row["case_id"]) is not str
            or row["case_id"] not in known
            or row["case_id"] in responses
        ):
            raise ValueError("Unknown or duplicate response case.")
        check_digest(row["input_sha256"])
        if row["status"] not in ("completed", "preflight_refused", "failed"):
            raise ValueError("Invalid response status.")
        raw = row["raw_response"]
        if row["status"] == "completed":
            if type(raw) is not str or len(raw) > 8192:
                raise ValueError("Recorded raw response budget exceeded.")
        elif raw is not None:
            raise ValueError("A refused/failed invocation cannot claim a model response.")
        responses[row["case_id"]] = row
    return responses


def _score_case(case, response, review_contract=LEGACY_V1):
    result = {
        "case_id": case.case_id,
        "family": case.family,
        "split": case.split,
        "expected": case.expected,
        "observed_verdict": None,
        "schema_valid": None,
        "verdict_match": False,
        "citation_requirements_met": False,
        "machine_checks_pass": False,
        "unsafe_support": False,
        "rationale_quality": "not_assessed_requires_operator_review",
        "raw_response": None,
    }
    if response is None:
        return {**result, "status": "missing"}
    result["raw_response"] = response["raw_response"]
    if response["input_sha256"] != digest(model_input(case, review_contract)):
        return {**result, "status": "input_binding_mismatch"}
    if case.expected == "preflight_refusal":
        passed = response["status"] == "preflight_refused"
        return {
            **result,
            "status": "preflight_correct" if passed else "preflight_failure",
            "machine_checks_pass": passed,
        }
    if response["status"] != "completed":
        return {**result, "status": "review_not_completed"}
    try:
        report = parse_role_report(response["raw_response"], "analyst", case.snapshot)
    except (ValueError, TypeError, RecursionError):
        return {**result, "status": "invalid_schema", "schema_valid": False}
    match = report.verdict == case.expected
    citations = all(set(group) & set(report.evidence_ids) for group in case.citation_groups)
    return {
        **result,
        "status": "checks_pass" if match and citations else "verdict_or_citation_failure",
        "observed_verdict": report.verdict,
        "schema_valid": True,
        "verdict_match": match,
        "citation_requirements_met": citations,
        "machine_checks_pass": match and citations,
        "unsafe_support": report.verdict == "support" and case.expected == "veto",
    }


def _summary(rows):
    review = [r for r in rows if r["expected"] != "preflight_refusal"]
    recalls = {}
    for verdict in ("support", "veto"):
        subset = [r for r in review if r["expected"] == verdict]
        recalls[verdict] = sum(r["verdict_match"] for r in subset) / len(subset) if subset else None
    balanced = sum(recalls.values()) / 2 if all(v is not None for v in recalls.values()) else None
    return {
        "case_count": len(rows),
        "missing_count": sum(r["status"] == "missing" for r in rows),
        "coverage_complete": all(r["status"] != "missing" for r in rows),
        "machine_checks_passed": sum(r["machine_checks_pass"] for r in rows),
        "all_machine_checks_pass": bool(rows) and all(r["machine_checks_pass"] for r in rows),
        "schema_valid_count": sum(r["schema_valid"] is True for r in review),
        "review_case_count": len(review),
        "unsafe_support_count": sum(r["unsafe_support"] for r in review),
        "support_recall": recalls["support"],
        "veto_recall": recalls["veto"],
        "balanced_verdict_accuracy": balanced,
        "preflight_correct_count": sum(r["status"] == "preflight_correct" for r in rows),
    }


def score_responses(suite, data):
    _validate_suite(suite)
    responses = _validate_responses(suite, data)
    contract = _response_contract(data)
    rows = [_score_case(c, responses.get(c.case_id), contract) for c in suite.cases]
    return {
        **artifact_contract_fields(contract),
        "kind": "synthetic_advisory_development_score",
        "suite_id": suite.suite_id,
        "suite_sha256": suite.sha256,
        "responses_sha256": digest(data),
        "producer": dict(data["producer"]),
        "review_status": REVIEW_STATUS,
        "summary": _summary(rows),
        "by_split": {split: _summary([r for r in rows if r["split"] == split]) for split in SPLITS},
        "cases": rows,
        "training_export_allowed": False,
        "promotion_allowed": False,
        "model_calls": 0,
        "orders": 0,
    }


def recorded_smoke_responses(suite, smoke, case_id):
    """Bind an existing smoke reply to its original request; no checkpoint/weights are opened."""
    case = next((c for c in suite.cases if c.case_id == case_id), None)
    if case is None or case.expected == "preflight_refusal" or type(smoke) is not dict:
        raise ValueError("Unknown or ineligible smoke case.")
    if (
        type(smoke.get("schema_version")) is not int
        or smoke["schema_version"] != 1
        or smoke.get("kind") != "synthetic_qwen_smoke"
        or smoke.get("generation_completed") is not True
        or type(smoke.get("orders")) is not int
        or smoke["orders"] != 0
        or smoke.get("training_started") is not False
        or smoke.get("promotion_allowed") is not False
    ):
        raise ValueError("Not a completed non-executing synthetic smoke artifact.")
    configuration = dict(smoke["configuration"])
    for name in ("checkpoint_path", "python_executable"):
        configuration[name] = Path(configuration[name])
    config = LocalReviewerConfig(**configuration)
    if (
        config.backend != "transformers"
        or config.model_id != "Qwen/Qwen3-4B-Base"
        or config.source_session != case.source_session
        or config.max_calls != 1
        or config.review_contract != LEGACY_V1
    ):
        raise ValueError("Unexpected smoke scope.")
    request = build_request(config, "analyst", case.snapshot, ())
    if (
        smoke.get("request_sha256") != digest(request)
        or smoke.get("prompt_sha256") != request["prompt_sha256"]
    ):
        raise ValueError("Recorded smoke request/prompt binding mismatch.")
    return {
        "schema_version": 1,
        "suite_sha256": suite.sha256,
        "producer": {
            "kind": "recorded",
            "model_id": config.model_id,
            "checkpoint_sha256": config.checkpoint_sha256,
            "prompt_sha256": request["prompt_sha256"],
        },
        "responses": [
            {
                "case_id": case.case_id,
                "input_sha256": digest(model_input(case)),
                "status": "completed",
                "raw_response": smoke["raw_response"],
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--suite-sha256", required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--demo", action="store_true")
    choice.add_argument("--responses", type=Path)
    choice.add_argument("--smoke", type=Path)
    parser.add_argument("--artifact-sha256")
    parser.add_argument("--smoke-case")
    parser.add_argument("--review-contract", choices=REVIEW_CONTRACTS, default=LEGACY_V1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.demo and args.review_contract != LEGACY_V1:
        parser.error(
            "--review-contract is only for --demo; recorded artifacts carry their contract."
        )
    suite = load_suite(args.suite, args.suite_sha256)
    if args.demo:
        data = reference_responses(suite, args.review_contract)
    elif args.responses:
        data = read_pinned(args.responses, args.artifact_sha256)
    else:
        data = recorded_smoke_responses(
            suite,
            read_pinned(args.smoke, args.artifact_sha256),
            args.smoke_case,
        )
    report = score_responses(suite, data)
    report["source_artifact_sha256"] = args.artifact_sha256 if not args.demo else None
    encoded = canonical(report)
    if len(encoded.encode()) > 2 * MAX_FILE_BYTES:
        raise ValueError("Output report budget exceeded.")
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(encoded + "\n")
    print(
        canonical(
            {
                "producer": report["producer"],
                "summary": report["summary"],
                "model_calls": 0,
                "training_export_allowed": False,
                "promotion_allowed": False,
            }
        )
    )
    return 0 if report["summary"]["all_machine_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
