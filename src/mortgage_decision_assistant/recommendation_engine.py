from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .boundary_solver import (
    BoundaryResult,
    BoundaryTargets,
    OptimizationObjective,
    SimulationPolicy,
    solve_boundary,
)
from .config import FinancialDefaults
from .domain import FinancialResult, FinancialScenario
from .financial_engine import calculate_financial_scenario


ZERO = Decimal("0")


ISSUE_LABELS = {
    "LIQUIDITY": "liquidez",
    "LTV": "LTV configurado",
    "DEBT_CAPACITY": "nivel de endeudamiento",
    "FINANCING": "coherencia de financiación",
}

CONSTRAINT_LABELS = {
    "LIQUIDITY": "liquidez",
    "LTV": "LTV configurado",
    "DEBT_CAPACITY": "nivel de endeudamiento",
}


class RecommendationStatus(str, Enum):
    WITHIN_TARGETS = "WITHIN_TARGETS"
    RESTRUCTURING_AVAILABLE = "RESTRUCTURING_AVAILABLE"
    NO_FEASIBLE_STRUCTURE_FOUND = "NO_FEASIBLE_STRUCTURE_FOUND"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class BaseIssue:
    type: str
    actual_value: Decimal
    target_value: Decimal | None
    explanation: str


@dataclass(frozen=True)
class RecommendationResult:
    status: RecommendationStatus

    base_financial_result: FinancialResult
    base_issues: tuple[BaseIssue, ...]

    boundary: BoundaryResult | None

    technical_property_price: Decimal | None
    technical_down_payment: Decimal | None

    presented_property_price: Decimal | None
    presented_down_payment: Decimal | None

    property_price_change: Decimal | None
    down_payment_change: Decimal | None

    summary: str


def _ltv_value(result: FinancialResult):
    return (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )


def _detect_base_issues(
    result: FinancialResult,
    targets: BoundaryTargets,
) -> tuple[BaseIssue, ...]:

    issues = []

    if result.cash_gap is not None and result.cash_gap > ZERO:
        issues.append(
            BaseIssue(
                type="LIQUIDITY",
                actual_value=result.cash_gap,
                target_value=ZERO,
                explanation=(
                    "La estructura no preserva completamente "
                    "la liquidez objetivo."
                ),
            )
        )

    ltv = _ltv_value(result)

    if ltv is not None and ltv > targets.ltv_target:
        issues.append(
            BaseIssue(
                type="LTV",
                actual_value=ltv,
                target_value=targets.ltv_target,
                explanation=(
                    "El nivel de financiación supera "
                    "el objetivo LTV configurado."
                ),
            )
        )

    if (
        result.dsti is not None
        and result.dsti > targets.dsti_target
    ):
        issues.append(
            BaseIssue(
                type="DEBT_CAPACITY",
                actual_value=result.dsti,
                target_value=targets.dsti_target,
                explanation=(
                    "El servicio mensual de deuda supera "
                    "el objetivo DSTI configurado."
                ),
            )
        )

    if result.loan_gap is not None and result.loan_gap > ZERO:
        issues.append(
            BaseIssue(
                type="FINANCING",
                actual_value=result.loan_gap,
                target_value=ZERO,
                explanation=(
                    "La financiación planteada es inferior "
                    "a la requerida por la estructura."
                ),
            )
        )

    return tuple(issues)


def _join_spanish(items: list[str]) -> str:

    if not items:
        return ""

    if len(items) == 1:
        return items[0]

    if len(items) == 2:
        return f"{items[0]} y {items[1]}"

    return ", ".join(items[:-1]) + f" y {items[-1]}"


