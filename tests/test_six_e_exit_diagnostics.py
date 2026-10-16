"""Synthetic exit-availability diagnostics; no historical data, models or feeds."""

import hashlib
import json
import math
import sys
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from ai_trader.research import six_e_continuous_replay as replay
from ai_trader.research import six_e_continuous_trial as trial
from ai_trader.research import six_e_exit_diagnostics as diagnostics

DAY, NEXT_DAY = "2025-03-26", "2025-03-27"
SECOND, TICK = replay.target.SECOND, replay.target.TICK
MS = SECOND // 1000
PIN = "a" * 64
VERSION = "six_e_exit_quote_diagnostics_v1"
SCOPE = "posthoc_exposed_development_not_validation"
REFERENCE_KEYS = {
    "source_session",
    "contract",
    "native_cursor",
    "quote_at_ns",
    "bid_nano",
    "ask_nano",
    "spread_ticks",
}


def file_pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(quotes, decisions=((0, 0, 1),), day=DAY):
    start, _ = replay.target.window(day)
    contract = replay.study.census.dated_contract(day)
    rows = []
    for offset, cursor, direction in decisions:
        features = dict.fromkeys(replay.rules.flow.data.FEATURES, 0.0)
        features.update(log_known_trades_5s=math.log1p(20), normalized_cvd_5s=direction * 0.5)
        row = {
            "source_session": day,
            "contract": contract,
            "partition": "development",
            "decision_ts_ns": start + offset,
            "eligible": True,
            "features": features,
            "execution_features": dict.fromkeys(replay.rules.flow.FEATURES, 0.0),
            "outcomes": object(),
            "hindsight_states": object(),
            "net_ticks": object(),
        }
        rows.append(replay.decision_input(row, cursor))
    native = np.asarray(
        [(start + offset, bid * TICK, ask * TICK) for offset, bid, ask in quotes],
        dtype=np.int64,
    ).reshape((-1, 3))
    native.setflags(write=False)
    return replay.ReplaySession(day, contract, PIN, tuple(rows), native)


def plan_for(inputs, **changes):
    if isinstance(inputs, replay.ReplaySession):
        inputs = (inputs,)
    config = replay.ledger.ScenarioConfig(
        "synthetic-exit-diagnostics",
        "cvd_follow",
        "bracket_exit",
        replay.manifest_pin(inputs),
        replay.protocol()["version"],
    )
    return replay.build_plan(inputs, replace(config, **changes))


def closed_source(day=DAY):
    return source(
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (300 * MS, 104, 105)],
        day=day,
    )


def unknown_source(day=DAY):
    return source(
        [(0, 100, 101), (100 * MS, 100, 101), (14 * SECOND, 100, 101), (18 * SECOND, 110, 111)],
        day=day,
    )


def single_exit(plan):
    report = diagnostics.describe_exits(plan)
    assert len(report["exits"]) == 1
    return report, report["exits"][0]


def assert_reference(ref, session, cursor):
    assert set(ref) == REFERENCE_KEYS
    assert ref["source_session"] == session.source_session
    assert ref["contract"] == session.contract
    assert ref["native_cursor"] == cursor
    timestamp, bid, ask = map(int, session.quotes[cursor])
    assert ref["quote_at_ns"] == timestamp
    assert ref["bid_nano"] == bid
    assert ref["ask_nano"] == ask
    assert ref["spread_ticks"] == (ask - bid) // TICK


def test_describes_complete_inputs_and_preserves_exact_terminal_account():
    inputs = (closed_source(), unknown_source(NEXT_DAY))
    plan = plan_for(inputs)
    report = diagnostics.describe_exits(plan)
    assert report["version"] == VERSION
    assert report["scope"] == SCOPE
    assert report["complete_inputs"] == {
        "sessions": 2,
        "decisions": 2,
        "quotes": 8,
        "exit_intents": 2,
    }
    assert len(report["exits"]) == 2
    assert report["terminal_state"] == asdict(plan.terminal_state)
    assert report["complete_simulated_net_contract_ticks"] is None
    assert report["terminal_state"]["reservation"]["status"] == "UNKNOWN"
    assert report["flags"] == replay._flags()
    assert not any(report["flags"].values())


