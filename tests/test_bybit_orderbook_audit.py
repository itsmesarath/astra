"""Synthetic, offline checks for the pinned Bybit OB200 reconstruction audit."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from ai_trader.research.bybit_orderbook_audit import audit_archive

START = 1790208000000
END = 1790294400000
NAME = "2026-09-24_BTCUSDT_ob200.data.zip"


def event(kind, timestamp, update_id, sequence, bids, asks):
    return {
        "topic": "orderbook.200.BTCUSDT",
        "ts": timestamp,
        "type": kind,
        "data": {
            "s": "BTCUSDT",
            "b": bids,
            "a": asks,
            "u": update_id,
            "seq": sequence,
        },
        "cts": timestamp,
    }


def records():
    return [
        event(
            "snapshot",
            START + 16,
            10,
            100,
            [["99", "1"], ["98", "1"]],
            [["101", "1"], ["102", "1"]],
        ),
        event(
            "delta",
            START + 100,
            11,
            101,
            [["99", "2"]],
            [["102", "0"], ["103", "1"]],
        ),
        event(
            "delta",
            END + 16,
            12,
            102,
            [["98", "0"], ["97", "1"]],
            [["101", "1.5"]],
        ),
        event(
            "snapshot",
            END + 16,
            12,
            102,
            [["99", "2"], ["97", "1"]],
            [["101", "1.5"], ["103", "1"]],
        ),
    ]


def archive(tmp_path, events, *, member_name=None):
    path = tmp_path / NAME
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as output:
        output.writestr(
            member_name or NAME.removesuffix(".zip"),
            "".join(json.dumps(item) + "\n" for item in events),
        )
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_reconstructs_pinned_archive_and_reports_boundary_without_trimming(tmp_path):
    path, sha256 = archive(tmp_path, records())

    report = audit_archive(path, sha256, "2026-09-24")

    assert report["status"] == "reconstruction_verified_research_only"
    assert (report["messages"], report["snapshots"], report["deltas"]) == (4, 2, 2)
    assert report["matched_snapshots"] == 1
    assert report["post_boundary_messages"] == 2
    assert report["final_best_bid"] == "99"
    assert report["final_best_ask"] == "101"
    assert report["training_allowed"] is False
    assert report["paper_trading_allowed"] is False


def test_accepts_large_delta_change_list_when_final_book_remains_200_levels(tmp_path):
    items = records()
    items[1]["data"]["b"] = [
        *[[str(price), "0"] for price in range(1000, 1400)],
        ["99", "2"],
    ]
    path, sha256 = archive(tmp_path, items)

    assert audit_archive(path, sha256, "2026-09-24")["matched_snapshots"] == 1


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda rows: rows[1]["data"].update(u=13), "nonconsecutive"),
        (lambda rows: rows[1]["data"].update(seq=99), "sequence regressed"),
        (lambda rows: rows[3]["data"]["b"][0].__setitem__(1, "3"), "differs"),
        (lambda rows: rows[1]["data"].update(s="ETHUSDT"), "symbol"),
        (lambda rows: rows[1]["data"]["b"].append(["99", "3"]), "duplicate"),
        (lambda rows: rows[1]["data"]["b"][0].__setitem__(1, "NaN"), "Invalid"),
        (lambda rows: rows[2].update(ts=END + 1001), "outside"),
        (lambda rows: rows[1]["data"]["a"].append(["98", "1"]), "crossed"),
        (lambda rows: rows.pop(3), "closing snapshot"),
        (lambda rows: rows.pop(0), "Missing snapshot"),
    ],
)
def test_refuses_unverified_or_malformed_stream(tmp_path, mutate, match):
    items = deepcopy(records())
    mutate(items)
    path, sha256 = archive(tmp_path, items)

    with pytest.raises(ValueError, match=match):
        audit_archive(path, sha256, "2026-09-24")


def test_requires_exact_source_pin_and_zip_member_identity(tmp_path):
    path, sha256 = archive(tmp_path, records(), member_name="../unexpected.data")

    with pytest.raises(ValueError, match="pinned SHA256"):
        audit_archive(path, "0" * 64, "2026-09-24")
    with pytest.raises(ValueError, match="ZIP member identity"):
        audit_archive(path, sha256, "2026-09-24")


def test_rejects_malformed_date_and_intermediate_unbridged_snapshot(tmp_path):
    items = records()
    items[3]["data"].update(u=14, seq=103)
    path, sha256 = archive(tmp_path, items)

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        audit_archive(path, sha256, "2026/09/24")
    with pytest.raises(ValueError, match="Unbridged"):
        audit_archive(path, sha256, "2026-09-24")
