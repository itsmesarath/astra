"""Calendar protection, explicit dated contracts and immutable research attempts."""

import hashlib
import json
import zipfile
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import databento_dbn as dbn
import pytest
from test_6e_cost_baseline import ASK, BID

from ai_trader.research import historical_6e_cohort as cohort


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = cohort.common.canonical(value)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def metadata_root(tmp_path, monkeypatch):
    batches = []
    for i, block in enumerate(cohort.BLOCKS):
        archive = tmp_path / f"source{i}.zip"
        with zipfile.ZipFile(archive, "w"):
            pass
        batches.append(
            {
                "archive": str(archive),
                "archive_bytes": archive.stat().st_size,
                "archive_sha256": "a" * 64,
                "files": [
                    {
                        "date": d,
                        "filename": f"{d}.dbn.zst",
                        "bytes": 1,
                        "sha256": "b" * 64,
                        "condition": "available",
                    }
                    for d in block.source_days
                ],
            }
        )
    intake = {
        "status": "integrity_and_headers_verified_event_quality_review_required",
        "batches": batches,
    }
    pin = write_json(tmp_path / cohort.INTAKE, intake)
    monkeypatch.setattr(cohort, "INTAKE_SHA256", pin)
    block = cohort.BLOCKS[0]
    evidence = {
        "sessions": list(block.sessions),
        "source": {
            "members": [
                {"utc_date": d, "member_sha256_verified_during_replay": "b" * 64}
                for d in block.source_days
            ]
        },
    }
    name = "prior.json"
    pin = write_json(tmp_path / name, evidence)
    monkeypatch.setattr(cohort, "EXPOSURE_EVIDENCE", {name: pin})
    return tmp_path


@pytest.mark.parametrize(
    "day,role",
    [
        ("2025-12-31", "development"),
        ("2026-01-01", "validation_reserved"),
        ("2026-03-31", "validation_reserved"),
        ("2026-04-01", "test_reserved"),
        ("2026-06-30", "test_reserved"),
        ("2026-07-01", "lockbox_reserved"),
        ("2026-09-25", "lockbox_reserved"),
    ],
)
def test_calendar_owners_are_exclusive(day, role):
    assert cohort.partition(day) == role


@pytest.mark.parametrize("day", ["2025-03-25", "2026-09-26", "20250101", "2026-02-30"])
def test_invalid_or_outside_calendar_rejected(day):
    with pytest.raises(ValueError):
        cohort.partition(day)


@pytest.mark.parametrize("contract", ["6E.FUT", "6E.c.0", "6EM5-6EU5", "BTCUSDT", "6EM25"])
def test_parent_continuous_and_spread_symbols_rejected(contract):
    with pytest.raises(ValueError, match="dated outright"):
        replace(cohort.BLOCKS[0], contract=contract).validate()


def test_reserved_dates_refused_before_source_access(tmp_path, monkeypatch):
    monkeypatch.setattr(cohort.source, "selected_sources", lambda *a: pytest.fail("source access"))
    block = cohort.Block("test", "6EM6", ("2026-04-06", "2026-04-07", "2026-04-08"))
    with pytest.raises(ValueError, match="Reserved"):
        cohort.replay_block(tmp_path, block)


def test_duplicate_and_overlapping_blocks_rejected():
    a, b, c = cohort.BLOCKS
    for blocks in ((a, b, a), (b, a, c), (a, replace(a, name="duplicate"), c)):
        with pytest.raises(ValueError):
            cohort.validate_blocks(blocks)
    # Adjacent sessions also share the previous UTC source day: refuse that overlap.
    next_block = cohort.Block("next", "6EM5", ("2025-04-10", "2025-04-11", "2025-04-14"))
    with pytest.raises(ValueError, match="overlap"):
        cohort.validate_blocks((a, next_block, c))


def test_no_cherry_picked_or_weekend_session_list():
    a = cohort.BLOCKS[0]
    for sessions in (
        ("2025-04-07", "2025-04-09", "2025-04-10"),
        ("2025-04-05", "2025-04-07", "2025-04-08"),
        a.sessions[:2],
    ):
        with pytest.raises(ValueError):
            replace(a, sessions=sessions).validate()


def test_preflight_never_opens_raw_and_does_not_certify_unseen(metadata_root, monkeypatch):
    monkeypatch.setattr(cohort.zipfile, "ZipFile", lambda *a: pytest.fail("raw archive opened"))
    result = cohort.preflight(metadata_root)
    assert result["prior_access_counts"] == {
        "outcomes_exposed": 3,
        "raw_replayed": 1,
        "no_replay_documented": 8,
    }
    assert result["raw_members_opened"] is False
    assert result["contract_mappings_verified"] is False
    assert len(result["selected_sources"]) == 3


