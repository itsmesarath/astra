"""Causal descriptors preserve original counterfactual unknowns and cohort pins."""

import hashlib
from copy import deepcopy

import numpy as np
import pytest

from ai_trader.research import six_e_quote_observability as o

DAY = "2025-04-07"
START, _ = o.target.window(DAY)
TICK = o.target.TICK


def quotes(day=DAY, recent=False):
    start, _ = o.target.window(day)
    values = [
        (0, 100, 101),
        (100_000_000, 100, 101),
        (100_000_000, 101, 102),
        (200_000_000, 99, 100),
        (300_000_000, 99, 100),
        (2_000_000_000, 100, 101),
        *(([(15_190_000_000, 100, 101)]) if recent else []),
        (17_000_000_000, 100, 101),
    ]
    return np.array([[start + t, b * TICK, a * TICK] for t, b, a in values], dtype=np.int64)


def columns(q):
    result = tuple(np.array(column, copy=True) for column in q.T)
    for column in result:
        column.flags.writeable = False
    return result


def index(q=None, day=DAY):
    return o.ReferenceIndex(
        columns(quotes(day) if q is None else q), day, o.study.census.dated_contract(day)
    )


def labels(q=None, day=DAY, eligible=True):
    q = quotes(day) if q is None else q
    row = {
        "source_session": day,
        "contract": o.study.census.dated_contract(day),
        "partition": "development",
        "decision_ts_ns": o.target.window(day)[0],
        "eligible": eligible,
        "eligibility_reason": None if eligible else "causal_refusal",
    }
    return o.target.targets([row], q)


@pytest.mark.parametrize("cursor", [-1, 0, 1, 2, 6])
def test_bulk_reference_matches_pure_explicit_cursor_helper(cursor):
    q = quotes()
    requests = np.array([START + 100_000_000, START + 4_000_000_000], dtype=np.int64)
    refs = index(q).lookup(requests, np.full(2, cursor, dtype=np.int64))
    for i, request in enumerate(requests):
        pure = o.reference.reference(
            q,
            source_session=DAY,
            contract="6EM5",
            request_ts_ns=int(request),
            published_cursor=cursor,
        )
        assert refs["cursor"][i] == (
            -1 if pure["reference_cursor"] is None else pure["reference_cursor"]
        )
        assert refs["ts_ns"][i] == (
            -1 if pure["reference_ts_ns"] is None else pure["reference_ts_ns"]
        )
        assert refs["age_ns"][i] == (-1 if pure["age_ns"] is None else pure["age_ns"])


def test_equal_time_cursor_and_strict_future_suffix_do_not_change_published_prefix():
    q = quotes()
    before = q.copy()
    request = np.array([START + 100_000_000] * 2, dtype=np.int64)
    cursors = np.array([1, 2], dtype=np.int64)
    full = index(q).lookup(request, cursors)
    prefix = index(q[:3]).lookup(request, cursors)
    assert full["cursor"].tolist() == [1, 2]
    for key in full:
        np.testing.assert_array_equal(full[key], prefix[key])
    np.testing.assert_array_equal(q, before)


def test_future_only_and_empty_columns_never_invent_a_reference():
    requests = np.array([START], dtype=np.int64)
    empty = index(np.empty((0, 3), dtype=np.int64)).lookup(requests, np.array([-1], dtype=np.int64))
    future = index(quotes()[1:]).lookup(requests, np.array([0], dtype=np.int64))
    assert all(empty[k].tolist() == [-1] == future[k].tolist() for k in empty)


@pytest.mark.parametrize("change", ["reserved", "contract"])
def test_scope_guard_precedes_price_access(change):
    class Poison:
        def __len__(self):
            pytest.fail("scope refusal accessed prices")

    with pytest.raises(ValueError):
        o.ReferenceIndex(Poison(), "2026-01-01" if change == "reserved" else DAY, "6EU5")


