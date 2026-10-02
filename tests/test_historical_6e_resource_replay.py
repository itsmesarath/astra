"""Disk quote storage preserves causal paths and refuses resource/source drift."""

from datetime import date
from types import SimpleNamespace

import databento_dbn as dbn
import numpy as np
import pytest
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_archive import setup_run
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for
from test_historical_6e_paths import original, quotes

from ai_trader.research import historical_6e_resource_replay as resource

SECOND = resource.paths.clock.SECOND_NS


def spool(tmp_path, q, monkeypatch):
    monkeypatch.setattr(resource, "CHUNK_QUOTES", 2)
    result = resource.QuoteSpool(tmp_path / "quotes", 100 * SECOND)
    try:
        for ts, bid, ask in q:
            result.append(SimpleNamespace(ts_recv_ns=int(ts), bid=int(bid), ask=int(ask)))
        return result
    except Exception:
        result.close()
        raise


@pytest.mark.parametrize(
    "points,end",
    [
        ([(0, 0, 1), (1, 1, 2), (5, 3, 4), (15, 5, 7), (30, -3, -2), (60, 8, 9)], 100),
        ([(0, 0, 1), (2.01, 10, 11), (5, 10, 11), (15, 0, 1), (60, 0, 1)], 100),
        ([(0, 0, 1), (1, -2, -1), (1, 10, 11), (15, 0, 1), (60, 0, 1)], 100),
        ([(0, 0, 1), (1, 0, 1), (5, 0, 1), (15, 2, 3), (20, 3, 4)], 30),
        ([(0, 0, 1), (5, 0, 1), (10, 0, 1), (14, 0, 1)], 21),
        ([(0, 0, 1), (5, 0, 1), (10, 0, 1), (15, 0, 1), (20.000000001, 0, 1)], 100),
    ],
)
def test_disk_paths_exactly_match_frozen_array_including_gaps_and_equal_timestamps(
    tmp_path,
    monkeypatch,
    points,
    end,
):
    q = quotes(points)
    store = spool(tmp_path, q, monkeypatch)
    expected = resource.paths.analyze_entry(q, original(q, end * SECOND), end * SECOND)
    with store.seal() as view:
        assert view[:, 0].flags.c_contiguous
        assert len(view) == len(q)
        assert tuple(view[0]) == tuple(q[0])
        assert np.array_equal(view[:], q)
        assert (
            resource.paths.analyze_entry(view, original(q, end * SECOND), end * SECOND) == expected
        )
    assert view.columns == []
    assert store.handles == []
    assert store.count == len(q)
    for name, expected_column in zip(resource.COLUMNS, q.T, strict=True):
        assert (store.directory / f"{name}.i64").read_bytes() == expected_column.astype(
            "<i8"
        ).tobytes()
    with pytest.raises(ValueError, match="closed"):
        store.append(SimpleNamespace(ts_recv_ns=0, bid=1, ask=2))
    with pytest.raises(ValueError, match="closed"):
        store.seal()


def test_disk_paths_retain_entry_failure_and_original_target_regression(tmp_path, monkeypatch):
    q = quotes([(0, 0, 1), (15, 0, 1), (60, 0, 1)])
    store = spool(tmp_path, q, monkeypatch)
    with store.seal() as view:
        assert resource.paths.analyze_entry(view, {"entry_ts_ns": None}, 100 * SECOND) == {}
        bad = original(q)
        bad["exit_bid_nano"] += 1
        with pytest.raises(ValueError, match="regression"):
            resource.paths.analyze_entry(view, bad, 100 * SECOND)


@pytest.mark.parametrize("seed", range(10))
def test_randomized_tapes_match_original_path_analyzer(tmp_path, monkeypatch, seed):
    rng = np.random.default_rng(seed)
    times = np.concatenate(([0], np.sort(rng.integers(0, 90 * SECOND, size=300))))
    prices = np.concatenate(([0], np.cumsum(rng.integers(-3, 4, size=300))))
    q = quotes(
        [
            (int(ts) / SECOND, int(price), int(price) + 1)
            for ts, price in zip(times, prices, strict=True)
        ]
    )
    store = spool(tmp_path, q, monkeypatch)
    with store.seal() as view:
        expected = resource.paths.analyze_entry(q, original(q), 100 * SECOND)
        assert resource.paths.analyze_entry(view, original(q), 100 * SECOND) == expected


