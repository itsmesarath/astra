"""Synthetic pinned rows/quotes only; never load the historical cohort or labels."""

import hashlib
import math
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from ai_trader.research import six_e_continuous_inputs as i
from ai_trader.research import six_e_continuous_replay as c

DAYS = ("2025-03-26", "2025-03-27", "2025-03-28", "2025-03-31")
PIN = "a" * 64


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    return write(path, i.study.common.canonical(value) + b"\n")


def row(day, offset=0):
    f = {name: 0.0 for name in i.study.rules.flow.data.FEATURES}
    f.update(
        log_bid_qty=math.log1p(6),
        log_ask_qty=math.log1p(6),
        log_bid_depth5=math.log1p(21),
        log_ask_depth5=math.log1p(21),
        log_known_trades_5s=math.log1p(21),
        log_quote_events_5s=math.log1p(21),
        normalized_cvd_5s=0.6,
        normalized_ofi_5s=0.6,
        mid_change_5s_ticks=1.0,
        mid_range_5s_ticks=4.0,
    )
    return {
        "source_session": day,
        "contract": i.study.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": i.obs.target.window(day)[0] + offset,
        "eligible": True,
        "eligibility_reason": None,
        "features": f,
        "execution_features": {name: 0.0 for name in i.study.rules.flow.FEATURES},
        # A strict causal loader does not interpret these original-envelope fields.
        "outcome": {"status": "not-a-valid-label", "net_ticks": "poison"},
        "hindsight_action": {"poison": True},
        "net_targets_long_short_ticks": "poison",
    }


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    root = tmp_path
    (root / "logs").mkdir()
    build = root / "data/processed/synthetic_collection"
    original = root / "data/processed/synthetic_original"
    sources, evidence = [], []
    for day in DAYS:
        rows = [row(day), row(day, 2 * i.obs.target.SECOND)]
        row_path = original / f"{day}.rows.jsonl"
        row_pin = write(row_path, b"".join(i.study.common.canonical(r) + b"\n" for r in rows))
        start, _ = i.obs.target.window(day)
        tick = i.obs.target.TICK
        quotes = np.array(
            [
                [start, 100 * tick, 101 * tick],
                [start, 101 * tick, 102 * tick],
                [start + 100_000_000, 100 * tick, 101 * tick],
                [start + 2 * i.obs.target.SECOND, 100 * tick, 101 * tick],
                [start + 2 * i.obs.target.SECOND, 101 * tick, 102 * tick],
                [start + 2 * i.obs.target.SECOND + 100_000_000, 100 * tick, 101 * tick],
            ],
            dtype="<i8",
        )
        columns = {}
        for name, column in zip(i.resource.COLUMNS, quotes.T, strict=True):
            raw = column.tobytes()
            columns[name] = {
                "bytes": len(raw),
                "sha256": write(build / f"{day}.quotes" / f"{name}.i64", raw),
            }
        quote_meta = {"count": len(quotes), "columns": columns}
        quality = {"synthetic_original_source": True}
        source_report_path = original / f"{day}.json"
        source_report_pin = write_json(
            source_report_path, {"quality": quality, "instrument_id": 17}
        )
        entry = {
            "utc_date": day,
            "contract": rows[0]["contract"],
            "partition": "development",
            "role": "train",
            "disposition": "decision_session",
            "source_sha256": PIN,
            "artifacts": {
                "rows": {
                    "path": row_path.relative_to(root).as_posix(),
                    "sha256": row_pin,
                    "count": len(rows),
                }
            },
            "report": {
                "path": source_report_path.relative_to(root).as_posix(),
                "sha256": source_report_pin,
            },
        }
        sources.append(
            {
                "entry": entry,
                "member": {
                    "utc_date": day,
                    "contract": entry["contract"],
                    "partition": "development",
                    "condition": "available",
                    "planned_action": "decision_window_replay",
                    "sha256": PIN,
                },
            }
        )
        saved = {
            "utc_date": day,
            "role": "train",
            "source_sha256": PIN,
            "parity_verified": True,
            "quotes": quote_meta,
            "replay": {
                "full_member_hash_verified": True,
                "quality": quality,
                "instrument_id": 17,
                "completed_quotes": len(quotes),
                "quote_columns": columns,
            },
            "accounting": {"poison_target_accounting": "not inspected"},
        }
        evidence.append(
            {
                "utc_date": day,
                "rows": len(rows),
                "quotes": quote_meta,
                "report_sha256": write_json(build / f"{day}.json", saved),
                "targets_sha256": "not-a-pin-and-not-read",
            }
        )
    value = {"inputs": {"build": str(build)}}
    frozen, report = {"sources": sources}, {"days": evidence}
    calls = []

    def metadata(*args):
        calls.append(args)
        return value, frozen, report

    monkeypatch.setattr(i, "metadata", metadata)
    for module, name in (
        (i.study.data, "read_rows"),
        (i.study, "_labels"),
        (i.study, "targets"),
        (i.study, "evaluate_day"),
        (i.study.rules, "sample"),
        (i.study.rules, "fit"),
    ):
        monkeypatch.setattr(module, name, lambda *args: pytest.fail("noncausal reader called"))
    return root, value, frozen, report, calls


