"""Refusal diagnosis is bounded, metadata-only, complete-file and fail-closed."""

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

import databento_dbn as dbn
import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_archive import setup_run
from test_historical_6e_cohort import make_metadata, write_json
from test_historical_6e_cohort import metadata_root as metadata_root

from ai_trader.research import historical_6e_refusal_diagnostic as audit

DAY = date(2025, 4, 27)
START = audit.source._utc_ns(DAY)


def event(hour=22, flags=dbn.F_BAD_TS_RECV, recv=None, instrument=42):
    timestamp = START + hour * 3600 * 10**9 if recv is None else recv
    return dbn.MBOMsg(
        publisher_id=1,
        instrument_id=instrument,
        ts_recv=timestamp,
        ts_event=timestamp,
        order_id=0,
        price=0,
        size=0,
        action=dbn.Action.CLEAR,
        side=dbn.Side.NONE,
        flags=flags,
        ts_in_delta=0,
    )


def analyze(*records):
    return audit.summarize([make_metadata(DAY, "6EM5"), *records], DAY, "6EM5")


def test_closed_clear_exception_and_open_clear_flag_are_distinguished_not_accepted():
    result = analyze(event(hour=20), event(hour=22))
    assert result["counts"]["legacy_closed_clear_exception"] == 1
    assert result["counts"]["flag_gate_refusal_records"] == 1
    sample = result["first_eight_flag_gate_refusals"][0]
    assert sample["legacy_weekly_session"] == "2025-04-28"
    assert sample["effective_bad_bits"] == dbn.F_BAD_TS_RECV
    assert not sample["inside_decision_window"]
    assert result["source_accepted"] is False
    assert result["holiday_calendar_verified"] is False


@pytest.mark.parametrize("flag", [dbn.F_MAYBE_BAD_BOOK, dbn.F_TOB, dbn.F_MBP])
def test_snapshot_only_exempts_bad_receive_flag_not_book_flags(flag):
    result = analyze(
        event(flags=dbn.F_SNAPSHOT | dbn.F_BAD_TS_RECV),
        event(flags=dbn.F_SNAPSHOT | dbn.F_BAD_TS_RECV | flag),
    )
    assert result["counts"]["snapshot_records"] == 2
    assert result["counts"]["flag_gate_refusal_records"] == 1
    assert result["first_eight_flag_gate_refusals"][0]["effective_bad_bits"] == flag


def test_window_boundaries_f_last_and_regressions_are_metadata_not_quotes():
    result = analyze(
        event(hour=11, flags=dbn.F_LAST),
        event(hour=12, flags=dbn.F_LAST),
        event(hour=12, flags=dbn.F_LAST | dbn.F_SNAPSHOT),
        event(hour=15, flags=dbn.F_LAST),
        event(hour=16, flags=dbn.F_LAST),
        event(hour=11, flags=dbn.F_LAST),
        event(instrument=99),
    )
    assert result["counts"]["target_records"] == 6
    assert result["counts"]["records_in_decision_window"] == 3
    assert result["counts"]["non_snapshot_f_last_in_decision_window"] == 2
    assert result["counts"]["snapshot_records_in_decision_window"] == 1
    assert result["counts"]["receive_regressions"] == 1
    assert result["f_last_is_not_a_reconstructed_quote_count"] is True
    assert not result["decision_window_empty_of_target_records"]


def test_empty_window_reported_without_asserting_a_holiday_or_missing_whole_day():
    result = analyze(event(hour=22, flags=dbn.F_LAST))
    assert result["counts"]["target_records"] == 1
    assert result["decision_window_empty_of_target_records"] is True
    assert result["counts"]["records_in_decision_window"] == 0


def test_out_of_day_and_undefined_metadata_reported_without_unsafe_calendar_conversion():
    result = analyze(event(recv=START - 1), event(recv=dbn.UNDEF_TIMESTAMP))
    assert result["counts"]["receive_outside_member_day"] == 2
    assert result["counts"]["undefined_receive_timestamp"] == 1
    assert result["first_valid_receive_ns"] is None
    assert all(s["legacy_weekly_session"] is None for s in result["first_eight_flag_gate_refusals"])


def test_samples_stay_bounded_and_do_not_include_price_size_order_or_labels():
    result = analyze(*(event() for _ in range(100)))
    assert result["counts"]["flag_gate_refusal_records"] == 100
    assert len(result["first_eight_flag_gate_refusals"]) == 8
    assert not {"price", "size", "order_id", "features", "outcome"}.intersection(
        result["first_eight_flag_gate_refusals"][0]
    )
    audit.common.canonical(result)


@pytest.mark.parametrize("kind", ["missing", "duplicate", "empty", "unexpected"])
def test_missing_or_duplicate_metadata_and_invalid_record_shape_refuse(kind):
    header = make_metadata(DAY, "6EM5")
    records = {
        "missing": [event()],
        "duplicate": [header, header],
        "empty": [header],
        "unexpected": [header, object()],
    }[kind]
    with pytest.raises(ValueError):
        audit.summarize(records, DAY, "6EM5")


def test_development_partition_checked_before_iterator_access():
    def records():
        pytest.fail("reserved raw consumed")
        yield

    with pytest.raises(ValueError, match="Reserved"):
        audit.summarize(records(), date(2026, 1, 1), "6EH6")


def test_time_limit_refuses_before_publication(monkeypatch):
    monkeypatch.setattr(audit, "MAX_DAY_SECONDS", -1)
    with pytest.raises(TimeoutError, match="per-day"):
        analyze(event())


