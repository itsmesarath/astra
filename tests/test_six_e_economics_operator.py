"""Independent synthetic operator checks; no historical inputs or external accounts."""

import hashlib
import json
import math
import sqlite3
import sys
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ai_trader.research import six_e_economics_operator as operator

replay, trial, economics = operator.replay, operator.trial, operator.economics
ledger = replay.ledger
DAYS = ("2025-03-26", "2025-03-27", "2025-03-28")
SECOND, TICK = replay.target.SECOND, replay.target.TICK
MS = SECOND // 1000


def file_pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def synthetic_source(day, *, unknown=False):
    start, _ = replay.target.window(day)
    features = dict.fromkeys(replay.rules.flow.data.FEATURES, 0.0)
    features.update(
        log_bid_qty=math.log1p(5),
        log_ask_qty=math.log1p(5),
        log_bid_depth5=math.log1p(20),
        log_ask_depth5=math.log1p(20),
        bid_top_share5=0.25,
        ask_top_share5=0.25,
        bid_span5_ticks=4.0,
        ask_span5_ticks=4.0,
        log_known_trades_5s=math.log1p(20),
        log_quote_events_5s=math.log1p(20),
        normalized_cvd_5s=0.5,
        normalized_ofi_5s=0.5,
        mid_change_5s_ticks=1.0,
        mid_range_5s_ticks=4.0,
    )
    row = {
        "source_session": day,
        "contract": replay.study.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": start,
        "eligible": True,
        "features": features,
        "execution_features": dict.fromkeys(replay.rules.flow.FEATURES, 0.0),
        "future_poison": object(),
    }
    quotes = [(0, 100, 101), (100 * MS, 100, 101)]
    if not unknown:
        quotes.extend([(200 * MS, 105, 106), (300 * MS, 104, 105)])
    native = np.asarray(
        [(start + offset, bid * TICK, ask * TICK) for offset, bid, ask in quotes],
        dtype=np.int64,
    )
    return replay.ReplaySession(
        day, row["contract"], "a" * 64, (replay.decision_input(row, 0),), native
    )


def new_assumptions(margin=None):
    return economics.DeclaredEconomics("USD", 125, 8, 11, margin)


def new_seed():
    return economics.EconomicSeed(1000, replay.target.window(DAYS[0])[0])


def forbidden(*args, **kwargs):
    raise AssertionError("Forbidden operator execution or historical access")


