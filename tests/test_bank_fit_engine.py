from decimal import Decimal

from mortgage_decision_assistant.bank_fit_engine import (
    BorrowerProfile,
    CriterionStatus,
    ProductStatus,
    evaluate_bank_product,
    load_bank_criteria,
)
from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.financial_engine import (
    calculate_financial_scenario,
)


def D(value):
    return Decimal(str(value))


def _scenario(
    *,
    appraisal_value=D("300000"),
    term_years=25,
    monthly_net_income=D("4000"),
):
    return FinancialScenario(
        property_price=D("300000"),
        available_savings=D("100000"),
        desired_cash_buffer=D("20000"),
        planned_down_payment=D("60000"),
        monthly_net_income=monthly_net_income,
        current_monthly_debt=D("300"),
        requested_loan_amount=D("240000"),
        interest_rate_annual=D("0.03"),
        term_years=term_years,
        purchase_cost_rate=D("0.10"),
        appraisal_value=appraisal_value,
    )


def _product(dataset, product_id):
    return next(
        product
        for product in dataset["products"]
        if product["product_id"] == product_id
    )


def _evaluation(result, criterion_id):
    return next(
        item
        for item in result.criteria
        if item.criterion_id == criterion_id
    )


def _evaluate(product_id, scenario, profile):
    dataset = load_bank_criteria()
    result = calculate_financial_scenario(
        scenario,
        defaults=load_financial_defaults(),
    )
    return evaluate_bank_product(
        scenario=scenario,
        result=result,
        profile=profile,
        product=_product(dataset, product_id),
        dataset=dataset,
    )


def test_santander_appraisal_based_ltv_is_unknown_without_appraisal():
    scenario = _scenario(appraisal_value=None)

    bank_fit = _evaluate(
        "SANTANDER_STANDARD_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(40,),
            property_use="PRIMARY_HOME",
        ),
    )

    ltv = _evaluation(bank_fit, "MAX_LTV")

    assert ltv.status == CriterionStatus.UNKNOWN
    assert ltv.actual_value is None

    # Term is evaluable but LTV is not and Santander's public
    # multi-borrower age selection rule remains unspecified.
    assert bank_fit.core_coverage == D("1") / D("3")
    assert bank_fit.product_status == ProductStatus.INSUFFICIENT_INFORMATION


def test_explicit_property_use_mismatch_excludes_product_before_scoring():
    scenario = _scenario()

    bank_fit = _evaluate(
        "BBVA_FIXED_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(40,),
            property_use="SECOND_HOME",
            residency_status="RESIDENT_ES",
        ),
    )

    assert bank_fit.product_status == ProductStatus.INELIGIBLE_PRODUCT
    assert bank_fit.criteria == ()


def test_missing_eligibility_input_is_not_assumed_negative():
    scenario = _scenario()

    bank_fit = _evaluate(
        "BBVA_FIXED_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(40,),
            property_use="PRIMARY_HOME",
            residency_status=None,
        ),
    )

    assert bank_fit.product_status == ProductStatus.INSUFFICIENT_INFORMATION
    assert bank_fit.criteria == ()


def test_bbva_youngest_borrower_rule_uses_youngest_age():
    scenario = _scenario(term_years=30)

    bank_fit = _evaluate(
        "BBVA_FIXED_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(60, 40),
            property_use="PRIMARY_HOME",
            residency_status="RESIDENT_ES",
        ),
    )

    age = _evaluation(bank_fit, "MAX_AGE_AT_MATURITY")

    assert age.actual_value == D("70")
    assert age.status == CriterionStatus.MATCH


def test_bankinter_all_borrowers_rule_uses_oldest_for_maximum_check():
    scenario = _scenario(
        term_years=25,
        monthly_net_income=D("4000"),
    )

    bank_fit = _evaluate(
        "BANKINTER_FIXED_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(50, 46),
            property_use="PRIMARY_HOME",
            residency_status="RESIDENT_ES",
        ),
    )

    age = _evaluation(bank_fit, "MAX_AGE_AT_MATURITY")
    income = _evaluation(bank_fit, "MIN_TOTAL_MONTHLY_INCOME")

    assert age.actual_value == D("75")
    assert age.status == CriterionStatus.MATCH
    assert income.status == CriterionStatus.MATCH


def test_caixabank_conflicting_age_source_stays_unknown():
    scenario = _scenario(term_years=30)

    bank_fit = _evaluate(
        "CAIXABANK_CASAFACIL_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(45, 40),
            property_use="PRIMARY_HOME",
        ),
    )

    age = _evaluation(bank_fit, "MAX_AGE_AT_MATURITY")

    assert age.status == CriterionStatus.UNKNOWN
    assert age.source_status == "CONFLICTING"


def test_hard_and_guidance_results_are_counted_separately():
    scenario = _scenario(term_years=25)

    bank_fit = _evaluate(
        "SABADELL_STANDARD_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(40,),
            property_use="PRIMARY_HOME",
            residency_status="RESIDENT_ES",
        ),
    )

    assert bank_fit.hard_matches >= 3
    assert bank_fit.guidance_matches + bank_fit.guidance_mismatches == 2
    assert bank_fit.hard_mismatches == 0


def test_bankinter_income_threshold_is_strictly_greater_than_2500():
    scenario = _scenario(
        term_years=25,
        monthly_net_income=D("2500"),
    )

    bank_fit = _evaluate(
        "BANKINTER_FIXED_PRIMARY_HOME",
        scenario,
        BorrowerProfile(
            borrower_ages=(40,),
            property_use="PRIMARY_HOME",
            residency_status="RESIDENT_ES",
        ),
    )

    income = _evaluation(bank_fit, "MIN_TOTAL_MONTHLY_INCOME")

    assert income.status == CriterionStatus.MISMATCH
