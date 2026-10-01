"""Opt-in clock revision preserves raw records, strict quality and causal features."""

import ast
import inspect
import json
import textwrap
from copy import deepcopy
from datetime import timedelta

import databento_dbn as dbn
import pytest
from test_6e_cost_baseline import BID
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for, write_json

from ai_trader.research import databento_6e_receive_clock as receive
from ai_trader.research import historical_6e_cohort as v1
from ai_trader.research import historical_6e_cohort_v2 as v2

BLOCK = v1.BLOCKS[1]
DAY = v1.iso_day(BLOCK.sessions[0])
START = v1.source._utc_ns(DAY)
WARMUP = START + (12 * 3600 - 10) * 10**9
END = START + 16 * 3600 * 10**9


def mbo(at, *, delta=0, send=0, flags=dbn.F_LAST, action="M", size=10, oid=1, instrument=42):
    return dbn.MBOMsg(
        publisher_id=1,
        instrument_id=instrument,
        ts_event=at + delta,
        ts_recv=at,
        ts_in_delta=send,
        order_id=oid,
        price=BID,
        size=size,
        action=dbn.Action.from_str(action),
        side=dbn.Side.BID,
        flags=flags,
    )


def seeded(kind=receive.ReceiveTimeBuilder):
    builder = kind(BLOCK, minimum_resolved=1)
    builder.start_day(DAY)
    for record in records_for(DAY, BLOCK.contract):
        if isinstance(record, dbn.MBOMsg) and record.ts_recv >= START + 12 * 3600 * 10**9:
            break
        builder.consume(record)
    return builder


def test_versioned_core_changes_only_the_cross_clock_check():
    old = ast.parse(textwrap.dedent(inspect.getsource(receive.clock.SecondsPilot.consume)))
    new = ast.parse(textwrap.dedent(inspect.getsource(receive.ReceiveClockCore.consume)))
    body = old.body[0].body
    matches = [
        i
        for i, node in enumerate(body)
        if isinstance(node, ast.If)
        and len(node.body) == 1
        and isinstance(node.body[0], ast.Raise)
        and "Target exchange timestamp is later than receive timestamp" in ast.unparse(node)
    ]
    assert len(matches) == 1
    body[matches[0]] = ast.parse("self.clock_audit.observe(item, snapshot)").body[0]
    assert ast.dump(old, include_attributes=False) == ast.dump(new, include_attributes=False)
    chain = receive.ReceiveTimeBuilder.__mro__
    index = chain.index(receive.ReceiveClockCore)
    assert chain[index + 1] is receive.clock.SecondsPilot
    assert v1.flow.ExecutionBuilder in chain[:index]
    assert v1.study.data.base.events.EventScalp in chain[:index]


@pytest.mark.parametrize(
    "at,protected",
    [(WARMUP - 1, False), (WARMUP, True), (END - 1, True), (END, False), (END + 1, False)],
)
@pytest.mark.parametrize("delta,send", [(1, 0), (0, -1), (10**12, -(2**31))])
def test_exact_warmup_and_end_boundaries_without_fitted_tolerance(at, protected, delta, send):
    audit = receive.ClockAudit(DAY.isoformat(), (WARMUP, END))
    record = mbo(at, delta=delta, send=send)
    original = bytes(record)
    if protected:
        with pytest.raises(ValueError, match="protected research interval"):
            audit.observe(record, False)
    else:
        audit.observe(record, False)
    assert bytes(record) == original
    assert audit.counts["disagreement_records"] == 1
    assert audit.samples[0]["ts_event_ns"] == at + delta


def test_reconstruction_day_audits_all_hours_and_bounded_samples():
    audit = receive.ClockAudit(DAY.isoformat(), None)
    for i in range(100):
        audit.observe(mbo(WARMUP + i, delta=i + 1, send=-1), False)
    assert audit.counts["outside_disagreements"] == 100
    assert audit.counts["protected_disagreements"] == 0
    assert len(audit.samples) == 8
    assert audit.min_event_ahead_ns == 1 and audit.max_event_ahead_ns == 100


@pytest.mark.parametrize("when", [WARMUP - 1, END])
def test_undefined_non_snapshot_event_refused_even_outside_window(when):
    audit = receive.ClockAudit(DAY.isoformat(), (WARMUP, END))
    with pytest.raises(ValueError, match="Undefined"):
        audit.observe(mbo(when, delta=dbn.UNDEF_TIMESTAMP - when), False)