def snapshot_files(root):
    return {
        str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def control_factory(tmp_path, monkeypatch):
    """Original native simulator evidence is built only from tiny synthetic arrays."""
    (tmp_path / "logs").mkdir()
    (tmp_path / "data/processed").mkdir(parents=True)

    def create(shape="closed"):
        days = DAYS if shape in ("carry", "flat") else DAYS[:2]
        policy = "no_trade" if shape == "flat" else "liquidity_follow"
        inputs = tuple(
            synthetic_source(day, unknown=shape in ("unknown", "carry") and index == 1)
            for index, day in enumerate(days)
        )
        scenario_id = f"synthetic-operator-{shape}"
        config = ledger.ScenarioConfig(
            scenario_id,
            policy,
            "bracket_exit",
            replay.manifest_pin(inputs),
            replay.protocol()["version"],
        )
        plan = replay.build_plan(inputs, config)
        output = tmp_path / "data/processed" / f"synthetic_{shape}"
        replay.write_plan(plan, output)
        origin = tmp_path / "logs" / f"origin_{shape}.json"
        origin.write_bytes(b'{"synthetic_metadata_only":true}')
        original_registration = tmp_path / "logs" / f"original_{shape}.json"
        original_coverage = {"synthetic_complete_prefix": len(days)}
        metadata = {
            "protocol": replay.protocol(),
            "source_pins": trial.fingerprints(),
            "original_registration": {"path": str(origin), "sha256": file_pin(origin)},
            "days": list(days),
            "manifest": plan.manifest,
            "config": asdict(config),
            "original_coverage": original_coverage,
            "output": str(output),
            "scope": trial.SCOPE,
            "flags": replay._flags(),
        }
        original_registration.write_bytes(replay._json(metadata))
        trusted = operator.TrustedControl(
            registration_path=str(original_registration),
            registration_sha256=file_pin(original_registration),
            request_sha256=file_pin(output / "request.json"),
            completion_sha256=file_pin(output / "completion.json"),
            output_path=str(output),
            days=days,
            policy_id=policy,
            scenario_id=scenario_id,
            manifest_sha256=config.source_manifest_sha256,
            origin_registration_path=str(origin),
            origin_registration_sha256=file_pin(origin),
        )
        control_id = "synthetic_control"
        monkeypatch.setattr(operator, "TRUSTED_CONTROLS", {control_id: trusted})
        calls = []

        def verify(project_root, path, registration_pin, completion_pin):
            assert (project_root, Path(path), registration_pin, completion_pin) == (
                tmp_path,
                original_registration,
                trusted.registration_sha256,
                trusted.completion_sha256,
            )
            calls.append((Path(path), registration_pin, completion_pin))
            proof = replay.verify_plan(
                inputs, config, output, trusted.request_sha256, completion_pin
            )
            return {
                **proof,
                "registration_sha256": registration_pin,
                "original_coverage": original_coverage,
            }

        monkeypatch.setattr(trial, "verify", verify)
        monkeypatch.setattr(trial, "run", forbidden)
        monkeypatch.setattr(trial, "prepare", forbidden)
        monkeypatch.setattr(trial, "registration", forbidden)
        monkeypatch.setattr(trial.reader, "load_sessions", forbidden)
        return SimpleNamespace(
            root=tmp_path,
            control_id=control_id,
            trusted=trusted,
            plan=plan,
            output=output,
            original_registration=original_registration,
            original_metadata=metadata,
            original_coverage=original_coverage,
            calls=calls,
            native_verify=verify,
            registration=tmp_path / "logs" / f"economics_{shape}.json",
            report=tmp_path / "logs" / f"economics_{shape}_report.json",
            failure=tmp_path / "logs" / f"economics_{shape}_failure.json",
            attempt=tmp_path / "logs" / f"economics_{shape}_report_attempt.json",
        )

    return create


@pytest.fixture
def control(control_factory):
    return control_factory()


def prepare(control, **changes):
    arguments = {
        "root": control.root,
        "control_id": control.control_id,
        "seed": new_seed(),
        "assumptions": new_assumptions(),
        "registration_path": control.registration,
        "report_path": control.report,
        "failure_path": control.failure,
    }
    arguments.update(changes)
    value = operator.prepare(**arguments)
    return value, file_pin(control.registration)


def repin_registration(control, value):
    control.registration.write_bytes(replay._json(value))
    return file_pin(control.registration)


def test_prepare_only_registers_declared_assumptions_before_native_verification(control):
    before = snapshot_files(control.output)
    value, pin = prepare(control)
    assert control.calls == []
    assert snapshot_files(control.output) == before
    assert not control.report.exists()
    assert not control.failure.exists()
    assert not control.attempt.exists()
    assert value["artifacts"] == {
        "registration": str(control.registration),
        "report": str(control.report),
        "failure": str(control.failure),
        "attempt": str(control.attempt),
    }
    registered, seed, assumptions = operator.registration(control.root, control.registration, pin)
    assert replay._json(registered) == replay._json(value)
    assert seed == new_seed()
    assert assumptions == new_assumptions()
    assert control.calls == []


@pytest.mark.parametrize("shape", ["closed", "unknown", "carry", "flat"])
def test_native_complete_shapes_and_readonly_canonical_verification(control_factory, shape):
    control = control_factory(shape)
    _, pin = prepare(control)
    before_original = snapshot_files(control.output)
    report = operator.inspect(control.root, control.registration, pin)
    assert report["status"] == "verified_local_declared_economic_projection_not_validation"
    assert control.report.read_bytes() == replay._json(report)
    assert control.attempt.is_file()
    assert not control.failure.exists()
    assert snapshot_files(control.output) == before_original
    assert report["complete_inputs"] == {
        "sessions": len(control.plan.inputs),
        "decisions": len(control.plan.decisions),
        "quotes": sum(len(session.quotes) for session in control.plan.inputs),
        "events": len(control.plan.events),
        "receipts": len(control.plan.receipts),
    }
    assert report["original_manifest"] == control.plan.manifest
    assert replay._json(report["original_sessions"]) == replay._json(control.plan.sessions)
    assert report["local_reconstruction"]["checkpoint"] == control.plan.checkpoint
    assert all(value is False for value in report["flags"].values())
    projection = report["economic_projection"]
    assert projection["supplied_event_count"] == len(control.plan.events)
    assert projection["matched_receipt_count"] == len(control.plan.receipts)
    assert projection["terminal_state"] == asdict(control.plan.terminal_state)
    assert projection["original_complete_simulated_net_contract_ticks"] == (
        control.plan.terminal_state.complete_simulated_net_contract_ticks
    )
    assert len(projection["path"]) == len(control.plan.events)
    if shape in ("unknown", "carry"):
        assert projection["complete_declared_equity_usd_micros"] is None
        assert projection["complete_declared_net_return_usd_micros"] is None
        assert projection["terminal_state"]["reservation"]["status"] == "UNKNOWN"
    else:
        assert projection["complete_declared_equity_usd_micros"] is not None
        assert projection["complete_declared_net_return_usd_micros"] is not None
    if shape == "flat":
        assert projection["complete_declared_net_return_usd_micros"] == 0
        assert projection["entry_fees_usd_micros"] == 0
        assert projection["exit_fees_usd_micros"] == 0
    before = snapshot_files(control.root)
    verified = operator.verify_report(
        control.root, control.registration, pin, file_pin(control.report)
    )
    assert verified["status"] == "verified_declared_economics_artifact_not_validation"
    assert snapshot_files(control.root) == before
    assert len(control.calls) == 2


def test_projection_uses_event_only_replay40_and_outer_proof_source47(control, monkeypatch):
    _, pin = prepare(control)
    original_project = economics.project
    seen = []

    def project(plan, seed, assumptions):
        assert plan.inputs == ()
        assert plan.decisions == ()
        assert set(plan.source_pins) == economics.SOURCE_NAMES
        assert len(plan.source_pins) == 40
        assert plan.source_pins == control.plan.source_pins
        seen.append(plan)
        return original_project(plan, seed, assumptions)

    monkeypatch.setattr(economics, "project", project)
    report = operator.inspect(control.root, control.registration, pin)
    assert len(seen) == 1
    assert len(report["source_pins"]) == 47
    assert set(trial.fingerprints()) <= set(report["source_pins"])
    assert report["economic_projection"]["terminal_state"]["tip_sha256"] == (
        control.plan.terminal_state.tip_sha256
    )


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("seed", "initial_balance_usd_micros", True),
        ("seed", "initial_balance_usd_micros", 0),
        ("seed", "initial_balance_usd_micros", -1),
        ("seed", "initial_balance_usd_micros", 1.0),
        ("seed", "initial_balance_usd_micros", "1000"),
        ("seed", "initial_balance_usd_micros", economics.MAX_MONEY + 1),
        ("seed", "initialized_at_ns", True),
        ("seed", "initialized_at_ns", 1.0),
        ("seed", "initialized_at_ns", replay.target.window(DAYS[0])[0] - 1),
        ("seed", "initialized_at_ns", replay.target.window(DAYS[0])[0] + 1),
        ("assumptions", "account_currency", "EUR"),
        ("assumptions", "account_currency", True),
        ("assumptions", "tick_value_usd_micros", True),
        ("assumptions", "tick_value_usd_micros", 0),
        ("assumptions", "tick_value_usd_micros", -1),
        ("assumptions", "tick_value_usd_micros", 1.0),
        ("assumptions", "entry_fee_usd_micros_per_contract", True),
        ("assumptions", "entry_fee_usd_micros_per_contract", -1),
        ("assumptions", "entry_fee_usd_micros_per_contract", 1.0),
        ("assumptions", "exit_fee_usd_micros_per_contract", True),
        ("assumptions", "exit_fee_usd_micros_per_contract", -1),
        ("assumptions", "exit_fee_usd_micros_per_contract", "11"),
        ("assumptions", "margin", {"initial": 5, "maintenance": 3}),
    ],
)
def test_prepare_refuses_poisoned_typed_amounts_before_verification(control, target, field, value):
    seed, assumptions = new_seed(), new_assumptions()
    object.__setattr__(seed if target == "seed" else assumptions, field, value)
    with pytest.raises((ValueError, TypeError)):
        prepare(control, seed=seed, assumptions=assumptions)
    assert control.calls == []
    assert not control.registration.exists()
    assert not control.attempt.exists()
    assert not control.report.exists()
    assert not control.failure.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("initial_usd_micros_per_contract", True),
        ("initial_usd_micros_per_contract", -1),
        ("initial_usd_micros_per_contract", 1.0),
        ("initial_usd_micros_per_contract", 2),
        ("maintenance_usd_micros_per_contract", True),
        ("maintenance_usd_micros_per_contract", -1),
        ("maintenance_usd_micros_per_contract", "3"),
        ("maintenance_usd_micros_per_contract", 6),
    ],
)
def test_prepare_revalidates_poisoned_margin(control, field, value):
    margin = economics.DeclaredMargin(5, 3)
    assumptions = new_assumptions(margin)
    object.__setattr__(margin, field, value)
    with pytest.raises((ValueError, TypeError)):
        prepare(control, assumptions=assumptions)
    assert control.calls == []
    assert not control.registration.exists()


