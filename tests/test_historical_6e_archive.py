"""Coverage, causal case selection, daily isolation and fail-closed census evidence."""

import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for, write_json

from ai_trader.research import historical_6e_archive as census


@pytest.fixture
def census_root(metadata_root, monkeypatch):
    root = metadata_root
    old = {"preflight": census.v1.preflight(root)}
    monkeypatch.setattr(census.prior, "registration", lambda *a: deepcopy(old))
    report = {
        "status": "completed",
        "registration_sha256": census.PRIOR_PIN,
        "by_session": {s: {} for b in census.v1.BLOCKS for s in b.sessions},
        "evidence": [
            {"dated_contract_mappings": [{"utc_date": d} for d in b.source_days]}
            for b in census.v1.BLOCKS
        ],
    }
    monkeypatch.setattr(census, "PRIOR_REPORT_PIN", write_json(root / census.PRIOR_REPORT, report))
    monkeypatch.setattr(census.shutil, "disk_usage", lambda *a: SimpleNamespace(free=100 * 1024**3))
    return root


@pytest.mark.parametrize(
    "day,contract",
    [
        ("2025-03-26", "6EM5"),
        ("2025-06-08", "6EM5"),
        ("2025-06-09", "6EU5"),
        ("2025-09-07", "6EU5"),
        ("2025-09-08", "6EZ5"),
        ("2025-12-07", "6EZ5"),
        ("2025-12-08", "6EH6"),
        ("2025-12-31", "6EH6"),
    ],
)
def test_declared_calendar_roll_boundaries(day, contract):
    assert census.dated_contract(day) == contract


@pytest.mark.parametrize("day", ["2025-03-25", "2026-01-01", "2026-04-01", "2026-07-01"])
def test_reserved_and_outside_dates_refused_before_raw_access(day, monkeypatch):
    monkeypatch.setattr(census.zipfile, "ZipFile", lambda *a: pytest.fail("raw opened"))
    with pytest.raises(ValueError):
        census.replay_day({"utc_date": day})


def test_inventory_updates_completed_exposure_without_opening_raw(census_root, monkeypatch):
    monkeypatch.setattr(census.zipfile, "ZipFile", lambda *a: pytest.fail("raw opened"))
    result = census.inventory(census_root)
    assert result["prior_access_counts"] == {"outcomes_exposed": 9, "raw_replayed": 3}
    assert result["planned_actions"] == {"reconstruction_only": 3, "decision_window_replay": 9}
    assert result["raw_opened"] is False


def test_new_inventory_accounts_for_degraded_and_reserved_without_replay(census_root, monkeypatch):
    path = census_root / census.v1.INTAKE
    intake = json.loads(path.read_bytes())
    intake["batches"][0]["files"][1]["condition"] = "degraded"
    for day in ("2026-01-01", "2026-04-01", "2026-07-01"):
        intake["batches"][-1]["files"].append(
            {"date": day, "filename": day, "bytes": 1, "sha256": "c" * 64, "condition": "available"}
        )
    ledger = census.v1.exposure_ledger(intake, [])
    monkeypatch.setattr(census.prior, "registration", lambda *a: {"preflight": {"ledger": ledger}})
    monkeypatch.setattr(census.v1, "INTAKE_SHA256", write_json(path, intake))
    result = census.inventory(census_root)
    assert result["planned_actions"]["vendor_degraded_no_replay"] == 1
    assert result["planned_actions"]["reserved_metadata_only"] == 3
    assert all(r["contract"] is None for r in result["ledger"] if r["partition"] != "development")


@pytest.mark.parametrize("block", census.v1.BLOCKS)
def test_single_daily_engine_exactly_reproduces_versioned_block_rows(block):
    original = census.receive.ReceiveTimeBuilder(block)
    expected = []
    for day in block.source_days:
        original.start_day(date.fromisoformat(day))
        daily = census.DailyBuilder(day, block.contract)
        daily.start_day(date.fromisoformat(day))
        for r in records_for(date.fromisoformat(day), block.contract):
            original.consume(r)
            daily.consume(r)
        original.finish_day()
        daily.finish_day()
        rows, cases, quality = daily.finish()
        assert quality["receive_clock_v2"]["counts"]["target_records"] > 0
        assert len(cases) <= 240
        assert all(
            set(r["path_horizons"]) == {"1", "5", "15", "30", "60"}
            for r in cases
            if r["outcome"].get("entry_ts_ns") is not None
        )
        expected.extend(
            {k: v for k, v in r.items() if k not in {"contract", "partition"}} for r in rows
        )
    assert original.finish()[0] == expected


def test_refuses_calendar_override_and_retains_strict_quality():
    with pytest.raises(ValueError, match="Contract"):
        census.DailyBuilder("2025-04-07", "6EU5")
    b = census.DailyBuilder("2025-04-07", "6EM5")
    b.start_day(date(2025, 4, 7))
    with pytest.raises(ValueError, match="Empty"):
        b.finish_day()


