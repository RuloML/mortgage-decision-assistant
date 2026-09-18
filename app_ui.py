import sys
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import plotly.graph_objects as go
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
from mortgage_decision_assistant.bank_fit_engine import (
    BorrowerProfile,
    CriterionStatus,
    ProductStatus,
    evaluate_bank_fit,
)
from mortgage_decision_assistant.config import load_financial_defaults
from mortgage_decision_assistant.domain import FinancialScenario
from mortgage_decision_assistant.financial_engine import calculate_financial_scenario
from mortgage_decision_assistant.presentation import (
    PresentationState,
    build_operation_status_payload,
    build_recommendation_comparison_payload,
    ltv_value,
    money_text,
    pct_text,
)
from mortgage_decision_assistant.recommendation_engine import RecommendationStatus


st.set_page_config(page_title="Mortgage Decision Assistant", layout="wide")
st.title("Mortgage Decision Assistant")
st.caption(
    "Asistente de estructuración hipotecaria. Analiza la operación, "
    "identifica puntos de ajuste y propone alternativas verificadas "
    "por el motor financiero."
)

defaults = load_financial_defaults()


def D(value):
    return Decimal(str(value))


def signed_money(value):
    if value is None:
        return "—"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{money_text(value)}"


ISSUE_TITLES = {
    "LIQUIDITY": "Liquidez disponible",
    "LTV": "Financiación sobre valor",
    "DEBT_CAPACITY": "Ratio de endeudamiento",
    "FINANCING": "Financiación planteada",
}

ALTERNATIVE_TITLES = {
    AlternativeType.KEEP_DOWN_PAYMENT: "Mantener entrada",
    AlternativeType.KEEP_PROPERTY_PRICE: "Mantener precio",
    AlternativeType.TERM_EXTENSION: "Ampliar plazo",
}

DECISION_STRATEGY_TITLES = {
    AlternativeType.KEEP_DOWN_PAYMENT: "Bajar precio manteniendo la entrada",
    AlternativeType.KEEP_PROPERTY_PRICE: "Mantener precio aumentando la entrada",
    AlternativeType.TERM_EXTENSION: "Mantener estructura ampliando plazo",
}

STATE_LABELS = {
    PresentationState.WITHIN_TARGET: "Dentro del objetivo",
    PresentationState.REQUIRES_ADJUSTMENT: "Requiere ajuste",
}

STATE_ICONS = {
    PresentationState.WITHIN_TARGET: "🟢",
    PresentationState.REQUIRES_ADJUSTMENT: "🔴",
}


def render_status_cards(payload):
    metrics = [payload.liquidity, payload.ltv, payload.dsti]
    all_within = all(
        metric.state == PresentationState.WITHIN_TARGET for metric in metrics
    )

    st.subheader("Estado de la operación")

    if all_within:
        st.success("🟢 La estructura está dentro de los objetivos analizados.")
    else:
        columns = st.columns(3)
        descriptions = {
            "liquidity": "Ahorro disponible tras entrada, gastos y colchón.",
            "ltv": "Nivel de financiación de la operación.",
            "dsti": "Peso mensual de hipoteca y deudas sobre los ingresos.",
        }

        for column, metric in zip(columns, metrics):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{metric.label}**")
                    st.markdown(
                        f"{STATE_ICONS[metric.state]} "
                        f"**{STATE_LABELS[metric.state]}**"
                    )
                    st.caption(descriptions[metric.key])

    with st.expander("Ver detalle técnico"):
        st.write(
            "**Liquidez:**",
            payload.liquidity.value_text,
            "· Objetivo:",
            payload.liquidity.target_text,
        )
        st.write(
            "**Financiación sobre valor (LTV):**",
            payload.ltv.value_text,
            "· Objetivo máximo:",
            payload.ltv.target_text,
        )
        st.write(
            "**Ratio de endeudamiento (DSTI):**",
            payload.dsti.value_text,
            "· Objetivo máximo:",
            payload.dsti.target_text,
        )
        st.caption(
            "Los límites son inclusivos: un valor exactamente igual al "
            "objetivo se considera dentro del objetivo."
        )


