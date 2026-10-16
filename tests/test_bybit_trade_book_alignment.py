"""Offline, source-time-only trade/book alignment tests with synthetic archives."""

from __future__ import annotations

import gzip
import hashlib
import json
from copy import deepcopy
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from ai_trader.research.bybit_trade_book_alignment import audit_alignment

START = 1790208000000
END = 1790294400000
BOOK_NAME = "2026-09-24_BTCUSDT_ob200.data.zip"


def book_event(kind, timestamp, update_id, sequence, bid_size):
    return {
        "topic": "orderbook.200.BTCUSDT",
        "ts": timestamp,
        "type": kind,
        "data": {
            "s": "BTCUSDT",
            "b": [["99", bid_size]],
            "a": [["101", "1"]],
            "u": update_id,
            "seq": sequence,
        },
        "cts": timestamp - 2,
    }


def book_records():
    return [
        book_event("snapshot", START + 10, 10, 100, "1"),
        book_event("delta", START + 100, 11, 101, "2"),
        book_event("delta", END + 16, 12, 102, "3"),
        book_event("snapshot", END + 16, 12, 102, "3"),
    ]


def trade_records():
    return [
        ["1", str(START + 5), "100", "0.1", "buy", "1"],
        ["2", str(START + 10), "100", "0.2", "sell", "0"],
        ["3", str(START + 100), "100", "0.3", "buy", "0"],
        ["4", str(START + 101), "100", "0.4", "sell", "0"],
    ]


def archives(tmp_path, *, trades=None, books=None, header=None):
    book_path = tmp_path / BOOK_NAME
    with ZipFile(book_path, "w", compression=ZIP_DEFLATED) as output:
        output.writestr(
            BOOK_NAME.removesuffix(".zip"),
            "".join(json.dumps(item) + "\n" for item in books or book_records()),
        )
    trade_path = tmp_path / "BTCUSDT_2026-09-24.csv.gz"
    lines = [header or "id,timestamp,price,volume,side,rpi"]
    lines.extend(",".join(row) for row in trades or trade_records())
    with gzip.open(trade_path, "wb") as output:
        output.write(("\n".join(lines) + "\n").encode())
    return (
        trade_path,
        hashlib.sha256(trade_path.read_bytes()).hexdigest(),
        book_path,
        hashlib.sha256(book_path.read_bytes()).hexdigest(),
    )


def audit(paths):
    return audit_alignment(*paths, "2026-09-24")


def test_strict_prior_join_withholds_same_timestamp_and_boundary_book(tmp_path):
    report = audit(archives(tmp_path))

    assert report["status"] == "source_time_alignment_audited_research_only"
    assert report["trade_rows"] == 4
    assert report["book_messages"] == 4
    assert report["post_boundary_book_messages"] == 2
    assert report["book_messages_not_eligible_for_any_trade"] == 2
    assert report["trades_without_strictly_prior_book"] == 2
    assert report["trades_with_equal_timestamp_book_withheld"] == 2
    assert report["strictly_prior_book_age_counts"] == {"1_to_100_ms": 2}
    assert report["strictly_prior_book_age_min_ms"] == 1
    assert report["strictly_prior_book_age_max_ms"] == 90
    assert report["observed_rpi_counts"] == {"1": 1, "0": 3}
    assert report["book_ts_minus_cts_min_ms"] == 2
    assert report["training_allowed"] is False
    assert report["paper_trading_allowed"] is False


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (lambda rows: rows[0].__setitem__(3, "NaN"), "price or volume"),
        (lambda rows: rows[0].__setitem__(4, "unknown"), "side"),
        (lambda rows: rows[0].__setitem__(1, str(END)), "outside"),
        (lambda rows: rows[3].__setitem__(1, str(START + 50)), "regressed"),
    ],
)
def test_rejects_invalid_trade_data(tmp_path, change, match):
    trades = deepcopy(trade_records())
    change(trades)
    with pytest.raises(ValueError, match=match):
        audit(archives(tmp_path, trades=trades))


def test_rejects_changed_trade_pin_and_wrong_header(tmp_path):
    trade_path, sha256, book_path, book_sha256 = archives(tmp_path)
    with pytest.raises(ValueError, match="pinned SHA256"):
        audit_alignment(trade_path, "0" * 64, book_path, book_sha256, "2026-09-24")
    assert len(sha256) == 64

    paths = archives(tmp_path, header="id,timestamp,price,qty,side,rpi")
    with pytest.raises(ValueError, match="header"):
        audit(paths)


def test_rejects_book_sequence_gap_before_cross_stream_alignment(tmp_path):
    books = book_records()
    books[1]["data"]["u"] = 13
    paths = archives(tmp_path, books=books)

    with pytest.raises(ValueError, match="nonconsecutive"):
        audit(paths)


def test_reports_row_id_discontinuity_without_calling_it_a_missing_execution(tmp_path):
    trades = trade_records()
    trades[2][0] = "8"
    paths = archives(tmp_path, trades=trades)

    assert audit(paths)["trade_id_discontinuities"] == 2