def test_snapshots_are_not_cross_clock_compared_but_undefined_receive_is_rejected():
    audit = receive.ClockAudit(DAY.isoformat(), (WARMUP, END))
    audit.observe(mbo(WARMUP, delta=dbn.UNDEF_TIMESTAMP - WARMUP, send=-1), True)
    assert audit.counts["snapshots_not_clock_compared"] == 1
    with pytest.raises(ValueError, match="Undefined receive"):
        audit.observe(mbo(dbn.UNDEF_TIMESTAMP), True)


def test_protected_disagreement_refused_before_book_and_feature_mutation():
    b = seeded()
    before = deepcopy(b.book.orders)
    with pytest.raises(ValueError, match="protected"):
        b.consume(mbo(WARMUP + 10 * 10**9, delta=1, size=99, flags=0))
    assert b.book.orders == before and not b.rows


def test_post_window_disagreement_keeps_book_update_and_legacy_stays_strict():
    b = seeded()
    record = mbo(END + 1, delta=500_000_000, send=-600_000_000, size=19)
    original = bytes(record)
    b.consume(record)
    assert b.book.orders[1][2] == 19
    assert not b.rows
    assert b.clock_audit.counts["outside_disagreements"] == 1
    assert bytes(record) == original
    old = seeded(v1.DatedExecutionBuilder)
    with pytest.raises(ValueError, match="later than receive"):
        old.consume(record)


@pytest.mark.parametrize("flag", [dbn.F_BAD_TS_RECV, dbn.F_MAYBE_BAD_BOOK, dbn.F_TOB, dbn.F_MBP])
def test_bad_flags_stay_fatal_outside_research_window(flag):
    b = seeded()
    with pytest.raises(ValueError, match="quality flag"):
        b.consume(mbo(END, delta=1, flags=flag | dbn.F_LAST))


def test_receive_regression_and_bad_book_stay_fatal():
    b = seeded()
    b.consume(mbo(END + 2, delta=1))
    with pytest.raises(ValueError, match="regressed"):
        b.consume(mbo(END + 1, delta=1))
    b = seeded()
    with pytest.raises(ValueError):
        b.consume(mbo(END, delta=1, action="C", oid=999))


def test_incomplete_event_gate_stays_fatal_and_other_contract_is_ignored():
    b = seeded()
    b.consume(mbo(WARMUP + 10 * 10**9, delta=1, instrument=99))
    assert b.clock_audit.counts["disagreement_records"] == 0
    b.consume(mbo(END, delta=1, flags=0))
    with pytest.raises(ValueError, match="Incomplete"):
        b.finish_day()


@pytest.mark.parametrize("block", v1.BLOCKS)
def test_all_features_and_targets_match_v1_on_clean_synthetic_blocks(block):
    old, new = v1.DatedExecutionBuilder(block), receive.ReceiveTimeBuilder(block)
    for text in block.source_days:
        day = v1.iso_day(text)
        for b in (old, new):
            b.start_day(day)
        for record in records_for(day, block.contract):
            old.consume(record)
            new.consume(record)
        old.finish_day()
        new.finish_day()
    old_rows, old_quality = old.finish()
    new_rows, new_quality = new.finish()
    assert new_rows == old_rows
    audit = new_quality.pop("receive_clock_v2")
    assert new_quality == old_quality
    assert len(audit) == 4
    assert sum(d["counts"]["target_records"] for d in audit) == new_quality["target_records"]


def test_daily_audit_and_feature_state_reset():
    b = seeded()
    b.consume(mbo(END, delta=1))
    b.start_day(DAY + timedelta(days=1))
    assert not b.clock_audit.counts
    assert not b.execution.events and not b.book.orders
    assert not b.pending_rows and b.last_quote is None


@pytest.fixture
def v2_root(metadata_root, monkeypatch):
    root = metadata_root
    path = root / v2.diagnostic.REGISTRATION
    v1.prepare(root, path)
    pin = v1.common.hash_file(path, 1024**2)
    monkeypatch.setattr(v2.diagnostic, "REGISTRATION_PIN", pin)
    attempt = {
        "registration_sha256": pin,
        "conservatively_exposed_source_days": [d for b in v1.BLOCKS for d in b.source_days],
    }
    monkeypatch.setattr(v2, "ATTEMPT_PIN", write_json(path.with_suffix(".attempt.json"), attempt))
    failure = {"registration_sha256": pin, "status": "failed_whole_cohort"}
    monkeypatch.setattr(
        v2.diagnostic, "FAILURE_PIN", write_json(path.with_suffix(".failure.json"), failure)
    )
    monkeypatch.setattr(
        v2, "DIAGNOSTIC_PIN", write_json(root / v2.DIAGNOSTIC_PATH, {"registration_sha256": pin})
    )
    return root


