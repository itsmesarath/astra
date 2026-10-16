"""Synthetic trial registration, durable replay and read-only verification only."""

import hashlib
import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ai_trader.research import six_e_continuous_trial as t

DAYS = ("2025-03-26", "2025-03-27")
PIN = "a" * 64
POLICY, EXIT_PLAN, SCENARIO = "cvd_follow", "bracket_exit", "synthetic-registered-trial"


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def session(day, *, unknown=False):
    start, _ = t.replay.target.window(day)
    tick = t.replay.target.TICK
    features = dict.fromkeys(t.replay.rules.flow.data.FEATURES, 0.0)
    features.update(log_known_trades_5s=math.log1p(20), normalized_cvd_5s=0.5)
    source = {
        "source_session": day,
        "contract": t.reader.study.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": start,
        "eligible": True,
        "features": features,
        "execution_features": dict.fromkeys(t.replay.rules.flow.FEATURES, 0.0),
        "outcome": object(),
        "hindsight_states": object(),
    }
    quote_values = [(0, 100, 101), (100_000_000, 100, 101)]
    if not unknown:
        quote_values.extend([(200_000_000, 105, 106), (300_000_000, 104, 105)])
    quotes = np.array(
        [(start + offset, bid * tick, ask * tick) for offset, bid, ask in quote_values],
        dtype=np.int64,
    )
    quotes.setflags(write=False)
    return t.replay.ReplaySession(
        day,
        source["contract"],
        PIN,
        (t.replay.decision_input(source, 0),),
        quotes,
    )


@pytest.fixture
def trial(tmp_path, monkeypatch):
    root = tmp_path
    (root / "logs").mkdir()
    build = root / "data/processed/synthetic_original_collection"
    build.mkdir(parents=True)
    origin = root / "logs/synthetic_original_observability.json"
    origin.write_bytes(b'{"synthetic_metadata_only":true}')
    inputs = (session(DAYS[0]), session(DAYS[1]))
    original = {"inputs": {"build": str(build)}}
    frozen = {
        "coverage": {
            "inventory_dates": 471,
            "decision_sessions": 196,
            "rows": 2136770,
            "sessions_by_role": {
                "train": 112,
                "validation_development": 43,
                "test_development": 41,
            },
            "dispositions": {"reserved_metadata_only": 230, "decision_session": 196},
        }
    }
    reads = {"metadata": [], "inputs": []}

    def metadata(project_root, path, original_pin):
        assert project_root == root
        reads["metadata"].append((path, original_pin))
        if path != origin or original_pin != PIN:
            raise ValueError("synthetic original metadata identity differs")
        return original, frozen, {}

    def load_sessions(project_root, path, original_pin, days):
        assert (project_root, path, original_pin) == (root, origin, PIN)
        reads["inputs"].append(days)
        if (
            type(days) is not tuple
            or not 1 <= len(days) <= len(inputs)
            or days != DAYS[: len(days)]
        ):
            raise ValueError("synthetic loader refuses any non-prefix choice")
        return inputs[: len(days)]

    monkeypatch.setattr(t.reader, "metadata", metadata)
    monkeypatch.setattr(t.reader, "load_sessions", load_sessions)
    monkeypatch.setattr(t, "fingerprints", lambda: {"synthetic_trial_sources": "f" * 64})
    return SimpleNamespace(
        root=root,
        build=build,
        origin=origin,
        inputs=inputs,
        original=original,
        frozen=frozen,
        reads=reads,
        registration=root / "logs/synthetic_continuous_trial.json",
        output=root / "data/processed/synthetic_continuous_trial",
    )


def prepare(trial, **changes):
    arguments = {
        "root": trial.root,
        "original_path": trial.origin,
        "original_pin": PIN,
        "days": DAYS,
        "policy": POLICY,
        "exit_plan": EXIT_PLAN,
        "scenario_id": SCENARIO,
        "path": trial.registration,
        "output": trial.output,
    }
    arguments.update(changes)
    value = t.prepare(**arguments)
    return value, pin(trial.registration)


def rewrite_registration(trial, value):
    trial.registration.write_bytes(t.replay._json(value))
    return pin(trial.registration)


def files_snapshot(trial):
    files = [trial.registration, *sorted(trial.output.iterdir())]
    return {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in files}


