import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mortgage_decision_assistant.alternatives_engine import (
    AlternativeType,
    StrategyStatus,
    generate_alternatives,
)
from mortgage_decision_assistant.boundary_solver import (
    BoundaryTargets,
    SimulationPolicy,
    SimulationVariablePolicy,
)
from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.financial_engine import (
    calculate_financial_scenario,
)
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
    AlternativeType.KEEP_DOWN_PAYMENT:
        "Mantener entrada",
    AlternativeType.KEEP_PROPERTY_PRICE:
        "Mantener precio",
    AlternativeType.TERM_EXTENSION:
        "Ampliar plazo",
}

DECISION_STRATEGY_TITLES = {
    AlternativeType.KEEP_DOWN_PAYMENT:
        "Bajar precio manteniendo la entrada",
    AlternativeType.KEEP_PROPERTY_PRICE:
        "Mantener precio aumentando la entrada",
    AlternativeType.TERM_EXTENSION:
        "Mantener estructura ampliando plazo",
}


# ============================================================
# EXPERIENCE MODE
# ============================================================

st.sidebar.title("Modo de trabajo")

experience_mode = st.sidebar.radio(
    "Selecciona tu perfil",
    [
        "Lite · Asesor inmobiliario",
        "Pro · Asesor financiero",
    ],
    index=1,
)

# ============================================================
# LITE · REAL ESTATE ADVISER
# ============================================================

if experience_mode == "Lite · Asesor inmobiliario":

    st.subheader("Preanálisis rápido")

    st.caption(
        "Primer filtro de la operación antes de derivarla "
        "a un análisis financiero completo."
    )

    lite_col1, lite_col2 = st.columns(2)

    with lite_col1:

        lite_price = st.number_input(
            "Precio del inmueble (€)",
            min_value=1.0,
            value=300000.0,
            step=5000.0,
            key="lite_price",
        )

        lite_savings = st.number_input(
            "Ahorro disponible (€)",
            min_value=0.0,
            value=100000.0,
            step=5000.0,
            key="lite_savings",
        )

        lite_down = st.number_input(
            "Entrada prevista (€)",
            min_value=0.0,
            value=60000.0,
            step=5000.0,
            key="lite_down",
        )

    with lite_col2:

        lite_income = st.number_input(
            "Ingresos netos mensuales (€)",
            min_value=1.0,
            value=4000.0,
            step=100.0,
            key="lite_income",
        )

        lite_debt = st.number_input(
            "Deuda mensual actual (€)",
            min_value=0.0,
            value=300.0,
            step=50.0,
            key="lite_debt",
        )

        lite_term = st.number_input(
            "Plazo orientativo (años)",
            min_value=1,
            max_value=40,
            value=30,
            step=1,
            key="lite_term",
        )

    if st.button(
        "Evaluar operación",
        type="primary",
        key="lite_analyse",
    ):

        lite_scenario = FinancialScenario(
            property_price=D(lite_price),
            available_savings=D(lite_savings),

            # Lite keeps the product assumptions simple.
            desired_cash_buffer=(
                defaults.desired_cash_buffer_reference
            ),

            planned_down_payment=D(lite_down),

            monthly_net_income=D(lite_income),
            current_monthly_debt=D(lite_debt),

            # Financing is derived from price and planned down payment.
            requested_loan_amount=None,

            interest_rate_annual=(
                defaults.interest_rate_reference
            ),

            term_years=int(lite_term),

            purchase_cost_rate=(
                defaults.purchase_cost_rate_global_default
            ),

            appraisal_value=None,
        )

        lite_targets = BoundaryTargets(
            target_profile="STANDARD",
            ltv_target=D("0.80"),
            dsti_target=D("0.40"),
        )

        lite_policy = SimulationPolicy(
            property_price=(
                SimulationVariablePolicy.ADJUSTABLE
            ),
            planned_down_payment=(
                SimulationVariablePolicy.ADJUSTABLE
            ),
        )

        lite_result = generate_alternatives(
            base=lite_scenario,
            defaults=defaults,
            targets=lite_targets,
            policy=lite_policy,
        )

        lite_rec = lite_result.recommendation
        lite_financial = lite_rec.base_financial_result

        st.divider()

        if (
            lite_rec.status
            == RecommendationStatus.WITHIN_TARGETS
        ):

            st.success("ENCaja dentro de los objetivos analizados")

            st.write(
                "La estructura inicial no presenta un punto "
                "de ajuste relevante dentro de los criterios "
                "analizados."
            )

        elif (
            lite_rec.status
            == RecommendationStatus.RESTRUCTURING_AVAILABLE
        ):

            st.warning("REQUIERE AJUSTE")

            issue_names = [
                ISSUE_TITLES.get(issue.type, issue.type)
                for issue in lite_rec.base_issues
            ]

            st.write(
                "**Principal punto a revisar:** "
                + ", ".join(issue_names)
            )

            if (
                lite_rec.presented_property_price is not None
            ):

                r1, r2 = st.columns(2)

                with r1:
                    st.metric(
                        "Precio analizado",
                        money(lite_scenario.property_price),
                    )

                with r2:
                    st.metric(
                        "Precio orientativo estructurable",
                        money(
                            lite_rec.presented_property_price
                        ),
                    )

            st.info(
                "Recomendación: derivar la operación al "
                "asesor financiero para revisar la estructura "
                "y las alternativas disponibles."
            )

        else:

            st.warning("REVISAR CON ASESOR FINANCIERO")

            st.write(
                "El preanálisis no permite cerrar una estructura "
                "dentro de los parámetros analizados."
            )

        st.subheader("Indicadores rápidos")

        q1, q2, q3 = st.columns(3)

        with q1:
            st.metric(
                "LTV",
                pct(ltv_value(lite_financial)),
            )

        with q2:
            st.metric(
                "DSTI",
                pct(lite_financial.dsti),
            )

        with q3:
            st.metric(
                "Déficit de liquidez",
                money(lite_financial.cash_gap),
            )

        st.caption(
            "Preanálisis orientativo. No constituye una "
            "decisión bancaria ni sustituye el análisis financiero."
        )

    # Stop here so the Pro interface is not rendered in Lite mode.
    st.stop()


