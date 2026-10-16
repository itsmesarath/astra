"""Read-only all-exit quote diagnostics; no fill reconciliation or strategy scoring.

The frozen replay remains the control. Later quotes describe an observed update
gap, never prove standing liquidity, cancel an order or reconcile an UNKNOWN exit.
"""

from __future__ import annotations

import argparse
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from ai_trader.research import six_e_continuous_trial as trial

replay, ledger, reader, status = trial.replay, trial.ledger, trial.reader, trial.status
VERSION = "six_e_exit_quote_diagnostics_v1"
SCOPE = "posthoc_exposed_development_not_validation"


def fingerprints() -> dict:
    return {
        **trial.fingerprints(),
        Path(__file__).name: reader.study.common.hash_file(Path(__file__), 1024**2),
    }


def _reference(session, cursor: int | None) -> dict | None:
    if cursor is None or not 0 <= cursor < len(session.quotes):
        return None
    now, bid, ask = map(int, session.quotes[cursor])
    return {
        "source_session": session.source_session,
        "contract": session.contract,
        "native_cursor": cursor,
        "quote_at_ns": now,
        "bid_nano": bid,
        "ask_nano": ask,
        "spread_ticks": (ask - bid) // replay.target.TICK,
    }


def _receipt(plan, event, session, phase: str) -> dict:
    matches = [r for r in plan.receipts if r["evidence_id"] == event.evidence_id]
    if len(matches) != 1:
        raise ValueError("Every fill requires its one complete native receipt")
    saved, receipt = matches[0], matches[0]["receipt"]
    if (
        saved["sha256"] != event.paper_receipt_sha256
        or replay._digest(replay._json(receipt)) != saved["sha256"]
        or receipt["phase"] != phase
        or receipt["source_session"] != session.source_session
        or receipt["contract"] != session.contract
    ):
        raise ValueError("Fill receipt identity or source differs")
    cursor = receipt["native_cursor"]
    ledger._integer(cursor, 0, len(session.quotes) - 1)
    reference = _reference(session, cursor)
    if (
        reference["quote_at_ns"] != event.executed_at_ns
        or receipt["executed_at_ns"] != event.executed_at_ns
        or receipt["price_nano"] != event.price_nano
        or receipt["quantity_contracts"] != event.quantity_contracts
        or event.contract != session.contract
    ):
        raise ValueError("Fill receipt native quote or complete quantity differs")
    return {**reference, "price_nano": event.price_nano}


def _intent_reference(session, entry, entry_reference, intent) -> tuple[str, dict | None]:
    times = session.quotes[:, 0]
    if intent.observed_at_ns == entry.executed_at_ns + replay.target.HOLD:
        # The hold timer fires BEFORE all quotes exactly at its deadline.
        cursor = int(np.searchsorted(times, intent.observed_at_ns, side="left")) - 1
        return "hold_timer", _reference(session, cursor)
    if entry.source_session != session.source_session or entry.contract != session.contract:
        raise ValueError("Bracket trigger requires its original native contract stream")
    last = int(np.searchsorted(times, intent.observed_at_ns, side="right"))
    for cursor in range(entry_reference["native_cursor"], last):
        now, bid, ask = map(int, session.quotes[cursor])
        net = (
            (bid - entry.price_nano) // replay.target.TICK
            if entry.side == "long"
            else (entry.price_nano - ask) // replay.target.TICK
        ) - replay.target.COST
        if net >= replay.target.TARGET or net <= replay.target.STOP:
            if now != intent.observed_at_ns:
                raise ValueError("Exit intent is not the first native bracket threshold")
            return "bracket_quote", _reference(session, cursor)
    raise ValueError("Exit intent lacks its original causal timer or bracket trigger")


