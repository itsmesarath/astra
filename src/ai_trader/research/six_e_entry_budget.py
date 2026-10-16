"""Pure declared one-contract entry budgeting on a supplied observed prefix.

No files, quotes, policy, fills, account mutation or reservation lifecycle are
accessed. Supplied cash, clocks and journal identities are not authenticated.
An available declared budget never grants trading, training or risk approval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from ai_trader.research import six_e_declared_economics as economics

ledger = economics.ledger
EconomicSeed = economics.EconomicSeed
DeclaredEconomics = economics.DeclaredEconomics
VERSION = "six_e_declared_entry_budget_v1"
STATUS = "declared_entry_budget_assessment_not_authenticated"
AUTHORITY_FLAGS = tuple(
    sorted(
        {
            **economics.replay._flags(),
            "source_files_authenticated": False,
            "snapshot_prefix_authenticated": False,
            "cash_balance_confirmed": False,
            "margin_requirement_confirmed": False,
            "risk_approved": False,
            "cfd_execution_confirmed": False,
            "reservation_created": False,
        }.items()
    )
)


def _money(value, low=0):
    ledger._integer(value, low, economics.MAX_MONEY)


def _signed(value):
    ledger._integer(value, -economics.MAX_MONEY, economics.MAX_MONEY)


@dataclass(frozen=True, slots=True)
class DeclaredCapitalSnapshot:
    seed: EconomicSeed
    declared_realization_balance_usd_micros: int
    sequence: int
    tip_sha256: str
    last_event_at_ns: int | None
    observed_through_ns: int
    remaining_position_contracts: int
    reserved_exit_contracts: int
    reservation_status: str | None
    pending_entry: bool

    def __post_init__(self):
        if type(self.seed) is not EconomicSeed:
            raise ValueError("Typed original economic seed required")
        EconomicSeed(**asdict(self.seed))
        _signed(self.declared_realization_balance_usd_micros)
        ledger._integer(self.sequence)
        ledger._pin(self.tip_sha256)
        ledger._integer(self.observed_through_ns, self.seed.initialized_at_ns)
        ledger._integer(self.remaining_position_contracts, 0, 1)
        ledger._integer(self.reserved_exit_contracts, 0, 1)
        if type(self.pending_entry) is not bool:
            raise ValueError("Exact Boolean pending-entry declaration required")
        if self.reservation_status is not None and (
            type(self.reservation_status) is not str
            or self.reservation_status not in ("PENDING", "UNKNOWN")
        ):
            raise ValueError("Only original PENDING/UNKNOWN exit reservations supported")
        if (
            self.reserved_exit_contracts > self.remaining_position_contracts
            or (self.reservation_status is None) != (self.reserved_exit_contracts == 0)
            or (
                self.pending_entry
                and (self.remaining_position_contracts or self.reserved_exit_contracts)
            )
        ):
            raise ValueError("Consistent one-contract inventory/reservation/pending state required")
        if self.sequence == 0:
            if (
                self.last_event_at_ns is not None
                or self.declared_realization_balance_usd_micros
                != self.seed.initial_balance_usd_micros
                or self.remaining_position_contracts
                or self.reserved_exit_contracts
                or self.pending_entry
            ):
                raise ValueError("Genesis prefix has no event, charge, inventory or pending entry")
        else:
            ledger._integer(
                self.last_event_at_ns, self.seed.initialized_at_ns, self.observed_through_ns
            )


@dataclass(frozen=True, slots=True)
class EntryProposal:
    decision_at_ns: int
    expected_sequence: int
    expected_tip_sha256: str
    contract: str
    quantity_contracts: int

    def __post_init__(self):
        ledger._integer(self.decision_at_ns)
        ledger._integer(self.expected_sequence)
        ledger._pin(self.expected_tip_sha256)
        if type(self.contract) is not str or self.contract not in ledger.CONTRACTS:
            raise ValueError("Explicit supported dated 6E futures contract required; no CFD")
        ledger._integer(self.quantity_contracts, 1, 1)


@dataclass(frozen=True, slots=True)
class DeclaredBudgetLimits:
    cash_buffer_usd_micros: int
    max_snapshot_age_ns: int
    max_cumulative_realization_loss_usd_micros: int | None

    def __post_init__(self):
        _money(self.cash_buffer_usd_micros)
        ledger._integer(self.max_snapshot_age_ns)
        if self.max_cumulative_realization_loss_usd_micros is not None:
            _money(self.max_cumulative_realization_loss_usd_micros)


@dataclass(frozen=True, slots=True)
class DeclaredBudgetDecision:
    version: str
    status: str
    disposition: str
    snapshot: DeclaredCapitalSnapshot
    proposal: EntryProposal
    economics: DeclaredEconomics
    limits: DeclaredBudgetLimits
    snapshot_age_ns: int
    realization_loss_from_original_seed_usd_micros: int
    hypothetical_loss_after_entry_fee_usd_micros: int
    declared_requirement_usd_micros: int | None
    declared_balance_less_requirement_usd_micros: int | None
    declared_budget_condition_met: bool | None
    reasons: tuple[str, ...]
    authority_flags: tuple[tuple[str, bool], ...]


def assess_entry_budget(
    snapshot: DeclaredCapitalSnapshot,
    proposal: EntryProposal,
    economics: DeclaredEconomics,
    limits: DeclaredBudgetLimits,
) -> DeclaredBudgetDecision:
    """Explain supplied prefix affordability, without admission, fee debit or reservation.

    The frontier asserts observation completeness, separately from event time;
    it proves neither feed health nor native equal-time publication order. This
    stateless function cannot detect caller re-seeding or authenticate an original
    prefix. Future integration must bind that seed and prefix before admission.
    Loss is net realization loss from the original seed, not gross losses or peak
    drawdown. Only the proposed entry fee enters its hypothetical next loss; exit
    reserves, margin and buffer are commitments, never already charged fees.
    """
    for value, cls in (
        (snapshot, DeclaredCapitalSnapshot),
        (proposal, EntryProposal),
        (economics, DeclaredEconomics),
        (limits, DeclaredBudgetLimits),
    ):
        if type(value) is not cls:
            raise ValueError("Exact typed immutable budgeting inputs required")
    # Reconstruct solely to validate even deliberately altered frozen instances.
    replace(snapshot)
    replace(proposal)
    replace(limits)
    DeclaredEconomics(
        economics.account_currency,
        economics.tick_value_usd_micros,
        economics.entry_fee_usd_micros_per_contract,
        economics.exit_fee_usd_micros_per_contract,
        economics.margin,
    )
    if (
        proposal.expected_sequence != snapshot.sequence
        or proposal.expected_tip_sha256 != snapshot.tip_sha256
        or proposal.decision_at_ns < snapshot.observed_through_ns
    ):
        raise ValueError("Exact pre-proposal prefix identity and nonfuture frontier required")
    age = proposal.decision_at_ns - snapshot.observed_through_ns
    balance = snapshot.declared_realization_balance_usd_micros
    after_entry_fee = balance - economics.entry_fee_usd_micros_per_contract
    _signed(after_entry_fee)
    loss = max(0, snapshot.seed.initial_balance_usd_micros - balance)
    proposed_loss = max(0, snapshot.seed.initial_balance_usd_micros - after_entry_fee)
    _money(loss)
    _money(proposed_loss)
    required = remainder = None
    if economics.margin is not None:
        required = (
            economics.entry_fee_usd_micros_per_contract
            + economics.margin.initial_usd_micros_per_contract
            + economics.exit_fee_usd_micros_per_contract
            + limits.cash_buffer_usd_micros
        )
        _money(required)
        remainder = balance - required
        _signed(remainder)
    blocked = tuple(
        reason
        for condition, reason in (
            (snapshot.remaining_position_contracts > 0, "inventory_present"),
            (snapshot.reserved_exit_contracts > 0, "exit_reservation_present"),
            (snapshot.pending_entry, "pending_entry_present"),
        )
        if condition
    )
    if blocked:
        disposition, met, reasons = "entry_blocked_by_liability", False, blocked
    elif age > limits.max_snapshot_age_ns:
        disposition, met, reasons = "budget_undetermined", None, ("stale_snapshot",)
    elif required is None:
        disposition, met, reasons = "budget_undetermined", None, ("margin_not_declared",)
    else:
        insufficient = []
        if balance < required:
            insufficient.append("insufficient_declared_cash")
        ceiling = limits.max_cumulative_realization_loss_usd_micros
        if ceiling is not None:
            if loss > ceiling:
                insufficient.append("realization_loss_ceiling_exceeded")
            elif proposed_loss > ceiling:
                insufficient.append("proposed_entry_fee_exceeds_loss_ceiling")
        disposition = (
            "declared_budget_insufficient" if insufficient else "declared_budget_available"
        )
        met, reasons = not insufficient, tuple(insufficient)
    return DeclaredBudgetDecision(
        VERSION,
        STATUS,
        disposition,
        snapshot,
        proposal,
        economics,
        limits,
        age,
        loss,
        proposed_loss,
        required,
        remainder,
        met,
        reasons,
        AUTHORITY_FLAGS,
    )