@pytest.mark.parametrize(
    "change",
    [
        "writable",
        "float",
        "unsigned",
        "shape",
        "different_lengths",
        "crossed",
        "off_tick",
        "outside",
        "page_order",
        "count",
    ],
)
def test_native_validation_is_once_bounded_and_fail_closed(change, monkeypatch):
    q = quotes()
    if change == "crossed":
        q[0, 2] = q[0, 1]
    elif change == "off_tick":
        q[0, 1] += 1
    elif change == "outside":
        q[-1, 0] += 86400 * o.target.SECOND
    elif change == "page_order":
        q[2, 0] = q[0, 0]
        monkeypatch.setattr(o.resource, "CHUNK_QUOTES", 2)
    elif change == "count":
        monkeypatch.setattr(o.resource, "MAX_QUOTES", 2)
    cols = columns(
        q.astype(float) if change == "float" else q.astype(np.uint64) if change == "unsigned" else q
    )
    if change == "writable":
        cols[0].flags.writeable = True
    elif change == "shape":
        cols = (cols[0].reshape(-1, 1), *cols[1:])
    elif change == "different_lengths":
        cols = (cols[0][:-1], *cols[1:])
    with pytest.raises(ValueError):
        o.ReferenceIndex(cols, DAY, "6EM5")


@pytest.mark.parametrize(
    "requests,cursors",
    [
        ([START - 1], [0]),
        ([START], [-2]),
        ([START], [7]),
        ([START], []),
        ([True], [0]),
        ([float(START)], [0]),
    ],
)
def test_invalid_requests_and_missing_cursor_refused(requests, cursors):
    with pytest.raises(ValueError):
        index().lookup(np.asarray(requests), np.asarray(cursors))


def test_per_request_batch_bound(monkeypatch):
    monkeypatch.setattr(o, "MAX_QUERIES", 1)
    with pytest.raises(ValueError):
        index().lookup(np.array([START] * 2, dtype=np.int64), np.array([0] * 2, dtype=np.int64))


@pytest.mark.parametrize("recent,expected_band", [(False, "over_1000ms"), (True, "at_most_100ms")])
def test_unknown_with_old_or_recent_reference_is_still_an_unreconciled_liability(
    recent, expected_band
):
    q = quotes(recent=recent)
    original = labels(q)
    before = deepcopy(original)
    result = o.describe(original, index(q), DAY, "6EM5")
    assert original == before
    for side in o.target.SIDES:
        values = result["exits"]["time_exit"][side]
        unknown = values["by_original_status"]["unresolved_exit_quote_timeout"]
        assert unknown["requests"] == values["unreconciled_counterfactual_exit_liabilities"] == 1
        assert unknown["reference_age_bands"][expected_band] == 1
        assert unknown["first_strictly_later_within_deadline"] == 0
        assert sum(unknown["reference_age_bands"].values()) == 1
    assert result["exit_requests"] == 4
    assert all(value is False for value in o.FLAGS.values())
    assert "net_ticks" not in result and "bid_nano" not in result and "fill" not in result


def test_equal_time_first_fresh_event_and_latest_reference_remain_separate():
    q = quotes()
    q = np.insert(q, 4, [START + 200_000_000, 101 * TICK, 102 * TICK], axis=0)
    source = labels(q)
    result = o.describe(source, index(q), DAY, "6EM5")
    assert result["exits"]["bracket_exit"]["short"]["equal_time_native_cursor_difference"] == 1
    source[0]["outcomes"]["bracket_exit"]["short"]["exit_bid_nano"] = 101 * TICK
    with pytest.raises(ValueError, match="parity"):
        o.describe(source, index(q), DAY, "6EM5")


def test_future_profit_and_hindsight_poison_are_not_descriptor_inputs():
    source = labels()
    expected = o.describe(source, index(), DAY, "6EM5")
    source[0]["hindsight_states"] = object()
    for outcomes in source[0]["outcomes"].values():
        for outcome in outcomes.values():
            for field in ("net_ticks", "gross_ticks", "hold_seconds", "trigger_net_ticks"):
                outcome[field] = object()
    assert o.describe(source, index(), DAY, "6EM5") == expected


