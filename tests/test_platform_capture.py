"""Offline feed contracts, no future quote backfill, and explicit unresolved readiness."""

import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path

import pytest

from ai_trader.research import platform_capture as capture

START = 1_790_856_000 * capture.NS
ROOT = Path(__file__).resolve().parents[1]


def records(provider="ninjatrader"):
    ninja = provider == "ninjatrader"
    start = {
        "kind": "session_start",
        "source_session": provider + "-" + "a" * 32,
        "sequence": 0,
        "observed_utc_ns": START,
        "elapsed_ns": 0,
        "schema": "ai_trader_market_capture_v1",
        "provider": provider,
        "market": "6E" if ninja else "EURUSD",
        "instrument": "6E 12-26" if ninja else "EURUSD.c",
        "feed_environment": "unverified" if ninja else "demo",
        "feed_label": "SYNTHETIC_TEST_ONLY",
        "tick_size": "0.00005" if ninja else "0.00001",
        "max_seconds": 60,
        "max_events": 100,
        "clock_basis": "serialized_callback_observation_utc",
        "clock_sync_verified": False,
        "trading_enabled": False,
    }
    values = [start]

    def append(kind, elapsed_ms, **fields):
        values.append(
            dict(
                kind=kind,
                source_session=start["source_session"],
                sequence=len(values),
                observed_utc_ns=START + elapsed_ms * 1_000_000,
                elapsed_ns=elapsed_ms * 1_000_000,
                **fields,
            )
        )

    if ninja:
        append("bid", 100, price="1.10000", size=10, provider_time_text="unverified-local-time")
        append("ask", 200, price="1.10010", size=12, provider_time_text="unverified-local-time")
        append("trade", 300, price="1.10010", size=3, provider_time_text="unverified-local-time")
        append(
            "depth",
            400,
            side="bid",
            operation="add",
            position=0,
            price="1.10000",
            size=10,
            provider_time_text="unverified-local-time",
        )
    else:
        append("quote", 100, bid="1.10000", ask="1.10010")
        append("quote", 200, bid="1.10001", ask="1.10011")
    append(
        "session_end",
        1000,
        reason="manual_stop",
        clean_shutdown=True,
        event_records=len(values) - 1,
    )
    return values


def save(tmp_path, values, name="capture.jsonl"):
    path = tmp_path / name
    path.write_bytes(b"".join((json.dumps(r) + "\n").encode() for r in values))
    return path


@pytest.mark.parametrize("provider", ["ninjatrader", "ctrader"])
def test_bounded_complete_capture_is_not_permission_to_train_or_trade(tmp_path, provider):
    path = save(tmp_path, records(provider))
    pin = hashlib.sha256(path.read_bytes()).hexdigest()
    result = capture.load_capture(path, pin)
    assert result.raw_sha256 == pin
    assert result.summary["transport_format_valid"] is True
    assert result.summary["training_ready"] is result.summary["trading_enabled"] is False
    assert "utc_synchronization_unverified" in result.summary["blockers"]
    assert "broker_costs_and_fills_unmeasured" in result.summary["blockers"]
    assert result.summary["spread_pips_event_mean"] == 1
    assert result.asof(START + 200_000_000).bid_nano == (
        1100000000 if provider == "ninjatrader" else 1100010000
    )
    assert result.asof(START) is None
    assert result.asof(START + capture.NS) is None  # closed session is unavailable


def test_no_future_side_backfill_and_each_side_has_own_age(tmp_path):
    result = capture.load_capture(save(tmp_path, records()))
    assert result.asof(START + 199_999_999) is None
    assert result.asof(START + 200_000_000) is not None
    assert result.asof(START + 600_000_000) is not None  # bid exactly 500 ms old
    assert result.asof(START + 600_000_001) is None  # ask and last trade cannot refresh bid


def test_crossed_latest_quote_blocks_fallback_to_older_good_quote(tmp_path):
    rows = records("ctrader")
    rows[2].update(bid="1.10020", ask="1.10010")
    result = capture.load_capture(save(tmp_path, rows))
    assert result.asof(START + 150_000_000) is not None
    assert result.asof(START + 200_000_000) is None
    assert result.summary["quote_states"] == 2
    assert result.summary["fresh_two_sided_observations"] == 1


