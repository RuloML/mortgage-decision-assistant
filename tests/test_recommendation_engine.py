from decimal import Decimal

from mortgage_decision_assistant.boundary_solver import (
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
)
from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.recommendation_engine import (
    RecommendationStatus,
    recommend_structure,
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


def _scenario():
    return FinancialScenario(
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


def test_recommendation_uses_feasible_presentation_boundary():

    scenario = _scenario()

    result = recommend_structure(
        base=scenario,
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert result.status == RecommendationStatus.RESTRUCTURING_AVAILABLE

    assert abs(
        result.technical_property_price
        - D("266666.6666666666666666666667")
    ) < D("0.01")

    assert abs(
        result.technical_down_payment
        - D("53333.33333333333333333333334")
    ) < D("0.01")

    assert result.presented_property_price == D("265000")
    assert result.presented_down_payment == D("53000")

    assert result.property_price_change == D("-35000")
    assert result.down_payment_change == D("-7000")

    assert (
        result.property_price_change
        == result.presented_property_price
        - scenario.property_price
    )

    assert (
        result.down_payment_change
        == result.presented_down_payment
        - scenario.planned_down_payment
    )


def test_recommendation_identifies_base_liquidity_issue():

    result = recommend_structure(
        base=_scenario(),
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert len(result.base_issues) == 1
    assert result.base_issues[0].type == "LIQUIDITY"
    assert result.base_issues[0].actual_value == D("10000.00")


def test_summary_uses_presented_values_not_technical_values():

    result = recommend_structure(
        base=_scenario(),
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert "265000 EUR" in result.summary
    assert "53000 EUR" in result.summary
    assert "-35000 EUR" in result.summary
    assert "-7000 EUR" in result.summary

    assert "266666" not in result.summary
    assert "53333" not in result.summary


def test_all_issue_codes_have_business_labels():

    from mortgage_decision_assistant.recommendation_engine import (
        ISSUE_LABELS,
    )

    expected_codes = {
        "LIQUIDITY",
        "LTV",
        "DEBT_CAPACITY",
        "FINANCING",
    }

    assert set(ISSUE_LABELS) == expected_codes


def test_all_boundary_constraints_have_business_labels():

    from mortgage_decision_assistant.boundary_solver import (
        BoundaryConstraint,
    )
    from mortgage_decision_assistant.recommendation_engine import (
        CONSTRAINT_LABELS,
    )

    assert {
        constraint.value
        for constraint in BoundaryConstraint
    } == set(CONSTRAINT_LABELS)


def test_summary_does_not_expose_raw_technical_labels():

    result = recommend_structure(
        base=_scenario(),
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert "LIQUIDITY" not in result.summary
    assert "DEBT_CAPACITY" not in result.summary


def test_no_feasible_structure_message_is_legally_prudent(monkeypatch):

    import mortgage_decision_assistant.recommendation_engine as module

    def _raise_no_solution(*args, **kwargs):
        raise ValueError("No feasible boundary")

    monkeypatch.setattr(
        module,
        "solve_boundary",
        _raise_no_solution,
    )

    result = module.recommend_structure(
        base=_scenario(),
        defaults=load_financial_defaults(),
        targets=_targets(),
        policy=_policy(),
    )

    assert (
        result.status
        == module.RecommendationStatus.NO_FEASIBLE_STRUCTURE_FOUND
    )

    assert "no constituye una decisión bancaria" in result.summary
    assert "no existan alternativas" in result.summary

    assert "LIQUIDITY" not in result.summary
    assert "LTV" not in result.summary
    assert "DEBT_CAPACITY" not in result.summary
