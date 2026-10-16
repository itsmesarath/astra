"""Synthetic capture/artifact audit; never enumerate real or reserved datasets."""

import hashlib
import json
from dataclasses import asdict

import pytest
from test_build_microstructure import build, capture_records, source

from ai_trader.research import capture_quality as quality
from ai_trader.trading.trade_case import CaseEvidence, PreTradeCase


def artifacts(tmp_path):
    capture = source(tmp_path)
    artifact = tmp_path / "features.jsonl"
    build(capture, artifact)
    return capture, artifact


def rewrite(path, records):
    path.write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")


def test_read_only_reproducible_report_and_coverage(tmp_path, monkeypatch):
    capture, artifact = artifacts(tmp_path)
    before = (capture.read_bytes(), artifact.read_bytes())

    def forbidden(*args, **kwargs):
        raise AssertionError("No network")

    monkeypatch.setattr("socket.socket", forbidden)
    result = quality.assess_capture(capture, artifact)
    assert result == quality.assess_capture(capture, artifact)
    assert result.observations == 2
    assert result.rolling_warmup_observations == 2
    assert result.invalid_evidence_intervals == 1
    assert result.usable_observations == 0
    assert result.producer_code_matches_current is True
    assert result.incomplete_top_n_observations == 0
    assert result.max_observation_gap_ns == 100_000_000
    assert result.source_sha256 == hashlib.sha256(before[0]).hexdigest()
    assert result.artifact_sha256 == hashlib.sha256(before[1]).hexdigest()
    assert (capture.read_bytes(), artifact.read_bytes()) == before


@pytest.mark.parametrize(
    "change",
    [
        "missing_footer",
        "wrong_count",
        "trailing",
        "wrong_source",
        "schema",
        "bool_schema",
        "session",
        "coverage",
        "cvd",
        "receipt",
        "numeric_type",
        "config",
        "empty",
    ],
)
def test_bad_or_partial_artifact_is_rejected(tmp_path, change):
    capture, artifact = artifacts(tmp_path)
    rows = [json.loads(line) for line in artifact.read_text().splitlines()]
    if change == "missing_footer":
        rows.pop()
    elif change == "wrong_count":
        rows[-1]["observation_count"] = 3
    elif change == "trailing":
        rows.append(rows[-1])
    elif change == "wrong_source":
        rows[0]["source_sha256"] = "0" * 64
    elif change == "schema":
        rows[0]["feature_schema"] = "future_schema"
    elif change == "bool_schema":
        rows[0]["schema_version"] = True
    elif change == "session":
        rows[1]["source_session"] = "different"
    elif change == "coverage":
        rows[1]["bid_top_n_covered"] = False
    elif change == "cvd":
        rows[2]["session_cvd_base"] = "99"
    elif change == "receipt":
        rows[1]["received_at_ns"] = 5
    elif change == "numeric_type":
        rows[1]["rolling_trade_count"] = False
    elif change == "config":
        del rows[0]["config"]["levels"]
    elif change == "empty":
        rows = []
    rewrite(artifact, rows)
    with pytest.raises(ValueError):
        quality.assess_capture(capture, artifact)


