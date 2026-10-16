"""Independent constructed-record oracles; no historical input or outcome access.

Expected canonical bodies, before states, complete event ranges and all 37 values
are built from literal contract tables and hand-declared scenarios. No private
witness helper, returned witness or legacy target builder supplies this oracle.
An additional in-memory original producer comparison is explicitly secondary.
"""

import builtins
import hashlib
import inspect
import json
import math
import socket
import subprocess
from copy import deepcopy
from dataclasses import asdict, fields, replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import databento_dbn as dbn
import pytest

from ai_trader.research import databento_6e_execution_flow as execution
from ai_trader.research import databento_6e_microdepth as microdepth
from ai_trader.research import databento_6e_ofi_scalp as ofi
from ai_trader.research import databento_6e_receive_clock as receive
from ai_trader.research import databento_6e_scenario_replay as strict
from ai_trader.research import six_e_feature_publication_witness as witness

C = {
    "VERSION": "six_e_feature_publication_witness_v1",
    "STATUS": "constructed_feature_reconstruction_not_historical_provenance",
    "UTC_DATE": "2025-04-07",
    "CONTRACT": "6EM5",
    "INSTRUMENT_ID": 1,
    "DAY_START_NS": 1743984000000000000,
    "WINDOW_START_NS": 1744027200000000000,
    "WINDOW_END_NS": 1744041600000000000,
    "WARMUP_START_NS": 1744027190000000000,
    "GENESIS_NS": 1744027189999999999,
    "SECOND_NS": 1000000000,
    "FLOW_NS": 5000000000,
    "WARMUP_NS": 10000000000,
    "MIN_PUBLICATION_CADENCE_NS": 1000000000,
    "READINESS_END_BUFFER_NS": 17000000000,
    "TICK_NANO": 50000,
    "F_LAST": 128,
    "MAX_RECORDS": 256,
    "MAX_COMPLETED_EVENTS": 128,
    "MAX_PUBLICATIONS": 32,
    "MAX_CANONICAL_BYTES": 1048576,
    "MAX_HELPER_SOURCE_BYTES": 1048576,
    "MAX_INT": 9223372036854775807,
    "MAX_SEQUENCE": 4294967295,
    "MAX_SEND_DELTA": 2147483647,
}
SCHEMAS = {
    "ConstructedMboRecord": (
        "record_ordinal",
        "instrument_id",
        "ts_recv",
        "ts_event",
        "ts_in_delta",
        "sequence",
        "action",
        "side",
        "flags",
        "price",
        "size",
        "order_id",
    ),
    "FeatureWitnessFixture": (
        "fixture_id",
        "source_session",
        "utc_date",
        "contract",
        "instrument_id",
        "records",
    ),
    "RecordAudit": (
        "record_ordinal",
        "before",
        "record_sha256",
        "preceding_prefix_sha256",
        "prefix_sha256",
    ),
    "CompletedEventWitness": (
        "event_id",
        "event_ordinal",
        "first_record_ordinal",
        "last_record_ordinal",
        "started_at_ns",
        "completed_at_ns",
        "quote_ordinal",
        "quote",
        "prior_quote_gap_ns",
        "ofi_first_ts_ns",
        "inactivity_reset",
        "execution_temporal_reset",
        "execution_stale_spanning",
        "prefix_sha256",
        "event_sha256",
    ),
    "FeaturePublication": (
        "publication_id",
        "publication_ordinal",
        "event_ordinal",
        "quote_ordinal",
        "received_at_ns",
        "quote",
        "prefix_sha256",
        "event_sha256",
        "ofi_first_ts_ns",
        "prior_quote_gap_ns",
        "cvd",
        "known_trade_count",
        "unknown_trade_count",
        "ofi_total",
        "feature_values",
        "eligible",
        "eligibility_reason",
        "publication_sha256",
    ),
    "FeaturePublicationWitness": (
        "version",
        "status",
        "protocol_sha256",
        "fixture_sha256",
        "fixture",
        "prefix_context_sha256",
        "record_audits",
        "completed_events",
        "publications",
        "execution_audit",
        "terminal_prefix_sha256",
        "terminal_received_at_ns",
        "record_count",
        "completed_event_count",
        "quote_count",
        "publication_count",
        "authority_flags",
        "witness_sha256",
    ),
}
NAMES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
    "log_bid_depth5",
    "log_ask_depth5",
    "depth5_imbalance",
    "bid_top_share5",
    "ask_top_share5",
    "bid_span5_ticks",
    "ask_span5_ticks",
    "mid_change_5s_ticks",
    "mid_range_5s_ticks",
    "mid_travel_5s_ticks",
    "log_quote_events_5s",
    "normalized_bid_reload_5s",
    "normalized_ask_reload_5s",
    "buy_absorption_proxy_5s",
    "sell_absorption_proxy_5s",
    "bid_passive_5s",
    "bid_held_top_passive_5s",
    "bid_linked_decrease_5s",
    "bid_unlinked_decrease_5s",
    "bid_same_id_reload_5s",
    "bid_other_id_reload_5s",
    "bid_same_id_net_refresh_5s",
    "ask_passive_5s",
    "ask_held_top_passive_5s",
    "ask_linked_decrease_5s",
    "ask_unlinked_decrease_5s",
    "ask_same_id_reload_5s",
    "ask_other_id_reload_5s",
    "ask_same_id_net_refresh_5s",
)
SOURCE_PINS = (
    (
        "src/ai_trader/research/databento_6e_cost_targets.py",
        "ebc4c1dc0a44e71362cd96bed0a699dac6ebc04a66fc7f568d2bf4898d427b2b",
    ),
    (
        "src/ai_trader/research/databento_6e_event_scalp.py",
        "48bd0402c2e8a7c0d8d286b8956a2f55059c71df81dc1115ee15d8adce560b3e",
    ),
    (
        "src/ai_trader/research/databento_6e_execution_flow.py",
        "7f777a19518378dd3b2a0371b7f3ddcf3077f51555faffa5e589de6255239b75",
    ),
    (
        "src/ai_trader/research/databento_6e_microdepth.py",
        "8964b20a5de8104a0f7831cf827c1c736f3c11b6a2d61dbe0206521ee3b451c4",
    ),
    (
        "src/ai_trader/research/databento_6e_ofi_scalp.py",
        "05cade0f206c06cbea93198c9fb92e591c0275ef5ac70f8ce50bcb000ad0ff24",
    ),
    (
        "src/ai_trader/research/databento_6e_receive_clock.py",
        "351b4b54fc3ac4ac905ebdbb9725f270288ac235178cb50180e2040d8fef4636",
    ),
    (
        "src/ai_trader/research/databento_6e_scenario_replay.py",
        "d5bf8e3e0ec4b1957f1a2a7ed515f1cf9530b922e5c2c3929389ed0bfeab91ff",
    ),
    (
        "src/ai_trader/research/databento_6e_seconds_pilot.py",
        "7c295b7cc3875a6955d3582368a7d28804dd318e061e0d0b3906e4a21e411b2b",
    ),
    (
        "src/ai_trader/research/databento_6e_training_data.py",
        "9d1c9190da304031113880dbfb4d002121908d35b6bc52671a65939a6e7049a3",
    ),
)
FLAG_NAMES = (
    "accounting_admission_authorized",
    "calendar_verified",
    "cohort_externally_complete",
    "collection_receipt_authenticated",
    "event_prefix_verified",
    "execution_authorized",
    "feature_derivation_verified",
    "feature_publication_verified",
    "feed_authenticated",
    "first_cursor_verified",
    "historical_access_authorized",
    "independent_validation",
    "input_authenticated",
    "metadata_assertions_authenticated",
    "promotion_allowed",
    "source_integrity_verified",
    "source_runtime_verified",
    "storage_resume_authorized",
    "trading_enabled",
    "training_enabled",
)
FLAGS = tuple((name, False) for name in FLAG_NAMES)
PROTOCOL = {
    "version": C["VERSION"],
    "status": C["STATUS"],
    "scope": "constructed_target_mbo_prefix_only",
    "constants": C,
    "schemas": {name: list(value) for name, value in SCHEMAS.items()},
    "feature_names": list(NAMES),
    "source_pins": [list(pair) for pair in SOURCE_PINS],
    "identifier_templates": {
        "event_id": "synthetic-completed-event-{ordinal:04d}",
        "publication_id": "synthetic-feature-publication-{ordinal:04d}",
    },
    "readiness_reasons": [
        "spread_not_one_tick",
        "insufficient_feature_warmup",
        "insufficient_window_for_hold",
    ],
    "authority_flags": [list(pair) for pair in FLAGS],
}
S = C["SECOND_NS"]
START = C["WINDOW_START_NS"]
TICK = C["TICK_NANO"]
BID = 1000000000
ASK = BID + TICK


def canonical(value):
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


PROTOCOL_PIN = digest(PROTOCOL)


def record(ordinal, offset, action="N", side="N", price=0, size=0, oid=0, last=True):
    now = C["GENESIS_NS"] if ordinal == 1 else START + offset
    return witness.ConstructedMboRecord(
        ordinal,
        1,
        now,
        now,
        0,
        0,
        action,
        side,
        128 if last else 0,
        price,
        size,
        oid,
    )


def fixture(records, suffix="oracle"):
    return witness.FeatureWitnessFixture(
        "synthetic-" + suffix,
        "synthetic-source-" + suffix,
        "2025-04-07",
        "6EM5",
        1,
        tuple(records),
    )


def input_body(value):
    return {"version": C["VERSION"], "protocol_sha256": PROTOCOL_PIN, "fixture": asdict(value)}


def input_pin(value):
    return digest(input_body(value))


def quote(now, bid=BID, ask=ASK, bq=10, aq=10):
    return {"ts_recv_ns": now, "bid": bid, "ask": ask, "bid_qty": bq, "ask_qty": aq}


def hand_values(
    *,
    bq=10,
    aq=10,
    bd=60,
    ad=60,
    bspan=2,
    aspan=2,
    ofitotal=0,
    cvd=0,
    known=0,
    unknown=0,
    gap=S,
    count=3,
    change=0.0,
    midrange=0.0,
    travel=0,
    breload=0,
    areload=0,
    bid_execution=(0, 0, 0, 0, 0, 0, 0),
    ask_execution=(0, 0, 0, 0, 0, 0, 0),
):
    """Hand arithmetic on explicitly supplied independent state, never raw replay."""
    depth = bq + aq
    total_count = known + unknown
    numbers = (
        math.log1p(bq),
        math.log1p(aq),
        (bq - aq) / depth,
        2 * ofitotal / depth,
        2 * cvd / depth,
        math.log1p(known),
        unknown / total_count if total_count else 0.0,
        math.log1p(gap / 1000000),
        math.log1p(bd),
        math.log1p(ad),
        (bd - ad) / (bd + ad),
        bq / bd,
        aq / ad,
        bspan / 1,
        aspan / 1,
        change,
        midrange,
        travel,
        math.log1p(count),
        breload / depth,
        areload / depth,
        max(cvd, 0) / (depth * (1 + max(change, 0))),
        max(-cvd, 0) / (depth * (1 + max(-change, 0))),
        *(number / depth for number in bid_execution),
        *(number / depth for number in ask_execution),
    )
    # QuoteHistory's empty travel sum is an int; the public witness must retain
    # exact float values, so this expected tuple explicitly spells that cast.
    return tuple((name, float(number)) for name, number in zip(NAMES, numbers, strict=True))