def test_all_exits_include_both_positive_and_negative_closed_positions():
    inputs = source(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (11 * SECOND, 100, 101),
            (11 * SECOND + 100 * MS, 100, 101),
            (11 * SECOND + 200 * MS, 99, 100),
            (11 * SECOND + 300 * MS, 98, 99),
        ],
        decisions=((0, 0, 1), (11 * SECOND, 4, 1)),
    )
    plan = plan_for(inputs)
    report = diagnostics.describe_exits(plan)
    assert report["complete_inputs"]["exit_intents"] == 2
    assert [record["position_id"] for record in report["exits"]] == [
        "position-1",
        "position-2",
    ]
    assert all(record["resolution"] == "filled_first_candidate" for record in report["exits"])
    assert [record["exit_fill"]["price_nano"] for record in report["exits"]] == [
        104 * TICK,
        98 * TICK,
    ]
    assert report["complete_simulated_net_contract_ticks"] == -2


def test_empty_window_explains_quote_gap_without_filling_a_later_good_quote():
    inputs = unknown_source()
    plan = plan_for(inputs)
    original_state = asdict(plan.terminal_state)
    report, record = single_exit(plan)
    start = replay.target.window(DAY)[0]
    assert record["requested_at_ns"] == start + 15 * SECOND + 100 * MS
    assert record["ready_at_ns"] == start + 15 * SECOND + 200 * MS
    assert record["deadline_at_ns"] == start + 16 * SECOND + 200 * MS
    assert record["trigger"] == "hold_timer"
    assert_reference(record["intent_reference"], inputs, 2)
    assert_reference(record["before_ready_reference"], inputs, 2)
    assert record["candidate_count"] == 0
    assert record["first_candidate"] is None
    assert_reference(record["after_deadline_reference"], inputs, 3)
    assert record["observed_gap_ns"] == 4 * SECOND
    assert record["late_after_deadline_ns"] == SECOND + 800 * MS
    assert record["resolution"] == "unknown_empty_window"
    assert record["exit_fill"] is None
    assert record["unresolved_at_ns"] == record["deadline_at_ns"]
    assert report["complete_simulated_net_contract_ticks"] is None
    assert report["terminal_state"] == original_state == asdict(plan.terminal_state)


def test_nanosecond_gap_fixture_matches_the_diagnosed_timeline():
    entry = 268_743_178_638
    previous = 281_845_689_921
    following = 286_381_589_056
    inputs = source(
        [
            (entry - 100 * MS, 100, 101),
            (entry, 100, 101),
            (previous, 100, 101),
            (following, 110, 111),
        ],
        decisions=((entry - 100 * MS, 0, 1),),
    )
    _, record = single_exit(plan_for(inputs))
    start = replay.target.window(DAY)[0]
    assert record["requested_at_ns"] == start + 283_743_178_638
    assert record["ready_at_ns"] == start + 283_843_178_638
    assert record["deadline_at_ns"] == start + 284_843_178_638
    assert record["candidate_count"] == 0
    assert record["observed_gap_ns"] == 4_535_899_135
    assert record["late_after_deadline_ns"] == 1_538_410_418
    assert record["resolution"] == "unknown_empty_window"


@pytest.mark.parametrize("candidate_at", [300 * MS, 1300 * MS])
def test_exit_candidates_at_ready_or_exact_deadline_are_inclusive(candidate_at):
    inputs = source(
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (candidate_at, 104, 105)]
    )
    _, record = single_exit(plan_for(inputs))
    assert record["candidate_count"] == 1
    assert record["resolution"] == "filled_first_candidate"
    assert record["unresolved_at_ns"] is None
    assert record["after_deadline_reference"] is None
    assert_reference(record["first_candidate"], inputs, 3)
    assert record["exit_fill"]["native_cursor"] == 3


def test_one_nanosecond_after_deadline_is_descriptive_and_cannot_fill():
    inputs = source(
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (1300 * MS + 1, 104, 105)]
    )
    report, record = single_exit(plan_for(inputs))
    assert record["candidate_count"] == 0
    assert record["first_candidate"] is None
    assert record["exit_fill"] is None
    assert record["late_after_deadline_ns"] == 1
    assert record["resolution"] == "unknown_empty_window"
    assert report["complete_simulated_net_contract_ticks"] is None
    assert_reference(record["after_deadline_reference"], inputs, 3)


