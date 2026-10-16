import pytest

from ai_trader.research.hf_spot_quality import _check_quote, _rabbit_line


def test_rabbit_line_preserves_pipe_inside_payload() -> None:
    timestamp, channel, payload = _rabbit_line(b'123|okx.spot.btc|{"text":"a|b"}\n')
    assert (timestamp, channel, payload) == (123, "okx.spot.btc", {"text": "a|b"})


def test_rabbit_line_accepts_protocol_heartbeat() -> None:
    assert _rabbit_line(b"123|okx.spot.btc|pong\n") == (123, "okx.spot.btc", None)


def test_rabbit_line_rejects_invalid_payload() -> None:
    with pytest.raises(ValueError):
        _rabbit_line(b"123|okx.spot.btc|not-json\n")


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ({"b": "100", "a": "101", "B": "1", "A": "2"}, True),
        ({"b": "101", "a": "100", "B": "1", "A": "2"}, False),
        ({"b": "100", "a": "101", "B": "-1", "A": "2"}, False),
    ],
)
def test_quote_integrity(quote: dict[str, str], expected: bool) -> None:
    assert _check_quote(quote) is expected
