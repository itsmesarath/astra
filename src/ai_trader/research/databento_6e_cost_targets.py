"""Session-separated, causal features and two-sided executable-quote cost targets."""

from __future__ import annotations

import hashlib
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

from ai_trader.research import databento_6e_event_scalp as events
from ai_trader.research.databento_6e_training_data import _member_records, selected_sources

clock = events.clock
CONFIG_SHA256 = "331b7faa85ed5d976453c12371cb0850e8c361e85b13d5eba6b69be14a2c1ede"
TRAIN = events.SESSIONS
VALIDATION = ("2025-07-14", "2025-07-15")
TEST = ("2025-07-16", "2025-07-17", "2025-07-18")
SESSIONS = (*TRAIN, *VALIDATION, *TEST)
SOURCE_DAYS = ("2025-07-06", *TRAIN, "2025-07-13", *VALIDATION, *TEST)
EXTRA_COST = 1
FEATURES = (
    "log_bid_qty",
    "log_ask_qty",
    "queue_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "log_known_trades_5s",
    "unknown_trade_fraction_5s",
    "log_prior_quote_gap_ms",
)


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CONFIG_SHA256:
        raise ValueError("Frozen cost-baseline configuration changed")
    return json.loads(raw), digest


def observed_targets(outcome: dict) -> tuple[list[float] | None, int | None]:
    """Unknown/no-entry is not a no-trade label; price both directions identically."""
    if outcome["status"] != "resolved":
        return None, None
    long = (outcome["exit_bid_nano"] - outcome["entry_ask_nano"]) / clock.TICK - EXTRA_COST
    short = (outcome["entry_bid_nano"] - outcome["exit_ask_nano"]) / clock.TICK - EXTRA_COST
    if not math.isfinite(long + short) or long + short >= 0:
        raise ValueError("Invalid crossed-quote targets")
    return [long, short], 1 if long > 0 else -1 if short > 0 else 0