def test_degraded_missing_and_duplicate_inventory_fail_whole_plan(metadata_root, monkeypatch):
    path = metadata_root / cohort.INTAKE
    original = json.loads(path.read_bytes())
    for kind in ("degraded", "missing", "duplicate"):
        value = deepcopy(original)
        members = value["batches"][-1]["files"]
        if kind == "degraded":
            members[-1]["condition"] = "degraded"
        elif kind == "missing":
            members.pop()
        else:
            members.append(deepcopy(members[-1]))
        monkeypatch.setattr(cohort, "INTAKE_SHA256", write_json(path, value))
        with pytest.raises(ValueError):
            cohort.preflight(metadata_root)


def test_exposure_mismatch_and_reserved_prior_access_rejected(metadata_root):
    intake = json.loads((metadata_root / cohort.INTAKE).read_bytes())
    prior = json.loads((metadata_root / "prior.json").read_bytes())
    prior["source"]["members"][0]["member_sha256_verified_during_replay"] = "c" * 64
    with pytest.raises(ValueError, match="differs"):
        cohort.exposure_ledger(intake, [prior])
    prior["source"]["members"] = [{"utc_date": "2026-04-06", "member_sha256": "b" * 64}]
    prior["sessions"] = ["2026-04-06"]
    intake["batches"][0]["files"].append(
        {"date": "2026-04-06", "condition": "available", "sha256": "b" * 64}
    )
    with pytest.raises(ValueError, match="reserved"):
        cohort.exposure_ledger(intake, [prior])


def test_frozen_registration_rejects_metadata_code_protocol_or_pin_drift(
    metadata_root, monkeypatch
):
    path = metadata_root / "registration.json"
    record = cohort.prepare(metadata_root, path)
    pin = cohort.common.hash_file(path, 1024**2)
    assert cohort.registration(metadata_root, path, pin) == record
    with pytest.raises(FileExistsError):
        cohort.prepare(metadata_root, path)
    with pytest.raises(ValueError, match="Pinned"):
        cohort.registration(metadata_root, path, "f" * 64)
    for field in ("implementation_sha256", "protocol", "preflight"):
        changed = deepcopy(record)
        changed[field] = {}
        new_pin = write_json(path, changed)
        with pytest.raises(ValueError, match="Frozen"):
            cohort.registration(metadata_root, path, new_pin)


def make_metadata(day, contract, instrument_id=42):
    return dbn.Metadata(
        dataset="GLBX.MDP3",
        schema=dbn.Schema.MBO,
        stype_in=dbn.SType.PARENT,
        stype_out=dbn.SType.INSTRUMENT_ID,
        start=cohort.source._utc_ns(day),
        end=cohort.source._utc_ns(day + timedelta(days=1)),
        symbols=["6E.FUT"],
        mappings=[
            SimpleNamespace(
                raw_symbol=contract,
                intervals=[
                    SimpleNamespace(
                        start_date=day, end_date=day + timedelta(days=1), symbol=str(instrument_id)
                    )
                ],
            )
        ],
    )


@pytest.mark.parametrize("block", cohort.BLOCKS)
def test_dated_contract_mapping_is_used_not_hardcoded_july(block):
    b = cohort.DatedExecutionBuilder(block)
    day = cohort.iso_day(block.sessions[0])
    b.start_day(day)
    b.consume(make_metadata(day, block.contract))
    assert b.instrument_id == 42
    assert b.contract == block.contract
    other = cohort.DatedExecutionBuilder(block)
    other.start_day(day)
    with pytest.raises(ValueError, match="dated outright mapping"):
        other.consume(make_metadata(day, "6EH5"))


def records_for(day, contract):
    yield make_metadata(day, contract)
    timestamp = cohort.source._utc_ns(day) + (12 * 3600 - 10) * cohort.source.SECOND_NS

    def message(action, side, price, qty, oid, at, flags):
        return dbn.MBOMsg(
            publisher_id=1,
            instrument_id=42,
            ts_event=at,
            ts_recv=at,
            order_id=oid,
            price=price,
            size=qty,
            action=dbn.Action.from_str(action),
            side=dbn.Side.from_str(side),
            flags=flags,
        )

    yield message("R", "N", 0, 0, 0, timestamp, dbn.F_SNAPSHOT)
    yield message("A", "B", BID, 10, 1, timestamp, dbn.F_SNAPSHOT)
    yield message("A", "A", ASK, 10, 2, timestamp, dbn.F_SNAPSHOT)
    for sec in range(140):
        at = timestamp + sec * cohort.source.SECOND_NS
        yield message("M", "B", BID, 10, 1, at, 0)
        yield message("M", "A", ASK, 10, 2, at, dbn.F_LAST)


def test_complete_synthetic_blocks_have_correct_contracts_and_no_state_carry(
    metadata_root, monkeypatch
):
    def iterator(archive, member):
        block = next(b for b in cohort.BLOCKS if member["day"].isoformat() in b.source_days)
        yield from records_for(member["day"], block.contract)

    monkeypatch.setattr(cohort.source, "_member_records", iterator)
    for block in cohort.BLOCKS:
        rows, report = cohort.replay_block(metadata_root, block)
        assert {r["contract"] for r in rows} == {block.contract}
        assert {r["source_session"] for r in rows} == set(block.sessions)
        assert {m["contract"] for m in report["dated_contract_mappings"]} == {block.contract}
        first = [r for r in rows if r["decision_ts_ns"] % cohort.source.DAY_NS == 12 * 3600 * 10**9]
        assert len(first) == 3
        assert first[0]["features"] == first[1]["features"] == first[2]["features"]
        assert all(sum(r["execution_features"].values()) == 0 for r in rows)
        assert all(
            r["net_targets_long_short_ticks"] == [-2, -2]
            for r in rows
            if r["outcome"]["status"] == "resolved"
        )