def test_equal_time_candidates_keep_first_native_cursor_and_full_count():
    inputs = source(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 105, 106),
            (300 * MS, 104, 105),
            (300 * MS, 102, 103),
        ]
    )
    _, record = single_exit(plan_for(inputs))
    assert record["candidate_count"] == 2
    assert_reference(record["first_candidate"], inputs, 3)
    assert record["exit_fill"]["native_cursor"] == 3
    assert record["exit_fill"]["price_nano"] == 104 * TICK


@pytest.mark.parametrize("direction", [1, -1])
def test_bracket_intent_uses_first_threshold_native_cursor_not_equal_time_suffix(direction):
    attack = (105, 106) if direction > 0 else (95, 96)
    suffix = (106, 107) if direction > 0 else (94, 95)
    inputs = source(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (200 * MS, 100, 101),
            (200 * MS, *attack),
            (200 * MS, *suffix),
            (300 * MS, *attack),
        ],
        decisions=((0, 0, direction),),
    )
    _, record = single_exit(plan_for(inputs))
    assert record["trigger"] == "bracket_quote"
    assert_reference(record["intent_reference"], inputs, 3)
    assert_reference(record["before_ready_reference"], inputs, 4)
    assert_reference(record["first_candidate"], inputs, 5)
    assert record["side"] == ("long" if direction > 0 else "short")


def test_hold_timer_wins_equal_time_threshold_quote_and_uses_prior_published_prefix():
    inputs = source(
        [
            (0, 100, 101),
            (100 * MS, 100, 101),
            (15 * SECOND + 100 * MS, 105, 106),
            (15 * SECOND + 200 * MS, 104, 105),
        ]
    )
    _, record = single_exit(plan_for(inputs))
    assert record["trigger"] == "hold_timer"
    assert_reference(record["intent_reference"], inputs, 1)
    assert_reference(record["before_ready_reference"], inputs, 2)
    assert_reference(record["first_candidate"], inputs, 3)


def test_widened_exit_remains_first_candidate_and_retains_crossing_price():
    inputs = source(
        [(0, 100, 101), (100 * MS, 100, 101), (200 * MS, 105, 106), (300 * MS, 103, 108)]
    )
    _, record = single_exit(plan_for(inputs))
    assert record["resolution"] == "filled_first_candidate"
    assert record["candidate_count"] == 1
    assert record["first_candidate"]["spread_ticks"] == 5
    assert record["exit_fill"]["price_nano"] == 103 * TICK


def test_no_later_quote_is_censored_coverage_and_leaves_unknown_inventory():
    inputs = source([(0, 100, 101), (100 * MS, 100, 101)])
    report, record = single_exit(plan_for(inputs))
    assert record["candidate_count"] == 0
    assert record["after_deadline_reference"] is None
    assert record["observed_gap_ns"] is None
    assert record["late_after_deadline_ns"] is None
    assert record["resolution"] == "unknown_empty_window"
    assert report["terminal_state"]["position"]["remaining_contracts"] == 1


def test_carried_unknown_cannot_use_next_contract_quotes_as_exit_candidates():
    first = source([(0, 100, 101), (100 * MS, 100, 101)], day="2025-06-06")
    second = closed_source(day="2025-06-09")
    assert first.contract != second.contract
    report, record = single_exit(plan_for((first, second)))
    assert report["complete_inputs"]["sessions"] == 2
    assert record["contract"] == first.contract
    assert record["candidate_count"] == 0
    assert record["after_deadline_reference"] is None
    assert report["terminal_state"]["position"]["contract"] == first.contract
    assert report["terminal_state"]["reservation"]["status"] == "UNKNOWN"


def test_no_trade_retains_complete_inputs_and_has_no_exit_requests():
    inputs = closed_source()
    plan = plan_for(inputs, policy_id="no_trade")
    report = diagnostics.describe_exits(plan)
    assert report["complete_inputs"] == {
        "sessions": 1,
        "decisions": 1,
        "quotes": 4,
        "exit_intents": 0,
    }
    assert report["exits"] == []
    assert report["complete_simulated_net_contract_ticks"] == 0
    assert report["terminal_state"] == asdict(plan.terminal_state)


