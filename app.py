import streamlit as st


def _safe_plotly_chart(fig, *args, **kwargs):
    """Temporary lightweight fallback for Streamlit Cloud stability."""
    rows = []
    for trace in getattr(fig, "data", []):
        name = getattr(trace, "name", "")
        x_values = list(getattr(trace, "x", []) or [])
        text_values = list(getattr(trace, "text", []) or [])
        for label, value_text in zip(x_values, text_values):
            rows.append(
                {
                    "Métrica": label,
                    "Escenario": name,
                    "Valor": value_text,
                }
            )

    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("Comparación gráfica temporalmente simplificada.")


# Plotly caused instability in the first Community Cloud deployment.
# Keep the presentation logic intact while using a native Streamlit fallback.
st.plotly_chart = _safe_plotly_chart

from app_ui import *  # noqa: F401,F403,E402
