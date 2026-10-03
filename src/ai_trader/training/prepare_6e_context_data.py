"""Join dense past-only 6E context to immutable train cases; token preflight, never fit."""

from __future__ import annotations

import argparse
import hashlib
import time
from collections import Counter
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

import numpy as np

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.training import causal_6e_context as context
from ai_trader.training import prepare_6e_qwen_data as original
from ai_trader.training import six_e_balance_plan as balance
from ai_trader.training import six_e_context_forecast as task
from ai_trader.training import six_e_context_tokens as tokens
from ai_trader.training.advisory_training_run import _write

data, snapshot = original.data, task.snapshot
KIND = "prepare_6e_train_only_context_v2"
MAX_SECONDS, MAX_DENSE_ROWS, MAX_SOURCE_BYTES = 1200, 2_000_000, 4 * 1024**3
MAX_OUTPUT_BYTES = snapshot.MAX_DATA_BYTES
FLAGS = {
    "training_authorized": False,
    "qwen_trained": False,
    "independent_holdout": False,
    "reserved_outcomes_opened": False,
    "trading_enabled": False,
    "promotion_enabled": False,
    "automatic_retry": False,
}


def protocol() -> dict:
    return {
        "kind": KIND,
        "task": task.protocol(),
        "context": context.protocol(),
        "permission": {"purpose": KIND, "dataset_preparation": True, "model_training": False},
        "scope": "Only train-role dense rows/cases and original train.jsonl; source manifest "
        "metadata and whole-session inner split unchanged; never raw/reserved/later row files",
        "cohort": "All original eligible sixty-second cases, before outcome availability; "
        "every dense observation contributes context, including ineligible/unknown observations",
        "join": "Exact dated session, contract and decision timestamp; cases must equal original "
        "causally thinned dense rows after removing case-only path_horizons; supervised records "
        "must equal the original prepared snapshot examples, including labels and source pins",
        "causal_prefix": "SHA256 of newline-delimited canonical session/contract/partition/time, "
        "features and execution_features through current decision; excludes ALL future fields",
        "encoding": "Full existing 109-column engine; persist 43 current values and three "
        "[count,span,ten means] rows. Redundant current-minus-mean columns omitted; finite "
        "eight-significant-digit rounding, no interpolation or outcome-based history filtering",
        "unknowns": "Unavailable/uncertain target ledger retained, completion null, never negative",
        "bounds": {
            "seconds": MAX_SECONDS,
            "dense_rows": MAX_DENSE_ROWS,
            "source_bytes": MAX_SOURCE_BYTES,
            "output_bytes": MAX_OUTPUT_BYTES,
            "cases": snapshot.MAX_CASES,
        },
        **FLAGS,
    }


def source_sha256() -> str:
    return digest(
        {
            "original_snapshot_builder": original.fingerprints(),
            "frozen_balance_tools": balance.source_sha256(),
            "token_pipeline": tokens.source_sha256(),
            **{
                Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                for m in (context, task)
            },
            Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        }
    )


def make_plan(
    root: Path, manifest_path: Path, manifest_pin: str, balance_path: Path, balance_pin: str
) -> tuple[dict, list[dict]]:
    manifest = data.load(root, manifest_path, manifest_pin)
    prior, request, examples = balance.registration(balance_path, balance_pin)
    receipt = balance.trial.metadata(
        Path(request["dataset"]) / "completion.json", request["dataset_sha256"]
    )
    entries = [e for e in manifest["ledger"] if e["role"] == "train"]
    split = prior["session_split"]
    if (
        receipt["manifest_sha256"] != manifest_pin
        or [e["utc_date"] for e in entries] != split["fit"] + split["check"]
        or context.FEATURES[: len(task.CURRENT)] != task.CURRENT
        or context.HISTORY != task.HISTORY
        or context.WINDOWS != task.WINDOWS
        or snapshot.FEATURES != context.prior.FEATURES
    ):
        raise ValueError("Original dataset/manifest, whole-session split or context layout differs")
    sessions = []
    for e in entries:
        if (
            snapshot.role_for_session(e["utc_date"]) != "train"
            or e["disposition"] != "decision_session"
        ):
            raise ValueError("Only original training decision sessions allowed")
        sessions.append(
            {
                "source_session": e["utc_date"],
                "contract": e["contract"],
                "inner_partition": "fit" if e["utc_date"] in split["fit"] else "check",
                "rows": e["artifacts"]["rows"],
                "cases": e["artifacts"]["cases"],
                "case_accounting": e["case_accounting"],
            }
        )
    coverage = {
        "sessions": len(sessions),
        "dense_rows": sum(s["rows"]["count"] for s in sessions),
        "cases": sum(s["cases"]["count"] for s in sessions),
        "supervised": len(examples),
        "supervised_by_partition": {
            "fit": prior["audits"]["inner_fit"]["examples"],
            "check": prior["audits"]["inner_check"]["examples"],
        },
    }
    if (
        not 1 <= coverage["dense_rows"] <= MAX_DENSE_ROWS
        or not 1 <= coverage["cases"] <= snapshot.MAX_CASES
    ):
        raise ValueError("Registered source coverage exceeds bounds")
    return {
        "kind": KIND,
        "project_root": str(root.resolve()),
        "protocol": protocol(),
        "source_sha256": source_sha256(),
        "cpu_runtime": balance.runtime(),
        "manifest": {"path": str(manifest_path.resolve()), "sha256": manifest_pin},
        "balance_registration": {"path": str(balance_path.resolve()), "sha256": balance_pin},
        "dataset": prior["dataset"],
        "checkpoint_directory": request["checkpoint"],
        "session_split": split,
        "source_sessions": sessions,
        "coverage": coverage,
        **FLAGS,
    }, examples