def load(corpus, days=DAYS[:1]):
    return i.load_sessions(corpus[0], corpus[0] / "logs/original.json", PIN, days)


def reset_rows(corpus, rows, *, day=DAYS[0]):
    root, _, frozen, _, _ = corpus
    entry = next(s["entry"] for s in frozen["sources"] if s["entry"]["utc_date"] == day)
    artifact = entry["artifacts"]["rows"]
    artifact["sha256"] = write(
        root / artifact["path"], b"".join(i.study.common.canonical(r) + b"\n" for r in rows)
    )


@pytest.mark.parametrize("count", [1, 2, 3])
def test_exact_prefix_strips_poisoned_outcomes_and_keeps_first_equal_time_cursor(
    corpus, monkeypatch, count
):
    seen = []
    real = c.decision_input

    def project(source, cursor):
        assert set(source) == set(i.CAUSAL_FIELDS)
        seen.append(cursor)
        return real(source, cursor)

    monkeypatch.setattr(c, "decision_input", project)
    result = load(corpus, DAYS[:count])
    assert tuple(s.source_session for s in result) == DAYS[:count]
    assert seen == [0, 3] * count
    assert len(corpus[4]) == 2  # Original metadata/source pins are checked after use too.
    for session in result:
        assert type(session) is c.ReplaySession
        assert type(session.decisions) is tuple and len(session.decisions) == 2
        assert session.quotes.dtype == np.dtype(np.int64)
        assert session.quotes.shape == (6, 3) and not session.quotes.flags.writeable
        assert session.quotes.flags.owndata
        assert not any(
            key in session.decisions[0]
            for key in ("outcome", "hindsight_action", "net_targets_long_short_ticks")
        )


@pytest.mark.parametrize(
    "days",
    [
        (),
        list(DAYS[:1]),
        DAYS,
        DAYS[1:2],
        (DAYS[0], DAYS[0]),
        tuple(reversed(DAYS[:2])),
        ("2026-01-01",),
        ("2025-10-01",),
        ("2025-3-26",),
        (True,),
    ],
)
def test_invalid_scope_refused_before_any_price_or_daily_report_access(corpus, monkeypatch, days):
    monkeypatch.setattr(i.obs, "_read", lambda *args: pytest.fail("daily metadata accessed"))
    monkeypatch.setattr(i.study, "_view", lambda *args: pytest.fail("quotes accessed"))
    monkeypatch.setattr(i, "_decisions", lambda *args: pytest.fail("rows accessed"))
    with pytest.raises(ValueError):
        load(corpus, days)


