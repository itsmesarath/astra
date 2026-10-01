"""A fixed 6EU5 OFI scalp and queue-only control on five July sessions.

This reuses the audited event/quote clock, but reports every late exit and keeps
unresolved entered positions visible. All prices are historical futures quotes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import zipfile
from collections import Counter, deque
from pathlib import Path

from ai_trader.research import databento_6e_seconds_pilot as clock
from ai_trader.research.databento_6e_training_data import (
    SECOND_NS,
    TICK,
    _member_records,
    selected_sources,
)

CONFIG_SHA256 = "93422798403e400ed59720e11e61e6a802065cff0507172a57061261913382e0"
SESSIONS = ("2025-07-07", "2025-07-08", "2025-07-09", "2025-07-10", "2025-07-11")
STRATEGIES = ("ofi_queue", "queue_only")


def ofi_increment(previous: clock.Quote, current: clock.Quote) -> int:
    """Best-level OFI between complete states; no double-counted Trade/Fill volume."""
    bid = (current.bid_qty if current.bid >= previous.bid else 0) - (
        previous.bid_qty if current.bid <= previous.bid else 0
    )
    ask = -(current.ask_qty if current.ask <= previous.ask else 0) + (
        previous.ask_qty if current.ask >= previous.ask else 0
    )
    return bid + ask


class OfiWindow:
    def __init__(self):
        self.previous: clock.Quote | None = None
        self.first_ts: int | None = None
        self.events = deque()
        self.total = 0

    def expire(self, timestamp: int) -> None:
        while self.events and self.events[0][0] < timestamp - clock.FLOW_NS:
            _, value = self.events.popleft()
            self.total -= value

    def observe(self, quote: clock.Quote) -> None:
        self.expire(quote.ts_recv_ns)
        if self.first_ts is None:
            self.first_ts = quote.ts_recv_ns
        if self.previous is not None:
            change = ofi_increment(self.previous, quote)
            self.events.append((quote.ts_recv_ns, change))
            self.total += change
        self.previous = quote


class OfiScalp(clock.SecondsPilot):
    def __init__(self, strategy: str, sessions: tuple[str, ...] = SESSIONS):
        if strategy not in STRATEGIES:
            raise ValueError("Unknown registered OFI strategy")
        super().__init__(
            sessions=sessions,
            contract="6EU5",
            minimum_fresh_grids_per_day=clock.MIN_FRESH_GRIDS_PER_DAY_V2,
            quote_warmup_ns=10 * SECOND_NS,
        )
        self.strategy = strategy
        self.ofi = OfiWindow()

    def start_day(self, day) -> None:
        super().start_day(day)
        self.ofi = OfiWindow()

    def _observe_completed_quote(self, quote: clock.Quote) -> None:
        # The base resets last_quote on a book clear; never bridge OFI over it.
        if self.last_quote is None:
            self.ofi = OfiWindow()
        self.ofi.observe(quote)

    def _signal_at_grid(self, grid_ns: int, quote: clock.Quote, imbalance: float) -> tuple:
        self.ofi.expire(grid_ns)
        depth = quote.bid_qty + quote.ask_qty
        difference = quote.bid_qty - quote.ask_qty
        normalized = 2 * self.ofi.total / depth
        offset = (quote.ask - quote.bid) * difference / (2 * depth * TICK)
        extra = {
            "strategy": self.strategy,
            "ofi_5s": self.ofi.total,
            "normalized_ofi_5s": normalized,
            "weighted_mid_offset_ticks": offset,
        }
        if quote.spread_ticks != 1:
            return 0, "spread_not_one_tick", extra
        if self.ofi.first_ts is None or self.ofi.first_ts > grid_ns - clock.FLOW_NS:
            return 0, "insufficient_ofi_warmup", extra
        # At one tick spread, offset >=0.15 is exactly |queue imbalance| >=0.3.
        if 10 * abs(difference) < 3 * depth:
            return 0, "weighted_mid_offset_too_small", extra
        if self.strategy == "ofi_queue":
            if 2 * abs(self.ofi.total) < depth:
                return 0, "ofi_below_one_side_depth", extra
            if (self.ofi.total > 0) != (difference > 0):
                return 0, "ofi_queue_disagree", extra
        return (1 if difference > 0 else -1), None, extra

    def _process_quote(self, quote: clock.Quote) -> None:
        """Late quotes close at their observed price instead of deleting the position."""
        pending = []
        for row in self.pending_rows:
            for variant in row["latency_variants"].values():
                if variant["status"] == "entry_pending":
                    target = variant["entry_target_ts_ns"]
                    if quote.ts_recv_ns < target:
                        continue
                    if quote.ts_recv_ns > target + clock.QUOTE_WAIT_NS:
                        variant["status"] = "no_entry_quote_timeout"
                    elif quote.spread_ticks != 1:
                        variant["status"] = "no_entry_spread_widened"
                    else:
                        variant.update(
                            status="exit_pending",
                            entry_ts_ns=quote.ts_recv_ns,
                            entry_bid_nano=quote.bid,
                            entry_ask_nano=quote.ask,
                            exit_target_ts_ns=quote.ts_recv_ns + clock.HOLD_NS,
                        )
                elif variant["status"] == "exit_pending":
                    target = variant["exit_target_ts_ns"]
                    if quote.ts_recv_ns < target:
                        continue
                    gross = (
                        quote.bid - variant["entry_ask_nano"]
                        if row["signal_direction"] == 1
                        else variant["entry_bid_nano"] - quote.ask
                    ) / TICK
                    variant.update(
                        status="resolved",
                        exit_ts_ns=quote.ts_recv_ns,
                        exit_bid_nano=quote.bid,
                        exit_ask_nano=quote.ask,
                        exit_lateness_ns=quote.ts_recv_ns - target,
                        late_exit=quote.ts_recv_ns > target + clock.QUOTE_WAIT_NS,
                        gross_crossed_quote_ticks=gross,
                        net_after_extra_cost_ticks={
                            str(cost): gross - cost for cost in clock.EXTRA_COST_TICKS
                        },
                    )
            primary = row["latency_variants"]["100"]
            if row is self.active_row and primary["status"] not in {
                "entry_pending",
                "exit_pending",
            }:
                self.active_row = None
                self.cooldown_until_ns = quote.ts_recv_ns + clock.COOLDOWN_NS
            if any(
                v["status"] in {"entry_pending", "exit_pending"}
                for v in row["latency_variants"].values()
            ):
                pending.append(row)
        self.pending_rows = pending

    def _end_window(self) -> None:
        super()._end_window()
        # The base retains pending entries/exits in rows when it closes the window.
        for row in self.rows:
            if row["source_session"] != self.day.isoformat():
                continue
            for variant in row["latency_variants"].values():
                if variant["status"] == "censored_window_end":
                    variant["status"] = (
                        "unresolved_exit_window_end"
                        if variant["entry_ts_ns"] is not None
                        else "no_entry_window_end"
                    )


def summarize(rows: list[dict]) -> dict:
    selected = [r for r in rows if r["selected_counterfactual"]]
    latencies = {}
    for latency in clock.LATENCY_MS:
        variants = [r["latency_variants"][str(latency)] for r in selected]
        closed = [v for v in variants if v["status"] == "resolved"]
        gross = [v["gross_crossed_quote_ticks"] for v in closed]
        unresolved = sum(
            v["entry_ts_ns"] is not None and v["status"] != "resolved" for v in variants
        )
        latencies[str(latency)] = {
            "statuses": dict(Counter(v["status"] for v in variants)),
            "entered": sum(v["entry_ts_ns"] is not None for v in variants),
            "closed": len(closed),
            "unresolved_entered": unresolved,
            "late_exits": sum(v["late_exit"] for v in closed),
            "positive_gross": sum(g > 0 for g in gross),
            "mean_gross_ticks": statistics.mean(gross) if gross else None,
            "median_gross_ticks": statistics.median(gross) if gross else None,
            "total_gross_ticks": sum(gross),
            "net_ticks_by_extra_cost": {
                str(cost): {
                    "mean_closed": statistics.mean(g - cost for g in gross) if gross else None,
                    "total_closed": sum(g - cost for g in gross),
                    "positive_closed": sum(g > cost for g in gross),
                    "all_entered_resolved": unresolved == 0,
                }
                for cost in clock.EXTRA_COST_TICKS
            },
        }
    return {
        "grid_rows": len(rows),
        "fresh_quotes": sum(
            r["decision_quote_age_ns"] is not None
            and 0 < r["decision_quote_age_ns"] <= clock.QUOTE_AGE_NS
            for r in rows
        ),
        "raw_signals": sum(r["signal_direction"] != 0 for r in rows),
        "selected": len(selected),
        "policy_reasons": dict(Counter(r["policy_reason"] for r in rows)),
        "latency_ms": latencies,
    }


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CONFIG_SHA256:
        raise ValueError("Frozen OFI experiment configuration changed")
    return json.loads(raw), digest


def experiment_decision(stats: dict) -> str:
    if any(v["unresolved_entered"] for s in stats.values() for v in s["latency_ms"].values()):
        return "inconclusive_unresolved_positions"
    primary = stats["ofi_queue"]["latency_ms"]["100"]
    mean_net = primary["net_ticks_by_extra_cost"]["1"]["mean_closed"]
    if mean_net is None or mean_net <= 0:
        return "reject_for_promotion"
    return "requires_independent_replication_and_broker_execution"


def source_fingerprints() -> dict:
    root = Path(__file__).resolve().parent
    names = (
        "databento_6e_ofi_scalp.py",
        "databento_6e_seconds_pilot.py",
        "databento_6e_scenario_replay.py",
        "databento_6e_training_data.py",
    )
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def run_experiment(
    *, project_root: Path, config_path: Path, rows_output: Path, summary_output: Path
) -> dict:
    if (
        rows_output.exists()
        or summary_output.exists()
        or (rows_output.resolve() == summary_output.resolve())
    ):
        raise ValueError("Refusing to overwrite OFI evidence")
    config, digest = load_config(config_path)
    fingerprints = source_fingerprints()
    _, sources, intake_sha = selected_sources(config, project_root)
    if tuple(s["day"].isoformat() for s in sources) != ("2025-07-06", *SESSIONS):
        raise ValueError("Unexpected source day outside the registered OFI cohort")
    builders = {name: OfiScalp(name) for name in STRATEGIES}
    archives, stamps = {}, {}
    mappings = []
    try:
        for source in sources:
            path = source["archive"]
            if path not in archives:
                stamps[path] = (path.stat().st_size, path.stat().st_mtime_ns)
                archives[path] = zipfile.ZipFile(path)
            for builder in builders.values():
                builder.start_day(source["day"])
            for record in _member_records(archives[path], source):
                for builder in builders.values():
                    builder.consume(record)
            for builder in builders.values():
                builder.finish_day()
            mappings.append(
                {
                    "utc_date": source["day"].isoformat(),
                    "contract": "6EU5",
                    "instrument_id": builder.instrument_id,
                }
            )
        quality = {name: builder.finish()[1] for name, builder in builders.items()}
        for path, stamp in stamps.items():
            if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
                raise ValueError("Source archive changed during OFI replay")
    finally:
        for archive in archives.values():
            archive.close()
    if fingerprints != source_fingerprints():
        raise ValueError("Replay implementation changed during experiment")
    rows = []
    for name, builder in builders.items():
        for row in builder.rows:
            row["strategy"] = name
            rows.append(row)
    rows_raw = b"".join(
        (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in rows
    )
    stats = {name: summarize(builder.rows) for name, builder in builders.items()}
    decision = experiment_decision(stats)
    report = {
        "artifact_type": "databento_6eu5_ofi_scalp_v1",
        "experiment_id": config["experiment_id"],
        "config_sha256": digest,
        "source_intake_report": config["source_intake_report"],
        "source_intake_sha256": intake_sha,
        "implementation_sha256": fingerprints,
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
        "dated_contract_mappings": mappings,
        "quality": quality,
        "rows_sha256": hashlib.sha256(rows_raw).hexdigest(),
        "rows": len(rows),
        "decision": decision,
        "promotion_enabled": False,
        "evaluation_sessions": list(SESSIONS),
        "fitted_parameters": 0,
        "strategies": stats,
        "by_session": [
            {
                "source_session": s,
                "strategies": {
                    name: summarize([r for r in builder.rows if r["source_session"] == s])
                    for name, builder in builders.items()
                },
            }
            for s in SESSIONS
        ],
        "limitations": [
            "Fixed thresholds are hypotheses, not estimates from the referenced equity papers.",
            "Queue-weighted mid is a queue proxy, not a fitted Stoikov microprice.",
            "Control has an independent position schedule; portfolio comparisons are unpaired.",
            "Slower latency variants reuse primary selections, not independent portfolios.",
            "Top-of-book quote counterfactuals omit fills, impact and broker execution.",
            "One extra tick is a cost sensitivity, not an observed broker commission.",
            "Five evaluation days become exposed after this run; no statistical edge proof.",
        ],
    }
    clock._publish(rows_output, summary_output, rows_raw, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rows-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()
    report = run_experiment(
        project_root=args.project_root,
        config_path=args.config,
        rows_output=args.rows_output,
        summary_output=args.summary_output,
    )
    print(
        json.dumps(
            {
                "decision": report["decision"],
                "rows": report["rows"],
                "strategies": report["strategies"],
            }
        )
    )


if __name__ == "__main__":
    main()