@pytest.mark.parametrize("failure_index", [0, 1, 2])
def test_failure_claim_retains_exposure_and_forbids_rerun_or_subset(
    metadata_root, monkeypatch, failure_index
):
    registration = metadata_root / "registration.json"
    cohort.prepare(metadata_root, registration)
    pin = cohort.common.hash_file(registration, 1024**2)
    calls = []

    def fail(root, block):
        calls.append(block.name)
        if len(calls) - 1 == failure_index:
            raise ValueError("synthetic quality refusal")
        return [], {}

    monkeypatch.setattr(cohort, "replay_block", fail)
    rows, report = metadata_root / "rows.jsonl", metadata_root / "report.json"
    with pytest.raises(ValueError, match="quality refusal"):
        cohort.run(metadata_root, registration, pin, rows, report)
    assert not rows.exists() and not report.exists()
    attempt = json.loads(registration.with_suffix(".attempt.json").read_bytes())
    assert len(attempt["conservatively_exposed_source_days"]) == 12
    failure = json.loads(registration.with_suffix(".failure.json").read_bytes())
    assert failure["status"] == "failed_whole_cohort"
    with pytest.raises(FileExistsError):
        cohort.run(metadata_root, registration, pin, rows, report)
    assert calls == [b.name for b in cohort.BLOCKS[: failure_index + 1]]


def test_existing_outputs_refused_before_registration_or_raw_access(tmp_path, monkeypatch):
    rows = tmp_path / "rows"
    rows.write_text("existing evidence")
    monkeypatch.setattr(cohort, "registration", lambda *a: pytest.fail("too late"))
    with pytest.raises(ValueError, match="overwrite"):
        cohort.run(tmp_path, tmp_path / "reg", "0" * 64, rows, tmp_path / "report")
    assert rows.read_text() == "existing evidence"


def test_july_exact_regression_rejects_change_and_missing_rows(tmp_path, monkeypatch):
    raw = {"source_session": "2025-07-07", "features": {"a": 1}, "outcome": {"status": "x"}}
    path = tmp_path / cohort.JULY_ROWS
    pin = write_json(path, raw)
    monkeypatch.setattr(cohort, "JULY_SHA256", pin)
    new = {**raw, "block": "july_2025", "partition": "development", "contract": "6EU5"}
    cohort.verify_july(tmp_path, [new])
    for rows in ([], [new, new], [{**new, "features": {"a": 2}}]):
        with pytest.raises(ValueError):
            cohort.verify_july(tmp_path, rows)


def test_complete_run_publishes_all_blocks_only_after_checks(metadata_root, monkeypatch):
    def iterator(archive, member):
        block = next(b for b in cohort.BLOCKS if member["day"].isoformat() in b.source_days)
        yield from records_for(member["day"], block.contract)

    monkeypatch.setattr(cohort.source, "_member_records", iterator)
    prior, _ = cohort.replay_block(metadata_root, cohort.BLOCKS[1])
    path = metadata_root / cohort.JULY_ROWS
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = b"".join(
        cohort.common.canonical(
            {k: v for k, v in r.items() if k not in {"block", "contract", "partition"}}
        )
        + b"\n"
        for r in prior
    )
    path.write_bytes(raw)
    monkeypatch.setattr(cohort, "JULY_SHA256", hashlib.sha256(raw).hexdigest())
    registration = metadata_root / "registration.json"
    cohort.prepare(metadata_root, registration)
    pin = cohort.common.hash_file(registration, 1024**2)
    rows, report = metadata_root / "rows.jsonl", metadata_root / "report.json"
    result = cohort.run(metadata_root, registration, pin, rows, report)
    assert result["status"] == "completed"
    assert len(result["by_session"]) == 9 and len(result["by_block"]) == 3
    assert result["rows_sha256"] == hashlib.sha256(rows.read_bytes()).hexdigest()
    assert result["training_enabled"] is result["trading_enabled"] is False
    assert json.loads(report.read_bytes()) == result
    assert not registration.with_suffix(".failure.json").exists()


@pytest.mark.parametrize("suffix", [".attempt.json", ".failure.json"])
def test_outputs_cannot_alias_attempt_or_failure_paths(tmp_path, suffix, monkeypatch):
    registration = tmp_path / "registration.json"
    monkeypatch.setattr(cohort, "registration", lambda *a: pytest.fail("too late"))
    with pytest.raises(ValueError, match="overwrite"):
        cohort.run(
            tmp_path, registration, "0" * 64, registration.with_suffix(suffix), tmp_path / "report"
        )
