"""Write-once microstructure shadow registration and explicit-source case evaluation.

No execution or portfolio simulation. Every frame is retained, including abstentions
and risk rejections. Reserved sessions are refused before opening a capture path.
"""

import argparse
import json
import os
import platform
import time
from collections import Counter
from dataclasses import dataclass, fields
from decimal import Decimal
from importlib.metadata import version
from itertools import islice
from pathlib import Path

from ai_trader.research.capture_quality import _config as _decode_features
from ai_trader.trading.capture_replay import (
    CaptureReplay,
    CaptureReplayConfig,
    _implementation_hash,
)
from ai_trader.trading.durable_paper_gateway import PaperGatewayConfig
from ai_trader.trading.durable_paper_gateway import _decode_config as _decode_gateway
from ai_trader.trading.microstructure_policy import (
    MicrostructurePolicyConfig,
    ResearchRiskSnapshot,
    assess_microstructure,
)
from ai_trader.trading.paper_lifecycle import _money, _timestamp
from ai_trader.trading.trade_case import _digest
from ai_trader.trading.trade_journal import (
    TradeJournal,
    _constant,
    _decimal,
    _encode,
    _hash,
    _identifier,
    _pairs,
    _shape,
)

MAX_REGISTRATION_BYTES = 1_000_000


def _environment():
    # Only packages used by capture/features, no native torch import or credential access.
    return json.dumps(
        {"python": platform.python_version(), **{p: version(p) for p in ("numpy", "websockets")}},
        sort_keys=True,
    )


@dataclass(frozen=True, slots=True)
class SourceDeclaration:
    source_session: str
    source_sha256: str
    started_at_ns: int
    ended_at_ns: int
    role: str

    def __post_init__(self):
        _identifier(self.source_session)
        _digest(self.source_sha256)
        _timestamp(self.started_at_ns)
        _timestamp(self.ended_at_ns)
        if self.ended_at_ns <= self.started_at_ns or self.role not in ("research", "reserved"):
            raise ValueError("Positive session duration and research/reserved role required.")


@dataclass(frozen=True, slots=True)
class MicrostructureRegistration:
    trial_id: str
    registered_at_ns: int
    sources: tuple[SourceDeclaration, ...]
    policy: MicrostructurePolicyConfig
    replay: CaptureReplayConfig
    gateway: PaperGatewayConfig
    initial_cash_usdt: Decimal
    implementation_sha256: str
    environment_json: str
    schema_version: int = 1
    study: str = "microstructure_shadow_v1"
    mode: str = "research_only"
    promotion_allowed: bool = False

    def __post_init__(self):
        _identifier(self.trial_id)
        _timestamp(self.registered_at_ns)
        _digest(self.implementation_sha256)
        _money(self.initial_cash_usdt)
        if (
            type(self.schema_version) is not int
            or self.schema_version != 1
            or self.study != "microstructure_shadow_v1"
            or self.mode != "research_only"
            or self.promotion_allowed is not False
        ):
            raise ValueError("Only unpromoted research-only registration is supported.")
        if (
            type(self.policy) is not MicrostructurePolicyConfig
            or type(self.replay) is not CaptureReplayConfig
            or type(self.gateway) is not PaperGatewayConfig
        ):
            raise ValueError("Typed policy, replay and gateway settings required.")
        if (
            type(self.sources) is not tuple
            or not 2 <= len(self.sources) <= 1000
            or any(type(s) is not SourceDeclaration for s in self.sources)
        ):
            raise ValueError("Declare an immutable inventory of 2-1000 source sessions.")
        if len({s.source_session for s in self.sources}) != len(self.sources):
            raise ValueError("Duplicate source session.")
        if len({s.source_sha256 for s in self.sources}) != len(self.sources):
            raise ValueError("Capture bytes cannot be aliased across source sessions or roles.")
        if {s.role for s in self.sources} != {"research", "reserved"}:
            raise ValueError("Both research and reserved sessions must be declared.")
        for earlier, later in zip(self.sources, self.sources[1:], strict=False):
            if earlier.ended_at_ns >= later.started_at_ns:
                raise ValueError("Source declarations must be chronological and non-overlapping.")
            if earlier.role == "reserved" and later.role == "research":
                raise ValueError("Reserved sessions must follow every research session.")
        if not isinstance(self.environment_json, str):
            raise ValueError("Expected canonical environment metadata.")
        environment = json.loads(
            self.environment_json, object_pairs_hook=_pairs, parse_constant=_constant
        )
        if (
            not isinstance(environment, dict)
            or set(environment) != {"python", "numpy", "websockets"}
            or any(not isinstance(v, str) or not v for v in environment.values())
            or json.dumps(environment, sort_keys=True) != self.environment_json
        ):
            raise ValueError("Invalid environment metadata.")

    @property
    def sha256(self):
        return _hash(_encode(self))

    def research_source(self, source_session):
        source = next((s for s in self.sources if s.source_session == source_session), None)
        if source is None or source.role != "research":
            raise ValueError("Only an explicitly registered research session may be opened.")
        return source

    def journal_run_id(self, source_session):
        """Bind the existing immutable journal identity without changing its schema."""
        self.research_source(source_session)
        return "micro-shadow-" + _hash(self.sha256 + ":" + source_session)


