from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

from .domain import FinancialResult, FinancialScenario


ZERO = Decimal("0")
HUNDRED = Decimal("100")


class PresentationState(str, Enum):
    WITHIN_TARGET = "WITHIN_TARGET"
    REQUIRES_ADJUSTMENT = "REQUIRES_ADJUSTMENT"


@dataclass(frozen=True)
class MetricStatus:
    key: str
    label: str
    state: PresentationState
    value: Decimal | None
    target: Decimal | None
    value_text: str
    target_text: str | None


@dataclass(frozen=True)
class RecommendationComparisonPayload:
    actual_price: Decimal
    recommended_price: Decimal
    actual_down_payment: Decimal | None
    recommended_down_payment: Decimal | None
    actual_dsti: Decimal | None
    recommended_dsti: Decimal | None
    actual_ltv: Decimal | None
    recommended_ltv: Decimal | None

    actual_price_text: str
    recommended_price_text: str
    actual_down_payment_text: str
    recommended_down_payment_text: str
    actual_dsti_text: str
    recommended_dsti_text: str
    actual_ltv_text: str
    recommended_ltv_text: str


@dataclass(frozen=True)
class PresentationPayload:
    liquidity: MetricStatus
    ltv: MetricStatus
    dsti: MetricStatus
    comparison: RecommendationComparisonPayload | None = None


def _quantize(value: Decimal, decimals: int) -> Decimal:
    unit = Decimal("1") if decimals == 0 else Decimal("1").scaleb(-decimals)
    return value.quantize(unit, rounding=ROUND_HALF_UP)


def format_number_es(value: Decimal, decimals: int = 0) -> str:
    quantized = _quantize(value, decimals)
    raw = f"{quantized:,.{decimals}f}"
    return raw.replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")


def money_text(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{format_number_es(value, 0)} €"


def pct_text(value: Decimal | None) -> str:
    if value is None:
        return "—"
    return f"{format_number_es(value * HUNDRED, 1)}%"


def ltv_value(result: FinancialResult) -> Decimal | None:
    return result.ltv if result.ltv is not None else result.ltv_provisional


def classify_upper_bound(
    value: Decimal | None,
    target: Decimal,
) -> PresentationState:
    if value is None:
        return PresentationState.REQUIRES_ADJUSTMENT
    return (
        PresentationState.WITHIN_TARGET
        if value <= target
        else PresentationState.REQUIRES_ADJUSTMENT
    )


def classify_cash_gap(value: Decimal | None) -> PresentationState:
    if value is None:
        return PresentationState.REQUIRES_ADJUSTMENT
    return (
        PresentationState.WITHIN_TARGET
        if value <= ZERO
        else PresentationState.REQUIRES_ADJUSTMENT
    )


def build_operation_status_payload(
    result: FinancialResult,
    ltv_target: Decimal,
    dsti_target: Decimal,
) -> PresentationPayload:
    current_ltv = ltv_value(result)

    return PresentationPayload(
        liquidity=MetricStatus(
            key="liquidity",
            label="Liquidez",
            state=classify_cash_gap(result.cash_gap),
            value=result.cash_gap,
            target=ZERO,
            value_text=money_text(result.cash_gap),
            target_text="Sin déficit",
        ),
        ltv=MetricStatus(
            key="ltv",
            label="Financiación sobre valor",
            state=classify_upper_bound(current_ltv, ltv_target),
            value=current_ltv,
            target=ltv_target,
            value_text=pct_text(current_ltv),
            target_text=pct_text(ltv_target),
        ),
        dsti=MetricStatus(
            key="dsti",
            label="Ratio de endeudamiento",
            state=classify_upper_bound(result.dsti, dsti_target),
            value=result.dsti,
            target=dsti_target,
            value_text=pct_text(result.dsti),
            target_text=pct_text(dsti_target),
        ),
    )


def build_recommendation_comparison_payload(
    base_scenario: FinancialScenario,
    base_result: FinancialResult,
    recommended_scenario: FinancialScenario,
    recommended_result: FinancialResult,
    ltv_target: Decimal,
    dsti_target: Decimal,
) -> PresentationPayload:
    actual_ltv = ltv_value(base_result)
    recommended_ltv = ltv_value(recommended_result)

    statuses = build_operation_status_payload(
        base_result,
        ltv_target=ltv_target,
        dsti_target=dsti_target,
    )

    comparison = RecommendationComparisonPayload(
        actual_price=base_scenario.property_price,
        recommended_price=recommended_scenario.property_price,
        actual_down_payment=base_scenario.planned_down_payment,
        recommended_down_payment=recommended_scenario.planned_down_payment,
        actual_dsti=base_result.dsti,
        recommended_dsti=recommended_result.dsti,
        actual_ltv=actual_ltv,
        recommended_ltv=recommended_ltv,
        actual_price_text=money_text(base_scenario.property_price),
        recommended_price_text=money_text(recommended_scenario.property_price),
        actual_down_payment_text=money_text(base_scenario.planned_down_payment),
        recommended_down_payment_text=money_text(
            recommended_scenario.planned_down_payment
        ),
        actual_dsti_text=pct_text(base_result.dsti),
        recommended_dsti_text=pct_text(recommended_result.dsti),
        actual_ltv_text=pct_text(actual_ltv),
        recommended_ltv_text=pct_text(recommended_ltv),
    )

    return PresentationPayload(
        liquidity=statuses.liquidity,
        ltv=statuses.ltv,
        dsti=statuses.dsti,
        comparison=comparison,
    )
