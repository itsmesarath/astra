"""Real SQLite files, separate connections and subprocess crash recovery."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal

import pytest
from test_trade_case import case, review

from ai_trader.trading.trade_journal import JournalConflict, JournalError, TradeJournal


def create(tmp_path, **kwargs):
    return TradeJournal.create(
        tmp_path / "journal.sqlite", run_id="run-1", mode="research_only", **kwargs
    )


def reopen(tmp_path, **kwargs):
    return TradeJournal(tmp_path / "journal.sqlite", run_id="run-1", mode="research_only", **kwargs)


def test_case_review_roundtrip_and_retries_across_restart(tmp_path):
    with create(tmp_path) as journal:
        assert journal.append_case(case()) is True
        assert journal.append_review("review-1", review()) is True
    with reopen(tmp_path) as journal:
        assert journal.get_case("case-1") == case()
        assert journal.get_review("review-1") == review()
        assert journal.append_case(case()) is False
        assert journal.append_review("review-1", review()) is False
        assert journal.review_ids("case-1") == ("review-1",)
        assert journal.get_case("missing") is None
        assert journal.get_review("missing") is None


def test_conflicting_case_cannot_rewrite_thesis(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        with pytest.raises(JournalConflict, match="different content"):
            journal.append_case(replace(case(), hypothesis="hindsight"))
        assert journal.get_case("case-1") == case()


def test_review_requires_exact_stored_case(tmp_path):
    with create(tmp_path) as journal:
        with pytest.raises(JournalConflict, match="exact stored case"):
            journal.append_review("review-1", review())
        journal.append_case(case())
        with pytest.raises(JournalConflict, match="exact stored case"):
            journal.append_review("review-1", review(case=replace(case(), hypothesis="changed")))
        assert journal.get_review("review-1") is None


def test_review_conflicts_and_explicit_revisions(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_review("review-1", review())
        revised = review(net_pnl_usdt=Decimal("1"), summary="Corrected accounting")
        with pytest.raises(JournalConflict):
            journal.append_review("review-1", revised)
        assert journal.append_review("review-2", revised)
        assert journal.review_ids("case-1") == ("review-1", "review-2")
        assert journal.get_review("review-1").net_pnl_usdt == Decimal("-1")


def test_one_trade_cannot_belong_to_two_cases(tmp_path):
    with create(tmp_path) as journal:
        other = replace(case(), case_id="case-2")
        journal.append_case(case())
        journal.append_case(other)
        journal.append_review("review-1", review())
        with pytest.raises(JournalConflict, match="another case"):
            journal.append_review("review-2", review(case=other))


def test_no_action_and_rejected_cases_are_preserved(tmp_path):
    rejected = replace(case(), risk_verdict="REJECTED", approved_quantity_btc=None)
    abstention = replace(rejected, case_id="no-action", action="NO_ACTION", plan=None)
    with create(tmp_path) as journal:
        journal.append_case(rejected)
        journal.append_case(abstention)
    with reopen(tmp_path, read_only=True) as journal:
        assert journal.get_case("case-1") == rejected
        assert journal.get_case("no-action") == abstention
        with pytest.raises(JournalError, match="read-only"):
            journal.append_case(rejected)


@pytest.mark.parametrize("mode", ["spot_live", "live", "spot_testnet", "", None])
def test_disallowed_mode_creates_no_file(tmp_path, mode):
    with pytest.raises(JournalError):
        TradeJournal.create(tmp_path / "journal.sqlite", run_id="run-1", mode=mode)
    assert not (tmp_path / "journal.sqlite").exists()


def test_run_mode_isolation_and_exclusive_creation(tmp_path):
    with create(tmp_path) as journal:
        with pytest.raises(JournalError, match="mode/type"):
            journal.append_case(replace(case(), mode="paper"))
    path = tmp_path / "journal.sqlite"
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        create(tmp_path)
    for run_id, mode in [("other", "research_only"), ("run-1", "paper")]:
        with pytest.raises(JournalError, match="identity"):
            TradeJournal(path, run_id=run_id, mode=mode)
    assert path.read_bytes() == before


def test_unknown_database_and_future_schema_are_not_migrated(tmp_path):
    path = tmp_path / "unrelated.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE private_data(value)")
    before = path.read_bytes()
    with pytest.raises(JournalError, match="Not an"):
        TradeJournal(path, run_id="run-1", mode="paper")
    assert path.read_bytes() == before
    with create(tmp_path):
        pass
    with sqlite3.connect(tmp_path / "journal.sqlite") as db:
        db.execute("PRAGMA user_version=999")
    with pytest.raises(JournalError, match="migration"):
        reopen(tmp_path)


def test_open_missing_does_not_create(tmp_path):
    with pytest.raises(sqlite3.OperationalError):
        reopen(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_sql_mutation_triggers_reject_update_and_delete(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_review("r", review())
        for table in ("metadata", "cases", "reviews"):
            for sql in (f"DELETE FROM {table}", f"UPDATE {table} SET rowid=rowid"):
                with pytest.raises(sqlite3.IntegrityError, match="Append-only"):
                    journal._db.execute(sql)
        assert journal.get_case("case-1") == case()


def test_payload_corruption_is_detected_not_silently_reused(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal._db.execute("DROP TRIGGER cases_no_update")
        journal._db.execute("UPDATE cases SET payload='{}'")
        with pytest.raises(JournalError, match="checksum"):
            journal.get_case("case-1")
        with pytest.raises(JournalError):
            journal.append_case(case())


def test_two_writers_same_record_commit_only_once(tmp_path):
    with create(tmp_path):
        pass

    def write(_):
        with reopen(tmp_path) as journal:
            return journal.append_case(case())

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(write, range(8)))
    assert results.count(True) == 1
    with reopen(tmp_path) as journal:
        assert journal.get_case("case-1") == case()


def test_failed_insert_rolls_back_and_connection_remains_usable(tmp_path):
    with create(tmp_path) as journal:
        journal._db.execute("""CREATE TRIGGER fail_insert BEFORE INSERT ON cases
                            BEGIN SELECT RAISE(ABORT, 'injected failure'); END""")
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            journal.append_case(case())
        assert journal.get_case("case-1") is None
        journal._db.execute("DROP TRIGGER fail_insert")
        assert journal.append_case(case())


def test_process_death_preserves_commits_and_rolls_back_inflight_write(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
    # Abrupt process termination, not a graceful context-manager rollback.
    script = """
