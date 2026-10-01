"""Frozen event-triggered 6EU5 quote research; no gateways, training or network."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import zipfile
from pathlib import Path

import databento_dbn as dbn

from ai_trader.research import databento_6e_ofi_scalp as ofi
from ai_trader.research import databento_6e_seconds_pilot as clock
from ai_trader.research.databento_6e_training_data import _member_records, selected_sources

CONFIG_SHA256 = "f4c17bb5f2c494d10be7df748e4b022e7ac13ab3805485292f54afc3e189a08f"
SESSIONS = ofi.SESSIONS
DEVELOPMENT = SESSIONS[:2]
EVALUATION = SESSIONS[2:]
DECISION_INTERVAL_NS = clock.SECOND_NS
INACTIVITY_NS = 5 * clock.SECOND_NS


class EventScalp(ofi.OfiScalp):
    """Use the strict decoder/book clock, but never synthesize grid observations."""

    def __init__(self, strategy: str, sessions: tuple[str, ...] = SESSIONS):
        super().__init__(strategy, sessions)
        self.completed_sessions: list[str] = []
        self.day_quality: list[dict] = []
        self.inactivity_intervals: list[dict] = []

    def start_day(self, day) -> None:
        super().start_day(day)
        self.next_decision_ns = self.window_start_ns
        self.watch_since_ns = self.window_start_ns - self.quote_warmup_ns
        self.inactivity_start_ns: int | None = None
        self.incomplete_event = False
        self.day_completed_quotes = 0
        self.day_row_start = len(self.rows)
        self.day_gap_start = len(self.inactivity_intervals)

    def _advance_grids_before(self, timestamp: int) -> None:
        # The inherited decoder calls this before applying the incoming record.
        if self.day.isoformat() not in self.session_set or self.window_closed:
            return
        self._advance_timers(min(timestamp, self.window_end_ns - 1))
        if timestamp >= self.window_end_ns:
            self._end_window()

    def _advance_timers(self, timestamp: int) -> None:
        """Process expiry at its logical deadline, even if the next quote is much later."""
        for row in self.pending_rows:
            for variant in row["latency_variants"].values():
                deadline = variant["entry_target_ts_ns"] + clock.QUOTE_WAIT_NS
                if variant["status"] == "entry_pending" and timestamp > deadline:
                    variant.update(status="no_entry_quote_timeout", entry_expiry_ts_ns=deadline + 1)
            primary = row["latency_variants"]["100"]
            if row is self.active_row and primary["status"] == "no_entry_quote_timeout":
                self.active_row = None
                self.cooldown_until_ns = primary["entry_expiry_ts_ns"] + clock.COOLDOWN_NS
        self.pending_rows = [
            row
            for row in self.pending_rows
            if any(
                v["status"] in {"entry_pending", "exit_pending"}
                for v in row["latency_variants"].values()
            )
        ]
        if self.inactivity_start_ns is None and timestamp > self.watch_since_ns + INACTIVITY_NS:
            self.inactivity_start_ns = self.watch_since_ns
            self.ofi = ofi.OfiWindow()
            self.episode_direction = 0
            detected = self.watch_since_ns + INACTIVITY_NS + 1
            for row in self.pending_rows:
                for variant in row["latency_variants"].values():
                    if variant["status"] == "exit_pending":
                        variant["inactivity_exposed"] = True
                        variant.setdefault("first_inactivity_ts_ns", detected)

    def _close_inactivity(self, end: int, recovered: bool) -> None:
        if self.inactivity_start_ns is not None:
            self.inactivity_intervals.append(
                {
                    "source_session": self.day.isoformat(),
                    "last_observation_or_warmup_start_ns": self.inactivity_start_ns,
                    "timer_fired_ns": self.inactivity_start_ns + INACTIVITY_NS + 1,
                    "end_ts_ns": end,
                    "recovered_with_completed_quote": recovered,
                }
            )
            self.inactivity_start_ns = None

    def _observe_completed_quote(self, quote: clock.Quote) -> None:
        # Warmup quotes also need the inactivity clock, including before 12:00.
        self._advance_timers(quote.ts_recv_ns)
        self._close_inactivity(quote.ts_recv_ns, recovered=True)
        super()._observe_completed_quote(quote)
        self.watch_since_ns = quote.ts_recv_ns
        if quote.ts_recv_ns >= self.window_start_ns:
            self.day_completed_quotes += 1

    def _process_quote(self, quote: clock.Quote) -> None:
        super()._process_quote(quote)
        if not self.window_closed and quote.ts_recv_ns >= self.next_decision_ns:
            self._event_decision(quote)
            self.next_decision_ns = quote.ts_recv_ns + DECISION_INTERVAL_NS

    def _event_decision(self, quote: clock.Quote) -> None:
        now = quote.ts_recv_ns
        imbalance = (quote.bid_qty - quote.ask_qty) / (quote.bid_qty + quote.ask_qty)
        direction, reason, fields = self._signal_at_grid(now, quote, imbalance)
        if direction == 0:
            self.episode_direction = 0
        elif direction != self.episode_direction:
            self.episode_direction = direction
            self.episode_id += 1
        row = {
            "source_session": self.day.isoformat(),
            "strategy": self.strategy,
            "decision_ts_ns": now,
            "decision_quote_ts_ns": now,
            "decision_quote_age_ns": 0,
            "decision_bid_nano": quote.bid,
            "decision_ask_nano": quote.ask,
            "decision_spread_ticks": quote.spread_ticks,
            "top_bid_qty": quote.bid_qty,
            "top_ask_qty": quote.ask_qty,
            "queue_imbalance": imbalance,
            "signal_direction": direction,
            "episode_id": self.episode_id if direction else None,
            "policy_reason": reason,
            "selected_counterfactual": False,
            "latency_variants": {},
            **fields,
        }
        self.rows.append(row)
        if not direction:
            return
        latest_hold = now + max(clock.LATENCY_MS) * 1_000_000 + clock.QUOTE_WAIT_NS + clock.HOLD_NS
        if self.active_row is not None:
            row["policy_reason"] = "entry_or_position_pending"
        elif now < self.cooldown_until_ns:
            row["policy_reason"] = "cooldown"
        elif self.accepted_episode_id == self.episode_id:
            row["policy_reason"] = "same_episode"
        elif latest_hold >= self.window_end_ns:
            row["policy_reason"] = "insufficient_window_for_hold"
        else:
            row.update(policy_reason="selected", selected_counterfactual=True)
            self.accepted_episode_id = self.episode_id
            self.active_row = row
            self.pending_rows.append(row)
            for latency in clock.LATENCY_MS:
                row["latency_variants"][str(latency)] = {
                    "status": "entry_pending",
                    "entry_target_ts_ns": now + latency * 1_000_000,
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

    def _end_window(self) -> None:
        if self.window_closed:
            return
        self._advance_timers(self.window_end_ns - 1)
        self._close_inactivity(self.window_end_ns, recovered=False)
        for row in self.pending_rows:
            for variant in row["latency_variants"].values():
                if variant["status"] == "exit_pending":
                    variant["status"] = "unresolved_exit_window_end"
                elif variant["status"] == "entry_pending":
                    variant["status"] = "no_entry_window_end"
        self.pending_rows.clear()
        self.active_row = None
        self.window_closed = True

    def consume(self, item) -> None:
        target = isinstance(item, dbn.MBOMsg) and item.instrument_id == self.instrument_id
        snapshot = target and bool(item.flags & dbn.F_SNAPSHOT)
        reset = target and str(item.action) == "R"
        if target and self.incomplete_event and (snapshot or reset):
            raise ValueError("Incomplete target event before reset or snapshot")
        super().consume(item)
        if target and not snapshot:
            self.incomplete_event = not reset and not bool(item.flags & dbn.F_LAST)

    def finish_day(self) -> None:
        if not self.metadata_seen or self.day_target_records == 0:
            raise ValueError(f"Empty target contract in UTC day {self.day}")
        if self.incomplete_event or self.pending_trade_records:
            raise ValueError("Incomplete target event at UTC member end")
        if self.day.isoformat() in self.session_set:
            self._end_window()
            rows = self.rows[self.day_row_start :]
            if not rows or len(rows) > 14_400:
                raise ValueError("Missing or excessive event decisions in source session")
            times = [r["decision_ts_ns"] for r in rows]
            if any(b - a < DECISION_INTERVAL_NS for a, b in zip(times, times[1:], strict=False)):
                raise ValueError("Event decision rate exceeded the frozen limit")
            self.completed_sessions.append(self.day.isoformat())
            self.day_quality.append(
                {
                    "source_session": self.day.isoformat(),
                    "decision_events": len(rows),
                    "completed_quote_events": self.day_completed_quotes,
                    "inactivity_intervals": len(self.inactivity_intervals) - self.day_gap_start,
                }
            )
        else:
            self.window_closed = True

    def finish(self) -> tuple[list[dict], dict]:
        if tuple(self.completed_sessions) != self.sessions or self.pending_rows or self.active_row:
            raise ValueError("Incomplete event-sampled cohort")
        return self.rows, {
            **dict(self.counts),
            "by_session": self.day_quality,
            "inactivity_intervals": self.inactivity_intervals,
        }


def summarize(rows: list[dict]) -> dict:
    result = ofi.summarize(rows)
    result["decision_events"] = result.pop("grid_rows")
    result.pop("fresh_quotes")  # Every event decision uses its just-completed quote, age zero.
    for latency in clock.LATENCY_MS:
        variants = [
            r["latency_variants"][str(latency)] for r in rows if r["selected_counterfactual"]
        ]
        result["latency_ms"][str(latency)]["inactivity_exposed_entered"] = sum(
            v["inactivity_exposed"] and v["entry_ts_ns"] is not None for v in variants
        )
        holds = [
            (v["exit_ts_ns"] - v["entry_ts_ns"]) / clock.SECOND_NS
            for v in variants
            if v["status"] == "resolved"
        ]
        result["latency_ms"][str(latency)]["mean_hold_seconds"] = (
            statistics.mean(holds) if holds else None
        )
        result["latency_ms"][str(latency)]["max_hold_seconds"] = max(holds, default=None)
    return result


def evaluate(strategies: dict, by_session: list[dict]) -> dict:
    """Only the predeclared evaluation partition can supply a research conclusion."""
    variants = [v for s in strategies.values() for v in s["latency_ms"].values()]
    primary = strategies["ofi_queue"]["latency_ms"]["100"]
    days = [
        s["strategies"]["ofi_queue"]["latency_ms"]["100"]
        for s in by_session
        if s["source_session"] in EVALUATION
    ]
    blockers = []
    if any(v["unresolved_entered"] for v in variants):
        blockers.append("unresolved_evaluation_positions")
    if any(v["inactivity_exposed_entered"] for v in variants):
        blockers.append("inactivity_exposed_evaluation_positions")
    if (
        primary["closed"] < 100
        or len(days) != len(EVALUATION)
        or any(d["closed"] < 20 for d in days)
    ):
        blockers.append("insufficient_evaluation_sample")
    means = [v["net_ticks_by_extra_cost"]["1"]["mean_closed"] for v in [primary, *days]]
    if any(m is None or m <= 0 for m in means):
        blockers.append("nonpositive_after_one_extra_tick")
    return {
        "decision": (
            "inconclusive_unresolved_positions"
            if "unresolved_evaluation_positions" in blockers
            else "reject_for_promotion"
            if "nonpositive_after_one_extra_tick" in blockers
            else "inconclusive_quality_or_sample"
            if blockers
            else "requires_independent_replication_and_broker_execution"
        ),
        "blockers": blockers,
        "promotion_enabled": False,
    }


def load_config(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != CONFIG_SHA256:
        raise ValueError("Frozen event-scalp configuration changed")
    return json.loads(raw), digest


def source_fingerprints() -> dict:
    return {
        **ofi.source_fingerprints(),
        Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def run_experiment(
    *, project_root: Path, config_path: Path, rows_output: Path, summary_output: Path
) -> dict:
    if (
        rows_output.exists()
        or summary_output.exists()
        or rows_output.resolve() == summary_output.resolve()
    ):
        raise ValueError("Refusing to overwrite event-scalp evidence")
    config, digest = load_config(config_path)
    fingerprints = source_fingerprints()
    _, sources, intake_sha = selected_sources(config, project_root)
    if tuple(s["day"].isoformat() for s in sources) != ("2025-07-06", *SESSIONS):
        raise ValueError("Unexpected source day outside the registered event cohort")
    builders = {name: EventScalp(name) for name in ofi.STRATEGIES}
    archives, stamps, mappings = {}, {}, []
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
                    "instrument_id": builders["ofi_queue"].instrument_id,
                }
            )
        quality = {name: builder.finish()[1] for name, builder in builders.items()}
        for path, stamp in stamps.items():
            if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
                raise ValueError("Source archive changed during event replay")
    finally:
        for archive in archives.values():
            archive.close()
    if fingerprints != source_fingerprints():
        raise ValueError("Replay implementation changed during experiment")
    rows = [row for builder in builders.values() for row in builder.rows]
    raw = b"".join(
        (json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n").encode() for r in rows
    )
    splits = {
        label: {
            name: summarize([r for r in builder.rows if r["source_session"] in sessions])
            for name, builder in builders.items()
        }
        for label, sessions in (("development", DEVELOPMENT), ("evaluation", EVALUATION))
    }
    days = [
        {
            "source_session": s,
            "strategies": {
                name: summarize([r for r in builder.rows if r["source_session"] == s])
                for name, builder in builders.items()
            },
        }
        for s in SESSIONS
    ]
    report = {
        "artifact_type": "databento_6eu5_event_scalp_v1",
        "experiment_id": config["experiment_id"],
        "mode": "offline_research_only",
        "config_sha256": digest,
        "source_intake_report": config["source_intake_report"],
        "source_intake_sha256": intake_sha,
        "implementation_sha256": fingerprints,
        "rows": len(rows),
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
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
        "development_sessions": list(DEVELOPMENT),
        "evaluation_sessions": list(EVALUATION),
        "fitted_parameters": 0,
        "splits": splits,
        "by_session": days,
        **evaluate(splits["evaluation"], days),
        "limitations": [
            "Separate event-sampled protocol, not a passing rerun of fixed-grid OFI V1.",
            "Target inactivity is observable; quiet trading versus feed loss "
            "cannot be distinguished here.",
            "Quote counterfactuals omit fills, size, market impact and cTrader broker execution.",
            "Cost ticks and thresholds are assumptions, not estimated charges or proven alpha.",
            "Controls have independent schedules; slower variants reprice primary selections.",
            "All inspected sessions become exposed; three days cannot establish a durable edge.",
            "No training, model promotion or order routing is connected.",
        ],
    }
    clock._publish(rows_output, summary_output, raw, report)
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
    print(json.dumps({k: report[k] for k in ("decision", "blockers", "rows", "splits")}))


if __name__ == "__main__":
    main()
