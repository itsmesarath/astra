"""Portable reference and fail-closed tests; these do not prove native engine behavior."""

import copy
import json
from decimal import Decimal, localcontext
from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace

import pytest

from ai_trader.research import nautilus_probe as probe


def test_fixture_is_receipt_ordered_not_exchange_sorted():
    rows = probe.fixture()
    receipts = [row.received_ns for row in rows]
    assert receipts == sorted(set(receipts))
    assert [row.event_ns for row in rows] != sorted(row.event_ns for row in rows)
    assert len(probe.fixture_hash()) == 64
    assert probe.fixture_hash() == probe.fixture_hash()


def test_exact_two_level_fill_and_fee_accounting():
    result = probe.expected_case("filled")
    assert Decimal(result["filled_btc"]) == Decimal("0.003")
    assert [Decimal(row["quantity"]) for row in result["fills"]] == [
        Decimal("0.001"),
        Decimal("0.002"),
    ]
    assert Decimal(result["fee_usdt"]) == Decimal("0.18005")
    assert Decimal(result["cash_usdt"]) == Decimal("819.76995")
    assert result["terminal_status"] == "FILLED"


def test_partial_does_not_invent_liquidity():
    result = probe.expected_case("partial")
    assert Decimal(result["filled_btc"]) == Decimal("0.003")
    assert result["terminal_status"] == "CANCELED"
    assert result["fills"] == probe.expected_case("filled")["fills"]


def test_risk_veto_submits_nothing():
    result = probe.expected_case("risk_veto")
    assert result["submitted"] == 0
    assert result["risk_reason"] == "kill_switch_active"
    assert result["fills"] == []
    assert Decimal(result["cash_usdt"]) == Decimal("1000")
    assert result["terminal_status"] == "NOT_SUBMITTED"


def test_delayed_order_uses_new_book_but_decision_cannot_see_it():
    result = probe.expected_case("delayed")
    assert result["submitted"] == 1
    assert result["decision_ask"] == "60010.00"
    assert result["fills"] == []
    assert result["terminal_status"] == "CANCELED"


def test_reference_ignores_ambient_decimal_precision():
    expected = probe.expected_case("filled")
    with localcontext() as context:
        context.prec = 6
        assert probe.expected_case("filled") == expected


def test_unknown_case_fails():
    with pytest.raises(ValueError, match="Unknown"):
        probe.expected_case("live")


@pytest.mark.parametrize(
    "field,value",
    [
        ("cash_usdt", "820"),
        ("filled_btc", "0.004"),
        ("fee_usdt", "0"),
        ("decision_ask", "60030"),
        ("submitted", 0),
        ("terminal_status", "OPEN"),
        ("trade_receipts_ns", []),
        ("risk_reason", "ignored"),
    ],
)
def test_comparison_rejects_wrong_engine_results(field, value):
    expected = probe.expected_case("filled")
    actual = copy.deepcopy(expected)
    actual[field] = value
    with pytest.raises(AssertionError):
        probe.assert_case_matches(actual, expected)


def test_comparison_checks_individual_fills():
    expected = probe.expected_case("filled")
    actual = copy.deepcopy(expected)
    actual["fills"][0]["price"] = "60011"
    with pytest.raises(AssertionError, match="fill price"):
        probe.assert_case_matches(actual, expected)
    actual["fills"] = []
    with pytest.raises(AssertionError, match="fill count"):
        probe.assert_case_matches(actual, expected)


def test_missing_dependency_blocks(monkeypatch):
    def missing(_):
        raise PackageNotFoundError("nautilus_trader")

    monkeypatch.setattr(probe, "version", missing)
    with pytest.raises(probe.NautilusUnavailable, match="not installed"):
        probe._load_backend()


def test_wrong_version_blocks_before_import(monkeypatch):
    monkeypatch.setattr(probe, "version", lambda _: "2.0.0")
    with pytest.raises(probe.NautilusUnavailable, match="Expected"):
        probe._load_backend()


@pytest.mark.parametrize(
    "failure", [ImportError("Application Control blocked DLL"), OSError("DLL")]
)
def test_native_load_failure_is_not_a_pass(monkeypatch, failure):
    monkeypatch.setattr(probe, "version", lambda _: probe.NAUTILUS_VERSION)

    def blocked(_):
        raise failure

    monkeypatch.setattr(probe.importlib, "import_module", blocked)
    with pytest.raises(probe.NautilusUnavailable, match="failed to load"):
        probe._load_backend()


def test_reference_cli_does_not_load_engine_or_network(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("No native engine or network")

    monkeypatch.setattr(probe, "_load_backend", forbidden)
    monkeypatch.setattr("socket.socket", forbidden)
    monkeypatch.setattr("sys.argv", ["probe", "--reference-only"])
    probe.main()
    assert json.loads(capsys.readouterr().out)["status"] == "REFERENCE_ONLY"


def test_blocked_cli_reports_nonzero_status(monkeypatch, capsys):
    def blocked():
        raise probe.NautilusUnavailable("native load blocked")

    monkeypatch.setattr(probe, "evaluate", blocked)
    monkeypatch.setattr("sys.argv", ["probe"])
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2
    assert json.loads(capsys.readouterr().out)["status"] == "BLOCKED"


def test_evaluation_repeats_every_case_with_fake_backend(monkeypatch):
    calls = []

    def run_case(case):
        calls.append(case)
        return probe.expected_case(case)

    monkeypatch.setattr(probe, "_load_backend", lambda: SimpleNamespace(run_case=run_case))
    assert probe.evaluate()["status"] == "PASS"
    assert calls == [case for case in probe.CASES for _ in range(2)]


def test_nondeterministic_fake_backend_fails(monkeypatch):
    calls = []

    def run_case(case):
        calls.append(case)
        result = probe.expected_case(case)
        if len(calls) == 2:
            result["cash_usdt"] = "0"
        return result

    monkeypatch.setattr(probe, "_load_backend", lambda: SimpleNamespace(run_case=run_case))
    with pytest.raises(AssertionError, match="repeated run"):
        probe.evaluate()


def test_failed_cli_cannot_report_pass(monkeypatch, capsys):
    def failed():
        raise AssertionError("native cash mismatch")

    monkeypatch.setattr(probe, "evaluate", failed)
    monkeypatch.setattr("sys.argv", ["probe"])
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"