def event(
    last,
    now,
    *,
    bq=10,
    aq=10,
    bid=BID,
    ask=ASK,
    first=START - 10 * S,
    inactivity=False,
    reset=False,
    stale=False,
):
    return {
        "last": last,
        "quote": quote(now, bid, ask, bq, aq),
        "first": first,
        "inactivity": inactivity,
        "reset": reset,
        "stale": stale,
    }


def publication(event_ordinal, values, *, cvd=0, known=0, unknown=0, total=0, reason=None):
    return {
        "event": event_ordinal,
        "values": values,
        "cvd": cvd,
        "known": known,
        "unknown": unknown,
        "total": total,
        "reason": reason,
    }


def expected(value, before, event_specs, publication_specs, audit):
    """Complete canonical oracle with supplied hand witnesses, not a book walker."""
    assert len(before) == len(value.records)
    context = {
        "version": C["VERSION"],
        "protocol_sha256": PROTOCOL_PIN,
        "fixture_id": value.fixture_id,
        "source_session": value.source_session,
        "utc_date": "2025-04-07",
        "contract": "6EM5",
        "instrument_id": 1,
        "record_schema": list(SCHEMAS["ConstructedMboRecord"]),
        "source_pins": [list(pair) for pair in SOURCE_PINS],
    }
    seed = digest(context)
    head = seed
    audits = []
    for source, previous in zip(value.records, before, strict=True):
        source_pin = digest(asdict(source))
        next_head = digest(
            {
                "preceding_prefix_sha256": head,
                "record_ordinal": source.record_ordinal,
                "record_sha256": source_pin,
            }
        )
        audits.append(
            {
                "record_ordinal": source.record_ordinal,
                "before": previous,
                "record_sha256": source_pin,
                "preceding_prefix_sha256": head,
                "prefix_sha256": next_head,
            }
        )
        head = next_head
    events = []
    preceding_last = 1
    preceding_time = None
    for ordinal, spec in enumerate(event_specs, 1):
        last = spec["last"]
        now = spec["quote"]["ts_recv_ns"]
        body = {
            "event_id": f"synthetic-completed-event-{ordinal:04d}",
            "event_ordinal": ordinal,
            "first_record_ordinal": preceding_last + 1,
            "last_record_ordinal": last,
            "started_at_ns": value.records[preceding_last].ts_recv,
            "completed_at_ns": now,
            "quote_ordinal": ordinal - 1,
            "quote": spec["quote"],
            "prior_quote_gap_ns": 0 if preceding_time is None else now - preceding_time,
            "ofi_first_ts_ns": spec["first"],
            "inactivity_reset": spec["inactivity"],
            "execution_temporal_reset": spec["reset"],
            "execution_stale_spanning": spec["stale"],
            "prefix_sha256": audits[last - 1]["prefix_sha256"],
        }
        events.append({**body, "event_sha256": digest(body)})
        preceding_time, preceding_last = now, last
    pubs = []
    for ordinal, spec in enumerate(publication_specs, 1):
        e = events[spec["event"] - 1]
        body = {
            "publication_id": f"synthetic-feature-publication-{ordinal:04d}",
            "publication_ordinal": ordinal,
            "event_ordinal": e["event_ordinal"],
            "quote_ordinal": e["quote_ordinal"],
            "received_at_ns": e["completed_at_ns"],
            "quote": e["quote"],
            "prefix_sha256": e["prefix_sha256"],
            "event_sha256": e["event_sha256"],
            "ofi_first_ts_ns": e["ofi_first_ts_ns"],
            "prior_quote_gap_ns": e["prior_quote_gap_ns"],
            "cvd": spec["cvd"],
            "known_trade_count": spec["known"],
            "unknown_trade_count": spec["unknown"],
            "ofi_total": spec["total"],
            "feature_values": spec["values"],
            "eligible": spec["reason"] is None,
            "eligibility_reason": spec["reason"],
        }
        pubs.append({**body, "publication_sha256": digest(body)})
    assert preceding_last == len(value.records)
    body = {
        "version": C["VERSION"],
        "status": C["STATUS"],
        "protocol_sha256": PROTOCOL_PIN,
        "fixture_sha256": input_pin(value),
        "fixture": asdict(value),
        "prefix_context_sha256": seed,
        "record_audits": tuple(audits),
        "completed_events": tuple(events),
        "publications": tuple(pubs),
        "execution_audit": tuple(sorted(audit.items())),
        "terminal_prefix_sha256": head,
        "terminal_received_at_ns": value.records[-1].ts_recv,
        "record_count": len(value.records),
        "completed_event_count": len(events),
        "quote_count": len(events),
        "publication_count": len(pubs),
        "authority_flags": FLAGS,
    }
    return {**body, "witness_sha256": digest(body)}


def check(case):
    value, before, events, pubs, audit = case
    oracle = expected(value, before, events, pubs, audit)
    assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == input_pin(value)
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    assert canonical(asdict(result)) == canonical(oracle)
    assert result.witness_sha256 == oracle["witness_sha256"]
    assert tuple(name for name, _ in result.publications[0].feature_values) == NAMES
    assert all(
        type(number) is float and math.isfinite(number)
        for pub in result.publications
        for _, number in pub.feature_values
    )
    assert all(type(flag) is bool and flag is False for _, flag in result.authority_flags)
    assert (
        witness.verify(
            result,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=oracle["witness_sha256"],
        )
        is None
    )
    return result, oracle


def deep_seed(at=-10 * S, markers=True):
    r = [record(1, 0, "R")]
    declarations = (
        ("B", BID, 10, 1),
        ("A", ASK, 10, 2),
        ("B", BID - TICK, 20, 11),
        ("B", BID - 2 * TICK, 30, 12),
        ("A", ASK + TICK, 20, 21),
        ("A", ASK + 2 * TICK, 30, 22),
    )
    for side, price, size, oid in declarations:
        r.append(record(len(r) + 1, at, "A", side, price, size, oid, last=oid == 22))
    b = [None] * len(r)
    e = [event(7, START + at, first=START + at, reset=True, inactivity=at > -5 * S)]
    if markers:
        for offset in (-5 * S, -S):
            r.append(record(len(r) + 1, offset))
            b.append(None)
            e.append(event(len(r), START + offset, first=START + at))
    return r, b, e


def execution_case(kind="buy-other"):
    r, b, e = deep_seed()
    aq = ASK
    side, aggressor, oid = ("B", "A", 1) if kind == "sell-other" else ("A", "B", 2)
    price = BID if side == "B" else aq
    audit = {"completed_events": 4, "temporal_resets": 1}
    metrics = [0] * 7
    cvd, known = 0, 0
    if kind == "cancel-only":
        additions = [
            ("C", side, price, 6, oid, (side, price, 10)),
            ("M", side, price, 10, oid, (side, price, 4)),
        ]
        metrics[3] = 6
        audit[f"{side}_unlinked_decrease_volume"] = 6
    else:
        additions = [
            ("T", aggressor, price, 6, 99, None),
            ("F", side, price, 6, oid, (side, price, 10)),
        ]
        metrics[0] = metrics[1] = 6
        audit.update(
            {
                f"{side}_passive_volume": 6,
                f"{side}_held_top_passive_volume": 6,
                "fill_matched_passive_records": 1,
                "fill_matched_passive_volume": 6,
                "fill_above_displayed_volume": 0,
                f"trade_{aggressor}_volume": 6,
            }
        )
        cvd, known = (-6 if kind == "sell-other" else 6), 1
        if kind == "buy-net-only":
            additions.append(("M", side, price, 10, oid, (side, price, 10)))
            metrics[6] = 6
            audit[f"{side}_same_id_net_refresh_volume"] = 6
        else:
            additions.append(("C", side, price, 6, oid, (side, price, 10)))
            metrics[2] = 6
            audit[f"{side}_linked_decrease_volume"] = 6
            if kind == "buy-same":
                additions.append(("M", side, price, 10, oid, (side, price, 4)))
                metrics[4] = metrics[6] = 6
                audit[f"{side}_same_id_reload_volume"] = 6
                audit[f"{side}_same_id_net_refresh_volume"] = 6
            else:
                additions.append(("A", side, price, 6, 3, None))
                metrics[5] = 6
                audit[f"{side}_other_id_reload_volume"] = 6
    for index, (action, side_, price_, size_, oid_, before_) in enumerate(additions):
        r.append(
            record(len(r) + 1, 0, action, side_, price_, size_, oid_, index == len(additions) - 1)
        )
        b.append(before_)
    e.append(event(len(r), START))
    values = hand_values(
        cvd=cvd,
        known=known,
        bid_execution=tuple(metrics) if side == "B" else (0,) * 7,
        ask_execution=tuple(metrics) if side == "A" else (0,) * 7,
    )
    return fixture(r, kind), b, e, [publication(4, values, cvd=cvd, known=known)], audit


@pytest.mark.parametrize(
    "kind", ["buy-other", "sell-other", "buy-same", "buy-net-only", "cancel-only"]
)
def test_complete_manual_execution_and_absorption_oracle(kind):
    check(execution_case(kind))


def test_literal_entire_protocol_identity_and_fresh_body():
    assert canonical(witness.protocol()) == canonical(PROTOCOL)
    assert witness.protocol_sha256() == PROTOCOL_PIN
    changed = witness.protocol()
    changed["constants"]["MAX_RECORDS"] = 0
    changed["feature_names"].reverse()
    changed["authority_flags"][0][1] = True
    assert canonical(witness.protocol()) == canonical(PROTOCOL)
    assert len(NAMES) == 37 and len(SOURCE_PINS) == 9 and len(FLAGS) == 20


@pytest.mark.parametrize("name,names", list(SCHEMAS.items()))
def test_exact_frozen_slotted_public_dataclasses(name, names):
    cls = getattr(witness, name)
    assert tuple(field.name for field in fields(cls)) == names
    assert cls.__dataclass_params__.frozen is True
    assert tuple(cls.__slots__) == names


