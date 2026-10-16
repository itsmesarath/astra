"""Build a self-contained offline operator review page; never approve, train or place orders."""

import argparse
import base64
import hashlib
import os
from importlib.resources import files
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2_PROMPT
from ai_trader.research.advisory_evaluation import load_suite, read_pinned
from ai_trader.research.advisory_fact_audit import curriculum_review_packet
from ai_trader.research.council import parse_role_report
from ai_trader.training.advisory_curriculum import audit_review, prepare_review

MAX_HTML_BYTES = 1024 * 1024


def build_payload(suite, proposal, proposal_raw_sha256):
    """Validate pinned proposals, but reset every operator decision/check/identity in the page."""
    check_digest(proposal_raw_sha256)
    audit_review(suite, proposal)  # Bind original evidence, targets, prompt and numeric facts.
    review = prepare_review(suite)
    proposals = {row["case_id"]: row for row in proposal["cases"]}
    facts = {row["case_id"]: row for row in curriculum_review_packet(suite)["cases"]}
    cases = {case.case_id: case for case in suite.cases}
    material = []
    for row in review["cases"]:
        case_id = row["case_id"]
        source, fact, case = proposals[case_id], facts[case_id], cases[case_id]
        target = parse_role_report(source["target_response"], "analyst", case.snapshot)
        if (
            target.verdict != case.expected
            or not all(set(group) & set(target.evidence_ids) for group in case.citation_groups)
            or fact["draft_verdict_agrees_with_numeric_check"] is not True
        ):
            raise ValueError("Proposed target fails verdict/citation/numeric checks.")
        row["target_response"] = source["target_response"]
        material.append({**fact, "proposal_note": source["note"]})
    return {
        "kind": "advisory_operator_workbench_v1",
        "proposal_raw_sha256": proposal_raw_sha256,
        "proposal_canonical_sha256": digest(proposal),
        "review": review,
        "material": material,
        "system_prompt": SPOT_LONG_V2_PROMPT,
        "mechanical_checks_passed": True,
        "rationale_semantics_verified": False,
        "training_allowed": False,
        "execution_allowed": False,
    }


def _csp_hash(text):
    return "sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()


def render_page(payload):
    assets = files("ai_trader.training").joinpath("assets")
    template = assets.joinpath("review_workbench.html").read_text(encoding="utf-8")
    script = assets.joinpath("review_workbench.js").read_text(encoding="utf-8")
    style = assets.joinpath("review_workbench.css").read_text(encoding="utf-8")
    # JSON remains inert even if supplied notes/metrics contain </script> or HTML-like text.
    data = (
        canonical(payload).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    )
    if len(data.encode()) > MAX_HTML_BYTES:
        raise ValueError("Review payload byte budget exceeded.")
    csp = (
        "default-src 'none'; connect-src 'none'; img-src 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'; "
        f"script-src '{_csp_hash(script)}'; style-src '{_csp_hash(style)}'"
    )
    # Substitute source placeholders once, never recursively through untrusted evidence text.
    parts = {
        "@@CSP@@": csp,
        "@@STYLE@@": style,
        "@@SCRIPT@@": script,
        "@@DATA@@": data,
    }
    import re

    page = re.sub(r"@@(?:CSP|STYLE|SCRIPT|DATA)@@", lambda m: parts[m[0]], template)
    if len(page.encode()) > MAX_HTML_BYTES:
        raise ValueError("Review page byte budget exceeded.")
    return page


def build_page(suite_path, suite_sha256, proposal_path, proposal_sha256, output):
    if output.suffix.lower() != ".html":
        raise ValueError("An explicit new .html output is required.")
    suite = load_suite(suite_path, suite_sha256)
    proposal = read_pinned(proposal_path, proposal_sha256)
    page = render_page(build_payload(suite, proposal, proposal_sha256))
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(page)
        stream.flush()
        os.fsync(stream.fileno())
    return {
        "output": str(output),
        "html_sha256": hashlib.sha256(page.encode()).hexdigest(),
        "operator_decisions": 0,
        "training_allowed": False,
        "execution_allowed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--suite-sha256", required=True)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--proposal-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = build_page(
        args.suite, args.suite_sha256, args.proposal, args.proposal_sha256, args.output
    )
    print(canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
