"""Past-only completed-event crossing evidence for the one-second research grid."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime

from ai_trader.research import six_e_auction_features as tape

ATTACK_SECONDS = 5
DELIVERY_SECONDS = 5
MAX_MARKERS = 64
MARKER_FIELDS = (
    "id",
    "segment",
    "direction",
    "start_ts_ns",
    "start_ordinal",
    "ts_ns",
    "ordinal",
    "prior_low_nano2",
    "prior_high_nano2",
    "level_nano2",
    "start_mid_nano2",
    "bid_nano",
    "ask_nano",
    "activity",
    "normalized_cvd",
    "known_trades",
    "unknown_trades",
    "delta_qty",
    "top_depth_qty",
    "unknown_fraction_qty_5s",
    "unknown_fraction_qty_15s",
    "unknown_fraction_qty_30s",
)
PACKET_FIELDS = (
    "segment",
    "previous_publication_ts_ns",
    "previous_publication_ordinal",
    "ordinal",
    "markers",
)


def protocol() -> dict:
    return {
        "version": "six_e_completed_crossing_evidence_v1",
        "reference": "At first strictly outside completed midpoint, freeze the PRE-event "
        "ready 60s range boundary and width; previous completed midpoint must be inside",
        "attack": "A completed midpoint reaches >=1 tick outside that frozen boundary; "
        "two half-tick quote updates are allowed; no threshold lowering",
        "attack_seconds": ATTACK_SECONDS,
        "invalidation": "Return to or inside frozen level, elapsed attack >5s, or OFI reset",
        "frames": "Only completed native F_LAST events, with original equal-time order; "
        "T-only tape; 5s normalized CVD = 2*known signed quantity/current top depth",
        "range_width_ticks": [2, 12],
        "publication": "Publish all completed markers since previous decision exactly once, "
        "in native order; never backdate a decision or execution to the attack",
        "delivery_seconds": DELIVERY_SECONDS,
        "bound_markers_per_publication": MAX_MARKERS,
        "reset": "Clear unpublished markers and partial attacks on inherited OFI reset; "
        "retain global IDs/ordinals, increment segment; count discarded evidence",
        "marker_fields": list(MARKER_FIELDS),
        "packet_fields": list(PACKET_FIELDS),
        "labels_accessed": False,
        "confirmed_icebergs": False,
        "trading_enabled": False,
    }


@dataclass(frozen=True)
class Attack:
    direction: int
    ts: int
    ordinal: int
    low: int
    high: int
    level: int
    mid: int


class CrossingBuffer:
    def __init__(self, session: str, contract: str):
        tape.data.role_for_day(session)
        if contract != tape.data.census.dated_contract(session):
            raise ValueError("Crossing contract differs from dated session")
        self.session, self.contract = session, contract
        self.segment = self.ordinal = self.marker_id = 0
        self.previous_mid = self.last_ts = None
        self.previous_publication_ts = self.previous_publication_ordinal = 0
        self.pending: dict[int, Attack] = {}
        self.markers: list[dict] = []
        self.audit = Counter()

    def reset(self) -> None:
        self.audit["unpublished_discarded_on_reset"] += len(self.markers)
        self.audit["partial_attacks_discarded_on_reset"] += len(self.pending)
        self.pending.clear()
        self.markers.clear()
        self.previous_mid = None
        self.segment += 1

    def observe(self, auction: tape.AuctionFeatures, quote) -> None:
        now = quote.ts_recv_ns
        if (
            self.segment == 0
            or auction.session != self.session
            or auction.contract != self.contract
            or auction.last_ts != now
            or auction.snapshot is None
            or (auction.snapshot["bid_nano"], auction.snapshot["ask_nano"])
            != (quote.bid, quote.ask)
            or type(quote.bid_qty) is not int
            or type(quote.ask_qty) is not int
            or min(quote.bid_qty, quote.ask_qty) <= 0
            or (self.last_ts is not None and now < self.last_ts)
        ):
            raise ValueError("Crossings require current completed native auction state")
        self.ordinal += 1
        self.last_ts = now
        g = auction.snapshot  # Pre-event range, already calculated by unchanged producer.
        mid = quote.bid + quote.ask
        ready = bool(g["range_ready"]) and 2 <= g["prior_range_ticks"] <= 12
        self.audit["completed_events"] += 1
        self.audit["ready_range_events"] += ready
        for direction in (1, -1):
            attack = self.pending.get(direction)
            if attack is not None:
                if (
                    direction * (mid - attack.level) <= 0
                    or now - attack.ts > ATTACK_SECONDS * tape.SECOND
                ):
                    del self.pending[direction]
                    self.audit["partial_attack_invalidated_or_expired"] += 1
                    continue
            else:
                level = g["prior_high_nano2"] if direction > 0 else g["prior_low_nano2"]
                if not (
                    ready
                    and self.previous_mid is not None
                    and direction * (self.previous_mid - level) <= 0
                    and direction * (mid - level) > 0
                ):
                    continue
                attack = Attack(
                    direction,
                    now,
                    self.ordinal,
                    g["prior_low_nano2"],
                    g["prior_high_nano2"],
                    level,
                    mid,
                )
                self.pending[direction] = attack
                self.audit["partial_attacks_started"] += 1
            if direction * (mid - attack.level) >= 2 * tape.TICK:
                if len(self.markers) >= MAX_MARKERS:
                    raise ValueError("Crossing publication marker bound exceeded; no truncation")
                frame = auction.tapes[5]
                known = frame.counts["B"] + frame.counts["A"]
                unknown = frame.counts["N"]
                delta = frame.qty["B"] - frame.qty["A"]
                self.marker_id += 1
                marker = {
                    "id": self.marker_id,
                    "segment": self.segment,
                    "direction": direction,
                    "start_ts_ns": attack.ts,
                    "start_ordinal": attack.ordinal,
                    "ts_ns": now,
                    "ordinal": self.ordinal,
                    "prior_low_nano2": attack.low,
                    "prior_high_nano2": attack.high,
                    "level_nano2": attack.level,
                    "start_mid_nano2": attack.mid,
                    "bid_nano": quote.bid,
                    "ask_nano": quote.ask,
                    "activity": math.log1p(known),
                    "normalized_cvd": 2 * delta / (quote.bid_qty + quote.ask_qty),
                    "known_trades": known,
                    "unknown_trades": unknown,
                    "delta_qty": delta,
                    "top_depth_qty": quote.bid_qty + quote.ask_qty,
                    **{
                        f"unknown_fraction_qty_{w}s": auction.tapes[w].values()[-1]
                        for w in tape.WINDOWS
                    },
                }
                self.markers.append(marker)
                del self.pending[direction]
                self.audit["completed_markers"] += 1
                self.audit["up_markers" if direction > 0 else "down_markers"] += 1
        self.previous_mid = mid

    def publish(self, now: int) -> dict:
        if now != self.last_ts or now <= self.previous_publication_ts:
            raise ValueError("Crossing publication requires unique current decision time")
        packet = {
            "segment": self.segment,
            "previous_publication_ts_ns": self.previous_publication_ts,
            "previous_publication_ordinal": self.previous_publication_ordinal,
            "ordinal": self.ordinal,
            "markers": self.markers,
        }
        self.audit["published_markers"] += len(self.markers)
        self.markers = []
        self.previous_publication_ts = now
        self.previous_publication_ordinal = self.ordinal
        return packet

    def report(self) -> dict:
        result = {
            **self.audit,
            "unpublished_tail_markers": len(self.markers),
            "unfinished_tail_attacks": len(self.pending),
            "segments": self.segment,
        }
        if self.audit["completed_markers"] != (
            self.audit["published_markers"]
            + self.audit["unpublished_discarded_on_reset"]
            + len(self.markers)
        ):
            raise ValueError("Crossing publication conservation differs")
        return result


def validate_packet(packet: dict, now: int, session: str) -> None:
    tape.data.role_for_day(session)  # Reserved guard before looking at marker contents.
    if (
        set(packet) != set(PACKET_FIELDS)
        or any(type(packet[k]) is not int or packet[k] < 0 for k in PACKET_FIELDS if k != "markers")
        or packet["segment"] < 1
        or packet["ordinal"] <= packet["previous_publication_ordinal"]
        or (packet["previous_publication_ts_ns"] >= now)
        or type(packet["markers"]) is not list
        or len(packet["markers"]) > MAX_MARKERS
    ):
        raise ValueError("Invalid crossing publication identity, order or bound")
    last_id, last_ordinal = 0, packet["previous_publication_ordinal"]
    for m in packet["markers"]:
        if set(m) != set(MARKER_FIELDS) or any(
            type(v) not in (int, float) or not math.isfinite(v) for v in m.values()
        ):
            raise ValueError("Crossing marker feature allowlist or values differ")
        float_keys = {
            "activity",
            "normalized_cvd",
            *(f"unknown_fraction_qty_{w}s" for w in tape.WINDOWS),
        }
        if any(type(v) is not int for k, v in m.items() if k not in float_keys):
            raise ValueError("Crossing native prices, counts and timestamps require integers")
        stamp = datetime.fromtimestamp(m["ts_ns"] // tape.SECOND, UTC)
        start_stamp = datetime.fromtimestamp(m["start_ts_ns"] // tape.SECOND, UTC)
        direction = m["direction"]
        low, high, level = m["prior_low_nano2"], m["prior_high_nano2"], m["level_nano2"]
        if (
            stamp.date().isoformat() != session
            or not 12 <= stamp.hour < 16
            or start_stamp.date().isoformat() != session
            or not 12 <= start_stamp.hour < 16
            or not packet["previous_publication_ts_ns"] <= m["ts_ns"] <= now
            or not 0 <= m["ts_ns"] - m["start_ts_ns"] <= ATTACK_SECONDS * tape.SECOND
            or m["segment"] != packet["segment"]
            or direction not in (-1, 1)
            or m["id"] <= last_id
            or not last_ordinal < m["ordinal"] <= packet["ordinal"]
            or not 0 < m["start_ordinal"] <= m["ordinal"]
            or min(low, high, m["bid_nano"], m["start_mid_nano2"]) <= 0
            or any(
                m[k] % tape.TICK
                for k in (
                    "bid_nano",
                    "ask_nano",
                    "prior_low_nano2",
                    "prior_high_nano2",
                    "start_mid_nano2",
                )
            )
            or m["ask_nano"] <= m["bid_nano"]
            or not 2 <= (high - low) / (2 * tape.TICK) <= 12
            or level != (high if direction > 0 else low)
            or direction * (m["start_mid_nano2"] - level) <= 0
            or direction * (m["bid_nano"] + m["ask_nano"] - level) < 2 * tape.TICK
            or min(m["known_trades"], m["unknown_trades"]) < 0
            or m["top_depth_qty"] <= 0
            or m["normalized_cvd"] != 2 * m["delta_qty"] / m["top_depth_qty"]
            or (m["known_trades"] == 0 and m["delta_qty"] != 0)
            or m["activity"] != math.log1p(m["known_trades"])
            or any(not 0 <= m[f"unknown_fraction_qty_{w}s"] <= 1 for w in tape.WINDOWS)
            or (m["delta_qty"] == 0) != (m["normalized_cvd"] == 0)
            or m["delta_qty"] * m["normalized_cvd"] < 0
        ):
            raise ValueError("Invalid crossing marker time, price, order or tape accounting")
        last_id, last_ordinal = m["id"], m["ordinal"]
