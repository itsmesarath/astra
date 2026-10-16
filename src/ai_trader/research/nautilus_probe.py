"""Bounded synthetic engine evaluation; never a runtime or exchange adapter.

Reference arithmetic is independent of Nautilus. REFERENCE_ONLY is not evidence
that the optional native engine executed successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from importlib.metadata import PackageNotFoundError, version

from ai_trader.risk.engine import OrderIntent, PortfolioRiskState, RiskLimits, evaluate_order

NAUTILUS_VERSION = "1.231.0"
BASE_NS = 1_700_000_000_000_000_000
SECOND = 1_000_000_000
CASES = ("filled", "partial", "risk_veto", "delayed")
D = Decimal
INITIAL_CASH = D("1000")
FEE_RATE = D("0.001")
LIMIT_PRICE = D("60020.00")


class NautilusUnavailable(RuntimeError):
    """Missing, mismatched or unloadable optional native dependency."""


@dataclass(frozen=True)
class BookImage:
    """Complete synthetic image, not a claim of complete Binance depth coverage."""

    event_ns: int
    received_ns: int
    sequence: int
    bids: tuple[tuple[str, str], ...]
    asks: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TradeObservation:
    """Synthetic aggressive buy, used as the one-time decision trigger."""

    event_ns: int
    received_ns: int
    trade_id: str
    price: str
    quantity: str


def fixture() -> tuple[BookImage | TradeObservation, ...]:
    """Return immutable receipt-ordered events with deliberately inverted event times."""
    return (
        BookImage(
            BASE_NS + SECOND,
            BASE_NS + SECOND + 100_000_000,
            1,
            (("60000.00", "0.005000"), ("59990.00", "0.010000")),
            (("60010.00", "0.001000"), ("60020.00", "0.002000")),
        ),
        TradeObservation(BASE_NS + 2 * SECOND, BASE_NS + 2 * SECOND, "1", "60010.00", "0.000100"),
        TradeObservation(BASE_NS + SECOND, BASE_NS + 3 * SECOND, "2", "60010.00", "0.000100"),
        BookImage(
            BASE_NS + SECOND + 500_000_000,
            BASE_NS + 4 * SECOND,
            2,
            (("59980.00", "0.005000"),),
            (("60030.00", "0.010000"),),
        ),
        TradeObservation(BASE_NS + 5 * SECOND, BASE_NS + 5 * SECOND, "3", "60030.00", "0.000100"),
    )


def fixture_hash() -> str:
    payload = [{"kind": type(row).__name__, **asdict(row)} for row in fixture()]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def case_parameters(case: str) -> tuple[Decimal, bool, int]:
    if case not in CASES:
        raise ValueError(f"Unknown evaluation case: {case}")
    return (
        D("0.005" if case == "partial" else "0.003"),
        case == "risk_veto",
        (2_500_000_000 if case == "delayed" else 0),
    )


def risk_verdict(case: str):
    """One entry from a flat synthetic portfolio; not a general gateway adapter."""
    quantity, halted, _ = case_parameters(case)
    return evaluate_order(
        OrderIntent("BUY", quantity, LIMIT_PRICE),
        PortfolioRiskState(D("0"), D("0"), INITIAL_CASH, INITIAL_CASH, halted),
        RiskLimits(D("0.01"), D("0.01"), D("1000"), D("1000"), D("20"), D("30")),
    )


def expected_case(case: str) -> dict:
    """Hand-checkable IOC depth walk at modeled arrival, with fees charged once."""
    quantity, _, delay_ns = case_parameters(case)
    verdict = risk_verdict(case)
    arrival = BASE_NS + 2 * SECOND + delay_ns
    book = [row for row in fixture() if isinstance(row, BookImage) and row.received_ns <= arrival][
        -1
    ]
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        remaining = quantity
        fills = []
        cost = D("0")
        fees = D("0")
        if verdict.approved:
            for price, available in book.asks:
                if D(price) > LIMIT_PRICE or remaining == 0:
                    break
                size = min(remaining, D(available))
                notional = size * D(price)
                fee = (notional * FEE_RATE).quantize(D("0.00000001"))
                fills.append({"price": price, "quantity": str(size), "fee_usdt": str(fee)})
                remaining -= size
                cost += notional
                fees += fee
        return {
            "case": case,
            "risk_reason": verdict.reason,
            "submitted": int(verdict.approved),
            "decision_ask": "60010.00",
            "fills": fills,
            "filled_btc": str(quantity - remaining),
            "cash_usdt": str(INITIAL_CASH - cost - fees),
            "fee_usdt": str(fees),
            "terminal_status": (
                "NOT_SUBMITTED"
                if not verdict.approved
                else "FILLED"
                if remaining == 0
                else "CANCELED"
            ),
            "trade_receipts_ns": [
                row.received_ns for row in fixture() if isinstance(row, TradeObservation)
            ],
        }


def _load_backend():
    try:
        installed = version("nautilus_trader")
    except PackageNotFoundError as error:
        raise NautilusUnavailable(
            "Optional Nautilus evaluation environment is not installed."
        ) from error
    if installed != NAUTILUS_VERSION:
        raise NautilusUnavailable(f"Expected Nautilus {NAUTILUS_VERSION}; found {installed}.")
    try:
        return importlib.import_module("ai_trader.research._nautilus_backend")
    except (ImportError, OSError) as error:
        raise NautilusUnavailable(f"Native dependency failed to load: {error}") from error


def assert_case_matches(actual: dict, expected: dict) -> None:
    """Fail on missing observations, even when aggregate PnL happens to match."""
    for field in ("case", "risk_reason", "submitted", "terminal_status", "trade_receipts_ns"):
        if actual[field] != expected[field]:
            raise AssertionError(f"{expected['case']}: {field} mismatch")
    for field in ("decision_ask", "filled_btc", "cash_usdt", "fee_usdt"):
        if D(actual[field]) != D(expected[field]):
            raise AssertionError(f"{expected['case']}: {field} mismatch")
    if len(actual["fills"]) != len(expected["fills"]):
        raise AssertionError(f"{expected['case']}: fill count mismatch")
    for observed, reference in zip(actual["fills"], expected["fills"], strict=True):
        for field in ("price", "quantity", "fee_usdt"):
            if D(observed[field]) != D(reference[field]):
                raise AssertionError(f"{expected['case']}: fill {field} mismatch")


def evaluate() -> dict:
    backend = _load_backend()
    results = []
    for case in CASES:
        actual = backend.run_case(case)
        assert_case_matches(actual, expected_case(case))
        repeated = backend.run_case(case)
        if actual != repeated:
            raise AssertionError(f"{case}: repeated run differs")
        results.append(actual)
    return {"status": "PASS", "cases": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-only", action="store_true", help="No native engine is run")
    args = parser.parse_args()
    metadata = {
        "schema": "nautilus_synthetic_probe_v1",
        "nautilus_version": NAUTILUS_VERSION,
        "fixture_sha256": fixture_hash(),
        "scope": "synthetic_offline_only",
        "not_validated": ["real_capture_conversion", "queue_priority", "restart", "live_execution"],
    }
    exit_code = 0
    try:
        result = (
            {"status": "REFERENCE_ONLY", "cases": [expected_case(case) for case in CASES]}
            if args.reference_only
            else evaluate()
        )
    except NautilusUnavailable as error:
        result, exit_code = {"status": "BLOCKED", "reason": str(error)}, 2
    except Exception as error:
        result, exit_code = {"status": "FAIL", "reason": str(error)}, 1
    print(json.dumps({**metadata, **result}, indent=2))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