def test_prepare_freezes_inputs_before_any_simulator_outcome_and_reads_back_same_config(
    trial, monkeypatch
):
    monkeypatch.setattr(
        t.replay, "build_plan", lambda *args: pytest.fail("simulation during prepare")
    )
    value, registration_pin = prepare(trial)
    assert trial.registration.is_file() and not trial.output.exists()
    assert "events" not in value and "receipts" not in value and "terminal_state" not in value
    assert value["source_pins"] == t.fingerprints()
    assert value["manifest"] == t.replay.input_manifest(trial.inputs)
    assert value["original_coverage"] == trial.frozen["coverage"]
    assert value["original_registration"] == {"path": str(trial.origin), "sha256": PIN}
    assert not any(value["flags"].values())
    returned, loaded, config = t.registration(trial.root, trial.registration, registration_pin)
    assert t.replay._json(returned) == t.replay._json(value)
    assert loaded == trial.inputs
    assert config == t.ledger.ScenarioConfig(
        SCENARIO,
        POLICY,
        EXIT_PLAN,
        t.replay.manifest_pin(trial.inputs),
        t.replay.protocol()["version"],
    )
    assert trial.reads["inputs"] == [DAYS, DAYS]


@pytest.mark.parametrize(
    "change",
    [
        {"policy": "hindsight_winner"},
        {"policy": "cpu_cost"},
        {"exit_plan": "instant_target_fill"},
        {"scenario_id": ""},
        {"scenario_id": "bad identifier"},
        {"days": DAYS[1:]},
        {"days": ("2026-01-01",)},
    ],
)
def test_invalid_choice_never_simulates_or_claims_output(trial, monkeypatch, change):
    monkeypatch.setattr(
        t.replay, "build_plan", lambda *args: pytest.fail("simulation after refusal")
    )
    with pytest.raises(ValueError):
        prepare(trial, **change)
    assert not trial.registration.exists() and not trial.output.exists()
    if not {"days"} & change.keys():
        assert not trial.reads["inputs"]


@pytest.mark.parametrize("change", ["registration_scope", "origin_scope", "output_scope", "suffix"])
def test_invalid_paths_fail_before_feature_quote_loading(trial, monkeypatch, change):
    arguments = {
        "registration_scope": {"path": trial.root / "outside.json"},
        "origin_scope": {"original_path": trial.root / "outside.json"},
        "output_scope": {"output": trial.root / "outside-output"},
        "suffix": {"path": trial.registration.with_suffix(".txt")},
    }[change]
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError):
        prepare(trial, **arguments)
    assert not trial.registration.exists() and not trial.output.exists()


@pytest.mark.parametrize("collision", ["registration", "output_file", "output_directory"])
def test_exclusive_collision_does_not_overwrite_or_access_prices(trial, monkeypatch, collision):
    target = trial.registration if collision == "registration" else trial.output
    if collision == "output_directory":
        target.mkdir()
        (target / "retained.txt").write_bytes(b"original user evidence")
    else:
        target.write_bytes(b"original user evidence")
    before = (target / "retained.txt").read_bytes() if target.is_dir() else target.read_bytes()
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="Exclusive"):
        prepare(trial)
    after = (target / "retained.txt").read_bytes() if target.is_dir() else target.read_bytes()
    assert before == after


@pytest.mark.parametrize("scope", ["logs", "data/processed"])
def test_linked_scope_is_refused_before_prices(trial, monkeypatch, scope):
    linked_component = trial.root / scope
    real = t.status.os.path.isjunction
    monkeypatch.setattr(t.status.os.path, "isjunction", lambda p: p == linked_component or real(p))
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="junction"):
        prepare(trial)


def test_output_inside_original_collection_is_refused_before_prices(trial, monkeypatch):
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="original collection"):
        prepare(trial, output=trial.build / "new-subdirectory")
    assert not trial.registration.exists()


def test_registration_source_drift_during_prepare_claims_nothing(trial, monkeypatch):
    fingerprints = iter(({"source": "a" * 64}, {"source": "b" * 64}))
    monkeypatch.setattr(t, "fingerprints", lambda: next(fingerprints))
    with pytest.raises(ValueError, match="source changed"):
        prepare(trial)
    assert not trial.registration.exists() and not trial.output.exists()