def build_financial_impact_chart(comparison):
    categories = [
        "Ratio de endeudamiento (DSTI)",
        "Financiación sobre valor (LTV)",
    ]

    actual_values = [
        float(comparison.actual_dsti) if comparison.actual_dsti is not None else None,
        float(comparison.actual_ltv) if comparison.actual_ltv is not None else None,
    ]
    recommended_values = [
        float(comparison.recommended_dsti)
        if comparison.recommended_dsti is not None
        else None,
        float(comparison.recommended_ltv)
        if comparison.recommended_ltv is not None
        else None,
    ]

    actual_text = [
        comparison.actual_dsti_text,
        comparison.actual_ltv_text,
    ]
    recommended_text = [
        comparison.recommended_dsti_text,
        comparison.recommended_ltv_text,
    ]

    fig = go.Figure()
    fig.add_bar(
        name="Actual",
        x=categories,
        y=actual_values,
        text=actual_text,
        textposition="outside",
        hovertemplate="%{x}<br>Actual: %{text}<extra></extra>",
    )
    fig.add_bar(
        name="Recomendado",
        x=categories,
        y=recommended_values,
        text=recommended_text,
        textposition="outside",
        hovertemplate="%{x}<br>Recomendado: %{text}<extra></extra>",
    )
    fig.update_layout(
        barmode="group",
        yaxis=dict(
            range=[0, 1],
            tickformat=".0%",
            title="Porcentaje",
        ),
        xaxis_title=None,
        legend_title_text=None,
        margin=dict(l=20, r=20, t=20, b=20),
        height=380,
    )
    return fig


