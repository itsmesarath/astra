"""Paired historical quote horizons and observed barriers; no fitting or execution."""

from __future__ import annotations

import argparse
import hashlib
from array import array
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_microdepth as data
from ai_trader.research import historical_6e_diagnostics as diagnostics
from ai_trader.training import train_6e_opportunity as common

clock = data.clock
SESSIONS = ("2025-07-07", "2025-07-08", "2025-07-09")
SOURCE_DAYS = ("2025-07-06", *SESSIONS)
HORIZONS = (1, 5, 15, 30, 60)
BARRIERS = (2, 4)
MAX_QUOTES = 2_000_000  # Per session; packed timestamp, bid, ask use 48 MB at this bound.
CONFIG = "configs/databento_6e_microdepth_tree_v1.json"


def protocol() -> dict:
    return {
        "artifact_type": "6e_paired_paths_protocol_v1",
        "sessions": list(SESSIONS),
        "source_days": list(SOURCE_DAYS),
        "exposure": "Already exposed development sessions only; no independent test",
        "original_config_sha256": data.CONFIG_SHA256,
        "original_rows_sha256": common.ROWS_SHA256,
        "horizons_seconds": list(HORIZONS),
        "symmetric_gross_barriers_ticks": list(BARRIERS),
        "extra_cost_ticks": list(diagnostics.EXTRA_COSTS),
        "entry": "Unchanged original eligibility and first quote at/after 100ms, within 1s wait",
        "exit": "First completed quote at/after entry plus horizon, strictly before 16 UTC",
        "path": "Entry quote through scheduled horizon, inclusive first quote exactly at deadline; "
        "late exit quotes excluded from path extrema and crossings",
        "barriers": "First observed gross liquidation quote at +threshold or -threshold, "
        "in event order including equal timestamps; triggers only, not fills or stop strategy PnL",
        "gaps": "Strictly greater than 5s between completed quotes or to observation deadline",
        "censoring": "Retain all entry failures and window-end unresolved exits; no interpolation",
        "paired": "All horizons resolved; also report all attempts and a no-gap/no-late subset",
        "thinning": "First eligible decision at least 60s after prior selected eligible decision",
        "original_regression": "Exact original fields including 23 features and 15s outcomes",
        "max_completed_quotes_per_session": MAX_QUOTES,
        "training_enabled": False,
        "trading_enabled": False,
        "promotion_enabled": False,
    }


def fingerprints() -> dict:
    paths = (
        Path(__file__),
        Path(data.__file__),
        Path(data.base.__file__),
        Path(diagnostics.__file__),
        Path(common.__file__),
    )
    return {
        **data.base.events.source_fingerprints(),
        **diagnostics.baseline.fingerprints(),
        **{p.name: common.hash_file(p, 1024 * 1024) for p in paths},
    }