# ============================================================
# INPUTS · PRO
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

analyze_clicked = st.button(
    "Analizar operación",
    type="primary",
)

if analyze_clicked:
    st.session_state["analysis_ready"] = True

if st.session_state.get("analysis_ready", False):

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
            presented_scenario = None
            presented_result = None

            if (
                recommendation.presented_property_price is not None
                and recommendation.presented_down_payment is not None
            ):
                presented_scenario = replace(
                    scenario,
                    property_price=(
                        recommendation.presented_property_price
                    ),
                    planned_down_payment=(
                        recommendation.presented_down_payment
                    ),
                    requested_loan_amount=None,
                )

                presented_result = calculate_financial_scenario(
                    presented_scenario,
                    defaults=defaults,
                )

            st.metric(
                "DSTI resultante",
                pct(
                    presented_result.dsti
                    if presented_result is not None
                    else None
                ),
            )

        st.info(
            "La recomendación mostrada corresponde a una "
            "estructura factible verificada por el motor financiero."
        )

        # ====================================================
        # BEFORE / AFTER COMPARISON
        # ====================================================

        if (
            presented_scenario is not None
            and presented_result is not None
        ):

            st.subheader("Actual vs recomendación")

            comparison_rows = [
                {
                    "Métrica": "Precio",
                    "Actual": money(scenario.property_price),
                    "Recomendación": money(
                        presented_scenario.property_price
                    ),
                    "Variación": signed_money(
                        presented_scenario.property_price
                        - scenario.property_price
                    ),
                },
                {
                    "Métrica": "Entrada",
                    "Actual": money(
                        scenario.planned_down_payment
                    ),
                    "Recomendación": money(
                        presented_scenario.planned_down_payment
                    ),
                    "Variación": signed_money(
                        presented_scenario.planned_down_payment
                        - scenario.planned_down_payment
                    ),
                },
                {
                    "Métrica": "Cuota mensual",
                    "Actual": money(
                        base_result.monthly_payment
                    ),
                    "Recomendación": money(
                        presented_result.monthly_payment
                    ),
                    "Variación": signed_money(
                        presented_result.monthly_payment
                        - base_result.monthly_payment
                    ),
                },
                {
                    "Métrica": "LTV",
                    "Actual": pct(
                        ltv_value(base_result)
                    ),
                    "Recomendación": pct(
                        ltv_value(presented_result)
                    ),
                    "Variación": (
                        f"{format_number_es(
                            float(
                                ltv_value(presented_result)
                                - ltv_value(base_result)
                            ) * 100,
                            1,
                        )} pp"
                    ),
                },
                {
                    "Métrica": "DSTI",
                    "Actual": pct(base_result.dsti),
                    "Recomendación": pct(
                        presented_result.dsti
                    ),
                    "Variación": (
                        f"{format_number_es(
                            float(
                                presented_result.dsti
                                - base_result.dsti
                            ) * 100,
                            1,
                        )} pp"
                    ),
                },
                {
                    "Métrica": "Déficit de liquidez",
                    "Actual": money(base_result.cash_gap),
                    "Recomendación": money(
                        presented_result.cash_gap
                    ),
                    "Variación": signed_money(
                        presented_result.cash_gap
                        - base_result.cash_gap
                    ),
                },
                {
                    "Métrica": "Ahorro residual",
                    "Actual": money(
                        base_result.residual_savings
                    ),
                    "Recomendación": money(
                        presented_result.residual_savings
                    ),
                    "Variación": signed_money(
                        presented_result.residual_savings
                        - base_result.residual_savings
                    ),
                },
                {
                    "Métrica": "Plazo",
                    "Actual": f"{scenario.term_years} años",
                    "Recomendación": (
                        f"{presented_scenario.term_years} años"
                    ),
                    "Variación": (
                        f"{presented_scenario.term_years - scenario.term_years:+d} años"
                    ),
                },
            ]

            st.dataframe(
                comparison_rows,
                use_container_width=True,
                hide_index=True,
            )

            # ====================================================
            # SENSITIVITY
            # ====================================================

            st.subheader("Explorar escenarios")

            st.caption(
                "Modifica una variable y observa cómo cambia "
                "la estructura financiera."
            )

            sensitivity_variable = st.selectbox(
                "Variable a modificar",
                [
                    "Tipo de interés",
                    "Ingresos mensuales",
                    "Entrada",
                    "Precio",
                    "Plazo",
                ],
            )

            sensitivity_scenario = scenario

            if sensitivity_variable == "Tipo de interés":

                new_rate = st.number_input(
                    "Nuevo tipo de interés (%)",
                    min_value=0.0,
                    value=float(interest_rate_pct),
                    step=0.1,
                    key="sens_rate",
                )

                sensitivity_scenario = replace(
                    scenario,
                    interest_rate_annual=(
                        D(new_rate) / D("100")
                    ),
                )

            elif sensitivity_variable == "Ingresos mensuales":

                new_income = st.number_input(
                    "Nuevos ingresos netos mensuales (€)",
                    min_value=1.0,
                    value=float(monthly_net_income),
                    step=100.0,
                    key="sens_income",
                )

                sensitivity_scenario = replace(
                    scenario,
                    monthly_net_income=D(new_income),
                )

            elif sensitivity_variable == "Entrada":

                new_down = st.number_input(
                    "Nueva entrada (€)",
                    min_value=0.0,
                    value=float(planned_down_payment),
                    step=1000.0,
                    key="sens_down",
                )

                sensitivity_scenario = replace(
                    scenario,
                    planned_down_payment=D(new_down),
                    requested_loan_amount=None,
                )

            elif sensitivity_variable == "Precio":

                new_price = st.number_input(
                    "Nuevo precio (€)",
                    min_value=1.0,
                    value=float(property_price),
                    step=1000.0,
                    key="sens_price",
                )

                sensitivity_scenario = replace(
                    scenario,
                    property_price=D(new_price),
                    requested_loan_amount=None,
                )

            elif sensitivity_variable == "Plazo":

                new_term = st.number_input(
                    "Nuevo plazo (años)",
                    min_value=1,
                    max_value=40,
                    value=int(term_years),
                    step=1,
                    key="sens_term",
                )

                sensitivity_scenario = replace(
                    scenario,
                    term_years=int(new_term),
                )

            sensitivity_result = calculate_financial_scenario(
                sensitivity_scenario,
                defaults=defaults,
            )

            s1, s2, s3, s4 = st.columns(4)

            with s1:
                st.metric(
                    "Cuota",
                    money(sensitivity_result.monthly_payment),
                    delta=signed_money(
                        sensitivity_result.monthly_payment
                        - base_result.monthly_payment
                    ),
                )

            with s2:
                st.metric(
                    "DSTI",
                    pct(sensitivity_result.dsti),
                )

            with s3:
                st.metric(
                    "LTV",
                    pct(
                        ltv_value(sensitivity_result)
                    ),
                )

            with s4:
                st.metric(
                    "Déficit de liquidez",
                    money(sensitivity_result.cash_gap),
                    delta=signed_money(
                        sensitivity_result.cash_gap
                        - base_result.cash_gap
                    ),
                )

        # ====================================================
        # ALTERNATIVES
        # ====================================================

        st.subheader("Otras estrategias posibles")

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

        # ====================================================
        # DECISION MAP
        # ====================================================

        st.subheader("Opciones para reestructurar la operación")

        st.caption(
            "El sistema analiza distintas estrategias y muestra "
            "cuáles pueden resolver las restricciones detectadas."
        )

        status_icons = {
            StrategyStatus.VIABLE: "✅",
            StrategyStatus.NOT_VIABLE: "❌",
            StrategyStatus.NOT_RELEVANT: "◯",
            StrategyStatus.DUPLICATE_MAIN: "=",
        }

        status_labels = {
            StrategyStatus.VIABLE: "Opción viable",
            StrategyStatus.NOT_VIABLE: "No resuelve la operación",
            StrategyStatus.NOT_RELEVANT:
                "No aplica al problema actual",
            StrategyStatus.DUPLICATE_MAIN:
                "Coincide con la recomendación principal",
        }

        for evaluation in alternatives_result.strategy_evaluations:

            strategy_name = DECISION_STRATEGY_TITLES[
                evaluation.alternative_type
            ]

            icon = status_icons[evaluation.status]
            status_label = status_labels[evaluation.status]

            with st.container(border=True):

                st.markdown(
                    f"**{icon} {strategy_name} · {status_label}**"
                )

                st.write(evaluation.explanation)

                if (
                    evaluation.status == StrategyStatus.VIABLE
                    and evaluation.alternative is not None
                ):

                    alt = evaluation.alternative
                    alt_financial = alt.financial_result

                    d1, d2, d3 = st.columns(3)

                    with d1:
                        st.metric(
                            "Precio",
                            money(alt.property_price),
                        )

                    with d2:
                        st.metric(
                            "Entrada",
                            money(alt.planned_down_payment),
                        )

                    with d3:
                        st.metric(
                            "Plazo",
                            (
                                f"{alt.term_years} años"
                                if alt.term_years is not None
                                else "—"
                            ),
                        )

                    i1, i2, i3 = st.columns(3)

                    with i1:
                        st.metric(
                            "Cuota estimada",
                            money(alt_financial.monthly_payment),
                        )

                    with i2:
                        st.metric(
                            "DSTI resultante",
                            pct(alt_financial.dsti),
                        )

                    with i3:
                        st.metric(
                            "LTV resultante",
                            pct(ltv_value(alt_financial)),
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