def freeze(
    root: Path,
    manifest_path: Path,
    manifest_pin: str,
    balance_path: Path,
    balance_pin: str,
    output: Path,
) -> dict:
    plan, _ = make_plan(root, manifest_path, manifest_pin, balance_path, balance_pin)
    # Exclusive metadata output; never overwrite or place it inside immutable inputs.
    balance.evaluation.disjoint(
        output,
        {"dataset": plan["dataset"]["directory"], "checkpoint": plan["checkpoint_directory"]},
        Path(balance_path),
    )
    if output.resolve() == manifest_path.resolve():
        raise ValueError("Registration cannot replace its manifest")
    _write(output, plan)
    return plan


def registration(root: Path, path: Path, pin: str) -> tuple[dict, list[dict]]:
    frozen = balance.trial.metadata(path, pin)
    prior, manifest = frozen["balance_registration"], frozen["manifest"]
    rebuilt, examples = make_plan(
        root, Path(manifest["path"]), manifest["sha256"], Path(prior["path"]), prior["sha256"]
    )
    if canonical(frozen) != canonical(rebuilt):
        raise ValueError("Context registration source, permission, runtime or cohort changed")
    return frozen, examples


def causal_projection(row: dict) -> dict:
    identity = snapshot.identity(row)  # Before features or any future fields.
    if (
        snapshot.role_for_session(identity["source_session"]) != "train"
        or row["partition"] != "development"
    ):
        raise ValueError("Only dense training observations may provide context")
    return {
        **identity,
        "partition": row["partition"],
        "features": row["features"],
        "execution_features": row["execution_features"],
    }


def compact(vector) -> dict:
    vector = np.asarray(vector, dtype=float)
    if vector.shape != (len(context.FEATURES),) or not np.isfinite(vector).all():
        raise ValueError("Finite aligned full context vector required")
    if any(vector[context.FEATURES.index(f"past_samples_{w}s")] % 1 != 0 for w in task.WINDOWS):
        raise ValueError("Integer past observation counts required")

    def rounded(value):
        return float(format(float(value), ".8g"))

    value = {"current": [rounded(v) for v in vector[: len(task.CURRENT)]], "past": []}
    for window in task.WINDOWS:
        value["past"].append(
            [
                int(vector[context.FEATURES.index(f"past_samples_{window}s")]),
                rounded(vector[context.FEATURES.index(f"past_span_fraction_{window}s")]),
                *[
                    rounded(vector[context.FEATURES.index(f"past_mean_{key}_{window}s")])
                    for key in task.HISTORY
                ],
            ]
        )
    task.validate_payload(value)
    return value


