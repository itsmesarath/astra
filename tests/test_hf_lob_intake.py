"""Synthetic public-intake tests; no market downloads or training."""

import copy
import hashlib
import io
import json
import socket
import ssl
from pathlib import Path

import pytest

from ai_trader.ingestion import hf_lob_intake as module


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Test attempted network access.")

    monkeypatch.setattr(socket, "create_connection", forbidden)


def plan():
    value = json.loads(Path("configs/hf_btcusdt_lob_pilot_v1.json").read_text())
    value["month"] = "2020-01"
    for spec in value["files"]:
        spec.update(
            path=f"{spec['kind']}/binance/BTCUSDT/2020-01.parquet",
            size=3,
            sha256=hashlib.sha256(b"abc").hexdigest(),
        )
    return value


def save_plan(tmp_path, value=None):
    path = tmp_path / "request.json"
    path.write_bytes(module._canonical(plan() if value is None else value))
    return path


class Response(io.BytesIO):
    status = 200

    def __init__(self, content=b"abc", *, headers=None, url="https://huggingface.co/file"):
        super().__init__(content)
        self.headers = headers or {}
        self.url = url

    def geturl(self):
        return self.url


def test_pinned_production_plan():
    value = module.load_plan("configs/hf_btcusdt_lob_pilot_v1.json")
    assert sum(spec["size"] for spec in value["files"]) == 446107380
    assert value["maximum_total_bytes"] == 512 * 1024 * 1024


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("dataset", "someone/else"),
        ("market", "futures"),
        ("symbol", "ETHUSDT"),
        ("revision", "main"),
        ("revision", "a" * 39),
        ("month", "2026-13"),
        ("month", "2099-01"),
        ("maximum_total_bytes", True),
        ("maximum_total_bytes", 8),
        ("maximum_total_bytes", module.MAX_TOTAL_BYTES + 1),
        ("training_started", True),
        ("promotion_allowed", True),
        ("live_trading_available", True),
        ("known_limitations", []),
        ("files", []),
    ],
)
def test_invalid_plan(key, value):
    request = plan()
    request[key] = value
    with pytest.raises(ValueError):
        module.validate_plan(request)


@pytest.mark.parametrize(
    "key,value",
    [
        ("path", "../../escape"),
        ("kind", "depth"),
        ("size", True),
        ("size", -1),
        ("sha256", "a" * 63),
        ("sha256", 12),
    ],
)
def test_invalid_file(key, value):
    request = plan()
    request["files"][0][key] = value
    with pytest.raises(ValueError):
        module.validate_plan(request)


def test_duplicate_or_oversized_metadata(tmp_path):
    path = tmp_path / "bad.json"
    for raw in (b'{"x":1,"x":2}', b" " * (module.MAX_PLAN_BYTES + 1)):
        path.write_bytes(raw)
        with pytest.raises(ValueError):
            module.load_plan(path)


def test_explicit_opt_in_before_read_or_write(tmp_path):
    with pytest.raises(ValueError, match="opt-in"):
        module.download_pilot(tmp_path / "missing", tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_download_verified_and_never_overwrites(tmp_path):
    request = save_plan(tmp_path)
    directory = tmp_path / "download"
    calls = []

    def opener(req, timeout):
        calls.append(req.full_url)
        assert timeout == 30
        assert req.get_header("Authorization") is None
        return Response()

    result = module.download_pilot(request, directory, enable_download=True, opener=opener)
    assert result["status"] == "download_verified"
    assert result["training_started"] is False
    assert len(calls) == 6
    assert all(plan()["revision"] in url for url in calls[::2])
    assert all(url.endswith("?download=true") for url in calls[::2])
    assert not list(directory.glob("*.partial"))
    with pytest.raises(FileExistsError):
        module.download_pilot(request, directory, enable_download=True, opener=opener)
    assert len(calls) == 6
    assert (directory / "snapshots.parquet").read_bytes() == b"abc"


@pytest.mark.parametrize(
    "response",
    [
        lambda: Response(b"bad"),
        lambda: Response(b"ab"),
        lambda: Response(b"abcd"),
        lambda: Response(headers={"Content-Length": "4"}),
        lambda: Response(headers={"Content-Encoding": "gzip"}),
        lambda: Response(url="http://huggingface.co/file"),
    ],
)
def test_failed_transfer_quarantines_without_retry(tmp_path, response):
    directory = tmp_path / "download"
    calls = []

    def opener(*args, **kwargs):
        calls.append(1)
        return response()

    with pytest.raises(ValueError):
        module.download_pilot(save_plan(tmp_path), directory, enable_download=True, opener=opener)
    assert len(calls) in (1, 2)  # A single HEAD followed by at most one GET; no retries.
    assert not (directory / "snapshots.parquet").exists()
    assert not (directory / "download_receipt.json").exists()
    failure = json.loads((directory / "failure.json").read_text())
    assert failure["training_started"] is False
    assert failure["retry_performed"] is False


def test_deadline_checked_after_eof(tmp_path, monkeypatch):
    ticks = iter([0, 0, 0, 0, 0, 300])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    with pytest.raises(TimeoutError):
        module._download_file(plan(), plan()["files"][0], tmp_path, lambda *a, **k: Response())
    assert not (tmp_path / "snapshots.parquet").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://huggingface.co/file",
        "https://huggingface.co.attacker.example/file",
        "https://localhost/file",
        "https://user:password@huggingface.co/file",
        "https://huggingface.co:8443/file",
        "file:///local/file",
    ],
)
def test_redirect_scope(url):
    with pytest.raises(ValueError):
        module._check_url(url)