def test_no_entry_rows_retained_with_zero_counterfactual_requests():
    source = labels(eligible=False)
    result = o.describe(source, index(), DAY, "6EM5")
    assert result["rows"] == result["entry_statuses"]["not_eligible"] == 1
    assert result["exit_requests"] == 0


@pytest.mark.parametrize(
    "change", ["unknown_closed", "deadline", "session", "contract", "bool", "order", "inactivity"]
)
def test_original_availability_identity_and_requests_cannot_be_rewritten(change):
    source = labels()
    outcome = source[0]["outcomes"]["time_exit"]["long"]
    if change == "unknown_closed":
        outcome["status"] = "resolved"
    elif change == "deadline":
        outcome["exit_deadline_ts_ns"] += 1
    elif change == "session":
        source[0]["source_session"] = "2026-01-01"
    elif change == "contract":
        source[0]["contract"] = "6EU5"
    elif change == "bool":
        source[0]["decision_ts_ns"] = True
    elif change == "order":
        source.append(deepcopy(source[0]))
    else:
        outcome["inactivity_exposed"] = 0
    with pytest.raises(ValueError):
        o.describe(source, index(), DAY, "6EM5")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(o.common.canonical(value) + b"\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def study_run(tmp_path, monkeypatch):
    root = tmp_path
    (root / "logs").mkdir()
    build = root / "data/processed/original"
    build.mkdir(parents=True)
    frozen = {
        "sources": [],
        "coverage": {"dispositions": {"metadata_only": 45}, "reserved_dates": 230},
    }
    evidence = []
    for day in ("2025-04-07", "2025-10-07", "2025-12-09"):
        q, source = quotes(day), labels(day=day)
        quote_path = build / f"{day}.quotes"
        quote_path.mkdir()
        pins = {}
        for name, column in zip(o.resource.COLUMNS, q.T, strict=True):
            path = quote_path / f"{name}.i64"
            path.write_bytes(np.asarray(column, dtype="<i8").tobytes())
            pins[name] = {
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        meta = {"count": len(q), "columns": pins}
        original = root / "data/processed" / f"{day}.original.json"
        original_pin = write(original, {"quality": {}, "instrument_id": 7})
        entry = {
            "utc_date": day,
            "contract": o.study.census.dated_contract(day),
            "role": o.study.data.role_for_day(day),
            "source_sha256": "a" * 64,
            "report": {"path": str(original.relative_to(root)), "sha256": original_pin},
        }
        frozen["sources"].append({"entry": entry})
        target_path = build / f"{day}.targets.jsonl"
        target_pin = write(target_path, source[0])
        daily_pin = write(
            build / f"{day}.json",
            {
                "source_sha256": entry["source_sha256"],
                "parity_verified": True,
                "quotes": meta,
                "replay": {
                    "full_member_hash_verified": True,
                    "quality": {},
                    "instrument_id": 7,
                    "completed_quotes": len(q),
                    "quote_columns": pins,
                },
                "accounting": {"entry_statuses": {"entered": 1}},
            },
        )
        evidence.append(
            {
                "utc_date": day,
                "rows": 1,
                "quotes": meta,
                "targets_sha256": target_pin,
                "report_sha256": daily_pin,
            }
        )
    monkeypatch.setattr(o.study, "registration", lambda *args: deepcopy(frozen))
    old_registration = root / "logs/original.json"
    old_pin = write(old_registration, {"original": True})
    request_pin = write(
        build / "request.json", {"registration_sha256": old_pin, "protocol": o.study.protocol()}
    )
    completion_pin = write(
        build / "completion.json",
        {
            "status": "completed_whole_liquidity_targets_not_validation",
            "registration_sha256": old_pin,
            "protocol": o.study.protocol(),
            "implementation_sha256": o.study.fingerprints(),
            "flags": {**o.study.AUTH, "cpu_training": False},
            "days": evidence,
            "request_sha256": request_pin,
        },
    )
    receipt_pin = write(
        build / "verification.json",
        {
            "status": "verified_whole_liquidity_targets_not_validation",
            "completion_sha256": completion_pin,
            "sessions": 3,
            "rows": 3,
            "flags": {**o.study.AUTH, "cpu_training": False},
        },
    )
    destination = root / "data/processed/observability.json"
    spec = {
        "registration": str(old_registration),
        "registration_sha256": old_pin,
        "build": str(build),
        "completion_sha256": completion_pin,
        "verification_sha256": receipt_pin,
        "output": str(destination),
    }
    path = root / "logs/observability.json"
    o.prepare(root, spec, path)
    return root, path, o.common.hash_file(path, o.status.MAX_REGISTRATION), destination, build


def test_full_descriptor_run_and_read_only_terminal_verifier(study_run, monkeypatch):
    root, path, pin, destination, build = study_run
    original = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in build.rglob("*") if p.is_file()
    }

    def forbidden(*args, **kwargs):
        pytest.fail("observability cannot replay archives or fit/score a model")

    monkeypatch.setattr(o.resource, "replay_day", forbidden)
    monkeypatch.setattr(o.study.rules, "fit", forbidden)
    monkeypatch.setattr(o.study, "evaluate", forbidden)
    result = o.run(root, path, pin, destination)
    verified = o.verify(
        root, path, pin, destination, o.common.hash_file(destination, o.MAX_OUTPUT_BYTES)
    )
    assert verified["sessions"] == verified["rows"] == 3
    assert result["summaries"]["overall"]["exit_requests"] == 12
    assert (
        result["summaries"]["overall"]["exits"]["time_exit"]["long"][
            "unreconciled_counterfactual_exit_liabilities"
        ]
        == 3
    )
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in original.items()
    )
    assert not (destination.parent / "progress.jsonl").exists()
    with pytest.raises(ValueError, match="new separate"):
        o.run(root, path, pin, destination)