def describe_exits(plan: replay.ReplayPlan) -> dict:
    """Reconstruct and describe EVERY exit, retaining incomplete whole-account return."""
    started, pins = time.monotonic(), fingerprints()
    replay._check_plan(plan)
    sessions = {s.source_session: s for s in plan.inputs}
    entries = {e.position_id: e for e in plan.events if type(e) is ledger.EntryFill}
    intents = [e for e in plan.events if type(e) is ledger.ExitIntent]
    exits = []
    for intent in intents:
        if time.monotonic() - started > replay.MAX_SECONDS:
            raise TimeoutError("Complete all-exit diagnostic deadline exceeded")
        entry = entries[intent.position_id]
        session = sessions[intent.source_session]
        if entry.contract != session.contract:
            raise ValueError("An exit cannot substitute a different dated contract")
        entry_ref = _receipt(plan, entry, sessions[entry.source_session], "entry")
        trigger, intent_ref = _intent_reference(session, entry, entry_ref, intent)
        ready = intent.observed_at_ns + replay.target.EXIT_DELAY
        deadline = ready + replay.target.WAIT
        times = session.quotes[:, 0]
        left = int(np.searchsorted(times, ready, side="left"))
        right = int(np.searchsorted(times, deadline, side="right"))
        before = _reference(session, left - 1)
        first = _reference(session, left) if right > left else None
        late = _reference(session, right)
        fills = [
            e
            for e in plan.events
            if type(e) is ledger.ExitFill and e.request_id == intent.request_id
        ]
        unknowns = [
            e
            for e in plan.events
            if type(e) is ledger.UnresolvedExit and e.request_id == intent.request_id
        ]
        if len(fills) > 1 or len(unknowns) > 1 or (fills and unknowns):
            raise ValueError("Frozen simulator requires one complete exit disposition")
        fill_ref = None
        if fills:
            fill_ref = _receipt(plan, fills[0], session, "exit")
            if first is None:
                raise ValueError("Exit fill requires an inclusive native candidate")
            price = first["bid_nano"] if entry.side == "long" else first["ask_nano"]
            if fill_ref != {**first, "price_nano": price}:
                raise ValueError("Exit fill must match the first inclusive native candidate")
            resolution = "filled_first_candidate"
        elif unknowns:
            if right != left or unknowns[0].observed_at_ns != deadline:
                raise ValueError("UNKNOWN exit must have an empty inclusive quote window")
            resolution = "unknown_empty_window"
        else:
            reservation = plan.terminal_state.reservation
            if (
                first is not None
                or reservation is None
                or reservation.request_id != intent.request_id
                or reservation.status != "PENDING"
                or deadline <= replay.target.window(session.source_session)[1]
            ):
                raise ValueError("Pending exit requires a genuinely unfinished terminal wait")
            resolution = "pending_at_window_end"
        following = first or late
        exits.append(
            {
                "request_id": intent.request_id,
                "position_id": intent.position_id,
                "source_session": intent.source_session,
                "contract": entry.contract,
                "side": entry.side,
                "requested_at_ns": intent.observed_at_ns,
                "ready_at_ns": ready,
                "deadline_at_ns": deadline,
                "trigger": trigger,
                "intent_reference": intent_ref,
                "before_ready_reference": before,
                "candidate_count": right - left,
                "first_candidate": first,
                "after_deadline_reference": late,
                "observed_gap_ns": (
                    following["quote_at_ns"] - before["quote_at_ns"]
                    if following is not None and before is not None
                    else None
                ),
                "late_after_deadline_ns": (
                    late["quote_at_ns"] - deadline if late is not None else None
                ),
                "resolution": resolution,
                "exit_fill": fill_ref,
                "unresolved_at_ns": unknowns[0].observed_at_ns if unknowns else None,
            }
        )
    if fingerprints() != pins or time.monotonic() - started > replay.MAX_SECONDS:
        raise ValueError("Diagnostic sources changed or complete-read deadline exceeded")
    return {
        "version": VERSION,
        "scope": SCOPE,
        "source_pins": pins,
        "complete_inputs": {
            "sessions": len(plan.inputs),
            "decisions": len(plan.decisions),
            "quotes": sum(len(s.quotes) for s in plan.inputs),
            "exit_intents": len(intents),
        },
        "interpretation": {
            "intent_reference": "Published at intent; timer precedes equal-time quotes",
            "before_ready_reference": "Retrospective strictly-before-ready reference, "
            "not necessarily published at intent",
            "candidate_interval": "Inclusive ready through deadline; original native order",
            "after_deadline_reference": "Retrospective excluded quote, never a fill or retry",
            "gap": "Observed update gap only; no standing liquidity or broker-fill proof",
            "coverage": "Only the complete declared input windows; no overnight inference",
        },
        "exits": exits,
        "terminal_state": asdict(plan.terminal_state),
        "complete_simulated_net_contract_ticks": (
            plan.terminal_state.complete_simulated_net_contract_ticks
        ),
        "flags": replay._flags(),
    }


