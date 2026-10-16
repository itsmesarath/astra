"""Completed-event causality, sequential hypotheses and complete offline evidence."""

import json
import math
from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import numpy as np
import pytest
from test_causal_6e_context import DAY, START, observation
from test_historical_6e_archive import census_root as census_root
from test_historical_6e_cohort import metadata_root as metadata_root
from test_historical_6e_cohort import records_for, write_json
from test_historical_6e_manifest import manifest_evidence as manifest_evidence
from test_historical_6e_manifest import protected_evidence as protected_evidence
from test_historical_6e_resource_replay import evidence as evidence

from ai_trader.research import six_e_auction_features as tape
from ai_trader.research import six_e_auction_study as s
from ai_trader.training import six_e_auction_playbooks as r

BASE = 1_000_000_000


def quote(seconds, shift=0):
    return SimpleNamespace(
        ts_recv_ns=START + seconds * tape.SECOND,
        bid=BASE + shift * tape.TICK,
        ask=BASE + (shift + 1) * tape.TICK,
    )


def record(seconds, action="T", side="B", size=3, shift=1):
    return SimpleNamespace(
        recv=START + seconds * tape.SECOND,
        action=action,
        side=side,
        size=size,
        price=BASE + shift * tape.TICK,
    )


def engine():
    return tape.AuctionFeatures(DAY, "6EM5")


def bundle():
    return {
        "cutoffs": {"activity": 2.0, "absolute_cvd": 1.0, "held_passive": 0.5},
        "confirmation_activity": 1.0,
        "targets_used": False,
    }


def row(second, dist=1, direction=1, attack=1):
    result = observation(second, 2.0 * direction)
    result["features"].update(
        log_known_trades_5s=3.0, mid_change_5s_ticks=direction, normalized_ofi_5s=direction
    )
    shift = 4 + dist if attack > 0 else -dist
    g = dict.fromkeys(tape.FEATURES, 0)
    g.update(
        bid_nano=BASE + shift * tape.TICK,
        ask_nano=BASE + (shift + 1) * tape.TICK,
        prior_low_nano2=2 * BASE + tape.TICK,
        prior_high_nano2=2 * BASE + 9 * tape.TICK,
        prior_range_ticks=4.0,
        range_ready=1,
        prior_quote_count=100,
        range_age_seconds=60,
    )
    for w in tape.WINDOWS:
        g.update(
            {
                f"buy_qty_{w}s": 3 if direction > 0 else 0,
                f"sell_qty_{w}s": 3 if direction < 0 else 0,
                f"delta_qty_{w}s": 3 * direction,
                f"known_trades_{w}s": 1,
                f"unknown_fraction_qty_{w}s": 0.0,
            }
        )
    result["auction_features"] = g
    return result


def test_current_price_excluded_from_prior_range_equal_times_preserve_native_order():
    e = engine()
    e.observe(quote(0), [])
    e.observe(quote(60, 4), [])
    g = e.features(START + 60 * tape.SECOND)
    assert g["range_ready"] == 0  # Only one prior quote, not enough support.
    assert g["prior_high_nano2"] == 2 * BASE + tape.TICK
    e.observe(quote(60, 8), [])
    g = e.features(START + 60 * tape.SECOND)
    assert g["range_ready"] == 1
    assert g["prior_high_nano2"] == 2 * BASE + 9 * tape.TICK  # Earlier equal-time quote included.
    e.observe(quote(61), [])
    assert e.features(START + 61 * tape.SECOND)["prior_low_nano2"] == 2 * BASE + 9 * tape.TICK


def test_t_only_no_fill_double_count_unknown_and_completed_event_availability():
    e = engine()
    e.observe(
        quote(1),
        [
            record(0),
            record(0, "F"),
            record(0, side="A", size=1, shift=0),
            record(0, side="N", size=2),
        ],
    )
    g = e.features(START + tape.SECOND)
    assert (g["buy_qty_5s"], g["sell_qty_5s"], g["unknown_qty_5s"]) == (3, 1, 2)
    assert g["delta_qty_5s"] == 2 and g["known_trades_5s"] == 2
    assert g["unknown_fraction_qty_5s"] == 1 / 3
    assert g["diagonal_buy_max_5s"] == 0.5 and g["diagonal_pairs_5s"] == 1
    assert g["segment_vwap_qty"] == 6
    assert g["segment_vwap_start_ns"] == START + tape.SECOND
    e.observe(quote(6), [])
    assert e.features(START + 6 * tape.SECOND)["buy_qty_5s"] == 3  # Inclusive boundary.
    e.observe(quote(7), [])
    g = e.features(START + 7 * tape.SECOND)
    assert g["buy_qty_5s"] == g["diagonal_pairs_5s"] == 0
    assert g["buy_qty_15s"] == 3 and g["segment_vwap_qty"] == 6
    e.observe(quote(17), [])
    assert e.features(START + 17 * tape.SECOND)["buy_qty_15s"] == 0
    assert e.features(START + 17 * tape.SECOND)["buy_qty_30s"] == 3


