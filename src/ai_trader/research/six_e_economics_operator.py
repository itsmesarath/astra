"""Registered declared economics on three frozen exposed-development controls.

Complete original verification precedes an event-only projection. No new policy,
fill, broker cost, funded-account approval, training or promotion is produced.
Every inspect claims one exclusive durable attempt; verify is read-only.
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path, PureWindowsPath

from ai_trader.research import six_e_continuous_trial as trial
from ai_trader.research import six_e_declared_economics as economics

replay, ledger, reader, status = trial.replay, trial.ledger, trial.reader, trial.status
VERSION = "six_e_economics_operator_v1"
SCOPE = "declared_sensitivity_on_exposed_development_not_validation"
REGISTERED = "registered_declared_economics_not_projected"
PROJECTED = "verified_local_declared_economic_projection_not_validation"
VERIFIED = "verified_declared_economics_artifact_not_validation"
ECONOMICS_SHA256 = "d45137f63c82afcce41d4214546d5ec1a1402487e8f91f02fd90d6617e627c85"


@dataclass(frozen=True, slots=True)
class TrustedControl:
    registration_path: str
    registration_sha256: str
    request_sha256: str
    completion_sha256: str
    output_path: str
    days: tuple[str, ...]
    policy_id: str
    scenario_id: str
    manifest_sha256: str
    origin_registration_path: str = "logs/6e_quote_observability_20261008_1_registration.json"
    origin_registration_sha256: str = (
        "d13052d355834fbdaeecd4efaaed3cbe76bf7e419683b78d42f613db9969c1a2"
    )


TRUSTED_CONTROLS = {
    "original": TrustedControl(
        "logs/6e_continuous_liquidity_20261008_1_registration.json",
        "05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea",
        "b99fd21383766d7a43f6009d759d8371a33dd437addddddcfdfe6607e0ff37b3",
        "b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9",
        "data/processed/6e_continuous_liquidity_20261008_1",
        ("2025-03-26", "2025-03-27"),
        "liquidity_follow",
        "liquidity-prefix-20261008-1",
        "b0b6139bfc2a49d807610fc7db4a186c943e5aa851d9d2d6aeb214635f4cb695",
    ),
    "carry": TrustedControl(
        "logs/6e_continuous_carry_20261008_1_registration.json",
        "b47904547b9b2a31fdca997f0e236794a99f4ff3084e83172d9ec9faaccfbe8c",
        "2761884b5d80b685c370ba625ed66f36c2bfd156d0e1cbdcbacbed40f6b89057",
        "f95d3b50a5fba7c54f5aba40ef0dbc945068362f23a0165716f111aee8ac2ea8",
        "data/processed/6e_continuous_carry_20261008_1",
        ("2025-03-26", "2025-03-27", "2025-03-28"),
        "liquidity_follow",
        "liquidity-carry-control-20261008-1",
        "671dc27bd96a00e1391be7e58f14cdea5df8cf977993f96fcc4a251273648e10",
    ),
    "no_trade": TrustedControl(
        "logs/6e_continuous_no_trade_20261008_1_registration.json",
        "0fd32bcaf6cafd458ece139091c03c6f00a216a9100098044d873ef09ab5b00b",
        "5fcfffaab6214ec831779804e463b8f59f55ab2802f2c9f5a15cbf431cbb26f6",
        "b4c5a08b57ddb8f1ee900590453900a30d0e7f7b0ab7ef18d6572db79980c54e",
        "data/processed/6e_continuous_no_trade_20261008_1",
        ("2025-03-26", "2025-03-27", "2025-03-28"),
        "no_trade",
        "no-trade-carry-control-20261008-1",
        "671dc27bd96a00e1391be7e58f14cdea5df8cf977993f96fcc4a251273648e10",
    ),
}


def _flags() -> dict:
    return {
        **replay._flags(),
        "source_files_authenticated": False,
        "cash_balance_confirmed": False,
        "margin_requirement_confirmed": False,
        "risk_approved": False,
        "cfd_execution_confirmed": False,
    }


def fingerprints() -> dict:
    pins = {
        **trial.fingerprints(),
        Path(economics.__file__).name: reader.study.common.hash_file(
            Path(economics.__file__), 1024**2
        ),
        Path(__file__).name: reader.study.common.hash_file(Path(__file__), 1024**2),
    }
    if pins[Path(economics.__file__).name] != ECONOMICS_SHA256:
        raise ValueError("Frozen declared economics source changed")
    return pins


def _shape(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(f"Exact {label} fields required")


def _equal(left, right, label):
    if replay._json(left) != replay._json(right):
        raise ValueError(f"{label} differs from its complete pinned declaration")


def _deadline(started):
    if time.monotonic() - started > replay.MAX_SECONDS:
        raise TimeoutError("Complete declared economics operator deadline exceeded")


def _path(root: Path, path: Path, scope: str) -> Path:
    if not isinstance(path, Path):
        raise ValueError("Explicit filesystem Path required")
    for component in path.parts:
        if component == path.anchor:
            continue
        if (
            ":" in component
            or component.endswith((".", " "))
            or PureWindowsPath(component).is_reserved()
        ):
            raise ValueError("Windows device names, trailing aliases and alternate streams refused")
    return status._inside(root, path if path.is_absolute() else root / path, scope)


def _log(root: Path, path: Path, *, fresh=False) -> Path:
    path = _path(root, path, "logs")
    if path.suffix != ".json" or not path.parent.is_dir():
        raise ValueError("JSON file beneath an existing logs directory required")
    if fresh and path.exists():
        raise ValueError("Fresh exclusive economics artifact required")
    return path


def _paths(root, registration_path, report_path, failure_path, *, fresh=()):
    paths = {
        "registration": registration_path,
        "report": report_path,
        "failure": failure_path,
        "attempt": report_path.with_name(report_path.stem + "_attempt.json"),
    }
    paths = {key: _log(root, path, fresh=key in fresh) for key, path in paths.items()}
    if len(set(paths.values())) != len(paths):
        raise ValueError("Registration, report, failure and derived attempt paths must differ")
    return paths


def _read_json(path, pin):
    raw = replay._read(path, pin)
    value = status._decode(raw)
    if raw != replay._json(value):
        raise ValueError("Pinned economics metadata must be a canonical JSON object")
    return value


def _control(root, control_id):
    if type(control_id) is not str or control_id not in TRUSTED_CONTROLS:
        raise ValueError("One of the three original trusted controls required")
    control = TRUSTED_CONTROLS[control_id]
    if type(control) is not TrustedControl:
        raise ValueError("Typed frozen trusted control required")
    value = asdict(control)
    for name in ("registration_path", "origin_registration_path"):
        value[name] = str(_log(root, Path(value[name])))
    value["output_path"] = str(_path(root, Path(control.output_path), "data/processed"))
    for name in (
        "registration_sha256",
        "request_sha256",
        "completion_sha256",
        "manifest_sha256",
        "origin_registration_sha256",
    ):
        ledger._pin(value[name])
    if type(control.days) is not tuple or not 1 <= len(control.days) <= replay.MAX_SESSIONS:
        raise ValueError("Bounded original train-prefix days required")
    for day in control.days:
        ledger._session(day)
        if replay.study.data.role_for_day(day) != "train":
            raise ValueError("Original development train sessions only")
    if tuple(sorted(set(control.days))) != control.days:
        raise ValueError("Original unique chronological control days required")
    return value


def _typed(seed, assumptions, days):
    if (
        type(seed) is not economics.EconomicSeed
        or type(assumptions) is not economics.DeclaredEconomics
    ):
        raise ValueError("Typed explicit EconomicSeed and DeclaredEconomics required")
    seed = economics.EconomicSeed(**asdict(seed))
    assumptions = economics.DeclaredEconomics(
        assumptions.account_currency,
        assumptions.tick_value_usd_micros,
        assumptions.entry_fee_usd_micros_per_contract,
        assumptions.exit_fee_usd_micros_per_contract,
        assumptions.margin,
    )
    if seed.initialized_at_ns != replay.target.window(days[0])[0]:
        raise ValueError("Seed time must equal the first original declared window start")
    return seed, assumptions


def _amounts(value, days):
    _shape(value["seed"], {field.name for field in fields(economics.EconomicSeed)}, "seed")
    _shape(
        value["assumptions"],
        {field.name for field in fields(economics.DeclaredEconomics)},
        "declared economics",
    )
    declared = dict(value["assumptions"])
    if declared["margin"] is not None:
        _shape(
            declared["margin"],
            {field.name for field in fields(economics.DeclaredMargin)},
            "declared margin",
        )
        declared["margin"] = economics.DeclaredMargin(**declared["margin"])
    return _typed(
        economics.EconomicSeed(**value["seed"]), economics.DeclaredEconomics(**declared), days
    )


def _manifest(value, control):
    _shape(value, {"version", "sessions"}, "original input manifest")
    if value["version"] != "six_e_feature_quote_fixture_v1":
        raise ValueError("Original input manifest version required")
    sessions = value["sessions"]
    if type(sessions) is not list or len(sessions) != len(control["days"]):
        raise ValueError("All original declared manifest sessions required")
    decisions = quotes = 0
    for day, session in zip(control["days"], sessions, strict=True):
        _shape(
            session,
            {
                "source_session",
                "contract",
                "role",
                "source_sha256",
                "decisions",
                "decisions_sha256",
                "quotes",
                "quotes_sha256",
            },
            "original manifest session",
        )
        if (
            session["source_session"] != day
            or session["contract"] != replay.study.census.dated_contract(day)
            or session["role"] != "train"
        ):
            raise ValueError("Original dated train-session identity differs")
        ledger._integer(session["decisions"], 0, 14_400)
        ledger._integer(session["quotes"], 0, replay.MAX_QUOTES)
        for key in ("source_sha256", "decisions_sha256", "quotes_sha256"):
            ledger._pin(session[key])
        decisions += session["decisions"]
        quotes += session["quotes"]
    ledger._integer(decisions, 0, replay.MAX_DECISIONS)
    if replay._digest(replay._json(value)) != control["manifest_sha256"]:
        raise ValueError("Trusted original complete manifest pin differs")
    return decisions, quotes


def _original(root, control, pins):
    """Pinned metadata only: never call trial.registration or any historical loader."""
    original = _read_json(Path(control["registration_path"]), control["registration_sha256"])
    _shape(
        original,
        {
            "protocol",
            "source_pins",
            "original_registration",
            "days",
            "manifest",
            "config",
            "original_coverage",
            "output",
            "scope",
            "flags",
        },
        "original trial registration",
    )
    original_pins = {
        key: pin
        for key, pin in pins.items()
        if key not in {Path(economics.__file__).name, Path(__file__).name}
    }
    replay_pins = {key: pins[key] for key in economics.SOURCE_NAMES}
    _equal(original["source_pins"], original_pins, "Original trial sources")
    _equal(original["protocol"], replay.protocol(), "Original protocol")
    _equal(original["flags"], replay._flags(), "Original false authority")
    _equal(original["days"], control["days"], "Original full days")
    _equal(
        original["original_registration"],
        {
            "path": control["origin_registration_path"],
            "sha256": control["origin_registration_sha256"],
        },
        "Original collection identity",
    )
    config = ledger.ScenarioConfig(
        control["scenario_id"],
        control["policy_id"],
        "bracket_exit",
        control["manifest_sha256"],
        replay.protocol()["version"],
        replay.target.COST,
        1,
    )
    _equal(original["config"], asdict(config), "Original one-contract configuration")
    if original["scope"] != trial.SCOPE or original["output"] != control["output_path"]:
        raise ValueError("Original declared scope or output changed")
    decisions, quotes = _manifest(original["manifest"], control)
    output = Path(control["output_path"])
    failure = _path(root, output / "failure.json", "data/processed")
    if failure.exists():
        raise ValueError("Original failure evidence forbids a successful-subset projection")
    request = _read_json(
        _path(root, output / "request.json", "data/processed"), control["request_sha256"]
    )
    _shape(
        request,
        {"protocol", "config", "manifest", "source_pins", "plan_sha256", "sidecars", "flags"},
        "original request",
    )
    for key, expected in (
        ("protocol", replay.protocol()),
        ("config", asdict(config)),
        ("manifest", original["manifest"]),
        ("source_pins", replay_pins),
        ("flags", replay._flags()),
    ):
        _equal(request[key], expected, f"Original request {key}")
    ledger._pin(request["plan_sha256"])
    _shape(request["sidecars"], {"events.jsonl", "receipts.jsonl", "decisions.jsonl"}, "sidecars")
    for name, descriptor in request["sidecars"].items():
        _shape(descriptor, {"bytes", "sha256"}, f"{name} descriptor")
        ledger._integer(descriptor["bytes"], 0, replay.MAX_OUTPUT_BYTES)
        ledger._pin(descriptor["sha256"])
    completion = _read_json(
        _path(root, output / "completion.json", "data/processed"), control["completion_sha256"]
    )
    _shape(
        completion,
        {
            "status",
            "request_sha256",
            "protocol",
            "source_pins",
            "sessions",
            "terminal_state",
            "checkpoint",
            "flags",
            "complete_simulated_net_contract_ticks",
        },
        "original completion",
    )
    if completion["status"] != "completed_continuous_quote_simulation_not_validation":
        raise ValueError("Original complete simulation status required")
    for key, expected in (
        ("request_sha256", control["request_sha256"]),
        ("protocol", replay.protocol()),
        ("source_pins", replay_pins),
        ("flags", replay._flags()),
    ):
        _equal(completion[key], expected, f"Original completion {key}")
    sessions = completion["sessions"]
    if type(sessions) is not list or len(sessions) != len(control["days"]):
        raise ValueError("Original complete session summaries required")
    for summary, session in zip(sessions, original["manifest"]["sessions"], strict=True):
        _shape(
            summary,
            {
                "source_session",
                "contract",
                "role",
                "decisions",
                "quotes",
                "counts",
                "triggers",
                "dispositions",
                "carried_contracts",
                "ledger_sequence",
                "ledger_tip_sha256",
            },
            "original session summary",
        )
        for key in ("source_session", "contract", "role", "decisions", "quotes"):
            _equal(summary[key], session[key], f"Original summary {key}")
        ledger._integer(summary["carried_contracts"], 0, 1)
        ledger._integer(summary["ledger_sequence"], 0, replay.MAX_EVENTS)
        ledger._pin(summary["ledger_tip_sha256"])
        for key in ("counts", "triggers", "dispositions"):
            if type(summary[key]) is not dict or len(summary[key]) > 32:
                raise ValueError("Bounded original complete session count map required")
            for name, count in summary[key].items():
                ledger._identifier(name)
                ledger._integer(count, 0, replay.MAX_QUOTES)
    _shape(
        completion["terminal_state"],
        {field.name for field in fields(ledger.LedgerState)},
        "original terminal state",
    )
    ledger._integer(completion["terminal_state"]["sequence"], 0, replay.MAX_EVENTS)
    ledger._pin(completion["terminal_state"]["tip_sha256"])
    _shape(
        completion["checkpoint"],
        {"pending_entry", "hold_at_ns", "exit_deadline_ns", "cooldown_until_ns"},
        "original checkpoint",
    )
    return original, request, completion, config, decisions, quotes


def prepare(
    root: Path,
    control_id: str,
    seed: economics.EconomicSeed,
    assumptions: economics.DeclaredEconomics,
    registration_path: Path,
    report_path: Path,
    failure_path: Path,
) -> dict:
    """Register explicit sensitivity assumptions using pinned metadata only."""
    started = time.monotonic()
    control = _control(root, control_id)
    seed, assumptions = _typed(seed, assumptions, control["days"])
    paths = _paths(
        root,
        registration_path,
        report_path,
        failure_path,
        fresh=("registration", "report", "failure", "attempt"),
    )
    pins = fingerprints()
    _original(root, control, pins)
    value = {
        "version": VERSION,
        "scope": SCOPE,
        "status": REGISTERED,
        "control_id": control_id,
        "control": control,
        "source_pins": pins,
        "seed": asdict(seed),
        "assumptions": asdict(assumptions),
        "artifacts": {key: str(path) for key, path in paths.items()},
        "flags": _flags(),
    }
    if fingerprints() != pins:
        raise ValueError("Operator source changed during assumption registration")
    _deadline(started)
    _paths(root, *[paths[key] for key in ("registration", "report", "failure")], fresh=paths)
    replay._write(_log(root, paths["registration"], fresh=True), replay._json(value))
    return value


def _registration(root, path, pin):
    ledger._pin(pin)
    path = _log(root, path)
    value = _read_json(path, pin)
    _shape(
        value,
        {
            "version",
            "scope",
            "status",
            "control_id",
            "control",
            "source_pins",
            "seed",
            "assumptions",
            "artifacts",
            "flags",
        },
        "operator registration",
    )
    if value["version"] != VERSION or value["scope"] != SCOPE or value["status"] != REGISTERED:
        raise ValueError("Original declared economics registration contract required")
    _equal(value["flags"], _flags(), "Operator false authority")
    control = _control(root, value["control_id"])
    _equal(value["control"], control, "Trusted frozen control identity")
    seed, assumptions = _amounts(value, control["days"])
    _shape(value["artifacts"], {"registration", "report", "failure", "attempt"}, "artifact paths")
    if any(type(item) is not str for item in value["artifacts"].values()):
        raise ValueError("Canonical explicit artifact paths required")
    paths = _paths(
        root, *[Path(value["artifacts"][key]) for key in ("registration", "report", "failure")]
    )
    _equal(value["artifacts"], {key: str(item) for key, item in paths.items()}, "Artifact paths")
    if paths["registration"] != path:
        raise ValueError("Registration cannot be adopted from a different path")
    pins = fingerprints()
    _equal(value["source_pins"], pins, "Registered operator sources")
    original = _original(root, control, pins)
    if fingerprints() != pins:
        raise ValueError("Operator source changed during metadata preflight")
    return value, seed, assumptions, original


def registration(root: Path, registration_path: Path, registration_sha256: str):
    """Validate canonical registration and original metadata, without price access."""
    value, seed, assumptions, _ = _registration(root, registration_path, registration_sha256)
    return value, seed, assumptions


def _attempt(value, pin):
    return {
        "version": VERSION,
        "scope": SCOPE,
        "status": "claimed_declared_economics_projection_attempt",
        "registration_path": value["artifacts"]["registration"],
        "registration_sha256": pin,
        "report_path": value["artifacts"]["report"],
        "failure_path": value["artifacts"]["failure"],
        "control_id": value["control_id"],
        "source_pins": value["source_pins"],
        "flags": _flags(),
    }


def _lines(root, output, request, name):
    descriptor = request["sidecars"][name]
    raw = replay._read(_path(root, output / name, "data/processed"), descriptor["sha256"])
    if len(raw) != descriptor["bytes"] or (raw and not raw.endswith(b"\n")):
        raise ValueError("Every original sidecar byte and complete newline record required")
    lines = raw.split(b"\n")[:-1] if raw else []
    if len(lines) > replay.MAX_EVENTS or any(
        not line or len(line) > ledger.MAX_RECORD_BYTES for line in lines
    ):
        raise ValueError("Full canonical sidecar records exceed event/record bounds")
    return lines


def _reconstruct(root, value, pin, seed, assumptions, original, started):
    control, pins = value["control"], value["source_pins"]
    declared, request, completion, config, decisions, quotes = original
    proof = trial.verify(
        root,
        Path(control["registration_path"]),
        control["registration_sha256"],
        control["completion_sha256"],
    )
    _shape(
        proof,
        {
            "status",
            "request_sha256",
            "completion_sha256",
            "sessions",
            "decisions",
            "events",
            "receipts",
            "terminal_state",
            "checkpoint",
            "complete_simulated_net_contract_ticks",
            "flags",
            "registration_sha256",
            "original_coverage",
        },
        "complete original verification proof",
    )
    if proof["status"] != "verified_continuous_quote_simulation_not_validation":
        raise ValueError("Complete original trial verification required")
    for key, expected in (
        ("request_sha256", control["request_sha256"]),
        ("completion_sha256", control["completion_sha256"]),
        ("registration_sha256", control["registration_sha256"]),
        ("sessions", len(control["days"])),
        ("decisions", decisions),
        ("terminal_state", completion["terminal_state"]),
        ("checkpoint", completion["checkpoint"]),
        (
            "complete_simulated_net_contract_ticks",
            completion["complete_simulated_net_contract_ticks"],
        ),
        ("flags", replay._flags()),
        ("original_coverage", declared["original_coverage"]),
    ):
        _equal(proof[key], expected, f"Complete original proof {key}")
    for key in ("events", "receipts"):
        ledger._integer(proof[key], 0, replay.MAX_EVENTS)
    _deadline(started)
    output = Path(control["output_path"])
    events = tuple(
        ledger._read_record(raw) for raw in _lines(root, output, request, "events.jsonl")
    )
    receipts = []
    for raw in _lines(root, output, request, "receipts.jsonl"):
        receipt = status._decode(raw)
        if replay._json(receipt) != raw:
            raise ValueError("Every original receipt must remain canonical")
        receipts.append(receipt)
    if len(events) != proof["events"] or len(receipts) != proof["receipts"]:
        raise ValueError("Complete verified event and receipt counts required")
    with ledger.ScenarioLedger(
        _path(root, output / "scenario.sqlite", "data/processed"), config, read_only=True
    ) as account:
        terminal = account.snapshot(expected_tip_sha256=proof["terminal_state"]["tip_sha256"])
    _equal(asdict(terminal), proof["terminal_state"], "Read-only complete journal state")
    plan = replay.ReplayPlan(
        config=config,
        inputs=(),
        manifest=request["manifest"],
        source_pins=request["source_pins"],
        events=events,
        receipts=tuple(receipts),
        decisions=(),
        sessions=tuple(completion["sessions"]),
        terminal_state=terminal,
        checkpoint=completion["checkpoint"],
    )
    projection = economics.project(plan, seed, assumptions)
    _equal(dict(projection.authority_flags), _flags(), "Pure projection false authority")
    _equal(asdict(projection.terminal_state), proof["terminal_state"], "Economic terminal state")
    _equal(
        projection.original_complete_simulated_net_contract_ticks,
        proof["complete_simulated_net_contract_ticks"],
        "Original nullable complete return",
    )
    if (
        projection.supplied_event_count != proof["events"]
        or projection.matched_receipt_count != proof["receipts"]
    ):
        raise ValueError("Projection must retain every verified event and receipt")
    # Recheck the registered identity and complete durable tape without another policy run.
    _equal(
        _read_json(Path(value["artifacts"]["registration"]), pin),
        value,
        "Operator registration after projection",
    )
    for name, descriptor in request["sidecars"].items():
        raw = replay._read(_path(root, output / name, "data/processed"), descriptor["sha256"])
        if len(raw) != descriptor["bytes"]:
            raise ValueError("Original complete sidecar size changed during projection")
    with ledger.ScenarioLedger(
        _path(root, output / "scenario.sqlite", "data/processed"), config, read_only=True
    ) as account:
        current = account.snapshot(expected_tip_sha256=terminal.tip_sha256)
    _equal(asdict(current), asdict(terminal), "Complete journal after projection")
    _equal(
        _original(root, control, pins)[:3],
        original[:3],
        "Original terminal metadata after projection",
    )
    if fingerprints() != pins:
        raise ValueError("Operator sources changed during complete projection")
    _deadline(started)
    attempt_raw = replay._json(_attempt(value, pin))
    report = {
        "version": VERSION,
        "scope": SCOPE,
        "status": PROJECTED,
        "registration_artifact": {"path": value["artifacts"]["registration"], "sha256": pin},
        "attempt_artifact": {
            "path": value["artifacts"]["attempt"],
            "sha256": replay._digest(attempt_raw),
        },
        "control_id": value["control_id"],
        "control": control,
        "source_pins": pins,
        "original_protocol": replay.protocol(),
        "original_config": asdict(config),
        "original_manifest": request["manifest"],
        "original_sessions": completion["sessions"],
        "local_reconstruction": proof,
        "complete_inputs": {
            "sessions": len(control["days"]),
            "decisions": decisions,
            "quotes": quotes,
            "events": len(events),
            "receipts": len(receipts),
        },
        "terminal_ledger_head_sha256": terminal.tip_sha256,
        "economic_projection": asdict(projection),
        "flags": _flags(),
    }
    if len(replay._json(report)) > replay.MAX_OUTPUT_BYTES:
        raise ValueError("Complete economic report exceeds original byte bound")
    return report


def inspect(root: Path, registration_path: Path, registration_sha256: str) -> dict:
    """Claim exactly one attempt, verify completely and write the registered report."""
    started = time.monotonic()
    value, seed, assumptions, original = _registration(root, registration_path, registration_sha256)
    artifacts = value["artifacts"]
    paths = _paths(
        root,
        *[Path(artifacts[key]) for key in ("registration", "report", "failure")],
        fresh=("report", "failure", "attempt"),
    )
    _deadline(started)
    marker = replay._json(_attempt(value, registration_sha256))
    owned = False
    try:
        with _log(root, paths["attempt"], fresh=True).open("xb") as handle:
            owned = True
            handle.write(marker)
            handle.flush()
            os.fsync(handle.fileno())
        report = _reconstruct(
            root, value, registration_sha256, seed, assumptions, original, started
        )
        _paths(
            root,
            *[paths[key] for key in ("registration", "report", "failure")],
            fresh=("report", "failure"),
        )
        if replay._read(paths["attempt"], replay._digest(marker)) != marker:
            raise ValueError("Owned attempt evidence changed during projection")
        _deadline(started)
        replay._write(_log(root, paths["report"], fresh=True), replay._json(report))
        return report
    except BaseException as exc:
        if owned:
            failure = {
                "version": VERSION,
                "scope": SCOPE,
                "status": "failed_declared_economics_projection",
                "registration_sha256": registration_sha256,
                "attempt_sha256": replay._digest(marker),
                "exception_type": type(exc).__name__,
                "reason": str(exc)[:512],
                "flags": _flags(),
            }
            try:
                replay._write(_log(root, paths["failure"], fresh=True), replay._json(failure))
            except (OSError, ValueError) as failure_exc:
                exc.add_note(f"Failure evidence could not be written: {type(failure_exc).__name__}")
        raise


def verify_report(
    root: Path, registration_path: Path, registration_sha256: str, report_sha256: str
) -> dict:
    """Pin-check report/attempt before original reconstruction; never write or resume."""
    ledger._pin(registration_sha256)
    ledger._pin(report_sha256)
    started = time.monotonic()
    value, seed, assumptions, original = _registration(root, registration_path, registration_sha256)
    artifacts = value["artifacts"]
    failure = _log(root, Path(artifacts["failure"]))
    if failure.exists():
        raise ValueError("Registered failure evidence forbids successful economics verification")
    marker = replay._json(_attempt(value, registration_sha256))
    marker_pin = replay._digest(marker)
    if replay._read(_log(root, Path(artifacts["attempt"])), marker_pin) != marker:
        raise ValueError("Original complete exclusive attempt marker required")
    report_path = _log(root, Path(artifacts["report"]))
    raw = replay._read(report_path, report_sha256)
    report = status._decode(raw)
    if raw != replay._json(report):
        raise ValueError("Pinned economic report must remain canonical")
    _shape(
        report,
        {
            "version",
            "scope",
            "status",
            "registration_artifact",
            "attempt_artifact",
            "control_id",
            "control",
            "source_pins",
            "original_protocol",
            "original_config",
            "original_manifest",
            "original_sessions",
            "local_reconstruction",
            "complete_inputs",
            "terminal_ledger_head_sha256",
            "economic_projection",
            "flags",
        },
        "complete economic report",
    )
    for key, expected in (
        ("version", VERSION),
        ("scope", SCOPE),
        ("status", PROJECTED),
        (
            "registration_artifact",
            {"path": artifacts["registration"], "sha256": registration_sha256},
        ),
        ("attempt_artifact", {"path": artifacts["attempt"], "sha256": marker_pin}),
        ("control_id", value["control_id"]),
        ("control", value["control"]),
        ("source_pins", value["source_pins"]),
        ("flags", _flags()),
    ):
        _equal(report[key], expected, f"Pinned report {key}")
    _shape(
        report["economic_projection"],
        {field.name for field in fields(economics.EconomicProjection)},
        "full economic projection",
    )
    for key, expected in (
        ("version", economics.VERSION),
        ("status", economics.STATUS),
        ("seed", asdict(seed)),
        ("assumptions", asdict(assumptions)),
        ("authority_flags", tuple(sorted(_flags().items()))),
    ):
        _equal(report["economic_projection"][key], expected, f"Pinned projection {key}")
    expected = _reconstruct(root, value, registration_sha256, seed, assumptions, original, started)
    if raw != replay._json(expected):
        raise ValueError("Complete economic report differs from canonical original reconstruction")
    # Recheck the externally pinned files and failure path after the bounded reconstruction.
    if (
        replay._read(report_path, report_sha256) != raw
        or replay._read(_log(root, Path(artifacts["attempt"])), marker_pin) != marker
        or _log(root, failure).exists()
    ):
        raise ValueError("Report, attempt or failure evidence changed during verification")
    _deadline(started)
    return {
        "status": VERIFIED,
        "registration_sha256": registration_sha256,
        "report_sha256": report_sha256,
        "attempt_sha256": marker_pin,
        "complete_inputs": expected["complete_inputs"],
        "terminal_ledger_head_sha256": expected["terminal_ledger_head_sha256"],
        "complete_declared_equity_usd_micros": expected["economic_projection"][
            "complete_declared_equity_usd_micros"
        ],
        "complete_declared_net_return_usd_micros": expected["economic_projection"][
            "complete_declared_net_return_usd_micros"
        ],
        "flags": _flags(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--control", choices=tuple(TRUSTED_CONTROLS), required=True)
    prep.add_argument("--registration", type=Path, required=True)
    prep.add_argument("--report", type=Path, required=True)
    prep.add_argument("--failure", type=Path, required=True)
    prep.add_argument("--initial-balance-usd-micros", type=int, required=True)
    prep.add_argument("--initialized-at-ns", type=int, required=True)
    prep.add_argument("--account-currency", choices=("USD",), required=True)
    prep.add_argument("--tick-value-usd-micros", type=int, required=True)
    prep.add_argument("--entry-fee-usd-micros-per-contract", type=int, required=True)
    prep.add_argument("--exit-fee-usd-micros-per-contract", type=int, required=True)
    prep.add_argument("--margin", choices=("none", "fixed"), required=True)
    prep.add_argument("--initial-margin-usd-micros-per-contract", type=int)
    prep.add_argument("--maintenance-margin-usd-micros-per-contract", type=int)
    for name in ("inspect", "verify"):
        command = sub.add_parser(name)
        command.add_argument("--registration", type=Path, required=True)
        command.add_argument("--registration-sha256", required=True)
        if name == "verify":
            command.add_argument("--report-sha256", required=True)
    args, root = parser.parse_args(), Path.cwd()
    if args.command == "prepare":
        margin_amounts = (
            args.initial_margin_usd_micros_per_contract,
            args.maintenance_margin_usd_micros_per_contract,
        )
        if (args.margin == "none" and any(amount is not None for amount in margin_amounts)) or (
            args.margin == "fixed" and any(amount is None for amount in margin_amounts)
        ):
            parser.error("fixed margin requires both amounts; none margin accepts neither amount")
        margin = None if args.margin == "none" else economics.DeclaredMargin(*margin_amounts)
        value = prepare(
            root,
            args.control,
            economics.EconomicSeed(args.initial_balance_usd_micros, args.initialized_at_ns),
            economics.DeclaredEconomics(
                args.account_currency,
                args.tick_value_usd_micros,
                args.entry_fee_usd_micros_per_contract,
                args.exit_fee_usd_micros_per_contract,
                margin,
            ),
            args.registration,
            args.report,
            args.failure,
        )
        result = {
            "status": REGISTERED,
            "registration_sha256": replay._digest(replay._json(value)),
            "control_id": value["control_id"],
            "artifacts": value["artifacts"],
            "flags": _flags(),
        }
    elif args.command == "inspect":
        report = inspect(root, args.registration, args.registration_sha256)
        result = {
            "status": PROJECTED,
            "report_sha256": replay._digest(replay._json(report)),
            "attempt_artifact": report["attempt_artifact"],
            "complete_inputs": report["complete_inputs"],
            "terminal_ledger_head_sha256": report["terminal_ledger_head_sha256"],
            "flags": _flags(),
        }
    else:
        result = verify_report(
            root, args.registration, args.registration_sha256, args.report_sha256
        )
    print(replay._json(result).decode())


if __name__ == "__main__":
    main()