@pytest.mark.parametrize(
    "change", ["subset", "numeric_false", "digest", "count", "progress", "failure"]
)
def test_terminal_verifier_rejects_re_pinned_incomplete_or_modified_result(study_run, change):
    root, path, pin, destination, _ = study_run
    result = o.run(root, path, pin, destination)
    if change == "subset":
        result["days"].pop()
    elif change == "numeric_false":
        result["flags"]["trading_enabled"] = 0
    elif change == "digest":
        result["days"][0]["ordered_descriptors_sha256"] = "f" * 64
    elif change == "count":
        result["summaries"]["overall"]["rows"] += 1
    elif change == "progress":
        destination.with_suffix(".progress.jsonl").write_bytes(b"partial")
    else:
        write(destination.with_suffix(".failure.json"), {"error": "retained"})
    with pytest.raises(ValueError):
        o.verify(root, path, pin, destination, write(destination, result))


def test_input_drift_and_failure_never_publish_success_or_retry(study_run):
    root, path, pin, destination, build = study_run
    quote_path = build / "2025-04-07.quotes/ts.i64"
    quote_path.write_bytes(quote_path.read_bytes()[:-8])
    with pytest.raises(ValueError):
        o.run(root, path, pin, destination)
    assert not destination.exists()
    assert destination.with_suffix(".failure.json").exists()
    with pytest.raises(ValueError, match="retained evidence"):
        o.run(root, path, pin, destination)


def test_source_drift_precedes_output_claim(study_run, monkeypatch):
    root, path, pin, destination, _ = study_run
    monkeypatch.setattr(o, "fingerprints", lambda: {"drift": "f" * 64})
    with pytest.raises(ValueError, match="source or protocol"):
        o.run(root, path, pin, destination)
    assert not destination.with_suffix(".attempt.json").exists()


def test_output_identity_and_registration_pin_are_required(study_run):
    root, path, pin, destination, build = study_run
    for output in (build / "changed.json", destination.with_name("unregistered.json")):
        with pytest.raises(ValueError):
            o.run(root, path, pin, output)
    with pytest.raises(ValueError, match="pinned metadata"):
        o.run(root, path, "f" * 64, destination)


