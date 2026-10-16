"""Offline rendering and synthetic review tests; never operator approvals of real targets."""

import copy
import hashlib
import json
import re
import shutil
import subprocess
from importlib.resources import files
from pathlib import Path

import pytest

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.research.advisory_evaluation import load_suite
from ai_trader.training import review_workbench as workbench
from ai_trader.training.advisory_curriculum import SEMANTIC_CHECKS, audit_review, prepare_review

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "configs/qwen_review_cases_v1.json"
SUITE_SHA = "5f192268d4c1d72f49262a530054713bf2556f0641a3cfc4164f30e46ed56659"


@pytest.fixture
def suite():
    return load_suite(SUITE, SUITE_SHA)


@pytest.fixture
def proposal(suite):
    result = prepare_review(suite)
    result["attestation"].update(
        reviewer_type="agent",
        reviewer_id="synthetic-agent",
        confirmed=True,
        reviewed_at_utc="2026-09-24T00:00:00Z",
    )
    for row in result["cases"]:
        row["decision"] = "approve"
        row["checks"] = dict.fromkeys(SEMANTIC_CHECKS, True)
        row["note"] = "Synthetic test findings, never a human approval."
    return result


def payload(suite, proposal):
    return workbench.build_payload(suite, proposal, digest(proposal))


@pytest.mark.parametrize("reviewer_type", ["agent", "operator"])
def test_page_resets_all_inherited_findings(suite, proposal, reviewer_type):
    proposal["attestation"]["reviewer_type"] = reviewer_type
    before = copy.deepcopy(proposal)
    result = payload(suite, proposal)
    review = result["review"]
    assert proposal == before
    assert review["attestation"] == {
        "reviewer_type": "operator",
        "confirmed": False,
        "reviewer_id": None,
        "reviewed_at_utc": None,
    }
    assert len(review["cases"]) == len(result["material"]) == 14
    assert all(row["decision"] == "pending" and row["note"] == "" for row in review["cases"])
    assert all(set(row["checks"].values()) == {None} for row in review["cases"])
    assert not audit_review(suite, review)["candidate_export_allowed"]
    assert result["training_allowed"] is False
    assert result["rationale_semantics_verified"] is False
    assert result["execution_allowed"] is False


def test_only_curriculum_evidence_and_exact_proposed_targets(suite, proposal):
    result = payload(suite, proposal)
    expected = [c.case_id for c in suite.cases if c.split == "curriculum_draft"]
    assert [r["case_id"] for r in result["material"]] == expected
    assert [r["case_id"] for r in result["review"]["cases"]] == expected
    for case, row, original in zip(
        result["material"], result["review"]["cases"], proposal["cases"], strict=True
    ):
        assert row["target_response"] == original["target_response"]
        assert case["proposal_note"] == original["note"]
        assert "numerical_assessment" in case and "input" in case


@pytest.mark.parametrize("change", ["binding", "verdict", "citations", "null", "schema"])
def test_invalid_proposals_refuse_even_when_pending(suite, proposal, change):
    row = proposal["cases"][0]
    row["decision"] = "pending"
    target = json.loads(row["target_response"])
    if change == "binding":
        row["binding_sha256"] = "0" * 64
    elif change == "verdict":
        target["verdict"] = "support"
    elif change == "citations":
        target["evidence_ids"] = []
    elif change == "schema":
        target["extra"] = "unknown"
    row["target_response"] = None if change == "null" else canonical(target)
    with pytest.raises((ValueError, TypeError)):
        payload(suite, proposal)


def test_embedded_data_cannot_end_script_or_expand_template(suite, proposal):
    attack = '</script><img src="https://invalid.invalid/leak" onerror="alert(1)">@@SCRIPT@@&'
    proposal["cases"][0]["note"] = attack
    result = payload(suite, proposal)
    page = workbench.render_page(result)
    assert attack not in page
    assert '<img src="https://invalid.invalid/leak"' not in page
    assert "\\u003c/script\\u003e" in page
    data = re.search(
        r'<script id="workbench-data" type="application/json">(.*?)</script>', page, re.S
    )
    assert json.loads(data[1])["material"][0]["proposal_note"] == attack
    assert page.count("<script") == page.count("</script>") == 2


