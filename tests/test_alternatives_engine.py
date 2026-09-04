from decimal import Decimal

from mortgage_decision_assistant.alternatives_engine import (
    AlternativeType,
    generate_alternatives,
)
from mortgage_decision_assistant.boundary_solver import (
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
)
from mortgage_decision_assistant.config import (
    load_financial_defaults,
)
from mortgage_decision_assistant.domain import (
    FinancialScenario,
)


D = Decimal


def _targets():
    return BoundaryTargets(
        target_profile="STANDARD",
        ltv_target=D("0.80"),
        dsti_target=D("0.40"),
    )


def _policy():
    return SimulationPolicy(
        property_price=SimulationVariablePolicy.ADJUSTABLE,
        planned_down_payment=SimulationVariablePolicy.ADJUSTABLE,
    )


def _ltv(result):
    return (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )


def test_liquidity_issue_offers_keep_down_payment_strategy():

    scenario = FinancialScenario(
        property_price=D("300000"),
        available_savings=D("100000"),
        desired_cash_buffer=D("20000"),
        planned_down_payment=D("60000"),
        monthly_net_income=D("4000"),
        current_monthly_debt=D("300"),
        requested_loan_amount=D("240000"),
        interest_rate_annual=D("0.03"),
        term_years=30,
        purchase_cost_rate=D("0.10"),
        appraisal_value=D("300000"),
    )

    result = generate_alternatives(
        base=scenario,
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert {
        issue.type
        for issue in result.recommendation.base_issues
    } == {"LIQUIDITY"}

    assert [
        alternative.alternative_type
        for alternative in result.alternatives
    ] == [
        AlternativeType.KEEP_DOWN_PAYMENT
    ]

    alternative = result.alternatives[0]

    assert alternative.planned_down_payment == D("60000")
    assert alternative.property_price == D("200000")


def test_dsti_issue_offers_distinct_strategies():

    scenario = FinancialScenario(
        property_price=D("300000"),
        available_savings=D("110000"),
        desired_cash_buffer=D("20000"),
        planned_down_payment=D("60000"),
        monthly_net_income=D("3000"),
        current_monthly_debt=D("200"),
        requested_loan_amount=D("240000"),
        interest_rate_annual=D("0.03"),
        term_years=30,
        purchase_cost_rate=D("0.10"),
        appraisal_value=D("300000"),
    )

    result = generate_alternatives(
        base=scenario,
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert {
        issue.type
        for issue in result.recommendation.base_issues
    } == {"DEBT_CAPACITY"}

    types = {
        alternative.alternative_type
        for alternative in result.alternatives
    }

    # KEEP_DOWN_PAYMENT is not returned here because it
    # coincides with the main recommendation and would be duplicate.
    assert AlternativeType.KEEP_DOWN_PAYMENT not in types
    assert AlternativeType.TERM_EXTENSION in types


def test_alternatives_are_different_from_main_recommendation():

    scenario = FinancialScenario(
        property_price=D("300000"),
        available_savings=D("100000"),
        desired_cash_buffer=D("20000"),
        planned_down_payment=D("60000"),
        monthly_net_income=D("4000"),
        current_monthly_debt=D("300"),
        requested_loan_amount=D("240000"),
        interest_rate_annual=D("0.03"),
        term_years=30,
        purchase_cost_rate=D("0.10"),
        appraisal_value=D("300000"),
    )

    result = generate_alternatives(
        base=scenario,
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    main = result.recommendation

    for alternative in result.alternatives:
        assert not (
            alternative.property_price
            == main.presented_property_price
            and alternative.planned_down_payment
            == main.presented_down_payment
        )


def test_every_generated_alternative_is_financially_feasible():

    scenarios = [
        FinancialScenario(
            property_price=D("300000"),
            available_savings=D("100000"),
            desired_cash_buffer=D("20000"),
            planned_down_payment=D("60000"),
            monthly_net_income=D("4000"),
            current_monthly_debt=D("300"),
            requested_loan_amount=D("240000"),
            interest_rate_annual=D("0.03"),
            term_years=30,
            purchase_cost_rate=D("0.10"),
            appraisal_value=D("300000"),
        ),
        FinancialScenario(
            property_price=D("300000"),
            available_savings=D("110000"),
            desired_cash_buffer=D("20000"),
            planned_down_payment=D("60000"),
            monthly_net_income=D("3000"),
            current_monthly_debt=D("200"),
            requested_loan_amount=D("240000"),
            interest_rate_annual=D("0.03"),
            term_years=30,
            purchase_cost_rate=D("0.10"),
            appraisal_value=D("300000"),
        ),
    ]

    for scenario in scenarios:

        result = generate_alternatives(
            base=scenario,
            defaults=load_financial_defaults(),
            targets=_targets(),
            policy=_policy(),
        )

        for alternative in result.alternatives:

            financial = alternative.financial_result

            assert financial.cash_gap == D("0")
            assert _ltv(financial) <= D("0.80")
            assert financial.dsti <= D("0.40")