def test_required_public_signatures_have_no_defaults_or_hidden_options():
    expected_names = {
        "protocol": (),
        "protocol_sha256": (),
        "fixture_sha256": ("fixture", "expected_protocol_sha256"),
        "replay": ("fixture", "expected_fixture_sha256", "expected_protocol_sha256"),
        "verify": (
            "witness",
            "fixture",
            "expected_fixture_sha256",
            "expected_protocol_sha256",
            "expected_witness_sha256",
        ),
    }
    for name, names in expected_names.items():
        params = inspect.signature(getattr(witness, name)).parameters
        assert tuple(params) == names
        assert all(param.default is inspect.Parameter.empty for param in params.values())
        assert all(
            params[key].kind is inspect.Parameter.KEYWORD_ONLY
            for key in names
            if key.startswith("expected_")
        )
    assert issubclass(witness.FeaturePublicationWitnessError, ValueError)


def test_unknown_flow_counts_records_not_quantities_and_f_is_not_second_trade():
    r, b, e = deep_seed()
    for side, price, size, oid in (("B", ASK, 3, 99), ("A", BID, 2, 100), ("N", ASK, 999, 101)):
        r.append(record(len(r) + 1, 0, "T", side, price, size, oid, last=oid == 101))
        b.append(None)
    e.append(event(len(r), START))
    p = publication(4, hand_values(cvd=1, known=2, unknown=1), cvd=1, known=2, unknown=1)
    check(
        (
            fixture(r, "unknown-count"),
            b,
            e,
            [p],
            {
                "completed_events": 4,
                "temporal_resets": 1,
                "trade_B_volume": 3,
                "trade_A_volume": 2,
                "trade_N_volume": 999,
            },
        )
    )


@pytest.mark.parametrize(
    "reason,specs,audit",
    [
        (
            "without_trade",
            [("F", "A", ASK, 4, 2)],
            {"fill_without_trade_records": 1, "fill_without_trade_volume": 4},
        ),
        (
            "unknown_aggressor",
            [("T", "N", ASK, 4, 99), ("F", "A", ASK, 4, 2)],
            {
                "trade_N_volume": 4,
                "fill_unknown_aggressor_records": 1,
                "fill_unknown_aggressor_volume": 4,
            },
        ),
        (
            "aggressor",
            [("T", "B", ASK, 4, 99), ("F", "B", ASK, 4, 2)],
            {"trade_B_volume": 4, "fill_aggressor_records": 1, "fill_aggressor_volume": 4},
        ),
        (
            "price_mismatch",
            [("T", "B", ASK, 4, 99), ("F", "A", ASK + TICK, 4, 2)],
            {
                "trade_B_volume": 4,
                "fill_price_mismatch_records": 1,
                "fill_price_mismatch_volume": 4,
            },
        ),
        (
            "unmatched_book",
            [("T", "B", ASK, 4, 99), ("F", "A", ASK, 4, 98)],
            {
                "trade_B_volume": 4,
                "fill_unmatched_book_records": 1,
                "fill_unmatched_book_volume": 4,
            },
        ),
    ],
)
def test_unmatched_fill_is_separate_view_not_passive_volume(reason, specs, audit):
    r, b, e = deep_seed()
    for index, (action, side, price, size, oid) in enumerate(specs):
        r.append(record(len(r) + 1, 0, action, side, price, size, oid, index == len(specs) - 1))
        b.append(("A", ASK, 10) if oid == 2 else None)
    e.append(event(len(r), START))
    cvd = 4 if any(action == "T" and side == "B" for action, side, *_ in specs) else 0
    unknown = int(any(action == "T" and side == "N" for action, side, *_ in specs))
    known = int(cvd != 0)
    p = publication(
        4, hand_values(cvd=cvd, known=known, unknown=unknown), cvd=cvd, known=known, unknown=unknown
    )
    check((fixture(r, reason), b, e, [p], {"completed_events": 4, "temporal_resets": 1, **audit}))


@pytest.mark.parametrize("fills", [(5,), (3, 2)])
def test_matched_fill_group_cannot_exceed_its_trade_summary(fills):
    r, _, _ = deep_seed()
    r.append(record(10, 0, "T", "B", ASK, 4, 99, False))
    for index, size in enumerate(fills):
        r.append(record(len(r) + 1, 0, "F", "A", ASK, size, 2, index == len(fills) - 1))
    value = fixture(r, "overmatched")
    assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == input_pin(value)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


def test_above_displayed_fill_is_a_separate_audit_and_linked_reload_is_bounded():
    r, b, e = deep_seed()
    specs = [
        ("T", "B", ASK, 12, 99, None),
        ("F", "A", ASK, 12, 2, ("A", ASK, 10)),
        ("C", "A", ASK, 10, 2, ("A", ASK, 10)),
        ("A", "A", ASK, 10, 3, None),
    ]
    for index, (action, side, price, size, oid, before) in enumerate(specs):
        r.append(record(len(r) + 1, 0, action, side, price, size, oid, index == 3))
        b.append(before)
    e.append(event(len(r), START))
    check(
        (
            fixture(r, "above-display"),
            b,
            e,
            [
                publication(
                    4,
                    hand_values(cvd=12, known=1, ask_execution=(12, 12, 10, 0, 0, 10, 0)),
                    cvd=12,
                    known=1,
                )
            ],
            {
                "completed_events": 4,
                "temporal_resets": 1,
                "trade_B_volume": 12,
                "fill_matched_passive_records": 1,
                "fill_matched_passive_volume": 12,
                "fill_above_displayed_volume": 2,
                "A_passive_volume": 12,
                "A_held_top_passive_volume": 12,
                "A_linked_decrease_volume": 10,
                "A_other_id_reload_volume": 10,
            },
        )
    )


def test_equal_time_later_opposing_event_never_changes_earlier_publication():
    original = execution_case()
    first, first_body = check(original)
    value, b, e, pubs, audit = original
    r = list(value.records)
    b, e, audit = list(b), list(e), dict(audit)
    additions = [
        ("T", "A", BID, 3, 100, None),
        ("F", "B", BID, 3, 1, ("B", BID, 10)),
        ("C", "B", BID, 3, 1, ("B", BID, 10)),
        ("M", "B", BID, 10, 1, ("B", BID, 7)),
    ]
    for index, (action, side, price, size, oid, before) in enumerate(additions):
        r.append(record(len(r) + 1, 0, action, side, price, size, oid, index == 3))
        b.append(before)
    e.append(event(len(r), START))
    audit.update(
        {
            "completed_events": 5,
            "trade_A_volume": 3,
            "fill_matched_passive_records": 2,
            "fill_matched_passive_volume": 9,
            "B_passive_volume": 3,
            "B_held_top_passive_volume": 3,
            "B_linked_decrease_volume": 3,
            "B_same_id_reload_volume": 3,
            "B_same_id_net_refresh_volume": 3,
        }
    )
    extended_value = replace(value, records=tuple(r))
    later, later_body = check((extended_value, b, e, pubs, audit))
    assert later.fixture_sha256 != first.fixture_sha256
    assert later.witness_sha256 != first.witness_sha256
    assert later.prefix_context_sha256 == first.prefix_context_sha256
    assert later.record_audits[: len(first.record_audits)] == first.record_audits
    assert later.completed_events[:4] == first.completed_events
    assert later.publications == first.publications
    assert later_body["publications"] == first_body["publications"]
    assert later.publication_count == 1 and later.quote_count == 5


def test_cadence_skipped_completions_still_update_history_and_prior_gap():
    value, b, e, pubs, audit = execution_case()
    r, b, e, pubs, audit = list(value.records), list(b), list(e), list(pubs), dict(audit)
    for offset in (900000000, S, 1900000000, 2 * S):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset))
        if offset in (S, 2 * S):
            count = 4 if offset == S else 6
            pubs.append(
                publication(
                    len(e),
                    hand_values(
                        cvd=6,
                        known=1,
                        count=count,
                        gap=100000000,
                        ask_execution=(6, 6, 6, 0, 0, 6, 0),
                    ),
                    cvd=6,
                    known=1,
                )
            )
    audit["completed_events"] = 8
    result, _ = check((replace(value, records=tuple(r)), b, e, pubs, audit))
    assert tuple(p.quote_ordinal for p in result.publications) == (3, 5, 7)


def test_rolling_cutoff_minus_one_equality_plus_one():
    r, b, e = deep_seed(markers=False)
    for offset, side, price, size in (
        (-5 * S - 1, "B", ASK, 7),
        (-5 * S, "A", BID, 2),
        (-5 * S + 1, "B", ASK, 3),
    ):
        r.append(record(len(r) + 1, offset, "T", side, price, size, 99))
        b.append(None)
        e.append(event(len(r), START + offset))
    for offset in (-S, 0):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset))
    check(
        (
            fixture(r, "cutoffs"),
            b,
            e,
            [publication(6, hand_values(cvd=1, known=2, count=4), cvd=1, known=2)],
            {
                "completed_events": 6,
                "temporal_resets": 1,
                "trade_A_volume": 2,
                "trade_B_volume": 10,
            },
        )
    )


@pytest.mark.parametrize("delta", [0, 1])
def test_feature_warmup_exact_equality_and_one_nanosecond_short(delta):
    at = -5 * S + delta
    r, b, e = deep_seed(at=at, markers=False)
    for offset in (-S, 0):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset, first=START + at))
    reason = "insufficient_feature_warmup" if delta else None
    check(
        (
            fixture(r, "warmup" + str(delta)),
            b,
            e,
            [publication(3, hand_values(), reason=reason)],
            {"completed_events": 3, "temporal_resets": 1},
        )
    )


@pytest.mark.parametrize("delta", [0, 1])
def test_completed_gap_retains_equality_and_resets_only_strict_excess(delta):
    value, b, e, pubs, audit = execution_case()
    r, b, e, pubs, audit = list(value.records), list(b), list(e), list(pubs), dict(audit)
    offset = 5 * S + delta
    r.append(record(len(r) + 1, offset))
    b.append(None)
    e.append(
        event(
            len(r),
            START + offset,
            first=START + offset if delta else START - 10 * S,
            inactivity=bool(delta),
            reset=bool(delta),
        )
    )
    cvd, known = (0, 0) if delta else (6, 1)
    values = hand_values(
        cvd=cvd,
        known=known,
        gap=offset,
        count=1 if delta else 2,
        ask_execution=(0,) * 7 if delta else (6, 6, 6, 0, 0, 6, 0),
    )
    pubs.append(
        publication(
            5, values, cvd=cvd, known=known, reason="insufficient_feature_warmup" if delta else None
        )
    )
    audit["completed_events"] = 5
    audit["temporal_resets"] = 2 if delta else 1
    check((replace(value, records=tuple(r)), b, e, pubs, audit))


