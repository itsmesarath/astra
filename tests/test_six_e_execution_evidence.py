"""Synthetic execution evidence coverage; no historical or external execution."""

import builtins
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import test_six_e_exit_diagnostics as fixtures

from ai_trader.research import six_e_execution_evidence as evidence

diagnostics, replay = evidence.diagnostics, evidence.replay
registered = fixtures.registered
DAY, SECOND, MS, TICK = fixtures.DAY, fixtures.SECOND, fixtures.MS, fixtures.TICK
PIN = fixtures.PIN
KINDS = {
    "local_transport_and_publication",
    "source_sequence_continuity",
    "size_at_execution_cursor",
    "measured_order_latency",
    "broker_receipts_and_reconciliation",
    "futures_to_cfd_execution_mapping",
}


def declared_for(plan):
    return {
        **diagnostics.describe_exits(plan),
        "status": "verified_all_exit_quote_diagnostics_not_reconciliation",
        "origin": {
            "registration_path": "logs/synthetic_declared_trial.json",
            "registration_sha256": PIN,
            "completion_sha256": PIN,
            "request_sha256": PIN,
            "input_manifest_sha256": plan.config.source_manifest_sha256,
        },
    }


@pytest.fixture
def declared():
    return declared_for(
        fixtures.plan_for((fixtures.closed_source(), fixtures.unknown_source(fixtures.NEXT_DAY)))
    )


def test_pure_assessor_is_declared_coverage_and_cannot_authenticate_supplied_status(declared):
    result = evidence.assess(declared)
    assert result["version"] == evidence.VERSION
    assert result["scope"] == evidence.SCOPE
    assert result["status"] == "declared_diagnostic_coverage_not_authenticated"
    assert result["derived_evidence"]["state"] == "DERIVED_FROM_DECLARED_DIAGNOSTIC"
    assert "source_pins" not in result
    assert "local_reconstruction" not in result
    assert result["complete_inputs"] == declared["complete_inputs"]
    assert result["exits"] == declared["exits"]
    assert result["terminal_state"] == declared["terminal_state"]
    assert result["terminal_ledger_head_sha256"] == declared["terminal_state"]["tip_sha256"]
    assert result["complete_simulated_net_contract_ticks"] is None
    assert result["inventory_status"] == "open_liability_preserved"
    assert result["flags"] == replay._flags()
    assert not any(result["flags"].values())


def test_complete_twenty_exit_coverage_retains_losing_positions_and_open_liability():
    quotes, decisions = [], []
    for index in range(20):
        base = index * 20 * SECOND
        decisions.append((base, len(quotes), 1))
        quotes.extend([(base, 100, 101), (base + 100 * MS, 100, 101)])
        if index == 19:
            quotes.extend([(base + 14 * SECOND, 100, 101), (base + 18 * SECOND, 110, 111)])
        elif index % 2:
            quotes.extend([(base + 200 * MS, 99, 100), (base + 300 * MS, 98, 99)])
        else:
            quotes.extend([(base + 200 * MS, 105, 106), (base + 300 * MS, 104, 105)])
    declared = declared_for(fixtures.plan_for(fixtures.source(quotes, tuple(decisions))))
    result = evidence.assess(declared)
    assert result["complete_inputs"]["exit_intents"] == 20
    assert result["exits"] == declared["exits"]
    assert len({r["request_id"] for r in result["exits"]}) == 20
    assert result["derived_evidence"]["simulator_exit_receipts"] == 19
    assert {r["exit_fill"]["price_nano"] for r in result["exits"][:-1]} == {
        98 * TICK,
        104 * TICK,
    }
    assert result["exits"][-1]["resolution"] == "unknown_empty_window"
    assert result["terminal_state"]["reservation"]["status"] == "UNKNOWN"
    assert result["complete_simulated_net_contract_ticks"] is None


def test_quiet_quote_gap_establishes_no_transport_health_or_outage(declared):
    result = evidence.assess(declared)
    requirements = {r["kind"]: r for r in result["missing_requirements"]}
    assert set(requirements) == KINDS
    assert all(r["state"] == "MISSING" for r in requirements.values())
    assert all(r["required"] and r["reason"] for r in requirements.values())
    transport = requirements["local_transport_and_publication"]
    assert "neither local transport health nor an outage" in transport["reason"]
    assert transport["applicability"] == "prospective_external_execution_claim"
    assert "native" in requirements["source_sequence_continuity"]["reason"]
    assert result["exits"][-1]["candidate_count"] == 0
    assert result["exits"][-1]["observed_gap_ns"] == 4 * SECOND
    assert result["exits"][-1]["exit_fill"] is None