@pytest.mark.parametrize("field", ["events", "receipts", "decisions", "terminal_state"])
def test_modified_plan_is_refused_instead_of_describing_a_successful_subset(field):
    plan = plan_for(closed_source())
    if field == "terminal_state":
        changed = replace(plan.terminal_state, closed_net_contract_ticks=100)
    else:
        changed = getattr(plan, field)[:-1]
    with pytest.raises(ValueError):
        diagnostics.describe_exits(replace(plan, **{field: changed}))


def test_returned_flags_and_descriptors_cannot_mutate_later_reports_or_plan():
    plan = plan_for(closed_source())
    first = diagnostics.describe_exits(plan)
    original_state = deepcopy(first["terminal_state"])
    first["flags"]["trading_enabled"] = True
    first["exits"][0]["first_candidate"]["bid_nano"] = 999 * TICK
    first["terminal_state"]["closed_positions"] = 999
    second = diagnostics.describe_exits(plan)
    assert second["flags"] == replay._flags()
    assert second["terminal_state"] == original_state == asdict(plan.terminal_state)
    assert second["exits"][0]["first_candidate"]["bid_nano"] == 104 * TICK


@pytest.fixture
def registered(tmp_path, monkeypatch):
    root = tmp_path
    (root / "logs").mkdir()
    build = root / "data/processed/synthetic_original"
    build.mkdir(parents=True)
    origin = root / "logs/synthetic_original.json"
    origin.write_bytes(b'{"synthetic_metadata_only":true}')
    inputs = (closed_source(), unknown_source(NEXT_DAY))
    original = {"inputs": {"build": str(build)}}
    frozen = {"coverage": {"decision_sessions": 196, "reserved_metadata_only": 230}}

    def metadata(project_root, path, pin):
        assert (project_root, path, pin) == (root, origin, PIN)
        return original, frozen, {}

    def load_sessions(project_root, path, pin, days):
        assert (project_root, path, pin) == (root, origin, PIN)
        assert days == (DAY, NEXT_DAY)
        return inputs

    monkeypatch.setattr(trial.reader, "metadata", metadata)
    monkeypatch.setattr(trial.reader, "load_sessions", load_sessions)
    registration = root / "logs/synthetic_trial.json"
    output = root / "data/processed/synthetic_trial"
    trial.prepare(
        root,
        origin,
        PIN,
        (DAY, NEXT_DAY),
        "cvd_follow",
        "bracket_exit",
        "synthetic-registered-exit-diagnostics",
        registration,
        output,
    )
    registration_pin = file_pin(registration)
    trial.run(root, registration, registration_pin)
    return SimpleNamespace(
        root=root,
        registration=registration,
        registration_pin=registration_pin,
        output=output,
        completion_pin=file_pin(output / "completion.json"),
    )


def snapshot_files(root):
    return {
        path: (path.read_bytes(), path.stat().st_mtime_ns)
        for path in root.rglob("*")
        if path.is_file()
    }


def inspect_registered(registered):
    return diagnostics.inspect(
        registered.root,
        registered.registration,
        registered.registration_pin,
        registered.completion_pin,
    )


def test_inspect_verifies_full_registered_trial_and_leaves_every_source_file_unchanged(registered):
    before = snapshot_files(registered.root)
    report = inspect_registered(registered)
    assert snapshot_files(registered.root) == before
    assert report["complete_inputs"]["exit_intents"] == 2
    assert report["complete_inputs"]["decisions"] == 2
    assert report["complete_simulated_net_contract_ticks"] is None
    assert report["source_pins"] == diagnostics.fingerprints()
    assert "six_e_exit_diagnostics.py" in report["source_pins"]
    assert report["source_pins"].items() >= trial.fingerprints().items()


@pytest.mark.parametrize("which", ["registration", "completion"])
@pytest.mark.parametrize("bad_pin", [True, "b" * 64, "A" * 64, "short"])
def test_inspect_rejects_wrong_or_boolean_required_evidence_pins(registered, which, bad_pin):
    before = snapshot_files(registered.root)
    registration_pin = bad_pin if which == "registration" else registered.registration_pin
    completion_pin = bad_pin if which == "completion" else registered.completion_pin
    with pytest.raises(ValueError):
        diagnostics.inspect(
            registered.root, registered.registration, registration_pin, completion_pin
        )
    assert snapshot_files(registered.root) == before