def test_csp_hashes_and_no_external_scripts_forms_or_storage(suite, proposal):
    page = workbench.render_page(payload(suite, proposal))
    script = re.findall(r"<script>(.*?)</script>", page, re.S)[0]
    style = re.findall(r"<style>(.*?)</style>", page, re.S)[0]
    assert workbench._csp_hash(script) in page
    assert workbench._csp_hash(style) in page
    for rule in (
        "default-src 'none'",
        "connect-src 'none'",
        "form-action 'none'",
        "base-uri 'none'",
    ):
        assert rule in page
    for forbidden in (
        "innerHTML",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sendBeacon",
        "eval(",
    ):
        assert forbidden not in script
    assert "<form" not in page and "<iframe" not in page
    assert not re.search(r"<script[^>]+src=", page)


def test_no_network_subprocess_model_or_native_calls(suite, proposal, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network or process dispatch allowed")

    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert "Target review" in workbench.render_page(payload(suite, proposal))


def test_page_byte_budget(suite, proposal, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_HTML_BYTES", 10)
    with pytest.raises(ValueError, match="budget"):
        workbench.render_page(payload(suite, proposal))


@pytest.mark.parametrize("bad", [None, "x", "F" * 64])
def test_proposal_raw_pin_required(suite, proposal, bad):
    with pytest.raises(ValueError):
        workbench.build_payload(suite, proposal, bad)


def test_build_pins_inputs_and_never_overwrites(tmp_path, suite, proposal):
    path = tmp_path / "proposal.json"
    raw = canonical(proposal).encode()
    path.write_bytes(raw)
    pin = hashlib.sha256(raw).hexdigest()
    output = tmp_path / "review.html"
    result = workbench.build_page(SUITE, SUITE_SHA, path, pin, output)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == result["html_sha256"]
    assert result["operator_decisions"] == 0
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        workbench.build_page(SUITE, SUITE_SHA, path, pin, output)
    assert output.read_bytes() == before
    with pytest.raises(ValueError):
        workbench.build_page(SUITE, SUITE_SHA, path, "0" * 64, tmp_path / "bad.html")
    assert not (tmp_path / "bad.html").exists()
    with pytest.raises(ValueError):
        workbench.build_page(SUITE, SUITE_SHA, path, pin, tmp_path / "bad.json")


def test_assets_are_package_resources():
    root = files("ai_trader.training").joinpath("assets")
    assert all(root.joinpath("review_workbench." + ext).is_file() for ext in ("html", "css", "js"))


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_synthetic_js_export_passes_python_audit(suite, proposal, decision):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Optional Node runtime needed for cross-language workbench test")
    subprocess.run(
        [node, "--test", str(ROOT / "tests_js/review_workbench.test.cjs")],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    script = r"""
const api = require(process.argv[1]);
let text = ''; process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => text += chunk);
process.stdin.on('end', () => {
  const payload = JSON.parse(text);
  const review = JSON.parse(JSON.stringify(payload.review));
  for (const row of review.cases) {
    row.decision = process.argv[2];
    row.note = 'Synthetic test only, not an actual operator review.';
    for (const key of api.checks) row.checks[key] = true;
  }
  process.stdout.write(JSON.stringify(api.makeExport(payload, review, {
    confirmed: true, reviewerId: 'synthetic-workbench-test', timestamp: '2026-09-24T12:00:00Z'
  })));
});
"""
    result = subprocess.run(
        [
            node,
            "-e",
            script,
            str(ROOT / "src/ai_trader/training/assets/review_workbench.js"),
            decision,
        ],
        input=canonical(payload(suite, proposal)),
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    review = json.loads(result.stdout)
    assert audit_review(suite, review)["operator_attestation_present"] is True
    assert audit_review(suite, review)["candidate_export_allowed"] is (decision == "approve")
    assert audit_review(suite, review)["training_allowed"] is False