def register_trial(
    output_path: Path,
    *,
    trial_id: str,
    sources: tuple[SourceDeclaration, ...],
    policy: MicrostructurePolicyConfig,
    replay: CaptureReplayConfig,
    gateway: PaperGatewayConfig,
    initial_cash_usdt: Decimal,
) -> MicrostructureRegistration:
    """Write only declaration metadata; NEVER open the declared market datasets."""
    record = MicrostructureRegistration(
        trial_id,
        time.time_ns(),
        sources,
        policy,
        replay,
        gateway,
        initial_cash_usdt,
        _implementation_hash(),
        _environment(),
    )
    encoded = (
        json.dumps(
            {"registration_sha256": record.sha256, "registration": json.loads(_encode(record))},
            sort_keys=True,
        ).encode()
        + b"\n"
    )
    if len(encoded) > MAX_REGISTRATION_BYTES:
        raise ValueError("Registration exceeds byte budget.")
    with Path(output_path).open("xb") as output:
        output.write(encoded)
        output.flush()
        os.fsync(output.fileno())
    return record


def _decode_policy(value):
    value = _shape(value, MicrostructurePolicyConfig)
    integer_fields = {
        "minimum_replenishment_intervals",
        "maximum_trade_age_ns",
        "maximum_hold_ns",
        "entry_ttl_ns",
    }
    for item in fields(MicrostructurePolicyConfig):
        if item.name not in integer_fields | {"rule"}:
            value[item.name] = _decimal(value[item.name])
    return MicrostructurePolicyConfig(**value)


def _decode_replay(value):
    value = _shape(value, CaptureReplayConfig)
    value["features"] = _decode_features(value["features"])
    return CaptureReplayConfig(**value)


def load_registration(path: Path) -> MicrostructureRegistration:
    with Path(path).open("rb") as source:
        raw = source.read(MAX_REGISTRATION_BYTES + 1)
    if len(raw) > MAX_REGISTRATION_BYTES:
        raise ValueError("Registration exceeds byte budget.")
    envelope = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(envelope, dict) or set(envelope) != {"registration", "registration_sha256"}:
        raise ValueError("Invalid registration envelope.")
    value = _shape(envelope["registration"], MicrostructureRegistration)
    if not isinstance(value["sources"], list):
        raise ValueError("Expected declared source list.")
    value["sources"] = tuple(
        SourceDeclaration(**_shape(s, SourceDeclaration)) for s in value["sources"]
    )
    value["policy"] = _decode_policy(value["policy"])
    value["replay"] = _decode_replay(value["replay"])
    value["gateway"] = _decode_gateway(value["gateway"])
    value["initial_cash_usdt"] = _decimal(value["initial_cash_usdt"])
    record = MicrostructureRegistration(**value)
    if record.sha256 != envelope["registration_sha256"]:
        raise ValueError("Registration checksum mismatch.")
    if (
        record.implementation_sha256 != _implementation_hash()
        or record.environment_json != _environment()
    ):
        raise ValueError(
            "Source code or environment changed after registration; create a new trial."
        )
    return record