def test_public_cdn_allowed():
    module._check_url("https://cas-bridge.xethub.hf.co/file?public-signed-download=1")


def test_ipv4_connector_is_local_and_single_attempt(monkeypatch):
    calls = []

    def lookup(host, port, *, family, type):
        assert host == "huggingface.co" and port == 443
        assert family == socket.AF_INET and type == socket.SOCK_STREAM
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 443))]

    def connect(address, timeout, source):
        calls.append((address, timeout, source))
        return "synthetic_socket"

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(socket, "create_connection", connect)
    assert module._ipv4_connect(("huggingface.co", 443), 30, None) == "synthetic_socket"
    assert calls == [(("192.0.2.1", 443), 30, None)]
    assert socket.create_connection is connect


def test_ipv4_connection_keeps_tls_hostname_verification():
    connection = module._IPv4HTTPSConnection("huggingface.co", timeout=30)
    assert connection.host == "huggingface.co"
    assert connection._create_connection is module._ipv4_connect
    assert connection._context.verify_mode == ssl.CERT_REQUIRED
    assert connection._context.check_hostname is True


def test_ipv4_empty_dns_fails_without_other_address_family(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [])
    with pytest.raises(OSError, match="No IPv4"):
        module._ipv4_connect(("huggingface.co", 443), 30, None)


def test_ipv4_selection_is_recorded(tmp_path):
    result = module.download_pilot(
        save_plan(tmp_path),
        tmp_path / "download",
        enable_download=True,
        ipv4=True,
        opener=lambda *a, **k: Response(),
    )
    assert result["ipv4_only"] is True


def make_archives(tmp_path):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    request = copy.deepcopy(plan())
    directory = tmp_path / "archives"
    directory.mkdir()
    for spec in request["files"]:
        path = directory / f"{spec['kind']}.parquet"
        table = pa.table({"timestamp_ms": [1, 2], "price": [1.0, 2.0], "quantity": [1.0, 1.0]})
        pq.write_table(table, path)
        raw = path.read_bytes()
        spec.update(size=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (directory / "plan.json").write_bytes(module._canonical(request))
    return request, directory


def test_schema_audit_blocks_incomplete_data_without_values(tmp_path, monkeypatch):
    request, directory = make_archives(tmp_path)
    import pyarrow.parquet as pq

    def forbidden(*args, **kwargs):
        pytest.fail("Metadata audit attempted to read market value rows.")

    for name in ("read", "read_row_group", "read_row_groups", "iter_batches"):
        monkeypatch.setattr(pq.ParquetFile, name, forbidden)
    output = tmp_path / "audit.json"
    report = module.audit_pilot(save_plan(tmp_path, request), directory, output)
    assert report["status"] == "blocked_training_intake"
    assert report["training_started"] is False
    assert report["labels_generated"] == report["epochs_completed"] == 0
    assert report["sequence_continuity_verified"] is False
    assert all(item["market_value_rows_read"] == 0 for item in report["files"])
    assert all(item["missing_reconstruction_columns"] for item in report["files"])
    assert len(report["blockers"]) == 8
    assert report["files"][0]["footer_timestamp_statistics_unverified"]["timestamp_ms"] == {
        "null_count": 0,
        "min": "1",
        "max": "2",
    }
    with pytest.raises(FileExistsError):
        module.audit_pilot(save_plan(tmp_path, request), directory, output)


def test_local_archive_corruption_blocks_report(tmp_path):
    request, directory = make_archives(tmp_path)
    (directory / "snapshots.parquet").write_bytes(b"bad")
    output = tmp_path / "audit.json"
    with pytest.raises(ValueError, match="pinned size"):
        module.audit_pilot(save_plan(tmp_path, request), directory, output)
    assert not output.exists()


def test_changed_plan_blocks_before_parquet_access(tmp_path):
    request, directory = make_archives(tmp_path)
    request["revision"] = "0" * 40
    with pytest.raises(ValueError, match="differs"):
        module.audit_pilot(save_plan(tmp_path, request), directory, tmp_path / "audit.json")


def test_publish_does_not_replace_existing_result(tmp_path):
    path = tmp_path / "report.json"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        module._publish(path, {"new": True})
    assert path.read_bytes() == b"original"