def test_original_metadata_refusal_precedes_price_access(trial, monkeypatch):
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="metadata identity"):
        prepare(trial, original_pin="b" * 64)


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "protocol",
        "source",
        "flags",
        "flags_zero",
        "protocol_flag_zero",
        "scope",
        "origin_schema",
        "coverage",
        "original_output",
        "output_scope",
    ],
)
def test_repinned_invalid_registration_refused_before_price_loading(trial, monkeypatch, change):
    prepare(trial)
    value = json.loads(trial.registration.read_bytes())
    if change == "schema":
        value["extra"] = True
    elif change == "protocol":
        value["protocol"]["version"] = "changed"
    elif change == "source":
        value["source_pins"] = {"different_source": "b" * 64}
    elif change == "flags":
        value["flags"]["trading_enabled"] = True
    elif change == "flags_zero":
        value["flags"]["trading_enabled"] = 0
    elif change == "protocol_flag_zero":
        value["protocol"]["flags"]["trading_enabled"] = 0
    elif change == "scope":
        value["scope"] = "invented independent holdout authority"
    elif change == "origin_schema":
        value["original_registration"]["extra"] = True
    elif change == "coverage":
        value["original_coverage"]["decision_sessions"] -= 1
    elif change == "original_output":
        value["output"] = str(trial.build / "forbidden-output")
    else:
        value["output"] = str(trial.root / "outside-output")
    registration_pin = rewrite_registration(trial, value)
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError):
        t.registration(trial.root, trial.registration, registration_pin)


def test_registration_json_suffix_is_required_before_price_loading(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    other = trial.registration.with_suffix(".txt")
    other.write_bytes(trial.registration.read_bytes())
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="JSON registration"):
        t.registration(trial.root, other, registration_pin)


def test_original_registration_pin_detects_any_changed_record_before_prices(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    value = json.loads(trial.registration.read_bytes())
    value["config"]["policy_id"] = "no_trade"
    rewrite_registration(trial, value)
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="pin"):
        t.registration(trial.root, trial.registration, registration_pin)


@pytest.mark.parametrize(
    "field,value",
    [
        ("policy_id", "cpu_cost"),
        ("exit_plan", "invented_fill"),
        ("max_position_contracts", 2),
        ("extra_round_trip_ticks_per_contract", 2),
        ("source_manifest_sha256", "b" * 64),
        ("simulator_version", "changed-simulator"),
    ],
)
def test_repinned_wrong_scenario_parameters_refused(trial, field, value):
    prepare(trial)
    registered = json.loads(trial.registration.read_bytes())
    registered["config"][field] = value
    registration_pin = rewrite_registration(trial, registered)
    with pytest.raises(ValueError):
        t.registration(trial.root, trial.registration, registration_pin)


def test_manifest_change_and_changed_loaded_source_refuse_run_without_output(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    altered = (replace(trial.inputs[0], source_sha256="b" * 64), trial.inputs[1])
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: altered)
    with pytest.raises(ValueError, match="inputs"):
        t.run(trial.root, trial.registration, registration_pin)
    assert not trial.output.exists()


def test_repinned_manifest_cannot_replace_registered_input_content(trial):
    prepare(trial)
    value = json.loads(trial.registration.read_bytes())
    value["manifest"]["sessions"][0]["decisions_sha256"] = "b" * 64
    registration_pin = rewrite_registration(trial, value)
    with pytest.raises(ValueError, match="inputs"):
        t.registration(trial.root, trial.registration, registration_pin)


def test_changed_current_implementation_refused_before_prices(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    monkeypatch.setattr(t, "fingerprints", lambda: {"changed": "b" * 64})
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: pytest.fail("prices accessed"))
    with pytest.raises(ValueError, match="source"):
        t.run(trial.root, trial.registration, registration_pin)
    assert not trial.output.exists()


def test_run_writes_complete_verified_artifacts_once_and_explicit_repeat_preserves_them(
    trial, monkeypatch
):
    value, registration_pin = prepare(trial)
    writes, real_write = [], t.replay.write_plan

    def write_plan(plan, output):
        writes.append(output)
        return real_write(plan, output)

    monkeypatch.setattr(t.replay, "write_plan", write_plan)
    result = t.run(trial.root, trial.registration, registration_pin)
    assert writes == [trial.output]
    assert result["status"] == "verified_continuous_quote_simulation_not_validation"
    assert result["registration_sha256"] == registration_pin
    assert result["original_coverage"] == value["original_coverage"]
    assert not any(result["flags"].values())
    assert {path.name for path in trial.output.iterdir()} == {
        "request.json",
        "events.jsonl",
        "receipts.jsonl",
        "decisions.jsonl",
        "scenario.sqlite",
        "completion.json",
        "verification.json",
    }
    assert json.loads((trial.output / "verification.json").read_bytes()) == result
    completion = json.loads((trial.output / "completion.json").read_bytes())
    assert completion["complete_simulated_net_contract_ticks"] == 4
    assert len(completion["sessions"]) == len(DAYS)
    before = files_snapshot(trial)
    with pytest.raises(FileExistsError):
        t.run(trial.root, trial.registration, registration_pin)
    assert writes == [trial.output, trial.output]
    assert files_snapshot(trial) == before