def evaluate_registered_capture(
    *,
    registration_path: Path,
    capture_path: Path,
    source_session: str,
    journal_path: Path,
    max_frames: int,
    resume: bool = False,
) -> dict:
    """Shadow-screen each frame under the SAME declared flat-account assumptions.

    Proposals never fill or deplete cash. Counts are not trades or backtest metrics.
    Each invocation commits atomically; explicit exact prefix retries deduplicate.
    """
    if type(max_frames) is not int or not 1 <= max_frames <= 10_000 or type(resume) is not bool:
        raise ValueError("Boolean resume and frame budget in [1, 10000] required.")
    registration = load_registration(registration_path)
    source = registration.research_source(source_session)  # BEFORE ANY capture/journal access.
    replay = CaptureReplay.from_path(
        capture_path,
        expected_sha256=source.source_sha256,
        source_session=source_session,
        config=registration.replay,
    )
    framing = replay._framing()
    if (framing[0]["started_at_ns"], framing[-1]["ended_at_ns"]) != (
        source.started_at_ns,
        source.ended_at_ns,
    ):
        raise ValueError("Capture times differ from the registered source declaration.")
    factory = TradeJournal if resume else TradeJournal.create
    counts, reasons, count, faults, last_line = Counter(), Counter(), 0, 0, 0
    run_id = registration.journal_run_id(source_session)
    with factory(journal_path, run_id=run_id, mode="research_only") as journal:
        with journal._write():
            for frame in islice(replay.frames(), max_frames):
                case = assess_microstructure(
                    frame,
                    policy=registration.policy,
                    features=registration.replay.features,
                    gateway=registration.gateway,
                    registration_sha256=registration.sha256,
                    risk=ResearchRiskSnapshot(
                        frame.tick.observed_at_ns,
                        registration.initial_cash_usdt,
                        Decimal(0),
                        Decimal(0),
                        registration.initial_cash_usdt,
                        False,
                        False,
                    ),
                )
                journal.append_case(case)
                count += 1
                faults += frame.status.startswith("resync_required:")
                last_line = frame.line_number
                counts[f"{case.action}:{case.risk_verdict}"] += 1
                reasons[case.risk_reason] += 1
            if (
                registration.implementation_sha256 != _implementation_hash()
                or registration.environment_json != _environment()
            ):
                raise ValueError(
                    "Source/environment changed during evaluation; invocation rolled back."
                )
    return {
        "mode": "research_only",
        "study": registration.study,
        "registration_sha256": registration.sha256,
        "journal_run_id": run_id,
        "source_session": source_session,
        "frames_evaluated": count,
        "session_consumed": last_line == replay.record_count,
        "market_fault_frames": faults,
        "case_counts": dict(counts),
        "reason_counts": dict(reasons),
        "orders": 0,
        "promotion_allowed": False,
        "limitation": "Stateless flat-account shadow proposals, not trades, PnL or a backtest.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser(
        "register", help="Read declaration JSON only; no capture access."
    )
    register.add_argument("--spec", type=Path, required=True)
    register.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser(
        "evaluate", help="Offline, research-only shadow cases; no orders."
    )
    evaluate.add_argument("--registration", type=Path, required=True)
    evaluate.add_argument("--capture", type=Path, required=True)
    evaluate.add_argument("--source-session", required=True)
    evaluate.add_argument("--journal", type=Path, required=True)
    evaluate.add_argument("--max-frames", type=int, required=True)
    evaluate.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.command == "register":
        with args.spec.open("rb") as source:
            raw = source.read(MAX_REGISTRATION_BYTES + 1)
        if len(raw) > MAX_REGISTRATION_BYTES:
            raise ValueError("Specification exceeds byte budget.")
        spec = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
        if not isinstance(spec, dict) or set(spec) != {
            "trial_id",
            "sources",
            "policy",
            "replay",
            "gateway",
            "initial_cash_usdt",
        }:
            raise ValueError("Invalid trial specification fields.")
        record = register_trial(
            args.output,
            trial_id=spec["trial_id"],
            sources=tuple(
                SourceDeclaration(**_shape(s, SourceDeclaration)) for s in spec["sources"]
            ),
            policy=_decode_policy(spec["policy"]),
            replay=_decode_replay(spec["replay"]),
            gateway=_decode_gateway(spec["gateway"]),
            initial_cash_usdt=_decimal(spec["initial_cash_usdt"]),
        )
        print(json.dumps({"registration_sha256": record.sha256, "mode": record.mode}))
    else:
        report = evaluate_registered_capture(
            registration_path=args.registration,
            capture_path=args.capture,
            source_session=args.source_session,
            journal_path=args.journal,
            max_frames=args.max_frames,
            resume=args.resume,
        )
        print(json.dumps(report, sort_keys=True))
        if report["market_fault_frames"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
