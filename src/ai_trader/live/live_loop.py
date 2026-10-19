"""Live loop: capture -> minute store -> rule -> (demo) bracket order, once a minute in the London window.

Each cycle (default every 60 s between 06:55 and 09:05 UTC, plus housekeeping until 21:00):
1. convert the NinjaTrader capture files of the day into the live minute store (capture_minutes);
2. run the fixed rule over warm-up history + live store (shadow_signals.decisions);
3. a decision whose entry minute is the current or previous minute and that has not been sent yet is
   turned into a bracket intent (ctrader_bridge.intent_from_decision) and, if the loop is **armed**
   and a bridge is available, placed on the DEMO account; otherwise it is logged as ``would_place``;
4. positions opened by this loop are closed after ``hold`` minutes or at 20:55 UTC (the bracket's own
   stop/target close them earlier at the broker).

State lives in ``logs/live/sent.jsonl`` (one row per decision handled) so restarts never resend.
A kill-switch file stops orders without stopping the loop. Nothing here is a learning loop: the
rule is fixed; decisions and outcomes are the record the later learning stage will be judged on.
"""

from __future__ import annotations

import argparse
import glob
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ai_trader.live import capture_minutes as cm
from ai_trader.live import shadow_signals as ss

WINDOW = (6 * 60 + 55, 9 * 60 + 5)   # minutes of UTC day in which entries are evaluated
FLAT_AT = 20 * 60 + 55


class LoopState:
    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict] = []
        if path.exists():
            self.rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]

    def key(self, d: dict) -> str:
        return f"{d['date']} {d['minute_utc']} {d['side']}"

    def seen(self, d: dict) -> bool:
        k = self.key(d)
        return any(r["key"] == k for r in self.rows)

    def record(self, row: dict) -> None:
        self.rows.append(row)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(json.dumps(row) + "\n")

    def open_orders(self) -> list[dict]:
        closed = {r["key"] for r in self.rows if r.get("action") == "closed"}
        return [r for r in self.rows if r.get("action") == "placed" and r["key"] not in closed]


def convert_today(capture_glob: str, store: Path) -> int:
    paths = sorted(Path(p) for p in glob.glob(capture_glob))
    if not paths:
        return 0
    rows = cm.read_capture(paths)
    bars, book = cm.convert(rows)
    cm.write_docs(bars, book, store)
    return len(rows)


def fresh_decisions(store: Path, warm_bars: Path | None, warm_book: Path | None, now: datetime) -> list[dict]:
    days: dict = {}
    if warm_bars:
        ss.load_store(warm_bars, warm_book, days)
    if (store / "bars").exists():
        ss.load_store(store / "bars", store / "book", days)
    if not days:
        return []
    out = ss.decisions(ss.arrays(days), since=now.date())
    cur = now.hour * 60 + now.minute
    fresh = []
    for d in out:
        hh, mm = (int(v) for v in d["minute_utc"].split(":"))
        if d["date"] == now.date().isoformat() and cur - 1 <= hh * 60 + mm <= cur:
            fresh.append(d)
    return fresh


def cycle(now: datetime, state: LoopState, store: Path, capture_glob: str, warm_bars, warm_book,
          bridge=None, armed: bool = False, lots: float = 0.01, hold: int = 240, log=print) -> list[dict]:
    from ai_trader.live.ctrader_bridge import intent_from_decision
    actions = []
    cur = now.hour * 60 + now.minute
    if WINDOW[0] <= cur <= WINDOW[1]:
        n = convert_today(capture_glob, store)
        for d in fresh_decisions(store, warm_bars, warm_book, now):
            if state.seen(d):
                continue
            intent = intent_from_decision(d, lots=lots)
            row = {"key": state.key(d), "utc": now.isoformat(timespec="seconds"), "decision": d, "intent": intent}
            if armed and bridge is not None:
                try:
                    result = bridge.place_bracket(**intent)
                    row.update(action="placed", result=result, close_after=(now + timedelta(minutes=hold)).isoformat())
                except Exception as exc:  # bridge refusals are logged, never retried automatically
                    row.update(action="refused", error=str(exc))
            else:
                row.update(action="would_place")
            state.record(row)
            actions.append(row)
            log(f"{row['action']}: {row['key']} {intent['side']} stop {intent['stop_price_distance']:.5f}")
        log(f"{now:%H:%M} UTC: {n} capture records, {len(actions)} new decisions")
    # housekeeping: time exits and day-end flat for positions this loop opened
    for r in state.open_orders():
        due = now >= datetime.fromisoformat(r["close_after"]) or cur >= FLAT_AT
        if due and bridge is not None:
            pos_id = (r.get("result") or {}).get("position_id")
            try:
                res = bridge.close_position(pos_id, int(round(r["intent"]["lots"] * 100_000 * 100))) if pos_id else {"skipped": "no position id"}
                state.record({"key": r["key"], "utc": now.isoformat(timespec="seconds"), "action": "closed", "result": res})
                actions.append({"key": r["key"], "action": "closed"})
                log(f"closed: {r['key']}")
            except Exception as exc:
                log(f"close failed for {r['key']}: {exc}")
    return actions


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--capture-glob", default=str(Path.home() / "Documents" / "NinjaTrader 8" / "ai-trader-captures" / "ninjatrader-*.jsonl"))
    p.add_argument("--store", type=Path, default=Path("data/live/6e_minutes"))
    p.add_argument("--warmup-bars", type=Path, default=Path("data/processed/6e_minute_bars_dev_1"))
    p.add_argument("--warmup-book", type=Path, default=Path("data/processed/6e_book_minutes_dev_1"))
    p.add_argument("--state", type=Path, default=Path("logs/live/sent.jsonl"))
    p.add_argument("--config", type=Path, default=Path("config/ctrader_demo.json"))
    p.add_argument("--arm", action="store_true", help="actually place DEMO orders; default logs only")
    p.add_argument("--transport", choices=["file", "api"], default="file",
                   help="file = AiTraderFileBridge cBot inside cTrader (no API app needed); api = Open API (needs config)")
    p.add_argument("--once", action="store_true", help="run one cycle now and exit")
    p.add_argument("--interval", type=int, default=60)
    a = p.parse_args(argv)
    bridge = None
    if a.arm:
        if a.transport == "api":
            from ai_trader.live import ctrader_bridge as cb
            cfg = cb.load_config(a.config)
            host = tuple(cfg["host"]) if cfg.get("host") else cb.DEMO_HOST
            bridge = cb.CTraderBridge(cb.TlsTransport(host), cfg, Path("logs/ctrader/audit.jsonl"))
        else:
            from ai_trader.live import ctrader_file_bridge as fb
            bridge = fb.FileBridge()
        print("bridge:", bridge.connect(), flush=True)
    state = LoopState(a.state)
    while True:
        now = datetime.now(timezone.utc)
        cycle(now, state, a.store, a.capture_glob, a.warmup_bars, a.warmup_book, bridge, a.arm)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