@pytest.mark.parametrize("margin", [None, economics.DeclaredMargin(0, 0)])
def test_optional_margin_is_explicit_and_not_defaulted(control, margin):
    _, pin = prepare(control, assumptions=new_assumptions(margin))
    report = operator.inspect(control.root, control.registration, pin)
    projection = report["economic_projection"]
    assert projection["assumptions"]["margin"] == (None if margin is None else asdict(margin))
    field = "declared_initial_margin_reserved_usd_micros"
    assert projection[field] == (None if margin is None else 0)


@pytest.mark.parametrize("control_id", ["", "unknown", "../../escape", True, None, 1])
def test_prepare_refuses_any_unallowlisted_control(control, control_id):
    with pytest.raises((ValueError, TypeError)):
        prepare(control, control_id=control_id)
    assert control.calls == []
    assert not control.registration.exists()


@pytest.mark.parametrize("kind", ["registration", "report", "failure", "attempt"])
def test_prepare_refuses_existing_target_before_any_original_verification(control, kind):
    path = getattr(control, kind)
    path.write_bytes(b"preserved prior attempt")
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        prepare(control)
    assert control.calls == []
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize(
    ("argument", "target"),
    [
        ("registration_path", "report"),
        ("registration_path", "failure"),
        ("registration_path", "attempt"),
        ("report_path", "registration"),
        ("report_path", "failure"),
        ("failure_path", "registration"),
        ("failure_path", "report"),
        ("failure_path", "attempt"),
    ],
)
def test_prepare_refuses_all_output_identity_collisions(control, argument, target):
    with pytest.raises(ValueError):
        prepare(control, **{argument: getattr(control, target)})
    assert control.calls == []
    assert not control.registration.exists()
    assert not control.report.exists()
    assert not control.failure.exists()
    assert not control.attempt.exists()


