"""Explicit, frozen-plan local Qwen development evaluation; no training or execution."""

import argparse
import os
import time
from dataclasses import replace
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, digest, strict_json
from ai_trader.models.local_reviewer import (
    LocalReviewerConfig,
    LocalReviewError,
    _configuration,
    _exchange,
    build_request,
    prompt_for_contract,
)
from ai_trader.models.review_contracts import LEGACY_V1, REVIEW_CONTRACTS
from ai_trader.research.advisory_evaluation import (
    _validate_suite,
    artifact_contract_fields,
    load_suite,
    model_input,
    read_pinned,
    score_responses,
)

SPLIT = "development_eval"
MAX_MODEL_CALLS = 7
MAX_CASES = 16
TEMPLATE_SESSION = "synthetic-qwen-development"
WORKER = "ai_trader.models._local_review_worker"


def _config_from_plan(plan):
    configuration = dict(plan["configuration_template"])
    for name in ("checkpoint_path", "python_executable"):
        configuration[name] = Path(configuration[name])
    return LocalReviewerConfig(**configuration)


def _prepare(suite, config):
    _validate_suite(suite)
    if (
        type(config) is not LocalReviewerConfig
        or config.backend != "transformers"
        or config.model_id != "Qwen/Qwen3-4B-Base"
        or config.device != "cuda"
        or config.source_session != TEMPLATE_SESSION
        or config.max_calls != 1
        or config.max_input_tokens != 2048
        or config.max_new_tokens != 256
        or config.timeout_ms != 120000
        or config.reply_ttl_ms != 120000
        or config.maximum_evidence_age_ms != 300000
    ):
        raise ValueError("Fixed single-call CUDA Base-model development profile required.")
    selected = tuple(c for c in suite.cases if c.split == SPLIT)
    if not 1 <= len(selected) <= MAX_CASES:
        raise ValueError("Development case budget exceeded or empty selection.")
    entries, requests = [], []
    for case in selected:
        request, refusal = None, None
        try:
            request = build_request(
                replace(config, source_session=case.source_session), "analyst", case.snapshot, ()
            )
        except LocalReviewError as error:
            refusal = str(error)
        entries.append(
            {
                "case_id": case.case_id,
                "input_sha256": digest(model_input(case, config.review_contract)),
                "request_sha256": digest(request) if request is not None else None,
                "preflight_refusal": refusal,
            }
        )
        requests.append(request)
    calls = sum(request is not None for request in requests)
    if not 1 <= calls <= MAX_MODEL_CALLS:
        raise ValueError("Model-call budget exceeded or empty generation selection.")
    return (
        {
            "schema_version": 1,
            "kind": "qwen_advisory_development_plan",
            "suite_sha256": suite.sha256,
            "split": SPLIT,
            "configuration_template": _configuration(config),
            "prompt_sha256": digest(prompt_for_contract(config.review_contract)),
            "worker_module": WORKER,
            "cases": entries,
            "maximum_model_calls": calls,
            "maximum_worker_wait_ms": calls * config.timeout_ms,
            "orders": 0,
            "training_allowed": False,
            "promotion_allowed": False,
        },
        requests,
    )


def prepare_plan(suite, config):
    """Metadata and preflight only: no checkpoint inspection, optional imports or subprocess."""
    return _prepare(suite, config)[0]


