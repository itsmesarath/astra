"""One separately registered offline first-prefix 6E account experiment.

No raw archive replay, target readers, model calls, automatic resume or trades.
Completion requires all registered inputs and independent ledger reconstruction.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from ai_trader.research import six_e_continuous_inputs as reader
from ai_trader.research import six_e_continuous_replay as replay

status, ledger = reader.status, replay.ledger
SCOPE = (
    "Exact first accepted train-session prefix, exposed development; "
    "no profitable-subset selection or independent validation"
)


def fingerprints() -> dict:
    return {
        **replay.fingerprints(),
        **reader.obs.fingerprints(),
        **{
            Path(m.__file__).name: reader.study.common.hash_file(Path(m.__file__), 1024**2)
            for m in (reader,)
        },
        Path(__file__).name: reader.study.common.hash_file(Path(__file__), 1024**2),
    }


def prepare(
    root: Path,
    original_path: Path,
    original_pin: str,
    days: tuple[str, ...],
    policy: str,
    exit_plan: str,
    scenario_id: str,
    path: Path,
    output: Path,
) -> dict:
    """Freeze one explicit cohort prefix and input content BEFORE simulating outcomes."""
    path = status._inside(root, path, "logs")
    output = status._inside(root, output, "data/processed")
    original_path = status._inside(root, original_path, "logs")
    if path.suffix != ".json" or path.exists() or output.exists():
        raise ValueError("Exclusive new JSON registration and separate new output required")
    # Reject invalid choices before loading any price/feature contents.
    if policy not in replay.POLICIES or exit_plan not in replay.target.PLANS:
        raise ValueError("A fixed causal policy and original exit plan required")
    ledger._identifier(scenario_id)
    original, frozen, _ = reader.metadata(root, original_path, original_pin)
    if output.is_relative_to(Path(original["inputs"]["build"]).resolve()):
        raise ValueError("Trial cannot write inside the original collection")
    pins = fingerprints()
    inputs = reader.load_sessions(root, original_path, original_pin, days)
    manifest = replay.input_manifest(inputs)
    config = ledger.ScenarioConfig(
        scenario_id, policy, exit_plan, replay.manifest_pin(inputs), replay.protocol()["version"]
    )
    if fingerprints() != pins:
        raise ValueError("Trial source changed while registering complete inputs")
    value = {
        "protocol": replay.protocol(),
        "source_pins": pins,
        "original_registration": {"path": str(original_path), "sha256": original_pin},
        "days": days,
        "manifest": manifest,
        "config": asdict(config),
        "original_coverage": frozen["coverage"],
        "output": str(output),
        "scope": SCOPE,
        "flags": replay._flags(),
    }
    replay._write(path, replay._json(value))
    return value


def registration(root: Path, path: Path, pin: str) -> tuple[dict, tuple, ledger.ScenarioConfig]:
    path = status._inside(root, path, "logs")
    raw = replay._read(path, pin)
    value = status._decode(raw)
    if path.suffix != ".json":
        raise ValueError("Trial requires its original JSON registration")
    if (
        set(value)
        != {
            "protocol",
            "source_pins",
            "original_registration",
            "days",
            "manifest",
            "config",
            "original_coverage",
            "output",
            "scope",
            "flags",
        }
        or replay._json(value["protocol"]) != replay._json(replay.protocol())
        or value["source_pins"] != fingerprints()
        or replay._json(value["flags"]) != replay._json(replay._flags())
        or value["scope"] != SCOPE
    ):
        raise ValueError("Trial registration schema, source, protocol or authority changed")
    origin = value["original_registration"]
    if type(origin) is not dict or set(origin) != {"path", "sha256"}:
        raise ValueError("Exact original registration identity required")
    original_path = status._inside(root, Path(origin["path"]), "logs")
    original, frozen, _ = reader.metadata(root, original_path, origin["sha256"])
    output = status._inside(root, Path(value["output"]), "data/processed")
    if (
        str(output) != value["output"]
        or output.is_relative_to(Path(original["inputs"]["build"]).resolve())
        or replay._json(value["original_coverage"]) != replay._json(frozen["coverage"])
    ):
        raise ValueError("Trial original coverage or exclusive output scope changed")
    inputs = reader.load_sessions(root, original_path, origin["sha256"], tuple(value["days"]))
    config = ledger.ScenarioConfig(**value["config"])
    if (
        replay._json(value["manifest"]) != replay._json(replay.input_manifest(inputs))
        or config.source_manifest_sha256 != replay.manifest_pin(inputs)
        or config.simulator_version != replay.protocol()["version"]
        or config.policy_id not in replay.POLICIES
        or config.max_position_contracts != 1
        or config.extra_round_trip_ticks_per_contract != replay.target.COST
    ):
        raise ValueError("Trial complete inputs or fixed scenario parameters changed")
    return value, inputs, config


def verify(root: Path, path: Path, pin: str, completion_pin: str) -> dict:
    started = time.monotonic()
    value, inputs, config = registration(root, path, pin)
    output = Path(value["output"])
    request_path = status._inside(root, output / "request.json", "data/processed")
    request_pin = reader.study.common.hash_file(request_path, replay.MAX_OUTPUT_BYTES)
    result = replay.verify_plan(inputs, config, output, request_pin, completion_pin)
    if fingerprints() != value["source_pins"]:
        raise ValueError("Trial source changed during terminal verification")
    if time.monotonic() - started > replay.MAX_SECONDS:
        raise TimeoutError("Full historical input/replay verifier deadline exceeded")
    return {**result, "registration_sha256": pin, "original_coverage": value["original_coverage"]}


def run(root: Path, path: Path, pin: str) -> dict:
    started = time.monotonic()
    value, inputs, config = registration(root, path, pin)
    output = Path(value["output"])
    plan = replay.build_plan(inputs, config)
    # No output claim for an incomplete/over-bound input or event plan.
    replay.write_plan(plan, output)
    try:
        completion_path = status._inside(root, output / "completion.json", "data/processed")
        completion_pin = reader.study.common.hash_file(completion_path, replay.MAX_OUTPUT_BYTES)
        result = verify(root, path, pin, completion_pin)
        if time.monotonic() - started > replay.MAX_SECONDS:
            raise TimeoutError("Full registered trial deadline exceeded")
        replay._write(output / "verification.json", replay._json(result))
        return result
    except BaseException as exc:
        if not (output / "failure.json").exists():
            replay._write(
                output / "failure.json",
                replay._json(
                    {
                        "status": "failed_terminal_continuous_trial_verification",
                        "exception_type": type(exc).__name__,
                        "reason": str(exc)[:512],
                        "flags": replay._flags(),
                    }
                ),
            )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--original-registration", type=Path, required=True)
    prep.add_argument("--original-sha256", required=True)
    prep.add_argument("--days", nargs="+", required=True)
    prep.add_argument("--policy", choices=replay.POLICIES, required=True)
    prep.add_argument("--exit-plan", choices=replay.target.PLANS, required=True)
    prep.add_argument("--scenario-id", required=True)
    prep.add_argument("--registration", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    for name in ("run", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--registration", type=Path, required=True)
        p.add_argument("--registration-sha256", required=True)
        if name == "verify":
            p.add_argument("--completion-sha256", required=True)
    args, root = parser.parse_args(), Path.cwd()
    if args.command == "prepare":
        prepare(
            root,
            args.original_registration,
            args.original_sha256,
            tuple(args.days),
            args.policy,
            args.exit_plan,
            args.scenario_id,
            args.registration,
            args.output,
        )
        result = {
            "status": "registered_continuous_trial_not_run",
            "registration_sha256": reader.study.common.hash_file(
                args.registration, replay.MAX_OUTPUT_BYTES
            ),
        }
    elif args.command == "run":
        result = run(root, args.registration, args.registration_sha256)
    else:
        result = verify(root, args.registration, args.registration_sha256, args.completion_sha256)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