class CostTargetBuilder(events.EventScalp):
    """Price all causally eligible decisions, not only winners or rule-selected entries."""

    def __init__(self, sessions: tuple[str, ...] = SESSIONS, minimum_resolved: int = 100):
        super().__init__("ofi_queue", sessions)
        self.minimum_resolved = minimum_resolved

    def start_day(self, day) -> None:
        super().start_day(day)
        self.prior_quote_gap_ns = 0

    def _observe_completed_quote(self, quote: clock.Quote) -> None:
        self.prior_quote_gap_ns = (
            quote.ts_recv_ns - self.last_quote.ts_recv_ns if self.last_quote else 0
        )
        super()._observe_completed_quote(quote)

    def _event_decision(self, quote: clock.Quote) -> None:
        now = quote.ts_recv_ns
        self.ofi.expire(now)
        self.flow.expire(now)
        depth = quote.bid_qty + quote.ask_qty
        trade_count = self.flow.known + self.flow.unknown
        features = dict(
            zip(
                FEATURES,
                (
                    math.log1p(quote.bid_qty),
                    math.log1p(quote.ask_qty),
                    (quote.bid_qty - quote.ask_qty) / depth,
                    2 * self.ofi.total / depth,
                    2 * self.flow.cvd / depth,
                    math.log1p(self.flow.known),
                    self.flow.unknown / trade_count if trade_count else 0.0,
                    math.log1p(self.prior_quote_gap_ns / 1_000_000),
                ),
                strict=True,
            )
        )
        reason = (
            "spread_not_one_tick"
            if quote.spread_ticks != 1
            else "insufficient_feature_warmup"
            if self.ofi.first_ts is None or self.ofi.first_ts > now - clock.FLOW_NS
            else "insufficient_window_for_hold"
            if now + 17 * clock.SECOND_NS >= self.window_end_ns
            else None
        )
        row = {
            "source_session": self.day.isoformat(),
            "decision_ts_ns": now,
            "features": features,
            "eligible": reason is None,
            "eligibility_reason": reason,
            # Private compatibility fields for the shared quote resolver, not model inputs.
            "signal_direction": 1,
            "latency_variants": {},
        }
        self.rows.append(row)
        if reason is not None:
            return
        row["latency_variants"]["100"] = {
            "status": "entry_pending",
            "entry_target_ts_ns": now + 100_000_000,
            "entry_ts_ns": None,
            "entry_bid_nano": None,
            "entry_ask_nano": None,
            "exit_target_ts_ns": None,
            "exit_ts_ns": None,
            "exit_bid_nano": None,
            "exit_ask_nano": None,
            "gross_crossed_quote_ticks": None,
            "net_after_extra_cost_ticks": None,
            "inactivity_exposed": False,
        }
        # These overlapping candidates label opportunities, not a simultaneous portfolio.
        self.pending_rows.append(row)

    def _process_quote(self, quote: clock.Quote) -> None:
        pending_entries = [
            r["latency_variants"]["100"]
            for r in self.pending_rows
            if r["latency_variants"]["100"]["status"] == "entry_pending"
        ]
        super()._process_quote(quote)
        for outcome in pending_entries:
            if outcome["status"] == "no_entry_spread_widened":
                outcome["entry_rejection_ts_ns"] = quote.ts_recv_ns

    def finish(self) -> tuple[list[dict], dict]:
        _, quality = super().finish()
        rows = []
        for row in self.rows:
            outcome = row["latency_variants"].get("100", {"status": "not_eligible"})
            targets, label = observed_targets(outcome)
            rows.append(
                {
                    "source_session": row["source_session"],
                    "decision_ts_ns": row["decision_ts_ns"],
                    "features": row["features"],
                    "eligible": row["eligible"],
                    "eligibility_reason": row["eligibility_reason"],
                    "outcome": outcome,
                    "net_targets_long_short_ticks": targets,
                    "hindsight_action": label,
                }
            )
        counts = Counter(r["source_session"] for r in rows if r["outcome"]["status"] == "resolved")
        if any(counts[s] < self.minimum_resolved for s in self.sessions):
            raise ValueError("Insufficient resolved cost targets in at least one source session")
        quality["resolved_targets_by_session"] = dict(counts)
        return rows, quality


def build_targets(
    config: dict,
    project_root: Path,
    *,
    builder: CostTargetBuilder | None = None,
    source_days: tuple[str, ...] = SOURCE_DAYS,
) -> tuple[list[dict], dict]:
    _, sources, intake_sha = selected_sources(config, project_root)
    if tuple(s["day"].isoformat() for s in sources) != source_days:
        raise ValueError("Unexpected cost-target source cohort")
    builder = CostTargetBuilder() if builder is None else builder
    if tuple(config.get("source_sessions", ())) != builder.sessions:
        raise ValueError("Builder sessions differ from the registered source sessions")
    archives, stamps, mappings = {}, {}, []
    try:
        for source in sources:
            path = source["archive"]
            if path not in archives:
                stamps[path] = (path.stat().st_size, path.stat().st_mtime_ns)
                archives[path] = zipfile.ZipFile(path)
            print(f"Checking cost-target source {source['day']}", flush=True)
            builder.start_day(source["day"])
            for record in _member_records(archives[path], source):
                builder.consume(record)
            builder.finish_day()
            mappings.append(
                {
                    "utc_date": source["day"].isoformat(),
                    "contract": "6EU5",
                    "instrument_id": builder.instrument_id,
                }
            )
        rows, quality = builder.finish()
        for path, stamp in stamps.items():
            if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
                raise ValueError("Source archive changed during cost-target replay")
    finally:
        for archive in archives.values():
            archive.close()
    return rows, {
        "source_intake_sha256": intake_sha,
        "quality": quality,
        "dated_contract_mappings": mappings,
        "source_days": [
            {
                "utc_date": s["day"].isoformat(),
                "archive": s["archive"].name,
                "archive_sha256_from_intake": s["archive_sha256"],
                "member": s["name"],
                "member_sha256": s["sha256"],
            }
            for s in sources
        ],
    }