@pytest.mark.parametrize(
    "change", ["contract", "role", "source_pin", "count", "quote_count", "column_bytes", "days"]
)
def test_all_requested_session_metadata_checked_before_any_price_path(corpus, monkeypatch, change):
    _, _, frozen, report, _ = corpus
    entry, evidence = frozen["sources"][1]["entry"], report["days"][1]
    if change == "contract":
        entry["contract"] = "6EU5"
    elif change == "role":
        entry["role"] = "validation_development"
    elif change == "source_pin":
        entry["source_sha256"] = "b" * 64
    elif change == "count":
        entry["artifacts"]["rows"]["count"] = True
    elif change == "quote_count":
        evidence["quotes"]["count"] = c.MAX_QUOTES + 1
    elif change == "column_bytes":
        evidence["quotes"]["columns"]["ts"]["bytes"] += 8
    else:
        report["days"].reverse()
    monkeypatch.setattr(i.obs, "_read", lambda *args: pytest.fail("price paths constructed"))
    with pytest.raises(ValueError):
        load(corpus, DAYS[:2])


def test_total_decision_bound_precedes_price_paths(corpus, monkeypatch):
    monkeypatch.setattr(c, "MAX_DECISIONS", 3)
    monkeypatch.setattr(i.obs, "_read", lambda *args: pytest.fail("daily metadata accessed"))
    with pytest.raises(ValueError, match="total decision"):
        load(corpus, DAYS[:2])


@pytest.mark.parametrize("change", ["newline", "long_line", "extra", "missing", "duplicate_key"])
def test_complete_original_line_count_and_hash_bounds(corpus, change):
    root, _, frozen, _, _ = corpus
    artifact = frozen["sources"][0]["entry"]["artifacts"]["rows"]
    path = root / artifact["path"]
    raw = path.read_bytes()
    if change == "newline":
        raw = raw[:-1]
    elif change == "long_line":
        raw = b" " * (i.MAX_LINE + 1) + b"\n"
    elif change == "extra":
        raw += raw.splitlines(keepends=True)[0]
    elif change == "missing":
        raw = raw.splitlines(keepends=True)[0]
    else:
        raw = b'{"source_session":"2025-03-26","source_session":"2025-03-26"}\n'
    artifact["sha256"] = write(path, raw)
    with pytest.raises(ValueError):
        load(corpus)


@pytest.mark.parametrize(
    "change",
    ["source", "contract", "clock", "bool", "order", "no_quote", "eligibility", "reason"],
)
def test_causal_row_identity_and_native_anchor_are_required(corpus, change):
    rows = [row(DAYS[0]), row(DAYS[0], 2 * i.obs.target.SECOND)]
    if change == "source":
        rows[0]["source_session"] = "2026-01-01"
    elif change == "contract":
        rows[0]["contract"] = "6EU5"
    elif change == "clock":
        rows[0]["decision_ts_ns"] -= i.obs.target.SECOND
    elif change == "bool":
        rows[0]["decision_ts_ns"] = True
    elif change == "order":
        rows.reverse()
    elif change == "eligibility":
        rows[0]["eligible"] = 1
    elif change == "reason":
        rows[0]["eligibility_reason"] = "refused but claims eligible"
    else:
        rows[0]["decision_ts_ns"] += 1
    reset_rows(corpus, rows)
    with pytest.raises(ValueError):
        load(corpus)


def test_quote_content_is_rechecked_after_copy_and_decision_projection(corpus, monkeypatch):
    root, value, _, _, _ = corpus
    path = root / value["inputs"]["build"] / f"{DAYS[0]}.quotes/bid.i64"
    real = c.decision_input
    changed = False

    def project(source, cursor):
        nonlocal changed
        result = real(source, cursor)
        if not changed:
            changed = True
            raw = bytearray(path.read_bytes())
            raw[0] ^= 1
            path.write_bytes(raw)
        return result

    monkeypatch.setattr(c, "decision_input", project)
    with pytest.raises(ValueError, match="changed"):
        load(corpus)