def join_session(
    dense: list[dict], cases: list[dict], originals: list[dict], session: dict, *, deadline=None
):
    if (
        session["inner_partition"] not in task.PARTITIONS
        or snapshot.role_for_session(session["source_session"]) != "train"
    ):
        raise ValueError("Training session and exact inner partition required")
    if (
        len(dense) != session["rows"]["count"]
        or len(cases) != session["cases"]["count"]
        or data.accounting(cases) != session["case_accounting"]
        or [{k: v for k, v in r.items() if k != "path_horizons"} for r in cases]
        != data.census.study.diagnostics.thin_causally(dense)
    ):
        raise ValueError("Complete original causal case cohort differs from dense observations")
    state = context.CausalContext(session["source_session"], session["contract"])
    prefix, index, original_index = hashlib.sha256(), 0, 0
    for dense_row in dense:
        balance.deadline_guard(deadline)
        projection = causal_projection(dense_row)
        vector = state.observe(projection)  # The observer never receives future fields.
        prefix.update((canonical(projection) + "\n").encode())
        if index == len(cases) or dense_row["decision_ts_ns"] != cases[index]["decision_ts_ns"]:
            continue
        case = cases[index]
        old, status = original.example(case, "train")
        payload = compact(vector)
        record = {
            **snapshot.identity(case),
            "role": "train",
            "inner_partition": session["inner_partition"],
            "case_id": old["case_id"],
            "source_row_sha256": old["source_row_sha256"],
            "dense_rows_sha256": session["rows"]["sha256"],
            "causal_prefix_sha256": prefix.hexdigest(),
            "schema_sha256": task.schema_sha256(),
            "input_sha256": digest(payload),
            "original_record_sha256": None,
        }
        if status == "supervised":
            if original_index >= len(originals) or old != originals[original_index]:
                raise ValueError("Original snapshot case, label or provenance changed")
            record.update(
                original_record_sha256=digest(old),
                target_sha256=old["target_sha256"],
                completion=old["completion"],
                prompt=task.prompt(payload),
            )
            task.validate_example(record)
            original_index += 1
        else:
            record.update(
                completion=None, target_status=status, outcome_status=case["outcome"]["status"]
            )
        index += 1
        yield record, status, payload
    if index != len(cases) or original_index != len(originals):
        raise ValueError("Missing dense case alignment or leftover original examples")


def run(root: Path, path: Path, pin: str, output: Path, *, enable_preparation=False) -> dict:
    if enable_preparation is not True:
        raise ValueError("Explicit offline context-preparation opt-in required")
    started, root = time.monotonic(), root.resolve()
    deadline = started + MAX_SECONDS
    frozen, examples = registration(root, path, pin)
    if (
        output.exists()
        or output.is_symlink()
        or not output.parent.is_dir()
        or not output.resolve().is_relative_to((root / "data/processed").resolve())
    ):
        raise ValueError("New context dataset directory required inside processed data")
    balance.evaluation.disjoint(
        output,
        {"dataset": frozen["dataset"]["directory"], "checkpoint": frozen["checkpoint_directory"]},
        path,
    )
    output.mkdir(exist_ok=False)
    _write(output / "attempt.json", {"registration_sha256": pin, **FLAGS})
    try:
        files = {
            name: {"count": 0, "bytes": 0, "hash": hashlib.sha256()}
            for name in ("fit.jsonl", "check.jsonl", "unavailable.jsonl")
        }
        daily, total_bytes, source_bytes, total_cases = [], 0, 0, 0
        with ExitStack() as stack:
            handles = {n: stack.enter_context((output / n).open("xb")) for n in files}
            for session in frozen["source_sessions"]:
                balance.deadline_guard(deadline)
                day = session["source_session"]
                print(f"Joining past-only training context {day}", flush=True)
                entry = {
                    "utc_date": day,
                    "role": "train",
                    "disposition": "decision_session",
                    "contract": session["contract"],
                    "artifacts": {k: session[k] for k in ("rows", "cases")},
                }
                for kind in ("rows", "cases"):
                    source_bytes += data.artifact_path(root, session[kind]["path"]).stat().st_size
                if source_bytes > MAX_SOURCE_BYTES:
                    raise ValueError("Dense/case source byte bound exceeded")
                dense, cases = (data.read_rows(root, entry, kind) for kind in ("rows", "cases"))
                selected = [r for r in examples if r["source_session"] == day]
                counts, histories = Counter(), {str(w): Counter() for w in task.WINDOWS}
                for record, status, payload in join_session(
                    dense, cases, selected, session, deadline=deadline
                ):
                    name = (
                        session["inner_partition"] + ".jsonl"
                        if status == "supervised"
                        else "unavailable.jsonl"
                    )
                    raw = (canonical(record) + "\n").encode()
                    total_bytes += len(raw)
                    total_cases += 1
                    if (
                        len(raw) > task.MAX_LINE
                        or total_bytes > MAX_OUTPUT_BYTES
                        or total_cases > snapshot.MAX_CASES
                    ):
                        raise ValueError("Context output framing, cases or byte bound exceeded")
                    handles[name].write(raw)
                    files[name]["count"] += 1
                    files[name]["bytes"] += len(raw)
                    files[name]["hash"].update(raw)
                    counts[status] += 1
                    for window, values in zip(task.WINDOWS, payload["past"], strict=True):
                        histories[str(window)][str(values[0])] += 1
                daily.append(
                    {
                        "source_session": day,
                        "inner_partition": session["inner_partition"],
                        "dense_rows": len(dense),
                        "cases": len(cases),
                        "statuses": dict(counts),
                        "past_sample_histograms_all_cases": {
                            k: dict(v) for k, v in histories.items()
                        },
                    }
                )
        if (
            total_cases != frozen["coverage"]["cases"]
            or files["fit.jsonl"]["count"] + files["check.jsonl"]["count"] != len(examples)
            or any(
                files[p + ".jsonl"]["count"] != frozen["coverage"]["supervised_by_partition"][p]
                for p in task.PARTITIONS
            )
        ):
            raise ValueError("Complete training cohort required, never successful subset")
        final, final_examples = registration(root, path, pin)
        if final != frozen or final_examples != examples:
            raise ValueError("Source registration or original examples changed during join")
        for session in frozen["source_sessions"]:
            balance.deadline_guard(deadline)
            for kind in ("rows", "cases"):
                item = session[kind]
                snapshot.checked_file(
                    data.artifact_path(root, item["path"]),
                    item["sha256"],
                    data.census.MAX_DAY_BYTES,
                )
        stats = {}
        for name, item in files.items():
            checksum = item["hash"].hexdigest()
            snapshot.checked_file(output / name, checksum, MAX_OUTPUT_BYTES)
            stats[name] = {k: v for k, v in item.items() if k != "hash"} | {"sha256": checksum}
        balance.deadline_guard(deadline)
        result = {
            "status": "prepared_train_only_6e_context_v2_not_training_approval",
            "protocol": protocol(),
            "source_sha256": source_sha256(),
            "token_pipeline_sha256": tokens.source_sha256(),
            "registration_sha256": pin,
            "schema_sha256": task.schema_sha256(),
            "coverage": frozen["coverage"],
            "session_split": frozen["session_split"],
            "source_sessions": frozen["source_sessions"],
            "sessions": daily,
            "files": stats,
            "source_bytes_read": source_bytes,
            "elapsed_seconds": time.monotonic() - started,
            "tokenization_verified": False,
            **FLAGS,
        }
        _write(output / "completion.json", result)
        return result
    except BaseException as exc:
        _write(
            output / "failure.json",
            {
                "error_type": type(exc).__name__,
                "incomplete_artifacts_not_training_data": True,
                **FLAGS,
            },
        )
        raise


