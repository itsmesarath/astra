"""Synthetic frozen-cohort checks for the offline 6E research baseline."""

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest

from ai_trader.training.train_6e_baseline import (
    CONFIG_SHA256,
    CONTRACT,
    EXPECTED_SESSIONS,
    FEATURE_NAMES,
    SOURCE_INTAKE_REPORT,
    SOURCE_INTAKE_SHA256,
    train_6e_baseline,
)

CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "configs/databento_6e_first_training_20261001.json"
)


def _rows():
    rows = []
    for session_index, session in enumerate(EXPECTED_SESSIONS):
        base = int(datetime.combine(date.fromisoformat(session), time(12), UTC).timestamp())
        for index in range(180):
            stamp = (base + index * 60) * 1_000_000_000
            rows.append(
                {
                    "source_session": session,
                    "decision_ts_ns": stamp,
                    "label_end_ts_ns": stamp + 60 * 1_000_000_000,
                    "contract": CONTRACT,
                    "spread_ticks": 1 + index,
                    "top_bid_qty": 10 + session_index,
                    "top_ask_qty": 20 + index,
                    "imbalance": (index - 1) / 2,
                    "cvd_rolling": index - 1,
                    "trade_count_rolling": 3 + index,
                    "cancel_imbalance_rolling": index / 4,
                    "replenishment_proxy": index / 2,
                    "label": (-1, 0, 1)[(session_index + index) % 3],
                }
            )
    return rows


def _files(tmp_path, rows, manifest_changes=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    raw = b"".join(
        (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode() for row in rows
    )
    rows_path = tmp_path / "features.jsonl"
    rows_path.write_bytes(raw)
    manifest = {
        "schema_version": 1,
        "artifact_type": "databento_6e_mbo_features_v1",
        "feature_names": list(FEATURE_NAMES),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "rows": len(rows),
        "contract": CONTRACT,
        "quality_passed": True,
        "held_dates": [],
        "first_session": EXPECTED_SESSIONS[0],
        "last_session": EXPECTED_SESSIONS[-1],
        "sessions": list(EXPECTED_SESSIONS),
        "config_sha256": CONFIG_SHA256,
        "source": {
            "intake_report": SOURCE_INTAKE_REPORT,
            "intake_sha256": SOURCE_INTAKE_SHA256,
            "experiment_config_sha256": CONFIG_SHA256,
            "members": [{"synthetic_test_only": True}],
        },
        "quality": {"rows_per_session": dict(Counter(row["source_session"] for row in rows))},
    }
    manifest.update(manifest_changes or {})
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return rows_path, manifest_path, tmp_path / "result.json"


def _run(tmp_path, rows=None, manifest_changes=None):
    paths = _files(tmp_path, _rows() if rows is None else rows, manifest_changes)
    return train_6e_baseline(
        rows_path=paths[0], manifest_path=paths[1], config_path=CONFIG_PATH, output_path=paths[2]
    ), paths


def test_fits_only_train_sessions_and_evaluates_reserved_after_fit(tmp_path):
    original, paths = _run(tmp_path / "a")
    assert paths[2].is_file()
    assert original["session_split"]["train"] == list(EXPECTED_SESSIONS[:8])
    assert original["session_split"]["validation"] == list(EXPECTED_SESSIONS[8:11])
    assert original["session_split"]["test"] == list(EXPECTED_SESSIONS[11:])
    assert original["training"]["rows"] == 1440
    assert original["validation"]["rows"] == 540
    assert original["test"]["rows"] == 540
    assert original["mode"] == "research_only"
    assert original["promotion_allowed"] is False
    assert original["paper_trading_connected"] is False
    assert original["live_trading_connected"] is False

    changed = _rows()
    for row in changed:
        if row["source_session"] not in EXPECTED_SESSIONS[:8]:
            row["label"] = 1
            row["spread_ticks"] *= 2
    after, _ = _run(tmp_path / "b", changed)
    assert after["model"] == original["model"]
    assert after["training"] == original["training"]
    assert after["test"]["aggregate"] != original["test"]["aggregate"]


def test_refuses_missing_or_reappearing_session_before_fit(tmp_path):
    missing = [row for row in _rows() if row["source_session"] != EXPECTED_SESSIONS[5]]
    with pytest.raises(ValueError, match="complete frozen cohort"):
        _run(tmp_path / "missing", missing)
    reordered = _rows()
    reordered.append(reordered[0].copy())
    reordered[-1]["decision_ts_ns"] = reordered[0]["decision_ts_ns"] + 600_000_000_000
    reordered[-1]["label_end_ts_ns"] = reordered[-1]["decision_ts_ns"] + 60_000_000_000
    with pytest.raises(ValueError, match="reappears"):
        _run(tmp_path / "reappearing", reordered)


def test_refuses_degraded_manifest_and_digest_mismatch(tmp_path):
    with pytest.raises(ValueError, match="quality_passed"):
        _run(tmp_path / "degraded", manifest_changes={"quality_passed": False})
    rows_path, manifest_path, output_path = _files(tmp_path / "tampered", _rows())
    rows_path.write_bytes(rows_path.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="digest"):
        train_6e_baseline(
            rows_path=rows_path,
            manifest_path=manifest_path,
            config_path=CONFIG_PATH,
            output_path=output_path,
        )
    assert not output_path.exists()


def test_refuses_cross_session_label_and_invalid_feature(tmp_path):
    rows = _rows()
    rows[179]["label_end_ts_ns"] = rows[180]["decision_ts_ns"]
    with pytest.raises(ValueError, match="invalid 60s label endpoint"):
        _run(tmp_path / "crossing", rows)
    rows = _rows()
    rows[0]["imbalance"] = "future"
    with pytest.raises(ValueError, match="must be numeric"):
        _run(tmp_path / "bad-feature", rows)


def test_refuses_decision_or_label_outside_frozen_utc_window(tmp_path):
    rows = _rows()
    rows[0]["decision_ts_ns"] -= 2 * 3600 * 1_000_000_000
    with pytest.raises(ValueError, match="fixed UTC window"):
        _run(tmp_path / "early-decision", rows)

    rows = _rows()
    rows[0]["label_end_ts_ns"] = rows[0]["decision_ts_ns"] + 59 * 1_000_000_000
    with pytest.raises(ValueError, match="invalid 60s label endpoint"):
        _run(tmp_path / "early-label", rows)

    rows = _rows()
    rows[0]["label_end_ts_ns"] = rows[0]["decision_ts_ns"] + 12 * 3600 * 1_000_000_000
    with pytest.raises(ValueError, match="invalid 60s label endpoint"):
        _run(tmp_path / "late-label", rows)


def test_refuses_missing_false_or_insufficient_session_quality(tmp_path):
    with pytest.raises(ValueError, match="quality counts"):
        _run(tmp_path / "missing-quality", manifest_changes={"quality": {}})
    with pytest.raises(ValueError, match="quality counts"):
        _run(
            tmp_path / "incomplete-quality",
            manifest_changes={"quality": {"rows_per_session": {EXPECTED_SESSIONS[0]: 180}}},
        )
    rows = _rows()
    rows.pop(0)
    with pytest.raises(ValueError, match="quality floor"):
        _run(tmp_path / "insufficient", rows)
    with pytest.raises(ValueError, match="differ from the actual"):
        _run(
            tmp_path / "false-count",
            manifest_changes={
                "quality": {"rows_per_session": dict.fromkeys(EXPECTED_SESSIONS, 180)}
            },
            rows=[row for index, row in enumerate(_rows()) if index != 0],
        )
