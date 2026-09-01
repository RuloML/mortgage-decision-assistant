import sys
from decimal import Decimal
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mortgage_decision_assistant.alternatives_engine import (
    AlternativeType,
    generate_alternatives,
)
from mortgage_decision_assistant.boundary_solver import (
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
)
from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.recommendation_engine import (
    RecommendationStatus,
)


st.set_page_config(
    page_title="Mortgage Decision Assistant",
    layout="wide",
)

st.title("Mortgage Decision Assistant")
st.caption(
    "Asistente de estructuración hipotecaria. "
    "Analiza la operación, identifica puntos de ajuste "
    "y propone alternativas verificadas por el motor financiero."
)

defaults = load_financial_defaults()


def D(value):
    return Decimal(str(value))


def format_number_es(value, decimals=0):
    formatted = f"{float(value):,.{decimals}f}"
    return (
        formatted
        .replace(",", "TEMP")
        .replace(".", ",")
        .replace("TEMP", ".")
    )


def money(value):
    if value is None:
        return "—"
    return f"{format_number_es(value, 0)} €"


def signed_money(value):
    if value is None:
        return "—"

    prefix = "+" if value > 0 else ""

    return f"{prefix}{format_number_es(value, 0)} €"


def pct(value):
    if value is None:
        return "—"

    return f"{format_number_es(float(value) * 100, 1)}%"


def ltv_value(result):
    return (
        result.ltv
        if result.ltv is not None
        else result.ltv_provisional
    )


ISSUE_TITLES = {
    "LIQUIDITY": "Liquidez",
    "LTV": "Nivel de financiación",
    "DEBT_CAPACITY": "Capacidad mensual",
    "FINANCING": "Financiación planteada",
}

ALTERNATIVE_TITLES = {
    AlternativeType.PRICE_AND_DOWN_PAYMENT:
        "Ajustar precio y entrada",
    AlternativeType.TERM_EXTENSION:
        "Ampliar plazo",
}


# ============================================================
# INPUTS
# ============================================================

st.subheader("Datos de la operación")

col1, col2, col3 = st.columns(3)

with col1:
    property_price = st.number_input(
        "Precio del inmueble (€)",
        min_value=1.0,
        value=300000.0,
        step=5000.0,
    )

    available_savings = st.number_input(
        "Ahorro disponible (€)",
        min_value=0.0,
        value=100000.0,
        step=5000.0,
    )

    desired_cash_buffer = st.number_input(
        "Colchón deseado tras la operación (€)",
        min_value=0.0,
        value=20000.0,
        step=1000.0,
    )

with col2:
    planned_down_payment = st.number_input(
        "Entrada prevista (€)",
        min_value=0.0,
        value=60000.0,
        step=5000.0,
    )

    monthly_net_income = st.number_input(
        "Ingresos netos mensuales (€)",
        min_value=1.0,
        value=4000.0,
        step=100.0,
    )

    current_monthly_debt = st.number_input(
        "Deuda mensual actual (€)",
        min_value=0.0,
        value=300.0,
        step=50.0,
    )

with col3:
    requested_loan_amount = st.number_input(
        "Hipoteca solicitada (€)",
        min_value=0.0,
        value=240000.0,
        step=5000.0,
    )

    interest_rate_pct = st.number_input(
        "Tipo de interés anual (%)",
        min_value=0.0,
        value=3.0,
        step=0.1,
    )

    term_years = st.number_input(
        "Plazo (años)",
        min_value=1,
        value=30,
        step=1,
    )

with st.expander("Datos avanzados"):
    appraisal_value = st.number_input(
        "Tasación (€)",
        min_value=0.0,
        value=300000.0,
        step=5000.0,
    )

    purchase_cost_rate_pct = st.number_input(
        "Gastos estimados de compra (%)",
        min_value=0.0,
        value=10.0,
        step=0.5,
    )


# ============================================================
# ANALYSIS
# ============================================================

