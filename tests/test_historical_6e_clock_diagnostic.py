"""Timestamp diagnosis cannot create strategy outcomes or relax the replay gate."""

from datetime import date

import databento_dbn as dbn
import pytest
from test_historical_6e_cohort import make_metadata

from ai_trader.research import historical_6e_clock_diagnostic as audit

DAY = date(2025, 10, 8)
START = audit.cohort.source._utc_ns(DAY)


def event(hour=12, delta=7, flags=dbn.F_LAST, instrument=42, at=None):
    recv = START + hour * 3600 * 10**9 if at is None else at
    return dbn.MBOMsg(
        publisher_id=1,
        instrument_id=instrument,
        ts_recv=recv,
        ts_event=recv + delta,
        order_id=0,
        price=0,
        size=0,
        action=dbn.Action.CLEAR,
        side=dbn.Side.NONE,
        flags=flags,
        ts_in_delta=-5,
    )


def analyze(*records):
    return audit.summarize([make_metadata(DAY, "6EZ5"), *records], DAY, "6EZ5")


def test_signed_clock_disagreement_and_window_boundaries():
    result = analyze(
        event(hour=11, delta=2),
        event(hour=12, delta=7),
        event(hour=15, delta=100),
        event(hour=16, delta=9),
        event(hour=17, delta=-5),
    )
    assert result["counts"]["exchange_after_receive_records"] == 4
    assert result["counts"]["exchange_after_receive_inside_decision_window"] == 2
    assert result["counts"]["exchange_after_receive_outside_decision_window"] == 2
    assert result["min_event_minus_receive_ns"] == 2
    assert result["max_event_minus_receive_ns"] == 100
    assert result["counts"]["event_later_than_sending_timestamp"] == 3
    assert result["counts"]["receive_regressions"] == 0


def test_snapshots_and_other_contracts_are_not_clock_inversions():
    result = analyze(event(flags=dbn.F_SNAPSHOT), event(instrument=99))
    assert result["counts"]["target_records"] == 1
    assert result["counts"]["snapshot_records_excluded_from_clock_comparison"] == 1
    assert result["min_event_minus_receive_ns"] is None


def test_receive_regressions_flags_and_source_bounds_reported_not_ignored():
    result = analyze(
        event(),
        event(hour=11, flags=dbn.F_BAD_TS_RECV | dbn.F_MAYBE_BAD_BOOK),
        event(at=START - 1),
        event(delta=0),
    )
    counts = result["counts"]
    assert counts["receive_regressions"] == 2
    assert counts["bad_receive_flag"] == counts["maybe_bad_book_flag"] == 1
    assert counts["receive_outside_member_day"] == 1


def test_samples_bounded_and_do_not_contain_price_size_or_outcomes():
    result = analyze(*[event(delta=i) for i in range(1, 101)])
    assert result["counts"]["exchange_after_receive_records"] == 100
    assert len(result["first_eight_inverted_records"]) == 8
    assert not {"price", "size", "outcome", "order_id"}.intersection(
        result["first_eight_inverted_records"][0]
    )


def test_missing_or_duplicate_metadata_and_empty_target_rejected():
    header = make_metadata(DAY, "6EZ5")
    for records in ([event()], [header, header], [header], [header, event(instrument=99)]):
        with pytest.raises(ValueError):
            audit.summarize(records, DAY, "6EZ5")


def test_existing_output_refused_before_metadata_access(tmp_path, monkeypatch):
    output = tmp_path / "audit.json"
    output.write_text("existing evidence")
    monkeypatch.setattr(audit.cohort, "registration", lambda *a: pytest.fail("too late"))
    with pytest.raises(ValueError, match="overwrite"):
        audit.run(tmp_path, output)
    assert output.read_text() == "existing evidence"
