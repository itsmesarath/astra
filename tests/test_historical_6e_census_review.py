"""Completed census integrity, reserved isolation and descriptive movement accounting."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_archive import setup_run
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for, write_json

from ai_trader.research import historical_6e_census_review as review


@pytest.fixture
def evidence(census_root, monkeypatch):
    census = review.census

    def iterator(archive, member):
        yield from records_for(date.fromisoformat(member["utc_date"]), member["contract"])

    # The iterator uses actual daily dates with the existing causal engine.
    monkeypatch.setattr(census.source, "_member_records", iterator)
    original = census.inventory

    def expanded(root):
        inventory = original(root)
        inventory["ledger"].append(
            {
                "utc_date": "2026-01-01",
                "partition": "validation_reserved",
                "planned_action": "reserved_metadata_only",
                "contract": None,
            }
        )
        inventory["planned_actions"]["reserved_metadata_only"] = 1
        return inventory

    monkeypatch.setattr(census, "inventory", expanded)
    registration, pin, directory = setup_run(census_root)
    census.run(census_root, registration, pin, directory)
    receipt_pin = review.common.hash_file(directory / "completion.json", review.MAX_METADATA_BYTES)
    # Published evidence review must not need raw archive access or another replay.
    monkeypatch.setattr(census.zipfile, "ZipFile", lambda *a: pytest.fail("archive opened"))
    return {
        "root": census_root,
        "directory": directory,
        "registration_path": registration,
        "registration_sha256": pin,
        "receipt_sha256": receipt_pin,
        "output": census_root / "data/processed/review.json",
    }


def rewrite_receipt(evidence, receipt):
    evidence["receipt_sha256"] = write_json(evidence["directory"] / "completion.json", receipt)


def receipt(evidence):
    return json.loads((evidence["directory"] / "completion.json").read_bytes())


def refresh_journal(evidence, updated):
    journal = evidence["directory"] / "progress.jsonl"
    journal.write_bytes(b"".join(review.common.canonical(r) + b"\n" for r in updated["dates"]))
    updated["progress_sha256"] = review.common.hash_file(journal, review.MAX_METADATA_BYTES)
    rewrite_receipt(evidence, updated)


def change_report(evidence, mutate):
    updated = receipt(evidence)
    item = next(r for r in updated["dates"] if r["status"] == "replayed" and r["cases"])
    report_path = evidence["directory"] / "days" / f"{item['utc_date']}.json"
    report = json.loads(report_path.read_bytes())
    old_size = report_path.stat().st_size
    mutate(report)
    item["report_sha256"] = write_json(report_path, report)
    updated["total_published_bytes"] += report_path.stat().st_size - old_size
    refresh_journal(evidence, updated)


def test_complete_review_reconciles_artifacts_and_preserves_reserved_dates(evidence, monkeypatch):
    reserved = evidence["directory"] / "days/2026-01-01.json"
    original = Path.open

    def guarded(path, *args, **kwargs):
        if path == reserved:
            pytest.fail("reserved outcome artifact opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = review.run(**evidence)
    assert result["coverage"]["all_inventory_dates"] == 13
    assert result["coverage"]["weekday_decision_dates"] == 9
    assert result["coverage"]["reconstruction_only_dates"] == 3
    assert result["coverage"]["terminal_counts"] == {"replayed": 12, "reserved_metadata_only": 1}
    assert result["coverage"]["sampled_cases"] > 0
    support = result["feature_observation_support"]["queue_imbalance"]
    assert support["observations"] == result["coverage"]["sampled_cases"]
    assert support["minimum"] <= support["maximum"]
    assert result["coverage"]["all_hours_analyzed"] is False
    assert all(
        result[key] is False
        for key in (
            "training_enabled",
            "trading_enabled",
            "promotion_enabled",
            "reserved_outcomes_opened",
            "raw_archives_opened",
            "strategy_aggregate_permitted",
        )
    )
    assert json.loads(evidence["output"].read_bytes()) == result
    assert "historical_6e_census_review.py" in result["review_implementation_sha256"]
    with pytest.raises(ValueError, match="new"):
        review.run(**evidence)


@pytest.mark.parametrize(
    "key",
    [
        "training_enabled",
        "promotion_enabled",
        "reserved_outcomes_opened",
        "strategy_aggregate_permitted",
    ],
)
def test_refuses_changed_census_operational_flags(evidence, key):
    updated = receipt(evidence)
    updated[key] = True
    rewrite_receipt(evidence, updated)
    with pytest.raises(ValueError, match="research-only"):
        review.run(**evidence)
    assert not evidence["output"].exists()


@pytest.mark.parametrize("kind", ["rows", "cases"])
def test_changed_published_data_refused_before_summary(evidence, kind):
    day = next(r["utc_date"] for r in receipt(evidence)["dates"] if r.get("cases", 0))
    path = evidence["directory"] / "days" / f"{day}.{kind}.jsonl"
    path.write_bytes(path.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="changed census artifact"):
        review.run(**evidence)
    assert not evidence["output"].exists()


def test_changed_registration_pin_refused(evidence):
    evidence["registration_path"].write_bytes(b"{}")
    with pytest.raises(ValueError, match="Pinned metadata"):
        review.run(**evidence)


def test_top_level_failure_refuses_even_with_completion(evidence):
    write_json(evidence["directory"] / "failure.json", {"error": "interrupted"})
    with pytest.raises(ValueError, match="completed"):
        review.run(**evidence)


def test_receipt_cannot_drop_failed_or_reserved_date(evidence):
    updated = receipt(evidence)
    updated["dates"].pop()
    updated["counts"].pop("reserved_metadata_only")
    refresh_journal(evidence, updated)
    with pytest.raises(ValueError, match="date accounting"):
        review.run(**evidence)


def test_reserved_replay_refused_before_artifact_lookup(evidence):
    updated = receipt(evidence)
    updated["dates"][-1] = {"utc_date": "2026-01-01", "status": "replayed"}
    updated["counts"] = {"replayed": 13}
    refresh_journal(evidence, updated)
    with pytest.raises(ValueError, match="Reserved"):
        review.run(**evidence)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(source_sha256="c" * 64),
        lambda r: r.update(contract="6EH6"),
        lambda r: r.update(training_eligible=True),
        lambda r: r["summary"].update(rows=r["rows"] + 1),
        lambda r: r["quality"]["receive_clock_v2"]["counts"].update(protected_disagreements=1),
    ],
)
def test_repacked_reports_must_still_match_identity_and_quality(evidence, mutation):
    change_report(evidence, mutation)
    with pytest.raises(ValueError):
        review.run(**evidence)
    assert not evidence["output"].exists()


def test_repacked_case_association_must_reproduce_published_cases(evidence):
    change_report(evidence, lambda r: r["case_associations"].update(positive=999))
    with pytest.raises(ValueError, match="associations"):
        review.run(**evidence)


def test_progress_must_exactly_match_receipt(evidence):
    updated = receipt(evidence)
    updated["dates"][0]["cases"] += 1
    rewrite_receipt(evidence, updated)
    with pytest.raises(ValueError, match="progress date"):
        review.run(**evidence)


def test_total_published_size_reconciled(evidence):
    updated = receipt(evidence)
    updated["total_published_bytes"] += 1
    rewrite_receipt(evidence, updated)
    with pytest.raises(ValueError, match="byte accounting"):
        review.run(**evidence)


def test_refusals_retained_without_retry(census_root, monkeypatch):
    census = review.census
    monkeypatch.setattr(
        census,
        "replay_day",
        lambda member: (_ for _ in ()).throw(
            ValueError("Target MBO has a bad timestamp or quality flag")
        ),
    )
    registration, pin, directory = setup_run(census_root)
    census.run(census_root, registration, pin, directory)
    result = review.run(
        root=census_root,
        directory=directory,
        registration_path=registration,
        registration_sha256=pin,
        receipt_sha256=review.common.hash_file(
            directory / "completion.json", review.MAX_METADATA_BYTES
        ),
        output=census_root / "data/processed/refusal_review.json",
    )
    assert len(result["quality_refusals"]) == 12
    assert result["refusal_categories"] == {"source_quality_flag": 12}
    assert result["coverage"]["sampled_cases"] == 0
    assert result["hindsight_horizons"]["15"]["unavailable"] == 0
    assert (
        result["equal_date_weight_feature_associations"]["any_positive_15s_direction"][
            "queue_imbalance"
        ]["p10_median_p90"]
        is None
    )


def test_hindsight_counts_keep_censored_paths_and_cost_sensitivity_separate():
    def row(gross, *, late=False, gap=False):
        return {
            "path_horizons": {
                str(h): {
                    "status": "resolved",
                    "gross_long_short_ticks": gross,
                    "late_exit": late,
                    "inactivity_exposed": gap,
                }
                for h in review.census.paths.HORIZONS
            }
        }

    rows = [row([2, -4]), row([-5, 3], late=True), row([0, -2], gap=True)]
    rows.append({"path_horizons": {}})
    result = review.horizon_counts(rows)["15"]
    assert result["attempts"] == 4 and result["unavailable"] == 1
    assert result["resolved"] == 3 and result["clean_resolved"] == 1
    assert result["positive_direction_in_hindsight"]["1"] == {
        "all_resolved": 2,
        "clean_resolved": 1,
    }
    assert result["positive_direction_in_hindsight"]["2"] == {
        "all_resolved": 1,
        "clean_resolved": 0,
    }
    assert result["positive_direction_in_hindsight"]["4"]["all_resolved"] == 0


def test_direction_and_opportunity_are_distinct_and_ties_are_explicit():
    rows = []
    for index, targets in enumerate(([2, -4], [-3, -1], [-2, -2], [-5, 3])):
        rows.append(
            {
                "outcome": {"status": "resolved"},
                "net_targets_long_short_ticks": targets,
                "hindsight_action": (1, 0, 0, -1)[index],
                "features": {k: float(index) for k in review.census.study.data.FEATURES},
                "execution_features": {k: float(index) for k in review.census.study.flow.FEATURES},
            }
        )
    result = review.daily_associations(rows)
    assert result["any_positive_15s_direction"]["observations"] == 4
    assert result["any_positive_15s_direction"]["positive_class"] == 2
    assert result["long_better_than_short_15s"]["observations"] == 3
    assert result["long_better_than_short_15s"]["excluded_resolved_ties"] == 1
    assert result["long_better_than_short_15s"]["positive_class"] == 1
    assert result["long_better_than_short_15s"]["feature_auc"]["queue_imbalance"] == 0
    assert result["any_positive_15s_direction"]["meets_descriptive_support"] is False
    changed = deepcopy(rows)
    changed[0]["features"]["queue_imbalance"] = float("nan")
    with pytest.raises(ValueError, match="Invalid binary AUC"):
        review.daily_associations(changed)


def test_feature_direction_is_not_reversed_to_improve_auc():
    result = review.auc_distribution([0.2, 0.4, 0.5, 0.7])
    assert result["p10_median_p90"][1] == pytest.approx(0.45)
    assert result["dates_above_half"] == 1
    assert result["dates_below_half"] == 2


def test_output_outside_processed_refused_before_any_intake(evidence):
    evidence["output"] = evidence["root"] / "outside.json"
    with pytest.raises(ValueError, match="processed"):
        review.run(**evidence)


def test_helper_implementation_drift_prevents_publication(evidence, monkeypatch):
    original = review.describe

    def changed(*args):
        result = original(*args)
        monkeypatch.setattr(review.census, "fingerprints", lambda: {"changed": "a" * 64})
        return result

    monkeypatch.setattr(review, "describe", changed)
    with pytest.raises(ValueError, match="implementation changed"):
        review.run(**evidence)
    assert not evidence["output"].exists()
