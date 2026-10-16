"""Draft Qwen training preflight and completion-only masks; never fits or loads model weights."""

import argparse
import hashlib
from pathlib import Path

from ai_trader.models.local_checkpoint import canonical, check_digest, digest
from ai_trader.models.review_contracts import SPOT_LONG_V2, SPOT_LONG_V2_PROMPT, base_review_prompt
from ai_trader.research.advisory_evaluation import load_suite, model_input, read_pinned
from ai_trader.research.council import parse_role_report
from ai_trader.research.spot_long_checks import assess_spot_long
from ai_trader.training.advisory_curriculum import _write_new, audit_review
from ai_trader.training.advisory_holdout import audit_reservation, reservation_template

TOKEN_PROTOCOL = "qwen_base_separate_completion_eos_v1"
MAX_PROMPT_TOKENS = 2048
MAX_COMPLETION_TOKENS = 256  # Includes one explicitly appended EOS.
MAX_SEQUENCE_TOKENS = MAX_PROMPT_TOKENS + MAX_COMPLETION_TOKENS
IGNORE_INDEX = -100


def _token_id(value):
    if type(value) is not int or not 0 <= value < 1_000_000:
        raise ValueError("Token IDs must be bounded nonnegative integers.")


def completion_only_record(prompt_ids, completion_ids, *, eos_token_id, pad_token_id):
    """Unshifted causal-LM labels; preserve EOS loss even when padding uses the EOS ID."""
    _token_id(eos_token_id)
    _token_id(pad_token_id)
    for sequence, limit in (
        (prompt_ids, MAX_PROMPT_TOKENS),
        (completion_ids, MAX_COMPLETION_TOKENS - 1),
    ):
        if type(sequence) not in (list, tuple) or not 1 <= len(sequence) <= limit:
            raise ValueError("Empty/oversized token sequence; no truncation.")
        for token in sequence:
            _token_id(token)
            if token in (eos_token_id, pad_token_id):
                raise ValueError("Embedded EOS/padding token refused.")
    prompt, answer = list(prompt_ids), [*completion_ids, eos_token_id]
    length = len(prompt) + len(answer)
    padding = MAX_SEQUENCE_TOKENS - length
    return {
        "input_ids": prompt + answer + [pad_token_id] * padding,
        "attention_mask": [1] * length + [0] * padding,
        "labels": [IGNORE_INDEX] * len(prompt) + answer + [IGNORE_INDEX] * padding,
    }


def proposed_recipe():
    """Resource ceilings for a future smoke worker, not an implemented optimization run."""
    return {
        "model_id": "Qwen/Qwen3-4B-Base",
        "method": "lora",
        "lora_rank": 8,
        "lora_alpha": 16,
        "lora_dropout": "0",
        "target_modules": ["q_proj", "v_proj"],
        "base_weights_frozen": True,
        "dtype": "bfloat16",
        "quantization": "none",
        "optimizer": "adamw",
        "learning_rate": "0.0002",
        "max_grad_norm": "1",
        "seed": 42,
        "batch_size": 1,
        "gradient_accumulation_steps": 1,
        "max_optimizer_steps": 20,
        "max_wall_time_seconds": 600,
        "max_retries": 0,
        "gradient_checkpointing": True,
        "use_cache": False,
        "loss": "completion_and_eos_only",
        "token_protocol": TOKEN_PROTOCOL,
        "max_prompt_tokens": MAX_PROMPT_TOKENS,
        "max_completion_tokens_including_eos": MAX_COMPLETION_TOKENS,
        "max_sequence_tokens": MAX_SEQUENCE_TOKENS,
        "limits_enforced_by_training_worker": False,
    }