def test_latency_full_contract_crossing_and_cost_are_assumptions_not_execution_evidence(declared):
    result = evidence.assess(declared)
    assumptions = result["assumptions"]
    assert assumptions["state"] == "ASSUMED_NOT_MEASURED_EXECUTION"
    assert assumptions["entry_delay_ns"] == assumptions["exit_delay_ns"] == 100 * MS
    assert assumptions["candidate_wait_ns"] == SECOND
    assert assumptions["quantity_contracts"] == 1
    assert assumptions["extra_round_trip_ticks_per_contract"] == 1
    assert result["derived_evidence"]["vendor_quote_columns"] == [
        "vendor_receive_timestamp_ns",
        "bid_nano",
        "ask_nano",
    ]
    requirements = {r["kind"]: r for r in result["missing_requirements"]}
    assert "size" in requirements["size_at_execution_cursor"]["reason"]
    assert "CPU prediction" in requirements["measured_order_latency"]["reason"]
    assert "CFD" in requirements["futures_to_cfd_execution_mapping"]["reason"]


def test_no_trade_has_no_expected_broker_orders_and_only_prospective_requirements():
    declared = declared_for(fixtures.plan_for(fixtures.closed_source(), policy_id="no_trade"))
    result = evidence.assess(declared)
    assert result["exits"] == []
    assert result["derived_evidence"]["simulator_exit_receipts"] == 0
    assert result["derived_evidence"]["broker_orders_expected_in_this_offline_trial"] == 0
    assert result["complete_simulated_net_contract_ticks"] == 0
    assert result["inventory_status"] == "flat_simulated_inventory_only"
    assert all(
        r["applicability"].startswith("prospective_") for r in result["missing_requirements"]
    )
    assert not any(result["flags"].values())