@pytest.fixture
def evidence(census_root, monkeypatch):
    census = audit.census
    original = census.inventory

    def inventory(root):
        result = original(root)
        result["ledger"].append(
            {
                "utc_date": "2026-01-01",
                "partition": "validation_reserved",
                "planned_action": "reserved_metadata_only",
                "contract": None,
            }
        )
        result["planned_actions"]["reserved_metadata_only"] = 1
        return result

    monkeypatch.setattr(census, "inventory", inventory)
    monkeypatch.setattr(
        census,
        "replay_day",
        lambda member: (_ for _ in ()).throw(
            ValueError("Target MBO has a bad timestamp or quality flag")
        ),
    )
    path, pin, directory = setup_run(census_root)
    census.run(census_root, path, pin, directory)
    monkeypatch.setattr(audit, "REGISTRATION", str(path))
    monkeypatch.setattr(audit, "REGISTRATION_PIN", pin)
    monkeypatch.setattr(audit, "CENSUS_DIRECTORY", str(directory))
    monkeypatch.setattr(
        audit,
        "RECEIPT_PIN",
        audit.common.hash_file(directory / "completion.json", audit.MAX_REPORT_BYTES),
    )

    def iterator(archive, member):
        day = date.fromisoformat(member["utc_date"])
        assert day.year == 2025
        yield make_metadata(day, member["contract"])
        yield event(recv=audit.source._utc_ns(day) + 22 * 3600 * 10**9)

    monkeypatch.setattr(audit.source, "_member_records", iterator)
    registration = census_root / "diagnostic-registration.json"
    audit.prepare(census_root, registration)
    return (
        census_root,
        registration,
        audit.common.hash_file(registration, audit.MAX_REPORT_BYTES),
        census_root / "data/processed/diagnostic",
    )


def test_whole_refusal_scope_verified_without_reserved_or_successful_artifacts(
    evidence, monkeypatch
):
    root, path, pin, output = evidence
    reserved = root / audit.CENSUS_DIRECTORY / "days/2026-01-01.json"
    original = Path.open

    def guarded(path, *args, **kwargs):
        if path == reserved:
            pytest.fail("reserved artifact opened")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    result = audit.run(root, path, pin, output)
    assert len(result["reports"]) == 12
    assert result["source_scope"]["all_inventory_dates"] == 13
    assert result["status"] == "all_refused_members_scanned_not_source_accepted"
    for r in result["reports"]:
        report = audit.review.pinned(output / f"{r['utc_date']}.json", r["report_sha256"])
        assert report["member_sha256_verified_at_eof"] == "b" * 64
        assert report["source_accepted"] is False
    for key in (
        "quality_gate_changed",
        "source_modified",
        "new_labels_or_features",
        "reserved_raw_opened",
        "training_enabled",
        "trading_enabled",
        "promotion_enabled",
    ):
        assert result[key] is False
    with pytest.raises(ValueError, match="new"):
        audit.run(root, path, pin, output)


def test_eof_source_hash_failure_cannot_publish_completed_scan(evidence, monkeypatch):
    root, path, pin, output = evidence
    original = audit.source._member_records

    def iterator(*args):
        yield from original(*args)
        raise ValueError("Selected source member SHA256 differs from pinned intake")

    monkeypatch.setattr(audit.source, "_member_records", iterator)
    with pytest.raises(ValueError, match="SHA256"):
        audit.run(root, path, pin, output)
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()
    assert len(list(output.glob("*.attempt.json"))) == 1
    assert len(list(output.glob("2025-*.json"))) == 1  # Only the retained date attempt.


@pytest.mark.parametrize("change", ["policy", "source", "implementation"])
def test_registration_drift_refuses_before_any_raw_access(evidence, monkeypatch, change):
    root, path, pin, output = evidence
    if change == "policy":
        monkeypatch.setattr(audit, "MAX_DATES", 33)
    elif change == "source":
        directory = root / audit.CENSUS_DIRECTORY
        (directory / "days/2025-04-07.failure.json").write_bytes(b"{}")
    else:
        monkeypatch.setattr(audit, "fingerprints", lambda: {})
    monkeypatch.setattr(audit, "scan", lambda *a: pytest.fail("raw opened"))
    with pytest.raises(ValueError):
        audit.run(root, path, pin, output)
    assert not output.exists()


def test_source_journal_and_partition_cannot_change_or_drop_refused_dates(evidence, monkeypatch):
    root, _, _, _ = evidence
    directory = root / audit.CENSUS_DIRECTORY
    receipt = json.loads((directory / "completion.json").read_bytes())
    changed = deepcopy(receipt)
    changed["dates"].pop(0)
    monkeypatch.setattr(audit, "RECEIPT_PIN", write_json(directory / "completion.json", changed))
    with pytest.raises(ValueError, match="accounting"):
        audit.scope(root)


def test_archive_size_or_member_scope_refuses_before_archive_open(evidence, monkeypatch):
    root, path, pin, _ = evidence
    member = audit.registration(root, path, pin)["scope"]["refused_dates"][0]["member"]
    monkeypatch.setattr(audit.zipfile, "ZipFile", lambda *a: pytest.fail("archive opened"))
    with pytest.raises(ValueError, match="archive"):
        audit.scan({**member, "archive_bytes": 99})
    with pytest.raises(ValueError, match="Reserved"):
        audit.scan({"utc_date": "2026-01-01"})