def test_inactivity_fires_before_noncompleting_record_not_only_at_f_last(monkeypatch):
    value, b, e, pubs, audit = execution_case()
    r, b, e, pubs, audit = list(value.records), list(b), list(e), list(pubs), dict(audit)
    first = record(len(r) + 1, 5 * S + 1, last=False)
    last = record(len(r) + 2, 5 * S + 2)
    r.extend((first, last))
    b.extend((None, None))
    e.append(event(len(r), last.ts_recv, first=last.ts_recv, inactivity=True, reset=True))
    pubs.append(
        publication(5, hand_values(gap=5 * S + 2, count=1), reason="insufficient_feature_warmup")
    )
    audit.update({"completed_events": 5, "temporal_resets": 2})
    trace = []
    old_init, old_apply = ofi.OfiWindow.__init__, strict.StrictBook.apply

    def traced_init(self):
        trace.append("ofi-reset")
        old_init(self)

    def traced_apply(self, item):
        trace.append(item.record_ordinal)
        old_apply(self, item)

    monkeypatch.setattr(ofi.OfiWindow, "__init__", traced_init)
    monkeypatch.setattr(strict.StrictBook, "apply", traced_apply)
    check((replace(value, records=tuple(r)), b, e, pubs, audit))
    # check() rebuilds twice; each reconstruction must reset before first raw
    # record of the long-gap event, not after applying it or only at completion.
    positions = [i for i, item in enumerate(trace) if item == first.record_ordinal]
    assert len(positions) == 2
    assert all(trace[i - 1] == "ofi-reset" for i in positions)


@pytest.mark.parametrize("delta", [0, 1])
def test_spanning_execution_exclusion_does_not_erase_completed_trade_flow(delta):
    r, b, e = deep_seed(markers=False)
    r.append(record(8, -6 * S))
    b.append(None)
    e.append(event(8, START - 6 * S))
    specs = (
        (-5 * S - delta, "T", "B", ASK, 4, 99, None),
        (-5 * S - delta, "F", "A", ASK, 4, 2, ("A", ASK, 10)),
        (0, "C", "A", ASK, 4, 2, ("A", ASK, 10)),
        (0, "M", "A", ASK, 10, 2, ("A", ASK, 6)),
    )
    for index, (offset, action, side, price, size, oid, before) in enumerate(specs):
        r.append(record(len(r) + 1, offset, action, side, price, size, oid, index == 3))
        b.append(before)
    e.append(event(len(r), START, first=START, inactivity=True, reset=True, stale=bool(delta)))
    metrics = (0,) * 7 if delta else (4, 0, 4, 0, 0, 0, 0)
    audit = {"completed_events": 2 if delta else 3, "temporal_resets": 2}
    if delta:
        audit["stale_spanning_events_excluded"] = 1
    else:
        audit.update(
            {
                "trade_B_volume": 4,
                "fill_matched_passive_records": 1,
                "fill_matched_passive_volume": 4,
                "fill_above_displayed_volume": 0,
                "A_passive_volume": 4,
                "A_linked_decrease_volume": 4,
            }
        )
    check(
        (
            fixture(r, "span" + str(delta)),
            b,
            e,
            [
                publication(
                    3,
                    hand_values(cvd=4, known=1, gap=6 * S, count=1, ask_execution=metrics),
                    cvd=4,
                    known=1,
                    reason="insufficient_feature_warmup",
                )
            ],
            audit,
        )
    )


def test_generic_visible_reload_is_not_passive_execution_or_hidden_liquidity():
    r, b, e = deep_seed()
    pubs = []
    declared = (
        (0, 4, 7, 10, 10, -3, 54, 57, 0, 0, 3),
        (S, 8, 10, 4, 7, -2, 58, 60, 4, 3, 3),
        (2 * S, 20, 20, 8, 10, 0, 70, 70, 6, 3, 4),
    )
    for offset, bq, aq, oldb, olda, total, bd, ad, br, ar, count in declared:
        r.append(record(len(r) + 1, offset, "M", "B", BID, bq, 1, False))
        b.append(("B", BID, oldb))
        r.append(record(len(r) + 1, offset, "M", "A", ASK, aq, 2))
        b.append(("A", ASK, olda))
        e.append(event(len(r), START + offset, bq=bq, aq=aq))
        values = hand_values(
            bq=bq,
            aq=aq,
            bd=bd,
            ad=ad,
            ofitotal=total,
            count=count,
            breload=br,
            areload=ar,
            bid_execution=(0, 0, 0, 6, 0, 0, 0),
            ask_execution=(0, 0, 0, 3, 0, 0, 0),
        )
        pubs.append(publication(len(e), values, total=total))
    check(
        (
            fixture(r, "visible-reload"),
            b,
            e,
            pubs,
            {
                "completed_events": 6,
                "temporal_resets": 1,
                "B_unlinked_decrease_volume": 6,
                "A_unlinked_decrease_volume": 3,
            },
        )
    )


def test_price_departure_and_return_cannot_reactivate_old_reload_credit():
    r = [
        record(1, 0, "R"),
        record(2, -10 * S, "A", "B", BID, 10, 1, False),
        record(3, -10 * S, "A", "A", ASK, 10, 2),
        record(4, -5 * S),
        record(5, -S),
    ]
    b = [None] * 5
    e = [event(3, START - 10 * S, reset=True), event(4, START - 5 * S), event(5, START - S)]
    pubs = []
    declarations = (
        (0, BID, ASK, 5, 7, BID, ASK, 10, 10, -2, 0.0, 0.0, 0, 0, 0, 3, 5, 3),
        (
            S,
            BID + 2 * TICK,
            ASK + 2 * TICK,
            10,
            10,
            BID,
            ASK,
            5,
            7,
            15,
            2.0,
            2.0,
            2.0,
            0,
            0,
            3,
            10,
            10,
        ),
        (
            2 * S,
            BID,
            ASK,
            10,
            10,
            BID + 2 * TICK,
            ASK + 2 * TICK,
            10,
            10,
            -5,
            0.0,
            2.0,
            4.0,
            0,
            0,
            4,
            20,
            20,
        ),
    )
    for (
        offset,
        bp,
        ap,
        bq,
        aq,
        oldbp,
        oldap,
        oldbq,
        oldaq,
        total,
        change,
        midrange,
        travel,
        br,
        ar,
        count,
        bu,
        au,
    ) in declarations:
        r.append(record(len(r) + 1, offset, "M", "B", bp, bq, 1, False))
        b.append(("B", oldbp, oldbq))
        r.append(record(len(r) + 1, offset, "M", "A", ap, aq, 2))
        b.append(("A", oldap, oldaq))
        e.append(event(len(r), START + offset, bid=bp, ask=ap, bq=bq, aq=aq))
        values = hand_values(
            bq=bq,
            aq=aq,
            bd=bq,
            ad=aq,
            bspan=0,
            aspan=0,
            ofitotal=total,
            count=count,
            change=change,
            midrange=midrange,
            travel=travel,
            breload=br,
            areload=ar,
            bid_execution=(0, 0, 0, bu, 0, 0, 0),
            ask_execution=(0, 0, 0, au, 0, 0, 0),
        )
        pubs.append(publication(len(e), values, total=total))
    check(
        (
            fixture(r, "depart-return"),
            b,
            e,
            pubs,
            {
                "completed_events": 6,
                "temporal_resets": 1,
                "B_unlinked_decrease_volume": 20,
                "A_unlinked_decrease_volume": 20,
            },
        )
    )


@pytest.mark.parametrize("direction", [-1, 1])
def test_mirrored_absorption_proxy_uses_mid_change_denominator_not_only_cvd(direction):
    r = [
        record(1, 0, "R"),
        record(2, -10 * S, "A", "B", BID, 10, 1, False),
        record(3, -10 * S, "A", "A", ASK, 10, 2),
        record(4, -5 * S),
        record(5, -S),
    ]
    b = [None] * 5
    e = [event(3, START - 10 * S, reset=True), event(4, START - 5 * S), event(5, START - S)]
    bp, ap = BID + direction * 2 * TICK, ASK + direction * 2 * TICK
    r.extend(
        (
            record(
                6, 0, "T", "B" if direction > 0 else "A", ap if direction > 0 else bp, 4, 99, False
            ),
            record(7, 0, "M", "B", bp, 10, 1, False),
            record(8, 0, "M", "A", ap, 10, 2),
        )
    )
    b.extend((None, ("B", BID, 10), ("A", ASK, 10)))
    e.append(event(8, START, bid=bp, ask=ap))
    values = hand_values(
        bd=10,
        ad=10,
        bspan=0,
        aspan=0,
        ofitotal=20 * direction,
        cvd=4 * direction,
        known=1,
        change=2.0 * direction,
        midrange=2.0,
        travel=2.0,
        bid_execution=(0, 0, 0, 10, 0, 0, 0),
        ask_execution=(0, 0, 0, 10, 0, 0, 0),
    )
    check(
        (
            fixture(r, "moving-buy" if direction > 0 else "moving-sell"),
            b,
            e,
            [publication(4, values, cvd=4 * direction, known=1, total=20 * direction)],
            {
                "completed_events": 4,
                "temporal_resets": 1,
                "trade_B_volume" if direction > 0 else "trade_A_volume": 4,
                "B_unlinked_decrease_volume": 10,
                "A_unlinked_decrease_volume": 10,
            },
        )
    )


def capacity_case():
    large = C["MAX_INT"]
    ap = large // TICK * TICK
    bp = ap - TICK
    r = [record(1, 0, "R")]
    r.extend(record(i, -10 * S, last=False) for i in range(2, 128))
    r.extend(
        (
            record(128, -10 * S, "A", "B", bp, large, large - 1, False),
            record(129, -10 * S, "A", "A", ap, large, large),
        )
    )
    e = [event(129, START - 10 * S, bid=bp, ask=ap, bq=large, aq=large, reset=True)]
    pubs = []
    for index in range(1, 128):
        offset = (
            -10 * S
            if index <= 31
            else -5 * S
            if index <= 63
            else -S
            if index <= 95
            else (index - 96) * S
        )
        r.append(record(len(r) + 1, offset))
        e.append(event(len(r), START + offset, bid=bp, ask=ap, bq=large, aq=large))
        if index >= 96:
            pindex = index - 96
            count = 65 if pindex == 0 else 33 + pindex if pindex <= 4 else 6
            pubs.append(
                publication(
                    index + 1,
                    hand_values(
                        bq=large, aq=large, bd=large, ad=large, bspan=0, aspan=0, count=count
                    ),
                )
            )
    value = fixture(r, "capacity")
    value = replace(
        value, fixture_id="synthetic-" + "f" * 54, source_session="synthetic-" + "s" * 54
    )
    return value, [None] * 256, e, pubs, {"completed_events": 128, "temporal_resets": 1}


