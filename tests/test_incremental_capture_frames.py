"""The incremental frame contract must match the complete offline capture replay."""

from copy import deepcopy

import pytest
from test_capture_replay import cfg, records, source, with_profit_tick

from ai_trader.trading.capture_replay import IncrementalCaptureFrames


def incremental(rows):
    stream = IncrementalCaptureFrames(rows[0], rows[1], source_session="capture-one", config=cfg())
    frames = [stream.opening_frame()]
    for row in rows[2:-1]:
        frame = stream.push(row)
        if frame is not None:
            frames.append(frame)
    return stream, frames


@pytest.mark.parametrize("scenario", ["ordinary", "pre_snapshot", "market_fault"])
def test_incremental_frames_match_complete_replay_and_prefix_rebuild(scenario):
    rows = with_profit_tick() if scenario == "ordinary" else records()
    if scenario == "pre_snapshot":
        rows[1]["received_at_ns"] = 1_075_000_000
    if scenario == "market_fault":
        rows[2]["event"]["s"] = "ETHUSDT"
    complete = list(source(rows).frames())
    stream, frames = incremental(rows)
    assert frames == complete[:-1]
    assert stream.opening_frame() == complete[0]
    assert stream.close(rows[-1]) == complete[-1]
    with pytest.raises(ValueError, match="closed"):
        stream.push(rows[2])
    with pytest.raises(ValueError, match="footer"):
        stream.close(rows[-1])

    # A crash/restart can reconstruct the exact paper prefix from staged rows.
    for count in range(len(rows[2:-1]) + 1):
        _, rebuilt = incremental([*deepcopy(rows[: 2 + count]), rows[-1]])
        expected_lines = {
            2,
            *(
                i + 3
                for i, row in enumerate(rows[2 : 2 + count])
                if row["received_at_ns"] > rows[1]["received_at_ns"]
            ),
        }
        assert rebuilt == [frame for frame in frames if frame.line_number in expected_lines]


def test_snapshot_buffered_events_never_make_early_paper_frames():
    rows = records()
    rows[1]["received_at_ns"] = 1_075_000_000
    stream = IncrementalCaptureFrames(rows[0], rows[1], source_session="capture-one", config=cfg())
    assert stream.push(rows[2]) is None
    assert stream.push(rows[3]) is None
    assert stream.opening_frame().tick.features_ready is False
    assert stream.push(rows[4]).observation.session_cvd_base == 0


def test_stream_rejects_bad_framing_receipt_and_footer_before_claiming_completion():
    rows = records()
    bad_start = dict(rows[0], schema_version=True)
    with pytest.raises(ValueError, match="envelope"):
        IncrementalCaptureFrames(bad_start, rows[1], source_session="capture-one", config=cfg())
    stream = IncrementalCaptureFrames(rows[0], rows[1], source_session="capture-one", config=cfg())
    stream.push(rows[2])
    with pytest.raises(ValueError, match="regressed"):
        stream.push(dict(rows[3], received_at_ns=rows[0]["started_at_ns"]))
    with pytest.raises(ValueError, match="count mismatch"):
        stream.close(dict(rows[-1], depth_events=0))
    with pytest.raises(ValueError, match="exceeded footer"):
        stream.close(dict(rows[-1], ended_at_ns=rows[0]["started_at_ns"]))
    # An invalid footer does not close the stream or turn it into a success.
    for row in rows[3:-1]:
        stream.push(row)
    assert stream.close(rows[-1]).status == "session_closed"