import os, sqlite3, sys
db = sqlite3.connect(sys.argv[1], isolation_level=None)
db.execute('BEGIN IMMEDIATE')
db.execute('INSERT INTO cases VALUES (?, ?, ?, ?)', ('uncommitted', '{}', 'bad', 1))
os._exit(23)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "journal.sqlite")],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 23, result.stderr
    with reopen(tmp_path) as journal:
        assert journal.get_case("case-1") == case()
        assert journal.get_case("uncommitted") is None
        assert journal.append_review("r", review())


def test_injection_like_ids_are_plain_data(tmp_path):
    value = replace(case(), case_id="case'; DROP TABLE cases; --")
    with create(tmp_path) as journal:
        assert journal.append_case(value)
        assert journal.get_case(value.case_id) == value


def test_journal_does_not_access_network(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No network")

    monkeypatch.setattr("socket.socket", forbidden)
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_review("r", review())
        assert json.loads(journal.get_case("case-1").to_json())["case_id"] == "case-1"


def test_retry_preserves_original_recording_timestamp(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_review("r", review())
        before = journal._db.execute("SELECT recorded_at_ns FROM cases").fetchall()
        review_before = journal._db.execute("SELECT recorded_at_ns FROM reviews").fetchall()
        assert journal.append_case(case()) is False
        assert journal.append_review("r", review()) is False
        assert journal._db.execute("SELECT recorded_at_ns FROM cases").fetchall() == before
        assert journal._db.execute("SELECT recorded_at_ns FROM reviews").fetchall() == review_before


@pytest.mark.parametrize("change", ["future_evidence", "numeric_decimal", "unknown_field"])
def test_valid_checksum_cannot_hide_invalid_typed_payload(tmp_path, change):
    value = json.loads(case().to_json())
    if change == "future_evidence":
        value["evidence"][0]["available_at_ns"] = 9999
    elif change == "numeric_decimal":
        value["approved_quantity_btc"] = 0.001
    else:
        value["extra"] = "unexpected"
    payload = json.dumps(value, sort_keys=True)
    with create(tmp_path) as journal:
        journal._db.execute(
            "INSERT INTO cases VALUES (?, ?, ?, ?)",
            ("case-1", payload, hashlib.sha256(payload.encode()).hexdigest(), 1),
        )
        with pytest.raises(JournalError):
            journal.get_case("case-1")


def test_review_reads_validate_case_binding_again(tmp_path):
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_case(replace(case(), case_id="other"))
        journal.append_review("r", review())
        journal._db.execute("DROP TRIGGER reviews_no_update")
        journal._db.execute("UPDATE reviews SET case_id='other'")
        with pytest.raises(JournalError, match="binding"):
            journal.get_review("r")


def test_concurrent_trade_bindings_cannot_cross_cases(tmp_path):
    other = replace(case(), case_id="case-2")
    with create(tmp_path) as journal:
        journal.append_case(case())
        journal.append_case(other)

    def write(value):
        with reopen(tmp_path) as journal:
            try:
                journal.append_review(value.case_id, review(case=value))
                return "inserted"
            except JournalConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, (case(), other))) == ["conflict", "inserted"]
    with reopen(tmp_path) as journal:
        assert len(journal.review_ids("case-1")) + len(journal.review_ids("case-2")) == 1


def test_readonly_reader_sees_committed_writer_data(tmp_path):
    with create(tmp_path) as writer, reopen(tmp_path, read_only=True) as reader:
        assert reader.get_case("case-1") is None
        writer.append_case(case())
        assert reader.get_case("case-1") == case()


def test_closed_connection_cannot_claim_success(tmp_path):
    journal = create(tmp_path)
    journal.close()
    with pytest.raises(sqlite3.ProgrammingError):
        journal.append_case(case())


def test_paper_journal_can_only_store_paper_cases(tmp_path):
    with TradeJournal.create(
        tmp_path / "paper.sqlite", run_id="paper-run", mode="paper"
    ) as journal:
        paper_case = replace(case(), mode="paper")
        assert journal.append_case(paper_case)
        assert journal.append_review("r", review(case=paper_case))
        with pytest.raises(JournalError):
            journal.append_case(case())
