"""Pure declared 6E tape economics, never a funded account or risk approval.

Consumes the supplied one-contract event/receipt plan without quote access,
policy evaluation, source-file hashing or broker connectivity. Internal tape
consistency is not source authentication or proof of causal executable fills.
Amounts and margins are caller-declared USD assumptions, not current prices,
broker charges, variation-margin settlement or EURUSD CFD execution economics.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from ai_trader.research import six_e_continuous_replay as replay

ledger = replay.ledger
VERSION = "six_e_declared_tape_economics_v1"
STATUS = "declared_tape_economic_projection_not_authenticated"
MAX_MONEY = ledger.MAX_INT
# This is the declared original v1 source-key contract, not a filesystem audit.
SOURCE_NAMES = frozenset(
    """causal_6e_context.py databento_6e_cost_targets.py
    databento_6e_event_scalp.py databento_6e_execution_flow.py
    databento_6e_microdepth.py databento_6e_ofi_scalp.py
    databento_6e_receive_clock.py databento_6e_scenario_replay.py
    databento_6e_seconds_pilot.py databento_6e_training_data.py
    historical_6e_archive.py historical_6e_census_review.py
    historical_6e_clock_diagnostic.py historical_6e_cohort.py
    historical_6e_cohort_v2.py historical_6e_diagnostics.py
    historical_6e_execution_study.py historical_6e_manifest.py
    historical_6e_paths.py historical_6e_refusal_diagnostic.py
    historical_6e_resource_replay.py six_e_auction_features.py
    six_e_auction_playbooks.py six_e_auction_study.py six_e_bracket_study.py
    six_e_bracket_targets.py six_e_continuous_replay.py six_e_crossing_events.py
    six_e_crossing_playbooks.py six_e_crossing_study.py six_e_liquidity.py
    six_e_liquidity_study.py six_e_position_ledger.py standardize.py
    study_6e_triggers.py train_6e_activity_direction.py train_6e_context.py
    train_6e_cost_baseline.py train_6e_microdepth_tree.py train_6e_opportunity.py""".split()
)
RECEIPT_FIELDS = frozenset(
    {
        "version",
        "phase",
        "source_manifest_sha256",
        "scenario_id",
        "policy_id",
        "exit_plan",
        "source_session",
        "contract",
        "native_cursor",
        "executed_at_ns",
        "price_nano",
        "quantity_contracts",
        "position_id",
        "execution_confirmed",
        "broker_execution_confirmed",
    }
)
EVENT_TYPES = (
    ledger.SessionBoundary,
    ledger.EntryFill,
    ledger.ExitIntent,
    ledger.UnresolvedExit,
    ledger.ExitFill,
    ledger.QuoteReference,
)


def _money(value, low=0):
    ledger._integer(value, low, MAX_MONEY)


def _signed_money(value):
    ledger._integer(value, -MAX_MONEY, MAX_MONEY)


@dataclass(frozen=True, slots=True)
class EconomicSeed:
    initial_balance_usd_micros: int
    initialized_at_ns: int

    def __post_init__(self):
        _money(self.initial_balance_usd_micros, 1)
        ledger._integer(self.initialized_at_ns)


@dataclass(frozen=True, slots=True)
class DeclaredMargin:
    initial_usd_micros_per_contract: int
    maintenance_usd_micros_per_contract: int

    def __post_init__(self):
        _money(self.initial_usd_micros_per_contract)
        _money(self.maintenance_usd_micros_per_contract)
        if self.initial_usd_micros_per_contract < self.maintenance_usd_micros_per_contract:
            raise ValueError("Declared initial margin cannot be below maintenance margin")


@dataclass(frozen=True, slots=True)
class DeclaredEconomics:
    account_currency: str
    tick_value_usd_micros: int
    entry_fee_usd_micros_per_contract: int
    exit_fee_usd_micros_per_contract: int
    margin: DeclaredMargin | None

    def __post_init__(self):
        if type(self.account_currency) is not str or self.account_currency != "USD":
            raise ValueError("Explicit USD futures assumptions required; no CFD/currency mapping")
        _money(self.tick_value_usd_micros, 1)
        _money(self.entry_fee_usd_micros_per_contract)
        _money(self.exit_fee_usd_micros_per_contract)
        if self.margin is not None:
            if type(self.margin) is not DeclaredMargin:
                raise ValueError("Typed declared margin or explicit None required")
            DeclaredMargin(**asdict(self.margin))


@dataclass(frozen=True, slots=True)
class EconomicPoint:
    sequence: int
    event_id: str
    event_kind: str
    source_session: str
    observed_at_ns: int
    gross_delta_contract_ticks: int
    gross_delta_usd_micros: int
    entry_fee_debit_usd_micros: int
    exit_fee_debit_usd_micros: int
    cumulative_entry_fees_usd_micros: int
    cumulative_exit_fees_usd_micros: int
    declared_realization_balance_usd_micros: int
    realization_balance_shortfall_usd_micros: int
    remaining_position_contracts: int
    reserved_exit_contracts: int
    reservation_status: str | None
    declared_initial_margin_reserved_usd_micros: int | None
    declared_maintenance_margin_required_usd_micros: int | None
    balance_less_declared_initial_margin_usd_micros: int | None


@dataclass(frozen=True, slots=True)
class DeclaredPendingEntry:
    """A supplied simulator intention, never a broker order or reserved cash proof."""

    position_id: str
    side: str
    decision_ts_ns: int
    target_ns: int
    deadline_ns: int


@dataclass(frozen=True, slots=True)
class DeclaredCheckpoint:
    pending_entry: DeclaredPendingEntry | None
    hold_at_ns: int | None
    exit_deadline_ns: int | None
    cooldown_until_ns: int


@dataclass(frozen=True, slots=True)
class EconomicProjection:
    version: str
    status: str
    seed: EconomicSeed
    assumptions: DeclaredEconomics
    scenario_id: str
    source_manifest_sha256: str
    declared_source_pins: tuple[tuple[str, str], ...]
    path: tuple[EconomicPoint, ...]
    supplied_event_count: int
    matched_receipt_count: int
    terminal_state: ledger.LedgerState
    declared_checkpoint: DeclaredCheckpoint
    gross_realized_usd_micros: int
    entry_fees_usd_micros: int
    exit_fees_usd_micros: int
    declared_realization_balance_usd_micros: int
    realization_balance_shortfall_usd_micros: int
    complete_declared_equity_usd_micros: int | None
    complete_declared_net_return_usd_micros: int | None
    original_complete_simulated_net_contract_ticks: int | None
    declared_initial_margin_reserved_usd_micros: int | None
    declared_maintenance_margin_required_usd_micros: int | None
    balance_less_declared_initial_margin_usd_micros: int | None
    authority_flags: tuple[tuple[str, bool], ...]


def _shape(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(f"Exact {label} fields required")


def _manifest(plan):
    _shape(plan.manifest, {"version", "sessions"}, "declared manifest")
    if plan.manifest["version"] != "six_e_feature_quote_fixture_v1":
        raise ValueError("Original declared feature/quote manifest version required")
    sessions = plan.manifest["sessions"]
    if type(sessions) is not list or not 1 <= len(sessions) <= replay.MAX_SESSIONS:
        raise ValueError("Complete bounded declared session list required")
    days, previous, decisions = {}, None, 0
    for session in sessions:
        _shape(
            session,
            {
                "source_session",
                "contract",
                "role",
                "source_sha256",
                "decisions",
                "decisions_sha256",
                "quotes",
                "quotes_sha256",
            },
            "declared manifest session",
        )
        day = session["source_session"]
        ledger._session(day)  # Calendar/reserved guard, no feature or price access.
        if previous is not None and day <= previous:
            raise ValueError("Unique chronological declared sessions required")
        if session["contract"] != replay.study.census.dated_contract(day) or session[
            "role"
        ] != replay.study.data.role_for_day(day):
            raise ValueError("Declared dated futures contract and development role differ")
        for key in ("source_sha256", "decisions_sha256", "quotes_sha256"):
            ledger._pin(session[key])
        ledger._integer(session["decisions"], 0, 14_400)
        ledger._integer(session["quotes"], 0, replay.MAX_QUOTES)
        decisions += session["decisions"]
        if decisions > replay.MAX_DECISIONS:
            raise ValueError("Declared decision count exceeds the original bound")
        days[day], previous = session, day
    if replay._digest(replay._json(plan.manifest)) != plan.config.source_manifest_sha256:
        raise ValueError("Declared complete manifest content differs from its configuration pin")
    return days


def _checkpoint(value, state, seen_positions, policy):
    _shape(
        value,
        {"pending_entry", "hold_at_ns", "exit_deadline_ns", "cooldown_until_ns"},
        "declared checkpoint",
    )
    for key in ("hold_at_ns", "exit_deadline_ns"):
        if value[key] is not None:
            ledger._integer(value[key])
            if state.position is None:
                raise ValueError("An exit/hold timer requires supplied inventory")
    position, reservation = state.position, state.reservation
    if position is not None:
        if reservation is None:
            if value["hold_at_ns"] != position.executed_at_ns + replay.target.HOLD:
                raise ValueError("Open unreserved inventory requires its original hold timer")
            if value["exit_deadline_ns"] is not None:
                raise ValueError("An exit deadline requires an outstanding reservation")
        elif value["hold_at_ns"] is not None:
            raise ValueError("An exit reservation cannot retain an active hold timer")
        elif reservation.status == "PENDING":
            expected = reservation.requested_at_ns + replay.target.EXIT_DELAY + replay.target.WAIT
            if value["exit_deadline_ns"] != expected:
                raise ValueError("Pending exit requires its original declared deadline")
        elif reservation.status == "UNKNOWN" and value["exit_deadline_ns"] is not None:
            raise ValueError("UNKNOWN cannot acquire a new exit deadline")
    ledger._integer(value["cooldown_until_ns"])
    pending = value["pending_entry"]
    if pending is not None:
        _shape(
            pending,
            {"position_id", "side", "decision_ts_ns", "target_ns", "deadline_ns"},
            "declared pending entry",
        )
        ledger._identifier(pending["position_id"])
        if policy == "no_trade" or pending["position_id"] in seen_positions:
            raise ValueError("Idle policy or previously used position cannot declare a new entry")
        if type(pending["side"]) is not str or pending["side"] not in replay.target.SIDES:
            raise ValueError("Declared pending futures entry side required")
        for key in ("decision_ts_ns", "target_ns", "deadline_ns"):
            ledger._integer(pending[key])
        start, end = replay.target.window(state.current_session)
        if (
            state.entry_recording_blocked
            or pending["target_ns"] != pending["decision_ts_ns"] + replay.target.ENTRY_DELAY
            or pending["deadline_ns"] != pending["target_ns"] + replay.target.WAIT
            or not pending["decision_ts_ns"] <= state.last_observed_at_ns <= pending["deadline_ns"]
            or not start <= pending["decision_ts_ns"] < end
        ):
            raise ValueError("Declared pending entry conflicts with inventory or original clocks")
    return DeclaredCheckpoint(
        None if pending is None else DeclaredPendingEntry(**pending),
        value["hold_at_ns"],
        value["exit_deadline_ns"],
        value["cooldown_until_ns"],
    )


def _receipt(event, wrapped, config, position_id, ordinal, days):
    _shape(wrapped, {"evidence_id", "sha256", "receipt"}, "supplied receipt binding")
    receipt = wrapped["receipt"]
    _shape(receipt, RECEIPT_FIELDS, "original one-contract simulator receipt")
    ledger._identifier(wrapped["evidence_id"])
    ledger._pin(wrapped["sha256"])
    ledger._integer(receipt["native_cursor"], 0, days[event.source_session]["quotes"] - 1)
    start, end = replay.target.window(event.source_session)
    if not start <= event.executed_at_ns < end or event.executed_at_ns != event.observed_at_ns:
        raise ValueError("Original immediate native fill clock required; no delayed broker tape")
    phase = "entry" if type(event) is ledger.EntryFill else "exit"
    expected = {
        "version": replay.protocol()["version"],
        "phase": phase,
        "source_manifest_sha256": config.source_manifest_sha256,
        "scenario_id": config.scenario_id,
        "policy_id": config.policy_id,
        "exit_plan": config.exit_plan,
        "source_session": event.source_session,
        "contract": event.contract,
        "native_cursor": receipt["native_cursor"],
        "executed_at_ns": event.executed_at_ns,
        "price_nano": event.price_nano,
        "quantity_contracts": 1,
        "position_id": position_id,
        "execution_confirmed": False,
        "broker_execution_confirmed": False,
    }
    # Refuse nested/oversized unsupported variants before serializing any value.
    if any(
        type(receipt[key]) is not type(value) or receipt[key] != value
        for key, value in expected.items()
    ):
        raise ValueError("Exact bounded original receipt values and false authority required")
    if (
        wrapped["evidence_id"] != f"receipt-{ordinal:06d}"
        or wrapped["evidence_id"] != event.evidence_id
        or wrapped["sha256"] != event.paper_receipt_sha256
        or replay._digest(replay._json(receipt)) != wrapped["sha256"]
    ):
        raise ValueError(
            "Supplied receipt order, content, identity or exact false authority differs"
        )


def _margin(assumptions, state, balance):
    if assumptions.margin is None:
        return None, None, None
    quantity = 0 if state.position is None else state.position.remaining_contracts
    initial = quantity * assumptions.margin.initial_usd_micros_per_contract
    maintenance = quantity * assumptions.margin.maintenance_usd_micros_per_contract
    remainder = balance - initial
    _money(initial)
    _money(maintenance)
    _signed_money(remainder)
    return initial, maintenance, remainder


def project(
    plan: replay.ReplayPlan,
    seed: EconomicSeed,
    assumptions: DeclaredEconomics,
) -> EconomicProjection:
    """Project the entire declared tape; no file reads, quote inspection or new fills.

    The old extra round-trip friction stays in the original tick comparator only.
    Hypothetical fees are charged at supplied fill observation, not backdated.
    A negative realization balance is retained, not successful-prefix filtered.
    Neither this balance nor balance-minus-margin is a liquidation/free-equity mark.
    """
    if type(plan) is not replay.ReplayPlan or type(seed) is not EconomicSeed:
        raise ValueError("Typed original ReplayPlan and economic seed required")
    if type(assumptions) is not DeclaredEconomics:
        raise ValueError("Typed explicit declared economics required")
    EconomicSeed(**asdict(seed))
    DeclaredEconomics(
        assumptions.account_currency,
        assumptions.tick_value_usd_micros,
        assumptions.entry_fee_usd_micros_per_contract,
        assumptions.exit_fee_usd_micros_per_contract,
        assumptions.margin,
    )
    if type(plan.config) is not ledger.ScenarioConfig:
        raise ValueError("Typed original scenario configuration required")
    ledger.ScenarioConfig(**asdict(plan.config))
    if (
        plan.config.max_position_contracts != 1
        or plan.config.extra_round_trip_ticks_per_contract != replay.target.COST
        or plan.config.policy_id not in replay.POLICIES
        or plan.config.simulator_version != replay.protocol()["version"]
    ):
        raise ValueError("Original one-contract replay protocol required; no partial/multi scope")
    if type(plan.source_pins) is not dict or set(plan.source_pins) != SOURCE_NAMES:
        raise ValueError("Exact original declared v1 source-key identities required")
    for pin in plan.source_pins.values():
        ledger._pin(pin)
    days = _manifest(plan)
    if (
        type(plan.events) is not tuple
        or not 2 * len(days) <= len(plan.events) <= replay.MAX_EVENTS
        or type(plan.receipts) is not tuple
        or len(plan.receipts) > replay.MAX_EVENTS
        or type(plan.terminal_state) is not ledger.LedgerState
    ):
        raise ValueError("Bounded full typed event/receipt tape and terminal state required")
    # Supplied keys/pins bind the declared genesis only. No files are authenticated.
    genesis = ledger._hash(
        ledger._canonical(
            {
                "config": asdict(plan.config),
                "protocol": ledger.protocol(),
                "source_sha256": {
                    key: value
                    for key, value in plan.source_pins.items()
                    if key != "six_e_continuous_replay.py"
                },
            }
        )
    )
    state = ledger.LedgerState(0, genesis, None, 0, None, None, None, 0, 0, 0, 0)
    seen_events, seen_positions, seen_requests, seen_receipts, seen_pins = (
        set(),
        set(),
        set(),
        set(),
        set(),
    )
    boundaries = {day: [] for day in days}
    phases = dict.fromkeys(days, 0)
    fill_cursors = dict.fromkeys(days, -1)
    path, receipt_index = [], 0
    balance, entry_fees, exit_fees = seed.initial_balance_usd_micros, 0, 0
    for event in plan.events:
        if type(event) not in EVENT_TYPES:
            raise ValueError("Original simulator event types only; no cancellation variants")
        if plan.config.policy_id == "no_trade" and type(event) is not ledger.SessionBoundary:
            raise ValueError("The original idle policy cannot declare trades or inventory events")
        raw = ledger._record(event)
        if event.event_id != f"event-{state.sequence + 1:06d}" or event.event_id in seen_events:
            raise ValueError("Full original event sequence and unique identities required")
        seen_events.add(event.event_id)
        if event.source_session not in days or event.observed_at_ns < seed.initialized_at_ns:
            raise ValueError("Supplied event must belong to declared scope after funding")
        start, end = replay.target.window(event.source_session)
        if not start <= event.observed_at_ns <= end:
            raise ValueError("Supplied event must remain in its original declared research window")
        phase = phases[event.source_session]
        if phase == 0:
            if type(event) is not ledger.SessionBoundary or event.observed_at_ns != start:
                raise ValueError("The original start boundary must precede every session event")
            if state.current_session is not None and phases[state.current_session] != 2:
                raise ValueError("The prior session requires its original final boundary")
            phases[event.source_session] = 1
        elif phase == 2:
            raise ValueError("The original end boundary must be the final event of its session")
        elif type(event) is ledger.SessionBoundary:
            if event.observed_at_ns != end:
                raise ValueError("Only the original start/end session boundaries are supported")
            phases[event.source_session] = 2
        if type(event) is ledger.SessionBoundary:
            boundaries[event.source_session].append(event.observed_at_ns)
        if type(event) is ledger.QuoteReference:
            if (
                event.observed_at_ns != end
                or not start <= event.quote_at_ns < end
                or event.native_cursor != days[event.source_session]["quotes"] - 1
            ):
                raise ValueError("Original end-of-session final native reference required")
        if type(event) in (ledger.ExitFill, ledger.UnresolvedExit):
            reservation = state.reservation
            if reservation is None or reservation.status != "PENDING":
                raise ValueError("Only the original PENDING exit may fill or become UNKNOWN once")
            ready = reservation.requested_at_ns + replay.target.EXIT_DELAY
            deadline = ready + replay.target.WAIT
            if type(event) is ledger.ExitFill and not ready <= event.executed_at_ns <= deadline:
                raise ValueError("Exit fill must remain inside the original inclusive wait")
            if type(event) is ledger.UnresolvedExit and event.observed_at_ns != deadline:
                raise ValueError("UNKNOWN requires the exact original exit timeout")
        if hasattr(event, "quantity_contracts") and event.quantity_contracts != 1:
            raise ValueError("One full contract required; no partial/multi-contract tape")
        if type(event) is ledger.EntryFill:
            if event.position_id in seen_positions:
                raise ValueError("Position identity cannot be reused")
            seen_positions.add(event.position_id)
        if type(event) is ledger.ExitIntent:
            if event.request_id in seen_requests:
                raise ValueError("Exit request identity cannot be reused")
            seen_requests.add(event.request_id)
        entry_debit = exit_debit = 0
        if type(event) in (ledger.EntryFill, ledger.ExitFill):
            if receipt_index >= len(plan.receipts):
                raise ValueError("Every supplied fill requires its exact ordered receipt")
            position_id = (
                event.position_id
                if type(event) is ledger.EntryFill
                else (None if state.position is None else state.position.position_id)
            )
            _receipt(
                event,
                plan.receipts[receipt_index],
                plan.config,
                position_id,
                receipt_index + 1,
                days,
            )
            cursor = plan.receipts[receipt_index]["receipt"]["native_cursor"]
            if cursor <= fill_cursors[event.source_session]:
                raise ValueError("Original same-session fill cursors must advance strictly")
            fill_cursors[event.source_session] = cursor
            if event.evidence_id in seen_receipts or event.paper_receipt_sha256 in seen_pins:
                raise ValueError("Receipt identities/pins cannot be reused")
            seen_receipts.add(event.evidence_id)
            seen_pins.add(event.paper_receipt_sha256)
            receipt_index += 1
            if type(event) is ledger.EntryFill:
                entry_debit = assumptions.entry_fee_usd_micros_per_contract
            else:
                exit_debit = assumptions.exit_fee_usd_micros_per_contract
        before = state.closed_gross_contract_ticks
        tip = ledger._hash(state.tip_sha256.encode() + b"\n" + raw)
        state = replace(
            ledger._apply(state, event, plan.config),
            sequence=state.sequence + 1,
            tip_sha256=tip,
        )
        delta_ticks = state.closed_gross_contract_ticks - before
        delta_usd = delta_ticks * assumptions.tick_value_usd_micros
        balance += delta_usd - entry_debit - exit_debit
        entry_fees += entry_debit
        exit_fees += exit_debit
        for amount in (delta_usd, balance):
            _signed_money(amount)
        _money(entry_fees)
        _money(exit_fees)
        initial, maintenance, remainder = _margin(assumptions, state, balance)
        path.append(
            EconomicPoint(
                state.sequence,
                event.event_id,
                type(event).__name__,
                event.source_session,
                event.observed_at_ns,
                delta_ticks,
                delta_usd,
                entry_debit,
                exit_debit,
                entry_fees,
                exit_fees,
                balance,
                max(0, -balance),
                0 if state.position is None else state.position.remaining_contracts,
                0 if state.reservation is None else state.reservation.remaining_contracts,
                None if state.reservation is None else state.reservation.status,
                initial,
                maintenance,
                remainder,
            )
        )
    if receipt_index != len(plan.receipts):
        raise ValueError("Unused receipts forbid successful-subset economic projection")
    if any(boundaries[day] != list(replay.target.window(day)) for day in days):
        raise ValueError("Both original boundaries of every declared session required")
    if replay._json(asdict(state)) != replay._json(asdict(plan.terminal_state)):
        raise ValueError("Full reconstructed declared terminal state/head differs")
    checkpoint = _checkpoint(plan.checkpoint, state, seen_positions, plan.config.policy_id)
    uncertain = (
        checkpoint.pending_entry is not None
        or checkpoint.hold_at_ns is not None
        or (checkpoint.exit_deadline_ns is not None)
    )
    complete = state.position is None and state.reservation is None and not uncertain
    gross = state.closed_gross_contract_ticks * assumptions.tick_value_usd_micros
    _signed_money(gross)
    if balance != seed.initial_balance_usd_micros + gross - entry_fees - exit_fees:
        raise ValueError("Declared economic conservation failed")
    net_return = balance - seed.initial_balance_usd_micros
    _signed_money(net_return)
    initial, maintenance, remainder = _margin(assumptions, state, balance)
    flags = {
        **replay._flags(),
        "source_files_authenticated": False,
        "cash_balance_confirmed": False,
        "margin_requirement_confirmed": False,
        "risk_approved": False,
        "cfd_execution_confirmed": False,
    }
    return EconomicProjection(
        VERSION,
        STATUS,
        seed,
        assumptions,
        plan.config.scenario_id,
        plan.config.source_manifest_sha256,
        tuple(sorted(plan.source_pins.items())),
        tuple(path),
        len(plan.events),
        receipt_index,
        state,
        checkpoint,
        gross,
        entry_fees,
        exit_fees,
        balance,
        max(0, -balance),
        balance if complete else None,
        net_return if complete else None,
        state.complete_simulated_net_contract_ticks,
        initial,
        maintenance,
        remainder,
        tuple(sorted(flags.items())),
    )