def test_zero_denominator_diagonal_is_not_infinite_imbalance_and_vwap_warmup_excluded():
    e = engine()
    e.observe(quote(-1), [record(-1, size=100)])
    e.observe(quote(0), [record(0, side="N", size=1)])
    g = e.features(START)
    assert g["diagonal_pairs_5s"] == g["diagonal_buy_max_5s"] == 0
    assert g["segment_vwap_qty"] == 1
    assert set(g) == set(tape.FEATURES)


@pytest.mark.parametrize("bad", ["future", "span", "off_tick", "negative", "side"])
def test_malformed_or_incomplete_event_is_refused(bad):
    item = record(0)
    if bad == "future":
        item.recv += 2 * tape.SECOND
    elif bad == "span":
        item.recv -= 5 * tape.SECOND
    elif bad == "off_tick":
        item.price += 1
    elif bad == "negative":
        item.size = -1
    else:
        item.side = "?"
    with pytest.raises(ValueError):
        engine().observe(quote(1), [item])


@pytest.mark.parametrize("direction", [1, -1])
def test_failed_auction_requires_return_retest_then_opposite_confirmation(direction):
    state = r.State(DAY, "6EM5", bundle())
    assert state.observe(row(0, 1, direction, direction))["failed_auction"] == 0
    assert state.observe(row(1, -1, -direction, direction))["failed_auction"] == 0
    assert state.observe(row(2, 0, -direction, direction))["failed_auction"] == 0
    assert state.observe(row(3, -1, -direction, direction))["failed_auction"] == -direction
    assert state.observe(row(4, 1, direction, direction))["failed_auction"] == 0
    assert "failed_auction" not in state.pending  # Cooldown, not immediate new episode.


@pytest.mark.parametrize("direction", [1, -1])
def test_breakout_requires_acceptance_weak_counter_retest_and_resumption(direction):
    state = r.State(DAY, "6EM5", bundle())
    state.observe(row(0, 1, direction, direction))
    assert state.observe(row(1, 2, direction, direction))["accepted_breakout"] == 0
    assert state.observe(row(2, 2, direction, direction))["accepted_breakout"] == 0
    retest = row(3, 1, -direction, direction)
    retest["features"]["normalized_cvd_5s"] = -0.5 * direction
    assert state.observe(retest)["accepted_breakout"] == 0
    assert state.observe(row(4, 2, direction, direction))["accepted_breakout"] == direction


@pytest.mark.parametrize("attack", [1, -1])
@pytest.mark.parametrize(
    "family,dist,confirmation", [("defended_hold", -1, -1), ("defended_failure", 2, 1)]
)
def test_defended_hold_and_failure_are_separate_mirrored_branches(
    attack, family, dist, confirmation
):
    state = r.State(DAY, "6EM5", bundle())
    initial = row(0, 0, attack, attack)
    side = "ask" if attack > 0 else "bid"
    initial["execution_features"].update(
        {f"{side}_held_top_passive_5s": 0.5, f"{side}_other_id_reload_5s": 0.1}
    )
    assert state.observe(initial)[family] == 0
    assert (
        state.observe(row(1, dist, confirmation * attack, attack))[family] == confirmation * attack
    )
    other = "defended_failure" if family == "defended_hold" else "defended_hold"
    assert state.audit.get(f"{other}_confirmed", 0) == 0


def test_gap_unknown_and_expiry_reset_without_future_eligibility_filters():
    for change in ("gap", "unknown", "not_ready"):
        state = r.State(DAY, "6EM5", bundle())
        state.observe(row(0))
        following = row(6 if change == "gap" else 1)
        if change == "unknown":
            following["features"]["unknown_trade_fraction_5s"] = 0.11
        if change == "not_ready":
            following["auction_features"]["range_ready"] = 0
        state.observe(following)
        assert not state.pending
    state = r.State(DAY, "6EM5", bundle())
    for sec in range(32):
        state.observe(row(sec, 1))
    assert state.audit["failed_auction_expired"] == 1


def test_prefix_invariance_and_outcomes_never_read_by_rules():
    rows = [row(0), row(1, -1, -1), row(2, 0, -1), row(3, -1, -1), row(4)]
    expected, _ = r.directions(rows, bundle())
    poisoned = deepcopy(rows)
    for item in poisoned:
        item.update(
            eligible="do not access",
            outcome=object(),
            hindsight_action=object(),
            net_targets_long_short_ticks=object(),
            path_horizons=object(),
        )
    for name, result in r.directions(poisoned, bundle())[0].items():
        np.testing.assert_array_equal(expected[name], result)
        np.testing.assert_array_equal(
            expected[name][:3], r.directions(poisoned[:3], bundle())[0][name]
        )


