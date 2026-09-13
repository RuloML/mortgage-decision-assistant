from pathlib import Path

SOURCE = Path(__file__).with_name("app_ui.py").read_text(encoding="utf-8")

SOURCE = SOURCE.replace(
    'categories = [\n        "Ratio de endeudamiento (DSTI)",\n        "Financiación sobre valor (LTV)",\n    ]',
    'categories = [\n        "Ratio de endeudamiento",\n        "Financiación sobre valor",\n    ]',
)

SOURCE = SOURCE.replace(
    'st.markdown("#### Impacto financiero")',
    'st.markdown("#### Impacto financiero: actual vs recomendado")\n'
    '    st.caption(\n'
    '        "Comparación del ratio de endeudamiento y de la financiación "\n'
    '        "sobre valor."\n'
    '    )',
)

SOURCE = SOURCE.replace(
    'use_container_width=True,',
    'width="stretch",',
)

exec(compile(SOURCE, str(Path(__file__).with_name("app_ui.py")), "exec"), globals())