def test_pure_assessor_performs_no_source_file_or_verifier_io(declared, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Pure assessment must not read files or reconstruct source inputs")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(evidence, "fingerprints", forbidden)
    monkeypatch.setattr(diagnostics, "verify_report", forbidden)
    monkeypatch.setattr(replay, "_check_plan", forbidden)
    assert evidence.assess(declared)["complete_inputs"]["exit_intents"] == 2


def test_report_mutation_cannot_change_inputs_flags_inventory_or_later_assessments(declared):
    before = deepcopy(declared)
    first = evidence.assess(declared)
    first["flags"]["trading_enabled"] = True
    first["exits"][-1]["resolution"] = "filled_first_candidate"
    first["terminal_state"]["reservation"]["status"] = "CANCELLED"
    first["missing_requirements"][0]["state"] = "HEALTHY"
    second = evidence.assess(declared)
    assert declared == before
    assert second["flags"] == replay._flags()
    assert second["exits"] == before["exits"]
    assert second["terminal_state"] == before["terminal_state"]
    assert all(r["state"] == "MISSING" for r in second["missing_requirements"])


@pytest.mark.parametrize("claim", ["healthy", "verified", "quantity", "latency", "order"])
def test_unexpected_caller_claims_are_refused_even_when_they_look_reassuring(declared, claim):
    declared[claim] = True
    with pytest.raises(ValueError):
        evidence.assess(declared)


@pytest.mark.parametrize(
    "change",
    [
        "numeric_flag",
        "numeric_count",
        "candidate_bool",
        "native_cursor_bool",
        "spread_bool",
        "price_bool",
        "current_session_bool",
        "pin_bool",
        "extra_size",
        "changed_contract",
        "future_intent_reference",
        "missing_bracket_reference",
        "same_cursor_different_price",
        "nonadjacent_first_candidate",
        "net_cost_contradiction",
        "closed_count_contradiction",
        "execution_watermark",
        "future_position_execution",
        "wrong_terminal_day",
        "incomplete_terminal_window",
        "changed_open_position_id",
        "changed_open_side",
        "changed_reservation_time",
        "changed_reservation_status",
        "future_ledger_reference",
        "duplicate_exit",
        "drop_exit",
        "complete_open_return",
    ],
)
def test_declared_contradictions_and_false_equals_zero_are_rejected(declared, change):
    closed, unknown = declared["exits"]
    state = declared["terminal_state"]
    if change == "numeric_flag":
        declared["flags"]["trading_enabled"] = 0
    elif change == "numeric_count":
        declared["complete_inputs"]["quotes"] = False
    elif change == "candidate_bool":
        assert unknown["candidate_count"] == 0
        unknown["candidate_count"] = False
    elif change == "native_cursor_bool":
        closed["intent_reference"]["native_cursor"] = True
    elif change == "spread_bool":
        closed["first_candidate"]["spread_ticks"] = True
    elif change == "price_bool":
        closed["first_candidate"]["bid_nano"] = True
    elif change == "current_session_bool":
        state["current_session"] = False
    elif change == "pin_bool":
        declared["origin"]["completion_sha256"] = True
    elif change == "extra_size":
        closed["first_candidate"]["quantity_contracts"] = 1
    elif change == "changed_contract":
        unknown["contract"] = "EURUSD_CFD"
    elif change == "future_intent_reference":
        closed["intent_reference"]["quote_at_ns"] += SECOND
    elif change == "missing_bracket_reference":
        closed["intent_reference"] = None
    elif change == "same_cursor_different_price":
        closed["before_ready_reference"]["bid_nano"] += TICK
        closed["before_ready_reference"]["ask_nano"] += TICK
    elif change == "nonadjacent_first_candidate":
        closed["first_candidate"]["native_cursor"] += 1
        closed["exit_fill"]["native_cursor"] += 1
    elif change == "net_cost_contradiction":
        state["closed_net_contract_ticks"] += 1
    elif change == "closed_count_contradiction":
        state["closed_contracts"] += 1
        state["closed_positions"] += 1
        state["closed_net_contract_ticks"] -= 1
    elif change == "execution_watermark":
        state["execution_watermark_ns"] += 1
    elif change == "future_position_execution":
        state["position"]["executed_at_ns"] = state["execution_watermark_ns"] + 1
    elif change == "wrong_terminal_day":
        state["last_observed_at_ns"] += evidence.ledger.DAY_NS
    elif change == "incomplete_terminal_window":
        state["last_observed_at_ns"] -= 1
    elif change == "changed_open_position_id":
        state["position"]["position_id"] = "different-position"
    elif change == "changed_open_side":
        state["position"]["side"] = "short"
    elif change == "changed_reservation_time":
        state["reservation"]["requested_at_ns"] += 1
    elif change == "changed_reservation_status":
        state["reservation"]["status"] = "PENDING"
    elif change == "future_ledger_reference":
        state["last_reference"]["observed_at_ns"] += 1
    elif change == "duplicate_exit":
        declared["exits"].append(deepcopy(closed))
        declared["complete_inputs"]["exit_intents"] += 1
    elif change == "drop_exit":
        declared["exits"].pop()
        declared["complete_inputs"]["exit_intents"] -= 1
    else:
        declared["complete_simulated_net_contract_ticks"] = 0
    with pytest.raises(ValueError):
        evidence.assess(declared)


def test_flat_complete_zero_return_cannot_be_replaced_by_false():
    declared = declared_for(fixtures.plan_for(fixtures.closed_source(), policy_id="no_trade"))
    assert declared["complete_simulated_net_contract_ticks"] == 0
    declared["complete_simulated_net_contract_ticks"] = False
    with pytest.raises(ValueError):
        evidence.assess(declared)


def test_all_equal_time_candidates_are_kept_and_first_cursor_is_preserved():
    source = fixtures.source(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (300 * MS, 103, 104),
            (2 * SECOND, 102, 103),
        ]
    )
    declared = declared_for(fixtures.plan_for(source))
    result = evidence.assess(declared)
    assert result["exits"][0]["candidate_count"] == 2
    assert result["exits"][0]["first_candidate"]["native_cursor"] == 3
    assert result["exits"][0]["after_deadline_reference"]["native_cursor"] == 5
    declared["exits"][0]["candidate_count"] = 1
    with pytest.raises(ValueError):
        evidence.assess(declared)