@pytest.mark.parametrize("argument", ["registration_path", "report_path", "failure_path"])
@pytest.mark.parametrize(
    "relative_path",
    [
        "outside.json",
        "logs",
        "logs/report.txt",
        "logs/../outside.json",
        "logs/hidden/report.json:stream",
        "logs/NUL.json",
        "logs/COM1.json",
        "logs/LPT9.json",
        "logs/trailing.json.",
        "logs/trailing.json ",
        "logs/report.json:secret.json",
    ],
)
def test_prepare_refuses_unsafe_output_before_verification(control, argument, relative_path):
    with pytest.raises((ValueError, OSError)):
        prepare(control, **{argument: control.root / relative_path})
    assert control.calls == []
    assert not control.attempt.exists()
    assert not control.report.exists()
    assert not control.failure.exists()


@pytest.mark.parametrize("kind", ["registration", "report", "failure", "attempt", "logs"])
@pytest.mark.parametrize("link_type", ["symlink", "junction"])
def test_prepare_refuses_final_and_ancestor_link_guards(control, monkeypatch, kind, link_type):
    target = control.root / "logs" if kind == "logs" else getattr(control, kind)
    if link_type == "symlink":
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == target or original(path))
    else:
        original = operator.os.path.isjunction
        monkeypatch.setattr(
            operator.os.path, "isjunction", lambda path: Path(path) == target or original(path)
        )
    with pytest.raises(ValueError):
        prepare(control)
    assert control.calls == []
    assert not control.registration.exists()


def test_real_link_never_overwrites_outside_sentinel(control):
    sentinel = control.root / "outside.json"
    sentinel.write_bytes(b"outside sentinel")
    try:
        control.report.symlink_to(sentinel)
    except OSError:
        pytest.skip("Windows symlink creation privilege unavailable")
    before = sentinel.read_bytes(), sentinel.stat().st_mtime_ns
    with pytest.raises(ValueError):
        prepare(control)
    assert (sentinel.read_bytes(), sentinel.stat().st_mtime_ns) == before
    assert control.calls == []


@pytest.mark.parametrize("pin", ["", "a" * 63, "A" * 64, "g" * 64, True, None])
def test_bad_registration_pin_fails_before_original_verifier(control, pin):
    prepare(control)
    with pytest.raises((ValueError, TypeError)):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert not control.attempt.exists()
    assert not control.report.exists()
    assert not control.failure.exists()


@pytest.mark.parametrize("pin", ["", "a" * 63, "A" * 64, "g" * 64, True, None])
def test_bad_report_pin_fails_before_original_verifier(control, pin):
    _, registration_pin = prepare(control)
    operator.inspect(control.root, control.registration, registration_pin)
    control.calls.clear()
    before = snapshot_files(control.root)
    with pytest.raises((ValueError, TypeError)):
        operator.verify_report(control.root, control.registration, registration_pin, pin)
    assert control.calls == []
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize("kind", ["attempt", "report", "failure"])
def test_inspect_refuses_prior_attempt_evidence_before_verification(control, kind):
    _, pin = prepare(control)
    getattr(control, kind).write_bytes(b"prior evidence")
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize("artifact", ["registration", "request", "completion", "failure"])
def test_original_evidence_tampering_refused_before_trial_verifier(control, artifact):
    _, pin = prepare(control)
    path = (
        control.original_registration
        if artifact == "registration"
        else control.output / f"{artifact}.json"
    )
    path.write_bytes(b'{"changed_original":true}')
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize("change", ["whitespace", "duplicate", "nonfinite", "extra", "missing"])
def test_registration_bytes_and_schema_refused_even_when_repinned(control, change):
    value, _ = prepare(control)
    if change == "whitespace":
        raw = json.dumps(value, indent=2).encode()
    elif change == "duplicate":
        raw = replay._json(value)
        raw = b'{"control":null,' + raw[1:]
    elif change == "nonfinite":
        raw = b'{"control":NaN}'
    elif change == "extra":
        raw = replay._json({**value, "new_authority": False})
    else:
        value.pop("artifacts")
        raw = replay._json(value)
    control.registration.write_bytes(raw)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, file_pin(control.registration))
    assert control.calls == []
    assert not control.attempt.exists()
    assert not control.report.exists()
    assert not control.failure.exists()