def _write(path, value):
    encoded = canonical(value) + "\n"
    if len(encoded.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("Artifact byte budget exceeded.")
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def _event(stream, value):
    stream.write(canonical({**value, "recorded_at_ns": time.time_ns()}) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _invoke(request):
    """Preserve malformed report JSON, but reject invalid transport bindings and expired replies."""
    started = time.monotonic()
    config = request["configuration"]
    raw, status, reason = None, "failed", "worker_or_protocol_failure"
    try:
        stdout = _exchange(
            [config["python_executable"], "-I", "-m", WORKER], request, config["timeout_ms"]
        )
        response = strict_json(stdout)
        if (
            type(response) is not dict
            or set(response) != {"request_sha256", "raw_response"}
            or response["request_sha256"] != digest(request)
            or type(response["raw_response"]) is not str
            or len(response["raw_response"]) > 2048
        ):
            raise LocalReviewError("invalid_worker_binding_or_budget")
        raw = response["raw_response"]
        if (time.monotonic() - started) * 1000 >= config["reply_ttl_ms"]:
            raise LocalReviewError("expired_review")
        status, reason = "completed", "generation_completed_not_semantically_graded"
    except Exception as error:
        if type(error) is LocalReviewError:
            # Only recognized transport codes; never propagate arbitrary provider exception text.
            reason = (
                str(error)
                if str(error)
                in {
                    "worker_deadline",
                    "worker_output_or_pipe_limit",
                    "worker_failed",
                    "invalid_worker_binding_or_budget",
                    "expired_review",
                }
                else "worker_or_protocol_failure"
            )
    return {
        "status": status,
        "raw_response": raw if status == "completed" else None,
        "audit": {
            "reason": reason,
            "elapsed_ms": (time.monotonic() - started) * 1000,
            "rejected_raw_response": raw if status != "completed" else None,
        },
    }


def run_plan(suite, plan, output_dir, *, enable_local_inference=False):
    """At most one attempt per selected case; a worker failure stops the entire batch.

    Claims a new directory and fsyncs intent before dispatch. No resume/retry/recovery inference.
    The local directory/runtime are trusted; this is not signed storage or an OS sandbox.
    """
    if enable_local_inference is not True:
        raise ValueError("Explicit local inference opt-in required.")
    expected, requests = _prepare(suite, _config_from_plan(plan))
    if canonical(expected) != canonical(plan):
        raise ValueError("Frozen plan no longer matches suite, prompt or configuration.")
    if not isinstance(output_dir, Path) or output_dir.is_symlink():
        raise ValueError("Explicit new output directory required.")
    output_dir.mkdir()  # Refuse reuse BEFORE dispatch, including interrupted or failed runs.
    _write(output_dir / "plan.json", plan)
    config = plan["configuration_template"]
    contract = config.get("review_contract", LEGACY_V1)
    envelope = {
        **artifact_contract_fields(contract),
        "suite_sha256": suite.sha256,
        "producer": {
            "kind": "recorded",
            "model_id": config["model_id"],
            "checkpoint_sha256": config["checkpoint_sha256"],
            "prompt_sha256": plan["prompt_sha256"],
        },
        "responses": [],
    }
    calls, stop_reason, interrupted = 0, "all_selected_cases_attempted", False
    started = time.monotonic()
    with (output_dir / "events.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        _event(stream, {"event": "run_started", "plan_sha256": digest(plan)})
        try:
            for entry, request in zip(plan["cases"], requests, strict=True):
                _event(stream, {"event": "case_started", **entry})
                if request is None:
                    outcome = {
                        "status": "preflight_refused",
                        "raw_response": None,
                        "audit": {"reason": entry["preflight_refusal"], "elapsed_ms": 0},
                    }
                else:
                    calls += 1  # Includes failed dispatches; no retry of the same case.
                    outcome = _invoke(request)
                row = {
                    "case_id": entry["case_id"],
                    "input_sha256": entry["input_sha256"],
                    "status": outcome["status"],
                    "raw_response": outcome["raw_response"],
                }
                _event(stream, {"event": "case_finished", "response": row, **outcome["audit"]})
                envelope["responses"].append(row)
                if outcome["status"] == "failed":
                    stop_reason = "stopped_after_worker_failure"
                    break
        except KeyboardInterrupt:
            # _exchange's finally kills its owned worker; retain completed rows without retry.
            stop_reason, interrupted = "interrupted_no_retry", True
        score = score_responses(suite, envelope)
        result = {
            **artifact_contract_fields(contract),
            "kind": "qwen_advisory_development_run",
            "plan_sha256": digest(plan),
            "status": stop_reason,
            "selected_case_count": len(plan["cases"]),
            "worker_attempts": calls,
            "maximum_model_calls": plan["maximum_model_calls"],
            "elapsed_seconds": time.monotonic() - started,
            "responses_sha256": digest(envelope),
            "development_summary": score["by_split"][SPLIT],
            "orders": 0,
            "training_started": False,
            "promotion_allowed": False,
        }
        _write(output_dir / "responses.json", envelope)
        _write(output_dir / "score.json", score)
        _write(output_dir / "run.json", result)
        _event(stream, {"event": "run_finished", **result})
    if interrupted:
        raise KeyboardInterrupt
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Write a plan without running a model")
    prepare.add_argument("--suite", type=Path, required=True)
    prepare.add_argument("--suite-sha256", required=True)
    prepare.add_argument("--checkpoint", type=Path, required=True)
    prepare.add_argument("--checkpoint-sha256", required=True)
    prepare.add_argument("--python-executable", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--review-contract", choices=REVIEW_CONTRACTS, default=LEGACY_V1)
    run = commands.add_parser("run", help="Explicitly execute one frozen development plan")
    run.add_argument("--suite", type=Path, required=True)
    run.add_argument("--plan", type=Path, required=True)
    run.add_argument("--plan-sha256", required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--enable-local-inference", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        suite = load_suite(args.suite, args.suite_sha256)
        config = LocalReviewerConfig(
            TEMPLATE_SESSION,
            backend="transformers",
            model_id="Qwen/Qwen3-4B-Base",
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            python_executable=args.python_executable,
            device="cuda",
            timeout_ms=120000,
            reply_ttl_ms=120000,
            max_calls=1,
            review_contract=args.review_contract,
        )
        plan = prepare_plan(suite, config)
        _write(args.output, plan)
        print(canonical({"prepared_only": True, "plan": plan, "model_calls": 0}))
        return 0
    plan = read_pinned(args.plan, args.plan_sha256)
    suite = load_suite(args.suite, plan["suite_sha256"])
    result = run_plan(
        suite, plan, args.output_dir, enable_local_inference=args.enable_local_inference
    )
    print(canonical(result))
    return 0 if result["development_summary"]["all_machine_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
