from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from enum import Enum
from itertools import combinations
from typing import Optional

from .config import FinancialDefaults
from .domain import FinancialResult, FinancialScenario
from .financial_engine import calculate_financial_scenario


ZERO = Decimal("0")
ONE = Decimal("1")
TWELVE = Decimal("12")

# Numerical verification tolerances.
#
# These tolerances exist only to absorb Decimal residuals generated
# when analytical boundaries are recalculated through the Financial Engine.
# They are not business tolerances and must never be used to relax
# configured financial targets.
MONEY_EPSILON = Decimal("0.01")
RATIO_EPSILON = Decimal("0.000000001")


class SimulationVariablePolicy(str, Enum):
    LOCKED = "LOCKED"
    ADJUSTABLE = "ADJUSTABLE"


class OptimizationObjective(str, Enum):
    MAXIMIZE_PROPERTY_PRICE = "MAXIMIZE_PROPERTY_PRICE"
    MINIMIZE_REQUIRED_CHANGE = "MINIMIZE_REQUIRED_CHANGE"


class BoundaryConstraint(str, Enum):
    LIQUIDITY = "LIQUIDITY"
    LTV = "LTV"
    DEBT_CAPACITY = "DEBT_CAPACITY"


class CandidateStatus(str, Enum):
    FEASIBLE = "FEASIBLE"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class BoundaryTargets:
    target_profile: str
    ltv_target: Decimal
    dsti_target: Decimal


@dataclass(frozen=True)
class SimulationPolicy:
    property_price: SimulationVariablePolicy
    planned_down_payment: SimulationVariablePolicy


@dataclass(frozen=True)
class CandidateEvaluation:
    constraints: tuple[BoundaryConstraint, ...]
    property_price: Decimal
    planned_down_payment: Decimal
    status: CandidateStatus
    rejection_reasons: tuple[str, ...]
    financial_result: Optional[FinancialResult]


@dataclass(frozen=True)
class BoundaryResult:
    base_scenario_id: str
    optimization_objective: OptimizationObjective
    target_profile: str

    property_price: Decimal
    planned_down_payment: Decimal
    financed_amount: Decimal

    rounded_property_price: Decimal

    dominant_constraints: tuple[BoundaryConstraint, ...]
    candidates: tuple[CandidateEvaluation, ...]

    financial_result: FinancialResult


def round_conservatively(
    value: Decimal,
    step: Decimal = Decimal("1000"),
    direction: str = "DOWN",
) -> Decimal:

    if step <= ZERO:
        raise ValueError("step must be positive")

    units = value / step

    if direction == "DOWN":
        rounded_units = units.to_integral_value(
            rounding=ROUND_FLOOR
        )
    elif direction == "UP":
        rounded_units = units.to_integral_value(
            rounding=ROUND_CEILING
        )
    else:
        raise ValueError("direction must be DOWN or UP")

    return rounded_units * step


def _payment_factor(
    annual_rate: Decimal,
    term_years: int,
) -> Decimal:

    if term_years <= 0:
        raise ValueError("term_years must be positive")

    months = term_years * 12

    if annual_rate < ZERO:
        raise ValueError("annual_rate cannot be negative")

    if annual_rate == ZERO:
        return ONE / Decimal(months)

    monthly_rate = annual_rate / TWELVE
    factor = (ONE + monthly_rate) ** months

    return (
        monthly_rate
        * factor
        / (factor - ONE)
    )


def _resolved_interest_rate(
    scenario: FinancialScenario,
    defaults: FinancialDefaults,
) -> Decimal:

    if scenario.interest_rate_annual is not None:
        return scenario.interest_rate_annual

    return defaults.interest_rate_reference


def _resolved_term_years(
    scenario: FinancialScenario,
    defaults: FinancialDefaults,
) -> int:

    if scenario.term_years is not None:
        return scenario.term_years

    return defaults.term_years_reference


def _resolved_buffer(
    scenario: FinancialScenario,
    defaults: FinancialDefaults,
) -> Decimal:

    if scenario.desired_cash_buffer is not None:
        return scenario.desired_cash_buffer

    return defaults.desired_cash_buffer_reference


def _resolved_purchase_cost_rate(
    scenario: FinancialScenario,
    defaults: FinancialDefaults,
) -> Decimal:

    if scenario.purchase_cost_rate is not None:
        return scenario.purchase_cost_rate

    return defaults.purchase_cost_rate_global_default