@pytest.fixture
def complete(registered):
    report = diagnostics.inspect(
        registered.root,
        registered.registration,
        registered.registration_pin,
        registered.completion_pin,
    )
    path = registered.root / "logs/synthetic_original_diagnostic.json"
    diagnostics.write_report(registered.root, path, report)
    return SimpleNamespace(
        trial=registered, diagnostic=path, diagnostic_pin=fixtures.file_pin(path)
    )


def inspect_args(complete):
    trial = complete.trial
    return (
        trial.root,
        trial.registration,
        trial.registration_pin,
        trial.completion_pin,
        complete.diagnostic,
        complete.diagnostic_pin,
    )


def test_inspect_reconstructs_complete_original_diagnostic_and_is_read_only(complete):
    before = fixtures.snapshot_files(complete.trial.root)
    report = evidence.inspect(*inspect_args(complete))
    assert report["status"] == "verified_local_evidence_coverage_external_execution_blocked"
    assert report["complete_inputs"]["exit_intents"] == 2
    assert report["local_reconstruction"]["report_sha256"] == complete.diagnostic_pin
    assert report["diagnostic_artifact"]["sha256"] == complete.diagnostic_pin
    assert report["source_pins"] == evidence.fingerprints()
    assert report["terminal_ledger_head_sha256"] == report["terminal_state"]["tip_sha256"]
    assert report["terminal_state"]["reservation"]["status"] == "UNKNOWN"
    assert report["complete_simulated_net_contract_ticks"] is None
    assert fixtures.snapshot_files(complete.trial.root) == before


def test_inspect_rejects_repinned_truncated_original_diagnostic(complete):
    report = json.loads(complete.diagnostic.read_bytes())
    report["exits"] = report["exits"][:-1]
    complete.diagnostic.write_bytes(replay._json(report))
    args = (*inspect_args(complete)[:-1], fixtures.file_pin(complete.diagnostic))
    with pytest.raises(ValueError):
        evidence.inspect(*args)


def test_inspect_detects_its_own_source_drift_after_original_reconstruction(complete, monkeypatch):
    original = evidence.fingerprints
    calls = 0

    def drifting():
        nonlocal calls
        calls += 1
        result = original()
        if calls > 1:
            result["six_e_execution_evidence.py"] = "b" * 64
        return result

    monkeypatch.setattr(evidence, "fingerprints", drifting)
    with pytest.raises(ValueError):
        evidence.inspect(*inspect_args(complete))


@pytest.mark.parametrize("index", [2, 3, 5])
def test_inspect_rejects_boolean_pins_before_any_original_evidence_read(
    tmp_path, monkeypatch, index
):
    def forbidden(*args, **kwargs):
        raise AssertionError("Bad pins must be rejected before source or historical reads")

    args = [tmp_path, Path("logs/trial.json"), PIN, PIN, Path("logs/diagnostic.json"), PIN]
    args[index] = True
    monkeypatch.setattr(evidence, "fingerprints", forbidden)
    monkeypatch.setattr(diagnostics, "verify_report", forbidden)
    with pytest.raises(ValueError):
        evidence.inspect(*args)


def save_coverage(complete):
    report = evidence.inspect(*inspect_args(complete))
    path = complete.trial.root / "logs/synthetic_execution_evidence.json"
    evidence.write_report(complete.trial.root, path, report)
    return path, fixtures.file_pin(path), report


def test_independent_coverage_verification_is_canonical_complete_and_read_only(complete):
    path, pin, report = save_coverage(complete)
    before = fixtures.snapshot_files(complete.trial.root)
    result = evidence.verify_report(*inspect_args(complete), path, pin)
    assert (
        result["status"]
        == "verified_execution_evidence_coverage_artifact_external_execution_blocked"
    )
    assert result["complete_inputs"] == report["complete_inputs"]
    assert result["terminal_ledger_head_sha256"] == report["terminal_ledger_head_sha256"]
    assert result["report_sha256"] == pin
    assert result["flags"] == replay._flags()
    assert fixtures.snapshot_files(complete.trial.root) == before