def test_complete_capacity_measurement_256_records_128_events_32_publications():
    case = capacity_case()
    result, body = check(case)
    assert (
        result.record_count,
        result.completed_event_count,
        result.quote_count,
        result.publication_count,
    ) == (256, 128, 128, 32)
    assert len(result.fixture.fixture_id) == len(result.fixture.source_session) == 64
    assert all(len(pub.feature_values) == 37 for pub in result.publications)
    complete_bytes = canonical({k: v for k, v in body.items() if k != "witness_sha256"})
    assert len(complete_bytes) < 1048576
    assert len(canonical(input_body(case[0]))) < len(complete_bytes)
    # This is one full constructed finite-large measurement, not a universal
    # maximum or native DBN uint32 quantity-capacity proof.
    assert result.fixture.records[127].size == 9223372036854775807


@pytest.mark.parametrize("which", ["input-exact", "input-excess", "result-exact", "result-excess"])
def test_complete_canonical_input_and_result_caps_are_distinct(monkeypatch, which):
    case = capacity_case()
    value = case[0]
    body = expected(*case)
    ibytes = len(canonical(input_body(value)))
    rbytes = len(canonical({k: v for k, v in body.items() if k != "witness_sha256"}))
    assert len(canonical(PROTOCOL)) < ibytes < rbytes
    limit = {
        "input-exact": ibytes,
        "input-excess": ibytes - 1,
        "result-exact": rbytes,
        "result-excess": rbytes - 1,
    }[which]
    monkeypatch.setattr(witness, "MAX_CANONICAL_BYTES", limit)
    constructed = []
    original_init = strict.StrictBook.__init__

    def count_book(self):
        constructed.append("book-after-whole-input-preflight")
        original_init(self)

    monkeypatch.setattr(strict.StrictBook, "__init__", count_book)
    if which == "input-excess":
        with pytest.raises(
            witness.FeaturePublicationWitnessError,
            match="Complete canonical witness body exceeds bound",
        ):
            witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)
    else:
        assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == input_pin(
            value
        )
    assert constructed == []
    if which == "result-exact":
        result = witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )
        assert canonical(asdict(result)) == canonical(body)
    else:
        with pytest.raises(
            witness.FeaturePublicationWitnessError,
            match="Complete canonical witness body exceeds bound",
        ):
            witness.replay(
                value,
                expected_fixture_sha256=input_pin(value),
                expected_protocol_sha256=PROTOCOL_PIN,
            )
    assert len(constructed) == (0 if which == "input-excess" else 1)


@pytest.mark.parametrize("delta", [0, -1])
def test_entire_literal_protocol_body_exact_and_excess_byte_cap(monkeypatch, delta):
    monkeypatch.setattr(witness, "MAX_CANONICAL_BYTES", len(canonical(PROTOCOL)) + delta)
    if delta:
        with pytest.raises(
            witness.FeaturePublicationWitnessError,
            match="Complete canonical witness body exceeds bound",
        ):
            witness.protocol_sha256()
    else:
        assert witness.protocol_sha256() == PROTOCOL_PIN


def test_aggregate_standing_quantity_can_exceed_input_scalar_limit_without_clipping():
    large = C["MAX_INT"]
    r = [record(1, 0, "R")]
    for side, price, oid in (("B", BID, 1), ("B", BID, 3), ("A", ASK, 2), ("A", ASK, 4)):
        r.append(record(len(r) + 1, -10 * S, "A", side, price, large, oid, oid == 4))
    b = [None] * len(r)
    e = [event(5, START - 10 * S, bq=2 * large, aq=2 * large, reset=True)]
    for offset in (-5 * S, -S, 0):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset, bq=2 * large, aq=2 * large))
    result, _ = check(
        (
            fixture(r, "aggregate"),
            b,
            e,
            [
                publication(
                    4,
                    hand_values(
                        bq=2 * large, aq=2 * large, bd=2 * large, ad=2 * large, bspan=0, aspan=0
                    ),
                )
            ],
            {"completed_events": 4, "temporal_resets": 1},
        )
    )
    assert result.publications[0].quote.bid_qty > C["MAX_INT"]


def test_trade_zero_id_allowed_and_nonmutating_existing_trade_prestate_is_derived():
    value, b, e, pubs, audit = execution_case("buy-net-only")
    r = list(value.records)
    r[9] = replace(r[9], order_id=0)
    check((replace(value, records=tuple(r)), b, e, pubs, audit))
    # An unknown-aggressor T can expose a real resting pre-state without ever
    # mutating it or gaining a sign; the full record audit must retain that fact.
    r, b, e = deep_seed()
    r.append(record(10, 0, "T", "N", BID, 3, 1))
    b.append(("B", BID, 10))
    e.append(event(10, START))
    check(
        (
            fixture(r, "existing-trade"),
            b,
            e,
            [publication(4, hand_values(unknown=1), unknown=1)],
            {"completed_events": 4, "temporal_resets": 1, "trade_N_volume": 3},
        )
    )


def test_top_five_depth_excludes_sixth_level_and_uses_actual_order_aggregation():
    r = [record(1, 0, "R")]
    for level, quantity in enumerate((10, 20, 30, 40, 50, 1000)):
        for side, price, oid in (
            ("B", BID - level * TICK, 1 + level),
            ("A", ASK + level * TICK, 101 + level),
        ):
            r.append(
                record(
                    len(r) + 1,
                    -10 * S,
                    "A",
                    side,
                    price,
                    quantity,
                    oid,
                    last=side == "A" and level == 5,
                )
            )
    b = [None] * len(r)
    e = [event(13, START - 10 * S, reset=True)]
    for offset in (-5 * S, -S, 0):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset))
    check(
        (
            fixture(r, "six-levels"),
            b,
            e,
            [publication(4, hand_values(bd=150, ad=150, bspan=4, aspan=4))],
            {"completed_events": 4, "temporal_resets": 1},
        )
    )


@pytest.mark.parametrize("spread", [1, 2])
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_readiness_end_buffer_adjacent_boundary_and_spread_precedence(spread, delta):
    end_offset = C["WINDOW_END_NS"] - START - 17 * S + delta
    initial = end_offset - 6 * S
    r, b, _ = deep_seed(at=initial, markers=False)
    if spread == 2:
        r = [replace(item, price=item.price + TICK) if item.side == "A" else item for item in r]
    ap = ASK + (spread - 1) * TICK
    e = [event(7, START + initial, ask=ap, first=START + initial, inactivity=True, reset=True)]
    first_reason = "spread_not_one_tick" if spread == 2 else "insufficient_feature_warmup"
    pubs = [publication(1, hand_values(gap=0, count=1), reason=first_reason)]
    for offset, count in ((end_offset - S, 2), (end_offset, 2)):
        r.append(record(len(r) + 1, offset))
        b.append(None)
        e.append(event(len(r), START + offset, ask=ap, first=START + initial))
        reason = (
            "spread_not_one_tick"
            if spread == 2
            else ("insufficient_window_for_hold" if offset == end_offset and delta >= 0 else None)
        )
        pubs.append(
            publication(
                len(e),
                hand_values(gap=5 * S if count == 2 and len(e) == 2 else S, count=count),
                reason=reason,
            )
        )
    check(
        (
            fixture(r, "end" + str(spread) + ("minus" if delta < 0 else str(delta))),
            b,
            e,
            pubs,
            {"completed_events": 3, "temporal_resets": 1},
        )
    )


def invocation(api, value, submitted=None, **overrides):
    pins = {"expected_protocol_sha256": PROTOCOL_PIN}
    if api != "fixture_sha256":
        pins["expected_fixture_sha256"] = input_pin(value)
    if api == "verify":
        pins["expected_witness_sha256"] = (
            submitted.witness_sha256 if submitted is not None else "0" * 64
        )
    pins.update(overrides)
    args = (submitted, value) if api == "verify" else (value,)
    return getattr(witness, api)(*args, **pins)


APIS = ("fixture_sha256", "replay", "verify")
BAD_PINS = ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, None, 0, True)


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize("bad", BAD_PINS)
def test_all_expected_pin_syntax_precedes_any_fixture_field_access(monkeypatch, api, bad):
    value = execution_case()[0]
    old_get = witness.FeatureWitnessFixture.__getattribute__

    def no_fixture(self, name):
        if self is value and name in SCHEMAS["FeatureWitnessFixture"]:
            raise AssertionError("fixture touched before expectation syntax")
        return old_get(self, name)

    monkeypatch.setattr(witness.FeatureWitnessFixture, "__getattribute__", no_fixture)
    pins = {"expected_protocol_sha256": PROTOCOL_PIN}
    if api != "fixture_sha256":
        pins["expected_fixture_sha256"] = "0" * 64
    if api == "verify":
        pins["expected_witness_sha256"] = bad
    else:
        pins["expected_protocol_sha256"] = bad
    args = (None, value) if api == "verify" else (value,)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        getattr(witness, api)(*args, **pins)


@pytest.mark.parametrize(
    "api,pin_name",
    [
        ("replay", "expected_fixture_sha256"),
        ("verify", "expected_fixture_sha256"),
        ("verify", "expected_protocol_sha256"),
    ],
)
@pytest.mark.parametrize("bad", BAD_PINS)
def test_complementary_expected_pin_syntax_also_precedes_any_fixture_access(
    monkeypatch, api, pin_name, bad
):
    value = execution_case()[0]
    old_get = witness.FeatureWitnessFixture.__getattribute__

    def no_fixture(self, name):
        if self is value and name in SCHEMAS["FeatureWitnessFixture"]:
            raise AssertionError("fixture accessed before complementary expected pin syntax")
        return old_get(self, name)

    monkeypatch.setattr(witness.FeatureWitnessFixture, "__getattribute__", no_fixture)
    pins = {"expected_protocol_sha256": PROTOCOL_PIN, "expected_fixture_sha256": "0" * 64}
    if api == "verify":
        pins["expected_witness_sha256"] = "0" * 64
    pins[pin_name] = bad
    with pytest.raises(witness.FeaturePublicationWitnessError):
        getattr(witness, api)(*((None, value) if api == "verify" else (value,)), **pins)