def prepare_training_plan(
    suite,
    review,
    registry,
    *,
    encode=None,
    tokenizer_sha256=None,
    eos_token_id=None,
    pad_token_id=None,
):
    """Inspect draft targets too, but never claim that tokenizing them approves training."""
    review_report = audit_review(suite, review)
    protection = audit_reservation(suite, registry)
    if encode is not None:
        if not callable(encode):
            raise ValueError("Explicit tokenizer callable required.")
        check_digest(tokenizer_sha256)
        _token_id(eos_token_id)
        _token_id(pad_token_id)
    elif any(v is not None for v in (tokenizer_sha256, eos_token_id, pad_token_id)):
        raise ValueError("Tokenizer metadata without tokenization is not a verified preflight.")
    cases = {c.case_id: c for c in suite.cases}
    rows = []
    for reviewed in review["cases"]:
        case = cases[reviewed["case_id"]]
        row = {
            "case_id": case.case_id,
            "decision": reviewed["decision"],
            "input_sha256": digest(model_input(case, SPOT_LONG_V2)),
            "target_sha256": digest(reviewed["target_response"]),
            "status": "excluded_rejection",
            "prompt_tokens": None,
            "completion_tokens": None,
            "supervised_tokens": None,
            "record_sha256": None,
        }
        if reviewed["decision"] == "reject":
            rows.append(row)
            continue
        try:
            report = parse_role_report(reviewed["target_response"], "analyst", case.snapshot)
            assessment = assess_spot_long(case.snapshot, case.source_session)
            numeric = {"veto": "veto", "conditional_support": "support"}.get(assessment["status"])
            if (
                report.verdict != case.expected
                or report.verdict != numeric
                or not all(set(g) & set(report.evidence_ids) for g in case.citation_groups)
            ):
                raise ValueError("Proposal verdict/citations do not match evidence.")
        except (ValueError, TypeError, RecursionError):
            row["status"] = "proposal_refused"
        else:
            row["status"] = "tokenizer_not_run"
            if encode is not None:
                try:
                    prompt = base_review_prompt(
                        SPOT_LONG_V2_PROMPT, model_input(case, SPOT_LONG_V2)
                    )
                    # Preserve the exact inference prefix. Do NOT retokenize prompt+completion
                    # jointly: BPE can merge across their boundary and change the loss mask.
                    prompt_ids = encode(prompt)
                    completion_ids = encode(reviewed["target_response"])
                    record = completion_only_record(
                        prompt_ids,
                        completion_ids,
                        eos_token_id=eos_token_id,
                        pad_token_id=pad_token_id,
                    )
                except (ValueError, TypeError):
                    row["status"] = "tokenization_refused"
                else:
                    row.update(
                        status="tokenized_proposal",
                        prompt_tokens=len(prompt_ids),
                        completion_tokens=len(completion_ids),
                        supervised_tokens=len(completion_ids) + 1,
                        record_sha256=digest(record),
                    )
        rows.append(row)
    blockers = []
    if not review_report["candidate_export_allowed"]:
        blockers.append("curriculum_review_incomplete")
    if not protection["reservation_complete"]:
        blockers.append("protected_evaluation_reservation_incomplete")
    if encode is None:
        blockers.append("tokenizer_preflight_not_run")
    if any(r["status"] in ("proposal_refused", "tokenization_refused") for r in rows):
        blockers.append("proposal_preflight_failed")
    blockers.extend(("optimization_worker_not_implemented", "training_environment_not_verified"))
    return {
        "schema_version": 1,
        "kind": "draft_advisory_training_plan_v1",
        "suite_sha256": suite.sha256,
        "review_sha256": digest(review),
        "registry_sha256": digest(registry),
        "review_contract": SPOT_LONG_V2,
        "prompt_sha256": digest(SPOT_LONG_V2_PROMPT),
        "tokenizer_sha256": tokenizer_sha256,
        "eos_token_id": eos_token_id,
        "pad_token_id": pad_token_id,
        "recipe": proposed_recipe(),
        "proposal_checks": rows,
        "review_audit": review_report,
        "protection_audit": protection,
        "blockers": blockers,
        "training_allowed": False,
        "weights_loaded": False,
        "optimization_steps": 0,
        "model_calls": 0,
        "orders": 0,
        "promotion_allowed": False,
        "execution_allowed": False,
    }


def load_tokenizer(path, expected_sha256):
    """Optional local CPU tokenizer only, loaded from bounded pinned bytes; no model imports."""
    check_digest(expected_sha256)
    if not isinstance(path, Path) or path.is_symlink() or not path.is_file():
        raise ValueError("Explicit regular local tokenizer JSON required.")
    with path.open("rb") as stream:
        raw = stream.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("Tokenizer size or SHA256 mismatch.")
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_str(raw.decode("utf-8"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    return lambda text: tokenizer.encode(text, add_special_tokens=False).ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("reserve-template", "prepare"))
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--suite-sha256", required=True)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--review-sha256")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--registry-sha256")
    parser.add_argument("--tokenizer-json", type=Path)
    parser.add_argument("--tokenizer-sha256")
    parser.add_argument("--eos-token-id", type=int)
    parser.add_argument("--pad-token-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare = args.action == "prepare"
    if any(
        bool(v) != prepare
        for v in (args.review, args.review_sha256, args.registry, args.registry_sha256)
    ):
        parser.error("Prepare requires review/registry paths and pins; template accepts neither.")
    tokenizer_values = (
        args.tokenizer_json,
        args.tokenizer_sha256,
        args.eos_token_id,
        args.pad_token_id,
    )
    enabled = any(v is not None for v in tokenizer_values)
    if enabled and (not prepare or any(v is None for v in tokenizer_values)):
        parser.error("Optional tokenizer requires JSON/pin and both token IDs, only with prepare.")
    suite = load_suite(args.suite, args.suite_sha256)
    if not prepare:
        result = reservation_template(suite)
    else:
        review = read_pinned(args.review, args.review_sha256)
        registry = read_pinned(args.registry, args.registry_sha256)
        # Validate bindings before loading the optional native tokenizer.
        prepare_training_plan(suite, review, registry)
        encode = load_tokenizer(args.tokenizer_json, args.tokenizer_sha256) if enabled else None
        result = prepare_training_plan(
            suite,
            review,
            registry,
            encode=encode,
            tokenizer_sha256=args.tokenizer_sha256,
            eos_token_id=args.eos_token_id,
            pad_token_id=args.pad_token_id,
        )
    _write_new(args.output, result)
    print(
        canonical({"kind": result["kind"], "output": str(args.output), "training_allowed": False})
    )
    return 0  # Artifact preparation only; inspect the explicit blockers, not the exit code.


if __name__ == "__main__":
    raise SystemExit(main())