@pytest.mark.parametrize("text", ['{"record_type":"a","record_type":"b"}', '{"x":NaN}'])
def test_ambiguous_json_rejected(tmp_path, text):
    capture, artifact = artifacts(tmp_path)
    artifact.write_text(text + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        quality.assess_capture(capture, artifact)


def test_capture_changes_during_audit_are_detected(tmp_path, monkeypatch):
    capture, artifact = artifacts(tmp_path)
    original = quality.validate_capture

    def changed(path):
        report = original(path)
        path.write_text(path.read_text() + "\n", encoding="utf-8")
        return report

    monkeypatch.setattr(quality, "validate_capture", changed)
    with pytest.raises(ValueError, match="changed"):
        quality.assess_capture(capture, artifact)


def test_incomplete_capture_cannot_get_a_quality_report(tmp_path):
    capture, artifact = artifacts(tmp_path)
    rewrite(capture, [json.loads(line) for line in capture.read_text().splitlines()][:-1])
    with pytest.raises(ValueError):
        quality.assess_capture(capture, artifact)


def test_old_producer_manifest_is_disclosed_not_mistaken_for_current(tmp_path):
    capture, artifact = artifacts(tmp_path)
    rows = [json.loads(line) for line in artifact.read_text().splitlines()]
    rows[0]["implementation_sha256"] = {"old.py": "0" * 64}
    rewrite(artifact, rows)
    assert quality.assess_capture(capture, artifact).producer_code_matches_current is False
    del rows[0]["implementation_sha256"]
    rewrite(artifact, rows)
    with pytest.raises(ValueError, match="manifest"):
        quality.assess_capture(capture, artifact)


def test_invalid_decimal_config_cli_is_rejected(tmp_path, monkeypatch, capsys):
    capture, artifact = artifacts(tmp_path)
    rows = [json.loads(line) for line in artifact.read_text().splitlines()]
    rows[0]["config"]["liquidity_band_bps"] = "not-a-number"
    rewrite(artifact, rows)
    monkeypatch.setattr("sys.argv", ["quality", str(capture), str(artifact)])
    with pytest.raises(SystemExit) as error:
        quality.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "REJECTED"


def test_trades_after_final_depth_are_reported_separately(tmp_path):
    rows = capture_records()
    trade = json.loads(json.dumps(rows[3]))
    trade["received_at_ns"] = 1_200_000_000
    trade["event"].update({"E": 1200, "T": 1200, "a": 2, "f": 2, "l": 2})
    rows.insert(-1, trade)
    rows[-1]["trade_events"] = 2
    capture = source(tmp_path, rows)
    artifact = tmp_path / "features.jsonl"
    build(capture, artifact)
    report = quality.assess_capture(capture, artifact)
    assert report.trades_after_last_observation == 1
    assert report.pending_trades_at_last_observation == 0


def test_usable_requires_warmup_valid_interval_and_both_side_coverage(tmp_path):
    rows = capture_records()
    for offset in range(1, 11):
        depth = json.loads(json.dumps(rows[4]))
        depth["received_at_ns"] = (1100 + offset * 1000) * 1_000_000
        depth["event"].update({"E": 1100 + offset * 1000, "U": 102 + offset, "u": 102 + offset})
        rows.insert(-1, depth)
    rows[-1]["depth_events"] = 12
    capture = source(tmp_path, rows)
    artifact = tmp_path / "features.jsonl"
    build(capture, artifact)
    report = quality.assess_capture(capture, artifact)
    assert report.observations == 12
    assert report.rolling_warmup_observations == 11
    assert report.usable_observations == 1


def test_synthetic_observation_to_no_order_case(tmp_path):
    capture, artifact = artifacts(tmp_path)
    report = quality.assess_capture(capture, artifact)
    row = json.loads(artifact.read_text().splitlines()[1])
    # Use this observation's causal flags, NOT full-session retrospective report metrics.
    assert row["rolling_window_complete"] is False
    digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
    case = PreTradeCase(
        case_id="synthetic-warmup-1",
        source_session=report.source_session,
        decision_at_ns=row["received_at_ns"],
        policy_version="warmup-rejection-v1",
        feature_version="receipt_causal_microstructure_v1",
        market_state_sha256=digest,
        hypothesis="Entry requires complete rolling context",
        expected_behavior="Abstain",
        invalidation="Rolling context incomplete",
        evidence=(CaseEvidence("observation-1", row["received_at_ns"], digest),),
        action="NO_ACTION",
        plan=None,
        risk_verdict="REJECTED",
        risk_reason="data_warmup_incomplete",
        risk_config_sha256="1" * 64,
    )
    assert case.plan is None
    assert json.loads(case.to_json())["action"] == "NO_ACTION"
    assert len(case.sha256) == 64


def test_cli_valid_and_rejected(tmp_path, monkeypatch, capsys):
    capture, artifact = artifacts(tmp_path)
    monkeypatch.setattr("sys.argv", ["quality", str(capture), str(artifact)])
    quality.main()
    assert json.loads(capsys.readouterr().out) == asdict(quality.assess_capture(capture, artifact))
    artifact.write_text("", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        quality.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "REJECTED"