@pytest.mark.parametrize(
    "change",
    [
        "reserved",
        "contract",
        "partition",
        "nan",
        "extra",
        "duplicate",
        "accounting",
        "price",
        "future_vwap",
    ],
)
def test_strict_feature_identity_and_accounting_guards(change):
    rows = [row(0), row(1)]
    if change == "reserved":
        rows[0]["source_session"] = "2026-01-01"
    elif change == "contract":
        rows[1]["contract"] = "6EU5"
    elif change == "partition":
        rows[1]["partition"] = "test"
    elif change == "nan":
        rows[1]["auction_features"]["range_age_seconds"] = math.nan
    elif change == "extra":
        rows[1]["auction_features"]["future_price"] = 1
    elif change == "duplicate":
        rows[1]["decision_ts_ns"] = rows[0]["decision_ts_ns"]
    elif change == "accounting":
        rows[1]["auction_features"]["delta_qty_5s"] += 1
    elif change == "price":
        rows[1]["auction_features"]["bid_nano"] += 1
    else:
        rows[1]["auction_features"]["segment_vwap_start_ns"] = rows[1]["decision_ts_ns"] + 1
    with pytest.raises(ValueError):
        r.directions(rows, bundle())


def test_native_augmentation_preserves_original_replay_and_resets_price_context():
    original = s.census.DailyBuilder(DAY, "6EM5")
    augmented = s.AuctionBuilder(DAY, "6EM5")
    for builder in (original, augmented):
        builder.start_day(date.fromisoformat(DAY))
        for item in records_for(date.fromisoformat(DAY), "6EM5"):
            builder.consume(item)
        builder.finish_day()
    rows, cases, quality = original.finish()
    assert augmented.finish() == (rows, cases, quality)
    assert len(augmented.auction_rows) == len(rows)
    assert augmented.auction_resets == 1
    assert sum(g["range_ready"] for g in augmented.auction_rows.values()) > 0


@pytest.fixture
def pilot(manifest_evidence, monkeypatch):
    root, path, pin, manifest = manifest_evidence
    entries = [e for e in manifest["ledger"] if e["artifacts"]]
    monkeypatch.setattr(s, "DAYS", tuple(e["utc_date"] for e in entries))

    def replay(member):
        entry = next(e for e in entries if e["utc_date"] == member["utc_date"])
        rows = s.data.read_rows(root, entry, "rows")
        features = []
        for source in rows:
            g = row(0)["auction_features"]
            g["range_ready"] = 0  # Synthetic no-trade pilot, not fitted market outcomes.
            features.append({**{k: source[k] for k in s.PROJECTION}, "auction_features": g})
        return rows, features, {"full_member_hash_verified": True}

    monkeypatch.setattr(s, "replay", replay)
    registration = root / "auction-registration.json"
    s.prepare(root, path, pin, registration)
    return root, registration, s.common.hash_file(registration, 2 * 1024**2)


def test_complete_pilot_recomputes_every_session_and_refuses_reuse_or_drift(pilot, monkeypatch):
    root, registration, pin = pilot
    output = root / "data/processed/auction"
    verified = s.run(root, registration, pin, output)
    assert verified["sessions"] == len(s.DAYS)
    assert not any(verified["flags"].values())
    assert s.verify(root, registration, pin, output) == verified
    report = json.loads((output / "completion.json").read_bytes())
    assert sum(x["rows"] for x in report["summaries"]["by_role"].values()) == verified["rows"]
    with pytest.raises(FileExistsError):
        s.run(root, registration, pin, output)
    monkeypatch.setattr(s, "replay", lambda *a: pytest.fail("replay accessed after drift"))
    monkeypatch.setattr(r, "EPISODE_SECONDS", 31)
    with pytest.raises(ValueError, match="protocol"):
        s.run(root, registration, pin, root / "data/processed/new")


def test_failure_retains_evidence_and_never_scores_successful_subset(pilot, monkeypatch):
    root, registration, pin = pilot
    monkeypatch.setattr(s, "replay", lambda *a: (_ for _ in ()).throw(ValueError("bad source")))
    output = root / "data/processed/failure"
    with pytest.raises(ValueError, match="bad source"):
        s.run(root, registration, pin, output)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    with pytest.raises(ValueError, match="failure"):
        s.verify(root, registration, pin, output)


def test_tampered_sidecar_and_repinned_pooled_metrics_are_refused(pilot):
    root, registration, pin = pilot
    output = root / "data/processed/auction"
    s.run(root, registration, pin, output)
    completion = output / "completion.json"
    report = json.loads(completion.read_bytes())
    report["summaries"]["overall"]["rows"] += 1
    write_json(completion, report)
    with pytest.raises(ValueError, match="pooled"):
        s.verify(root, registration, pin, output)
    report["summaries"]["overall"]["rows"] -= 1
    write_json(completion, report)
    sidecar = output / f"{s.DAYS[0]}.features.jsonl"
    sidecar.write_bytes(sidecar.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="artifact"):
        s.verify(root, registration, pin, output)


def test_reserved_replay_refused_before_archive_access(monkeypatch):
    monkeypatch.setattr(s.zipfile, "ZipFile", lambda *a: pytest.fail("raw reserved opened"))
    with pytest.raises(ValueError):
        s.replay({"utc_date": "2026-01-01"})
