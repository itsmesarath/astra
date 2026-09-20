"""Execute a registered research-only study with reserved archives excluded."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from ai_trader.backtesting.candle_replay import CandleSession, replay_report_payload
from ai_trader.features.kline_dataset import load_verified_sessions
from ai_trader.research.pullback_replay import replay_pullback_scenarios
from ai_trader.research.registration import verify_registration


def run_registered_pullback(registration_path: Path, output_path: Path) -> dict:
    """Verify registration before data access, reserve output before replay.

    Completed and failed artifacts are write-once at the requested path. This does
    not prevent a user from creating another registration/output and rerunning.
    No fitting, winner selection, uncertainty claims, or promotion is performed.
    """
    if output_path.exists():
        raise FileExistsError(output_path)
    registration_bytes = registration_path.read_bytes()
    registered = verify_registration(registration_path)
    selected = tuple(registered["research_sessions"])
    reserved = tuple(registered["reserved_sessions"])
    if not selected or set(selected) & set(reserved):
        raise ValueError("Research sessions must be nonempty and exclude reserved sessions.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as output:
        try:
            symbol, interval, interval_ms, loaded = load_verified_sessions(
                Path(registered["manifest_path"]), selected_sessions=selected
            )
            if (symbol, interval, interval_ms) != ("BTCUSDT", "5m", 300000):
                raise ValueError("Registered study requires BTCUSDT five-minute candles.")
            if tuple(name for name, _ in loaded) != selected:
                raise ValueError("Loaded sessions do not match the registered selection.")
            study = replay_pullback_scenarios(
                tuple(CandleSession(name, tuple(candles)) for name, candles in loaded)
            )
            verify_registration(registration_path)
            if registration_path.read_bytes() != registration_bytes:
                raise ValueError("Registration changed during the study.")
            payload = {
                "schema_version": 1,
                "status": "completed_research_only",
                "promotion_allowed": False,
                "registration_file_sha256": hashlib.sha256(registration_bytes).hexdigest(),
                "registration": registered,
                "signal_evidence": [asdict(result) for result in study.signals],
                "scenarios": [
                    {
                        "round_trip_cost_bps": scenario.round_trip_cost_bps,
                        "entry_delay_bars": scenario.entry_delay_bars,
                        "replay": replay_report_payload(scenario.replay),
                    }
                    for scenario in study.scenarios
                ],
                "limitations": [
                    "controls_and_uncertainty_pending",
                    "not_evidence_of_alpha",
                    "not_physical_lockbox_isolation",
                    "no_promotion_decision",
                ],
            }
            encoded = json.dumps(payload, default=_decimal, indent=2, allow_nan=False)
        except BaseException as error:
            json.dump(
                {
                    "status": "failed",
                    "trial_id": registered["trial_id"],
                    "error_type": type(error).__name__,
                    "promotion_allowed": False,
                },
                output,
            )
            output.flush()
            raise
        output.write(encoded + "\n")
    return json.loads(encoded)


def _decimal(value: object) -> str:
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError("Unsupported research report value.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registration", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run_registered_pullback(args.registration, args.output)
    print(f"{result['status']}: all six scenarios saved; promotion is disabled.")


if __name__ == "__main__":
    main()
