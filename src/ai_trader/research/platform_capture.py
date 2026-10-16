"""Offline audit of bounded NinjaTrader/cTrader observations; no feeds or trading.

These are serialized callback observation clocks, NOT exchange receipt timestamps.
Stable wall/monotonic deltas do not verify UTC synchronization across providers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

NS = 1_000_000_000
MAX_BYTES = 64 * 1024 * 1024
MAX_LINE = 4096
MAX_EVENTS = 1_000_000
BASE = {"kind", "source_session", "sequence", "observed_utc_ns", "elapsed_ns"}
START = {
    "schema",
    "provider",
    "market",
    "instrument",
    "feed_environment",
    "feed_label",
    "tick_size",
    "max_seconds",
    "max_events",
    "clock_basis",
    "clock_sync_verified",
    "trading_enabled",
}
FIELDS = {
    "session_start": START,
    "session_end": {"reason", "clean_shutdown", "event_records"},
    "quote": {"bid", "ask"},
    "bid": {"price", "size", "provider_time_text"},
    "ask": {"price", "size", "provider_time_text"},
    "trade": {"price", "size", "provider_time_text"},
    "depth": {"side", "operation", "position", "price", "size", "provider_time_text"},
    "heartbeat": set(),
}


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON field")
        value[key] = item
    return value


def _constant(_):
    raise ValueError("Nonfinite JSON value")


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Invalid {name}")
    return value


def _text(value, maximum, name):
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= maximum
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"Invalid {name}")
    return value


def _price(value, *, zero=False):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,9})?", value):
        raise ValueError("Expected an exact decimal price string")
    nano = int(Decimal(value) * NS)
    if not (0 if zero else 1) <= nano < 1000 * NS:
        raise ValueError("Price outside bounded range")
    return nano


@dataclass(frozen=True)
class Quote:
    observed_utc_ns: int
    bid_nano: int | None
    ask_nano: int | None
    bid_observed_utc_ns: int | None
    ask_observed_utc_ns: int | None

    def usable_at(self, now: int, max_age_ns: int) -> bool:
        return (
            self.bid_nano is not None
            and self.ask_nano is not None
            and 0 < self.bid_nano < self.ask_nano
            and self.bid_observed_utc_ns is not None
            and self.ask_observed_utc_ns is not None
            and 0 <= now - self.bid_observed_utc_ns <= max_age_ns
            and 0 <= now - self.ask_observed_utc_ns <= max_age_ns
        )


@dataclass(frozen=True)
class Capture:
    header: dict
    footer: dict
    raw_sha256: str
    quotes: tuple[Quote, ...]
    summary: dict

    def asof(self, observed_utc_ns: int, max_age_ns: int = 500_000_000) -> Quote | None:
        """Own-clock observation only. Never backfill from future or older valid states."""
        _integer(observed_utc_ns, 0, 2**63 - 1, "decision clock")
        _integer(max_age_ns, 1, 5 * NS, "quote age limit")
        if not self.header["observed_utc_ns"] <= observed_utc_ns < self.footer["observed_utc_ns"]:
            return None
        index = bisect_right(self.quotes, observed_utc_ns, key=lambda q: q.observed_utc_ns) - 1
        if index < 0:
            return None
        quote = self.quotes[index]
        return quote if quote.usable_at(observed_utc_ns, max_age_ns) else None


def _header(row):
    if (
        row["schema"] != "ai_trader_market_capture_v1"
        or row["sequence"] != 0
        or row["elapsed_ns"] != 0
    ):
        raise ValueError("Invalid capture header")
    if (
        row["trading_enabled"] is not False
        or row["clock_sync_verified"] is not False
        or row["clock_basis"] != "serialized_callback_observation_utc"
    ):
        raise ValueError("Capture is not the supported unverified-clock data-only format")
    _text(row["feed_label"], 120, "feed label")
    _text(row["instrument"], 80, "instrument")
    _integer(row["max_seconds"], 1, 3600, "duration limit")
    _integer(row["max_events"], 1, MAX_EVENTS, "event limit")
    tick = _price(row["tick_size"])
    if row["provider"] == "ninjatrader":
        # Euro FX futures: standard 6E (tick 0.00005) or micro M6E (tick 0.0001).
        expected_tick = {"6E": 50000, "M6E": 100000}.get(row["market"])
        match = re.fullmatch(
            re.escape(str(row["market"])) + r" (0[1-9]|1[0-2])-[0-9]{2}", row["instrument"]
        )
        if (
            expected_tick is None
            or row["feed_environment"] != "unverified"
            or not match
            or tick != expected_tick
        ):
            raise ValueError("Expected a dated 6E or M6E NinjaTrader observation capture")
    elif row["provider"] == "ctrader":
        if row["market"] != "EURUSD" or row["feed_environment"] != "demo" or 100000 % tick:
            raise ValueError("Expected demo EURUSD broker quotes with valid tick size")
    else:
        raise ValueError("Unsupported capture provider")
    if not re.fullmatch(re.escape(row["provider"]) + r"-[a-f0-9]{32}", row["source_session"]):
        raise ValueError("Invalid source session identity")
    return tick


def load_capture(path: Path, expected_sha256: str | None = None) -> Capture:
    """Require a closed bounded file; report all missing feed/cost/clock evidence."""
    if path.is_symlink() or not path.is_file() or not 1 <= path.stat().st_size <= MAX_BYTES:
        raise ValueError("Capture must be a bounded regular file")
    if expected_sha256 is not None and not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("Invalid expected capture hash")
    stamp = (path.stat().st_size, path.stat().st_mtime_ns)
    header, footer, previous = None, None, None
    digest = hashlib.sha256()
    counts, quotes, spreads = Counter(), [], []
    bid, ask, bid_at, ask_at = None, None, None, None
    maximum_drift, maximum_gap, total_bytes = 0, 0, 0
    with path.open("rb") as stream:
        for sequence in range(MAX_EVENTS + 3):
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            total_bytes += len(line)
            if (
                footer is not None
                or len(line) > MAX_LINE
                or total_bytes > MAX_BYTES
                or not line.endswith(b"\n")
            ):
                raise ValueError("Trailing, partial or oversized capture record")
            digest.update(line)
            row = json.loads(line, object_pairs_hook=_pairs, parse_constant=_constant)
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("kind"), str)
                or row.get("kind") not in FIELDS
                or set(row) != BASE | FIELDS[row["kind"]]
            ):
                raise ValueError("Capture record schema mismatch")
            _integer(row["sequence"], sequence, sequence, "record sequence")
            now = _integer(
                row["observed_utc_ns"], 946684800 * NS, 4102444800 * NS, "observation clock"
            )
            elapsed = _integer(row["elapsed_ns"], 0, 3610 * NS, "elapsed clock")
            kind = row["kind"]
            if sequence == 0:
                if kind != "session_start":
                    raise ValueError("Missing capture header")
                tick = _header(row)
                header, previous = row, row
                continue
            if kind == "session_start" or row["source_session"] != header["source_session"]:
                raise ValueError("Mixed source session or repeated header")
            if now < previous["observed_utc_ns"] or elapsed < previous["elapsed_ns"]:
                raise ValueError("Capture clock regressed")
            drift = abs(now - header["observed_utc_ns"] - elapsed)
            maximum_drift = max(maximum_drift, drift)
            maximum_gap = max(maximum_gap, elapsed - previous["elapsed_ns"])
            if drift > 250_000_000 or elapsed > (header["max_seconds"] + 10) * NS:
                raise ValueError("Clock drift or capture duration exceeded")
            previous = row
            if kind == "session_end":
                if row["clean_shutdown"] is not True or row["reason"] not in {
                    "duration_limit",
                    "event_limit",
                    "byte_limit",
                    "manual_stop",
                }:
                    raise ValueError("Capture contains failure evidence")
                _integer(row["event_records"], sequence - 1, sequence - 1, "footer event count")
                if row["event_records"] > header["max_events"]:
                    raise ValueError("Declared event budget exceeded")
                if row["reason"] == "duration_limit" and elapsed < header["max_seconds"] * NS:
                    raise ValueError("Premature duration footer")
                if row["reason"] == "event_limit" and row["event_records"] != header["max_events"]:
                    raise ValueError("Premature event-limit footer")
                if row["reason"] == "byte_limit" and total_bytes < MAX_BYTES - 8192:
                    raise ValueError("Premature byte-limit footer")
                footer = row
                continue
            if sequence > header["max_events"] or elapsed >= header["max_seconds"] * NS:
                raise ValueError("Market record outside registered capture bounds")
            counts[kind] += 1
            if kind == "heartbeat":
                continue
            if header["provider"] == "ctrader":
                if kind != "quote":
                    raise ValueError("Unexpected nonquote cTrader event")
                bid, ask = _price(row["bid"]), _price(row["ask"])
                if bid % tick or ask % tick:
                    raise ValueError("Broker quote off tick grid")
                bid_at = ask_at = now
            else:
                if kind == "quote":
                    raise ValueError("NinjaTrader capture must preserve separate side updates")
                _text(row["provider_time_text"], 64, "diagnostic provider time")
                _integer(row["size"], 0, 2**63 - 1, "market volume")
                price = _price(row["price"], zero=kind == "depth" and row["operation"] == "remove")
                if price % tick:
                    raise ValueError("Futures price off tick grid")
                if kind == "depth":
                    if row["side"] not in ("bid", "ask") or row["operation"] not in (
                        "add",
                        "update",
                        "remove",
                    ):
                        raise ValueError("Invalid depth side or operation")
                    _integer(row["position"], 0, 9999, "depth position")
                    continue  # L2 is retained raw, NOT certified as an initialized L3 book.
                if kind == "trade":
                    if row["size"] == 0:
                        raise ValueError("Trade size must be positive")
                    continue  # No invented aggressor side, CVD or execution assignment.
                if kind == "bid":
                    bid, bid_at = price, now
                else:
                    ask, ask_at = price, now
            quote = Quote(now, bid, ask, bid_at, ask_at)
            quotes.append(quote)  # Keep crossed, missing-side and stale states to block fallback.
            if quote.usable_at(now, 500_000_000):
                spreads.append((ask - bid) / 100000)  # Both products use 0.0001 as comparison pip.
    if header is None or footer is None:
        raise ValueError("Capture is still open, truncated or missing a footer")
    if (path.stat().st_size, path.stat().st_mtime_ns) != stamp or total_bytes != stamp[0]:
        raise ValueError("Capture changed while being audited")
    pin = digest.hexdigest()
    if expected_sha256 is not None and pin != expected_sha256:
        raise ValueError("Capture SHA256 mismatch")
    blockers = ["utc_synchronization_unverified", "broker_costs_and_fills_unmeasured"]
    quote_times = [
        header["observed_utc_ns"],
        *[q.observed_utc_ns for q in quotes],
        footer["observed_utc_ns"],
    ]
    maximum_quote_gap = max(b - a for a, b in zip(quote_times, quote_times[1:], strict=False))
    if not spreads:
        blockers.append("no_fresh_two_sided_quotes")
    if maximum_gap > 5 * NS:
        blockers.append("observation_gap_over_five_seconds")
    if maximum_quote_gap > 5 * NS:
        blockers.append("quote_inactivity_over_five_seconds")
    if header["provider"] == "ninjatrader":
        blockers.append("feed_entitlement_and_realtime_status_unverified")
        if not counts["depth"]:
            blockers.append("no_level_two_events_observed")
    summary = {
        "artifact_type": "platform_capture_audit_v1",
        "source_session": header["source_session"],
        "provider": header["provider"],
        "market": header["market"],
        "instrument": header["instrument"],
        "raw_sha256": pin,
        "bytes": total_bytes,
        "events": dict(counts),
        "quote_states": len(quotes),
        "fresh_two_sided_observations": len(spreads),
        "spread_pips_min": min(spreads) if spreads else None,
        "spread_pips_max": max(spreads) if spreads else None,
        "spread_pips_event_mean": sum(spreads) / len(spreads) if spreads else None,
        "maximum_clock_delta_ns": maximum_drift,
        "maximum_record_gap_ns": maximum_gap,
        "maximum_quote_update_gap_ns": maximum_quote_gap,
        "end_reason": footer["reason"],
        "transport_format_valid": True,
        "training_ready": False,
        "trading_enabled": False,
        "blockers": blockers,
    }
    return Capture(header, footer, pin, tuple(quotes), summary)


def audit_to_file(capture_path: Path, output: Path, expected_sha256: str | None = None) -> dict:
    if output.exists() or output.resolve() == capture_path.resolve():
        raise ValueError("Refusing to overwrite capture or audit evidence")
    capture = load_capture(capture_path, expected_sha256)
    raw = (json.dumps(capture.summary, indent=2, sort_keys=True) + "\n").encode()
    # Exclusive creation; no source modification and no automatic retry or training.
    with output.open("xb") as target:
        target.write(raw)
    return capture.summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    print(json.dumps(audit_to_file(args.capture, args.output, args.expected_sha256)))


if __name__ == "__main__":
    main()
