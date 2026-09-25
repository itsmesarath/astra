"""Predeclared policy and bounded delayed paper replay of new public captures.

The policy is frozen before the first capture starts. Completed sessions are
replayed in receipt order into one durable paper journal. This is prospective
paper research with a capture-duration delay, not real-time execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ai_trader.research.microstructure_trial import (
    _decode_gateway,
    _decode_policy,
    _decode_replay,
    _environment,
)
from ai_trader.trading.capture_replay import (
    MAX_BYTES,
    CaptureReplay,
    CaptureReplayConfig,
    _implementation_hash,
)
from ai_trader.trading.durable_paper_gateway import PaperGatewayConfig
from ai_trader.trading.microstructure_paper import _simulate_replays
from ai_trader.trading.microstructure_policy import MicrostructurePolicyConfig
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.trade_case import _digest
from ai_trader.trading.trade_journal import _constant, _decimal, _encode, _hash, _identifier, _pairs

MAX_PLAN_BYTES = 100_000
MAX_SOURCES = 32
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
MAX_FRAMES = 10_000
PLAN_VERSION = "prospective_delayed_paper_v1"


@dataclass(frozen=True, slots=True)
class ProspectivePaperPlan:
    plan_id: str
    service_id: str
    registered_at_ns: int
    policy: MicrostructurePolicyConfig
    replay: CaptureReplayConfig
    gateway: PaperGatewayConfig
    initial_cash_usdt: Decimal
    implementation_sha256: str
    environment_json: str
    schema_version: int = 1
    version: str = PLAN_VERSION
    mode: str = "paper"
    promotion_allowed: bool = False

    def __post_init__(self) -> None:
        _identifier(self.plan_id)
        _identifier(self.service_id)
        _timestamp(self.registered_at_ns)
        _digest(self.implementation_sha256)
        _money(self.initial_cash_usdt)
        if (
            type(self.policy) is not MicrostructurePolicyConfig
            or type(self.replay) is not CaptureReplayConfig
            or type(self.gateway) is not PaperGatewayConfig
        ):
            raise ValueError("Typed policy, replay and paper gateway are required.")
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or self.version != PLAN_VERSION
            or self.mode != "paper"
            or self.promotion_allowed is not False
            or self.environment_json != _environment()
        ):
            raise ValueError("Unsupported or changed prospective paper plan.")

    @property
    def sha256(self) -> str:
        return _hash(_encode(self))


@dataclass(frozen=True, slots=True)
class PaperSource:
    source_session: str
    capture_path: Path

    def __post_init__(self) -> None:
        _identifier(self.source_session)
        if not isinstance(self.capture_path, Path):
            raise ValueError("An explicit capture Path is required.")


def register_paper_plan(
    path: Path,
    *,
    plan_id: str,
    service_id: str,
    policy: MicrostructurePolicyConfig,
    replay: CaptureReplayConfig,
    gateway: PaperGatewayConfig,
    initial_cash_usdt: Decimal,
) -> ProspectivePaperPlan:
    """Write a new, immutable paper policy bundle before any source is captured."""
    plan = ProspectivePaperPlan(
        plan_id,
        service_id,
        time.time_ns(),
        policy,
        replay,
        gateway,
        initial_cash_usdt,
        _implementation_hash(),
        _environment(),
    )
    raw = (
        json.dumps(
            {"plan_sha256": plan.sha256, "plan": json.loads(_encode(plan))}, sort_keys=True
        ).encode()
        + b"\n"
    )
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("Paper plan exceeds its byte budget.")
    with Path(path).open("xb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    return plan


def load_paper_plan(path: Path) -> ProspectivePaperPlan:
    """Verify a policy bundle and its exact source/environment before capture IO."""
    with Path(path).open("rb") as source:
        raw = source.read(MAX_PLAN_BYTES + 1)
    if len(raw) > MAX_PLAN_BYTES:
        raise ValueError("Paper plan exceeds its byte budget.")
    envelope = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(envelope, dict) or set(envelope) != {"plan", "plan_sha256"}:
        raise ValueError("Invalid paper plan envelope.")
    value = envelope["plan"]
    if not isinstance(value, dict) or set(value) != set(ProspectivePaperPlan.__dataclass_fields__):
        raise ValueError("Invalid paper plan fields.")
    value["policy"] = _decode_policy(value["policy"])
    value["replay"] = _decode_replay(value["replay"])
    value["gateway"] = _decode_gateway(value["gateway"])
    value["initial_cash_usdt"] = _decimal(value["initial_cash_usdt"])
    plan = ProspectivePaperPlan(**value)
    if plan.sha256 != envelope["plan_sha256"]:
        raise ValueError("Paper plan checksum mismatch.")
    if plan.implementation_sha256 != _implementation_hash():
        raise ValueError("Source code changed after paper plan registration.")
    return plan


def simulate_paper_prefix(
    *,
    plan_path: Path,
    sources: tuple[PaperSource, ...],
    journal_path: Path,
    max_frames: int = MAX_FRAMES,
    enable_paper_simulation: bool = False,
    resume: bool = False,
) -> dict:
    """Atomically replay the complete declared prefix into one paper account.

    Repeated calls start at the first source and verify already committed ticks.
    The next source begins with a fresh book while the paper balance and risk
    checkpoint remain in the existing journal.
    """
    if enable_paper_simulation is not True:
        raise ValueError("Explicit paper simulation activation is required.")
    if type(resume) is not bool or type(max_frames) is not int or not 1 <= max_frames <= MAX_FRAMES:
        raise ValueError("Boolean resume and frame budget in [1, 10000] required.")
    plan = load_paper_plan(plan_path)
    if (
        type(sources) is not tuple
        or not 1 <= len(sources) <= MAX_SOURCES
        or any(type(source) is not PaperSource for source in sources)
    ):
        raise ValueError("Supply 1-32 explicit paper capture sources.")
    expected_names = tuple(
        f"{plan.service_id}-s{index:04d}" for index in range(1, len(sources) + 1)
    )
    if tuple(source.source_session for source in sources) != expected_names:
        raise ValueError("Paper sources must be the unbroken service sequence.")
    total_bytes = 0
    total_frames = 0
    previous_end = None
    replays = []
    for source in sources:
        if total_bytes + source.capture_path.stat().st_size > MAX_CAPTURE_BYTES:
            raise ValueError("Paper source prefix exceeds its aggregate byte budget.")
        with source.capture_path.open("rb") as capture:
            raw = capture.read(MAX_BYTES + 1)
        total_bytes += len(raw)
        if total_bytes > MAX_CAPTURE_BYTES:
            raise ValueError("Paper source prefix changed beyond its byte budget.")
        replay = CaptureReplay(
            raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            source_session=source.source_session,
            config=plan.replay,
        )
        framing = replay._framing()
        start_ns, end_ns = framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]
        if start_ns <= plan.registered_at_ns or (
            previous_end is not None and start_ns <= previous_end
        ):
            raise ValueError("Paper capture predates its plan or overlaps a prior session.")
        previous_end = end_ns
        total_frames += replay.record_count - 1
        if total_frames > max_frames:
            raise ValueError("Complete paper prefix exceeds the declared frame budget.")
        replays.append(replay)
    report = _simulate_replays(
        plan,
        tuple(replays),
        journal_path=journal_path,
        max_frames=max_frames,
        resume=resume,
        run_id="prospective-paper-" + _hash(PLAN_VERSION + ":" + plan.sha256),
    )
    report.pop("registration_sha256")
    report.update(
        mode="prospective_delayed_paper",
        plan_sha256=plan.sha256,
        plan_id=plan.plan_id,
        capture_delay=True,
    )
    return report


def _register_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.settings.read_text(encoding="utf-8"), object_pairs_hook=_pairs)
    if not isinstance(value, dict) or set(value) != {
        "plan_id",
        "service_id",
        "policy",
        "replay",
        "gateway",
        "initial_cash_usdt",
    }:
        parser.error("Settings must contain the six required paper plan fields.")
    plan = register_paper_plan(
        args.output,
        plan_id=value["plan_id"],
        service_id=value["service_id"],
        policy=_decode_policy(value["policy"]),
        replay=_decode_replay(value["replay"]),
        gateway=_decode_gateway(value["gateway"]),
        initial_cash_usdt=_decimal(value["initial_cash_usdt"]),
    )
    print(json.dumps({"plan": str(args.output.resolve()), "sha256": plan.sha256}))


if __name__ == "__main__":
    _register_cli()