if st.button("Analizar operación", type="primary"):

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

    targets = BoundaryTargets(
        target_profile="STANDARD",
        ltv_target=D("0.80"),
        dsti_target=D("0.40"),
    )

    policy = SimulationPolicy(
        property_price=SimulationVariablePolicy.ADJUSTABLE,
        planned_down_payment=SimulationVariablePolicy.ADJUSTABLE,
    )

    alternatives_result = generate_alternatives(
        base=scenario,
        defaults=defaults,
        targets=targets,
        policy=policy,
    )

    recommendation = alternatives_result.recommendation
    base_result = recommendation.base_financial_result

    st.divider()

    # ========================================================
    # BASE SCENARIO
    # ========================================================

    st.subheader("Situación actual")

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric(
            "Cuota mensual",
            money(base_result.monthly_payment),
        )

    with m2:
        st.metric(
            "LTV",
            pct(ltv_value(base_result)),
        )

    with m3:
        st.metric(
            "DSTI",
            pct(base_result.dsti),
        )

    with m4:
        st.metric(
            "Déficit de liquidez",
            money(base_result.cash_gap),
        )

    # ========================================================
    # DIAGNOSIS
    # ========================================================

    st.subheader("Diagnóstico")

    if recommendation.status == RecommendationStatus.WITHIN_TARGETS:

        st.success(
            "La estructura actual cumple los objetivos "
            "configurados analizados."
        )

    elif recommendation.status == RecommendationStatus.INCOMPLETE:

        st.warning(recommendation.summary)

    elif (
        recommendation.status
        == RecommendationStatus.NO_FEASIBLE_STRUCTURE_FOUND
    ):

        st.warning(recommendation.summary)

    else:

        for issue in recommendation.base_issues:

            title = ISSUE_TITLES.get(
                issue.type,
                issue.type,
            )

            st.warning(
                f"**{title}:** {issue.explanation}"
            )

        # ====================================================
        # MAIN RECOMMENDATION
        # ====================================================

        st.subheader("Recomendación principal")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Precio orientativo",
                money(
                    recommendation.presented_property_price
                ),
                delta=signed_money(
                    recommendation.property_price_change
                ),
            )

        with c2:
            st.metric(
                "Entrada orientativa",
                money(
                    recommendation.presented_down_payment
                ),
                delta=signed_money(
                    recommendation.down_payment_change
                ),
            )

        with c3:
            boundary_result = recommendation.boundary.financial_result

            st.metric(
                "DSTI resultante",
                pct(boundary_result.dsti),
            )

        st.info(
            "La recomendación mostrada corresponde a una "
            "estructura factible verificada por el motor financiero."
        )

        # ====================================================
        # ALTERNATIVES
        # ====================================================

        st.subheader("Alternativas viables")

        if not alternatives_result.alternatives:

            st.write(
                "No se han encontrado alternativas adicionales "
                "dentro de las palancas analizadas."
            )

        for index, alternative in enumerate(
            alternatives_result.alternatives,
            start=1,
        ):

            title = ALTERNATIVE_TITLES[
                alternative.alternative_type
            ]

            with st.container(border=True):

                st.markdown(
                    f"### Opción {index} · {title}"
                )

                st.write(alternative.explanation)

                a1, a2, a3, a4 = st.columns(4)

                with a1:
                    st.metric(
                        "Precio",
                        money(alternative.property_price),
                    )

                with a2:
                    st.metric(
                        "Entrada",
                        money(
                            alternative.planned_down_payment
                        ),
                    )

                with a3:
                    st.metric(
                        "Plazo",
                        (
                            f"{alternative.term_years} años"
                            if alternative.term_years
                            is not None
                            else "—"
                        ),
                    )

                with a4:
                    st.metric(
                        "Cuota",
                        money(
                            alternative
                            .financial_result
                            .monthly_payment
                        ),
                    )

                r1, r2, r3 = st.columns(3)

                with r1:
                    st.write(
                        "**Liquidez:**",
                        money(
                            alternative
                            .financial_result
                            .cash_gap
                        ),
                    )

                with r2:
                    st.write(
                        "**LTV:**",
                        pct(
                            ltv_value(
                                alternative.financial_result
                            )
                        ),
                    )

                with r3:
                    st.write(
                        "**DSTI:**",
                        pct(
                            alternative
                            .financial_result
                            .dsti
                        ),
                    )

    # ========================================================
    # TRACEABILITY
    # ========================================================

    with st.expander("Detalle técnico y trazabilidad"):

        st.write(
            "**Perfil objetivo:** STANDARD"
        )

        st.write(
            "**LTV objetivo:** 80%"
        )

        st.write(
            "**DSTI objetivo:** 40%"
        )

        st.write(
            "**Completitud del cálculo:**",
            base_result
            .metadata
            .calculation_completeness
            .value,
        )

        st.write(
            "**Confianza técnica:**",
            base_result
            .metadata
            .technical_confidence
            .value,
        )

        if recommendation.boundary is not None:

            st.write(
                "**Frontera técnica de precio:**",
                money(
                    recommendation
                    .technical_property_price
                ),
            )

            st.write(
                "**Entrada técnica:**",
                money(
                    recommendation
                    .technical_down_payment
                ),
            )

            st.write(
                "**Restricciones dominantes:**",
                ", ".join(
                    constraint.value
                    for constraint
                    in recommendation
                    .boundary
                    .dominant_constraints
                ),
            )

        if base_result.metadata.assumptions:

            st.write(
                "**Supuestos / fallbacks:**",
                ", ".join(
                    item.value
                    for item
                    in base_result.metadata.assumptions
                ),
            )

        if base_result.metadata.calculation_modes:

            st.write(
                "**Modos de cálculo:**",
                ", ".join(
                    item.value
                    for item
                    in base_result.metadata.calculation_modes
                ),
            )

    st.caption(
        "Herramienta de apoyo a la estructuración. "
        "No predice aprobación bancaria ni sustituye "
        "el análisis profesional."
    )