@pytest.mark.parametrize(
    "change",
    [
        "drop_path",
        "reverse_path",
        "event_count",
        "receipt_count",
        "balance",
        "null_return",
        "head",
        "seed",
        "fees",
        "source",
        "status",
        "flag_integer",
        "flag_true",
        "extra",
    ],
)
def test_complete_report_forgeries_fail_even_with_matching_new_report_pin(control_factory, change):
    control = control_factory("unknown")
    _, pin = prepare(control)
    report = operator.inspect(control.root, control.registration, pin)
    forged = deepcopy(report)
    projection = forged["economic_projection"]
    if change == "drop_path":
        projection["path"] = projection["path"][:-1]
    elif change == "reverse_path":
        projection["path"] = projection["path"][::-1]
    elif change == "event_count":
        projection["supplied_event_count"] -= 1
    elif change == "receipt_count":
        projection["matched_receipt_count"] -= 1
    elif change == "balance":
        projection["declared_realization_balance_usd_micros"] += 1
    elif change == "null_return":
        projection["complete_declared_net_return_usd_micros"] = 0
        projection["complete_declared_equity_usd_micros"] = 1000
    elif change == "head":
        projection["terminal_state"]["tip_sha256"] = "a" * 64
    elif change == "seed":
        projection["seed"]["initial_balance_usd_micros"] += 1
    elif change == "fees":
        projection["assumptions"]["entry_fee_usd_micros_per_contract"] += 1
    elif change == "source":
        name = next(iter(forged["source_pins"]))
        forged["source_pins"][name] = "a" * 64
    elif change == "status":
        forged["status"] = "risk_approved"
    elif change.startswith("flag_"):
        flags = [list(item) for item in projection["authority_flags"]]
        flags[0][1] = 0 if change == "flag_integer" else True
        projection["authority_flags"] = flags
    else:
        forged["complete_return_claim"] = 123
    control.report.write_bytes(replay._json(forged))
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.verify_report(control.root, control.registration, pin, file_pin(control.report))
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize("encoding", ["whitespace", "newline", "duplicate", "truncated"])
def test_noncanonical_or_incomplete_saved_report_never_verifies(control, encoding):
    _, pin = prepare(control)
    report = operator.inspect(control.root, control.registration, pin)
    canonical = replay._json(report)
    if encoding == "whitespace":
        raw = json.dumps(report, indent=2).encode()
    elif encoding == "newline":
        raw = canonical + b"\n"
    elif encoding == "duplicate":
        raw = b'{"status":"forged",' + canonical[1:]
    else:
        raw = canonical[:-1]
    control.report.write_bytes(raw)
    with pytest.raises(ValueError):
        operator.verify_report(control.root, control.registration, pin, file_pin(control.report))


def test_attempt_is_exclusively_claimed_before_original_verifier(control, monkeypatch):
    _, pin = prepare(control)
    seen = []

    def verify(*args):
        assert control.attempt.is_file()
        assert not control.report.exists()
        assert not control.failure.exists()
        seen.append(file_pin(control.attempt))
        return control.native_verify(*args)

    monkeypatch.setattr(trial, "verify", verify)
    operator.inspect(control.root, control.registration, pin)
    assert len(seen) == 1
    assert file_pin(control.attempt) == seen[0]


@pytest.mark.parametrize("exception_type", [ValueError, RuntimeError, TimeoutError, OSError])
def test_native_verifier_failure_retains_attempt_and_failure_and_refuses_retry(
    control, monkeypatch, exception_type
):
    _, pin = prepare(control)
    calls = []

    def failing_verifier(*args):
        assert control.attempt.exists()
        calls.append(args)
        raise exception_type("synthetic verifier failure")

    monkeypatch.setattr(trial, "verify", failing_verifier)
    with pytest.raises(exception_type):
        operator.inspect(control.root, control.registration, pin)
    assert len(calls) == 1
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()
    failed = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert len(calls) == 1
    assert snapshot_files(control.root) == failed


def test_projection_failure_retains_admitted_attempt(control, monkeypatch):
    _, pin = prepare(control)
    monkeypatch.setattr(economics, "project", lambda *args: (_ for _ in ()).throw(ValueError()))
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert len(control.calls) == 1
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_deadline_after_verifier_is_failure_never_success(control, monkeypatch):
    _, pin = prepare(control)
    clock = {"now": 0.0}
    monkeypatch.setattr(operator.time, "monotonic", lambda: clock["now"])

    def verify(*args):
        proof = control.native_verify(*args)
        clock["now"] = replay.MAX_SECONDS + 1
        return proof

    monkeypatch.setattr(trial, "verify", verify)
    with pytest.raises((ValueError, TimeoutError)):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_losing_attempt_creation_race_cannot_poison_winner(control, monkeypatch):
    _, pin = prepare(control)
    original_open = Path.open

    def racing_open(path, mode="r", *args, **kwargs):
        if path == control.attempt and mode == "xb":
            with original_open(path, "wb") as stream:
                stream.write(b"independent race winner")
            raise FileExistsError("Synthetic exclusive attempt race")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises((ValueError, FileExistsError)):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert control.attempt.read_bytes() == b"independent race winner"
    assert not control.failure.exists()
    assert not control.report.exists()


@pytest.mark.parametrize("sidecar", ["events.jsonl", "receipts.jsonl"])
def test_sidecar_replacement_after_verification_cannot_supply_projection(
    control, monkeypatch, sidecar
):
    _, pin = prepare(control)
    original_project = economics.project
    projections = []

    def project(*args):
        projections.append(args)
        return original_project(*args)

    def verify(*args):
        proof = control.native_verify(*args)
        path = control.output / sidecar
        path.write_bytes(path.read_bytes() + b"\n")
        return proof

    monkeypatch.setattr(economics, "project", project)
    monkeypatch.setattr(trial, "verify", verify)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert projections == []
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_sources_changed_during_projection_refuse_success(control, monkeypatch):
    _, pin = prepare(control)
    original_fingerprints = operator.fingerprints
    original_project = economics.project
    drift = {"changed": False}

    def fingerprints():
        pins = original_fingerprints()
        if drift["changed"]:
            pins["six_e_economics_operator.py"] = "a" * 64
        return pins

    def project(*args):
        result = original_project(*args)
        drift["changed"] = True
        return result

    monkeypatch.setattr(operator, "fingerprints", fingerprints)
    monkeypatch.setattr(economics, "project", project)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_original_request_replaced_during_projection_refuse_success(control, monkeypatch):
    _, pin = prepare(control)
    original_project = economics.project

    def project(*args):
        result = original_project(*args)
        path = control.output / "request.json"
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(economics, "project", project)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_operator_does_not_plan_a_second_time_after_original_verification(control, monkeypatch):
    _, pin = prepare(control)

    def verify(*args):
        proof = control.native_verify(*args)
        monkeypatch.setattr(replay, "build_plan", forbidden)
        return proof

    monkeypatch.setattr(trial, "verify", verify)
    report = operator.inspect(control.root, control.registration, pin)
    assert report["economic_projection"]["supplied_event_count"] == len(control.plan.events)
    assert len(control.calls) == 1