@pytest.mark.parametrize("change", ["bad_flag", "protected_clock", "receive_regression"])
def test_disk_builder_keeps_frozen_receive_and_quality_refusals(tmp_path, change):
    day = date(2025, 4, 7)
    builder = resource.DiskDailyBuilder(day.isoformat(), "6EM5", tmp_path / "quotes")
    builder.start_day(day)
    try:
        records = records_for(day, "6EM5")
        for _ in range(6):  # Metadata, snapshot, and one completed warmup event.
            builder.consume(next(records))
        record = next(records)
        if change == "bad_flag":
            record = dbn.MBOMsg(
                publisher_id=1,
                instrument_id=42,
                order_id=0,
                price=0,
                size=0,
                ts_recv=record.ts_recv,
                ts_event=record.ts_event,
                action=dbn.Action.CLEAR,
                side=dbn.Side.NONE,
                flags=dbn.F_MAYBE_BAD_BOOK,
            )
        elif change == "protected_clock":
            record = dbn.MBOMsg(
                publisher_id=1,
                instrument_id=42,
                order_id=0,
                price=0,
                size=0,
                ts_recv=record.ts_recv,
                ts_event=record.ts_recv + 1,
                action=dbn.Action.NONE,
                side=dbn.Side.NONE,
                flags=dbn.F_LAST,
            )
        else:
            record = dbn.MBOMsg(
                publisher_id=1,
                instrument_id=42,
                order_id=0,
                price=0,
                size=0,
                ts_recv=builder.window_start_ns - 11 * SECOND,
                ts_event=builder.window_start_ns - 11 * SECOND,
                action=dbn.Action.NONE,
                side=dbn.Side.NONE,
                flags=dbn.F_LAST,
            )
        expected = {
            "bad_flag": "quality flag",
            "protected_clock": "Cross-clock",
            "receive_regression": "regressed",
        }[change]
        with pytest.raises(ValueError, match=expected):
            builder.consume(record)
        assert resource.DiskDailyBuilder.consume is resource.census.DailyBuilder.consume
    finally:
        builder.spool.close()


@pytest.mark.parametrize("kind", ["crossed", "off_tick", "negative", "at_end", "regressed"])
def test_invalid_quote_or_cross_chunk_regression_refused(tmp_path, monkeypatch, kind):
    q = quotes([(0, 0, 1), (1, 0, 1), (2, 0, 1)])
    if kind == "crossed":
        q[1, 2] = q[1, 1]
    elif kind == "off_tick":
        q[1, 1] += 1
    elif kind == "negative":
        q[1, 0] = -1
    elif kind == "at_end":
        q[1, 0] = 100 * SECOND
    else:
        q[2, 0] = 0  # The previous chunk was flushed; global ordering still required.
    with pytest.raises(ValueError):
        store = spool(tmp_path, q, monkeypatch)
        try:
            store.seal()
        finally:
            store.close()


def test_quote_and_path_caps_refuse_without_thinning_or_partial_success(tmp_path, monkeypatch):
    q = quotes([(0, 0, 1), (1, 0, 1), (15, 0, 1)])
    monkeypatch.setattr(resource, "MAX_QUOTES", 2)
    with pytest.raises(ValueError, match="quote bound"):
        spool(tmp_path, q, monkeypatch)
    monkeypatch.setattr(resource, "MAX_QUOTES", 10)
    (tmp_path / "other").mkdir()
    store = spool(tmp_path / "other", q, monkeypatch)
    monkeypatch.setattr(resource, "MAX_PATH_QUOTES", 2)
    with store.seal() as view:
        with pytest.raises(ValueError, match="slice"):
            view[:]
        with pytest.raises(ValueError, match="slice"):
            view[::2]
        assert len(view[:2]) == 2


def test_changed_column_lengths_and_empty_spool_refuse_and_release_maps(tmp_path, monkeypatch):
    store = spool(tmp_path, quotes([(0, 0, 1), (15, 0, 1)]), monkeypatch)
    with store.seal():
        pass
    (store.directory / "ask.i64").write_bytes(b"bad")
    with pytest.raises(ValueError, match="length"):
        resource.QuoteView(store.directory, store.count)
    # The previously opened timestamp/bid mappings must have been closed after the error.
    (store.directory / "ts.i64").write_bytes(b"replacement")
    with pytest.raises(ValueError, match="count"):
        resource.QuoteView(store.directory, 0)