def verified_receipt(directory: Path, pin: str) -> dict:
    """Builder environment also revalidates the full historical preparation pipeline."""
    value = tokens.verified_receipt(directory, pin)
    if value["protocol"] != protocol() or value["source_sha256"] != source_sha256():
        raise ValueError("Frozen full context preparation pipeline differs")
    return value


read_examples = tokens.read_examples
audit_tokens = tokens.audit_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "tokens"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--balance-registration", type=Path)
    parser.add_argument("--balance-registration-sha256")
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--registration-sha256")
    parser.add_argument("--enable-preparation", action="store_true")
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--completion-sha256")
    parser.add_argument("--tokenizer-json", type=Path)
    parser.add_argument("--tokenizer-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "freeze":
        if any(
            v is None
            for v in (
                args.manifest,
                args.manifest_sha256,
                args.balance_registration,
                args.balance_registration_sha256,
            )
        ):
            parser.error("Pinned source manifest and original balance registration required")
        result = freeze(
            args.project_root,
            args.manifest,
            args.manifest_sha256,
            args.balance_registration,
            args.balance_registration_sha256,
            args.output,
        )
        print(canonical({"kind": result["kind"], "coverage": result["coverage"]}))
    elif args.action == "run":
        if args.registration is None or args.registration_sha256 is None:
            parser.error("Pinned context preparation registration required")
        result = run(
            args.project_root,
            args.registration,
            args.registration_sha256,
            args.output,
            enable_preparation=args.enable_preparation,
        )
        print(
            canonical(
                {
                    "status": result["status"],
                    "coverage": result["coverage"],
                    "elapsed_seconds": result["elapsed_seconds"],
                }
            )
        )
    else:
        if any(
            v is None
            for v in (
                args.dataset,
                args.completion_sha256,
                args.tokenizer_json,
                args.tokenizer_sha256,
            )
        ):
            parser.error("Pinned completed dataset and local tokenizer required")
        result = audit_tokens(
            args.dataset,
            args.completion_sha256,
            args.output,
            encode=original.token_plan.load_tokenizer(args.tokenizer_json, args.tokenizer_sha256),
            tokenizer_pin=args.tokenizer_sha256,
            tokenizer_version=version("tokenizers"),
            eos=151643,
            pad=151643,
        )
        print(canonical({"status": result["status"], "by_partition": result["by_partition"]}))


if __name__ == "__main__":
    main()
