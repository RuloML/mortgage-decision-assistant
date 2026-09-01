import csv
from decimal import Decimal
from pathlib import Path

from mortgage_decision_assistant.boundary_solver import (
    BoundaryConstraint,
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
    solve_boundary,
)
from mortgage_decision_assistant.config import (
    load_financial_defaults,
)
from mortgage_decision_assistant.domain import FinancialScenario


D = Decimal

REFERENCE_PATH = Path(
    "tests/golden/boundary_solver_reference_v1.csv"
)


def _load_reference_rows():
    with REFERENCE_PATH.open(
        encoding="utf-8",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def _scenario(row):
    return FinancialScenario(
        property_price=D(row["initial_property_price"]),
        available_savings=D(row["available_savings"]),
        desired_cash_buffer=D(row["desired_cash_buffer"]),
        planned_down_payment=D(row["planned_down_payment"]),
        monthly_net_income=D(row["monthly_net_income"]),
        current_monthly_debt=D(row["current_monthly_debt"]),
        requested_loan_amount=None,
        interest_rate_annual=D(row["interest_rate_annual"]),
        term_years=int(row["term_years"]),
        purchase_cost_rate=D(row["purchase_cost_rate"]),
        appraisal_value=None,
    )


def _targets(row):
    return BoundaryTargets(
        target_profile=row["target_profile"],
        ltv_target=D(row["ltv_target"]),
        dsti_target=D(row["dsti_target"]),
    )


def _policy(row):
    return SimulationPolicy(
        property_price=SimulationVariablePolicy.ADJUSTABLE,
        planned_down_payment=(
            SimulationVariablePolicy.ADJUSTABLE
            if row["down_payment_policy"] == "ADJUSTABLE"
            else SimulationVariablePolicy.LOCKED
        ),
    )


def _assert_close(actual, expected, tolerance=D("1")):
    assert abs(actual - expected) <= tolerance, (
        f"actual={actual}, expected={expected}, "
        f"tolerance={tolerance}"
    )


def test_reference_table_contains_frozen_cases():

    rows = _load_reference_rows()

    assert [x["case_id"] for x in rows] == [
        "B01",
        "B02",
        "B03",
    ]


def test_boundary_solver_matches_frozen_reference_cases():

    defaults = load_financial_defaults()

    for row in _load_reference_rows():

        result = solve_boundary(
            _scenario(row),
            defaults,
            _targets(row),
            _policy(row),
        )

        _assert_close(
            result.property_price,
            D(row["expected_property_price"]),
        )

        _assert_close(
            result.planned_down_payment,
            D(row["expected_down_payment"]),
        )

        _assert_close(
            result.financed_amount,
            D(row["expected_financed_amount"]),
        )

        assert (
            result.rounded_property_price
            == D(row["expected_rounded_price"])
        )

        assert (
            result.rounded_down_payment
            == D(row["expected_rounded_down_payment"])
        )

        expected_constraints = set(
            row["expected_dominant_constraints"].split("|")
        )

        actual_constraints = {
            x.value
            for x in result.dominant_constraints
        }

        assert actual_constraints == expected_constraints


def test_b03_rejects_ltv_liquidity_candidate_on_dsti():

    defaults = load_financial_defaults()

    row = next(
        x
        for x in _load_reference_rows()
        if x["case_id"] == "B03"
    )

    result = solve_boundary(
        _scenario(row),
        defaults,
        _targets(row),
        _policy(row),
    )

    rejected = [
        candidate
        for candidate in result.candidates
        if candidate.status.value == "REJECTED"
    ]

    assert any(
        set(x.value for x in candidate.constraints)
        == {"LTV", "LIQUIDITY"}
        and "VIOLATES_DSTI_TARGET"
        in candidate.rejection_reasons
        for candidate in rejected
    )


def test_boundary_results_are_feasible_after_financial_engine_verification():

    defaults = load_financial_defaults()

    for row in _load_reference_rows():

        result = solve_boundary(
            _scenario(row),
            defaults,
            _targets(row),
            _policy(row),
        )

        financial = result.financial_result

        # Numerical residuals at analytical boundaries are allowed
        # within technical verification tolerances.
        assert financial.cash_gap <= D("0.01")

        ltv = (
            financial.ltv
            if financial.ltv is not None
            else financial.ltv_provisional
        )

        assert ltv <= D(row["ltv_target"]) + D("0.000000001")
        assert financial.dsti <= D(row["dsti_target"]) + D("0.000000001")


def test_conservative_rounding_is_consistent():

    defaults = load_financial_defaults()

    for row in _load_reference_rows():

        result = solve_boundary(
            _scenario(row),
            defaults,
            _targets(row),
            _policy(row),
        )

        # Presentation boundary must never exceed the technical
        # maximum property-price boundary.
        assert result.rounded_property_price <= result.property_price

        # Presentation values must lie on the configured 1,000 EUR grid.
        assert result.rounded_property_price % D("1000") == D("0")
        assert result.rounded_down_payment % D("1000") == D("0")

        # In 2D the feasible presentation pair may require moving more
        # than one grid step away from the technical boundary.
        # Feasibility is therefore the governing requirement, not
        # distance < one rounding step.


def test_b01_feasible_presentation_pair():

    defaults = load_financial_defaults()

    row = next(
        x for x in _load_reference_rows()
        if x["case_id"] == "B01"
    )

    result = solve_boundary(
        _scenario(row),
        defaults,
        _targets(row),
        _policy(row),
    )

    assert result.rounded_property_price == D("265000")
    assert result.rounded_down_payment == D("53000")

    presentation_scenario = FinancialScenario(
        property_price=result.rounded_property_price,
        available_savings=D(row["available_savings"]),
        desired_cash_buffer=D(row["desired_cash_buffer"]),
        planned_down_payment=result.rounded_down_payment,
        monthly_net_income=D(row["monthly_net_income"]),
        current_monthly_debt=D(row["current_monthly_debt"]),
        requested_loan_amount=None,
        interest_rate_annual=D(row["interest_rate_annual"]),
        term_years=int(row["term_years"]),
        purchase_cost_rate=D(row["purchase_cost_rate"]),
        appraisal_value=None,
    )

    from mortgage_decision_assistant.financial_engine import (
        calculate_financial_scenario,
    )

    financial = calculate_financial_scenario(
        presentation_scenario,
        defaults=defaults,
    )

    assert financial.cash_gap == D("0")

    ltv = (
        financial.ltv
        if financial.ltv is not None
        else financial.ltv_provisional
    )

    assert ltv <= D("0.80")
    assert financial.dsti <= D("0.40")


def test_b03_feasible_presentation_pair():

    defaults = load_financial_defaults()

    row = next(
        x for x in _load_reference_rows()
        if x["case_id"] == "B03"
    )

    result = solve_boundary(
        _scenario(row),
        defaults,
        _targets(row),
        _policy(row),
    )

    assert result.rounded_property_price == D("249000")
    assert result.rounded_down_payment == D("55000")

    presentation_scenario = FinancialScenario(
        property_price=result.rounded_property_price,
        available_savings=D(row["available_savings"]),
        desired_cash_buffer=D(row["desired_cash_buffer"]),
        planned_down_payment=result.rounded_down_payment,
        monthly_net_income=D(row["monthly_net_income"]),
        current_monthly_debt=D(row["current_monthly_debt"]),
        requested_loan_amount=None,
        interest_rate_annual=D(row["interest_rate_annual"]),
        term_years=int(row["term_years"]),
        purchase_cost_rate=D(row["purchase_cost_rate"]),
        appraisal_value=None,
    )

    from mortgage_decision_assistant.financial_engine import (
        calculate_financial_scenario,
    )

    financial = calculate_financial_scenario(
        presentation_scenario,
        defaults=defaults,
    )

    assert financial.cash_gap == D("0")

    ltv = (
        financial.ltv
        if financial.ltv is not None
        else financial.ltv_provisional
    )

    assert ltv <= D("0.80")
    assert financial.dsti <= D("0.40")


def test_feasible_presentation_respects_lower_appraisal_ltv_base():

    defaults = load_financial_defaults()

    base = FinancialScenario(
        property_price=D("300000"),
        available_savings=D("150000"),
        desired_cash_buffer=D("20000"),
        planned_down_payment=D("60000"),
        monthly_net_income=D("5000"),
        current_monthly_debt=D("0"),
        requested_loan_amount=None,
        interest_rate_annual=D("0.03"),
        term_years=30,
        purchase_cost_rate=D("0.10"),
        appraisal_value=D("250000"),
    )

    targets = BoundaryTargets(
        target_profile="STANDARD",
        ltv_target=D("0.80"),
        dsti_target=D("0.40"),
    )

    policy = SimulationPolicy(
        property_price=SimulationVariablePolicy.ADJUSTABLE,
        planned_down_payment=SimulationVariablePolicy.ADJUSTABLE,
    )

    result = solve_boundary(
        base,
        defaults,
        targets,
        policy,
    )

    presentation = FinancialScenario(
        property_price=result.rounded_property_price,
        available_savings=base.available_savings,
        desired_cash_buffer=base.desired_cash_buffer,
        planned_down_payment=result.rounded_down_payment,
        monthly_net_income=base.monthly_net_income,
        current_monthly_debt=base.current_monthly_debt,
        requested_loan_amount=None,
        interest_rate_annual=base.interest_rate_annual,
        term_years=base.term_years,
        purchase_cost_rate=base.purchase_cost_rate,
        appraisal_value=base.appraisal_value,
    )

    from mortgage_decision_assistant.financial_engine import (
        calculate_financial_scenario,
    )

    financial = calculate_financial_scenario(
        presentation,
        defaults=defaults,
    )

    assert financial.ltv is not None
    assert financial.ltv <= D("0.80")
    assert financial.cash_gap == D("0")
