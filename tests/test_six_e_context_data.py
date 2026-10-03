"""Synthetic dense joins, future blindness, whole-session gates and tokenizer-only checks."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import test_six_e_balance_plan as balance_tests
from test_six_e_balance_plan import original as original
from test_six_e_balance_plan import samples as samples
from test_six_e_forecast import observation
from test_six_e_forecast_eval import candidate as candidate
from test_six_e_forecast_eval import trial_request as trial_request
from test_six_e_lora_trial import gpu_request as gpu_request
from test_six_e_lora_trial import pin, write

from ai_trader.models.local_checkpoint import canonical
from ai_trader.training import prepare_6e_context_data as b

t = b.task
balance_frozen = balance_tests.frozen


def lines(path, rows):
    path.write_text("".join(canonical(r) + "\n" for r in rows), encoding="utf-8")
    return {"path": path.as_posix(), "count": len(rows), "sha256": pin(path)}


@pytest.fixture
def evidence(balance_frozen, samples, monkeypatch):
    balance_path, balance_pin, prior = balance_frozen
    root = balance_path.parent
    processed = root / "data/processed"
    processed.mkdir(parents=True)
    entries = []
    for day in prior["session_split"]["fit"] + prior["session_split"]["check"]:
        sparse, dense = [], []
        count = sum(r["source_session"] == day for r in samples)
        for index in range(count + 1):
            if index:
                for lag in (2, 1):
                    row = observation(day=day, offset=index * 60 - lag)
                    row.update(
                        eligible=False,
                        outcome={"status": "not_eligible"},
                        net_targets_long_short_ticks=None,
                        hindsight_action=None,
                    )
                    row["features"]["normalized_cvd_5s"] = float(lag)
                    dense.append(row)
            state = index % 7
            row = observation(day=day, offset=index * 60, move=(0, 3, 4, 6, -3, -4, -6)[state])
            row["features"]["log_bid_qty"] = float(state)
            if index == count:
                row.update(
                    outcome={"status": "no_entry_quote_timeout"},
                    net_targets_long_short_ticks=None,
                    hindsight_action=None,
                )
            sparse.append(row)
            dense.append(copy.deepcopy(row))
        artifacts = {}
        for kind, rows in (("rows", dense), ("cases", sparse)):
            file = processed / f"{day}.{kind}.jsonl"
            meta = lines(file, rows)
            meta["path"] = file.relative_to(root).as_posix()
            artifacts[kind] = meta
        entries.append(
            {
                "utc_date": day,
                "role": "train",
                "partition": "development",
                "disposition": "decision_session",
                "contract": sparse[0]["contract"],
                "artifacts": artifacts,
                "case_accounting": b.data.accounting(sparse),
            }
        )
    for day, role in (
        ("2025-09-01", "validation_development"),
        ("2025-11-01", "test_development"),
        ("2026-01-01", "validation_reserved"),
    ):
        entries.append(
            {
                "utc_date": day,
                "role": role,
                "artifacts": {"rows": {"path": "data/raw/FORBIDDEN.dbn"}},
            }
        )
    manifest = {"ledger": entries}
    manifest_path = root / "manifest-for-context.json"
    actual_pin = write(manifest_path, manifest)

    def verified_manifest(test_root, path, supplied_pin):
        # Upstream lineage is independently tested; fake snapshot fixture uses this sentinel pin.
        assert test_root == root and path == manifest_path and supplied_pin == "b" * 64
        if pin(path) != actual_pin:
            raise ValueError("Synthetic manifest changed")
        return copy.deepcopy(manifest)

    monkeypatch.setattr(b.data, "load", verified_manifest)
    registration = root / "context-plan.json"
    plan = b.freeze(root, manifest_path, "b" * 64, balance_path, balance_pin, registration)
    return root, registration, pin(registration), plan


@pytest.fixture
def prepared(evidence):
    root, path, plan_pin, plan = evidence
    output = root / "data/processed/context"
    result = b.run(root, path, plan_pin, output, enable_preparation=True)
    return root, output, result, pin(output / "completion.json"), plan


def test_import_does_not_load_gpu_models_or_exchange_client():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; "
            "from ai_trader.training import prepare_6e_context_data; "
            "assert not ({'torch','transformers','peft','tokenizers','databento'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_compact_layout_preserves_information_without_redundant_delta_arrays():
    rows = [observation(offset=i) for i in range(4)]
    for i, row in enumerate(rows):
        row["features"]["normalized_cvd_5s"] = float(i)
    matrix, _ = b.context.transform(rows)
    payload = b.compact(matrix[-1])
    assert len(payload["current"]) == 43
    assert [len(row) for row in payload["past"]] == [12, 12, 12]
    assert payload["past"][0][:2] == [3, 0.6]
    assert payload["past"][0][2 + t.HISTORY.index("normalized_cvd_5s")] == 1.0
    assert t.payload_from_prompt(t.prompt(payload)) == payload
    assert t.TASK != b.snapshot.TASK


def test_context_projection_never_touches_future_eligibility_or_label_fields():
    row = observation()
    expected = b.causal_projection(row)

    class CausalOnly(dict):
        def __getitem__(self, key):
            assert key in {
                "source_session",
                "contract",
                "decision_ts_ns",
                "partition",
                "features",
                "execution_features",
            }
            return super().__getitem__(key)

    changed = CausalOnly(row)
    for key in (
        "outcome",
        "path_horizons",
        "eligible",
        "hindsight_action",
        "net_targets_long_short_ticks",
    ):
        changed[key] = object()
    assert b.causal_projection(changed) == expected


def test_prefix_and_payload_are_future_invariant_and_gap_reset_has_explicit_missingness():
    rows = [observation(offset=i) for i in range(5)]

    def collect(rows):
        state = b.context.CausalContext(rows[0]["source_session"], rows[0]["contract"])
        import hashlib

        prefix, result = hashlib.sha256(), []
        for row in rows:
            value = b.causal_projection(row)
            payload = b.compact(state.observe(value))
            prefix.update((canonical(value) + "\n").encode())
            result.append((payload, prefix.hexdigest()))
        return result

    original = collect(rows)
    assert collect(rows[:3]) == original[:3]
    changed = copy.deepcopy(rows)
    for row in changed:
        row.update(outcome=None, eligible="poison", path_horizons=object(), hindsight_action=999)
    assert collect(changed) == original
    changed[-1]["features"]["normalized_cvd_5s"] = 999
    assert collect(changed)[:4] == original[:4]
    rows[-1]["decision_ts_ns"] += 10 * b.snapshot.SECOND
    assert all(row == [0, 0.0, *([0.0] * 10)] for row in collect(rows)[-1][0]["past"])


@pytest.mark.parametrize(
    "mutation",
    [
        "length",
        "nan",
        "bool",
        "negative_execution",
        "count",
        "span",
        "empty_mean",
        "order",
        "extra",
    ],
)
def test_payload_shape_finiteness_and_history_missingness_refused(mutation):
    vector, _ = b.context.transform([observation(offset=i) for i in range(3)])
    payload = b.compact(vector[-1])
    if mutation == "length":
        payload["current"].pop()
    elif mutation == "nan":
        payload["current"][0] = float("nan")
    elif mutation == "bool":
        payload["current"][0] = True
    elif mutation == "negative_execution":
        payload["current"][b.snapshot.FEATURES.index(b.snapshot.EXECUTION_FEATURES[0])] = -1
    elif mutation == "count":
        payload["past"][0][0] = True
    elif mutation == "span":
        payload["past"][0][1] = 2
    elif mutation == "empty_mean":
        payload["past"][0][0] = 0
    elif mutation == "order":
        payload["past"][1][0] = 1
    else:
        payload["future_return"] = 1
    with pytest.raises(ValueError):
        t.prompt(payload)


def test_bad_full_vector_and_noninteger_count_cannot_be_silently_truncated():
    for vector in (np.zeros(108), np.full(109, np.inf)):
        with pytest.raises(ValueError):
            b.compact(vector)
    vector = np.zeros(109)
    vector[b.context.FEATURES.index("past_samples_5s")] = 1.5
    with pytest.raises(ValueError):
        b.compact(vector)


def test_train_fit_gate_before_prompt_or_target_access():
    class Poison(dict):
        def __getitem__(self, key):
            assert key in {"role", "inner_partition"}
            return "train" if key == "role" else "check"

    with pytest.raises(ValueError, match="inner-fit"):
        t.model_view(Poison(), for_training=True)


def test_preparation_uses_all_dense_rows_preserves_targets_and_unknowns(prepared):
    _, output, receipt, completion_pin, plan = prepared
    assert receipt["coverage"]["supervised"] == 448
    assert receipt["files"]["fit.jsonl"]["count"] == 336
    assert receipt["files"]["check.jsonl"]["count"] == 112
    assert receipt["files"]["unavailable.jsonl"]["count"] == 8
    assert b.verified_receipt(output, completion_pin) == receipt
    assert receipt["coverage"]["dense_rows"] > receipt["coverage"]["cases"]
    rows = [r for r, _, _ in b.read_examples(output, "fit", receipt)]
    first, second = (t.payload_from_prompt(r["prompt"]) for r in rows[:2])
    assert first["past"][0][0] == 0 and second["past"][0][0] == 2
    assert second["past"][0][2 + t.HISTORY.index("normalized_cvd_5s")] == 1.5
    unknown = [json.loads(raw) for raw in (output / "unavailable.jsonl").read_text().splitlines()]
    assert all(r["completion"] is None and "prompt" not in r for r in unknown)
    assert all(r["target_status"] == "unavailable:no_entry_quote_timeout" for r in unknown)
    assert receipt["session_split"] == plan["session_split"]
    assert all(receipt[k] is False for k in b.FLAGS)


def test_later_raw_reserved_and_original_unavailable_files_never_opened(evidence, monkeypatch):
    root, path, plan_pin, _ = evidence
    old = Path.open

    def guarded(path, *args, **kwargs):
        assert path.name not in {
            "validation_development.jsonl",
            "test_development.jsonl",
            "unavailable.jsonl",
        } or "context" in str(path)
        assert path.suffix not in {".dbn", ".zip"} and "FORBIDDEN" not in str(path)
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    b.run(root, path, plan_pin, root / "data/processed/context", enable_preparation=True)


@pytest.mark.parametrize("change", ["schema", "input", "target", "role", "reserved", "fields"])
def test_changed_example_binding_refused(prepared, change):
    _, output, receipt, _, _ = prepared
    row = next(b.read_examples(output, "fit", receipt))[0]
    if change == "schema":
        row["schema_sha256"] = "0" * 64
    elif change == "input":
        row["input_sha256"] = "0" * 64
    elif change == "target":
        row["target_sha256"] = "0" * 64
    elif change == "role":
        row["role"] = "test_development"
    elif change == "reserved":
        row["source_session"] = "2026-01-01"
    else:
        row["execution_allowed"] = True
    with pytest.raises(ValueError):
        t.validate_example(row)


@pytest.mark.parametrize("change", ["permission", "source", "split", "rows", "authority"])
def test_registration_change_refused_before_dense_reads(evidence, monkeypatch, change):
    root, path, _, value = evidence
    value = copy.deepcopy(value)
    if change == "permission":
        value["protocol"]["permission"]["model_training"] = True
    elif change == "source":
        value["source_sha256"] = "0" * 64
    elif change == "split":
        value["session_split"]["fit"].append(value["session_split"]["check"][0])
    elif change == "rows":
        value["source_sessions"][0]["rows"]["sha256"] = "0" * 64
    else:
        value["trading_enabled"] = True
    changed = write(path, value)
    monkeypatch.setattr(b.data, "read_rows", lambda *args: pytest.fail("Prohibited source read"))
    with pytest.raises(ValueError):
        b.run(root, path, changed, root / "data/processed/context", enable_preparation=True)


@pytest.mark.parametrize("failure", ["cohort", "original", "missing", "final_input", "timeout"])
def test_failure_never_publishes_subset_or_retries(evidence, monkeypatch, failure):
    root, path, plan_pin, plan = evidence
    output = root / "data/processed/failed-context"
    if failure in {"cohort", "original", "missing"}:
        old = b.data.read_rows

        def changed(root, entry, kind):
            rows = old(root, entry, kind)
            if kind == "cases":
                if failure == "missing":
                    rows.pop()
                elif failure == "cohort":
                    rows[0]["features"]["queue_imbalance"] = 99
                else:
                    rows[0]["path_horizons"] = {"future": "different bound provenance"}
            return rows

        monkeypatch.setattr(b.data, "read_rows", changed)
    elif failure == "final_input":
        old = b.join_session

        def changed(*args, **kwargs):
            yield from old(*args, **kwargs)
            file = root / plan["source_sessions"][0]["rows"]["path"]
            file.write_bytes(file.read_bytes() + b"changed")

        monkeypatch.setattr(b, "join_session", changed)
    else:
        monkeypatch.setattr(b, "MAX_SECONDS", 0)
        # Re-freeze the deliberately expired test budget before running.
        value = json.loads(path.read_text())
        value["protocol"] = b.protocol()
        plan_pin = write(path, value)
    with pytest.raises((ValueError, TimeoutError)):
        b.run(root, path, plan_pin, output, enable_preparation=True)
    assert (output / "failure.json").exists() and not (output / "completion.json").exists()
    with pytest.raises(ValueError, match="New context"):
        b.run(root, path, plan_pin, output, enable_preparation=True)


def test_opt_in_required_before_any_input_access_and_output_cannot_reuse_dataset(evidence):
    root, path, plan_pin, _ = evidence
    with pytest.raises(ValueError, match="opt-in"):
        b.run(root, root / "absent", "bad", root / "unused")
    output = root / "data/processed/context"
    b.run(root, path, plan_pin, output, enable_preparation=True)
    with pytest.raises(ValueError, match="New context"):
        b.run(root, path, plan_pin, output, enable_preparation=True)


def tokens(output, completion_pin, path, encode=lambda _: [10, 11]):
    return b.audit_tokens(
        output,
        completion_pin,
        path,
        encode=encode,
        tokenizer_pin="a" * 64,
        tokenizer_version="fixture",
        eos=151643,
        pad=151643,
    )


def test_all_supervised_tokens_mask_prompt_and_keep_eos_without_model_calls(prepared):
    root, output, receipt, completion_pin, _ = prepared
    report = tokens(output, completion_pin, root / "token-report.json")
    assert report["by_partition"]["fit"]["examples"] == 336
    assert report["by_partition"]["check"]["examples"] == 112
    assert report["unavailable_examples_not_tokenized"] == 8
    assert report["prompt_loss_masked"] and report["completion_and_eos_supervised"]
    assert not report["model_weights_loaded"] and not report["truncation"]
    assert all(report[k] is False for k in b.FLAGS)
    assert pin(output / "completion.json") == completion_pin
    assert receipt["tokenization_verified"] is False  # Never mutate dataset receipt.


@pytest.mark.parametrize("bad", ["long_prompt", "long_answer", "eos", "changed_file", "receipt"])
def test_token_preflight_refuses_truncation_embedded_specials_or_changed_inputs(prepared, bad):
    root, output, _, completion_pin, _ = prepared
    path = root / "refused-token-report.json"

    def encode(text):
        if bad == "long_prompt" and text.startswith(t.PREFIX):
            return [10] * 2049
        if bad == "long_answer" and not text.startswith(t.PREFIX):
            return [10] * 256
        if bad == "eos":
            return [151643]
        return [10, 11]

    if bad == "changed_file":
        file = output / "fit.jsonl"
        file.write_bytes(file.read_bytes() + b"\n")
    elif bad == "receipt":
        value = json.loads((output / "completion.json").read_text())
        value["training_authorized"] = True
        completion_pin = write(output / "completion.json", value)
    with pytest.raises(ValueError):
        tokens(output, completion_pin, path, encode)
    assert not path.exists()


def test_token_preflight_cannot_write_inside_dataset_or_overwrite(prepared):
    root, output, _, completion_pin, _ = prepared
    with pytest.raises(ValueError):
        tokens(output, completion_pin, output / "new-token.json")
    path = root / "new-context-tokens.json"
    tokens(output, completion_pin, path)
    with pytest.raises(ValueError):
        tokens(output, completion_pin, path)


@pytest.mark.parametrize("change", ["extra_authority", "overlap", "missing_day", "counts"])
def test_rehashed_receipt_cannot_change_scope_or_claim_extra_authority(prepared, change):
    _, output, receipt, _, _ = prepared
    receipt = copy.deepcopy(receipt)
    if change == "extra_authority":
        receipt["execution_allowed"] = True
    elif change == "overlap":
        receipt["session_split"]["fit"].append(receipt["session_split"]["check"][0])
    elif change == "missing_day":
        receipt["sessions"].pop()
    else:
        receipt["coverage"]["supervised_by_partition"]["fit"] -= 1
    changed = write(output / "completion.json", receipt)
    with pytest.raises(ValueError):
        b.verified_receipt(output, changed)


def test_pure_context_contract_imports_no_decoder_or_native_model_packages():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; "
            "from ai_trader.training import six_e_context_forecast; "
            "assert not ({'torch','transformers','peft','tokenizers','databento_dbn'} "
            "& set(sys.modules))",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_pure_token_pipeline_imports_without_decoder_or_native_model_packages():
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import sys; from ai_trader.training import six_e_context_tokens; "
            "assert not ({'torch','transformers','peft','tokenizers','databento_dbn'} "
            "& set(sys.modules)); assert len(six_e_context_tokens.source_sha256()) == 64",
        ],
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_token_receipt_binds_current_lightweight_pipeline_and_records_full_builder(prepared):
    root, output, receipt, completion_pin, _ = prepared
    report = tokens(output, completion_pin, root / "new-context-pins.json")
    assert report["dataset_source_sha256"] == receipt["source_sha256"] == b.source_sha256()
    assert report["token_pipeline_sha256"] == b.tokens.source_sha256()
    receipt["token_pipeline_sha256"] = "0" * 64
    changed = write(output / "completion.json", receipt)
    with pytest.raises(ValueError):
        b.tokens.verified_receipt(output, changed)


@pytest.mark.parametrize("field", ["dense_rows_sha256", "contract"])
def test_token_reader_checks_record_binding_to_pinned_source_metadata(prepared, field):
    _, output, receipt, _, _ = prepared
    path = output / "fit.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0][field] = "0" * 64 if field.endswith("sha256") else "6EZ5"
    path.write_text("".join(canonical(r) + "\n" for r in rows), encoding="utf-8")
    receipt["files"]["fit.jsonl"].update(sha256=pin(path), bytes=path.stat().st_size)
    with pytest.raises(ValueError, match="source contract or dense-file"):
        list(b.tokens.read_examples(output, "fit", receipt))