def test_inspect_refuses_linked_registration_without_adopting_its_contents(registered):
    link = registered.root / "logs/linked_registration.json"
    try:
        link.symlink_to(registered.registration)
    except OSError:
        pytest.skip("Creating Windows symlinks requires unavailable local privileges")
    with pytest.raises(ValueError):
        diagnostics.inspect(
            registered.root, link, registered.registration_pin, registered.completion_pin
        )


@pytest.mark.parametrize("name", ["events.jsonl", "receipts.jsonl", "decisions.jsonl"])
def test_inspect_cannot_accept_a_modified_complete_sidecar(registered, name):
    path = registered.output / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError):
        inspect_registered(registered)


def test_inspect_refuses_source_drift_between_entry_and_terminal_verification(
    registered, monkeypatch
):
    original = diagnostics.fingerprints
    calls = 0

    def changed():
        nonlocal calls
        calls += 1
        values = original()
        if calls > 1:
            values["six_e_exit_diagnostics.py"] = "b" * 64
        return values

    monkeypatch.setattr(diagnostics, "fingerprints", changed)
    with pytest.raises(ValueError):
        inspect_registered(registered)


def cli_args(registered, output=None):
    args = [
        "six_e_exit_diagnostics",
        "inspect",
        "--registration",
        str(registered.registration),
        "--registration-sha256",
        registered.registration_pin,
        "--completion-sha256",
        registered.completion_pin,
    ]
    if output is not None:
        args.extend(["--output", str(output)])
    return args


def test_cli_inspect_prints_complete_report_without_writing_files(registered, monkeypatch, capsys):
    before = snapshot_files(registered.root)
    monkeypatch.chdir(registered.root)
    monkeypatch.setattr(sys, "argv", cli_args(registered))
    diagnostics.main()
    report = json.loads(capsys.readouterr().out)
    assert report["version"] == VERSION
    assert report["complete_inputs"]["exit_intents"] == 2
    assert snapshot_files(registered.root) == before


def test_cli_optional_fresh_log_is_exact_report_and_does_not_modify_trial(
    registered, monkeypatch, capsys
):
    before = snapshot_files(registered.root)
    output = registered.root / "logs/synthetic_exit_diagnostics.json"
    monkeypatch.chdir(registered.root)
    monkeypatch.setattr(sys, "argv", cli_args(registered, output))
    diagnostics.main()
    printed = json.loads(capsys.readouterr().out)
    stored = json.loads(output.read_bytes())
    assert stored["version"] == VERSION
    assert stored["status"] == printed["status"]
    assert stored["complete_inputs"] == printed["complete_inputs"]
    assert printed["report_sha256"] == file_pin(output)
    assert printed["flags"] == stored["flags"] == replay._flags()
    after = snapshot_files(registered.root)
    assert set(after) - set(before) == {output}
    assert {path: contents for path, contents in after.items() if path != output} == before


@pytest.mark.parametrize("relative", ["logs/existing.json", "data/processed/diagnostics.json"])
def test_cli_output_refuses_existing_or_non_log_target_without_modifying_it(
    registered, monkeypatch, relative
):
    output = registered.root / relative
    if relative.startswith("logs"):
        output.write_bytes(b"existing-output-must-stay")
    before = snapshot_files(registered.root)
    monkeypatch.chdir(registered.root)
    monkeypatch.setattr(sys, "argv", cli_args(registered, output))
    with pytest.raises((ValueError, FileExistsError)):
        diagnostics.main()
    assert snapshot_files(registered.root) == before