def test_verify_is_read_only_and_checks_complete_registered_inputs(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    expected = t.run(trial.root, trial.registration, registration_pin)
    completion_pin = pin(trial.output / "completion.json")
    before = files_snapshot(trial)
    monkeypatch.setattr(t.replay, "_write", lambda *args: pytest.fail("verify wrote evidence"))
    monkeypatch.setattr(t.replay, "write_plan", lambda *args: pytest.fail("verify reran a writer"))
    monkeypatch.setattr(
        t.ledger.ScenarioLedger, "create", lambda *args: pytest.fail("verify created")
    )
    assert t.verify(trial.root, trial.registration, registration_pin, completion_pin) == expected
    assert files_snapshot(trial) == before
    with pytest.raises(ValueError):
        t.verify(trial.root, trial.registration, registration_pin, "b" * 64)
    assert files_snapshot(trial) == before


def test_unknown_carried_terminal_account_still_verifies_with_incomplete_total(trial, monkeypatch):
    inputs = (session(DAYS[0], unknown=True), trial.inputs[1])
    monkeypatch.setattr(t.reader, "load_sessions", lambda *args: inputs)
    _, registration_pin = prepare(trial)
    result = t.run(trial.root, trial.registration, registration_pin)
    completion = json.loads((trial.output / "completion.json").read_bytes())
    assert result["status"] == "verified_continuous_quote_simulation_not_validation"
    assert completion["complete_simulated_net_contract_ticks"] is None
    assert completion["terminal_state"]["position"]["entry_source_session"] == DAYS[0]
    assert completion["terminal_state"]["reservation"]["status"] == "UNKNOWN"


@pytest.mark.parametrize(
    "exception", [ValueError("synthetic verification failure"), KeyboardInterrupt()]
)
def test_post_write_verification_failure_remains_and_forbids_successful_verification(
    trial, monkeypatch, exception
):
    _, registration_pin = prepare(trial)
    real_verify = t.verify

    def fail(*args):
        raise exception

    monkeypatch.setattr(t, "verify", fail)
    with pytest.raises(type(exception)):
        t.run(trial.root, trial.registration, registration_pin)
    failure_path = trial.output / "failure.json"
    failure = json.loads(failure_path.read_bytes())
    assert failure["status"] == "failed_terminal_continuous_trial_verification"
    assert failure["exception_type"] == type(exception).__name__
    assert not any(failure["flags"].values())
    assert (trial.output / "completion.json").exists()
    assert (trial.output / "scenario.sqlite").exists()
    assert not (trial.output / "verification.json").exists()
    before = files_snapshot(trial)
    monkeypatch.setattr(t, "verify", real_verify)
    with pytest.raises(ValueError, match="Failure evidence"):
        t.verify(
            trial.root, trial.registration, registration_pin, pin(trial.output / "completion.json")
        )
    with pytest.raises(FileExistsError):
        t.run(trial.root, trial.registration, registration_pin)
    assert files_snapshot(trial) == before


def test_terminal_trial_deadline_failure_retains_complete_written_evidence(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    times = iter((0.0, 0.0, 0.0, t.replay.MAX_SECONDS + 1.0))
    monkeypatch.setattr(t, "time", SimpleNamespace(monotonic=lambda: next(times)))
    with pytest.raises(TimeoutError, match="trial deadline"):
        t.run(trial.root, trial.registration, registration_pin)
    assert (trial.output / "completion.json").exists()
    failure = json.loads((trial.output / "failure.json").read_bytes())
    assert failure["exception_type"] == "TimeoutError"
    assert not (trial.output / "verification.json").exists()


def test_request_leaf_link_is_refused_before_hashing_or_verification_writes(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    t.run(trial.root, trial.registration, registration_pin)
    completion_pin = pin(trial.output / "completion.json")
    before = files_snapshot(trial)
    request_path = trial.output / "request.json"
    real_junction = t.status.os.path.isjunction
    real_hash = t.reader.study.common.hash_file
    monkeypatch.setattr(
        t.status.os.path, "isjunction", lambda p: p == request_path or real_junction(p)
    )

    def hash_file(path, bound):
        if path == request_path:
            pytest.fail("linked request was opened for hashing")
        return real_hash(path, bound)

    monkeypatch.setattr(t.reader.study.common, "hash_file", hash_file)
    with pytest.raises(ValueError, match="junction"):
        t.verify(trial.root, trial.registration, registration_pin, completion_pin)
    assert files_snapshot(trial) == before


def test_completion_leaf_link_failure_is_retained_before_any_hash_read(trial, monkeypatch):
    _, registration_pin = prepare(trial)
    completion_path = trial.output / "completion.json"
    real_junction = t.status.os.path.isjunction
    real_hash = t.reader.study.common.hash_file
    monkeypatch.setattr(
        t.status.os.path, "isjunction", lambda p: p == completion_path or real_junction(p)
    )

    def hash_file(path, bound):
        if path == completion_path:
            pytest.fail("linked completion was opened for hashing")
        return real_hash(path, bound)

    monkeypatch.setattr(t.reader.study.common, "hash_file", hash_file)
    with pytest.raises(ValueError, match="junction"):
        t.run(trial.root, trial.registration, registration_pin)
    assert completion_path.exists()
    failure = json.loads((trial.output / "failure.json").read_bytes())
    assert failure["exception_type"] == "ValueError"
    assert "junction" in failure["reason"]
    assert not (trial.output / "verification.json").exists()


@pytest.mark.parametrize("command", ["prepare", "run", "verify"])
def test_cli_dispatches_explicit_arguments_without_loading_history(
    trial, monkeypatch, capsys, command
):
    monkeypatch.chdir(trial.root)
    calls = []

    def prepare_cli(*args):
        calls.append(args)
        args[-2].write_bytes(b"{}")

    def dispatch(*args):
        calls.append(args)
        return {"status": f"synthetic_{command}"}

    monkeypatch.setattr(t, "prepare", prepare_cli)
    monkeypatch.setattr(t, "run", dispatch)
    monkeypatch.setattr(t, "verify", dispatch)
    arguments = [
        "six_e_continuous_trial",
        command,
        "--registration",
        str(trial.registration),
    ]
    if command == "prepare":
        arguments.extend(
            [
                "--original-registration",
                str(trial.origin),
                "--original-sha256",
                PIN,
                "--days",
                *DAYS,
                "--policy",
                POLICY,
                "--exit-plan",
                EXIT_PLAN,
                "--scenario-id",
                SCENARIO,
                "--output",
                str(trial.output),
            ]
        )
        expected = (
            trial.root,
            trial.origin,
            PIN,
            DAYS,
            POLICY,
            EXIT_PLAN,
            SCENARIO,
            trial.registration,
            trial.output,
        )
    else:
        arguments.extend(["--registration-sha256", PIN])
        expected = (trial.root, trial.registration, PIN)
        if command == "verify":
            arguments.extend(["--completion-sha256", "b" * 64])
            expected += ("b" * 64,)
    monkeypatch.setattr(sys, "argv", arguments)
    t.main()
    assert calls == [expected]
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == (
        "registered_continuous_trial_not_run" if command == "prepare" else f"synthetic_{command}"
    )
    if command == "prepare":
        assert result["registration_sha256"] == pin(trial.registration)


def test_cli_verify_requires_completion_pin_before_dispatch(trial, monkeypatch):
    monkeypatch.setattr(t, "verify", lambda *args: pytest.fail("verify dispatched without pin"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "six_e_continuous_trial",
            "verify",
            "--registration",
            str(trial.registration),
            "--registration-sha256",
            PIN,
        ],
    )
    with pytest.raises(SystemExit) as error:
        t.main()
    assert error.value.code == 2


def test_cli_prepare_rejects_hindsight_policy_before_dispatch(trial, monkeypatch):
    monkeypatch.setattr(t, "prepare", lambda *args: pytest.fail("unsupported prepare dispatched"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "six_e_continuous_trial",
            "prepare",
            "--original-registration",
            str(trial.origin),
            "--original-sha256",
            PIN,
            "--days",
            *DAYS,
            "--policy",
            "hindsight_winner",
            "--exit-plan",
            EXIT_PLAN,
            "--scenario-id",
            SCENARIO,
            "--registration",
            str(trial.registration),
            "--output",
            str(trial.output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        t.main()
    assert error.value.code == 2
    assert not trial.registration.exists() and not trial.output.exists()


def test_actual_wrapper_fingerprints_include_every_new_module_and_original_source():
    pins = t.fingerprints()
    for module in (t, t.reader, t.replay):
        path = Path(module.__file__)
        assert pins[path.name] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert set(t.reader.obs.fingerprints()) <= set(pins)
