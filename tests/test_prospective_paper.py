"""Prospective plan and delayed paper continuity across public-data sessions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from test_microstructure_campaign import shifted
from test_microstructure_policy import (
    capture_bytes,
    capture_rows,
    gateway_config,
    policy,
    replay_config,
)

from ai_trader.ingestion.paper_data_service import PaperDataServiceConfig, run_paper_data_service
from ai_trader.trading import prospective_paper
from ai_trader.trading.prospective_paper import (
    PaperSource,
    load_paper_plan,
    register_paper_plan,
    simulate_paper_prefix,
)

MS = 1_000_000


def _plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(prospective_paper.time, "time_ns", lambda: 100 * MS)
    path = tmp_path / "plan.json"
    plan = register_paper_plan(
        path,
        plan_id="test-paper-plan",
        service_id="test-service",
        policy=policy(),
        replay=replay_config(),
        gateway=gateway_config(),
        initial_cash_usdt=prospective_paper.Decimal("1000"),
    )
    return path, plan


def _source(tmp_path: Path, number: int) -> PaperSource:
    name = f"test-service-s{number:04d}"
    path = tmp_path / f"{name}.jsonl"
    rows = capture_rows() if number == 1 else shifted(capture_rows(), ms=number * 1000)
    path.write_bytes(capture_bytes(rows))
    return PaperSource(name, path)


def test_frozen_plan_replays_full_sessions_into_one_account(tmp_path, monkeypatch):
    plan_path, plan = _plan(tmp_path, monkeypatch)
    sources = (_source(tmp_path, 1), _source(tmp_path, 2))
    journal = tmp_path / "paper.sqlite"
    first = simulate_paper_prefix(
        plan_path=plan_path,
        sources=sources[:1],
        journal_path=journal,
        max_frames=100,
        enable_paper_simulation=True,
    )
    second = simulate_paper_prefix(
        plan_path=plan_path,
        sources=sources,
        journal_path=journal,
        max_frames=100,
        enable_paper_simulation=True,
        resume=True,
    )
    assert first["session_consumed"] and second["session_consumed"]
    assert second["plan_sha256"] == plan.sha256
    assert second["frames_processed"] > first["frames_processed"]
    assert second["journal_run_id"] == first["journal_run_id"]
    assert [row["source_session"] for row in second["source_sessions"]] == [
        source.source_session for source in sources
    ]
    assert load_paper_plan(plan_path) == plan


def test_rejects_capture_that_predates_plan_before_creating_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(prospective_paper.time, "time_ns", lambda: 1000 * MS)
    plan_path = tmp_path / "plan.json"
    register_paper_plan(
        plan_path,
        plan_id="late-plan",
        service_id="test-service",
        policy=policy(),
        replay=replay_config(),
        gateway=gateway_config(),
        initial_cash_usdt=prospective_paper.Decimal("1000"),
    )
    source = _source(tmp_path, 1)
    journal = tmp_path / "paper.sqlite"
    with pytest.raises(ValueError, match="predates its plan"):
        simulate_paper_prefix(
            plan_path=plan_path,
            sources=(source,),
            journal_path=journal,
            enable_paper_simulation=True,
        )
    assert not journal.exists()


def test_service_runs_paper_after_each_capture_and_keeps_one_journal(tmp_path, monkeypatch):
    plan_path, plan = _plan(tmp_path, monkeypatch)
    journal = tmp_path / "paper.sqlite"
    calls = 0

    async def collector(seconds, *, output_path, limits):
        nonlocal calls
        calls += 1
        rows = capture_rows() if calls == 1 else shifted(capture_rows(), ms=calls * 1000)
        output_path.write_bytes(capture_bytes(rows))
        return output_path, 6, 4

    config = PaperDataServiceConfig(
        sessions=2,
        seconds_per_session=1,
        output_directory=tmp_path / "captures",
        enable_public_data=True,
        build_features=False,
        service_id="test-service",
        paper_plan_path=plan_path,
        paper_journal_path=journal,
        max_paper_frames=100,
        enable_paper_simulation=True,
    )
    result = asyncio.run(run_paper_data_service(config, collector=collector))
    records = [json.loads(line) for line in result.manifest_path.read_text().splitlines()]
    successes = [record for record in records if record["record_type"] == "session_completed"]
    assert result.completed_sessions == 2 and len(successes) == 2
    assert all(record["paper_plan_sha256"] == plan.sha256 for record in successes)
    assert all(record["paper_journal_path"] == str(journal) for record in successes)
    assert journal.is_file()


def test_shipped_abstain_settings_can_be_registered(tmp_path, monkeypatch):
    monkeypatch.setattr(prospective_paper.time, "time_ns", lambda: 100 * MS)
    settings_path = (
        Path(__file__).resolve().parents[1] / "configs/paper_service_abstain_example.json"
    )
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    path = tmp_path / "plan.json"
    plan = register_paper_plan(
        path,
        plan_id=settings["plan_id"],
        service_id=settings["service_id"],
        policy=prospective_paper._decode_policy(settings["policy"]),
        replay=prospective_paper._decode_replay(settings["replay"]),
        gateway=prospective_paper._decode_gateway(settings["gateway"]),
        initial_cash_usdt=prospective_paper._decimal(settings["initial_cash_usdt"]),
    )
    assert plan.policy.rule == "abstain"
    assert load_paper_plan(path) == plan
