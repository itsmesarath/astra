"""Descriptive closed-only uncertainty must never hide unknown trades or weak support."""

from copy import deepcopy
from datetime import date, timedelta

import numpy as np
import pytest
from test_six_e_liquidity_status import run as run
from test_six_e_liquidity_status import terminal, write

from ai_trader.research import six_e_liquidity_diagnostics as d


def daily(day, closed=1, net=2, unknown=0, rows=100):
    selected = closed + unknown
    statuses = {}
    if closed:
        statuses["resolved"] = closed
    if unknown:
        statuses["unresolved_exit_quote_timeout"] = unknown
    metric = {
        "selected": selected,
        "closed": closed,
        "positive_closed": closed if net > 0 else 0,
        "unresolved_entered": unknown,
        "statuses": statuses,
        "skips": {"no_signal": rows - selected},
        "total_closed_net_ticks": net,
        "mean_net_ticks": net / closed if closed else None,
        "extra_cost_ticks": {
            str(c): {
                "closed": closed,
                "positive_closed": closed if closed and net / closed - c + 1 > 0 else 0,
                "total_closed_net_ticks": net - (c - 1) * closed,
            }
            for c in (1, 2, 4)
        },
    }
    policies = {
        name: {"signals": selected, **{plan: deepcopy(metric) for plan in d.PLANS}}
        for name in d.POLICIES
    }
    policies["no_trade"] = {
        "signals": 0,
        **{
            plan: {
                **deepcopy(metric),
                "selected": 0,
                "closed": 0,
                "positive_closed": 0,
                "unresolved_entered": 0,
                "statuses": {},
                "skips": {"no_signal": rows},
                "total_closed_net_ticks": 0,
                "mean_net_ticks": None,
                "extra_cost_ticks": {
                    str(c): {"closed": 0, "positive_closed": 0, "total_closed_net_ticks": 0}
                    for c in (1, 2, 4)
                },
            }
            for plan in d.PLANS
        },
    }
    return {"source_session": day, "role": d._role(day), "rows": rows, "policies": policies}


def cohort(count=25):
    start = date(2025, 4, 1)
    return [
        daily((start + timedelta(days=i)).isoformat(), net=2 if i % 2 else -2) for i in range(count)
    ]


def test_deterministic_five_session_blocks_not_trade_sampling():
    indices = d.indices(25)
    assert indices.shape == (2000, 25)
    assert np.array_equal(indices, d.indices(25))
    assert indices.min() >= 0 and indices.max() < 25
    assert np.all(np.diff(indices.reshape(2000, 5, 5), axis=2) == 1)


def test_complete_cohort_recost_and_idle_have_honest_denominators():
    result = d.describe(cohort())
    m = result["overall"]["policies"]["cvd_follow"]["bracket_exit"]
    assert m["closed"] == m["sessions_with_closed"] == 25
    assert m["costs"]["1"]["mean_closed_net_ticks"] == -2 / 25
    assert m["costs"]["2"]["total_closed_net_ticks"] == -27
    assert m["costs"]["4"]["total_closed_net_ticks"] == -77
    interval = m["costs"]["1"]["descriptive_closed_mean_interval"]
    assert interval is not None and interval[0] <= interval[1]
    idle = result["overall"]["policies"]["no_trade"]["bracket_exit"]
    assert idle["closed"] == 0
    assert idle["costs"]["1"]["mean_closed_net_ticks"] is None
    assert idle["costs"]["1"]["descriptive_closed_mean_interval"] is None


def test_unknowns_remain_present_with_incomplete_economics():
    days = cohort()
    days[0] = daily(days[0]["source_session"], closed=0, net=0, unknown=1)
    m = d.describe(days)["overall"]["policies"]["cpu_cost"]["time_exit"]
    assert m["selected"] == 25 and m["closed"] == 24
    assert m["unknown_entered_exits"] == m["sessions_with_unknown_entered_exit"] == 1
    assert m["economics_incomplete"] is True
    assert m["sessions_without_closed"] == 1
    assert m["costs"]["1"]["mean_closed_net_ticks"] == 0


def test_zero_closed_bootstrap_draw_is_not_dropped(monkeypatch):
    days = cohort(30)
    for i in range(10):
        days[i] = daily(days[i]["source_session"], closed=0, net=0, unknown=1)
    monkeypatch.setattr(d, "indices", lambda count: np.zeros((2000, count), dtype=int))
    m = d.describe(days)["overall"]["policies"]["absorption_fade"]["time_exit"]
    assert m["sessions_with_closed"] == 20
    assert m["costs"]["1"]["interval_status"] == "zero_closed_resample_no_subset"
    assert m["costs"]["1"]["descriptive_closed_mean_interval"] is None