def _build_summary(
    issues: tuple[BaseIssue, ...],
    boundary: BoundaryResult,
    presented_property_price: Decimal,
    presented_down_payment: Decimal,
    property_price_change: Decimal,
    down_payment_change: Decimal,
) -> str:

    issue_labels = [
        ISSUE_LABELS[issue.type]
        for issue in issues
    ]

    constraint_labels = [
        CONSTRAINT_LABELS[constraint.value]
        for constraint in boundary.dominant_constraints
    ]

    diagnosis = _join_spanish(issue_labels)
    dominant = _join_spanish(constraint_labels)

    return (
        f"Diagnóstico: se requieren ajustes por {diagnosis}. "
        f"Frontera estimada: precio máximo conservador de "
        f"{presented_property_price} EUR, con una entrada aproximada de "
        f"{presented_down_payment} EUR. "
        f"Esta estructura está condicionada principalmente por {dominant}. "
        f"Cambio respecto al escenario actual: precio "
        f"{property_price_change} EUR y entrada {down_payment_change} EUR. "
        f"Los valores mostrados corresponden a una estructura factible "
        f"verificada por el motor financiero. "
        f"Es una estimación de estructuración basada en reglas; "
        f"no es una decisión bancaria."
    )


def recommend_structure(
    base: FinancialScenario,
    defaults: FinancialDefaults,
    targets: BoundaryTargets,
    policy: SimulationPolicy,
) -> RecommendationResult:

    base_result = calculate_financial_scenario(
        base,
        defaults=defaults,
    )

    if (
        base_result.metadata.calculation_completeness.value
        == "PARTIAL"
    ):
        return RecommendationResult(
            status=RecommendationStatus.INCOMPLETE,
            base_financial_result=base_result,
            base_issues=(),
            boundary=None,

            technical_property_price=None,
            technical_down_payment=None,

            presented_property_price=None,
            presented_down_payment=None,

            property_price_change=None,
            down_payment_change=None,

            summary=(
                "No hay información suficiente para emitir "
                "una recomendación estructural completa."
            ),
        )

    issues = _detect_base_issues(
        base_result,
        targets,
    )

    if not issues:
        return RecommendationResult(
            status=RecommendationStatus.WITHIN_TARGETS,
            base_financial_result=base_result,
            base_issues=(),
            boundary=None,

            technical_property_price=base.property_price,
            technical_down_payment=base.planned_down_payment,

            presented_property_price=base.property_price,
            presented_down_payment=base.planned_down_payment,

            property_price_change=ZERO,
            down_payment_change=ZERO,

            summary=(
                "La estructura actual cumple los objetivos "
                "configurados analizados."
            ),
        )

    try:
        boundary = solve_boundary(
            base=base,
            defaults=defaults,
            targets=targets,
            policy=policy,
            objective=(
                OptimizationObjective.MAXIMIZE_PROPERTY_PRICE
            ),
        )
    except ValueError:
        return RecommendationResult(
            status=RecommendationStatus.NO_FEASIBLE_STRUCTURE_FOUND,
            base_financial_result=base_result,
            base_issues=issues,
            boundary=None,

            technical_property_price=None,
            technical_down_payment=None,

            presented_property_price=None,
            presented_down_payment=None,

            property_price_change=None,
            down_payment_change=None,

            summary=(
                "No se ha encontrado una estructura que cumpla "
                "simultáneamente los objetivos configurados dentro de "
                "las variables y límites analizados. "
                "Esto no constituye una decisión bancaria ni implica "
                "que no existan alternativas fuera del alcance "
                "del modelo evaluado."
            ),
        )

    base_down_payment = (
        base.planned_down_payment
        if base.planned_down_payment is not None
        else ZERO
    )

    return RecommendationResult(
        status=RecommendationStatus.RESTRUCTURING_AVAILABLE,
        base_financial_result=base_result,
        base_issues=issues,
        boundary=boundary,

        technical_property_price=boundary.property_price,
        technical_down_payment=boundary.planned_down_payment,

        presented_property_price=boundary.rounded_property_price,
        presented_down_payment=boundary.rounded_down_payment,

        property_price_change=(
            boundary.rounded_property_price
            - base.property_price
        ),

        down_payment_change=(
            boundary.rounded_down_payment
            - base_down_payment
        ),

        summary=_build_summary(
            issues=issues,
            boundary=boundary,
            presented_property_price=boundary.rounded_property_price,
            presented_down_payment=boundary.rounded_down_payment,
            property_price_change=(
                boundary.rounded_property_price
                - base.property_price
            ),
            down_payment_change=(
                boundary.rounded_down_payment
                - base_down_payment
            ),
        ),
    )