def test_cli_inspect_requires_completion_pin_before_any_history_dispatch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Incomplete CLI must not inspect historical data")

    monkeypatch.setattr(diagnostics, "inspect", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "six_e_exit_diagnostics",
            "inspect",
            "--registration",
            "logs/synthetic.json",
            "--registration-sha256",
            PIN,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        diagnostics.main()
    assert exc.value.code == 2


def test_cli_help_starts_no_data_or_model_work(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Help must not inspect historical data")

    monkeypatch.setattr(diagnostics, "inspect", forbidden)
    monkeypatch.setattr(sys, "argv", ["six_e_exit_diagnostics", "inspect", "--help"])
    with pytest.raises(SystemExit) as exc:
        diagnostics.main()
    assert exc.value.code == 0


def test_source_pins_include_existing_trial_pins_and_only_the_new_diagnostic_module():
    pins = diagnostics.fingerprints()
    original = trial.fingerprints()
    assert pins.items() >= original.items()
    assert set(pins) - set(original) == {"six_e_exit_diagnostics.py"}
    assert pins["six_e_exit_diagnostics.py"] == file_pin(Path(diagnostics.__file__))


def saved_report(registered):
    report = inspect_registered(registered)
    path = registered.root / "logs/synthetic_saved_diagnostic.json"
    diagnostics.write_report(registered.root, path, report)
    return path, file_pin(path), report


def verify_saved(registered, path, pin):
    return diagnostics.verify_report(
        registered.root,
        registered.registration,
        registered.registration_pin,
        registered.completion_pin,
        path,
        pin,
    )


def test_saved_diagnostic_verifier_reconstructs_complete_report_read_only(registered):
    path, pin, report = saved_report(registered)
    before = snapshot_files(registered.root)
    result = verify_saved(registered, path, pin)
    assert result["status"] == "verified_all_exit_diagnostic_artifact_not_reconciliation"
    assert result["report_sha256"] == pin
    assert result["complete_inputs"] == report["complete_inputs"]
    assert result["terminal_tip_sha256"] == report["terminal_state"]["tip_sha256"]
    assert result["flags"] == replay._flags()
    assert snapshot_files(registered.root) == before


@pytest.mark.parametrize(
    "change",
    [
        "drop_exit",
        "extra_exit",
        "quote_price",
        "candidate_count",
        "candidate_bool",
        "terminal_state",
        "flags",
        "source_pins",
        "noncanonical",
    ],
)
def test_repinned_modified_diagnostic_cannot_be_verified_as_original_result(registered, change):
    path, _, report = saved_report(registered)
    if change == "drop_exit":
        report["exits"] = report["exits"][:-1]
    elif change == "extra_exit":
        report["exits"].append(deepcopy(report["exits"][-1]))
    elif change == "quote_price":
        report["exits"][0]["first_candidate"]["bid_nano"] += TICK
    elif change == "candidate_count":
        report["exits"][0]["candidate_count"] += 1
    elif change == "candidate_bool":
        assert report["exits"][1]["candidate_count"] == 0
        report["exits"][1]["candidate_count"] = False
    elif change == "terminal_state":
        report["terminal_state"]["closed_net_contract_ticks"] += 1
    elif change == "flags":
        report["flags"]["trading_enabled"] = True
    elif change == "source_pins":
        report["source_pins"]["six_e_exit_diagnostics.py"] = "b" * 64
    raw = (
        json.dumps(report, indent=2).encode() if change == "noncanonical" else replay._json(report)
    )
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        verify_saved(registered, path, file_pin(path))


@pytest.mark.parametrize("bad_pin", [True, "b" * 64, "A" * 64])
def test_diagnostic_verifier_requires_exact_nonboolean_report_pin(registered, bad_pin):
    path, _, _ = saved_report(registered)
    with pytest.raises(ValueError):
        verify_saved(registered, path, bad_pin)


def test_cli_verify_requires_report_pin_before_dispatch(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Incomplete CLI must not inspect diagnostic or historical data")

    monkeypatch.setattr(diagnostics, "verify_report", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "six_e_exit_diagnostics",
            "verify",
            "--registration",
            "logs/synthetic.json",
            "--registration-sha256",
            PIN,
            "--completion-sha256",
            PIN,
            "--report",
            "logs/synthetic_report.json",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        diagnostics.main()
    assert exc.value.code == 2


def test_cli_existing_output_is_refused_before_inspecting_history(registered, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("An existing output must be refused before inspecting history")

    output = registered.root / "logs/synthetic_existing_diagnostic.json"
    output.write_bytes(b"existing-output-must-stay")
    monkeypatch.setattr(diagnostics, "inspect", forbidden)
    monkeypatch.chdir(registered.root)
    monkeypatch.setattr(sys, "argv", cli_args(registered, output))
    with pytest.raises(ValueError):
        diagnostics.main()
    assert output.read_bytes() == b"existing-output-must-stay"
