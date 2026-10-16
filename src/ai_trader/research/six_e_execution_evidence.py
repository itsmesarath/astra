"""Offline execution-evidence coverage, never fills, reconciliation or authority.

The pure assessor checks declared diagnostic consistency. The operator commands
first reconstruct the complete pinned original diagnostic. Neither operation
authenticates external receipts or interprets quiet quote updates as transport
health, an outage, executable size or a cancellation.
"""

from __future__ import annotations

import argparse
import time
from copy import deepcopy
from dataclasses import fields
from pathlib import Path

from ai_trader.research import six_e_exit_diagnostics as diagnostics

replay, ledger, reader, status = (
    diagnostics.replay,
    diagnostics.ledger,
    diagnostics.reader,
    diagnostics.status,
)
VERSION = "six_e_execution_evidence_coverage_v1"
SCOPE = "posthoc_exposed_development_evidence_coverage_not_execution_authority"
REFERENCE_FIELDS = {
    "source_session",
    "contract",
    "native_cursor",
    "quote_at_ns",
    "bid_nano",
    "ask_nano",
    "spread_ticks",
}
EXIT_FIELDS = {
    "request_id",
    "position_id",
    "source_session",
    "contract",
    "side",
    "requested_at_ns",
    "ready_at_ns",
    "deadline_at_ns",
    "trigger",
    "intent_reference",
    "before_ready_reference",
    "candidate_count",
    "first_candidate",
    "after_deadline_reference",
    "observed_gap_ns",
    "late_after_deadline_ns",
    "resolution",
    "exit_fill",
    "unresolved_at_ns",
}


def fingerprints() -> dict:
    return {
        **diagnostics.fingerprints(),
        Path(__file__).name: reader.study.common.hash_file(Path(__file__), 1024**2),
    }


