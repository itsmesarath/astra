"""Synthetic compressed snapshots: independent wire/output budgets and strict framing."""

import asyncio
import gzip
import json
from email.message import Message

import pytest
from test_capture_replay import records

from ai_trader.ingestion import collect_combined as module
from ai_trader.ingestion.capture_failure import failure_details

SECRET = "private-response-header-or-decoder-message"


@pytest.fixture
def response_factory(monkeypatch):
    """Install exactly one context-managed, chunked response; prohibit real IO."""
    responses = []

    def install(body, encodings=(), *, chunk_size=13):
        class Headers(Message):
            def get_all(self, name, failobj=None):
                assert response.entered and not response.closed
                return super().get_all(name, failobj)

        class Response:
            entered = False
            closed = False
            offset = 0

            def __init__(self):
                self.headers = Headers()
                for value in encodings:
                    self.headers["Content-Encoding"] = value
                self.read_sizes = []
                self.calls = []

            def __enter__(self):
                self.entered = True
                return self

            def __exit__(self, *args):
                self.closed = True

            def read1(self, size):
                assert self.entered and not self.closed
                assert 0 < size <= 64 * 1024
                self.read_sizes.append(size)
                chunk = body[self.offset : self.offset + min(size, chunk_size)]
                self.offset += len(chunk)
                return chunk

        response = Response()

        def open_response(request, *, timeout):
            response.calls.append((request, timeout))
            assert len(response.calls) == 1
            assert request.full_url == module.SNAPSHOT_URL
            assert request.get_header("Accept-encoding") == "gzip"
            assert request.data is None and request.get_method() == "GET"
            assert timeout == 10
            return response

        monkeypatch.setattr(module.urllib.request, "urlopen", open_response)
        responses.append(response)
        return response

    yield install
    for response in responses:
        assert len(response.calls) == 1 and response.closed


def _body():
    return json.dumps(records()[1]["event"]).encode()


def _gzip_wire_size(body, size):
    """Pad the gzip filename field without adding members or decoded bytes."""
    compressed = gzip.compress(body, mtime=0)
    padding = size - len(compressed)
    assert padding > 0
    header = bytearray(compressed[:10])
    header[3] = 8  # FNAME; one terminated name is part of this member's header.
    return bytes(header) + b"p" * (padding - 1) + b"\0" + compressed[10:]


@pytest.mark.parametrize("encoding", ["gzip", "GZIP", " gZiP "])
@pytest.mark.parametrize("via_worker", [False, True])
def test_valid_gzip_snapshot_preserves_payload_and_request_budget(
    response_factory, encoding, via_worker
):
    response_factory(gzip.compress(_body(), mtime=0), (encoding,))
    assert module.MAX_SNAPSHOT_BYTES == 1_900_000
    assert module.SNAPSHOT_URL.endswith("/api/v3/depth?symbol=BTCUSDT&limit=1000")
    result = (
        asyncio.run(module._snapshot_with_failure_code()) if via_worker else module.fetch_snapshot()
    )
    assert result == records()[1]["event"]


@pytest.mark.parametrize("encodings", [(), ("identity",), (" IDENTITY ",)])
def test_absent_and_identity_encoding_remain_compatible(response_factory, encodings):
    response_factory(_body(), encodings)
    assert module.fetch_snapshot() == records()[1]["event"]


@pytest.mark.parametrize(
    "encodings",
    [
        ("",),
        ("   ",),
        ("br",),
        ("deflate",),
        ("gzip, identity",),
        ("gzip, gzip",),
        ("gzip", "gzip"),
        ("identity", "gzip"),
        ("identity", "identity"),
        (SECRET,),
    ],
)
@pytest.mark.parametrize("via_worker", [False, True])
def test_ambiguous_or_unknown_encoding_rejected_before_body(
    response_factory, encodings, via_worker
):
    response = response_factory(gzip.compress(_body()), encodings)
    with pytest.raises(ValueError) as caught:
        if via_worker:
            asyncio.run(module._snapshot_with_failure_code())
        else:
            module.fetch_snapshot()
    assert failure_details(caught.value)["reason"] == "invalid_response"
    assert SECRET not in str(caught.value)
    assert not response.read_sizes


@pytest.mark.parametrize("gzip_encoded", [False, True])
def test_exact_decoded_byte_budget_is_accepted(monkeypatch, response_factory, gzip_encoded):
    cap = 512
    monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", cap)
    body = _body().ljust(cap, b" ")
    assert len(body) == cap
    response_factory(
        gzip.compress(body) if gzip_encoded else body, ("gzip",) if gzip_encoded else ()
    )
    assert module.fetch_snapshot() == records()[1]["event"]