@pytest.mark.parametrize("change", ["crossed", "off_tick", "outside", "order"])
def test_whole_native_sequence_is_validated_without_thinning(corpus, change, monkeypatch):
    _, value, _, report, _ = corpus
    directory = Path(value["inputs"]["build"]) / f"{DAYS[0]}.quotes"
    name = "ask" if change == "crossed" else "bid" if change == "off_tick" else "ts"
    path = directory / f"{name}.i64"
    column = np.frombuffer(path.read_bytes(), dtype="<i8").copy()
    if change == "crossed":
        column[0] = 100 * i.obs.target.TICK
    elif change == "off_tick":
        column[0] += 1
    elif change == "outside":
        column[-1] = i.obs.target.window(DAYS[0])[1]
    else:
        monkeypatch.setattr(i.resource, "CHUNK_QUOTES", 2)
        column[3] = column[0]
    report["days"][0]["quotes"]["columns"][name]["sha256"] = write(path, column.tobytes())
    saved_path = directory.parent / f"{DAYS[0]}.json"
    saved = i.study.common.loads(saved_path.read_bytes())
    saved["quotes"] = deepcopy(report["days"][0]["quotes"])
    saved["replay"]["quote_columns"] = saved["quotes"]["columns"]
    report["days"][0]["report_sha256"] = write_json(saved_path, saved)
    with pytest.raises(ValueError):
        load(corpus)


def test_price_path_ancestor_junction_is_refused(corpus, monkeypatch):
    root, _, frozen, _, _ = corpus
    source_directory = (root / frozen["sources"][0]["entry"]["report"]["path"]).parent
    real = i.status.os.path.isjunction
    monkeypatch.setattr(i.status.os.path, "isjunction", lambda p: p == source_directory or real(p))
    with pytest.raises(ValueError, match="junction"):
        load(corpus)


def test_metadata_wrapper_uses_actual_three_value_registration_api(tmp_path, monkeypatch):
    (tmp_path / "logs").mkdir()
    expected, calls = ({}, {}, {}), []

    def registration(*args):
        calls.append(args)
        return expected

    monkeypatch.setattr(i.obs, "registration", registration)
    path = tmp_path / "logs/original.json"
    assert i.metadata(tmp_path, path, PIN) is expected
    assert calls == [(tmp_path, path, PIN)]


@pytest.mark.parametrize("kind", ["rows", "column", "daily_report", "source_report"])
def test_changed_pinned_source_content_is_refused(corpus, kind):
    root, value, frozen, _, _ = corpus
    entry = frozen["sources"][0]["entry"]
    build = Path(value["inputs"]["build"])
    path = {
        "rows": root / entry["artifacts"]["rows"]["path"],
        "column": build / f"{DAYS[0]}.quotes/ask.i64",
        "daily_report": build / f"{DAYS[0]}.json",
        "source_report": root / entry["report"]["path"],
    }[kind]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        load(corpus)


def test_source_change_during_loading_is_refused(corpus, monkeypatch):
    pins = iter(({"loader": "a" * 64}, {"loader": "b" * 64}))
    monkeypatch.setattr(i, "fingerprints", lambda: next(pins))
    with pytest.raises(ValueError, match="source changed"):
        load(corpus)


def test_final_original_metadata_drift_is_not_accepted(corpus, monkeypatch):
    _, value, frozen, report, _ = corpus
    calls = 0

    def metadata(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("pinned original metadata changed")
        return value, frozen, report

    monkeypatch.setattr(i, "metadata", metadata)
    with pytest.raises(ValueError, match="metadata changed"):
        load(corpus)


def test_loader_source_fingerprint_is_explicit_and_bounded():
    pins = i.fingerprints()
    own = Path(i.__file__)
    assert pins[own.name] == hashlib.sha256(own.read_bytes()).hexdigest()
    assert pins == {**i.obs.fingerprints(), own.name: pins[own.name]}