def render_actual_vs_recommended(payload):
    comparison = payload.comparison
    if comparison is None:
        return

    st.subheader("Actual vs recomendado")

    structure_col1, structure_col2 = st.columns(2)

    with structure_col1:
        with st.container(border=True):
            st.markdown("**Precio**")
            st.write(
                f"{comparison.actual_price_text}  →  "
                f"**{comparison.recommended_price_text}**"
            )

    with structure_col2:
        with st.container(border=True):
            st.markdown("**Entrada**")
            st.write(
                f"{comparison.actual_down_payment_text}  →  "
                f"**{comparison.recommended_down_payment_text}**"
            )

    st.markdown("#### Impacto financiero")
    st.plotly_chart(
        build_financial_impact_chart(comparison),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.caption(
        "Objetivo aplicado: mantener el mayor precio posible dentro de "
        "los objetivos analizados."
    )


# ============================================================
# EXPERIENCE MODE
# ============================================================

st.sidebar.title("Modo de trabajo")
experience_mode = st.sidebar.radio(
    "Selecciona tu perfil",
    ["Lite · Asesor inmobiliario", "Pro · Asesor financiero"],
    index=1,
)


# ============================================================
# LITE · REAL ESTATE ADVISER
# ============================================================

if experience_mode == "Lite · Asesor inmobiliario":
    st.subheader("Preanálisis rápido")
    st.caption(
        "Primer filtro de la operación antes de derivarla a un análisis "
        "financiero completo."
    )

    lite_col1, lite_col2 = st.columns(2)

    with lite_col1:
        lite_price = st.number_input(
            "Precio del inmueble (€)", min_value=1.0, value=300000.0, step=5000.0
        )
        lite_savings = st.number_input(
            "Ahorro disponible (€)", min_value=0.0, value=100000.0, step=5000.0
        )
        lite_down = st.number_input(
            "Entrada prevista (€)", min_value=0.0, value=60000.0, step=5000.0
        )

    with lite_col2:
        lite_income = st.number_input(
            "Ingresos netos mensuales (€)", min_value=1.0, value=4000.0, step=100.0
        )
        lite_debt = st.number_input(
            "Deuda mensual actual (€)", min_value=0.0, value=300.0, step=50.0
        )
        lite_term = st.number_input(
            "Plazo orientativo (años)", min_value=1, max_value=40, value=30, step=1
        )

    if st.button("Evaluar operación", type="primary", key="lite_analyse"):
        lite_scenario = FinancialScenario(
            property_price=D(lite_price),
            available_savings=D(lite_savings),
            desired_cash_buffer=defaults.desired_cash_buffer_reference,
            planned_down_payment=D(lite_down),
            monthly_net_income=D(lite_income),
            current_monthly_debt=D(lite_debt),
            requested_loan_amount=None,
            interest_rate_annual=defaults.interest_rate_reference,
            term_years=int(lite_term),
            purchase_cost_rate=defaults.purchase_cost_rate_global_default,
            appraisal_value=None,
        )

        lite_targets = BoundaryTargets(
            target_profile="STANDARD",
            ltv_target=D("0.80"),
            dsti_target=D("0.40"),
        )
        lite_policy = SimulationPolicy(
            property_price=SimulationVariablePolicy.ADJUSTABLE,
            planned_down_payment=SimulationVariablePolicy.ADJUSTABLE,
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

        if lite_rec.status == RecommendationStatus.WITHIN_TARGETS:
            st.success("Encaja dentro de los objetivos analizados")
            st.write(
                "La estructura inicial no presenta un punto de ajuste "
                "relevante dentro de los criterios analizados."
            )
        elif lite_rec.status == RecommendationStatus.RESTRUCTURING_AVAILABLE:
            st.warning("REQUIERE AJUSTE")
            issue_names = [
                ISSUE_TITLES.get(issue.type, issue.type)
                for issue in lite_rec.base_issues
            ]
            st.write("**Principal punto a revisar:** " + ", ".join(issue_names))
            if lite_rec.presented_property_price is not None:
                r1, r2 = st.columns(2)
                with r1:
                    st.metric("Precio analizado", money_text(lite_scenario.property_price))
                with r2:
                    st.metric(
                        "Precio orientativo estructurable",
                        money_text(lite_rec.presented_property_price),
                    )
            st.info(
                "Recomendación: derivar la operación al asesor financiero "
                "para revisar la estructura y las alternativas disponibles."
            )
        else:
            st.warning("REVISAR CON ASESOR FINANCIERO")
            st.write(
                "El preanálisis no permite cerrar una estructura dentro "
                "de los parámetros analizados."
            )

        st.subheader("Indicadores rápidos")
        q1, q2, q3 = st.columns(3)
        with q1:
            st.metric(
                "Financiación sobre valor (LTV)",
                pct_text(ltv_value(lite_financial)),
            )
        with q2:
            st.metric(
                "Ratio de endeudamiento (DSTI)",
                pct_text(lite_financial.dsti),
            )
        with q3:
            st.metric("Déficit de liquidez", money_text(lite_financial.cash_gap))

        st.caption(
            "El déficit de liquidez considera los gastos estimados de compra "
            f"({pct_text(defaults.purchase_cost_rate_global_default)}) y el "
            "colchón mínimo de ahorro que se intenta preservar "
            f"({money_text(defaults.desired_cash_buffer_reference)})."
        )
        st.caption(
            "Preanálisis orientativo. No constituye una decisión bancaria "
            "ni sustituye el análisis financiero."
        )

    st.stop()


# ============================================================
# INPUTS · PRO
# ============================================================

st.subheader("Datos de la operación")
col1, col2, col3 = st.columns(3)

with col1:
    property_price = st.number_input(
        "Precio del inmueble (€)", min_value=1.0, value=300000.0, step=5000.0
    )
    available_savings = st.number_input(
        "Ahorro disponible (€)", min_value=0.0, value=100000.0, step=5000.0
    )
    desired_cash_buffer = st.number_input(
        "Colchón deseado tras la operación (€)",
        min_value=0.0,
        value=20000.0,
        step=1000.0,
    )

with col2:
    planned_down_payment = st.number_input(
        "Entrada prevista (€)", min_value=0.0, value=60000.0, step=5000.0
    )
    monthly_net_income = st.number_input(
        "Ingresos netos mensuales conjuntos (€)",
        min_value=1.0,
        value=4000.0,
        step=100.0,
        help="Suma de los ingresos netos mensuales computables de todos los titulares.",
    )
    current_monthly_debt = st.number_input(
        "Deuda mensual actual (€)", min_value=0.0, value=300.0, step=50.0
    )

with col3:
    requested_loan_amount = st.number_input(
        "Hipoteca solicitada (€)", min_value=0.0, value=240000.0, step=5000.0
    )
    interest_rate_pct = st.number_input(
        "Tipo de interés anual (%)", min_value=0.0, value=3.0, step=0.1
    )
    term_years = st.number_input(
        "Plazo (años)", min_value=1, max_value=40, value=30, step=1
    )

with st.expander("Datos avanzados"):
    appraisal_value = st.number_input(
        "Tasación (€)", min_value=0.0, value=300000.0, step=5000.0
    )
    purchase_cost_rate_pct = st.number_input(
        "Gastos estimados de compra (%)", min_value=0.0, value=10.0, step=0.5
    )

with st.expander("Perfil para compatibilidad con criterios públicos de entidades"):
    st.caption(
        "Datos usados únicamente por el prototipo académico Bank Fit. "
        "No predice aprobación bancaria ni sustituye el criterio profesional."
    )
    bank_num_borrowers = st.number_input(
        "Número de titulares",
        min_value=1,
        max_value=4,
        value=1,
        step=1,
        key="bank_num_borrowers",
    )
    borrower_ages = []
    age_columns = st.columns(int(bank_num_borrowers))
    for borrower_index, age_column in enumerate(age_columns, start=1):
        with age_column:
            borrower_ages.append(
                int(
                    st.number_input(
                        f"Edad titular {borrower_index}",
                        min_value=18,
                        max_value=90,
                        value=40,
                        step=1,
                        key=f"bank_age_{borrower_index}",
                    )
                )
            )

    property_use_label = st.selectbox(
        "Uso de la vivienda",
        ["Vivienda habitual", "Segunda residencia"],
        key="bank_property_use",
    )
    residency_label = st.selectbox(
        "Residencia",
        ["Residente en España", "No residente", "No indicado"],
        key="bank_residency",
    )

analyze_clicked = st.button("Analizar operación", type="primary")
if analyze_clicked:
    st.session_state["analysis_ready"] = True


# ============================================================
# ANALYSIS · PRO
# ============================================================

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
        appraisal_value=D(appraisal_value) if appraisal_value > 0 else None,
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

    analysis_tab, bank_fit_tab, scenarios_tab = st.tabs(
        ["Análisis y recomendación", "Bank Fit", "Escenarios"]
    )

    with analysis_tab:
        st.subheader("Situación actual")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Cuota mensual", money_text(base_result.monthly_payment))
        with m2:
            st.metric("Financiación sobre valor (LTV)", pct_text(ltv_value(base_result)))
        with m3:
            st.metric("Ratio de endeudamiento (DSTI)", pct_text(base_result.dsti))
        with m4:
            st.metric("Déficit de liquidez", money_text(base_result.cash_gap))

        st.subheader("Diagnóstico")

        if recommendation.status == RecommendationStatus.WITHIN_TARGETS:
            st.success("La estructura actual cumple los objetivos configurados analizados.")
        elif recommendation.status in {
            RecommendationStatus.INCOMPLETE,
            RecommendationStatus.NO_FEASIBLE_STRUCTURE_FOUND,
        }:
            st.warning(recommendation.summary)
        else:
            for issue in recommendation.base_issues:
                title = ISSUE_TITLES.get(issue.type, issue.type)
                st.warning(f"**{title}:** {issue.explanation}")

        status_payload = build_operation_status_payload(
            base_result,
            ltv_target=targets.ltv_target,
            dsti_target=targets.dsti_target,
        )
        render_status_cards(status_payload)

        if recommendation.status == RecommendationStatus.RESTRUCTURING_AVAILABLE:
            if (
                recommendation.presented_property_price is not None
                and recommendation.presented_down_payment is not None
            ):
                bank_fit_recommended_scenario = replace(
                    scenario,
                    property_price=recommendation.presented_property_price,
                    planned_down_payment=recommendation.presented_down_payment,
                    requested_loan_amount=None,
                )
                bank_fit_recommended_result = calculate_financial_scenario(
                    bank_fit_recommended_scenario,
                    defaults=defaults,
                )
                bank_fit_choice = st.radio(
                    "Estructura a comparar con las entidades",
                    ["Recomendada", "Actual"],
                    horizontal=True,
                    key="bank_fit_scenario_choice",
                    help=(
                        "Por defecto se evalúa la estructura recomendada. "
                        "Puedes volver al escenario actual para comparar."
                    ),
                )
                if bank_fit_choice == "Recomendada":
                    bank_fit_scenario = bank_fit_recommended_scenario
                    bank_fit_financial_result = bank_fit_recommended_result
                    bank_fit_scenario_label = "Escenario recomendado"

        st.caption(f"Estructura evaluada: **{bank_fit_scenario_label}**")

        bank_fit_results = evaluate_bank_fit(
            scenario=bank_fit_scenario,
            result=bank_fit_financial_result,
            profile=bank_profile,
        )

        comparable_results = [
            item
            for item in bank_fit_results
            if item.product_status != ProductStatus.INELIGIBLE_PRODUCT
        ]

        if not comparable_results:
            st.info(
                "No hay productos comparables con el perfil indicado dentro "
                "del dataset académico actual."
            )
        else:
            for bank_fit in comparable_results:
                with st.container(border=True):
                    st.markdown(
                        f"### {bank_fit.bank_name} · {bank_fit.product_name}"
                    )

                    if bank_fit.product_status == ProductStatus.INSUFFICIENT_INFORMATION:
                        st.warning(
                            "Información insuficiente para comparar este producto "
                            "con fiabilidad."
                        )
                    elif bank_fit.hard_mismatches > 0:
                        st.warning(
                            "Se han detectado criterios públicos duros que la "
                            "estructura evaluada no cumple."
                        )
                    else:
                        st.success(
                            "No se han detectado incumplimientos en los criterios "
                            "públicos duros que han podido evaluarse."
                        )

                    evaluable_hard = (
                        bank_fit.hard_matches + bank_fit.hard_mismatches
                    )
                    compatibility_text = (
                        f"{bank_fit.hard_matches}/{evaluable_hard}"
                        if evaluable_hard > 0
                        else "—"
                    )

                    bf1, bf2, bf3, bf4 = st.columns(4)
                    with bf1:
                        st.metric("Criterios duros", compatibility_text)
                    with bf2:
                        st.metric(
                            "Cobertura core",
                            f"{float(bank_fit.core_coverage) * 100:.0f}%",
                        )
                    with bf3:
                        st.metric(
                            "Mismatches duros",
                            str(bank_fit.hard_mismatches),
                        )
                    with bf4:
                        st.metric(
                            "Criterios desconocidos",
                            str(bank_fit.unknown_count),
                        )

                    if (
                        bank_fit.guidance_matches
                        or bank_fit.guidance_mismatches
                    ):
                        st.caption(
                            "Orientaciones públicas: "
                            f"{bank_fit.guidance_matches} compatibles · "
                            f"{bank_fit.guidance_mismatches} no compatibles. "
                            "Estas orientaciones no se tratan como límites duros."
                        )

                    with st.expander("Ver criterios y trazabilidad"):
                        rows = []
                        for criterion in bank_fit.criteria:
                            status_label = {
                                CriterionStatus.MATCH: "Cumple",
                                CriterionStatus.MISMATCH: "No cumple",
                                CriterionStatus.UNKNOWN: "Desconocido",
                                CriterionStatus.NOT_APPLICABLE: "No aplica",
                            }[criterion.status]

                            rows.append(
                                {
                                    "Criterio": criterion.criterion_id,
                                    "Estado": status_label,
                                    "Evidencia": criterion.evidence_type.value,
                                    "Valor observado": (
                                        str(criterion.actual_value)
                                        if criterion.actual_value is not None
                                        else "—"
                                    ),
                                    "Criterio publicado": (
                                        str(criterion.criterion_value)
                                        if criterion.criterion_value is not None
                                        else "—"
                                    ),
                                    "Fuente": criterion.source_status,
                                    "Verificado": criterion.verified_at or "—",
                                    "Revisar antes de": criterion.review_due_at or "—",
                                }
                            )

                        st.dataframe(
                            rows,
                            width="stretch",
                            hide_index=True,
                        )

                        source_urls = []
                        for criterion in bank_fit.criteria:
                            if (
                                criterion.source_url
                                and criterion.source_url not in source_urls
                            ):
                                source_urls.append(criterion.source_url)

                        if source_urls:
                            st.markdown("**Fuentes oficiales consultadas**")
                            for source_index, source_url in enumerate(
                                source_urls,
                                start=1,
                            ):
                                st.markdown(
                                    f"- [Fuente oficial {source_index}]({source_url})"
                                )

                    st.caption(
                        "Compatibilidad documental, no recomendación de entidad "
                        "ni predicción de concesión."
                    )

        if recommendation.status == RecommendationStatus.RESTRUCTURING_AVAILABLE:
            st.subheader("Objetivo de la recomendación")
            st.write(
                "**Mantener el mayor precio posible dentro de los objetivos analizados.**"
            )
            with st.expander("¿Por qué esta recomendación?"):
                st.write(
                    "El sistema busca una estructura que cumpla los objetivos "
                    "configurados de liquidez, financiación y ratio de "
                    "endeudamiento, intentando conservar el mayor precio de "
                    "compra posible."
                )

            presented_scenario = None
            presented_result = None

            if (
                recommendation.presented_property_price is not None
                and recommendation.presented_down_payment is not None
            ):
                presented_scenario = replace(
                    scenario,
                    property_price=recommendation.presented_property_price,
                    planned_down_payment=recommendation.presented_down_payment,
                    requested_loan_amount=None,
                )
                presented_result = calculate_financial_scenario(
                    presented_scenario,
                    defaults=defaults,
                )

            st.subheader("Recomendación principal")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(
                    "Precio orientativo",
                    money_text(recommendation.presented_property_price),
                    delta=signed_money(recommendation.property_price_change),
                )
            with c2:
                st.metric(
                    "Entrada orientativa",
                    money_text(recommendation.presented_down_payment),
                    delta=signed_money(recommendation.down_payment_change),
                )
            with c3:
                st.metric(
                    "Ratio de endeudamiento resultante",
                    pct_text(presented_result.dsti if presented_result else None),
                )

            st.caption(
                "Esta propuesta conserva el mayor precio posible entre las "
                "estructuras evaluadas que cumplen los objetivos configurados."
            )

            if presented_scenario is not None and presented_result is not None:
                comparison_payload = build_recommendation_comparison_payload(
                    base_scenario=scenario,
                    base_result=base_result,
                    recommended_scenario=presented_scenario,
                    recommended_result=presented_result,
                    ltv_target=targets.ltv_target,
                    dsti_target=targets.dsti_target,
                )
                render_actual_vs_recommended(comparison_payload)

                with st.expander("Ver comparación técnica completa"):
                    technical_rows = [
                        {
                            "Métrica": "Precio",
                            "Actual": money_text(scenario.property_price),
                            "Recomendado": money_text(presented_scenario.property_price),
                        },
                        {
                            "Métrica": "Entrada",
                            "Actual": money_text(scenario.planned_down_payment),
                            "Recomendado": money_text(
                                presented_scenario.planned_down_payment
                            ),
                        },
                        {
                            "Métrica": "Cuota mensual",
                            "Actual": money_text(base_result.monthly_payment),
                            "Recomendado": money_text(presented_result.monthly_payment),
                        },
                        {
                            "Métrica": "Financiación sobre valor (LTV)",
                            "Actual": pct_text(ltv_value(base_result)),
                            "Recomendado": pct_text(ltv_value(presented_result)),
                        },
                        {
                            "Métrica": "Ratio de endeudamiento (DSTI)",
                            "Actual": pct_text(base_result.dsti),
                            "Recomendado": pct_text(presented_result.dsti),
                        },
                        {
                            "Métrica": "Déficit de liquidez",
                            "Actual": money_text(base_result.cash_gap),
                            "Recomendado": money_text(presented_result.cash_gap),
                        },
                        {
                            "Métrica": "Ahorro residual",
                            "Actual": money_text(base_result.residual_savings),
                            "Recomendado": money_text(presented_result.residual_savings),
                        },
                        {
                            "Métrica": "Plazo",
                            "Actual": f"{scenario.term_years} años",
                            "Recomendado": f"{presented_scenario.term_years} años",
                        },
                    ]
                    st.dataframe(
                        technical_rows,
                        use_container_width=True,
                        hide_index=True,
                    )

            st.subheader("Otras estrategias")
            st.caption(
                "Cada estrategia responde a un objetivo distinto. El sistema muestra cuáles "
                "pueden resolver las restricciones detectadas sin duplicar la recomendación principal."
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
                StrategyStatus.NOT_RELEVANT: "No aplica al problema actual",
                StrategyStatus.DUPLICATE_MAIN: "Coincide con la recomendación principal",
            }

            for evaluation in alternatives_result.strategy_evaluations:
                strategy_name = DECISION_STRATEGY_TITLES[evaluation.alternative_type]
                icon = status_icons[evaluation.status]
                status_label = status_labels[evaluation.status]

                with st.container(border=True):
                    st.markdown(f"**{icon} {strategy_name} · {status_label}**")
                    st.write(evaluation.explanation)

                    if (
                        evaluation.status == StrategyStatus.VIABLE
                        and evaluation.alternative is not None
                    ):
                        alt = evaluation.alternative
                        alt_financial = alt.financial_result
                        d1, d2, d3 = st.columns(3)
                        with d1:
                            st.metric("Precio", money_text(alt.property_price))
                        with d2:
                            st.metric("Entrada", money_text(alt.planned_down_payment))
                        with d3:
                            st.metric(
                                "Plazo",
                                f"{alt.term_years} años"
                                if alt.term_years is not None
                                else "—",
                            )

                        i1, i2, i3 = st.columns(3)
                        with i1:
                            st.metric(
                                "Cuota estimada",
                                money_text(alt_financial.monthly_payment),
                            )
                        with i2:
                            st.metric(
                                "Ratio de endeudamiento resultante",
                                pct_text(alt_financial.dsti),
                            )
                        with i3:
                            st.metric(
                                "Financiación sobre valor resultante",
                                pct_text(ltv_value(alt_financial)),
                            )

        with st.expander("Detalle técnico y trazabilidad"):
            st.write("**Perfil objetivo:** STANDARD")
            st.write("**LTV objetivo máximo:** 80%")
            st.write("**DSTI objetivo máximo:** 40%")
            st.write(
                "**Completitud del cálculo:**",
                base_result.metadata.calculation_completeness.value,
            )
            st.write(
                "**Confianza técnica:**",
                base_result.metadata.technical_confidence.value,
            )

            if recommendation.boundary is not None:
                st.write(
                    "**Frontera técnica de precio:**",
                    money_text(recommendation.technical_property_price),
                )
                st.write(
                    "**Entrada técnica:**",
                    money_text(recommendation.technical_down_payment),
                )
                st.write(
                    "**Restricciones dominantes:**",
                    ", ".join(
                        constraint.value
                        for constraint in recommendation.boundary.dominant_constraints
                    ),
                )

            if base_result.metadata.assumptions:
                st.write(
                    "**Supuestos / fallbacks:**",
                    ", ".join(item.value for item in base_result.metadata.assumptions),
                )

            if base_result.metadata.calculation_modes:
                st.write(
                    "**Modos de cálculo:**",
                    ", ".join(
                        item.value for item in base_result.metadata.calculation_modes
                    ),
                )

        st.caption(
            "Herramienta de apoyo a la estructuración. No predice aprobación "
            "bancaria ni sustituye el análisis profesional."
        )


    with bank_fit_tab:
        # ========================================================
        # BANK FIT · ACADEMIC / TFM PROTOTYPE
        # ========================================================

        st.subheader("Compatibilidad con criterios públicos de entidades")
        st.caption(
            "Prototipo académico para TFM. Compara la estructura con criterios "
            "públicos documentados; no estima probabilidad de aprobación, no "
            "recomienda una entidad y no debe utilizarse operativamente con "
            "prestatarios reales sin revisión jurídica previa."
        )

        bank_profile = BorrowerProfile(
            borrower_ages=tuple(borrower_ages),
            property_use=(
                "PRIMARY_HOME"
                if property_use_label == "Vivienda habitual"
                else "SECOND_HOME"
            ),
            residency_status=(
                "RESIDENT_ES"
                if residency_label == "Residente en España"
                else (
                    "NON_RESIDENT"
                    if residency_label == "No residente"
                    else None
                )
            ),
        )

        bank_fit_scenario = scenario
        bank_fit_financial_result = base_result
        bank_fit_scenario_label = "Escenario actual"


    with scenarios_tab:
        # ====================================================
        # SCENARIO EXPLORATION
        # ====================================================

        st.subheader("Explorar escenarios")
        st.caption(
            "Modifica una variable y observa cómo cambia la estructura "
            "financiera. Esta sección simula escenarios libres; no "
            "recalcula la recomendación principal."
        )

        sensitivity_variable = st.selectbox(
            "Variable a modificar",
            [
                "Tipo de interés",
                "Ingresos mensuales",
                "Entrada",
                "Precio",
                "Plazo",
                "Tasación y financiación",
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
                interest_rate_annual=D(new_rate) / D("100"),
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

        elif sensitivity_variable == "Tasación y financiación":
            base_appraisal_pct = (
                float(scenario.appraisal_value / scenario.property_price) * 100
                if scenario.appraisal_value is not None
                and scenario.property_price > 0
                else 100.0
            )
            new_appraisal_pct = st.slider(
                "Tasación esperada respecto al precio (%)",
                min_value=80.0,
                max_value=120.0,
                value=float(round(base_appraisal_pct)),
                step=1.0,
                key="sens_appraisal_pct",
            )
            financing_pct = st.slider(
                "Financiación sobre tasación (%)",
                min_value=50.0,
                max_value=100.0,
                value=80.0,
                step=1.0,
                key="sens_financing_pct",
            )

            simulated_appraisal = (
                scenario.property_price * D(new_appraisal_pct) / D("100")
            )
            simulated_loan = min(
                scenario.property_price,
                simulated_appraisal * D(financing_pct) / D("100"),
            )
            simulated_down = scenario.property_price - simulated_loan
            sensitivity_scenario = replace(
                scenario,
                appraisal_value=simulated_appraisal,
                requested_loan_amount=simulated_loan,
                planned_down_payment=simulated_down,
            )

        sensitivity_result = calculate_financial_scenario(
            sensitivity_scenario,
            defaults=defaults,
        )

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.metric("Cuota", money_text(sensitivity_result.monthly_payment))
        with s2:
            st.metric(
                "Ratio de endeudamiento (DSTI)",
                pct_text(sensitivity_result.dsti),
            )
        with s3:
            st.metric(
                "Financiación sobre valor (LTV)",
                pct_text(ltv_value(sensitivity_result)),
            )
        with s4:
            st.metric(
                "Déficit de liquidez",
                money_text(sensitivity_result.cash_gap),
            )

        if sensitivity_variable == "Tasación y financiación":
            st.markdown("#### Estructura resultante")
            f1, f2, f3, f4 = st.columns(4)
            with f1:
                st.metric(
                    "Tasación estimada",
                    money_text(sensitivity_scenario.appraisal_value),
                )
            with f2:
                st.metric(
                    "Hipoteca simulada",
                    money_text(sensitivity_scenario.requested_loan_amount),
                )
            with f3:
                st.metric(
                    "Entrada necesaria",
                    money_text(sensitivity_scenario.planned_down_payment),
                )
            with f4:
                financing_vs_price = (
                    sensitivity_scenario.requested_loan_amount
                    / sensitivity_scenario.property_price
                )
                st.metric(
                    "Financiación / precio",
                    pct_text(financing_vs_price),
                )

            financing_vs_appraisal = (
                sensitivity_scenario.requested_loan_amount
                / sensitivity_scenario.appraisal_value
                if sensitivity_scenario.appraisal_value
                and sensitivity_scenario.appraisal_value > 0
                else None
            )
            st.caption(
                "Financiación sobre tasación: "
                f"{pct_text(financing_vs_appraisal)} · Simulación "
                "orientativa: la concesión real depende de la política "
                "y condiciones de cada entidad."
            )
