import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.financial_engine import (
    calculate_financial_scenario,
)


st.set_page_config(
    page_title="Mortgage Decision Assistant",
    layout="wide",
)

st.title("Mortgage Decision Assistant")
st.caption(
    "Financial structuring prototype — deterministic calculation only. "
    "No bank approval prediction."
)

defaults = load_financial_defaults()


def D(value):
    return Decimal(str(value))


def money(value):
    if value is None:
        return "—"
    return f"{float(value):,.0f} €"


def pct(value):
    if value is None:
        return "—"
    return f"{float(value) * 100:.1f}%"


st.subheader("Scenario inputs")

col1, col2, col3 = st.columns(3)

with col1:
    property_price = st.number_input(
        "Property price (€)",
        min_value=1.0,
        value=300000.0,
        step=5000.0,
    )

    available_savings = st.number_input(
        "Available savings (€)",
        min_value=0.0,
        value=100000.0,
        step=5000.0,
    )

    desired_cash_buffer = st.number_input(
        "Desired cash buffer (€)",
        min_value=0.0,
        value=20000.0,
        step=1000.0,
    )

with col2:
    planned_down_payment = st.number_input(
        "Planned down payment (€)",
        min_value=0.0,
        value=60000.0,
        step=5000.0,
    )

    monthly_net_income = st.number_input(
        "Monthly net income (€)",
        min_value=1.0,
        value=4000.0,
        step=100.0,
    )

    current_monthly_debt = st.number_input(
        "Current monthly debt (€)",
        min_value=0.0,
        value=300.0,
        step=50.0,
    )

with col3:
    requested_loan_amount = st.number_input(
        "Requested loan amount (€)",
        min_value=0.0,
        value=240000.0,
        step=5000.0,
    )

    interest_rate_pct = st.number_input(
        "Annual interest rate (%)",
        min_value=0.0,
        value=3.0,
        step=0.1,
    )

    term_years = st.number_input(
        "Term (years)",
        min_value=1,
        value=30,
        step=1,
    )

with st.expander("Optional / advanced inputs"):
    appraisal_value = st.number_input(
        "Appraisal value (€)",
        min_value=0.0,
        value=300000.0,
        step=5000.0,
    )

    purchase_cost_rate_pct = st.number_input(
        "Purchase cost rate (%)",
        min_value=0.0,
        value=10.0,
        step=0.5,
    )

if st.button("Calculate scenario", type="primary"):

    scenario = FinancialScenario(
        property_price=D(property_price),
        available_savings=D(available_savings),
        desired_cash_buffer=D(desired_cash_buffer),
        planned_down_payment=D(planned_down_payment),
        monthly_net_income=D(monthly_net_income),
        current_monthly_debt=D(current_monthly_debt),
        requested_loan_amount=D(requested_loan_amount),
        interest_rate_annual=D(interest_rate_pct) / D("100"),
        term_years=int(term_years),
        purchase_cost_rate=D(purchase_cost_rate_pct) / D("100"),
        appraisal_value=(
            D(appraisal_value)
            if appraisal_value > 0
            else None
        ),
    )

    result = calculate_financial_scenario(
        scenario,
        defaults=defaults,
    )

    st.divider()
    st.subheader("Scenario results")

    r1, r2, r3 = st.columns(3)

    with r1:
        st.metric("Monthly payment", money(result.monthly_payment))
        st.metric(
            "LTV",
            pct(
                result.ltv
                if result.ltv is not None
                else result.ltv_provisional
            ),
        )

    with r2:
        st.metric("DSTI", pct(result.dsti))
        st.metric("Cash gap", money(result.cash_gap))

    with r3:
        st.metric("Residual savings", money(result.residual_savings))
        st.metric("Monthly margin", money(result.monthly_margin))

    st.subheader("Calculation quality")

    q1, q2 = st.columns(2)

    with q1:
        st.write(
            "**Completeness:**",
            result.metadata.calculation_completeness.value,
        )

    with q2:
        st.write(
            "**Technical confidence:**",
            result.metadata.technical_confidence.value,
        )

    if result.metadata.assumptions:
        st.info(
            "Fallbacks used: "
            + ", ".join(x.value for x in result.metadata.assumptions)
        )

    if result.metadata.calculation_modes:
        st.info(
            "Calculation modes: "
            + ", ".join(x.value for x in result.metadata.calculation_modes)
        )

    if result.metadata.validation_errors:
        st.error(
            "Validation issues: "
            + ", ".join(result.metadata.validation_errors)
        )

    if result.metadata.calculation_completeness.value == "PARTIAL":
        st.warning(
            "Some outputs could not be calculated because "
            "required information is missing or invalid."
        )

    st.caption(
        "Development prototype. Financial calculations are deterministic "
        "and separate from future Rules, Simulation and ML layers."
    )