def test_case_thinning_is_independent_of_future_targets_and_keeps_unavailable():
    rows = []
    for i in range(121):
        values = {k: float(i) for k in census.study.data.FEATURES}
        rows.append(
            {
                "source_session": "2025-04-07",
                "decision_ts_ns": (1000 + i) * 10**9,
                "features": values,
                "execution_features": {k: 0.0 for k in census.study.flow.FEATURES},
                "eligible": True,
                "outcome": {"status": "resolved"},
                "hindsight_action": 1 if i >= 60 else 0,
            }
        )
    rows[60]["outcome"]["status"] = "no_entry_quote_timeout"
    rows[60]["hindsight_action"] = None
    result = census.case_associations(rows)
    assert (result["causally_thinned"], result["resolved"], result["unavailable"]) == (3, 2, 1)
    assert result["positive"] == result["nonpositive"] == 1
    assert result["feature_associations"]["queue_imbalance"]["positive_opportunity_auc"] == 1
    assert result["feature_associations"]["bid_passive_5s"]["positive_opportunity_auc"] == 0.5
    changed = deepcopy(rows)
    changed[0]["hindsight_action"] = -1
    assert census.case_associations(changed)["causally_thinned"] == 3


def test_empty_case_summary_has_no_fabricated_auc():
    result = census.case_associations([])
    assert result["positive"] == result["nonpositive"] == result["resolved"] == 0
    assert all(
        v["positive_opportunity_auc"] is None for v in result["feature_associations"].values()
    )


def setup_run(root):
    path = root / "census.json"
    census.prepare(root, path)
    pin = census.common.hash_file(path, 2 * 1024**2)
    return path, pin, root / "data/processed/census"


def test_registration_rejects_implementation_policy_and_metadata_drift(census_root, monkeypatch):
    path, pin, _ = setup_run(census_root)
    assert census.registration(census_root, path, pin)
    monkeypatch.setattr(census, "MAX_DAY_SECONDS", 1)
    with pytest.raises(ValueError, match="changed"):
        census.registration(census_root, path, pin)


def test_census_retains_every_refusal_and_never_retries(census_root, monkeypatch):
    path, pin, output = setup_run(census_root)
    calls = []

    def refuse(member):
        calls.append(member["utc_date"])
        raise ValueError("synthetic incomplete book")

    monkeypatch.setattr(census, "replay_day", refuse)
    result = census.run(census_root, path, pin, output)
    assert result["counts"] == {"quality_refused": 12}
    assert len(calls) == len(set(calls)) == 12
    assert len(list((output / "attempts").glob("*.json"))) == 12
    assert not result["training_enabled"] and not result["strategy_aggregate_permitted"]
    with pytest.raises(FileExistsError):
        census.run(census_root, path, pin, output)
    assert len(calls) == 12


def test_fatal_error_preserves_attempt_and_has_no_completion(census_root, monkeypatch):
    path, pin, output = setup_run(census_root)

    def crash(member):
        raise RuntimeError("synthetic unexpected error")

    monkeypatch.setattr(census, "replay_day", crash)
    with pytest.raises(RuntimeError):
        census.run(census_root, path, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    assert len(list((output / "attempts").glob("*.json"))) == 1


def test_complete_synthetic_census_publishes_pinned_daily_shards(census_root, monkeypatch):
    def iterator(archive, member):
        yield from records_for(date.fromisoformat(member["utc_date"]), member["contract"])

    monkeypatch.setattr(census.source, "_member_records", iterator)
    path, pin, output = setup_run(census_root)
    result = census.run(census_root, path, pin, output)
    assert result["counts"] == {"replayed": 12}
    for item in result["dates"]:
        stem = output / "days" / item["utc_date"]
        report = census.v1.read_pinned(
            stem.with_suffix(".json"), item["report_sha256"], 2 * 1024**2
        )
        assert report["rows_sha256"] == census.common.hash_file(
            stem.with_suffix(".rows.jsonl"), census.MAX_DAY_BYTES
        )
        assert report["cases_sha256"] == census.common.hash_file(
            stem.with_suffix(".cases.jsonl"), census.MAX_DAY_BYTES
        )
        assert not report["training_eligible"]


def test_no_output_outside_processed_or_when_disk_is_low(census_root, monkeypatch):
    path, pin, output = setup_run(census_root)
    with pytest.raises(ValueError, match="processed"):
        census.run(census_root, path, pin, census_root / "elsewhere")
    monkeypatch.setattr(census.shutil, "disk_usage", lambda *a: SimpleNamespace(free=0))
    with pytest.raises(ValueError, match="space"):
        census.run(census_root, path, pin, output)
    assert not output.exists()


def test_serialization_byte_limit(monkeypatch):
    monkeypatch.setattr(census, "MAX_DAY_BYTES", 10)
    with pytest.raises(ValueError, match="byte"):
        census.encode_rows([{"too_large": "x" * 20}])