def test_partial_report_write_is_preserved_and_retry_refused(control, monkeypatch):
    _, pin = prepare(control)
    original_open = Path.open

    def partial_open(path, mode="r", *args, **kwargs):
        if path == control.report and mode == "xb":
            with original_open(path, "xb") as stream:
                stream.write(b"partial owned report")
            raise OSError("Synthetic interrupted report creation")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", partial_open)
    with pytest.raises(OSError):
        operator.inspect(control.root, control.registration, pin)
    assert control.report.read_bytes() == b"partial owned report"
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert len(control.calls) == 1
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert snapshot_files(control.root) == before
    assert len(control.calls) == 1


def test_report_fsync_failure_is_not_a_verifiable_success(control, monkeypatch):
    _, pin = prepare(control)
    original_fsync = operator.os.fsync

    def fsync(fd):
        if control.report.exists():
            handle = operator.os.fstat(fd)
            saved = control.report.stat()
            if (handle.st_dev, handle.st_ino) == (saved.st_dev, saved.st_ino):
                raise OSError("Synthetic report sync failure")
        return original_fsync(fd)

    monkeypatch.setattr(operator.os, "fsync", fsync)
    with pytest.raises(OSError):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert control.report.is_file()
    control.calls.clear()
    before = snapshot_files(control.root)
    with pytest.raises(ValueError):
        operator.verify_report(control.root, control.registration, pin, file_pin(control.report))
    assert control.calls == []
    assert snapshot_files(control.root) == before


def test_failure_write_interruption_still_consumes_the_attempt(control, monkeypatch):
    _, pin = prepare(control)
    original_open = Path.open

    def unavailable_failure(path, mode="r", *args, **kwargs):
        if path == control.failure and mode == "xb":
            raise OSError("Synthetic failure evidence path unavailable")
        return original_open(path, mode, *args, **kwargs)

    def failing_verifier(*args):
        control.calls.append(args)
        raise RuntimeError("Synthetic original failure")

    monkeypatch.setattr(Path, "open", unavailable_failure)
    monkeypatch.setattr(trial, "verify", failing_verifier)
    with pytest.raises((OSError, RuntimeError)):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert not control.report.exists()
    assert len(control.calls) == 1
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert len(control.calls) == 1


def test_negative_balance_does_not_stop_or_filter_complete_economic_path(control_factory):
    control = control_factory("unknown")
    seed = economics.EconomicSeed(1, new_seed().initialized_at_ns)
    assumptions = economics.DeclaredEconomics("USD", 125, 2000, 11, None)
    _, pin = prepare(control, seed=seed, assumptions=assumptions)
    projection = operator.inspect(control.root, control.registration, pin)["economic_projection"]
    assert projection["declared_realization_balance_usd_micros"] < 0
    assert projection["realization_balance_shortfall_usd_micros"] > 0
    assert projection["complete_declared_net_return_usd_micros"] is None
    assert len(projection["path"]) == len(control.plan.events)
    assert projection["entry_fees_usd_micros"] == 4000


