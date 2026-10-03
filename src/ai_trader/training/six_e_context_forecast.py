"""Pure, compact, versioned 6E causal-context forecast contract; no models or orders."""

from __future__ import annotations

import math

from ai_trader.models.local_checkpoint import canonical, check_digest, digest, strict_json
from ai_trader.training import six_e_forecast as snapshot

TASK = "six_e_quote_opportunity_context_v2"
PARTITIONS = ("fit", "check")
WINDOWS = (5, 15, 30)
DERIVED = ("passive_pressure", "held_support", "other_reload_support", "generic_reload_support")
CURRENT = (*snapshot.FEATURES, *DERIVED, "cvd_price_product", "cvd_held_support_product")
HISTORY = (
    "queue_imbalance",
    "depth5_imbalance",
    "normalized_ofi_5s",
    "normalized_cvd_5s",
    "mid_change_5s_ticks",
    "log_quote_events_5s",
    *DERIVED,
)
MAX_LINE, MAX_PROMPT_BYTES = 32 * 1024, 12 * 1024
PREFIX = (
    "Task: " + TASK + "\nForecast a 6E futures crossed-quote opportunity, not an order. "
    "Same target as v1: 100ms delayed entry, 15s hold, additional total round-trip costs "
    "1/2/4 ticks; positive strictly above zero, otherwise neither_positive. "
    "Return only JSON keys extra_1_tick, extra_2_ticks, extra_4_ticks, each long_positive, "
    "short_positive or neither_positive. More cost cannot create/reverse an opportunity.\n"
    "Inputs are completed receive-time observations only. Current vector order: "
    + canonical(list(CURRENT))
    + ".\nPast rows are ordered by lookback seconds "
    + canonical(list(WINDOWS))
    + "; each row is [prior_sample_count, prior_span_fraction, "
    "then observation-weighted prior means in order " + canonical(list(HISTORY)) + "]. "
    "Past interval [now-window,now) excludes current; reset per session/contract or gap >5s, "
    "including causal quote gaps. Empty history has zero means/count/span. No interpolation. "
    "Mean CVD/OFI snapshots are NOT longer-window raw volume sums. Current minus a past "
    "mean describes change, not a future direction. log_ means log1p; execution quantities "
    "are normalized by current top depth. Derived pressure/support are signed differences; "
    "products multiply CVD by price change or held support. Reload/absorption are observable "
    "proxies, not confirmed icebergs or causal explanations. These futures targets are NOT "
    "EUR/USD CFD fills, measured broker costs or portfolio PnL.\nInputs: "
)
SUFFIX = "\nForecast JSON:"
PROVENANCE = (
    "case_id",
    "source_session",
    "contract",
    "decision_ts_ns",
    "role",
    "inner_partition",
    "source_row_sha256",
    "dense_rows_sha256",
    "causal_prefix_sha256",
    "schema_sha256",
    "original_record_sha256",
    "input_sha256",
)
FIELDS = {*PROVENANCE, "target_sha256", "prompt", "completion"}


def protocol() -> dict:
    return {
        "task": TASK,
        "target_task": snapshot.TASK,
        "current_order": list(CURRENT),
        "history_mean_order": list(HISTORY),
        "windows_seconds": list(WINDOWS),
        "past_row_order": "sample_count, span_fraction, ten prior observation means",
        "float_precision": "Eight significant digits, finite numeric values only",
        "inputs": "43 current values and 36 past values; no dates, exact contracts, roles, "
        "case IDs, eligibility, target availability, outcomes or paths in the prompt",
        "context_version": "causal_6e_context_v1",
        "missingness": "Zero mean/count/span for absent history, never fabricated observations",
        "partitions": list(PARTITIONS),
        "fit_gate": "Train role AND inner-fit partition only, before prompt/target access",
        "target": snapshot.protocol()["supervision"],
        "exposure": "Previously exposed 2025 train-only temporal development, NOT a holdout",
        "prefix": PREFIX,
        "suffix": SUFFIX,
        "bounds": {"line_bytes": MAX_LINE, "prompt_bytes": MAX_PROMPT_BYTES},
        "training_authorized": False,
        "trading_enabled": False,
        "promotion_enabled": False,
        "reserved_outcomes_opened": False,
    }


def schema_sha256() -> str:
    return digest(protocol())


def validate_payload(value: dict) -> None:
    if type(value) is not dict or set(value) != {"current", "past"}:
        raise ValueError("Exact compact causal payload required")
    current, past = value["current"], value["past"]
    if (
        type(current) is not list
        or len(current) != len(CURRENT)
        or type(past) is not list
        or len(past) != len(WINDOWS)
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in current)
    ):
        raise ValueError("Finite aligned compact current/past arrays required")
    snapshot.validate_features(
        dict(zip(snapshot.FEATURES, current[: len(snapshot.FEATURES)], strict=True))
    )
    previous = 0
    for window, row in zip(WINDOWS, past, strict=True):
        if (
            type(row) is not list
            or len(row) != 2 + len(HISTORY)
            or type(row[0]) is not int
            or not previous <= row[0] <= window
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[1:])
            or not 0 <= row[1] <= 1
            or (row[0] == 0 and any(v != 0 for v in row[1:]))
            or (row[0] > 0 and row[1] == 0)
        ):
            raise ValueError("Finite bounded past means, counts and missingness required")
        previous = row[0]


def prompt(value: dict) -> str:
    validate_payload(value)
    text = PREFIX + canonical(value) + SUFFIX
    if len(text.encode()) > MAX_PROMPT_BYTES:
        raise ValueError("Context prompt byte ceiling exceeded; no truncation")
    return text


def payload_from_prompt(text: str) -> dict:
    if type(text) is not str or not text.startswith(PREFIX) or not text.endswith(SUFFIX):
        raise ValueError("Versioned context prompt required")
    value = strict_json(text[len(PREFIX) : -len(SUFFIX)])
    if text != prompt(value):
        raise ValueError("Canonical compact context prompt required")
    return value


def validate_example(row: dict) -> None:
    if row["role"] != "train" or row["inner_partition"] not in PARTITIONS:
        raise ValueError("Train-only inner partition required")
    identity = snapshot.identity(row)  # Refuses reserved calendars before prompt/target.
    if snapshot.role_for_session(identity["source_session"]) != "train":
        raise ValueError("Context example date is outside training")
    if type(row) is not dict or set(row) != FIELDS or row["case_id"] != digest(identity):
        raise ValueError("Context example fields or case identity differ")
    for key in (*[k for k in PROVENANCE if k.endswith("sha256")], "target_sha256"):
        check_digest(row[key])
    if row["schema_sha256"] != schema_sha256():
        raise ValueError("Compact context schema differs")
    value = payload_from_prompt(row["prompt"])
    target = snapshot.parse_completion(row["completion"])
    if (
        digest(value) != row["input_sha256"]
        or canonical(target) != row["completion"]
        or digest(target) != row["target_sha256"]
    ):
        raise ValueError("Changed causal input or unchanged-target binding")


def model_view(row: dict, *, for_training: bool) -> tuple[str, str]:
    if type(for_training) is not bool or (
        for_training and (row["role"] != "train" or row["inner_partition"] != "fit")
    ):
        raise ValueError("Only train/inner-fit examples may enter a fit")
    validate_example(row)
    return row["prompt"], row["completion"]
