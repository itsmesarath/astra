"""Explicit, bounded public LOB intake; data only, never a training authorization.

This intentionally does not impersonate our native receipt-causal capture format.
Parquet metadata inspection cannot establish sequence continuity or data quality.
"""

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DATASET = "Goooddy/crypto-lob-stream"
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_PLAN_BYTES = 32 * 1024
MAX_SECONDS_PER_FILE = 300
KINDS = ("snapshots", "trades", "depth")
REQUIRED_COLUMNS = {
    "snapshots": {"timestamp_ms", "side", "price", "quantity", "last_update_id"},
    "trades": {"timestamp_ms", "price", "quantity", "trade_id", "buyer_maker"},
    "depth": {"timestamp_ms", "side", "price", "quantity", "first_update_id", "last_update_id"},
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata key.")
        result[key] = value
    return result


def validate_plan(plan):
    """Accept only the documented spot pilot, with pinned raw-file SHA256 identities."""
    fixed = {
        "schema_version": 1,
        "dataset": DATASET,
        "exchange": "binance",
        "market": "spot",
        "symbol": "BTCUSDT",
        "purpose": "research_intake_only",
        "training_started": False,
        "promotion_allowed": False,
        "live_trading_available": False,
    }
    if type(plan) is not dict or set(plan) != set(fixed) | {
        "revision",
        "month",
        "maximum_total_bytes",
        "files",
        "known_limitations",
    }:
        raise ValueError("Invalid intake plan fields.")
    if any(type(plan[k]) is not type(v) or plan[k] != v for k, v in fixed.items()):
        raise ValueError("Only the research-only BTCUSDT spot dataset is supported.")
    if not isinstance(plan["revision"], str) or not re.fullmatch(r"[0-9a-f]{40}", plan["revision"]):
        raise ValueError("An immutable 40-character revision is required.")
    month = plan["month"]
    if not isinstance(month, str) or not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", month):
        raise ValueError("Invalid calendar month.")
    if month >= datetime.now(UTC).strftime("%Y-%m"):
        raise ValueError("Use a completed historical month.")
    budget = plan["maximum_total_bytes"]
    if type(budget) is not int or not 1 <= budget <= MAX_TOTAL_BYTES:
        raise ValueError("Invalid download byte budget.")
    if (
        type(plan["known_limitations"]) is not list
        or not plan["known_limitations"]
        or any(
            type(item) is not str or not 1 <= len(item) <= 1024
            for item in plan["known_limitations"]
        )
    ):
        raise ValueError("Explicit source limitations are required.")
    files = plan["files"]
    if type(files) is not list or len(files) != len(KINDS):
        raise ValueError("Exactly one snapshot, trade and depth file is required.")
    total = 0
    for kind, spec in zip(KINDS, files, strict=True):
        if type(spec) is not dict or set(spec) != {"kind", "path", "size", "sha256"}:
            raise ValueError("Invalid file specification.")
        if spec["kind"] != kind or spec["path"] != f"{kind}/binance/BTCUSDT/{month}.parquet":
            raise ValueError("Unexpected, reordered or unsafe source path.")
        if type(spec["size"]) is not int or not 1 <= spec["size"] <= budget:
            raise ValueError("Invalid pinned file size.")
        if not isinstance(spec["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", spec["sha256"]):
            raise ValueError("An explicit raw-file SHA256 pin is required.")
        total += spec["size"]
    if total > budget:
        raise ValueError("Combined files exceed the download budget.")
    return plan


def load_plan(path):
    with Path(path).open("rb") as source:
        raw = source.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("Plan exceeds metadata budget.")
    return validate_plan(json.loads(raw, object_pairs_hook=_no_duplicates))


def _publish(path, value):
    """No-replacement publication; failed partials remain available for diagnosis."""
    partial = path.with_name(path.name + ".partial")
    if path.exists():
        raise FileExistsError(path)
    with partial.open("xb") as output:
        output.write(_canonical(value))
        output.flush()
        os.fsync(output.fileno())
    os.link(partial, path)
    partial.unlink()


def _check_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or not (host == "huggingface.co" or host.endswith((".huggingface.co", ".hf.co")))
    ):
        raise ValueError("Refused redirect outside public Hugging Face HTTPS hosts.")


class _PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(request, fp, code, msg, headers, newurl)


def _ipv4_connect(address, timeout, source_address):
    # Client-local address-family selection. Do not monkeypatch global socket state.
    host, port = address
    candidates = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
    if not candidates:
        raise OSError("No IPv4 address available.")
    # One address/connection attempt, not an implicit failover or retry loop.
    return socket.create_connection(candidates[0][4], timeout, source_address)


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._create_connection = _ipv4_connect
        # HTTPSConnection.connect still wraps TLS using the original hostname,
        # including normal certificate/hostname verification and SNI.


class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, request):
        return self.do_open(_IPv4HTTPSConnection, request, context=self._context)