@pytest.mark.parametrize("api", APIS)
def test_protocol_conflict_precedes_source_reads_and_fixture_access(monkeypatch, api):
    value = execution_case()[0]
    old_get = witness.FeatureWitnessFixture.__getattribute__

    def no_fixture(self, name):
        if self is value and name in SCHEMAS["FeatureWitnessFixture"]:
            raise AssertionError("fixture touched despite protocol conflict")
        return old_get(self, name)

    monkeypatch.setattr(witness.FeatureWitnessFixture, "__getattribute__", no_fixture)
    monkeypatch.setattr(
        Path, "open", lambda *a, **k: pytest.fail("source read before protocol conflict")
    )
    pins = {"expected_protocol_sha256": "0" * 64}
    if api != "fixture_sha256":
        pins["expected_fixture_sha256"] = "1" * 64
    if api == "verify":
        pins["expected_witness_sha256"] = "2" * 64
    with pytest.raises(witness.FeaturePublicationWitnessError):
        getattr(witness, api)(*((None, value) if api == "verify" else (value,)), **pins)


def test_constructors_do_not_traverse_any_numeric_slots_or_child_record(monkeypatch):
    access = []
    old_get = witness.ConstructedMboRecord.__getattribute__

    def numeric_spy(self, name):
        if name in ("price", "size", "order_id"):
            access.append(name)
            raise AssertionError("numeric field accessed by metadata constructor")
        return old_get(self, name)

    monkeypatch.setattr(witness.ConstructedMboRecord, "__getattribute__", numeric_spy)
    source = record(1, 0, "R")
    fixture((source, source, source), "constructor")
    assert access == []


@pytest.mark.parametrize("api", APIS)
@pytest.mark.parametrize(
    "field,bad",
    [
        ("record_ordinal", 0),
        ("instrument_id", 2),
        ("ts_recv", START - 2 * S),
        ("ts_event", START + 1),
        ("ts_in_delta", -1),
        ("sequence", C["MAX_SEQUENCE"] + 1),
        ("action", "R"),
        ("side", "N"),
        ("flags", 0),
    ],
)
def test_invalid_final_metadata_precedes_first_numeric_attribute_retrieval(
    monkeypatch, api, field, bad
):
    value = execution_case()[0]
    retained_pin = input_pin(value)
    object.__setattr__(value.records[-1], field, bad)
    first = value.records[0]
    old_get = witness.ConstructedMboRecord.__getattribute__
    access = []

    def no_numeric(self, name):
        if name in ("price", "size", "order_id"):
            access.append((old_get(self, "record_ordinal"), name))
            raise AssertionError("numeric touched before all metadata passes")
        return old_get(self, name)

    monkeypatch.setattr(witness.ConstructedMboRecord, "__getattribute__", no_numeric)
    assert first is value.records[0]
    pins = {"expected_protocol_sha256": PROTOCOL_PIN}
    if api != "fixture_sha256":
        pins["expected_fixture_sha256"] = retained_pin
    if api == "verify":
        pins["expected_witness_sha256"] = "0" * 64
    with pytest.raises(witness.FeaturePublicationWitnessError):
        getattr(witness, api)(*((None, value) if api == "verify" else (value,)), **pins)
    assert access == []


@pytest.mark.parametrize("missing", ["price", "size", "order_id"])
def test_deleted_early_numeric_slot_is_only_observed_after_later_metadata_refusal(
    monkeypatch, missing
):
    value = execution_case()[0]
    object.__delattr__(value.records[0], missing)
    object.__setattr__(value.records[-1], "ts_in_delta", -1)
    old_get = witness.ConstructedMboRecord.__getattribute__

    def no_numeric(self, name):
        if name in ("price", "size", "order_id"):
            raise AssertionError("hasattr or numeric traversal in metadata phase")
        return old_get(self, name)

    monkeypatch.setattr(witness.ConstructedMboRecord, "__getattribute__", no_numeric)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("price", 0),
        ("price", BID + 1),
        ("price", C["MAX_INT"] + 1),
        ("price", True),
        ("price", 1.0),
        ("size", 0),
        ("size", -1),
        ("size", C["MAX_INT"] + 1),
        ("size", True),
        ("size", 1.0),
        ("order_id", 0),
        ("order_id", -1),
        ("order_id", C["MAX_INT"] + 1),
        ("order_id", True),
        ("order_id", 1.0),
    ],
)
def test_all_numerical_validation_precedes_any_book_or_feature_construction(
    monkeypatch, field, bad
):
    value = execution_case()[0]
    object.__setattr__(value.records[-1], field, bad)
    monkeypatch.setattr(
        strict.StrictBook,
        "__init__",
        lambda *a: pytest.fail("book before complete numeric preflight"),
    )
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256="0" * 64, expected_protocol_sha256=PROTOCOL_PIN
        )


@pytest.mark.parametrize("name", SCHEMAS["ConstructedMboRecord"])
def test_missing_input_record_fields_fail_closed(name):
    value = execution_case()[0]
    object.__delattr__(value.records[-1], name)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("name", SCHEMAS["FeatureWitnessFixture"])
def test_missing_fixture_fields_fail_closed(name):
    value = execution_case()[0]
    object.__delattr__(value, name)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("fixture_id", "synthetic-"),
        ("fixture_id", "ordinary"),
        ("fixture_id", "synthetic-é"),
        ("fixture_id", "synthetic-" + "x" * 55),
        ("fixture_id", "synthetic-x.y"),
        ("fixture_id", "synthetic-x/y"),
        ("fixture_id", "synthetic-x\\y"),
        ("fixture_id", None),
        ("source_session", "synthetic-"),
        ("source_session", "2025-04-07"),
        ("utc_date", "2025-04-08"),
        ("contract", "6E.FUT"),
        ("contract", "6EM6"),
        ("instrument_id", True),
        ("instrument_id", 2),
        ("records", []),
        ("records", {}),
    ],
)
def test_poisoned_fixture_metadata_has_exact_types_context_and_identifiers(field, bad):
    value = execution_case()[0]
    object.__setattr__(value, field, bad)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("record_ordinal", True),
        ("instrument_id", True),
        ("ts_recv", True),
        ("ts_event", True),
        ("ts_in_delta", True),
        ("sequence", True),
        ("flags", True),
        ("action", b"A"),
        ("side", b"A"),
        ("action", "a"),
        ("side", "a"),
        ("flags", 1),
        ("flags", 256),
        ("ts_recv", C["WINDOW_END_NS"]),
        ("ts_recv", C["WARMUP_START_NS"] - 1),
        ("ts_event", -1),
        ("ts_event", C["MAX_INT"] + 1),
        ("ts_in_delta", C["MAX_SEND_DELTA"] + 1),
        ("sequence", -1),
    ],
)
def test_record_metadata_bounds_and_exact_types(field, bad):
    value = execution_case()[0]
    object.__setattr__(value.records[-1], field, bad)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("record_ordinal", 2),
        ("ts_recv", C["GENESIS_NS"] + 1),
        ("ts_event", C["GENESIS_NS"] - 1),
        ("ts_in_delta", 1),
        ("sequence", 1),
        ("action", "N"),
        ("side", "A"),
        ("flags", 0),
        ("price", TICK),
        ("size", 1),
        ("order_id", 1),
    ],
)
def test_genesis_complete_identity_is_mandatory(field, bad):
    value = execution_case()[0]
    object.__setattr__(value.records[0], field, bad)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "action,side",
    [("A", "N"), ("C", "N"), ("M", "N"), ("N", "A"), ("N", "B"), ("T", "X"), ("F", "X")],
)
def test_restricted_action_side_pairs_refuse_before_helpers(action, side):
    value = execution_case()[0]
    object.__setattr__(value.records[-1], "action", action)
    object.__setattr__(value.records[-1], "side", side)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("field", ["price", "size", "order_id"])
def test_n_marker_has_exact_zero_payload(field):
    r, _, _ = deep_seed()
    r.append(record(len(r) + 1, 0))
    value = fixture(r)
    object.__setattr__(value.records[-1], field, 1)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


def test_sequence_not_sorted_and_exchange_clock_not_substituted_for_receive_clock():
    value, b, e, pubs, audit = execution_case()
    changed = []
    for item in value.records:
        if item.record_ordinal == 1:
            changed.append(item)
        else:
            changed.append(
                replace(
                    item,
                    sequence=C["MAX_SEQUENCE"] if item.record_ordinal % 2 else 0,
                    ts_event=item.ts_recv - S,
                    ts_in_delta=C["MAX_SEND_DELTA"],
                )
            )
    check((replace(value, records=tuple(changed)), b, e, pubs, audit))


def test_structural_input_hash_is_not_book_or_publication_acceptance():
    values = [
        fixture(
            (record(1, 0, "R"), record(2, 0, "A", "B", BID, 10, 1, False), record(3, 0)),
            "one-sided",
        ),
        fixture(
            (
                record(1, 0, "R"),
                record(2, -10 * S, "A", "B", BID, 10, 1, False),
                record(3, -10 * S, "A", "A", ASK, 10, 2),
            ),
            "no-publication",
        ),
    ]
    for value in values:
        assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == input_pin(
            value
        )
        with pytest.raises(witness.FeaturePublicationWitnessError):
            witness.replay(
                value,
                expected_fixture_sha256=input_pin(value),
                expected_protocol_sha256=PROTOCOL_PIN,
            )


@pytest.mark.parametrize(
    "spec",
    [
        ("A", "B", BID, 10, 1),
        ("M", "B", BID, 10, 100),
        ("C", "B", BID, 1, 100),
        ("C", "A", BID, 1, 1),
        ("C", "B", BID + TICK, 1, 1),
        ("C", "B", BID, 11, 1),
        ("M", "A", BID, 10, 1),
    ],
)
def test_strict_add_modify_cancel_faults_refuse_entire_validly_pinned_input(spec):
    r, _, _ = deep_seed()
    r.append(record(len(r) + 1, 0, *spec))
    value = fixture(r, "book-fault")
    pin = input_pin(value)
    assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == pin
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(value, expected_fixture_sha256=pin, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("ask", [BID, BID - TICK])
def test_completed_locked_or_crossed_book_is_not_dropped(ask):
    value = fixture(
        (
            record(1, 0, "R"),
            record(2, 0, "A", "B", BID, 10, 1, False),
            record(3, 0, "A", "A", ask, 10, 2),
        )
    )
    assert witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN) == input_pin(value)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


def test_late_book_fault_after_valid_publication_returns_no_subset():
    value = execution_case()[0]
    value = replace(
        value, records=(*value.records, record(len(value.records) + 1, S, "M", "B", BID, 10, 999))
    )
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


