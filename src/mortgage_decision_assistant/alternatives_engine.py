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
GRID_STEP = Decimal("1000")


class AlternativeType(str, Enum):
    KEEP_DOWN_PAYMENT = "KEEP_DOWN_PAYMENT"
    KEEP_PROPERTY_PRICE = "KEEP_PROPERTY_PRICE"
    TERM_EXTENSION = "TERM_EXTENSION"


class StrategyStatus(str, Enum):
    VIABLE = "VIABLE"
    NOT_VIABLE = "NOT_VIABLE"
    NOT_RELEVANT = "NOT_RELEVANT"
    DUPLICATE_MAIN = "DUPLICATE_MAIN"


@dataclass(frozen=True)
class StructuringAlternative:
    alternative_type: AlternativeType
    property_price: Decimal
    planned_down_payment: Decimal | None
    term_years: int | None
    financial_result: FinancialResult
    explanation: str


@dataclass(frozen=True)
class StrategyEvaluation:
    alternative_type: AlternativeType
    status: StrategyStatus
    explanation: str
    alternative: StructuringAlternative | None = None


@dataclass(frozen=True)
class AlternativesResult:
    recommendation: RecommendationResult
    alternatives: tuple[StructuringAlternative, ...]
    strategy_evaluations: tuple[StrategyEvaluation, ...]


def _ltv(result: FinancialResult) -> Decimal | None:
    return (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )


def _is_feasible(
    result: FinancialResult,
    targets: BoundaryTargets,
) -> bool:

    if result.metadata.validation_errors:
        return False

    if result.cash_gap is None or result.cash_gap > ZERO:
        return False

    ltv = _ltv(result)

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
            "del inmueble."
        ),
    )


def _build_keep_property_price_alternative(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
) -> StructuringAlternative | None:

    if (
        base.property_price is None
        or base.planned_down_payment is None
    ):
        return None

    price = base.property_price

    # Search on a presentation grid for the feasible down payment
    # closest to the customer's original planned down payment.
    candidates = []

    down = ZERO

    while down <= price:

        scenario = replace(
            base,
            planned_down_payment=down,
            requested_loan_amount=None,
        )

        result = calculate_financial_scenario(
            scenario,
            defaults=defaults,
        )

        if _is_feasible(result, targets):
            candidates.append(
                (
                    abs(down - base.planned_down_payment),
                    down,
                    result,
                )
            )

        down += GRID_STEP

    if not candidates:
        return None

    _, selected_down, selected_result = min(
        candidates,
        key=lambda item: item[0],
    )

    scenario = replace(
        base,
        planned_down_payment=selected_down,
        requested_loan_amount=None,
    )

    return StructuringAlternative(
        alternative_type=AlternativeType.KEEP_PROPERTY_PRICE,
        property_price=price,
        planned_down_payment=selected_down,
        term_years=scenario.term_years,
        financial_result=selected_result,
        explanation=(
            "Mantener el precio del inmueble y ajustar la entrada "
            "hasta una estructura viable."
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
                    "Mantener precio y entrada y ampliar el plazo "
                    "para reducir la carga mensual."
                ),
            )

    return None


def _evaluate_candidate_strategy(
    alternative_type: AlternativeType,
    alternative: StructuringAlternative | None,
    recommendation: RecommendationResult,
    not_viable_message: str,
) -> StrategyEvaluation:

    if alternative is None:
        return StrategyEvaluation(
            alternative_type=alternative_type,
            status=StrategyStatus.NOT_VIABLE,
            explanation=not_viable_message,
        )

    if not _is_different_from_main(
        alternative,
        recommendation,
    ):
        return StrategyEvaluation(
            alternative_type=alternative_type,
            status=StrategyStatus.DUPLICATE_MAIN,
            explanation=(
                "La estrategia conduce esencialmente a la misma "
                "estructura que la recomendación principal."
            ),
            alternative=alternative,
        )

    return StrategyEvaluation(
        alternative_type=alternative_type,
        status=StrategyStatus.VIABLE,
        explanation=alternative.explanation,
        alternative=alternative,
    )


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
            strategy_evaluations=(),
        )

    issue_types = {
        issue.type
        for issue in recommendation.base_issues
    }

    evaluations = []

    # Strategy 1 — keep down payment, adjust property price.
    keep_down = _build_keep_down_payment_alternative(
        base,
        defaults,
        targets,
    )

    evaluations.append(
        _evaluate_candidate_strategy(
            AlternativeType.KEEP_DOWN_PAYMENT,
            keep_down,
            recommendation,
            (
                "No se encontró un precio que permita mantener "
                "la entrada y cumplir simultáneamente los objetivos."
            ),
        )
    )

    # Strategy 2 — keep property price, adjust down payment.
    keep_price = _build_keep_property_price_alternative(
        base,
        defaults,
        targets,
    )

    evaluations.append(
        _evaluate_candidate_strategy(
            AlternativeType.KEEP_PROPERTY_PRICE,
            keep_price,
            recommendation,
            (
                "No se encontró una entrada que permita mantener "
                "el precio y cumplir simultáneamente liquidez, "
                "LTV y DSTI."
            ),
        )
    )

    # Strategy 3 — term extension only addresses debt capacity.
    if "DEBT_CAPACITY" in issue_types:

        term_alt = _build_term_alternative(
            base,
            defaults,
            targets,
        )

        evaluations.append(
            _evaluate_candidate_strategy(
                AlternativeType.TERM_EXTENSION,
                term_alt,
                recommendation,
                (
                    "Ampliar el plazo no fue suficiente para "
                    "alcanzar los objetivos configurados."
                ),
            )
        )

    else:

        evaluations.append(
            StrategyEvaluation(
                alternative_type=AlternativeType.TERM_EXTENSION,
                status=StrategyStatus.NOT_RELEVANT,
                explanation=(
                    "El problema detectado no es de capacidad mensual, "
                    "por lo que ampliar el plazo no resuelve "
                    "la restricción principal."
                ),
            )
        )

    alternatives = tuple(
        evaluation.alternative
        for evaluation in evaluations
        if (
            evaluation.status == StrategyStatus.VIABLE
            and evaluation.alternative is not None
        )
    )

    return AlternativesResult(
        recommendation=recommendation,
        alternatives=alternatives[:max_alternatives],
        strategy_evaluations=tuple(evaluations),
    )
