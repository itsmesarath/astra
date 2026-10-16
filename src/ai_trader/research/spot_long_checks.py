"""Exact, bounded checks on supplied Spot-long research estimates, never trade authority."""

import re
from dataclasses import asdict
from decimal import Context, Decimal, Inexact, Rounded, localcontext

from ai_trader.models.local_checkpoint import canonical, digest
from ai_trader.research.council import Evidence, ResearchSnapshot

CHECK_VERSION = "spot_long_numeric_v1"
GROSS = "estimated_gross_return_bps"
COST = "estimated_round_trip_cost_bps"
NET = "net_expectancy_bps"
STRESS = "stressed_net_expectancy_bps"
ESTIMATES = (GROSS, COST, NET, STRESS)
RISK_FLAGS = ("kill_switch_active", "daily_loss_limit_reached")
MAX_DIGITS = 64
MAX_EXPONENT = 128
MAX_TIMESTAMP = 2**63 - 1
MAX_INPUT_BYTES = 32 * 1024


def _numeric_domain(value):
    if type(value) is not Decimal or not value.is_finite():
        return False
    parts = value.as_tuple()
    return len(parts.digits) <= MAX_DIGITS and abs(parts.exponent) <= MAX_EXPONENT


def _text(value):
    """Bounded fixed-point text without ambient-context normalization or rounding."""
    if value.is_zero():
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _subtract(gross, cost):
    # Largest exponent spread is 256, with <=64 coefficient digits plus a carry.
    # A fresh Context prevents caller precision/exponent/trap settings changing the result.
    with localcontext(Context(prec=2 * MAX_EXPONENT + MAX_DIGITS + 2, Emin=-512, Emax=512)) as ctx:
        ctx.traps[Inexact] = ctx.traps[Rounded] = True
        return gross - cost


def assess_spot_long(snapshot, source_session, *, maximum_evidence_age_ms=300000):
    """Apply a research-only numeric rubric without case labels, model output or inference.

    Missing risk flags do NOT certify risk clearance. Compatible bps units/horizons and the
    validity/calibration of supplied estimates remain caller assumptions, not proven facts.
    """
    if type(snapshot) is not ResearchSnapshot or any(
        type(e) is not Evidence for e in snapshot.evidence
    ):
        raise ValueError("Typed immutable snapshot and evidence required.")
    if type(source_session) is not str or not re.fullmatch(
        r"[A-Za-z0-9_.:-]{1,128}", source_session
    ):
        raise ValueError("One explicit source-session scope required.")
    if type(maximum_evidence_age_ms) is not int or not 0 <= maximum_evidence_age_ms <= 300000:
        raise ValueError("Evidence-age budget must be an integer within 0-300000 ms.")
    result = {
        "check_version": CHECK_VERSION,
        "source_session": source_session,
        "status": "preflight_refused",
        "reasons": [],
        "input_sha256": None,
        "facts": {},
        "ignored_evidence_ids": [],
        "computed_net_bps": None,
        "net_matches_supplied": None,
        "costs_exceed_gross": None,
        "execution_allowed": False,
        "risk_state_verified": False,
        "calibration_verified": False,
        "rationale_semantics_verified": False,
        "training_export_allowed": False,
    }
    failures = []
    if not 0 <= snapshot.as_of_ms <= MAX_TIMESTAMP:
        failures.append("timestamp_domain")
    for e in snapshot.evidence:
        if e.symbol != snapshot.symbol or e.source_session != source_session:
            failures.append("symbol_or_session_mismatch")
        if not 0 <= e.event_time_ms <= e.available_time_ms <= MAX_TIMESTAMP:
            failures.append("timestamp_domain")
        if e.available_time_ms > snapshot.as_of_ms:
            failures.append("future_evidence")
        if snapshot.as_of_ms - e.event_time_ms > maximum_evidence_age_ms:
            failures.append("stale_evidence")
        if not _numeric_domain(e.value):
            failures.append("numeric_domain")
    if failures:
        result["reasons"] = list(dict.fromkeys(failures))
        return result
    payload = {
        "snapshot": {
            "symbol": snapshot.symbol,
            "as_of_ms": snapshot.as_of_ms,
            "evidence": [{**asdict(e), "value": str(e.value)} for e in snapshot.evidence],
        },
        "source_session": source_session,
        "maximum_evidence_age_ms": maximum_evidence_age_ms,
        "check_version": CHECK_VERSION,
    }
    if len(canonical(payload).encode("utf-8")) > MAX_INPUT_BYTES:
        result["reasons"] = ["input_byte_budget"]
        return result
    result["input_sha256"] = digest(payload)
    grouped = {metric: [] for metric in (*ESTIMATES, *RISK_FLAGS)}
    for e in snapshot.evidence:
        if e.metric in grouped:
            grouped[e.metric].append(e)
        else:
            result["ignored_evidence_ids"].append(e.evidence_id)
    reasons, values = [], {}
    for metric, observations in grouped.items():
        result["facts"][metric] = [
            {"evidence_id": e.evidence_id, "value": _text(e.value)} for e in observations
        ]
        if not observations and metric in ESTIMATES:
            reasons.append("missing_metric:" + metric)
        elif len(observations) > 1:
            reasons.append("duplicate_metric:" + metric)
        elif observations:
            values[metric] = observations[0].value
        if metric in RISK_FLAGS and any(e.value != 0 for e in observations):
            reasons.append("active_risk_flag:" + metric)
    if COST in values and values[COST] < 0:
        reasons.append("negative_cost")
    if GROSS in values and COST in values:
        calculated = _subtract(values[GROSS], values[COST])
        result["computed_net_bps"] = _text(calculated)
        result["costs_exceed_gross"] = values[COST] > values[GROSS]
        if NET in values:
            result["net_matches_supplied"] = values[NET] == calculated
            if not result["net_matches_supplied"]:
                reasons.append("inconsistent_net")
    if NET in values and values[NET] <= 0:
        reasons.append("nonpositive_net")
    if STRESS in values and values[STRESS] <= 0:
        reasons.append("nonpositive_stress")
    result.update(status="veto" if reasons else "conditional_support", reasons=reasons)
    return result
