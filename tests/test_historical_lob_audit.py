"""Synthetic sequence-audit tests; no source archive values are used."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from ai_trader.ingestion import hf_lob_intake as intake
from ai_trader.research import historical_lob_audit as module

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")


def _write_archive(path, kind):
    timestamps = [1577836800000 + index for index in range(300)]
    columns = {
        "timestamp_ms": timestamps,
        "asset": ["BTCUSDT"] * len(timestamps),
        "exchange": ["binance"] * len(timestamps),
    }
    if kind == "snapshots":
        columns.update(
            side=["bid"] * len(timestamps),
            last_update_id=[index * 10 for index in range(len(timestamps))],
        )
    elif kind == "trades":
        columns.update(
            trade_id=[1, 2, 4] + [index + 5 for index in range(297)],
            buyer_maker=[False] * len(timestamps),
        )
    else:
        columns.update(
            side=["bid"] * len(timestamps),
            first_update_id=[1, 3] + [index + 4 for index in range(298)],
            last_update_id=[1, 3] + [index + 4 for index in range(298)],
        )
    pq.write_table(pa.table(columns), path)
    raw = path.read_bytes()
    return {
        "kind": kind,
        "path": f"{kind}/binance/BTCUSDT/2020-01.parquet",
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _plan(directory):
    files = [
        _write_archive(directory / f"{kind}.parquet", kind)
        for kind in ("snapshots", "trades", "depth")
    ]
    value = json.loads(Path("configs/hf_btcusdt_lob_pilot_v1.json").read_text())
    value.update(month="2020-01", maximum_total_bytes=50_000_000, files=files)
    value["revision"] = "a" * 40
    (directory / "plan.json").write_bytes(intake._canonical(value))
    return value


def test_registered_audit_retains_full_scan_but_bounds_snapshot_anchors(tmp_path):
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan_request.json"
    plan_path.write_bytes(intake._canonical(plan))
    registration_path = tmp_path / "registration.json"
    registration_sha = module.register_audit(plan_path, registration_path)
    report_path = tmp_path / "report.json"

    report = module.audit_registered(registration_path, registration_sha, tmp_path, report_path)

    assert report["status"] == "sequence_audit_complete_training_blocked"
    assert report["all_declared_sources_fully_scanned"] is True
    assert report["training_started"] is False
    assert report["epochs_completed"] == report["labels_generated"] == 0
    assert report["snapshot_anchor_groups_scanned"] == 300
    assert report["snapshot_anchor_groups_retained"] == module.MAX_ANCHORS
    assert report["snapshot_anchor_sampling_truncated"] is True
    by_kind = {item["kind"]: item for item in report["files"]}
    assert by_kind["snapshots"]["rows_scanned"] == 300
    assert by_kind["trades"]["rows_scanned"] == 300
    assert by_kind["depth"]["rows_scanned"] == 300
    assert by_kind["trades"]["counts"]["forward_id_gaps"] == 1
    assert by_kind["depth"]["counts"]["forward_id_gaps"] == 1
    assert by_kind["snapshots"]["counts"]["forward_id_gaps"] == 0
    assert by_kind["trades"]["observed_run_count"] == 2
    assert len(by_kind["trades"]["segments"]) == 2
    assert by_kind["trades"]["segments_truncated"] is False
    assert by_kind["trades"]["segments"][0]["first_source_row"] == 0
    assert by_kind["trades"]["segments"][1]["first_source_row"] == 2
    assert report["price_quantity_columns_read"] is False
    assert report["receipt_clock_reconstructed"] is False
    assert report["book_reconstructed"] is False


def test_register_audit_is_metadata_only_and_no_replacement(tmp_path):
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan_request.json"
    plan_path.write_bytes(intake._canonical(plan))
    registration_path = tmp_path / "registration.json"
    first = module.register_audit(plan_path, registration_path)
    assert isinstance(first, str) and len(first) == 64
    with pytest.raises(FileExistsError):
        module.register_audit(plan_path, registration_path)


def test_protocol_rejects_changed_plan_or_code(tmp_path):
    plan = _plan(tmp_path)
    plan_path = tmp_path / "plan_request.json"
    plan_path.write_bytes(intake._canonical(plan))
    registration_path = tmp_path / "registration.json"
    registration_sha = module.register_audit(plan_path, registration_path)
    changed = deepcopy(plan)
    changed["known_limitations"] = ["changed"]
    (tmp_path / "plan.json").write_bytes(intake._canonical(changed))
    with pytest.raises(ValueError, match="differs"):
        module.audit_registered(
            registration_path, registration_sha, tmp_path, tmp_path / "report.json"
        )