@pytest.mark.parametrize(
    "day,contract", [("2025-04-07", "6EM5"), ("2025-07-07", "6EU5"), ("2025-10-06", "6EZ5")]
)
def test_disk_builder_exactly_reproduces_original_rows_cases_and_quality(tmp_path, day, contract):
    old = resource.census.DailyBuilder(day, contract)
    new = resource.DiskDailyBuilder(day, contract, tmp_path / "quotes")
    old.start_day(date.fromisoformat(day))
    new.start_day(date.fromisoformat(day))
    try:
        for record in records_for(date.fromisoformat(day), contract):
            old.consume(record)
            new.consume(record)
        old.finish_day()
        new.finish_day()
        expected = old.finish()
        actual = new.finish()
        assert actual == expected
        assert len(new.quote_buffer) == 0  # The inherited whole-day buffer is never populated.
        assert new.spool.count == len(old.quote_buffer) // 3
        assert resource.census.encode_rows(actual[0]) == resource.census.encode_rows(expected[0])
        with pytest.raises(ValueError, match="across"):
            new.start_day(date(2025, 4, 8))
    finally:
        new.spool.close()


def test_original_quote_cap_stays_frozen_while_disk_builder_has_separate_bound(
    tmp_path, monkeypatch
):
    day = "2025-04-07"
    old = resource.census.DailyBuilder(day, "6EM5")
    new = resource.DiskDailyBuilder(day, "6EM5", tmp_path / "quotes")
    for builder in (old, new):
        builder.start_day(date.fromisoformat(day))
    monkeypatch.setattr(resource.paths, "MAX_QUOTES", 1)
    with pytest.raises(ValueError, match="Daily completed quote bound"):
        for record in records_for(date.fromisoformat(day), "6EM5"):
            old.consume(record)
    try:
        for record in records_for(date.fromisoformat(day), "6EM5"):
            new.consume(record)
        new.finish_day()
        assert new.finish()[0]
    finally:
        new.spool.close()


@pytest.fixture
def evidence(census_root, monkeypatch):
    census = resource.census
    monkeypatch.setattr(resource, "CONTROL_DAY", "2025-04-07")
    monkeypatch.setattr(resource, "RESOURCE_DAY", "2025-04-08")
    original = census.replay_day

    def iterator(archive, member):
        yield from records_for(date.fromisoformat(member["utc_date"]), member["contract"])

    monkeypatch.setattr(census.source, "_member_records", iterator)

    def replay(member):
        if member["utc_date"] == resource.RESOURCE_DAY:
            raise ValueError("Daily completed quote bound exceeded")
        return original(member)

    monkeypatch.setattr(census, "replay_day", replay)
    path, pin, directory = setup_run(census_root)
    census.run(census_root, path, pin, directory)
    monkeypatch.setattr(resource.diagnostic, "REGISTRATION", str(path))
    monkeypatch.setattr(resource.diagnostic, "REGISTRATION_PIN", pin)
    monkeypatch.setattr(resource.diagnostic, "CENSUS_DIRECTORY", str(directory))
    monkeypatch.setattr(
        resource.diagnostic,
        "RECEIPT_PIN",
        resource.common.hash_file(
            directory / "completion.json", resource.diagnostic.MAX_REPORT_BYTES
        ),
    )
    registration = census_root / "resource-registration.json"
    resource.prepare(census_root, registration)
    return (
        census_root,
        registration,
        resource.common.hash_file(registration, resource.diagnostic.MAX_REPORT_BYTES),
        census_root / "data/processed/resource",
    )