@pytest.mark.parametrize(
    "artifact", ["registration", "events.jsonl", "receipts.jsonl", "decisions.jsonl", "journal"]
)
@pytest.mark.parametrize("command", ["inspect", "verify"])
def test_post_projection_input_drift_rejects_success(control, monkeypatch, artifact, command):
    _, pin = prepare(control)
    if command == "verify":
        operator.inspect(control.root, control.registration, pin)
        saved_report = control.report.read_bytes()
        saved_attempt = control.attempt.read_bytes()
    original_project = economics.project

    def project(*args):
        result = original_project(*args)
        if artifact == "journal":
            with sqlite3.connect(control.output / "scenario.sqlite") as db:
                db.execute("DROP TRIGGER events_no_delete")
                db.execute("DELETE FROM events WHERE sequence = ?", (len(control.plan.events),))
        else:
            path = control.registration if artifact == "registration" else control.output / artifact
            path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(economics, "project", project)
    with pytest.raises(ValueError):
        if command == "inspect":
            operator.inspect(control.root, control.registration, pin)
        else:
            operator.verify_report(
                control.root, control.registration, pin, file_pin(control.report)
            )
    assert control.attempt.is_file()
    if command == "inspect":
        assert control.failure.is_file()
        assert not control.report.exists()
    else:
        assert control.report.read_bytes() == saved_report
        assert control.attempt.read_bytes() == saved_attempt
        assert not control.failure.exists()


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "scope",
        "status",
        "control_id",
        "control_pin",
        "days",
        "policy",
        "source_missing",
        "source_extra",
        "source_changed",
        "source_trial45",
        "source_replay40",
        "flag_true",
        "flag_integer",
        "flag_missing",
        "flag_extra",
        "seed_bool",
        "seed_time",
        "seed_extra",
        "fees_bool",
        "currency",
        "margin_shape",
        "margin_order",
        "artifact_adoption",
        "artifact_relative",
        "attempt_path",
        "report_collision",
    ],
)
def test_repinned_registration_cannot_change_scope_types_authority_or_paths(control, change):
    value, _ = prepare(control)
    if change in ("version", "scope", "status"):
        value[change] = "another_contract"
    elif change == "control_id":
        value["control_id"] = "other_experiment"
    elif change == "control_pin":
        value["control"]["registration_sha256"] = "a" * 64
    elif change == "days":
        value["control"]["days"] = list(DAYS[:1])
    elif change == "policy":
        value["control"]["policy_id"] = "no_trade"
    elif change == "source_missing":
        value["source_pins"].pop(next(iter(value["source_pins"])))
    elif change == "source_extra":
        value["source_pins"]["extra.py"] = "a" * 64
    elif change == "source_changed":
        value["source_pins"]["six_e_economics_operator.py"] = "a" * 64
    elif change == "source_trial45":
        value["source_pins"] = trial.fingerprints()
    elif change == "source_replay40":
        value["source_pins"] = control.plan.source_pins
    elif change == "flag_true":
        value["flags"]["trading_enabled"] = True
    elif change == "flag_integer":
        value["flags"]["trading_enabled"] = 0
    elif change == "flag_missing":
        value["flags"].pop("risk_approved")
    elif change == "flag_extra":
        value["flags"]["more_authority"] = False
    elif change == "seed_bool":
        value["seed"]["initial_balance_usd_micros"] = True
    elif change == "seed_time":
        value["seed"]["initialized_at_ns"] += 1
    elif change == "seed_extra":
        value["seed"]["funding_confirmed"] = False
    elif change == "fees_bool":
        value["assumptions"]["entry_fee_usd_micros_per_contract"] = True
    elif change == "currency":
        value["assumptions"]["account_currency"] = "EUR"
    elif change == "margin_shape":
        value["assumptions"]["margin"] = {"initial": 5, "maintenance": 3}
    elif change == "margin_order":
        value["assumptions"]["margin"] = {
            "initial_usd_micros_per_contract": 2,
            "maintenance_usd_micros_per_contract": 3,
        }
    elif change == "artifact_adoption":
        value["artifacts"]["registration"] = str(control.root / "logs/elsewhere.json")
    elif change == "artifact_relative":
        value["artifacts"]["report"] = "logs/sensitivity.json"
    elif change == "attempt_path":
        value["artifacts"]["attempt"] = str(control.root / "logs/new_attempt.json")
    else:
        value["artifacts"]["report"] = value["artifacts"]["failure"]
    pin = repin_registration(control, value)
    before = snapshot_files(control.root)
    with pytest.raises((ValueError, TypeError)):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert snapshot_files(control.root) == before


@pytest.mark.parametrize(
    "key",
    [
        "status",
        "request_sha256",
        "completion_sha256",
        "registration_sha256",
        "events",
        "receipts",
        "decisions",
        "sessions",
        "terminal_state",
        "checkpoint",
        "flags",
        "original_coverage",
    ],
)
def test_original_verification_proof_is_bound_completely(control, monkeypatch, key):
    _, pin = prepare(control)

    def verify(*args):
        proof = control.native_verify(*args)
        if key in ("events", "receipts", "decisions", "sessions"):
            proof[key] += 1
        elif key in ("terminal_state", "checkpoint", "flags", "original_coverage"):
            proof[key] = {}
        else:
            proof[key] = "forged_proof"
        return proof

    monkeypatch.setattr(trial, "verify", verify)
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.attempt.is_file()
    assert control.failure.is_file()
    assert not control.report.exists()


def test_cli_prepare_inspect_verify_roundtrip_and_required_assumptions(
    control, monkeypatch, capsys
):
    monkeypatch.chdir(control.root)
    command = [
        "economics",
        "prepare",
        "--control",
        control.control_id,
        "--registration",
        str(control.registration),
        "--report",
        str(control.report),
        "--failure",
        str(control.failure),
        "--initial-balance-usd-micros",
        "1000",
        "--initialized-at-ns",
        str(new_seed().initialized_at_ns),
        "--account-currency",
        "USD",
        "--tick-value-usd-micros",
        "125",
        "--entry-fee-usd-micros-per-contract",
        "8",
        "--exit-fee-usd-micros-per-contract",
        "11",
        "--margin",
        "none",
    ]
    monkeypatch.setattr(sys, "argv", command)
    operator.main()
    prepared = json.loads(capsys.readouterr().out)
    assert prepared["status"] == "registered_declared_economics_not_projected"
    assert control.calls == []
    pin = prepared["registration_sha256"]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "economics",
            "inspect",
            "--registration",
            str(control.registration),
            "--registration-sha256",
            pin,
        ],
    )
    operator.main()
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["report_sha256"] == file_pin(control.report)
    before = snapshot_files(control.root)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "economics",
            "verify",
            "--registration",
            str(control.registration),
            "--registration-sha256",
            pin,
            "--report-sha256",
            file_pin(control.report),
        ],
    )
    operator.main()
    verified = json.loads(capsys.readouterr().out)
    assert verified["status"] == "verified_declared_economics_artifact_not_validation"
    assert snapshot_files(control.root) == before