def _download_file(plan, spec, directory, opener):
    url = (
        f"https://huggingface.co/datasets/{DATASET}/resolve/"
        f"{plan['revision']}/{spec['path']}?download=true"
    )
    _check_url(url)
    destination = directory / f"{spec['kind']}.parquet"
    partial = destination.with_suffix(".parquet.partial")
    if destination.exists():
        raise FileExistsError(destination)
    digest = hashlib.sha256()
    count = 0
    started = time.monotonic()
    headers = {"Accept-Encoding": "identity", "User-Agent": "ai-trader-research-intake/1"}
    # Resolve via the publisher's HEAD route, then GET the returned public CDN URL.
    # Some networks reset resolve-route GETs while HEAD and the CDN remain available.
    # This is not a mirror, an HTTP/TLS downgrade or a credentialed request.
    with opener(
        urllib.request.Request(url, method="HEAD", headers=headers), timeout=30
    ) as response:
        resolved = response.geturl()
        _check_url(resolved)
        if response.status != 200:
            raise ValueError("Expected a complete HTTP 200 metadata response.")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) != spec["size"]:
            raise ValueError("Resolved file size differs from pinned size.")
    if time.monotonic() - started >= MAX_SECONDS_PER_FILE:
        raise TimeoutError("Archive resolution exceeded its elapsed-time budget.")
    request = urllib.request.Request(resolved, headers=headers)
    with partial.open("xb") as output, opener(request, timeout=30) as response:
        _check_url(response.geturl())
        if response.status != 200:
            raise ValueError("Expected a complete HTTP 200 response.")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Unexpected encoded archive response.")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) != spec["size"]:
            raise ValueError("Response length differs from pinned size.")
        while True:
            if time.monotonic() - started >= MAX_SECONDS_PER_FILE:
                raise TimeoutError("Archive transfer exceeded its elapsed-time budget.")
            chunk = response.read(min(1024 * 1024, spec["size"] - count + 1))
            if time.monotonic() - started >= MAX_SECONDS_PER_FILE:
                raise TimeoutError("Archive transfer exceeded its elapsed-time budget.")
            if not chunk:
                break
            count += len(chunk)
            if count > spec["size"]:
                raise ValueError("Archive exceeds pinned byte limit.")
            digest.update(chunk)
            output.write(chunk)
        if count != spec["size"] or digest.hexdigest() != spec["sha256"]:
            raise ValueError("Archive size or SHA256 verification failed.")
        output.flush()
        os.fsync(output.fileno())
    os.link(partial, destination)
    partial.unlink()
    return {"kind": spec["kind"], "bytes": count, "sha256": digest.hexdigest()}


def download_pilot(plan_path, directory, *, enable_download=False, ipv4=False, opener=None):
    if enable_download is not True:
        raise ValueError("Explicit download opt-in is required.")
    if type(ipv4) is not bool:
        raise ValueError("IPv4 selection must be an explicit boolean.")
    plan = load_plan(plan_path)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    _publish(directory / "plan.json", plan)
    handlers = [_PublicRedirect()]
    if ipv4:
        handlers.append(_IPv4HTTPSHandler())
    opener = opener or urllib.request.build_opener(*handlers).open
    results = []
    try:
        for spec in plan["files"]:
            print(
                json.dumps({"downloading": spec["kind"], "expected_bytes": spec["size"]}),
                flush=True,
            )
            results.append(_download_file(plan, spec, directory, opener))
            print(json.dumps({"verified": results[-1]}), flush=True)
    except Exception as error:
        _publish(
            directory / "failure.json",
            {
                "status": "download_failed",
                "error_type": type(error).__name__,
                "verified_files": results,
                "training_started": False,
                "partial_files_quarantined": True,
                "retry_performed": False,
                "ipv4_only": ipv4,
            },
        )
        raise
    receipt = {
        "schema_version": 1,
        "status": "download_verified",
        "plan_sha256": hashlib.sha256(_canonical(plan)).hexdigest(),
        "files": results,
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "transport": "https_public_head_resolution_then_get_no_retries",
        "ipv4_only": ipv4,
        "training_started": False,
        "promotion_allowed": False,
        "live_trading_available": False,
    }
    _publish(directory / "download_receipt.json", receipt)
    return receipt


def _verify_file(source, spec):
    if os.fstat(source.fileno()).st_size != spec["size"]:
        raise ValueError("Local archive differs from pinned size.")
    source.seek(0)
    digest = hashlib.sha256()
    remaining = spec["size"]
    while remaining:
        chunk = source.read(min(1024 * 1024, remaining))
        if not chunk:
            raise ValueError("Local archive was truncated.")
        digest.update(chunk)
        remaining -= len(chunk)
    if source.read(1) or digest.hexdigest() != spec["sha256"]:
        raise ValueError("Local archive differs from its pinned SHA256.")
    source.seek(0)