@pytest.mark.parametrize(
    "kind", ["record-over", "events-over", "publications-over", "too-short", "no-final-last"]
)
def test_whole_fixture_count_capacity_and_final_event_refusals(kind):
    if kind == "record-over":
        value = capacity_case()[0]
        extra = record(256, 32 * S)
        object.__setattr__(extra, "record_ordinal", 257)
        object.__setattr__(value, "records", (*value.records, extra))
    elif kind == "events-over":
        r = [
            record(1, 0, "R"),
            record(2, -10 * S, "A", "B", BID, 10, 1, False),
            record(3, -10 * S, "A", "A", ASK, 10, 2),
        ]
        r.extend(record(i, 0) for i in range(4, 132))
        value = fixture(r)
    elif kind == "publications-over":
        r, _, _ = deep_seed()
        initial_count = len(r)
        r.extend(record(initial_count + i + 1, i * S) for i in range(33))
        value = fixture(r)
    elif kind == "too-short":
        value = execution_case()[0]
        object.__setattr__(value, "records", value.records[:2])
    else:
        value = execution_case()[0]
        object.__setattr__(value.records[-1], "flags", 0)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        if kind == "publications-over":
            assert witness.fixture_sha256(
                value, expected_protocol_sha256=PROTOCOL_PIN
            ) == input_pin(value)
            witness.replay(
                value,
                expected_fixture_sha256=input_pin(value),
                expected_protocol_sha256=PROTOCOL_PIN,
            )
        else:
            witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("api", APIS)
def test_each_consuming_api_reads_exactly_nine_installed_fixed_sources(monkeypatch, api):
    case = execution_case()
    result, _ = check(case)
    opened = []
    real_open = Path.open
    allowed = {Path(path).name for path, _ in SOURCE_PINS}
    research = Path(witness.__file__).resolve().parent

    def traced_open(path, mode="r", *args, **kwargs):
        assert mode == "rb" and path.name in allowed
        assert path.resolve().parent == research
        opened.append(path.name)
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", traced_open)
    invocation(api, case[0], result)
    assert sorted(opened) == sorted(allowed)


def test_protocol_only_calls_do_not_access_helpers_or_files(monkeypatch):
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("protocol source access"))
    monkeypatch.setattr(Path, "stat", lambda *a, **k: pytest.fail("protocol source stat"))
    assert canonical(witness.protocol()) == canonical(PROTOCOL)
    assert witness.protocol_sha256() == PROTOCOL_PIN


@pytest.mark.parametrize("relative,_pin", SOURCE_PINS)
def test_every_fixed_source_read_failure_refuses_before_payload(monkeypatch, relative, _pin):
    value = execution_case()[0]
    old_open, old_get = Path.open, witness.FeatureWitnessFixture.__getattribute__

    def failed_open(path, *args, **kwargs):
        if path.name == Path(relative).name:
            raise OSError("invented helper read failure")
        return old_open(path, *args, **kwargs)

    def no_fixture(self, name):
        if self is value and name in SCHEMAS["FeatureWitnessFixture"]:
            raise AssertionError("payload reached after source failure")
        return old_get(self, name)

    monkeypatch.setattr(Path, "open", failed_open)
    monkeypatch.setattr(witness.FeatureWitnessFixture, "__getattribute__", no_fixture)
    with pytest.raises(witness.FeaturePublicationWitnessError) as error:
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)
    assert isinstance(error.value.__cause__, OSError)


@pytest.mark.parametrize("relative,_pin", SOURCE_PINS)
def test_every_literal_helper_pin_syntax_checked_before_payload(monkeypatch, relative, _pin):
    value = execution_case()[0]
    changed = tuple((path, "A" * 64 if path == relative else pin) for path, pin in SOURCE_PINS)
    monkeypatch.setattr(witness, "_SOURCE_PINS", changed)
    old_get = witness.FeatureWitnessFixture.__getattribute__

    def no_fixture(self, name):
        if self is value and name in SCHEMAS["FeatureWitnessFixture"]:
            raise AssertionError("payload reached after malformed literal helper pin")
        return old_get(self, name)

    monkeypatch.setattr(witness.FeatureWitnessFixture, "__getattribute__", no_fixture)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "mode", ["drift", "oversize-read", "symlink", "nonregular", "mtime-change"]
)
def test_fixed_source_drift_bounds_links_and_stability_are_not_data_permissions(monkeypatch, mode):
    value = execution_case()[0]
    target = Path(SOURCE_PINS[0][0]).name
    old_open, old_link, old_stat = Path.open, Path.is_symlink, Path.stat
    calls = 0

    class Handle:
        def __init__(self, original):
            self.original = original

        def __enter__(self):
            self.original.__enter__()
            return self

        def __exit__(self, *args):
            return self.original.__exit__(*args)

        def fileno(self):
            return self.original.fileno()

        def read(self, count):
            assert count == 1048577
            raw = self.original.read(count)
            return b"x" * 1048577 if mode == "oversize-read" else b"x" + raw[1:]

    def changed_open(path, *args, **kwargs):
        original = old_open(path, *args, **kwargs)
        return (
            Handle(original)
            if path.name == target and mode in ("drift", "oversize-read")
            else original
        )

    def changed_link(path):
        return path.name == target if mode == "symlink" else old_link(path)

    def changed_stat(path, *args, **kwargs):
        nonlocal calls
        result = old_stat(path, *args, **kwargs)
        if path.name != target:
            return result
        calls += 1
        attrs = {name: getattr(result, name) for name in dir(result) if name.startswith("st_")}
        if mode == "nonregular":
            attrs["st_mode"] = 0o040755
        if mode == "mtime-change" and calls > 1:
            attrs["st_mtime_ns"] += 1
        return SimpleNamespace(**attrs)

    monkeypatch.setattr(Path, "open", changed_open)
    monkeypatch.setattr(Path, "is_symlink", changed_link)
    if mode in ("nonregular", "mtime-change"):
        monkeypatch.setattr(Path, "stat", changed_stat)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize(
    "field,bad", [("TICK", 50001), ("FLOW_NS", 5000000001), ("SECOND_NS", 1000000001)]
)
def test_held_clock_constants_fail_before_numeric_payload(monkeypatch, field, bad):
    value = execution_case()[0]
    old_get = witness.ConstructedMboRecord.__getattribute__

    def no_numeric(self, name):
        if name in ("price", "size", "order_id"):
            raise AssertionError("numeric reached before held constant check")
        return old_get(self, name)

    monkeypatch.setattr(witness.ConstructedMboRecord, "__getattribute__", no_numeric)
    monkeypatch.setattr(microdepth.clock, field, bad)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


def test_held_f_last_constant_mismatch_refuses(monkeypatch):
    value = execution_case()[0]
    monkeypatch.setattr(dbn, "F_LAST", 64)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


def test_fixed_source_read_bound_is_defensive_not_mutable_protocol_identity(monkeypatch):
    value = execution_case()[0]
    monkeypatch.setattr(witness, "MAX_HELPER_SOURCE_BYTES", 1)
    assert witness.protocol_sha256() == PROTOCOL_PIN
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("module", [microdepth, execution])
def test_literal_feature_schema_guard_precedes_payload(monkeypatch, module):
    value = execution_case()[0]
    monkeypatch.setattr(module, "FEATURES", tuple(reversed(module.FEATURES)))
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(value, expected_protocol_sha256=PROTOCOL_PIN)


@pytest.mark.parametrize("problem", [ValueError, TypeError, AttributeError, OverflowError, OSError])
def test_helper_public_error_normalization_preserves_cause(monkeypatch, problem):
    value = execution_case()[0]

    def failure(*args):
        raise problem("invented helper refusal")

    monkeypatch.setattr(strict.StrictBook, "apply", failure)
    with pytest.raises(witness.FeaturePublicationWitnessError) as error:
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )
    assert type(error.value.__cause__) is problem


@pytest.mark.parametrize("problem", [AssertionError, KeyboardInterrupt, SystemExit])
def test_process_interrupts_and_oracle_assertions_are_never_swallowed(monkeypatch, problem):
    value = execution_case()[0]

    def failure(*args):
        raise problem("invented interrupt")

    monkeypatch.setattr(strict.StrictBook, "apply", failure)
    with pytest.raises(problem):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_every_feature_must_be_exact_finite_float_before_any_witness_returns(monkeypatch, bad):
    value = execution_case()[0]
    real_features = execution.ExecutionWindow.features

    def poisoned(self, q):
        values = real_features(self, q)
        values["ask_passive_5s"] = bad
        return values

    monkeypatch.setattr(execution.ExecutionWindow, "features", poisoned)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


def test_verified_identity_preserves_signed_zero_feature_bytes(monkeypatch):
    value = execution_case("cancel-only")[0]
    real_features = execution.ExecutionWindow.features

    def negative_zero(self, q):
        values = real_features(self, q)
        values["ask_passive_5s"] = -0.0
        return values

    monkeypatch.setattr(execution.ExecutionWindow, "features", negative_zero)
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    number = dict(result.publications[0].feature_values)["ask_passive_5s"]
    assert math.copysign(1.0, number) == -1.0
    body = asdict(result)
    own = body.pop("witness_sha256")
    assert own == digest(body)
    assert b'"ask_passive_5s",-0.0' in canonical(body)
    assert (
        witness.verify(
            result,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=own,
        )
        is None
    )


@pytest.mark.parametrize("supplied", [0, 0.0, -0.0, 1.25])
def test_only_empty_travel_int_zero_is_represented_as_float_and_float_sign_is_preserved(
    monkeypatch, supplied
):
    # Controlled helper return checks representation only; the independent
    # numerical oracle above still uses unmodified held helpers.
    value = execution_case()[0]
    original = microdepth.QuoteHistory.features

    def representation(self, book, cvd):
        values = original(self, book, cvd)
        values["mid_travel_5s_ticks"] = supplied
        return values

    monkeypatch.setattr(microdepth.QuoteHistory, "features", representation)
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    number = dict(result.publications[0].feature_values)["mid_travel_5s_ticks"]
    assert type(number) is float
    assert number == float(supplied)
    assert math.copysign(1.0, number) == math.copysign(1.0, float(supplied))
    assert all(flag is False for _, flag in result.authority_flags)
    body = asdict(result)
    own = body.pop("witness_sha256")
    assert own == digest(body)
    assert (
        witness.verify(
            result,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=own,
        )
        is None
    )


@pytest.mark.parametrize("bad", [1, True, "0"])
def test_nonzero_int_bool_or_string_travel_never_uses_empty_sum_exception(monkeypatch, bad):
    value = execution_case()[0]
    original = microdepth.QuoteHistory.features

    def representation(self, book, cvd):
        values = original(self, book, cvd)
        values["mid_travel_5s_ticks"] = bad
        return values

    monkeypatch.setattr(microdepth.QuoteHistory, "features", representation)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