def test_production_allowlist_is_exact_three_frozen_control_pin_pairs():
    assert set(operator.TRUSTED_CONTROLS) == {"original", "carry", "no_trade"}
    expected = {
        "original": (
            "05e238e2ff0ef62417ad3ba19e946a5ad6bab446a794af4d5a360f366f320eea",
            "b4a94815f4dae2c62f11d72920cb721a5bc0376ca3f4f3a10121dbfadaf4e3d9",
            DAYS[:2],
            "liquidity_follow",
        ),
        "carry": (
            "b47904547b9b2a31fdca997f0e236794a99f4ff3084e83172d9ec9faaccfbe8c",
            "f95d3b50a5fba7c54f5aba40ef0dbc945068362f23a0165716f111aee8ac2ea8",
            DAYS,
            "liquidity_follow",
        ),
        "no_trade": (
            "0fd32bcaf6cafd458ece139091c03c6f00a216a9100098044d873ef09ab5b00b",
            "b4c5a08b57ddb8f1ee900590453900a30d0e7f7b0ab7ef18d6572db79980c54e",
            DAYS,
            "no_trade",
        ),
    }
    for name, control in operator.TRUSTED_CONTROLS.items():
        assert (
            control.registration_sha256,
            control.completion_sha256,
            control.days,
            control.policy_id,
        ) == expected[name]


@pytest.mark.parametrize(
    "missing",
    [
        "--initial-balance-usd-micros",
        "--initialized-at-ns",
        "--account-currency",
        "--tick-value-usd-micros",
        "--entry-fee-usd-micros-per-contract",
        "--exit-fee-usd-micros-per-contract",
        "--margin",
    ],
)
def test_cli_requires_every_declared_assumption_without_defaults(monkeypatch, missing):
    arguments = {
        "--control": "original",
        "--registration": "logs/synthetic_registration.json",
        "--report": "logs/synthetic_report.json",
        "--failure": "logs/synthetic_failure.json",
        "--initial-balance-usd-micros": "1000",
        "--initialized-at-ns": str(new_seed().initialized_at_ns),
        "--account-currency": "USD",
        "--tick-value-usd-micros": "125",
        "--entry-fee-usd-micros-per-contract": "8",
        "--exit-fee-usd-micros-per-contract": "11",
        "--margin": "none",
    }
    del arguments[missing]
    argv = ["economics", "prepare", *[item for pair in arguments.items() for item in pair]]
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(operator, "prepare", forbidden)
    with pytest.raises(SystemExit) as exc:
        operator.main()
    assert exc.value.code == 2


@pytest.mark.parametrize("kind", ["registration", "report"])
def test_oversized_pinned_json_is_rejected_before_historical_access(control, kind):
    _, pin = prepare(control)
    if kind == "report":
        operator.inspect(control.root, control.registration, pin)
        control.calls.clear()
        path = control.report
    else:
        path = control.registration
    path.write_bytes(b" " * (replay.MAX_OUTPUT_BYTES + 1))
    with pytest.raises(ValueError):
        if kind == "registration":
            operator.inspect(control.root, path, file_pin(path))
        else:
            operator.verify_report(control.root, control.registration, pin, file_pin(path))
    assert control.calls == []


@pytest.mark.parametrize("key", ["flags", "protocol", "source_pins", "sidecar_bool"])
def test_original_metadata_strictness_is_checked_even_at_injected_trusted_pins(control, key):
    request_path = control.output / "request.json"
    request = json.loads(request_path.read_bytes())
    if key == "flags":
        request["flags"]["trading_enabled"] = 0
    elif key == "protocol":
        request["protocol"]["execution"] = "wait longer for known late quote"
    elif key == "source_pins":
        request["source_pins"] = trial.fingerprints()
    else:
        request["sidecars"]["events.jsonl"]["bytes"] = True
    request_path.write_bytes(replay._json(request))
    trusted = deepcopy(control.trusted)
    object.__setattr__(trusted, "request_sha256", file_pin(request_path))
    operator.TRUSTED_CONTROLS[control.control_id] = trusted
    with pytest.raises(ValueError):
        prepare(control)
    assert control.calls == []
    assert not control.registration.exists()


@pytest.mark.parametrize("link_type", ["symlink", "junction"])
def test_post_preflight_attempt_path_link_swap_is_refused_before_verifier(
    control, monkeypatch, link_type
):
    _, pin = prepare(control)
    original_paths = operator._paths
    switched = {"active": False}

    def paths(*args, **kwargs):
        result = original_paths(*args, **kwargs)
        if kwargs.get("fresh") == ("report", "failure", "attempt"):
            switched["active"] = True
        return result

    monkeypatch.setattr(operator, "_paths", paths)
    if link_type == "symlink":
        original = Path.is_symlink
        monkeypatch.setattr(
            Path,
            "is_symlink",
            lambda path: (switched["active"] and path == control.attempt) or original(path),
        )
    else:
        original = operator.os.path.isjunction
        monkeypatch.setattr(
            operator.os.path,
            "isjunction",
            lambda path: (switched["active"] and Path(path) == control.attempt) or original(path),
        )
    with pytest.raises(ValueError):
        operator.inspect(control.root, control.registration, pin)
    assert control.calls == []
    assert not control.report.exists()
