from decimal import Decimal, localcontext
from typing import Optional

from .domain import (
    AssumptionType,
    CalculationCompleteness,
    CalculationMetadata,
    CalculationMode,
    FinancialResult,
    FinancialScenario,
    TechnicalConfidence,
)


ZERO = Decimal("0")
TWELVE = Decimal("12")


def _monthly_payment(
    principal: Optional[Decimal],
    annual_rate: Optional[Decimal],
    term_years: Optional[int],
) -> Optional[Decimal]:

    if principal is None or annual_rate is None or term_years is None:
        return None

    if term_years <= 0 or annual_rate < 0:
        return None

    months = term_years * 12

    if principal == ZERO:
        return ZERO

    if annual_rate == ZERO:
        return principal / Decimal(months)

    with localcontext() as ctx:
        ctx.prec = 28

        monthly_rate = annual_rate / TWELVE
        factor = (Decimal("1") + monthly_rate) ** months

        return (
            principal
            * monthly_rate
            * factor
            / (factor - Decimal("1"))
        )


def calculate_financial_scenario(
    scenario: FinancialScenario,
) -> FinancialResult:

    assumptions: list[AssumptionType] = []
    calculation_modes: list[CalculationMode] = []
    validation_errors: list[str] = []
    missing_inputs: list[str] = []

    # --------------------------------------------------------
    # Required core validation
    # --------------------------------------------------------

    if scenario.property_price <= ZERO:
        validation_errors.append("property_price")

    if scenario.available_savings < ZERO:
        validation_errors.append("available_savings")

    if scenario.monthly_net_income <= ZERO:
        validation_errors.append("monthly_net_income")

    if scenario.current_monthly_debt is None:
        missing_inputs.append("current_monthly_debt")
    elif scenario.current_monthly_debt < ZERO:
        validation_errors.append("current_monthly_debt")

    # --------------------------------------------------------
    # Values that currently require explicit input because
    # financial_defaults.yaml is intentionally not frozen yet.
    # --------------------------------------------------------

    if scenario.desired_cash_buffer is None:
        missing_inputs.append("desired_cash_buffer")

    if scenario.purchase_cost_rate is None:
        missing_inputs.append("purchase_cost_rate")

    if scenario.interest_rate_annual is None:
        missing_inputs.append("interest_rate_annual")

    if scenario.term_years is None:
        missing_inputs.append("term_years")

    # --------------------------------------------------------
    # Purchase costs
    # --------------------------------------------------------

    purchase_costs = None

    if (
        scenario.property_price > ZERO
        and scenario.purchase_cost_rate is not None
        and scenario.purchase_cost_rate >= ZERO
    ):
        purchase_costs = (
            scenario.property_price
            * scenario.purchase_cost_rate
        )
    elif (
        scenario.purchase_cost_rate is not None
        and scenario.purchase_cost_rate < ZERO
    ):
        validation_errors.append("purchase_cost_rate")

    # --------------------------------------------------------
    # Available cash
    # --------------------------------------------------------

    available_cash_for_operation = None

    if scenario.desired_cash_buffer is not None:
        if scenario.desired_cash_buffer < ZERO:
            validation_errors.append("desired_cash_buffer")
        else:
            available_cash_for_operation = (
                scenario.available_savings
                - scenario.desired_cash_buffer
            )

    # --------------------------------------------------------
    # Planned down payment
    # --------------------------------------------------------

    planned_down_payment = scenario.planned_down_payment

    if planned_down_payment is None:
        if (
            available_cash_for_operation is not None
            and purchase_costs is not None
        ):
            planned_down_payment = max(
                ZERO,
                available_cash_for_operation - purchase_costs,
            )

            assumptions.append(
                AssumptionType.MAX_AVAILABLE_DOWN_PAYMENT
            )
        else:
            missing_inputs.append("planned_down_payment")

    if planned_down_payment is not None:
        if (
            planned_down_payment < ZERO
            or planned_down_payment > scenario.property_price
        ):
            validation_errors.append("planned_down_payment")

    down_payment_valid = (
        planned_down_payment is not None
        and "planned_down_payment" not in validation_errors
        and scenario.property_price > ZERO
    )

    # --------------------------------------------------------
    # Required loan
    # --------------------------------------------------------

    required_loan = (
        scenario.property_price - planned_down_payment
        if down_payment_valid
        else None
    )

    # --------------------------------------------------------
    # Financed amount
    # --------------------------------------------------------

    if scenario.requested_loan_amount is not None:

        if scenario.requested_loan_amount < ZERO:
            validation_errors.append("requested_loan_amount")
            financed_amount = None
        else:
            financed_amount = scenario.requested_loan_amount

    else:
        financed_amount = required_loan

    # --------------------------------------------------------
    # Loan gap
    # --------------------------------------------------------

    loan_gap = None

    if (
        scenario.requested_loan_amount is not None
        and required_loan is not None
        and "requested_loan_amount" not in validation_errors
    ):
        loan_gap = (
            required_loan
            - scenario.requested_loan_amount
        )

    # --------------------------------------------------------
    # Cash structure
    # --------------------------------------------------------

    total_cash_required = None

    if (
        down_payment_valid
        and purchase_costs is not None
    ):
        total_cash_required = (
            planned_down_payment
            + purchase_costs
        )

    cash_gap = None

    if (
        total_cash_required is not None
        and available_cash_for_operation is not None
    ):
        cash_gap = max(
            ZERO,
            total_cash_required
            - available_cash_for_operation,
        )

    residual_savings = None

    if (
        down_payment_valid
        and purchase_costs is not None
    ):
        residual_savings = (
            scenario.available_savings
            - planned_down_payment
            - purchase_costs
        )

    # --------------------------------------------------------
    # Monthly payment
    # --------------------------------------------------------

    monthly_payment = _monthly_payment(
        financed_amount,
        scenario.interest_rate_annual,
        scenario.term_years,
    )

    # --------------------------------------------------------
    # LTV
    # --------------------------------------------------------

    ltv = None
    ltv_provisional = None

    if financed_amount is not None and scenario.property_price > ZERO:

        if scenario.appraisal_value is not None:

            if scenario.appraisal_value <= ZERO:
                validation_errors.append("appraisal_value")

            else:
                denominator = min(
                    scenario.property_price,
                    scenario.appraisal_value,
                )
                ltv = financed_amount / denominator

        else:
            ltv_provisional = (
                financed_amount
                / scenario.property_price
            )

            calculation_modes.append(
                CalculationMode.LTV_PROVISIONAL_WITHOUT_APPRAISAL
            )

    # --------------------------------------------------------
    # DSTI and monthly margin
    # --------------------------------------------------------

    dsti = None
    monthly_margin = None

    if (
        monthly_payment is not None
        and scenario.current_monthly_debt is not None
        and scenario.current_monthly_debt >= ZERO
        and scenario.monthly_net_income > ZERO
    ):
        dsti = (
            monthly_payment
            + scenario.current_monthly_debt
        ) / scenario.monthly_net_income

        monthly_margin = (
            scenario.monthly_net_income
            - scenario.current_monthly_debt
            - monthly_payment
        )

    # --------------------------------------------------------
    # Total interest
    # --------------------------------------------------------

    total_interest = None

    if (
        monthly_payment is not None
        and financed_amount is not None
        and scenario.term_years is not None
        and scenario.term_years > 0
    ):
        total_interest = (
            monthly_payment
            * Decimal(scenario.term_years * 12)
            - financed_amount
        )

    # --------------------------------------------------------
    # Calculation completeness
    # --------------------------------------------------------

    expected_outputs = (
        purchase_costs,
        available_cash_for_operation,
        required_loan,
        financed_amount,
        total_cash_required,
        cash_gap,
        residual_savings,
        monthly_payment,
        dsti,
        monthly_margin,
        total_interest,
    )

    partial = (
        bool(validation_errors)
        or any(value is None for value in expected_outputs)
    )

    completeness = (
        CalculationCompleteness.PARTIAL
        if partial
        else CalculationCompleteness.COMPLETE
    )

    # --------------------------------------------------------
    # Technical confidence
    # --------------------------------------------------------

    if partial:
        technical_confidence = TechnicalConfidence.LOW

    elif assumptions or calculation_modes:
        technical_confidence = TechnicalConfidence.MEDIUM

    else:
        technical_confidence = TechnicalConfidence.HIGH

    metadata = CalculationMetadata(
        missing_inputs=tuple(dict.fromkeys(missing_inputs)),
        assumptions=tuple(assumptions),
        fallbacks_applied=tuple(a.value for a in assumptions),
        calculation_completeness=completeness,
        technical_confidence=technical_confidence,
        calculation_modes=tuple(calculation_modes),
        validation_errors=tuple(dict.fromkeys(validation_errors)),
    )

    return FinancialResult(
        scenario_id=scenario.scenario_id,
        purchase_costs=purchase_costs,
        available_cash_for_operation=available_cash_for_operation,
        planned_down_payment=planned_down_payment,
        required_loan=required_loan,
        requested_loan_amount=scenario.requested_loan_amount,
        financed_amount=financed_amount,
        loan_gap=loan_gap,
        total_cash_required=total_cash_required,
        cash_gap=cash_gap,
        residual_savings=residual_savings,
        monthly_payment=monthly_payment,
        ltv=ltv,
        ltv_provisional=ltv_provisional,
        dsti=dsti,
        monthly_margin=monthly_margin,
        total_interest=total_interest,
        metadata=metadata,
    )
