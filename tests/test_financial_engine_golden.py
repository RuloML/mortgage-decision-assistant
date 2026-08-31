import csv
from decimal import Decimal
from pathlib import Path

from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.financial_engine import (
    calculate_financial_scenario,
)


GOLDEN = Path("tests/golden/financial_engine_golden_v1.csv")


def optional_decimal(value: str):
    return None if value == "" else Decimal(value)


def optional_int(value: str):
    return None if value == "" else int(value)


def decimal_equal(actual, expected):
    if expected == "":
        return actual is None

    assert actual is not None
    return actual == Decimal(expected)


def test_financial_engine_against_golden_cases():

    with GOLDEN.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 18

    defaults = load_financial_defaults()

    for row in rows:

        scenario = FinancialScenario(
            scenario_id=row["case_id"],
            property_price=Decimal(row["property_price"]),
            available_savings=Decimal(row["available_savings"]),
            desired_cash_buffer=optional_decimal(
                row["desired_cash_buffer"]
            ),
            planned_down_payment=optional_decimal(
                row["planned_down_payment"]
            ),
            monthly_net_income=Decimal(row["monthly_net_income"]),
            current_monthly_debt=optional_decimal(
                row["current_monthly_debt"]
            ),
            requested_loan_amount=optional_decimal(
                row["requested_loan_amount"]
            ),
            interest_rate_annual=optional_decimal(
                row["interest_rate_annual"]
            ),
            term_years=optional_int(row["term_years"]),
            purchase_cost_rate=optional_decimal(
                row["purchase_cost_rate"]
            ),
            appraisal_value=optional_decimal(
                row["appraisal_value"]
            ),
        )

        result = calculate_financial_scenario(
            scenario,
            defaults=defaults,
        )

        fields = [
            "purchase_costs",
            "available_cash_for_operation",
            "required_loan",
            "financed_amount",
            "loan_gap",
            "total_cash_required",
            "cash_gap",
            "residual_savings",
            "monthly_payment",
            "ltv",
            "ltv_provisional",
            "dsti",
            "monthly_margin",
            "total_interest",
        ]

        for field in fields:
            expected = row[f"expected_{field}"]
            actual = getattr(result, field)

            assert decimal_equal(actual, expected), (
                f"{row['case_id']} failed for {field}: "
                f"actual={actual}, expected={expected}"
            )

        assert (
            result.planned_down_payment
            == Decimal(row["expected_resolved_planned_down_payment"])
        )

        assert (
            result.metadata.calculation_completeness.value
            == row["expected_calculation_completeness"]
        )

        assert (
            result.metadata.technical_confidence.value
            == row["expected_technical_confidence"]
        )

        assumptions = "|".join(
            x.value for x in result.metadata.assumptions
        )

        modes = "|".join(
            x.value for x in result.metadata.calculation_modes
        )

        errors = "|".join(result.metadata.validation_errors)

        assert assumptions == row["expected_assumptions"]
        assert modes == row["expected_calculation_modes"]
        assert errors == row["expected_invalid_inputs"]

        # Internal financial invariant:
        # cash_gap = max(0, desired_cash_buffer - residual_savings)
        if (
            result.cash_gap is not None
            and result.residual_savings is not None
        ):
            resolved_buffer = (
                scenario.desired_cash_buffer
                if scenario.desired_cash_buffer is not None
                else defaults.desired_cash_buffer_reference
            )

            expected_cash_gap_from_invariant = max(
                Decimal("0"),
                resolved_buffer - result.residual_savings,
            )

            assert result.cash_gap == expected_cash_gap_from_invariant, (
                f"{row['case_id']} cash-gap invariant failed: "
                f"cash_gap={result.cash_gap}, "
                f"buffer={resolved_buffer}, "
                f"residual_savings={result.residual_savings}"
            )