def _max_financed_amount_from_dsti(
    scenario: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> Optional[Decimal]:

    if scenario.current_monthly_debt is None:
        return None

    max_total_debt_service = (
        scenario.monthly_net_income
        * targets.dsti_target
    )

    max_mortgage_payment = (
        max_total_debt_service
        - scenario.current_monthly_debt
    )

    if max_mortgage_payment < ZERO:
        return ZERO

    rate = _resolved_interest_rate(
        scenario,
        defaults,
    )

    term = _resolved_term_years(
        scenario,
        defaults,
    )

    payment_factor = _payment_factor(
        rate,
        term,
    )

    return max_mortgage_payment / payment_factor


def _scenario_from_boundary(
    base: FinancialScenario,
    property_price: Decimal,
    planned_down_payment: Decimal,
) -> FinancialScenario:

    return replace(
        base,
        property_price=property_price,
        planned_down_payment=planned_down_payment,

        # Boundary Solver evaluates the financing required by the
        # restructured purchase price and down payment.
        requested_loan_amount=None,

        # Do not manufacture a new appraisal value when price changes.
        # Existing appraisal remains a locked input if supplied.
    )


def _constraint_failures(
    result: FinancialResult,
    targets: BoundaryTargets,
) -> tuple[str, ...]:

    failures = []

    # A boundary calculated analytically may return to the Financial
    # Engine with a microscopic Decimal residual, e.g. cash_gap=1E-23.
    # Treat only economically meaningful positive differences as failures.
    if (
        result.cash_gap is None
        or result.cash_gap > MONEY_EPSILON
    ):
        failures.append("VIOLATES_LIQUIDITY_TARGET")

    ltv = (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )

    if (
        ltv is None
        or ltv > targets.ltv_target + RATIO_EPSILON
    ):
        failures.append("VIOLATES_LTV_TARGET")

    if (
        result.dsti is None
        or result.dsti > targets.dsti_target + RATIO_EPSILON
    ):
        failures.append("VIOLATES_DSTI_TARGET")

    if result.metadata.validation_errors:
        failures.append("FINANCIAL_ENGINE_VALIDATION_ERROR")

    return tuple(failures)


def _evaluate_candidate(
    base: FinancialScenario,
    property_price: Decimal,
    planned_down_payment: Decimal,
    constraints: tuple[BoundaryConstraint, ...],
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> CandidateEvaluation:

    if (
        property_price <= ZERO
        or planned_down_payment < ZERO
        or planned_down_payment > property_price
    ):
        return CandidateEvaluation(
            constraints=constraints,
            property_price=property_price,
            planned_down_payment=planned_down_payment,
            status=CandidateStatus.REJECTED,
            rejection_reasons=("OUT_OF_DOMAIN",),
            financial_result=None,
        )

    scenario = _scenario_from_boundary(
        base,
        property_price,
        planned_down_payment,
    )

    result = calculate_financial_scenario(
        scenario,
        defaults=defaults,
    )

    failures = _constraint_failures(
        result,
        targets,
    )

    return CandidateEvaluation(
        constraints=constraints,
        property_price=property_price,
        planned_down_payment=planned_down_payment,
        status=(
            CandidateStatus.FEASIBLE
            if not failures
            else CandidateStatus.REJECTED
        ),
        rejection_reasons=failures,
        financial_result=result,
    )


def _solve_1d_price(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> BoundaryResult:

    if base.planned_down_payment is None:
        raise ValueError(
            "1D property-price solve requires "
            "planned_down_payment to be locked and explicit"
        )

    down_payment = base.planned_down_payment

    cost_rate = _resolved_purchase_cost_rate(
        base,
        defaults,
    )

    buffer = _resolved_buffer(
        base,
        defaults,
    )

    available_cash = (
        base.available_savings
        - buffer
    )

    limits = []

    # Liquidity
    if cost_rate > ZERO:
        liquidity_limit = (
            available_cash - down_payment
        ) / cost_rate

        limits.append(
            (
                BoundaryConstraint.LIQUIDITY,
                liquidity_limit,
            )
        )

    # LTV
    if targets.ltv_target < ONE:
        denominator = ONE - targets.ltv_target

        ltv_limit = (
            down_payment / denominator
        )

        limits.append(
            (
                BoundaryConstraint.LTV,
                ltv_limit,
            )
        )

    # DSTI
    max_financed = _max_financed_amount_from_dsti(
        base,
        defaults,
        targets,
    )

    if max_financed is not None:
        dsti_limit = (
            max_financed + down_payment
        )

        limits.append(
            (
                BoundaryConstraint.DEBT_CAPACITY,
                dsti_limit,
            )
        )

    if not limits:
        raise ValueError("No applicable boundary constraints")

    dominant_constraint, selected_price = min(
        limits,
        key=lambda x: x[1],
    )

    candidate = _evaluate_candidate(
        base,
        selected_price,
        down_payment,
        (dominant_constraint,),
        defaults,
        targets,
    )

    if candidate.status != CandidateStatus.FEASIBLE:
        raise ValueError(
            "Calculated 1D boundary failed final feasibility verification: "
            + ", ".join(candidate.rejection_reasons)
        )

    result = candidate.financial_result

    assert result is not None
    assert result.financed_amount is not None

    return BoundaryResult(
        base_scenario_id=base.scenario_id,
        optimization_objective=(
            OptimizationObjective.MAXIMIZE_PROPERTY_PRICE
        ),
        target_profile=targets.target_profile,

        property_price=selected_price,
        planned_down_payment=down_payment,
        financed_amount=result.financed_amount,

        rounded_property_price=round_conservatively(
            selected_price,
            Decimal("1000"),
            "DOWN",
        ),

        dominant_constraints=(dominant_constraint,),
        candidates=(candidate,),
        financial_result=result,
    )


def _solve_pair_intersection(
    constraint_a: BoundaryConstraint,
    constraint_b: BoundaryConstraint,
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> Optional[tuple[Decimal, Decimal]]:

    pair = frozenset(
        (constraint_a, constraint_b)
    )

    cost_rate = _resolved_purchase_cost_rate(
        base,
        defaults,
    )

    buffer = _resolved_buffer(
        base,
        defaults,
    )

    available_cash = (
        base.available_savings
        - buffer
    )

    max_financed = _max_financed_amount_from_dsti(
        base,
        defaults,
        targets,
    )

    # LTV + Liquidity
    if pair == frozenset(
        (
            BoundaryConstraint.LTV,
            BoundaryConstraint.LIQUIDITY,
        )
    ):
        denominator = (
            ONE
            - targets.ltv_target
            + cost_rate
        )

        if denominator <= ZERO:
            return None

        price = (
            available_cash / denominator
        )

        down_payment = (
            (ONE - targets.ltv_target)
            * price
        )

        return price, down_payment

    # LTV + DSTI
    if pair == frozenset(
        (
            BoundaryConstraint.LTV,
            BoundaryConstraint.DEBT_CAPACITY,
        )
    ):
        if (
            max_financed is None
            or targets.ltv_target <= ZERO
        ):
            return None

        price = (
            max_financed
            / targets.ltv_target
        )

        down_payment = (
            (ONE - targets.ltv_target)
            * price
        )

        return price, down_payment

    # Liquidity + DSTI
    if pair == frozenset(
        (
            BoundaryConstraint.LIQUIDITY,
            BoundaryConstraint.DEBT_CAPACITY,
        )
    ):
        if max_financed is None:
            return None

        denominator = ONE + cost_rate

        if denominator <= ZERO:
            return None

        price = (
            available_cash
            + max_financed
        ) / denominator

        down_payment = (
            available_cash
            - cost_rate * price
        )

        return price, down_payment

    return None


def _solve_2d_price_down_payment(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> BoundaryResult:

    candidate_constraints = (
        BoundaryConstraint.LIQUIDITY,
        BoundaryConstraint.LTV,
        BoundaryConstraint.DEBT_CAPACITY,
    )

    evaluations = []

    for constraint_a, constraint_b in combinations(
        candidate_constraints,
        2,
    ):
        solution = _solve_pair_intersection(
            constraint_a,
            constraint_b,
            base,
            defaults,
            targets,
        )

        if solution is None:
            continue

        price, down_payment = solution

        evaluations.append(
            _evaluate_candidate(
                base,
                price,
                down_payment,
                (constraint_a, constraint_b),
                defaults,
                targets,
            )
        )

    feasible = [
        candidate
        for candidate in evaluations
        if candidate.status == CandidateStatus.FEASIBLE
    ]

    if not feasible:
        raise ValueError(
            "No feasible 2D boundary candidate found"
        )

    selected = max(
        feasible,
        key=lambda candidate: candidate.property_price,
    )

    result = selected.financial_result

    assert result is not None
    assert result.financed_amount is not None

    return BoundaryResult(
        base_scenario_id=base.scenario_id,
        optimization_objective=(
            OptimizationObjective.MAXIMIZE_PROPERTY_PRICE
        ),
        target_profile=targets.target_profile,

        property_price=selected.property_price,
        planned_down_payment=selected.planned_down_payment,
        financed_amount=result.financed_amount,

        rounded_property_price=round_conservatively(
            selected.property_price,
            Decimal("1000"),
            "DOWN",
        ),

        dominant_constraints=selected.constraints,
        candidates=tuple(evaluations),
        financial_result=result,
    )


def solve_boundary(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
    policy: SimulationPolicy,
    objective: OptimizationObjective = (
        OptimizationObjective.MAXIMIZE_PROPERTY_PRICE
    ),
) -> BoundaryResult:

    if objective != OptimizationObjective.MAXIMIZE_PROPERTY_PRICE:
        raise NotImplementedError(
            "MINIMIZE_REQUIRED_CHANGE is defined by the contract "
            "but not implemented in Boundary Solver v1 first increment"
        )

    price_adjustable = (
        policy.property_price
        == SimulationVariablePolicy.ADJUSTABLE
    )

    down_adjustable = (
        policy.planned_down_payment
        == SimulationVariablePolicy.ADJUSTABLE
    )

    if price_adjustable and not down_adjustable:
        return _solve_1d_price(
            base,
            defaults,
            targets,
        )

    if price_adjustable and down_adjustable:
        return _solve_2d_price_down_payment(
            base,
            defaults,
            targets,
        )

    raise NotImplementedError(
        "This first Boundary Solver increment supports "
        "property_price 1D and property_price + "
        "planned_down_payment 2D only"
    )