def inspect(
    root: Path, registration_path: Path, registration_sha256: str, completion_sha256: str
) -> dict:
    """Read-only complete original-trial verification before describing its exits."""
    ledger._pin(registration_sha256)
    ledger._pin(completion_sha256)
    started, pins = time.monotonic(), fingerprints()
    value, inputs, config = trial.registration(root, registration_path, registration_sha256)
    output = Path(value["output"])
    request = status._inside(root, output / "request.json", "data/processed")
    request_pin = reader.study.common.hash_file(request, replay.MAX_OUTPUT_BYTES)
    verified = replay.verify_plan(inputs, config, output, request_pin, completion_sha256)
    report = describe_exits(replay.build_plan(inputs, config))
    if (
        replay._json(report["terminal_state"]) != replay._json(verified["terminal_state"])
        or fingerprints() != pins
        or time.monotonic() - started > replay.MAX_SECONDS
    ):
        raise ValueError("Original complete result or diagnostic sources changed")
    return {
        **report,
        "status": "verified_all_exit_quote_diagnostics_not_reconciliation",
        "origin": {
            "registration_path": str(status._inside(root, registration_path, "logs")),
            "registration_sha256": registration_sha256,
            "completion_sha256": completion_sha256,
            "request_sha256": request_pin,
            "input_manifest_sha256": config.source_manifest_sha256,
        },
    }


def _fresh_output(root: Path, path: Path) -> Path:
    path = status._inside(root, path, "logs")
    if path.suffix != ".json" or path.exists():
        raise ValueError("Diagnostic output requires a fresh logs JSON file")
    return path


def write_report(root: Path, path: Path, report: dict) -> None:
    path = _fresh_output(root, path)
    replay._write(path, replay._json(report))


def verify_report(
    root: Path,
    registration_path: Path,
    registration_sha256: str,
    completion_sha256: str,
    report_path: Path,
    report_sha256: str,
) -> dict:
    report_path = status._inside(root, report_path, "logs")
    if report_path.suffix != ".json":
        raise ValueError("Diagnostic evidence requires its JSON file")
    raw = replay._read(report_path, report_sha256)
    expected = inspect(root, registration_path, registration_sha256, completion_sha256)
    if raw != replay._json(expected):
        raise ValueError("Complete diagnostic differs from original-trial reconstruction")
    return {
        "status": "verified_all_exit_diagnostic_artifact_not_reconciliation",
        "report_sha256": report_sha256,
        "complete_inputs": expected["complete_inputs"],
        "terminal_tip_sha256": expected["terminal_state"]["tip_sha256"],
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
        if name == "inspect":
            p.add_argument("--output", type=Path)
        else:
            p.add_argument("--report", type=Path, required=True)
            p.add_argument("--report-sha256", required=True)
    args, root = parser.parse_args(), Path.cwd()
    if args.command == "verify":
        result = verify_report(
            root,
            args.registration,
            args.registration_sha256,
            args.completion_sha256,
            args.report,
            args.report_sha256,
        )
    else:
        if args.output is not None:
            _fresh_output(root, args.output)  # Refuse unsafe output BEFORE price access.
        result = inspect(root, args.registration, args.registration_sha256, args.completion_sha256)
        if args.output is not None:
            write_report(root, args.output, result)
            result = {
                "status": result["status"],
                "complete_inputs": result["complete_inputs"],
                "report_sha256": reader.study.common.hash_file(
                    args.output, replay.MAX_OUTPUT_BYTES
                ),
                "flags": replay._flags(),
            }
    print(replay._json(result).decode())


if __name__ == "__main__":
    main()