def _shape(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(f"Exact {label} fields required; no additional evidence claims")


def _integer(value, low=0, high=ledger.MAX_INT):
    ledger._integer(value, low, high)


def _pin(value):
    if type(value) is not str:
        raise ValueError("Exact string evidence pin required")
    ledger._pin(value)


def _identifier(value):
    if type(value) is not str:
        raise ValueError("Exact string evidence identity required")
    ledger._identifier(value)


def _session(day, contract):
    if type(day) is not str or reader.study.data.role_for_day(day) != "train":
        raise ValueError("Original train-development session required")
    start, end = replay.target.window(day)
    if type(contract) is not str or contract != reader.study.census.dated_contract(day):
        raise ValueError("Original dated futures contract required; no CFD substitution")
    return start, end


def _reference(value, day, contract, *, fill=False):
    if value is None:
        return
    _shape(value, REFERENCE_FIELDS | ({"price_nano"} if fill else set()), "native reference")
    start, end = _session(day, contract)
    if (value["source_session"], value["contract"]) != (day, contract):
        raise ValueError("Native reference cannot substitute another session or contract")
    _integer(value["native_cursor"], 0, replay.MAX_QUOTES - 1)
    _integer(value["quote_at_ns"], start, end - 1)
    ledger._price(value["bid_nano"])
    ledger._price(value["ask_nano"])
    _integer(value["spread_ticks"], 1)
    if value["spread_ticks"] * replay.target.TICK != value["ask_nano"] - value["bid_nano"]:
        raise ValueError("Native reference spread differs from its supplied prices")
    if fill:
        ledger._price(value["price_nano"])


def _optional_integer(value, expected):
    if expected is None:
        if value is not None:
            raise ValueError("Absent evidence must remain null")
    else:
        _integer(value)
        if value != expected:
            raise ValueError("Declared time or gap differs from its reference evidence")


def _exit(value):
    _shape(value, EXIT_FIELDS, "exit diagnostic")
    for name in ("request_id", "position_id"):
        _identifier(value[name])
    day, contract = value["source_session"], value["contract"]
    start, end = _session(day, contract)
    if value["side"] not in replay.target.SIDES or type(value["side"]) is not str:
        raise ValueError("Original long or short side required")
    _integer(value["requested_at_ns"], start, end - 1)
    _integer(value["ready_at_ns"])
    _integer(value["deadline_at_ns"])
    if (
        value["ready_at_ns"] != value["requested_at_ns"] + replay.target.EXIT_DELAY
        or value["deadline_at_ns"] != value["ready_at_ns"] + replay.target.WAIT
        or value["trigger"] not in ("hold_timer", "bracket_quote")
        or type(value["trigger"]) is not str
    ):
        raise ValueError("Original declared delay, wait and trigger required")
    for name in (
        "intent_reference",
        "before_ready_reference",
        "first_candidate",
        "after_deadline_reference",
        "exit_fill",
    ):
        _reference(value[name], day, contract, fill=name == "exit_fill")
    intent, before = value["intent_reference"], value["before_ready_reference"]
    first, after = value["first_candidate"], value["after_deadline_reference"]
    if intent is None or before is None:
        raise ValueError("Original entered exit requires its prior published quote references")
    seen = {}
    for ref in (intent, before, first, after):
        if ref is not None:
            cursor = ref["native_cursor"]
            if cursor in seen and replay._json(seen[cursor]) != replay._json(ref):
                raise ValueError("One native cursor cannot identify different quote content")
            seen[cursor] = ref
    if intent is not None and (
        intent["quote_at_ns"] > value["requested_at_ns"]
        or value["trigger"] == "hold_timer"
        and intent["quote_at_ns"] == value["requested_at_ns"]
        or value["trigger"] == "bracket_quote"
        and intent["quote_at_ns"] != value["requested_at_ns"]
    ):
        raise ValueError("Intent reference must respect the declared publication boundary")
    if before is not None and before["quote_at_ns"] >= value["ready_at_ns"]:
        raise ValueError("Before-ready reference must be strictly prior")
    if (
        first is not None
        and not value["ready_at_ns"] <= first["quote_at_ns"] <= value["deadline_at_ns"]
    ):
        raise ValueError("First candidate must be inside the inclusive declared wait")
    if after is not None and after["quote_at_ns"] <= value["deadline_at_ns"]:
        raise ValueError("After-deadline reference must be excluded from the original wait")
    _integer(value["candidate_count"], 0, replay.MAX_QUOTES)
    if (value["candidate_count"] > 0) != (first is not None):
        raise ValueError("Candidate count and first native candidate disagree")
    following = first or after
    if before is not None and following is not None:
        if before["native_cursor"] + 1 != following["native_cursor"]:
            raise ValueError("Before-ready reference must precede the immediate next quote")
    if intent is not None and before is not None:
        if (
            intent["native_cursor"] > before["native_cursor"]
            or intent["quote_at_ns"] > before["quote_at_ns"]
        ):
            raise ValueError("Published intent prefix cannot use a later native cursor")
    if first is not None and after is not None:
        if after["native_cursor"] - first["native_cursor"] != value["candidate_count"]:
            raise ValueError("Complete candidate count must span the original native interval")
    _optional_integer(
        value["observed_gap_ns"],
        following["quote_at_ns"] - before["quote_at_ns"]
        if following is not None and before is not None
        else None,
    )
    _optional_integer(
        value["late_after_deadline_ns"],
        after["quote_at_ns"] - value["deadline_at_ns"] if after is not None else None,
    )
    if value["resolution"] == "filled_first_candidate":
        price = (
            first["bid_nano"]
            if first is not None and value["side"] == "long"
            else (first["ask_nano"] if first is not None else None)
        )
        if first is None or value["exit_fill"] != {**first, "price_nano": price}:
            raise ValueError("Simulator fill must identify its first native candidate")
        _optional_integer(value["unresolved_at_ns"], None)
    elif value["resolution"] == "unknown_empty_window":
        if first is not None or value["exit_fill"] is not None:
            raise ValueError("UNKNOWN cannot become a fill from quote references")
        _optional_integer(value["unresolved_at_ns"], value["deadline_at_ns"])
    elif value["resolution"] == "pending_at_window_end":
        if first is not None or value["exit_fill"] is not None or value["deadline_at_ns"] <= end:
            raise ValueError("Pending wait cannot manufacture an execution")
        _optional_integer(value["unresolved_at_ns"], None)
    else:
        raise ValueError("Original exit disposition required")


def _terminal(value, total):
    _shape(value, (f.name for f in fields(ledger.LedgerState)), "terminal ledger state")
    _pin(value["tip_sha256"])
    _integer(value["sequence"], 0, replay.MAX_EVENTS)
    for name in ("last_observed_at_ns", "execution_watermark_ns"):
        _integer(value[name])
    for name in ("closed_contracts", "closed_positions"):
        _integer(value[name], 0, replay.MAX_EVENTS)
    for name in ("closed_gross_contract_ticks", "closed_net_contract_ticks"):
        _integer(value[name], -ledger.MAX_INT, ledger.MAX_INT)
    if (
        value["closed_positions"] != value["closed_contracts"]
        or value["closed_net_contract_ticks"]
        != value["closed_gross_contract_ticks"] - replay.target.COST * value["closed_contracts"]
        or value["execution_watermark_ns"] > value["last_observed_at_ns"]
    ):
        raise ValueError("Original full-contract cost accounting or execution clock differs")
    day = value["current_session"]
    if type(day) is not str:
        raise ValueError("Exact current source-session string required")
    _, session_end = _session(day, reader.study.census.dated_contract(day))
    day_start = ledger._session(day)
    if not day_start <= value["last_observed_at_ns"] < day_start + ledger.DAY_NS:
        raise ValueError("Terminal observation clock must belong to its current UTC day")
    if value["last_observed_at_ns"] != session_end:
        raise ValueError("Complete frozen replay must reach its final declared window end")
    position, reservation = value["position"], value["reservation"]
    if position is not None:
        _shape(position, (f.name for f in fields(ledger.Position)), "remaining position")
        _identifier(position["position_id"])
        entry_start, entry_end = _session(position["entry_source_session"], position["contract"])
        for name in ("initial_contracts", "remaining_contracts"):
            _integer(position[name], 1, 1)
        ledger._price(position["entry_price_nano"])
        _integer(position["executed_at_ns"], entry_start, entry_end - 1)
        if position["executed_at_ns"] > value["execution_watermark_ns"]:
            raise ValueError("Position execution cannot follow its execution watermark")
        if position["side"] not in replay.target.SIDES:
            raise ValueError("Original remaining position side required")
    if reservation is not None:
        _shape(reservation, (f.name for f in fields(ledger.Reservation)), "exit reservation")
        _identifier(reservation["request_id"])
        for name in ("quantity_contracts", "remaining_contracts"):
            _integer(reservation[name], 1, 1)
        _integer(reservation["requested_at_ns"], 0, value["last_observed_at_ns"])
        if position is None or reservation["status"] not in ("PENDING", "UNKNOWN"):
            raise ValueError("Original unresolved reservation and inventory required")
    if value["last_reference"] is not None:
        _shape(
            value["last_reference"],
            (f.name for f in fields(ledger.QuoteReference)),
            "ledger reference",
        )
        ledger.QuoteReference(**value["last_reference"])
        ref = value["last_reference"]
        _integer(ref["native_cursor"], 0, replay.MAX_QUOTES - 1)
        if (
            position is None
            or ref["contract"] != position["contract"]
            or ref["observed_at_ns"] > value["last_observed_at_ns"]
            or ref["quote_at_ns"] < position["executed_at_ns"]
        ):
            raise ValueError("A ledger reference cannot close or replace remaining inventory")
    if position is None:
        if total is None:
            raise ValueError("Flat simulated account requires its complete original total")
        _integer(total, -ledger.MAX_INT, ledger.MAX_INT)
        if total != value["closed_net_contract_ticks"]:
            raise ValueError("Complete simulated total differs from terminal accounting")
    elif total is not None:
        raise ValueError("Remaining inventory must retain null complete simulated return")


def _requirements() -> list[dict]:
    requirements = [
        {
            "kind": "local_transport_and_publication",
            "state": "MISSING",
            "required": [
                "source_channel_and_subscription_epoch",
                "same_clock_local_receive_and_publication_trace",
                "independent_heartbeat_or_packet_observations",
            ],
            "reason": "Vendor receive timestamps and quiet updates establish neither local "
            "transport health nor an outage.",
        },
        {
            "kind": "source_sequence_continuity",
            "state": "MISSING",
            "required": [
                "sequence_protocol_and_channel_scope",
                "snapshot_reset_anchor",
                "complete_ordered_sequence_trace_and_gap_audit",
            ],
            "reason": "Stored native cursor order does not establish source sequence continuity.",
        },
        {
            "kind": "size_at_execution_cursor",
            "state": "MISSING",
            "required": [
                "same_contract_and_native_cursor",
                "exact_displayed_bid_ask_size_in_contracts",
                "execution_capacity_and_quantity_evidence",
            ],
            "reason": "Quote columns contain no size; decision log-depth proxies and displayed "
            "size alone cannot prove executable quantity.",
        },
        {
            "kind": "measured_order_latency",
            "state": "MISSING",
            "required": [
                "clock_domains_and_alignment_bounds",
                "bound_order_send_acknowledgement_fill_timestamps",
                "measurement_scope_and_complete_samples",
            ],
            "reason": "Fixed 100ms delays are assumptions; CPU prediction timing is not feed "
            "or order latency.",
        },
        {
            "kind": "broker_receipts_and_reconciliation",
            "state": "MISSING",
            "required": [
                "independent_receipt_provenance",
                "contract_order_receipt_fill_identities",
                "incremental_and_cumulative_quantity_semantics",
                "execution_observation_times_prices_fees",
                "complete_order_and_inventory_reconciliation_cursor",
            ],
            "reason": "Quote-simulator hashes do not authenticate broker fills, cancellation, "
            "costs or inventory reconciliation.",
        },
        {
            "kind": "futures_to_cfd_execution_mapping",
            "state": "MISSING",
            "required": [
                "explicit_broker_product_and_price_quantity_units",
                "broker_cfd_quote_execution_and_cost_evidence",
                "documented_mapping_without_contract_substitution",
            ],
            "reason": "Required for CFD claims; dated 6E references cannot supply CFD fills "
            "or economics.",
        },
    ]
    return [
        {
            **item,
            "applicability": (
                "prospective_cfd_execution_claim"
                if item["kind"] == "futures_to_cfd_execution_mapping"
                else "prospective_external_execution_claim"
            ),
        }
        for item in requirements
    ]


def assess(diagnostic: dict) -> dict:
    """Pure consistency assessment of DECLARED diagnostics, not authentication."""
    _shape(
        diagnostic,
        {
            "version",
            "scope",
            "source_pins",
            "complete_inputs",
            "interpretation",
            "exits",
            "terminal_state",
            "complete_simulated_net_contract_ticks",
            "flags",
            "status",
            "origin",
        },
        "diagnostic report",
    )
    if (
        diagnostic["version"] != diagnostics.VERSION
        or diagnostic["scope"] != diagnostics.SCOPE
        or diagnostic["status"] != "verified_all_exit_quote_diagnostics_not_reconciliation"
    ):
        raise ValueError("Original diagnostic format and declared verification status required")
    flags = diagnostic["flags"]
    _shape(flags, replay._flags(), "false authority flags")
    if any(type(v) is not bool or v for v in flags.values()):
        raise ValueError("Evidence coverage cannot grant authority or accept numeric flags")
    pins = diagnostic["source_pins"]
    if type(pins) is not dict or not 1 <= len(pins) <= 128:
        raise ValueError("Bounded declared source pins required")
    for name, pin in pins.items():
        _identifier(name)
        _pin(pin)
    origin = diagnostic["origin"]
    _shape(
        origin,
        {
            "registration_path",
            "registration_sha256",
            "completion_sha256",
            "request_sha256",
            "input_manifest_sha256",
        },
        "original trial identity",
    )
    if (
        type(origin["registration_path"]) is not str
        or not 1 <= len(origin["registration_path"]) <= 2048
    ):
        raise ValueError("Bounded declared original registration path required")
    for name in set(origin) - {"registration_path"}:
        _pin(origin[name])
    interpretation = diagnostic["interpretation"]
    _shape(
        interpretation,
        {
            "intent_reference",
            "before_ready_reference",
            "candidate_interval",
            "after_deadline_reference",
            "gap",
            "coverage",
        },
        "diagnostic interpretation",
    )
    if any(type(v) is not str or not 1 <= len(v) <= 4096 for v in interpretation.values()):
        raise ValueError("Bounded interpretation text required")
    coverage = diagnostic["complete_inputs"]
    _shape(coverage, {"sessions", "decisions", "quotes", "exit_intents"}, "complete input counts")
    _integer(coverage["sessions"], 1, replay.MAX_SESSIONS)
    _integer(coverage["decisions"], 0, replay.MAX_DECISIONS)
    _integer(coverage["quotes"], 0, replay.MAX_SESSIONS * replay.MAX_QUOTES)
    _integer(coverage["exit_intents"], 0, replay.MAX_EVENTS)
    exits = diagnostic["exits"]
    if type(exits) is not list or len(exits) != coverage["exit_intents"]:
        raise ValueError("Every declared exit required; no successful subset")
    identifiers = set()
    positions = set()
    for record in exits:
        _exit(record)
        if record["request_id"] in identifiers or record["position_id"] in positions:
            raise ValueError("Duplicate exit identity")
        identifiers.add(record["request_id"])
        positions.add(record["position_id"])
    terminal = diagnostic["terminal_state"]
    _terminal(terminal, diagnostic["complete_simulated_net_contract_ticks"])
    reservation = terminal["reservation"]
    filled = sum(r["resolution"] == "filled_first_candidate" for r in exits)
    if filled != terminal["closed_contracts"]:
        raise ValueError("Every full-contract simulated close requires its original exit")
    execution_times = [r["exit_fill"]["quote_at_ns"] for r in exits if r["exit_fill"] is not None]
    if terminal["position"] is not None:
        execution_times.append(terminal["position"]["executed_at_ns"])
    if terminal["execution_watermark_ns"] != max(execution_times, default=0):
        raise ValueError("Terminal execution watermark differs from complete declared fills")
    open_records = [r for r in exits if r["resolution"] != "filled_first_candidate"]
    if len(open_records) != int(reservation is not None):
        raise ValueError("Original open exit count and terminal reservation disagree")
    if reservation is not None:
        unresolved = [r for r in exits if r["request_id"] == reservation["request_id"]]
        expected = (
            "unknown_empty_window"
            if reservation["status"] == "UNKNOWN"
            else "pending_at_window_end"
        )
        if (
            len(unresolved) != 1
            or unresolved[0]["resolution"] != expected
            or unresolved[0]["position_id"] != terminal["position"]["position_id"]
            or unresolved[0]["contract"] != terminal["position"]["contract"]
            or unresolved[0]["side"] != terminal["position"]["side"]
            or unresolved[0]["source_session"] != terminal["position"]["entry_source_session"]
            or unresolved[0]["requested_at_ns"] < terminal["position"]["executed_at_ns"]
            or unresolved[0]["requested_at_ns"] != reservation["requested_at_ns"]
        ):
            raise ValueError("Remaining liability must retain its exact original exit")
    return {
        "version": VERSION,
        "scope": SCOPE,
        "status": "declared_diagnostic_coverage_not_authenticated",
        "diagnostic_origin": deepcopy(origin),
        "complete_inputs": deepcopy(coverage),
        "derived_evidence": {
            "state": "DERIVED_FROM_DECLARED_DIAGNOSTIC",
            "vendor_quote_columns": ["vendor_receive_timestamp_ns", "bid_nano", "ask_nano"],
            "native_order": "Stored native cursors include equal-time order; no transport "
            "sequence proof",
            "candidate_interval": "First candidate in inclusive original "
            "ready-through-deadline window",
            "simulator_exit_receipts": sum(r["exit_fill"] is not None for r in exits),
            "broker_orders_expected_in_this_offline_trial": 0,
            "simulator_receipt_scope": "Supplied quote-simulator receipt claims; no broker "
            "receipt provenance",
        },
        "assumptions": {
            "state": "ASSUMED_NOT_MEASURED_EXECUTION",
            "entry_delay_ns": replay.target.ENTRY_DELAY,
            "exit_delay_ns": replay.target.EXIT_DELAY,
            "candidate_wait_ns": replay.target.WAIT,
            "quantity_contracts": 1,
            "crossing": "Whole contract at supplied top-of-book bid or ask; no size or queue proof",
            "extra_round_trip_ticks_per_contract": replay.target.COST,
        },
        "missing_requirements": _requirements(),
        "exits": deepcopy(exits),
        "terminal_state": deepcopy(terminal),
        "terminal_ledger_head_sha256": terminal["tip_sha256"],
        "inventory_status": "open_liability_preserved"
        if terminal["position"] is not None
        else "flat_simulated_inventory_only",
        "complete_simulated_net_contract_ticks": diagnostic[
            "complete_simulated_net_contract_ticks"
        ],
        "interpretation": "Missing-evidence coverage establishes no executable size, fills, "
        "cancellation, external reconciliation, CFD economics, strategy scores "
        "or training permission.",
        "flags": replay._flags(),
    }


def inspect(
    root: Path,
    registration_path: Path,
    registration_sha256: str,
    completion_sha256: str,
    diagnostic_path: Path,
    diagnostic_sha256: str,
) -> dict:
    """Reconstruct the complete pinned diagnostic before assessing evidence gaps."""
    for pin in (registration_sha256, completion_sha256, diagnostic_sha256):
        _pin(pin)
    registration_path = status._inside(root, registration_path, "logs")
    diagnostic_path = status._inside(root, diagnostic_path, "logs")
    if diagnostic_path.suffix != ".json":
        raise ValueError("Pinned original diagnostic JSON required")
    started, pins = time.monotonic(), fingerprints()
    proof = diagnostics.verify_report(
        root,
        registration_path,
        registration_sha256,
        completion_sha256,
        diagnostic_path,
        diagnostic_sha256,
    )
    declared = status._decode(replay._read(diagnostic_path, diagnostic_sha256))
    report = assess(declared)
    if (
        replay._json(proof["complete_inputs"]) != replay._json(report["complete_inputs"])
        or proof["terminal_tip_sha256"] != report["terminal_ledger_head_sha256"]
        or fingerprints() != pins
        or time.monotonic() - started > replay.MAX_SECONDS
    ):
        raise ValueError("Complete original evidence or assessor sources changed")
    return {
        **report,
        "status": "verified_local_evidence_coverage_external_execution_blocked",
        "source_pins": pins,
        "diagnostic_artifact": {"path": str(diagnostic_path), "sha256": diagnostic_sha256},
        "local_reconstruction": proof,
    }


def write_report(root: Path, path: Path, report: dict) -> None:
    path = diagnostics._fresh_output(root, path)
    replay._write(path, replay._json(report))


def verify_report(
    root: Path,
    registration_path: Path,
    registration_sha256: str,
    completion_sha256: str,
    diagnostic_path: Path,
    diagnostic_sha256: str,
    report_path: Path,
    report_sha256: str,
) -> dict:
    report_path = status._inside(root, report_path, "logs")
    if report_path.suffix != ".json":
        raise ValueError("Evidence coverage requires its pinned JSON artifact")
    raw = replay._read(report_path, report_sha256)
    expected = inspect(
        root,
        registration_path,
        registration_sha256,
        completion_sha256,
        diagnostic_path,
        diagnostic_sha256,
    )
    if raw != replay._json(expected):
        raise ValueError("Complete evidence coverage differs from canonical reconstruction")
    return {
        "status": "verified_execution_evidence_coverage_artifact_external_execution_blocked",
        "report_sha256": report_sha256,
        "complete_inputs": expected["complete_inputs"],
        "terminal_ledger_head_sha256": expected["terminal_ledger_head_sha256"],
        "flags": replay._flags(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        p.add_argument("--completion-sha256", required=True)
        p.add_argument("--diagnostic", type=Path, required=True)
        p.add_argument("--diagnostic-sha256", required=True)
        if name == "inspect":
            p.add_argument("--output", type=Path)
        else:
            p.add_argument("--report", type=Path, required=True)
            p.add_argument("--report-sha256", required=True)
    args, root = parser.parse_args(), Path.cwd()
    shared = (
        root,
        args.registration,
        args.registration_sha256,
        args.completion_sha256,
        args.diagnostic,
        args.diagnostic_sha256,
    )
    if args.command == "verify":
        result = verify_report(*shared, args.report, args.report_sha256)
    else:
        if args.output is not None:
            diagnostics._fresh_output(root, args.output)
        result = inspect(*shared)
        if args.output is not None:
            write_report(root, args.output, result)
            result = {
                "status": result["status"],
                "complete_inputs": result["complete_inputs"],
                "report_sha256": reader.study.common.hash_file(
                    args.output, replay.MAX_OUTPUT_BYTES
                ),
                "terminal_ledger_head_sha256": result["terminal_ledger_head_sha256"],
                "missing_requirements": [r["kind"] for r in result["missing_requirements"]],
                "flags": replay._flags(),
            }
    print(replay._json(result).decode())


if __name__ == "__main__":
    main()