def test_total_deadline_retains_failure_without_successful_subset(study_run, monkeypatch):
    root, path, pin, destination, _ = study_run
    monkeypatch.setattr(o, "MAX_SECONDS", -1)
    # Freeze the deliberately tiny resource limit before exercising its run.
    value = o.status._decode(path.read_bytes())
    value["protocol"] = o.protocol()
    new_pin = write(path, value)
    with pytest.raises(TimeoutError):
        o.run(root, path, new_pin, destination)
    assert not destination.exists()
    assert destination.with_suffix(".failure.json").exists()


def test_zero_entry_session_is_pooled_without_dropping_missing_roles():
    result = o.describe(labels(eligible=False), index(), DAY, "6EM5")
    summary = o.pooled([result])
    assert summary["overall"]["rows"] == 1
    assert summary["overall"]["exit_requests"] == 0
    assert summary["by_role"]["test_development"]["sessions"] == 0
    assert summary["by_role"]["test_development"]["exits"]["time_exit"]["long"]["requests"] == 0
    with pytest.raises(ValueError):
        o.pooled([])


def test_mid_read_quote_drift_is_caught_before_success(study_run, monkeypatch):
    root, path, pin, destination, build = study_run
    original = o.describe

    def changed(*args):
        result = original(*args)
        # Simulate another writer changing the source during descriptor construction.
        native = build / "2025-04-07.quotes/bid.i64"
        with native.open("r+b") as stream:
            stream.write(np.array([102 * TICK], dtype="<i8").tobytes())
        return result

    monkeypatch.setattr(o, "describe", changed)
    with pytest.raises(ValueError, match="changed census artifact"):
        o.run(root, path, pin, destination)
    assert not destination.exists()


def test_final_source_drift_cannot_publish_partial_success(study_run, monkeypatch):
    root, path, pin, destination, _ = study_run
    original = o.registration
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("simulated frozen source drift")
        return original(*args)

    monkeypatch.setattr(o, "registration", changed)
    with pytest.raises(ValueError, match="source drift"):
        o.run(root, path, pin, destination)
    assert not destination.exists()
    assert destination.with_suffix(".failure.json").exists()


def test_per_session_deadline_also_retains_failure(study_run, monkeypatch):
    root, path, pin, destination, _ = study_run
    monkeypatch.setattr(o, "MAX_DAY_SECONDS", -1)
    value = o.status._decode(path.read_bytes())
    value["protocol"] = o.protocol()
    with pytest.raises(TimeoutError, match="per-session"):
        o.run(root, path, write(path, value), destination)
    assert not destination.exists()


def test_linked_input_refused_before_price_access(study_run, monkeypatch):
    root, path, pin, destination, build = study_run
    original = o.status.os.path.isjunction
    watched = build / "2025-04-07.quotes"
    monkeypatch.setattr(o.status.os.path, "isjunction", lambda p: p == watched or original(p))
    with pytest.raises(ValueError, match="symlinks or junctions"):
        o.run(root, path, pin, destination)
    assert not destination.exists()


def test_registered_output_does_not_append_preexisting_progress(study_run):
    root, path, pin, destination, _ = study_run
    progress = destination.with_suffix(".progress.jsonl")
    progress.write_bytes(b"unrelated retained evidence\n")
    with pytest.raises(ValueError, match="retained evidence"):
        o.run(root, path, pin, destination)
    assert progress.read_bytes() == b"unrelated retained evidence\n"
    assert not destination.with_suffix(".attempt.json").exists()


def test_resource_receipt_cannot_be_re_pinned_as_boolean_elapsed(study_run):
    root, path, pin, destination, _ = study_run
    result = o.run(root, path, pin, destination)
    result["elapsed_seconds"] = False
    with pytest.raises(ValueError, match="terminal identity"):
        o.verify(root, path, pin, destination, write(destination, result))


def test_flags_in_returned_result_cannot_mutate_registered_authority(study_run):
    root, path, pin, destination, _ = study_run
    result = o.run(root, path, pin, destination)
    result["flags"]["trading_enabled"] = True
    result["protocol"]["flags"]["training_eligible"] = True
    assert o.FLAGS["trading_enabled"] is False
    assert o.protocol()["flags"]["training_eligible"] is False