@pytest.mark.parametrize("region", ["base", "history", "execution"])
@pytest.mark.parametrize("bad", [0, 1, True, "0"])
def test_no_other_feature_coercion_for_int_bool_or_string_in_any_region(monkeypatch, region, bad):
    value = execution_case()[0]
    if region == "base":
        # All logarithms carry this invalid representation; the first base
        # value must refuse, not silently float-coerce it.
        monkeypatch.setattr(math, "log1p", lambda _value: bad)
    elif region == "history":
        original = microdepth.QuoteHistory.features

        def changed_history(self, book, cvd):
            values = original(self, book, cvd)
            values["log_bid_depth5"] = bad
            return values

        monkeypatch.setattr(microdepth.QuoteHistory, "features", changed_history)
    else:
        original = execution.ExecutionWindow.features

        def changed_execution(self, q):
            values = original(self, q)
            values["ask_passive_5s"] = bad
            return values

        monkeypatch.setattr(execution.ExecutionWindow, "features", changed_execution)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )


def target_object(result, group):
    return {
        "FeaturePublicationWitness": result,
        "FeatureWitnessFixture": result.fixture,
        "ConstructedMboRecord": result.fixture.records[-1],
        "RecordAudit": result.record_audits[-1],
        "CompletedEventWitness": result.completed_events[-1],
        "FeaturePublication": result.publications[-1],
        "Quote": result.publications[-1].quote,
    }[group]


ALL_OUTPUT_FIELDS = [
    (group, field)
    for group, names in {
        **SCHEMAS,
        "Quote": ("ts_recv_ns", "bid", "ask", "bid_qty", "ask_qty"),
    }.items()
    for field in names
]


def altered(value):
    if type(value) is bool:
        return not value
    if type(value) is int:
        return value + 1
    if type(value) is str:
        return "x" + value[1:]
    if type(value) is tuple:
        return value[:-1] if value else (1,)
    if value is None:
        return ("A", ASK, 10)
    return None


@pytest.mark.parametrize("group,field", ALL_OUTPUT_FIELDS)
def test_every_nested_submitted_field_is_rebuilt_not_adopted_even_with_new_digest(group, field):
    case = execution_case()
    value = case[0]
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    # Do not mutate original input through the result's retained fixture/record.
    submitted = deepcopy(result)
    item = target_object(submitted, group)
    old = getattr(item, field)
    object.__setattr__(item, field, altered(old))
    body = asdict(submitted)
    body.pop("witness_sha256")
    candidate_pin = digest(body)
    object.__setattr__(submitted, "witness_sha256", candidate_pin)
    # Altering witness_sha256 itself cannot be repaired into a tamper test by
    # recomputing it; independently conflict its external expectation instead.
    if group == "FeaturePublicationWitness" and field == "witness_sha256":
        candidate_pin = "0" * 64
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=candidate_pin,
        )


@pytest.mark.parametrize("group,field", ALL_OUTPUT_FIELDS)
def test_every_missing_nested_submitted_field_fails_closed(group, field):
    value = execution_case()[0]
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    retained_pin = result.witness_sha256
    submitted = deepcopy(result)
    object.__delattr__(target_object(submitted, group), field)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=retained_pin,
        )


@pytest.mark.parametrize("name", FLAG_NAMES)
def test_every_authority_flag_remains_false_even_when_matching_tampered_digest(name):
    value = execution_case()[0]
    submitted = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    object.__setattr__(
        submitted, "authority_flags", tuple((key, key == name) for key in FLAG_NAMES)
    )
    body = asdict(submitted)
    body.pop("witness_sha256")
    pin = digest(body)
    object.__setattr__(submitted, "witness_sha256", pin)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=pin,
        )


@pytest.mark.parametrize("name", NAMES)
def test_all_37_values_are_part_of_complete_verified_body_not_only_feature_count(name):
    value = execution_case()[0]
    submitted = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    pub = submitted.publications[0]
    object.__setattr__(
        pub,
        "feature_values",
        tuple(
            (key, number + 0.125 if key == name else number) for key, number in pub.feature_values
        ),
    )
    body = asdict(submitted)
    body.pop("witness_sha256")
    pin = digest(body)
    object.__setattr__(submitted, "witness_sha256", pin)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=pin,
        )


@pytest.mark.parametrize(
    "group,field",
    [
        ("FeaturePublicationWitness", "record_audits"),
        ("FeaturePublicationWitness", "completed_events"),
        ("FeaturePublicationWitness", "publications"),
        ("FeaturePublicationWitness", "execution_audit"),
        ("FeaturePublicationWitness", "authority_flags"),
        ("FeatureWitnessFixture", "records"),
        ("FeaturePublication", "feature_values"),
    ],
)
def test_json_equivalent_list_is_not_exact_tuple_acceptance(group, field):
    value = execution_case()[0]
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    submitted = deepcopy(result)
    item = target_object(submitted, group)
    object.__setattr__(item, field, list(getattr(item, field)))
    assert canonical(asdict(submitted)) == canonical(asdict(result))
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=result.witness_sha256,
        )


@pytest.mark.parametrize(
    "group,field",
    [
        ("FeatureWitnessFixture", "instrument_id"),
        ("ConstructedMboRecord", "instrument_id"),
        ("CompletedEventWitness", "event_ordinal"),
        ("FeaturePublication", "publication_ordinal"),
        ("FeaturePublication", "eligible"),
    ],
)
def test_bool_and_int_are_not_interchangeable_in_submitted_nested_fields(group, field):
    value = execution_case()[0]
    submitted = deepcopy(
        witness.replay(
            value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
        )
    )
    object.__setattr__(target_object(submitted, group), field, 1 if field == "eligible" else True)
    body = asdict(submitted)
    body.pop("witness_sha256")
    pin = digest(body)
    object.__setattr__(submitted, "witness_sha256", pin)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            submitted,
            value,
            expected_fixture_sha256=input_pin(value),
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256=pin,
        )


def test_subclasses_are_not_input_or_output_transport_types():
    value = execution_case()[0]

    class ChildFixture(witness.FeatureWitnessFixture):
        pass

    child = object.__new__(ChildFixture)
    for name in SCHEMAS["FeatureWitnessFixture"]:
        object.__setattr__(child, name, getattr(value, name))
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(child, expected_protocol_sha256=PROTOCOL_PIN)

    class ChildRecord(witness.ConstructedMboRecord):
        pass

    source = value.records[-1]
    child_record = object.__new__(ChildRecord)
    for name in SCHEMAS["ConstructedMboRecord"]:
        object.__setattr__(child_record, name, getattr(source, name))
    poisoned = deepcopy(value)
    object.__setattr__(poisoned, "records", (*value.records[:-1], child_record))
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.fixture_sha256(poisoned, expected_protocol_sha256=PROTOCOL_PIN)


def test_verify_rebuilds_original_input_before_reading_submitted_witness(monkeypatch):
    value = execution_case()[0]
    result = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    retained_pin = input_pin(value)
    object.__setattr__(value.records[-1], "flags", 0)
    old_get = witness.FeaturePublicationWitness.__getattribute__

    def no_output(self, name):
        if self is result and name in SCHEMAS["FeaturePublicationWitness"]:
            raise AssertionError("submitted witness inspected before complete original preflight")
        return old_get(self, name)

    monkeypatch.setattr(witness.FeaturePublicationWitness, "__getattribute__", no_output)
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.verify(
            result,
            value,
            expected_fixture_sha256=retained_pin,
            expected_protocol_sha256=PROTOCOL_PIN,
            expected_witness_sha256="0" * 64,
        )


def test_wrong_whole_fixture_pin_refuses_before_book_state(monkeypatch):
    value = execution_case()[0]
    monkeypatch.setattr(
        strict.StrictBook,
        "__init__",
        lambda *a: pytest.fail("book created despite fixture conflict"),
    )
    with pytest.raises(witness.FeaturePublicationWitnessError):
        witness.replay(
            value, expected_fixture_sha256="0" * 64, expected_protocol_sha256=PROTOCOL_PIN
        )


def test_constructed_replay_has_no_files_writes_network_process_or_legacy_builder_hook(monkeypatch):
    case = execution_case()
    allowed = {Path(path).name for path, _ in SOURCE_PINS}
    real_open = Path.open

    def guarded_open(path, mode="r", *args, **kwargs):
        assert mode == "rb" and path.name in allowed
        return real_open(path, mode, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("unreleased I/O or legacy target/builder hook")

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(receive.ReceiveTimeBuilder, "__init__", forbidden)
    monkeypatch.setattr(execution.ExecutionBuilder, "__init__", forbidden)
    monkeypatch.setattr(microdepth.MicrodepthBuilder, "__init__", forbidden)
    check(case)


@pytest.mark.parametrize("kind", ["buy-other", "sell-other", "buy-same", "cancel-only"])
def test_additional_original_producer_parity_only_invented_valid_metadata_and_records(kind):
    # This is secondary parity, not the hand oracle. No finish/targets/labels,
    # archive reader, stored rows, historical file or outcome field is accessed.
    value = execution_case(kind)[0]
    output = witness.replay(
        value, expected_fixture_sha256=input_pin(value), expected_protocol_sha256=PROTOCOL_PIN
    )
    day = date(2025, 4, 7)
    metadata = dbn.Metadata(
        dataset="GLBX.MDP3",
        schema=dbn.Schema.MBO,
        stype_in=dbn.SType.PARENT,
        stype_out=dbn.SType.INSTRUMENT_ID,
        start=C["DAY_START_NS"],
        end=C["DAY_START_NS"] + 86400 * S,
        symbols=["6E.FUT"],
        mappings=[
            SimpleNamespace(
                raw_symbol="6EM5",
                intervals=[SimpleNamespace(start_date=day, end_date=date(2025, 4, 8), symbol="1")],
            )
        ],
    )
    builder = receive.ReceiveTimeBuilder(receive.cohort.BLOCKS[0])
    builder.start_day(day)
    builder.consume(metadata)
    for source in value.records:
        item = dbn.MBOMsg(
            publisher_id=1,
            instrument_id=1,
            ts_event=source.ts_event,
            ts_recv=source.ts_recv,
            ts_in_delta=source.ts_in_delta,
            sequence=source.sequence,
            order_id=source.order_id,
            price=source.price,
            size=source.size,
            action=dbn.Action.from_str(source.action),
            side=dbn.Side.from_str(source.side),
            flags=source.flags,
        )
        builder.consume(item)
    assert len(builder.rows) == len(output.publications) == 1
    original = builder.rows[0]
    pub = output.publications[0]
    values = {**original["features"], **builder.execution_rows[("2025-04-07", pub.received_at_ns)]}
    assert tuple((name, float(values[name])) for name in NAMES) == pub.feature_values
    assert original["eligible"] is pub.eligible
    assert original["eligibility_reason"] == pub.eligibility_reason
