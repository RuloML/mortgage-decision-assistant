from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum

from .boundary_solver import (
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
    solve_boundary,
)
from .config import FinancialDefaults
from .domain import FinancialResult, FinancialScenario
from .financial_engine import calculate_financial_scenario
from .recommendation_engine import (
    RecommendationResult,
    RecommendationStatus,
    recommend_structure,
)


ZERO = Decimal("0")


class AlternativeType(str, Enum):
    KEEP_DOWN_PAYMENT = "KEEP_DOWN_PAYMENT"
    TERM_EXTENSION = "TERM_EXTENSION"


@dataclass(frozen=True)
class StructuringAlternative:
    alternative_type: AlternativeType
    property_price: Decimal
    planned_down_payment: Decimal | None
    term_years: int | None
    financial_result: FinancialResult
    explanation: str


@dataclass(frozen=True)
class AlternativesResult:
    recommendation: RecommendationResult
    alternatives: tuple[StructuringAlternative, ...]


def _is_feasible(
    result: FinancialResult,
    targets: BoundaryTargets,
) -> bool:

    if result.metadata.validation_errors:
        return False

    if result.cash_gap is None or result.cash_gap > ZERO:
        return False

    ltv = (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )

    if ltv is None or ltv > targets.ltv_target:
        return False

    if result.dsti is None or result.dsti > targets.dsti_target:
        return False

    return True


def _is_different_from_main(
    alternative: StructuringAlternative,
    recommendation: RecommendationResult,
) -> bool:

    return not (
        alternative.property_price
        == recommendation.presented_property_price
        and alternative.planned_down_payment
        == recommendation.presented_down_payment
    )


def _build_keep_down_payment_alternative(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> StructuringAlternative | None:

    if base.planned_down_payment is None:
        return None

    strategy_policy = SimulationPolicy(
        property_price=SimulationVariablePolicy.ADJUSTABLE,
        planned_down_payment=SimulationVariablePolicy.LOCKED,
    )

    try:
        boundary = solve_boundary(
            base=base,
            defaults=defaults,
            targets=targets,
            policy=strategy_policy,
        )
    except (ValueError, NotImplementedError):
        return None

    scenario = replace(
        base,
        property_price=boundary.rounded_property_price,
        planned_down_payment=base.planned_down_payment,
        requested_loan_amount=None,
    )

    result = calculate_financial_scenario(
        scenario,
        defaults=defaults,
    )

    if not _is_feasible(result, targets):
        return None

    return StructuringAlternative(
        alternative_type=AlternativeType.KEEP_DOWN_PAYMENT,
        property_price=scenario.property_price,
        planned_down_payment=scenario.planned_down_payment,
        term_years=scenario.term_years,
        financial_result=result,
        explanation=(
            "Mantener la entrada prevista y ajustar el precio "
            "del inmueble hasta una estructura que cumpla "
            "simultáneamente los objetivos configurados."
        ),
    )


def _build_term_alternative(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> StructuringAlternative | None:

    allowed_terms = (20, 25, 30, 35, 40)

    current_term = (
        base.term_years
        if base.term_years is not None
        else defaults.term_years_reference
    )

    for term in allowed_terms:

        if term <= current_term:
            continue

        scenario = replace(
            base,
            term_years=term,
        )

        result = calculate_financial_scenario(
            scenario,
            defaults=defaults,
        )

        if _is_feasible(result, targets):
            return StructuringAlternative(
                alternative_type=AlternativeType.TERM_EXTENSION,
                property_price=scenario.property_price,
                planned_down_payment=scenario.planned_down_payment,
                term_years=term,
                financial_result=result,
                explanation=(
                    "Mantener el precio y la entrada actuales "
                    "y ampliar el plazo para reducir la carga mensual."
                ),
            )

    return None


def generate_alternatives(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
    policy: SimulationPolicy,
    max_alternatives: int = 3,
) -> AlternativesResult:

    recommendation = recommend_structure(
        base=base,
        defaults=defaults,
        targets=targets,
        policy=policy,
    )

    if (
        recommendation.status
        != RecommendationStatus.RESTRUCTURING_AVAILABLE
    ):
        return AlternativesResult(
            recommendation=recommendation,
            alternatives=(),
        )

    issue_types = {
        issue.type
        for issue in recommendation.base_issues
    }

    alternatives = []

    # Strategy 1:
    # Preserve the customer's planned down payment and adjust price.
    if issue_types & {
        "LIQUIDITY",
        "LTV",
        "DEBT_CAPACITY",
    }:
        alternative = _build_keep_down_payment_alternative(
            base,
            defaults,
            targets,
        )

        if (
            alternative is not None
            and _is_different_from_main(
                alternative,
                recommendation,
            )
        ):
            alternatives.append(alternative)

    # Strategy 2:
    # Preserve price and down payment and extend the term.
    # This is only relevant when debt capacity is the problem.
    if "DEBT_CAPACITY" in issue_types:
        alternative = _build_term_alternative(
            base,
            defaults,
            targets,
        )

        if (
            alternative is not None
            and _is_different_from_main(
                alternative,
                recommendation,
            )
        ):
            alternatives.append(alternative)

    return AlternativesResult(
        recommendation=recommendation,
        alternatives=tuple(
            alternatives[:max_alternatives]
        ),
    )
