"""Offline 6E cohort protocol tests; run with the isolated DBN runtime."""

import importlib.util
import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

HAS_DBN = importlib.util.find_spec("databento_dbn") is not None
HAS_ZSTD = importlib.util.find_spec("zstandard") is not None

if HAS_DBN and HAS_ZSTD:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import databento_dbn as dbn

    from ai_trader.research.databento_6e_training_data import (
        SECOND_NS,
        Book,
        CohortBuilder,
        FlowWindow,
        _mapped_instrument,
        _needed_dates,
        _session_list,
        cme_session,
    )


def ns(value):
    return int(value.timestamp()) * 1_000_000_000


@unittest.skipUnless(HAS_DBN and HAS_ZSTD, "Requires isolated Databento DBN runtime")
class Databento6EProtocolTests(unittest.TestCase):
    def test_cme_session_and_dst_transitions(self):
        self.assertEqual(cme_session(ns(datetime(2025, 3, 9, 21, 59, tzinfo=UTC))), None)
        self.assertEqual(cme_session(ns(datetime(2025, 3, 9, 22, tzinfo=UTC))), "2025-03-10")
        self.assertEqual(cme_session(ns(datetime(2025, 11, 2, 22, tzinfo=UTC))), None)
        self.assertEqual(cme_session(ns(datetime(2025, 11, 2, 23, tzinfo=UTC))), "2025-11-03")
        self.assertEqual(cme_session(ns(datetime(2025, 4, 1, 20, 59, tzinfo=UTC))), "2025-04-01")
        self.assertIsNone(cme_session(ns(datetime(2025, 4, 1, 21, tzinfo=UTC))))
        self.assertEqual(cme_session(ns(datetime(2025, 4, 1, 22, tzinfo=UTC))), "2025-04-02")

    def test_exact_session_inventory_and_source_days(self):
        sessions = ["2025-03-27", "2025-03-28", "2025-03-31"]
        self.assertEqual(_session_list({"source_sessions": sessions}), sessions)
        self.assertEqual(
            _needed_dates(sessions),
            [
                date(2025, 3, 26),
                date(2025, 3, 27),
                date(2025, 3, 28),
                date(2025, 3, 30),
                date(2025, 3, 31),
            ],
        )
        with self.assertRaisesRegex(ValueError, "complete"):
            _session_list({"source_sessions": ["2025-03-27", "2025-03-31", "2025-04-01"]})

    def test_contract_mapping_must_cover_exact_utc_day(self):
        day = date(2025, 3, 31)
        metadata = SimpleNamespace(
            dataset="GLBX.MDP3",
            start=ns(datetime(2025, 3, 31, tzinfo=UTC)),
            end=ns(datetime(2025, 4, 1, tzinfo=UTC)),
            schema=dbn.Schema.MBO,
            symbols=["6E.FUT"],
            not_found=[],
            mappings={"6EM5": [{"start_date": day, "end_date": date(2025, 4, 1), "symbol": "42"}]},
        )
        self.assertEqual(_mapped_instrument(metadata, "6EM5", day), 42)
        with self.assertRaisesRegex(ValueError, "dated outright mapping"):
            _mapped_instrument(metadata, "6EH5", day)

    def test_book_partial_cancel_and_trade_is_informational(self):
        book = Book()
        book.apply(self.event("R", "N", 0, 0, 0, 0))
        book.apply(self.event("A", "B", 100_000, 10, 1, 0))
        book.apply(self.event("C", "B", 100_000, 4, 1, 1))
        book.apply(self.event("T", "A", 100_000, 2, 0, 2))
        self.assertEqual(book.levels["B"][100_000], 6)
        self.assertFalse(book.errors)

    def test_rolling_flow_is_past_only_and_expires(self):
        flow = FlowWindow()
        flow.add(0, self.event("T", "B", 100_000, 3, 0, 0), None)
        flow.add(1_000_000_000, self.event("C", "A", 100_000, 2, 2, 1), None)
        at_one = flow.snapshot(1_000_000_000)
        self.assertEqual(at_one["cvd_rolling"], 3)
        self.assertEqual(at_one["cancel_imbalance_rolling"], 1.0)
        self.assertEqual(flow.snapshot(302_000_000_000)["cvd_rolling"], 0)

    def test_forward_label_uses_later_mid_and_stays_in_session(self):
        session = "2025-03-31"
        builder = CohortBuilder([session], "6EM5")
        builder.start_day(date(2025, 3, 31))
        builder.metadata_seen = True
        builder.instrument_id = 42
        base = ns(datetime(2025, 3, 31, 12, tzinfo=UTC))
        builder.consume(self.event("R", "N", 0, 0, 0, base, flags=dbn.F_SNAPSHOT))
        builder.consume(self.event("A", "B", 1_000_000_000, 10, 1, base, flags=dbn.F_SNAPSHOT))
        builder.consume(self.event("A", "A", 1_000_100_000, 10, 2, base, flags=dbn.F_SNAPSHOT))
        builder.consume(
            self.event("T", "B", 1_000_100_000, 3, 0, base + SECOND_NS, flags=dbn.F_LAST)
        )
        self.assertEqual(len(builder.rows), 0)
        self.assertEqual(len(builder.pending), 1)
        builder.consume(self.event("M", "B", 1_000_050_000, 10, 1, base + 60 * SECOND_NS))
        builder.consume(
            self.event("M", "A", 1_000_150_000, 10, 2, base + 61 * SECOND_NS, flags=dbn.F_LAST)
        )
        self.assertEqual(len(builder.rows), 1)
        row = builder.rows[0]
        self.assertEqual(row["label"], 1)
        self.assertEqual(row["cvd_rolling"], 3)
        self.assertGreaterEqual(row["label_end_ts_ns"], row["decision_ts_ns"] + 60 * SECOND_NS)
        self.assertEqual(row["source_session"], session)

    def test_future_exchange_timestamp_rejected(self):
        builder = CohortBuilder(["2025-03-31"], "6EM5")
        builder.start_day(date(2025, 3, 31))
        builder.metadata_seen = True
        builder.instrument_id = 42
        timestamp = ns(datetime(2025, 3, 31, 12, tzinfo=UTC))
        builder.consume(self.event("R", "N", 0, 0, 0, timestamp, flags=dbn.F_SNAPSHOT))
        with self.assertRaisesRegex(ValueError, "exchange timestamp"):
            builder.consume(self.event("T", "B", 100_000, 1, 0, timestamp, ts_event=timestamp + 1))

    def test_only_exact_closed_period_bad_timestamp_clear_is_accepted(self):
        sunday = date(2025, 3, 30)
        builder = CohortBuilder(["2025-03-31"], "6EM5")
        builder.start_day(sunday)
        builder.metadata_seen = True
        builder.instrument_id = 42
        closed = ns(datetime(2025, 3, 30, 11, 7, 48, tzinfo=UTC))
        builder.consume(self.event("R", "N", 0, 0, 0, closed, flags=dbn.F_BAD_TS_RECV))
        self.assertEqual(len(builder.accepted_closed_period_clears), 1)
        self.assertEqual(builder.accepted_closed_period_clears[0]["ts_recv_ns"], closed)
        self.assertEqual(len(builder.rows), 0)
        self.assertEqual(len(builder.pending), 0)
        self.assertFalse(builder.flow.events)
        with self.assertRaisesRegex(ValueError, "quality flag"):
            builder.consume(
                self.event("T", "B", 100_000, 1, 0, closed + 1, flags=dbn.F_BAD_TS_RECV)
            )
        opened = ns(datetime(2025, 3, 30, 22, tzinfo=UTC))
        with self.assertRaisesRegex(ValueError, "quality flag"):
            builder.consume(self.event("R", "N", 0, 0, 0, opened, flags=dbn.F_BAD_TS_RECV))
        window_but_closed = ns(datetime(2025, 3, 30, 12, tzinfo=UTC))
        with self.assertRaisesRegex(ValueError, "quality flag"):
            builder.consume(
                self.event("R", "N", 0, 0, 0, window_but_closed, flags=dbn.F_BAD_TS_RECV)
            )

    @staticmethod
    def event(action, side, price, size, order_id, timestamp, flags=0, ts_event=None):
        return dbn.MBOMsg(
            publisher_id=1,
            instrument_id=42,
            ts_event=timestamp if ts_event is None else ts_event,
            order_id=order_id,
            price=price,
            size=size,
            action=dbn.Action.from_str(action),
            side=dbn.Side.from_str(side),
            ts_recv=timestamp,
            flags=flags,
        )


if __name__ == "__main__":
    unittest.main()