def inspect_archive(path, spec):
    """Footer/schema only: no prices, trade values, labels or model inputs are loaded."""
    import pyarrow.parquet as pq  # Optional, pinned 'historical' dependency; no dataset code.

    with Path(path).open("rb") as source:
        _verify_file(source, spec)
        parquet = pq.ParquetFile(
            source,
            pre_buffer=False,
            thrift_string_size_limit=1_000_000,
            thrift_container_size_limit=100_000,
        )
        metadata = parquet.metadata
        if metadata.num_columns > 64 or metadata.num_row_groups > 10_000:
            raise ValueError("Parquet metadata exceeds the inspection budget.")
        schema = {field.name: str(field.type) for field in parquet.schema_arrow}
        if len(schema) != metadata.num_columns:
            raise ValueError("Nested or duplicate Parquet columns are unsupported.")
        missing = sorted(REQUIRED_COLUMNS[spec["kind"]] - schema.keys())
        time_fields = sorted({"timestamp_ms", "exchange_ts"} & schema.keys())
        stats = {}
        for field in time_fields:
            column_index = parquet.schema_arrow.get_field_index(field)
            groups = [
                metadata.row_group(index).column(column_index).statistics
                for index in range(metadata.num_row_groups)
            ]
            # Footer statistics are publisher-provided hints, not independently audited rows.
            stats[field] = {
                "null_count": sum(g.null_count for g in groups)
                if groups and all(g is not None and g.has_null_count for g in groups)
                else None,
                "min": str(min(g.min for g in groups))
                if groups and all(g is not None and g.has_min_max for g in groups)
                else None,
                "max": str(max(g.max for g in groups))
                if groups and all(g is not None and g.has_min_max for g in groups)
                else None,
            }
        result = {
            "kind": spec["kind"],
            "sha256": spec["sha256"],
            "bytes": spec["size"],
            "footer_rows": metadata.num_rows,
            "row_groups": metadata.num_row_groups,
            "schema": schema,
            "missing_reconstruction_columns": missing,
            "footer_timestamp_statistics_unverified": stats,
            "has_separate_exchange_timestamp_column": "exchange_ts" in schema,
            "market_value_rows_read": 0,
        }
        _verify_file(source, spec)
    return result


def audit_pilot(plan_path, directory, output_path):
    plan = load_plan(plan_path)
    # Compare with the plan frozen before transfer, not a subsequently edited request.
    if _canonical(load_plan(Path(directory) / "plan.json")) != _canonical(plan):
        raise ValueError("Intake plan differs from the downloaded campaign.")
    output_path = Path(output_path)
    if output_path.exists() or output_path.with_name(output_path.name + ".partial").exists():
        raise FileExistsError(output_path)
    results = [
        inspect_archive(Path(directory) / f"{spec['kind']}.parquet", spec) for spec in plan["files"]
    ]
    blockers = []
    for item in results:
        if item["missing_reconstruction_columns"]:
            blockers.append(f"{item['kind']}: missing reconstruction columns")
        if (
            item["kind"] in {"depth", "trades"}
            and not item["has_separate_exchange_timestamp_column"]
        ):
            blockers.append(
                f"{item['kind']}: exchange/receipt times are not separately represented"
            )
    blockers.extend(
        [
            "Snapshot request/receipt availability and cross-stream arrival order are unverified.",
            "No source-qualified native capture adapter or full sequence/gap audit exists.",
            "No costed labels, predeclared session split or training recipe exist for these files.",
        ]
    )
    report = {
        "schema_version": 1,
        "status": "blocked_training_intake",
        "inspection_scope": "checksummed_parquet_schema_and_footer_only",
        "dataset": DATASET,
        "revision": plan["revision"],
        "plan_sha256": hashlib.sha256(_canonical(plan)).hexdigest(),
        "files": results,
        "blockers": blockers,
        "known_limitations": plan["known_limitations"],
        "source_quality_verified": False,
        "sequence_continuity_verified": False,
        "training_started": False,
        "epochs_completed": 0,
        "labels_generated": 0,
        "promotion_allowed": False,
        "live_trading_available": False,
    }
    _publish(output_path, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("download", "audit"))
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--enable-download", action="store_true")
    parser.add_argument("--ipv4", action="store_true", help="Client only; no OS network changes.")
    args = parser.parse_args()
    if args.command == "download":
        result = download_pilot(
            args.plan, args.directory, enable_download=args.enable_download, ipv4=args.ipv4
        )
    else:
        if args.report is None:
            parser.error("audit requires --report")
        result = audit_pilot(args.plan, args.directory, args.report)
    print(json.dumps({"status": result["status"], "training_started": False}), flush=True)
    if result["status"] == "blocked_training_intake":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