def test_v2_preflight_incorporates_prior_attempt_without_opening_raw(v2_root, monkeypatch):
    monkeypatch.setattr(zipfile := v2.zipfile, "ZipFile", lambda *a: pytest.fail("raw access"))
    result = v2.preflight(v2_root)
    assert result["prior_access_counts"]["prior_attempt_conservatively_exposed"] == 8
    assert "no_replay_documented" not in result["prior_access_counts"]
    assert len(result["prior_attempt_conservative_exposure_days"]) == 12
    assert zipfile is v1.zipfile


def test_v2_registration_rejects_clock_policy_and_attempt_drift(v2_root):
    path = v2_root / "v2.json"
    record = v2.prepare(v2_root, path)
    pin = v1.common.hash_file(path, 1024**2)
    assert v2.registration(v2_root, path, pin) == record
    changed = deepcopy(record)
    changed["protocol"]["receive_clock_policy"]["inside"] = "allow everything"
    new_pin = write_json(path, changed)
    with pytest.raises(ValueError, match="registration"):
        v2.registration(v2_root, path, new_pin)
    attempt = (v2_root / v2.diagnostic.REGISTRATION).with_suffix(".attempt.json")
    attempt.write_text("{}")
    with pytest.raises(ValueError, match="Pinned"):
        v2.preflight(v2_root)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_v2_failure_keeps_evidence_and_never_publishes_subset(v2_root, monkeypatch, index):
    path = v2_root / "v2.json"
    v2.prepare(v2_root, path)
    pin = v1.common.hash_file(path, 1024**2)
    calls = []

    def replay(root, block):
        calls.append(block.name)
        if len(calls) == index + 1:
            raise ValueError("synthetic protected-clock failure")
        return [], {}

    monkeypatch.setattr(v2, "replay_block", replay)
    rows, report = v2_root / "rows", v2_root / "report"
    with pytest.raises(ValueError, match="protected-clock"):
        v2.run(v2_root, path, pin, rows, report)
    assert not rows.exists() and not report.exists()
    assert json.loads(path.with_suffix(".failure.json").read_bytes())["block"] == calls[-1]
    with pytest.raises(ValueError, match="reuse"):
        v2.run(v2_root, path, pin, rows, report)
    assert len(calls) == index + 1


def test_v2_complete_synthetic_replay_checks_regression_before_publication(v2_root, monkeypatch):
    def iterator(archive, member):
        block = next(b for b in v1.BLOCKS if member["day"].isoformat() in b.source_days)
        yield from records_for(member["day"], block.contract)

    monkeypatch.setattr(v2.source, "_member_records", iterator)
    verified = []

    def check(root, rows):
        assert {r["block"] for r in rows} == {b.name for b in v1.BLOCKS}
        assert {r["partition"] for r in rows} == {"development"}
        verified.append(True)

    monkeypatch.setattr(v1, "verify_july", check)
    path = v2_root / "v2.json"
    v2.prepare(v2_root, path)
    pin = v1.common.hash_file(path, 1024**2)
    rows, report = v2_root / "rows", v2_root / "report"
    result = v2.run(v2_root, path, pin, rows, report)
    assert verified == [True]
    assert json.loads(report.read_bytes()) == result
    assert v1.common.hash_file(rows, v1.MAX_OUTPUT_BYTES) == result["rows_sha256"]
    assert len(result["by_session"]) == 9
    assert sum(len(e["quality"]["receive_clock_v2"]) for e in result["evidence"]) == 12


def test_v2_reserved_source_refused_before_any_archive_access(tmp_path, monkeypatch):
    monkeypatch.setattr(v2.source, "selected_sources", lambda *a: pytest.fail("raw access"))
    block = v1.Block("reserved", "6EM6", ("2026-04-06", "2026-04-07", "2026-04-08"))
    with pytest.raises(ValueError, match="Reserved"):
        v2.replay_block(tmp_path, block)