def test_provider_clock_not_used_for_sorting_or_quote_availability(tmp_path):
    rows = records()
    rows[1]["provider_time_text"] = "2100-01-01T00:00:00"
    rows[2]["provider_time_text"] = "1990-01-01T00:00:00"
    result = capture.load_capture(save(tmp_path, rows))
    assert result.asof(START + 200_000_000) is not None
    assert result.summary["maximum_clock_delta_ns"] == 0
    assert result.header["clock_sync_verified"] is False


def test_quiet_market_not_hidden_by_heartbeats(tmp_path):
    rows = records("ctrader")[:-1]
    for second in range(1, 10):
        rows.append(
            dict(
                kind="heartbeat",
                source_session=rows[0]["source_session"],
                sequence=len(rows),
                observed_utc_ns=START + second * capture.NS,
                elapsed_ns=second * capture.NS,
            )
        )
    rows.append(
        dict(
            kind="session_end",
            source_session=rows[0]["source_session"],
            sequence=len(rows),
            observed_utc_ns=START + 10 * capture.NS,
            elapsed_ns=10 * capture.NS,
            reason="manual_stop",
            clean_shutdown=True,
            event_records=len(rows) - 1,
        )
    )
    result = capture.load_capture(save(tmp_path, rows))
    assert result.summary["maximum_record_gap_ns"] == capture.NS
    assert "quote_inactivity_over_five_seconds" in result.summary["blockers"]
    assert result.asof(START + 9 * capture.NS) is None


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r[0].update(trading_enabled=True),
        lambda r: r[0].update(clock_sync_verified=True),
        lambda r: r[0].update(provider="unknown"),
        lambda r: r[0].update(instrument="6E ##-##"),
        lambda r: r[0].update(tick_size="0.00001"),
        lambda r: r[0].update(max_events=True),
        lambda r: r[1].update(sequence=2),
        lambda r: r[1].update(sequence=True),
        lambda r: r[1].update(price="NaN"),
        lambda r: r[1].update(price=1.1),
        lambda r: r[1].update(price="1.10001"),
        lambda r: r[1].update(size=-1),
        lambda r: r[1].update(source_session="changed"),
        lambda r: r[1].update(kind=[]),
        lambda r: r[1].update(secret="unexpected-field"),
        lambda r: r[2].update(observed_utc_ns=START - 1),
        lambda r: r[2].update(elapsed_ns=0),
        lambda r: r[2].update(observed_utc_ns=START + 500_000_001),
        lambda r: r[3].update(size=0),
        lambda r: r[4].update(position=-1),
        lambda r: r[4].update(operation="invented"),
        lambda r: r[-1].update(clean_shutdown=False),
        lambda r: r[-1].update(event_records=0),
        lambda r: r[-1].update(reason="duration_limit"),
        lambda r: r[-1].update(reason="event_limit"),
        lambda r: r[-1].update(reason="byte_limit"),
        lambda r: r.append(deepcopy(r[-1])),
        lambda r: r.pop(),
    ],
)
def test_bad_or_incomplete_capture_fails_closed(tmp_path, change):
    rows = records()
    change(rows)
    with pytest.raises(ValueError):
        capture.load_capture(save(tmp_path, rows))


def test_demo_guard_no_live_ctrader_capture(tmp_path):
    rows = records("ctrader")
    rows[0]["feed_environment"] = "live"
    with pytest.raises(ValueError, match="demo"):
        capture.load_capture(save(tmp_path, rows))


@pytest.mark.parametrize(
    "raw", [b'{"kind":"heartbeat","kind":"heartbeat"}\n', b"NaN\n", b"{}", b"x" * 4097 + b"\n"]
)
def test_json_duplicates_nonfinite_partial_and_line_budget(tmp_path, raw):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        capture.load_capture(path)


def test_hash_and_overwrite_guards_and_no_report_on_invalid_input(tmp_path):
    path = save(tmp_path, records())
    with pytest.raises(ValueError, match="SHA256"):
        capture.load_capture(path, "b" * 64)
    output = tmp_path / "report.json"
    report = capture.audit_to_file(path, output)
    assert json.loads(output.read_bytes()) == report
    with pytest.raises(ValueError, match="overwrite"):
        capture.audit_to_file(path, output)
    with pytest.raises(ValueError, match="overwrite"):
        capture.audit_to_file(path, path)
    invalid = save(tmp_path, records()[:-1], "invalid.jsonl")
    with pytest.raises(ValueError):
        capture.audit_to_file(invalid, tmp_path / "must-not-exist.json")
    assert not (tmp_path / "must-not-exist.json").exists()