def test_registered_control_parity_and_whole_resource_completion(evidence):
    root, path, pin, output = evidence
    result = resource.run(root, path, pin, output)
    assert result["status"] == "resource_correction_completed_not_strategy_validated"
    assert [r["utc_date"] for r in result["reports"]] == [
        resource.CONTROL_DAY,
        resource.RESOURCE_DAY,
    ]
    for entry in result["reports"]:
        day = entry["utc_date"]
        report = resource.review.pinned(output / f"{day}.json", entry["report_sha256"])
        assert report["completed_quotes"] > 100
        assert report["full_member_hash_verified"] is True
        assert report["training_eligible"] is False
        for column, metadata in report["quote_columns"].items():
            assert metadata["bytes"] == report["completed_quotes"] * 8
            assert metadata["sha256"] == resource.common.hash_file(
                output / f"{day}.quotes/{column}.i64", resource.MAX_QUOTES * 8
            )
        for kind in ("rows", "cases"):
            assert report[f"{kind}_sha256"] == resource.common.hash_file(
                output / f"{day}.{kind}.jsonl", resource.census.MAX_DAY_BYTES
            )
    for key in (
        "original_census_modified",
        "quality_gate_changed",
        "reserved_raw_opened",
        "training_enabled",
        "trading_enabled",
        "promotion_enabled",
    ):
        assert result[key] is False
    with pytest.raises(ValueError, match="new"):
        resource.run(root, path, pin, output)


def test_control_parity_mismatch_stops_before_resource_day_without_subset_receipt(
    evidence, monkeypatch
):
    root, path, pin, output = evidence
    original = resource.replay_day
    calls = []

    def replay(member, quotes):
        calls.append(member["utc_date"])
        rows, cases, metadata = original(member, quotes)
        rows[0]["strategy"] = "changed"
        return rows, cases, metadata

    monkeypatch.setattr(resource, "replay_day", replay)
    with pytest.raises(ValueError, match="control"):
        resource.run(root, path, pin, output)
    assert calls == [resource.CONTROL_DAY]
    assert (output / "failure.json").exists()
    assert not (output / "completion.json").exists()


def test_second_day_failure_retains_control_but_never_claims_success(evidence, monkeypatch):
    root, path, pin, output = evidence
    original = resource.replay_day

    def replay(member, quotes):
        if member["utc_date"] == resource.RESOURCE_DAY:
            raise ValueError("Synthetic bad source flag")
        return original(member, quotes)

    monkeypatch.setattr(resource, "replay_day", replay)
    with pytest.raises(ValueError, match="bad source"):
        resource.run(root, path, pin, output)
    assert (output / f"{resource.CONTROL_DAY}.json").exists()
    assert (output / f"{resource.RESOURCE_DAY}.attempt.json").exists()
    assert not (output / "completion.json").exists()
    failure = resource.common.loads((output / "failure.json").read_bytes())
    assert failure["completed_dates"] == 1
    assert failure["automatic_retry"] is False


def test_reserved_member_refused_before_raw_or_quote_output(tmp_path, monkeypatch):
    monkeypatch.setattr(resource.zipfile, "ZipFile", lambda *a: pytest.fail("raw opened"))
    with pytest.raises(ValueError, match="Reserved"):
        resource.replay_day({"utc_date": "2026-01-01"}, tmp_path / "quotes")
    assert not (tmp_path / "quotes").exists()


@pytest.mark.parametrize("kind", ["disk", "policy", "implementation"])
def test_disk_or_registration_drift_refuses_before_new_output(evidence, monkeypatch, kind):
    root, path, pin, output = evidence
    if kind == "disk":
        monkeypatch.setattr(resource.shutil, "disk_usage", lambda *a: SimpleNamespace(free=0))
    elif kind == "policy":
        monkeypatch.setattr(resource, "MAX_PATH_QUOTES", 10)
    else:
        monkeypatch.setattr(resource, "fingerprints", lambda: {})
    monkeypatch.setattr(resource, "replay_day", lambda *a: pytest.fail("raw opened"))
    with pytest.raises(ValueError):
        resource.run(root, path, pin, output)
    assert not output.exists()


def test_per_day_timeout_retains_attempt_and_closes_quote_files(evidence, monkeypatch):
    root, path, pin, output = evidence
    frozen = resource.registration(root, path, pin)
    monkeypatch.setattr(resource.census, "MAX_DAY_SECONDS", -1)
    member = frozen["scope"]["members"][0]
    with pytest.raises(TimeoutError):
        resource.replay_day(member, root / "timeout-quotes")
    (root / "timeout-quotes/ts.i64").write_bytes(b"closed handle verified")
