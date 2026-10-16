"""Small synthetic contracts for the Kaggle-specific L2 reconstruction audit."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

pa = pytest.importorskip("pyarrow")
parquet = pytest.importorskip("pyarrow.parquet")

from ai_trader.research.kaggle_binance_l2_audit import (  # noqa: E402
    FILES,
    _mismatch_detail,
    _parse_levels,
    audit,
)


def _book(*levels):
    return json.dumps([list(level) for level in levels])


def _write(tmp_path, *, gap=False, mismatch=False, coverage=False):
    ns = 1_776_470_400_000_000_000
    final = 20 if gap else 13
    snapshots = {
        "time": [ns + 2_000_000, ns + 4_000_000, ns + 6_000_000],
        "received_at": [ns + 3_000_000, ns + 5_000_000, ns + 7_000_000],
        "symbol": ["BTCUSDT"] * 3,
        "last_update_id": [11, 12, final],
        "bids": [
            _book(("99", "1"), *(("98", "1"),) if coverage else ()),
            _book(("99", "2"), *(("98", "1"),) if coverage else ()),
            _book(("98", "1"), ("97", "1"))
            if coverage
            else _book(("99", "9" if mismatch else "2"), ("98", "1")),
        ],
        "asks": [
            _book(("101", "1")),
            _book(("101", "1"), ("102", "1")),
            _book(("102", "1")),
        ],
    }
    diffs = {
        "time": [ns + 1_000_000, ns + 3_000_000, ns + 5_000_000],
        "received_at": [ns + 2_000_000, ns + 4_000_000, ns + 6_000_000],
        "symbol": ["BTCUSDT"] * 3,
        "first_update_id": [10, 12, final],
        "final_update_id": [11, 12, final],
        "bids": [
            _book(("99", "1")),
            _book(("99", "2")),
            _book(("99", "0")) if coverage else _book(("98", "1")),
        ],
        "asks": [
            _book(),
            _book(("102", "1")),
            _book(("101", "0")),
        ],
    }
    trades = {
        "time": [ns + 1_000_000, ns + 2_000_000, ns + 3_000_000],
        "received_at": [ns + 2_000_000, ns + 3_000_000, ns + 4_000_000],
        "trade_id": [1, 2, 3],
    }

    def table(values):
        columns = {
            name: pa.array(items, type=pa.timestamp("ns", tz="UTC"))
            if name in ("time", "received_at")
            else pa.array(items)
            for name, items in values.items()
        }
        return pa.table(columns)

    pins = {}
    for kind, rows in (("trades", trades), ("snapshots", snapshots), ("diffs", diffs)):
        path = tmp_path / FILES[kind]
        parquet.write_table(table(rows), path)
        pins[kind] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pins


def test_exact_snapshot_ids_match_replayed_top_levels(tmp_path):
    report = audit(tmp_path, _write(tmp_path))

    assert report["trades"]["rows"] == 3
    assert report["diffs"]["forward_gap_count"] == 0
    assert report["snapshots"]["matched_top20"] == 2
    assert report["snapshots"]["top20_mismatch_count"] == 0
    assert report["training_allowed"] is False


def test_gap_is_reported_and_next_snapshot_reanchors_without_claiming_match(tmp_path):
    report = audit(tmp_path, _write(tmp_path, gap=True))

    assert report["diffs"]["forward_gap_count"] == 1
    assert report["diffs"]["forward_gaps"][0]["missing_id_positions"] == 7
    assert report["snapshots"]["matched_top20"] == 1
    assert report["snapshots"]["unverified"] == 1


def test_mismatch_is_visible_and_source_pin_is_required(tmp_path):
    pins = _write(tmp_path, mismatch=True)
    report = audit(tmp_path, pins)

    assert report["snapshots"]["top20_mismatch_count"] == 1
    assert report["snapshots"]["consistent_with_truncated_prior_snapshot_count"] == 0
    with pytest.raises(ValueError, match="pinned SHA256"):
        audit(tmp_path, pins | {"diffs": "0" * 64})


@pytest.mark.parametrize("raw", ['[["99","NaN"]]', '[["99","1"],["99","2"]]', "{}"])
def test_rejects_invalid_level_json(raw):
    with pytest.raises(ValueError):
        _parse_levels(raw, snapshot=True)


def test_marks_prior_depth_limit_as_plausible_not_proven_cause():
    d = Decimal
    prior = ({d(99): d(1), d(98): d(1)}, {d(101): d(1)})
    observed = ({d(98): d(1)}, {d(101): d(1)})
    expected = ({d(98): d(1), d(97): d(1)}, {d(101): d(1)})

    detail = _mismatch_detail(observed, expected, prior)

    assert detail["consistent_with_truncated_prior_snapshot"] is True
    assert detail["missing_expected_bid_levels"] == 1


def test_audit_keeps_snapshot_anchors_immutable_for_coverage_diagnosis(tmp_path):
    report = audit(tmp_path, _write(tmp_path, coverage=True))

    assert report["snapshots"]["matched_top20"] == 1
    assert report["snapshots"]["top20_mismatch_count"] == 1
    assert report["snapshots"]["consistent_with_truncated_prior_snapshot_count"] == 1
