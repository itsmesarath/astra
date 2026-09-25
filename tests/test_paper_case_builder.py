"""New runner seam: context ordering, immutable inputs, exact retry and rollback."""

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest
from test_paper_lifecycle import paper_case
from test_paper_runner import buy, tick
from test_paper_runner import runner as runner

from ai_trader.trading.trade_journal import JournalConflict, JournalError


def build(context):
    return replace(
        paper_case(),
        case_id=context.tick.candidate_case_id,
        source_session=context.tick.source_session,
        decision_at_ns=context.tick.observed_at_ns,
        market_state_sha256=context.tick.observation_sha256,
        plan=replace(paper_case().plan, expires_at_ns=context.tick.observed_at_ns + 1000),
    )


def builder(runner, contexts):
    def create(context):
        contexts.append(context)
        return replace(build(context), risk_config_sha256=runner.gateway.config.risk_config_sha256)

    return create


def test_ledger_context_is_immutable_marked_and_bound_to_generated_case(runner):
    contexts = []
    value = tick()
    result = runner.process_with_case_builder(
        value, case_id="built", build_case=builder(runner, contexts)
    )
    assert result.entry_order_id and len(contexts) == 1
    context = contexts[0]
    assert context.checkpoint.observed_at_ns == value.observed_at_ns
    assert context.account.position_btc == 0
    assert context.account.cash_usdt == 1000
    assert context.quote_health == "healthy" and not context.protection_active
    assert runner.journal.get_case("built").mode == "paper"
    with pytest.raises(FrozenInstanceError):
        context.protection_active = True


def test_exact_retry_never_calls_builder_again(runner):
    contexts = []
    result = runner.process_with_case_builder(
        tick(), case_id="built", build_case=builder(runner, contexts)
    )

    def forbidden(context):
        pytest.fail("Retry reassessed the policy.")

    assert runner.process_with_case_builder(tick(), case_id="built", build_case=forbidden) == result
    with pytest.raises(JournalConflict):
        runner.process_with_case_builder(tick(), case_id="different", build_case=forbidden)
    with pytest.raises(JournalConflict):
        runner.process_with_case_builder(
            replace(tick(), features_ready=False), case_id="built", build_case=forbidden
        )


def test_protection_precedes_builder_and_unconditional_entry_is_still_vetoed(runner):
    buy(runner)
    value = tick("stop", 1300, bid_usdt=Decimal("59000"))
    contexts = []
    result = runner.process_with_case_builder(
        value, case_id="after-stop", build_case=builder(runner, contexts)
    )
    assert len(result.exit_order_ids) == 1 and result.entry_order_id is None
    assert result.entry_reason == "protective_exit_tick"
    assert contexts[0].protection_active
    assert contexts[0].account.position_btc == 0
    assert contexts[0].account.realized_pnl_usdt < 0


@pytest.mark.parametrize(
    "change",
    ["wrong_id", "research_mode", "wrong_source", "wrong_hash", "wrong_risk", "wrong_time", "none"],
)
def test_mismatched_builder_case_rolls_back_tick_and_marks(runner, change):
    prior = runner.gateway.risk_checkpoint()

    def bad(context):
        case = builder(runner, [])(context)
        if change == "wrong_id":
            return replace(case, case_id="different")
        if change == "research_mode":
            return replace(case, mode="research_only")
        if change == "wrong_source":
            return replace(case, source_session="different")
        if change == "wrong_hash":
            return replace(case, market_state_sha256="f" * 64)
        if change == "wrong_risk":
            return replace(case, risk_config_sha256="f" * 64)
        if change == "wrong_time":
            return replace(case, decision_at_ns=case.decision_at_ns - 1)
        return None

    with pytest.raises(JournalError, match="context"):
        runner.process_with_case_builder(tick(), case_id="built", build_case=bad)
    assert runner.gateway.risk_checkpoint() == prior
    assert runner.journal.order_ids() == () and runner.get_result(tick().tick_id) is None
    assert runner.journal.get_case("built") is None


def test_sql_side_effects_inside_builder_are_rolled_back(runner):
    prior = runner.gateway.risk_checkpoint()

    def mutating(context):
        runner.journal.append_case(replace(paper_case(), case_id="unexpected"))
        return builder(runner, [])(context)

    with pytest.raises(JournalError, match="changed"):
        runner.process_with_case_builder(tick(), case_id="built", build_case=mutating)
    assert runner.gateway.risk_checkpoint() == prior
    assert runner.journal.get_case("unexpected") is None


def test_builder_exception_rolls_back_protective_fill_with_the_tick(runner):
    buy(runner)
    account = runner.journal.account_state()

    def broken(context):
        assert context.protection_active and context.account.position_btc == 0
        raise RuntimeError("synthetic crash")

    with pytest.raises(RuntimeError):
        runner.process_with_case_builder(
            tick("stop", 1300, bid_usdt=Decimal("59000")),
            case_id="after-stop",
            build_case=broken,
        )
    assert runner.journal.account_state() == account
    assert runner.get_result("stop") is None


def test_existing_case_without_tick_is_not_silently_adopted(runner):
    runner.journal.append_case(paper_case())
    with pytest.raises(JournalConflict, match="already exists"):
        runner.process_with_case_builder(
            tick(), case_id=paper_case().case_id, build_case=builder(runner, [])
        )


def test_approved_generated_case_cannot_bypass_current_gateway_kill_switch(runner):
    runner.gateway.set_kill_switch(True, observed_at_ns=1000)
    result = runner.process_with_case_builder(
        tick(), case_id="built", build_case=builder(runner, [])
    )
    assert runner.journal.get_case("built").risk_verdict == "APPROVED"
    assert result.entry_reason == "risk_rejected:kill_switch_active"
    assert runner.journal.account_state().cash_usdt == 1000
    assert runner.journal.account_state().position_btc == 0


@pytest.mark.parametrize("wrapped", [False, True])
def test_coroutine_builder_is_closed_without_running_and_tick_rolls_back(runner, wrapped):
    prior = runner.gateway.risk_checkpoint()

    async def asynchronous(context):
        pytest.fail("Async code must never run inside the synchronous policy seam.")

    callback = (lambda context: asynchronous(context)) if wrapped else asynchronous
    with pytest.raises(JournalError, match="synchronous"):
        runner.process_with_case_builder(tick(), case_id="built", build_case=callback)
    assert runner.gateway.risk_checkpoint() == prior
    assert runner.get_result(tick().tick_id) is None