@pytest.mark.parametrize(
    "change", ["numeric_zero", "drop_exit", "healthy_claim", "closed_total", "noncanonical"]
)
def test_repinned_coverage_forgeries_fail_complete_reconstruction(complete, change):
    path, _, report = save_coverage(complete)
    if change == "numeric_zero":
        report["exits"][-1]["candidate_count"] = False
    elif change == "drop_exit":
        report["exits"].pop()
    elif change == "healthy_claim":
        report["missing_requirements"][0]["state"] = "HEALTHY"
    elif change == "closed_total":
        report["complete_simulated_net_contract_ticks"] = report["terminal_state"][
            "closed_net_contract_ticks"
        ]
    raw = (
        json.dumps(report, indent=2).encode() if change == "noncanonical" else replay._json(report)
    )
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        evidence.verify_report(*inspect_args(complete), path, fixtures.file_pin(path))


def cli_args(complete, command="inspect", destination=None):
    trial = complete.trial
    result = [
        "six_e_execution_evidence",
        command,
        "--registration",
        str(trial.registration),
        "--registration-sha256",
        trial.registration_pin,
        "--completion-sha256",
        trial.completion_pin,
        "--diagnostic",
        str(complete.diagnostic),
        "--diagnostic-sha256",
        complete.diagnostic_pin,
    ]
    if destination is not None:
        result.extend(["--output", str(destination)])
    return result


def test_cli_inspect_prints_full_read_only_coverage(complete, monkeypatch, capsys):
    before = fixtures.snapshot_files(complete.trial.root)
    monkeypatch.chdir(complete.trial.root)
    monkeypatch.setattr(sys, "argv", cli_args(complete))
    evidence.main()
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "verified_local_evidence_coverage_external_execution_blocked"
    assert {r["kind"] for r in report["missing_requirements"]} == KINDS
    assert fixtures.snapshot_files(complete.trial.root) == before


def test_cli_fresh_log_contains_full_report_with_compact_printed_pin(complete, monkeypatch, capsys):
    before = fixtures.snapshot_files(complete.trial.root)
    output = complete.trial.root / "logs/synthetic_cli_execution_evidence.json"
    monkeypatch.chdir(complete.trial.root)
    monkeypatch.setattr(sys, "argv", cli_args(complete, destination=output))
    evidence.main()
    summary = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_bytes())
    assert summary["report_sha256"] == fixtures.file_pin(output)
    assert summary["complete_inputs"] == stored["complete_inputs"]
    assert set(summary["missing_requirements"]) == KINDS
    assert stored["flags"] == summary["flags"] == replay._flags()
    after = fixtures.snapshot_files(complete.trial.root)
    assert set(after) - set(before) == {output}
    assert {path: contents for path, contents in after.items() if path != output} == before


@pytest.mark.parametrize("destination", ["logs/existing.json", "data/processed/unsafe.json"])
def test_cli_output_guard_precedes_every_historical_read(tmp_path, monkeypatch, destination):
    (tmp_path / "logs").mkdir()
    output = tmp_path / destination
    if destination.startswith("logs"):
        output.write_bytes(b"existing-coverage")

    def forbidden(*args, **kwargs):
        raise AssertionError("Unsafe destination must fail before source or price reads")

    placeholder = SimpleNamespace(
        trial=SimpleNamespace(
            registration=tmp_path / "logs/trial.json", registration_pin=PIN, completion_pin=PIN
        ),
        diagnostic=tmp_path / "logs/diagnostic.json",
        diagnostic_pin=PIN,
    )
    monkeypatch.setattr(evidence, "inspect", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", cli_args(placeholder, destination=output))
    with pytest.raises(ValueError):
        evidence.main()
    if output.exists():
        assert output.read_bytes() == b"existing-coverage"


def test_cli_help_reads_no_evidence_or_models(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Help must not read source or historical evidence")

    monkeypatch.setattr(evidence, "inspect", forbidden)
    monkeypatch.setattr(evidence, "fingerprints", forbidden)
    monkeypatch.setattr(sys, "argv", ["six_e_execution_evidence", "inspect", "--help"])
    with pytest.raises(SystemExit) as exc:
        evidence.main()
    assert exc.value.code == 0


def test_source_pins_add_only_new_assessor_to_existing_frozen_diagnostic_sources():
    pins = evidence.fingerprints()
    original = diagnostics.fingerprints()
    assert pins.items() >= original.items()
    assert set(pins) - set(original) == {"six_e_execution_evidence.py"}
    assert len(pins) == len(original) + 1
    assert pins["six_e_execution_evidence.py"] == fixtures.file_pin(Path(evidence.__file__))
