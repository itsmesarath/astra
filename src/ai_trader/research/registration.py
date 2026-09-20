"""Write-once registration for the fixed pullback study, before candle loading.

This is a local reproducibility record, not trusted timestamping or tamper-proof
preregistration. Archive hashes are declarations until verified by the loader.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
from datetime import UTC, date, datetime
from importlib.metadata import version
from pathlib import Path


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def implementation_fingerprint() -> dict[str, str]:
    """Hash the entire installed project source tree, not credentials or datasets."""
    root = Path(__file__).resolve().parents[1]
    return {
        str(p.relative_to(root)).replace("\\", "/"): _digest(p.read_bytes())
        for p in sorted(root.rglob("*.py"))
    }


def environment_fingerprint() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        **{package: version(package) for package in ("numpy", "torch", "websockets")},
    }


def _sessions(names: tuple[str, ...]) -> None:
    if not names or any(not isinstance(name, str) for name in names):
        raise ValueError("Session lists must contain names.")
    if tuple(sorted(set(names))) != names:
        raise ValueError("Session lists must be unique and chronological.")
    for name in names:
        if not re.fullmatch(r"binance_spot_BTCUSDT_\d{4}-\d{2}-\d{2}", name):
            raise ValueError("Expected canonical BTCUSDT session names.")
        date.fromisoformat(name[-10:])


def register_pullback(
    manifest_path: Path,
    output_path: Path,
    *,
    trial_id: str,
    research_sessions: tuple[str, ...],
    reserved_sessions: tuple[str, ...],
) -> dict:
    """Read manifest metadata only; never open normalized candle archives."""
    if output_path.exists():
        raise FileExistsError(output_path)
    if not isinstance(trial_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", trial_id):
        raise ValueError("Trial ID must be 1-80 letters, digits, underscores or hyphens.")
    _sessions(research_sessions)
    _sessions(reserved_sessions)
    if research_sessions[-1] >= reserved_sessions[0]:
        raise ValueError("Reserved sessions must follow all research sessions without overlap.")
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != expected
        for key, expected in (
            ("source", "binance_public_data"),
            ("market", "spot"),
            ("data_type", "klines"),
            ("symbol", "BTCUSDT"),
            ("interval", "5m"),
        )
    ):
        raise ValueError("Expected a BTCUSDT five-minute public Spot manifest.")
    archives = manifest.get("archives")
    if not isinstance(archives, list) or not archives:
        raise ValueError("Manifest must contain archive metadata.")
    inventory = {}
    for archive in archives:
        if not isinstance(archive, dict):
            raise ValueError("Invalid archive metadata.")
        day = archive.get("date")
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("Invalid archive date.")
        name = f"binance_spot_BTCUSDT_{day}"
        if name in inventory:
            raise ValueError("Duplicate archive session.")
        inventory[name] = archive
    if not set(research_sessions + reserved_sessions) <= inventory.keys():
        raise ValueError("Manifest is missing declared sessions.")
    selected = []
    for name in research_sessions:
        archive = inventory[name]
        checksum = archive.get("normalized_sha256")
        if not isinstance(checksum, str) or not re.fullmatch("[a-f0-9]{64}", checksum):
            raise ValueError("Research archives require SHA-256 declarations.")
        if not isinstance(archive.get("normalized_path"), str) or not archive["normalized_path"]:
            raise ValueError("Research archives require normalized paths.")
        selected.append({"session": name, "declared_sha256": checksum})
    payload = {
        "schema_version": 1,
        "trial_id": trial_id,
        "registered_at_utc": datetime.now(UTC).isoformat(),
        "study": "fixed_trend_pullback_v1",
        "execution_mode": "paper",
        "status": "registered_not_evaluated",
        "promotion_allowed": False,
        "manifest_path": str(manifest_path.resolve()),
        "manifest_sha256": _digest(raw),
        "research_sessions": list(research_sessions),
        "reserved_sessions": list(reserved_sessions),
        "excluded_sessions": sorted(set(inventory) - set(research_sessions)),
        "research_archive_declarations": selected,
        "implementation_sha256": implementation_fingerprint(),
        "environment": environment_fingerprint(),
        "protocol": {
            "decimal_precision": 28,
            "decimal_rounding": "ROUND_HALF_EVEN",
            "ema_periods": [20, 60],
            "slow_slope_bars": 6,
            "atr_period": 14,
            "indicator_policy": "session_reset_sma_ema_seed_wilder_atr_first_previous_close",
            "signal_policy": "upward_ema20_cross_fast_above_rising_slow",
            "stop_atr": 1,
            "target_atr": 2,
            "holding_bars": 24,
            "screen_reference_round_trip_bps": 24,
            "screen_cost_multiple": 3,
            "screen_price": "signal_close",
            "starting_balance": 10000,
            "position_fraction": "0.1",
            "full_session_horizon_required": True,
            "round_trip_cost_scenarios_bps": [24, 36, 48],
            "per_side_fee_bps": 10,
            "per_side_slippage_scenarios_bps": [2, 8, 14],
            "entry_delays_bars": [0, 1],
            "scenario_selection": "none_report_all",
            "fitting": "none_rule_only",
        },
        "limitations": [
            "local_record_not_trusted_timestamp",
            "archive_bytes_not_yet_verified",
            "reserved_metadata_visible",
            "not_physical_lockbox_isolation",
            "controls_and_uncertainty_not_implemented",
            "no_promotion_decision",
        ],
    }
    envelope = {"registration_sha256": _digest(_canonical(payload)), "registration": payload}
    if manifest_path.read_bytes() != raw:
        raise ValueError("Manifest changed during registration.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        json.dump(envelope, output, indent=2, allow_nan=False)
        output.write("\n")
    return envelope


def verify_registration(path: Path) -> dict:
    """Fail on changed registration, manifest, source code or package versions.

    Does not load candles, attest authorship, or prove this record predates a trial.
    """
    envelope = json.loads(path.read_bytes())
    if not isinstance(envelope, dict) or set(envelope) != {"registration", "registration_sha256"}:
        raise ValueError("Invalid registration envelope.")
    payload = envelope["registration"]
    if (
        not isinstance(payload, dict)
        or _digest(_canonical(payload)) != envelope["registration_sha256"]
    ):
        raise ValueError("Registration checksum mismatch.")
    if (
        payload.get("schema_version") != 1
        or payload.get("study") != "fixed_trend_pullback_v1"
        or payload.get("execution_mode") != "paper"
        or payload.get("promotion_allowed") is not False
    ):
        raise ValueError("Unsupported research registration.")
    if implementation_fingerprint() != payload["implementation_sha256"]:
        raise ValueError("Project source changed after registration.")
    if environment_fingerprint() != payload["environment"]:
        raise ValueError("Environment changed after registration.")
    if _digest(Path(payload["manifest_path"]).read_bytes()) != payload["manifest_sha256"]:
        raise ValueError("Source manifest changed after registration.")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--research-sessions", nargs="+", required=True)
    parser.add_argument("--reserved-sessions", nargs="+", required=True)
    args = parser.parse_args()
    result = register_pullback(
        args.manifest,
        args.output,
        trial_id=args.trial_id,
        research_sessions=tuple(args.research_sessions),
        reserved_sessions=tuple(args.reserved_sessions),
    )
    print(f"Registered only; no candle data loaded: {result['registration_sha256']}")


if __name__ == "__main__":
    main()