def test_exact_compressed_wire_budget_is_accepted(monkeypatch, response_factory):
    cap = 512
    monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", cap)
    response_factory(_gzip_wire_size(_body(), cap), ("gzip",))
    assert module.fetch_snapshot() == records()[1]["event"]


@pytest.mark.parametrize("gzip_encoded", [False, True])
def test_wire_budget_rejected_before_decoding(monkeypatch, response_factory, gzip_encoded):
    cap = 512
    monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", cap)
    body = _gzip_wire_size(_body(), cap + 1) if gzip_encoded else _body().ljust(cap + 1, b" ")
    response = response_factory(body, ("gzip",) if gzip_encoded else (), chunk_size=64 * 1024)
    with pytest.raises(module.CaptureQuotaExceeded) as caught:
        module.fetch_snapshot()
    assert failure_details(caught.value)["reason"] == "byte_limit"
    assert response.offset == cap + 1 and response.read_sizes == [cap + 1]


@pytest.mark.parametrize("decoded_size", [513, 1_900_001])
def test_gzip_expansion_is_bounded_independently(monkeypatch, response_factory, decoded_size):
    monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", 512)
    body = gzip.compress(b" " * decoded_size)
    # The larger bomb still has to pass the wire cap to test the output cap.
    if len(body) > 512:
        monkeypatch.setattr(module, "MAX_SNAPSHOT_BYTES", 1_900_000)
    response_factory(body, ("gzip",))
    with pytest.raises(module.CaptureQuotaExceeded) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "byte_limit"


@pytest.mark.parametrize("fault", ["empty", "invalid", "truncated", "crc", "trailing", "members"])
@pytest.mark.parametrize("via_worker", [False, True])
def test_invalid_gzip_framing_never_returns_payload(response_factory, fault, via_worker):
    body = gzip.compress(_body(), mtime=0)
    if fault == "empty":
        body = b""
    elif fault == "invalid":
        body = SECRET.encode()
    elif fault == "truncated":
        body = body[:-1]
    elif fault == "crc":
        body = body[:-8] + bytes([body[-8] ^ 1]) + body[-7:]
    elif fault == "trailing":
        body += b"extra"
    else:
        body += gzip.compress(b"", mtime=0)
    response_factory(body, ("gzip",))
    with pytest.raises(ValueError) as caught:
        if via_worker:
            asyncio.run(module._snapshot_with_failure_code())
        else:
            module.fetch_snapshot()
    assert failure_details(caught.value)["reason"] == "invalid_response"
    assert SECRET not in str(caught.value)


@pytest.mark.parametrize("body", [b"not json", b"[]", b"{}", b'{"x":1,"x":2}', b'{"x":NaN}'])
def test_decoded_body_still_requires_strict_json_and_snapshot(response_factory, body):
    response_factory(gzip.compress(body), ("gzip",))
    with pytest.raises((ValueError, KeyError)) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "invalid_response"


@pytest.mark.parametrize("late_at", [10.0, 11.0])
def test_late_decompression_is_rejected(monkeypatch, response_factory, late_at):
    clock = [0.0]
    response_factory(gzip.compress(_body()), ("gzip",))
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    original = module.zlib.decompressobj
    calls = []

    class Decoder:
        def __init__(self, bits):
            assert bits == 31
            self.decoder = original(bits)

        def decompress(self, body, max_length):
            assert max_length == module.MAX_SNAPSHOT_BYTES + 1
            calls.append(True)
            result = self.decoder.decompress(body, max_length)
            clock[0] = late_at
            return result

        def __getattr__(self, name):
            return getattr(self.decoder, name)

    monkeypatch.setattr(module.zlib, "decompressobj", Decoder)
    with pytest.raises(module.SnapshotTimeout) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "deadline"
    assert calls == [True]


def test_decoder_message_is_sanitized_across_worker(monkeypatch, response_factory):
    response_factory(gzip.compress(_body()), ("gzip",))

    class Decoder:
        def decompress(self, body, max_length):
            raise module.zlib.error(SECRET)

    monkeypatch.setattr(module.zlib, "decompressobj", lambda bits: Decoder())
    with pytest.raises(ValueError) as caught:
        asyncio.run(module._snapshot_with_failure_code())
    assert failure_details(caught.value)["reason"] == "invalid_response"
    assert SECRET not in str(caught.value)