def test_weak_support_is_not_invented():
    m = d.describe(cohort(19))["overall"]["policies"]["liquidity_follow"]["time_exit"]
    assert m["costs"]["1"]["interval_status"] == "insufficient_sessions_with_closed"


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate",
        "reorder",
        "reserved",
        "drop_policy",
        "role",
        "bool_rows",
        "mean",
        "unknown",
        "cost",
        "status",
        "skip",
        "nonfinite",
        "idle",
    ],
)
def test_invalid_complete_report_is_refused(mutation):
    days = cohort()
    m = days[0]["policies"]["cvd_follow"]["time_exit"]
    if mutation == "duplicate":
        days[1] = days[0]
    elif mutation == "reorder":
        days.reverse()
    elif mutation == "reserved":
        days[-1]["source_session"] = "2026-01-01"
    elif mutation == "drop_policy":
        del days[0]["policies"]["absorption_fade"]
    elif mutation == "role":
        days[0]["role"] = "test_development"
    elif mutation == "bool_rows":
        days[0]["rows"] = True
    elif mutation == "mean":
        m["mean_net_ticks"] = 0
    elif mutation == "unknown":
        m["unresolved_entered"] = 2
    elif mutation == "cost":
        m["extra_cost_ticks"]["2"]["closed"] = 2
    elif mutation == "status":
        m["statuses"]["discarded_loss"] = 1
    elif mutation == "skip":
        m["skips"]["no_signal"] -= 1
    elif mutation == "nonfinite":
        m["total_closed_net_ticks"] = float("inf")
    else:
        days[0]["policies"]["no_trade"]["signals"] = 1
    with pytest.raises(ValueError):
        d.describe(days)


def ready(run):
    root, registration, pin, output, frozen, request = run
    completed, receipt, _ = terminal(run, cpu=True)
    for evidence in completed["days"]:
        day = evidence["utc_date"]
        value = daily(day, rows=10)
        evidence["report_sha256"] = write(output / f"{day}.json", value)
    completion_pin = write(output / "completion.json", completed)
    receipt["completion_sha256"] = completion_pin
    write(output / "verification.json", receipt)
    return completion_pin


def test_report_only_reads_metadata_and_cannot_overwrite(run, monkeypatch):
    pin = ready(run)
    destination = run[0] / "data/processed/diagnostics.json"
    original = d.status._raw

    def metadata(root, path, *args):
        assert path.suffix in (".json", ".jsonl")
        assert path.name not in ("model.json", "features.jsonl", "predictions.jsonl")
        return original(root, path, *args)

    monkeypatch.setattr(d.status, "_raw", metadata)
    result = d.report(*run[:4], pin, destination)
    assert result["sessions"] == 2
    assert result["status"] == "completed_descriptive_metadata_diagnostics_not_validation"
    with pytest.raises(FileExistsError):
        d.report(*run[:4], pin, destination)
    with pytest.raises(ValueError, match="separate JSON"):
        d.report(*run[:4], pin, run[3] / "not_a_model.json")


def test_complete_daily_pin_drift_and_no_subset(run):
    pin = ready(run)
    write(run[3] / "2025-04-07.json", daily("2025-04-07", net=100, rows=10))
    destination = run[0] / "data/processed/diagnostics.json"
    with pytest.raises(ValueError, match="pin"):
        d.report(*run[:4], pin, destination)
    assert not destination.exists()


def test_incomplete_or_failed_metadata_cannot_be_described(run):
    destination = run[0] / "data/processed/diagnostics.json"
    with pytest.raises(ValueError, match="complete pinned"):
        d.report(*run[:4], "a" * 64, destination)
    pin = ready(run)
    write(
        run[3] / "failure.json",
        {
            "registration_sha256": run[2],
            "status": "failed_no_subset_or_retry",
            "exception": "ValueError",
        },
    )
    with pytest.raises(ValueError, match="complete pinned"):
        d.report(*run[:4], pin, destination)
    assert not destination.exists()


def test_role_groups_keep_later_development_names():
    days = [daily("2025-08-29"), daily("2025-09-01"), daily("2025-11-03")]
    result = d.describe(days)
    assert set(result["by_role"]) == set(d.ROLES)
    assert all(group["sessions"] == 1 for group in result["by_role"].values())
    assert d.protocol()["independent_holdout"] is False