def test_zero_depth_and_no_market_quotes_are_not_silently_accepted_as_training(tmp_path):
    rows = records("ctrader")
    rows = [rows[0], dict(rows[-1], sequence=1, event_records=0)]
    result = capture.load_capture(save(tmp_path, rows))
    assert "no_fresh_two_sided_quotes" in result.summary["blockers"]
    assert result.asof(START + 500_000_000) is None


def test_adapters_contain_guards_but_no_order_or_secret_access():
    ninja = (ROOT / "integrations/ninjatrader/AiTraderSixEDataCapture.cs").read_text()
    ctrader = (ROOT / "integrations/ctrader/AiTraderEurUsdCapture.cs").read_text()
    for source in (ninja, ctrader):
        for forbidden in (
            "ExecuteMarketOrder(",
            "SubmitOrder",
            "EnterLong(",
            "EnterShort(",
            "PlaceLimitOrder(",
            "Account.Number",
            "Account.UserId",
            "Http.Get(",
        ):
            assert forbidden not in source
    assert "EnableCapture = false" in ninja and "State != State.Realtime" in ninja
    assert "Account.IsLive" in ctrader and "DefaultValue = false" in ctrader
    assert "RunningMode.RealTime" in ctrader
    assert "OnMarketDepth" in ninja and "OnMarketData" in ninja


def test_depth_capture_does_not_claim_book_reconstruction_or_aggressor_volume(tmp_path):
    result = capture.load_capture(save(tmp_path, records()))
    assert result.summary["events"]["depth"] == result.summary["events"]["trade"] == 1
    assert "cvd" not in result.summary
    assert result.summary["quote_states"] == 2
    assert "feed_entitlement_and_realtime_status_unverified" in result.summary["blockers"]


def test_source_packaging_is_self_contained_pinned_and_never_installs(tmp_path):
    package = runpy.run_path(str(ROOT / "integrations/package_sources.py"))["package_sources"]
    target = tmp_path / "new-package"
    result = package(target)
    assert result["installed"] is result["started"] is result["trading_enabled"] is False
    for name, pin in result["files"].items():
        raw = (target / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == pin
        assert raw.count(b"class BoundedCaptureWriter") == 1
        assert not any(
            line.startswith("using ")
            for line in raw.decode().split("namespace ", 1)[1].splitlines()
        )
    with pytest.raises(ValueError, match="overwrite"):
        package(target)


def _micro(rows):
    rows[0].update(market="M6E", instrument="M6E 12-26", tick_size="0.0001")
    return rows


def test_micro_m6e_capture_is_accepted_on_its_own_tick_grid(tmp_path):
    result = capture.load_capture(save(tmp_path, _micro(records())))
    assert result.summary["transport_format_valid"] is True
    assert result.summary["training_ready"] is result.summary["trading_enabled"] is False


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r[0].update(tick_size="0.00005"),  # M6E header with the 6E tick
        lambda r: r[0].update(instrument="6E 12-26"),  # market/instrument mismatch
        lambda r: r[0].update(instrument="M6E ##-##"),  # continuous contract refused
        lambda r: r[0].update(market="MES", instrument="MES 12-26"),  # other contracts refused
        lambda r: r[1].update(price="1.10005"),  # off the 0.0001 grid
    ],
)
def test_micro_m6e_capture_still_fails_closed(tmp_path, change):
    rows = _micro(records())
    change(rows)
    with pytest.raises(ValueError):
        capture.load_capture(save(tmp_path, rows))


def test_ninjatrader_adapter_rotates_only_after_clean_limits():
    ninja = (ROOT / "integrations/ninjatrader/AiTraderSixEDataCapture.cs").read_text()
    writer = (ROOT / "integrations/market_data/BoundedCaptureWriter.cs").read_text()
    assert '"M6E"' in ninja and "TotalHours = 0" in ninja
    for reason in ("duration_limit", "event_limit", "byte_limit"):
        assert '"' + reason + '"' in ninja
    assert "public string CloseReason" in writer