def prepare(path: Path) -> dict:
    """Freeze assumptions and code before reading market outcomes."""
    result = {
        "protocol": protocol(),
        "implementation_sha256": fingerprints(),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    common._write_new(path, result)
    return result


def verify_registration(path: Path) -> tuple[dict, str]:
    pin = common.hash_file(path, 64 * 1024)
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError("Registration changed while reading")
    result = common.loads(raw)
    if (
        result.get("protocol") != protocol()
        or result.get("implementation_sha256") != fingerprints()
    ):
        raise ValueError("Frozen path registration or implementation differs")
    return result, pin


def validate_quotes(quotes: np.ndarray, window_end: int) -> None:
    if (
        quotes.dtype != np.int64
        or quotes.ndim != 2
        or quotes.shape[1] != 3
        or not 1 <= len(quotes) <= MAX_QUOTES
    ):
        raise ValueError("Invalid bounded quote array")
    ts, bid, ask = quotes.T
    if (
        np.any(np.diff(ts) < 0)
        or np.any(ts < 0)
        or np.any(ts >= window_end)
        or np.any(bid <= 0)
        or np.any(ask <= bid)
        or np.any(bid % clock.TICK)
        or np.any(ask % clock.TICK)
    ):
        raise ValueError("Invalid completed quote sequence")


def first_crossing(values: np.ndarray, times: np.ndarray, threshold: int) -> dict:
    hits = np.flatnonzero((values >= threshold) | (values <= -threshold))
    if not len(hits):
        return {"kind": "none_observed", "ts_ns": None, "gross_ticks": None}
    i = int(hits[0])
    return {
        "kind": "target" if values[i] >= threshold else "stop",
        "ts_ns": int(times[i]),
        "gross_ticks": float(values[i]),
    }


def analyze_entry(quotes: np.ndarray, outcome: dict, window_end: int) -> dict:
    """Use one actual entry for every horizon; caller validates the session array once."""
    if outcome.get("entry_ts_ns") is None:
        return {}
    times = quotes[:, 0]
    i = int(np.searchsorted(times, outcome["entry_target_ts_ns"], side="left"))
    expected = (outcome["entry_ts_ns"], outcome["entry_bid_nano"], outcome["entry_ask_nano"])
    if i >= len(quotes) or tuple(quotes[i]) != expected:
        raise ValueError("Original entry differs from first observed quote")
    if (
        expected[0] > outcome["entry_target_ts_ns"] + clock.QUOTE_WAIT_NS
        or expected[2] - expected[1] != clock.TICK
    ):
        raise ValueError("Invalid original entry timing or spread")
    result = {}
    for horizon in HORIZONS:
        target = expected[0] + horizon * clock.SECOND_NS
        j = int(np.searchsorted(times, target, side="left"))
        resolved = j < len(quotes) and target < window_end
        # A late recovery quote must never be backdated into the scheduled path.
        stop = j + 1 if resolved and times[j] == target else j
        path = quotes[i:stop]
        deadline = min(target, window_end - 1)
        gaps = np.diff(path[:, 0])
        path_gap = max(int(gaps.max()) if len(gaps) else 0, deadline - int(path[-1, 0]))
        exit_gap = path_gap
        if resolved:
            exit_gap = max(exit_gap, int(times[j] - times[j - 1]))
        else:
            exit_gap = max(exit_gap, window_end - 1 - int(times[-1]))
        exit_ts = int(times[j]) if resolved else None
        values = ((path[:, 1] - expected[2]) / clock.TICK, (expected[1] - path[:, 2]) / clock.TICK)
        item = {
            "status": "resolved" if resolved else "unresolved_exit_window_end",
            "exit_target_ts_ns": target,
            "exit_ts_ns": exit_ts,
            "exit_bid_nano": int(quotes[j, 1]) if resolved else None,
            "exit_ask_nano": int(quotes[j, 2]) if resolved else None,
            "exit_lateness_ns": exit_ts - target if resolved else None,
            "late_exit": exit_ts > target + clock.QUOTE_WAIT_NS if resolved else None,
            "inactivity_exposed": exit_gap > data.base.events.INACTIVITY_NS,
            "path_inactivity_exposed": path_gap > data.base.events.INACTIVITY_NS,
            "path_max_quote_gap_ns": path_gap,
            "path_observation_deadline_ns": deadline,
            "path_window_truncated": target >= window_end,
            "path_quote_count": len(path),
            "gross_long_short_ticks": [
                float((quotes[j, 1] - expected[2]) / clock.TICK),
                float((expected[1] - quotes[j, 2]) / clock.TICK),
            ]
            if resolved
            else None,
            "directions": {
                name: {
                    "max_liquidation_ticks": float(v.max()),
                    "min_liquidation_ticks": float(v.min()),
                    "barriers": {str(b): first_crossing(v, path[:, 0], b) for b in BARRIERS},
                }
                for name, v in zip(("long", "short"), values, strict=True)
            },
        }
        result[str(horizon)] = item
    old = result["15"]
    for key in (
        "status",
        "exit_target_ts_ns",
        "exit_ts_ns",
        "exit_bid_nano",
        "exit_ask_nano",
        "inactivity_exposed",
    ):
        if old[key] != outcome[key]:
            raise ValueError(f"15s reconstructed quote regression: {key}")
    if old["status"] == "resolved":
        for key in ("late_exit", "exit_lateness_ns"):
            if old[key] != outcome[key]:
                raise ValueError(f"15s reconstructed quote regression: {key}")
        if old["gross_long_short_ticks"][0] != outcome["gross_crossed_quote_ticks"]:
            raise ValueError("15s gross quote target regression")
    return result


class PathBuilder(data.MicrodepthBuilder):
    def __init__(self, sessions: tuple[str, ...] = SESSIONS, minimum_resolved: int = 100):
        super().__init__(sessions, minimum_resolved)
        self.path_rows: dict[tuple[str, int], dict] = {}

    def start_day(self, day) -> None:
        super().start_day(day)
        self.quote_buffer = array("q")

    def _process_quote(self, quote: clock.Quote) -> None:
        if len(self.quote_buffer) // 3 >= MAX_QUOTES:
            raise ValueError("Completed quote bound exceeded")
        self.quote_buffer.extend((quote.ts_recv_ns, quote.bid, quote.ask))
        super()._process_quote(quote)

    def finish_day(self) -> None:
        super().finish_day()
        if self.day.isoformat() not in self.session_set:
            return
        quotes = np.frombuffer(self.quote_buffer, dtype=np.int64).reshape(-1, 3)
        validate_quotes(quotes, self.window_end_ns)
        for row in self.rows[self.day_row_start :]:
            outcome = row["latency_variants"].get("100", {"status": "not_eligible"})
            self.path_rows[(row["source_session"], row["decision_ts_ns"])] = analyze_entry(
                quotes, outcome, self.window_end_ns
            )

    def finish(self) -> tuple[list[dict], dict]:
        rows, quality = super().finish()
        for row in rows:
            row["path_horizons"] = self.path_rows[(row["source_session"], row["decision_ts_ns"])]
        return rows, quality


def verify_original(rows: list[dict], original: list[dict]) -> None:
    reduced = [{k: v for k, v in r.items() if k != "path_horizons"} for r in rows]
    selected = [r for r in original if r["source_session"] in SESSIONS]
    if not selected or reduced != selected:
        raise ValueError("Original 15s rows or features changed")


def paired(rows: list[dict], *, clean: bool = False) -> list[dict]:
    return [
        r
        for r in rows
        if len(r["path_horizons"]) == len(HORIZONS)
        and all(
            h["status"] == "resolved"
            and (not clean or not (h["inactivity_exposed"] or h["late_exit"]))
            for h in r["path_horizons"].values()
        )
    ]


def horizon_summary(rows: list[dict]) -> dict:
    result = {}
    for horizon in HORIZONS:
        entered = [r["path_horizons"][str(horizon)] for r in rows if r["path_horizons"]]
        resolved = [h for h in entered if h["status"] == "resolved"]
        gross = np.asarray([h["gross_long_short_ticks"] for h in resolved], dtype=float).reshape(
            -1, 2
        )
        result[str(horizon)] = {
            "entered": len(entered),
            "resolved": len(resolved),
            "unresolved": len(entered) - len(resolved),
            "late_exits": sum(h["late_exit"] for h in resolved),
            "inactivity_exposed": sum(h["inactivity_exposed"] for h in entered),
            "window_truncated_paths": sum(h["path_window_truncated"] for h in entered),
            "extra_cost_ticks": {
                str(cost): {
                    "hindsight_either_direction_positive_fraction": float(
                        (gross.max(axis=1) > cost).mean()
                    )
                    if len(gross)
                    else None,
                    "mean_long_short_net_ticks": (gross - cost).mean(axis=0).tolist()
                    if len(gross)
                    else None,
                }
                for cost in diagnostics.EXTRA_COSTS
            },
            "exit_lateness_ms": diagnostics.distribution(
                [h["exit_lateness_ns"] / 1e6 for h in resolved]
            ),
            "paths_all_entered_including_censored": {
                side: {
                    "max_liquidation_ticks": diagnostics.distribution(
                        [h["directions"][side]["max_liquidation_ticks"] for h in entered]
                    ),
                    "min_liquidation_ticks": diagnostics.distribution(
                        [h["directions"][side]["min_liquidation_ticks"] for h in entered]
                    ),
                    "barrier_first_observation_counts": {
                        str(b): dict(
                            Counter(
                                h["directions"][side]["barriers"][str(b)]["kind"] for h in entered
                            )
                        )
                        for b in BARRIERS
                    },
                }
                for side in ("long", "short")
            },
        }
    return result


def summarize(rows: list[dict]) -> dict:
    thinned = diagnostics.thin_causally(rows)
    return {
        "decisions": len(rows),
        "eligible": sum(r["eligible"] for r in rows),
        "original_outcome_counts": dict(Counter(r["outcome"]["status"] for r in rows)),
        "paired_all_resolved_count": len(paired(rows)),
        "paired_no_gap_no_late_count": len(paired(rows, clean=True)),
        "all_attempts": horizon_summary(rows),
        "paired_all_resolved": horizon_summary(paired(rows)),
        "paired_no_gap_no_late": horizon_summary(paired(rows, clean=True)),
        "causally_thinned_decisions": len(thinned),
        "causally_thinned_all_attempts": horizon_summary(thinned),
    }


def run(*, root: Path, registration: Path, rows_output: Path, summary_output: Path) -> dict:
    if (
        rows_output.exists()
        or summary_output.exists()
        or rows_output.resolve() == summary_output.resolve()
    ):
        raise ValueError("Refusing to overwrite historical path evidence")
    frozen, registration_pin = verify_registration(registration)
    config, _ = data.load_config(root / CONFIG)
    config = {**config, "source_sessions": list(SESSIONS)}
    original = diagnostics.load_rows(root / common.ROWS_PATH)
    rows, evidence = data.base.build_targets(
        config, root, builder=PathBuilder(), source_days=SOURCE_DAYS
    )
    verify_original(rows, original)
    del original
    raw = b"".join(common.canonical(r) + b"\n" for r in rows)
    report = {
        "artifact_type": "6e_paired_historical_paths_v1",
        "mode": "offline_research_only",
        "registration_sha256": registration_pin,
        **frozen,
        **evidence,
        "original_regression": "exact_all_original_fields_and_rows_on_selected_sessions",
        "rows_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": summarize(rows),
        "by_session": {
            s: summarize([r for r in rows if r["source_session"] == s]) for s in SESSIONS
        },
        "decision": "exploratory_only_no_strategy_promotion",
        "limitations": [
            "Overlapping entries are not a tradable portfolio or independent observations.",
            "Three exposed sessions cannot establish generalization or select the best horizon.",
            "Extrema and crossings are observed quotes, not fills; no stop latency model.",
            "Inactivity can hide crossings; none_observed does not establish no real crossing.",
            "Late exits remain marked; paired/clean subsets are outcome-dependent diagnostics.",
            "No broker EURUSD spread, basis, slippage, rejection or queue simulation.",
            "No new training, model selection, downloads, platform connection or trading.",
        ],
    }
    if verify_registration(registration)[1] != registration_pin:
        raise ValueError("Registration changed during replay")
    if common.hash_file(root / common.ROWS_PATH, common.MAX_BYTES) != common.ROWS_SHA256:
        raise ValueError("Original rows changed during replay")
    clock._publish(rows_output, summary_output, raw, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--rows-output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    if args.prepare:
        prepare(args.registration)
        print("Historical path protocol frozen; no market files opened.")
    else:
        if args.rows_output is None or args.summary_output is None:
            parser.error("Execution requires new rows and summary output paths")
        report = run(
            root=args.project_root,
            registration=args.registration,
            rows_output=args.rows_output,
            summary_output=args.summary_output,
        )
        print(
            common.canonical(
                {
                    "decision": report["decision"],
                    "decisions": report["summary"]["decisions"],
                    "rows_sha256": report["rows_sha256"],
                }
            ).decode()
        )


if __name__ == "__main__":
    main()
